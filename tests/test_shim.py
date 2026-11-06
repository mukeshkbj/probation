import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shim.relay import SwitchRelay  # noqa: E402
from shim.server import ShimServer, echo_ask, flatten_chat  # noqa: E402


@pytest.mark.asyncio
async def test_generic_http_shape_echo():
    async with ShimServer(echo_ask, port=0) as shim:
        async with httpx.AsyncClient(base_url=shim.url, trust_env=False) as c:
            # exactly what flintai GenericHttpModel / OpenAIAgentModel send
            r = await c.post("/agents/scout/run", json={"input": "hello"})
            assert r.status_code == 200
            assert r.json()["output"] == "[echo] hello"
            assert r.json()["agent"] == "scout"
            r = await c.post("/run", json={"input": "hi"})
            assert r.json()["output"] == "[echo] hi"
            assert (await c.get("/health")).json() == {"ok": True}
    assert shim.requests[0] == {"agent": "scout", "prompt": "hello", "reply": "[echo] hello", "endpoint": "run"}


@pytest.mark.asyncio
async def test_router_selects_agent_by_path_and_model():
    seen = []

    def router(agent):
        async def ask(prompt):
            seen.append((agent, prompt))
            return f"{agent}:{prompt}"
        return ask

    async with ShimServer(router=router, port=0) as shim:
        async with httpx.AsyncClient(base_url=shim.url, trust_env=False) as c:
            r = await c.post("/agents/rookie/run", json={"input": "a"})
            assert r.json()["output"] == "rookie:a"
            r = await c.post("/run?agent=scout", json={"input": "b"})
            assert r.json()["output"] == "scout:b"
            r = await c.post("/v1/chat/completions",
                             json={"model": "scout", "messages": [{"role": "user", "content": "c"}]})
            body = r.json()
            assert body["object"] == "chat.completion"
            assert body["choices"][0]["message"] == {"role": "assistant", "content": "scout:c"}
            assert body["choices"][0]["finish_reason"] == "stop"
            r = await c.post("/agents/rookie/v1/chat/completions",
                             json={"model": "ignored", "messages": [{"role": "user", "content": "d"}]})
            assert r.json()["choices"][0]["message"]["content"] == "rookie:d"
    assert [a for a, _ in seen] == ["rookie", "scout", "scout", "rookie"]


def test_flatten_chat_matches_flintai():
    assert flatten_chat([{"role": "user", "content": "x"}]) == "x"
    out = flatten_chat([{"role": "system", "content": "s"}, {"role": "user", "content": [{"type": "text", "text": "u"}]}])
    assert out == "SYSTEM: s\n\nUSER: u"


@pytest.mark.asyncio
async def test_errors_are_json():
    async def boom(prompt):
        raise RuntimeError("relay down")

    async def slow(prompt):
        await asyncio.sleep(5)
        return "late"

    async with ShimServer(boom, port=0) as shim:
        async with httpx.AsyncClient(base_url=shim.url, trust_env=False) as c:
            assert (await c.post("/agents/x/run", json={"input": "p"})).status_code == 502
            assert (await c.post("/agents/x/run", json={"nothing": 1})).status_code == 400
            assert (await c.post("/agents/x/run", content=b"not json")).status_code == 400
            assert (await c.post("/nope/nope/nope/nope", json={})).status_code == 404
            assert (await c.get("/run")).status_code == 405
    async with ShimServer(slow, port=0, timeout=0.2) as shim:
        async with httpx.AsyncClient(base_url=shim.url, trust_env=False) as c:
            r = await c.post("/run", json={"input": "p"})
            assert r.status_code == 504
            assert "did not reply" in r.json()["error"]["message"]


@pytest.mark.asyncio
async def test_requests_to_one_agent_are_serialised():
    active = 0
    peak = 0

    async def ask(prompt):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1
        return prompt

    async with ShimServer(ask, port=0) as shim:
        async with httpx.AsyncClient(base_url=shim.url, trust_env=False) as c:
            rs = await asyncio.gather(*[c.post("/agents/a/run", json={"input": str(i)}) for i in range(5)])
    assert sorted(r.json()["output"] for r in rs) == [str(i) for i in range(5)]
    assert peak == 1


class _Msg:
    def __init__(self, room_id, sender, text, sender_kind="agent"):
        self.room_id, self.sender, self.text, self.sender_kind = room_id, sender, text, sender_kind


class FakeSwitch:
    def __init__(self):
        self.sent = []
        self.q: asyncio.Queue = asyncio.Queue()

    async def send_targeted(self, room_id, target, content):
        self.sent.append((room_id, target, content))
        await self.q.put(_Msg(room_id, "someone", "noise", sender_kind="user"))
        await self.q.put(_Msg(room_id, f"@{target}:switch", f"reply to {content}"))
        return {"ok": True}

    async def listen(self, rooms):
        while True:
            yield await self.q.get()


@pytest.mark.asyncio
async def test_switch_relay_round_trip_through_shim():
    fake = FakeSwitch()
    relay = SwitchRelay(fake, {"scout": "room-scout"}, timeout=2)
    async with ShimServer(router=relay.ask_for, port=0) as shim:
        async with httpx.AsyncClient(base_url=shim.url, trust_env=False) as c:
            r = await c.post("/agents/scout/run", json={"input": "ping"})
    await relay.stop()
    assert r.json()["output"] == "reply to ping"
    assert fake.sent == [("room-scout", "scout", "ping")]


@pytest.mark.asyncio
async def test_switch_relay_unknown_room():
    relay = SwitchRelay(FakeSwitch(), {}, timeout=1)
    with pytest.raises(RuntimeError, match="no probation room"):
        await relay.ask_for("ghost")("hi")
    await relay.stop()
