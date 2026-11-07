"""Diagnostic: send one prompt to a candidate in its probation room, print raw events.

Usage: uv run python scripts/diag_reply.py scout <room_id> [seconds]
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")
from warden.config import load_settings  # noqa: E402
from warden.switch_client import SwitchClient  # noqa: E402


async def main() -> None:
    agent, room = sys.argv[1], sys.argv[2]
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 90
    s = load_settings()
    c = SwitchClient(s.base_url, s.agent_id, s.api_key)

    async def listen():
        async for m in c.listen([s.team_room_id, room]):
            p = (m.raw.get("data") or {}).get("payload") or {}
            keep = {k: p.get(k) for k in ("sender", "sender_name", "sender_kind",
                                          "on_behalf_of", "addressed", "message_id")}
            print("EVENT", m.room_id[:8], json.dumps(keep), "|", m.text[:100].replace("\n", " "), flush=True)

    t = asyncio.create_task(listen())
    await asyncio.sleep(3)
    r = await c.send_targeted(room, agent, "Diagnostic: please reply with the single word READY.")
    print("SENT", json.dumps(r)[:200], flush=True)
    await asyncio.sleep(secs)
    t.cancel()
    await c.close()


asyncio.run(main())
