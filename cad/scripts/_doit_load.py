"""The doit graph load -- the ``dodo`` import plus every ``task_*`` generator --
recorded as one ``doit.load`` span.

That load is pure CPU that runs before any task span opens: measured at 16-28 s
of every farm leaf (worker ``execute`` minus the leaf's ``task`` span), paid again
by every submitter command, with nothing in the trace to say so.

``dodo`` stamps its own first line (:class:`LoadStamp`), calls
:func:`watch_import` so a failure in the rest of its own import is still
recorded, and calls :func:`install`, which wraps doit's
``DodoTaskLoader.load_tasks`` once per process. The wrapper finds the stamp in the namespace it just loaded, so
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
import inspect
import sys
import time

from doit.cmd_base import DodoTaskLoader

STAMP_NAME = "_DOIT_LOAD"
_TOOL_NAME = "harmonic-doit-load"


class LoadStamp:
    """One graph load's start, taken once: a cached ``dodo`` module that doit
    loads again in the same process never reports a load from its stale import.
    Taking it also ends any :func:`watch_import` on the module."""

    def __init__(self, started_ns: int) -> None:
        self._started_ns: int | None = started_ns
        self._unwatch = None

    def take(self) -> int | None:
        started, self._started_ns = self._started_ns, None
        unwatch, self._unwatch = self._unwatch, None
        if unwatch is not None:
            unwatch()
        return started


def watch_import(stamp: LoadStamp) -> None:
    """Record the load, ERROR, if the caller's module body fails to import.

    An exception in ``dodo`` after this call (a helper import, a module-level
    computation) unwinds dodo's own frame inside doit's ``setup``, before
    ``load_tasks`` ever runs, so the :func:`install` wrapper never sees it.
    ``sys.monitoring`` ``PY_UNWIND`` does: it is a global-only event, so the
    callback ignores every frame but the caller's module code and writes the
    span, with the exception, when that frame unwinds. A ``PY_RETURN`` of that
    code (the import completed) ends the watch, so the global event is armed
    only while dodo's own body runs, never for the rest of a process that
    imports dodo without loading it through doit.
    Best-effort: no free monitoring tool id means no watch."""
    monitoring = getattr(sys, "monitoring", None)
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    if monitoring is None or caller is None:
        return
    code = caller.f_code
    tool = next((i for i in range(6) if monitoring.get_tool(i) is None), None)
    if tool is None:
        return
    unwind, returned = monitoring.events.PY_UNWIND, monitoring.events.PY_RETURN
    watching = [True]

    def unwatch() -> None:
        if not watching:
            return
        watching.clear()
        stamp._unwatch = None
        monitoring.set_events(tool, 0)
        monitoring.set_local_events(tool, code, 0)
        monitoring.register_callback(tool, unwind, None)
        monitoring.register_callback(tool, returned, None)
        monitoring.free_tool_id(tool)

    def unwound(unwinding, _offset, exc) -> None:
        if unwinding is not code:
            return
        unwatch()
        record(
            stamp.take(), command="import", targets=[], task_names=None, error=exc
        )

    def imported(_code, _offset, _value) -> None:
        unwatch()

    try:
        monitoring.use_tool_id(tool, _TOOL_NAME)
        monitoring.register_callback(tool, unwind, unwound)
        monitoring.register_callback(tool, returned, imported)
        monitoring.set_events(tool, unwind)
        monitoring.set_local_events(tool, code, returned)
    except Exception:  # noqa: BLE001 - telemetry never fails the graph load
        unwatch()
        return
    stamp._unwatch = unwatch


def install() -> None:
    """Wrap ``DodoTaskLoader.load_tasks`` (idempotent). A namespace without a
    :data:`STAMP_NAME` stamp -- any other dodo file -- loads untouched."""
    original = DodoTaskLoader.load_tasks
    if getattr(original, "_records_doit_load", False):
        return

    @functools.wraps(original)
    def load_tasks(self, cmd, pos_args):
        stamp = getattr(self, "namespace", {}).get(STAMP_NAME)
        if not hasattr(stamp, "take"):
            return original(self, cmd, pos_args)
        started = stamp.take()
        command = cmd.get_name() if hasattr(cmd, "get_name") else str(cmd)
        targets = list(pos_args or ())
        try:
            tasks = original(self, cmd, pos_args)
        except BaseException as exc:
            # A task generator raised: the load still happened and failed, so
            # the span is written, ERROR, before the failure propagates.
            record(started, command=command, targets=targets, task_names=None, error=exc)
            raise
        record(
            started,
            command=command,
            targets=targets,
            task_names={task.name for task in tasks},
        )
        return tasks

    load_tasks._records_doit_load = True
    DodoTaskLoader.load_tasks = load_tasks


def record(started_ns, *, command, targets, task_names, error=None) -> None:
    """Write the ``doit.load`` span. ``error`` (with ``task_names=None``) is a
    failed load: the span is ERROR with the exception recorded, and carries no
    task count or label, since no graph was built."""
    telemetry = sys.modules.get("_telemetry")
    if started_ns is None or telemetry is None:
        return
    try:
        from opentelemetry.trace import Status, StatusCode

        attributes = {
            "harmonic.depth": 0,
            "doit.command": command,
            "doit.targets": " ".join(targets),
        }
        if task_names is not None:
            attributes["doit.tasks"] = len(task_names)
        if task_names is not None and len(targets) == 1 and targets[0] in task_names:
            # One named task (a farm leaf's ``run -n 0 part:x``): the same
            # ``label`` its task and cache phase spans carry.
            attributes["label"] = targets[0]
        # Under a farm leaf the helper injects TRACEPARENT: land in that trace.
        parent = getattr(telemetry, "_parent_context_from_env", lambda: None)()
        span = telemetry.get_tracer(service=telemetry.BUILD_INFRA_SERVICE).start_span(
            "doit.load", context=parent, start_time=started_ns, attributes=attributes
        )
        if error is None:
            span.set_status(Status(StatusCode.OK))
        else:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, f"{type(error).__name__}: {error}"))
        span.end(end_time=time.time_ns())
    except Exception:  # noqa: BLE001 - telemetry never fails the graph load
        return
