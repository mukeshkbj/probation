"""python -m warden"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from warden.app import Warden
from warden.config import load_settings
from warden.switch_client import SwitchClient


async def main() -> int:
    settings = load_settings()
    missing = [k for k, v in {
        "WARDEN_AGENT_ID": settings.agent_id,
        "WARDEN_API_KEY": settings.api_key,
        "TEAM_ROOM_ID": settings.team_room_id,
    }.items() if not v]
    if missing:
        print(f"Missing settings: {', '.join(missing)} (see .env.example)", file=sys.stderr)
        return 2
    client = SwitchClient(settings.base_url, settings.agent_id, settings.api_key,
                          agent_name=settings.name)
    warden = Warden(settings, client)
    try:
        await warden.run()
    finally:
        await client.close()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        pass
