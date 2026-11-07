"""Diagnostic: print the recent timeline of a room (who said what).

Usage: uv run python scripts/diag_room.py <room_id> [limit] [grep]
"""
import asyncio
import sys

sys.path.insert(0, ".")
from warden.config import load_settings  # noqa: E402
from warden.switch_client import SwitchClient  # noqa: E402


async def main() -> None:
    room = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    needle = sys.argv[3].lower() if len(sys.argv) > 3 else ""
    s = load_settings()
    c = SwitchClient(s.base_url, s.agent_id, s.api_key)
    task = asyncio.create_task(anext(aiter(c.listen([s.team_room_id]))))
    await asyncio.sleep(3)
    r = await c.op("read_context", {"room_id": room, "limit": limit})
    r = r.get("result", r)
    for th in r.get("threads", []):
        for e in [th["root"], *th.get("replies", [])]:
            body = (e.get("body") or "").replace("\n", " ")
            if needle and needle not in body.lower():
                continue
            print(f"[{e.get('sender_name')}] {body[:600]}\n")
    task.cancel()
    await c.close()


asyncio.run(main())
