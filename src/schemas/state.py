# Copyright (c) Microsoft. All rights reserved.
"""
State Schemas for LangGraph Agents

Defines the shared state structure that flows through the agent graph.
LangGraph uses typed state to enable:
- Type-safe state transitions
- Automatic state persistence
- Clear data contracts between agents
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================

class IngestionStatus(str, Enum):
    """Status of the code ingestion process."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportType(str, Enum):
    """Type of comprehension report."""
    BUSINESS = "business"
    TECHNICAL = "technical"


class RiskSeverity(str, Enum):
    """Severity level for identified risks."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class EffortBand(str, Enum):
    """Effort estimation bands."""
    SMALL = "S"
    MEDIUM = "M"
    LARGE = "L"
    EXTRA_LARGE = "XL"


# =============================================================================
# SUB-MODELS
# =============================================================================

class FileInfo(BaseModel):
    """Information about a file in the repository."""
    path: str
    language: str | None = None
    size_bytes: int = 0
    classification: str | None = None  # code, config, docs, iac, cicd, tests
    checksum: str | None = None


class DependencyInfo(BaseModel):
    """Information about a dependency."""
    name: str
    version: str | None = None
    package_manager: str  # npm, pip, maven, gradle, cargo, go
    is_dev: bool = False
    vulnerabilities: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    """A single risk identified in the codebase."""
    id: str
    category: str  # security, tech_debt, compliance, reliability, operability
    severity: RiskSeverity
    title: str
    description: str
    evidence_uri: str | None = None
    remediation: str | None = None
    effort: EffortBand | None = None


class IngestionPolicy(BaseModel):
    """Policy for code ingestion."""
    max_file_mb: float = 2.0
    exclude_globs: list[str] = Field(default_factory=lambda: [
        "**/*.pem", "**/*.key", "**/.env", 
        "dist/**", "build/**", "node_modules/**",
        "**/*.jar", "**/*.zip", "**/*.pdf",
    ])
    include_tests: bool = True
    redact_secrets: bool = True


class IndexingProfile(BaseModel):
    """Profile for indexing operations."""
    code_embeddings: bool = True
    doc_embeddings: bool = True
    test_discovery: bool = True


class BusinessContext(BaseModel):
    """Business context for architecture analysis."""
    objective: str
    constraints: list[str] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list)
    compliance_requirements: list[str] = Field(default_factory=list)  # GDPR, PCI, etc.


class TargetArchitecture(BaseModel):
    """Target architecture specification."""
    platforms: list[str] = Field(default_factory=list)  # Azure AKS, SQL MI, etc.
    patterns: list[str] = Field(default_factory=list)  # CQRS, event-driven, etc.


# =============================================================================
# REPO BUNDLE - Output from Code Ingestion Agent
# =============================================================================

class RepoBundle(BaseModel):
    """
    Knowledge bundle produced by the Code Ingestion Agent.
    This is the primary artifact passed to the Architect Agent.
    """
    # Metadata
    repo_url: str
    ref: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Repository structure
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    build_systems: list[str] = Field(default_factory=list)
    
    # File inventory
    files: list[FileInfo] = Field(default_factory=list)
    total_files: int = 0
    total_size_bytes: int = 0
    
    # Dependencies
    dependencies: list[DependencyInfo] = Field(default_factory=list)
    
    # Classified content (URIs or summaries)
    code_files: list[str] = Field(default_factory=list)
    config_files: list[str] = Field(default_factory=list)
    doc_files: list[str] = Field(default_factory=list)
    iac_files: list[str] = Field(default_factory=list)
    cicd_files: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)
    
    # Risks identified during ingestion
    risks: list[RiskItem] = Field(default_factory=list)
    
    # Ingestion stats
    files_ingested: int = 0
    files_excluded: int = 0
    secrets_redacted: int = 0
    
    # Policy used
    ingestion_policy: IngestionPolicy = Field(default_factory=IngestionPolicy)


# =============================================================================
# COMPREHENSION REPORTS - Output from Architect Agent
# =============================================================================

class OptionItem(BaseModel):
    """A solution option in the options matrix."""
    id: str
    name: str
    description: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    effort: EffortBand
    risk_level: RiskSeverity
    recommended: bool = False


class MigrationWave(BaseModel):
    """A migration wave in the migration plan."""
    wave_number: int
    name: str
    duration_weeks: int
    tasks: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    rollback_plan: str | None = None


class BacklogItem(BaseModel):
    """A backlog item for the next sprints."""
    id: str
    title: str
    description: str
    effort: EffortBand
    linked_risk_id: str | None = None
    sprint: int  # 1 or 2


class BusinessReport(BaseModel):
    """Business Comprehension Report for Executives."""
    executive_summary: str
    current_state: str
    options: list[OptionItem] = Field(default_factory=list)
    value_and_kpis: str
    adoption_plan: str
    diagram_mermaid: str | None = None


class TechnicalReport(BaseModel):
    """Technical Comprehension Report for Architects."""
    codebase_map: str
    topology: str
    security_compliance: str
    nfrs: str  # Non-functional requirements
    risk_register: list[RiskItem] = Field(default_factory=list)
    target_architecture: str
    architecture_diagram_mermaid: str | None = None
    migration_plan: list[MigrationWave] = Field(default_factory=list)
    backlog_slice: list[BacklogItem] = Field(default_factory=list)


# =============================================================================
# MAIN GRAPH STATE
# =============================================================================

class AgentState(BaseModel):
    """
    Main state schema for the LangGraph agent workflow.
    
    This state flows through all agents and accumulates results.
    Using Pydantic models enables:
    - Type validation
    - Automatic serialization for checkpointing
    - Clear documentation of state structure
    """
    
    # Message history (uses LangGraph's add_messages reducer)
    messages: Annotated[list[AnyMessage], add_messages] = Field(default_factory=list)
    
    # Input parameters
    repo_url: str | None = None
    ref: str = "main"
    path_filters: list[str] = Field(default_factory=list)
    ingestion_policy: IngestionPolicy = Field(default_factory=IngestionPolicy)
    indexing_profile: IndexingProfile = Field(default_factory=IndexingProfile)
    
    # Business context for Architect Agent
    business_context: BusinessContext | None = None
    target_architecture: TargetArchitecture | None = None
    report_audience: list[str] = Field(default_factory=lambda: ["Exec", "Architect"])
    
    # Ingestion state
    ingestion_status: IngestionStatus = IngestionStatus.PENDING
    repo_bundle: RepoBundle | None = None
    
    # Report outputs
    business_report: BusinessReport | None = None
    technical_report: TechnicalReport | None = None
    
    # Workflow metadata
    current_agent: str | None = None
    error: str | None = None
    completed: bool = False


# =============================================================================
# TYPE ALIASES for LangGraph
# =============================================================================

# For use with TypedDict if needed (LangGraph supports both)
from typing import TypedDict


class AgentStateDict(TypedDict, total=False):
    """TypedDict version for LangGraph compatibility."""
    messages: Annotated[list[AnyMessage], add_messages]
    repo_url: str | None
    ref: str
    path_filters: list[str]
    ingestion_policy: dict
    indexing_profile: dict
    business_context: dict | None
    target_architecture: dict | None
    report_audience: list[str]
    ingestion_status: str
    repo_bundle: dict | None
    business_report: dict | None
    technical_report: dict | None
    current_agent: str | None
    error: str | None
    completed: bool
