# Copyright (c) Microsoft. All rights reserved.
"""
A2A Client - Agent Communication Orchestrator

This module demonstrates how to use the A2A protocol to orchestrate communication
between the Code Ingestion Agent and Architect Agent.

Workflow:
1. Code Ingestion Agent ingests a GitHub repository
2. The repo_bundle is passed to the Architect Agent
3. Architect Agent generates Business + Technical Comprehension reports
"""

import asyncio
import os

import httpx
from a2a.client import A2ACardResolver
from agent_framework.a2a import A2AAgent
from dotenv import load_dotenv

load_dotenv()

# Agent endpoint configuration
CODE_INGESTION_AGENT_HOST = os.getenv("CODE_INGESTION_AGENT_HOST", "http://localhost:5001")
ARCHITECT_AGENT_HOST = os.getenv("ARCHITECT_AGENT_HOST", "http://localhost:5002")


async def discover_agent(host: str) -> tuple[A2AAgent, str]:
    """
    Discover and connect to an A2A agent at the specified host.
    
    Args:
        host: The base URL of the A2A agent server
        
    Returns:
        Tuple of (A2AAgent instance, agent name)
    """
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        resolver = A2ACardResolver(httpx_client=http_client, base_url=host)
        agent_card = await resolver.get_agent_card()
        
        print(f"✅ Discovered agent: {agent_card.name}")
        print(f"   Description: {agent_card.description}")
        print(f"   URL: {agent_card.url}")
        
        if agent_card.skills:
            print(f"   Skills: {[skill.name for skill in agent_card.skills]}")
        
        # Create A2A agent wrapper
        agent = A2AAgent(
            name=agent_card.name,
            description=agent_card.description,
            agent_card=agent_card,
            url=host,
        )
        
        return agent, agent_card.name


async def send_message_to_agent(agent: A2AAgent, message: str) -> str:
    """
    Send a message to an agent and get the response.
    
    Args:
        agent: The A2AAgent to communicate with
        message: The message to send
        
    Returns:
        The agent's response text
    """
    print(f"\n📤 Sending to {agent.name}: '{message}'")
    
    response = await agent.run(message)
    
    response_text = ""
    for msg in response.messages:
        if hasattr(msg, 'text') and msg.text:
            response_text += msg.text
        elif hasattr(msg, 'contents'):
            for content in msg.contents:
                if hasattr(content, 'text'):
                    response_text += content.text
    
    print(f"📥 Response from {agent.name}: '{response_text}'")
    return response_text


async def agent_to_agent_communication(
    agent1: A2AAgent,
    agent2: A2AAgent,
    initial_message: str,
    rounds: int = 3,
):
    """
    Demonstrate agent-to-agent communication via A2A protocol.
    
    This creates a conversation loop where agents exchange messages.
    
    Args:
        agent1: First A2A agent
        agent2: Second A2A agent
        initial_message: The starting message for the conversation
        rounds: Number of conversation rounds
    """
    print("\n" + "=" * 60)
    print("🔄 Starting Agent-to-Agent Communication")
    print("=" * 60)
    
    current_message = initial_message
    current_sender = "User"
    
    for round_num in range(1, rounds + 1):
        print(f"\n--- Round {round_num} ---")
        
        # Agent 1 receives and responds
        print(f"\n[{current_sender} → Agent 1]")
        response1 = await send_message_to_agent(agent1, current_message)
        
        # Agent 2 receives Agent 1's response
        print(f"\n[Agent 1 → Agent 2]")
        response2 = await send_message_to_agent(agent2, response1)
        
        # Prepare for next round
        current_message = response2
        current_sender = "Agent 2"
    
    print("\n" + "=" * 60)
    print("✅ Agent-to-Agent Communication Complete")
    print("=" * 60)


async def main():
    """
    Main orchestrator demonstrating A2A protocol communication.
    """
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║           A2A Protocol - Agent Communication Demo             ║
    ╠═══════════════════════════════════════════════════════════════╣
    ║  This demo shows how two agents communicate via A2A protocol  ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    print(f"Connecting to agents...")
    print(f"  Agent 1: {AGENT1_HOST}")
    print(f"  Agent 2: {AGENT2_HOST}")
    print()
    
    try:
        # Discover both agents
        print("🔍 Discovering Agent 1...")
        agent1, agent1_name = await discover_agent(AGENT1_HOST)
        
        print("\n🔍 Discovering Agent 2...")
        agent2, agent2_name = await discover_agent(AGENT2_HOST)
        
        # Start agent-to-agent communication
        await agent_to_agent_communication(
            agent1=agent1,
            agent2=agent2,
            initial_message="Hello! Let's start a conversation between agents.",
            rounds=2,
        )
        
    except httpx.ConnectError as e:
        print(f"""
        ❌ Connection Error: Could not connect to agent servers.
        
        Make sure both agent servers are running:
        
        Terminal 1: cd src/agents && python agent1_server.py
        Terminal 2: cd src/agents && python agent2_server.py
        
        Then run this script again.
        
        Error details: {e}
        """)
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
