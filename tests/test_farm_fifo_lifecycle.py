"""Real FIFO producer ownership with a fake, guarded Temporal boundary.

No native work, credentials, live service, or parent interrupt is allowed here.
Child processes probe inheritance and deliver SIGINT only inside their own PID.
"""

import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import textwrap
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
        self.warnings = []
        self.registration_records = []
        self.start_error = None
        self.register_response = None
        self.heartbeat_response = None
        self.query_response = None
        self.close_response = None
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
        if isinstance(self.close_response, BaseException):
            raise self.close_response
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
    monkeypatch.setattr(
        _farm._telemetry, "warn",
        lambda message, **fields: fake.warnings.append((message, fields)),
    )
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


@pytest.mark.skipif(os.name != "nt", reason="Windows lock waits have distinct signal behavior")
@pytest.mark.parametrize("registration", ["waiting", "accepted-reply-pending"])
def test_windows_sigint_while_entering_closes_accepted_build_and_restores_environment(
    _guarded_process, tmp_path, registration
):
    # A real Python SIGINT is queued from the isolated child's background thread.
    # No console broadcast, parent interrupt, credentials or native leaf is used.
    # On 3.12/3.13 an indefinite Event.wait leaves this child blocked until killed.
    source = textwrap.dedent(
        """
        import asyncio
        import json
        import os
        import signal
        import sys
        from datetime import datetime, timedelta, timezone

        sys.path.insert(0, sys.argv[1])
        import _farm
        from temporalio.client import Client

        def refuse(*args, **kwargs):
            raise AssertionError("isolated signal probe attempted live farm access")

        Client.connect = refuse
        _farm.load_config = refuse
        _farm.FIFO_RPC_TIMEOUT_S = 4
        _farm.FIFO_HEARTBEAT_INTERVAL_S = 60
        _farm.STATUS_POLL_INTERVAL_S = 0.002
        _farm._telemetry.info = lambda *args, **kwargs: None
        _farm._telemetry.warn = lambda *args, **kwargs: None
        previous_id = os.environ["HARMONIC_FARM_BUILD_ID"]
        owner = _farm.producer_build("Windows SIGINT test")
        updates = []

        class Control:
            def status(self, state="open"):
                return _farm.BuildStatus(
                    owner.build_id, 7, state, "waiting",
                    (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat(),
                    2, 1,
                )

            async def execute_update(self, name, arg, **options):
                updates.append((name, getattr(arg, "reason", None)))
                assert arg.build_id == owner.build_id
                if name == "register_build":
                    asyncio.get_running_loop().call_later(
                        0.05, signal.raise_signal, signal.SIGINT
                    )
                    if sys.argv[2] == "accepted-reply-pending":
                        # The fake accepted registration, but withholds its reply
                        # until the real producer's cancellation cleanup starts.
                        while not owner._stop.is_set():
                            await asyncio.sleep(0.002)
                    return self.status()
                assert name == "close_build", "signal probe unexpectedly renewed"
                return self.status("closed")

            async def query(self, name, arg, **options):
                assert name == "build_status"
                assert arg == _farm.BuildKey(owner.build_id)
                return self.status()

            async def cancel(self):
                raise AssertionError("local SIGINT cancelled remote work")

        control = Control()

        class FakeClient:
            async def start_workflow(self, name, **options):
                assert name == _farm.WORKFLOW_BUILD_FIFO, "signal probe started a leaf"
                assert options["id"] == _farm.WORKFLOW_BUILD_FIFO_ID
                return control

            def get_workflow_handle(self, workflow_id, **options):
                assert workflow_id == _farm.WORKFLOW_BUILD_FIFO_ID
                assert options == {}
                return control

        async def connect(identity):
            return FakeClient()

        _farm._connect_client = connect
        entered = False
        interrupted = False
        try:
            with owner:
                entered = True
        except KeyboardInterrupt:
            interrupted = True
        print(json.dumps({
            "entered": entered,
            "interrupted": interrupted,
            "updates": updates,
            "thread_alive": owner._thread.is_alive(),
            "restored": os.environ.get("HARMONIC_FARM_BUILD_ID") == previous_id,
            "build_id": owner.build_id,
        }))
        """
    )
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            source,
            str(REPO_ROOT / "cad" / "scripts"),
            registration,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=WAIT_S + 5,
    )
    outcome = json.loads(child.stdout)
    assert outcome["interrupted"]
    assert not outcome["entered"], "cancelled waiting build entered the scheduler"
    assert not outcome["thread_alive"], "cancelled producer left a renewal thread"
    assert outcome["restored"]
    assert outcome["updates"] == [["register_build", None], ["close_build", "cancelled"]]
    assert json.loads((_guarded_process[0] / "build.json").read_text("utf-8")) == {
        "build_id": outcome["build_id"], "farm_run": FARM_RUN,
    }
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID


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


