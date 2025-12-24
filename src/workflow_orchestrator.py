# Copyright (c) Microsoft. All rights reserved.
"""
Multi-Agent Workflow Example using Microsoft Agent Framework

This module demonstrates how to build a multi-agent workflow where
agents collaborate to complete tasks using the Agent Framework's
workflow orchestration capabilities combined with A2A protocol.
"""

import asyncio
import os
from typing import Any

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowOutputEvent,
    handler,
)
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()


class Agent1Executor(Executor):
    """
    Executor wrapper for Agent 1.
    
    This executor handles messages for Agent 1 in a workflow context.
    TODO: Replace with your agent's logic and instructions.
    """
    
    def __init__(self, id: str = "agent1"):
        super().__init__(id=id)
        self.instructions = """
        You are Agent 1 in a multi-agent workflow.
        TODO: Define your agent's role and capabilities here.
        """
    
    @handler
    async def handle(self, message: str, ctx: WorkflowContext[str]) -> None:
        """
        Handle incoming messages and forward processed output.
        
        Args:
            message: Input message from previous step or user
            ctx: Workflow context for sending messages downstream
        """
        # TODO: Replace with your agent logic
        # This could involve calling an LLM, processing data, etc.
        processed = f"[Agent 1 processed]: {message}"
        
        print(f"🤖 Agent 1: {processed}")
        await ctx.send_message(processed)


class Agent2Executor(Executor):
    """
    Executor wrapper for Agent 2.
    
    This executor handles messages for Agent 2 in a workflow context.
    TODO: Replace with your agent's logic and instructions.
    """
    
    def __init__(self, id: str = "agent2"):
        super().__init__(id=id)
        self.instructions = """
        You are Agent 2 in a multi-agent workflow.
        TODO: Define your agent's role and capabilities here.
        """
    
    @handler
    async def handle(self, message: str, ctx: WorkflowContext[Any, str]) -> None:
        """
        Handle incoming messages and yield final output.
        
        Args:
            message: Input message from previous executor
            ctx: Workflow context for yielding workflow output
        """
        # TODO: Replace with your agent logic
        final_output = f"[Agent 2 finalized]: {message}"
        
        print(f"🤖 Agent 2: {final_output}")
        await ctx.yield_output(final_output)


async def run_sequential_workflow(initial_message: str) -> str:
    """
    Run a sequential workflow: Agent 1 → Agent 2
    
    Args:
        initial_message: The starting message for the workflow
        
    Returns:
        The final output from the workflow
    """
    print("\n" + "=" * 60)
    print("📋 Running Sequential Workflow: Agent 1 → Agent 2")
    print("=" * 60)
    
    # Create executor instances
    agent1 = Agent1Executor()
    agent2 = Agent2Executor()
    
    # Build the workflow
    workflow = (
        WorkflowBuilder()
        .add_edge(agent1, agent2)
        .set_start_executor(agent1)
        .build()
    )
    
    # Run the workflow
    print(f"\n📥 Input: {initial_message}")
    
    final_output = None
    async for event in workflow.run_stream(initial_message):
        if isinstance(event, WorkflowOutputEvent):
            final_output = event.data
    
    print(f"\n📤 Final Output: {final_output}")
    print("=" * 60)
    
    return final_output


async def run_bidirectional_workflow(initial_message: str, rounds: int = 2) -> str:
    """
    Run a bidirectional workflow where agents exchange messages.
    
    This demonstrates a more complex pattern where agents can
    communicate back and forth (similar to the A2A communication pattern).
    
    Args:
        initial_message: The starting message for the workflow
        rounds: Number of exchange rounds
        
    Returns:
        The final output from the workflow
    """
    print("\n" + "=" * 60)
    print("🔄 Running Bidirectional Workflow")
    print("=" * 60)
    
    # For bidirectional, we'll manually orchestrate
    agent1 = Agent1Executor()
    agent2 = Agent2Executor()
    
    current_message = initial_message
    
    for round_num in range(rounds):
        print(f"\n--- Round {round_num + 1} ---")
        
        # Simple simulation of message passing
        # In a real scenario, you'd use the workflow builder with edges
        agent1_response = f"[Agent 1 - Round {round_num + 1}]: {current_message}"
        print(f"🤖 {agent1_response}")
        
        agent2_response = f"[Agent 2 - Round {round_num + 1}]: {agent1_response}"
        print(f"🤖 {agent2_response}")
        
        current_message = agent2_response
    
    print("\n" + "=" * 60)
    return current_message


async def main():
    """
    Main entry point demonstrating workflow patterns.
    """
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║        Multi-Agent Workflow Demo - Agent Framework            ║
    ╠═══════════════════════════════════════════════════════════════╣
    ║  Demonstrating sequential and bidirectional agent workflows   ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Demo 1: Sequential workflow
    await run_sequential_workflow(
        "Analyze this data and provide insights."
    )
    
    # Demo 2: Bidirectional workflow
    await run_bidirectional_workflow(
        "Let's collaborate on solving this problem.",
        rounds=2,
    )
    
    print("\n✅ All workflow demos completed!")


if __name__ == "__main__":
    asyncio.run(main())
