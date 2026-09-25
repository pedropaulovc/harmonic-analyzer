"""Farm fan-out: every ready leaf reaches the pool at once, slowest first, while
the SolidWorks-free local work stays inside the machine-wide local slots."""

import asyncio
import contextlib
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from doit.cmd_base import ModuleTaskLoader

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "cad" / "scripts"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS))

import _farm  # noqa: E402
import _farm_order  # noqa: E402
import _local_slot  # noqa: E402
import build  # noqa: E402

SHA = "c" * 40
TOKEN = "eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJzdWJtaXR0ZXItdGVzdCJ9.c2ln"
LEAVES = ("a", "b", "c", "d", "e", "f")


# --- the doit side: submission concurrency and order ---------------------------


def _graph(submit):
    """``build`` over six independent part leaves and one local check.

    ``build`` lists them in FIFO order a..f with the local check FIRST, so an
    order other than that is the ready queue's doing, not doit's defaults.
    """

    def task_part():
        for stem in LEAVES:
            yield {
                "name": stem,
                "actions": [(submit, [f"part:{stem}"])],
                "verbosity": 2,
            }

    def task_check():
        yield {"name": "x", "actions": [(submit, ["check:x"])], "verbosity": 2}

    def task_build():
        return {
            "actions": None,
            "task_dep": ["check:x", *(f"part:{stem}" for stem in LEAVES)],
        }

    return {"task_part": task_part, "task_check": task_check, "task_build": task_build}


@pytest.fixture
def farm_doit(tmp_path, monkeypatch):
    """``build.main`` under the farm executor on a fixture graph, with the REAL
    doit parallel runner the wrapper chooses; the preflight is faked."""
    seen: list[list[str]] = []
    monkeypatch.setattr(build, "_farm_preflight", lambda: None)
    monkeypatch.delenv("HARMONIC_FARM_PARALLELISM", raising=False)

    def install(namespace):
        config = {
            "GLOBAL": {"backend": "json", "dep_file": str(tmp_path / ".doit.db")}
        }

        class FixtureFarmDoit(build._FarmDoitMain):
            def __init__(self):
                super().__init__(
                    task_loader=ModuleTaskLoader(namespace), extra_config=config
                )

            def run(self, args):
                seen.append(list(args))
                return super().run(args)

        monkeypatch.setattr(build, "_FarmDoitMain", FixtureFarmDoit)

    return install, seen


def test_a_ready_set_of_leaves_is_submitted_without_waiting_on_each_other(farm_doit):
    install, seen = farm_doit
    barrier = threading.Barrier(len(LEAVES), timeout=60)
    submitted: list[str] = []
    stdout = sys.stdout

    def submit(label):
        if not label.startswith("part:"):
            return
        submitted.append(label)
        # Every leaf blocks here until all six are in flight: a runner that
        # waited on one leaf before submitting the next breaks the barrier.
        barrier.wait()

    install(_graph(submit))

    assert build.main(["--executor", "farm", "build"]) == 0

    assert seen == [["-P", "thread", "-n", "16", "build"]]
    assert sorted(submitted) == [f"part:{stem}" for stem in LEAVES]
    assert not barrier.broken
    # doit's per-action stream capture is off, so no action's tee survived it.
    assert sys.stdout is stdout


