# Copyright (c) Microsoft. All rights reserved.
"""
Code Ingestion Agent - LangGraph Node

This agent ingests a GitHub repository and produces a RepoBundle
containing classified files, dependencies, and initial risk assessment.

Implements the Code Ingestion Agent prompt as a LangGraph node.
"""

import asyncio
import json
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from src.llm import get_code_ingestion_llm
from src.observability import (
    GitHubError,
    IngestionError,
    LLMError,
    LogContext,
    PerformanceTracker,
    get_logger,
    metrics,
    track_performance,
)
from src.schemas import (
    AgentState,
    DependencyInfo,
    FileInfo,
    IngestionStatus,
    RepoBundle,
    RiskItem,
    RiskSeverity,
)
from src.services import get_github_service

# Initialize logger
logger = get_logger(__name__)


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

CODE_INGESTION_SYSTEM_PROMPT = """You are **Code-Ingestion-Agent**, a specialised AI module in an enterprise Application Modernisation Workbench.

## ROLE
Read-only codebase extraction and classification.

## RESPONSIBILITIES
1. **Ingest** source repositories via GitHub API (read-only: no writes, no code execution).
2. **Classify** files into standard buckets:
   - source-code, config, docs, IaC, CI/CD, tests, assets, other.
3. **Build manifest**:
   - languages, frameworks, build-systems, folder-tree, dependency graphs, test inventory.
4. **Detect secrets / PII** and redact or flag before hand-off.
5. **Publish** a knowledge bundle (embeddings-ready) to the Comprehension Layer (in-memory or RAG store).

## PERMITTED API CALLS
| Method | Description |
|--------|-------------|
| get_file(path, ref) | Return UTF-8 content (max 2 MB). |
| search(query, scope, ref) | Full-text / regex within scope=file|repo. |
| list_dependencies(manifest) | Parse package.json / pom.xml / *.csproj / requirements.txt etc. |
| list_tests(path, ref) | Enumerate test classes/methods. |
| get_manifest() | Return JSON manifest built so far. |
| get_risks() | Return list of flagged secrets / large binaries / known CVEs. |

## INPUT CONTRACT (per request)
```yaml
repo_url: https://github.com/<org>/<repo>
ref: main | <branch> | <tag> | <commit>
path_filters: ["src/**", "!vendor/**"]   # optional globs
ingestion_policy:
  max_file_mb: 2
  exclude_globs: ["*.pem","*.key",".env"]
  include_tests: true
  redact_secrets: true
indexing_profile:
  code_embeddings: true
  doc_embeddings: true
  test_discovery: true
```

## OUTPUT CONTRACT → Comprehension Layer
```yaml
bundle_id: <uuid>
repo_url: <url>
ref: <ref>
timestamp: <iso8601>
manifest:
  languages: [Python, JavaScript, ...]
  frameworks: [Flask, React, ...]
  build_systems: [pip, npm, ...]
  folder_tree: {...}
  dependency_graph: {...}
  test_inventory: {...}
classified_content:
  code:   [uri_list]
  config: [uri_list]
  docs:   [uri_list]
  iac:    [uri_list]
  cicd:   [uri_list]
  tests:  [uri_list]
risks:
  - type: secret
    path: .env.production
    severity: critical
embeddings_pointer: <vector_store_collection_id>  # optional
```

## EXECUTION STEPS
A) Validate inputs; reject if repo_url inaccessible or policy missing.
B) Clone / shallow-fetch; apply exclusions.
C) Walk tree, classify each file by extension + heuristics.
D) Extract dependencies from known manifests.
E) Run secret scanner; redact or flag.
F) Emit bundle JSON + optional chunked content for embedding.

## GUARDRAILS
- NEVER commit, push, or modify remote.
- NEVER execute build scripts / tests.
- Timeout per file: 10 s; total ingestion: 10 min.
- If any file is unreadable, log and skip (do not halt).
"""


# =============================================================================
# ANALYSIS PROMPT for LLM
# =============================================================================

ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are analyzing a code repository to identify:
1. Programming languages and their approximate percentages
2. Frameworks and libraries in use
3. Build systems and package managers
4. Potential risks (outdated deps, security concerns, tech debt indicators)

Analyze the following repository structure and dependency information."""),
    ("human", """Repository: {repo_url}
Branch/Ref: {ref}

Files discovered ({file_count} total):
{file_summary}

Dependencies found ({dep_count} total):
{dependency_summary}

