"""The doit graph load -- the ``dodo`` import plus every ``task_*`` generator --
recorded as one ``doit.load`` span.

That load is pure CPU that runs before any task span opens: measured at 16-28 s
of every farm leaf (worker ``execute`` minus the leaf's ``task`` span), paid again
by every submitter command, with nothing in the trace to say so.

``dodo`` stamps its own first line (:class:`LoadStamp`) and calls
:func:`install`, which wraps doit's ``DodoTaskLoader.load_tasks`` once per
process. The wrapper finds the stamp in the namespace it just loaded, so
``python -m doit``, ``build.py`` and a farm leaf's ``build.py run -n 0 <task>``
all emit the span from this one place and none of them can emit it twice.

The span is back-dated with OTel's creation-time ``start_time`` (as
``proc.startup`` is): ``_telemetry`` is importable only once dodo has put
``cad/scripts`` on the path. It lands on the ``build-infra`` resource -- graph
loading is no pipeline stage's work. Best-effort: telemetry can never fail the
load.
"""

from __future__ import annotations

import functools
import sys
import time

from doit.cmd_base import DodoTaskLoader

STAMP_NAME = "_DOIT_LOAD"


class LoadStamp:
    """One graph load's start, taken once: a cached ``dodo`` module that doit
    loads again in the same process never reports a load from its stale import."""

    def __init__(self, started_ns: int) -> None:
        self._started_ns: int | None = started_ns

    def take(self) -> int | None:
        started, self._started_ns = self._started_ns, None
        return started


def install() -> None:
    """Wrap ``DodoTaskLoader.load_tasks`` (idempotent). A namespace without a
    :data:`STAMP_NAME` stamp -- any other dodo file -- loads untouched."""
    original = DodoTaskLoader.load_tasks
    if getattr(original, "_records_doit_load", False):
        return

    @functools.wraps(original)
    def load_tasks(self, cmd, pos_args):
        tasks = original(self, cmd, pos_args)
        stamp = getattr(self, "namespace", {}).get(STAMP_NAME)
        if hasattr(stamp, "take"):
            record(
                stamp.take(),
                command=cmd.get_name() if hasattr(cmd, "get_name") else str(cmd),
                targets=list(pos_args or ()),
                task_names={task.name for task in tasks},
            )
        return tasks

    load_tasks._records_doit_load = True
    DodoTaskLoader.load_tasks = load_tasks


def record(started_ns, *, command, targets, task_names) -> None:
    telemetry = sys.modules.get("_telemetry")
    if started_ns is None or telemetry is None:
        return
    try:
        from opentelemetry.trace import Status, StatusCode

        attributes = {
            "harmonic.depth": 0,
            "doit.command": command,
            "doit.targets": " ".join(targets),
            "doit.tasks": len(task_names),
        }
        if len(targets) == 1 and targets[0] in task_names:
            # One named task (a farm leaf's ``run -n 0 part:x``): the same
            # ``label`` its task and cache phase spans carry.
            attributes["label"] = targets[0]
        # Under a farm leaf the helper injects TRACEPARENT: land in that trace.
        parent = getattr(telemetry, "_parent_context_from_env", lambda: None)()
        span = telemetry.get_tracer(service=telemetry.BUILD_INFRA_SERVICE).start_span(
            "doit.load", context=parent, start_time=started_ns, attributes=attributes
        )
        span.set_status(Status(StatusCode.OK))
        span.end(end_time=time.time_ns())
    except Exception:  # noqa: BLE001 - telemetry never fails the graph load
        return
