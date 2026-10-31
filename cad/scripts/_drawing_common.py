"""Universal drawing session, document policy, export and finalization core.

Every drawing needs the new_project_drawing/finalize_drawing closure here;
metadata stamping and process-global center-mark registration share that
lifecycle rather than adding modules with no useful cache isolation.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import math
from pathlib import Path
import time
from typing import Any, Callable, Iterable, Iterator, Literal, Mapping, Sequence

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks import drawing as _sw_drawing
from solidworks_mcp.adapters.solidworks.drawing import (
    iter_views,
    new_drawing,
    remove_notes_matching as remove_notes_matching,
    save_drawing,
    set_units_mm,
    view_name,
)

from _com import _early_bound, _read_member
import _config
from _custom_properties import apply_custom_properties
from _drawing_layout_audit import run_layout_audit
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout, layout_report_path
import _seat_forensics
from _session import _visible_document_paths
from _source_identity import _build_id
import _telemetry


def _record_center_marks(counts: dict[str, Any]) -> None:
    """Every auto_center_marks call's centre-mark count, before and after
    AutoInsertCenterMarks2, as a span event (#913: each mark printed twice on
    30 views). after == 2 x before would point at a template auto-insert the
    explicit call repeats; before == 0 at duplicates made some other way.

    The observer is process-global and set when this module is imported, so
    a script that never imports _drawing_common records nothing (every
    auto_center_marks caller does). OTel attributes must be primitives: a
    count whose read raised arrives as None and is sent as -1, named in
    ``read_failed``.
    """
    attributes = {key: value for key, value in counts.items() if value is not None}
    failed = sorted(key for key, value in counts.items() if value is None)
    for key in failed:
        attributes[key] = -1
    if failed:
        attributes["read_failed"] = failed
    _telemetry.event("center_marks.auto_insert", **attributes)
    _telemetry.debug(
        f"center marks {counts.get('view')!r}: {counts.get('before')} -> {counts.get('after')}"
        f" (holes={counts.get('holes')}, slots={counts.get('slots')}, ok={counts.get('ok')})"
    )


_sw_drawing.CENTER_MARK_OBSERVER = _record_center_marks


# These ints are READ OFF the installed swconst.tlb, not the published docs: the
# API reference prints "See System Options and Document Properties" instead of a
# value for every swUserPreferenceIntegerValue_e / swUserPreferenceOption_e
# member, and that page documents none of them. Re-read them from the type
# library (swconst.tlb, SOLIDWORKS Constant type library) rather than guessing
# if they ever need revisiting.
_PREF_DIM_TEXT_AND_LEADER_STYLE = 372


_BROKEN_LEADER_HORIZONTAL_TEXT = 2


# swUserPreferenceOption_e's dimension scopes. Two live-probed facts pin this
# list, neither of them documented:
#
#  * the style REQUIRES a dimension scope -- writing it under
#    swDetailingNoOptionSpecified(0) returns False and leaves the document on
#    swSolidLeaderAlignedText(1), the aligned-text default this fix exists to
#    replace; and
#  * the umbrella swDetailingDimension(200) does NOT propagate -- after setting
#    it, every per-type scope still read 1, so a drawing whose dimensions are
#    linear/radius/diameter would have kept rotated text.
#
# So every scope is set explicitly and read back. Values are from swconst.tlb
# (the docs print no integer for any swUserPreferenceOption_e member).
_DIM_DETAILING_SCOPES = {
    "swDetailingDimension": 200,
    "swDetailingAngleDimension": 201,
    "swDetailingArcLengthDimension": 202,
    "swDetailingChamferDimension": 203,
    "swDetailingDiameterDimension": 204,
    "swDetailingHoleDimension": 205,
    "swDetailingLinearDimension": 206,
    "swDetailingOrdinateDimension": 207,
    "swDetailingRadiusDimension": 208,
    "swDetailingAngularRunningDimension": 209,
}


@dataclass(frozen=True)
class DrawingOutputs:
    slddrw: Path
    pdf: Path
    png: Path




# swUserPreferenceIntegerValue_e.swUnitsLinear and swLengthUnit_e.swINCHES.
_PREF_UNITS_LINEAR = 47
_LENGTH_INCHES = 3

# The general-tolerance custom properties every part carries
# (_part_properties.part_properties, from cad/config/title_block.yaml) and the drawing
# template's title block reads via $PRPSHEET. finalize_drawing requires them on
# the linked model so a stale part can't ship blank tolerance cells.
TITLE_BLOCK_TOLERANCE_PROPERTIES = (
    "TOL_LIN_X",
    "TOL_LIN_XX",
    "TOL_LIN_XXX",
    "TOL_ANG",
    "TOL_SURFACE",
    # The DRILLED HOLES row's two cells. Required like the rest: with holes now
    # relying on this general tolerance UOS (no per-feature callout), a blank row
    # would silently drop every clearance hole's fit -- so a stale source part
    # that predates the TOL_HOLE_* stamp must fail loud here, not ship blank.
    "TOL_HOLE_MINUS",
    "TOL_HOLE_PLUS",
    # Edge-break and thread rows (2026-09 template): $PRPSHEET links, so a
    # source part that predates the stamp would print "REMOVE BURRS AND BREAK
    # SHARP EDGES  OR CHAMFER  MAX" -- fail loud instead.
    "TOL_EDGE_BREAK_R",
    "TOL_CHAMFER_MAX",
    "TOL_INSIDE_CORNER",
    "THREAD_TYPE",
    "THREAD_CLASS",
)


TITLE_BLOCK_REVISION_PROPERTY = "Revision"


# The copyright line's year ($PRPSHEET:{COPYRIGHT_YEAR}); required like the
# tolerance rows so a stale source model cannot print "(c)  Pedro ...".
TITLE_BLOCK_COPYRIGHT_PROPERTY = "COPYRIGHT_YEAR"


# Stamped on the drawing document itself at finalize (see _source_identity._build_id).
DRAWING_BUILD_ID_PROPERTY = "BUILD_ID"


# ``IModelDoc2.IsOpenedViewOnly`` is True for two reasons (API remarks): the
# file is still loading ("Files are loaded using multi-threading ... Until all
# data and references are loaded, the file is in view-only mode ... many API
# queries return NULL or empty data"), or it was DELIBERATELY opened for
# viewing, which only the opener can ask for: ``swOpenDocOptions_ViewOnly``
# (0x4) on ``OpenDoc6``, or ``IDocumentSpecification.ViewOnly`` on
# ``OpenDoc7``. The build asks for neither. Every open passes ``OpenDoc6``
# options without 0x4 (``adapter.open_model`` passes 1, Silent), and
# ``test_failure_forensics`` holds every ``OpenDoc6``/``OpenDoc7`` call in
# cad/scripts and solidworks_mcp to that. So on any document the build opened,
# part or assembly, view-only means "still loading": an empty read waits for
# the flag to clear (bounded and logged), and is re-read once only when the
# document then says it is loaded -- never on a flag it cannot read.
_VIEW_ONLY_WAIT_S = 30.0


_VIEW_ONLY_POLL_S = 0.25


def _opened_view_only(model: Any) -> bool | None:
    """``IsOpenedViewOnly``, or ``None`` when the document gives no boolean."""
    try:
        value = _read_member(model, "IsOpenedViewOnly")
    except Exception:  # noqa: BLE001 - unreadable is "unknown", never a verdict
        return None
    return value if isinstance(value, bool) else None


def _await_document_loaded(model: Any) -> dict[str, Any]:
    """Wait for a view-only (still loading) document to finish loading.

    Returns the observation for the failure capture: ``view_only`` as first
    read; when it had to wait, ``view_only_wait_s`` and the final state; and
    ``loaded``, True only when the document's last answer was a definite
    ``IsOpenedViewOnly=False``.
    """
    view_only = _opened_view_only(model)
    load: dict[str, Any] = {"view_only": "unknown" if view_only is None else view_only}
    if view_only is True:
        _telemetry.info(
            "source document is still loading (IsOpenedViewOnly=True, and the build "
            "never opens view-only) with empty custom properties; waiting up to "
            f"{_VIEW_ONLY_WAIT_S:.0f}s for it to load"
        )
        begun = time.monotonic()
        while view_only is True and time.monotonic() - begun < _VIEW_ONLY_WAIT_S:
            time.sleep(_VIEW_ONLY_POLL_S)
            view_only = _opened_view_only(model)
            # One record per poll keeps the watchdog's idle clock (log records
            # are its heartbeat) from reading this wait as a wedged COM call.
            _telemetry.debug(
                f"source document load poll: IsOpenedViewOnly={view_only} after "
                f"{time.monotonic() - begun:.1f}s"
            )
        load["view_only_wait_s"] = round(time.monotonic() - begun, 2)
        load["view_only_after_wait"] = "unknown" if view_only is None else view_only
        _telemetry.info(
            f"source document view-only wait ended after {load['view_only_wait_s']:.1f}s "
            f"(IsOpenedViewOnly={load['view_only_after_wait']})"
        )
    load["loaded"] = view_only is False
    return load


def read_required_properties(
    model: Any, names: Sequence[str], *, required: Iterable[str]
) -> dict[str, str]:
    """The source document's file-level custom properties ``names``; raise when
    one of ``required`` is empty, or ``Revision`` is not the current release.

    An empty required value is re-read once, and only once the document itself
    reports it is loaded (``IsOpenedViewOnly=False``, after waiting out a load
    in progress; see ``_await_document_loaded``). The first read may have landed
    before a load that finished by the time the flag was asked, so a definite
    "loaded" earns a re-read; an unreadable flag does not. Still empty, the
    failure names the document, its configuration, both property APIs' answers
    and the seat's age and startup state
    (``_seat_forensics.capture_missing_properties``) before raising the same
    ``RuntimeError``.
    """
    required = tuple(required)

    def read() -> dict[str, str]:
        return {name: str(model.GetCustomInfoValue("", name) or "") for name in names}

    properties = read()
    missing = [name for name in required if not properties.get(name)]
    if missing:
        load = _await_document_loaded(model)
        if load["loaded"]:
            properties = read()
            missing = [name for name in required if not properties.get(name)]
        if missing:
            _seat_forensics.capture_missing_properties(
                model,
                f"source part properties are missing: {missing}",
                missing=missing,
                values=properties,
                load=load,
            )
        _telemetry.info("source part properties read after the document finished loading")
    revision = properties.get(TITLE_BLOCK_REVISION_PROPERTY)
    if revision is not None:
        expected = _config.release_revision()
        if revision != expected:
            raise RuntimeError(
                f"source model Revision {revision!r} != current release {expected!r}"
            )
    return properties


# swUserPreferenceIntegerValue_e system colours, read off swconst.tlb R2026x
# (the docs print no integer).  A drawing-ADDED dimension or callout is a
# "non-imported annotation" and SolidWorks draws it in a grey that exports at
# ~level 128 -- the 75.00 / (93.00) / hole callouts read pale beside the black
# model-imported dimensions (machinist review 2026-09-02: "plotted in very
# pale gray ... reducing arm's-length readability"; Lipton: faint lines are
# for accountants).  Both books want every line on the print pressed hard.
_PREF_COLOR_NON_IMPORTED_ANNOTATION = 232


_PREF_COLOR_IMPORTED_DRIVEN_ANNOTATION = 113


_COLORREF_BLACK = 0


def _pin_annotation_ink(adapter: Any) -> None:
    """Pin the seat's driven / non-imported annotation colours to black.

    System (seat) preferences, so every sheet the seat exports gets the same
    ink; read back after each write so a rejected write fails loud instead of
    shipping pale dimensions.
    """
    sw = _early_bound(adapter.swApp, "ISldWorks")
    for pref in (
        _PREF_COLOR_NON_IMPORTED_ANNOTATION,
        _PREF_COLOR_IMPORTED_DRIVEN_ANNOTATION,
    ):
        if int(sw.GetUserPreferenceIntegerValue(pref)) == _COLORREF_BLACK:
            continue
        if not sw.SetUserPreferenceIntegerValue(pref, _COLORREF_BLACK):
            raise RuntimeError(f"failed to set annotation colour pref {pref}")
        if int(sw.GetUserPreferenceIntegerValue(pref)) != _COLORREF_BLACK:
            raise RuntimeError(f"annotation colour pref {pref} did not persist")
        _telemetry.debug(f"annotation colour pref {pref} pinned to black")


# System Options > Export > PDF > "Shaded/Draft geometry DPI"
# (swUserPreferenceIntegerValue_e.swPDFExportShadedDraftDPI = 534, read off
# swconst.tlb R2026x; docs/swconst/FileSaveAsPDFOptions.md). SolidWorks prints
# a shaded or draft-quality view into the PDF as ONE raster at this resolution
# and draws the edges over it as vectors. Every farm seat carries the factory
# 96 (registry ``Export Settings\PDF Dots Per Inch`` on all five workers,
# 2026-10-16), which embeds the shaded isos at 120.5 dpi: the 0.21 mm pixel
# staircase shows as white specks between the vector silhouette and the fill
# (machinist review MHA-MG-01 r2: "draft quality, speckled broken edges").
_PREF_PDF_SHADED_DRAFT_DPI = 534


PDF_SHADED_DRAFT_DPI = 300


# The DECLARED seat value restored after every export, never the value read on
# entry: a leaf that dies inside the export (watchdog ``os._exit`` skips
# ``finally``) would otherwise teach the next leaf that 300 is "the original"
# (see ``_preferences``). A seat found elsewhere is reported, then healed.
_PDF_SHADED_DRAFT_DPI_BASELINE = 96


@contextlib.contextmanager
def pdf_shaded_raster_dpi(adapter: Any, span: Any) -> Iterator[None]:
    """Export the PDF with shaded views rastered at ``PDF_SHADED_DRAFT_DPI``.

    A seat-global system preference, so it is raised for the one ``SaveAs3``
    that prints the PDF and put back to the declared baseline in a ``finally``:
    the lock holder leaves the seat as the fleet configures it. Each write is
    read back; the entry, applied and restored values land on ``span``. A
    refused write raises (a quiet refusal ships the 120 dpi raster again),
    and so does a restore that throws, except while the export is already
    failing: then a refused or throwing restore (a seat that disconnected
    mid-export) is warned, so it cannot replace the export's own exception.
    """
    sw = _early_bound(adapter.swApp, "ISldWorks")
    pref = _PREF_PDF_SHADED_DRAFT_DPI
    before = int(sw.GetUserPreferenceIntegerValue(pref))
    span.set_attribute("pdf.shaded_draft_dpi.before", before)
    span.set_attribute("pdf.shaded_draft_dpi.baseline", _PDF_SHADED_DRAFT_DPI_BASELINE)
    if before != _PDF_SHADED_DRAFT_DPI_BASELINE:
        _telemetry.warn(
            f"[seat] PDF shaded/draft DPI was {before}, declared baseline "
            f"{_PDF_SHADED_DRAFT_DPI_BASELINE}: a seat left mutated, restored after export",
            before=before,
        )
    exporting = True
    try:
        sw.SetUserPreferenceIntegerValue(pref, PDF_SHADED_DRAFT_DPI)
        applied = int(sw.GetUserPreferenceIntegerValue(pref))
        span.set_attribute("pdf.shaded_draft_dpi.applied", applied)
        if applied != PDF_SHADED_DRAFT_DPI:
            raise RuntimeError(
                f"PDF shaded/draft DPI did not persist: wanted "
                f"{PDF_SHADED_DRAFT_DPI}, seat reports {applied}"
            )
        yield
        exporting = False
    finally:
        try:
            sw.SetUserPreferenceIntegerValue(pref, _PDF_SHADED_DRAFT_DPI_BASELINE)
            restored = int(sw.GetUserPreferenceIntegerValue(pref))
        except Exception as exc:
            if not exporting:
                raise
            _telemetry.warn(
                f"[seat] PDF shaded/draft DPI restore failed during a failed export: {exc!r}",
                error=repr(exc),
            )
        else:
            span.set_attribute("pdf.shaded_draft_dpi.restored", restored)
            refused = (
                f"PDF shaded/draft DPI restore refused: wanted "
                f"{_PDF_SHADED_DRAFT_DPI_BASELINE}, seat reports {restored}"
            )
            if restored != _PDF_SHADED_DRAFT_DPI_BASELINE:
                if exporting:
                    _telemetry.warn(f"[seat] {refused}", restored=restored)
                else:
                    raise RuntimeError(refused)
            _telemetry.info(
                f"PDF shaded/draft DPI: seat {before}, export {PDF_SHADED_DRAFT_DPI}, "
                f"restored {restored}"
            )


@contextlib.contextmanager
def _drawing_checkpoint(
    checkpoint: Callable[[str], None] | None, operation: str
) -> Iterator[None]:
    """Observe an attempted operation without replacing its primary failure.

    A refused before-check never enters the operation or emits an after-check.
    Observers detect source mutation; read-only-at-open is not a save guarantee.
    """
    if checkpoint is not None:
        checkpoint(f"before_{operation}")
    try:
        yield
    except BaseException as primary:
        if checkpoint is not None:
            try:
                checkpoint(f"after_{operation}")
            except BaseException as secondary:
                primary.add_note(
                    f"after_{operation} checkpoint also failed: "
                    f"{type(secondary).__name__}: {secondary}"
                )
        raise
    else:
        if checkpoint is not None:
            checkpoint(f"after_{operation}")


@contextlib.contextmanager
def _drawing_artifact_save(
    adapter: Any,
    kind: Literal["drawing", "pdf", "png"],
    path: str,
    checkpoint: Callable[[str], None] | None = None,
) -> Iterator[None]:
    """Observe the existing save context, including preparation and file checks.

    An after-check on failure means the context was entered, not proof SaveAs3
    was reached (filesystem preparation can fail first). Successful contexts
    have completed the native save and the existing output-file check.
    """
    with _telemetry.span(f"drawing.save_{kind}") as span:
        with (
            pdf_shaded_raster_dpi(adapter, span)
            if kind == "pdf"
            else contextlib.nullcontext()
        ):
            with _drawing_checkpoint(checkpoint, f"{kind}_save"):
                yield
        span.set_attribute("artifact.bytes", Path(path).stat().st_size)


def _pin_dimension_text_and_leader_style(draw: Any) -> None:
    """Force every dimension on ``draw`` to a bent leader with HORIZONTAL text.

    Set on the DOCUMENT (``IModelDocExtension::SetUserPreferenceInteger``), not
    the application, so a build can never drift the seat's global preferences.

    This is the only mechanism that reaches dimensions: ``SetLeader3`` covers
    notes / GD&T / surface-finish symbols but explicitly not dimensions. Read
    back and raise on mismatch -- the preference's value enum is undocumented
    (read from swconst.tlb), so a silent no-op is exactly the failure mode to
    guard against.
    """
    for name, option in _DIM_DETAILING_SCOPES.items():
        ok = draw.Extension.SetUserPreferenceInteger(
            _PREF_DIM_TEXT_AND_LEADER_STYLE, option, _BROKEN_LEADER_HORIZONTAL_TEXT
        )
        applied = int(
            draw.Extension.GetUserPreferenceInteger(
                _PREF_DIM_TEXT_AND_LEADER_STYLE, option
            )
        )
        if not ok or applied != _BROKEN_LEADER_HORIZONTAL_TEXT:
            raise RuntimeError(
                "failed to pin dimension text/leader style to broken-leader + "
                f"horizontal-text for {name} (set returned {ok!r}, document "
                f"reads {applied})"
            )
    _telemetry.event(
        "drawing.dim_text_leader_style",
        style=_BROKEN_LEADER_HORIZONTAL_TEXT,
        scopes=len(_DIM_DETAILING_SCOPES),
    )


@_telemetry.traced("drawing.new_from_template")
def new_project_drawing(
    adapter: Any,
    *,
    layout: DrawingLayout,
    property_view: str | None = None,
    scale: tuple[float, float] = (1.0, 1.0),
    decimals: int = 2,
    checkpoint: Callable[[str], None] | None = None,
    unit: str = "mm",
) -> tuple[Any, Any]:
    """Create a drawing from the selected hand-made project template.

    Each template embeds its own ASME B sheet format (title block, tolerance
    block, projection symbol), so there is no SetupSheet6 format re-apply; the
    only per-drawing knobs are the sheet scale (here) and WHICH view's model
    feeds the sheet's $PRPSHEET property links -- linked in finalize_drawing,
    once views exist (SolidWorks silently ignores a CustomPropertyView naming a
    view that does not exist yet, falling back to 'Default' = first view).
    ``property_view`` is accepted for compatibility and unused.
    ``checkpoint`` runs immediately after native document creation/binding,
    before drawing setup, so source load transitions are not attributed to views.
    ``unit`` is the package's ``drawing_unit`` (``_part_properties.part_drawing_unit``
    or the assembly contract's): ``"in"`` selects the SDK's decimal-inch
    document units, anything else millimetres.
    """
    if checkpoint is not None and not callable(checkpoint):
        raise TypeError("drawing checkpoint must be callable")
    if unit not in ("mm", "in"):
        raise ValueError(f"unknown drawing unit {unit!r}")
    _ = property_view
    template = DRAWING_TEMPLATES[layout]
    if not template.path.is_file() or template.path.stat().st_size == 0:
        raise FileNotFoundError(f"project drawing standard is missing: {template.path}")

    draw = new_drawing(
        adapter,
        template=str(template.path),
        width=template.width_m,
        height=template.height_m,
    )
    if checkpoint is not None:
        checkpoint("after_new_document")
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    # A hand-saved template can be saved while in Edit Sheet Format mode (it
    # was, the day the title block was drawn) -- a drawing created from it then
    # opens with the FORMAT layer active, where every pick lands on the sheet
    # format and view geometry is inert (all typed SelectByID2 picks fail).
    # EditSheet() drops back to the sheet layer; idempotent when already there.
    ddoc.EditSheet()
    sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("project drawing template has no current sheet")
    # 2 decimals by default: 3-decimal display (76.000) reads as false precision
    # next to the ±0.25 blanket tolerance. A drawing that genuinely needs finer
    # display (an exact inch conversion like 9.525) can pass decimals=3.
    if unit == "in":
        _sw_drawing.set_units_inch(adapter, decimals=decimals)
    else:
        set_units_mm(adapter, decimals=decimals)
    _pin_dimension_text_and_leader_style(draw)
    _pin_annotation_ink(adapter)
    if not sheet.SetScale(float(scale[0]), float(scale[1]), True, False):
        raise RuntimeError(
            f"failed to force drawing sheet to {scale[0]:g}:{scale[1]:g}"
        )
    assert_asme_b_sheet(
        adapter, sheet, layout=layout, phase="initial setup", scale=scale
    )
    # Normalize the viewport: sheet-coordinate picks (the hole-table datum
    # vertex / hole rims) hit-test with a PIXEL tolerance mapped through the
    # current zoom, and a hand-saved template opens at whatever zoom it was
    # saved with (the old generated one happened to be saved fit). Fit once so
    # coordinate picks are deterministic regardless of how the template binary
    # was last saved.
    draw.ViewZoomtofit2()
    draw.ForceRebuild3(False)
    rebuild_drawing(adapter, label="new_project_drawing")
    # The window every coordinate pick in this drawing hit-tests in, as fitted.
    _seat_forensics.record_drawing_display(adapter, f"new {layout.value} drawing")
    return draw, sheet


# IView::SetDisplayMode4 requires swSHADED plus its explicit Edges flag for
# "Shaded With Edges". Faceted=False selects precision geometry; the getter may
# report either swSHADED or the composite swSHADED_EDGES value after the write.
#
# GetFacettedHlrDisplay is NOT read back here. On a fresh view it is transient:
# it reads False for ~10 ms after the write, flips True ~50 ms later, and only
# settles False once SolidWorks first computes the view's display geometry —
# which nothing short of the export does (ForceRebuild3, EditRebuild3,
# IModelDocExtension.Rebuild, GraphicsRedraw2, UpdateViewDisplayGeometry and the
# zoom calls all leave it True; the PDF export clears it —
# `_frame_shading_idempotence_probe --fresh-view-compute`, 2026-09-15). Reading it
# here was a timing lottery (a slow getter under load read True and failed a
# correct view); `assert_precise_isometric_views` proves it after export instead.
_SW_SHADED = 3


_SW_SHADED_EDGES = 7


@_telemetry.traced("drawing.shaded_with_edges", label_param="label")
def set_high_quality_shaded_with_edges(adapter: Any, view: Any, *, label: str) -> None:
    """Set and verify a Shaded With Edges drawing view (precision proven post-export).

    ``SetDisplayMode4`` returns False when the view ALREADY reads the requested
    mode (frame_assembly sets its exploded isometric before the BOM/balloon
    pass, then ``finalize_drawing`` re-applies it: readback mode 3, edges True,
    use_parent False, no COM error -- 2026-09-17), so the setter's bool is not
    the proof. Only a COM exception is fatal here; the readback below is the
    contract either way.
    """
    _ok, error = adapter._attempt_with_error(
        lambda: view.SetDisplayMode4(False, _SW_SHADED, False, True, True)
    )
    if error is not None:
        raise RuntimeError(
            f"{label}: SetDisplayMode4 raised {error!r}"
        ) from error

    mode = adapter._attempt(lambda: view.GetDisplayMode2(), default=None)
    use_parent = adapter._attempt(lambda: view.GetUseParentDisplayMode(), default=None)
    edges = adapter._attempt(lambda: view.GetDisplayEdgesInShadedMode(), default=None)
    cosmetic_threads = adapter._attempt(lambda: view.GetCThreadQuality(), default=None)
    readback = {
        "mode": mode,
        "use_parent": use_parent,
        "edges": edges,
        "cosmetic_threads": cosmetic_threads,
    }
    if any(value is None for value in readback.values()):
        raise RuntimeError(f"{label}: incomplete display-mode readback {readback!r}")

    try:
        mode_value = int(mode)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label}: invalid display mode {mode!r}") from exc
    if (
        mode_value not in {_SW_SHADED, _SW_SHADED_EDGES}
        or bool(use_parent)
        or not bool(edges)
        or not bool(cosmetic_threads)
    ):
        raise RuntimeError(
            f"{label}: drawing view is not precise Shaded With Edges {readback!r}"
        )


@_telemetry.traced("drawing.assert_precise_isometrics")
def assert_precise_isometric_views(adapter: Any, sheet_names: Sequence[str]) -> int:
    """Fail unless every exported standard isometric reads precision geometry.

    Runs AFTER the PDF export, the only step that computes a fresh view's
    display geometry and settles ``GetFacettedHlrDisplay`` (see the note above
    ``set_high_quality_shaded_with_edges``), so the flag proves the geometry
    the PDF was cut from. Returns the number of isometric views checked.
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    checked = 0
    for sheet_name in sheet_names:
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(
                f"failed to activate {sheet_name!r} for precision readback"
            )
        for view in iter_views(adapter):
            orientation = str(
                adapter._get_attr_or_call(view, "GetOrientationName") or ""
            )
            if not is_pictorial_orientation(orientation):
                continue
            faceted = adapter._attempt(view.GetFacettedHlrDisplay, default=None)
            if faceted is None or bool(faceted):
                raise RuntimeError(
                    f"{sheet_name} {view_name(adapter, view)!r}: exported isometric "
                    f"is not precision geometry (faceted={faceted!r})"
                )
            checked += 1
    return checked


