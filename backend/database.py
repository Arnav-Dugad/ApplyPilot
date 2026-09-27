from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
VALID_FACT_STATUS = {"VERIFIED", "UNVERIFIED", "UNKNOWN", "EXPIRED"}


# Columns added after the first release; applied idempotently on startup.
COLUMN_MIGRATIONS = [
    ("jobs", "external_id", "TEXT"),
    ("jobs", "board_questions_json", "TEXT"),
    ("jobs", "ai_summary_json", "TEXT"),
    ("jobs", "employment_type", "TEXT"),
    ("eligibility_results", "score_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("applications", "prep_source", "TEXT"),
    ("applications", "browser_run_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("jobs", "fingerprint", "TEXT"),
    ("jobs", "duplicate_of", "TEXT"),
    ("applications", "previous_status", "TEXT"),
    ("applications", "status_note", "TEXT"),
    ("applications", "followed_up_at", "TEXT"),
    ("drafts", "application_id", "TEXT"),
]

AUTOPILOT_DEFAULTS = {
    "enabled": False,
    "interval_hours": 6,
    "min_score": 60,
    "auto_queue": True,
    "auto_prepare": True,
    "location_filter": True,
    "internships_only": True,
    "ai_summaries": True,
    "ai_cover_letters": False,
}


SETTING_DEFAULTS: dict[str, Any] = {
    "strict_accuracy_mode": True,
    "dry_run": True,
    "actual_submission_enabled": False,
    "automation_mode": "REVIEW_BEFORE_SUBMIT",
    "ollama": {"provider": "OFF", "endpoint": "http://localhost:11434", "model": None},
    "first_run_complete": False,
    "autopilot": AUTOPILOT_DEFAULTS,
    "updates": {"auto_install": True},
    "desktop": {"close_to_tray": True, "start_with_windows": False},
    "email_sync": {"enabled": False, "provider": "GMAIL", "host": "imap.gmail.com", "port": 993, "address": "", "secret": None, "last_sync": None, "last_error": None},
    "base_currency": "USD",
    "last_version": None,
    "whats_new_pending": None,
}


def _rebuild(conn: sqlite3.Connection, table: str, marker: str, create_sql: str, columns: str, indexes: tuple[str, ...] = ()) -> None:
    """Recreates a 0.3 table whose CHECK constraint is too narrow for 0.4, copying every row."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not row or marker not in row[0]:
        return
    conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
    conn.execute(create_sql)
    conn.execute(f"INSERT INTO {table}({columns}) SELECT {columns} FROM {table}_old")
    conn.execute(f"DROP TABLE {table}_old")
    for index in indexes:
        conn.execute(index)


def _rebuild_drafts_without_kind_check(conn: sqlite3.Connection) -> None:
    """0.3 limited draft kinds and job-board platforms with CHECK constraints; 0.4 adds more of both."""
    _rebuild(conn, "drafts", "CHECK(kind IN", """CREATE TABLE drafts (
      id TEXT PRIMARY KEY, kind TEXT NOT NULL, job_id TEXT, application_id TEXT, question TEXT, content TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','APPROVED')), model TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE)""", "id,kind,job_id,question,content,status,model,created_at,updated_at",
             ("CREATE INDEX IF NOT EXISTS idx_drafts_job ON drafts(job_id, kind)",))
    _rebuild(conn, "watchlist", "CHECK(platform IN", """CREATE TABLE watchlist (
      id TEXT PRIMARY KEY, platform TEXT NOT NULL, slug TEXT NOT NULL, company TEXT NOT NULL, created_at TEXT NOT NULL, last_scanned_at TEXT, last_status TEXT,
      jobs_seen INTEGER NOT NULL DEFAULT 0, internships_seen INTEGER NOT NULL DEFAULT 0, UNIQUE(platform, slug))""",
             "id,platform,slug,company,created_at,last_scanned_at,last_status,jobs_seen,internships_seen")


def data_dir() -> Path:
    """Where the database and uploads live. Packaged builds use the per-user app data folder."""
    if os.environ.get("APPLYPILOT_DATA_DIR"):
        return Path(os.environ["APPLYPILOT_DATA_DIR"])
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ApplyPilot"
    return ROOT / "data"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("APPLYPILOT_DB") or data_dir() / "applypilot.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self) -> None:
        schema = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")
        with self._lock, self.connect() as conn:
            conn.executescript(schema)
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(1, ?)", (now(),))
            _rebuild_drafts_without_kind_check(conn)
            for table, column, ddl in COLUMN_MIGRATIONS:
                if column not in {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(fingerprint)")
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(2, ?)", (now(),))
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(3, ?)", (now(),))
            for key, value in SETTING_DEFAULTS.items():
                conn.execute("INSERT OR IGNORE INTO settings(key,value_json,updated_at) VALUES(?,?,?)", (key, json.dumps(value), now()))

    def rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self.rows(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self._lock, self.connect() as conn:
            conn.execute(sql, params)

    def setting(self, key: str) -> Any:
        row = self.one("SELECT value_json FROM settings WHERE key=?", (key,))
        return json.loads(row["value_json"]) if row else None

    def set_setting(self, key: str, value: Any) -> None:
        self.execute(
            "INSERT INTO settings(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
            (key, json.dumps(value), now()),
        )

    def upsert_fact(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status", "UNVERIFIED")
        if status not in VALID_FACT_STATUS:
            raise ValueError("Invalid fact status")
        category, key = payload["category"], payload["fact_key"]
        country = payload.get("country_code") or None
        existing = self.one(
            "SELECT * FROM profile_facts WHERE category=? AND fact_key=? AND country_code IS ?",
            (category, key, country),
        )
        fact_id = existing["id"] if existing else str(uuid.uuid4())
        revision = (existing["revision"] + 1) if existing else 1
        confirmed = now() if status == "VERIFIED" else payload.get("last_confirmed")
        with self._lock, self.connect() as conn:
            conn.execute(
                """INSERT INTO profile_facts(id,category,fact_key,country_code,value_json,status,source,date_added,last_confirmed,expires_at,notes,revision)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET value_json=excluded.value_json,status=excluded.status,source=excluded.source,last_confirmed=excluded.last_confirmed,expires_at=excluded.expires_at,notes=excluded.notes,revision=excluded.revision""",
                (fact_id, category, key, country, json.dumps(payload.get("value")), status, payload.get("source", "USER"), existing["date_added"] if existing else now(), confirmed, payload.get("expires_at"), payload.get("notes", ""), revision),
            )
            if existing and existing["value_json"] != json.dumps(payload.get("value")):
                conn.execute(
                    "UPDATE answer_vault SET status='EXPIRED', updated_at=? WHERE id IN (SELECT dependent_id FROM fact_dependencies WHERE fact_id=? AND dependent_type='ANSWER')",
                    (now(), fact_id),
                )
                conn.execute("UPDATE applications SET status='NEEDS_INFO', updated_at=? WHERE id IN (SELECT dependent_id FROM fact_dependencies WHERE fact_id=? AND dependent_type='APPLICATION')", (now(), fact_id))
        self.log("PROFILE_FACT_SAVED", "profile_fact", fact_id, {"key": key, "status": status, "revision": revision})
        return self.one("SELECT * FROM profile_facts WHERE id=?", (fact_id,)) or {}

    def log(self, action: str, entity_type: str | None = None, entity_id: str | None = None, details: dict[str, Any] | None = None, level: str = "INFO") -> None:
        self.execute("INSERT INTO activity_log(timestamp,level,action,entity_type,entity_id,details_json) VALUES(?,?,?,?,?,?)", (now(), level, action, entity_type, entity_id, json.dumps(details or {})))

