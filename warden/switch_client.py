"""Switch agent-protocol client: HTTP operations + the reconnecting WebSocket.

Protocol facts below were read from the Switch source (sandbox-quantum/switch):

* WebSocket: ``GET /agents/{id}/connection/ws`` with query params
  ``connection_id`` (required, a UUID reused across reconnects), ``scope``
  ("single"|"all"), ``filter`` ("all"|"addressed"), ``start_from``,
  ``start_at`` (JSON position or "head"), ``protocol`` (9), ``protocol_accepts``,
  ``client``, ``client_version``, ``rooms`` (comma list), ``expected_generation``.
  Auth: ``Authorization: Bearer <api key>``.
  (core/switch_core/bridges/agent/api/handlers.py:1218-1236, loadtest/agents.py:149-165)
* Frames are JSON ``{"event", "data", "id"?}`` (protocol/stream.py:94-100).
  ``ping`` -> reply ``{"type": "pong", "cursor": n, "position": {...}}``
  (handlers.py:1322, 1390; loadtest/agents.py:225-235).
  ``connection_state`` (first frame: generation, position, rooms...; stream.py:130-165),
  ``refused`` ({status, detail}; handlers.py:1278-1284), ``evicted`` ({code, reason,
  room_id}), ``gap`` ({resumed_position, reason}).
* A room message frame: ``event == "message"``, ``data`` is AgentEvent.model_dump():
  ``{"type": "message", "room_id", "bridge_id", "channel_type", "payload": {
  "addressed", "sender", "sender_name", "sender_kind", "message_id", "body",
  "timestamp", "thread_id", ...}, "position": {...}}``
  (protocol/types.py:219-246, 281-287; protocol/message_events.py:41-95; stream.py:435-470).
* Posting: ``POST /agents/{id}/message`` ``{"room_id", "content"}`` -> ``{"ok", "event_id"}``
  (handlers.py:487-506).
* Operations: ``POST /agents/{id}/ops/{name}`` with the op's args as JSON body ->
  ``{"result": ...}`` (api/operations.py:296-350). Room-scoped ops
  (send_targeted_message, post_message) resolve the room from the caller binding:
  headers ``X-Switch-Connection-Id`` (+ ``X-Switch-Session-Id`` placed in a room by
  ``connect_to_room``) (operations/context.py:92-153; definitions.py:252-420).
* ``create_room(name, description, agent_names, ...)`` -> ``{"id", "name", ...}``
  (definitions.py:896-1053). ``list_rooms()`` -> ``[{room_id, name, description,
  connected, archived}]`` (definitions.py:219-248).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
import websockets

log = logging.getLogger("warden.switch")

PROTOCOL = 9
OWN_EVENTS = "s"


@dataclass
class RoomMessage:
    room_id: str
    sender: str  # handle/name of sender (user or agent)
    sender_kind: str  # "user" | "agent" | "unknown"
    text: str
    addressed: bool  # payload.addressed
    message_id: str | None
    raw: dict = field(default_factory=dict)


def handle_of(value: str | None) -> str:
    """Normalise a sender id/name to a comparable handle: '@Scout:host' -> 'scout'."""
    v = (value or "").strip().lstrip("@").lower()
    if ":" in v:  # matrix-style "@name:server"
        v = v.split(":", 1)[0]
    return v


def _parse_message(frame: dict) -> RoomMessage | None:
    """Turn one WebSocket frame into a RoomMessage, or None if it is not one.

    Every guess about the wire format lives here.
    """
    if frame.get("event") != "message":
        return None
    data = frame.get("data") or {}
    payload = data.get("payload") or {}
    room_id = data.get("room_id") or ""
    # ASSUMPTION: `data.room_id` is the Switch room id (UUID), the same id that
    # create_room returns as "id" and that TEAM_ROOM_ID holds. types.py says
    # AgentEvent.room_id without saying which id, and connect_to_room docs say
    # "the Switch room id, not the transport room id".
    body = payload.get("body")
    if not isinstance(body, str):
        # ASSUMPTION: older/other frame shapes keep text in body/content
        # (same fallbacks loadtest/agents.py:_text uses).
        body = data.get("body") or data.get("content") or ""
    # ASSUMPTION: `sender_name` is the human-readable handle we compare against
    # SPONSOR_HANDLES and candidate agent names (an agent's sender_name is its
    # registry name; a Discord user's is their display name). `sender` is a
    # transport id, used only as a fallback.
    sender = payload.get("sender_name") or payload.get("sender") or ""
    kind = payload.get("sender_kind")
    # ASSUMPTION: sender_kind is usually None on the wire (only "platform" is set
    # in message_events.py), so "unknown" is the common value.
    sender_kind = kind if kind in ("user", "agent") else "unknown"
    return RoomMessage(
        room_id=room_id,
        sender=sender,
        sender_kind=sender_kind,
        text=body,
        addressed=bool(payload.get("addressed", False)),
        message_id=payload.get("message_id"),
        raw=frame,
    )


def _furthest(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, int) and v > out.get(k, -1):
            out[k] = v
    return out


class SwitchLike(Protocol):
    """What Warden needs from Switch. SwitchClient implements it; tests fake it."""

    async def post_message(self, room_id: str, content: str) -> dict: ...
    async def send_targeted(self, room_id: str, target: str, content: str) -> dict: ...
    async def create_room(self, name: str, purpose: str = "", **kw: Any) -> str: ...
    async def list_rooms(self) -> list[dict]: ...
    async def subscribe(self, room_id: str) -> None: ...
    def listen(self, rooms: list[str]) -> AsyncIterator[RoomMessage]: ...
    async def close(self) -> None: ...


class SwitchError(RuntimeError):
    pass


class SwitchClient:
    def __init__(
        self,
        base_url: str,
        agent_id: str,
        api_key: str,
        *,
        agent_name: str = "warden",
        http: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.auth = {"Authorization": f"Bearer {api_key}"}
        self.http = http or httpx.AsyncClient(base_url=self.base_url, timeout=30)
        self.connection_id = str(uuid.uuid4())
        self.position: dict[str, int] = {}
        self.generation: int | None = None
        self.connected = asyncio.Event()
        self._rooms: list[str] = []
        self._bound_rooms: set[str] = set()  # rooms placed via connect_to_room
        self._queue: asyncio.Queue[RoomMessage] = asyncio.Queue()
        self._reader: asyncio.Task | None = None
        self._closed = False

    # ---------------------------------------------------------------- HTTP

    async def _post(self, path: str, body: dict, headers: dict | None = None) -> dict:
        r = await self.http.post(
            path,
            json=body,
            headers={**self.auth, "X-Request-Id": str(uuid.uuid4()), **(headers or {})},
        )
        if r.status_code >= 400:
            raise SwitchError(f"{path} -> {r.status_code}: {r.text[:300]}")
        try:
            return r.json()
        except ValueError:
            return {}

    async def op(self, name: str, payload: dict, *, room_id: str | None = None) -> dict:
        """POST /agents/{id}/ops/{name}; returns the unwrapped `result`.

        With `room_id`, the call is bound to that room through a per-room
        session on our live connection (connect_to_room first), because a
        connection covering several rooms cannot answer "which room?".
        """
        headers: dict[str, str] = {}
        if room_id is not None:
            headers = self._session_headers(room_id)
            if room_id not in self._bound_rooms:
                await self._post(
                    f"/agents/{self.agent_id}/ops/connect_to_room",
                    {"room_id": room_id, "include_general_instructions": False},
                    headers,
                )
                self._bound_rooms.add(room_id)
        data = await self._post(f"/agents/{self.agent_id}/ops/{name}", payload, headers)
        result = data.get("result", data) if isinstance(data, dict) else data
        return result if isinstance(result, dict) else {"result": result}

    def _session_headers(self, room_id: str) -> dict[str, str]:
        return {
            "X-Switch-Connection-Id": self.connection_id,
            "X-Switch-Session-Id": f"w-{room_id}"[:64],
        }

    async def post_message(self, room_id: str, content: str) -> dict:
        return await self._post(
            f"/agents/{self.agent_id}/message", {"room_id": room_id, "content": content}
        )

    async def send_targeted(self, room_id: str, target: str, content: str) -> dict:
        target = target.lstrip("@")
        try:
            return await self.op(
                "send_targeted_message",
                {"body": content, "target_names": [target]},
                room_id=room_id,
            )
        except (SwitchError, httpx.HTTPError) as exc:
            # A plain message with a leading @name addresses the same way
            # (agent_core.py send_targeted_message comment: "the same thing that
            # happens to an `@name` in a plain message").
            log.warning("send_targeted_message failed (%s); posting @%s instead", exc, target)
            self._bound_rooms.discard(room_id)
            return await self.post_message(room_id, f"@{target} {content}")

    async def create_room(
        self,
        name: str,
        purpose: str = "",
        *,
        agent_names: list[str] | None = None,
        **extra: Any,
    ) -> str:
        names = list(dict.fromkeys([self.agent_name, *(agent_names or [])]))
        body = {"name": name, "description": purpose, "agent_names": names, **extra}
        result = await self.op("create_room", body)
        room_id = result.get("id") or result.get("room_id")
        if not room_id:
            raise SwitchError(f"create_room returned no id: {result}")
        return room_id

    async def list_rooms(self) -> list[dict]:
        data = await self._post(f"/agents/{self.agent_id}/ops/list_rooms", {})
        result = data.get("result", data)
        return result if isinstance(result, list) else []

    async def subscribe(self, room_id: str) -> None:
        """Claim a room on the open connection (best effort; `scope=all`
        already covers rooms no sibling connection has claimed)."""
        if room_id not in self._rooms:
            self._rooms.append(room_id)
        if not self.connected.is_set():
            return
        body: dict[str, Any] = {
            "connection_id": self.connection_id,
            "room_id": room_id,
            "takeover": True,
        }
        if self.generation is not None:
            body["generation"] = self.generation
        try:
            await self._post(f"/agents/{self.agent_id}/connection/subscribe", body)
        except (SwitchError, httpx.HTTPError) as exc:
            log.warning("subscribe %s failed: %s", room_id, exc)

    # ----------------------------------------------------------- WebSocket

    def _ws_url(self) -> str:
        ws_base = self.base_url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
        cursor = self.position.get(OWN_EVENTS, 0)
        params = {
            "connection_id": self.connection_id,
            "scope": "all",
            "filter": "all",
            "start_from": str(cursor) if cursor else "head",
            "start_at": json.dumps(self.position) if self.position else "head",
            "protocol": str(PROTOCOL),
            "protocol_accepts": "1",
            "client": "probation-warden",
            "client_version": "0.1.0",
            "rooms": ",".join(self._rooms),
        }
        if self.generation is not None:
            params["expected_generation"] = str(self.generation)
        return f"{ws_base}/agents/{self.agent_id}/connection/ws?{urlencode(params)}"

    async def listen(self, rooms: list[str]) -> AsyncIterator[RoomMessage]:
        """Yield room messages forever, reconnecting with backoff.

        Frames are read by a background task so pings are answered even while
        the consumer is busy.
        """
        for r in rooms:
            if r and r not in self._rooms:
                self._rooms.append(r)
        if self._reader is None or self._reader.done():
            self._reader = asyncio.create_task(self._run())
        while not self._closed:
            yield await self._queue.get()

    async def _run(self) -> None:
        backoff = 1.0
        while not self._closed:
            opened = time.monotonic()
            outcome = "closed"
            try:
                async with websockets.connect(
                    self._ws_url(),
                    additional_headers=self.auth,
                    open_timeout=30,
                    max_size=None,
                    ping_interval=None,  # the server's ping frames are the heartbeat
                ) as ws:
                    outcome = await self._read(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - every ending is retried
                outcome = type(exc).__name__
                log.warning("websocket error: %r", exc)
            self.connected.clear()
            self._bound_rooms.clear()  # session placements die with the stream
            if outcome == "taken_over" or self._closed:
                log.error("connection ended for good: %s", outcome)
                return
            if time.monotonic() - opened > 30:
                backoff = 1.0
            delay = backoff * (0.5 + random.random())
            log.info("reconnecting in %.1fs (%s)", delay, outcome)
            await asyncio.sleep(delay)
            backoff = min(backoff * 2, 30)

    async def _read(self, ws) -> str:
        async for raw in ws:
            try:
                frame = json.loads(raw)
            except ValueError:
                continue
            ev = frame.get("event")
            data = frame.get("data") or {}
            if ev == "ping":
                await ws.send(
                    json.dumps(
                        {
                            "type": "pong",
                            "cursor": self.position.get(OWN_EVENTS, 0),
                            "position": self.position,
                        }
                    )
                )
                continue
            if ev == "connection_state":
                self.generation = data.get("generation", self.generation)
                if isinstance(data.get("position"), dict):
                    self.position = _furthest(self.position, data["position"])
                self.connected.set()
                log.info("connected: rooms=%s", data.get("rooms"))
                continue
            if ev == "refused":
                detail = data.get("detail")
                code = detail.get("code") if isinstance(detail, dict) else None
                log.error("connection refused: %s", data)
                if data.get("status") == 403 and self._rooms:
                    # A declared room we cannot serve refuses the whole stream;
                    # scope=all still delivers every room we belong to.
                    self._rooms = []
                return code or f"refused {data.get('status')}"
            if ev == "evicted":
                log.warning("evicted: %s", data)
                return str(data.get("code"))
            if ev == "gap":
                log.warning("gap: %s", data.get("reason"))
                if isinstance(data.get("resumed_position"), dict):
                    self.position = data["resumed_position"]
                continue
            if isinstance(data.get("position"), dict):
                self.position = _furthest(self.position, data["position"])
            elif frame.get("id") is not None:
                self.position = _furthest(self.position, {OWN_EVENTS: int(frame["id"])})
            msg = _parse_message(frame)
            if msg is not None:
                await self._queue.put(msg)
        return "closed"

    async def close(self) -> None:
        self._closed = True
        if self._reader is not None:
            self._reader.cancel()
            await asyncio.gather(self._reader, return_exceptions=True)
        await self.http.aclose()
