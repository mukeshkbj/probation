#!/usr/bin/env python3
"""Register Warden as a custom agent on your Switch server.

Usage:
    python scripts/register_warden.py              # first time
    python scripts/register_warden.py --overwrite  # name taken: re-register (rotates the key)

Reads SWITCH_BASE_URL and SWITCH_REGISTRATION_KEY from .env (or the real
environment). On success it prints the two lines to paste into .env:

    WARDEN_AGENT_ID=...
    WARDEN_API_KEY=...

The API key is shown once by Switch and is printed here once, to stdout only.
It is never written to a file or a log by this script.

Verified against the Switch server source (sandbox-quantum/switch):
  * route   POST /agents   core/switch_core/bridges/agent/api/handlers.py:206
            (router mounted at prefix "/agents", bridges/agent/app.py:171)
  * auth    Authorization: Bearer <registration key>
            (handlers.py:_resolve_registration_user_id; the key's owner becomes
            the agent's owner, so use a key YOU created, not the bootstrap key)
  * body    RegisterAgentRequest, api/schemas.py:20-30
  * profile IntegrationProfile, protocol/types.py:28-43
            (same shape as loadtest/seed.py PROFILE)
  * reply   {"id", "api_key"}; 409 when the name exists and overwrite is false
"""

from __future__ import annotations

import argparse
import sys

import httpx

from _common import base_url, load_env, need

# The agent is always connected and only exchanges messages. Same profile the
# Switch load-test agents register with (loadtest/seed.py PROFILE).
PROFILE = {
    "connection_model": "always_on",
    "message_exchange": True,
    "pre_invocation_mediation": [],
    "post_invocation_mediation": [],
    "event_reporting": [],
    # Dropped by current servers (extra="ignore"), still required by older builds.
    "task_protocol": {"can_delegate": False, "can_accept": False},
}

DESCRIPTION = (
    "Runs the probation programme for new agents: enrols them, red-teams them, "
    "forwards only the work their trust level allows, and keeps their personnel files."
)


def main() -> int:
    env = load_env()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--name", default=env.get("WARDEN_NAME") or "warden",
                        help="agent name (lowercase letters, digits, . - _)")
    parser.add_argument("--description", default=DESCRIPTION)
    parser.add_argument("--overwrite", action="store_true",
                        help="re-register an existing agent of yours; rotates its API key")
    parser.add_argument("--base-url", default=base_url(env),
                        help="Switch server address (default: SWITCH_BASE_URL)")
    args = parser.parse_args()

    (reg_key,) = need(env, "SWITCH_REGISTRATION_KEY")
    url = args.base_url.rstrip("/")

    with httpx.Client(base_url=url, timeout=30) as http:
        # /health is public: a 200 here means this really is the agent API address.
        try:
            h = http.get("/health")
        except httpx.HTTPError as exc:
            print(f"Cannot reach {url}: {type(exc).__name__}. Is the Switch server running, "
                  "and is SWITCH_BASE_URL the address shown under Settings > System status?",
                  file=sys.stderr)
            return 2
        if h.status_code != 200:
            print(f"{url}/health answered HTTP {h.status_code}. Wrong address? "
                  "Use the server's API address, not the dashboard's.", file=sys.stderr)
            return 2

        body = {
            "name": args.name,
            "description": args.description,
            "display_name": "Warden",
            "connector_type": "custom",
            "integration_profile": PROFILE,
            "overwrite": args.overwrite,
        }
        r = http.post("/agents", json=body,
                      headers={"Authorization": f"Bearer {reg_key}"})

    if r.status_code == 409:
        print(f"An agent called '{args.name}' already exists ({_detail(r)}).\n"
              "If it is yours, run again with --overwrite (this issues a new API key).\n"
              "If it belongs to someone else, choose another --name and set WARDEN_NAME.",
              file=sys.stderr)
        return 1
    if r.status_code == 401:
        print("Switch refused the registration key (HTTP 401). Create one under "
              "Switch Console > Settings > API keys > Create registration key, and paste "
              "it into SWITCH_REGISTRATION_KEY. An agent's own API key will not work here.",
              file=sys.stderr)
        return 1
    if r.status_code != 200:
        print(f"Registration failed: HTTP {r.status_code} {_detail(r)}", file=sys.stderr)
        return 1

    data = r.json()
    print("# Registered. Paste these two lines into .env (the key is not shown again):")
    print(f"WARDEN_AGENT_ID={data['id']}")
    print(f"WARDEN_API_KEY={data['api_key']}")
    print(f"# Next: in your Discord team room, type  !invite-agent @{args.name}", file=sys.stderr)
    return 0


def _detail(r: httpx.Response) -> str:
    # Error bodies carry a reason, never a key.
    try:
        d = r.json().get("detail")
    except ValueError:
        d = r.text
    return str(d)[:300]


if __name__ == "__main__":
    sys.exit(main())
