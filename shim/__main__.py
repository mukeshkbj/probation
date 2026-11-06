"""Run the shim: `python -m shim --echo` (dev) or `python -m shim --switch` (relay via Switch)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os

from .server import ShimServer, echo_ask


async def _main(args: argparse.Namespace) -> None:
    relay = None
    if args.echo:
        server = ShimServer(echo_ask, host=args.host, port=args.port, default_agent=args.agent)
    else:
        from .relay import relay_from_env  # noqa: PLC0415

        relay = relay_from_env()
        server = ShimServer(router=relay.ask_for, host=args.host, port=args.port,
                            default_agent=args.agent, timeout=relay.timeout + 5)
    await server.start()
    print(f"shim ready on {server.url}  (mode={'echo' if args.echo else 'switch'})", flush=True)
    try:
        await server.serve_forever()
    finally:
        if relay:
            await relay.stop()
            await relay.client.close()


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m shim", description=__doc__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--echo", action="store_true", help="reply with the prompt (no agent needed)")
    mode.add_argument("--switch", action="store_true", help="relay prompts to the candidate via Switch (default)")
    p.add_argument("--host", default=os.environ.get("SHIM_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("SHIM_PORT", "8787")))
    p.add_argument("--agent", default="candidate", help="agent used when the request does not name one")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    try:
        asyncio.run(_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
