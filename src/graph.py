# Copyright (c) Microsoft. All rights reserved.
"""
LangGraph Orchestrator

This module defines the main workflow graph that connects:
1. Code Ingestion Agent → 2. Architect Agent

The graph uses LangGraph's StateGraph to manage state transitions
and supports checkpointing for fault tolerance.
"""

import os
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agents import architect_node, code_ingestion_node
from src.observability import get_logger, LogContext, metrics
from src.schemas import AgentState, IngestionStatus

# Initialize logger
logger = get_logger(__name__)


# =============================================================================
# CONDITIONAL EDGES
# =============================================================================

def should_continue_to_architect(state: AgentState) -> Literal["architect", "end"]:
    """
    Determine if we should proceed to Architect Agent.
    
    Returns:
        "architect" if ingestion succeeded
        "end" if ingestion failed
    """
    if state.ingestion_status == IngestionStatus.COMPLETED and state.repo_bundle:
        logger.info("routing_to_architect", reason="ingestion_completed")
        return "architect"
    logger.info("routing_to_end", reason="ingestion_failed_or_incomplete")
    return "end"


def check_completion(state: AgentState) -> Literal["end"]:
    """
    Final check after architect node.
    
    Always ends - this is the terminal node.
    """
    logger.info("workflow_completing")
    return "end"


# =============================================================================
# GRAPH BUILDER
# =============================================================================

def create_comprehension_graph(
    checkpointer=None,
    debug: bool = False,
) -> StateGraph:
    """
    Create the code comprehension workflow graph.
    
    The workflow:
    1. START → code_ingestion: Ingest GitHub repo
    2. code_ingestion → (conditional):
       - If success → architect: Generate reports
       - If failure → END
    3. architect → END
    
    Args:
        checkpointer: Optional LangGraph checkpointer for state persistence
        debug: Enable debug mode with detailed logging
        
    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("creating_comprehension_graph", debug=debug)
    
    # Create the graph with our state schema
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("code_ingestion", code_ingestion_node)
    workflow.add_node("architect", architect_node)
    
    logger.debug("nodes_added", nodes=["code_ingestion", "architect"])
    
    # Add edges
    # Start → Code Ingestion
    workflow.add_edge(START, "code_ingestion")
    
    # Code Ingestion → Conditional routing
    workflow.add_conditional_edges(
        "code_ingestion",
        should_continue_to_architect,
        {
            "architect": "architect",
            "end": END,
        },
    )
    
    # Architect → END
    workflow.add_edge("architect", END)
    
    # Use memory saver if no checkpointer provided (for development)
    if checkpointer is None:
        checkpointer = MemorySaver()
        logger.debug("using_memory_saver")
    
    # Compile the graph
    compiled = workflow.compile(checkpointer=checkpointer)
    logger.info("graph_compiled")
    
    return compiled


# =============================================================================
# GRAPH VISUALIZATION
# =============================================================================

def get_graph_mermaid() -> str:
    """
    Get Mermaid diagram representation of the graph.
    
    Returns:
        Mermaid diagram string
    """
    graph = create_comprehension_graph()
    return graph.get_graph().draw_mermaid()


def save_graph_image(output_path: str = "graph.png") -> None:
    """
    Save the graph as an image file.
    
    Requires graphviz and pygraphviz to be installed.
    
    Args:
        output_path: Path to save the image
    """
    try:
        graph = create_comprehension_graph()
        graph_image = graph.get_graph().draw_mermaid_png()
        with open(output_path, "wb") as f:
            f.write(graph_image)
        print(f"Graph saved to {output_path}")
    except Exception as e:
        print(f"Could not save graph image: {e}")
        print("Try saving the Mermaid diagram instead:")
        print(get_graph_mermaid())


# =============================================================================
# CONVENIENCE RUNNERS
# =============================================================================

async def run_comprehension_workflow(
    repo_url: str,
    ref: str = "main",
    business_objective: str | None = None,
    target_platforms: list[str] | None = None,
    thread_id: str = "default",
) -> AgentState:
    """
    Run the full code comprehension workflow.
    
    Args:
        repo_url: GitHub repository URL
        ref: Git reference (branch, tag, commit)
        business_objective: Optional business context objective
        target_platforms: Optional target platform list
        thread_id: Thread ID for checkpointing
        
    Returns:
        Final AgentState with reports
    """
    from src.schemas import BusinessContext, TargetArchitecture
    
    with LogContext(repo_url=repo_url, ref=ref, thread_id=thread_id):
        logger.info("workflow_started")
        
        # Create initial state
        initial_state = AgentState(
            repo_url=repo_url,
            ref=ref,
            business_context=BusinessContext(
                objective=business_objective or "Modernize application",
            ) if business_objective else None,
            target_architecture=TargetArchitecture(
                platforms=target_platforms or ["Azure"],
            ) if target_platforms else None,
        )
        
        # Create and run graph
        graph = create_comprehension_graph()
        
        # Run with thread ID for checkpointing
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            result = await graph.ainvoke(initial_state, config)
            logger.info("workflow_completed")
            metrics.increment("workflows_completed", tags={"status": "success"})
            return result
        except Exception as e:
            logger.exception("workflow_failed")
            metrics.increment("workflows_completed", tags={"status": "failed"})
            raise


def run_comprehension_workflow_sync(
    repo_url: str,
    ref: str = "main",
    business_objective: str | None = None,
    target_platforms: list[str] | None = None,
    thread_id: str = "default",
) -> AgentState:
    """
    Synchronous wrapper for run_comprehension_workflow.
    """
    import asyncio
    return asyncio.run(run_comprehension_workflow(
        repo_url=repo_url,
        ref=ref,
        business_objective=business_objective,
        target_platforms=target_platforms,
        thread_id=thread_id,
    ))


# =============================================================================
# STREAMING SUPPORT
# =============================================================================

async def stream_comprehension_workflow(
    repo_url: str,
    ref: str = "main",
    thread_id: str = "default",
):
    """
    Stream the comprehension workflow with real-time updates.
    
    Yields state updates as each node completes.
    
    Args:
        repo_url: GitHub repository URL
        ref: Git reference
        thread_id: Thread ID for checkpointing
        
    Yields:
        Tuple of (node_name, state_update)
    """
    initial_state = AgentState(
        repo_url=repo_url,
        ref=ref,
    )
    
    graph = create_comprehension_graph()
    config = {"configurable": {"thread_id": thread_id}}
    
    async for event in graph.astream(initial_state, config):
        for node_name, state_update in event.items():
            yield node_name, state_update


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Print the graph structure
    print("Code Comprehension Workflow Graph")
    print("=" * 40)
    print(get_graph_mermaid())