@pytest.mark.parametrize("fault", ["lost-reply", "frontend-unavailable", "update-timeout"])
def test_transient_heartbeat_retries_same_lease_sequence_and_update_id(
    control, start_parent, _guarded_process, fault
):
    first_deadline = control.lease_deadline
    attempts = []
    from temporalio.client import WorkflowUpdateRPCTimeoutOrCancelledError
    from temporalio.service import RPCError, RPCStatusCode

    outage = {
        "lost-reply": TimeoutError("accepted heartbeat reply lost"),
        "frontend-unavailable": RPCError("frontend restarting", RPCStatusCode.UNAVAILABLE, b""),
        "update-timeout": WorkflowUpdateRPCTimeoutOrCancelledError(),
    }[fault]

    def heartbeat_response(status):
        attempts.append(status)
        if len(attempts) == 1:
            # The server accepted the renewal; only its reply was lost.
            control.lease_deadline = _deadline(120)
            raise outage
        return control.status()

    control.heartbeat_response = heartbeat_response
    control.heartbeat_gate = _AsyncGate()
    control.heartbeat_gate_sequence = 2
    parent = start_parent()
    _wait(parent.entered, "producer did not enter action")
    _wait(control.heartbeat_gate.entered, "recovered producer did not send next heartbeat")

    heartbeats = control.calls("heartbeat_build")
    assert [heartbeat.sequence for heartbeat, _options in heartbeats] == [1, 1, 2]
    assert heartbeats[0] == heartbeats[1], "retry changed uncertain heartbeat identity"
    assert control.lease_deadline != first_deadline
    assert parent.ownership._lease_wall == datetime.fromisoformat(control.lease_deadline)
    assert parent.ownership._failure is None
    assert not _guarded_process[1].is_set()
    assert len(control.calls("register_build")) == 1
    assert control.calls("close_build") == []

    control.heartbeat_gate.release()
    parent.finish()
    assert parent.errors == []
    _assert_close(control, parent.ownership.build_id, "finished")


@pytest.mark.parametrize("fault", ["connection", "frontend-unavailable"])
def test_transient_waiting_status_query_retries_without_new_registration_or_lease(
    control, start_parent, _guarded_process, fault
):
    control.active.clear()
    original_deadline = control.lease_deadline
    attempts = []
    from temporalio.service import RPCError, RPCStatusCode

    outage = (
        ConnectionError("temporary frontend outage") if fault == "connection"
        else RPCError("frontend restarting", RPCStatusCode.UNAVAILABLE, b"")
    )

    def query_response(status):
        attempts.append(status)
        if len(attempts) == 1:
            raise outage
        control.active.set()
        return control.status()

    control.query_response = query_response
    control.heartbeat_gate = _AsyncGate()
    parent = start_parent()
    _wait(parent.entered, "recovered waiting query did not activate producer")
    _wait(control.heartbeat_gate.entered, "active producer did not begin renewal")

    assert len(control.queries) == 2
    assert control.queries[0] == control.queries[1]
    assert control.lease_deadline == original_deadline
    assert parent.ownership._lease_wall == datetime.fromisoformat(original_deadline)
    assert len(control.calls("register_build")) == 1
    assert parent.ownership._failure is None
    assert not _guarded_process[1].is_set()

    control.heartbeat_gate.release()
    parent.finish()
    assert parent.errors == []
    _assert_close(control, parent.ownership.build_id, "finished")