def assert_asme_b_sheet(
    adapter: Any,
    sheet: Any,
    *,
    layout: DrawingLayout,
    phase: str,
    scale: tuple[float, float] = (1.0, 1.0),
) -> None:
    properties = list(adapter._get_attr_or_call(sheet, "GetProperties2") or [])
    if len(properties) < 7:
        raise RuntimeError(
            f"{phase}: incomplete drawing sheet properties {properties!r}"
        )
    if properties[2:4] != [float(scale[0]), float(scale[1])]:
        raise RuntimeError(
            f"{phase}: drawing sheet scale is not "
            f"{scale[0]:g}:{scale[1]:g}: {properties!r}"
        )
    template = DRAWING_TEMPLATES[layout]
    if (
        abs(properties[5] - template.width_m) > 1e-6
        or abs(properties[6] - template.height_m) > 1e-6
    ):
        raise RuntimeError(
            f"{phase}: drawing sheet is not {layout.value} ASME B size: {properties!r}"
        )


def _contact_preview_grid(page_count: int) -> tuple[int, int]:
    """Return the contact-preview column/row count for a multi-sheet drawing."""
    if page_count < 2:
        raise ValueError(f"contact preview requires at least 2 pages, got {page_count}")
    if page_count <= 4:
        return (2, 2)
    columns = math.ceil(math.sqrt(page_count))
    return (columns, math.ceil(page_count / columns))


