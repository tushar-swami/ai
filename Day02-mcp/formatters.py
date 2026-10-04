"""
Terminal Formatters for MCP Tools using Rich.

Formats Kubernetes diagnostic tables, pod descriptions, logs, events,
and system utilities into clean, human-readable terminal UI components.
"""

import json
from pathlib import Path
import re
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def format_get_pods(output: str, namespace_label: str = "default") -> None:
    """Format `kubectl get pods` table into a stylized Rich Table."""
    lines = [l for l in output.splitlines() if l.strip()]

    # Locate the header line
    header_idx = -1
    for i, line in enumerate(lines):
        if "NAME" in line and "READY" in line and "STATUS" in line:
            header_idx = i
            break

    if header_idx == -1:
        # Fallback to panel if not a standard table
        console.print(Panel(output.strip(), title=f"☸ Pods ({namespace_label})", border_style="cyan"))
        return

    header_line = lines[header_idx]
    desired_cols = ["NAMESPACE", "NAME", "READY", "STATUS", "RESTARTS", "AGE", "IP", "NODE"]
    col_spans = []
    for col in desired_cols:
        m = re.search(r"\b" + col + r"\b", header_line)
        if m:
            col_spans.append((col, m.start()))
    col_spans.sort(key=lambda x: x[1])

    table = Table(
        title=f"☸ Kubernetes Pods Inventory ({namespace_label})",
        header_style="bold cyan",
        border_style="blue",
        show_lines=False,
    )

    for col_name, start in col_spans:
        justify = "right" if col_name in ("RESTARTS", "AGE") else "left"
        if col_name == "READY":
            justify = "center"
        table.add_column(col_name, justify=justify)

    # Add rows
    row_count = 0
    for row_line in lines[header_idx + 1:]:
        if not row_line.strip():
            continue

        row_vals = []
        for i, (col_name, start) in enumerate(col_spans):
            end = col_spans[i + 1][1] if i + 1 < len(col_spans) else None
            val = row_line[start:end].strip() if end else row_line[start:].strip()

            # Colorize Status
            if col_name == "STATUS":
                val_lower = val.lower()
                if val_lower == "running":
                    styled_val = f"[bold green]{val}[/bold green]"
                elif any(err in val_lower for err in ("crash", "error", "oom", "backoff", "unknown", "evicted")):
                    styled_val = f"[bold red blink]{val}[/bold red blink]"
                elif any(pend in val_lower for pend in ("pending", "creating", "init")):
                    styled_val = f"[bold yellow]{val}[/bold yellow]"
                else:
                    styled_val = val
            # Highlight Restarts
            elif col_name == "RESTARTS":
                first_token = val.split()[0] if val else "0"
                if first_token.isdigit() and int(first_token) > 0:
                    styled_val = f"[bold yellow]{val}[/bold yellow]"
                else:
                    styled_val = val
            elif col_name == "NAMESPACE":
                styled_val = f"[cyan]{val}[/cyan]"
            elif col_name == "NAME":
                styled_val = f"[bold white]{val}[/bold white]"
            else:
                styled_val = val

            row_vals.append(styled_val)

        table.add_row(*row_vals)
        row_count += 1

    console.print(table)


def format_describe_pod(output: str, pod_name: str, namespace: str) -> None:
    """Format `kubectl describe pod` output, highlighting critical diagnostic fields."""
    lines = output.splitlines()

    # Highlight important diagnostic markers
    highlighted_lines = []
    for line in lines:
        if line.startswith("=== kubectl"):
            continue
        line_lower = line.lower()
        if any(key in line_lower for key in ("state:", "last state:", "reason:", "exit code:", "restarts:")):
            if "running" in line_lower:
                highlighted_lines.append(f"[green]{line}[/green]")
            elif any(err in line_lower for err in ("error", "crash", "oom", "137", "non-zero", "failed")):
                highlighted_lines.append(f"[bold red]{line}[/bold red]")
            else:
                highlighted_lines.append(f"[bold yellow]{line}[/bold yellow]")
        elif "events:" in line_lower:
            highlighted_lines.append(f"\n[bold cyan]── Events ──[/bold cyan]")
        elif "warning" in line_lower:
            highlighted_lines.append(f"[bold red]{line}[/bold red]")
        else:
            highlighted_lines.append(line)

    # Show up to 35 lines to prevent terminal overflow while preserving full diagnosis
    max_preview = 40
    if len(highlighted_lines) > max_preview:
        display_body = "\n".join(highlighted_lines[:max_preview]) + f"\n\n[dim italic]... ({len(highlighted_lines) - max_preview} more lines omitted for display)[/dim italic]"
    else:
        display_body = "\n".join(highlighted_lines)

    console.print(
        Panel(
            display_body,
            title=f"🔍 [bold cyan]Pod Diagnostics: {pod_name}[/bold cyan] ([dim]{namespace}[/dim])",
            border_style="magenta",
            expand=False,
        )
    )


