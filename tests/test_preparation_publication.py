"""Lazy producer preparation publication, with guarded pool/Temporal boundaries."""

import asyncio
import importlib.util
import json
import queue
import subprocess
import sys
import threading
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from doit.dependency import CHECKERS, Dependency, JsonDB

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

import _farm  # noqa: E402
import build  # noqa: E402

COMMIT = "c" * 40
AGENT = "a" * 64
BUILD = "preparation-publication-build"
TASK = "part:pen_rod"
KEY = "d" * 64
WAIT_S = 5


@pytest.fixture
def boundary(tmp_path, monkeypatch):
    """Exercise real run_leaf/_dispatch without credentials, cloud, or native work."""
    workspace = tmp_path / "workspace"
    pool = tmp_path / "pool"
    monkeypatch.setattr(_farm, "REPO_ROOT", workspace)
    monkeypatch.setattr(build, "_pool_home", lambda: pool)
    requests_directory = tmp_path / "requests"
    requests_directory.mkdir()
    monkeypatch.setenv("HARMONIC_FARM_REQUESTS", str(requests_directory))
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", json.dumps({
        "capability": "preparation-publish-v1", "configured": True,
        "account": "testpreparation", "configuration_error": False,
        "operation_timeout_s": 900.0, "process_margin_s": 10.0,
    }))
    monkeypatch.setenv("HARMONIC_FARM_COMMIT", COMMIT)
    monkeypatch.setenv("HARMONIC_FARM_AGENT_IDENTITY", AGENT)
    monkeypatch.setenv("HARMONIC_FARM_BUILD_ID", BUILD)
    monkeypatch.setenv("HARMONIC_FARM_DISPLAY_NAME", "Preparation publication regression")
    monkeypatch.setenv("HARMONIC_FARM_ADMITTED_LEAVES", json.dumps([TASK, "check:math"]))
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    for name in (
        "HARMONIC_CACHE_REFRESH", "HARMONIC_FARM_LEAF_TIMEOUT_S",
        "HARMONIC_FARM_RUN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(_farm, "submitter", lambda: "offline@test")
    monkeypatch.setattr(_farm._telemetry, "info", lambda *_a, **_k: None)
    monkeypatch.setattr(_farm._telemetry, "event", lambda *_a, **_k: None)
    monkeypatch.setattr(_farm._telemetry, "warn", lambda *_a, **_k: None)
    state = SimpleNamespace(
        workspace=workspace.resolve(), pool=pool.resolve(), events=[], publication_calls=[],
        requests=[], publication_hook=None, publication_result=None, publication_error=None,
        coordinator_hook=None, coordinator_error=None, interrupts=[],
        heartbeat=threading.Event(),
        close_reasons=[],
        requests_directory=requests_directory,
        publication_options=[], spans={},
        result=_farm.LeafResult("succeeded", 0, "fake-worker", 1, True, None, None, None),
    )
    state.publication_clock = time.perf_counter

    def selected_publication_clock(selected_pool):
        assert selected_pool == build._pool_home().resolve()
        return state.publication_clock

    monkeypatch.setattr(build, "_pool_publication_clock", selected_publication_clock)

    def span(name, **_options):
        attributes = {}
        state.spans.setdefault(name, []).append(attributes)
        return nullcontext(SimpleNamespace(
            set_attribute=lambda key, value: attributes.__setitem__(key, value)
        ))

    monkeypatch.setattr(_farm._telemetry, "span", span)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("preparation test crossed an unmocked host/service boundary")

    monkeypatch.setattr(_farm.subprocess, "run", forbidden)
    monkeypatch.setattr(_farm, "load_config", forbidden)
    monkeypatch.setattr(_farm._thread, "interrupt_main", lambda: state.interrupts.append(True))

    def pool_preparation(
        selected_pool, workspace, *, commit, operation_deadline, process_margin_s, clock,
    ):
        assert clock is state.publication_clock
        state.events.append("publish")
        state.publication_calls.append((selected_pool, workspace))
        state.publication_options.append({
            "commit": commit, "operation_deadline": operation_deadline,
            "process_margin_s": process_margin_s, "clock": clock,
        })
        if state.publication_hook is not None:
            state.publication_hook()
        if state.publication_error is not None:
            raise state.publication_error
        if state.publication_result is not None:
            return state.publication_result
        return {
            "configured": True, "commit": commit,
            "agent_identity_sha256": _farm.os.environ["HARMONIC_FARM_AGENT_IDENTITY"],
        }

    monkeypatch.setattr(build, "_pool_preparation", pool_preparation)
    monkeypatch.setattr(build, "_pool_farm", forbidden)

    class Client:
        def get_workflow_handle(self, _workflow_id, **_options):
            return self

        async def result(self, *, follow_runs):
            assert follow_runs is False
            state.events.append("result")
            return state.result

    async def connect(_identity):
        state.events.append("connect")
        return Client()

    async def fifo(_client):
        state.events.append("coordinator")
        if state.coordinator_hook is not None:
            state.coordinator_hook()
        if state.coordinator_error is not None:
            raise state.coordinator_error
        return object()

    async def update(_handle, name, arg, _result_type, _operation):
        state.events.append(name)
        if name == "submit_leaf":
            request = arg.request
            state.requests.append(request)
            workflow = _farm.workflow_id(
                request.build_id, request.task, request.cache_key, request.commit,
                _farm.clamp_leaf_timeout_s(request.leaf_timeout_s),
            )
            key = _farm.LeafKey(request.build_id, workflow)
            return _farm.LeafStatus(
                key, "bound", _farm.LeafBinding(key.build_id, workflow, "exact-run"), []
            )
        assert name in {"register_build", "heartbeat_build", "close_build"}
        if name == "heartbeat_build":
            state.heartbeat.set()
        if name == "close_build":
            state.close_reasons.append(arg.reason)
        return _farm.BuildStatus(
            arg.build_id, 1, "closed" if name == "close_build" else "open", "active",
            (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
            0, 0, 1, 0,
        )

    monkeypatch.setattr(_farm, "_connect_client", connect)
    monkeypatch.setattr(_farm, "_fifo_handle", fifo)
    monkeypatch.setattr(_farm, "_rpc_update", update)
    monkeypatch.setattr(_farm, "_record_build", lambda _build: state.events.append("record_build"))
    monkeypatch.setattr(
        _farm, "_record_request", lambda *_args: state.events.append("record_request")
    )
    return state


def _load_dodo():
    """Reuse the recipe-test isolation pattern for its process-wide doit patches."""
    save_success, json_dump = Dependency.save_success, JsonDB.dump
    absent = object()
    checker = CHECKERS.get("content", absent)
    try:
        spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        Dependency.save_success, JsonDB.dump = save_success, json_dump
        if checker is absent:
            CHECKERS.pop("content", None)
        else:
            CHECKERS["content"] = checker


@pytest.fixture
def cached_part(boundary, monkeypatch):
    dodo = _load_dodo()
    monkeypatch.setattr(dodo, "_part_cache_outputs", lambda _stem: [])
    monkeypatch.setattr(dodo, "_part_file_deps", lambda *_args: [])
    monkeypatch.setattr(dodo, "_cache_key", lambda *_args: KEY)
    monkeypatch.setattr(dodo._cache, "key_input_paths", lambda *_args: [])
    monkeypatch.setattr(dodo._farm, "checkout_drift", lambda **_kwargs: None)
    monkeypatch.setattr(dodo, "_stamp_part_execution", lambda *_args: None)
    monkeypatch.setattr(dodo._cache, "restore", lambda *_args: True)

    def no_native(*_args, **_kwargs):
        raise AssertionError("preparation test attempted native execution or cache publication")

    monkeypatch.setattr(dodo, "_com_seat", no_native)
    monkeypatch.setattr(dodo, "_exec_com", no_native)
    monkeypatch.setattr(dodo._cache, "store", no_native)
    return dodo


@pytest.mark.parametrize("readiness", [
    "null",
    json.dumps({"capability": None, "probe_error": "optional preparation import failed"}),
    json.dumps({
        "capability": "preparation-publish-v1", "configured": True,
        "account": "testpreparation", "configuration_error": False,
    }),
])
def test_cache_only_build_registers_but_never_publishes_or_dispatches(
    boundary, cached_part, monkeypatch, readiness
):
    monkeypatch.setattr(cached_part, "_probe_cache", lambda *_args: "hit")
    # Neither optional probe failures nor missing publication budgets affect hits.
    boundary.publication_error = build.FarmPreflightError("publisher must not run")
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", readiness)
    with _farm.producer_build("Cache-only publication regression") as ownership:
        cached_part._cached_part_action("pen_rod", Path("unused.py"))
        ownership.finish(True)
    assert boundary.publication_calls == []
    assert boundary.requests == []
    assert boundary.events == [
        "record_build", "connect", "coordinator", "register_build", "close_build"
    ]
    assert not (boundary.requests_directory / "preparation").exists()
    assert boundary.interrupts == []


def test_first_cache_miss_publishes_admitted_source_after_parent_registration(
    boundary, cached_part, monkeypatch
):
    monkeypatch.setattr(cached_part, "_probe_cache", lambda *_args: "miss")
    with _farm.producer_build("First publication regression") as ownership:
        cached_part._cached_part_action("pen_rod", Path("unused.py"))
        ownership.finish(True)
    assert boundary.publication_calls == [(boundary.pool, boundary.workspace)]
    options = boundary.publication_options[0]
    assert options["commit"] == COMMIT
    assert options["process_margin_s"] == 10.0
    assert options["operation_deadline"] == (
        boundary.spans["farm.preparation"][0]["operation_deadline_counter"]
    )
    assert options["clock"] is boundary.publication_clock
    timing = boundary.spans["farm.preparation"][0]
    assert timing["operation_timeout_s"] == 900.0
    assert timing["process_margin_s"] == 10.0
    assert timing["lock_wait_ms"] >= 0
    assert timing["publication_ms"] >= 0
    assert timing["publication_state"] == "succeeded"
    assert boundary.events.index("register_build") < boundary.events.index("publish")
    assert boundary.events.index("publish") < boundary.events.index("record_request")
    assert boundary.events.index("record_request") < boundary.events.index("submit_leaf")
    assert boundary.events[-1] == "close_build"
    assert boundary.requests[0].commit == COMMIT
    assert boundary.interrupts == []


def test_slow_preparation_keeps_the_existing_parent_lease_renewer_running(
    boundary, monkeypatch
):
    monkeypatch.setattr(_farm, "FIFO_HEARTBEAT_INTERVAL_S", 0.01)

    def publish():
        assert boundary.heartbeat.wait(WAIT_S), "publisher blocked parent lease renewal"

    boundary.publication_hook = publish
    with _farm.producer_build("Lease renewal publication regression") as ownership:
        assert _farm.run_leaf(TASK, KEY) is boundary.result
        ownership.finish(True)
    assert boundary.events.index("publish") < boundary.events.index("heartbeat_build")
    assert boundary.events.index("heartbeat_build") < boundary.events.index("submit_leaf")
    assert boundary.interrupts == []


def test_publication_failure_closes_parent_as_failed_without_a_reservation(
    boundary, cached_part, monkeypatch
):
    monkeypatch.setattr(cached_part, "_probe_cache", lambda *_args: "miss")
    boundary.publication_error = build.FarmPreflightError("preparation descriptor is corrupt")
    with pytest.raises(RuntimeError, match="preparation descriptor is corrupt"):
        with _farm.producer_build("Failed publication regression"):
            cached_part._cached_part_action("pen_rod", Path("unused.py"))
    assert boundary.events[-1] == "close_build"
    assert boundary.close_reasons == ["failed"]
    assert boundary.requests == []
    assert boundary.interrupts == []


def test_repeated_native_and_check_leaves_share_one_publication(boundary):
    assert _farm.run_leaf(TASK, KEY) is boundary.result
    assert _farm.run_leaf("check:math", None) is boundary.result
    assert _farm.run_leaf(TASK, KEY) is boundary.result
    assert len(boundary.publication_calls) == 1
    assert [request.task for request in boundary.requests] == [TASK, "check:math", TASK]


def test_concurrent_first_leaves_wait_for_one_publication_before_any_dispatch(boundary):
    publishing, release, both_coordinated = threading.Event(), threading.Event(), threading.Event()
    count_lock = threading.Lock()
    coordinated = 0

    def coordinator():
        nonlocal coordinated
        with count_lock:
            coordinated += 1
            if coordinated == 2:
                both_coordinated.set()

    def publish():
        publishing.set()
        assert release.wait(WAIT_S), "test did not release preparation publisher"

    boundary.publication_hook = publish
    boundary.coordinator_hook = coordinator
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(_farm.run_leaf, TASK, KEY) for _ in range(2)]
        try:
            assert publishing.wait(WAIT_S)
            assert both_coordinated.wait(WAIT_S)
            assert len(boundary.publication_calls) == 1
            assert boundary.requests == []
        finally:
            release.set()
        assert [future.result(WAIT_S) for future in futures] == [boundary.result] * 2
    assert len(boundary.publication_calls) == 1
    assert len(boundary.requests) == 2


@pytest.mark.parametrize("identity", ["source", "agent", "build", "workspace", "pool"])
def test_identity_transition_publishes_once_for_each_exact_key(
    boundary, monkeypatch, identity
):
    _farm.run_leaf(TASK, KEY)
    with monkeypatch.context() as changed:
        if identity == "source":
            changed.setenv("HARMONIC_FARM_COMMIT", "e" * 40)
        elif identity == "agent":
            changed.setenv("HARMONIC_FARM_AGENT_IDENTITY", "f" * 64)
        elif identity == "build":
            changed.setenv("HARMONIC_FARM_BUILD_ID", "another-build")
        elif identity == "workspace":
            changed.setattr(_farm, "REPO_ROOT", boundary.workspace.parent / "another-workspace")
        else:
            changed.setattr(build, "_pool_home", lambda: boundary.pool.parent / "another-pool")
        _farm.run_leaf(TASK, KEY)
        _farm.run_leaf(TASK, KEY)
    _farm.run_leaf(TASK, KEY)
    assert len(boundary.publication_calls) == 2
    assert len(boundary.requests) == 4


def test_workspace_alias_uses_canonical_root_and_same_singleflight_key(boundary, monkeypatch):
    _farm.run_leaf(TASK, KEY)
    monkeypatch.setattr(_farm, "REPO_ROOT", boundary.workspace / "unused" / "..")
    _farm.run_leaf(TASK, KEY)
    assert boundary.publication_calls == [(boundary.pool, boundary.workspace)]


@pytest.mark.parametrize("failure", [
    build.FarmPreflightError("publisher authorization denied"),
    build.FarmPreflightError("preparation descriptor is corrupt"),
])
def test_publication_failure_is_shared_and_prevents_every_leaf_dispatch(boundary, failure):
    def refuse():
        raise failure

    boundary.publication_hook = refuse
    errors = []
    for _ in range(2):
        with pytest.raises(RuntimeError, match=str(failure)) as caught:
            _farm.run_leaf(TASK, KEY)
        errors.append(caught.value)
    assert str(errors[0]) == str(errors[1])
    assert errors[0] is not errors[1]
    assert len(boundary.publication_calls) == 1
    assert boundary.requests == []
    assert "record_request" not in boundary.events


def test_concurrent_publication_failure_is_not_retried_or_demoted_to_a_miss(boundary):
    publishing, release = threading.Event(), threading.Event()
    failure = build.FarmPreflightError("publisher authorization denied")

    def refuse():
        publishing.set()
        assert release.wait(WAIT_S)
        raise failure

    boundary.publication_hook = refuse
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(_farm.run_leaf, TASK, KEY) for _ in range(2)]
        try:
            assert publishing.wait(WAIT_S)
        finally:
            release.set()
        errors = []
        for future in futures:
            with pytest.raises(RuntimeError, match=str(failure)) as caught:
                future.result(WAIT_S)
            errors.append(caught.value)
        assert str(errors[0]) == str(errors[1])
        assert errors[0] is not errors[1]
    assert len(boundary.publication_calls) == 1
    assert boundary.requests == []


