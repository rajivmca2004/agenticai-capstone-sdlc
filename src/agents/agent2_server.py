# Copyright (c) Microsoft. All rights reserved.
"""
Agent 2 - A2A Server Implementation

This module implements Agent 2 as an A2A-compliant server that can be
discovered and communicated with by other agents.

The agent exposes:
- /.well-known/agent.json - Agent Card for discovery
- A2A message endpoint for communication
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

# Agent 2 Configuration
AGENT2_NAME = "Agent2"
AGENT2_DESCRIPTION = "Agent 2 - Placeholder for your custom agent functionality"
AGENT2_PORT = int(os.getenv("AGENT2_PORT", "5002"))


class Agent2RequestHandler(DefaultRequestHandler):
    """
    Custom request handler for Agent 2.
    
    This handler processes incoming A2A messages and generates responses.
    Customize the handle_message method to implement your agent's logic.
    """
    
    def __init__(self):
        super().__init__()
        # TODO: Add your agent's instructions/prompt here
        self.instructions = """
        You are Agent 2. Your role and capabilities will be defined later.
        For now, respond to messages by acknowledging them.
        """
    
    async def handle_message(self, message: Message) -> AsyncIterator[Event]:
        """
        Handle incoming A2A messages.
        
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
        
        # TODO: Replace with your agent's logic
        # This is where you'll integrate with LLM or implement custom behavior
        response_text = f"[Agent 2] Received: '{incoming_text}'. (Placeholder response - implement your agent logic here)"
        
        # Create response message
        response_message = Message(
            message_id=str(uuid.uuid4()),
            role=Role.agent,
            parts=[Part(root=TextPart(text=response_text))],
        )
        
        # Yield the response as an Event
        yield Event(data=response_message)


def create_agent_card() -> AgentCard:
    """
    Create the Agent Card for Agent 2.
    
    The Agent Card is used for agent discovery and describes
    the agent's capabilities, skills, and endpoints.
    """
    return AgentCard(
        name=AGENT2_NAME,
        description=AGENT2_DESCRIPTION,
        url=f"http://localhost:{AGENT2_PORT}",
        version="1.0.0",
        capabilities=AgentCapabilities(
            streaming=False,
            pushNotifications=False,
        ),
        skills=[
            AgentSkill(
                id="agent2_skill",
                name="Agent 2 Primary Skill",
                description="Placeholder skill - define your agent's capabilities here",
                tags=["placeholder", "agent2"],
            )
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown."""
    print(f"🚀 Starting {AGENT2_NAME} A2A Server on port {AGENT2_PORT}...")
    yield
    print(f"👋 Shutting down {AGENT2_NAME} A2A Server...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application with A2A endpoints."""
    app = FastAPI(
        title=AGENT2_NAME,
        description=AGENT2_DESCRIPTION,
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
    request_handler = Agent2RequestHandler()
    a2a_server = A2AServer(
        agent_card=agent_card,
        request_handler=request_handler,
    )
    
    # Register A2A routes
    a2a_server.register_routes(app)
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "agent": AGENT2_NAME}
    
    return app


# Create the FastAPI app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    print(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║                    Agent 2 - A2A Server                   ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  Agent Card: http://localhost:{AGENT2_PORT}/.well-known/agent.json  ║
    ║  Health:     http://localhost:{AGENT2_PORT}/health                  ║
    ╚═══════════════════════════════════════════════════════════╝
    
    NOTE: Replace the placeholder instructions and logic in 
    Agent2RequestHandler with your custom agent implementation.
    """)
    
    uvicorn.run(
        "agent2_server:app",
        host="0.0.0.0",
        port=AGENT2_PORT,
        reload=True,
    )
