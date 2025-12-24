# Copyright (c) Microsoft. All rights reserved.
"""
Architect Agent - LangGraph Node

This agent consumes a RepoBundle from the Code Ingestion Agent and produces
Business and Technical Comprehension Reports.

Implements the Architect Agent prompt as a LangGraph node.
"""

import asyncio
import json
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from src.llm import get_architect_llm
from src.observability import (
    ArchitectError,
    LLMError,
    LogContext,
    MissingRepoBundleError,
    PerformanceTracker,
    ReportGenerationError,
    get_logger,
    metrics,
    track_performance,
)
from src.schemas import (
    AgentState,
    BacklogItem,
    BusinessReport,
    EffortBand,
    MigrationWave,
    OptionItem,
    RiskItem,
    RiskSeverity,
    TechnicalReport,
)

# Initialize logger
logger = get_logger(__name__)


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

ARCHITECT_SYSTEM_PROMPT = """You are **Architect-Agent**, a senior solutions architect inside an Application Modernisation Workbench.

## MISSION
Transform the knowledge bundle produced by **Code-Ingestion-Agent** into two complementary comprehension reports—plus supporting artefacts—that enable an organisation to decide *whether*, *how*, and *when* to modernise a legacy codebase.

## OUTPUTS
| Artefact | Audience | Purpose |
|----------|----------|---------|
| **business_report.md** | Exec / PM | Executive-level value story, options, KPIs |
| **technical_report.md** | Architect / Lead Dev | Deep-dive: topology, risks, migration playbook |
| **arch_overview.mmd** | Both | Mermaid diagram (current → target) |
| **risk_register.csv** | Governance | Severity, owner, mitigation, deadline |
| **options_matrix.csv** | Steering | Option comparison with pros/cons/effort |

## INPUT (from bundle)
```yaml
repo_url, ref, manifest, classified_content, risks, embeddings_pointer
```

## ADDITIONAL INPUTS (orchestrator may inject)
```yaml
business_context:
  objective: "migrate to Azure, improve scalability"
  constraints: ["budget < $500k", "6-month runway"]
  kpis: ["reduce MTTR by 50%", "achieve 99.9% uptime"]
  compliance: ["GDPR", "PCI-DSS"]
target_architecture:
  platforms: ["Azure AKS", "Azure SQL MI", "Azure Front Door"]
  patterns: ["CQRS", "Event-Driven", "BFF"]
report_audience: ["Exec", "Architect"]
```

## EXECUTION STEPS
1. **Analyse bundle** – summarise languages, frameworks, dependencies, test coverage hints, CI/CD maturity.
2. **Risk synthesis** – merge ingestion risks with architecture / security observations; score each (Critical → Info).
3. **Current-state diagram** – Mermaid C4-style context or container view.
4. **Options generation** – min 2, max 5 migration/modernisation pathways (Rehost, Refactor, Rearchitect, Rebuild, Replace).
5. **Target-state diagram** – for the recommended option.
6. **Migration plan skeleton** – waves, dependencies, rollback hooks.
7. **Backlog slice** – top 10 epics/stories to feed into Sprint 1-2.
8. **Write reports** – Markdown using templates below.

## BUSINESS REPORT STRUCTURE
```markdown
# Executive Summary
(1 paragraph: problem, recommendation, expected outcome)

# Current State
(brief tech footprint, key pain points)

# Options Analysis
| Option | Description | Pros | Cons | Effort | Risk |
|--------|-------------|------|------|--------|------|
| A      |             |      |      | M      | Med  |
| ...    |             |      |      |        |      |
*Recommended: Option X*

# Value Realisation & KPIs
(mapped to input KPIs)

# Adoption Roadmap
(high-level phases, timeline)

# Appendix
(link to tech report, risk register)
```

## TECHNICAL REPORT STRUCTURE
```markdown
# 1. Codebase Map
(languages %, frameworks, folder rationale)

# 2. Dependency & Integration Topology
(Mermaid diagram + narrative)

# 3. Security & Compliance Posture
(findings mapped to compliance tags)

# 4. Non-Functional Requirements Gap
(scalability, observability, resilience)

# 5. Risk Register (Top 10)
| ID | Category | Severity | Title | Mitigation | Owner | Deadline |

# 6. Target Architecture
(Mermaid diagram + narrative)

# 7. Migration Playbook
## Wave 1 – Foundation (Weeks 1-4)
- Task list, rollback

## Wave 2 – Core Services (Weeks 5-8)
...

# 8. Backlog Slice (Sprint 1-2)
| ID | Title | Effort | Linked Risk |
```

## GUARDRAILS
- Reference bundle data; do not hallucinate file names or dependencies.
- Use *shall* for mandatory, *should* for recommended.
- If information is missing, state "TBD – requires discovery" rather than guessing.
- Keep executive summary ≤ 200 words.
"""


