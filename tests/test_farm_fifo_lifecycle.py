"""Real FIFO producer ownership with a fake, guarded Temporal boundary.

No native work, credentials, live service, or parent interrupt is allowed here.
The one child process is an isolated Python environment/thread-name probe.
"""

import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import doit.cmd_base as _doit_cmd_base
import pytest
from doit.cmd_base import ModuleTaskLoader
from doit.dependency import JsonDB

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

import _farm  # noqa: E402
import build  # noqa: E402

_RealFarmDoitMain = build._FarmDoitMain
DISPLAY_NAME = "FIFO lifecycle test"
INHERITED_BUILD_ID = "20261010T190000.000000Z-" + "a" * 32
FARM_RUN = "launcher-run-is-not-the-build-id"
WAIT_S = 5


def _deadline(seconds=60):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _wait(event, description, timeout=WAIT_S):
    assert event.wait(timeout), description


class _AsyncGate:
    """Let the test thread release an RPC without blocking its asyncio loop."""

    def __init__(self):
        self.entered = threading.Event()
        self.cancelled = threading.Event()
        self.released = threading.Event()
        self._loop = None
        self._event = None

    async def wait(self):
        self._loop = asyncio.get_running_loop()
        self._event = asyncio.Event()
        self.entered.set()
        if self.released.is_set():
            self._event.set()
        try:
            await self._event.wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise

    def release(self):
        self.released.set()
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._event.set)


class _Control:
    """Record wire calls; only this fake can supply ownership or renew it."""

    def __init__(self, requests, *, active=True):
        self.requests = requests
        self.active = threading.Event()
        if active:
            self.active.set()
        self.registered = threading.Event()
        self.queried = threading.Event()
        self.closed = threading.Event()
        self.heartbeat_seen = {sequence: threading.Event() for sequence in range(1, 5)}
        self.updates = []
        self.queries = []
        self.connections = []
        self.starts = []
        self.handles = []
        self.cancellations = []
        self.registration_records = []
        self.start_error = None
        self.register_response = None
        self.heartbeat_response = None
        self.query_response = None
        self.heartbeat_gate = None
        self.heartbeat_gate_sequence = None
        self.build_id = None
        self.lease_deadline = _deadline()

    def status(self):
        return _farm.BuildStatus(
            build_id=self.build_id,
            fifo_ordinal=7,
            producer_state="open",
            ownership_state="active" if self.active.is_set() else "waiting",
            lease_deadline=self.lease_deadline,
            outstanding_leaf_count=2,
            unconfirmed_attempt_count=1,
        )

    async def connect(self, identity):
        # The real durable record must precede even connection, not only register.
        record = json.loads((self.requests / "build.json").read_text("utf-8"))
        self.connections.append((identity, record, threading.get_ident()))
        assert record["build_id"] == os.environ["HARMONIC_FARM_BUILD_ID"]
        return _Client(self)

    async def execute_update(self, name, arg, **options):
        self.updates.append((name, arg, options, threading.get_ident()))
        assert options["result_type"] is _farm.BuildStatus
        assert options["rpc_timeout"] == timedelta(seconds=_farm.FIFO_RPC_TIMEOUT_S)
        if name == "register_build":
            assert isinstance(arg, _farm.RegisterBuild)
            self.build_id = arg.build_id
            self.registration_records.append(
                json.loads((self.requests / "build.json").read_text("utf-8"))
            )
            self.registered.set()
            if isinstance(self.register_response, BaseException):
                raise self.register_response
            return self.register_response(self.status()) if self.register_response else self.status()
        assert arg.build_id == self.build_id
        if name == "heartbeat_build":
            assert isinstance(arg, _farm.HeartbeatBuild)
            event = self.heartbeat_seen.get(arg.sequence)
            if event is not None:
                event.set()
            if self.heartbeat_gate is not None and (
                self.heartbeat_gate_sequence is None
                or self.heartbeat_gate_sequence == arg.sequence
            ):
                await self.heartbeat_gate.wait()
            if isinstance(self.heartbeat_response, BaseException):
                raise self.heartbeat_response
            if self.heartbeat_response is not None:
                return self.heartbeat_response(self.status())
            self.lease_deadline = _deadline()
            return self.status()
        assert name == "close_build"
        assert isinstance(arg, _farm.CloseBuild)
        self.closed.set()
        return replace(self.status(), producer_state="closed")

    async def query(self, name, arg, **options):
        assert name == "build_status"
        assert arg == _farm.BuildKey(self.build_id)
        assert options["result_type"] is _farm.BuildStatus
        assert options["rpc_timeout"] == timedelta(seconds=_farm.FIFO_RPC_TIMEOUT_S)
        self.queries.append((name, arg, options))
        self.queried.set()
        if isinstance(self.query_response, BaseException):
            raise self.query_response
        return self.query_response(self.status()) if self.query_response else self.status()

    async def cancel(self):
        self.cancellations.append("coordinator.cancel")
        raise AssertionError("ownership must never cancel a shared remote workflow")

    def calls(self, name):
        return [(arg, options) for method, arg, options, _thread_id in self.updates if method == name]


