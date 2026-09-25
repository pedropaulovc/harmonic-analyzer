"""Observation-only seat code: provenance, failure forensics and seat teardown.

RECIPE-INERT. This module is in ``_buildgraph._local_modules``' skip set (see
``_buildgraph.RECIPE_INERT_MODULES``), like ``_telemetry`` and ``_watchdog``: no
part, assembly or drawing folds its content into its cache key, so an edit here
re-keys nothing. That is sound only because nothing here can change a saved
artefact, which ``check:inert`` (``test_recipe_inert.py``) enforces:

- Tracked code reaches this module only through pinned call sites: connect-time
  provenance and the post-save teardown in ``_common.run_build``, the pre-save
  authoring snapshot in ``_common.save_part_and_images`` (read-only: it has to
  run before the camera moves), ``package_native``'s teardown, and
  ``capture_com_failure`` as a terminal failure call (it always raises).
- No COM mutator runs here except three pinned ones, each after the artefact
  is settled: ``SaveAs3``/``SaveBMP`` of a failing document (only under the
  always-raising ``capture_com_failure``) and ``SetCurrentWorkingDirectory``
  (only at teardown).
- This module reads ``_common`` and ``_sketch_closure`` through pinned names
  only, as module attributes (``_common`` imports this module, so a
  ``from _common import`` here would be a cycle).

A change that makes any of this untrue (a verdict a build raises on, a write
into the model before its save) belongs in a tracked module instead: the
sketch-closure verdict lives in ``_sketch_closure`` for exactly that reason.

Everything here is BEST-EFFORT by construction. Forensics that can fail a build,
or that can replace a clear geometry failure with an unrelated crash, is worse
than no forensics: it moves the diagnosis further away.
"""

from __future__ import annotations

import contextlib
import ctypes
from ctypes import wintypes
import json
import math
import os
import re
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

import _common
import _sketch_closure
import _telemetry
import _watchdog

# Forensic artefacts of a failed COM build step: a saved copy of the failing
# document, a BMP of the seat and the capture.json that indexes them, one
# directory per failure label AND per capture instant -- a retried failure must
# not erase the evidence of the failure it is retrying (see
# :func:`capture_com_failure`).
OUT_FAILURES = Path(__file__).resolve().parents[1] / "out" / "reports" / "failures"


def _normal_path(path: str | Path) -> Path:
    """``path`` comparable to another Windows path (case-folded, links resolved)."""

    return Path(os.path.normcase(os.path.realpath(path)))


def _seat_park_directory() -> Path:
    """An existing directory no build owns, for the seat to sit in.

    The system temp directory is the intent, but ``tempfile.gettempdir()`` is
    not a constant: it takes ``TMPDIR``/``TEMP``/``TMP`` from the environment
    and, with none of them usable, falls back to the PROCESS CURRENT DIRECTORY
    -- which under the farm helper IS the workspace being torn down. Parking
    there would make this helper a silent no-op for exactly the bug it guards,
    so every candidate is checked and a drive root, which no checkout can be,
    is the last resort.

    Disposable means this checkout AND every sibling checkout: a farm worker
    keeps several source roots under one work root and removes them with the
    same housekeeping, so parking in a sibling only moves which leaf fails.
    ``FARM_WORK_ROOT`` is the worker's own name for that tree and reaches the
    helper in its environment.
    """

    checkout = _normal_path(_common.CAD_ROOT.parent)
    disposable = [checkout]
    work_root = os.environ.get("FARM_WORK_ROOT")
    if work_root:
        disposable.append(_normal_path(work_root))
    windows = os.environ.get("SystemRoot") or os.environ.get("windir")
    candidates = [Path(tempfile.gettempdir())]
    if windows:
        candidates.append(Path(windows) / "Temp")
    candidates.append(Path(_normal_path(_common.CAD_ROOT).anchor))
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        resolved = _normal_path(candidate)
        if any(root == resolved or root in resolved.parents for root in disposable):
            continue
        return candidate
    raise RuntimeError(
        f"no seat working directory outside {disposable}: tried {candidates}"
    )


def release_seat_working_directory(sw: Any) -> str | None:
    """Park the seat's working directory where nothing is disposable; return it.

    SolidWorks follows the documents it opens: after a build that saved into
    ``cad/out/sldprt``, the seat's own PROCESS current directory IS that
    directory, and Windows refuses to remove a directory that is any process's
    current directory. Closing documents does not release it -- the directory
    is the process's, not a document's -- so only a re-point clears it.

    Off the farm that is invisible (the checkout outlives the seat). On a farm
    worker the checkout is a disposable source root the agent removes between
    leaves and evicts to bound the disk, so a seat parked inside one makes an
    UNRELATED leaf's housekeeping fail: observed 2026-09-18 on swmaker000006,
    where ``sldworks.exe`` held
    ``C:\\harmonic\\work\\sources\\6621e07a...\\workspace\\cad\\out\\sldprt``
    from an earlier drawing leaf and the release's first farm ``export`` leaf
    failed three times with ``WinError 32`` before it ran a line.

    Parked UNCONDITIONALLY, not only when the seat sits in *this* checkout: a
    worker keeps several source roots, and the seat this session inherited may
    still be parked in a SIBLING root whose own leaf died before its teardown
    (that is exactly the shape above -- the failing leaf's root was not the
    pinned one). Re-pointing only out of our own checkout would leave that root
    pinned until the seat itself died; re-pointing always heals it.

    Teardown, not connect: the seat drifts back into a workspace on the next
    open/save, so a session that re-points only at startup ends parked again.

    Takes the raw ``ISldWorks`` (``adapter.swApp``, or ``package_native``'s
    comtypes pointer), so both COM entrypoints share this one implementation.

    Returns the directory the seat was left in, or ``None`` when it was already
    there. Raises when the seat will not move -- the caller decides what that is
    worth (both callers warn: it is the NEXT leaf's hazard, not this build's
    failure).
    """

    target = _seat_park_directory()
    before = sw.GetCurrentWorkingDirectory()
    if type(before) is not str or not before:
        raise RuntimeError(f"seat working directory unreadable: {before!r}")
    if _normal_path(before) == _normal_path(target):
        return None
    if sw.SetCurrentWorkingDirectory(str(target)) is not True:
        raise RuntimeError(f"seat refused working directory {target}")
    # A True answer is not evidence: the readback is. Anything else and the
    # caller must not report a directory the seat never took. Emptiness is
    # refused BEFORE normalizing, because ``os.path.realpath("")`` is the
    # PROCESS current directory -- so a seat that answers nothing would
    # normalize onto ``target`` itself whenever this helper runs from there,
    # and an unreadable seat would be reported as parked.
    after = sw.GetCurrentWorkingDirectory()
    if type(after) is not str or not after:
        raise RuntimeError(f"seat working directory unreadable after move: {after!r}")
    if _normal_path(after) != _normal_path(target):
        raise RuntimeError(f"seat working directory did not move: {after!r}")
    return after


