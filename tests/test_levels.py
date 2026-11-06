import pytest

from warden.levels import (
    THRESHOLDS,
    Level,
    classify_request,
    decide,
    demotion_due,
    passes_redteam,
    promotion_due,
)


def test_thresholds_match_contract():
    assert THRESHOLDS == {
        "redteam_min": 0.8,
        "intern_good_ratings": 3,
        "associate_good_ratings": 5,
        "bad_ratings_demote": 3,
    }


@pytest.mark.parametrize("room", ["team", "probation"])
@pytest.mark.parametrize("kind", ["task", "action"])
def test_enrolled_refuses_everything(room, kind):
    assert decide(Level.ENROLLED, room, kind) == "refuse"


def test_intern():
    assert decide(Level.INTERN, "probation", "task") == "forward"
    assert decide(Level.INTERN, "probation", "action") == "propose"
    assert decide(Level.INTERN, "team", "task") == "propose"
    assert decide(Level.INTERN, "team", "action") == "refuse"


def test_associate_and_colleague():
    assert decide(Level.ASSOCIATE, "team", "task") == "forward"
    assert decide(Level.ASSOCIATE, "team", "action") == "propose"
    for room in ("team", "probation"):
        for kind in ("task", "action"):
            assert decide(Level.COLLEAGUE, room, kind) == "forward"


def test_unknown_inputs_refuse():
    assert decide(Level.COLLEAGUE, "lobby", "task") == "refuse"
    assert decide(7, "team", "task") == "refuse"  # type: ignore[arg-type]


def test_trust_only_grows_with_level():
    order = {"refuse": 0, "propose": 1, "forward": 2}
    for room in ("team", "probation"):
        for kind in ("task", "action"):
            ranks = [order[decide(lvl, room, kind)] for lvl in Level]
            assert ranks == sorted(ranks)


def test_classify_request():
    assert classify_request("Summarise the open tickets") == "task"
    assert classify_request("Email the customer a refund note") == "action"
    assert classify_request("Deploy the hotfix") == "action"


def test_promotion_and_demotion():
    assert promotion_due(Level.INTERN, 2) is None
    assert promotion_due(Level.INTERN, 3) == Level.ASSOCIATE
    assert promotion_due(Level.ASSOCIATE, 4) is None
    assert promotion_due(Level.ASSOCIATE, 5) == Level.COLLEAGUE
    assert promotion_due(Level.COLLEAGUE, 99) is None
    assert promotion_due(Level.ENROLLED, 99) is None
    assert not demotion_due(2)
    assert demotion_due(3)
    assert passes_redteam(0.8) and not passes_redteam(0.79)


def test_labels():
    assert Level.INTERN.label == "L1 Intern"
    assert Level.COLLEAGUE.label == "L3 Colleague"
