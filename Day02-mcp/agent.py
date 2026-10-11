"""
AI Pair-Programming Agent with Model Context Protocol (MCP) Integration.

Features:
    - MCP Subprocess Tool Dispatch: Tools run in decoupled child processes over stdio JSON-RPC.
    - Fault-tolerant execution: If a tool crashes, the main agent stays alive and reports the error.
    - Concurrent Tool Execution: Executes multiple tool calls in parallel using asyncio.gather().
    - Autonomous Multi-Step Reasoning: Iteratively chains diagnostic tools before producing the final answer.
    - Persistent Conversation Memory: Saves history to history.json.
"""

import asyncio
import json
import os
from pathlib import Path
import re
import sys
from dotenv import load_dotenv
from openai import AsyncOpenAI

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from mcp_client import MCPClientManager
from formatters import render_mcp_output
from orchestrator import OrchestratorEngine

# Global rich console
console = Console()

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# DevOps System Prompt with Autonomous Investigation Protocol
DEVOPS_SYSTEM_PROMPT = (
    "You are a Senior DevOps & Cloud Infrastructure Engineer. You specialize in Docker, "
    "Kubernetes, Linux system administration, CI/CD pipelines, and live incident troubleshooting.\n\n"
    "Your Guidelines:\n"
    "1. Live Cluster State Directive (Strict Freshness): Kubernetes cluster state is dynamic and changes continuously in real-time. "
    "Whenever the user asks for the status, summary, list, health, or inspection of pods, nodes, or cluster resources, "
    "you MUST NEVER answer from stale conversation memory. You MUST ALWAYS execute a fresh live diagnostic tool call "
    "(e.g. `kubectl_diagnose` with action='get_pods' and namespace='all') before providing your summary.\n"
    "2. Provide battle-tested, secure, and production-ready configurations.\n"
    "3. Autonomous Investigation Protocol: When asked to inspect pods or clusters, DO NOT stop after merely running `get_pods`. "
    "If any pod is not healthy (e.g. `ImagePullBackOff`, `CrashLoopBackOff`, `OOMKilled`, `Error`, or non-zero restarts), "
    "you MUST proactively and autonomously chain tools—invoking `describe_pod`, `get_logs`, or `get_events`—to discover the "
    "exact failure reason and error messages before presenting your final root-cause analysis and remediation.\n"
    "4. Cluster-Wide Scope: When asked to inspect the cluster, check all namespaces, or if no namespace is specified, pass namespace='all' to inspect all namespaces simultaneously. When subsequently drilling down into an unhealthy pod using describe_pod or get_logs, specify that pod's exact namespace (e.g. namespace='kube-system').\n"
    "5. GitHub PR & CI/CD Protocol:\n"
    "   - When asked to list, show, or inspect Pull Requests (PRs), dispatch `list_prs()` to display the repository's PRs.\n"
    "   - When asked why a Pull Request (PR) failed or to investigate a CI check failure, you MUST autonomously chain:\n"
    "     a. `get_pr_failed_checks(pr_number)` to discover failing jobs and their IDs.\n"
    "     b. `get_failed_job_logs(job_id)` to extract the scrubbed failure stack trace.\n"
    "     c. `get_pr_diff(pr_number)` to examine the code changes introduced by the PR.\n"
    "     d. Synthesize the root cause, identify the exact broken line in the PR diff, and output a copy-pasteable code fix in unified diff format.\n"
    "   - For GitHub PR code CI fixes, dispatch `create_remediation_pr(...)`. Never write or commit directly to `main`.\n\n"
    "6. Kubernetes & GitOps Remediation Protocol:\n"
    "   - When asked to fix a Kubernetes issue (e.g. 'can you fix this?' or 'remediate this pod'): "
    "YOU MUST FOLLOW GITOPS: First locate and read the source YAML from the repository using `find_workload_manifest(workload_name=...)`. "
    "Then synthesize the corrected manifest (e.g. companion ConfigMap and volumeMounts), and call `create_remediation_pr(...)` with "
    "the updated manifest in `new_content`, targeting a dedicated fix branch (`fix/k8s-...`). "
    "NEVER bypass Git by applying untracked changes directly with `kubectl_apply` unless the user explicitly commands a live cluster hotfix.\n"
    "   - For GitHub repository CI/CD Pull Requests: Use `create_remediation_pr(...)`.\n"
    "   - Strict Git Governance & Safety: NEVER commit or push directly to `main`. Always open an unmerged PR awaiting human maintainer review.\n"
    "   - Strict Error Honesty: NEVER claim an action succeeded if a tool call returned an error or validation failure. "
    "Always accurately report the tool output to the user.\n\n"
    "7. Operational Memory & Past Task Recall:\n"
    "   - When asked about past tasks, incidents, or fixes (e.g. 'what tasks have we performed in the past?', 'what was fixed for payment-service?', 'did we work on PR #42?'): "
    "Refer to your Operational Memory & Recent Task Journal summary below. If more detail or search is needed, "
    "autonomously dispatch `search_past_tasks(query=...)` or `list_past_tasks()` to retrieve past diagnoses, root causes, and PR links directly from the task journal."
)


