# 🧠 Agent Operational Memory & Workspace Guidelines

> **Scope**: Applies across the entire repository (`/Users/tusharswami/Documents/ai`)  
> **Authority**: System Rules & Continuous Engineering Practices  

---

## 📌 1. Continuous Documentation Mandate (CRITICAL)

As a mandatory continuous engineering practice, **whenever any phase, step, feature, bug fix, or architectural change is implemented or modified**:

1. **Update `Day02-mcp/JOURNEY_AND_STAGES.md`**:
   - Mark completed checkboxes (`[x]`).
   - Record exact implementation details, design decisions, and trade-offs.
   - Log verification output (test results, terminal screenshots, or execution traces).
2. **Update `Day02-mcp/README.md`**:
   - Keep architectural diagrams, directory trees, tool catalogs, and CLI usage up to date.
   - Ensure quick links to deep-dive documentation remain synchronized.
3. **Preserve Context & History**:
   - Never delete previous historical stages (Day 01 evolution, Stages 0–5); append new milestones chronologically.

---

## 🛡️ 2. Core Safety & Git Governance Mandates

1. **Protected Branch Rule**:
   - ⛔ **NEVER write directly to the `main` or `master` branch.**
   - ⛔ **NEVER push commits directly to `origin/main` or `origin/master`.**
   - ⛔ **NEVER auto-merge Pull Requests.** Pull Requests must remain in `OPEN` state for human-in-the-loop review.
2. **Remediation Workflow**:
   - Always create a dedicated branch: `fix/<issue-name-or-pr-id>`.
   - Run the local automated test suite (`pytest tests/`) as a required pre-commit quality gate.
   - Push only to the feature branch and raise a Pull Request against `main`.

---

## ⚙️ 3. FastMCP & Code Quality Standards

1. **Tool Signature Enforcement**:
   - FastMCP introspects function signatures to generate JSON-RPC schemas.
   - **`**kwargs` is strictly forbidden** in FastMCP tools (`ValueError: Functions with **kwargs are not supported`).
   - All tool arguments must be explicitly declared with type annotations and optional defaults (e.g. `diff: str | None = None`).
2. **Local Model Efficiency**:
   - Optimize for local Ollama inference (`gemma4:e4b`).
   - Protect the model's context window: use regex log scrubbers and context pruning between milestones so raw logs do not degrade attention.
