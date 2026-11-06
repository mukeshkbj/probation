"""SQLite state: agents, an append-only event log, and pending proposals."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from warden.levels import Level

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    name TEXT PRIMARY KEY,
    level INTEGER NOT NULL DEFAULT 0,
    redteam_score REAL,
    good INTEGER NOT NULL DEFAULT 0,
    bad INTEGER NOT NULL DEFAULT 0,
    probation_room_id TEXT,
    status TEXT NOT NULL DEFAULT 'enrolled',
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    agent TEXT NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    agent TEXT NOT NULL,
    task TEXT NOT NULL,
    reply TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
"""


@dataclass
class AgentRecord:
    name: str
    level: Level
    redteam_score: float | None
    good: int
    bad: int
    probation_room_id: str | None
    status: str


@dataclass
class Proposal:
    id: int
    agent: str
    task: str
    reply: str
    status: str


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    # agents
    def get(self, name: str) -> AgentRecord | None:
        row = self.db.execute("SELECT * FROM agents WHERE name = ?", (name.lower(),)).fetchone()
        if row is None:
            return None
        return AgentRecord(
            name=row["name"],
            level=Level(row["level"]),
            redteam_score=row["redteam_score"],
            good=row["good"],
            bad=row["bad"],
            probation_room_id=row["probation_room_id"],
            status=row["status"],
        )

    def all(self) -> list[AgentRecord]:
        names = [r["name"] for r in self.db.execute("SELECT name FROM agents ORDER BY name")]
        return [rec for n in names if (rec := self.get(n)) is not None]

    def upsert(self, name: str, **fields) -> AgentRecord:
        name = name.lower()
        if self.get(name) is None:
            self.db.execute(
                "INSERT INTO agents (name, updated_at) VALUES (?, ?)", (name, time.time())
            )
        if fields:
            if "level" in fields:
                fields["level"] = int(fields["level"])
            cols = ", ".join(f"{k} = ?" for k in fields)
            self.db.execute(
                f"UPDATE agents SET {cols}, updated_at = ? WHERE name = ?",
                (*fields.values(), time.time(), name),
            )
        self.db.commit()
        rec = self.get(name)
        assert rec is not None
        return rec

    def room_owner(self, room_id: str) -> str | None:
        row = self.db.execute(
            "SELECT name FROM agents WHERE probation_room_id = ?", (room_id,)
        ).fetchone()
        return row["name"] if row else None

    # events
    def log(self, agent: str, kind: str, **detail) -> int:
        cur = self.db.execute(
            "INSERT INTO events (ts, agent, kind, detail) VALUES (?, ?, ?, ?)",
            (time.time(), agent.lower(), kind, json.dumps(detail, default=str)),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def events(self, agent: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM events", ()
        if agent:
            q, args = q + " WHERE agent = ?", (agent.lower(),)
        rows = self.db.execute(q + " ORDER BY id", args).fetchall()
        return [
            {"id": r["id"], "ts": r["ts"], "agent": r["agent"], "kind": r["kind"],
             "detail": json.loads(r["detail"])}
            for r in rows
        ]

    # proposals
    def add_proposal(self, agent: str, task: str, reply: str) -> int:
        cur = self.db.execute(
            "INSERT INTO proposals (ts, agent, task, reply) VALUES (?, ?, ?, ?)",
            (time.time(), agent.lower(), task, reply),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def get_proposal(self, pid: int) -> Proposal | None:
        r = self.db.execute("SELECT * FROM proposals WHERE id = ?", (pid,)).fetchone()
        if r is None:
            return None
        return Proposal(r["id"], r["agent"], r["task"], r["reply"], r["status"])

    def set_proposal_status(self, pid: int, status: str) -> None:
        self.db.execute("UPDATE proposals SET status = ? WHERE id = ?", (status, pid))
        self.db.commit()

    def close(self) -> None:
        self.db.close()
