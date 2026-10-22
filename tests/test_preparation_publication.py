"""Lazy producer preparation publication, with guarded pool/Temporal boundaries."""

import asyncio
import importlib.util
import json
import queue
import subprocess
import sys
import threading
import textwrap
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
        workspace=workspace.resolve(), pool=pool.resolve(), events=[], cli_calls=[],
        requests=[], publication_hook=None, returncode=0, stdout=None,
        coordinator_hook=None, coordinator_error=None, interrupts=[],
        heartbeat=threading.Event(),
        close_reasons=[],
        requests_directory=requests_directory,
        cli_options=[], spans={},
        result=_farm.LeafResult("succeeded", 0, "fake-worker", 1, True, None, None, None),
    )

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

    def pool_farm(selected_pool, *args, **options):
        state.events.append("publish")
        state.cli_calls.append((selected_pool, args))
        state.cli_options.append(options)
        if state.publication_hook is not None:
            state.publication_hook()
        payload = state.stdout
        if payload is None:
            payload = json.dumps({
                "configured": True,
                "commit": _farm.os.environ["HARMONIC_FARM_COMMIT"],
                "agent_identity_sha256": _farm.os.environ["HARMONIC_FARM_AGENT_IDENTITY"],
            })
        return subprocess.CompletedProcess(args, state.returncode, stdout=payload)

    monkeypatch.setattr(build, "_pool_farm", pool_farm)

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


def test_cache_only_build_registers_but_never_publishes_or_dispatches(
    boundary, cached_part, monkeypatch
):
    monkeypatch.setattr(cached_part, "_probe_cache", lambda *_args: "hit")
    # An otherwise admitted older PoolHome need not expose preparation on hits.
    boundary.returncode = 2
    boundary.stdout = ""
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", "null")
    with _farm.producer_build("Cache-only publication regression") as ownership:
        cached_part._cached_part_action("pen_rod", Path("unused.py"))
        ownership.finish(True)
    assert boundary.cli_calls == []
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
    assert boundary.cli_calls == [(boundary.pool, (
        "preparation", "publish", "--workspace", str(boundary.workspace),
        "--commit", COMMIT, "--json",
    ))]
    assert boundary.cli_options == [{"timeout_s": 900}]
    timing = boundary.spans["farm.preparation"][0]
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
    boundary.returncode = 2
    boundary.stdout = '{"ok": false, "error": {"code": "corruption", "message": "bad graph"}}'
    with pytest.raises(RuntimeError, match="bad graph"):
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
    assert len(boundary.cli_calls) == 1
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
            assert len(boundary.cli_calls) == 1
            assert boundary.requests == []
        finally:
            release.set()
        assert [future.result(WAIT_S) for future in futures] == [boundary.result] * 2
    assert len(boundary.cli_calls) == 1
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
    assert len(boundary.cli_calls) == 2
    assert len(boundary.requests) == 4


def test_workspace_alias_uses_canonical_root_and_same_singleflight_key(boundary, monkeypatch):
    _farm.run_leaf(TASK, KEY)
    monkeypatch.setattr(_farm, "REPO_ROOT", boundary.workspace / "unused" / "..")
    _farm.run_leaf(TASK, KEY)
    assert len(boundary.cli_calls) == 1
    assert boundary.cli_calls[0][1][3] == str(boundary.workspace)


@pytest.mark.parametrize("failure", [PermissionError("publisher authorization denied"),
                                    RuntimeError("preparation descriptor is corrupt")])
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
    assert len(boundary.cli_calls) == 1
    assert boundary.requests == []
    assert "record_request" not in boundary.events


def test_concurrent_publication_failure_is_not_retried_or_demoted_to_a_miss(boundary):
    publishing, release = threading.Event(), threading.Event()
    failure = PermissionError("publisher authorization denied")

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
    assert len(boundary.cli_calls) == 1
    assert boundary.requests == []


@pytest.mark.parametrize("stdout", [
    "not JSON", "[]", "{}",
    json.dumps({"configured": False, "commit": COMMIT, "agent_identity_sha256": AGENT}),
    json.dumps({"configured": True, "commit": "e" * 40, "agent_identity_sha256": AGENT}),
    json.dumps({"configured": True, "commit": COMMIT, "agent_identity_sha256": "f" * 64}),
])
def test_invalid_or_foreign_publisher_success_fails_closed(boundary, stdout):
    boundary.stdout = stdout
    with pytest.raises(RuntimeError, match="preparation publication"):
        _farm.run_leaf(TASK, KEY)
    assert boundary.requests == []
    assert "record_request" not in boundary.events