@pytest.mark.parametrize(
    ("success", "action_error", "reason"),
    [
        (True, None, "finished"),
        (False, None, "failed"),
        (True, RuntimeError("artifact restore failed"), "failed"),
        (True, KeyboardInterrupt("parent cancelled"), "cancelled"),
    ],
)
def test_close_transport_failure_warns_without_replacing_local_outcome(
    control, start_parent, _guarded_process, success, action_error, reason
):
    control.close_response = ConnectionError("final close unavailable")
    parent = start_parent()
    _wait(parent.entered, "producer did not enter action")
    parent.success = success
    parent.action_error = action_error
    parent.finish()

    assert parent.errors == ([] if action_error is None else [action_error])
    assert parent.ownership._failure is None
    assert not _guarded_process[1].is_set()
    _assert_close(control, parent.ownership.build_id, reason)
    [(warning, fields)] = control.warnings
    assert "final close unavailable" in warning
    assert "producer lease will expire" in warning
    assert fields == {"build_id": parent.ownership.build_id}


def test_close_transport_warning_cannot_mask_prior_ownership_loss(
    control, start_parent, _guarded_process
):
    control.close_response = ConnectionError("final close unavailable")
    control.heartbeat_gate = _AsyncGate()
    control.heartbeat_response = lambda status: replace(status, producer_state="closed")
    parent = start_parent()
    _wait(parent.entered, "producer did not enter action")
    _wait(control.heartbeat_gate.entered, "heartbeat did not reach fake boundary")
    control.heartbeat_gate.release()
    _wait(_guarded_process[1], "refused ownership did not interrupt parent")
    prior_failure = parent.ownership._failure
    parent.finish()

    assert len(parent.errors) == 1
    assert isinstance(parent.errors[0], _farm.BuildOwnershipError)
    assert parent.errors[0].__cause__ is prior_failure
    assert "coordinator refused" in str(prior_failure)
    _assert_close(control, parent.ownership.build_id, "failed")
    assert len(control.warnings) == 1


@pytest.mark.parametrize(
    "fault",
    ["lease-expiring-outage", "update-refusal", "rpc-refusal", "closed", "expired",
     "past-deadline", "foreign-build", "waiting", "drained"],
)
def test_active_renewal_fault_fails_closed_and_interrupts_only_mocked_parent(
    control, start_parent, _guarded_process, fault
):
    # Gate the first renewal until local execution has actually started.
    control.heartbeat_gate = _AsyncGate()
    if fault == "lease-expiring-outage":
        control.lease_deadline = _deadline(0.5)
    parent = start_parent()
    _wait(parent.entered, "producer did not enter action")
    _wait(control.heartbeat_gate.entered, "heartbeat did not reach fake boundary")
    if fault == "lease-expiring-outage":
        control.heartbeat_response = ConnectionError("control unavailable")
    elif fault == "update-refusal":
        from temporalio.client import WorkflowUpdateFailedError
        from temporalio.exceptions import ApplicationError

        control.heartbeat_response = WorkflowUpdateFailedError(
            cause=ApplicationError("ownership explicitly refused", non_retryable=True)
        )
    elif fault == "rpc-refusal":
        from temporalio.service import RPCError, RPCStatusCode

        control.heartbeat_response = RPCError("unauthorized", RPCStatusCode.UNAUTHENTICATED, b"")
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
    heartbeats = control.calls("heartbeat_build")
    if fault == "lease-expiring-outage":
        assert len(heartbeats) > 1, "an outage must retry while its lease remains valid"
        assert {heartbeat.sequence for heartbeat, _options in heartbeats} == {1}
        assert len({options["id"] for _heartbeat, options in heartbeats}) == 1
        assert "acknowledged lease expired" in str(parent.errors[0].__cause__)
    else:
        assert len(heartbeats) == 1, "an explicit refusal is not a transient outage"
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