# =============================================================================
# REPORT GENERATION PROMPTS
# =============================================================================

BUSINESS_REPORT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", ARCHITECT_SYSTEM_PROMPT),
    ("human", """Generate the Business Comprehension Report based on the following repository analysis:

Repository: {repo_url}
Branch: {ref}

**Codebase Summary:**
- Languages: {languages}
- Frameworks: {frameworks}
- Build Systems: {build_systems}
- Total Files: {total_files}
- Dependencies: {dep_count}

**Identified Risks ({risk_count}):**
{risk_summary}

**Business Context:**
- Objective: {objective}
- Constraints: {constraints}
- KPIs: {kpis}
- Compliance: {compliance}

**Target Architecture:**
- Platforms: {platforms}
- Patterns: {patterns}

Generate the Business Report following the template structure. Include:
1. Executive Summary (max 200 words)
2. Current State assessment
3. Options Analysis table with at least 3 options
4. Value Realization mapped to provided KPIs
5. High-level Adoption Roadmap

Also provide a Mermaid diagram showing current to target state transformation.

Return your response as JSON:
{{
    "executive_summary": "...",
    "current_state": "...",
    "options": [
        {{
            "id": "A",
            "name": "Option name",
            "description": "...",
            "pros": ["..."],
            "cons": ["..."],
            "effort": "S|M|L|XL",
            "risk_level": "low|medium|high|critical",
            "recommended": true|false
        }}
    ],
    "value_and_kpis": "...",
    "adoption_plan": "...",
    "diagram_mermaid": "graph TD\\n..."
}}"""),
])

TECHNICAL_REPORT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", ARCHITECT_SYSTEM_PROMPT),
    ("human", """Generate the Technical Comprehension Report based on the following repository analysis:

Repository: {repo_url}
Branch: {ref}

**Codebase Details:**
- Languages: {languages}
- Frameworks: {frameworks}
- Build Systems: {build_systems}
- Code Files: {code_file_count}
- Config Files: {config_file_count}
- IaC Files: {iac_file_count}
- CI/CD Files: {cicd_file_count}
- Test Files: {test_file_count}
- Doc Files: {doc_file_count}

**Dependencies ({dep_count}):**
{dependency_list}

**Identified Risks ({risk_count}):**
{risk_details}

**Target Architecture:**
- Platforms: {platforms}
- Patterns: {patterns}

Generate the Technical Report following the template structure. Include:
1. Codebase Map with language percentages
2. Dependency & Integration Topology (with Mermaid diagram)
3. Security & Compliance Posture
4. Non-Functional Requirements Gap analysis
5. Risk Register (top 10)
6. Target Architecture (with Mermaid diagram)
7. Migration Playbook with waves
8. Backlog Slice for Sprint 1-2

Return your response as JSON:
{{
    "codebase_map": "...",
    "topology": "...",
    "security_compliance": "...",
    "nfrs": "...",
    "risk_register": [
        {{
            "id": "RISK-001",
            "category": "security|tech_debt|compliance|reliability|operability",
            "severity": "critical|high|medium|low|info",
            "title": "...",
            "description": "...",
            "remediation": "...",
            "effort": "S|M|L|XL"
        }}
    ],
    "target_architecture": "...",
    "architecture_diagram_mermaid": "graph TD\\n...",
    "migration_plan": [
        {{
            "wave_number": 1,
            "name": "Foundation",
            "duration_weeks": 4,
            "tasks": ["..."],
            "prerequisites": ["..."],
            "rollback_plan": "..."
        }}
    ],
    "backlog_slice": [
        {{
            "id": "STORY-001",
            "title": "...",
            "description": "...",
            "effort": "S|M|L|XL",
            "linked_risk_id": "RISK-001",
            "sprint": 1
        }}
    ]
}}"""),
])