def test_ready_leaves_go_to_the_farm_slowest_first(farm_doit, tmp_path, monkeypatch):
    install, seen = farm_doit
    ledger = tmp_path / "durations.json"
    # f is unknown: it ranks at the median known duration (50 s), after b,
    # which reached the ready queue first.
    ledger.write_text(
        json.dumps({"part:a": 10, "part:b": 50, "part:c": 600, "part:d": 5, "part:e": 300}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HARMONIC_FARM_DURATIONS", str(ledger))
    monkeypatch.setenv("HARMONIC_FARM_PARALLELISM", "1")
    order: list[str] = []
    install(_graph(lambda label: order.append(label)))

    assert build.main(["--executor", "farm", "build"]) == 0

    assert seen == [["-P", "thread", "-n", "1", "build"]]
    assert order == [
        "part:c",
        "part:e",
        "part:b",
        "part:f",
        "part:a",
        "part:d",
        # local work waits for every farm leaf ahead of it
        "check:x",
    ]


def test_without_a_ledger_leaves_keep_the_order_doit_offered_them(
    farm_doit, tmp_path, monkeypatch
):
    install, _seen = farm_doit
    monkeypatch.setenv("HARMONIC_FARM_DURATIONS", str(tmp_path / "absent.json"))
    monkeypatch.setenv("HARMONIC_FARM_PARALLELISM", "1")
    order: list[str] = []
    install(_graph(lambda label: order.append(label)))

    assert build.main(["--executor", "farm", "build"]) == 0

    assert order == [*(f"part:{stem}" for stem in LEAVES), "check:x"]


def test_the_ready_queue_is_only_replaced_inside_the_farm_run():
    from doit.control import TaskDispatcher

    original = TaskDispatcher.__init__
    with _farm_order.installed({}):
        assert TaskDispatcher.__init__ is not original
    assert TaskDispatcher.__init__ is original


def test_the_ledger_folds_observations_and_survives_garbage(tmp_path):
    ledger = tmp_path / "durations.json"
    _farm_order.record("part:a", 100, ledger)
    _farm_order.record("part:a", 300, ledger)
    assert _farm_order.load(ledger) == {"part:a": 200.0}

    # a leaf the worker restored in seconds says nothing about its build time
    _farm_order.record("part:a", 5, ledger)
    assert _farm_order.load(ledger) == {"part:a": 200.0}

    ledger.write_text("{not json", encoding="utf-8")
    assert _farm_order.load(ledger) == {}
    _farm_order.record("part:b", 7, ledger)
    assert _farm_order.load(ledger) == {"part:b": 7.0}


# --- scheduling never reaches a cache key --------------------------------------


def _build_scripts():
    return sorted(
        [*SCRIPTS.glob("build_*.py"), *SCRIPTS.glob("draw_*.py")],
        key=lambda path: path.name,
    )


def test_no_build_script_imports_the_scheduling_modules():
    """A module in a build script's import closure is folded into its recipe
    digest, so scheduling code there would re-key the fleet on every tweak."""
    from _buildgraph import module_deps_of

    scheduling = {"_farm_order.py", "_local_slot.py", "_farm.py"}
    offenders = {
        script.name: sorted(scheduling & {Path(dep).name for dep in module_deps_of(script)})
        for script in _build_scripts()
    }
    assert {name: deps for name, deps in offenders.items() if deps} == {}


def _load_dodo():
    """Load dodo without leaking its process-wide doit patches into other tests."""
    import importlib.util

    from doit.dependency import CHECKERS, Dependency, JsonDB

    save_success = Dependency.save_success
    json_dump = JsonDB.dump
    missing = object()
    content_checker = CHECKERS.get("content", missing)
    try:
        spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        Dependency.save_success = save_success
        JsonDB.dump = json_dump
        if content_checker is missing:
            CHECKERS.pop("content", None)
        else:
            CHECKERS["content"] = content_checker


@pytest.fixture(scope="module")
def dodo():
    return _load_dodo()


def test_the_duration_ledger_never_moves_a_cache_key(dodo, tmp_path, monkeypatch):
    stem = "pen_rod"
    script = SCRIPTS / f"build_{stem}.py"

    def key_under(ledger_body):
        ledger = tmp_path / f"ledger-{len(ledger_body)}.json"
        ledger.write_text(json.dumps(ledger_body), encoding="utf-8")
        monkeypatch.setenv("HARMONIC_FARM_DURATIONS", str(ledger))
        deps = dodo._part_file_deps(script, stem)
        assert not any("farm-durations" in dep for dep in deps)
        return dodo._cache_key(deps, f"part:{stem}")

    assert key_under({}) == key_under({f"part:{stem}": 9999.0, "part:x": 1.0})


def test_the_seat_refuses_a_worker_thread_by_name(dodo):
    failures = []

    def take_seat():
        try:
            with dodo._com_seat("part:pen_rod"):
                failures.append("seat taken")
        except RuntimeError as problem:
            failures.append(str(problem))

    worker = threading.Thread(target=take_seat, name="doit-worker-3")
    worker.start()
    worker.join(60)

    [message] = failures
    assert message.startswith("part:pen_rod: the SolidWorks seat was requested")
    assert "doit-worker-3" in message


def test_run_holds_a_local_slot_around_its_subprocess(dodo, slots, monkeypatch):
    seen = []

    def fake_exec(cmd, label, log_stem=None, *, task=None):
        seen.append((label, _local_slot.held_env()))

    monkeypatch.setattr(dodo, "_exec", fake_exec)

    dodo._run(["python", "-c", "pass"], "check math")

    [(label, env)] = seen
    assert label == "check math"
    assert env[_local_slot.HELD_ENV].startswith("check math pid=")


# --- local slots ---------------------------------------------------------------


@pytest.fixture
def slots(tmp_path, monkeypatch):
    directory = tmp_path / "slots"
    monkeypatch.setenv("HARMONIC_LOCAL_SLOT_DIR", str(directory))
    monkeypatch.setenv("HARMONIC_LOCAL_SLOTS", "2")
    monkeypatch.delenv("HARMONIC_LOCAL_SLOT", raising=False)
    return directory


def test_local_work_in_threads_never_exceeds_the_slots(slots):
    active = 0
    peak = 0
    lock = threading.Lock()
    waits = []

    def work(index):
        nonlocal active, peak
        with _local_slot.local_slot(f"check:{index}") as waited:
            waits.append(waited)
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.2)
            with lock:
                active -= 1

    workers = [threading.Thread(target=work, args=(i,)) for i in range(6)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=120)

    assert peak == 2
    assert len(waits) == 6 and all(w is not None for w in waits)
    assert _local_slot.holders(slots, 2) == []


_SLOT_CHILD = """
import sys, time
sys.path.insert(0, sys.argv[1])
import _local_slot
with _local_slot.local_slot("check:" + sys.argv[3]):
    with open(sys.argv[2], "a", encoding="utf-8") as log:
        log.write(f"+ {time.time()}\\n")
    time.sleep(0.5)
    with open(sys.argv[2], "a", encoding="utf-8") as log:
        log.write(f"- {time.time()}\\n")
"""


def test_local_work_in_separate_processes_never_exceeds_the_slots(slots, tmp_path):
    child = tmp_path / "slot_child.py"
    child.write_text(_SLOT_CHILD, encoding="utf-8")
    log = tmp_path / "slot.log"
    processes = [
        subprocess.Popen(
            [sys.executable, str(child), str(SCRIPTS), str(log), str(index)],
            env=os.environ.copy(),
        )
        for index in range(5)
    ]
    for process in processes:
        assert process.wait(timeout=300) == 0

    active = peak = 0
    events = sorted(
        (float(stamp), sign)
        for sign, stamp in (line.split() for line in log.read_text().splitlines())
    )
    for _stamp, sign in events:
        active += 1 if sign == "+" else -1
        peak = max(peak, active)
    assert len(events) == 10
    assert peak <= 2


def test_a_nested_run_reuses_its_parents_slot_instead_of_deadlocking(
    slots, monkeypatch, tmp_path
):
    monkeypatch.setenv("HARMONIC_LOCAL_SLOTS", "1")
    child = tmp_path / "slot_child.py"
    child.write_text(_SLOT_CHILD, encoding="utf-8")
    with _local_slot.local_slot("check:parent") as waited:
        assert waited is not None
        env = {**os.environ, **_local_slot.held_env()}
        assert env[_local_slot.HELD_ENV].startswith("check:parent")
        # The only slot is ours; the child must not queue for it.
        completed = subprocess.run(
            [sys.executable, str(child), str(SCRIPTS), str(tmp_path / "n.log"), "n"],
            env=env,
            timeout=120,
        )
        assert completed.returncode == 0
        # and a nested call in this thread reuses it too
        with _local_slot.local_slot("check:inner") as inner:
            assert inner is None
    assert _local_slot.held_env() == {}


def test_a_waiter_names_the_holder_it_queued_behind(slots, monkeypatch):
    monkeypatch.setenv("HARMONIC_LOCAL_SLOTS", "1")
    spans = []

    class Span:
        def __init__(self, name, attrs):
            self.name, self.attrs = name, dict(attrs)

        def set_attribute(self, key, value):
            self.attrs[key] = value

    @contextlib.contextmanager
    def span(name, **attrs):
        record = Span(name, attrs)
        spans.append(record)
        yield record

    monkeypatch.setattr(_local_slot._telemetry, "span", span)
    entered = threading.Event()
    release = threading.Event()

    def holder():
        with _local_slot.local_slot("check:math"):
            entered.set()
            release.wait(60)

    first = threading.Thread(target=holder)
    first.start()
    assert entered.wait(60)
    threading.Timer(1.0, release.set).start()
    with _local_slot.local_slot("check:graph"):
        pass
    first.join(60)

    [waiter] = [s for s in spans if s.name == "local.slot.wait check:graph"]
    assert any(h.startswith("check:math pid=") for h in waiter.attrs["holders"])
    assert waiter.attrs["wait_s"] > 0


def test_a_bad_slot_count_fails_loud(slots, monkeypatch):
    monkeypatch.setenv("HARMONIC_LOCAL_SLOTS", "0")
    with pytest.raises(RuntimeError, match="HARMONIC_LOCAL_SLOTS"):
        with _local_slot.local_slot("check:x"):
            pass


# --- farm.run telemetry ----------------------------------------------------------


def _write_config(tmp_path: Path) -> Path:
    for name in ("ca.pem", "client.pem", "client-key.pem"):
        (tmp_path / name).write_bytes(b"-----BEGIN " + name.encode() + b"-----\n")
    (tmp_path / "token.jwt").write_text(TOKEN + "\n", encoding="ascii")
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "temporal_address": "farm.example.invalid:7233",
                "namespace": "solidworks",
                "ca_cert": "ca.pem",
                "client_cert": "client.pem",
                "client_key": "client-key.pem",
                "token": "token.jwt",
            }
        ),
        encoding="utf-8",
    )
    return path


