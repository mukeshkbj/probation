"""HTTP shim between the Switch Trust CLI (flintai / switch-trust) and a Switch candidate agent."""

from .server import AskFn, ShimServer, echo_ask, flatten_chat

__all__ = ["AskFn", "ShimServer", "echo_ask", "flatten_chat"]