# ---------------------------------------------------------------------------
# Seat provenance + COM failure forensics
#
# A leaf that fails once and passes on retry is "transient" only while nothing
# recorded WHICH seat ran it and WHAT that seat looked like when it failed. On
# 2026-09-17 `logo ring extrude failed` (FeatureExtrusion3 -> None) failed one
# leaf on swmaker000005@5 and passed on retry, having passed twice earlier the
# same day; neither the trace nor the log could say which sldworks.exe had run
# it, how old that seat was, or what the seat's sketch-authoring preferences
# were -- the three facts that separate "the geometry is wrong" from "this seat
# authors sketches differently". Both gaps are closed here: every session
# records its seat's provenance, and a null COM return captures the seat's state
# before it raises.
#
# Everything below is BEST-EFFORT by construction. Forensics that can fail a
# build, or that can replace a clear geometry failure with an unrelated crash,
# is worse than no forensics: it moves the diagnosis further away.
# ---------------------------------------------------------------------------

# ``PROCESS_QUERY_LIMITED_INFORMATION`` -- enough for the start time, memory and
# session of a process this one did not create, and granted where the full
# ``PROCESS_QUERY_INFORMATION`` right is not.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
# FILETIME counts 100 ns ticks from 1601-01-01; Unix time runs from 1970-01-01.
_FILETIME_UNIX_EPOCH_TICKS = 116_444_736_000_000_000


class _MemoryCounters(ctypes.Structure):
    """``PROCESS_MEMORY_COUNTERS_EX``.

    ``PrivateUsage`` is the process's commit charge (Task Manager's "Commit
    size"), ``WorkingSetSize`` its resident set. A seat that has been up for
    hours across dozens of leaves carries a very different footprint from one
    that just started, which is exactly the axis a "only fails on warm seats"
    hypothesis needs.
    """

    _fields_ = (
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    )


@contextlib.contextmanager
def _process_handle(pid: int):
    """Open ``pid`` for limited query; yields ``None`` when it cannot be opened."""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    try:
        yield handle or None
    finally:
        if handle:
            kernel32.CloseHandle(handle)


def _process_started_at(pid: int) -> float | None:
    """Unix timestamp of ``pid``'s creation (``GetProcessTimes``)."""
    created = ctypes.c_uint64()
    exited = ctypes.c_uint64()
    kernel = ctypes.c_uint64()
    user = ctypes.c_uint64()
    with _process_handle(pid) as handle:
        if handle is None:
            return None
        if not ctypes.windll.kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
    return (created.value - _FILETIME_UNIX_EPOCH_TICKS) / 1e7


def _process_memory(pid: int) -> tuple[int | None, int | None]:
    """``(commit charge, working set)`` bytes of ``pid``, or ``(None, None)``."""
    counters = _MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    with _process_handle(pid) as handle:
        if handle is None:
            return None, None
        if not ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        ):
            return None, None
    return int(counters.PrivateUsage), int(counters.WorkingSetSize)


def _process_session_id(pid: int) -> int | None:
    """Windows session of ``pid``: 0 is a service-launched seat with no
    interactive desktop, 1+ an RDP/console login. A seat started from a signed-in
    session behaves differently from one a scheduled task launched, so the
    session id is part of "which seat was this"."""
    session = ctypes.c_uint32()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(
        int(pid), ctypes.byref(session)
    ):
        return None
    return int(session.value)


def _sldworks_pids() -> set[int]:
    """Pids of every running ``sldworks.exe`` (the lifecycle library's scan)."""
    from solidworks_mcp.adapters import sw_recovery

    return set(sw_recovery.pids_of_image("sldworks.exe"))


# Seats already running when this process began connecting, so a seat THIS build
# started can be told from one it attached to. ``None`` means the sample never
# ran (or failed), which is recorded as ``unknown`` rather than guessed: COM
# starts SolidWorks when none is running, and a seat on its first document of the
# process is the leading suspect in any first-run-only failure.
_seat_pids_at_start: frozenset[int] | None = None
_seat_identity: dict[str, Any] = {}


def note_seats_before_connect() -> None:
    """Sample the running seats BEFORE connecting (see ``_seat_pids_at_start``)."""
    global _seat_pids_at_start
    try:
        _seat_pids_at_start = frozenset(_sldworks_pids())
    except Exception as exc:  # noqa: BLE001 - provenance is never fatal
        _telemetry.debug(f"pre-connect seat scan unavailable: {exc}")
        _seat_pids_at_start = None


def _seat_identity_of(adapter: Any) -> dict[str, Any]:
    """Immutable facts about the seat this adapter drives (pid, origin, start)."""
    sw = getattr(adapter, "swApp", None)
    ident: dict[str, Any] = {}
    pid = (
        adapter._attempt(lambda: int(sw.GetProcessID()), default=None)
        if sw is not None
        else None
    )
    if pid is None:
        # No ``ISldWorks.GetProcessID`` answer: one running seat is unambiguous,
        # several are not -- and a wrong pid is worse than no pid.
        running = sorted(_sldworks_pids())
        pid = running[0] if len(running) == 1 else None
        ident["seat_pid_source"] = "image-scan" if pid is not None else "unresolved"
    else:
        ident["seat_pid_source"] = "GetProcessID"
    if pid is None:
        return ident
    ident["seat_pid"] = pid
    if _seat_pids_at_start is None:
        ident["seat_origin"] = "unknown"
    elif pid in _seat_pids_at_start:
        ident["seat_origin"] = "attached"
    else:
        ident["seat_origin"] = "started-by-build"
    started = _process_started_at(pid)
    if started is not None:
        ident["seat_started_epoch_s"] = round(started, 3)
        ident["seat_started_at"] = datetime.fromtimestamp(started, UTC).isoformat(
            timespec="seconds"
        )
    session = _process_session_id(pid)
    if session is not None:
        ident["seat_session_id"] = session
    revision = adapter._attempt(lambda: str(sw.RevisionNumber()), default=None)
    if revision:
        ident["seat_revision"] = revision
    commit, working_set = _process_memory(pid)
    if commit is not None:
        ident["seat_commit_bytes_at_start"] = commit
    if working_set is not None:
        ident["seat_working_set_bytes_at_start"] = working_set
    return ident