def format_events(output: str, namespace: str) -> None:
    """Format `kubectl get events` table."""
    if "no output" in output.lower() or "no resources found" in output.lower():
        console.print(f"[dim]ℹ No events recorded in namespace '{namespace}'.[/dim]")
        return

    lines = [l for l in output.splitlines() if l.strip() and not l.startswith("===")]
    styled_lines = []
    for line in lines:
        if "warning" in line.lower():
            styled_lines.append(f"[bold red]{line}[/bold red]")
        elif "normal" in line.lower():
            styled_lines.append(f"[green]{line}[/green]")
        else:
            styled_lines.append(line)

    console.print(
        Panel(
            "\n".join(styled_lines[:25]),
            title=f"📋 [bold yellow]Cluster Events ({namespace})[/bold yellow]",
            border_style="yellow",
            expand=False,
        )
    )


def render_mcp_output(func_name: str, func_args: dict | str, output: str) -> None:
    """Dispatcher to render clean, readable terminal UI for any MCP tool output."""
    if isinstance(func_args, str):
        try:
            func_args = json.loads(func_args) if func_args.strip() else {}
        except Exception:
            func_args = {}
    elif func_args is None:
        func_args = {}

    action = func_args.get("action", "")
    ns = func_args.get("namespace", "default")
    pod = func_args.get("pod_name", "")

    # 1. Kubernetes Diagnostics
    if func_name == "kubectl_diagnose":
        if "Command succeeded but returned no output" in output:
            console.print(f"[dim]ℹ No pods found in namespace '{ns}'.[/dim]\n")
            return

        if action == "get_pods":
            format_get_pods(output, namespace_label=ns)
            print()
            return
        elif action == "describe_pod":
            format_describe_pod(output, pod_name=pod, namespace=ns)
            print()
            return
        elif action == "get_events":
            format_events(output, namespace=ns)
            print()
            return
        elif action == "get_logs":
            console.print(
                Panel(
                    output.strip() if len(output) < 1500 else output[:1500] + "\n... [truncated]",
                    title=f"📄 [bold blue]Logs: {pod}[/bold blue] ({ns})",
                    border_style="blue",
                    expand=False,
                )
            )
            print()
            return

    # 2. System Utilities
    if func_name == "get_current_datetime":
        console.print(f"[bold green]🕒 Current Time:[/bold green] [bold white]{output.strip()}[/bold white]\n")
        return
    elif func_name == "roll_dice":
        sides = func_args.get("sides", 6)
        console.print(f"[bold magenta]🎲 Rolled {sides}-sided die:[/bold magenta] [bold yellow]{output.strip()}[/bold yellow]\n")
        return
    elif func_name == "generate_password":
        console.print(f"[bold cyan]🔑 Generated Secure Password:[/bold cyan] [bold green on black] {output.strip()} [/bold green on black]\n")
        return
    elif func_name == "search_knowledge":
        console.print(Panel(output.strip(), title="📚 Knowledge Base Search Results", border_style="cyan"))
        print()
        return

    # Fallback default display
    display_out = output if len(output) < 500 else output[:500] + "\n... [truncated for display]"
    console.print(Panel(display_out, title=f"Tool: {func_name}", border_style="dim"))
    print()
