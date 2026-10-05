# 🚀 Day 02 — Model Context Protocol (MCP) Agent Framework

> 📖 **Full Engineering Journey & Multi-Agent Roadmap**: See [`JOURNEY_AND_STAGES.md`](./JOURNEY_AND_STAGES.md) for the step-by-step evolution of how every stage was designed and achieved.

This project builds an autonomous AI engineering assistant powered by **Model Context Protocol (MCP)**, completely separating tool execution from the agent's core brain.

---

## 🏛️ Architecture Overview

In Day 01, tools were imported directly into the agent's Python process. In Day 02, tools run as **independent child processes** communicating over standard JSON-RPC 2.0 (`stdio`), orchestrated by an extensible **SRE Flight Plan State Machine**.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Agent Process (agent.py)                        │
│                                                                        │
│   User Prompt ──────────► OrchestratorEngine (orchestrator.py)         │
│                                  │                                     │
│                     ┌────────────┴────────────┐                        │
│                     ▼                         ▼                        │
│              [Flight Plan Match]     [Fallback General ReAct]          │
│             M1 ➔ M2 ➔ M3 ➔ M4        Ollama LLM (gemma4:e4b)           │
│                     │                         │                        │
│                     └────────────┬────────────┘                        │
│                                  ▼                                     │
│                          MCPClientManager                              │
└──────────────┬────────────────────┬────────────────────┬───────────────┘
               │ stdio JSON-RPC     │ stdio JSON-RPC     │ stdio JSON-RPC
               ▼                    ▼                    ▼
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│ Server 1: k8s_server.py │ │Server 2:system_server.py│ │Server 3:github_server.py│
│  (FastMCP Subprocess)   │ │  (FastMCP Subprocess)   │ │  (FastMCP Subprocess)   │
│                         │ │                         │ │                         │
│ • kubectl_diagnose      │ │ • read_file, list_files │ │ • list_prs              │
│   (pods, nodes, logs,   │ │ • get_current_datetime  │ │ • get_pr_failed_checks  │
│    events, describe)    │ │ • generate_password     │ │ • get_failed_job_logs   │
│                         │ │ • roll_dice             │ │   (regex log scrubber)  │
│                         │ │ • search_knowledge      │ │ • get_pr_diff           │
│                         │ │                         │ │ • create_remediation_pr │
└─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘
```

---

## 🌟 Why MCP & SRE Flight Plans? (Key Architectural Advantages)

1. **Pluggable Flight Plan Orchestrator**: Executes structured 4-phase incident resolutions (`DISCOVER` ➔ `DIAGNOSE` ➔ `ISOLATE` ➔ `REMEDIATE`) with live terminal dashboards.
2. **Zero Blast-Radius & Fault Isolation**: External tools run in child processes. Failures over JSON-RPC are caught gracefully without terminating the agent.
3. **Dynamic Tool Scoping**: Injects *only* the tools relevant to the active domain (e.g. K8s tools for clusters, GitHub tools for PRs), eliminating LLM hallucination and saving tokens.
4. **Context Window Garbage Collection**: Prunes raw multi-thousand-line logs after each milestone, feeding only 1-line distilled artifact summaries forward.
5. **Strict Git & Branch Governance**: Pre-commit automated test gate verification (`pytest tests/`), safe feature branching (`fix/pr-XX`), and **zero direct commits to `main`**.

---

## 📁 Directory Structure

```
Day02-mcp/
├── .env                  # Ollama endpoint & model settings
├── mcp_servers.json      # Declarative MCP tri-server catalog (k8s, system, github)
├── orchestrator.py       # SRE Flight Plan Orchestrator (GitHub CI & K8s plans)
├── k8s_server.py         # Subprocess 1: FastMCP server for Kubernetes diagnostics
├── system_server.py      # Subprocess 2: FastMCP server for files, datetime, & BM25 search
├── github_server.py      # Subprocess 3: FastMCP server for PR failure & CI log diagnostics
├── mcp_client.py         # Dynamic MCP client bridge (spawns servers & translates schemas)
├── formatters.py         # Terminal Rich formatters, Flight Plan dashboards, & diff panels
├── agent.py              # Interactive DevOps assistant with autonomous multi-step reasoning
├── JOURNEY_AND_STAGES.md # Living retrospective, stage tracker, and multi-agent roadmap
├── history.json          # Persistent conversation history
├── data/                 # Sample pod manifests and mock PR fixtures
│   ├── sample_pr/        # Mock fixtures for PR #42 (checks.json, failed_test_log.txt, diff.patch)
│   ├── broken_pod.yaml
│   └── ...
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

### 3. Test GitHub CI Diagnostics Standalone
Inspect PR #42's failed checks, scrubbed failure logs, and code diff:
```bash
python -c "
import asyncio
from github_server import get_pr_failed_checks, get_failed_job_logs, get_pr_diff

async def test():
    print('--- Failed Checks ---')
    print(await get_pr_failed_checks(42))
    print('--- Scrubbed Logs (Job 987654321) ---')
    print(await get_failed_job_logs(987654321))
    print('--- Code Diff ---')
    print(await get_pr_diff(42))

asyncio.run(test())
"
```

### 4. Interactive Autonomous In-Chat Prompts
Launch `python agent.py` and test these scenarios:
1. **SRE Flight Plan: Kubernetes CrashLoop Incident Triage**:
   - *"Why is my payment pod crashing in kubernetes?"*
   - Flight Plan executes 4 discrete milestones: `M1_DISCOVER` ➔ `M2_DIAGNOSE` ➔ `M3_ISOLATE` ➔ `M4_REMEDIATE`.
2. **SRE Flight Plan: GitHub CI/CD Auto-Remediation**:
   - *"Triage and fix failing checks on PR #42"*
   - Chained deterministic milestones: scrubbed logs ➔ diff correlation ➔ local `pytest` gate ➔ PR creation.
3. **Informational Kubernetes Cluster Queries (Fast-Path ReAct)**:
   - *"Show me the pod status and summary of all pods running in my kubernetes environment"*
   - *"Describe the nodes and check if there is memory pressure"*
4. **Multi-Domain System Queries**:
   - *"What is the current time and can you roll an 8-sided die?"*
   - *"Search knowledge base for Mariana Trench and generate a 16-character password"*

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
