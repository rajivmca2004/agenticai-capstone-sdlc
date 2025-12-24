# Copyright (c) Microsoft. All rights reserved.
"""
Code Comprehension Agentic AI Solution.

This package provides a LangGraph-based multi-agent workflow:
- Code Ingestion Agent: GitHub repo analysis
- Architect Agent: Business + Technical comprehension reports
"""

__version__ = "0.2.0"

from .config import Settings, get_settings
from .graph import (
    create_comprehension_graph,
    run_comprehension_workflow,
    run_comprehension_workflow_sync,
    stream_comprehension_workflow,
)
from .llm import get_architect_llm, get_code_ingestion_llm, get_llm

__all__ = [
    # Configuration
    "Settings",
    "get_settings",
    # LLM
    "get_llm",
    "get_code_ingestion_llm",
    "get_architect_llm",
    # Graph
    "create_comprehension_graph",
    "run_comprehension_workflow",
    "run_comprehension_workflow_sync",
    "stream_comprehension_workflow",
]
