"""Machine-wide slots for the SolidWorks-free local subprocesses of a build.

``dodo._run`` is the one chokepoint for every task that runs a local
SolidWorks-free subprocess (all ``check:*`` gates, ``gallery``, the publishing
half of ``release``). Under ``--executor farm`` doit's worker count is sized for
farm leaves, which are I/O-bound waits on the pool, not for local CPU work; so
``-n`` no longer bounds how many pytest/Blender processes a build starts on this
machine. These slots do: at most ``HARMONIC_LOCAL_SLOTS`` (default 4) such
subprocesses run at once across every doit invocation and worktree on the
machine, whatever ``-n`` and the parallel type are.

Each slot is an exclusive OS file lock (``filelock``), so a killed holder frees
its slot at once and there is no stale-lock cleanup. The locks live next to the
COM seat lock (``%PROGRAMDATA%/harmonic-analyzer``; ``HARMONIC_LOCAL_SLOT_DIR``
overrides). A holder writes ``slot-<i>.holder.json`` beside its lock so a waiter
can name who it is queued behind.

Nesting cannot deadlock: the holder's identity rides into the subprocess
environment as ``HARMONIC_LOCAL_SLOT`` (``held_env``), and a process that
inherits it runs its own ``_run`` calls inside the parent's slot instead of
queueing for a second one (a ``check:*`` pytest run that itself exercises
``_run`` would otherwise wait on the slot its own parent holds).

These are NOT the agent guard slots of ``C:/src/dt-logs/guards/suite_slot.py``:
that wrapper admits whole commands (a full offline suite, a batch of gates) into
its own lock set before they start. A build running inside a suite slot still
takes these slots for its ``check:*`` fan-out, and a build outside any suite
slot competes only here, so the two sets can stack; each bounds its own layer.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import os
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

from filelock import FileLock, Timeout

import _telemetry

SLOTS_ENV = "HARMONIC_LOCAL_SLOTS"
DIR_ENV = "HARMONIC_LOCAL_SLOT_DIR"
HELD_ENV = "HARMONIC_LOCAL_SLOT"
DEFAULT_SLOTS = 4
POLL_S = 0.5
REPORT_S = 30.0

_held: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "harmonic_local_slot", default=None
)


def slot_count() -> int:
    raw = os.environ.get(SLOTS_ENV, "").strip()
    if not raw:
        return DEFAULT_SLOTS
    try:
        count = int(raw)
    except ValueError:
        raise RuntimeError(f"{SLOTS_ENV} is not an integer: {raw!r}") from None
    if count < 1:
        raise RuntimeError(f"{SLOTS_ENV} must be at least 1, got {count}")
    return count


def slot_dir() -> Path:
    override = os.environ.get(DIR_ENV)
    if override:
        return Path(override)
    base = os.environ.get("PROGRAMDATA") or tempfile.gettempdir()
    return Path(base) / "harmonic-analyzer" / "local-slots"


def _holder_path(directory: Path, index: int) -> Path:
    return directory / f"slot-{index}.holder.json"


def holders(directory: Path | None = None, count: int | None = None) -> list[dict]:
    """The recorded holder of every occupied slot (best-effort, for diagnostics)."""
    directory = directory or slot_dir()
    found = []
    for index in range(count or slot_count()):
        try:
            found.append(
                json.loads(_holder_path(directory, index).read_text(encoding="utf-8"))
            )
        except (OSError, ValueError):
            continue
    return found


def _try_acquire(directory: Path, count: int) -> tuple[int, FileLock] | None:
    for index in range(count):
        lock = FileLock(str(directory / f"slot-{index}.lock"))
        try:
            lock.acquire(timeout=0)
        except Timeout:
            continue
        return index, lock
    return None


def _describe(entries: list[dict]) -> list[str]:
    return [
        f"{entry.get('label', '?')} pid={entry.get('pid', '?')} "
        f"({entry.get('worktree', '?')})"
        for entry in entries
    ]


def held_env() -> dict[str, str]:
    """Environment a subprocess inherits so its own ``_run`` calls reuse this slot."""
    holder = _held.get()
    return {HELD_ENV: holder} if holder else {}


@contextlib.contextmanager
def local_slot(label: str) -> Iterator[float | None]:
    """Hold one machine-wide local slot for ``label``; yields the seconds waited.

    Yields ``None`` without taking a slot when this thread or a parent process
    already holds one (see the module docstring on nesting). The wait is its own
    ``local.slot.wait <label>`` span on the ``build-infra`` resource, a sibling
    of the task span it precedes, carrying the holders it queued behind.
    """
    if _held.get() or os.environ.get(HELD_ENV):
        yield None
        return

    directory = slot_dir()
    directory.mkdir(parents=True, exist_ok=True)
    count = slot_count()
    entered = time.monotonic()
    with _telemetry.span(
        f"local.slot.wait {label}",
        label=label,
        slots=count,
        service=_telemetry.BUILD_INFRA_SERVICE,
    ) as wait_span:
        acquired = _try_acquire(directory, count)
        if acquired is None:
            queued_behind = _describe(holders(directory, count))
            wait_span.set_attribute("holders", queued_behind)
            _telemetry.debug(
                f"[local.slot] {label} waiting for one of {count} local slots"
                + (f" (held by {'; '.join(queued_behind)})" if queued_behind else "")
            )
            reported = time.monotonic()
            while acquired is None:
                time.sleep(POLL_S)
                acquired = _try_acquire(directory, count)
                if acquired is None and time.monotonic() - reported >= REPORT_S:
                    reported = time.monotonic()
                    _telemetry.debug(
                        f"[local.slot] {label} still waiting; held by "
                        + "; ".join(_describe(holders(directory, count)))
                    )
        index, lock = acquired
        waited = time.monotonic() - entered
        wait_span.set_attribute("slot", index)
        wait_span.set_attribute("wait_s", round(waited, 3))

    holder = f"{label} pid={os.getpid()} slot={index}"
    record = _holder_path(directory, index)
    with contextlib.suppress(OSError):
        record.write_text(
            json.dumps(
                {
                    "label": label,
                    "pid": os.getpid(),
                    "thread": threading.current_thread().name,
                    "worktree": str(Path.cwd()),
                    "slot": index,
                    "since": time.time(),
                }
            ),
            encoding="utf-8",
        )
    token = _held.set(holder)
    try:
        yield waited
    finally:
        _held.reset(token)
        with contextlib.suppress(OSError):
            record.unlink()
        lock.release()
