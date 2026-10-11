"""
Operational Task & Conversation History Memory Engine.

Provides persistent, structured storage of past tasks, diagnostic investigations,
and remediations using SQLite with FTS5 (Full-Text Search) and local Ollama
vector embeddings (nomic-embed-text) for hybrid lexical-semantic retrieval.

Zero external pip dependencies: uses Python standard library (sqlite3, urllib, struct, math, json).
Zero credential storage: records only workloads, root causes, actions, and PR links.
"""

from datetime import datetime
import json
import logging
import math
from pathlib import Path
import sqlite3
import struct
import urllib.error
import urllib.request

logger = logging.getLogger("task_journal")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "tasks_journal.db"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text:latest"
EMBED_DIM = 768


def get_embedding(text: str, timeout: float = 2.5) -> list[float] | None:
    """
    Fetch dense vector embedding from local Ollama instance (nomic-embed-text).
    Fails gracefully to None if Ollama is unreachable or model is not loaded.
    """
    if not text or not text.strip():
        return None
    try:
        clean_text = text.strip()[:1500]
        payload = json.dumps({"model": EMBED_MODEL, "prompt": clean_text}).encode("utf-8")
        req = urllib.request.Request(
            OLLAMA_EMBED_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            vec = data.get("embedding")
            if isinstance(vec, list) and len(vec) == EMBED_DIM:
                return vec
    except Exception as e:
        logger.debug(f"Ollama embedding fetch skipped ({e}); falling back to FTS5 lexical search.")
    return None


def pack_vector(vec: list[float] | None) -> bytes | None:
    """Pack list of float32s into raw binary bytes for SQLite BLOB storage."""
    if not vec or len(vec) != EMBED_DIM:
        return None
    return struct.pack(f"{EMBED_DIM}f", *vec)


def unpack_vector(blob: bytes | None) -> list[float] | None:
    """Unpack raw binary bytes from SQLite BLOB into list of float32s."""
    if not blob or len(blob) != EMBED_DIM * 4:
        return None
    return list(struct.unpack(f"{EMBED_DIM}f", blob))


def cosine_similarity(v1: list[float] | None, v2: list[float] | None) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class TaskJournalDB:
    """
    Persistent SQLite + FTS5 + Vector hybrid memory manager for agent task history.
    """

    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path), timeout=10.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode = WAL;")
        con.execute("PRAGMA synchronous = NORMAL;")
        return con

    def _init_db(self) -> None:
        """Create tables, FTS5 virtual table, and triggers if they do not exist."""
        with self._get_connection() as con:
            # 1. Main Relational Table
            con.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                domain TEXT NOT NULL,
                target_workload TEXT,
                user_query TEXT NOT NULL,
                root_cause TEXT,
                actions_summary TEXT,
                outcome TEXT,
                status TEXT NOT NULL,
                details_json TEXT,
                embedding BLOB
            );
            """)

            # 2. Indexes on frequently queried relational columns
            con.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_tasks_domain ON tasks(domain);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_tasks_target ON tasks(target_workload);")

            # 3. FTS5 Virtual Table for full-text search
            con.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
                task_id UNINDEXED,
                user_query,
                target_workload,
                root_cause,
                actions_summary,
                outcome,
                content='tasks',
                content_rowid='rowid'
            );
            """)

            # 4. Triggers to keep FTS5 synchronized with the tasks table
            con.execute("""
            CREATE TRIGGER IF NOT EXISTS tasks_ai AFTER INSERT ON tasks BEGIN
                INSERT INTO tasks_fts(rowid, task_id, user_query, target_workload, root_cause, actions_summary, outcome)
                VALUES (new.rowid, new.task_id, new.user_query, new.target_workload, new.root_cause, new.actions_summary, new.outcome);
            END;
            """)

            con.execute("""
            CREATE TRIGGER IF NOT EXISTS tasks_ad AFTER DELETE ON tasks BEGIN
                INSERT INTO tasks_fts(tasks_fts, rowid, task_id, user_query, target_workload, root_cause, actions_summary, outcome)
                VALUES('delete', old.rowid, old.task_id, old.user_query, old.target_workload, old.root_cause, old.actions_summary, old.outcome);
            END;
            """)

            con.execute("""
            CREATE TRIGGER IF NOT EXISTS tasks_au AFTER UPDATE ON tasks BEGIN
                INSERT INTO tasks_fts(tasks_fts, rowid, task_id, user_query, target_workload, root_cause, actions_summary, outcome)
                VALUES('delete', old.rowid, old.task_id, old.user_query, old.target_workload, old.root_cause, old.actions_summary, old.outcome);
                INSERT INTO tasks_fts(rowid, task_id, user_query, target_workload, root_cause, actions_summary, outcome)
                VALUES (new.rowid, new.task_id, new.user_query, new.target_workload, new.root_cause, new.actions_summary, new.outcome);
            END;
            """)

    def record_task(
        self,
        domain: str,
        user_query: str,
        target_workload: str | None = None,
        root_cause: str | None = None,
        actions_summary: str | None = None,
        outcome: str | None = None,
        status: str = "COMPLETED",
        details: dict | None = None,
        task_id: str | None = None,
    ) -> str:
        """
        Record a task into the journal. Generates vector embedding and indexes text in FTS5.
        Returns the generated or supplied task_id.
        """
        now = datetime.now()
        prefix = "k8s" if "k8s" in domain.lower() or "kube" in domain.lower() else ("gh" if "git" in domain.lower() else "task")
        tid = task_id or f"{prefix}-{now.strftime('%Y%m%d-%H%M%S')}"

        # Combine key descriptive text for embedding
        embed_text = (
            f"Domain: {domain}. Workload: {target_workload or 'N/A'}. "
            f"Query: {user_query}. Root cause: {root_cause or 'N/A'}. "
            f"Action: {actions_summary or 'N/A'}. Outcome: {outcome or 'N/A'}."
        )
        vec = get_embedding(embed_text)
        blob = pack_vector(vec)

        details_str = json.dumps(details or {}, ensure_ascii=False)

        with self._get_connection() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    task_id, created_at, domain, target_workload, user_query,
                    root_cause, actions_summary, outcome, status, details_json, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tid,
                    now.strftime("%Y-%m-%d %H:%M:%S"),
                    domain.strip().lower(),
                    (target_workload or "").strip(),
                    user_query.strip(),
                    (root_cause or "").strip(),
                    (actions_summary or "").strip(),
                    (outcome or "").strip(),
                    status.strip().upper(),
                    details_str,
                    blob,
                ),
            )
        return tid

    def list_recent_tasks(self, limit: int = 5, domain: str | None = None) -> list[dict]:
        """Fetch the most recent tasks ordered by timestamp descending."""
        limit = max(1, min(50, int(limit)))
        query = "SELECT * FROM tasks"
        params: list = []
        if domain:
            query += " WHERE domain = ?"
            params.append(domain.strip().lower())
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as con:
            rows = con.execute(query, params).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def search_tasks(self, query_str: str, limit: int = 5) -> list[dict]:
        """
        Hybrid search combining SQLite FTS5 (BM25) and local Ollama vector cosine similarity
        using Reciprocal Rank Fusion (RRF).
        """
        if not query_str or not query_str.strip():
            return self.list_recent_tasks(limit=limit)

        clean_q = query_str.strip()
        limit = max(1, min(20, int(limit)))

        # 1. Lexical Search via FTS5
        # Clean query for FTS5 syntax
        fts_tokens = [w for w in clean_q.replace('"', "").replace("'", "").split() if len(w) > 1]
        fts_query = " OR ".join(f"{t}*" for t in fts_tokens) if fts_tokens else clean_q

        fts_results: list[dict] = []
        try:
            with self._get_connection() as con:
                sql = """
                SELECT t.*, bm25(tasks_fts) AS bm25_score
                FROM tasks_fts f
                JOIN tasks t ON t.rowid = f.rowid
                WHERE tasks_fts MATCH ?
                ORDER BY bm25_score ASC
                LIMIT 15;
                """
                rows = con.execute(sql, (fts_query,)).fetchall()
                fts_results = [self._row_to_dict(r) for r in rows]
        except Exception as e:
            logger.debug(f"FTS5 match failed ({e}), falling back to LIKE query.")
            with self._get_connection() as con:
                like_sql = """
                SELECT * FROM tasks
                WHERE target_workload LIKE ? OR root_cause LIKE ? OR user_query LIKE ?
                ORDER BY created_at DESC LIMIT 10;
                """
                pattern = f"%{clean_q}%"
                rows = con.execute(like_sql, (pattern, pattern, pattern)).fetchall()
                fts_results = [self._row_to_dict(r) for r in rows]

        # 2. Semantic Vector Search via Ollama nomic-embed-text
        query_vec = get_embedding(clean_q)
        vector_ranked: list[tuple[float, dict]] = []

        if query_vec:
            with self._get_connection() as con:
                rows = con.execute("SELECT * FROM tasks WHERE embedding IS NOT NULL;").fetchall()
                for r in rows:
                    task_dict = self._row_to_dict(r)
                    stored_blob = r["embedding"]
                    stored_vec = unpack_vector(stored_blob)
                    if stored_vec:
                        sim = cosine_similarity(query_vec, stored_vec)
                        vector_ranked.append((sim, task_dict))
            vector_ranked.sort(key=lambda x: x[0], reverse=True)

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF formula: RRF_score = sum(1 / (k + rank))
        k = 60
        rrf_scores: dict[str, float] = {}
        task_map: dict[str, dict] = {}

        for rank, item in enumerate(fts_results, 1):
            tid = item["task_id"]
            task_map[tid] = item
            rrf_scores[tid] = rrf_scores.get(tid, 0.0) + (1.0 / (k + rank))

        for rank, (sim, item) in enumerate(vector_ranked[:15], 1):
            tid = item["task_id"]
            task_map[tid] = item
            rrf_scores[tid] = rrf_scores.get(tid, 0.0) + (1.0 / (k + rank))

        # Sort tasks by RRF score
        sorted_tids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        results = [task_map[tid] for tid in sorted_tids[:limit]]

        # If neither search found anything, fall back to recent tasks
        if not results:
            return self.list_recent_tasks(limit=limit)

        return results

    def get_task_by_id(self, task_id: str) -> dict | None:
        """Fetch full details for a specific task ID."""
        with self._get_connection() as con:
            row = con.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id.strip(),)).fetchone()
            if row:
                return self._row_to_dict(row)
        return None

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        d.pop("embedding", None)  # Do not expose raw vector bytes
        if isinstance(d.get("details_json"), str):
            try:
                d["details"] = json.loads(d["details_json"])
            except Exception:
                d["details"] = {}
        return d

    def format_agent_card(self, task: dict) -> str:
        """
        Format a single task into a high-density, agent-friendly Markdown Card (~40 tokens).
        Completely strips boilerplate JSON syntax.
        """
        tid = task.get("task_id", "N/A")
        ts = task.get("created_at", "")[:16]
        domain = task.get("domain", "system").capitalize()
        workload = task.get("target_workload") or "general"
        status = task.get("status", "COMPLETED")
        root_cause = task.get("root_cause") or "—"
        outcome = task.get("outcome") or "—"
        actions = task.get("actions_summary") or "—"

        lines = [
            f"• **[{tid}]** `{ts}` | **{domain}** | Target: `{workload}` | Status: **{status}**",
            f"  - **Root Cause**: {root_cause}",
            f"  - **Resolution**: {actions}",
            f"  - **Outcome**: {outcome}",
        ]
        return "\n".join(lines)

    def format_prompt_summary(self, limit: int = 3) -> str:
        """
        Generates the compact 3-item recent operational journal card
        for dynamic injection into DEVOPS_SYSTEM_PROMPT (~120 tokens).
        """
        recent = self.list_recent_tasks(limit=limit)
        if not recent:
            return ""

        lines = ["\n### 🧠 Operational Memory & Recent Task Journal:"]
        lines.append("The following tasks were previously diagnosed and resolved in this workspace:")
        for t in recent:
            tid = t.get("task_id", "")
            target = t.get("target_workload", "general")
            cause = t.get("root_cause", "")
            outcome = t.get("outcome", "")
            lines.append(f"- **{target}** (`{tid}`): {cause} ➔ {outcome}")
        lines.append("You may refer to these past fixes when answering queries or checking prior status.\n")
        return "\n".join(lines)


# Singleton instance
task_journal = TaskJournalDB()