@pytest.mark.parametrize("published", [
    "not a result object", [], {},
    {"configured": False, "commit": COMMIT, "agent_identity_sha256": AGENT},
    {"configured": True, "commit": "e" * 40, "agent_identity_sha256": AGENT},
    {"configured": True, "commit": COMMIT, "agent_identity_sha256": "f" * 64},
])
def test_invalid_or_foreign_publisher_success_fails_closed(boundary, published):
    boundary.publication_result = published
    with pytest.raises(RuntimeError, match="preparation publication"):
        _farm.run_leaf(TASK, KEY)
    assert boundary.requests == []
    assert "record_request" not in boundary.events


@pytest.mark.parametrize("diagnostic", [
    "preparation publication failed [azure]",
    "preparation publication returned an invalid private receipt",
])
def test_private_bridge_failure_preserves_its_safe_diagnostic(boundary, diagnostic):
    boundary.publication_error = build.FarmPreflightError(diagnostic)
    with pytest.raises(RuntimeError) as caught:
        _farm.run_leaf(TASK, KEY)
    assert diagnostic in str(caught.value)
    assert len(boundary.publication_calls) == 1
    assert boundary.requests == []
    assert "record_request" not in boundary.events


@pytest.mark.parametrize(("variable", "value"), [
    ("HARMONIC_FARM_COMMIT", "c" * 12),
    ("HARMONIC_FARM_COMMIT", "C" * 40),
    ("HARMONIC_FARM_AGENT_IDENTITY", ""),
    ("HARMONIC_FARM_AGENT_IDENTITY", "a" * 12),
    ("HARMONIC_FARM_AGENT_IDENTITY", "A" * 64),
])
def test_publication_refuses_unadmitted_source_or_agent_identity(
    boundary, monkeypatch, variable, value
):
    monkeypatch.setenv(variable, value)
    with pytest.raises(RuntimeError, match=f"requires admitted {variable}"):
        _farm.run_leaf(TASK, KEY)
    assert boundary.publication_calls == []
    assert boundary.requests == []


