#!/usr/bin/env python3
"""Spike 4: can Warden create a side room (a probation room) for a candidate?

    python scripts/spike_create_room.py --bridges                 # list bridges only
    python scripts/spike_create_room.py --candidate scout --user <your-discord-username>
    python scripts/spike_create_room.py --candidate scout --internal-only   # fallback

Calls the `create_room` operation (POST /agents/{id}/ops/create_room) and prints
the result. By default it picks the active Discord bridge from `list_bridges`
so the room appears as a new private Discord channel with Warden, the candidate
and you in it.

Server source checked: core/switch_core/bridges/agent/operations/definitions.py
  create_room(name, description, agent_names, user_names=None, channel_type=None,
              bridge_id=None, internal_only=False, instructions=None, ...)
  -> {"id", "name", "matrix_room_id", "caller_is_member", "failed_attachments"}
  list_bridges() -> [{id, type, display_name, status, is_default, can_create_channels}]
Note: `channel_type` is required whenever `bridge_id` is given, and the caller is
only a member if its own name is in `agent_names`.
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

from _common import base_url, load_env, need


def op(http: httpx.Client, agent_id: str, name: str, payload: dict) -> tuple[int, object]:
    r = http.post(f"/agents/{agent_id}/ops/{name}", json=payload)
    if r.status_code != 200:
        return r.status_code, r.text[:500]
    return 200, r.json().get("result")


def main() -> int:
    env = load_env()
    parser = argparse.ArgumentParser(description="Spike: create_room")
    parser.add_argument("--candidate", default="scout")
    parser.add_argument("--name", help="room name (default probation-<candidate>)")
    parser.add_argument("--user", action="append", default=[],
                        help="messaging-app username to add (repeatable); add yourself")
    parser.add_argument("--bridge-id", help="bridge to use (default: the active Discord one)")
    parser.add_argument("--channel-type", default="channel_private",
                        choices=["channel_public", "channel_private"])
    parser.add_argument("--internal-only", action="store_true",
                        help="fallback: no Discord channel, room lives only in Switch")
    parser.add_argument("--bridges", action="store_true", help="only list bridges")
    args = parser.parse_args()

    agent_id, api_key = need(env, "WARDEN_AGENT_ID", "WARDEN_API_KEY")
    warden = (env.get("WARDEN_NAME") or "warden").lstrip("@")
    candidate = args.candidate.lstrip("@")

    with httpx.Client(base_url=base_url(env), timeout=60,
                      headers={"Authorization": f"Bearer {api_key}"}) as http:
        status, bridges = op(http, agent_id, "list_bridges", {})
        if status != 200:
            print(f"list_bridges failed: HTTP {status} {bridges}", file=sys.stderr)
            return 1
        print("bridges:")
        for b in bridges or []:
            print(f"  {b.get('id')}  type={b.get('type')} name={b.get('display_name')!r} "
                  f"status={b.get('status')} default={b.get('is_default')} "
                  f"can_create_channels={b.get('can_create_channels')}")
        if args.bridges:
            return 0

        payload: dict = {
            "name": args.name or f"probation-{candidate}",
            "description": f"Probation room for {candidate}. Warden relays work here.",
            "agent_names": [warden, candidate],
            "instructions": (
                f"This is {candidate}'s probation room. Only Warden assigns work here. "
                "Answer Warden's requests; never share customer personal data."
            ),
        }
        if args.internal_only:
            payload["internal_only"] = True
        else:
            bridge_id = args.bridge_id
            if not bridge_id:
                discord = [b for b in bridges or []
                           if str(b.get("type", "")).lower() == "discord"
                           and b.get("status") == "active"]
                if not discord:
                    print("No active Discord bridge. Connect Discord first, or use "
                          "--internal-only.", file=sys.stderr)
                    return 1
                bridge_id = discord[0]["id"]
            payload["bridge_id"] = bridge_id
            payload["channel_type"] = args.channel_type
            if args.user:
                payload["user_names"] = [u.lstrip("@") for u in args.user]

        print("create_room payload:", json.dumps(payload, indent=2))
        status, result = op(http, agent_id, "create_room", payload)

    if status != 200:
        print(f"create_room failed: HTTP {status} {result}", file=sys.stderr)
        print("Fallback: create the channel yourself in Discord, post in it, "
              f"!invite-agent @{warden} and @{candidate}, then set "
              f"PROBATION_ROOM_{candidate.upper()}=<room id> in .env.", file=sys.stderr)
        return 1
    print("create_room result:", json.dumps(result, indent=2))
    if isinstance(result, dict) and result.get("id"):
        print(f"\nOptional pin in .env:  PROBATION_ROOM_{candidate.upper()}={result['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
