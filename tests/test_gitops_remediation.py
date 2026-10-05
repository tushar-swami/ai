"""
Unit tests for GitOps Kubernetes Manifest Remediation and PR Safety.
"""

from pathlib import Path
import pytest
import sys

# Ensure Day02-mcp is importable
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "Day02-mcp"))

from k8s_server import find_workload_manifest, kubectl_diagnose, kubectl_apply
from github_server import create_remediation_pr
from orchestrator import K8sDiagnosticFlightPlan, MilestoneStatus


def test_find_workload_manifest_found():
    """Verify find_workload_manifest locates broken_pod.yaml for payment-service."""
    res = find_workload_manifest(workload_name="payment-service")
    assert "Workload Manifest Found" in res
    assert "Day02-mcp/data/broken_pod.yaml" in res
    assert "payment-service" in res


def test_find_workload_manifest_parameter_aliases():
    """Verify find_workload_manifest accepts parameter aliases."""
    res_pod = find_workload_manifest(pod_name="payment-service")
    assert "broken_pod.yaml" in res_pod

    res_name = find_workload_manifest(name="payment-service")
    assert "broken_pod.yaml" in res_name


def test_find_workload_manifest_not_found():
    """Verify graceful message when workload manifest is not found."""
    res = find_workload_manifest(workload_name="nonexistent-svc-xyz")
    assert "No YAML manifest found" in res


def test_create_remediation_pr_blocks_main():
    """Verify safety rule 1: attempting to target 'main' is blocked."""
    res = create_remediation_pr(branch_name="main")
    assert "SAFETY VIOLATION BLOCKED" in res


def test_create_remediation_pr_blocks_master():
    """Verify safety rule 1: attempting to target 'master' is blocked."""
    res = create_remediation_pr(branch_name="master")
    assert "SAFETY VIOLATION BLOCKED" in res


def test_k8s_flight_plan_matches_intents():
    """Verify flight plan regex matching for diagnostic and fix queries."""
    assert K8sDiagnosticFlightPlan.match("Why is payment-service crashing?") is True
    assert K8sDiagnosticFlightPlan.match("fix payment-service") is True
    assert K8sDiagnosticFlightPlan.match("troubleshoot payment-service pod") is True
    assert K8sDiagnosticFlightPlan.match("what is the current time?") is False


def test_k8s_flight_plan_milestones_structure():
    """Verify the 4-phase milestone structure including GitOps PR."""
    plan = K8sDiagnosticFlightPlan("fix payment-service pod")
    assert len(plan.milestones) == 4
    milestone_ids = [m.id for m in plan.milestones]
    assert milestone_ids == ["M1_DISCOVER", "M2_DIAGNOSE", "M3_ISOLATE", "M4_REMEDIATE"]
    assert "GitOps" in plan.milestones[3].name or "Remediation" in plan.milestones[3].name
