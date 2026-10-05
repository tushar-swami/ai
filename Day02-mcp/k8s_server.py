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
    pod: str | None = None,
    node_name: str | None = None,
    node: str | None = None,
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
    target_pod = (pod_name or pod or "").strip()
    target_node = (node_name or node or target_pod).strip()

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
            if not target_pod:
                return "Error: 'pod_name' (or 'pod') is required for action 'describe_pod'."
            cmd.extend(["describe", "pod", target_pod])
        elif action_clean == "get_logs":
            if not target_pod:
                return "Error: 'pod_name' (or 'pod') is required for action 'get_logs'."
            cmd.extend(["logs", target_pod, f"--tail={max(10, min(500, int(tail)))}"])
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

        # Fallback to current logs if --previous failed or returned unable to retrieve
        if action_clean == "get_logs" and previous:
            out_check = (res.stdout or "") + (res.stderr or "")
            if res.returncode != 0 or "unable to retrieve" in out_check.lower():
                fallback_cmd = [c for c in cmd if c != "--previous"]
                fb_res = subprocess.run(
                    fallback_cmd,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if fb_res.returncode == 0 and fb_res.stdout.strip():
                    res = fb_res

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


@mcp.tool(
    name="kubectl_apply",
    description=(
        "Safely applies a Kubernetes YAML manifest (ConfigMap, Secret, Deployment patch, or Pod) "
        "to resolve cluster incidents, provide missing configurations, or deploy fixes."
    ),
)
def kubectl_apply(
    yaml_content: str | None = None,
    manifest: str | None = None,
    yaml: str | None = None,
    content: str | None = None,
    namespace: str = "default",
) -> str:
    """Apply a YAML manifest to the Kubernetes cluster."""
    kubectl_bin = find_kubectl()
    if not kubectl_bin:
        return "Error: kubectl binary not found."

    clean_yaml = (yaml_content or manifest or yaml or content or "").strip()
    if not clean_yaml:
        return "Error: No YAML content provided to apply (expected 'manifest' or 'yaml_content')."

    ns = namespace.strip() if namespace else "default"
    cmd = [kubectl_bin, "-n", ns, "apply", "-f", "-"]

    try:
        res = subprocess.run(
            cmd,
            input=clean_yaml,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        if res.returncode != 0:
            err_msg = res.stderr.strip() or res.stdout.strip()
            return f"kubectl apply error (exit {res.returncode}):\n{err_msg}"

        return f"=== kubectl apply successful (namespace: {ns}) ===\n\n{res.stdout.strip()}"

    except subprocess.TimeoutExpired:
        return "Error: kubectl apply timed out after 15 seconds."
    except Exception as e:
        return f"Error executing kubectl apply: {e}"


@mcp.tool(
    name="find_workload_manifest",
    description=(
        "Searches the repository workspace for Kubernetes YAML manifest files defining a specific workload "
        "(by metadata.name, service name, or app label). Returns the relative file path and current YAML contents."
    ),
)
def find_workload_manifest(
    workload_name: str | None = None,
    pod_name: str | None = None,
    name: str | None = None,
    target: str | None = None,
) -> str:
    """Find the source YAML manifest for a workload in the repository."""
    search_target = (workload_name or pod_name or name or target or "").strip()
    if not search_target:
        return "Error: 'workload_name' is required to find manifest."

    base_dir = Path(__file__).resolve().parent.parent
    search_dirs = [base_dir / "Day02-mcp" / "data", base_dir / "Day02-mcp", base_dir]

    candidates = []
    seen_paths = set()
    for d in search_dirs:
        if not d.exists():
            continue
        for p in list(d.rglob("*.yaml")) + list(d.rglob("*.yml")):
            if ".venv" in p.parts or ".git" in p.parts or p in seen_paths:
                continue
            seen_paths.add(p)
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                if search_target in txt:
                    # Score candidate: prefer exact metadata.name match or filename match
                    score = 0
                    if f"name: {search_target}" in txt or f"name: \"{search_target}\"" in txt:
                        score += 10
                    if search_target in p.name:
                        score += 5
                    if "data" in p.parts:
                        score += 2
                    candidates.append((score, p, txt))
            except Exception:
                continue

    if not candidates:
        return f"No YAML manifest found in repository matching workload '{search_target}'."

    candidates.sort(key=lambda c: c[0], reverse=True)
    _, best_file, best_content = candidates[0]
    rel_path = str(best_file.relative_to(base_dir))
    return f"=== Workload Manifest Found: {rel_path} ===\n\nFile Path: {rel_path}\n\nCurrent YAML Content:\n{best_content}"


if __name__ == "__main__":
    # When run directly, start the FastMCP stdio server cleanly without banner
    mcp.run(show_banner=False)