Based on this information, provide your analysis in the following JSON format:
{{
    "languages": ["lang1", "lang2"],
    "frameworks": ["framework1", "framework2"],
    "build_systems": ["system1", "system2"],
    "risks": [
        {{
            "id": "RISK-001",
            "category": "security|tech_debt|compliance",
            "severity": "critical|high|medium|low",
            "title": "Brief title",
            "description": "Detailed description",
            "remediation": "Suggested fix"
        }}
    ]
}}"""),
])


# =============================================================================
# AGENT NODE
# =============================================================================

@track_performance("code_ingestion")
async def code_ingestion_node(state: AgentState) -> dict:
    """
    LangGraph node for Code Ingestion Agent.
    
    This node:
    1. Validates input parameters
    2. Connects to GitHub and lists files
    3. Classifies files and discovers dependencies
    4. Uses LLM to analyze the codebase
    5. Produces a RepoBundle
    
    Args:
        state: Current graph state
        
    Returns:
        State updates with repo_bundle and status
    """
    with LogContext(agent="code_ingestion", repo_url=state.repo_url, ref=state.ref):
        logger.info("ingestion_started")
        
        # Initialize
        github = get_github_service()
        llm = get_code_ingestion_llm()
        
        # Track messages
        messages = list(state.messages)
        messages.append(SystemMessage(content=CODE_INGESTION_SYSTEM_PROMPT))
        
        try:
            # Validate inputs
            if not state.repo_url:
                logger.error("validation_failed", reason="repo_url required")
                return {
                    "ingestion_status": IngestionStatus.FAILED,
                    "error": "repo_url is required",
                    "messages": messages + [AIMessage(content="Error: repo_url is required")],
                }
            
            messages.append(HumanMessage(content=f"Ingesting repository: {state.repo_url} (ref: {state.ref})"))
            
            # Get repository
            logger.info("fetching_repository")
            try:
                repo = github.get_repository(state.repo_url)
                logger.info("repository_found", repo_name=repo.full_name)
            except Exception as e:
                logger.error("github_error", error=str(e))
                metrics.increment("ingestion_errors", tags={"type": "github"})
                raise GitHubError(f"Failed to access repository: {e}", repo_url=state.repo_url, cause=e)
            
            # List and classify files
            logger.info("listing_files")
            files: list[FileInfo] = []
            code_files, config_files, doc_files = [], [], []
            iac_files, cicd_files, test_files = [], [], []
            
            total_size = 0
            excluded_count = 0
            secrets_redacted = 0
            
            with PerformanceTracker("file_discovery", logger) as tracker:
                async for file_info in github.list_files(
                    repo,
                    ref=state.ref,
                    policy=state.ingestion_policy,
                ):
                    files.append(file_info)
                    total_size += file_info.size_bytes
                    
                    # Classify into buckets
                    if file_info.classification == "code":
                        code_files.append(file_info.path)
                    elif file_info.classification == "config":
                        config_files.append(file_info.path)
                    elif file_info.classification == "docs":
                        doc_files.append(file_info.path)
                    elif file_info.classification == "iac":
                        iac_files.append(file_info.path)
                    elif file_info.classification == "cicd":
                        cicd_files.append(file_info.path)
                    elif file_info.classification == "tests":
                        test_files.append(file_info.path)
                
                tracker.add_metadata(files_found=len(files), total_size_bytes=total_size)
            
            logger.info("files_discovered", count=len(files), total_size_mb=round(total_size / 1024 / 1024, 2))
            metrics.gauge("files_processed", len(files))
            
            # Discover dependencies
            logger.info("discovering_dependencies")
            dependencies = await github.discover_dependencies(repo, ref=state.ref)
            logger.info("dependencies_found", count=len(dependencies))
            
            # Build summaries for LLM analysis
            language_counts: dict[str, int] = {}
            for f in files:
                if f.language:
                    language_counts[f.language] = language_counts.get(f.language, 0) + 1
            
            file_summary = "\n".join([
                f"- {lang}: {count} files"
                for lang, count in sorted(language_counts.items(), key=lambda x: -x[1])[:10]
            ])
            
            dependency_summary = "\n".join([
                f"- {d.name} ({d.package_manager}): {d.version or 'unknown'}"
                for d in dependencies[:20]
            ])
            
            # Use LLM to analyze and identify risks
            logger.info("invoking_llm_analysis")
            with PerformanceTracker("llm_analysis", logger):
                analysis_prompt = ANALYSIS_PROMPT.format(
                    repo_url=state.repo_url,
                    ref=state.ref,
                    file_count=len(files),
                    file_summary=file_summary or "No files classified by language",
                    dep_count=len(dependencies),
                    dependency_summary=dependency_summary or "No dependencies found",
                )
                
                try:
                    analysis_response = await llm.ainvoke([HumanMessage(content=str(analysis_prompt))])
                except Exception as e:
                    logger.error("llm_error", error=str(e))
                    metrics.increment("ingestion_errors", tags={"type": "llm"})
                    raise LLMError(f"LLM analysis failed: {e}", cause=e)
            
            # Parse LLM response (simplified - in production use structured output)
            try:
                # Extract JSON from response
                response_text = analysis_response.content
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    analysis = json.loads(response_text[json_start:json_end])
                else:
                    logger.warning("llm_response_no_json", response_preview=response_text[:200])
                    analysis = {"languages": [], "frameworks": [], "build_systems": [], "risks": []}
            except json.JSONDecodeError as e:
                logger.warning("llm_response_parse_error", error=str(e))
                analysis = {"languages": [], "frameworks": [], "build_systems": [], "risks": []}
            
            # Build risks from analysis
            risks = [
                RiskItem(
                    id=r.get("id", f"RISK-{i:03d}"),
                    category=r.get("category", "tech_debt"),
                    severity=RiskSeverity(r.get("severity", "medium")),
                    title=r.get("title", "Unknown risk"),
                    description=r.get("description", ""),
                    remediation=r.get("remediation"),
                )
                for i, r in enumerate(analysis.get("risks", []))
            ]
            
            logger.info("risks_identified", count=len(risks))
            
            # Create RepoBundle
            repo_bundle = RepoBundle(
                repo_url=state.repo_url,
                ref=state.ref,
                timestamp=datetime.utcnow(),
                languages=analysis.get("languages", list(language_counts.keys())),
                frameworks=analysis.get("frameworks", []),
                build_systems=analysis.get("build_systems", []),
                files=files,
                total_files=len(files),
                total_size_bytes=total_size,
                dependencies=dependencies,
                code_files=code_files,
                config_files=config_files,
                doc_files=doc_files,
                iac_files=iac_files,
                cicd_files=cicd_files,
                test_files=test_files,
                risks=risks,
                files_ingested=len(files),
                files_excluded=excluded_count,
                secrets_redacted=secrets_redacted,
                ingestion_policy=state.ingestion_policy,
            )
            
            # Success message
            success_msg = f"""Repository ingestion complete:
