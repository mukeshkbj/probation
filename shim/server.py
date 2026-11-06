"""HTTP shim that lets the Switch Trust CLI (flintai / switch-trust) red-team a Switch agent.

The CLI cannot talk to a Switch room, but it can call any HTTP agent. This shim exposes the
request/response shapes the CLI sends (verified against flintai-cli 1.6.2 and switch-trust-cli
1.8.0 wheel source, see redteam/FLINTAI_NOTES.md) and forwards each prompt to an injectable
`ask(prompt) -> reply` coroutine. In production Warden wires `ask` to its probation-room relay.

Endpoints
---------
POST /agents/{agent}/run      {"input": "<prompt>"} -> {"output": "<reply>"}
POST /run                     same, agent from ?agent=, body "agent"/"model", or the default
                              (shape of model types `generic_http` and `openai_agent`/`anthropic_agent`)
POST /v1/chat/completions     OpenAI chat-completions request -> chat.completion response;
POST /agents/{agent}/v1/chat/completions   agent = path segment or body "model"
                              (model type `openai_compatible`, and a generic fallback)
GET  /health                  {"ok": true}

Dependency-free: a tiny HTTP/1.1 server on asyncio streams (Content-Length bodies only,
one request per connection, `Connection: close`).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qs, unquote, urlsplit

log = logging.getLogger("shim")

AskFn = Callable[[str], Awaitable[str]]
Router = Callable[[str], AskFn]  # agent name -> ask function for that agent

MAX_BODY = 2 * 1024 * 1024
_REASONS = {200: "OK", 400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed",
            411: "Length Required", 413: "Payload Too Large", 502: "Bad Gateway",
            504: "Gateway Timeout", 500: "Internal Server Error"}


async def echo_ask(prompt: str) -> str:
    """Dev mode: reply with the prompt (lets you smoke-test the CLI wiring without an agent)."""
    return f"[echo] {prompt}"


def flatten_chat(messages: list[dict]) -> str:
    """Mirror flintai's flatten_messages: one message -> its text; several -> 'ROLE: text' blocks."""
    def text_of(m: dict) -> str:
        c = m.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):  # OpenAI content parts
            return " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("text"))
        return ""

    msgs = [m for m in messages or [] if isinstance(m, dict)]
    if len(msgs) == 1:
        return text_of(msgs[0])
    return "\n\n".join(f"{str(m.get('role', 'user')).upper()}: {text_of(m)}" for m in msgs)


