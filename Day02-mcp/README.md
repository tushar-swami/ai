# 🚀 Day 02 — Model Context Protocol (MCP) Agent Framework

This project builds an autonomous AI engineering assistant powered by **Model Context Protocol (MCP)**, completely separating tool execution from the agent's core brain.

---

## 🏛️ Architecture Overview

In Day 01, tools were imported directly into the agent's Python process. In Day 02, tools run as **independent child processes** communicating over standard JSON-RPC 2.0 (`stdio`).

```
┌────────────────────────────────────────────────────────┐
│               Agent Process (agent.py)                 │
│                                                        │
│   User Prompt ──► Ollama LLM (gemma4:e4b)              │
│                          │                             │
│                          ▼ (Tool Call Request)         │
│                 MCPClientManager                       │
└──────────────┬──────────────────────────┬──────────────┘
               │ stdio JSON-RPC           │ stdio JSON-RPC
               ▼                          ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│  Server 1: k8s_server.py     │ │  Server 2: system_server.py  │
│  (FastMCP Subprocess)        │ │  (FastMCP Subprocess)        │
│                              │ │                              │
│  • kubectl_diagnose          │ │  • read_file, list_files     │
│                              │ │  • get_current_datetime      │
│                              │ │  • generate_password         │
│                              │ │  • roll_dice                 │
│                              │ │  • search_knowledge (BM25)   │
└──────────────────────────────┘ └──────────────────────────────┘
```

---

## 🌟 Why MCP? (Key Architectural Advantages)

1. **Zero Blast-Radius & Fault Isolation**: If an external tool hangs on a network socket, hits a C-extension memory crash, or throws an unhandled exception, `agent.py` never crashes. The client catches the error and reports it cleanly to the LLM.
2. **Multi-Server Microservices**: Tools are separated by domain into specialized servers (`kubernetes` and `system`), preventing monolith bloat.
3. **Standardized Ecosystem**: Any MCP server (GitHub, PostgreSQL, Filesystem, Brave Search) can be added simply by listing it in `mcp_servers.json`.
4. **Language Independence (Polyglot)**: Tools can be written in Go, Rust, or Node.js without changing a line of Python code.
5. **Parallel Execution**: Tools requested in the same step run concurrently via `asyncio.gather()`.

---

## 📁 Directory Structure

```
Day02-mcp/
├── .env                  # Ollama endpoint & model settings
├── mcp_servers.json      # Declarative MCP multi-server catalog
├── k8s_server.py         # Subprocess 1: FastMCP server for Kubernetes
├── system_server.py      # Subprocess 2: FastMCP server for files, datetime, & search
├── mcp_client.py         # Dynamic MCP client bridge (spawns servers & translates schemas)
├── agent.py              # Interactive DevOps assistant with autonomous investigation
├── history.json          # Persistent conversation history
├── data/                 # Sample diagnostic pod manifests (OOMKilled, LivenessProbe, etc.)
├── knowledge/            # Knowledge base documents (Japan, Marie Curie, deep ocean, etc.)
└── README.md             # This guide
```

---

## 💻 How to Run & Test

> [!IMPORTANT]
> Ensure you activate the root virtual environment where `fastmcp` and `mcp` are installed:
> ```bash
> cd Day02-mcp
> source ../.venv/bin/activate
> ```

### 1. Launch the Autonomous MCP Agent
```bash
python agent.py
```
- Available in-chat commands:
  - `/clear` — Reset conversation history
  - `exit` or `quit` — Leave session

### 2. Test the FastMCP Server Standalone
You can inspect the tools exposed by `k8s_server.py` directly:
```bash
python -c "
import asyncio
from k8s_server import mcp
tools = asyncio.run(mcp.list_tools())
print('Server Tools:', [t.name for t in tools])
"
```

### 3. Test the MCP Client Bridge
Test the stdio JSON-RPC handshake and execution without launching the chat loop:
```bash
python -c "
import asyncio
from mcp_client import MCPClientManager

async def test():
    async with MCPClientManager() as mcp:
        print('Discovered MCP tools:', mcp.tool_names)
        res = await mcp.execute('kubectl_diagnose', {'action': 'get_pods'})
        print('Tool response:\n', res)

asyncio.run(test())
"
```

---

## 🔌 How to Add New MCP Servers

To connect your agent to other tools, simply edit [`mcp_servers.json`](file:///Users/tusharswami/Documents/ai/Day02-mcp/mcp_servers.json):

```json
{
  "mcpServers": {
    "kubernetes": {
      "command": "python",
      "args": ["k8s_server.py"],
      "description": "Safe read-only Kubernetes diagnostics"
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "your-token-here"
      }
    }
  }
}
```
On next launch, `agent.py` will automatically start the new server, discover its tools, and provide them to the LLM!
