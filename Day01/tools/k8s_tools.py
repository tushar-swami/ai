"""
Kubernetes Diagnostic Tools — Safe, read-only kubectl inspection for AI agents.

Features:
    - Principle of Least Privilege (PoLP): Only read-only diagnostic operations are permitted.
    - Strictly allowlisted actions: 'get_pods', 'describe_pod', 'get_logs', 'get_events'.
    - Safe subprocess execution (shell=False) with zero risk of command injection.
    - Automatic kubectl binary location and connection error diagnostics.
"""

from pathlib import Path
import shutil
import subprocess
import sys

from tools.registry import tool

# Allowlisted read-only diagnostic commands
ALLOWED_ACTIONS = {"get_pods", "describe_pod", "get_logs", "get_events"}


def find_kubectl() -> str:
    """Find the path to the kubectl binary on the system."""
    for candidate in ("/usr/local/bin/kubectl", "/opt/homebrew/bin/kubectl"):
        if Path(candidate).is_file():
            return candidate
    found = shutil.which("kubectl")
    if found:
        return found
    return "kubectl"


@tool(
    description=(
        "Run safe, read-only kubectl diagnostic commands to inspect pods and troubleshoot Kubernetes issues. "
        "Allowed actions: 'get_pods' (list pods and statuses), 'describe_pod' (events & exit codes), "
        "'get_logs' (container logs, supports previous=True for crashes), 'get_events' (warning events). "
        "Mutations (delete, apply, edit) are strictly prohibited."
    ),
    parameters={
        "action": {
            "type": "string",
            "enum": ["get_pods", "describe_pod", "get_logs", "get_events"],
            "description": "The read-only diagnostic action to perform.",
        },
        "pod_name": {
            "type": "string",
            "description": "Name of the pod (required for 'describe_pod' and 'get_logs').",
        },
        "namespace": {
            "type": "string",
            "description": "Kubernetes namespace to query (defaults to 'default').",
        },
        "previous": {
            "type": "boolean",
            "description": "If true, fetch logs for previous terminated/crashed container instance (useful for CrashLoopBackOff).",
        },
        "tail": {
            "type": "integer",
            "description": "Number of log lines to retrieve (defaults to 100).",
        },
    },
)
def kubectl_diagnose(
    action: str,
    pod_name: str | None = None,
    namespace: str = "default",
    previous: bool = False,
    tail: int = 100,
) -> str:
    """
    Execute a safe read-only kubectl diagnostic command and return the formatted output.
    """
    action_clean = (action or "").strip().lower()

    if action_clean not in ALLOWED_ACTIONS:
        return (
            f"Security Error: Action '{action}' is not permitted. "
            f"Only read-only diagnostic actions are allowed: {', '.join(sorted(ALLOWED_ACTIONS))}."
        )

    kubectl_bin = find_kubectl()
    ns = (namespace or "default").strip()

    # Build explicit argument list (No shell=True for injection prevention)
    cmd: list[str] = [kubectl_bin, "-n", ns]

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
                    "Is your local Kind cluster or Docker daemon running? "
                    f"\nDetails: {err_msg}"
                )
            return f"kubectl error (exit {res.returncode}):\n{err_msg}"

        output = res.stdout.strip()
        if not output:
            return f"Command succeeded but returned no output for action '{action_clean}' in namespace '{ns}'."

        return f"=== kubectl {action_clean} (namespace: {ns}) ===\n\n{output}"

    except subprocess.TimeoutExpired:
        return "Error: kubectl command timed out after 15 seconds. Cluster may be unreachable."
    except Exception as e:
        return f"Error executing kubectl: {e}"


if __name__ == "__main__":
    action_arg = sys.argv[1] if len(sys.argv) > 1 else "get_pods"
    pod_arg = sys.argv[2] if len(sys.argv) > 2 else None
    print(f"Testing kubectl_diagnose(action='{action_arg}', pod_name='{pod_arg}'):\n")
    print(kubectl_diagnose(action=action_arg, pod_name=pod_arg))