@pytest.mark.parametrize("action_succeeds", [True, False])
def test_real_build_wrapper_preserves_command_exit_on_unacknowledged_close(
    control, monkeypatch, action_succeeds
):
    monkeypatch.setattr(build, "_farm_preflight", lambda: None)
    executed = []

    def action():
        executed.append(os.environ["HARMONIC_FARM_BUILD_ID"])
        return action_succeeds

    _install_serial_build(monkeypatch, action)
    arguments = ["--executor", "farm", "--display-name", DISPLAY_NAME, "local_gap"]
    baseline = build.main(arguments)
    assert (baseline == 0) is action_succeeds
    [(baseline_registration, _options)] = control.calls("register_build")
    reason = "finished" if action_succeeds else "failed"
    _assert_close(control, baseline_registration.build_id, reason)
    assert control.warnings == []
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID

    control.close_response = TimeoutError("close reply lost")
    result = build.main(arguments)

    assert result == baseline, "an unacknowledged close replaced the runner's actual exit"
    registrations = [registration for registration, _options in control.calls("register_build")]
    assert len(registrations) == 2
    assert registrations[0].build_id != registrations[1].build_id
    assert executed == [registration.build_id for registration in registrations]
    assert [close for close, _options in control.calls("close_build")] == [
        _farm.CloseBuild(registration.build_id, reason) for registration in registrations
    ]
    assert control.cancellations == []
    [(warning, fields)] = control.warnings
    assert "close reply lost" in warning
    assert fields == {"build_id": registrations[1].build_id}
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == INHERITED_BUILD_ID


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


class _LeafControl:
    """Accepted reservation and exact result behind the real dispatch RPC helpers."""

    def __init__(self, requests):
        self.requests = requests
        self.request = _farm.LeafRequest(
            farm_protocol_version=5,
            commit="c" * 40,
            task="part:pen_rod",
            cache_key="k" * 64,
            traceparent=None,
            submitter="test@submitter",
            build_id=INHERITED_BUILD_ID,
        )
        self.workflow_id = _farm.workflow_id(
            self.request.task, self.request.cache_key, self.request.commit, 900
        )
        self.key = _farm.LeafKey(self.request.build_id, self.workflow_id)
        self.binding = _farm.LeafBinding(self.request.build_id, self.workflow_id, "exact-run")
        self.reserved = _farm.LeafStatus(self.key, "reserved", None, [])
        self.bound = _farm.LeafStatus(self.key, "bound", self.binding, [])
        self.result_value = _farm.LeafResult(
            "succeeded", 0, "test-worker", 1, True, "test/log", None, None
        )
        self.updates = []
        self.queries = []
        self.starts = []
        self.handles = []
        self.cancellations = []
        self.start_error = None
        self.responses = []
        self.fallback = self.bound
        self.query_hook = None
        self.result_reads = 0

    async def connect(self, identity):
        assert identity == self.request.submitter
        return _LeafClient(self)

    async def execute_update(self, name, arg, **options):
        assert name == "submit_leaf"
        assert arg == _farm.SubmitLeaf(self.request, FARM_RUN)
        assert options["result_type"] is _farm.LeafStatus
        assert options["rpc_timeout"] == timedelta(seconds=_farm.FIFO_RPC_TIMEOUT_S)
        assert options["id"] == "fifo:" + hashlib.sha256(
            f"submit:{self.key.build_id}:{self.key.workflow_id}".encode()
        ).hexdigest()
        self.updates.append((name, arg, options))
        records = [json.loads(path.read_text("utf-8")) for path in self.requests.iterdir()]
        assert records == [{
            "task": self.request.task, "workflow_id": self.workflow_id,
            "build_id": self.request.build_id, "farm_run": FARM_RUN,
        }]
        return self.reserved

    async def query(self, name, arg, **options):
        assert name == "leaf_status"
        assert arg == self.key
        assert options["result_type"] is _farm.LeafStatus
        assert options["rpc_timeout"] == timedelta(seconds=_farm.FIFO_RPC_TIMEOUT_S)
        self.queries.append((name, arg, options))
        if self.query_hook is not None:
            await self.query_hook()
        response = self.responses.pop(0) if self.responses else self.fallback
        if isinstance(response, BaseException):
            raise response
        return response

    async def result(self, *, follow_runs):
        assert follow_runs is False
        self.result_reads += 1
        return self.result_value

    async def cancel(self):
        self.cancellations.append(True)
        raise AssertionError("consumer cancelled accepted remote work")

    def assert_dispatch_safety(self, *, attached=False):
        assert len(self.updates) == 1, "reconciliation resubmitted accepted work"
        assert len(self.starts) == 1, "consumer restarted a workflow"
        expected = [(_farm.WORKFLOW_BUILD_FIFO_ID, {})]
        if attached:
            expected.append((self.workflow_id, {
                "run_id": self.binding.run_id, "result_type": _farm.LeafResult,
            }))
        assert self.handles == expected
        assert self.cancellations == []
        assert self.result_reads == int(attached)
        assert all(arg is self.queries[0][1] for _name, arg, _options in self.queries)


