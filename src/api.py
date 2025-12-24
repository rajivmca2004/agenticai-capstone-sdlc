# Copyright (c) Microsoft. All rights reserved.
"""
REST API for Code Comprehension Agents

Provides HTTP endpoints to trigger the LangGraph workflow.
Includes production-grade logging, error handling, and observability.
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.graph import create_comprehension_graph, stream_comprehension_workflow
from src.observability import (
    CodeComprehensionError,
    JobNotFoundError,
    LogContext,
    PerformanceTracker,
    get_correlation_id,
    get_logger,
    metrics,
    new_correlation_id,
    set_correlation_id,
)
from src.schemas import (
    AgentState,
    BusinessContext,
    IngestionPolicy,
    IngestionStatus,
    TargetArchitecture,
)

# Initialize logger
logger = get_logger(__name__)


# =============================================================================
# MODELS
# =============================================================================

class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ComprehensionRequest(BaseModel):
    """Request to analyze a repository."""
    repo_url: str = Field(..., description="GitHub repository URL")
    ref: str = Field(default="main", description="Git reference (branch/tag/commit)")
    
    # Optional business context
    business_objective: str | None = Field(default=None, description="Business objective")
    constraints: list[str] = Field(default_factory=list, description="Business constraints")
    kpis: list[str] = Field(default_factory=list, description="Target KPIs")
    compliance: list[str] = Field(default_factory=list, description="Compliance requirements")
    
    # Optional target architecture
    target_platforms: list[str] = Field(default_factory=list, description="Target platforms")
    target_patterns: list[str] = Field(default_factory=list, description="Architecture patterns")
    
    # Ingestion options
    include_tests: bool = Field(default=True, description="Include test files")
    max_file_mb: float = Field(default=2.0, description="Max file size in MB")


class JobResponse(BaseModel):
    """Response for job creation."""
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime


class JobStatusResponse(BaseModel):
    """Response for job status query."""
    job_id: str
    status: JobStatus
    progress: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    agents: list[str]


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    correlation_id: str
    details: dict[str, Any] | None = None


# =============================================================================
# JOB STORAGE (In-memory for POC)
# =============================================================================

jobs: dict[str, dict[str, Any]] = {}


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

async def code_comprehension_exception_handler(
    request: Request, exc: CodeComprehensionError
) -> JSONResponse:
    """Handle domain-specific exceptions."""
    correlation_id = get_correlation_id()
    logger.error(
        "domain_error",
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        path=str(request.url.path),
    )
    metrics.increment("api_errors", tags={"error_code": exc.error_code})
    
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "correlation_id": correlation_id,
            "details": exc.details,
        },
    )


async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions."""
    correlation_id = get_correlation_id()
    logger.exception(
        "unhandled_error",
        error_type=type(exc).__name__,
        error_message=str(exc),
        path=str(request.url.path),
    )
    metrics.increment("api_errors", tags={"error_code": "INTERNAL_ERROR"})
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "correlation_id": correlation_id,
            "details": {"error_type": type(exc).__name__},
        },
    )


# =============================================================================
# APP SETUP
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("api_starting", version="0.2.0", agents=["code_ingestion", "architect"])
    yield
    # Shutdown
    logger.info("api_shutdown")


app = FastAPI(
    title="Code Comprehension API",
    description="REST API for multi-agent code comprehension using LangGraph",
    version="0.2.0",
    lifespan=lifespan,
)