class _Client:
    def __init__(self, control):
        self.control = control

    async def start_workflow(self, *args, **options):
        from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

        self.control.starts.append((args, options))
        assert args == (_farm.WORKFLOW_BUILD_FIFO,), "producer started a leaf"
        assert options == {
            "id": _farm.WORKFLOW_BUILD_FIFO_ID,
            "task_queue": _farm.TASK_QUEUE_CONTROL,
            "id_conflict_policy": WorkflowIDConflictPolicy.USE_EXISTING,
            "id_reuse_policy": WorkflowIDReusePolicy.REJECT_DUPLICATE,
        }
        if self.control.start_error is not None:
            raise self.control.start_error
        return self.control

    def get_workflow_handle(self, workflow_id, **options):
        self.control.handles.append((workflow_id, options))
        assert workflow_id == _farm.WORKFLOW_BUILD_FIFO_ID
        assert options == {}, "coordinator must follow continue-as-new, not pin a run"
        return self.control


class _Parent:
    """Block an action independently of the actual producer renewal thread."""

    def __init__(self, ownership):
        self.ownership = ownership
        self.entered = threading.Event()
        self.release = threading.Event()
        self.done = threading.Event()
        self.errors = []
        self.success = True
        self.action_error = None
        self.action_thread_id = None
        self.action_build_id = None
        self.thread = threading.Thread(target=self._run, name="fake-doit-parent", daemon=True)

    def _run(self):
        try:
            with self.ownership:
                self.action_thread_id = threading.get_ident()
                self.action_build_id = os.environ["HARMONIC_FARM_BUILD_ID"]
                self.entered.set()
                if not self.release.wait(WAIT_S):
                    raise AssertionError("test did not release its fake local action")
                if self.action_error is not None:
                    raise self.action_error
                self.ownership.finish(self.success)
        except BaseException as exc:
            self.errors.append(exc)
        finally:
            self.done.set()

    def finish(self):
        self.release.set()
        _wait(self.done, "producer did not close after its action finished")
        self.thread.join(WAIT_S)
        assert not self.thread.is_alive()


