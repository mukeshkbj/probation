"""An in-process fake of Switch for testing Warden end-to-end.

FakeSwitchClient implements the same interface as warden.switch_client.SwitchClient
(SwitchLike). Candidates are scripted: `responders[agent](prompt) -> reply`, and a
reply is delivered back through listen() the way the real stream would deliver it.
"""

from __future__ import annotations

import asyncio
import itertools
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from warden.switch_client import RoomMessage


@dataclass
class Sent:
    room_id: str
    content: str
    target: str | None = None


@dataclass
class FakeSwitchClient:
    team_room_id: str = "room-team"
    responders: dict[str, Callable[[str], str | None]] = field(default_factory=dict)
    statuses: dict[str, str] = field(default_factory=dict)  # per-target send status, default "live"
    fail_create_room: bool = False
    sent: list[Sent] = field(default_factory=list)
    rooms_created: dict[str, str] = field(default_factory=dict)  # name -> id
    subscribed: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.queue: asyncio.Queue[RoomMessage] = asyncio.Queue()
        self._ids = itertools.count(1)

    # --- what the tests drive
    def inject(self, room_id: str, sender: str, text: str, addressed: bool = True) -> None:
        mid = f"m{next(self._ids)}"
        frame = {
            "event": "message",
            "data": {
                "type": "message",
                "room_id": room_id,
                "payload": {"addressed": addressed, "sender": f"@{sender}:switch.test",
                            "sender_name": sender, "message_id": mid, "body": text},
            },
        }
        self.queue.put_nowait(RoomMessage(room_id, sender, "unknown", text, addressed, mid, frame))

    def team_posts(self) -> list[str]:
        return [s.content for s in self.sent if s.room_id == self.team_room_id and s.target is None]

    def last_team_post(self) -> str:
        posts = self.team_posts()
        return posts[-1] if posts else ""

    # --- SwitchLike
    async def post_message(self, room_id: str, content: str) -> dict:
        self.sent.append(Sent(room_id, content))
        return {"ok": True, "event_id": f"e{next(self._ids)}"}

    async def send_targeted(self, room_id: str, target: str, content: str) -> dict:
        self.sent.append(Sent(room_id, content, target))
        status = self.statuses.get(target, "live")
        if status == "not_permitted":
            # What real Switch does: the target posts an instant refusal in the room.
            asyncio.get_running_loop().call_soon(
                self.inject, room_id, target, "@warden You're not permitted to direct messages to me in this room", False
            )
            return {"event_id": f"e{next(self._ids)}", "target_statuses": {target: status}}
        responder = self.responders.get(target)
        if responder is not None:
            reply = responder(content)
            if reply is not None:
                asyncio.get_running_loop().call_soon(
                    self.inject, room_id, target, reply, False
                )
        return {"event_id": f"e{next(self._ids)}", "target_statuses": {target: "live"}}

    async def create_room(self, name: str, purpose: str = "", **kw: Any) -> str:
        if self.fail_create_room:
            raise RuntimeError("create_room refused")
        room_id = f"room-{name}"
        self.rooms_created[name] = room_id
        return room_id

    async def list_rooms(self) -> list[dict]:
        return [{"room_id": rid, "name": n} for n, rid in self.rooms_created.items()]

    async def subscribe(self, room_id: str) -> None:
        self.subscribed.append(room_id)

    async def listen(self, rooms: list[str]) -> AsyncIterator[RoomMessage]:
        while True:
            yield await self.queue.get()

    async def close(self) -> None:
        pass