class _Stamp:
    def __init__(self, when):
        self.when = when

    def ToDatetime(self):  # noqa: N802 -- protobuf Timestamp API
        return self.when


class _Event:
    def __init__(self, event_type, when):
        self.event_type = event_type
        self.event_time = _Stamp(when)


def test_farm_run_records_fan_out_queue_and_worker_time(tmp_path, monkeypatch):
    from temporalio.api.enums.v1 import EventType
    from temporalio.client import Client

    monkeypatch.setenv("SOLIDWORKS_POOL_CONFIG", str(_write_config(tmp_path)))
    monkeypatch.setenv("HARMONIC_FARM_COMMIT", SHA)
    ledger = tmp_path / "durations.json"
    monkeypatch.setenv("HARMONIC_FARM_DURATIONS", str(ledger))
    both_in_flight = threading.Barrier(2, timeout=60)
    t0 = datetime(2026, 9, 25, 16, 0, 0)

    class Handle:
        async def result(self):
            await asyncio.to_thread(both_in_flight.wait)
            return _farm.LeafResult(
                state="succeeded",
                exit_code=0,
                worker_id="sw-01@3",
                attempt=1,
                cache_present=True,
                log_blob=None,
                failure_category=None,
                failure_message=None,
            )

        async def fetch_history_events(self):
            for event_type, offset in (
                (EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED, 0),
                (EventType.EVENT_TYPE_ACTIVITY_TASK_STARTED, 30),
                (EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED, 630),
            ):
                yield _Event(event_type, t0 + timedelta(seconds=offset))

    class FakeClient:
        async def start_workflow(self, *_args, **_kwargs):
            return Handle()

    async def connect(*_args, **_kwargs):
        return FakeClient()

    monkeypatch.setattr(Client, "connect", connect)
    spans = []

    class Span:
        def __init__(self, name):
            self.name, self.attrs = name, {}

        def set_attribute(self, key, value):
            self.attrs[key] = value

    @contextlib.contextmanager
    def span(name, **_attrs):
        record = Span(name)
        spans.append(record)
        yield record

    monkeypatch.setattr(_farm._telemetry, "span", span)
    results = []
    workers = [
        threading.Thread(
            target=lambda stem=stem: results.append(
                _farm.run_leaf(f"part:{stem}", stem * 64)
            )
        )
        for stem in ("a", "b")
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=120)

    assert [r.state for r in results] == ["succeeded", "succeeded"]
    assert sorted(s.attrs["inflight"] for s in spans) == [1, 2]
    for record in spans:
        assert record.attrs["temporal_queue_s"] == 30
        assert record.attrs["worker_run_s"] == 600
        assert record.attrs["submit_s"] >= 0
        assert record.attrs["remote_wait_s"] >= 0
    assert _farm._inflight == 0
    assert _farm_order.load(ledger) == {"part:a": 600.0, "part:b": 600.0}


def test_an_unreadable_history_costs_the_timings_not_the_leaf(tmp_path, monkeypatch):
    from temporalio.client import Client

    monkeypatch.setenv("SOLIDWORKS_POOL_CONFIG", str(_write_config(tmp_path)))
    monkeypatch.setenv("HARMONIC_FARM_COMMIT", SHA)
    ledger = tmp_path / "durations.json"
    monkeypatch.setenv("HARMONIC_FARM_DURATIONS", str(ledger))

    class Handle:
        async def result(self):
            return _farm.LeafResult("succeeded", 0, "sw-01@3", 1, True, None, None, None)

        def fetch_history_events(self):
            raise RuntimeError("history service unavailable")

    class FakeClient:
        async def start_workflow(self, *_args, **_kwargs):
            return Handle()

    async def connect(*_args, **_kwargs):
        return FakeClient()

    monkeypatch.setattr(Client, "connect", connect)

    result = _farm.run_leaf("part:a", "a" * 64)

    assert result.state == "succeeded"
    # the ledger falls back to the submitter's remote wait
    assert set(_farm_order.load(ledger)) == {"part:a"}
