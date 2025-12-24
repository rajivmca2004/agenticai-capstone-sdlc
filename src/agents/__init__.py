# Copyright (c) Microsoft. All rights reserved.
"""
Agents Package Initialization

This package contains the A2A-compliant agent implementations:
- Code Ingestion Agent: Ingest code from GitHub and prepare it for downstream analysis
- Architect Agent: Generate business + technical comprehension reports
"""

from .code_ingestion_agent import (
    CodeIngestionRequestHandler,
    create_agent_card as create_code_ingestion_agent_card,
    CODE_INGESTION_SYSTEM_PROMPT,
)
from .architect_agent import (
    ArchitectRequestHandler,
    create_agent_card as create_architect_agent_card,
    ARCHITECT_SYSTEM_PROMPT,
)

__all__ = [
    # Code Ingestion Agent
    "CodeIngestionRequestHandler",
    "create_code_ingestion_agent_card",
    "CODE_INGESTION_SYSTEM_PROMPT",
    # Architect Agent
    "ArchitectRequestHandler",
    "create_architect_agent_card",
    "ARCHITECT_SYSTEM_PROMPT",
]
