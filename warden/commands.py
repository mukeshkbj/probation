"""Parse "@warden ..." commands from the team room."""

from __future__ import annotations

import re
from dataclasses import dataclass

VERBS = (
    "enrol", "status", "rate", "approve", "reject", "approve-action", "reject-action",
    "spotcheck", "demote", "ask", "help",
)
_ALIASES = {"enroll": "enrol", "spot-check": "spotcheck"}

USAGE = {
    "enrol": "enrol @agent",
    "status": "status @agent",
    "rate": "rate @agent good|bad",
    "approve": "approve @agent",
    "reject": "reject @agent",
    "approve-action": "approve-action <id>",
    "reject-action": "reject-action <id>",
    "spotcheck": "spotcheck @agent",
    "demote": "demote @agent",
    "ask": "ask @agent <task>",
    "help": "help",
}

HELP_TEXT = (
    "Start a command with `warden,` (e.g. `warden, enrol scout`). Commands: "
    + " · ".join(f"`{u}`" for u in USAGE.values())
)

_PREFIX = r"^\s*(?:(?:@|<@!?)?{name}>?[:,]?\s+)?"
_VERB = r"(?P<verb>approve-action|reject-action|spot-check|spotcheck|enrol|enroll|status|rate|approve|reject|demote|ask|help)\b"
_AGENT = re.compile(r"^@?(?P<agent>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<rest>.*)$", re.DOTALL)


@dataclass
class Command:
    verb: str
    agent: str | None = None
    rating: str | None = None
    task: str | None = None
    proposal_id: int | None = None
    error: str | None = None  # set when the verb is known but the arguments are not


def parse(text: str, warden_name: str = "warden", *, require_prefix: bool = False) -> Command | None:
    """Return a Command, or None when the text is not a Warden command.

    With `require_prefix`, the text must start with Warden's name ("warden,
    enrol scout"). Used for messages Switch did not address to Warden: it reads
    every message in its rooms, and a bare "help" from a teammate is not for it.
    """
    if not text:
        return None
    prefix = _PREFIX.format(name=re.escape(warden_name))
    if require_prefix:
        prefix = prefix[:-1]  # drop the trailing `?`: the name is no longer optional
    pattern = re.compile(prefix + _VERB + r"\s*(?P<rest>.*)$",
                         re.IGNORECASE | re.DOTALL)
    m = pattern.match(text)
    if not m:
        return None
    verb = m.group("verb").lower()
    verb = _ALIASES.get(verb, verb)
    rest = m.group("rest").strip()

    def bad() -> Command:
        return Command(verb=verb, error=f"Usage: `@{warden_name} {USAGE[verb]}`")

    if verb == "help":
        return Command(verb="help")
    if verb in ("approve-action", "reject-action"):
        idm = re.match(r"^#?(\d+)\b", rest)
        return Command(verb=verb, proposal_id=int(idm.group(1))) if idm else bad()

    am = _AGENT.match(rest)
    if not am:
        return bad()
    agent = am.group("agent").lower().rstrip(".,:")
    tail = am.group("rest").strip()
    if agent == warden_name.lower():
        return bad()
    if verb == "rate":
        rm = re.match(r"^(good|bad|\+1|-1|👍|👎)(?=$|[\s.!,])", tail, re.IGNORECASE)
        if not rm:
            return bad()
        token = rm.group(1).lower()
        rating = "good" if token in ("good", "+1", "👍") else "bad"
        return Command(verb=verb, agent=agent, rating=rating)
    if verb == "ask":
        if not tail:
            return bad()
        return Command(verb=verb, agent=agent, task=tail.lstrip(":, ").strip())
    return Command(verb=verb, agent=agent)
