"""Claude SDK API-pool routing and isolated OMP RPC fallback.

Both adapters emit the existing Claude evidence vocabulary. Native records are
retained separately; normalization never substitutes text for a tool image.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid

import _telemetry
from filelock import FileLock, Timeout as LockTimeout
from machinist_review_credentials import CredentialPool, _directory

TOOLS = {"mcp__sheets__view_sheet", "mcp__sheets__crop"}
OMP_TOOLS = {"mcp__sheets_view_sheet", "mcp__sheets_crop"}


class TransportError(RuntimeError):
    def __init__(self, message, *, stdout="", stderr="", returncode=None):
        super().__init__(message)
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


def environment(key=None):
    env = dict(os.environ)
    for name in tuple(env):
        if name.startswith("ANTHROPIC_") or re.match(r"CLAUDE_CODE_(OAUTH|USE_|API_KEY|SUBAGENT_MODEL|AWS|VERTEX|FOUNDRY)", name):
            env[name] = ""
    if key:
        env["ANTHROPIC_API_KEY"] = key
    # An explicitly configured API proxy is trusted by both transports (and
    # enables loopback protocol smoke tests without paid/provider calls).
    if os.environ.get("ANTHROPIC_BASE_URL"):
        env["ANTHROPIC_BASE_URL"] = os.environ["ANTHROPIC_BASE_URL"]
    return env


def sdk_event(message):
    """Convert SDK public dataclasses without losing image/result/error data."""
    from claude_agent_sdk import AssistantMessage, UserMessage, SystemMessage, ResultMessage
    value = asdict(message)
    if isinstance(message, (AssistantMessage, UserMessage)):
        if isinstance(message.content, str):
            return {"type": "user", "message": {"content": message.content}}
        content = []
        for block, data in zip(message.content, value["content"]):
            if "type" not in data:
                data["type"] = {"TextBlock": "text", "ThinkingBlock": "thinking", "ToolUseBlock": "tool_use", "ToolResultBlock": "tool_result"}.get(type(block).__name__, type(block).__name__)
            content.append(data)
        return {"type": "assistant" if isinstance(message, AssistantMessage) else "user",
                "session_id": value.get("session_id"), "error": value.get("error"),
                "message": {**value, "content": content}}
    if isinstance(message, ResultMessage):
        return {"type": "result", **{name: item for name, item in value.items() if item is not None}, "modelUsage": value.get("model_usage")}
    if isinstance(message, SystemMessage):
        return {"type": "system", **value["data"]}
    return {"type": "sdk_event", **value}


def quota_event(event):
    """Only typed API failures authorize rotation, never ordinary model prose."""
    now = int(time.time() * 1000)
    if event.get("type") == "system" and event.get("subtype") == "api_retry" and event.get("error") == "rate_limit" and event.get("error_status") == 429:
        return {"status": "cooldown", "retryAt": now + max(1, event.get("retry_delay_ms") or 60000), "reason": "rate-limit"}
    if event.get("type") != "assistant" or not event.get("error"):
        return None
    error = event["error"]
    text = "\n".join(block.get("text", "") for block in event.get("message", {}).get("content", []) if block.get("type") == "text")
    if error in {"rate_limit", "invalid_request", "billing_error"}:
        if (error == "billing_error" and text == "Credit balance is too low") or re.search(r"Your credit balance is too low to access the Anthropic API|Insufficient (?:API )?credits", text, re.I):
            return {"status": "exhausted", "retryAt": None, "reason": "credit-balance"}
        if "enforced_spend_limit_reached" in text or re.search(r"You have reached your specified (?:workspace )?API usage limits", text):
            from datetime import datetime, timezone
            match = re.search(r"(?:reset|resets|until|on|at)\s+(?:(?:at|on)\s+)?(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)?)", text, re.I)
            retry = None
            if match:
                parsed = datetime.fromisoformat(match[1].replace("Z", "+00:00"))
                candidate = int(parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp() * 1000)
                if candidate > now:
                    retry = candidate
            return {"status": "exhausted", "retryAt": retry, "reason": "spend-limit"}
    if error == "rate_limit":
        return {"status": "cooldown", "retryAt": now + 60000, "reason": "rate-limit"}
    return None


async def _sdk(*, key, config, schema, model, effort, session_id, resume, cwd, remaining, startup, settings, emit, diagnostics, provenance):
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
    env = environment(key.api_key)
    session_dir = Path(provenance.get("sdk_session_dir") or tempfile.mkdtemp(prefix="machrev-sdk-sessions-"))
    provenance["sdk_session_dir"] = str(session_dir)
    env["CLAUDE_CONFIG_DIR"] = str(session_dir)
    env["MCP_TIMEOUT"] = str(max(1, int(min(startup, remaining()) * 1000)))
    options = ClaudeAgentOptions(
        cwd=cwd, env=env, model=model, effort=effort, thinking={"type": "adaptive"},
        tools=[], allowed_tools=sorted(TOOLS), mcp_servers=config["mcpServers"], strict_mcp_config=True,
        permission_mode="dontAsk", setting_sources=[], settings=json.dumps(settings),
        output_format={"type": "json_schema", "schema": schema},
        resume=session_id if resume else None, session_id=None if resume else session_id,
        extra_args={"restricted": None, "disable-slash-commands": None, "no-chrome": None},
        stderr=diagnostics.append,
    )
    client = ClaudeSDKClient(options=options)
    try:
        async with asyncio.timeout(min(startup, remaining())):
            await client.connect()
            while True:
                status = await client.get_mcp_status()
                servers = status.get("mcpServers")
                if not isinstance(servers, list) or len(servers) != 1 or servers[0].get("name") != "sheets":
                    raise RuntimeError("SDK lacks sole private sheets MCP server")
                server = servers[0]
                if server.get("status") == "connected":
                    if {tool.get("name") for tool in server.get("tools", [])} != {"view_sheet", "crop"}:
                        raise RuntimeError("SDK sheets tool catalog mismatch")
                    break
                if server.get("status") not in {"pending", "connecting"}:
                    raise RuntimeError("SDK sheets MCP startup failed")
                await asyncio.sleep(0.05)
        await client.query(config["prompt"])
        quota = None
        async for message in client.receive_response():
            event = sdk_event(message)
            emit(event, {"sdk_message_type": type(message).__name__, "message": asdict(message)})
            actual_session = event.get("session_id")
            if actual_session:
                if actual_session != session_id:
                    raise RuntimeError("SDK session differs from requested conversation")
                provenance["session_id"] = actual_session
            if event.get("type") == "assistant" and event.get("message", {}).get("model"):
                provenance["resolved_model"] = event["message"]["model"]
            current = quota_event(event)
            if current:
                quota = current
                if event.get("subtype") == "api_retry":
                    return quota
            if event.get("type") == "result":
                if not event.get("is_error") and event.get("subtype") == "success":
                    if not provenance.get("session_id"):
                        raise RuntimeError("SDK success lacks its persisted conversation id")
                    return None
                if quota and event.get("subtype") in {"success", "error_during_execution"}:
                    return quota
                raise RuntimeError("SDK review failed (non-quota terminal result)")
        raise RuntimeError("SDK ended without terminal result")
    finally:
        try:
            await client.disconnect()
        finally:
            # SDK transcripts are resumable state, not an unredacted back door
            # around the retained-stream redactor.
            for path in session_dir.rglob("*"):
                if path.is_file() and path.suffix in {".json", ".jsonl", ".txt", ".log"}:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    sanitized = text.replace(key.api_key, "[REDACTED]").replace(
                        json.dumps(key.api_key, ensure_ascii=True)[1:-1], "[REDACTED]",
                    )
                    if sanitized != text:
                        path.write_text(sanitized, encoding="utf-8")


def omp_event(event):
    """Normalize exactly message_end, not duplicate turn_end/agent_end history."""
    if event.get("type") != "message_end":
        return None
    message = event.get("message", {})
    role = message.get("role")
    if role == "toolResult":
        return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": message.get("toolCallId"), "is_error": message.get("isError", False), "content": message.get("content", [])}]}}
    if role != "assistant":
        return None
    content = []
    for block in message.get("content", []):
        if block.get("type") == "toolCall":
            name = str(block.get("name", ""))
            if name in OMP_TOOLS:
                name = name.replace("mcp__sheets_", "mcp__sheets__", 1)
            else:
                # Never let an unregistered native name collide with the SDK's
                # allowed sheets/StructuredOutput evidence namespace.
                name = "omp_unrecognized__" + name
            content.append({"type": "tool_use", "id": block.get("id"), "name": name, "input": block.get("arguments")})
        else:
            content.append(block)
    usage = message.get("usage", {})
    return {"type": "assistant", "total_cost_usd": (usage.get("cost") or {}).get("total", 0),
            "is_error": message.get("stopReason") in {"error", "aborted"},
            "error": message.get("errorMessage") if message.get("stopReason") in {"error", "aborted"} else None,
            "message": {"model": message.get("model"), "content": content,
            "usage": {"input_tokens": usage.get("input", 0), "output_tokens": usage.get("output", 0), "cache_read_input_tokens": usage.get("cacheRead", 0), "cache_creation_input_tokens": usage.get("cacheWrite", 0)}}}


@asynccontextmanager
async def _broker(executable, register_secret, remaining, startup):
    """Use the supported vault boundary, never copy or relink refresh tokens."""
    url = os.environ.get("OMP_AUTH_BROKER_URL")
    token = os.environ.get("OMP_AUTH_BROKER_TOKEN")
    if url:
        if not token:
            raise RuntimeError("Configured OMP broker requires an explicit token")
        register_secret(token)
        yield {"OMP_AUTH_BROKER_URL": url, "OMP_AUTH_BROKER_TOKEN": token,
               "OMP_AUTH_BROKER_SNAPSHOT_TTL_MS": "0"}
        return
    env = dict(os.environ)
    env.pop("OMP_AUTH_BROKER_URL", None)
    env.pop("OMP_AUTH_BROKER_TOKEN", None)
    proc = None
    broker = None
    drain = None
    try:
        async with asyncio.timeout(min(startup, remaining())):
            # OMP's first token creation is not exclusive. Coordinate our
            # parallel workers before starting brokers against the same vault.
            lock_dir = Path.home() / ".local/state/harmonic-analyzer"
            _directory(lock_dir)
            lock = FileLock(str(lock_dir / "omp-broker-init.lock"), mode=0o600)
            while True:
                try:
                    lock.acquire(timeout=0)
                    break
                except LockTimeout:
                    await asyncio.sleep(min(0.05, remaining()))
            try:
                proc = await asyncio.create_subprocess_exec(
                    executable, "auth-broker", "token", "--json", env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                output, _ = await proc.communicate()
            finally:
                if proc is not None and proc.returncode is None:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    await proc.communicate()
                lock.release()
            if proc.returncode:
                raise RuntimeError("OMP broker credential initialization failed")
            try:
                token = json.loads(output)["token"]
            except (ValueError, KeyError, TypeError):
                raise RuntimeError("OMP broker token response is invalid") from None
            if not isinstance(token, str) or not token:
                raise RuntimeError("OMP broker returned no token")
            register_secret(token)
            broker = await asyncio.create_subprocess_exec(
                executable, "auth-broker", "serve", "--bind=127.0.0.1:0",
                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            while True:
                line = await broker.stdout.readline()
                if not line:
                    raise RuntimeError("OMP broker exited before becoming ready")
                match = re.search(rb"http://127\\.0\\.0\\.1:(\\d+)", line)
                if match and int(match[1]) > 0:
                    url = match[0].decode("ascii")
                    break
        async def discard():
            while await broker.stdout.read(65536):
                pass
        drain = asyncio.create_task(discard())
        _telemetry.info("machinist_review.omp_broker", mode="private_loopback", outcome="ready")
        yield {"OMP_AUTH_BROKER_URL": url, "OMP_AUTH_BROKER_TOKEN": token,
               "OMP_AUTH_BROKER_SNAPSHOT_TTL_MS": "0"}
    finally:
        for child in (proc, broker):
            if child is not None:
                if child.returncode is None:
                    try:
                        child.kill()
                    except ProcessLookupError:
                        pass
        if proc is not None:
            await proc.communicate()
        if broker is not None:
            if drain is not None:
                await drain
            else:
                while await broker.stdout.read(65536):
                    pass
            await broker.wait()


async def _omp(*, register_secret, remaining, startup, **kwargs):
    executable = shutil.which("omp")
    if not executable:
        raise RuntimeError("OMP fallback executable not found")
    startup_deadline = time.monotonic() + min(startup, remaining())
    async with _broker(executable, register_secret, remaining, startup) as broker_env:
        startup_remaining = min(startup_deadline - time.monotonic(), remaining())
        if startup_remaining <= 0:
            raise TimeoutError
        await _omp_session(executable=executable, broker_env=broker_env,
                           remaining=remaining, startup=startup_remaining, **kwargs)


async def _omp_session(*, executable, broker_env, config, schema, model, effort, cwd, remaining, startup, emit, diagnostics, provenance, resume):
    # Configuration/cache live outside retained attempts; credentials stay only
    # in the original vault behind the broker. No privileged symlinks required.
    with tempfile.TemporaryDirectory(prefix="machrev-omp-private-") as private:
        home = Path(private)
        agent = home / "agent"
        agent.mkdir(mode=0o700)
        (agent / "mcp.json").write_text(json.dumps({"mcpServers": config["mcpServers"]}))
        overlay = home / "config.yml"
        overlay.write_text("mcp:\n  startupTimeoutMs: 0\n  enableProjectConfig: false\nmemory:\n  backend: 'off'\nautolearn:\n  enabled: false\n  autoContinue: false\n")
        sessions = Path(provenance.get("session_dir") or tempfile.mkdtemp(prefix="machrev-omp-sessions-"))
        provenance["session_dir"] = str(sessions)
        env = environment()
        for name in tuple(env):
            if name.startswith(("PI_", "OMP_", "XDG_")):
                env.pop(name)
        env.update(HOME=str(home), USERPROFILE=str(home), PI_CODING_AGENT_DIR=str(agent),
                   XDG_CONFIG_HOME=str(home / "config"), XDG_DATA_HOME=str(home / "data"),
                   XDG_STATE_HOME=str(home / "state"), XDG_CACHE_HOME=str(home / "cache"),
                   OMP_MCP_REQUIRE_READY="1", OMP_MCP_TIMEOUT_MS=str(max(1, int(min(startup, remaining()) * 1000))), OMP_MCP_STARTUP_TIMEOUT_MS="0")
        env.update(broker_env)
        command = [executable, "--mode", "rpc", "--no-ui", "--cwd", cwd,
                   "--config", str(overlay), "--no-tools", "--no-extensions", "--no-skills", "--no-rules",
                   "--no-lsp", "--no-pty", "--no-prewalk", "--no-title", "--auto-approve",
                   "--system-prompt", "You are a blind drawing reviewer. Use only the supplied sheet tools. Return only the requested JSON verdict.",
                   "--model", model, "--thinking", effort, "--session-dir", str(sessions)]
        if resume:
            command += ["--resume", provenance["session_file"]]
        provenance["omp_command"] = command
        proc = await asyncio.create_subprocess_exec(*command, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, limit=256 * 1024 * 1024)
        async def errors():
            while chunk := await proc.stderr.read(65536):
                diagnostics.append(chunk.decode("utf-8", errors="replace"))
        task = asyncio.create_task(errors())
        async def send(value):
            proc.stdin.write((json.dumps(value) + "\n").encode())
            await proc.stdin.drain()
        async def receive():
            line = await proc.stdout.readline()
            if not line:
                raise RuntimeError("OMP exited before terminal response")
            event = json.loads(line)
            emit(omp_event(event), event)
            return event
        async def control(kind, **fields):
            identity = str(uuid.uuid4())
            await send({"id": identity, "type": kind, **fields})
            while True:
                event = await receive()
                if event.get("type") == "response" and event.get("id") == identity:
                    if not event.get("success"):
                        raise RuntimeError("OMP control request failed")
                    return event.get("data", {})
        try:
            async with asyncio.timeout(min(startup, remaining())):
                state = await control("get_state")
                tools = {tool["name"] for tool in state.get("dumpTools", [])}
                if tools != OMP_TOOLS:
                    raise RuntimeError("OMP sheets-only tool catalog mismatch")
                actual = state.get("sessionId")
                if not actual or resume and actual != provenance.get("session_id"):
                    raise RuntimeError("OMP continuation/session mismatch")
                if not isinstance(state.get("sessionFile"), str) or not state["sessionFile"]:
                    raise RuntimeError("OMP lacks its persisted session file")
                resolved = state.get("model") or {}
                provenance.update(session_id=actual, session_file=state.get("sessionFile"),
                                  resolved_model={name: resolved.get(name) for name in ("provider", "id")})
            await control("set_auto_compaction", enabled=False)
            prompt_id = str(uuid.uuid4())
            await send({"id": prompt_id, "type": "prompt", "message": config["prompt"] + "\nReturn JSON matching this schema:\n" + json.dumps(schema)})
            while True:
                event = await receive()
                if event.get("type") == "prompt_result" and event.get("id") == prompt_id:
                    if event.get("status") != "completed":
                        raise RuntimeError("OMP review did not complete")
                    break
            text = await control("get_last_assistant_text")
            emit({"type": "result", "subtype": "success", "is_error": False, "session_id": actual, "result": text.get("text", "")}, None)
        finally:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            # Reap only after draining both pipes; Process.wait can otherwise
            # deadlock behind a paused stdout transport after cancellation.
            partial = []
            while chunk := await proc.stdout.read(65536):
                partial.append(chunk)
            if partial:
                emit(None, {"type": "unconsumed_stdout", "text": b"".join(partial).decode("utf-8", errors="replace")})
            await task
            await proc.wait()


def run(*, command, prompt, timeout, cwd, startup, settings, provenance, on_first_response=None, provider_response=None):
    """Synchronous integration seam, retaining every routed subattempt."""
    started = time.monotonic()
    deadline = started + timeout
    provenance["operation_id"] = str(uuid.uuid4())
    provenance["routes"] = []
    common = {name: provenance.get(name) for name in ("operation_id", "package", "phase", "attempt")}
    pinned_omp = "--resume" in command and provenance.get("transport") == "omp"
    resume_flag = "--resume" if "--resume" in command else "--session-id"
    provenance["requested_session_id"] = command[command.index(resume_flag) + 1]
    if resume_flag != "--resume":
        provenance.update(transport="routing", session_id=None)
    try:
        pool = CredentialPool(load=not pinned_omp)
    except Exception:
        _telemetry.error("machinist_review.credentials", reason="invalid_configuration", configured_count=None, selected_id=None, **common)
        _telemetry.error("machinist_review.transport_failed", error_category="credential_configuration", timed_out=False, **common)
        raise
    native, events, diagnostics = [], [], []
    notified = False
    route_index = 0
    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError
        return value
    def scope_tool_ids(node):
        if isinstance(node, list):
            for child in node:
                scope_tool_ids(child)
        elif isinstance(node, dict):
            if node.get("type") == "tool_use" and node.get("id"):
                node["id"] = f"route-{route_index}:{node['id']}"
            if node.get("type") == "tool_result" and node.get("tool_use_id"):
                node["tool_use_id"] = f"route-{route_index}:{node['tool_use_id']}"
            for child in node.values():
                if isinstance(child, (dict, list)):
                    scope_tool_ids(child)
    def emit(event, raw):
        nonlocal notified
        if raw is not None:
            native.append(pool.redact(json.dumps({"route_index": route_index, "native_event": raw}, default=str)))
        if event is not None:
            safe = json.loads(pool.redact(json.dumps(event)))
            scope_tool_ids(safe)
            safe["route_index"] = route_index
            events.append(safe)
            if not notified and on_first_response is not None and provider_response(safe):
                notified = True
                on_first_response()
    def finish_usage():
        rows = [event for event in events if event.get("route_index") == route_index]
        if not rows:
            return
        results = [event for event in rows if event.get("type") == "result"]
        if results and provenance.get("transport") != "omp":
            return
        usage = {}
        turns = 0
        cost = 0
        for event in rows:
            if event.get("type") == "assistant":
                turns += 1
                cost += event.get("total_cost_usd", 0) or 0
                for name, count in (event["message"].get("usage") or {}).items():
                    usage[name] = usage.get(name, 0) + count
        if results:
            results[-1].update(usage=usage, num_turns=turns, total_cost_usd=cost)
        else:
            emit({"type": "result", "is_error": True, "usage": usage,
                  "num_turns": turns, "total_cost_usd": cost}, None)

    @asynccontextmanager
    async def operation(name, **attributes):
        # Sanitize before span.__exit__: automatic exception logging must never
        # see a raw provider exception containing credentials.
        with _telemetry.span(name, **common, **attributes):
            try:
                yield
            except Exception as exc:
                if isinstance(exc, TimeoutError):
                    raise
                raise RuntimeError(pool.redact(f"{type(exc).__name__}: {exc}")) from None
    config = json.loads((Path(cwd) / "mcp.json").read_text())
    config["prompt"] = prompt
    schema = json.loads((Path(cwd) / "schema.json").read_text())
    resume = "--resume" in command
    session_id = command[command.index("--resume" if resume else "--session-id") + 1]
    provenance["requested_session_id"] = session_id
    model = command[command.index("--model") + 1]
    effort = command[command.index("--effort") + 1]
    prior_transport = provenance.get("transport") if resume else None
    async def execute():
        nonlocal session_id, route_index
        attempted = []
        while prior_transport != "omp":
            credential = pool.claim(attempted, required_id=provenance.get("credential_id") if resume else None,
                                    required_fingerprint=provenance.get("credential_fingerprint") if resume else None,
                                    timeout=remaining())
            remaining()
            _telemetry.info("machinist_review.credentials", configured_count=len(pool.credentials), selected_id=credential.id if credential else None, reason="selected" if credential else "no_eligible_keys", **common)
            if credential is None:
                break
            attempted.append(credential.id)
            route_index += 1
            provenance.update(transport="claude_agent_sdk", credential_id=credential.id, credential_fingerprint=credential.fingerprint,
                              session_id=session_id if resume else None)
            route = {"transport": "claude_agent_sdk", "credential_id": credential.id, "outcome": "started",
                     "session_id": session_id, "route_index": route_index, "event_start": len(events)}
            provenance.setdefault("routes", []).append(route)
            _telemetry.info("machinist_review.sdk_attempt", model=model, effort=effort, credential_id=credential.id, route_index=route_index, **common)
            async with operation("machinist_review.sdk", credential_id=credential.id, model=model, effort=effort):
                quota = await _sdk(key=credential, config=config, schema=schema, model=model, effort=effort, session_id=session_id, resume=resume, cwd=cwd, remaining=remaining, startup=startup, settings=settings, emit=emit, diagnostics=diagnostics, provenance=provenance)
            finish_usage()
            route["event_end"] = len(events)
            if quota is None:
                route["outcome"] = "succeeded"
                return
            route.update(outcome="quota", reason=quota["reason"])
            pool.unavailable(credential, quota, timeout=remaining())
            _telemetry.warn("machinist_review.credential_unavailable", credential_id=credential.id,
                            reason=quota["reason"], status=quota["status"], retry_at=quota["retryAt"], **common)
            if resume:
                raise RuntimeError("SDK continuation credential exhausted; refusing transport switch")
            # Session history may contain the API error: start a new session for
            # the next route, and scope tool IDs to its own routed attempt.
            session_id = str(uuid.uuid4())
        if resume and prior_transport != "omp":
            raise RuntimeError("SDK continuation cannot switch transport")
        provenance.update(transport="omp", credential_id=None, credential_fingerprint=None,
                          session_id=provenance.get("session_id") if resume else None)
        route_index += 1
        route = {"transport": "omp", "outcome": "started", "route_index": route_index, "event_start": len(events)}
        provenance["routes"].append(route)
        _telemetry.info("machinist_review.omp_attempt" if pinned_omp else "machinist_review.fallback",
                        source_transport="omp" if pinned_omp else "claude_agent_sdk", destination_transport="omp",
                        reason="continuation" if pinned_omp else "no_configured_keys" if not pool.credentials else "no_eligible_keys", **common)
        async with operation("machinist_review.omp", model=model, effort=effort):
            await _omp(config=config, schema=schema, model=model, effort=effort, cwd=cwd, remaining=remaining, startup=startup, emit=emit, diagnostics=diagnostics, provenance=provenance, resume=resume, register_secret=pool.secrets.add)
        finish_usage()
        route.update(outcome="succeeded", event_end=len(events), session_id=provenance.get("session_id"))
    try:
        async def bounded():
            async with asyncio.timeout(remaining()):
                await execute()
        asyncio.run(bounded())
        _telemetry.success("machinist_review.transport_completed", transport=provenance.get("transport"), duration_s=time.monotonic() - started, session_id=provenance.get("session_id"), **common)
        return subprocess.CompletedProcess(command, 0, "\n".join(json.dumps(event) for event in events), pool.redact("".join(diagnostics)))
    except Exception as exc:
        finish_usage()
        if provenance["routes"] and provenance["routes"][-1]["outcome"] == "started":
            provenance["routes"][-1].update(outcome="failed", event_end=len(events), error_category=type(exc).__name__)
        category = type(exc).__name__
        _telemetry.error("machinist_review.transport_failed", transport=provenance.get("transport"), error_category=category, timed_out=isinstance(exc, TimeoutError), **common)
        output = "\n".join(json.dumps(event) for event in events)
        errors = pool.redact("".join(diagnostics))
        if isinstance(exc, TimeoutError):
            raise subprocess.TimeoutExpired(command, timeout, output=output, stderr=errors) from None
        raise TransportError(pool.redact(f"{category}: {exc}"), stdout=output, stderr=errors) from None
    finally:
        (Path(cwd) / "native-events.jsonl").write_text("\n".join(native), encoding="utf-8")