def test_foreign_request_commit_cannot_prepare_a_different_admitted_source(boundary):
    request = _farm.LeafRequest(
        _farm.FARM_PROTOCOL_VERSION, "e" * 40, TASK, KEY, None, "offline@test", BUILD,
    )
    with pytest.raises(RuntimeError, match="does not match the admitted commit"):
        asyncio.run(_farm._dispatch(request, "foreign-request"))
    assert boundary.publication_calls == []
    assert boundary.requests == []


def test_invalid_coordinator_still_fails_before_preparation(boundary):
    boundary.coordinator_error = RuntimeError("coordinator protocol refused")
    with pytest.raises(RuntimeError, match="coordinator protocol refused"):
        _farm.run_leaf(TASK, KEY)
    assert boundary.publication_calls == []
    assert boundary.requests == []


def test_unadmitted_leaf_does_not_publish_or_connect(boundary, monkeypatch):
    monkeypatch.setenv("HARMONIC_FARM_ADMITTED_LEAVES", "[]")
    with pytest.raises(RuntimeError, match="lacks preflight admission"):
        _farm.run_leaf(TASK, KEY)
    assert boundary.events == []


def test_missing_parent_ownership_does_not_publish_or_connect(boundary, monkeypatch):
    monkeypatch.delenv("HARMONIC_FARM_BUILD_ID")
    with pytest.raises(_farm.BuildOwnershipError, match="parent build ownership"):
        _farm.run_leaf(TASK, KEY)
    assert boundary.events == []


@pytest.mark.parametrize("readiness", [
    None, "not JSON", "null", "{}",
    json.dumps({"capability": "older-publisher", "configured": True,
                "account": "testpreparation", "configuration_error": False}),
    json.dumps({"capability": "preparation-publish-v1", "configured": False,
                "account": None, "configuration_error": False}),
    json.dumps({"capability": "preparation-publish-v1", "configured": False,
                "account": None, "configuration_error": True}),
    json.dumps({"capability": "preparation-publish-v1", "configured": "true",
                "account": "testpreparation", "configuration_error": False}),
    json.dumps({"capability": "preparation-publish-v1", "configured": True,
                "account": None, "configuration_error": False}),
])
def test_unready_publisher_refuses_first_miss_before_any_connection(
    boundary, monkeypatch, readiness
):
    if readiness is None:
        monkeypatch.delenv("HARMONIC_FARM_PREPARATION_READINESS")
    else:
        monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", readiness)
    with pytest.raises(RuntimeError, match="PoolHome") as caught:
        _farm.run_leaf(TASK, KEY)
    assert str(boundary.pool) in str(caught.value)
    assert boundary.events == []
    assert not (boundary.requests_directory / "preparation").exists()


@pytest.mark.parametrize("problem", [
    "probe_error", "operation_timeout_s", "process_margin_s",
])
def test_optional_readiness_failure_refuses_first_real_miss_before_network(
    boundary, cached_part, monkeypatch, problem
):
    readiness = json.loads(_farm.os.environ["HARMONIC_FARM_PREPARATION_READINESS"])
    if problem == "probe_error":
        readiness["probe_error"] = "optional preparation import failed"
    else:
        readiness.pop(problem)
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", json.dumps(readiness))
    monkeypatch.setattr(cached_part, "_probe_cache", lambda *_args: "miss")
    with pytest.raises(RuntimeError, match="readiness"):
        cached_part._cached_part_action("pen_rod", Path("unused.py"))
    assert boundary.events == []
    assert boundary.publication_calls == []
    assert boundary.requests == []
    assert not (boundary.requests_directory / "preparation").exists()


@pytest.mark.parametrize("field", ["operation_timeout_s", "process_margin_s"])
@pytest.mark.parametrize("value", [
    None, True, False, 0, -1, float("nan"), float("inf"), float("-inf"),
    "900", [], {}, 10 ** 400,
])
def test_readiness_rejects_invalid_declared_publication_budgets(
    boundary, monkeypatch, field, value
):
    readiness = json.loads(_farm.os.environ["HARMONIC_FARM_PREPARATION_READINESS"])
    readiness[field] = value
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", json.dumps(readiness))
    with pytest.raises(RuntimeError, match=f"invalid publisher {field} readiness"):
        _farm.run_leaf(TASK, KEY)
    assert boundary.events == []
    assert not (boundary.requests_directory / "preparation").exists()


@pytest.mark.parametrize("operation_timeout_s, process_margin_s", [(23, 4), (23.5, 4.25)])
def test_readiness_returns_the_declared_budgets_as_floats(
    boundary, monkeypatch, operation_timeout_s, process_margin_s
):
    readiness = json.loads(_farm.os.environ["HARMONIC_FARM_PREPARATION_READINESS"])
    readiness.update(
        operation_timeout_s=operation_timeout_s, process_margin_s=process_margin_s,
    )
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", json.dumps(readiness))
    budgets = _farm._require_preparation_readiness()
    assert budgets == (operation_timeout_s, process_margin_s)
    assert all(type(value) is float for value in budgets)
    assert boundary.events == []


@pytest.mark.parametrize("initial", [None, ""])
def test_attended_build_cleans_only_its_owned_requests_directory(
    boundary, monkeypatch, tmp_path, initial
):
    temporary_directory = _farm.tempfile.TemporaryDirectory
    monkeypatch.setattr(
        _farm.tempfile, "TemporaryDirectory",
        lambda **kwargs: temporary_directory(dir=tmp_path, **kwargs),
    )
    if initial is None:
        monkeypatch.delenv("HARMONIC_FARM_REQUESTS")
    else:
        monkeypatch.setenv("HARMONIC_FARM_REQUESTS", initial)
    with _farm.producer_build("Attended preparation cleanup") as ownership:
        owned = Path(_farm.os.environ["HARMONIC_FARM_REQUESTS"])
        assert owned.is_dir()
        assert _farm.run_leaf(TASK, KEY) is boundary.result
        assert len(list((owned / "preparation").glob("*.json"))) == 1
        ownership.finish(True)
    assert _farm.os.environ.get("HARMONIC_FARM_REQUESTS") == initial
    assert not owned.exists()
    assert boundary.requests_directory.is_dir(), "cleanup removed a caller-owned directory"


