# Copyright (c) Microsoft. All rights reserved.
"""
Agents package - LangGraph nodes for code comprehension workflow.

This package provides:
- code_ingestion_node: Ingests GitHub repos and produces RepoBundle
- architect_node: Analyzes repos and produces comprehension reports
"""

from .architect_node import (
    ARCHITECT_SYSTEM_PROMPT,
    architect_node,
    architect_node_sync,
)
from .code_ingestion_node import (
    CODE_INGESTION_SYSTEM_PROMPT,
    code_ingestion_node,
    code_ingestion_node_sync,
)

__all__ = [
    # Code Ingestion Agent
    "CODE_INGESTION_SYSTEM_PROMPT",
    "code_ingestion_node",
    "code_ingestion_node_sync",
    # Architect Agent
    "ARCHITECT_SYSTEM_PROMPT",
    "architect_node",
    "architect_node_sync",
]