def _seat_working_directory(adapter: Any) -> dict[str, Any]:
    """The directory the SEAT is sitting in, re-read per call.

    ``sldworks.exe`` moves its own working directory as documents are opened and
    saved, and a seat parked inside a leaf's workspace PINS that directory: the
    pool's source-root eviction then fails ``os.rmdir`` with a sharing violation
    on a directory whose files all deleted fine, and the leaf dies with
    ``(log: None)`` -- an infrastructure failure carrying no log at all. That
    happened tonight on the ``export`` leaf and was identified only by probing
    every process's PEB for its current directory over run-command. Recording
    the seat's own answer makes the next one readable off the artefact.
    """
    sw = getattr(adapter, "swApp", None)
    if sw is None:
        return {}
    value = adapter._attempt(
        lambda: _common._read_member(sw, "GetCurrentWorkingDirectory"), default=None
    )
    return {"seat_working_directory": str(value)} if value else {}


def _seat_liveness(pid: Any, started: Any) -> dict[str, Any]:
    """How old and how big the seat is RIGHT NOW (re-read on every call)."""
    live: dict[str, Any] = {}
    if not isinstance(pid, int):
        return live
    if isinstance(started, (int, float)):
        live["seat_uptime_s"] = round(time.time() - float(started), 1)
    commit, working_set = _process_memory(pid)
    if commit is not None:
        live["seat_commit_bytes"] = commit
    if working_set is not None:
        live["seat_working_set_bytes"] = working_set
    return live


def seat_provenance(adapter: Any) -> dict[str, Any]:
    """WHICH ``sldworks.exe`` this session drives, how old it is and how big.

    Flat ``seat_*`` keys, so the whole set can ride as span attributes (OTel
    attribute values are scalars) and one filter over ``traces.jsonl`` /
    ``logs.jsonl`` finds every one of them. The immutable half is resolved once
    per process and cached; uptime, memory and the seat's working directory are
    re-read per call, so a failure capture records the seat as it was at the
    moment it failed.
    """
    global _seat_identity
    if not _seat_identity:
        try:
            _seat_identity = _seat_identity_of(adapter)
        except Exception as exc:  # noqa: BLE001 - provenance is never fatal
            _seat_identity = {"seat_provenance_error": f"{type(exc).__name__}: {exc}"}
    prov = dict(_seat_identity)
    try:
        prov.update(
            _seat_liveness(prov.get("seat_pid"), prov.get("seat_started_epoch_s"))
        )
        prov.update(_seat_working_directory(adapter))
    except Exception as exc:  # noqa: BLE001 - provenance is never fatal
        prov["seat_liveness_error"] = f"{type(exc).__name__}: {exc}"
    return prov


def record_seat_provenance(adapter: Any) -> dict[str, Any]:
    """Resolve the seat's provenance, publish it, and return it for the caller to
    hang on the build PHASE span.

    Published three ways, because each answers a different question: a
    ``seat.provenance`` span event (WHEN in the session the seat was identified),
    one INFO log record (so the entries with no phase span -- verify, export, the
    ``diagnostics/`` probes -- are still attributable in ``logs.jsonl``), and a
    push into the watchdog so a fatal crash/timeout abort names the seat it killed
    rather than just the exit code.
    """
    prov = seat_provenance(adapter)
    _watchdog.set_seat_provenance(prov)
    _telemetry.event("seat.provenance", **prov)
    _telemetry.info(
        "seat "
        + " ".join(
            f"{key.removeprefix('seat_')}={value}" for key, value in prov.items()
        ),
        **prov,
    )
    return prov


# The seat user preferences that govern SKETCH AUTHORING. A profile authored from
# bare ``CreateLine``/``Create3PointArc`` calls closes into an extrudable contour
# only if the seat merges exactly-coincident endpoints, which is application
# state: inference and automatic relations persist across leaves on the same seat,
# so a leaf that turns them off and dies before its ``finally`` restores them
# poisons that seat for every later leaf -- deterministic per seat, random-looking
# across a fleet. Every name below is a verified member of
# ``swUserPreferenceToggle_e`` / ``swUserPreferenceIntegerValue_e`` (swconst
# R2026x), and is resolved to its id AT RUNTIME by name: the ids move between
# releases while the member names do not, and the captured id is recorded next to
# the value so an id can be confirmed rather than assumed. The baseline the farm
# ENFORCES lives in the pool repo (``agent/seat_settings.py``); this list is what
# a failure READS.
SKETCH_AUTHORING_TOGGLE_NAMES = (
    # Inference, automatic relations and the solver: what merges coincident
    # endpoints into a closed loop when the recipe adds no explicit relations.
    "swSketchInference",
    "swSketchAutomaticRelations",
    "swSketchInferFromModel",
    "swSketchNoSolveMove",
    "swFullyConstrainedSketchMode",
    # Snapping: which existing entity a new endpoint may land on. The
    # quadrant/nearest snaps are the "circle-snap hazard" a raw-primitive
    # profile has to reason about.
    "swSnapToPoints",
    "swSketchSnapsPoints",
    "swSketchSnapsCenterPoints",
    "swSketchSnapsMidPoints",
    "swSketchSnapsQuadrantPoints",
    "swSketchSnapsIntersections",
    "swSketchSnapsNearest",
    # Grid snapping quantizes coordinates AT CREATION -- the one snap preference
    # with a direct "silently moves scripted geometry" mechanism (SeatSettings
    # pins this one to False for exactly that reason).
    "swSketchSnapsGrid",
    # Autosolve/undo mode: swSketchTurnOffAutomaticSolveModeAndUndo decides
    # whether the solver runs at all as segments are added.
    "swSketchTurnOffAutomaticSolveModeAndUndo",
    # Dimension entry: a seat that pops the dimension box, or rescales a sketch
    # on its first dimension, authors different geometry from one that does not.
    "swInputDimValOnCreate",
    "swSketchAcceptNumericInput",
    "swSketchCreateDimensionOnlyWhenEntered",
    "swScaleSketchOnFirstDimension",
    "swAddDimensionsToSketchEntity",
)

SKETCH_AUTHORING_INTEGER_NAMES = ("swSketch_Auto_Solve_Threshold",)

# Preferences that wedge a seat with a modal dialog instead of failing it: a
# ``#32770`` parked over the graphics area makes a leaf log healthy heartbeats
# and no progress, and no COM read can see it. Captured because "leaf stalled,
# no error" is otherwise indistinguishable from slow work (see the pool's
# diagnose-wedged-solidworks-seat / unwedge-3dexperience-connector-modal
# playbooks, and SeatSettings' baseline, which PINS these).
MODAL_HAZARD_TOGGLE_NAMES = (
    "swSketchPromptToCloseSketch",
    "swSketchOverdefiningDimsPromptToSetState",
    "swSketchOverdefiningDimsSetDrivenByDefault",
    "swDrawingShowSheetFormatDialog",
    "swShowErrorsEveryRebuild",
    "swSaveReminderEnable",
    "swWhileOpeningAssembliesAutoDismissMessages",
    "swAlwaysUseDefaultTemplates",
    "swOpenLastUsedDocumentAtStart",
)