def test_attended_registration_failure_retains_owned_requests_before_any_marker(
    boundary, monkeypatch, tmp_path
):
    temporary_directory = _farm.tempfile.TemporaryDirectory
    created = []

    def own_directory(**kwargs):
        temporary = temporary_directory(dir=tmp_path, **kwargs)
        created.append(Path(temporary.name))
        return temporary

    monkeypatch.setattr(_farm.tempfile, "TemporaryDirectory", own_directory)
    monkeypatch.delenv("HARMONIC_FARM_REQUESTS")
    boundary.coordinator_error = RuntimeError("coordinator unavailable")
    with pytest.raises(_farm.BuildOwnershipError, match="coordinator unavailable") as caught:
        with _farm.producer_build("Failed attended preparation cleanup"):
            pytest.fail("producer entered after registration failed")
    assert created and all(path.is_dir() for path in created)
    assert all(not (path / "preparation").exists() for path in created)
    assert any(str(created[0]) in note for note in caught.value.__notes__)
    assert "HARMONIC_FARM_REQUESTS" not in _farm.os.environ
    assert boundary.requests_directory.is_dir()


@pytest.fixture
def requests_cleanup_failure(boundary, monkeypatch):
    """Fail only a captured owned object's cleanup; always remove its real root."""
    monkeypatch.delenv("HARMONIC_FARM_REQUESTS")
    state = SimpleNamespace(
        owned=None, root=None, real_cleanup=None, calls=[], warnings=[], environment=None,
    )
    monkeypatch.setattr(
        _farm._telemetry, "warn",
        lambda message, **attributes: state.warnings.append((message, attributes)),
    )

    def arm(ownership):
        owned = ownership._owned_requests
        assert owned is not None
        state.owned = owned
        state.root = Path(owned.name)
        state.real_cleanup = owned.cleanup
        (state.root / "retained-receipt.json").write_text("{}", encoding="utf-8")

        def refuse_cleanup():
            state.calls.append(state.root)
            state.environment = (
                _farm.os.environ.get("HARMONIC_FARM_BUILD_ID"),
                _farm.os.environ.get("HARMONIC_FARM_REQUESTS"),
            )
            raise PermissionError("synthetic cleanup detail")

        monkeypatch.setattr(owned, "cleanup", refuse_cleanup)

    state.arm = arm
    try:
        yield state
    finally:
        if state.real_cleanup is not None:
            state.real_cleanup()


def _assert_requests_cleanup_report(
    ownership, state, *, primary=None, cleanup_attempted=True,
):
    assert ownership._owned_requests is state.owned
    assert state.root.is_dir()
    assert (state.root / "retained-receipt.json").is_file()
    assert _farm.os.environ["HARMONIC_FARM_BUILD_ID"] == BUILD
    assert "HARMONIC_FARM_REQUESTS" not in _farm.os.environ
    assert state.calls == ([state.root] if cleanup_attempted else [])
    if cleanup_attempted:
        assert state.environment == (BUILD, None), "cleanup preceded environment restoration"
    assert len(state.warnings) == 1
    message, attributes = state.warnings[0]
    assert str(state.root) in message
    assert attributes == {"build_id": ownership.build_id}
    assert "synthetic cleanup detail" not in message
    if cleanup_attempted:
        assert "PermissionError" in message
        assert "possible residue" in message
    else:
        assert "primary build exception or interrupt" in message
    if primary is not None:
        assert primary.__notes__ == [message]
        assert "synthetic cleanup detail" not in str(primary)


@pytest.mark.parametrize("primary_type", [RuntimeError, KeyboardInterrupt, asyncio.CancelledError])
def test_body_primary_retains_owned_requests_without_probe_or_cleanup(
    boundary, requests_cleanup_failure, monkeypatch, primary_type,
):
    ownership = _farm.producer_build("Body primary retention regression")
    primary = primary_type("original build failure")

    def forbidden_probe(*_args):
        raise AssertionError("primary-error teardown inspected a possibly active publisher")

    monkeypatch.setattr(_farm, "_require_quiescent_requests", forbidden_probe)
    with pytest.raises(primary_type) as caught:
        with ownership:
            requests_cleanup_failure.arm(ownership)
            assert not (requests_cleanup_failure.root / "preparation").exists()
            raise primary
    assert caught.value is primary
    assert boundary.close_reasons == [
        "cancelled" if isinstance(primary, KeyboardInterrupt) else "failed",
    ]
    _assert_requests_cleanup_report(
        ownership, requests_cleanup_failure, primary=primary, cleanup_attempted=False,
    )


def test_registration_primary_retains_owned_requests_without_cleanup(
    boundary, requests_cleanup_failure,
):
    ownership = _farm.producer_build("Registration primary cleanup regression")
    boundary.coordinator_error = RuntimeError("original registration failure")
    boundary.coordinator_hook = lambda: requests_cleanup_failure.arm(ownership)
    with pytest.raises(_farm.BuildOwnershipError, match="original registration failure") as caught:
        with ownership:
            pytest.fail("producer entered after registration failure")
    assert caught.value.__cause__ is boundary.coordinator_error
    _assert_requests_cleanup_report(
        ownership, requests_cleanup_failure, primary=caught.value, cleanup_attempted=False,
    )


def test_failed_finish_keeps_nonzero_outcome_and_reports_owned_requests_residue(
    boundary, requests_cleanup_failure,
):
    ownership = _farm.producer_build("Nonzero outcome cleanup regression")

    def finish_failed_build():
        with ownership:
            requests_cleanup_failure.arm(ownership)
            ownership.finish(False)
            return 7

    assert finish_failed_build() == 7
    assert boundary.close_reasons == ["failed"]
    _assert_requests_cleanup_report(ownership, requests_cleanup_failure)


def test_successful_finish_refuses_unconfirmed_owned_requests_cleanup(
    boundary, requests_cleanup_failure,
):
    ownership = _farm.producer_build("Successful outcome cleanup regression")
    with pytest.raises(_farm.BuildOwnershipError, match="possible residue") as caught:
        with ownership:
            requests_cleanup_failure.arm(ownership)
            ownership.finish(True)
    assert caught.value.__cause__ is None
    assert "synthetic cleanup detail" not in str(caught.value)
    assert boundary.close_reasons == ["finished"]
    _assert_requests_cleanup_report(ownership, requests_cleanup_failure)


def test_unconfirmed_publisher_primary_retains_owned_requests_without_cleanup(
    boundary, requests_cleanup_failure,
):
    ownership = _farm.producer_build("Unconfirmed publisher cleanup regression")
    primary = build.PoolProcessCleanupError("owned publisher cleanup remains unconfirmed")
    assert primary.cleanup_confirmed is False
    with pytest.raises(build.PoolProcessCleanupError) as caught:
        with ownership:
            requests_cleanup_failure.arm(ownership)
            raise primary
    assert caught.value is primary
    assert boundary.close_reasons == ["failed"]
    _assert_requests_cleanup_report(
        ownership, requests_cleanup_failure, primary=primary, cleanup_attempted=False,
    )


@pytest.mark.parametrize("damage", ["invalid JSON", "identity", "unfinished"])
def test_corrupt_or_interrupted_receipt_never_launches_a_second_publisher(boundary, damage):
    _farm.run_leaf(TASK, KEY)
    paths = list((boundary.requests_directory / "preparation").glob("*.json"))
    assert len(paths) == 1
    receipt = json.loads(paths[0].read_text(encoding="utf-8"))
    if damage == "invalid JSON":
        paths[0].write_text("{invalid", encoding="utf-8")
    else:
        if damage == "identity":
            receipt["identity"]["agent_identity_sha256"] = "f" * 64
        else:
            receipt["state"] = "publishing"
        paths[0].write_text(json.dumps(receipt), encoding="utf-8")
    for _ in range(2):
        with pytest.raises(RuntimeError, match="publication (receipt|was interrupted)"):
            _farm.run_leaf(TASK, KEY)
    assert len(boundary.publication_calls) == 1
    assert len(boundary.requests) == 1


def test_receipt_setup_consumes_work_budget_without_launch_or_fresh_retry(
    boundary, monkeypatch, publication_request, publication_clock,
):
    readiness = json.loads(_farm.os.environ["HARMONIC_FARM_PREPARATION_READINESS"])
    readiness.update(operation_timeout_s=1.0, process_margin_s=3.0)
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", json.dumps(readiness))
    real_atomic_json = _farm._atomic_json
    writes = []

    def delayed_marker(path, payload):
        writes.append(payload["state"])
        real_atomic_json(path, payload)
        if payload["state"] == "publishing":
            publication_clock.now += 2.0

    monkeypatch.setattr(_farm, "_atomic_json", delayed_marker)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="operation deadline exhausted before publisher launch"):
            _farm._ensure_preparation_published(publication_request)
    assert writes == ["publishing", "failed"]
    assert boundary.publication_calls == []
    assert boundary.requests == []
    path = next((boundary.requests_directory / "preparation").glob("*.json"))
    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "failed"


