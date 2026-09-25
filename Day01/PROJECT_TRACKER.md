# 🚀 AI Engineering Project Tracker — Day 01

> **Status:** Active & Production-Ready Architecture  
> **Last Updated:** 2026-09-25  
> **Current LLM:** `gemma4:e4b` (via local Ollama on `http://localhost:11434/v1`)  
> **Primary Directory:** [`/Users/tusharswami/Documents/ai/Day01`](file:///Users/tusharswami/Documents/ai/Day01)

---

## 📑 Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Active Tools Catalog (6 Tools)](#active-tools-catalog-6-tools)
3. [Knowledge Database](#knowledge-database)
4. [Completed Milestones & Git History](#completed-milestones)
5. [How to Run & Test](#how-to-run--test)
6. [Pending Tasks & Future Roadmap](#pending-tasks--future-roadmap)

---

## 🏛️ Architecture Overview

The system is built as a modular, extensible AI pair-programming and reasoning agent capable of automated tool calling and document question answering.

```
Day01/
├── hello_ai.py               # Interactive CLI chat assistant with streaming & tool dispatch
├── rag.py                    # Dual-engine RAG: BM25 keyword + nomic-embed-text vector embeddings
├── .env                      # Configuration (BASE_URL, API_KEY, MODEL, EMBEDDING_MODEL)
├── history.json              # Persistent conversation memory
├── PROJECT_TRACKER.md        # Living project roadmap and status (this document)
├── .cache/                   # Persistent vector embedding disk cache (git-ignored)
│
├── data/                     # General user documents
│   └── test.txt              # Shopping list sample document
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
    ├── file_tools.py         # read_file (safe workspace-bounded file reader)
    └── rag_tools.py          # search_knowledge (BM25 knowledge base search)
```

---

## 🛠️ Active Tools Catalog (6 Tools)

Every tool is defined with the `@tool` decorator in `tools/*_tools.py` and is automatically discovered and passed to the LLM on startup.

| # | Tool Name | Module | Parameters | Description |
|---|-----------|--------|------------|-------------|
| 1 | `get_current_datetime` | `datetime_tools.py` | `format_type: 'time'\|'date'\|'all'`, `timezone_str` | Formats current date/time in `dd-mm-yyyy hh:mm:ss` format. |
| 2 | `roll_dice` | `fun_tools.py` | `sides: integer` (default: 6) | Rolls an N-sided die and returns only the integer result. |
| 3 | `generate_password` | `security_tools.py` | `length: integer` (12), `include_special: bool` | Generates a cryptographically secure random password. |
| 4 | `list_files` | `file_tools.py` | `directory: 'all'\|'knowledge'\|'data'` | Lists all available text files with line counts across directories. |
| 5 | `read_file` | `file_tools.py` | `file_path: string` | Safely reads local files (searches `knowledge/`, `data/`, project dir). Restricts reads to workspace. |
| 6 | `search_knowledge` | `rag_tools.py` | `query: string`, `top_k: integer` (3) | Searches the knowledge database using BM25 and returns top matching snippets with line citations. |

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
- **Agentic 2-Step Tool Loop**: Model decides if tools are required → tool executes locally → result fed back to model for synthesized streaming answer.
- **Tool Manager Architecture**: Scalable plugin system replacing flat dicts with decorator-based registry and dynamic auto-discovery (`pkgutil`). Adding new tools requires zero changes to `hello_ai.py`.
- **Dual-Engine RAG**:
  - **BM25 Engine**: Custom chunker with sliding overlap and probabilistic BM25 ranking (pure Python).
  - **Vector Semantic Engine**: 768-dimensional dense vector embeddings using `nomic-embed-text:latest` (or `mxbai-embed-large:latest`) via Ollama, controlled by `EMBEDDING_MODEL` in `.env`.
  - **Side-by-Side Comparison**: `--compare` CLI flag to contrast keyword matching against semantic vector similarity.
  - **Persistent Disk Caching**: Cached under `.cache/` for instant sub-second startup on repeated queries.

---

## 💻 How to Run & Test

### 1. Interactive Chat Assistant
```bash
cd Day01
python hello_ai.py
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
