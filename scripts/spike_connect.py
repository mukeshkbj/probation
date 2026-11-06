#!/usr/bin/env python3
"""Spike 1: prove Warden can connect to Switch and speak in the team room.

    python scripts/spike_connect.py            # uses TEAM_ROOM_ID from .env
    python scripts/spike_connect.py --rooms    # just list the rooms Warden is in

What it does, mirroring the Switch load-test client (loadtest/agents.py):
  1. opens the agent WebSocket  /agents/{id}/connection/ws  (protocol 9),
     declaring TEAM_ROOM_ID on the URL;
  2. prints the first `connection_state` frame;
  3. posts "Warden online" with  POST /agents/{id}/message {room_id, content};
  4. prints the first 5 events from the room (your own post usually echoes back
     as one of them), answering every server `ping` with a `pong`;
  5. exits.

If TEAM_ROOM_ID is empty it calls the `list_rooms` operation instead and prints
the rooms Warden has been invited to, so you can copy the id.

Server source checked: WS route core/switch_core/bridges/agent/api/handlers.py:1218
(frames are JSON {"event","data","id"}; server pings, client answers
{"type":"pong","cursor":n}); message route handlers.py:487; ops route
api/operations.py:296 (reply {"result": ...}).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from urllib.parse import urlencode

import httpx
import websockets

from _common import base_url, load_env, need

PROTOCOL = 9
CONTROL = {"connection_state", "gap", "evicted", "subscription_changed", "room_released"}


async def list_rooms(url: str, agent_id: str, auth: dict) -> int:
    async with httpx.AsyncClient(base_url=url, timeout=30) as http:
        r = await http.post(f"/agents/{agent_id}/ops/list_rooms", headers=auth, json={})
    if r.status_code != 200:
        print(f"list_rooms failed: HTTP {r.status_code} {r.text[:300]}", file=sys.stderr)
        return 1
    rooms = r.json().get("result") or []
    if not rooms:
        print("Warden is in no rooms yet. In Discord, post in the team channel, then type:"
              "\n  !invite-agent @warden")
        return 1
    print("Rooms Warden is in (copy the team room's id into TEAM_ROOM_ID):")
    for room in rooms:
        print(f"  {room.get('room_id')}  {room.get('name')!r}")
    return 0


async def spike(url: str, agent_id: str, api_key: str, room_id: str,
                want: int, timeout: float, post: bool) -> int:
    auth = {"Authorization": f"Bearer {api_key}"}
    ws_base = url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    params = {
        "connection_id": str(uuid.uuid4()),
        "scope": "all",
        "filter": "all",
        "start_from": "head",
        "protocol": str(PROTOCOL),
        "protocol_accepts": "1",
        "client": "probation-spike",
        "client_version": "0.1.0",
        "rooms": room_id,
    }
    ws_url = f"{ws_base}/agents/{agent_id}/connection/ws?{urlencode(params)}"
    cursor = 0
    position: dict = {}
    seen = 0

    async with websockets.connect(ws_url, additional_headers=auth, open_timeout=30,
                                  max_size=None, ping_interval=None) as ws:
        async def read_loop() -> int:
            nonlocal cursor, position, seen
            async for raw in ws:
                msg = json.loads(raw)
                ev = msg.get("event")
                data = msg.get("data") or {}
                if ev == "ping":
                    await ws.send(json.dumps({"type": "pong", "cursor": cursor,
                                              "position": position}))
                    continue
                if ev == "refused":
                    print(f"REFUSED: {json.dumps(data)[:400]}")
                    return 1
                if ev == "connection_state":
                    print("connection_state:")
                    for k in ("connection_id", "scope", "filter", "rooms", "cursor",
                              "protocol", "heartbeat_interval_seconds", "server"):
                        if k in data:
                            print(f"  {k}: {json.dumps(data[k])}")
                    if isinstance(data.get("position"), dict):
                        position = data["position"]
                    if post:
                        await post_online(url, agent_id, auth, room_id)
                    continue
                if ev in CONTROL:
                    print(f"[{ev}] {json.dumps(data)[:200]}")
                    if ev == "evicted":
                        return 1
                    continue
                if msg.get("id") is not None:
                    try:
                        cursor = max(cursor, int(msg["id"]))
                    except (TypeError, ValueError):
                        pass
                if isinstance(data.get("position"), dict):
                    position = data["position"]
                seen += 1
                p = data.get("payload") or {}
                who = p.get("sender_name") or p.get("user_name") or p.get("sender") or "?"
                text = p.get("body") or p.get("command") or ""
                print(f"event {seen}: type={data.get('type') or ev} room={data.get('room_id')} "
                      f"from={who} addressed={p.get('addressed')} text={str(text)[:120]!r}")
                if seen >= want:
                    return 0
            return 0

        try:
            rc = await asyncio.wait_for(read_loop(), timeout)
        except TimeoutError:
            print(f"(stopped after {timeout:.0f}s with {seen} event(s); "
                  "post something in the Discord channel to see more)")
            rc = 0
    return rc


async def post_online(url: str, agent_id: str, auth: dict, room_id: str) -> None:
    async with httpx.AsyncClient(base_url=url, timeout=30) as http:
        r = await http.post(f"/agents/{agent_id}/message", headers=auth,
                            json={"room_id": room_id, "content": "Warden online"})
    if r.status_code == 200:
        print("posted: 'Warden online'")
    else:
        print(f"post failed: HTTP {r.status_code} {r.text[:300]}")


def main() -> int:
    env = load_env()
    parser = argparse.ArgumentParser(description="Spike: WebSocket connect + post")
    parser.add_argument("--rooms", action="store_true", help="only list Warden's rooms")
    parser.add_argument("--events", type=int, default=5, help="events to print (default 5)")
    parser.add_argument("--timeout", type=float, default=90.0, help="seconds to wait")
    parser.add_argument("--no-post", action="store_true", help="do not post 'Warden online'")
    args = parser.parse_args()

    url = base_url(env)
    agent_id, api_key = need(env, "WARDEN_AGENT_ID", "WARDEN_API_KEY")
    auth = {"Authorization": f"Bearer {api_key}"}
    room_id = env.get("TEAM_ROOM_ID", "")
    if args.rooms or not room_id:
        if not room_id:
            print("TEAM_ROOM_ID is empty; listing rooms instead.")
        return asyncio.run(list_rooms(url, agent_id, auth))
    return asyncio.run(spike(url, agent_id, api_key, room_id, args.events,
                             args.timeout, not args.no_post))


if __name__ == "__main__":
    sys.exit(main())
