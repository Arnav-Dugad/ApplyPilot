"""Backups, restore, and full reset of the local workspace."""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from .database import Database

BACKUP_NAME = re.compile(r"^applypilot-backup-\d{8}-\d{6}(-[a-z0-9-]+)?\.zip$")
KEEP_BACKUPS = 20


def backups_dir(db: Database) -> Path:
    path = db.path.parent / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def uploads_dir(db: Database) -> Path:
    return db.path.parent / "uploads"


def create_backup(db: Database, label: str = "") -> dict[str, Any]:
    """Consistent snapshot (SQLite online backup API) of the database plus uploaded CVs, zipped."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = f"-{re.sub(r'[^a-z0-9-]+', '-', label.lower()).strip('-')}" if label else ""
    target = backups_dir(db) / f"applypilot-backup-{stamp}{suffix}.zip"
    counter = 1
    while target.exists():
        target = backups_dir(db) / f"applypilot-backup-{stamp}{suffix}-{counter}.zip"
        counter += 1
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "applypilot.db"
        with db._lock:
            source = sqlite3.connect(db.path)
            dest = sqlite3.connect(snapshot)
            try:
                source.backup(dest)
            finally:
                dest.close()
                source.close()
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, "applypilot.db")
            uploads = uploads_dir(db)
            if uploads.is_dir():
                for file in uploads.rglob("*"):
                    if file.is_file():
                        archive.write(file, f"uploads/{file.relative_to(uploads).as_posix()}")
    _prune(db)
    return _describe(target)


def _prune(db: Database) -> None:
    for old in sorted(backups_dir(db).glob("applypilot-backup-*.zip"), reverse=True)[KEEP_BACKUPS:]:
        old.unlink(missing_ok=True)


def _describe(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"name": path.name, "size": stat.st_size, "created_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()}


def list_backups(db: Database) -> list[dict[str, Any]]:
    return [_describe(p) for p in sorted(backups_dir(db).glob("applypilot-backup-*.zip"), reverse=True) if BACKUP_NAME.match(p.name)]


def _wipe_tables(db: Database) -> None:
    with db._lock, db.connect() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'schema_migrations'")]
        for table in tables:
            conn.execute(f"DELETE FROM {table}")
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").fetchone():
            conn.execute("DELETE FROM sqlite_sequence")
    with closing(sqlite3.connect(db.path)) as conn:  # sqlite3's own context manager doesn't close
        conn.execute("VACUUM")


def reset(db: Database, *, backup_first: bool = True, extra_dirs: tuple[Path, ...] = ()) -> dict[str, Any]:
    """Erases every job, fact, answer, CV, and setting, then restores safe defaults. Backups themselves are kept."""
    backup = create_backup(db, "before-reset") if backup_first else None
    _wipe_tables(db)
    shutil.rmtree(uploads_dir(db), ignore_errors=True)
    for folder in extra_dirs:
        shutil.rmtree(folder, ignore_errors=True)
    db.migrate()
    return {"ok": True, "backup": backup}


def restore(db: Database, name: str) -> dict[str, Any]:
    """Replaces the current workspace with a backup, after taking a safety backup of the current state."""
    if not BACKUP_NAME.match(name):
        raise ValueError("Unknown backup")
    path = backups_dir(db) / name
    if not path.is_file():
        raise ValueError("Backup not found")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "applypilot.db" not in names:
            raise ValueError("This backup has no database")
        for member in names:
            parts = Path(member).parts
            if member != "applypilot.db" and (not member.startswith("uploads/") or ".." in parts or Path(member).is_absolute() or ":" in member):
                raise ValueError("Backup contains unexpected files")
        with tempfile.TemporaryDirectory() as tmp:
            archive.extractall(tmp)
            candidate = Path(tmp) / "applypilot.db"
            with closing(sqlite3.connect(candidate)) as check:
                if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Backup database is damaged")
                if not check.execute("SELECT 1 FROM sqlite_master WHERE name='profile_facts'").fetchone():
                    raise ValueError("This isn't an ApplyPilot backup")
            safety = create_backup(db, "before-restore")
            with db._lock:
                source = sqlite3.connect(candidate)
                dest = sqlite3.connect(db.path)
                try:
                    source.backup(dest)
                finally:
                    dest.close()
                    source.close()
            shutil.rmtree(uploads_dir(db), ignore_errors=True)
            restored_uploads = Path(tmp) / "uploads"
            if restored_uploads.is_dir():
                shutil.copytree(restored_uploads, uploads_dir(db))
    db.migrate()
    _repoint_cv_paths(db)
    return {"ok": True, "safety_backup": safety}


def _repoint_cv_paths(db: Database) -> None:
    """Backups may come from another machine or user folder; CV paths are rebuilt from their ids."""
    folder = uploads_dir(db) / "cvs"
    for row in db.rows("SELECT id FROM cvs"):
        db.execute("UPDATE cvs SET path=? WHERE id=?", (str(folder / f"{row['id']}.pdf"), row["id"]))


def open_folder(path: Path) -> None:
    if hasattr(os, "startfile"):
        os.startfile(path)  # type: ignore[attr-defined]