# Per-DOCUMENT toggles, read through ``IModelDocExtension`` and reported in their
# own bucket. These are not "preferences SolidWorks ignores on write": SolidWorks'
# own option-to-API mapping (docs/swconst/ToolsSketchEntitiesRectangle.md:11,14)
# documents both members on ``IModelDocExtension::Get/SetUserPreferenceToggle``
# and NOT on ``ISldWorks``, so reading them through the system accessor is a
# category error -- which is exactly why one worker read system=False while its
# active document read True in the same pass. They are also HALF A RADIO PAIR
# each (From Midpoint / From Corner), so a snapshot naming only one describes
# half a control.
DOCUMENT_SCOPE_TOGGLE_NAMES = (
    "swSketchAddConstToRectEntity",  # Rectangle Type > Add construction lines > From Midpoint
    "swSketchAddConstLineDiagonalType",  # ... > From Corner (id 585, verified in swconst)
)

# The SolidWorks default-template preferences (``swUserPreferenceStringValue_e``
# member names): the part template sets the document's INITIAL VIEW SCALE, which
# is a load-bearing input to any inference-dependent sketch (see
# :func:`display_geometry`), so "which template" is part of the geometry's
# provenance, not mere configuration.
TEMPLATE_PREFERENCE_NAMES = ("swDefaultTemplatePart", "swDefaultTemplateAssembly")


def sketch_authoring_preferences(adapter: Any) -> dict[str, Any]:
    """The seat's CURRENT values for the preferences that govern sketch authoring.

    ``"unresolved"`` = the name is not in this seat's swconst (so nothing was
    read); ``"unreadable"`` = the seat refused the read. Both are recorded rather
    than dropped -- and neither is reported as ``False``, because
    ``GetUserPreferenceToggle`` answers an unknown id with a plausible-looking
    ``False`` and a silent one of those would send the next investigation the
    wrong way. ``preference_ids`` carries the id each name resolved to, so the
    id/member pairing can be confirmed against the type library.
    """
    sw = adapter.swApp
    snapshot: dict[str, Any] = {}
    ids: dict[str, int] = {}
    readers = (
        (SKETCH_AUTHORING_TOGGLE_NAMES, "GetUserPreferenceToggle", bool),
        (MODAL_HAZARD_TOGGLE_NAMES, "GetUserPreferenceToggle", bool),
        (SKETCH_AUTHORING_INTEGER_NAMES, "GetUserPreferenceIntegerValue", int),
        (TEMPLATE_PREFERENCE_NAMES, "GetUserPreferenceStringValue", str),
    )
    for names, accessor, cast in readers:
        read = getattr(sw, accessor, None)
        for name in names:
            pref = _common._preference_id(adapter, name)
            if pref is None or read is None:
                snapshot[name] = "unresolved"
                continue
            ids[name] = pref
            value = adapter._attempt(lambda p=pref, r=read: r(p), default=None)
            snapshot[name] = cast(value) if value is not None else "unreadable"
    snapshot["preference_ids"] = ids
    snapshot["document_scope"] = _document_scope_preferences(adapter, ids)
    return snapshot


def _document_scope_preferences(
    adapter: Any, ids: dict[str, int]
) -> dict[str, Any]:
    """Per-DOCUMENT toggles, read through the document's own accessor.

    Kept in a separate bucket, explicitly labelled: the system accessor answers
    these with a value that does not govern the active document (system=False
    while the document reads True, observed on worker 4), so folding them into
    the system snapshot logs a misleading number.
    """
    model = adapter.currentModel
    extension = _common._read_member(model, "Extension") if model is not None else None
    if extension is None:
        return {"scope": "document", "document": None}
    scoped: dict[str, Any] = {"scope": "document"}
    read = getattr(extension, "GetUserPreferenceToggle", None)
    for name in DOCUMENT_SCOPE_TOGGLE_NAMES:
        pref = _common._preference_id(adapter, name)
        if pref is None or read is None:
            scoped[name] = "unresolved"
            continue
        ids[name] = pref
        # The document accessor takes (id, swUserPreferenceOption_e); 0 is
        # swDetailingNoOptionSpecified, i.e. "this document's value".
        value = adapter._attempt(lambda p=pref, r=read: r(p, 0), default=None)
        scoped[name] = bool(value) if value is not None else "unreadable"
    return scoped


def sketch_manager_state(adapter: Any) -> dict[str, Any]:
    """``ISketchManager``'s STICKY per-session state.

    This is a second state bag that ``Get/SetUserPreferenceToggle`` cannot see,
    and it overrides the preferences: with ``AddToDB=True`` a new segment
    bypasses inference relations at creation time no matter what
    ``swSketchInference`` says (that is exactly why
    :func:`set_sketch_direct_db` exists). A snapshot that reads only user
    preferences therefore reports a perfectly healthy seat while the thing that
    actually governs endpoint merging sits in here -- which is what "the log was
    clean and the failure still happened" looked like on 2026-09-17.

    It is per SESSION, not per document, so a leaf that sets ``AddToDB`` and dies
    before restoring it hands the next leaf on that seat a different authoring
    mode, with nothing on disk to show it.
    """
    manager = adapter.currentSketchManager
    if manager is None:
        return {"sketch_manager": None}
    state: dict[str, Any] = {"scope": "session"}
    for name in ("AddToDB", "AutoInference", "AutoSolve", "DisplayWhenAdded"):
        value = adapter._attempt(lambda n=name: _common._read_member(manager, n), default=None)
        state[name] = bool(value) if isinstance(value, (bool, int)) else "unreadable"
    return state


class _Rect(ctypes.Structure):
    """Win32 ``RECT`` (``GetClientRect`` fills it with client-area pixels)."""

    _fields_ = (
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    )


# GetSystemMetrics indices: primary screen pixels and monitor count. A session
# whose RDP client disconnected reports a degenerate or stale desktop, which is
# the documented "live frame froze after someone RDP'd in" shape -- and worker 5's
# seat was hand-launched over RDP 54 min before the 2026-09-17 failure.
_SM_CXSCREEN, _SM_CYSCREEN, _SM_CMONITORS = 0, 1, 80
# A sketch-inference snap is a SCREEN-SPACE hit test of a few pixels. 8 px is the
# pessimistic end of SolidWorks' observed 5-8 px tolerance, so
# ``snap_floor_mm`` = 8 / (px per mm) is the model distance below which two
# DISTINCT points stop being separately clickable -- compare it against the
# profile's nearest non-coincident competitor (0.400 mm for the 91247A720 logo
# ring) to decide whether that geometry could author correctly at all.
_SNAP_TOLERANCE_PX = 8

