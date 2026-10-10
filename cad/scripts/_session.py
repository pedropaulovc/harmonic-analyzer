"""Build-session connection, document cleanup and teardown.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

# Recipe-inert (in no cache key; see its docstring and check:inert). Imported as a
# module and used by attribute: it reads these helpers the same way, so neither
# side needs the other fully initialised at import time.
import _seat_forensics
import _telemetry
import _watchdog  # COM crash/hang watchdog (started per session in run_build)
from _com import _early_bound, _read_member, _scalar
from _paths import CAD_ROOT, PART_TEMPLATE

_T0 = time.perf_counter()


_PREF_DEFAULT_PART_TEMPLATE = 8  # swUserPreferenceStringValue_e.swDefaultTemplatePart


@_telemetry.traced("seat.pin_part_template")
def _pin_default_part_template(adapter: Any) -> None:
    """Point the seat's default part template at the repo-owned PRTDOT.

    ``NewPart()`` (behind the adapter's ``create_part``) instantiates the
    seat's DEFAULT part template, whose document properties carry the DimXpert
    prefs the COM API cannot write (decimals + angular block tolerance).
    Pinning the default to the checked-in template removes that per-seat
    state: every seat builds from the same template, and dodo folds the file
    into every part's recipe/cache key, so a template edit rebuilds parts and
    busts the remote cache. The setting is seat-global and persists -- that is
    the point. apply_block_tolerances still fail-louds if the template's
    get-only prefs drift from title_block.yaml.
    """
    if not PART_TEMPLATE.is_file() or PART_TEMPLATE.stat().st_size == 0:
        raise FileNotFoundError(f"repo part template missing: {PART_TEMPLATE}")
    sw = adapter.swApp
    ok = adapter._attempt(
        lambda: sw.SetUserPreferenceStringValue(
            _PREF_DEFAULT_PART_TEMPLATE, str(PART_TEMPLATE)
        ),
        default=False,
    )
    got = str(
        adapter._attempt(
            lambda: sw.GetUserPreferenceStringValue(_PREF_DEFAULT_PART_TEMPLATE),
            default="",
        )
        or ""
    )
    if not ok or not got or Path(got).resolve() != PART_TEMPLATE.resolve():
        raise RuntimeError(
            f"failed to pin default part template: set={ok} readback={got!r}"
        )
    _telemetry.success(f"default part template pinned -> {PART_TEMPLATE.name}")


def _visible_document_paths(adapter: Any) -> list[str]:
    """Paths of the documents a user could see in the session (not Toolbox
    residents), for the post-CloseAllDocuments check."""
    paths: list[str] = []
    doc = adapter.swApp.GetFirstDocument()
    while doc is not None:
        doc = _early_bound(doc, "IModelDoc2")
        if bool(doc.Visible):
            paths.append(str(doc.GetPathName() or ""))
        doc = doc.GetNext()
    return paths


def _resident_output_documents(adapter: Any) -> list[str]:
    """Paths of EVERY resident document (visible or hidden) under ``cad/out``.

    A hidden resident -- the part behind a closed drawing, the children of a
    reopened assembly -- still holds a Windows share lock on its file, so this
    is the set that would fail a later ``cad/out`` write (a cache restore over
    the file, a from-scratch rebuild deleting it). Toolbox residents live
    outside ``cad/out`` and are excluded by construction."""
    out_root = (CAD_ROOT / "out").resolve()
    paths: list[str] = []
    doc = adapter.swApp.GetFirstDocument()
    while doc is not None:
        doc = _early_bound(doc, "IModelDoc2")
        path = str(doc.GetPathName() or "")
        if path and Path(path).resolve().is_relative_to(out_root):
            paths.append(path)
        doc = doc.GetNext()
    return paths


def discard_open_documents(adapter: Any) -> None:
    """Close every open document WITHOUT a "Save Modified Documents" prompt.

    The transient-drive paths author real mates (and verify's pen sweep installs
    equations), so the reopened assembly (and its referenced children) are
    DIRTY. ``CloseAllDocuments(True)`` still pops the save modal for a dirty
    referenced child in 3DX R2026x -- headless, that hangs the run forever.
    This mirrors ``package_native._discard_open_documents``: close the active doc
    by TITLE first (``CloseDoc`` discards a dirty doc without saving, and
    closing the assembly title drops its hidden components too), then
    ``CloseAllDocuments(True)`` as a backstop with nothing dirty left to prompt
    about. Bounded so a misbehaving session can't spin; an empty title is
    refused (``CloseDoc("")`` silently no-ops on assemblies and would leave the
    document resident)."""
    for _ in range(500):
        doc = adapter._attempt(
            lambda: _read_member(adapter.swApp, "IActiveDoc2"), default=None
        )
        if doc is None:
            break
        title = str(_read_member(doc, "GetTitle") or "")
        if not title:
            raise RuntimeError(
                "active document has an empty title -- refusing CloseDoc(''), which "
                "silently no-ops on assemblies and would leave the document resident"
            )
        adapter._attempt(lambda t=title: adapter.swApp.CloseDoc(t), default=None)
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)


# Keyword names the telemetry helpers own: a captured key of the same name would
# bind to the helper's own parameter (``_telemetry.event(name, **attributes)``
# takes ``name``; ``error(message, *, exc_info)`` takes both) and raise
# TypeError. Captured data is RENAMED rather than dropped -- a sketch's ``name``
# is exactly the field a reader looks for first.
_TELEMETRY_OWNED_KEYS = frozenset({"name", "message", "service", "exc_info"})


def _attributes_of(values: Mapping[str, Any]) -> dict[str, Any]:
    """Captured values as telemetry attributes: scalars, no shadowed keywords."""
    return {
        (f"captured_{key}" if key in _TELEMETRY_OWNED_KEYS else key): _scalar(value)
        for key, value in values.items()
    }


def run_build(build: Callable[[Any], Awaitable[dict[str, str]]]) -> int:
    """Connect, run ``build(adapter)``, disconnect; return a process exit code."""
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    # Build output carries non-ASCII (e.g. the "A ∩ B" named-axis labels). When
    # stdout is redirected to a file/pipe Windows defaults it to cp1252, so the
    # first such print would raise UnicodeEncodeError and abort the build. Force
    # UTF-8 so a piped from-scratch build doesn't depend on PYTHONUTF8=1.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    script = Path(sys.argv[0]).stem if sys.argv and sys.argv[0] else "build"
    # The part/assembly/drawing this process is building -- surfaced in the span
    # NAMES so the trace title + waterfall say WHICH target is processing, not a
    # generic "build". A part script is build_<stem>.py; an assembly script is
    # build_<stem>_assembly.py; a drawing script is draw_<stem>.py;
    # refresh_assembly.py takes the stem as argv[1].
    if script == "refresh_assembly" and len(sys.argv) > 1:
        target = sys.argv[1].removesuffix(".SLDASM").replace("_", "-")
    elif script.startswith("draw_"):
        target = script.removeprefix("draw_")
    else:
        target = script.removeprefix("build_").removesuffix("_assembly")

    # Which pipeline stage this process is. ``run_build`` is also the entry for
    # non-BUILD tools (verify.py, export_models.py, the diagnostics/ probes); a
    # build_<stem>.py / build_<stem>_assembly.py / refresh_assembly.py is a genuine
    # part/assembly build, and a draw_<stem>.py is a drawing build. ``kind`` (None
    # for the non-build tools) drives BOTH the build-body grouping span below and the
    # fallback resource label -- the non-build entries set their own richer label
    # (verify: verify-<suite>) or inherit dodo's.
    if script == "refresh_assembly":
        kind: str | None = "assembly"
    elif script.startswith("build_"):
        kind = "assembly" if script.endswith("_assembly") else "part"
    elif script.startswith("draw_"):
        kind = "drawing"
    else:
        kind = None
    # Resource label (Aspire "resource" column): dodo sets OTEL_SERVICE_NAME per
    # subprocess, so under the spine this is a fallback-only no-op that KEEPS dodo's
    # precise stage name; run standalone it self-labels so the column is still
    # meaningful -- part-build / assembly-build, and drawing-export (matching dodo's
    # ``_stage_name`` for ``drawing:`` tasks) for a drawing.
    if kind == "drawing":
        _telemetry.set_service("drawing-export")
    elif kind is not None:
        _telemetry.set_service(f"{kind}-build")

    async def _run() -> dict[str, str]:
        # Runtime successor to dodo's removed ``_assert_spine_complete`` tripwire:
        # a COM build launched BY doit (which injects TRACEPARENT into every child)
        # must hold the single SolidWorks seat lock -- dodo's ``_com_seat`` sets
        # HARMONIC_COM_SEAT while held. If a doit-launched COM process reaches connect
        # WITHOUT it, some COM task is missing its ``_com_seat`` wrapper and would race
        # the STA seat -- fail loud rather than corrupt it. A standalone run (no
        # TRACEPARENT) is exempt, so hand-run build/diagnostic scripts still work.
        if os.environ.get("TRACEPARENT") and not os.environ.get("HARMONIC_COM_SEAT"):
            raise RuntimeError(
                "COM build launched under doit without holding the SolidWorks seat "
                "(HARMONIC_COM_SEAT unset) -- a COM task is missing _com_seat(); "
                "see dodo.py._com_seat"
            )
        # Crash/hang protection for the whole COM session (see _watchdog.py):
        # a new sldexitapp.exe (SolidWorks' crash-report dialog) or 15 min of
        # telemetry silence hard-exits this process so the doit parent can fail
        # the task and release the seat lock; a hung SW window only logs.
        adapter = PyWin32Adapter({})
        _watchdog.start()
        try:
            async with _telemetry.aspan("sw.connect"):
                _telemetry.info("connecting to SolidWorks")
                # Sample the seats already running BEFORE connecting: COM starts
                # SolidWorks when none is running, so this is the only moment at
                # which "did this build start the seat, or attach to one someone
                # left?" can still be answered (see _seat_forensics.note_seats_before_connect).
                # 2.2 s p50 per COM subprocess, split into its three steps so
                # the connect cost is attributable (dispatch/identity/discard).
                async with _telemetry.aspan("sw.dispatch"):
                    _seat_forensics.note_seats_before_connect()
                    await adapter.connect()
                _telemetry.success("connected")
                # WHICH sldworks.exe is about to build this target, how old it is
                # and how big: the attribution a "failed once, passed on retry"
                # leaf needs, recorded before any build work can fail.
                with _telemetry.span("seat.identity"):
                    provenance = _seat_forensics.record_seat_provenance(adapter)
                # Re-runnable: a previous (possibly failed) build — or a human
                # inspecting an artefact in the UI — leaves documents open, and
                # saving over (or deleting) an open path fails. Verified, not
                # best-effort: a document that refuses to close would surface later
                # as an opaque save/permission error mid-build. Discard by title
                # first (a crashed build leaves DIRTY documents, and a bare
                # ``CloseAllDocuments(True)`` pops the save modal for a dirty
                # referenced child -- headless, forever). Only cad/out residents
                # count, hidden ones included: a hidden referenced part still
                # share-locks its file, while Toolbox library parts (e.g. `binding
                # head screw_ai.sldprt` behind a Hole Wizard insert) live outside
                # cad/out and are residents CloseAllDocuments never releases.
                with _telemetry.span("seat.discard"):
                    discard_open_documents(adapter)
                    holding = _resident_output_documents(adapter)
                    if holding:
                        raise RuntimeError(
                            f"{len(holding)} cad/out document(s) still open after "
                            f"discard_open_documents: {holding}"
                        )
                _telemetry.success("all documents closed (clean session)")
                _pin_default_part_template(adapter)
            # Group the build's own operations (inserts, the mate chokepoint, the
            # per-config gates) under ONE ``<kind>.build`` phase span, a sibling of
            # sw.connect/sw.disconnect. This is deliberately NOT the removed
            # ``build.<target>`` ROOT layer (which mirrored the doit task span 1:1):
            # it is an inner PHASE that separates the build proper from
            # connect/teardown, so e.g. the ~40 mate spans read as children of
            # "assembly.build drive-train" instead of a flat run under the task span.
            # Non-build entries (verify/export/probes) keep their operations flat.
            if kind is None:
                return await build(adapter)
            # The provenance rides the phase span, so every operation of this
            # build hangs under a span that names the seat that ran it.
            async with _telemetry.aspan(f"{kind}.build", target=target, **provenance):
                return await build(adapter)
        finally:
            # Teardown is its own span so a disconnect failure is attributable
            # and never a silent gap before process exit. The watchdog stop is
            # outermost so telemetry teardown cannot leave it armed. What the
            # teardown does -- no resident cad/out document, the seat parked
            # outside every checkout, disconnect -- is post-save seat hygiene,
            # so it lives in the recipe-inert _seat_forensics.
            try:
                async with _telemetry.aspan("sw.disconnect"):
                    await _seat_forensics.teardown_seat(adapter)
            finally:
                # COM session over: stop the watchdog so a long SolidWorks-free
                # tail (pure-python post-processing) can't trip the idle timeout.
                _watchdog.stop()

    # build_session continues the doit task span when one was injected (so we add
    # no duplicate root layer under the spine) and opens a local root only when run
    # standalone -- named per-target (build.<target>) so a standalone trace title
    # says WHICH part. Either way every connect/operation/disconnect span has a
    # parent: one gapless trace from process start to exit.
    with _telemetry.build_session(target, script=script) as root:
        try:
            artefacts = asyncio.run(_run())
        except Exception as exc:  # noqa: BLE001 - recorded on the root span
            # A bare `return` would let the root exit cleanly and be marked OK, so
            # a failed build (process exits 1) would trace as success. Mark ERROR
            # before returning -- span() only fills OK when the status is UNSET, so
            # it sticks. Under the spine root is None: the build's failing
            # operation span already carries ERROR, and the doit task span goes
            # ERROR via the subprocess exit code.
            if root is not None:
                root.record_exception(exc)
                root.set_status(
                    _telemetry.Status(_telemetry.StatusCode.ERROR, str(exc))
                )
            _telemetry.error(f"build {script} failed: {exc}", exc_info=True)
            rc = 1
        else:
            _telemetry.success(f"done in {time.perf_counter() - _T0:.1f}s")
            for key, value in artefacts.items():
                _telemetry.info(f"artefact {key}: {value}")
            rc = 0
    # Flush AFTER the build_session `with` has closed the root span -- shutting the
    # providers down inside the block would tear down the exporters before the
    # ERROR root span is ended/exported, losing exactly the failure trace.
    _telemetry.shutdown()
    return rc
