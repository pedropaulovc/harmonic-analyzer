"""Critical-path-first dispatch for ``--executor farm``: scheduling only.

The pool's task queue is served roughly first-in, first-out (per partition,
and per fairness key once fairness is enabled), so the ORDER a run submits its
leaves in matters as much as how many it keeps in flight. W15 (2026-09-25) put ``part:cone_gear`` -- a
643 s leaf on the assembly's critical path -- into the queue 141 s after the run
started, behind leaves that took seconds, and the assembly started that much
later. This module makes the slow leaves go first:

* a machine-wide **duration ledger** (``farm-durations.json`` next to the COM
  seat lock; ``HARMONIC_FARM_DURATIONS`` overrides) that ``_farm.run_leaf``
  updates after every successful leaf with the worker's run time for that task
  label, falling back to the submitter's remote wait;
* ``CriticalFirst``, a drop-in for doit's ``TaskDispatcher.ready`` deque whose
  ``popleft`` returns, among the READY nodes, structural nodes first (actionless
  group tasks such as ``build`` -- popping them early only discovers more
  leaves), then farm-dispatchable leaves slowest-first by ledger, then every
  other task (``check:*`` and the rest of the local work, which queues on the
  machine-wide local slots and must not occupy doit workers the farm leaves
  need). Ties keep doit's own FIFO order, so a leaf the ledger does not know
  keeps the per-seat order ``dodo._seat_part_order`` gave it; an unknown leaf
  ranks at the median known duration.

doit hands a worker whatever ``TaskDispatcher._get_next_node`` pops from
``ready`` (a FIFO deque in stock doit), for the process and the thread runner
alike, so replacing that one container is the whole mechanism. Nothing here is
read by a cache key, a recipe digest or a doit ``file_dep``:
``test_farm_fanout.py`` pins that keys are identical under different ledgers.
"""

from __future__ import annotations

import contextlib
import json
import os
import statistics
import tempfile
from collections import deque
from collections.abc import Iterator, Mapping
from pathlib import Path

from filelock import FileLock, Timeout

LEDGER_ENV = "HARMONIC_FARM_DURATIONS"
# Farm-dispatchable task families: every leaf ``dodo._cached_com_action`` can
# send to the pool. Kept here, not imported from dodo, so the order is
# computable without loading the graph.
FARM_LEAF_PREFIXES = (
    "part:",
    "assembly:",
    "drawing:",
    "verify_soundness:",
    "verify:kinematics",
    "preflight",
    "export",
    "package:release",
)
# Weight of the newest observation in the ledger's running estimate.
_ALPHA = 0.5
# An observation this far under the estimate is a cache hit, not a build.
_CHEAP = 0.25

_STRUCTURAL, _FARM_LEAF, _LOCAL = 2, 1, 0


def ledger_path() -> Path:
    override = os.environ.get(LEDGER_ENV)
    if override:
        return Path(override)
    base = os.environ.get("PROGRAMDATA") or tempfile.gettempdir()
    return Path(base) / "harmonic-analyzer" / "farm-durations.json"


def load(path: Path | None = None) -> dict[str, float]:
    """``{task label: seconds}``; empty when the ledger is absent or unreadable."""
    try:
        data = json.loads((path or ledger_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(label): float(seconds)
        for label, seconds in data.items()
        if isinstance(seconds, (int, float)) and not isinstance(seconds, bool)
    }


def record(label: str, seconds: float, path: Path | None = None) -> None:
    """Fold one observed leaf duration into the ledger (best-effort, atomic).

    The ledger estimates what a leaf costs when it BUILDS. A leaf whose worker
    found its key already published returns in seconds; such an observation
    (under a quarter of the running estimate) is dropped rather than folded in,
    or one cheap run would demote a slow leaf to the back of the next cold run.
    """
    path = path or ledger_path()
    with contextlib.suppress(OSError, Timeout):
        path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(path.with_suffix(".lock")), timeout=10):
            ledger = load(path)
            previous = ledger.get(label)
            if previous is not None and seconds < previous * _CHEAP:
                return
            ledger[label] = round(
                seconds if previous is None else _ALPHA * seconds + (1 - _ALPHA) * previous,
                1,
            )
            staged = path.with_suffix(".tmp")
            staged.write_text(json.dumps(ledger, sort_keys=True, indent=1), encoding="utf-8")
            os.replace(staged, path)


def is_farm_leaf(name: str) -> bool:
    return name.startswith(FARM_LEAF_PREFIXES)


def _tier(task) -> int:
    if not task.actions:
        return _STRUCTURAL
    if is_farm_leaf(task.name):
        return _FARM_LEAF
    return _LOCAL


class CriticalFirst(deque):
    """doit's ready queue, popping the most urgent ready node instead of the oldest."""

    def __init__(self, durations: Mapping[str, float], iterable=()):
        super().__init__(iterable)
        self.durations = dict(durations)
        self.unknown = (
            statistics.median(self.durations.values()) if self.durations else 0.0
        )

    def _rank(self, node) -> tuple[int, float]:
        task = node.task
        tier = _tier(task)
        if tier != _FARM_LEAF:
            return tier, 0.0
        return tier, self.durations.get(task.name, self.unknown)

    def popleft(self):
        if not self:
            raise IndexError("pop from an empty deque")
        best = 0
        best_rank = self._rank(self[0])
        for index in range(1, len(self)):
            rank = self._rank(self[index])
            if rank > best_rank:  # strict: ties keep FIFO order
                best, best_rank = index, rank
        node = self[best]
        del self[best]
        return node


@contextlib.contextmanager
def installed(durations: Mapping[str, float] | None = None) -> Iterator[None]:
    """Give every doit ``TaskDispatcher`` built inside this block a ``CriticalFirst``."""
    from doit.control import TaskDispatcher

    durations = load() if durations is None else durations
    original = TaskDispatcher.__init__

    def __init__(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.ready = CriticalFirst(durations, self.ready)

    TaskDispatcher.__init__ = __init__
    try:
        yield
    finally:
        TaskDispatcher.__init__ = original