# Win32 prototypes for the display probes. An undeclared ``argtypes`` marshals a
# Python int as a 32-bit C int, which on win64 truncates the HWND before
# ``GetWindowRect`` ever sees it; an undeclared ``restype`` defaults to
# ``c_int`` -- harmless for these BOOL/int returns, declared anyway so the
# contract is explicit (audit-native-binding-contracts). ``GetSystemMetrics``
# is int(int).
_USER32_PROTOTYPES: tuple[tuple[str, tuple[Any, ...], Any], ...] = (
    ("GetWindowRect", (wintypes.HWND, ctypes.POINTER(_Rect)), wintypes.BOOL),
    ("GetClientRect", (wintypes.HWND, ctypes.POINTER(_Rect)), wintypes.BOOL),
    ("IsIconic", (wintypes.HWND,), wintypes.BOOL),
    ("IsZoomed", (wintypes.HWND,), wintypes.BOOL),
    ("GetSystemMetrics", (ctypes.c_int,), ctypes.c_int),
)


def _user32() -> Any:
    """``user32`` with every function the display probes call prototyped.

    Resolved through ``ctypes.windll`` each call (the function objects are
    cached on the loaded DLL, so re-declaring is idempotent) rather than a
    module-level ``WinDLL``: the probes' tests substitute ``windll.user32``.
    """
    user32 = ctypes.windll.user32
    for name, argtypes, restype in _USER32_PROTOTYPES:
        function = getattr(user32, name)
        function.argtypes = argtypes
        function.restype = restype
    return user32


def _frame_geometry(adapter: Any) -> dict[str, Any]:
    """The SolidWorks main window's pixel rect -- the term the 2026-09-17
    investigation had to reconstruct by hand and could not.

    RootCause's verdict refuted preference drift by measurement (45 shared
    sketch/snap/inference preference names, ZERO differences across workers
    4/5/6) and landed on this instead: the failing seat's main window was
    1024x640 against 1278x750 and 1296x816 on the two that passed -- 0.620 of
    the area, monotonic with the outcome. Nothing recorded it. The live
    dashboard frames are capped and unversioned and the published PNGs are a
    forced 1600x1000 (they measure the EXPORT, not the window), so the rect at
    04:59:56Z is permanently unrecoverable.

    Recorded as INTEGERS, not a "1024x640" label: width/height/left/top plus the
    derived area are what a later comparison across seats needs, and the
    maximised/minimised state says whether an operator had hand-arranged the
    window (which is how w5 got its size -- launched over RDP, then ``tscon``'d
    to the console). SeatSettings records the same fields on every periodic seat
    check, including clean seats; this is the failure-time half of the pair, and
    the field names match theirs so both halves join on one query.
    """
    sw = adapter.swApp
    frame = adapter._attempt(lambda: _common._read_member(sw, "Frame"), default=None)
    # ``IFrame::GetHWndx64`` (dispid 16, VT_I8) is the handle; ``GetHWnd``
    # (dispid 11, VT_I4) is the 32-bit form and truncates on win64.
    hwnd = (
        adapter._attempt(lambda: int(_common._early_bound(frame, "IFrame").GetHWndx64()), default=None)
        if frame is not None
        else None
    )
    if not hwnd:
        return {"frame_hwnd": None}
    user32 = _user32()
    geometry: dict[str, Any] = {"frame_hwnd": hwnd}
    window = _Rect()
    if user32.GetWindowRect(hwnd, ctypes.byref(window)):
        width = window.right - window.left
        height = window.bottom - window.top
        geometry.update(
            frame_left=window.left,
            frame_top=window.top,
            frame_width_px=width,
            frame_height_px=height,
            frame_area_px=width * height,
        )
    client = _Rect()
    if user32.GetClientRect(hwnd, ctypes.byref(client)):
        geometry["frame_client_width_px"] = client.right - client.left
        geometry["frame_client_height_px"] = client.bottom - client.top
    geometry["frame_state"] = (
        "minimised"
        if user32.IsIconic(hwnd)
        else "maximised"
        if user32.IsZoomed(hwnd)
        else "normal"
    )
    return geometry


def _projected_px_per_mm(adapter: Any, view: Any) -> dict[str, Any]:
    """MEASURE pixels-per-millimetre by projecting model points to the screen.

    ``IModelView.ProjectModelPoint`` is the only route that answers the governing
    quantity directly instead of requiring ``Scale2`` to be interpreted: project
    the origin and a point 1 mm along each axis, and the pixel distance IS px/mm
    for that direction. The axes are reported separately because a rotated view
    foreshortens them differently, and the maximum is the one a snap in the
    sketch plane sees.

    ``[out]`` params ride the return tuple (early binding; see
    :func:`_early_bound`).
    """
    typed = _common._early_bound(view, "IModelView")
    project = getattr(typed, "ProjectModelPoint", None)
    if project is None:
        return {}
    def screen(x: float, y: float, z: float) -> tuple[float, float] | None:
        out = adapter._attempt(lambda: project(x, y, z), default=None)
        if not isinstance(out, (list, tuple)) or len(out) < 3:
            return None
        values = [v for v in out if isinstance(v, (int, float))]
        return (float(values[0]), float(values[1])) if len(values) >= 2 else None

    origin = screen(0.0, 0.0, 0.0)
    if origin is None:
        return {}
    measured: dict[str, Any] = {}
    for axis, point in (("x", (1e-3, 0.0, 0.0)), ("y", (0.0, 1e-3, 0.0)), ("z", (0.0, 0.0, 1e-3))):
        far = screen(*point)
        if far is None:
            continue
        measured[f"px_per_mm_{axis}"] = round(
            math.dist(origin, far), 3
        )  # 1 mm apart in model space -> pixels on screen
    axes = [value for key, value in measured.items() if key.startswith("px_per_mm_")]
    if axes:
        px_per_mm = max(axes)
        measured["px_per_mm"] = px_per_mm
        if px_per_mm > 0:
            measured["snap_floor_mm"] = round(_SNAP_TOLERANCE_PX / px_per_mm, 4)
            measured["snap_tolerance_px"] = _SNAP_TOLERANCE_PX
    return measured