class _LeafClient(_Client):
    def get_workflow_handle(self, workflow_id, **options):
        if workflow_id == _farm.WORKFLOW_BUILD_FIFO_ID:
            return super().get_workflow_handle(workflow_id, **options)
        self.control.handles.append((workflow_id, options))
        assert workflow_id == self.control.workflow_id
        assert options == {
            "run_id": self.control.binding.run_id, "result_type": _farm.LeafResult,
        }
        return self.control


@pytest.fixture
def leaf_control(_guarded_process, monkeypatch):
    fake = _LeafControl(_guarded_process[0])
    monkeypatch.setattr(_farm, "_connect_client", fake.connect)
    return fake


def test_accepted_unbound_dispatch_keeps_polling_and_local_cancel_preserves_reservation(
    leaf_control
):
    fake = leaf_control
    fake.fallback = fake.reserved

    async def exercise():
        queried_twice = asyncio.Event()
        never_bound = asyncio.Event()

        async def query_hook():
            if len(fake.queries) == 2:
                queried_twice.set()
                await never_bound.wait()

        fake.query_hook = query_hook
        dispatch = asyncio.create_task(_farm._dispatch(fake.request, fake.workflow_id))
        try:
            await asyncio.wait_for(queried_twice.wait(), timeout=WAIT_S)
            assert not dispatch.done()
            fake.assert_dispatch_safety()
        finally:
            dispatch.cancel()
            with pytest.raises(asyncio.CancelledError):
                await dispatch

    asyncio.run(exercise())
    fake.assert_dispatch_safety()
    assert len(fake.queries) == 2


def test_healthy_reserved_reads_have_no_total_startup_deadline(leaf_control, monkeypatch):
    fake = leaf_control
    monkeypatch.setattr(_farm, "FIFO_LEAF_STATUS_RETRY_S", 0.05)
    monkeypatch.setattr(_farm, "STATUS_POLL_INTERVAL_S", 0.05)
    fake.responses = [fake.reserved, fake.reserved, fake.reserved, fake.bound]

    async def exercise():
        return await asyncio.wait_for(
            _farm._dispatch(fake.request, fake.workflow_id), timeout=WAIT_S
        )

    result = asyncio.run(exercise())

    assert result is fake.result_value
    assert len(fake.queries) == 4
    fake.assert_dispatch_safety(attached=True)


@pytest.mark.parametrize(
    "fault",
    ["timeout", "connection", "CANCELLED", "UNKNOWN", "DEADLINE_EXCEEDED",
     "RESOURCE_EXHAUSTED", "ABORTED", "INTERNAL", "UNAVAILABLE"],
)
def test_reserved_leaf_transient_reads_recover_the_exact_result_without_resubmission(
    leaf_control, fault
):
    from temporalio.service import RPCError, RPCStatusCode

    fake = leaf_control
    if fault == "timeout":
        outage = TimeoutError("accepted leaf status reply lost")
    elif fault == "connection":
        outage = ConnectionError("temporary connection loss")
    else:
        outage = RPCError("temporary frontend failure", getattr(RPCStatusCode, fault), b"")
    fake.responses = [outage, outage, fake.reserved, outage, fake.bound]

    result = asyncio.run(_farm._dispatch(fake.request, fake.workflow_id))

    assert result is fake.result_value
    assert len(fake.queries) == 5
    fake.assert_dispatch_safety(attached=True)


