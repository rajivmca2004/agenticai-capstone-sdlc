# Copyright (c) Microsoft. All rights reserved.
"""
Architect Agent - A2A Server Implementation

Agent Goal:
Transform ingested repository knowledge and project artifacts into executive-friendly 
Business Comprehension and architect-ready Technical Comprehension reports, with risks, 
options, and actionable recommendations aligned to Microsoft delivery standards.

Role / Persona:
You are the Architect Agent, acting like a Solution Cloud Technical Architect. You 
synthesize repo insights, backlog/ADR/SDD content, CI/CD configs, and deployment topology 
to produce decision-grade documents and visuals (diagrams, risks, effort bands, migration paths).
"""

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from a2a.server import A2AServer
from a2a.server.events import Event
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Message,
    Part,
    Role,
    Task,
    TaskState,
    TaskStatus,
    TextPart,
)
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# Agent Configuration
AGENT_NAME = "ArchitectAgent"
AGENT_DESCRIPTION = "Generate business + technical code comprehension reports like a solution cloud technical architect"
AGENT_PORT = int(os.getenv("ARCHITECT_AGENT_PORT", "5002"))

# =============================================================================
# ARCHITECT AGENT - SYSTEM PROMPT
# =============================================================================
ARCHITECT_SYSTEM_PROMPT = """
You are the Architect Agent. Produce two companion reports:

(1) Business Comprehension Report (Executive)
- Summarize business objectives, current capabilities, key risks/opportunities.
- Quantify impact: cycle-time, defect leakage, reliability, cost drivers.
- Recommend 2–3 solution options with trade-offs, risks, and value hypotheses.
- Provide an adoption plan: phases, milestones, KPIs, governance.
- Keep jargon minimal; use clear visuals (one summary diagram).

(2) Technical Comprehension Report (Architect/Engineering)
- Codebase overview: languages, frameworks, layering, ownership hints.
- Dependency and runtime topology from CI/CD + IaC; identify anti-patterns.
- Security & compliance: authz/authn, secrets handling, data protection.
- Non-functional: performance, reliability, scalability, operability.
- Risks & tech debt with severity; map to remediation tasks.
- Target architecture proposal with reference patterns; include Mermaid diagrams.
- Migration steps with effort bands (S/M/L), prerequisites, and roll-back plan.

Operating Principles:
- Ground everything in the repo_bundle manifest and context_artifacts; add links back
  to original URIs. Never speculate beyond evidence; when evidence is missing, mark
  "Unknown – needs discovery" and propose a precise action.
- Use Microsoft delivery templates (SDD/ADR/RAID) terminology and structure.
- Adhere to Responsible AI and security posture; do not include secrets or PII.
- Prefer options matrices and checklists over prose when listing decisions.

Output:
- business_report.md
- technical_report.md
- arch_overview.mmd (Mermaid)
- risk_register.csv
- options_matrix.csv

Ask ONLY for missing artifacts (e.g., target_arch, business_context). Return a crisp
executive summary followed by deep technical detail. Where helpful, generate
"Next 2 sprints" backlog slices linked to risks/remediation tasks.
"""

# =============================================================================
# TRIGGER PROMPT TEMPLATE (for operator-side usage)
# =============================================================================
TRIGGER_PROMPT_TEMPLATE = """
Generate both reports using:
repo_bundle: <attach from Code Ingestion Agent>
context_artifacts: ["docs/ADR/*.md", "architecture/SDD/*.md", ".github/workflows/*.yml", "infra/**", "readme.md"]
business_context: {objective: "Modernize to Azure AKS and SQL MI with Zero Trust", constraints: ["PCI DSS", "GDPR"], kpis: ["lead_time -30%", "MTTR -40%", "pipeline success 95%"]}
target_arch: {platforms: ["Azure AKS", "Azure SQL MI", "Azure API Management", "Keycloak/Entra"], patterns: ["SaaS control plane", "event-driven", "CQRS"]}
report_audience: ["Exec", "Architect"]
"""

# =============================================================================
# REPORT STRUCTURE TEMPLATES
# =============================================================================
BUSINESS_REPORT_STRUCTURE = """
## Business Comprehension Report Structure (Executive)

1. **Executive Summary** (value narrative and top risks)
2. **Current State** (capabilities, bottlenecks)
3. **Options & Trade-offs** (table + one-paragraph rationale each)
4. **Value & KPIs** (baseline → target deltas, dependencies)
5. **Adoption Plan** (phased roadmap, governance, RAI)
6. **One-page Diagram** (capability view)
"""

TECHNICAL_REPORT_STRUCTURE = """
## Technical Comprehension Report Structure (Architect)

1. **Codebase Map** (modules, ownership hints, test coverage signals)
2. **Topology** (CI/CD, IaC → runtime; ports/secrets/egress)
3. **Security & Compliance** (auth/authz, data, secrets)
4. **NFRs** (perf, scale, reliability, ops)
5. **Risk Register** (severity, evidence URI, remediation)
6. **Target Architecture** (Mermaid + decisions)
7. **Migration Plan** (2–3 waves; effort bands; rollback)
8. **Backlog Slice** (next 2 sprints mapped to risks)
"""