def display_geometry(adapter: Any) -> dict[str, Any]:
    """The SCREEN-SPACE state an inference-dependent sketch is authored under.

    Sketch inference snapping is a pixel hit test, so the authoring-time view
    scale and the window's pixel size decide whether two points 0.4 mm apart are
    distinguishable at all. Nothing in the build path fits or orients the view
    before authoring (the only ``ViewZoomtofit2``/``ShowNamedView2`` calls on the
    whole path are inside the adapter's screenshot helper), so this state is
    INHERITED from the document template and the window size and was, until now,
    never recorded -- which is why a run that produced correct geometry and one
    that did not could not be compared.

    Recorded: ``Scale2`` and the visible model box (the raw inputs, each
    uninterpretable without the other), the main window's numeric rect, area and
    state (:func:`_frame_geometry` -- the measured root cause of the 2026-09-17
    failure), the measured px/mm with the per-axis values behind it, the
    resulting snap floor in millimetres, and the interactive session's screen
    metrics.
    """
    geometry: dict[str, Any] = dict(_frame_geometry(adapter))
    user32 = _user32()
    screen_w = int(user32.GetSystemMetrics(_SM_CXSCREEN))
    screen_h = int(user32.GetSystemMetrics(_SM_CYSCREEN))
    geometry["screen_width_px"] = screen_w
    geometry["screen_height_px"] = screen_h
    geometry["screen_px"] = f"{screen_w}x{screen_h}"
    geometry["monitors"] = int(user32.GetSystemMetrics(_SM_CMONITORS))
    # 0x0 with no monitors is a session whose RDP client disconnected: screen
    # capture stops and the seat's view geometry stops meaning anything.
    geometry["session_has_display"] = geometry["screen_px"] != "0x0"
    model = adapter.currentModel
    view = (
        adapter._attempt(lambda: _common._read_member(model, "ActiveView"), default=None)
        if model is not None
        else None
    )
    if view is None:
        return geometry
    scale = adapter._attempt(lambda: float(_common._read_member(view, "Scale2")), default=None)
    if scale is not None:
        geometry["view_scale2"] = scale
    box = adapter._attempt(
        lambda: list(_common._early_bound(view, "IModelView").GetVisibleBox() or []), default=None
    )
    if box and len(box) >= 6:
        numbers = [float(value) for value in box[:6]]
        geometry["visible_box_mm"] = [round(value * 1000.0, 3) for value in numbers]
        geometry["visible_width_mm"] = round(abs(numbers[3] - numbers[0]) * 1000.0, 3)
        geometry["visible_height_mm"] = round(abs(numbers[4] - numbers[1]) * 1000.0, 3)
        client_width = geometry.get("frame_client_width_px")
        if client_width and geometry["visible_width_mm"]:
            geometry["px_per_mm_from_box"] = round(
                client_width / geometry["visible_width_mm"], 3
            )
    geometry.update(_projected_px_per_mm(adapter, view))
    return geometry


def record_authoring_context(adapter: Any, label: str) -> dict[str, Any]:
    """Publish the authoring-time seat state for a SUCCESSFUL build too.

    A failure-only capture cannot answer "what was different about the run that
    worked?", which is the question that actually identifies a seat-state cause.
    So the same state bags a failure captures -- the screen-space geometry,
    ``ISketchManager``'s sticky session state, and the sketch-authoring
    preferences -- are recorded once per part build, on the success path, as a
    span event plus one INFO record carrying the whole snapshot as JSON.

    EVERY probe is guarded individually, because this runs on the path where
    nothing is wrong: ``save_part_and_images`` calls it before ``save_file``, and
    these probes reach ``_early_bound`` (raises when no generated wrapper binds)
    and raw ``user32`` calls. A diagnostic that fails a good part export is worse
    than no diagnostic, so a bag that cannot be read is recorded as its own error
    string and the build continues.
    """
    bags: dict[str, Callable[[], Any]] = {
        "seat": lambda: seat_provenance(adapter),
        "display": lambda: display_geometry(adapter),
        "sketch_manager": lambda: sketch_manager_state(adapter),
        "preferences": lambda: sketch_authoring_preferences(adapter),
    }
    context: dict[str, Any] = {"label": label}
    for name, probe in bags.items():
        try:
            context[name] = probe()
        except Exception as exc:  # noqa: BLE001 - see above: never fail a good build
            context[name] = {"capture_error": f"{type(exc).__name__}: {exc}"}
    display = context["display"]
    summary = (
        f"authoring {label}: px/mm={display.get('px_per_mm', 'unknown')} "
        f"snap_floor={display.get('snap_floor_mm', 'unknown')}mm "
        f"view_scale2={display.get('view_scale2', 'unknown')} "
        f"frame={display.get('frame_width_px', '?')}x"
        f"{display.get('frame_height_px', '?')}"
        f"({display.get('frame_state', 'unknown')}) "
        f"AddToDB={context['sketch_manager'].get('AddToDB', 'unknown')}"
    )
    with contextlib.suppress(Exception):
        _telemetry.event(
            "seat.authoring_context",
            label=label,
            **_common._attributes_of(display),
        )
        _telemetry.info(summary, label=label, authoring=json.dumps(context, default=str))
    return context


_SAVE_AS_CURRENT_VERSION = 0  # swSaveAsVersion_e.swSaveAsCurrentVersion
# swSaveAsOptions_e.swSaveAsOptions_Silent | swSaveAsOptions_Copy: silent so a
# headless leaf can never block on a save dialog, and a COPY so the live document
# keeps its own path -- a rename would repoint the session at cad/out/reports and
# lie to run_build's teardown scan of resident cad/out documents.
_SAVE_AS_SILENT_COPY = 1 | 2
_DOC_SUFFIX = {1: ".SLDPRT", 2: ".SLDASM", 3: ".SLDDRW"}


def _slug(label: str) -> str:
    """Filesystem-safe directory name for a failure label."""
    return re.sub(r"[^a-z0-9._-]+", "-", label.strip().lower()).strip("-.") or "failure"


def _capture_step(report: dict[str, Any], name: str, probe: Callable[[], Any]) -> None:
    """Run ONE capture: record its result -- or its own failure -- in ``report``
    and as a single ``com.failure.<name>`` span event.

    Individually guarded, and one event per STEP rather than per captured item:
    a step that cannot read the seat must not stop the steps that can, and a
    census of a 40-segment sketch must not arrive as 40 span events. The
    REPORTING is guarded too: the value is already in ``report``, so a telemetry
    failure must not cost the artefact (it did, for one round of this change: a
    captured ``name`` key collided with ``event``'s own parameter and aborted the
    whole capture before it could write capture.json).
    """
    try:
        value = probe()
    except Exception as exc:  # noqa: BLE001 - forensics never raise (see above)
        error = f"{type(exc).__name__}: {exc}"
        report[name] = {"capture_error": error}
        with contextlib.suppress(Exception):
            _telemetry.event(f"com.failure.{name}", capture_error=error)
        return
    report[name] = value
    attributes = value if isinstance(value, dict) else {"value": value}
    with contextlib.suppress(Exception):
        _telemetry.event(f"com.failure.{name}", **_common._attributes_of(attributes))