# =============================================================================
# AGENT NODE
# =============================================================================

@track_performance("architect_analysis")
async def architect_node(state: AgentState) -> dict:
    """
    LangGraph node for Architect Agent.
    
    This node:
    1. Consumes the RepoBundle from Code Ingestion Agent
    2. Analyzes the codebase structure and risks
    3. Generates Business and Technical Comprehension Reports
    
    Args:
        state: Current graph state with repo_bundle
        
    Returns:
        State updates with business_report and technical_report
    """
    repo_url = state.repo_bundle.repo_url if state.repo_bundle else "unknown"
    
    with LogContext(agent="architect", repo_url=repo_url):
        logger.info("architect_started")
        
        llm = get_architect_llm()
        messages = list(state.messages)
        messages.append(SystemMessage(content=ARCHITECT_SYSTEM_PROMPT))
        
        try:
            # Validate we have a repo bundle
            if not state.repo_bundle:
                logger.error("missing_repo_bundle")
                metrics.increment("architect_errors", tags={"type": "missing_bundle"})
                raise MissingRepoBundleError()
            
            bundle = state.repo_bundle
            messages.append(HumanMessage(
                content=f"Generating comprehension reports for: {bundle.repo_url}"
            ))
            
            logger.info(
                "analyzing_bundle",
                files=bundle.total_files,
                languages=bundle.languages[:5],
                risks=len(bundle.risks),
            )
            
            # Prepare context
            business_ctx = state.business_context or {}
            target_arch = state.target_architecture or {}
            
            # Risk summary for business report
            risk_summary = "\n".join([
                f"- [{r.severity.value.upper()}] {r.title}: {r.description[:100]}..."
                for r in bundle.risks[:10]
            ]) or "No critical risks identified"
            
            # Detailed risks for technical report
            risk_details = "\n".join([
                f"- **{r.id}** [{r.severity.value}] ({r.category}): {r.title}\n  {r.description}\n  Remediation: {r.remediation or 'TBD'}"
                for r in bundle.risks
            ]) or "No risks identified during ingestion"
            
            # Dependency list
            dependency_list = "\n".join([
                f"- {d.name} ({d.package_manager}): {d.version or 'unknown'}"
                for d in bundle.dependencies[:30]
            ]) or "No dependencies discovered"
            
            # Generate Business Report
            logger.info("generating_business_report")
            with PerformanceTracker("business_report_generation", logger):
                business_prompt = BUSINESS_REPORT_PROMPT.format(
                    repo_url=bundle.repo_url,
                    ref=bundle.ref,
                    languages=", ".join(bundle.languages) or "Unknown",
                    frameworks=", ".join(bundle.frameworks) or "None detected",
                    build_systems=", ".join(bundle.build_systems) or "Unknown",
                    total_files=bundle.total_files,
                    dep_count=len(bundle.dependencies),
                    risk_count=len(bundle.risks),
                    risk_summary=risk_summary,
                    objective=getattr(business_ctx, 'objective', 'Modernize application'),
                    constraints=", ".join(getattr(business_ctx, 'constraints', [])) or "None specified",
                    kpis=", ".join(getattr(business_ctx, 'kpis', [])) or "Improve reliability",
                    compliance=", ".join(getattr(business_ctx, 'compliance_requirements', [])) or "Standard",
                    platforms=", ".join(getattr(target_arch, 'platforms', [])) or "Cloud-native",
                    patterns=", ".join(getattr(target_arch, 'patterns', [])) or "Microservices",
                )
                
                try:
                    business_response = await llm.ainvoke([HumanMessage(content=str(business_prompt))])
                except Exception as e:
                    logger.error("llm_error_business", error=str(e))
                    metrics.increment("architect_errors", tags={"type": "llm_business"})
                    raise LLMError(f"Failed to generate business report: {e}", cause=e)
            
            # Parse business report
            try:
                biz_text = business_response.content
                biz_json_start = biz_text.find("{")
                biz_json_end = biz_text.rfind("}") + 1
                if biz_json_start >= 0 and biz_json_end > biz_json_start:
                    biz_data = json.loads(biz_text[biz_json_start:biz_json_end])
                else:
                    logger.warning("business_report_no_json")
                    biz_data = {}
            except json.JSONDecodeError as e:
                logger.warning("business_report_parse_error", error=str(e))
                biz_data = {}
            
            business_report = BusinessReport(
                executive_summary=biz_data.get("executive_summary", "Report generation incomplete"),
                current_state=biz_data.get("current_state", ""),
                options=[
                    OptionItem(
                        id=opt.get("id", f"OPT-{i}"),
                        name=opt.get("name", f"Option {i}"),
                        description=opt.get("description", ""),
                        pros=opt.get("pros", []),
                        cons=opt.get("cons", []),
                        effort=EffortBand(opt.get("effort", "M")),
                        risk_level=RiskSeverity(opt.get("risk_level", "medium")),
                        recommended=opt.get("recommended", False),
                    )
                    for i, opt in enumerate(biz_data.get("options", []))
                ],
                value_and_kpis=biz_data.get("value_and_kpis", ""),
                adoption_plan=biz_data.get("adoption_plan", ""),
                diagram_mermaid=biz_data.get("diagram_mermaid"),
            )
            
            logger.info("business_report_generated", options_count=len(business_report.options))
            
            # Generate Technical Report
            logger.info("generating_technical_report")
            with PerformanceTracker("technical_report_generation", logger):
                tech_prompt = TECHNICAL_REPORT_PROMPT.format(
                    repo_url=bundle.repo_url,
                    ref=bundle.ref,
                    languages=", ".join(bundle.languages) or "Unknown",
                    frameworks=", ".join(bundle.frameworks) or "None detected",
                    build_systems=", ".join(bundle.build_systems) or "Unknown",
                    code_file_count=len(bundle.code_files),
                    config_file_count=len(bundle.config_files),
                    iac_file_count=len(bundle.iac_files),
                    cicd_file_count=len(bundle.cicd_files),
                    test_file_count=len(bundle.test_files),
                    doc_file_count=len(bundle.doc_files),
                    dep_count=len(bundle.dependencies),
                    dependency_list=dependency_list,
                    risk_count=len(bundle.risks),
                    risk_details=risk_details,
                    platforms=", ".join(getattr(target_arch, 'platforms', [])) or "Cloud-native",
                    patterns=", ".join(getattr(target_arch, 'patterns', [])) or "Microservices",
                )
                
                try:
                    tech_response = await llm.ainvoke([HumanMessage(content=str(tech_prompt))])
                except Exception as e:
                    logger.error("llm_error_technical", error=str(e))
                    metrics.increment("architect_errors", tags={"type": "llm_technical"})
                    raise LLMError(f"Failed to generate technical report: {e}", cause=e)
            
            # Parse technical report
            try:
                tech_text = tech_response.content
                tech_json_start = tech_text.find("{")
                tech_json_end = tech_text.rfind("}") + 1
                if tech_json_start >= 0 and tech_json_end > tech_json_start:
                    tech_data = json.loads(tech_text[tech_json_start:tech_json_end])
                else:
                    logger.warning("technical_report_no_json")
                    tech_data = {}
            except json.JSONDecodeError as e:
                logger.warning("technical_report_parse_error", error=str(e))
                tech_data = {}
            
            technical_report = TechnicalReport(
                codebase_map=tech_data.get("codebase_map", ""),
                topology=tech_data.get("topology", ""),
                security_compliance=tech_data.get("security_compliance", ""),
                nfrs=tech_data.get("nfrs", ""),
                risk_register=[
                    RiskItem(
                        id=r.get("id", f"RISK-{i:03d}"),
                        category=r.get("category", "tech_debt"),
                        severity=RiskSeverity(r.get("severity", "medium")),
                        title=r.get("title", ""),
                        description=r.get("description", ""),
                        remediation=r.get("remediation"),
                        effort=EffortBand(r.get("effort", "M")) if r.get("effort") else None,
                    )
                    for i, r in enumerate(tech_data.get("risk_register", []))
                ],
                target_architecture=tech_data.get("target_architecture", ""),
                architecture_diagram_mermaid=tech_data.get("architecture_diagram_mermaid"),
                migration_plan=[
                    MigrationWave(
                        wave_number=w.get("wave_number", i + 1),
                        name=w.get("name", f"Wave {i + 1}"),
                        duration_weeks=w.get("duration_weeks", 4),
                        tasks=w.get("tasks", []),
                        prerequisites=w.get("prerequisites", []),
                        rollback_plan=w.get("rollback_plan"),
                    )
                    for i, w in enumerate(tech_data.get("migration_plan", []))
                ],
                backlog_slice=[
                    BacklogItem(
                        id=b.get("id", f"STORY-{i:03d}"),
                        title=b.get("title", ""),
                        description=b.get("description", ""),
                        effort=EffortBand(b.get("effort", "M")),
                        linked_risk_id=b.get("linked_risk_id"),
                        sprint=b.get("sprint", 1),
                    )
                    for i, b in enumerate(tech_data.get("backlog_slice", []))
                ],
            )
            
            logger.info(
                "technical_report_generated",
                migration_waves=len(technical_report.migration_plan),
                backlog_items=len(technical_report.backlog_slice),
                risks=len(technical_report.risk_register),
            )
            
            # Success message
            success_msg = f"""Architecture analysis complete:
- Business Report: Generated with {len(business_report.options)} options
- Technical Report: Generated with {len(technical_report.migration_plan)} migration waves
- Backlog Items: {len(technical_report.backlog_slice)} stories for Sprint 1-2
- Risk Register: {len(technical_report.risk_register)} items documented"""
            
            messages.append(AIMessage(content=success_msg))
            
            logger.info("architect_completed")
            metrics.increment("architect_success")
            
            return {
                "business_report": business_report,
                "technical_report": technical_report,
                "messages": messages,
                "current_agent": "architect",
                "completed": True,
                "error": None,
            }
            
        except (ArchitectError, LLMError, MissingRepoBundleError) as e:
            error_msg = f"Architecture analysis failed: {e.message}"
            logger.error("architect_failed", error_code=e.error_code, message=e.message)
            messages.append(AIMessage(content=error_msg))
            metrics.increment("architect_failed")
            
            return {
                "error": error_msg,
                "messages": messages,
                "current_agent": "architect",
            }
            
        except Exception as e:
            error_msg = f"Architecture analysis failed: {str(e)}"
            logger.exception("architect_unexpected_error")
            messages.append(AIMessage(content=error_msg))
            metrics.increment("architect_failed")
            
            return {
                "error": error_msg,
                "messages": messages,
                "current_agent": "architect",
            }


# =============================================================================
# SYNC WRAPPER
# =============================================================================

def architect_node_sync(state: AgentState) -> dict:
    """Synchronous wrapper for architect node."""
    return asyncio.run(architect_node(state))
