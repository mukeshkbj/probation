"""Diagnostic: print Warden's id and each candidate's stored addressing policy.

Usage: uv run python scripts/diag_policy.py scout rookie
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")
from warden.config import load_settings  # noqa: E402
from warden.switch_client import SwitchClient  # noqa: E402


async def main() -> None:
    s = load_settings()
    c = SwitchClient(s.base_url, s.agent_id, s.api_key)
    task = asyncio.create_task(anext(aiter(c.listen([s.team_room_id]))))  # opens a live connection
    await asyncio.sleep(3)
    print("warden id:", s.agent_id)
    agents = await c.op("list_agents", {})
    for a in agents["result"]: print(a["name"], a["id"], "owner:", a["owner_name"], "policy:", json.dumps(a.get("addressing_policy")))
    task.cancel()
    await c.close()


asyncio.run(main())