@pytest.fixture
def publication_request():
    return _farm.LeafRequest(
        _farm.FARM_PROTOCOL_VERSION, COMMIT, TASK, KEY, None, "offline@test", BUILD,
    )


@pytest.fixture
def publication_clock(boundary, monkeypatch):
    clock = SimpleNamespace(now=1000.0)
    clock.read = lambda: clock.now
    boundary.publication_clock = clock.read
    # Publication uses the selected pool's counter, not this divergent epoch.
    # Keep the process-wide time module used by pytest and FileLock unchanged.
    monkeypatch.setattr(_farm, "time", SimpleNamespace(monotonic=lambda: -1_000_000.0))
    return clock


def test_lock_wait_consumes_the_original_declared_publication_budget(
    boundary, monkeypatch, publication_request, publication_clock,
):
    from filelock import FileLock

    readiness = json.loads(_farm.os.environ["HARMONIC_FARM_PREPARATION_READINESS"])
    readiness.update(operation_timeout_s=7.5, process_margin_s=1.25)
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", json.dumps(readiness))
    real_acquire = FileLock.acquire
    waits = []

    def delayed_acquire(lock, *, timeout):
        waits.append(timeout)
        publication_clock.now += 2.0
        return real_acquire(lock, timeout=0)

    monkeypatch.setattr(FileLock, "acquire", delayed_acquire)
    _farm._ensure_preparation_published(publication_request)
    assert waits == [1.0]
    assert boundary.publication_calls == [(boundary.pool, boundary.workspace)]
    assert boundary.publication_options == [{
        "commit": COMMIT, "operation_deadline": 1007.5, "process_margin_s": 1.25,
        "clock": publication_clock.read,
    }]
    timing = boundary.spans["farm.preparation"][0]
    assert timing["operation_timeout_s"] == 7.5
    assert timing["process_margin_s"] == 1.25
    assert timing["lock_wait_ms"] == 2000
    assert timing["operation_deadline_counter"] == 1007.5
    assert timing["publication_ms"] == 0


@pytest.mark.parametrize("shared_state", ["succeeded", "failed", "publishing", "missing"])
def test_process_margin_observes_shared_outcomes_but_never_starts_publication(
    boundary, monkeypatch, publication_request, publication_clock, shared_state,
):
    from filelock import FileLock

    _farm._ensure_preparation_published(publication_request)
    path = next((boundary.requests_directory / "preparation").glob("*.json"))
    if shared_state == "missing":
        path.unlink()
    else:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["state"] = shared_state
        receipt["error"] = "shared publisher failure" if shared_state == "failed" else None
        path.write_text(json.dumps(receipt), encoding="utf-8")
    readiness = json.loads(_farm.os.environ["HARMONIC_FARM_PREPARATION_READINESS"])
    readiness.update(operation_timeout_s=1.0, process_margin_s=3.0)
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", json.dumps(readiness))
    real_acquire = FileLock.acquire
    holder = FileLock(str(path.with_suffix(".lock")))
    holder.acquire()
    waits = []

    def acquire_after_work_deadline(lock, *, timeout):
        waits.append(timeout)
        if holder.is_locked:
            publication_clock.now += timeout
            if len(waits) == 2:
                holder.release()
        return real_acquire(lock, timeout=0)

    monkeypatch.setattr(FileLock, "acquire", acquire_after_work_deadline)
    try:
        if shared_state == "succeeded":
            _farm._ensure_preparation_published(publication_request)
        else:
            diagnostic = {
                "failed": "shared publisher failure",
                "publishing": "was interrupted",
                "missing": "operation deadline exhausted before publisher launch",
            }[shared_state]
            with pytest.raises(RuntimeError, match=diagnostic):
                _farm._ensure_preparation_published(publication_request)
        assert publication_clock.now == 1002.0
        assert waits == [1.0, 1.0]
        if shared_state == "missing":
            assert json.loads(path.read_text(encoding="utf-8"))["state"] == "failed"
            # A new caller gets a new observation window, never a retry of the
            # publication whose one work budget was already exhausted.
            with pytest.raises(RuntimeError, match="operation deadline exhausted"):
                _farm._ensure_preparation_published(publication_request)
    finally:
        holder.release()
    assert len(boundary.publication_calls) == 1
    assert boundary.requests == []


def test_build_shared_lock_uses_responsive_slices_and_one_observation_deadline(
    boundary, monkeypatch, publication_request, publication_clock,
):
    from filelock import FileLock

    _farm._ensure_preparation_published(publication_request)
    path = next((boundary.requests_directory / "preparation").glob("*.json"))
    readiness = json.loads(_farm.os.environ["HARMONIC_FARM_PREPARATION_READINESS"])
    readiness.update(operation_timeout_s=2.5, process_margin_s=0.75)
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", json.dumps(readiness))
    real_acquire = FileLock.acquire
    holder = FileLock(str(path.with_suffix(".lock")))
    holder.acquire()
    waits = []

    def contended_acquire(lock, *, timeout):
        waits.append(timeout)
        publication_clock.now += timeout
        return real_acquire(lock, timeout=0)

    monkeypatch.setattr(FileLock, "acquire", contended_acquire)
    try:
        with pytest.raises(RuntimeError, match="lock timed out after 2.5s work and 0.75s"):
            _farm._ensure_preparation_published(publication_request)
    finally:
        holder.release()
    assert waits == [1.0, 1.0, 1.0, 0.25]
    assert publication_clock.now == 1003.25
    assert len(boundary.publication_calls) == 1
    assert boundary.requests == []


_SHARED_PUBLICATION_CHILD = textwrap.dedent(
    """
    import json
    import os
    import sys
    from contextlib import nullcontext
    from pathlib import Path
    from types import SimpleNamespace

    sys.path.insert(0, sys.argv[1])
    sys.path.insert(0, str(Path(sys.argv[1]) / "cad" / "scripts"))
    import _farm
    import build

    _farm.REPO_ROOT = Path(sys.argv[2])
    build._pool_home = lambda: Path(sys.argv[3])
    build._pool_publication_clock = lambda pool: _farm.time.perf_counter
    mode = sys.argv[4]
    calls = Path(sys.argv[5])
    _farm._telemetry.span = lambda *a, **k: nullcontext(
        SimpleNamespace(set_attribute=lambda *a: None)
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("shared-publication child attempted live or native work")

    _farm.subprocess.run = forbidden
    _farm.subprocess.Popen = forbidden
    _farm.load_config = forbidden
    _farm._connect_client = forbidden
    _farm._thread.interrupt_main = forbidden

    def publish(pool, workspace, *, commit, operation_deadline, process_margin_s, clock):
        assert clock is _farm.time.perf_counter
        with calls.open("a", encoding="utf-8") as stream:
            stream.write(str(os.getpid()) + "\\n")
        print("publishing", flush=True)
        assert sys.stdin.readline() == "release\\n"
        if mode == "crash":
            os._exit(23)
        if mode == "failure":
            raise build.FarmPreflightError("publisher authorization denied")
        return {
            "configured": True, "commit": commit,
            "agent_identity_sha256": os.environ["HARMONIC_FARM_AGENT_IDENTITY"],
        }

    build._pool_preparation = publish
    request = _farm.LeafRequest(
        _farm.FARM_PROTOCOL_VERSION, os.environ["HARMONIC_FARM_COMMIT"],
        "part:pen_rod", "d" * 64, None, "guarded@test",
        os.environ["HARMONIC_FARM_BUILD_ID"],
    )
    print("ready", flush=True)
    assert sys.stdin.readline() == "start\\n"
    print("attempt", flush=True)
    try:
        _farm._ensure_preparation_published(request)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), flush=True)
    else:
        print(json.dumps({"ok": True}), flush=True)
    """
)