# Register exception handlers
app.add_exception_handler(CodeComprehensionError, code_comprehension_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# REQUEST MIDDLEWARE
# =============================================================================

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Add correlation ID to all requests."""
    # Get or generate correlation ID
    correlation_id = request.headers.get("X-Correlation-ID", "")
    if correlation_id:
        set_correlation_id(correlation_id)
    else:
        correlation_id = new_correlation_id()
    
    # Track request timing
    start_time = time.perf_counter()
    
    # Log request
    logger.info(
        "request_started",
        method=request.method,
        path=str(request.url.path),
        query=str(request.url.query) if request.url.query else None,
    )
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration_ms = (time.perf_counter() - start_time) * 1000
    
    # Log response
    logger.info(
        "request_completed",
        method=request.method,
        path=str(request.url.path),
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    
    # Track metrics
    metrics.increment("api_requests", tags={
        "method": request.method,
        "path": str(request.url.path),
        "status": str(response.status_code),
    })
    metrics.histogram("api_request_duration_ms", duration_ms, tags={
        "path": str(request.url.path),
    })
    
    # Add correlation ID to response
    response.headers["X-Correlation-ID"] = correlation_id
    
    return response


# =============================================================================
# BACKGROUND TASK
# =============================================================================

async def run_comprehension_job(job_id: str, request: ComprehensionRequest):
    """Run comprehension workflow as background task."""
    # Set correlation ID for this job
    set_correlation_id(job_id)
    
    with LogContext(job_id=job_id, repo_url=request.repo_url):
        logger.info("job_started", request=request.model_dump())
        
        jobs[job_id]["status"] = JobStatus.RUNNING
        jobs[job_id]["progress"] = {"current_agent": None, "messages": []}
        
        with PerformanceTracker("comprehension_workflow", logger) as tracker:
            tracker.add_metadata(repo_url=request.repo_url, ref=request.ref)
            
            try:
                # Build initial state
                business_context = None
                if request.business_objective:
                    business_context = BusinessContext(
                        objective=request.business_objective,
                        constraints=request.constraints,
                        kpis=request.kpis,
                        compliance_requirements=request.compliance,
                    )
                
                target_arch = None
                if request.target_platforms:
                    target_arch = TargetArchitecture(
                        platforms=request.target_platforms,
                        patterns=request.target_patterns,
                    )
                
                initial_state = AgentState(
                    repo_url=request.repo_url,
                    ref=request.ref,
                    business_context=business_context,
                    target_architecture=target_arch,
                    ingestion_policy=IngestionPolicy(
                        include_tests=request.include_tests,
                        max_file_mb=request.max_file_mb,
                    ),
                )
                
                # Run graph
                graph = create_comprehension_graph()
                config = {"configurable": {"thread_id": job_id}}
                
                final_state = None
                async for event in graph.astream(initial_state, config):
                    for node_name, state_update in event.items():
                        jobs[job_id]["progress"]["current_agent"] = node_name
                        logger.info("agent_progress", agent=node_name)
                        
                        if "messages" in state_update:
                            for msg in state_update.get("messages", []):
                                if hasattr(msg, "content"):
                                    jobs[job_id]["progress"]["messages"].append({
                                        "agent": node_name,
                                        "content": msg.content[:500],
                                    })
                        final_state = state_update
                
                # Extract results
                result = {}
                if final_state:
                    if hasattr(final_state, "repo_bundle") and final_state.repo_bundle:
                        bundle = final_state.repo_bundle
                        result["repo_bundle"] = {
                            "repo_url": bundle.repo_url,
                            "ref": bundle.ref,
                            "languages": bundle.languages,
                            "frameworks": bundle.frameworks,
                            "total_files": bundle.total_files,
                            "dependencies_count": len(bundle.dependencies),
                            "risks_count": len(bundle.risks),
                        }
                        tracker.add_metadata(
                            files_processed=bundle.total_files,
                            risks_found=len(bundle.risks),
                        )
                    
                    if hasattr(final_state, "business_report") and final_state.business_report:
                        report = final_state.business_report
                        result["business_report"] = {
                            "executive_summary": report.executive_summary,
                            "options_count": len(report.options),
                            "diagram": report.diagram_mermaid,
                        }
                    
                    if hasattr(final_state, "technical_report") and final_state.technical_report:
                        report = final_state.technical_report
                        result["technical_report"] = {
                            "codebase_map": report.codebase_map[:500] if report.codebase_map else None,
                            "risks_count": len(report.risk_register),
                            "migration_waves": len(report.migration_plan),
                            "backlog_items": len(report.backlog_slice),
                            "diagram": report.architecture_diagram_mermaid,
                        }
                
                jobs[job_id]["status"] = JobStatus.COMPLETED
                jobs[job_id]["result"] = result
                jobs[job_id]["completed_at"] = datetime.utcnow()
                
                logger.info("job_completed", result_summary=list(result.keys()))
                metrics.increment("jobs_completed", tags={"status": "success"})
                
            except Exception as e:
                logger.exception("job_failed", error=str(e))
                jobs[job_id]["status"] = JobStatus.FAILED
                jobs[job_id]["error"] = str(e)
                jobs[job_id]["completed_at"] = datetime.utcnow()
                metrics.increment("jobs_completed", tags={"status": "failed"})


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.2.0",
        agents=["code_ingestion", "architect"],
    )


@app.get("/metrics", tags=["Health"])
async def get_metrics():
    """Get application metrics."""
    return metrics.get_metrics()


@app.post("/analyze", response_model=JobResponse, tags=["Analysis"])
async def start_analysis(
    request: ComprehensionRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start repository analysis.
    
    This triggers the full comprehension workflow:
    1. Code Ingestion Agent - fetches and classifies repo
    2. Architect Agent - generates business & technical reports
    
    Returns a job ID to track progress.
    """
    job_id = str(uuid.uuid4())
    
    logger.info(
        "analysis_requested",
        repo_url=request.repo_url,
        ref=request.ref,
        include_tests=request.include_tests,
    )
    
    jobs[job_id] = {
        "status": JobStatus.PENDING,
        "request": request.model_dump(),
        "created_at": datetime.utcnow(),
        "completed_at": None,
        "progress": None,
        "result": None,
        "error": None,
        "correlation_id": get_correlation_id(),
    }
    
    # Run in background
    background_tasks.add_task(run_comprehension_job, job_id, request)
    
    metrics.increment("jobs_created")
    
    return JobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message=f"Analysis started for {request.repo_url}",
        created_at=jobs[job_id]["created_at"],
    )


