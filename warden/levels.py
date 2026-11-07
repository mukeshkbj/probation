"""Trust levels and the routing policy. Pure functions, no I/O."""

from __future__ import annotations

import re
from enum import IntEnum


class Level(IntEnum):
    ENROLLED = 0
    INTERN = 1
    ASSOCIATE = 2
    COLLEAGUE = 3

    @property
    def title(self) -> str:
        return self.name.capitalize()

    @property
    def label(self) -> str:
        return f"L{int(self)} {self.title}"


THRESHOLDS = {
    "redteam_min": 0.8,
    "intern_good_ratings": 3,  # good ratings at L1 before a review for L2
    "associate_good_ratings": 5,  # good ratings at L2 before a review for L3
    "bad_ratings_demote": 3,  # bad ratings at any level -> back to L0
}

# (level, room_kind, request_kind) -> decision.
# room_kind: where the request came from ("team" = shared team room,
# "probation" = the agent's own side room). request_kind: "task" (produce
# words) or "action" (do something with side effects).
_POLICY: dict[tuple[Level, str, str], str] = {
    (Level.ENROLLED, "probation", "task"): "refuse",
    (Level.ENROLLED, "probation", "action"): "refuse",
    (Level.ENROLLED, "team", "task"): "refuse",
    (Level.ENROLLED, "team", "action"): "refuse",
    (Level.INTERN, "probation", "task"): "forward",
    (Level.INTERN, "probation", "action"): "propose",
    (Level.INTERN, "team", "task"): "propose",
    (Level.INTERN, "team", "action"): "refuse",
    (Level.ASSOCIATE, "probation", "task"): "forward",
    (Level.ASSOCIATE, "probation", "action"): "forward",
    (Level.ASSOCIATE, "team", "task"): "forward",
    (Level.ASSOCIATE, "team", "action"): "propose",
    (Level.COLLEAGUE, "probation", "task"): "forward",
    (Level.COLLEAGUE, "probation", "action"): "forward",
    (Level.COLLEAGUE, "team", "task"): "forward",
    (Level.COLLEAGUE, "team", "action"): "forward",
}


def decide(level: Level, room_kind: str, request_kind: str) -> str:
    """Return "forward" | "propose" | "refuse". Unknown inputs refuse."""
    try:
        lvl = Level(int(level))
    except ValueError:
        return "refuse"
    return _POLICY.get((lvl, room_kind, request_kind), "refuse")


def refusal_reason(level: Level, room_kind: str, request_kind: str) -> str:
    lvl = Level(int(level))
    if lvl == Level.ENROLLED:
        return f"it is {lvl.label}: it must pass the red-team before taking any work"
    return f"{lvl.label} may not take {request_kind}s from the {room_kind} room yet"


_ACTION_WORDS = re.compile(
    r"\b(send|e-?mail|email|post|publish|delete|remove|drop|deploy|release|merge|push|"
    r"commit|pay|refund|transfer|invite|share|update|change|modify|write to|run|"
    r"execute|install|book|order|cancel|close|create)\b",
    re.IGNORECASE,
)


# Words that make a request side-effect free when they lead it.
_TASK_LEAD = re.compile(
    r"^(draft|summari[sz]e|write( up)?|explain|list|describe|outline|suggest|propose|"
    r"review|check|read|find|compare|analy[sz]e|plan|answer|tell|what|how|why|which|who|"
    r"when|can you (draft|summari[sz]e|explain|list|describe|suggest|check))\b",
    re.IGNORECASE,
)
# A side effect asked for later in the sentence ("draft it and send it").
_ACTION_TAIL = re.compile(
    r"\b(and|then)\s+(send|e-?mail|post|publish|delete|remove|deploy|merge|push|pay|"
    r"refund|transfer|invite|share|book|order|cancel|close|create)\b"
    r"|\b(send|post|publish|share) (it|this|them)\b",
    re.IGNORECASE,
)


def classify_request(text: str) -> str:
    """'action' if the request asks the agent to *do* something with side
    effects, otherwise 'task' (read, draft, summarise, answer).

    Judged by what the request asks the agent to do, not by every word in it:
    "draft an update about this week's refunds" is a task, "refund her" and
    "draft it and send it" are actions (live, 7 Nov: the first was proposed).
    """
    text = re.sub(r"^\s*(please|pls|could you|can you)\s+", "", (text or "").strip(), flags=re.I)
    if _ACTION_TAIL.search(text):
        return "action"
    if _TASK_LEAD.search(text):
        return "task"
    first = re.match(r"\W*(\w[\w-]*)", text)
    return "action" if first and _ACTION_WORDS.fullmatch(first.group(1)) else "task"


def promotion_due(level: Level, good: int) -> Level | None:
    """The level a sponsor should review the agent for, if any."""
    lvl = Level(int(level))
    if lvl == Level.INTERN and good >= THRESHOLDS["intern_good_ratings"]:
        return Level.ASSOCIATE
    if lvl == Level.ASSOCIATE and good >= THRESHOLDS["associate_good_ratings"]:
        return Level.COLLEAGUE
    return None


def demotion_due(bad: int) -> bool:
    return bad >= THRESHOLDS["bad_ratings_demote"]


def passes_redteam(score: float) -> bool:
    return score >= THRESHOLDS["redteam_min"]
