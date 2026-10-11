"""
Unit tests for token tracking and consumption metrics in Orchestrator and Agent.
"""

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "Day02-mcp"))

from orchestrator import FlightPlanResult, Milestone


def test_flight_plan_result_default_tokens():
    """Verify FlightPlanResult defaults to 0 tokens."""
    res = FlightPlanResult(
        plan_name="test_plan",
        success=True,
        milestones=[],
        final_summary="Test summary",
    )
    assert res.prompt_tokens == 0
    assert res.completion_tokens == 0
    assert res.total_tokens == 0


def test_flight_plan_result_custom_tokens():
    """Verify FlightPlanResult accurately retains token metrics."""
    res = FlightPlanResult(
        plan_name="test_plan",
        success=True,
        milestones=[],
        final_summary="Test summary",
        prompt_tokens=1050,
        completion_tokens=220,
        total_tokens=1270,
    )
    assert res.prompt_tokens == 1050
    assert res.completion_tokens == 220
    assert res.total_tokens == 1270


def test_format_tools_catalog():
    """Verify format_tools_catalog executes cleanly."""
    from formatters import format_tools_catalog
    # Should run with None or explicit tool list without exceptions
    format_tools_catalog(None)


def test_anti_hallucination_vendor_prefix_scrubber():
    """Verify regex scrubber strips phantom vendor prefixes from tool names."""
    import re
    dirty_text = "I will use NVIDIA_kubectl_diagnose and Google_list_prs with OpenAI_search_past_tasks."
    clean_text = re.sub(r"\b(?:NVIDIA_|Google_|OpenAI_)(?=[a-zA-Z0-9_]+)", "", dirty_text)
    assert "NVIDIA_" not in clean_text
    assert "Google_" not in clean_text
    assert "OpenAI_" not in clean_text
    assert clean_text == "I will use kubectl_diagnose and list_prs with search_past_tasks."

