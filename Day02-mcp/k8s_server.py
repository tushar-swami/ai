"""
FastMCP Server — Kubernetes Diagnostics.

Provides safe, read-only kubectl diagnostics to AI agents over standard MCP (Model Context Protocol).
Runs as an isolated child process communicating via JSON-RPC 2.0 over standard I/O (stdio).
"""

from pathlib import Path
import shutil
import subprocess
import sys
from fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP(
    "Kubernetes-Diagnostics",
    instructions="Provides safe read-only diagnostics for Kubernetes pods, logs, and events.",
)

# Strictly allowlisted read-only diagnostic operations (Principle of Least Privilege)
ALLOWED_ACTIONS = {"get_pods", "describe_pod", "get_logs", "get_events", "get_nodes", "describe_node"}


def find_kubectl() -> str:
    """Find the path to the kubectl binary on the system."""
    for candidate in ("/usr/local/bin/kubectl", "/opt/homebrew/bin/kubectl"):
        if Path(candidate).is_file():
            return candidate
    found = shutil.which("kubectl")
    if found:
        return found
    return "kubectl"


@mcp.tool(
    name="kubectl_diagnose",
    description=(
        "Run safe, read-only kubectl diagnostic commands to inspect pods and troubleshoot Kubernetes issues. "
        "Allowed actions: 'get_pods' (list pods and statuses), 'describe_pod' (events & exit codes), "
        "'get_logs' (container logs, supports previous=True for crashes), 'get_events' (warning events), "
        "'get_nodes' (list cluster nodes, roles, and status), 'describe_node' (node conditions, CPU/memory pressure). "
        "Pass namespace='all' or '-A' to inspect all namespaces across the entire cluster. "
        "Mutations (delete, apply, edit) are strictly prohibited."
    ),
)
def kubectl_diagnose(
    action: str,
    pod_name: str | None = None,
    node_name: str | None = None,
    namespace: str = "default",
    previous: bool = False,
    tail: int = 100,
) -> str:
    """Execute safe read-only kubectl diagnostics and return formatted output."""
    action_clean = (action or "").strip().lower()

    if action_clean not in ALLOWED_ACTIONS:
        return (
            f"Security Error: Action '{action}' is not permitted. "
            f"Only read-only diagnostic actions are allowed: {', '.join(sorted(ALLOWED_ACTIONS))}."
        )

    kubectl_bin = find_kubectl()
    ns = (namespace or "default").strip()
    is_all_ns = ns.lower() in ("all", "-a", "--all-namespaces", "*")
    target_node = (node_name or pod_name or "").strip()

    # Node operations are cluster-scoped
    if action_clean == "get_nodes":
        cmd = [kubectl_bin, "get", "nodes", "-o", "wide"]
    elif action_clean == "describe_node":
        if not target_node:
            return "Error: 'node_name' or 'pod_name' is required for action 'describe_node'."
        cmd = [kubectl_bin, "describe", "node", target_node]

    # Pod operations can be namespaced
    elif is_all_ns:
        if action_clean in ("describe_pod", "get_logs"):
            return f"Error: Action '{action_clean}' requires a specific namespace (e.g. namespace='kube-system')."
        if action_clean == "get_pods":
            cmd = [kubectl_bin, "get", "pods", "-A", "-o", "wide"]
        elif action_clean == "get_events":
            cmd = [kubectl_bin, "get", "events", "-A", "--sort-by=.metadata.creationTimestamp"]
        else:
            cmd = [kubectl_bin, "get", "pods", "-A", "-o", "wide"]
    else:
        cmd = [kubectl_bin, "-n", ns]
        if action_clean == "get_pods":
            cmd.extend(["get", "pods", "-o", "wide"])
        elif action_clean == "describe_pod":
            if not pod_name or not str(pod_name).strip():
                return "Error: 'pod_name' is required for action 'describe_pod'."
            cmd.extend(["describe", "pod", str(pod_name).strip()])
        elif action_clean == "get_logs":
            if not pod_name or not str(pod_name).strip():
                return "Error: 'pod_name' is required for action 'get_logs'."
            cmd.extend(["logs", str(pod_name).strip(), f"--tail={max(10, min(500, int(tail)))}"])
            if previous:
                cmd.append("--previous")
        elif action_clean == "get_events":
            cmd.extend(["get", "events", "--sort-by=.metadata.creationTimestamp"])

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        if res.returncode != 0:
            err_msg = res.stderr.strip() or res.stdout.strip()
            if "refused" in err_msg.lower() or "connect" in err_msg.lower():
                return (
                    "Kubernetes Error: Unable to connect to the cluster server. "
                    "Is your local Kubernetes cluster or Docker daemon running? "
                    f"\nDetails: {err_msg}"
                )
            return f"kubectl error (exit {res.returncode}):\n{err_msg}"

        output = res.stdout.strip()
        display_ns = "all namespaces" if is_all_ns else ns
        if not output:
            return f"Command succeeded but returned no output for action '{action_clean}' in {display_ns}."

        return f"=== kubectl {action_clean} (namespace: {display_ns}) ===\n\n{output}"

    except subprocess.TimeoutExpired:
        return "Error: kubectl command timed out after 15 seconds. Cluster may be unreachable."
    except Exception as e:
        return f"Error executing kubectl: {e}"


if __name__ == "__main__":
    # When run directly, start the FastMCP stdio server cleanly without banner
    mcp.run(show_banner=False)
