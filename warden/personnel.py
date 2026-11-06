"""Personnel files: personnel/<agent>.md.

A short header (current level, scores) that is rewritten on each update,
followed by timestamped entries that are only ever appended.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from warden.levels import Level

MARKER = "<!-- entries below are append-only -->"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class Personnel:
    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, agent: str) -> Path:
        return self.dir / f"{agent.lower()}.md"

    def _header(self, agent: str, level: Level, redteam: float | None, good: int, bad: int,
                status: str) -> str:
        score = f"{redteam:.2f}" if redteam is not None else "not yet run"
        return (
            f"# Personnel file: {agent}\n\n"
            f"- Current level: **{Level(level).label}**\n"
            f"- Status: {status}\n"
            f"- Red-team score: {score}\n"
            f"- Ratings at this level: {good} good / {bad} bad\n"
            f"- Updated: {_now()}\n\n"
            f"## Record\n\n{MARKER}\n"
        )

    def _entries(self, agent: str) -> str:
        p = self.path(agent)
        if not p.exists():
            return ""
        text = p.read_text(encoding="utf-8")
        return text.split(MARKER, 1)[1].lstrip("\n") if MARKER in text else ""

    def update_header(self, agent: str, level: Level, redteam: float | None = None,
                      good: int = 0, bad: int = 0, status: str = "active") -> None:
        entries = self._entries(agent)
        self.path(agent).write_text(
            self._header(agent, level, redteam, good, bad, status) + entries, encoding="utf-8"
        )

    def append(self, agent: str, title: str, detail: str = "") -> str:
        p = self.path(agent)
        if not p.exists():
            self.update_header(agent, Level.ENROLLED, status="enrolled")
        line = f"- {_now()} — **{title}**"
        if detail:
            line += f". {detail.strip()}"
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return line

    def entries(self, agent: str) -> list[str]:
        return [ln for ln in self._entries(agent).splitlines() if ln.startswith("- ")]

    def summary(self, agent: str, last: int = 3) -> str:
        items = self.entries(agent)[-last:]
        if not items:
            return f"{agent}: no record yet."
        return f"{agent} personnel file (last {len(items)}):\n" + "\n".join(items)
