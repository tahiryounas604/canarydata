"""SQLite registry: recipient <-> canary mapping, seed history.

Standard library only (sqlite3). The registry is the single source of
truth for attribution: a canary marker found in a suspect dataset is
looked up here to name the recipient whose copy it came from.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from canarydata.models import Canary, Recipient


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS canaries (
    canary_id TEXT PRIMARY KEY,
    recipient_id INTEGER NOT NULL REFERENCES recipients(id),
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL UNIQUE,
    record_id TEXT NOT NULL UNIQUE,
    token TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seed_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL REFERENCES recipients(id),
    source_file TEXT NOT NULL,
    output_file TEXT NOT NULL,
    canary_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seed_event_canaries (
    seed_event_id INTEGER NOT NULL REFERENCES seed_events(id),
    canary_id TEXT NOT NULL REFERENCES canaries(canary_id),
    PRIMARY KEY (seed_event_id, canary_id)
);
"""


class Registry:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Registry":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- recipients -----------------------------------------------------
    def add_recipient(self, name: str) -> Recipient:
        name = name.strip()
        if not name:
            raise ValueError("recipient name must not be empty")
        try:
            cur = self._conn.execute(
                "INSERT INTO recipients (name, created_at) VALUES (?, ?)",
                (name, utcnow()),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"recipient already exists: {name}") from exc
        return Recipient(id=cur.lastrowid, name=name, created_at=utcnow())

    def get_recipient(self, name: str) -> Recipient | None:
        row = self._conn.execute(
            "SELECT * FROM recipients WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        return Recipient(id=row["id"], name=row["name"], created_at=row["created_at"])

    def list_recipients(self) -> list[Recipient]:
        rows = self._conn.execute(
            "SELECT * FROM recipients ORDER BY id"
        ).fetchall()
        return [
            Recipient(id=r["id"], name=r["name"], created_at=r["created_at"])
            for r in rows
        ]

    # -- canaries --------------------------------------------------------
    def add_canary(self, canary: Canary) -> Canary:
        self._conn.execute(
            """INSERT INTO canaries
               (canary_id, recipient_id, name, email, phone, record_id,
                token, city, address, company, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                canary.canary_id, canary.recipient_id, canary.name,
                canary.email, canary.phone, canary.record_id, canary.token,
                canary.city, canary.address, canary.company,
                canary.created_at or utcnow(),
            ),
        )
        self._conn.commit()
        return canary

    def _row_to_canary(self, row: sqlite3.Row) -> Canary:
        seeded = self._conn.execute(
            """SELECT se.output_file FROM seed_events se
               JOIN seed_event_canaries sec ON sec.seed_event_id = se.id
               WHERE sec.canary_id = ? ORDER BY se.id""",
            (row["canary_id"],),
        ).fetchall()
        recipient = self._conn.execute(
            "SELECT name FROM recipients WHERE id = ?", (row["recipient_id"],)
        ).fetchone()
        return Canary(
            canary_id=row["canary_id"],
            recipient_id=row["recipient_id"],
            recipient_name=recipient["name"] if recipient else "",
            name=row["name"], email=row["email"], phone=row["phone"],
            record_id=row["record_id"], token=row["token"],
            city=row["city"], address=row["address"], company=row["company"],
            created_at=row["created_at"],
            seeded_into=[r["output_file"] for r in seeded],
        )

    def list_canaries(self, recipient_name: str | None = None) -> list[Canary]:
        if recipient_name is None:
            rows = self._conn.execute(
                "SELECT * FROM canaries ORDER BY created_at, canary_id"
            ).fetchall()
        else:
            recipient = self.get_recipient(recipient_name)
            if recipient is None:
                return []
            rows = self._conn.execute(
                "SELECT * FROM canaries WHERE recipient_id = ? "
                "ORDER BY created_at, canary_id",
                (recipient.id,),
            ).fetchall()
        return [self._row_to_canary(r) for r in rows]

    def existing_values(self) -> dict[str, set[str]]:
        """All marker values already in use (for collision checking)."""
        out: dict[str, set[str]] = {}
        for col in ("email", "phone", "record_id", "token"):
            rows = self._conn.execute(f"SELECT {col} FROM canaries").fetchall()
            out[col] = {r[0] for r in rows}
        return out

    # -- seed history ----------------------------------------------------
    def record_seed_event(
        self, recipient: Recipient, source_file: str, output_file: str,
        canary_ids: list[str],
    ) -> int:
        cur = self._conn.execute(
            """INSERT INTO seed_events
               (recipient_id, source_file, output_file, canary_count, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (recipient.id, source_file, output_file, len(canary_ids), utcnow()),
        )
        event_id = cur.lastrowid
        self._conn.executemany(
            "INSERT OR IGNORE INTO seed_event_canaries (seed_event_id, canary_id) "
            "VALUES (?, ?)",
            [(event_id, cid) for cid in canary_ids],
        )
        self._conn.commit()
        return event_id

    def list_seed_events(self) -> list[dict]:
        rows = self._conn.execute(
            """SELECT se.*, r.name AS recipient_name FROM seed_events se
               JOIN recipients r ON r.id = se.recipient_id ORDER BY se.id"""
        ).fetchall()
        return [dict(r) for r in rows]
