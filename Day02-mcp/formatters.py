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


def format_get_nodes(output: str) -> None:
    """Format `kubectl get nodes` table into a stylized Rich Table."""
    lines = [l for l in output.splitlines() if l.strip()]
    header_idx = -1
    for i, line in enumerate(lines):
        if "NAME" in line and "STATUS" in line and "ROLES" in line:
            header_idx = i
            break

    if header_idx == -1:
        console.print(Panel(output.strip(), title="☸ Cluster Nodes", border_style="cyan"))
        return

    header_line = lines[header_idx]
    desired_cols = ["NAME", "STATUS", "ROLES", "AGE", "VERSION", "INTERNAL-IP"]
    col_spans = []
    for col in desired_cols:
        m = re.search(r"\b" + col + r"\b", header_line)
        if m:
            col_spans.append((col, m.start()))
    col_spans.sort(key=lambda x: x[1])

    table = Table(
        title="☸ Kubernetes Cluster Nodes",
        header_style="bold cyan",
        border_style="green",
        show_lines=False,
    )
    for col_name, _ in col_spans:
        table.add_column(col_name)

    for row_line in lines[header_idx + 1:]:
        if not row_line.strip():
            continue
        row_vals = []
        for i, (col_name, start) in enumerate(col_spans):
            end = col_spans[i + 1][1] if i + 1 < len(col_spans) else None
            val = row_line[start:end].strip() if end else row_line[start:].strip()
            if col_name == "STATUS":
                styled_val = f"[bold green]{val}[/bold green]" if "ready" in val.lower() and "not" not in val.lower() else f"[bold red]{val}[/bold red]"
            elif col_name == "NAME":
                styled_val = f"[bold white]{val}[/bold white]"
            else:
                styled_val = val
            row_vals.append(styled_val)
        table.add_row(*row_vals)

    console.print(table)


