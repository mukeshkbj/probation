"""Export a room's timeline (verbatim) to JSON, for the demo replay.

Usage: uv run python scripts/export_room.py <room_id> <out.json> [limit]
"""
import asyncio, json, sys
sys.path.insert(0, ".")
from warden.config import load_settings  # noqa: E402
from warden.switch_client import SwitchClient  # noqa: E402


async def main() -> None:
    room, out = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    s = load_settings()
    c = SwitchClient(s.base_url, s.agent_id, s.api_key)
    task = asyncio.create_task(anext(aiter(c.listen([s.team_room_id]))))
    await asyncio.sleep(3)
    r = await c.op("read_context", {"room_id": room, "limit": limit})
    r = r.get("result", r)
    rows = []
    for th in r.get("threads", []):
        for e in [th["root"], *th.get("replies", [])]:
            rows.append({"ts": e.get("timestamp"), "sender": e.get("sender_name"), "body": e.get("body")})
    rows.sort(key=lambda x: x["ts"] or 0)
    json.dump({"room": room, "truncated": r.get("truncated"), "messages": rows}, open(out, "w"), indent=1)
    print(len(rows), "messages; truncated:", r.get("truncated"))
    task.cancel(); await c.close()

asyncio.run(main())
