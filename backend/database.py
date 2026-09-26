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
            defaults = {
                "strict_accuracy_mode": True,
                "dry_run": True,
                "actual_submission_enabled": False,
                "automation_mode": "REVIEW_BEFORE_SUBMIT",
                "ollama": {"provider": "OFF", "endpoint": "http://localhost:11434", "model": None},
                "first_run_complete": False,
            }
            for key, value in defaults.items():
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