def _get_path(data, path: str):
    cur = data
    for key in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list):
            try:
                cur = cur[int(key)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


class HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class ShimServer:
    """Serve the shim. Provide `ask` (single agent) and/or `router` (per-agent ask factory)."""

    def __init__(
        self,
        ask: AskFn | None = None,
        *,
        router: Router | None = None,
        default_agent: str = "candidate",
        host: str = "127.0.0.1",
        port: int = 8787,
        input_keys: tuple[str, ...] = ("input", "prompt", "message", "query", "text"),
        timeout: float | None = None,
    ):
        if ask is None and router is None:
            raise ValueError("ShimServer needs ask= or router=")
        self._ask = ask
        self._router = router
        self.default_agent = default_agent
        self.host = host
        self._port = port
        self.input_keys = input_keys
        self.timeout = timeout
        self._server: asyncio.base_events.Server | None = None
        self._locks: dict[str, asyncio.Lock] = {}
        self.requests: list[dict] = []  # audit trail: {agent, prompt, reply, endpoint}

    # -- lifecycle ------------------------------------------------------------------------------

    @property
    def port(self) -> int:
        if self._server and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self._port

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    async def start(self) -> ShimServer:
        self._server = await asyncio.start_server(self._handle, self.host, self._port)
        log.info("shim listening on %s", self.url)
        return self

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def serve_forever(self) -> None:
        if not self._server:
            await self.start()
        assert self._server
        async with self._server:
            await self._server.serve_forever()

    async def __aenter__(self) -> ShimServer:
        return await self.start()

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    # -- core -----------------------------------------------------------------------------------

    def _ask_for(self, agent: str) -> AskFn:
        if self._router is not None:
            return self._router(agent)
        assert self._ask is not None
        return self._ask

    async def ask(self, agent: str, prompt: str, endpoint: str = "") -> str:
        lock = self._locks.setdefault(agent, asyncio.Lock())
        async with lock:  # candidates answer one message at a time in their room
            coro = self._ask_for(agent)(prompt)
            try:
                reply = await (asyncio.wait_for(coro, self.timeout) if self.timeout else coro)
            except asyncio.TimeoutError as e:
                raise HttpError(504, f"agent {agent!r} did not reply in time") from e
            except HttpError:
                raise
            except Exception as e:  # noqa: BLE001 - surface any relay failure as 502
                log.exception("ask failed for %s", agent)
                raise HttpError(502, f"relay to {agent!r} failed: {type(e).__name__}: {e}") from e
        reply = "" if reply is None else str(reply)
        self.requests.append({"agent": agent, "prompt": prompt, "reply": reply, "endpoint": endpoint})
        return reply

    async def _route(self, method: str, target: str, body: bytes) -> tuple[int, dict]:
        parts = urlsplit(target)
        path = parts.path.rstrip("/") or "/"
        query = parse_qs(parts.query)
        segs = [unquote(s) for s in path.split("/") if s]

        if path == "/health":
            return 200, {"ok": True}
        if method != "POST":
            raise HttpError(405, "use POST")
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise HttpError(400, f"invalid JSON body: {e}") from e
        if not isinstance(data, dict):
            raise HttpError(400, "JSON body must be an object")

        # /v1/chat/completions  or  /agents/{agent}/v1/chat/completions
        if segs[-3:] == ["v1", "chat", "completions"] or segs[-2:] == ["chat", "completions"]:
            agent = segs[1] if len(segs) >= 2 and segs[0] == "agents" else str(data.get("model") or self.default_agent)
            prompt = flatten_chat(data.get("messages") or [])
            if not prompt:
                raise HttpError(400, "messages[] is empty")
            reply = await self.ask(agent, prompt, "chat.completions")
            return 200, {
                "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": str(data.get("model") or agent),
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": reply},
                    "finish_reason": "stop",
                    "logprobs": None,
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }

        # /agents/{agent}/run | /run/{agent} | /run | /agents/{agent}
        agent = None
        if len(segs) >= 2 and segs[0] == "agents":
            agent = segs[1]
        elif len(segs) == 2 and segs[0] in ("run", "ask"):
            agent = segs[1]
        elif segs in (["run"], ["ask"], []):
            agent = (query.get("agent") or [None])[0] or data.get("agent") or data.get("model")
        else:
            raise HttpError(404, f"no route for {path}")
        agent = str(agent or self.default_agent)

        prompt = None
        for key in self.input_keys:
            val = _get_path(data, key)
            if isinstance(val, str) and val:
                prompt = val
                break
        if prompt is None and isinstance(data.get("messages"), list):
            prompt = flatten_chat(data["messages"])
        if not prompt:
            raise HttpError(400, f"no prompt in body; expected one of {list(self.input_keys)}")
        reply = await self.ask(agent, prompt, "run")
        return 200, {"output": reply, "agent": agent}

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        status, payload = 500, {"error": "internal error"}
        respond = True
        try:
            request_line = (await reader.readline()).decode("latin-1").strip()
            if not request_line:
                respond = False
                return
            try:
                method, target, _ = request_line.split(" ", 2)
            except ValueError as e:
                raise HttpError(400, "bad request line") from e
            headers: dict[str, str] = {}
            while True:
                line = (await reader.readline()).decode("latin-1")
                if line in ("\r\n", "\n", ""):
                    break
                k, _, v = line.partition(":")
                headers[k.strip().lower()] = v.strip()
            body = b""
            if "chunked" in headers.get("transfer-encoding", "").lower():
                body = await self._read_chunked(reader)
            elif headers.get("content-length"):
                n = int(headers["content-length"])
                if n > MAX_BODY:
                    raise HttpError(413, "body too large")
                body = await reader.readexactly(n)
            elif method.upper() == "POST":
                body = b"{}"
            status, payload = await self._route(method.upper(), target, body)
        except HttpError as e:
            status, payload = e.status, {"error": {"message": e.message, "type": "shim_error"}}
        except Exception as e:  # noqa: BLE001
            log.exception("shim request failed")
            status, payload = 500, {"error": {"message": f"{type(e).__name__}: {e}", "type": "shim_error"}}
        finally:
            try:
                if not respond:
                    raise ConnectionError("empty request")
                raw = json.dumps(payload).encode()
                head = (
                    f"HTTP/1.1 {status} {_REASONS.get(status, 'OK')}\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(raw)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
                writer.write(head + raw)
                await writer.drain()
            except (ConnectionError, RuntimeError):
                pass
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, RuntimeError):
                    pass

    @staticmethod
    async def _read_chunked(reader: asyncio.StreamReader) -> bytes:
        chunks = []
        total = 0
        while True:
            size = int((await reader.readline()).strip().split(b";")[0], 16)
            if size == 0:
                await reader.readline()
                break
            total += size
            if total > MAX_BODY:
                raise HttpError(413, "body too large")
            chunks.append(await reader.readexactly(size))
            await reader.readline()
        return b"".join(chunks)