@pytest.mark.parametrize(
    "fault",
    ["foreign-key", "foreign-build", "foreign-workflow", "empty-run", "recovery",
     "bound-error", "reserved-error", "invalid-state", "closed-unbound",
     "UNAUTHENTICATED", "PERMISSION_DENIED", "NOT_FOUND", "INVALID_ARGUMENT",
     "ownership-error", "query-error"],
)
def test_reserved_leaf_reconciliation_never_retries_definitive_errors_after_an_outage(
    leaf_control, fault
):
    from temporalio.service import RPCError, RPCStatusCode

    fake = leaf_control
    if fault in {"UNAUTHENTICATED", "PERMISSION_DENIED", "NOT_FOUND", "INVALID_ARGUMENT"}:
        refusal = RPCError("definitive query refusal", getattr(RPCStatusCode, fault), b"")
        expected_type, expected_message = RPCError, "definitive query refusal"
    elif fault in {"ownership-error", "query-error"}:
        expected_type = _farm.BuildOwnershipError if fault == "ownership-error" else RuntimeError
        expected_message = "definitive refusal"
        refusal = expected_type(expected_message)
    else:
        expected_type = _farm.BuildOwnershipError
        if fault == "foreign-key":
            refusal = replace(fake.bound, key=replace(fake.key, build_id="foreign"))
            expected_message = "foreign leaf reservation"
        elif fault in {"foreign-build", "foreign-workflow", "empty-run"}:
            changes = {
                "foreign-build": {"build_id": "foreign"},
                "foreign-workflow": {"workflow_id": "foreign"},
                "empty-run": {"run_id": ""},
            }[fault]
            refusal = replace(fake.bound, binding=replace(fake.binding, **changes))
            expected_message = "foreign leaf binding"
        elif fault in {"recovery", "bound-error", "reserved-error"}:
            status = fake.bound if fault == "bound-error" else fake.reserved
            refusal = replace(
                status,
                state="recovery_required" if fault == "recovery" else status.state,
                error_code=None if fault == "recovery" else "fifo_observation_failed",
                error="history needs operator evidence",
            )
            expected_message = "operator recovery"
        elif fault == "invalid-state":
            refusal = replace(fake.bound, state="not-a-reservation-state")
            expected_message = "invalid leaf reservation state"
        else:
            refusal = replace(fake.reserved, state="missing_closed")
            expected_message = "closed without a proven run binding"
    fake.responses = [ConnectionError("temporary outage"), refusal]

    with pytest.raises(expected_type, match=expected_message) as error:
        asyncio.run(_farm._dispatch(fake.request, fake.workflow_id))

    if isinstance(refusal, BaseException):
        assert error.value is refusal
    assert len(fake.queries) == 2, "definitive status or refusal was retried"
    fake.assert_dispatch_safety()


@pytest.mark.parametrize("outage", ["repeated-failure", "hung-query"])
def test_reserved_leaf_read_outage_budget_bounds_retries_and_inflight_query(
    leaf_control, monkeypatch, outage
):
    fake = leaf_control
    gate = _AsyncGate()
    monkeypatch.setattr(_farm, "FIFO_LEAF_STATUS_RETRY_S", 0.05)
    monkeypatch.setattr(_farm, "FIFO_RPC_TIMEOUT_S", 4)
    if outage == "hung-query":
        fake.query_hook = gate.wait
    else:
        fake.fallback = ConnectionError("frontend remains unavailable")

    async def exercise():
        with pytest.raises(TimeoutError, match="accepted work remains under the coordinator"):
            # This outer bound makes a missing independent budget fail quickly.
            await asyncio.wait_for(
                _farm._dispatch(fake.request, fake.workflow_id), timeout=1
            )

    asyncio.run(exercise())
    if outage == "hung-query":
        assert gate.entered.is_set()
        assert gate.cancelled.is_set(), "in-progress read exceeded its monotonic budget"
        assert not gate.released.is_set()
        assert len(fake.queries) == 1
    else:
        assert len(fake.queries) > 1
    fake.assert_dispatch_safety()


def test_reserved_leaf_query_cancellation_propagates_without_read_retry(leaf_control):
    fake = leaf_control
    cancellation = asyncio.CancelledError("local action cancelled")
    fake.responses = [ConnectionError("temporary outage"), cancellation]

    with pytest.raises(asyncio.CancelledError, match="local action cancelled"):
        asyncio.run(_farm._dispatch(fake.request, fake.workflow_id))

    assert len(fake.queries) == 2
    fake.assert_dispatch_safety()