def format_describe_node(output: str, node_name: str) -> None:
    """Format `kubectl describe node` highlighting Conditions and Allocatable resources."""
    lines = output.splitlines()
    highlighted = []
    in_conditions = False

    for line in lines:
        if line.startswith("=== kubectl"):
            continue
        if line.startswith("Conditions:"):
            in_conditions = True
            highlighted.append("\n[bold cyan]── Node Conditions ──[/bold cyan]")
            continue
        elif in_conditions and (line.startswith("Addresses:") or line.startswith("Capacity:")):
            in_conditions = False

        if in_conditions:
            if "MemoryPressure" in line or "DiskPressure" in line or "PIDPressure" in line:
                if "False" in line:
                    highlighted.append(f"[green]{line}[/green]")
                else:
                    highlighted.append(f"[bold red]{line}[/bold red]")
            elif "Ready" in line:
                if "True" in line:
                    highlighted.append(f"[bold green]{line}[/bold green]")
                else:
                    highlighted.append(f"[bold red]{line}[/bold red]")
            else:
                highlighted.append(line)
        elif any(k in line.lower() for k in ("cpu:", "memory:", "ephemeral-storage:", "taints:", "unschedulable:")):
            highlighted.append(f"[yellow]{line}[/yellow]")
        elif len(highlighted) < 30:
            highlighted.append(line)

    console.print(
        Panel(
            "\n".join(highlighted[:35]),
            title=f"🖥 [bold cyan]Node Diagnostics: {node_name}[/bold cyan]",
            border_style="cyan",
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


def format_pr_list(output: str, repo: str) -> None:
    """Format GitHub PR list into a Rich Table."""
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    table = Table(
        title=f"🐙 GitHub Pull Requests ({repo})",
        header_style="bold magenta",
        border_style="magenta",
    )
    table.add_column("PR #", style="bold cyan", justify="right")
    table.add_column("Title", style="bold white")
    table.add_column("State", justify="center")
    table.add_column("Author", style="yellow")
    table.add_column("Branch", style="dim white")
    table.add_column("CI Status", justify="center")

    curr_pr = {}
    for line in lines:
        if line.startswith("• PR #"):
            if curr_pr.get("number"):
                state_badge = "[green]OPEN[/green]" if curr_pr.get("state", "").upper() == "OPEN" else "[purple]CLOSED[/purple]"
                ci = curr_pr.get("ci", "N/A").upper()
                ci_badge = "[bold red on black] FAILED [/bold red on black]" if "FAIL" in ci else (
                    "[bold green on black] PASSED [/bold green on black]" if "PASS" in ci else (
                        "[purple on black] MERGED [/purple on black]" if "MERGE" in ci else ci
                    )
                )
                table.add_row(curr_pr["number"], curr_pr.get("title", ""), state_badge, curr_pr.get("author", "N/A"), curr_pr.get("branch", "N/A"), ci_badge)
            m = re.match(r"• PR #(\d+):\s*(.*)", line)
            if m:
                curr_pr = {"number": f"#{m.group(1)}", "title": m.group(2)}
            else:
                curr_pr = {"number": "N/A", "title": line}
        elif line.startswith("State:"):
            curr_pr["state"] = line.split(":", 1)[1].strip()
        elif line.startswith("Author:"):
            curr_pr["author"] = line.split(":", 1)[1].strip()
        elif line.startswith("Branch:"):
            curr_pr["branch"] = line.split(":", 1)[1].strip()
        elif line.startswith("CI:"):
            curr_pr["ci"] = line.split(":", 1)[1].strip()

    if curr_pr.get("number"):
        state_badge = "[green]OPEN[/green]" if curr_pr.get("state", "").upper() == "OPEN" else "[purple]CLOSED[/purple]"
        ci = curr_pr.get("ci", "N/A").upper()
        ci_badge = "[bold red on black] FAILED [/bold red on black]" if "FAIL" in ci else (
            "[bold green on black] PASSED [/bold green on black]" if "PASS" in ci else (
                "[purple on black] MERGED [/purple on black]" if "MERGE" in ci else ci
            )
        )
        table.add_row(curr_pr["number"], curr_pr.get("title", ""), state_badge, curr_pr.get("author", "N/A"), curr_pr.get("branch", "N/A"), ci_badge)

    console.print(table)


def format_pr_failed_checks(output: str, pr_number: int | str) -> None:
    """Format failed GitHub check runs into a Rich Table."""
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    if "all" in output.lower() and "passed" in output.lower():
        console.print(Panel(f"✅ {output.strip()}", title=f"🐙 GitHub PR #{pr_number} Checks", border_style="green"))
        return

    table = Table(
        title=f"🐙 GitHub PR #{pr_number} — Failed Checks & CI Tasks",
        header_style="bold red",
        border_style="red",
    )
    table.add_column("Job Name", style="bold white")
    table.add_column("Job ID", style="cyan")
    table.add_column("Conclusion", justify="center")

    curr_job = {}
    for line in lines:
        if line.startswith("• Job Name:"):
            if curr_job.get("name"):
                table.add_row(curr_job["name"], curr_job.get("id", "N/A"), "[bold red on black] FAILED [/bold red on black]")
            curr_job = {"name": line.split(":", 1)[1].strip()}
        elif line.startswith("Job ID:"):
            curr_job["id"] = line.split(":", 1)[1].strip()
        elif line.startswith("Conclusion:"):
            curr_job["conclusion"] = line.split(":", 1)[1].strip()

    if curr_job.get("name"):
        table.add_row(curr_job["name"], curr_job.get("id", "N/A"), "[bold red on black] FAILED [/bold red on black]")

    console.print(table)


def format_job_logs(output: str, job_id: int | str) -> None:
    """Format scrubbed CI failure logs with syntax highlighting for stack traces."""
    lines = output.splitlines()
    styled_lines = []
    for line in lines:
        line_lower = line.lower()
        if any(err in line_lower for err in ("fail", "error", "assertionerror", "traceback")):
            styled_lines.append(f"[bold red]{line}[/bold red]")
        elif line.startswith("=== Extracted"):
            styled_lines.append(f"[bold yellow]{line}[/bold yellow]")
        elif ">" in line and ("assert" in line or "def test" in line):
            styled_lines.append(f"[bold cyan]{line}[/bold cyan]")
        else:
            styled_lines.append(f"[dim white]{line}[/dim white]")

    console.print(
        Panel(
            "\n".join(styled_lines),
            title=f"📋 [bold red]Scrubbed CI Failure Log: Job #{job_id}[/bold red]",
            border_style="red",
            expand=False,
        )
    )


def format_pr_diff(output: str, pr_number: int | str) -> None:
    """Format unified PR diff with colored additions and deletions."""
    lines = output.splitlines()
    styled_lines = []
    for line in lines:
        if line.startswith("+++") or line.startswith("---"):
            styled_lines.append(f"[bold white]{line}[/bold white]")
        elif line.startswith("@@"):
            styled_lines.append(f"[cyan]{line}[/cyan]")
        elif line.startswith("+"):
            styled_lines.append(f"[bold green]{line}[/bold green]")
        elif line.startswith("-"):
            styled_lines.append(f"[bold red]{line}[/bold red]")
        elif line.startswith("diff --git"):
            styled_lines.append(f"[bold yellow]\n{line}[/bold yellow]")
        else:
            styled_lines.append(f"[dim]{line}[/dim]")

    console.print(
        Panel(
            "\n".join(styled_lines[:50]),
            title=f"🔀 [bold green]PR #{pr_number} Unified Code Diff[/bold green]",
            border_style="green",
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
    node = func_args.get("node_name", "") or pod

    # 1. Kubernetes Diagnostics
    if func_name == "kubectl_diagnose":
        if "Command succeeded but returned no output" in output:
            console.print(f"[dim]ℹ No resources found for '{action}' in namespace '{ns}'.[/dim]\n")
            return

        if action == "get_pods":
            format_get_pods(output, namespace_label=ns)
            print()
            return
        elif action == "describe_pod":
            format_describe_pod(output, pod_name=pod, namespace=ns)
            print()
            return
        elif action == "get_nodes":
            format_get_nodes(output)
            print()
            return
        elif action == "describe_node":
            format_describe_node(output, node_name=node)
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

    # 3. GitHub Diagnostics
    if func_name == "list_prs":
        repo = func_args.get("repo") or "tushar-swami/ai"
        format_pr_list(output, repo=repo)
        print()
        return
    elif func_name == "get_pr_failed_checks":
        pr = func_args.get("pr_number", "N/A")
        format_pr_failed_checks(output, pr_number=pr)
        print()
        return
    elif func_name == "get_failed_job_logs":
        job = func_args.get("job_id", "N/A")
        format_job_logs(output, job_id=job)
        print()
        return
    elif func_name == "get_pr_diff":
        pr = func_args.get("pr_number", "N/A")
        format_pr_diff(output, pr_number=pr)
        print()
        return
    elif func_name == "create_remediation_pr":
        console.print(
            Panel(
                output.strip(),
                title="🛡️ [bold green]Remediation Pull Request (Main Branch Protected)[/bold green]",
                border_style="green",
            )
        )
        print()
        return

    # Fallback default display
    display_out = output if len(output) < 500 else output[:500] + "\n... [truncated for display]"
    console.print(Panel(display_out, title=f"Tool: {func_name}", border_style="dim"))
    print()


def print_flight_plan_dashboard(
    plan_name: str,
    milestones: list,
    current_milestone_id: str | None = None,
    overall_status: str = "IN_PROGRESS",
) -> None:
    """Renders a Rich terminal dashboard showing active Flight Plan milestones and progress."""
    table = Table(
        title=f"✈️ SRE Flight Plan Dashboard: [bold cyan]{plan_name}[/bold cyan] ({overall_status})",
        header_style="bold magenta",
        border_style="cyan",
        show_lines=True,
    )
    table.add_column("Milestone", style="bold cyan", width=16)
    table.add_column("Phase & Objective", style="white", min_width=25)
    table.add_column("Status", justify="center", width=16)
    table.add_column("Key Finding / Distilled Artifact", style="dim white", min_width=35)

    status_styles = {
        "COMPLETED": "[bold green]✅ COMPLETED[/bold green]",
        "IN_PROGRESS": "[bold yellow]⚡ ACTIVE[/bold yellow]",
        "PENDING": "[dim white]⏳ PENDING[/dim white]",
        "FAILED": "[bold red]❌ FAILED[/bold red]",
        "SKIPPED": "[dim cyan]⏭️ SKIPPED[/dim cyan]",
    }

    for m in milestones:
        # Handle dict or object attributes safely
        mid = getattr(m, "id", None) if hasattr(m, "id") else (m.get("id", "") if isinstance(m, dict) else "")
        name = getattr(m, "name", None) if hasattr(m, "name") else (m.get("name", "") if isinstance(m, dict) else "")
        desc = getattr(m, "description", None) if hasattr(m, "description") else (m.get("description", "") if isinstance(m, dict) else "")
        status = getattr(m, "status", None) if hasattr(m, "status") else (m.get("status", "PENDING") if isinstance(m, dict) else "PENDING")
        if hasattr(status, "value"):
            status_str = status.value
        else:
            status_str = str(status)
        raw_summary = getattr(m, "summary", None) if hasattr(m, "summary") else (m.get("summary", "") if isinstance(m, dict) else "")
        summary = raw_summary or "—"

        status_display = status_styles.get(status_str, status_str)
        phase_text = f"[bold]{name}[/bold]\n[dim]{desc}[/dim]"
        table.add_row(mid, phase_text, status_display, summary)

    console.print()
    console.print(table)
    console.print()

