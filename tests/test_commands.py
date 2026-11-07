import pytest

from warden.commands import parse


@pytest.mark.parametrize(
    "text,verb,agent",
    [
        ("@warden enrol @scout", "enrol", "scout"),
        ("@warden enroll scout", "enrol", "scout"),
        ("warden: status @Rookie", "status", "rookie"),
        ("@warden spot-check @scout", "spotcheck", "scout"),
        ("@warden spotcheck @scout", "spotcheck", "scout"),
        ("@warden demote @scout", "demote", "scout"),
        ("@warden approve @scout", "approve", "scout"),
        ("@warden reject @scout", "reject", "scout"),
        ("enrol @scout", "enrol", "scout"),  # mention stripped by the bridge
    ],
)
def test_agent_commands(text, verb, agent):
    cmd = parse(text)
    assert cmd is not None and cmd.error is None
    assert (cmd.verb, cmd.agent) == (verb, agent)


def test_rate():
    assert parse("@warden rate @scout good").rating == "good"
    assert parse("@warden rate @scout BAD").rating == "bad"
    assert parse("@warden rate @scout 👍").rating == "good"
    assert parse("@warden rate @scout meh").error


def test_ask_keeps_task_text():
    cmd = parse("@warden ask @scout Summarise ticket #42, please.\nKeep it short.")
    assert cmd.verb == "ask" and cmd.agent == "scout"
    assert cmd.task == "Summarise ticket #42, please.\nKeep it short."
    assert parse("@warden ask @scout").error


def test_approve_action():
    assert parse("@warden approve-action 7").proposal_id == 7
    assert parse("@warden approve-action #12").proposal_id == 12
    assert parse("@warden reject-action 3").verb == "reject-action"
    assert parse("@warden approve-action soon").error


def test_help_and_non_commands():
    assert parse("@warden help").verb == "help"
    assert parse("hello team") is None
    assert parse("") is None
    assert parse("@someone enrol @scout") is None


def test_missing_agent_is_usage_error():
    cmd = parse("@warden enrol")
    assert cmd.error and "enrol @agent" in cmd.error


def test_cannot_target_warden():
    assert parse("@warden demote @warden").error


def test_custom_name():
    assert parse("@gatekeeper status @scout", warden_name="gatekeeper").agent == "scout"


def test_unaddressed_messages_need_the_warden_prefix():
    # Warden reads every message in its rooms; a teammate's bare "help" is not for it.
    assert parse("help", require_prefix=True) is None
    assert parse("status scout", require_prefix=True) is None
    assert parse("warden, enrol scout", require_prefix=True).verb == "enrol"
    assert parse("Warden: status rookie", require_prefix=True).agent == "rookie"