@_telemetry.traced("drawing.render_png")
def render_pdf_png(
    pdf: Path,
    png: Path,
    *,
    layout: DrawingLayout,
    expected_pages: int = 1,
    page_layouts: Sequence[DrawingLayout] | None = None,
) -> None:
    """Render a drawing PDF to its preview PNG.

    Single-sheet drawings retain a one-page 300 dpi preview. Multi-sheet
    drawings use the registered preview path for a contact sheet, keeping the
    doit/cache/release artifact contract to one PNG. The historical 2x2 layout
    is retained through four pages; larger drawings use the smallest near-square
    grid that fits every page. Mixed packages validate and render each PDF page
    against its own registered ASME B orientation without stretching the contact
    preview.
    """
    if page_layouts is None:
        layouts = (layout,) * expected_pages
    else:
        layouts = tuple(page_layouts)
        if len(layouts) != expected_pages:
            raise ValueError(
                f"page layout count {len(layouts)} != expected pages {expected_pages}"
            )
        if any(not isinstance(item, DrawingLayout) for item in layouts):
            raise TypeError("every page layout must be a DrawingLayout")
    import pypdfium2 as pdfium
    from PIL import Image

    contact_template = DRAWING_TEMPLATES[layout]
    document = pdfium.PdfDocument(str(pdf))
    if len(document) != expected_pages:
        raise RuntimeError(
            f"drawing PDF has {len(document)} pages, expected {expected_pages}"
        )
    images: list[Any] = []
    for index, page_layout in enumerate(layouts):
        page = document[index]
        page_template = DRAWING_TEMPLATES[page_layout]
        expected_points = (
            page_template.width_m / 0.0254 * 72.0,
            page_template.height_m / 0.0254 * 72.0,
        )
        actual_points = (float(page.get_width()), float(page.get_height()))
        point_tolerance = 72.0 / page_template.dpi + 1e-6
        if any(
            abs(actual - expected) > point_tolerance
            for actual, expected in zip(actual_points, expected_points, strict=True)
        ):
            document.close()
            raise RuntimeError(
                f"PDF page {index + 1} is {actual_points[0]:g} x "
                f"{actual_points[1]:g} pt, expected {expected_points[0]:g} x "
                f"{expected_points[1]:g} pt for {page_layout.value}"
            )
        image = page.render(scale=page_template.dpi / 72.0).to_pil()
        page.close()
        expected_width, expected_height = page_template.pixel_size
        actual_width, actual_height = image.size
        if (
            actual_width in (expected_width, expected_width + 1)
            and actual_height in (expected_height, expected_height + 1)
            and image.size != page_template.pixel_size
        ):
            image = image.crop((0, 0, expected_width, expected_height))
        if image.size != page_template.pixel_size:
            document.close()
            raise RuntimeError(
                f"{page_layout.value} ASME B PNG page {index + 1} is {image.size}, "
                f"expected {page_template.pixel_size}"
            )
        images.append(image)
    document.close()
    png.parent.mkdir(parents=True, exist_ok=True)
    if expected_pages == 1:
        images[0].save(png, dpi=(contact_template.dpi, contact_template.dpi))
        return

    columns, rows = _contact_preview_grid(expected_pages)
    cell_size = (
        contact_template.pixel_size[0] // columns,
        contact_template.pixel_size[1] // rows,
    )
    contact = Image.new("RGB", contact_template.pixel_size, "white")
    for index, image in enumerate(images):
        scale = min(cell_size[0] / image.width, cell_size[1] / image.height)
        preview_size = (
            round(image.width * scale),
            round(image.height * scale),
        )
        cell = image.resize(preview_size, Image.Resampling.LANCZOS)
        column = index % columns
        row = index // columns
        x = column * cell_size[0] + (cell_size[0] - preview_size[0]) // 2
        y = row * cell_size[1] + (cell_size[1] - preview_size[1]) // 2
        contact.paste(cell.convert("RGB"), (x, y))
    contact.save(png, dpi=(contact_template.dpi, contact_template.dpi))


