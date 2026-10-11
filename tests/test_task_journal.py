"""
Unit tests for Operational Task & Conversation Memory Engine (SQLite + FTS5 + Vector).
"""

from pathlib import Path
import pytest
import sys
import tempfile

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "Day02-mcp"))

from task_journal import TaskJournalDB, cosine_similarity, pack_vector, unpack_vector
from system_server import list_past_tasks, search_past_tasks, get_past_task_details


@pytest.fixture
def temp_journal():
    """Create a temporary TaskJournalDB instance for isolated testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_tasks.db"
        journal = TaskJournalDB(db_path=db_file)
        yield journal


def test_db_initialization(temp_journal):
    """Verify tables and FTS5 virtual table are created."""
    with temp_journal._get_connection() as con:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        assert "tasks" in tables
        assert "tasks_fts" in tables


def test_record_and_retrieve_task(temp_journal):
    """Verify task recording and retrieval by ID."""
    tid = temp_journal.record_task(
        domain="kubernetes",
        user_query="Why is auth-service crashing?",
        target_workload="auth-service",
        root_cause="ExitCode: 137 (OOMKilled - Exceeded 256Mi memory limit)",
        actions_summary="Patched deployment resource limits to 512Mi",
        outcome="Pod stabilized in running state",
        status="COMPLETED",
        details={"replicas": 2},
        task_id="k8s-test-01",
    )
    assert tid == "k8s-test-01"

    task = temp_journal.get_task_by_id(tid)
    assert task is not None
    assert task["target_workload"] == "auth-service"
    assert "OOMKilled" in task["root_cause"]
    assert task["details"]["replicas"] == 2


def test_fts5_lexical_search(temp_journal):
    """Verify FTS5 full-text keyword search accuracy."""
    temp_journal.record_task(
        domain="kubernetes",
        user_query="Fix payment-service CrashLoopBackOff",
        target_workload="payment-service",
        root_cause="Missing configuration file /etc/config/database.json",
        actions_summary="Mounted ConfigMap volume",
        outcome="GitOps PR opened",
        task_id="k8s-payment-01",
    )
    temp_journal.record_task(
        domain="github",
        user_query="Fix PR #42 test failure",
        target_workload="PR #42",
        root_cause="AssertionError in test_pricing.py",
        actions_summary="Updated assertions",
        outcome="PR updated",
        task_id="gh-pr42-01",
    )

    # Search for exact keyword
    results = temp_journal.search_tasks("database.json")
    assert len(results) > 0
    assert results[0]["task_id"] == "k8s-payment-01"

    # Search for PR keyword
    results_gh = temp_journal.search_tasks("test_pricing")
    assert len(results_gh) > 0
    assert results_gh[0]["task_id"] == "gh-pr42-01"


def test_cosine_similarity():
    """Verify mathematical cosine similarity calculations."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    assert abs(cosine_similarity(v1, v2) - 1.0) < 1e-5
    assert abs(cosine_similarity(v1, v3) - 0.0) < 1e-5


def test_pack_unpack_vector():
    """Verify 768-float binary pack and unpack integrity."""
    test_vec = [float(i) * 0.01 for i in range(768)]
    blob = pack_vector(test_vec)
    assert blob is not None
    assert len(blob) == 768 * 4

    unpacked = unpack_vector(blob)
    assert unpacked is not None
    assert len(unpacked) == 768
    assert abs(unpacked[0] - test_vec[0]) < 1e-5


def test_format_agent_card(temp_journal):
    """Verify card formatting generates low-token, clean Markdown without JSON boilerplate."""
    tid = temp_journal.record_task(
        domain="kubernetes",
        user_query="Investigate pod crash",
        target_workload="payment-service",
        root_cause="ExitCode: 1",
        actions_summary="Patched YAML",
        outcome="PR opened",
        task_id="test-card-01",
    )
    task = temp_journal.get_task_by_id(tid)
    card = temp_journal.format_agent_card(task)

    assert "• **[test-card-01]**" in card
    assert "Root Cause" in card
    assert "Resolution" in card
    # Ensure no raw JSON syntax clutter
    assert "{" not in card and "}" not in card


def test_mcp_system_tools_registered():
    """Verify MCP tools for task memory execute cleanly."""
    list_out = list_past_tasks(limit=3)
    assert "Operational Task Journal" in list_out or "No previous tasks" in list_out

    search_out = search_past_tasks(query="payment")
    assert "payment" in search_out.lower() or "no past tasks" in search_out.lower()
