# Agentic AI Solution with A2A Protocol

A Python bootstrap POC project demonstrating agent-to-agent communication using the **Microsoft Agent Framework** and the **A2A (Agent-to-Agent) Protocol**.

## 🎯 Overview

This project provides a starting template for building agentic AI solutions with two agents communicating via the A2A protocol. The agents are designed as placeholders - you can customize their prompts and logic once you provide your specific requirements.

## 📁 Project Structure

```
agenticai-capstone-sdlc/
├── src/
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── agent1_server.py      # Agent 1 A2A Server
│   │   └── agent2_server.py      # Agent 2 A2A Server
│   ├── a2a_client.py             # A2A Client for agent communication
│   └── workflow_orchestrator.py  # Multi-agent workflow patterns
├── requirements.txt
├── .env.example
└── README.md
```

## 🚀 Quick Start

### 1. Set Up Python Environment

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows)
.\.venv\Scripts\Activate.ps1

# Install dependencies (--pre flag required for Agent Framework preview)
pip install -r requirements.txt
```

> ⚠️ **Important**: The `--pre` flag is required because the Microsoft Agent Framework is currently in preview.

### 2. Configure Environment

```powershell
# Copy environment template
Copy-Item .env.example .env

# Edit .env with your configuration
```

### 3. Start Agent Servers

Open **two separate terminals** and start each agent:

**Terminal 1 - Agent 1:**
```powershell
cd src/agents
python agent1_server.py
```

**Terminal 2 - Agent 2:**
```powershell
cd src/agents
python agent2_server.py
```

### 4. Run A2A Communication Demo

In a **third terminal**:
```powershell
cd src
python a2a_client.py
```

## 🔧 Architecture

### A2A Protocol

The [A2A (Agent-to-Agent) Protocol](https://a2a-protocol.org/) is a standardized communication protocol that enables interoperability between different agent systems. Key features:

- **Agent Discovery**: Agents expose their capabilities via Agent Cards at `/.well-known/agent.json`
- **Standardized Communication**: JSON-RPC based message exchange
- **Cross-Platform**: Agents built with different frameworks can communicate seamlessly

### Microsoft Agent Framework

This project uses the [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) which provides:

- **Flexible Agent Framework**: Build, orchestrate, and deploy AI agents
- **Multi-Agent Orchestration**: Group chat, sequential, concurrent, and handoff patterns
- **Plugin Ecosystem**: Native functions, OpenAPI, MCP, and more
- **LLM Support**: OpenAI, Azure OpenAI, Microsoft Foundry, and more

## 📝 Customizing Your Agents

### Adding Agent Prompts

When you're ready to define your agents' behavior, update the `instructions` in each agent:

**Agent 1** (`src/agents/agent1_server.py`):
```python
class Agent1RequestHandler(DefaultRequestHandler):
    def __init__(self):
        super().__init__()
        self.instructions = """
        Your custom Agent 1 instructions here...
        Define the role, capabilities, and behavior.
        """
```

**Agent 2** (`src/agents/agent2_server.py`):
```python
class Agent2RequestHandler(DefaultRequestHandler):
    def __init__(self):
        super().__init__()
        self.instructions = """
        Your custom Agent 2 instructions here...
        Define the role, capabilities, and behavior.
        """
```

### Integrating with LLMs

To connect your agents to an LLM (e.g., Azure OpenAI, GitHub Models):

```python
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

# Create chat client
chat_client = AzureOpenAIChatClient(credential=DefaultAzureCredential())

# Create agent with LLM
agent = chat_client.create_agent(
    name="MyAgent",
    instructions="Your agent instructions here...",
)

# Use in request handler
async def handle_message(self, message: Message) -> AsyncIterator[Event]:
    response = await agent.run(incoming_text)
    # Process and return response
```

## 🔄 Workflow Patterns

The project includes examples of different multi-agent workflow patterns:

### Sequential Workflow
```
User → Agent 1 → Agent 2 → Output
```

### Bidirectional Communication
```
Agent 1 ⟷ Agent 2 (multiple rounds)
```

Run the workflow demo:
```powershell
cd src
python workflow_orchestrator.py
```

## 🧪 Testing A2A Endpoints

### Check Agent Cards
```powershell
# Agent 1
Invoke-RestMethod http://localhost:5001/.well-known/agent.json

# Agent 2
Invoke-RestMethod http://localhost:5002/.well-known/agent.json
```

### Health Checks
```powershell
Invoke-RestMethod http://localhost:5001/health
Invoke-RestMethod http://localhost:5002/health
```

## 📚 Resources

- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [A2A Protocol Specification](https://a2a-protocol.org/latest/)
- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
- [GitHub Models](https://github.com/marketplace/models)

## 🔮 Next Steps

1. **Define Agent Prompts**: Share your agent requirements, and I'll help customize the agents
2. **Integrate LLM**: Connect to Azure OpenAI, GitHub Models, or Microsoft Foundry
3. **Add Tools**: Extend agents with function calling capabilities
4. **Build Workflows**: Create complex multi-agent orchestration patterns

## 📄 License

This project is for demonstration purposes.