@pytest.mark.parametrize("mode", ["success", "failure", "crash"])
def test_spawned_action_processes_share_exactly_one_publisher_and_its_outcome(
    boundary, tmp_path, mode
):
    """Real independent interpreters, but only a synthetic publisher in each."""
    calls = tmp_path / "publisher-calls.txt"
    messages = queue.Queue()
    children, readers, output = [], [], [[], []]
    env = dict(_farm.os.environ, OTEL_SDK_DISABLED="true")

    def read_output(index, child):
        for line in child.stdout:
            line = line.rstrip("\n")
            output[index].append(line)
            messages.put((index, line))

    try:
        for index in range(2):
            child = subprocess.Popen(
                [sys.executable, "-I", "-c", _SHARED_PUBLICATION_CHILD,
                 str(REPO_ROOT), str(boundary.workspace), str(boundary.pool),
                 mode, str(calls)],
                cwd=tmp_path, env=env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            children.append(child)
            reader = threading.Thread(
                target=read_output, args=(index, child),
                name=f"preparation-child-output-{index}", daemon=True,
            )
            readers.append(reader)
            reader.start()
        ready = set()
        while len(ready) < 2:
            index, line = messages.get(timeout=60)
            assert line == "ready", output
            ready.add(index)
        for child in children:
            child.stdin.write("start\n")
            child.stdin.flush()
        attempts, publisher = set(), None
        while len(attempts) < 2 or publisher is None:
            index, line = messages.get(timeout=WAIT_S)
            if line == "attempt":
                attempts.add(index)
            elif line == "publishing":
                assert publisher is None, "more than one process started publication"
                publisher = index
            else:
                pytest.fail(f"child completed before publication was released: {output}")
        assert len(calls.read_text(encoding="utf-8").splitlines()) == 1
        children[publisher].stdin.write("release\n")
        children[publisher].stdin.flush()
        for child in children:
            child.wait(timeout=WAIT_S)
        for reader in readers:
            reader.join(timeout=WAIT_S)
            assert not reader.is_alive()
        outcomes = [
            json.loads(lines[-1]) for index, lines in enumerate(output)
            if mode != "crash" or index != publisher
        ]
        if mode == "success":
            assert outcomes == [{"ok": True}, {"ok": True}]
        else:
            assert all(outcome["ok"] is False for outcome in outcomes)
            expected = "authorization denied" if mode == "failure" else "was interrupted"
            assert all(expected in outcome["error"] for outcome in outcomes)
            if mode == "failure":
                assert outcomes[0]["error"] == outcomes[1]["error"]
        assert len(calls.read_text(encoding="utf-8").splitlines()) == 1
        assert [child.returncode for child in children].count(23) == (mode == "crash")
    finally:
        # Only captured synthetic children are stopped. No console broadcast,
        # process-name kill, COM seat, or remote worker is involved.
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=WAIT_S)
        for reader in readers:
            reader.join(timeout=WAIT_S)
        for child in children:
            child.stdin.close()
            child.stdout.close()
            child.stderr.close()


def test_confirmed_publisher_timeout_is_a_shared_terminal_failure(boundary):
    def timeout():
        raise build.FarmPreflightError(
            "publisher exceeded 900s; owned publisher process tree termination confirmed"
        )

    boundary.publication_hook = timeout
    errors = []
    for _ in range(2):
        with pytest.raises(RuntimeError, match="900s.*termination confirmed") as caught:
            _farm.run_leaf(TASK, KEY)
        errors.append(str(caught.value))
    assert errors[0] == errors[1]
    assert len(boundary.publication_calls) == 1
    assert boundary.requests == []
    receipt = json.loads(next(
        (boundary.requests_directory / "preparation").glob("*.json")
    ).read_text(encoding="utf-8"))
    assert receipt["state"] == "failed"
    assert boundary.spans["farm.preparation"][0]["publication_ms"] >= 0


def test_unconfirmed_publisher_cleanup_keeps_the_nonterminal_fail_closed_marker(boundary):
    failure = build.PoolProcessCleanupError(
        "publisher exceeded 900s; owned process tree cleanup remains unconfirmed"
    )

    def timeout():
        raise failure

    boundary.publication_hook = timeout
    with pytest.raises(build.PoolProcessCleanupError) as caught:
        _farm.run_leaf(TASK, KEY)
    assert caught.value is failure
    path = next((boundary.requests_directory / "preparation").glob("*.json"))
    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "publishing"
    with pytest.raises(RuntimeError, match="was interrupted"):
        _farm.run_leaf(TASK, KEY)
    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "publishing"
    assert len(boundary.publication_calls) == 1
    assert boundary.requests == []


@pytest.fixture
def owned_requests(boundary, monkeypatch, tmp_path):
    """Capture real owned roots and cleanup calls without leaking retained roots."""
    monkeypatch.delenv("HARMONIC_FARM_REQUESTS")
    temporary_directory = _farm.tempfile.TemporaryDirectory
    state = SimpleNamespace(root=None, owned=None, cleanup_calls=[], warnings=[])
    cleanups = []

    def create(**kwargs):
        owned = temporary_directory(dir=tmp_path, **kwargs)
        state.owned, state.root = owned, Path(owned.name)
        real_cleanup = owned.cleanup
        cleanups.append(real_cleanup)

        def cleanup():
            state.cleanup_calls.append(state.root)
            real_cleanup()

        monkeypatch.setattr(owned, "cleanup", cleanup)
        return owned

    monkeypatch.setattr(_farm.tempfile, "TemporaryDirectory", create)
    monkeypatch.setattr(
        _farm._telemetry, "warn",
        lambda message, **attributes: state.warnings.append((message, attributes)),
    )
    try:
        yield state
    finally:
        for cleanup in cleanups:
            cleanup()


@pytest.mark.parametrize("evidence", [
    "succeeded", "failed", "empty", "free-lock", "receipt-staging", "lock-staging",
])
def test_normal_return_cleans_terminal_receipts_and_free_lock_evidence(
    boundary, owned_requests, evidence,
):
    ownership = _farm.producer_build("Normal receipt cleanup")
    with ownership:
        root = owned_requests.root
        if evidence != "empty":
            if evidence == "failed":
                boundary.publication_error = build.FarmPreflightError("synthetic rejection")
                with pytest.raises(RuntimeError, match="synthetic rejection"):
                    _farm.run_leaf(TASK, KEY)
            else:
                _farm.run_leaf(TASK, KEY)
            path = next((root / "preparation").glob("*.json"))
            lock_path = path.with_suffix(".lock")
            if evidence in {"free-lock", "lock-staging"}:
                path.unlink()
                # FileLock may remove the file on Windows release. Supply a real,
                # currently free lock entry, without assuming it persists.
                lock_path.touch()
            if evidence in {"receipt-staging", "lock-staging"}:
                path.with_name(f"{path.name}.123.{'b' * 32}.tmp").write_text(
                    "{partial", encoding="utf-8",
                )
        ownership.finish(evidence != "failed")
    assert owned_requests.cleanup_calls == [root]
    assert ownership._owned_requests is None
    assert not root.exists()
    assert owned_requests.warnings == []
    assert boundary.requests_directory.is_dir()