def build_system_prompt() -> str:
    """Dynamically append recent task memory journal card to the system prompt."""
    try:
        from task_journal import task_journal
        summary_card = task_journal.format_prompt_summary(limit=3)
        if summary_card:
            return f"{DEVOPS_SYSTEM_PROMPT}\n{summary_card}"
    except Exception:
        pass
    return DEVOPS_SYSTEM_PROMPT


def get_clean_context(messages: list, max_messages: int = 12) -> list:
    """
    Ensure the chat context starts with the dynamic system prompt (including recent tasks)
    and slices recent messages starting cleanly on a 'user' message.
    """
    sys_prompt = build_system_prompt()
    if len(messages) <= 1:
        return [{"role": "system", "content": sys_prompt}]
    valid_msgs = [m for m in messages[1:] if m.get("content") or m.get("tool_calls")]
    slice_start = max(0, len(valid_msgs) - max_messages)
    while slice_start < len(valid_msgs) and valid_msgs[slice_start].get("role") != "user":
        slice_start += 1
    if slice_start >= len(valid_msgs):
        for i, m in enumerate(valid_msgs):
            if m.get("role") == "user":
                slice_start = i
                break
    return [{"role": "system", "content": sys_prompt}] + valid_msgs[slice_start:]


async def main():
    # Load environment variables
    env_path = BASE_DIR / ".env"
    load_dotenv(dotenv_path=env_path)

    base_url = os.getenv("BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("API_KEY", "ollama")
    model = os.getenv("MODEL", "gemma4:e4b")

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    history_file = BASE_DIR / "history.json"
    messages = [{"role": "system", "content": DEVOPS_SYSTEM_PROMPT}]

    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, list) and len(saved) > 0:
                messages = saved
                if messages[0].get("role") != "system":
                    messages.insert(0, {"role": "system", "content": DEVOPS_SYSTEM_PROMPT})
                else:
                    messages[0]["content"] = DEVOPS_SYSTEM_PROMPT
                print(f"Loaded {len(messages) - 1} previous messages from history.json")
        except Exception:
            messages = [{"role": "system", "content": DEVOPS_SYSTEM_PROMPT}]

    def save_history():
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save history: {e}")

    # Launch MCP Server child processes via MCPClientManager
    async with MCPClientManager() as mcp:
        print("═" * 70)
        print(" 🚀 DAY 02 — MODEL CONTEXT PROTOCOL (MCP) AGENT")
        print(f" Model:     {model} (via {base_url})")
        print(f" MCP Tools: {', '.join(mcp.tool_names) if mcp.tool_names else 'None'}")
        print(" Commands:  /clear (reset memory), /tokens (token ledger), exit or quit")
        print("═" * 70 + "\n")

        session_prompt_tokens = 0
        session_completion_tokens = 0

        while True:
            try:
                user_input = input("\033[1;36mYou:\033[0m ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nSession ended.")
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                print("Goodbye!")
                break

            if user_input.lower().startswith("/tokens"):
                session_total = session_prompt_tokens + session_completion_tokens
                console.print(Panel(
                    f"[bold cyan]Token Consumption Metrics (Current Session)[/bold cyan]\n\n"
                    f"  • [bold]Prompt Tokens (Input):[/bold]     {session_prompt_tokens:,}\n"
                    f"  • [bold]Completion Tokens (Output):[/bold] {session_completion_tokens:,}\n"
                    f"  • [bold]Total Session Tokens:[/bold]       {session_total:,}\n\n"
                    f"[dim]Tracking engine: Native Ollama /v1/chat/completions ground truth[/dim]",
                    title="📊 Session Token Ledger",
                    border_style="cyan",
                    expand=False,
                ))
                print()
                continue

            if user_input.lower().startswith("/clear"):
                messages = [{"role": "system", "content": DEVOPS_SYSTEM_PROMPT}]
                save_history()
                print("Conversation history cleared!\n")
                continue

            messages.append({"role": "user", "content": user_input})
            save_history()

            turn_prompt_tokens = 0
            turn_completion_tokens = 0
            turn_llm_calls = 0

            # 1. Attempt Flight Plan Orchestration (Phase-Gated SRE State Machine)
            orchestrator = OrchestratorEngine(mcp_manager=mcp, llm_client=client, model=model)
            plan_result = await orchestrator.run(user_input)

            if plan_result:
                # Flight Plan successfully completed all milestones!
                console.print("\n[bold green]🤖 AI Assistant (Incident Diagnosis & Remediation):[/bold green]\n")
                console.print(Markdown(plan_result.final_summary))
                messages.append({"role": "assistant", "content": plan_result.final_summary})
                save_history()
                if plan_result.total_tokens > 0:
                    session_prompt_tokens += plan_result.prompt_tokens
                    session_completion_tokens += plan_result.completion_tokens
                    session_total = session_prompt_tokens + session_completion_tokens
                    console.print(
                        f"\n[dim cyan]📊 [Tokens] Flight Plan Synthesis: {plan_result.total_tokens:,} "
                        f"(Prompt: {plan_result.prompt_tokens:,} | Completion: {plan_result.completion_tokens:,}) "
                        f"| Session Total: {session_total:,}[/dim cyan]"
                    )
                print()
                continue

            # 2. Fallback to General Autonomous ReAct Loop if no specialized Flight Plan matched
            max_tool_steps = 5
            step_count = 0

            # Detect if user asks for live cluster/system status or summary
            live_triggers = (
                "pod", "pods", "node", "nodes", "cluster", "status", "summary", "health",
                "check", "inspect", "list", "show", "log", "logs", "event", "events",
                "time", "date", "password", "pr", "prs", "github", "pull", "ci", "failed", "fix",
                "patch", "raise", "create", "task", "tasks", "history", "past", "journal", "remember",
                "previous", "earlier", "incident", "incidents"
            )
            user_text_lower = user_input.lower()
            requires_live_data = any(re.search(r"\b" + re.escape(t) + r"\b", user_text_lower) for t in live_triggers)

            while step_count < max_tool_steps:
                context_messages = get_clean_context(messages, max_messages=12)

                # Use 'auto' tool choice (Ollama compatibility layer returns None if 'required' is explicitly passed)
                tool_choice = "auto" if mcp.schemas else None

                try:
                    res = await client.chat.completions.create(
                        model=model,
                        messages=context_messages,
                        tools=mcp.schemas if mcp.schemas else None,
                        tool_choice=tool_choice,
                        max_tokens=2048,
                    )
                    if hasattr(res, "usage") and res.usage:
                        turn_prompt_tokens += res.usage.prompt_tokens
                        turn_completion_tokens += res.usage.completion_tokens
                        turn_llm_calls += 1
                    msg = res.choices[0].message
                except Exception as e:
                    print(f"\n\033[91mError querying LLM: {e}\033[0m\n")
                    break

                # If LLM requested tool calls, execute them on the MCP server!
                if msg.tool_calls:
                    step_count += 1

                    # Display any intermediate diagnostic observation from the model
                    if msg.content and msg.content.strip():
                        obs = msg.content.strip()
                        if "<think>" in obs and "</think>" in obs:
                            obs = obs.split("</think>")[-1].strip()
                        if obs:
                            console.print(f"\n[italic dim white]💡 {obs}[/italic dim white]")

                    # Record assistant message with tool calls
                    assistant_msg = {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in msg.tool_calls
                        ],
                    }
                    messages.append(assistant_msg)

                    # Execute all tool calls concurrently via asyncio.gather()
                    print(
                        f"\n\033[94m[MCP Agent Step {step_count} — Calling {len(msg.tool_calls)} tool(s) in parallel]\033[0m"
                    )
                    tasks = [
                        mcp.execute(tc.function.name, tc.function.arguments)
                        for tc in msg.tool_calls
                    ]
                    tool_outputs = await asyncio.gather(*tasks)

                    for tc, output in zip(msg.tool_calls, tool_outputs):
                        func_name = tc.function.name
                        func_args = tc.function.arguments
                        print(f"\033[93m  ➔ [MCP Dispatched] {func_name}({func_args})\033[0m")

                        # Render stylized, human-readable terminal UI
                        render_mcp_output(func_name, func_args, output)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": output,
                        })

                    save_history()
                    # Continue the investigation loop so LLM can read outputs and chain next tool
                    continue
                else:
                    # Final synthesis reached
                    answer = msg.content or ""
                    if "<think>" in answer and "</think>" in answer:
                        answer = answer.split("</think>")[-1].strip()

                    # Filter residual regex artifacts
                    answer = re.sub(r"\*\([^\)]*\)\*", "", answer).strip()

                    # Fallback synthesis pass if model produced empty text after tool execution
                    if not answer.strip() and step_count > 0:
                        try:
                            synth_prompt = (
                                "Based on the live tool and diagnostic outputs above, provide a clear, "
                                "concise summary answering the user request, explaining the status and root causes."
                            )
                            synth_res = await client.chat.completions.create(
                                model=model,
                                messages=context_messages + [{"role": "user", "content": synth_prompt}],
                                max_tokens=1500,
                            )
                            if hasattr(synth_res, "usage") and synth_res.usage:
                                turn_prompt_tokens += synth_res.usage.prompt_tokens
                                turn_completion_tokens += synth_res.usage.completion_tokens
                                turn_llm_calls += 1
                            answer = synth_res.choices[0].message.content or ""
                            if "<think>" in answer and "</think>" in answer:
                                answer = answer.split("</think>")[-1].strip()
                            answer = re.sub(r"\*\([^\)]*\)\*", "", answer).strip()
                        except Exception as e:
                            print(f"\033[93m[Synthesis fallback warning]: {e}\033[0m")

                    if not answer.strip():
                        answer = "Diagnostic operations completed. Please review the live command output above."

                    print()
                    console.print("[bold green]🤖 AI Assistant:[/bold green]")
                    console.print(Markdown(answer))
                    messages.append({"role": "assistant", "content": answer})
                    save_history()

                    turn_total = turn_prompt_tokens + turn_completion_tokens
                    session_prompt_tokens += turn_prompt_tokens
                    session_completion_tokens += turn_completion_tokens
                    session_total = session_prompt_tokens + session_completion_tokens

                    if turn_total > 0:
                        calls_str = f" across {turn_llm_calls} call{'s' if turn_llm_calls != 1 else ''}" if turn_llm_calls > 1 else ""
                        console.print(
                            f"\n[dim cyan]📊 [Tokens] Turn: {turn_total:,} "
                            f"(Prompt: {turn_prompt_tokens:,} | Completion: {turn_completion_tokens:,}{calls_str}) "
                            f"| Session Total: {session_total:,}[/dim cyan]"
                        )
                    print()
                    break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting cleanly...")
