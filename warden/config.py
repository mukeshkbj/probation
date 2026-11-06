"""Settings from the environment (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _split(value: str | None) -> list[str]:
    return [v.strip().lstrip("@").lower() for v in (value or "").split(",") if v.strip()]


def read_dotenv(path: str | os.PathLike[str] = ".env") -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file. Missing file -> {}."""
    p = Path(path)
    if not p.is_file():
        return {}
    out: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        out[key.strip()] = value
    return out


@dataclass
class Settings:
    base_url: str = "http://localhost:8000"
    registration_key: str = ""
    agent_id: str = ""
    api_key: str = ""
    name: str = "warden"
    team_room_id: str = ""
    sponsors: list[str] = field(default_factory=lambda: ["mukesh"])
    candidates: list[str] = field(default_factory=lambda: ["scout", "rookie"])
    db_path: str = "./warden.db"
    personnel_dir: str = "./personnel"
    shim_port: int = 8787
    redteam_mode: str = "fallback"
    judge_model: str = ""
    spotcheck_rate: float = 0.0
    reply_timeout: float = 120.0
    # PROBATION_ROOM_<AGENT> fallbacks, used when create_room is refused.
    probation_rooms: dict[str, str] = field(default_factory=dict)

    def fallback_room(self, agent: str) -> str | None:
        return self.probation_rooms.get(agent.lower())


def load_settings(env: dict[str, str] | None = None, dotenv: str | None = ".env") -> Settings:
    """Build Settings. Real environment variables win over the .env file."""
    merged: dict[str, str] = {}
    if dotenv:
        merged.update(read_dotenv(dotenv))
    merged.update(os.environ if env is None else env)

    def get(key: str, default: str = "") -> str:
        v = merged.get(key)
        return v if v not in (None, "") else default

    rooms = {
        k[len("PROBATION_ROOM_"):].lower(): v
        for k, v in merged.items()
        if k.startswith("PROBATION_ROOM_") and v
    }
    return Settings(
        base_url=get("SWITCH_BASE_URL", "http://localhost:8000").rstrip("/"),
        registration_key=get("SWITCH_REGISTRATION_KEY"),
        agent_id=get("WARDEN_AGENT_ID"),
        api_key=get("WARDEN_API_KEY"),
        name=get("WARDEN_NAME", "warden").lstrip("@"),
        team_room_id=get("TEAM_ROOM_ID"),
        sponsors=_split(get("SPONSOR_HANDLES", "mukesh")),
        candidates=_split(get("CANDIDATES", "scout,rookie")),
        db_path=get("PROBATION_DB", "./warden.db"),
        personnel_dir=get("PERSONNEL_DIR", "./personnel"),
        shim_port=int(get("SHIM_PORT", "8787")),
        redteam_mode=get("REDTEAM_MODE", "fallback"),
        judge_model=get("JUDGE_MODEL"),
        spotcheck_rate=float(get("SPOTCHECK_RATE", "0")),
        reply_timeout=float(get("REPLY_TIMEOUT", "120")),
        probation_rooms=rooms,
    )