@app.get("/analyze/{job_id}", response_model=JobStatusResponse, tags=["Analysis"])
async def get_analysis_status(job_id: str):
    """Get the status of an analysis job."""
    if job_id not in jobs:
        logger.warning("job_not_found", job_id=job_id)
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        result=job.get("result"),
        error=job.get("error"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
    )


@app.get("/jobs", tags=["Analysis"])
async def list_jobs():
    """List all analysis jobs."""
    logger.debug("listing_jobs", count=len(jobs))
    return [
        {
            "job_id": job_id,
            "status": job["status"],
            "repo_url": job["request"]["repo_url"],
            "created_at": job["created_at"],
        }
        for job_id, job in jobs.items()
    ]


@app.delete("/analyze/{job_id}", tags=["Analysis"])
async def delete_job(job_id: str):
    """Delete an analysis job."""
    if job_id not in jobs:
        logger.warning("job_not_found", job_id=job_id)
        raise HTTPException(status_code=404, detail="Job not found")
    
    del jobs[job_id]
    logger.info("job_deleted", job_id=job_id)
    return {"message": f"Job {job_id} deleted"}


# =============================================================================
# SYNC ENDPOINTS (for simple use cases)
# =============================================================================

@app.post("/analyze/sync", tags=["Analysis"])
async def analyze_sync(request: ComprehensionRequest):
    """
    Synchronous analysis (waits for completion).
    
    ⚠️ Warning: This may timeout for large repositories.
    Use the async /analyze endpoint for large repos.
    """
    job_id = str(uuid.uuid4())
    
    logger.info(
        "sync_analysis_requested",
        repo_url=request.repo_url,
        ref=request.ref,
    )
    
    jobs[job_id] = {
        "status": JobStatus.RUNNING,
        "request": request.model_dump(),
        "created_at": datetime.utcnow(),
        "correlation_id": get_correlation_id(),
    }
    
    # Run synchronously
    await run_comprehension_job(job_id, request)
    
    job = jobs[job_id]
    if job["status"] == JobStatus.FAILED:
        logger.error("sync_analysis_failed", job_id=job_id, error=job.get("error"))
        raise HTTPException(status_code=500, detail=job.get("error", "Unknown error"))
    
    return {
        "job_id": job_id,
        "status": job["status"],
        "result": job.get("result"),
    }


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