@pytest.fixture(autouse=True)
def _guarded_process(tmp_path, monkeypatch):
    from temporalio.client import Client

    requests = tmp_path / "requests"
    requests.mkdir()
    monkeypatch.setenv("HARMONIC_FARM_REQUESTS", str(requests))
    monkeypatch.setenv("HARMONIC_FARM_RUN", FARM_RUN)
    monkeypatch.setenv("HARMONIC_FARM_DISPLAY_NAME", DISPLAY_NAME)
    monkeypatch.setenv("HARMONIC_FARM_BUILD_ID", INHERITED_BUILD_ID)
    monkeypatch.setattr(_farm, "FIFO_HEARTBEAT_INTERVAL_S", 0.01)
    monkeypatch.setattr(_farm, "STATUS_POLL_INTERVAL_S", 0.002)
    monkeypatch.setattr(_farm, "FIFO_RPC_TIMEOUT_S", 0.5)
    monkeypatch.setattr(_farm, "submitter", lambda: "test@submitter")
    monkeypatch.setattr(_farm._telemetry, "info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_farm._telemetry, "event", lambda *_args, **_kwargs: None)

    async def refuse_live_client(*_args, **_kwargs):
        raise AssertionError("test attempted a live Temporal connection")

    def refuse_config(*_args, **_kwargs):
        raise AssertionError("test attempted to read real farm credentials")

    monkeypatch.setattr(Client, "connect", refuse_live_client)
    monkeypatch.setattr(_farm, "_connect_client", refuse_live_client)
    monkeypatch.setattr(_farm, "load_config", refuse_config)
    interrupted = threading.Event()
    interrupt_calls = []

    def interrupt_parent():
        interrupt_calls.append(threading.get_ident())
        interrupted.set()

    # ALWAYS replace the native interrupt, including cases expected not to fail.
    monkeypatch.setattr(_farm._thread, "interrupt_main", interrupt_parent)
    return requests, interrupted, interrupt_calls


@pytest.fixture
def control(_guarded_process, monkeypatch):
    requests, _interrupted, _interrupt_calls = _guarded_process
    fake = _Control(requests)
    monkeypatch.setattr(_farm, "_connect_client", fake.connect)
    yield fake
    if fake.heartbeat_gate is not None:
        fake.heartbeat_gate.release()


@pytest.fixture
def start_parent(control):
    parents = []

    def start():
        parent = _Parent(_farm.producer_build(DISPLAY_NAME))
        parents.append(parent)
        parent.thread.start()
        return parent

    yield start
    # Do not leave a daemon renewing against torn-down monkeypatches on failure.
    for parent in parents:
        parent.release.set()
        parent.ownership._stop.set()
        parent.ownership._ready.set()
        if control.heartbeat_gate is not None:
            control.heartbeat_gate.release()
        parent.thread.join(WAIT_S)
        assert not parent.thread.is_alive(), "fake parent thread leaked"
        assert not parent.ownership._thread.is_alive(), "producer renewal thread leaked"


def _assert_close(control, build_id, reason):
    [(close, options)] = control.calls("close_build")
    assert close == _farm.CloseBuild(build_id, reason)
    operation = f"close:{build_id}:{reason}"
    assert options["id"] == "fifo:" + hashlib.sha256(operation.encode()).hexdigest()
    assert control.cancellations == []


def test_waiting_registration_renews_without_entering_scheduler_then_activation_enters(
    control, start_parent, _guarded_process
):
    control.active.clear()
    parent = start_parent()
    _wait(control.registered, "build was not registered")
    _wait(control.queried, "waiting ownership was not polled")
    _wait(control.heartbeat_seen[2], "waiting producer did not independently renew")

    assert not parent.entered.is_set(), "waiting build entered its native scheduler"
    assert control.calls("close_build") == []
    assert control.connections[0][0] == "test@submitter"
    [(registration, registration_options)] = control.calls("register_build")
    assert registration == _farm.RegisterBuild(parent.ownership.build_id, "test@submitter", DISPLAY_NAME)
    assert registration_options["id"] == "fifo:" + hashlib.sha256(
        f"register:{registration.build_id}".encode()
    ).hexdigest()

    control.active.set()
    _wait(parent.entered, "active ownership did not release scheduler entry")
    assert parent.action_build_id == registration.build_id
    heartbeat_calls = control.calls("heartbeat_build")
    sequences = [heartbeat.sequence for heartbeat, _options in heartbeat_calls]
    assert len(sequences) >= 2
    assert sequences == list(range(1, len(sequences) + 1))
    for heartbeat, options in heartbeat_calls:
        assert heartbeat.build_id == registration.build_id
        assert options["id"] == "fifo:" + hashlib.sha256(
            f"heartbeat:{registration.build_id}:{heartbeat.sequence}".encode()
        ).hexdigest()
    assert len({options["id"] for _heartbeat, options in heartbeat_calls}) == len(sequences)
    assert control.connections[0][2] != parent.action_thread_id

    parent.finish()
    assert parent.errors == []
    _assert_close(control, registration.build_id, "finished")
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID
    assert not _guarded_process[1].is_set()


def test_active_local_action_gap_renews_and_spawned_child_inherits_only_build_identity(
    control, start_parent, tmp_path
):
    original_deadline = datetime.fromisoformat(control.lease_deadline)
    control.heartbeat_gate = _AsyncGate()
    control.heartbeat_gate_sequence = 2
    parent = start_parent()
    _wait(parent.entered, "active ownership did not enter its local action")
    _wait(control.heartbeat_gate.entered, "local-only action gap stopped ownership renewal")
    # Reaching renewal two proves renewal one has been received and validated.
    assert parent.ownership._lease_wall == datetime.fromisoformat(control.lease_deadline)
    assert parent.ownership._lease_wall > original_deadline
    control.heartbeat_gate.release()
    assert not parent.done.is_set()
    assert control.queries == [], "active renewal should not depend on a dispatched leaf"

    # Safe probe only: no repository imports, COM, shell, credentials or workload.
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import json, os, threading; print(json.dumps({"
            "'build_id': os.environ.get('HARMONIC_FARM_BUILD_ID'), "
            "'threads': [t.name for t in threading.enumerate()]}))",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=WAIT_S,
    )
    inherited = json.loads(child.stdout)
    assert inherited["build_id"] == parent.ownership.build_id
    assert inherited["build_id"] != INHERITED_BUILD_ID
    assert "farm-build-lease" not in inherited["threads"]
    assert control.calls("close_build") == []

    parent.finish()
    assert parent.errors == []
    _assert_close(control, parent.ownership.build_id, "finished")


@pytest.mark.parametrize(
    ("success", "action_error", "reason"),
    [
        (True, None, "finished"),
        (False, None, "failed"),
        (True, RuntimeError("local action failed"), "failed"),
        (True, KeyboardInterrupt("cancel local producer"), "cancelled"),
    ],
    ids=["success", "failed-exit", "action-exception", "parent-cancellation"],
)
def test_finally_closes_group_without_cancelling_shared_remote_work(
    control, start_parent, _guarded_process, success, action_error, reason
):
    parent = start_parent()
    _wait(parent.entered, "producer did not enter action")
    parent.success = success
    parent.action_error = action_error
    parent.finish()

    assert parent.errors == ([] if action_error is None else [action_error])
    _assert_close(control, parent.ownership.build_id, reason)
    assert control.status().outstanding_leaf_count == 2
    assert control.status().unconfirmed_attempt_count == 1
    assert control.handles == [(_farm.WORKFLOW_BUILD_FIFO_ID, {})]
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID
    assert not _guarded_process[1].is_set()


@pytest.mark.parametrize(
    "fault",
    ["rpc-outage", "closed", "expired", "past-deadline", "foreign-build", "waiting", "drained"],
)
def test_active_renewal_fault_fails_closed_and_interrupts_only_mocked_parent(
    control, start_parent, _guarded_process, fault
):
    # Gate the first renewal until local execution has actually started.
    control.heartbeat_gate = _AsyncGate()
    parent = start_parent()
    _wait(parent.entered, "producer did not enter action")
    _wait(control.heartbeat_gate.entered, "heartbeat did not reach fake boundary")
    if fault == "rpc-outage":
        control.heartbeat_response = ConnectionError("control unavailable")
    else:
        changes = {
            "closed": {"producer_state": "closed"},
            "expired": {"producer_state": "expired"},
            "past-deadline": {"lease_deadline": _deadline(-1)},
            "foreign-build": {"build_id": "another-build"},
            "waiting": {"ownership_state": "waiting"},
            "drained": {"ownership_state": "drained"},
        }[fault]
        control.heartbeat_response = lambda status: replace(status, **changes)
    control.heartbeat_gate.release()
    _wait(_guarded_process[1], "lost ownership did not interrupt the parent")

    with pytest.raises(_farm.BuildOwnershipError, match="ownership lost"):
        parent.ownership.check()
    assert not parent.done.is_set(), "mocked interrupt unexpectedly acted on the host"
    parent.finish()
    assert len(parent.errors) == 1
    assert isinstance(parent.errors[0], _farm.BuildOwnershipError)
    _assert_close(control, parent.ownership.build_id, "failed")
    assert len(_guarded_process[2]) == 1
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID


@pytest.mark.parametrize("state", ["closed", "expired"])
def test_waiting_status_failure_never_enters_or_interrupts_scheduler(
    control, start_parent, _guarded_process, state
):
    control.active.clear()
    control.query_response = lambda status: replace(status, producer_state=state)
    parent = start_parent()
    _wait(parent.done, "waiting producer did not fail closed")

    assert not parent.entered.is_set()
    assert len(parent.errors) == 1
    assert isinstance(parent.errors[0], _farm.BuildOwnershipError)
    _assert_close(control, parent.ownership.build_id, "failed")
    assert not _guarded_process[1].is_set()
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID


def test_unanswered_heartbeat_cannot_extend_last_acknowledged_lease(
    control, start_parent, _guarded_process, monkeypatch
):
    # A deadline much shorter than the RPC timeout distinguishes lease expiry
    # from ordinary RPC timeout without sleeps or an elapsed-time assertion.
    monkeypatch.setattr(_farm, "FIFO_RPC_TIMEOUT_S", 4)
    control.lease_deadline = _deadline(0.5)
    control.heartbeat_gate = _AsyncGate()
    parent = start_parent()
    _wait(parent.entered, "producer did not enter action")
    _wait(control.heartbeat_gate.entered, "heartbeat did not become outstanding")
    acknowledged_deadline = control.lease_deadline
    _wait(_guarded_process[1], "parent survived its acknowledged lease deadline", timeout=2)

    assert not control.heartbeat_gate.released.is_set()
    assert control.heartbeat_gate.cancelled.is_set()
    assert control.lease_deadline == acknowledged_deadline
    assert len(control.calls("heartbeat_build")) == 1
    with pytest.raises(_farm.BuildOwnershipError):
        parent.ownership.check()
    parent.finish()
    _assert_close(control, parent.ownership.build_id, "failed")


def test_waiting_status_queries_do_not_renew_acknowledged_lease(
    control, start_parent, _guarded_process, monkeypatch
):
    control.active.clear()
    control.lease_deadline = _deadline(0.5)
    monkeypatch.setattr(_farm, "FIFO_HEARTBEAT_INTERVAL_S", 10)
    control.query_response = lambda status: replace(status, lease_deadline=_deadline(60))
    parent = start_parent()
    _wait(control.queried, "waiting producer did not query status")
    _wait(parent.done, "status query incorrectly extended producer lease", timeout=2)

    assert not parent.entered.is_set()
    assert isinstance(parent.errors[0], _farm.BuildOwnershipError)
    assert control.calls("heartbeat_build") == []
    _assert_close(control, parent.ownership.build_id, "failed")
    assert not _guarded_process[1].is_set()


def test_accepted_registration_response_loss_leaves_durable_id_and_closes_group(
    control, start_parent, _guarded_process
):
    control.register_response = TimeoutError("registration accepted but response lost")
    parent = start_parent()
    _wait(parent.done, "uncertain registration did not finish reconciliation")

    record = {"build_id": parent.ownership.build_id, "farm_run": FARM_RUN}
    assert control.connections[0][1] == record
    assert control.registration_records == [record]
    assert json.loads((control.requests / "build.json").read_text("utf-8")) == record
    assert list(control.requests.iterdir()) == [control.requests / "build.json"]
    assert not parent.entered.is_set()
    assert isinstance(parent.errors[0], _farm.BuildOwnershipError)
    assert isinstance(parent.errors[0].__cause__, TimeoutError)
    _assert_close(control, parent.ownership.build_id, "failed")
    assert not _guarded_process[1].is_set()
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID


def test_terminal_coordinator_start_rejection_fails_closed_without_new_registration(
    control, start_parent, _guarded_process
):
    rejection = RuntimeError("terminal coordinator history cannot be restarted")
    control.start_error = rejection
    parent = start_parent()
    _wait(parent.done, "terminal singleton rejection did not fail closed")

    assert not parent.entered.is_set()
    assert len(parent.errors) == 1
    assert isinstance(parent.errors[0], _farm.BuildOwnershipError)
    assert parent.errors[0].__cause__ is rejection
    assert len(control.starts) == 1
    assert control.handles == []
    assert control.updates == [], "terminal singleton must not create a new build group"
    assert control.cancellations == []
    assert json.loads((control.requests / "build.json").read_text("utf-8")) == {
        "build_id": parent.ownership.build_id,
        "farm_run": FARM_RUN,
    }
    assert not _guarded_process[1].is_set()
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID


def test_build_that_cannot_be_recorded_never_connects_or_registers(
    control, monkeypatch, tmp_path
):
    monkeypatch.setenv("HARMONIC_FARM_REQUESTS", str(tmp_path / "missing"))
    ownership = _farm.producer_build(DISPLAY_NAME)
    with pytest.raises(FileNotFoundError):
        with ownership:
            pytest.fail("unrecorded build entered scheduler")

    assert control.connections == []
    assert control.starts == []
    assert control.updates == []
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID


def _install_serial_build(monkeypatch, action):
    """Keep the real build/main/doit wrapper, but never a real graph or DB."""

    class MemoryJsonDB(JsonDB):
        def __init__(self, name, codec, *, module_name=None):
            self.name = name
            self.codec = codec
            self._db = {}

        def dump(self):
            pass

    monkeypatch.setattr(_doit_cmd_base, "JsonDB", MemoryJsonDB)
    namespace = {"task_local_gap": lambda: {"actions": [action]}}
    config = {"GLOBAL": {"backend": "json", "dep_file": ":memory:"}}

    class FixtureFarmDoit(_RealFarmDoitMain):
        def __init__(self):
            super().__init__(task_loader=ModuleTaskLoader(namespace), extra_config=config)

        def run(self, args):
            serial = list(args)
            for index in range(len(serial) - 1):
                if serial[index:index + 2] == ["-n", "8"]:
                    serial[index + 1] = "0"
                    break
            return super().run(serial)

    monkeypatch.setattr(build, "_FarmDoitMain", FixtureFarmDoit)


def test_real_build_wrapper_mints_fresh_ids_only_after_successful_preflight(
    control, monkeypatch
):
    events = []
    minted = []
    observed = []
    real_build_id = _farm._build_id

    def preflight():
        assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID
        events.append("preflight")

    def mint():
        assert events[-1] == "preflight"
        events.append("mint")
        build_id = real_build_id()
        minted.append(build_id)
        return build_id

    def action():
        events.append("action")
        observed.append(os.environ["HARMONIC_FARM_BUILD_ID"])

    monkeypatch.setattr(build, "_farm_preflight", preflight)
    monkeypatch.setattr(_farm, "_build_id", mint)
    _install_serial_build(monkeypatch, action)
    for _ in range(2):
        assert build.main(["--executor", "farm", "--display-name", DISPLAY_NAME, "local_gap"]) == 0
        assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID

    assert events == ["preflight", "mint", "action", "preflight", "mint", "action"]
    assert observed == minted
    assert len(set(minted)) == 2
    assert INHERITED_BUILD_ID not in minted
    assert FARM_RUN not in minted
    assert all(re.fullmatch(r"\d{8}T\d{6}\.\d{6}Z-[0-9a-f]{32}", build_id) for build_id in minted)
    assert [registration.build_id for registration, _options in control.calls("register_build")] == minted
    assert [close for close, _options in control.calls("close_build")] == [
        _farm.CloseBuild(build_id, "finished") for build_id in minted
    ]
    assert control.cancellations == []


@pytest.mark.parametrize(
    ("refusal", "argv", "exit_code", "preflight_count"),
    [
        ("selection", ["local_typo"], 3, 0),
        ("label", ["--display-name=bad\nlabel", "local_gap"], 2, 0),
        ("preflight", ["local_gap"], 2, 1),
    ],
)
def test_real_wrapper_refusal_never_mints_records_registers_or_executes(
    control, monkeypatch, refusal, argv, exit_code, preflight_count
):
    preflights = []
    executed = []
    minted = []

    def preflight():
        preflights.append(1)
        raise build.FarmPreflightError("preflight rejected before ownership")

    def mint():
        minted.append(1)
        raise AssertionError(f"{refusal} refusal minted a build ID")

    monkeypatch.setattr(build, "_farm_preflight", preflight)
    monkeypatch.setattr(_farm, "_build_id", mint)
    _install_serial_build(monkeypatch, lambda: executed.append(1))
    assert build.main(["--executor", "farm", *argv]) == exit_code
    assert len(preflights) == preflight_count
    assert minted == []
    assert executed == []
    assert control.connections == []
    assert control.updates == []
    assert list(control.requests.iterdir()) == []
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID


def test_retrying_uncertain_heartbeat_reuses_update_id_and_does_not_reset_sequence(control):
    calls = []
    request = _farm.HeartbeatBuild(INHERITED_BUILD_ID, 9)

    class Handle:
        async def execute_update(self, name, arg, **options):
            calls.append((name, arg, options))
            if len(calls) == 1:
                raise TimeoutError("heartbeat accepted but response lost")
            return replace(control.status(), build_id=INHERITED_BUILD_ID)

    async def exercise():
        operation = f"heartbeat:{request.build_id}:{request.sequence}"
        with pytest.raises(TimeoutError, match="response lost"):
            await _farm._rpc_update(Handle(), "heartbeat_build", request, _farm.BuildStatus, operation)
        return await _farm._rpc_update(Handle(), "heartbeat_build", request, _farm.BuildStatus, operation)

    status = asyncio.run(exercise())
    assert status.build_id == request.build_id
    assert calls[0] == calls[1]
    assert calls[0][1].sequence == 9
    assert calls[0][2]["id"] == "fifo:" + hashlib.sha256(
        f"heartbeat:{request.build_id}:9".encode()
    ).hexdigest()
    assert calls[0][2]["rpc_timeout"] == timedelta(seconds=_farm.FIFO_RPC_TIMEOUT_S)
    assert calls[0][2]["result_type"] is _farm.BuildStatus


def test_accepted_unbound_dispatch_keeps_polling_and_local_cancel_preserves_reservation(
    _guarded_process, monkeypatch
):
    requests = _guarded_process[0]
    request = _farm.LeafRequest(
        farm_protocol_version=5,
        commit="c" * 40,
        task="part:pen_rod",
        cache_key="k" * 64,
        traceparent=None,
        submitter="test@submitter",
        build_id=INHERITED_BUILD_ID,
    )
    workflow_id = _farm.workflow_id(request.task, request.cache_key, request.commit, 900)
    key = _farm.LeafKey(request.build_id, workflow_id)
    calls = {"updates": [], "queries": [], "handles": [], "cancel": [], "start": []}

    async def exercise():
        queried_twice = asyncio.Event()
        never_bound = asyncio.Event()

        class Handle:
            async def execute_update(self, name, arg, **options):
                assert name == "submit_leaf"
                assert arg == _farm.SubmitLeaf(request, FARM_RUN)
                calls["updates"].append((name, arg, options))
                records = [json.loads(path.read_text("utf-8")) for path in requests.iterdir()]
                assert records == [{
                    "task": request.task,
                    "workflow_id": workflow_id,
                    "build_id": request.build_id,
                    "farm_run": FARM_RUN,
                }]
                return _farm.LeafStatus(key, "reserved", None, [])

            async def query(self, name, arg, **options):
                assert name == "leaf_status"
                assert arg == key
                assert options["result_type"] is _farm.LeafStatus
                calls["queries"].append((name, arg, options))
                if len(calls["queries"]) == 2:
                    queried_twice.set()
                    await never_bound.wait()
                return _farm.LeafStatus(key, "reserved", None, [])

            async def cancel(self):
                calls["cancel"].append(True)

            async def result(self):
                raise AssertionError("accepted-unbound reservation has no run to await")

        class Client:
            async def start_workflow(self, *args, **options):
                from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

                assert args == (_farm.WORKFLOW_BUILD_FIFO,)
                assert options == {
                    "id": _farm.WORKFLOW_BUILD_FIFO_ID,
                    "task_queue": _farm.TASK_QUEUE_CONTROL,
                    "id_conflict_policy": WorkflowIDConflictPolicy.USE_EXISTING,
                    "id_reuse_policy": WorkflowIDReusePolicy.REJECT_DUPLICATE,
                }
                calls["start"].append((args, options))
                return Handle()

            def get_workflow_handle(self, workflow_id, **options):
                calls["handles"].append((workflow_id, options))
                assert workflow_id == _farm.WORKFLOW_BUILD_FIFO_ID
                assert options == {}
                return Handle()

        async def connect(identity):
            assert identity == request.submitter
            return Client()

        monkeypatch.setattr(_farm, "_connect_client", connect)
        dispatch = asyncio.create_task(_farm._dispatch(request, workflow_id))
        try:
            await asyncio.wait_for(queried_twice.wait(), timeout=WAIT_S)
            assert not dispatch.done()
            assert len(calls["updates"]) == 1, "polling must not resubmit or start a leaf"
            assert calls["handles"] == [(_farm.WORKFLOW_BUILD_FIFO_ID, {})]
        finally:
            dispatch.cancel()
            with pytest.raises(asyncio.CancelledError):
                await dispatch

    asyncio.run(exercise())
    assert calls["cancel"] == []
    assert len(calls["queries"]) == 2
    assert len(calls["start"]) == 1
    [record_path] = requests.iterdir()
    assert json.loads(record_path.read_text("utf-8"))["build_id"] == request.build_id