def sanitize_pdf_metadata(pdf: Path, *, title: str, expected_pages: int = 1) -> None:
    """Replace seat/user PDF metadata while preserving the vector page."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(pdf)
    if len(reader.pages) != expected_pages:
        raise RuntimeError(
            f"drawing PDF has {len(reader.pages)} pages, expected {expected_pages}"
        )
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    metadata = {
        "/Title": title,
        "/Author": "Harmonic Analyzer Project",
        "/Subject": "Hobby-machinist manufacturing drawing",
        "/Keywords": "harmonic analyzer, manufacturing drawing, #4-40 UNC",
        "/Creator": "Harmonic Analyzer SolidWorks drawing pipeline",
        "/Producer": "Harmonic Analyzer Project",
    }
    writer.add_metadata(metadata)
    temporary = pdf.with_suffix(".sanitized.pdf")
    try:
        writer.write(temporary)
        temporary.replace(pdf)
    finally:
        temporary.unlink(missing_ok=True)
    reread = PdfReader(pdf).metadata or {}
    for key, value in metadata.items():
        if reread.get(key) != value:
            raise RuntimeError(f"PDF metadata {key} did not sanitize")


@_telemetry.traced("drawing.rebuild", label_param="label")
def rebuild_drawing(adapter: Any, *, label: str) -> None:
    """The one ``EditRebuild3`` chokepoint for drawing recipes.

    Every annotation helper used to call ``EditRebuild3`` inline -- 31 sites
    in this module, a dozen more in top_frame's recipe -- and each one
    regenerates every view on every sheet. Untraced, that cost was ~50 s of
    a 270 s top_frame build with nothing in the trace to attribute it to.
    Routing them here makes each rebuild a ``drawing.rebuild`` span named for
    the helper that asked, so "which helper's rebuilds are worth removing?"
    is read off ``traces.jsonl`` instead of guessed.
    """
    adapter.currentModel.EditRebuild3()


def stamp_drawing_summary(
    adapter: Any, drawing_model: Any, fields: dict[int, str]
) -> None:
    """Write and read-verify the drawing document summary metadata."""
    model_doc = _sw_type_info.early_bound_or_flag(drawing_model, "IModelDoc2")
    for field, value in fields.items():
        # SummaryInfo is a property: early binding splits it into a getter
        # (SummaryInfo(field)) and a setter (SetSummaryInfo(field, value)).
        # A 2-arg SummaryInfo(field, value) put only worked under late binding.
        model_doc.SetSummaryInfo(field, value)
        if model_doc.SummaryInfo(field) != value:
            raise RuntimeError(f"drawing summary field {field} did not persist")


# An isometric/pictorial view's axis-aligned outline is mostly empty diagonal
# space, so its box is not a faithful collision footprint -- give such views
# ``NONE`` collision scope. ``GetOrientationName`` returns the predefined view
# name (e.g. "*Isometric"); ortho views return "*Front"/"*Right"/... and
# projected / section / detail views return "". The part-named octant views
# (``_named_views``, "ISO FRONT-TOP-LEFT") are isometrics of the other seven
# octants and are treated exactly like ``*Isometric`` wherever a pictorial is
# special-cased: this predicate, the finalizer's Shaded With Edges pass and
# the post-export precision assertion.
_PICTORIAL_ORIENTATIONS = frozenset({"*isometric", "*dimetric", "*trimetric"})


_OCTANT_ORIENTATION_PREFIX = "iso "


def is_pictorial_orientation(orientation: str) -> bool:
    """True for ``*Isometric``/``*Dimetric``/``*Trimetric`` and the octant ``ISO …`` views."""
    name = orientation.strip().lower()
    return name in _PICTORIAL_ORIENTATIONS or name.startswith(_OCTANT_ORIENTATION_PREFIX)


@_telemetry.traced("drawing.finalize")
async def finalize_drawing(
    adapter: Any,
    outputs: DrawingOutputs,
    *,
    layout: DrawingLayout,
    pdf_title: str,
    scale: tuple[float, float] = (1.0, 1.0),
    redundant_note_substrings: Sequence[str] = (),
    expected_redundant_notes: int = 0,
    expected_sheet_names: tuple[str, ...] | None = None,
    sheet_layouts: Mapping[str, DrawingLayout] | None = None,
    sheet_scales: Mapping[str, tuple[float, float]] | None = None,
    settled_checks: Sequence[Callable[[], None]] = (),
    checkpoint: Callable[[str], None] | None = None,
) -> dict[str, str]:
    """Enforce the sheet/view contract and export SLDDRW, PDF, and rendered PNG.

    ``settled_checks`` run after the last rebuild, before anything is
    saved: a readback taken when an annotation was placed says nothing
    about the drawing the later rebuilds leave (:func:`assert_balloon_landings`).
    ``checkpoint`` observes each existing native artifact-save boundary and
    drawing close, including failed attempts. It never changes save options.
    """
    if checkpoint is not None and not callable(checkpoint):
        raise TypeError("drawing checkpoint must be callable")
    drawing_model = adapter.currentModel
    ddoc = _early_bound(
        drawing_model, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    drawing_model.ClearSelection2(True)
    # The sheet's own build identifier (title block "BUILD $PRP:{BUILD_ID}"):
    # a DRAWING-document property, not a $PRPSHEET link, so it names the build
    # that made this sheet even when the part it shows is older.
    apply_custom_properties(
        adapter, {DRAWING_BUILD_ID_PROPERTY: _build_id()}, model=drawing_model
    )
    sheet_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if not sheet_names:
        raise RuntimeError("finished drawing has no sheets")
    if expected_sheet_names is not None and sheet_names != expected_sheet_names:
        raise RuntimeError(
            f"drawing sheet contract mismatch: {sheet_names!r} != "
            f"{expected_sheet_names!r}"
        )
    if sheet_layouts is None:
        resolved_layouts = {name: layout for name in sheet_names}
    else:
        if set(sheet_layouts) != set(sheet_names):
            missing = sorted(set(sheet_names) - set(sheet_layouts))
            unknown = sorted(set(sheet_layouts) - set(sheet_names))
            raise ValueError(
                f"sheet layout mapping must cover every sheet exactly; "
                f"missing={missing!r}, unknown={unknown!r}"
            )
        if any(
            not isinstance(sheet_layout, DrawingLayout)
            for sheet_layout in sheet_layouts.values()
        ):
            raise TypeError("every sheet layout must be a DrawingLayout")
        resolved_layouts = dict(sheet_layouts)
    if sheet_scales is not None and set(sheet_scales) != set(sheet_names):
        missing = sorted(set(sheet_names) - set(sheet_scales))
        unknown = sorted(set(sheet_scales) - set(sheet_names))
        raise ValueError(
            f"sheet scale mapping must cover every sheet exactly; "
            f"missing={missing!r}, unknown={unknown!r}"
        )

    # Every sheet owns its own $PRPSHEET link. Point each at that sheet's first
    # real view after all views exist, validate the linked model's tolerance and
    # current-release Revision properties, and hold every sheet to the same ASME B
    # contract.
    for sheet_name in sheet_names:
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to activate drawing sheet {sheet_name!r}")
        sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
        if sheet is None:
            raise RuntimeError(f"drawing sheet {sheet_name!r} has no ISheet")
        sheet_scale = scale if sheet_scales is None else sheet_scales[sheet_name]
        # Inserting a model view lets SolidWorks auto-drift the SHEET scale off
        # the 1:1 the template pinned (each view still carries its own explicit
        # scale), so re-pin it once here before asserting the contract.
        if not sheet.SetScale(
            float(sheet_scale[0]), float(sheet_scale[1]), False, False
        ):
            raise RuntimeError(
                f"failed to set final drawing sheet {sheet_name!r} scale"
            )
        assert_asme_b_sheet(
            adapter,
            sheet,
            layout=resolved_layouts[sheet_name],
            phase=f"before save {sheet_name}",
            scale=sheet_scale,
        )
        properties = list(adapter._get_attr_or_call(sheet, "GetProperties2") or [])
        if len(properties) < 8:
            raise RuntimeError(
                f"sheet {sheet_name!r} has incomplete properties: {properties!r}"
            )
        if bool(properties[7]):
            # PasteSheet preserves the source sheet's "same as sheet specified
            # in Document Properties" flag. In that mode SolidWorks silently
            # ignores a per-sheet CustomPropertyView assignment and returns the
            # literal UI label instead of a view name. Clear the mode through
            # the current ISheet API while preserving every other property.
            sheet.SetProperties2(
                int(properties[0]),
                int(properties[1]),
                float(properties[2]),
                float(properties[3]),
                bool(properties[4]),
                float(properties[5]),
                float(properties[6]),
                False,
            )
            sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
            properties = list(adapter._get_attr_or_call(sheet, "GetProperties2") or [])
            if len(properties) < 8 or bool(properties[7]):
                raise RuntimeError(
                    f"failed to enable explicit property source on {sheet_name!r}"
                )
            assert_asme_b_sheet(
                adapter,
                sheet,
                layout=resolved_layouts[sheet_name],
                phase=f"explicit property source {sheet_name}",
                scale=sheet_scale,
            )
        views = tuple(iter_views(adapter))
        first_view = views[0] if views else None
        if first_view is None:
            raise RuntimeError(
                f"drawing sheet {sheet_name!r} has no view for property links"
            )
        for view in views:
            orientation = str(
                adapter._get_attr_or_call(view, "GetOrientationName") or ""
            )
            if not is_pictorial_orientation(orientation):
                continue
            set_high_quality_shaded_with_edges(
                adapter,
                view,
                label=f"{sheet_name} {view_name(adapter, view)!r}",
            )
        first_name = view_name(adapter, first_view)
        sheet.CustomPropertyView = first_name
        sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
        linked = str(adapter._get_attr_or_call(sheet, "CustomPropertyView") or "")
        if linked != first_name:
            raise RuntimeError(
                f"sheet {sheet_name!r} CustomPropertyView did not take: "
                f"{linked!r} != {first_name!r}"
            )
        linked_model = adapter._get_attr_or_call(first_view, "ReferencedDocument")
        if linked_model is None:
            raise RuntimeError(
                f"view {first_name!r} has no referenced document to validate"
            )
        linked_model = _sw_type_info.early_bound_or_flag(
            linked_model, "IModelDoc2", "GetCustomInfoValue"
        )
        linked_properties = read_required_properties(
            linked_model,
            (
                *TITLE_BLOCK_TOLERANCE_PROPERTIES,
                TITLE_BLOCK_REVISION_PROPERTY,
                TITLE_BLOCK_COPYRIGHT_PROPERTY,
            ),
            required=(
                *TITLE_BLOCK_TOLERANCE_PROPERTIES,
                TITLE_BLOCK_REVISION_PROPERTY,
                TITLE_BLOCK_COPYRIGHT_PROPERTY,
            ),
        )
        # A model stamped for an inch sheet (its package declares
        # ``drawing_unit: in``) prints ASME inch rows, which drop the leading
        # zero (``±.01``; millimetre rows keep it, ``±0.51``). Such a model
        # must sit on an inch sheet: a draw script that forgot its ``unit``
        # would otherwise print inch rows beside millimetre dimensions.
        if linked_properties["TOL_LIN_XX"].startswith("±."):
            linear = _read_member(drawing_model, "Extension").GetUserPreferenceInteger(
                _PREF_UNITS_LINEAR, 0
            )
            if linear != _LENGTH_INCHES:
                raise RuntimeError(
                    f"sheet {sheet_name!r} links {first_name!r}, stamped for an inch "
                    f"sheet, but the drawing's length unit is {linear!r}; pass the "
                    "package's drawing_unit to new_project_drawing"
                )

    # Explicit recipe-requested cleanup remains sheet-scoped. When a standard
    # Isometric view is present, the finalizer owns its high-quality Shaded With
    # Edges mode; every other view keeps the appearance authored by its recipe.
    removed_notes = 0
    # No substrings, no sweep: activating five sheets to match nothing is
    # exactly the cycling a recipe that deletes its own notes is avoiding.
    for sheet_name in sheet_names if redundant_note_substrings else ():
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(
                f"failed to activate drawing sheet {sheet_name!r} for note cleanup"
            )
        removed_notes += sum(
            remove_notes_matching(adapter, substring)
            for substring in redundant_note_substrings
        )
    if removed_notes != expected_redundant_notes:
        raise RuntimeError(
            f"final drawing removed {removed_notes} redundant notes, "
            f"expected {expected_redundant_notes}: "
            f"{tuple(redundant_note_substrings)!r}"
        )
    if removed_notes:
        _telemetry.info(f"removed {removed_notes} redundant final drawing notes")

    # COM can export before SolidWorks recomputes a changed HLR/HLV view's
    # display geometry: a hidden-lines-visible side view exported as a bare
    # outline while the reopened SLDDRW (which regenerates on load) showed the
    # dashed edges. Flush every view's display geometry HERE, after all the
    # rebuilds above and right before export — the same call at view-placement
    # time is invalidated again by the later annotation/table imports. The
    # views come off each ``ISheet`` by name -- ``ISheet::GetViews`` returns
    # the drawing views alone (unlike ``IDrawingDoc::GetViews``, whose per-sheet
    # rows lead with the sheet's own view) -- so no sheet is activated for this.
    for sheet_name in sheet_names:
        sheet = _early_bound(ddoc.Sheet(str(sheet_name)), "ISheet")
        for raw_view in sheet.GetViews() or ():
            _early_bound(raw_view, "IView").UpdateViewDisplayGeometry()

    if not ddoc.ActivateSheet(sheet_names[0]):
        raise RuntimeError("failed to restore first drawing sheet before export")
    # The ONE settling rebuild for the whole print: per-dimension and
    # per-callout helpers no longer rebuild (their readbacks never needed it),
    # so every text extent and view outline is brought current here, before
    # the SLDDRW/PDF that the blind review and the layout audit read.
    rebuild_drawing(adapter, label="finalize_drawing")
    if settled_checks:
        for settled in settled_checks:
            settled()
        # A check may activate the sheet it reads.
        if not ddoc.ActivateSheet(sheet_names[0]):
            raise RuntimeError("failed to restore first drawing sheet after the settled checks")

    # Persist the native drawing and PDF once from the fully loaded authored
    # document. Reopen/scale/save cycles are deliberately absent from this hot
    # path; the template and precomputed recipe placements own the layout.
    # One child span per SaveAs3: an assembly drawing's save_and_export_pdf
    # runs 42-180 s (harmonic_analyzer_assembly p50 177 s) and nothing said
    # whether the SLDDRW save or the PDF export spends it. The PDF's span also
    # carries the shaded-raster DPI it was printed at (pdf_shaded_raster_dpi).
    with _telemetry.span("drawing.save_and_export_pdf"):
        artifacts = save_drawing(
            adapter,
            str(outputs.slddrw),
            pdf_path=str(outputs.pdf),
            artifact_context=lambda kind, path: _drawing_artifact_save(
                adapter, kind, path, checkpoint
            ),
        )
    if set(artifacts) != {"drawing", "pdf"}:
        raise RuntimeError(f"drawing save/export incomplete: {artifacts!r}")
    # The export just computed every view; the precision flag is truthful now.
    assert_precise_isometric_views(adapter, sheet_names)
    sanitize_pdf_metadata(outputs.pdf, title=pdf_title, expected_pages=len(sheet_names))
    render_pdf_png(
        outputs.pdf,
        outputs.png,
        layout=layout,
        expected_pages=len(sheet_names),
        page_layouts=tuple(resolved_layouts[name] for name in sheet_names),
    )
    artifacts["png"] = str(outputs.png.resolve())
    if set(artifacts) != {"drawing", "pdf", "png"}:
        raise RuntimeError(f"drawing export incomplete: {artifacts!r}")
    # Every sheet of every drawing is audited on the finished, still-open
    # document, next to the PDF it printed (``_drawing_layout_audit``). Under
    # GATE a finding fails the leaf, so no artefact is stored.
    run_layout_audit(
        adapter,
        stem=outputs.slddrw.stem,
        pdf=outputs.pdf,
        report=layout_report_path(outputs.slddrw.stem),
        sheet_layouts=resolved_layouts,
        is_pictorial=is_pictorial_orientation,
    )
    # Release the file: SolidWorks keeps the saved SLDDRW open past the COM
    # session, and the next run (or a from-scratch rebuild deleting the
    # target) then hits "in use by another process".
    title = str(drawing_model.GetTitle())
    with _drawing_checkpoint(checkpoint, "drawing_close"):
        adapter.swApp.CloseDoc(title)
    still_open = [
        p
        for p in _visible_document_paths(adapter)
        if Path(p).resolve() == outputs.slddrw.resolve()
    ]
    if still_open:
        raise RuntimeError(f"drawing {title!r} did not close after export")
    return artifacts
