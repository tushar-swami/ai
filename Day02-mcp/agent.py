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

from mcp_client import MCPClientManager
from formatters import render_mcp_output

# Global rich console
console = Console()

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# DevOps System Prompt with Autonomous Investigation Protocol
DEVOPS_SYSTEM_PROMPT = (
    "You are a Senior DevOps & Cloud Infrastructure Engineer. You specialize in Docker, "
    "Kubernetes, Linux system administration, CI/CD pipelines, and live incident troubleshooting.\n\n"
    "Your Guidelines:\n"
    "1. Provide battle-tested, secure, and production-ready configurations.\n"
    "2. You have access to Kubernetes diagnostics (`kubectl_diagnose`) running over Model Context Protocol (MCP).\n"
    "3. Autonomous Investigation Protocol: When asked to inspect pods or clusters, DO NOT stop after merely running `get_pods`. "
    "If any pod is not healthy (e.g. `ImagePullBackOff`, `CrashLoopBackOff`, `OOMKilled`, `Error`, or non-zero restarts), "
    "you MUST proactively and autonomously chain tools—invoking `describe_pod`, `get_logs`, or `get_events`—to discover the "
    "exact failure reason and error messages before presenting your final root-cause analysis and remediation.\n"
    "4. Cluster-Wide Scope: When asked to inspect the cluster, check all namespaces, or if no namespace is specified, pass namespace='all' to inspect all namespaces simultaneously. When subsequently drilling down into an unhealthy pod using describe_pod or get_logs, specify that pod's exact namespace (e.g. namespace='kube-system')."
)


def get_clean_context(messages: list, max_messages: int = 12) -> list:
    """
    Ensure the chat context starts with the system prompt and slices recent messages
    starting cleanly on a 'user' message, preventing orphaned tool or assistant turns.
    """
    if len(messages) <= 1:
        return messages
    valid_msgs = [m for m in messages[1:] if m.get("content") or m.get("tool_calls")]
    slice_start = max(0, len(valid_msgs) - max_messages)
    while slice_start < len(valid_msgs) and valid_msgs[slice_start].get("role") != "user":
        slice_start += 1
    if slice_start >= len(valid_msgs):
        for i, m in enumerate(valid_msgs):
            if m.get("role") == "user":
                slice_start = i
                break
    return [messages[0]] + valid_msgs[slice_start:]


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
        print(" Commands:  /clear (reset memory), exit or quit")
        print("═" * 70 + "\n")

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

            if user_input.lower().startswith("/clear"):
                messages = [{"role": "system", "content": DEVOPS_SYSTEM_PROMPT}]
                save_history()
                print("Conversation history cleared!\n")
                continue

            messages.append({"role": "user", "content": user_input})
            save_history()

            # Autonomous Multi-Step Reasoning Loop (up to 5 autonomous investigation steps)
            max_tool_steps = 5
            step_count = 0

            while step_count < max_tool_steps:
                context_messages = get_clean_context(messages, max_messages=12)

                try:
                    res = await client.chat.completions.create(
                        model=model,
                        messages=context_messages,
                        tools=mcp.schemas if mcp.schemas else None,
                        max_tokens=2048,
                    )
                    msg = res.choices[0].message
                except Exception as e:
                    print(f"\n\033[91mError querying LLM: {e}\033[0m\n")
                    break

                # If LLM requested tool calls, execute them on the MCP server!
                if msg.tool_calls:
                    step_count += 1

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

                    print()
                    console.print("[bold green]🤖 AI Assistant:[/bold green]")
                    console.print(Markdown(answer))
                    print()
                    messages.append({"role": "assistant", "content": answer})
                    save_history()
                    break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting cleanly...")
