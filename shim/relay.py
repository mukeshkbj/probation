"""Standalone Switch relay for the shim (`python -m shim --switch`).

Sends each prompt to the candidate with `send_targeted` in its probation room and waits for the
candidate's next message in that room. Warden normally runs the shim in-process with its own relay
(warden.redteam starts it), so this mode is for running the shim on its own / debugging.

NOTE: this opens a second WebSocket as the Warden agent. If Warden itself is running, prefer the
in-process path (REDTEAM_MODE=flintai inside Warden) so two connections don't compete for frames.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from typing import Any

from .server import AskFn

log = logging.getLogger("shim.relay")


def _handle(value: str | None) -> str:
    v = (value or "").strip().lstrip("@").lower()
    return v.split(":", 1)[0] if ":" in v else v


class SwitchRelay:
    def __init__(self, client: Any, rooms: dict[str, str], timeout: float = 120.0):
        """`client`: a warden.switch_client.SwitchClient (or compatible fake).
        `rooms`: candidate handle -> probation room id."""
        self.client = client
        self.rooms = {_handle(k): v for k, v in rooms.items()}
        self.default_room = rooms.get("*")
        self.timeout = timeout
        self._queues: dict[tuple[str, str], asyncio.Queue[str]] = {}
        self._pump_task: asyncio.Task | None = None

    def room_for(self, agent: str) -> str:
        room = self.rooms.get(_handle(agent)) or self.default_room
        if not room:
            raise RuntimeError(f"no probation room configured for {agent!r} "
                               f"(set PROBATION_ROOM_{agent.upper()} or PROBATION_ROOM)")
        return room

    def _queue(self, room: str, agent: str) -> asyncio.Queue[str]:
        return self._queues.setdefault((room, _handle(agent)), asyncio.Queue())

    async def start(self) -> None:
        if self._pump_task is None:
            rooms = sorted({r for r in self.rooms.values() if r} | ({self.default_room} if self.default_room else set()))
            self._pump_task = asyncio.create_task(self._pump(rooms))

    async def _pump(self, rooms: list[str]) -> None:
        async for msg in self.client.listen(rooms):
            sender = _handle(getattr(msg, "sender", ""))
            if getattr(msg, "sender_kind", "agent") == "user":
                continue
            self._queue(msg.room_id, sender).put_nowait(msg.text)

    async def stop(self) -> None:
        if self._pump_task:
            self._pump_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._pump_task
            self._pump_task = None

    def ask_for(self, agent: str) -> AskFn:
        async def ask(prompt: str) -> str:
            await self.start()
            room = self.room_for(agent)
            q = self._queue(room, agent)
            while not q.empty():  # drop stale chatter from before this prompt
                q.get_nowait()
            await self.client.send_targeted(room, _handle(agent), prompt)
            return await asyncio.wait_for(q.get(), self.timeout)

        return ask


def relay_from_env() -> SwitchRelay:
    """Build a SwitchRelay from Warden's settings (lazy import of warden.*)."""
    from warden.config import load_settings  # noqa: PLC0415 - lazy: shim works without warden
    from warden.switch_client import SwitchClient  # noqa: PLC0415

    s = load_settings()
    if not (s.agent_id and s.api_key):
        raise RuntimeError("WARDEN_AGENT_ID / WARDEN_API_KEY are not set")
    rooms = dict(getattr(s, "probation_rooms", {}) or {})
    if os.environ.get("PROBATION_ROOM"):
        rooms["*"] = os.environ["PROBATION_ROOM"]
    client = SwitchClient(s.base_url, s.agent_id, s.api_key)
    timeout = float(os.environ.get("SHIM_REPLY_TIMEOUT", getattr(s, "reply_timeout", 120.0)))
    return SwitchRelay(client, rooms, timeout=timeout)