def test_publisher_cli_error_preserves_auth_or_corruption_diagnostic(boundary):
    boundary.returncode = 2
    boundary.stdout = json.dumps({
        "ok": False, "error": {"code": "authorization", "message": "create denied"},
    })
    with pytest.raises(RuntimeError, match=r"publication failed \(exit 2\).*create denied"):
        _farm.run_leaf(TASK, KEY)
    assert boundary.requests == []


def test_old_pool_cli_failure_names_selected_revision_and_required_capability(boundary):
    # argparse diagnostics are inherited on stderr, leaving stdout empty.
    boundary.returncode = 2
    boundary.stdout = ""
    with pytest.raises(RuntimeError) as caught:
        _farm.run_leaf(TASK, KEY)
    message = str(caught.value)
    assert f"PoolHome {boundary.pool}" in message
    assert "selected pool revision must support `preparation publish`" in message
    assert "see pool CLI stderr above" in message
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
    assert boundary.cli_calls == []
    assert boundary.requests == []


def test_foreign_request_commit_cannot_prepare_a_different_admitted_source(boundary):
    request = _farm.LeafRequest(
        _farm.FARM_PROTOCOL_VERSION, "e" * 40, TASK, KEY, None, "offline@test", BUILD,
    )
    with pytest.raises(RuntimeError, match="does not match the admitted commit"):
        asyncio.run(_farm._dispatch(request, "foreign-request"))
    assert boundary.cli_calls == []
    assert boundary.requests == []


def test_invalid_coordinator_still_fails_before_preparation(boundary):
    boundary.coordinator_error = RuntimeError("coordinator protocol refused")
    with pytest.raises(RuntimeError, match="coordinator protocol refused"):
        _farm.run_leaf(TASK, KEY)
    assert boundary.cli_calls == []
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


def test_attended_registration_failure_also_cleans_owned_requests(
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
    with pytest.raises(_farm.BuildOwnershipError, match="coordinator unavailable"):
        with _farm.producer_build("Failed attended preparation cleanup"):
            pytest.fail("producer entered after registration failed")
    assert created and all(not path.exists() for path in created)
    assert "HARMONIC_FARM_REQUESTS" not in _farm.os.environ
    assert boundary.requests_directory.is_dir()


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
    assert len(boundary.cli_calls) == 1
    assert len(boundary.requests) == 1


def test_build_shared_lock_has_a_finite_wait_without_publishing(boundary, monkeypatch):
    from filelock import FileLock

    _farm.run_leaf(TASK, KEY)
    path = next((boundary.requests_directory / "preparation").glob("*.lock"), None)
    # Windows may delete an unlocked FileLock file; its identity remains the
    # receipt basename even when the lock file itself no longer exists.
    if path is None:
        path = next((boundary.requests_directory / "preparation").glob("*.json")).with_suffix(".lock")
    monkeypatch.setattr(_farm, "_PREPARATION_LOCK_TIMEOUT_S", 0)
    with FileLock(str(path)):
        with pytest.raises(RuntimeError, match="lock timed out after 0s"):
            _farm.run_leaf(TASK, KEY)
    assert len(boundary.cli_calls) == 1
    assert len(boundary.requests) == 1


_SHARED_PUBLICATION_CHILD = textwrap.dedent(
    """
    import json
    import os
    import subprocess
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
    mode = sys.argv[4]
    calls = Path(sys.argv[5])
    _farm._PREPARATION_LOCK_TIMEOUT_S = 10
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

    def publish(pool, *args, **kwargs):
        with calls.open("a", encoding="utf-8") as stream:
            stream.write(str(os.getpid()) + "\\n")
        print("publishing", flush=True)
        assert sys.stdin.readline() == "release\\n"
        if mode == "crash":
            os._exit(23)
        if mode == "failure":
            raise PermissionError("publisher authorization denied")
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps({
            "configured": True,
            "commit": os.environ["HARMONIC_FARM_COMMIT"],
            "agent_identity_sha256": os.environ["HARMONIC_FARM_AGENT_IDENTITY"],
        }))

    build._pool_farm = publish
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
    assert len(boundary.cli_calls) == 1
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
    assert len(boundary.cli_calls) == 1
    assert boundary.requests == []
