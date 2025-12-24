# Copyright (c) Microsoft. All rights reserved.
"""
Code Ingestion Agent - A2A Server Implementation

Agent Goal:
Reliably connect to GitHub, fetch and normalize repository artifacts (code, config, 
docs, issues, PRs), build a structured knowledge bundle with cross-links and embeddings, 
and expose deterministic APIs to downstream analysis agents.

Role / Persona:
You are a Code Ingestion Agent specialized in read-only GitHub operations, repo 
introspection, dependency mapping, and safe content normalization. You do NOT generate 
or modify code; you ONLY ingest, catalog, and publish well-typed artifacts for other agents.
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
AGENT_NAME = "CodeIngestionAgent"
AGENT_DESCRIPTION = "Ingest code from GitHub and prepare it for downstream analysis"
AGENT_PORT = int(os.getenv("CODE_INGESTION_AGENT_PORT", "5001"))

# =============================================================================
# CODE INGESTION AGENT - SYSTEM PROMPT
# =============================================================================
CODE_INGESTION_SYSTEM_PROMPT = """
You are the Code Ingestion Agent. Your mission is to ingest GitHub repositories safely and produce a
versioned, queryable knowledge bundle for downstream analysis.

Operate with these constraints:
1) READ-ONLY: never push, commit, or change repository contents.
2) PRIVACY & SECURITY: run secret/PII redaction on all text and configs; exclude files matching
   organization exclusion rules (e.g., *.pem, *.key, .env). Log exclusions.
3) SCALE GUARDS: obey file size caps, skip generated/binary artifacts unless explicitly requested
   (e.g., dist/, build/, node_modules/, .jar/.zip/.pdf).
4) REPRODUCIBILITY: store source URIs (repo+path+ref+line), checksums, and a manifest of all
   ingested items. Every chunk must carry its origin.

Execution steps:
A) Discover repository structure: languages, frameworks, build systems, test layout.
B) Parse dependencies (pom.xml/build.gradle, package.json, requirements.txt, etc.); record versions,
   transitive graphs, and supply-chain risk notes.
C) Run classifiers: {code, config, docs, infra-as-code, CI/CD, tests}.
D) Chunk & embed code and docs with repo-relative anchors (file:path:line-range).
E) Produce outputs:
   - repo_bundle.manifest.json (schema-v1)
   - dependency_graph.(json|dot)
   - file_inventory.csv
   - embeddings.index (code+docs)
   - risks.md (license, secrets, known vulnerable libs)
F) Publish bundle with metadata: {repo, ref, timestamp, policy, index_profile}.

APIs you must expose:
- get_file(uri|glob)
- search(text|semantic) -> [{chunk_uri, score, preview}]
- list_dependencies(scope)
- list_tests()
- get_manifest()
- get_risks()

