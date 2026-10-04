# 🚀 AI Engineering Project Tracker — Day 01

> **Status:** Active & Production-Ready Architecture  
> **Last Updated:** 2026-10-04  
> **Current LLM:** `gemma4:e4b` (via local Ollama on `http://localhost:11434/v1`)  
> **Primary Directory:** [`/Users/tusharswami/Documents/ai/Day01`](file:///Users/tusharswami/Documents/ai/Day01)

---

## 📑 Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Active Tools Catalog (7 Tools)](#active-tools-catalog-7-tools)
3. [Agent Personas & System Prompts](#-agent-personas--system-prompts-personaspy)
4. [Knowledge Database](#knowledge-database)
5. [Completed Milestones & Git History](#completed-milestones)
6. [How to Run & Test](#how-to-run--test)
7. [Pending Tasks & Future Roadmap](#pending-tasks--future-roadmap)

---

## 🏛️ Architecture Overview

The system is built as a modular, extensible AI pair-programming and reasoning agent capable of automated tool calling and document question answering.

```
Day01/
├── hello_ai.py               # Interactive CLI chat assistant with streaming & tool dispatch
├── personas.py               # Extensible Persona Manager (Smart AI, DevOps Expert, Software Engineer)
├── rag.py                    # Dual-engine RAG: BM25 keyword + nomic-embed-text vector embeddings
├── .env                      # Configuration (BASE_URL, API_KEY, MODEL, EMBEDDING_BASE_URL, EMBEDDING_API_KEY, EMBEDDING_MODEL)
├── history.json              # Persistent conversation memory
├── PROJECT_TRACKER.md        # Living project roadmap and status (this document)
├── .cache/                   # Persistent vector embedding disk cache (git-ignored)
│
├── data/                     # General user documents & test manifests
│   ├── test.txt              # Shopping list sample document
│   ├── broken_pod.yaml       # CrashLoopBackOff test pod (missing /etc/config/database.json)
│   ├── broken_oom_pod.yaml   # OOMKilled test pod (Exit Code 137, RAM exceeded)
│   ├── broken_probe_pod.yaml # Failed Liveness Probe test pod (HTTP 404)
│   └── broken_image_pod.yaml # ImagePullBackOff test pod (non-existent image tag)
│
├── knowledge/                # Domain knowledge database (~50 lines each)
│   ├── japan.txt             # Geography, history, economy, Washoku cuisine
│   ├── snow_leopard.txt      # Habitat, morphology, hunting, conservation
│   ├── marie_curie.txt       # Early life, radioactivity discoveries, Nobel prizes
│   ├── alien_life.txt        # Drake equation, Fermi paradox, SETI, Wow! signal
│   └── deep_ocean.txt        # Mariana trench, Challenger deep, hydrothermal vents
│
└── tools/                    # Tool Manager Package (Auto-Discovery)
    ├── __init__.py           # Dynamic module scanner (pkgutil)
    ├── registry.py           # ToolRegistry singleton & @tool decorator
    ├── datetime_tools.py     # get_current_datetime (time / date / all)
    ├── fun_tools.py          # roll_dice (N-sided dice)
    ├── security_tools.py     # generate_password (cryptographically secure)
    ├── file_tools.py         # read_file & list_files (workspace-bounded file operations)
    ├── rag_tools.py          # search_knowledge (BM25 & vector knowledge base search)
    └── k8s_tools.py          # kubectl_diagnose (safe read-only Kubernetes diagnostics)
```

---

## 🛠️ Active Tools Catalog (7 Tools)

Every tool is defined with the `@tool` decorator in `tools/*_tools.py` and is automatically discovered and passed to the LLM on startup.

| # | Tool Name | Module | Parameters | Description |
|---|-----------|--------|------------|-------------|
| 1 | `get_current_datetime` | `datetime_tools.py` | `format_type: 'time'\|'date'\|'all'`, `timezone_str` | Formats current date/time in `dd-mm-yyyy hh:mm:ss` format. |
| 2 | `roll_dice` | `fun_tools.py` | `sides: integer` (default: 6) | Rolls an N-sided die and returns only the integer result. |
| 3 | `generate_password` | `security_tools.py` | `length: integer` (12), `include_special: bool` | Generates a cryptographically secure random password. |
| 4 | `list_files` | `file_tools.py` | `directory: 'all'\|'knowledge'\|'data'` | Lists all available text files with line counts across directories. |
| 5 | `read_file` | `file_tools.py` | `file_path: string` | Safely reads local files (searches `knowledge/`, `data/`, project dir). Restricts reads to workspace. |
| 6 | `search_knowledge` | `rag_tools.py` | `query: string`, `top_k: integer` (3) | Searches the knowledge database using BM25 and returns top matching snippets with line citations. |
| 7 | `kubectl_diagnose` | `k8s_tools.py` | `action: 'get_pods'\|'describe_pod'\|'get_logs'\|'get_events'`, `pod_name`, `namespace`, `previous`, `tail` | Safe read-only Kubernetes diagnostic command runner for troubleshooting pods. |

---

## 🎭 Agent Personas & System Prompts (`personas.py`)

A modular role management system that allows the AI to act as a general assistant or specialized expert.

### Built-in Personas
| Key | Role Name | Focus Area & Capabilities |
|---|---|---|
| `general` | **Smart AI Agent** *(Default)* | Versatile general-purpose AI assistant with access to local tools. |
| `devops` | **DevOps Expert Agent** | Specialist in Docker, Kubernetes, CI/CD pipelines, Linux, Terraform, Prometheus/Grafana, cloud infra, and incident debugging. |
| `coder` | **Senior Software Engineer** | Specialist in clean architecture, Python design patterns, algorithms, performance, and code reviews. |
| `custom` | **Custom Persona** | Prompts user to enter an ad-hoc custom system prompt. |

### How It Works:
1. **Interactive Login Selection**: On launching `python hello_ai.py`, an interactive menu appears. Pressing **Enter** activates the default (`Smart AI Agent`), or press `2` for `DevOps Expert Agent`.
2. **In-Chat Switching**:
   - `/role` — View the currently active persona and list all available roles.
   - `/role devops` — Instantly switch to the DevOps Expert (resets history for memory hygiene).
   - `/role general` — Switch back to the general Smart AI Agent.
3. **Adding New Roles in the Future**:
   Simply add a new entry to the `PERSONAS` dictionary in [`personas.py`](file:///Users/tusharswami/Documents/ai/Day01/personas.py):
   ```python
   "security": Persona(
       key="security",
       name="Cybersecurity Analyst",
       description="Security auditing, penetration testing & threat modeling",
       prompt="You are a Senior Cybersecurity Analyst..."
   )
   ```

---

## 📚 Knowledge Database

Created in `Day01/knowledge/` to serve as our indexed facts database:

- **`japan.txt`** (52 lines): Japan's archipelago, Tokyo, Mount Fuji, Heian/Edo/Meiji history, Shinkansen, Washoku cuisine, anime, and demographics.
- **`snow_leopard.txt`** (52 lines): *Panthera uncia*, Himalayan habitat, snowshoe paws, tail counterweight, hunting behavior, and IUCN vulnerability.
- **`marie_curie.txt`** (52 lines): Flying University, Sorbonne studies, isolation of radium and polonium, 1903/1911 Nobel Prizes, WWI "petites Curies".
- **`alien_life.txt`** (52 lines): Drake equation, Fermi paradox, Big Ear Wow! Signal, Europa/Enceladus oceans, Dyson spheres, Kardashev scale.
- **`deep_ocean.txt`** (52 lines): Mariana Trench, Challenger Deep (10,928m), hydrothermal vents, chemosynthesis, bioluminescent fauna.

---

## 📜 Completed Milestones & Git History

```text
0a3cf34 feat(Day01): add autonomous investigation protocol to DevOps persona prompt and update PROJECT_TRACKER.md
c979e9f docs(Day01): update PROJECT_TRACKER.md with recent milestones
93dbd91 fix(Day01): add get_clean_context helper to prevent orphaned tool messages in context window
6301750 perf(Day01): add max_tokens=2048 to prevent answer truncation on long multi-pod diagnostics
0a4d35b feat(Day01): add OOMKilled, LivenessProbe, and ImagePullBackOff diagnostic test manifests and update PROJECT_TRACKER.md
6f06bab feat(Day01): implement autonomous multi-step agent loop in hello_ai.py and update PROJECT_TRACKER.md
4313631 feat(Day01): add safe read-only kubectl diagnostic tool for Kubernetes pod troubleshooting
8dbf4e7 feat(Day01): add extensible agent persona system (Smart AI, DevOps Expert) with startup menu and /role command
c04656b feat(Day01): add dedicated EMBEDDING_BASE_URL and EMBEDDING_API_KEY support in rag.py and PROJECT_TRACKER.md
188518d feat(Day01): add configurable dense vector RAG with nomic-embed-text, disk caching, and comparison CLI
a7fd588 feat(Day01): add list_files tool with folder grouping and line counts, update PROJECT_TRACKER.md
ef7e6a2 feat(Day01): add pure-Python BM25 RAG system, search_knowledge tool, knowledge base, and PROJECT_TRACKER.md
382f2d6 feat(Day01): add file reading tool with smart path resolution and workspace boundary checks
8593476 refactor(Day01): replace flat tools.py with tool manager (registry + auto-discovery)
9241614 feat(Day01): integrate tools into hello_ai.py with automated tool execution
211ce0d feat(Day01): rename tool.py to tools.py, add dice and password tools, and optimize CLI
502ac87 feat(Day01): add tool.py with current datetime tool and schema
98f8ad3 chore(Day01): update DEFAULT_SYSTEM_PROMPT to smart AI agent
9d3d632 perf(Day01): add sliding window and live thinking status indicator
136e082 feat(Day01): suppress stage directions and action monologues from assistant output
31f2be4 feat(Day01): filter internal thinking stream and add /think toggle
5724a5e feat(Day01): add interactive chat script with persistent history
```

### Key Technical Achievements:
- **Autonomous Multi-Step Agentic Loop**: Upgraded `hello_ai.py` from single-step tool execution to an iterative multi-step reasoning loop (up to 5 sequential tool invocations). The agent can autonomously run a sequence of diagnostic tools (e.g. `get_pods` → `get_logs` → `get_events`) before producing the final synthesized root cause and remediation.
- **Agentic 2-Step Tool Loop**: Model decides if tools are required → tool executes locally → result fed back to model for synthesized streaming answer.
- **Tool Manager Architecture**: Scalable plugin system replacing flat dicts with decorator-based registry and dynamic auto-discovery (`pkgutil`). Adding new tools requires zero changes to `hello_ai.py`.
- **Extensible Agent Personas (`personas.py`)**: Multi-role system with startup menu and mid-chat `/role` switching (Smart AI, DevOps Expert, Software Engineer, Custom).
- **Safe Kubernetes Diagnostics (`kubectl_diagnose`)**: Principle of Least Privilege (PoLP) tool allowing read-only inspection (`get_pods`, `describe_pod`, `get_logs`, `get_events`) while strictly blocking all mutating/exec commands.
- **Dual-Engine RAG**:
  - **BM25 Engine**: Custom chunker with sliding overlap and probabilistic BM25 ranking (pure Python).
  - **Vector Semantic Engine**: 768-dimensional dense vector embeddings using `nomic-embed-text:latest` (or `mxbai-embed-large:latest`) via Ollama, controlled by `EMBEDDING_MODEL` in `.env`.
  - **Side-by-Side Comparison**: `--compare` CLI flag to contrast keyword matching against semantic vector similarity.
  - **Persistent Disk Caching**: Cached under `.cache/` for instant sub-second startup on repeated queries.

---

## 💻 How to Run & Test

> [!IMPORTANT]
> Ensure the virtual environment is activated before running scripts, or run via `.venv` Python:
> ```bash
> # From project root:
> source .venv/bin/activate
> # Or if navigating into Day01:
> source ../.venv/bin/activate
> ```

### 1. Interactive Chat Assistant
```bash
# From Day01 directory:
cd Day01
source ../.venv/bin/activate
python hello_ai.py

# Or directly from project root:
.venv/bin/python Day01/hello_ai.py
```
- Available in-chat commands:
  - `/clear [optional persona]` — Reset conversation memory (and set custom persona)
  - `/think` — Toggle showing internal reasoning traces
  - `exit` or `quit` — Leave session

### 2. Standalone RAG CLI & Comparison
```bash
# Query the knowledge base and get an AI-generated answer with citations:
python rag.py "Who was the first woman to win a Nobel Prize?"

# Perform raw search only (uses EMBEDDING_MODEL from .env):
python rag.py --search "Mariana Trench depth"

# Compare BM25 vs nomic-embed-text side-by-side on the same query:
python rag.py --compare "feline predators in freezing mountains"

# Force a specific engine on demand:
python rag.py --model bm25 "snow leopard habitat"
python rag.py --model nomic-embed-text:latest "snow leopard habitat"
```

### 3. Tool Testing (Individual CLI)
```bash
# Test registry directly:
python -c "from tools import registry; print(registry.tool_names)"

# List available files:
python -m tools.file_tools list

# Read specific file:
python -m tools.file_tools test.txt

# Test knowledge search tool:
python -m tools.rag_tools "snow leopard camouflage"
```

### 4. Kubernetes Diagnostic Testing (DevOps Expert Agent)
```bash
# Scenario A: Test OOMKilled failure (Exit Code 137)
kubectl apply -f data/broken_oom_pod.yaml

# Scenario B: Test Liveness Probe failure (HTTP 404)
kubectl apply -f data/broken_probe_pod.yaml

# Scenario C: Test ImagePullBackOff (Manifest Unknown)
kubectl apply -f data/broken_image_pod.yaml

# Launch assistant and ask DevOps agent to diagnose:
python hello_ai.py
# Select [2] DevOps Expert Agent and prompt:
# "Inspect my default namespace, find the failing pod, check why it is failing, and explain the fix."
```

---

## 🔮 Pending Tasks & Future Roadmap

- [x] **Option A: Pure Python BM25 RAG** (Completed: zero-dependency probabilistic ranking)
- [x] **Option B: Semantic Vector RAG** (Completed: `nomic-embed-text:latest` via Ollama with disk caching)
- [ ] **Hybrid Search with Reciprocal Rank Fusion (RRF)**
  - Combine BM25 keyword rankings with dense vector cosine rankings for maximum retrieval precision.
- [ ] **Persistent SQLite Database Memory**
  - Migrate `history.json` to an indexed SQLite database to store user sessions, timestamps, tool execution logs, and analytics.
- [ ] **Multi-Format Document Ingestion**
  - Add loaders for `.pdf`, `.docx`, and `.md` files to automatically parse and ingest documents into `knowledge/`.
- [ ] **Web Search Tool**
  - Add a tool (e.g. `search_web`) to retrieve real-time data from the internet when knowledge files don't have the answer.
- [ ] **Evaluation & Benchmarks**
  - Create a test suite measuring retrieval accuracy (Precision@k, Recall@k) on knowledge questions.