@pytest.mark.parametrize("damage", [
    "publishing", "busy", "busy-lock-only", "staging-busy", "corrupt",
    "foreign-build", "bad-digest", "extra-identity-key", "missing-identity-key",
    "non-string-identity", "failed-without-error", "unknown-state", "unknown-entry",
    "subdirectory", "unreadable", "scan-error", "staging-only", "preparation-file",
])
def test_successful_return_retains_unsafe_preparation_and_fails_loud(
    boundary, owned_requests, monkeypatch, damage,
):
    from filelock import FileLock

    ownership = _farm.producer_build("Unsafe receipt cleanup")
    holder = None
    try:
        with pytest.raises(_farm.BuildOwnershipError, match="Farm requests retained") as caught:
            with ownership:
                _farm.run_leaf(TASK, KEY)
                root = owned_requests.root
                preparation = root / "preparation"
                path = next(preparation.glob("*.json"))
                receipt = json.loads(path.read_text(encoding="utf-8"))
                if damage in {"busy", "busy-lock-only", "staging-busy"}:
                    holder = FileLock(str(path.with_suffix(".lock")))
                    holder.acquire(timeout=0)
                    if damage != "busy":
                        path.unlink()
                    if damage == "staging-busy":
                        path.with_name(f"{path.name}.123.{'b' * 32}.tmp").write_text(
                            "{partial", encoding="utf-8",
                        )
                elif damage == "corrupt":
                    path.write_text("{broken", encoding="utf-8")
                elif damage == "bad-digest":
                    path.rename(preparation / f"{'f' * 64}.json")
                elif damage == "unknown-entry":
                    (preparation / "unexpected.txt").write_text("unknown", encoding="utf-8")
                elif damage == "subdirectory":
                    (preparation / "unexpected").mkdir()
                elif damage == "unreadable":
                    real_read = Path.read_text

                    def unreadable(candidate, *args, **kwargs):
                        if candidate == path:
                            raise PermissionError("synthetic unreadable receipt")
                        return real_read(candidate, *args, **kwargs)

                    monkeypatch.setattr(Path, "read_text", unreadable)
                elif damage == "scan-error":
                    real_iterdir = Path.iterdir

                    def unreadable_directory(candidate):
                        if candidate == preparation:
                            raise OSError("synthetic listing failure")
                        return real_iterdir(candidate)

                    monkeypatch.setattr(Path, "iterdir", unreadable_directory)
                elif damage in {"staging-only", "preparation-file"}:
                    path.unlink()
                    path.with_suffix(".lock").unlink(missing_ok=True)
                    if damage == "staging-only":
                        path.with_name(f"{path.name}.123.{'b' * 32}.tmp").write_text(
                            "{partial", encoding="utf-8",
                        )
                    else:
                        preparation.rmdir()
                        preparation.write_text("not a directory", encoding="utf-8")
                else:
                    if damage == "publishing":
                        receipt["state"] = "publishing"
                    elif damage == "foreign-build":
                        receipt["identity"]["build_id"] = "foreign-build"
                    elif damage == "extra-identity-key":
                        receipt["identity"]["extra"] = "not part of the identity"
                    elif damage == "missing-identity-key":
                        del receipt["identity"]["workspace"]
                    elif damage == "non-string-identity":
                        receipt["identity"]["workspace"] = 17
                    elif damage == "failed-without-error":
                        receipt.update(state="failed", error="")
                    else:
                        receipt["state"] = "unknown"
                    path.write_text(json.dumps(receipt), encoding="utf-8")
                ownership.finish(True)
        assert caught.value.__cause__ is None
        assert ownership._owned_requests is owned_requests.owned
        assert root.is_dir()
        assert owned_requests.cleanup_calls == []
        assert len(owned_requests.warnings) == 1
        assert str(root) in owned_requests.warnings[0][0]
        assert "HARMONIC_FARM_REQUESTS" not in _farm.os.environ
    finally:
        if holder is not None:
            holder.release()


def test_failed_finish_retains_publishing_receipt_without_changing_nonzero_result(
    boundary, owned_requests,
):
    boundary.publication_error = build.PoolProcessCleanupError("synthetic unconfirmed child")
    ownership = _farm.producer_build("Generic failed action outcome")

    def failed_build():
        with ownership:
            with pytest.raises(build.PoolProcessCleanupError):
                _farm.run_leaf(TASK, KEY)
            ownership.finish(False)
            return 7

    assert failed_build() == 7
    assert owned_requests.cleanup_calls == []
    assert owned_requests.root.is_dir()
    path = next((owned_requests.root / "preparation").glob("*.json"))
    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "publishing"
    assert len(owned_requests.warnings) == 1
    assert boundary.close_reasons == ["failed"]


@pytest.mark.parametrize("location", ["root", "preparation", "receipt"])
@pytest.mark.parametrize("alias_kind", ["symlink", "junction"])
def test_normal_return_retains_aliases_without_following_other_roots(
    boundary, owned_requests, monkeypatch, tmp_path, location, alias_kind,
):
    if alias_kind == "junction" and _farm.os.name != "nt":
        pytest.skip("Windows junctions only")
    if alias_kind == "junction" and location == "receipt":
        pytest.skip("junctions alias directories, not receipt files")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "untouched.txt"
    sentinel.write_text("not owned", encoding="utf-8")
    ownership = _farm.producer_build("Aliased receipt cleanup")
    alias = None
    try:
        with pytest.raises(_farm.BuildOwnershipError, match="Farm requests retained"):
            with ownership:
                root = owned_requests.root
                if location == "root":
                    alias = tmp_path / "requests-alias"
                    target = root
                elif location == "preparation":
                    alias, target = root / "preparation", outside
                else:
                    preparation = root / "preparation"
                    preparation.mkdir()
                    alias, target = preparation / f"{'a' * 64}.json", sentinel
                try:
                    if alias_kind == "junction":
                        import _winapi
                        _winapi.CreateJunction(str(target), str(alias))
                    else:
                        alias.symlink_to(target, target_is_directory=target.is_dir())
                except OSError as exc:
                    pytest.skip(f"local alias creation unavailable: {type(exc).__name__}")
                if location == "root":
                    # Change only the captured owned object's path; its original
                    # root remains available for fixture-owned cleanup.
                    monkeypatch.setattr(owned_requests.owned, "name", str(alias))
                ownership.finish(True)
        assert owned_requests.cleanup_calls == []
        assert root.is_dir()
        assert sentinel.read_text(encoding="utf-8") == "not owned"
        assert len(owned_requests.warnings) == 1
    finally:
        if alias is not None:
            if alias.is_symlink():
                alias.unlink()
            elif alias.is_junction():
                alias.rmdir()
        if owned_requests.owned is not None:
            monkeypatch.setattr(owned_requests.owned, "name", str(owned_requests.root))


def test_teardown_acquires_each_digest_lock_before_shared_receipt_validation(
    boundary, owned_requests, monkeypatch,
):
    from filelock import FileLock, Timeout

    validated = []
    real_read = _farm._read_preparation_receipt
    ownership = _farm.producer_build("Locked teardown validation")
    with ownership:
        _farm.run_leaf(TASK, KEY)
        path = next((owned_requests.root / "preparation").glob("*.json"))

        def read_locked(candidate, **kwargs):
            assert candidate == path
            with pytest.raises(Timeout):
                FileLock(str(candidate.with_suffix(".lock"))).acquire(timeout=0)
            validated.append(candidate)
            return real_read(candidate, **kwargs)

        monkeypatch.setattr(_farm, "_read_preparation_receipt", read_locked)
        ownership.finish(True)
    assert validated == [path]
    assert owned_requests.cleanup_calls == [owned_requests.root]


@pytest.mark.parametrize("terminal", ["succeeded", "failed"])
def test_producer_writes_under_lock_before_launch_and_never_rewrites_terminal_receipts(
    boundary, monkeypatch, publication_request, terminal,
):
    from filelock import FileLock, Timeout

    real_atomic = _farm._atomic_json
    writes = []

    def write_locked(path, receipt):
        with pytest.raises(Timeout):
            FileLock(str(path.with_suffix(".lock"))).acquire(timeout=0)
        writes.append(receipt["state"])
        real_atomic(path, receipt)

    def publish_after_marker():
        path = next((boundary.requests_directory / "preparation").glob("*.json"))
        assert json.loads(path.read_text(encoding="utf-8"))["state"] == "publishing"
        with pytest.raises(Timeout):
            FileLock(str(path.with_suffix(".lock"))).acquire(timeout=0)
        if terminal == "failed":
            raise build.FarmPreflightError("absorbing rejection")

    monkeypatch.setattr(_farm, "_atomic_json", write_locked)
    boundary.publication_hook = publish_after_marker
    for _ in range(2):
        if terminal == "failed":
            with pytest.raises(RuntimeError, match="absorbing rejection"):
                _farm._ensure_preparation_published(publication_request)
        else:
            _farm._ensure_preparation_published(publication_request)
    assert writes == ["publishing", terminal]
    assert len(boundary.publication_calls) == 1


