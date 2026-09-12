"""SQLite storage. Run records are append-only by convention: the runs row is
written once at creation; everything after that is an event or a new row.
Draft state changes live in drafts + draft_events so every human decision is
reconstructable: evidence, prompt/model versions, edits/rejects, cost, outcome."""
import json, os, sqlite3, uuid
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  template TEXT NOT NULL,
  template_version TEXT NOT NULL,
  connector TEXT NOT NULL,
  trigger TEXT NOT NULL,
  status TEXT NOT NULL,              -- queued | running | awaiting_approval | done | failed
  input_title TEXT,
  input_hash TEXT,
  evidence_json TEXT NOT NULL,       -- the raw input, stored once, never mutated
  model TEXT,
  prompt_versions_json TEXT,
  tokens_in INTEGER DEFAULT 0,
  tokens_out INTEGER DEFAULT 0,
  cost_usd REAL DEFAULT 0,
  error TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  at TEXT NOT NULL,
  event TEXT NOT NULL,
  detail_json TEXT
);
CREATE TABLE IF NOT EXISTS ideas (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  timestamp_ref TEXT,
  speaker TEXT,
  idea TEXT NOT NULL,
  why_it_lands TEXT,
  score REAL,
  confidential INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS drafts (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  format TEXT NOT NULL,              -- linkedin_post | x_thread | newsletter_blurb
  title TEXT,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | edited | rejected
  prompt_version TEXT,
  model TEXT,
  fewshot_count INTEGER DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS draft_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id TEXT NOT NULL,
  at TEXT NOT NULL,
  event TEXT NOT NULL,               -- approved | rejected | edited | regenerated
  actor TEXT,
  reason TEXT,
  diff_json TEXT,
  final_body TEXT
);
-- The learning loop: every accepted edit becomes a before/after pair that
-- few-shots the next draft in the same format. This is the table that makes
-- the product taste better the longer you use it.
CREATE TABLE IF NOT EXISTS edit_examples (
  id TEXT PRIMARY KEY,
  draft_id TEXT NOT NULL,
  format TEXT NOT NULL,
  original_body TEXT NOT NULL,
  edited_body TEXT NOT NULL,
  diff TEXT NOT NULL,
  created_at TEXT NOT NULL
);
-- Outcome + removal tracking, present from day one: where each approved draft
-- was posted, what it did, and whether it later disappeared (mod removal is
-- the honest scoreboard).
CREATE TABLE IF NOT EXISTS outcomes (
  id TEXT PRIMARY KEY,
  draft_id TEXT NOT NULL,
  platform TEXT,
  url TEXT,
  posted_at TEXT,
  metrics_json TEXT,
  removed INTEGER DEFAULT 0,
  last_checked_at TEXT,
  created_at TEXT NOT NULL
);
-- Rate/ratio caps accounting. template.yaml budgets are enforced against this.
CREATE TABLE IF NOT EXISTS budget_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template TEXT NOT NULL,
  at TEXT NOT NULL,
  kind TEXT NOT NULL,                -- llm_call | run
  amount_usd REAL DEFAULT 0,
  detail_json TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

class DB:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def q(self, sql: str, args=()):
        return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql: str, args=()):
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def insert(self, table: str, row: dict):
        cols = ",".join(row.keys())
        marks = ",".join("?" for _ in row)
        self.conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(row.values()))
        self.conn.commit()

    def execute(self, sql: str, args=()):
        self.conn.execute(sql, args)
        self.conn.commit()

    def event(self, run_id: str, event: str, detail: dict | None = None):
        self.insert("run_events", {
            "run_id": run_id, "at": _now(), "event": event,
            "detail_json": json.dumps(detail or {}),
        })

    def set_status(self, run_id: str, status: str):
        # Status is a pointer, not history: the run_events stream is the record.
        self.execute("UPDATE runs SET status=? WHERE id=?", (status, run_id))
        self.event(run_id, f"status:{status}")

    def draft_event(self, draft_id: str, event: str, actor="local-user", reason=None,
                    diff=None, final_body=None):
        self.insert("draft_events", {
            "draft_id": draft_id, "at": _now(), "event": event, "actor": actor,
            "reason": reason,
            "diff_json": json.dumps(diff) if diff is not None else None,
            "final_body": final_body,
        })

    def budget_spend_7d(self, template: str) -> float:
        row = self.one(
            "SELECT COALESCE(SUM(amount_usd),0) AS s FROM budget_events "
            "WHERE template=? AND at >= datetime('now','-7 days')", (template,))
        return float(row["s"])

    def runs_today(self, template: str) -> int:
        row = self.one(
            "SELECT COUNT(*) AS c FROM budget_events WHERE template=? AND kind='run' "
            "AND date(at)=date('now')", (template,))
        return int(row["c"])

    def recent_edit_examples(self, fmt: str, limit: int = 5):
        return self.q(
            "SELECT * FROM edit_examples WHERE format=? ORDER BY created_at DESC LIMIT ?",
            (fmt, limit))
