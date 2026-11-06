"""Small helpers shared by the setup scripts. Standard library + httpx only.

The scripts are deliberately standalone (they do not import the `warden`
package), so they can be used to check a Switch server before Warden exists.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def read_dotenv(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file. Missing file -> {}."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        out[key.strip()] = value
    return out


def load_env() -> dict[str, str]:
    """.env in the repo root, overridden by real environment variables."""
    merged = read_dotenv(REPO_ROOT / ".env")
    merged.update({k: v for k, v in os.environ.items() if v != ""})
    return merged


def need(env: dict[str, str], *keys: str) -> list[str]:
    """Return the values for `keys`, or exit with a clear message naming the missing ones."""
    missing = [k for k in keys if not env.get(k)]
    if missing:
        sys.exit(
            "Missing in .env: "
            + ", ".join(missing)
            + "\nSee docs/SETUP.md (copy .env.example to .env first)."
        )
    return [env[k] for k in keys]


def base_url(env: dict[str, str]) -> str:
    return (env.get("SWITCH_BASE_URL") or "http://localhost:8000").rstrip("/")