def _seat_error_state(adapter: Any) -> dict[str, Any]:
    """SolidWorks' own error surface: the What's Wrong table and the session
    message stack.

    Both take ``[out]`` params that ride the RETURN TUPLE under early binding --
    call them bare and unpack (a byref VARIANT stays unwritten and reads as "no
    errors"; see ``_early_bound`` and ``test_out_param_binding``).
    ``GetErrorMessages`` is read-AND-CLEAR and keeps only the last 20 messages,
    which is safe exactly here: this is the failure path, and draining the stack
    into the capture is strictly better than leaving it to be discarded with the
    session.
    """
    state: dict[str, Any] = {}
    sw = adapter.swApp
    messages = adapter._attempt(
        lambda: _common._early_bound(sw, "ISldWorks").GetErrorMessages(), default=None
    )
    if isinstance(messages, (list, tuple)) and len(messages) >= 2:
        state["error_messages"] = [str(text) for text in (messages[1] or [])]
    model = adapter.currentModel
    extension = _common._read_member(model, "Extension") if model is not None else None
    if extension is None:
        return state
    state["whats_wrong_count"] = adapter._attempt(
        lambda: int(_common._early_bound(extension, "IModelDocExtension").GetWhatsWrongCount()),
        default=None,
    )
    faults = adapter._attempt(
        lambda: _common._early_bound(extension, "IModelDocExtension").GetWhatsWrong(),
        default=None,
    )
    if isinstance(faults, (list, tuple)) and len(faults) >= 4:
        _retval, features, codes, warnings = faults[:4]
        state["whats_wrong"] = [
            {
                "feature": str(_common._read_member(feature, "Name")),
                "code": int(code or 0),
                "error": _common._FEATURE_ERROR.get(int(code or 0), "unknown"),
                "warning": bool(warning),
            }
            for feature, code, warning in zip(
                list(features or []),
                list(codes or []),
                list(warnings or []),
                strict=False,
            )
        ]
    return state


def _document_state(adapter: Any) -> dict[str, Any]:
    """Which document was active, whether a sketch was open for edit, and how
    much of it had been built when the call failed."""
    model = adapter.currentModel
    if model is None:
        return {"active_document": None}
    active_sketch = adapter._attempt(
        lambda: _common._read_member(model, "GetActiveSketch2"), default=None
    )
    probes: dict[str, Callable[[], Any]] = {
        "title": lambda: str(_common._read_member(model, "GetTitle") or ""),
        "path": lambda: str(_common._read_member(model, "GetPathName") or ""),
        "doc_type": lambda: int(_common._read_member(model, "GetType") or 0),
        "feature_count": lambda: int(_common._read_member(model, "GetFeatureCount") or 0),
        "needs_save": lambda: bool(_common._read_member(model, "GetSaveFlag")),
        "configuration": lambda: _common.active_configuration_name(adapter, model),
    }
    state: dict[str, Any] = {
        key: adapter._attempt(probe, default=None) for key, probe in probes.items()
    }
    # A feature created while a sketch is still open for edit is the classic
    # cause of a None return, so the edit state is as important as the geometry.
    state["in_sketch_edit"] = active_sketch is not None
    return state


