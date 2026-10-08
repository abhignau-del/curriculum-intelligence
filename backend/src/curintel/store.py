"""SQLite storage for the programmes library.

Each programme is kept as one validated JSON record, so `schema.Programme`
stays the single source of truth and the table never holds a record the
analysis cannot read.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .schema import Programme

DEFAULT_DB = Path(__file__).resolve().parents[2] / "curintel.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS programmes (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = str(path)
        with self._db() as db:
            db.executescript(_SCHEMA)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path)
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def list(self) -> list[tuple[str, Programme, str]]:
        """(id, programme, updated_at), sorted by institution."""
        with self._db() as db:
            rows = db.execute("SELECT id, data, updated_at FROM programmes").fetchall()
        items = [(i, Programme.model_validate_json(d), u) for i, d, u in rows]
        return sorted(items, key=lambda t: (t[1].institution.lower(), t[1].name.lower()))

    def get(self, pid: str) -> Programme | None:
        with self._db() as db:
            row = db.execute("SELECT data FROM programmes WHERE id = ?", (pid,)).fetchone()
        return Programme.model_validate_json(row[0]) if row else None

    def add(self, programme: Programme) -> str:
        pid = uuid.uuid4().hex[:12]
        now = _now()
        with self._db() as db:
            db.execute("INSERT INTO programmes VALUES (?, ?, ?, ?)",
                       (pid, programme.model_dump_json(), now, now))
        return pid

    def replace(self, pid: str, programme: Programme) -> bool:
        with self._db() as db:
            cur = db.execute("UPDATE programmes SET data = ?, updated_at = ? WHERE id = ?",
                             (programme.model_dump_json(), _now(), pid))
        return cur.rowcount == 1

    def delete(self, pid: str) -> bool:
        with self._db() as db:
            cur = db.execute("DELETE FROM programmes WHERE id = ?", (pid,))
        return cur.rowcount == 1

    def is_empty(self) -> bool:
        with self._db() as db:
            return db.execute("SELECT COUNT(*) FROM programmes").fetchone()[0] == 0
