"""Minimal client for the Autodesk Fusion desktop MCP server (Streamable HTTP).

Fusion hosts it at ``http://127.0.0.1:27182/mcp`` once Preferences > General >
API > "Fusion MCP Server" is enabled; it is local-only and unauthenticated.
The only tools this pipeline uses are ``fusion_mcp_execute`` (run a Python
script inside Fusion; its ``print`` output is the result) and
``fusion_mcp_read`` (``activeCommand``, ``document``). The server rejects every
script while a command dialog is open, and no MCP tool can close one, so a
session refuses to start until Fusion is idle.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_URL = "http://127.0.0.1:27182/mcp"
URL_ENV = "HARMONIC_FUSION_MCP_URL"
_PROTOCOL = "2025-03-26"
_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


class FusionError(RuntimeError):
    """Fusion was unreachable, busy, or a script it ran raised."""


class FusionSession:
    def __init__(self, url: str | None = None, timeout_s: float = 900.0) -> None:
        self.url = url or os.environ.get(URL_ENV) or DEFAULT_URL
        self.timeout_s = timeout_s
        self._next_id = 0
        self._session_id: str | None = None
        self._initialize()

    def _post(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, str]]:
        headers = dict(_HEADERS)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        request = urllib.request.Request(self.url, json.dumps(payload).encode(), headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = response.read().decode("utf-8")
                return (json.loads(body) if body.strip() else None), dict(response.headers)
        except urllib.error.URLError as exc:
            raise FusionError(
                f"Fusion MCP server unreachable at {self.url} ({exc}). Start Fusion and enable "
                "Preferences > General > API > Fusion MCP Server."
            ) from exc

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        reply, _headers = self._post({"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params})
        if reply is None:
            raise FusionError(f"{method}: empty reply")
        if "error" in reply:
            raise FusionError(f"{method}: {reply['error']}")
        return reply["result"]

    def _initialize(self) -> None:
        self._next_id += 1
        reply, headers = self._post({
            "jsonrpc": "2.0", "id": self._next_id, "method": "initialize",
            "params": {"protocolVersion": _PROTOCOL, "capabilities": {}, "clientInfo": {"name": "harmonic-analyzer", "version": "1"}},
        })
        session = {k.lower(): v for k, v in headers.items()}.get("mcp-session-id")
        if reply is None or "result" not in reply or not session:
            raise FusionError(f"initialize failed: {reply}")
        self._session_id = session
        self.server = reply["result"].get("serverInfo", {})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, tool: str, arguments: dict[str, Any]) -> str:
        result = self._rpc("tools/call", {"name": tool, "arguments": arguments})
        text = "\n".join(part.get("text", "") for part in result.get("content", []))
        if result.get("isError"):
            raise FusionError(f"{tool}: {text}")
        return text

    def call_json(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        reply = json.loads(self.call(tool, arguments))
        if reply.get("success") is False:
            raise FusionError(f"{tool}: {reply.get('error') or reply}")
        return reply

    # Fusion's selection mode is always active and the reply carries no
    # default-command flag: {"commandId": "SelectCommand", ...} means idle.
    IDLE_COMMANDS = frozenset({"SelectCommand"})

    def require_idle(self) -> None:
        """Refuse to start while a command dialog is open: scripts would be rejected."""
        active = self.call_json("fusion_mcp_read", {"queryType": "activeCommand"})
        command = active.get("commandId")
        if command and command not in self.IDLE_COMMANDS:
            raise FusionError(
                f"Fusion has the '{active.get('commandName', command)}' dialog open; "
                "cancel it in Fusion and rerun."
            )

    def run_script(self, script: str) -> str:
        """Run ``script`` (which defines ``run(_context)``) inside Fusion; return its printed output.

        The script's own traceback is the error report, so scripts must not catch
        their exceptions.
        """
        reply = self.call_json("fusion_mcp_execute", {"featureType": "script", "object": {"script": script}})
        return str(reply.get("message", ""))

    def close_active_document_without_saving(self) -> None:
        self.call_json("fusion_mcp_execute", {
            "featureType": "document",
            "object": {"operation": "close", "userConfirmedCloseWithoutSave": True},
        })