@pytest.mark.parametrize("phase", ["before-acquire", "after-acquire", "before-launch"])
def test_runner_cancellation_stops_publication_and_releases_any_acquired_lock(
    boundary, monkeypatch, publication_request, phase,
):
    from filelock import FileLock

    real_acquire, real_atomic = FileLock.acquire, _farm._atomic_json
    acquired = []

    def acquire(lock, *, timeout):
        result = real_acquire(lock, timeout=timeout)
        acquired.append(lock.lock_file)
        if phase == "after-acquire":
            asyncio.current_task().cancel()
        return result

    def marker(path, receipt):
        real_atomic(path, receipt)
        if phase == "before-launch" and receipt["state"] == "publishing":
            asyncio.current_task().cancel()

    monkeypatch.setattr(FileLock, "acquire", acquire)
    monkeypatch.setattr(_farm, "_atomic_json", marker)

    async def publication():
        if phase == "before-acquire":
            asyncio.current_task().cancel()
        _farm._ensure_preparation_published(publication_request)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(publication())
    assert boundary.publication_calls == []
    assert boundary.requests == []
    preparation = boundary.requests_directory / "preparation"
    receipts = list(preparation.glob("*.json"))
    if phase == "before-launch":
        assert len(receipts) == 1
        assert json.loads(receipts[0].read_text(encoding="utf-8"))["state"] == "publishing"
    else:
        assert receipts == []
    for path in acquired:
        # Use the real acquire, outside the cancelled Runner task.
        probe = FileLock(path)
        with real_acquire(probe, timeout=0):
            pass


def test_selected_clock_load_finishes_before_the_single_prelock_deadline_starts(
    boundary, monkeypatch, publication_request, publication_clock,
):
    from filelock import FileLock

    readiness = json.loads(_farm.os.environ["HARMONIC_FARM_PREPARATION_READINESS"])
    readiness.update(operation_timeout_s=7.5, process_margin_s=1.25)
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", json.dumps(readiness))
    selected = []
    started = []
    real_acquire = FileLock.acquire

    def load_clock(pool):
        assert pool == boundary.pool
        selected.append(pool)
        # Loading the selected pure helper is not an operation-budget reset.
        # It must complete before the initial counter read that starts the work.
        publication_clock.now += 5000
        started.append(publication_clock.now)
        return publication_clock.read

    def acquire(lock, *, timeout):
        publication_clock.now += 2
        return real_acquire(lock, timeout=0)

    def publish():
        publication_clock.now += 0.125

    monkeypatch.setattr(build, "_pool_publication_clock", load_clock)
    monkeypatch.setattr(FileLock, "acquire", acquire)
    boundary.publication_hook = publish
    _farm._ensure_preparation_published(publication_request)
    assert selected == [boundary.pool]
    options = boundary.publication_options[0]
    timing = boundary.spans["farm.preparation"][0]
    assert options["clock"] is publication_clock.read
    assert options["operation_deadline"] - started[0] == 7.5
    assert timing["operation_deadline_counter"] == options["operation_deadline"]
    assert timing["publication_clock_domain"] == "perf_counter"
    assert timing["lock_wait_ms"] == 2000
    assert timing["publication_ms"] == 125


def test_missing_selected_clock_capability_fails_before_timer_or_lock_setup(
    boundary, monkeypatch, publication_request,
):
    from filelock import FileLock

    loads = []

    def missing_clock(pool):
        loads.append(pool)
        raise build.FarmPreflightError("selected PoolHome lacks publication_clock")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("missing clock reached a fallback timer or lock")

    monkeypatch.setattr(build, "_pool_publication_clock", missing_clock)
    monkeypatch.setattr(_farm, "time", SimpleNamespace(monotonic=forbidden, perf_counter=forbidden))
    monkeypatch.setattr(FileLock, "acquire", forbidden)
    with pytest.raises(build.FarmPreflightError, match="lacks publication_clock"):
        _farm._ensure_preparation_published(publication_request)
    assert loads == [boundary.pool]
    assert boundary.publication_calls == []
    assert boundary.spans == {}
    assert not (boundary.requests_directory / "preparation").exists()


@pytest.mark.parametrize("parent_outcome", ["generic-error", "nonzero-return"])
def test_interrupted_action_process_evidence_survives_parent_without_typed_child_error(
    boundary, owned_requests, tmp_path, parent_outcome,
):
    """A real action interpreter dies; only a generic doit outcome reaches parent."""
    calls = tmp_path / "interrupted-publisher-calls.txt"
    messages = queue.Queue()
    child = reader = None
    ownership = _farm.producer_build("Interrupted action teardown")
    primary = RuntimeError("doit action process failed")

    def failed_build():
        nonlocal child, reader
        with ownership:
            child = subprocess.Popen(
                [sys.executable, "-I", "-c", _SHARED_PUBLICATION_CHILD,
                 str(REPO_ROOT), str(boundary.workspace), str(boundary.pool),
                 "crash", str(calls)],
                cwd=tmp_path, env=dict(_farm.os.environ, OTEL_SDK_DISABLED="true"),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )

            def read_output():
                for line in child.stdout:
                    messages.put(line.rstrip("\n"))

            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            assert messages.get(timeout=60) == "ready"
            child.stdin.write("start\n")
            child.stdin.flush()
            assert messages.get(timeout=WAIT_S) == "attempt"
            assert messages.get(timeout=WAIT_S) == "publishing"
            path = next((owned_requests.root / "preparation").glob("*.json"))
            assert json.loads(path.read_text(encoding="utf-8"))["state"] == "publishing"
            child.stdin.write("release\n")
            child.stdin.flush()
            assert child.wait(timeout=WAIT_S) == 23
            if parent_outcome == "generic-error":
                raise primary
            ownership.finish(False)
            return 7

    try:
        if parent_outcome == "generic-error":
            with pytest.raises(RuntimeError) as caught:
                failed_build()
            assert caught.value is primary
            assert str(owned_requests.root) in primary.__notes__[0]
        else:
            assert failed_build() == 7
        path = next((owned_requests.root / "preparation").glob("*.json"))
        assert json.loads(path.read_text(encoding="utf-8"))["state"] == "publishing"
        assert owned_requests.cleanup_calls == []
        assert len(owned_requests.warnings) == 1
        assert boundary.close_reasons == ["failed"]
        assert len(calls.read_text(encoding="utf-8").splitlines()) == 1
    finally:
        if child is not None:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=WAIT_S)
        if reader is not None:
            reader.join(timeout=WAIT_S)
            assert not reader.is_alive()
        if child is not None:
            child.stdin.close()
            child.stdout.close()
            child.stderr.close()


def test_inherited_requests_root_and_pending_evidence_are_never_inspected_or_cleaned(
    boundary, monkeypatch,
):
    _farm.run_leaf(TASK, KEY)
    path = next((boundary.requests_directory / "preparation").glob("*.json"))
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["state"] = "publishing"
    original = json.dumps(receipt)
    path.write_text(original, encoding="utf-8")

    def forbidden(*_args):
        raise AssertionError("producer inspected a caller-owned requests root")

    monkeypatch.setattr(_farm, "_require_quiescent_requests", forbidden)
    with _farm.producer_build("Inherited root ownership") as ownership:
        assert ownership._owned_requests is None
        ownership.finish(True)
    assert path.read_text(encoding="utf-8") == original
    assert _farm.os.environ["HARMONIC_FARM_REQUESTS"] == str(boundary.requests_directory)


def test_normal_cleanup_does_not_invent_a_schema_for_root_request_records(
    boundary, owned_requests,
):
    with _farm.producer_build("Existing request inventory") as ownership:
        root = owned_requests.root
        (root / "existing-request-record.custom").write_text("opaque", encoding="utf-8")
        ownership.finish(True)
    assert owned_requests.cleanup_calls == [root]
    assert not root.exists()


def test_lock_probe_oserror_retains_real_receipt_and_fails_success_loud(
    boundary, owned_requests, monkeypatch,
):
    from filelock import FileLock

    ownership = _farm.producer_build("Unconfirmed lock probe")
    with pytest.raises(_farm.BuildOwnershipError, match="Farm requests retained"):
        with ownership:
            _farm.run_leaf(TASK, KEY)
            path = next((owned_requests.root / "preparation").glob("*.json"))

            def refuse_probe(_lock, *, timeout):
                assert timeout == 0
                raise OSError("synthetic lock probe failure")

            monkeypatch.setattr(FileLock, "acquire", refuse_probe)
            ownership.finish(True)
    assert path.is_file()
    assert owned_requests.cleanup_calls == []
    assert len(owned_requests.warnings) == 1