class ArchitectRequestHandler(DefaultRequestHandler):
    """
    Request handler for the Architect Agent.
    
    Processes incoming A2A messages to generate business and technical
    comprehension reports from ingested repository knowledge.
    
    Primary Inputs:
    - repo_bundle from Code Ingestion Agent
    - context_artifacts: ADRs, SDDs, backlog, readme/docs, pipeline yaml, IaC, env configs
    - business_context: objectives, constraints, NFRs, compliance, cost targets
    - target_arch: desired cloud platforms/services
    - report_audience: {Exec, Architect, Engineering, QA, Security}
    
    Required Tools / Actions:
    - Cross-referencer (link code chunks → docs → pipeline steps → IaC → runtime topology)
    - Architecture Pattern Catalog (SaaS multi-tenant, CQRS, event-driven, zero-trust)
    - Risk Scorer (tech debt, security, compliance, reliability, operability)
    - Diagram Generator (Mermaid/PlantUML)
    - Estimator (effort bands, options matrix)
    - Governance Checklist (RAI, agent safety, policy alignment)
    """
    
    def __init__(self):
        super().__init__()
        self.instructions = ARCHITECT_SYSTEM_PROMPT
        
        # TODO: Initialize your tools/services here
        # self.cross_referencer = CrossReferencer(...)
        # self.pattern_catalog = ArchitecturePatternCatalog(...)
        # self.risk_scorer = RiskScorer(...)
        # self.diagram_generator = DiagramGenerator(...)
        # self.estimator = EffortEstimator(...)
    
    async def handle_message(self, message: Message) -> AsyncIterator[Event]:
        """
        Handle incoming A2A messages for architecture analysis.
        
        Expected message format:
        {
            "repo_bundle": {...},  # From Code Ingestion Agent
            "context_artifacts": [...],
            "business_context": {...},
            "target_arch": {...},
            "report_audience": [...]
        }
        
        Args:
            message: The incoming A2A message from another agent or client
            
        Yields:
            Event objects representing the agent's response
        """
        # Extract text from incoming message
        incoming_text = ""
        for part in message.parts:
            if hasattr(part.root, 'text'):
                incoming_text += part.root.text
        
        # TODO: Implement actual architecture analysis logic
        # 1. Parse the incoming request for repo_bundle, context, etc.
        # 2. Cross-reference code with docs, pipelines, IaC
        # 3. Apply architecture pattern matching
        # 4. Score risks (tech debt, security, compliance)
        # 5. Generate diagrams (Mermaid)
        # 6. Estimate effort bands
        # 7. Produce reports and artifacts
        
        # Placeholder response - replace with actual implementation
        response_text = f"""[Architect Agent] Received analysis request.

📥 **Request Analysis:**
{incoming_text[:500]}{'...' if len(incoming_text) > 500 else ''}

🏗️ **Architecture Analysis Pipeline Status:**
- Cross-Referencing: PENDING
- Pattern Matching: PENDING
- Risk Scoring: PENDING
- Diagram Generation: PENDING
- Effort Estimation: PENDING
- Report Generation: PENDING

📋 **Expected Outputs:**

### Business Comprehension Report (Executive)
{BUSINESS_REPORT_STRUCTURE}

### Technical Comprehension Report (Architect)
{TECHNICAL_REPORT_STRUCTURE}

### Artifacts
- business_report.md
- technical_report.md
- arch_overview.mmd (Mermaid)
- risk_register.csv
- options_matrix.csv

⚠️ **Note:** This is a placeholder response. Implement the actual analysis logic by:
1. Integrating with Code Ingestion Agent output (repo_bundle)
2. Adding cross-referencing capabilities
3. Implementing architecture pattern catalog
4. Setting up risk scoring engine
5. Creating Mermaid diagram generator
6. Building effort estimation module

🔗 **Operating Principles Applied:**
- Ground everything in repo_bundle manifest and context_artifacts
- Use Microsoft delivery templates (SDD/ADR/RAID) terminology
- Adhere to Responsible AI and security posture
- Prefer options matrices and checklists over prose
"""
        
        # Create response message
        response_message = Message(
            message_id=str(uuid.uuid4()),
            role=Role.agent,
            parts=[Part(root=TextPart(text=response_text))],
        )
        
        yield Event(data=response_message)
    
    # =========================================================================
    # Report Generation Methods (to be implemented)
    # =========================================================================
    
    async def generate_business_report(self, repo_bundle: dict, context: dict) -> str:
        """Generate the Business Comprehension Report for executives."""
        # TODO: Implement business report generation
        raise NotImplementedError("generate_business_report not yet implemented")
    
    async def generate_technical_report(self, repo_bundle: dict, context: dict) -> str:
        """Generate the Technical Comprehension Report for architects."""
        # TODO: Implement technical report generation
        raise NotImplementedError("generate_technical_report not yet implemented")
    
    async def generate_architecture_diagram(self, repo_bundle: dict, target_arch: dict) -> str:
        """Generate Mermaid architecture diagram."""
        # TODO: Generate Mermaid diagram
        raise NotImplementedError("generate_architecture_diagram not yet implemented")
    
    async def generate_risk_register(self, repo_bundle: dict) -> list[dict]:
        """Generate risk register with severity and remediation tasks."""
        # TODO: Score and categorize risks
        raise NotImplementedError("generate_risk_register not yet implemented")
    
    async def generate_options_matrix(self, context: dict, target_arch: dict) -> list[dict]:
        """Generate options matrix with trade-offs."""
        # TODO: Build options comparison
        raise NotImplementedError("generate_options_matrix not yet implemented")
    
    async def estimate_effort(self, migration_tasks: list[dict]) -> dict:
        """Estimate effort bands (S/M/L) for migration tasks."""
        # TODO: Estimate effort
        raise NotImplementedError("estimate_effort not yet implemented")