def _save_failure_document(adapter: Any, out_dir: Path, slug: str) -> dict[str, Any]:
    """Save a COPY of the failing document into the failure directory.

    The document is the evidence: with it, the profile can be opened and the
    failing feature retried on any seat. Saved as a silent copy in the live
    document's own format (the extension comes from the document, so a part,
    assembly and drawing each land native).
    """
    model = adapter.currentModel
    if model is None:
        return {"document_copy": None}
    suffix = Path(str(_common._read_member(model, "GetPathName") or "")).suffix
    if not suffix:
        doc_type = _common._read_member(model, "GetType")
        suffix = _DOC_SUFFIX.get(
            doc_type if isinstance(doc_type, int) else 0, ".SLDPRT"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{slug}{suffix}"
    target.unlink(missing_ok=True)
    rc = adapter._attempt(
        lambda: model.SaveAs3(
            str(target), _SAVE_AS_CURRENT_VERSION, _SAVE_AS_SILENT_COPY
        ),
        default=None,
    )
    saved = target.exists()
    return {
        "document_copy": str(target) if saved else None,
        "document_copy_bytes": target.stat().st_size if saved else None,
        "save_rc": _common._scalar(rc),
    }


def _save_seat_image(adapter: Any, out_dir: Path, slug: str) -> dict[str, Any]:
    """Capture the seat's current viewport with ``IModelDoc2.SaveBMP``.

    No dialog, no camera move and no zoom-to-fit, so the image shows the seat
    exactly as it sat when the call failed -- and shows a modal box parked over
    the graphics area, which is invisible to every COM read. (``export_image``
    would have re-oriented the view and destroyed that evidence.)
    """
    model = adapter.currentModel
    if model is None:
        return {"seat_image": None}
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{slug}.bmp"
    target.unlink(missing_ok=True)
    adapter._attempt(lambda: model.SaveBMP(str(target), 1600, 1000), default=None)
    saved = target.exists()
    return {
        "seat_image": str(target) if saved else None,
        "seat_image_bytes": target.stat().st_size if saved else None,
    }


def _write_failure_report(out_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Write ``capture.json`` -- the index of everything captured."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "capture.json"
    target.write_text(
        json.dumps(report, indent=2, default=str, sort_keys=True), encoding="utf-8"
    )
    return {"report": str(target)}




def capture_com_failure(
    adapter: Any,
    label: str,
    message: str,
    *,
    api: str | None = None,
    sketch: Any | None = None,
    expected_points: int | None = None,
    exc_type: type[BaseException] = RuntimeError,
    **context: Any,
) -> NoReturn:
    """Capture the seat's state behind a COM call that returned ``None``, then raise.

    A feature-creation API that hands back ``None`` says only "no feature". The
    state that decides WHY -- which seat, which document, whether the profile
    closed, what the seat's sketch-authoring preferences were -- lives in a
    session that is about to be torn down, so a bare ``raise`` throws the
    diagnosis away and leaves "transient" as the only available verdict. Use this
    instead of ``raise`` at such a site::

        if feat is None:
            capture_com_failure(
                adapter,
                "logo-ring-extrude",
                "logo ring extrude failed",
                api="IFeatureManager.FeatureExtrusion3",
                sketch="LogoProfile",
            )

    Three guarantees, in order of importance:

    1. It ALWAYS raises ``exc_type(message)``, with ``message`` unchanged. Every
       capture step is guarded individually and the capture as a whole is guarded
       again, so forensics can neither mask the failure's message nor convert a
       clear geometry failure into an unrelated crash.
    2. Everything captured lands as ``com.failure.<step>`` span events on a
       ``com.failure <label>`` span AND in exactly ONE ERROR log record (the
       whole capture as JSON), so the evidence reaches App Insights and
       ``logs.jsonl`` -- not just a disposable worker's disk.
    3. The artefacts (a copy of the failing document, a BMP of the seat,
       ``capture.json``) land under
       ``cad/out/reports/failures/<label>/<UTC timestamp>/``. The timestamp
       directory is not cosmetic: on 2026-09-17 the successful RETRY overwrote
       the failing attempt's leaf log, and the whole diagnosis had to be
       reconstructed from traces. A retry must never erase the evidence of the
       failure it is retrying.

    Captured, in this order: the seat (:func:`seat_provenance`), the
    sketch-authoring and modal-hazard preferences with their per-document bucket,
    ``ISketchManager``'s sticky session state (which OVERRIDES those
    preferences), the screen-space view geometry that decides whether a snap can
    resolve at all (:func:`display_geometry`), SolidWorks' own error surface, the
    document, the sketch census, then the artefacts.

    ``sketch`` selects the sketch to census: a name, a live dispatch, or omitted
    for the document's last profile sketch. ``expected_points`` is the number of
    DISTINCT sketch points the author expects when every coincident endpoint
    merged (9 for the 91247A720 logo ring, 18 if nothing merged); passing it lets
    the artefact state the discrepancy instead of leaving the reader to count.
    Extra keyword arguments are recorded as attributes on the span, the events
    and the log record.
    """
    slug = _slug(label)
    stamp = datetime.now(UTC)
    out_dir = OUT_FAILURES / slug / stamp.strftime("%Y%m%dT%H%M%SZ")
    # Caller context, with any key the telemetry helpers own renamed rather than
    # dropped (see _attributes_of).
    extra = _common._attributes_of(context)
    report: dict[str, Any] = {
        "label": label,
        "message": message,
        "api": api,
        "captured_at": stamp.isoformat(timespec="seconds"),
        "failure_dir": str(out_dir),
        "context": extra,
    }
    try:
        with _telemetry.span(
            f"com.failure {label}", label=label, api=api or "unknown", **extra
        ):
            _capture_step(report, "seat", lambda: seat_provenance(adapter))
            _capture_step(
                report, "preferences", lambda: sketch_authoring_preferences(adapter)
            )
            # Read BEFORE the document/sketch probes touch anything: these two
            # bags are what a preference-only snapshot misses entirely.
            _capture_step(
                report, "sketch_manager", lambda: sketch_manager_state(adapter)
            )
            _capture_step(report, "display", lambda: display_geometry(adapter))
            _capture_step(report, "error_state", lambda: _seat_error_state(adapter))
            _capture_step(report, "document", lambda: _document_state(adapter))
            _capture_step(
                report, "sketch", lambda: _sketch_closure._sketch_state(adapter, sketch, expected_points)
            )
            _capture_step(
                report, "document_copy", lambda: _save_failure_document(adapter, out_dir, slug)
            )
            _capture_step(
                report, "seat_image", lambda: _save_seat_image(adapter, out_dir, slug)
            )
            _capture_step(report, "artefacts", lambda: _write_failure_report(out_dir, report))
    except Exception as exc:  # noqa: BLE001 - see guarantee 1
        report["capture_aborted"] = f"{type(exc).__name__}: {exc}"
    with contextlib.suppress(Exception):
        _telemetry.error(
            f"[forensics] {label}: {message}",
            **{
                **extra,
                "label": label,
                "api": api or "unknown",
                "failure_dir": str(out_dir),
                "capture": json.dumps(report, default=str, sort_keys=True),
            },
        )
    raise exc_type(message)


async def teardown_seat(adapter: Any) -> None:
    """Leave the seat holding no ``cad/out`` document and no checkout directory,
    then disconnect. Runs after the build, whether it succeeded or not.

    SolidWorks keeps every document the build touched resident after the COM
    session ends -- a part after its own build, the (hidden) referenced models
    behind a closed drawing, the reopened assembly and its children -- and each
    holds a share lock on its file. The next task's cache restore runs BEFORE any
    COM session (outside the seat, so before the connect-time
    CloseAllDocuments) and its extract then fails with PermissionError, falling
    through to a local rebuild whose exact ``.execution`` token no peer can
    reproduce: on a farm worker that silently forks every dependent's cache key
    off the submitter's (observed 2026-09-17: worker 4 rebuilt measuring_stick
    behind the open top-assembly drawing and `cache_missing`-failed the leaf).

    Every step is warn-only: a document that refuses to close, or a seat that
    will not move, is a hazard for the NEXT task, not a failure of this one, and
    connect re-checks loud.
    """
    try:
        _common.discard_open_documents(adapter)
        holding = _common._resident_output_documents(adapter)
        if holding:
            _telemetry.warn(
                f"{len(holding)} cad/out document(s) still resident "
                f"after teardown close: {holding}"
            )
        else:
            _telemetry.success("all documents closed (seat left clean)")
    except Exception as exc:  # noqa: BLE001
        _telemetry.warn(f"teardown close failed: {exc}")
    # ... and holding NO directory of this checkout either. The seat's own current
    # directory follows the documents it opened, and on a farm worker this
    # checkout is a source root the agent removes between leaves: a seat parked in
    # cad/out makes an unrelated leaf's cleanup fail with WinError 32 (see
    # release_seat_working_directory).
    #
    # The readback is emitted under the same ``seat_working_directory`` key the
    # seat provenance uses, which samples at CONNECT: one query then reads both
    # ends -- where a leaf left the seat, and where the next leaf found it.
    try:
        left = release_seat_working_directory(adapter.swApp)
        if left is not None:
            _telemetry.success(
                f"seat working directory moved to {left}",
                seat_working_directory=left,
            )
    except Exception as exc:  # noqa: BLE001
        _telemetry.warn(f"seat working directory re-point failed: {exc}")
    try:
        await adapter.disconnect()
        _telemetry.success("disconnected")
    except Exception as exc:  # noqa: BLE001
        _telemetry.warn(f"disconnect failed: {exc}")