If inputs are missing (repo_url, ref, token), ask precisely for those and nothing else.
If rate-limited, back off and continue. Always return a summary with ingestion stats.
"""

# =============================================================================
# TRIGGER PROMPT TEMPLATE (for operator-side usage)
# =============================================================================
TRIGGER_PROMPT_TEMPLATE = """
Ingest the repository:
repo_url: https://github.com/<org>/<repo>
ref: main
path_filters: ["src/**", "docs/**", ".github/**"]
ingestion_policy: {maxFileMB: 2, excludeGlobs: ["**/*.pem", "**/*.key", "**/.env", "dist/**", "node_modules/**"]}
indexing_profile: {codeEmbeddings: true, docEmbeddings: true, testDiscovery: true}
Return the repo_bundle.manifest.json and publish indexes.
"""


class CodeIngestionRequestHandler(DefaultRequestHandler):
    """
    Request handler for the Code Ingestion Agent.
    
    Processes incoming A2A messages to ingest GitHub repositories
    and produce structured knowledge bundles for downstream agents.
    
    Primary Inputs:
    - repo_url, ref (branch/tag/SHA), optional path_filters
    - auth_context (scoped token, read-only)
    - ingestion_policy (file size caps, license filters, secret redaction rules)
    - indexing_profile (which analyzers/embedders to run)
    
    Required Tools / Actions:
    - GitHub Read APIs (tree, blob, commits, PRs, issues)
    - Content Classifiers (language, framework, license)
    - Secret/PII Redactor (YAML/ENV/JSON patterns; entropy checks)
    - Dependency Parsers (Maven/Gradle, npm/pnpm, Poetry/pip, Cargo, Go)
    - Embedding Pipeline (code+doc chunking; attach repo-relative URIs)
    - Bundle Publisher (writes versioned "repo-bundle" manifest and indexes)
    """
    
    def __init__(self):
        super().__init__()
        self.instructions = CODE_INGESTION_SYSTEM_PROMPT
        
        # TODO: Initialize your tools/services here
        # self.github_client = GitHubClient(...)
        # self.secret_redactor = SecretRedactor(...)
        # self.dependency_parser = DependencyParser(...)
        # self.embedding_pipeline = EmbeddingPipeline(...)
    
    async def handle_message(self, message: Message) -> AsyncIterator[Event]:
        """
        Handle incoming A2A messages for code ingestion.
        
        Expected message format:
        {
            "repo_url": "https://github.com/org/repo",
            "ref": "main",
            "path_filters": ["src/**", "docs/**"],
            "ingestion_policy": {...},
            "indexing_profile": {...}
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
        
        # TODO: Implement actual code ingestion logic
        # 1. Parse the incoming request for repo_url, ref, policies
        # 2. Connect to GitHub API (read-only)
        # 3. Discover repository structure
        # 4. Parse dependencies
        # 5. Run content classifiers
        # 6. Apply secret/PII redaction
        # 7. Chunk and embed code/docs
        # 8. Produce manifest and indexes
        
        # Placeholder response - replace with actual implementation
        response_text = f"""[Code Ingestion Agent] Received ingestion request.

📥 **Request Analysis:**
{incoming_text[:500]}{'...' if len(incoming_text) > 500 else ''}

🔧 **Ingestion Pipeline Status:**
- Repository Discovery: PENDING
- Dependency Parsing: PENDING  
- Content Classification: PENDING
- Secret Redaction: PENDING
- Embedding Generation: PENDING
- Bundle Publishing: PENDING

⚠️ **Note:** This is a placeholder response. Implement the actual ingestion logic by:
1. Integrating GitHub API client
2. Adding dependency parsers (npm, pip, maven, etc.)
3. Implementing secret/PII redaction
4. Setting up embedding pipeline
5. Creating bundle publisher

📋 **Expected Outputs:**
- repo_bundle.manifest.json
- dependency_graph.json
- file_inventory.csv
- embeddings.index
- risks.md
"""
        
        # Create response message
        response_message = Message(
            message_id=str(uuid.uuid4()),
            role=Role.agent,
            parts=[Part(root=TextPart(text=response_text))],
        )
        
        yield Event(data=response_message)
    
    # =========================================================================
    # API Methods (to be implemented)
    # =========================================================================
    
    async def get_file(self, uri_or_glob: str) -> dict:
        """Get file content by URI or glob pattern."""
        # TODO: Implement file retrieval from ingested bundle
        raise NotImplementedError("get_file not yet implemented")
    
    async def search(self, query: str, semantic: bool = False) -> list[dict]:
        """Search ingested content (text or semantic)."""
        # TODO: Implement search over embeddings/content
        raise NotImplementedError("search not yet implemented")
    
    async def list_dependencies(self, scope: str = "all") -> dict:
        """List dependencies with optional scope filter."""
        # TODO: Return dependency graph
        raise NotImplementedError("list_dependencies not yet implemented")
    
    async def list_tests(self) -> list[dict]:
        """List discovered tests from the repository."""
        # TODO: Return test inventory
        raise NotImplementedError("list_tests not yet implemented")
    
    async def get_manifest(self) -> dict:
        """Get the repo bundle manifest."""
        # TODO: Return manifest JSON
        raise NotImplementedError("get_manifest not yet implemented")
    
    async def get_risks(self) -> dict:
        """Get identified risks (license, secrets, vulnerabilities)."""
        # TODO: Return risk register
        raise NotImplementedError("get_risks not yet implemented")


def create_agent_card() -> AgentCard:
    """
    Create the Agent Card for the Code Ingestion Agent.
    
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
                id="github_ingestion",
                name="GitHub Repository Ingestion",
                description="Connect to GitHub, fetch and normalize repository artifacts (code, config, docs, issues, PRs)",
                tags=["github", "ingestion", "code-analysis"],
            ),
            AgentSkill(
                id="dependency_mapping",
                name="Dependency Mapping",
                description="Parse and map dependencies from various package managers (npm, pip, maven, etc.)",
                tags=["dependencies", "security", "sbom"],
            ),
            AgentSkill(
                id="content_classification",
                name="Content Classification",
                description="Classify repository content (code, config, docs, IaC, CI/CD, tests)",
                tags=["classification", "analysis"],
            ),
            AgentSkill(
                id="bundle_publishing",
                name="Knowledge Bundle Publishing",
                description="Produce versioned repo bundles with manifests and embeddings for downstream agents",
                tags=["embeddings", "knowledge-base", "indexing"],
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
    request_handler = CodeIngestionRequestHandler()
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
            "system_prompt": CODE_INGESTION_SYSTEM_PROMPT,
            "trigger_template": TRIGGER_PROMPT_TEMPLATE,
        }
    
    return app


# Create the FastAPI app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    print(f"""
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║                     CODE INGESTION AGENT - A2A Server                     ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║  Mission: Ingest code from GitHub and prepare it for downstream analysis  ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║  Agent Card: http://localhost:{AGENT_PORT}/.well-known/agent.json               ║
    ║  Health:     http://localhost:{AGENT_PORT}/health                               ║
    ║  Prompt:     http://localhost:{AGENT_PORT}/prompt                               ║
    ╚═══════════════════════════════════════════════════════════════════════════╝
    
    Role: READ-ONLY GitHub operations, repo introspection, dependency mapping,
          and safe content normalization. Does NOT generate or modify code.
    
    Outputs:
    - repo_bundle.manifest.json (schema-v1)
    - dependency_graph.(json|dot)
    - file_inventory.csv
    - embeddings.index (code+docs)
    - risks.md (license, secrets, known vulnerable libs)
    """)
    
    uvicorn.run(
        "code_ingestion_agent:app",
        host="0.0.0.0",
        port=AGENT_PORT,
        reload=True,
    )