def create_agent_card() -> AgentCard:
    """
    Create the Agent Card for the Architect Agent.
    
    The Agent Card is used for agent discovery and describes
    the agent's capabilities, skills, and endpoints.
    """
    return AgentCard(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        url=f"http://localhost:{AGENT_PORT}",
        version="1.0.0",
        capabilities=AgentCapabilities(
            streaming=False,
            pushNotifications=False,
        ),
        skills=[
            AgentSkill(
                id="business_comprehension",
                name="Business Comprehension Report",
                description="Generate executive-friendly reports with value narratives, options, and adoption plans",
                tags=["business", "executive", "strategy"],
            ),
            AgentSkill(
                id="technical_comprehension",
                name="Technical Comprehension Report",
                description="Generate architect-ready reports with codebase analysis, topology, and migration plans",
                tags=["architecture", "technical", "migration"],
            ),
            AgentSkill(
                id="risk_assessment",
                name="Risk Assessment",
                description="Score and categorize risks (tech debt, security, compliance, reliability)",
                tags=["risk", "security", "compliance"],
            ),
            AgentSkill(
                id="architecture_diagrams",
                name="Architecture Diagrams",
                description="Generate Mermaid/PlantUML diagrams for target architecture",
                tags=["diagrams", "mermaid", "visualization"],
            ),
            AgentSkill(
                id="effort_estimation",
                name="Effort Estimation",
                description="Estimate effort bands (S/M/L) and generate options matrices",
                tags=["estimation", "planning", "roadmap"],
            ),
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown."""
    print(f"🚀 Starting {AGENT_NAME} A2A Server on port {AGENT_PORT}...")
    print(f"📋 Mission: {AGENT_DESCRIPTION}")
    yield
    print(f"👋 Shutting down {AGENT_NAME} A2A Server...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application with A2A endpoints."""
    app = FastAPI(
        title=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Add CORS middleware for cross-origin requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Create A2A server components
    agent_card = create_agent_card()
    request_handler = ArchitectRequestHandler()
    a2a_server = A2AServer(
        agent_card=agent_card,
        request_handler=request_handler,
    )
    
    # Register A2A routes
    a2a_server.register_routes(app)
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "agent": AGENT_NAME}
    
    @app.get("/prompt")
    async def get_system_prompt():
        """Return the agent's system prompt for reference."""
        return {
            "agent": AGENT_NAME,
            "system_prompt": ARCHITECT_SYSTEM_PROMPT,
            "trigger_template": TRIGGER_PROMPT_TEMPLATE,
            "business_report_structure": BUSINESS_REPORT_STRUCTURE,
            "technical_report_structure": TECHNICAL_REPORT_STRUCTURE,
        }
    
    return app


# Create the FastAPI app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    print(f"""
    ╔═══════════════════════════════════════════════════════════════════════════════════════╗
    ║                           ARCHITECT AGENT - A2A Server                                ║
    ╠═══════════════════════════════════════════════════════════════════════════════════════╣
    ║  Mission: Generate business + technical comprehension reports like a Solution Cloud  ║
    ║           Technical Architect                                                         ║
    ╠═══════════════════════════════════════════════════════════════════════════════════════╣
    ║  Agent Card: http://localhost:{AGENT_PORT}/.well-known/agent.json                           ║
    ║  Health:     http://localhost:{AGENT_PORT}/health                                           ║
    ║  Prompt:     http://localhost:{AGENT_PORT}/prompt                                           ║
    ╚═══════════════════════════════════════════════════════════════════════════════════════╝
    
    Role: Solution Cloud Technical Architect synthesizing repo insights, ADR/SDD content,
          CI/CD configs, and deployment topology into decision-grade documents.
    
    Outputs:
    - business_report.md (Executive)
    - technical_report.md (Architect/Engineering)
    - arch_overview.mmd (Mermaid diagrams)
    - risk_register.csv
    - options_matrix.csv
    """)
    
    uvicorn.run(
        "architect_agent:app",
        host="0.0.0.0",
        port=AGENT_PORT,
        reload=True,
    )
