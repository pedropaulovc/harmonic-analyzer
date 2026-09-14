"""Farm executor: dispatch one cache-missing doit leaf to the SolidWorks build farm.

The constants, ``LeafRequest``/``LeafResult`` and ``workflow_id`` below mirror
``solidworks-pool/agent/contract.py`` field-for-field; ``FARM_PROTOCOL_VERSION``
mirrors ``agent/protocol.py`` and guards drift between the two repos (a mismatch
fails admission on the farm). This module must never import the pool package.

Configuration is the same ``~/.solidworks-pool/config.json`` that ``farm.py``
writes (``farm.py credentials issue``); ``SOLIDWORKS_POOL_CONFIG`` overrides the
path. Certificate and token paths in the file are relative to the config
directory. The farm's external frontend requires both the mTLS client
certificate and the bearer token (``Authorization: Bearer <jwt>``).
"""

from __future__ import annotations

import asyncio
import getpass
import json
import os
import socket
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import _telemetry

FARM_PROTOCOL_VERSION = 2

TASK_QUEUE_CONTROL = "solidworks-control"  # BuildLeaf workflow tasks
TASK_QUEUE_COM = "solidworks-com"  # build_leaf activity tasks
WORKFLOW_BUILD_LEAF = "BuildLeaf"
ACTIVITY_BUILD_LEAF = "build_leaf"
NAMESPACE = "solidworks"

CONFIG_ENV = "SOLIDWORKS_POOL_CONFIG"
DEFAULT_CONFIG_PATH = Path.home() / ".solidworks-pool" / "config.json"
EXECUTION_TIMEOUT = timedelta(hours=8)


@dataclass(frozen=True)
class LeafRequest:
    farm_protocol_version: int  # must equal FARM_PROTOCOL_VERSION
    source_identity_sha256: str  # published package id
    commit: str
    task: str  # exact doit task name, e.g. "part:fulcrum_keeper"
    cache_key: str | None  # 64-hex expected buildcache key; None only for check:*
    traceparent: str | None
    submitter: str  # f"{user}@{host}", UI summary only


@dataclass(frozen=True)
class LeafResult:
    state: str  # "succeeded" | "failed"
    exit_code: int | None
    worker_id: str  # f"{computername}@{instance_id}"
    attempt: int
    cache_present: bool
    log_blob: str | None  # "<results-container>/<blob-name>"
    failure_category: str | None
    failure_message: str | None  # <=1000 chars, CR/LF stripped


def workflow_id(task: str, cache_key: str | None, source_identity: str) -> str:
    return f"leaf:{task}:{cache_key or source_identity[:16]}"


def enabled() -> bool:
    return os.environ.get("HARMONIC_EXECUTOR", "local") == "farm"


def config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override)
    return DEFAULT_CONFIG_PATH


_CONFIG_KEYS = (
    "temporal_address",
    "namespace",
    "ca_cert",
    "client_cert",
    "client_key",
    "token",
)
_CONFIG_FILE_KEYS = ("ca_cert", "client_cert", "client_key", "token")


def load_config(path: Path | None = None) -> dict:
    """The submitter's farm config with certificate and token paths resolved.

    Every problem is a ``RuntimeError("farm config <path>: <problem>")`` naming
    the path and offending key only; certificate contents are never read here
    and the token is read only to reject a blank file.
    """
    path = path or config_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise RuntimeError(
            f"farm config {path}: not found; run `farm.py credentials issue` first"
        ) from None
    except OSError as exc:
        raise RuntimeError(f"farm config {path}: {exc.strerror}") from None
    try:
        config = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"farm config {path}: invalid JSON ({exc.msg})") from None
    if not isinstance(config, dict):
        raise RuntimeError(f"farm config {path}: expected a JSON object")
    for key in _CONFIG_KEYS:
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"farm config {path}: {key} must be a non-empty string")
    for key in _CONFIG_FILE_KEYS:
        file = (path.parent / config[key]).resolve()
        if not file.is_file() or not os.access(file, os.R_OK):
            raise RuntimeError(f"farm config {path}: {key} file is not readable")
        config[key] = str(file)
    if not Path(config["token"]).read_text(encoding="ascii").strip():
        raise RuntimeError(f"farm config {path}: token file is empty")
    return config


def submitter() -> str:
    return f"{getpass.getuser()}@{socket.gethostname()}"


def run_leaf(task: str, cache_key: str | None) -> LeafResult:
    """Run ``task`` on the farm and return its result once the workflow closes.

    Shares the workflow with any other submitter of the same leaf
    (``USE_EXISTING``), so Ctrl-C here never cancels it -- the interrupt just
    propagates. A workflow cancelled through ``farm.py cancel`` comes back as a
    failed result with ``failure_category="cancelled"``; every other failure
    (connection, protocol) propagates as-is: it is a local fault, not a build
    outcome.
    """
    with _telemetry.span(
        f"farm.run {task}", label=task, service=_telemetry.BUILD_INFRA_SERVICE
    ) as sp:
        request = LeafRequest(
            farm_protocol_version=FARM_PROTOCOL_VERSION,
            source_identity_sha256=os.environ["HARMONIC_FARM_SOURCE_IDENTITY"],
            commit=os.environ["HARMONIC_FARM_COMMIT"],
            task=task,
            cache_key=cache_key,
            traceparent=_telemetry.inject_env().get("TRACEPARENT"),
            submitter=submitter(),
        )
        wf_id = workflow_id(task, cache_key, request.source_identity_sha256)
        sp.set_attribute("workflow_id", wf_id)
        result = asyncio.run(_dispatch(request, wf_id))
        sp.set_attribute("worker", result.worker_id)
        sp.set_attribute("attempt", result.attempt)
        sp.set_attribute("state", result.state)
        return result


async def _dispatch(request: LeafRequest, wf_id: str) -> LeafResult:
    # temporalio loads a Rust bridge; import it only when a leaf is dispatched so
    # local builds and the offline check:* workers never pay for it.
    from temporalio.client import Client, WorkflowFailureError
    from temporalio.common import WorkflowIDConflictPolicy
    from temporalio.exceptions import CancelledError
    from temporalio.service import TLSConfig

    config = load_config()
    address = config["temporal_address"]
    client = await Client.connect(
        address,
        namespace=config["namespace"],
        api_key=Path(config["token"]).read_text(encoding="ascii").strip(),
        tls=TLSConfig(
            server_root_ca_cert=Path(config["ca_cert"]).read_bytes(),
            domain=address.rsplit(":", 1)[0],
            client_cert=Path(config["client_cert"]).read_bytes(),
            client_private_key=Path(config["client_key"]).read_bytes(),
        ),
        identity=request.submitter,
    )
    handle = await client.start_workflow(
        WORKFLOW_BUILD_LEAF,
        request,
        id=wf_id,
        task_queue=TASK_QUEUE_CONTROL,
        result_type=LeafResult,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        execution_timeout=EXECUTION_TIMEOUT,
    )
    try:
        return await handle.result()
    except WorkflowFailureError as exc:
        if not isinstance(exc.cause, CancelledError):
            raise
        return LeafResult(
            state="failed",
            exit_code=None,
            worker_id="",
            attempt=0,
            cache_present=False,
            log_blob=None,
            failure_category="cancelled",
            failure_message="cancelled via farm.py cancel",
        )