- Files: {len(files)} ingested, {excluded_count} excluded
- Languages: {', '.join(repo_bundle.languages[:5])}
- Frameworks: {', '.join(repo_bundle.frameworks[:5]) or 'None detected'}
- Dependencies: {len(dependencies)}
- Risks identified: {len(risks)}"""
            
            messages.append(AIMessage(content=success_msg))
            
            logger.info(
                "ingestion_completed",
                files=len(files),
                languages=repo_bundle.languages[:5],
                frameworks=repo_bundle.frameworks[:5],
                risks=len(risks),
            )
            metrics.increment("ingestion_success")
            
            return {
                "ingestion_status": IngestionStatus.COMPLETED,
                "repo_bundle": repo_bundle,
                "messages": messages,
                "current_agent": "code_ingestion",
                "error": None,
            }
            
        except (GitHubError, IngestionError, LLMError) as e:
            error_msg = f"Ingestion failed: {e.message}"
            logger.error("ingestion_failed", error_code=e.error_code, message=e.message)
            messages.append(AIMessage(content=error_msg))
            metrics.increment("ingestion_failed")
            
            return {
                "ingestion_status": IngestionStatus.FAILED,
                "error": error_msg,
                "messages": messages,
                "current_agent": "code_ingestion",
            }
            
        except Exception as e:
            error_msg = f"Ingestion failed: {str(e)}"
            logger.exception("ingestion_unexpected_error")
            messages.append(AIMessage(content=error_msg))
            metrics.increment("ingestion_failed")
            
            return {
                "ingestion_status": IngestionStatus.FAILED,
                "error": error_msg,
                "messages": messages,
                "current_agent": "code_ingestion",
            }


# =============================================================================
# SYNC WRAPPER (for non-async contexts)
# =============================================================================

def code_ingestion_node_sync(state: AgentState) -> dict:
    """Synchronous wrapper for code ingestion node."""
    return asyncio.run(code_ingestion_node(state))
