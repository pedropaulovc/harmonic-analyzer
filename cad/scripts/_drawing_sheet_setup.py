"""Blank project-sheet setup, independent of manufacturing annotations/layout.

Preparation keys follow this module and its actual validator dependencies. Keep
later view, callout and export operations in their own drawing helpers.
"""

from __future__ import annotations

from typing import Any

from _common import _early_bound
from _drawing_registry import PROJECT_DRWDOT
import _telemetry
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import new_drawing, set_units_mm


# swAnnotationType_e.swNote -- the view-owned annotation TYPE that becomes a
# free-standing layout element (the general-notes block, schedule cells). Tables
# are enumerated separately via IView.GetTableAnnotations.
_ANNOT_NOTE = 6

_OLD_EDGE_BREAK_NOTE = "REMOVE BURRS AND BREAK SHARP EDGES R.01 OR CHAMFER .01 MAX"
_METRIC_EDGE_BREAK_NOTE = "REMOVE BURRS AND BREAK SHARP EDGES R0.25 OR CHAMFER 0.25 MAX"

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

ASME_B_WIDTH_M = 0.4318
ASME_B_HEIGHT_M = 0.2794


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
    property_view: str | None = None,
    scale: tuple[float, float] = (1.0, 1.0),
    decimals: int = 2,
) -> tuple[Any, Any]:
    """Create a drawing from the hand-made project template.

    The template embeds its own ASME B sheet format (title block, tolerance
    block, projection symbol), so there is no SetupSheet6 format re-apply; the
    only per-drawing knobs are the sheet scale (here) and WHICH view's model
    feeds the sheet's $PRPSHEET property links -- linked in finalize_drawing,
    once views exist (SolidWorks silently ignores a CustomPropertyView naming a
    view that does not exist yet, falling back to 'Default' = first view).
    ``property_view`` is accepted for compatibility and unused.
    """
    _ = property_view
    if not PROJECT_DRWDOT.is_file() or PROJECT_DRWDOT.stat().st_size == 0:
        raise FileNotFoundError(
            f"project drawing standard is missing: {PROJECT_DRWDOT}"
        )

    draw = new_drawing(
        adapter,
        template=str(PROJECT_DRWDOT),
        width=ASME_B_WIDTH_M,
        height=ASME_B_HEIGHT_M,
    )
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    # A hand-saved template can be saved while in Edit Sheet Format mode (it
    # was, the day the title block was drawn) -- a drawing created from it then
    # opens with the FORMAT layer active, where every pick lands on the sheet
    # format and view geometry is inert (all typed SelectByID2 picks fail).
    # EditSheet() drops back to the sheet layer; idempotent when already there.
    ddoc.EditSheet()
    _normalize_metric_edge_break_note(adapter, ddoc)
    sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("project drawing template has no current sheet")
    # 2 decimals by default: 3-decimal display (76.000) reads as false precision
    # next to the ±0.25 blanket tolerance. A drawing that genuinely needs finer
    # display (an exact inch conversion like 9.525) can pass decimals=3.
    set_units_mm(adapter, decimals=decimals)
    _pin_dimension_text_and_leader_style(draw)
    if not sheet.SetScale(float(scale[0]), float(scale[1]), True, False):
        raise RuntimeError(f"failed to force ASME B sheet to {scale[0]:g}:{scale[1]:g}")
    assert_asme_b_sheet(adapter, sheet, phase="initial setup", scale=scale)
    # Normalize the viewport: sheet-coordinate picks (the hole-table datum
    # vertex / hole rims) hit-test with a PIXEL tolerance mapped through the
    # current zoom, and a hand-saved template opens at whatever zoom it was
    # saved with (the old generated one happened to be saved fit). Fit once so
    # coordinate picks are deterministic regardless of how the template binary
    # was last saved.
    draw.ViewZoomtofit2()
    draw.ForceRebuild3(False)
    draw.EditRebuild3()
    return draw, sheet


@_telemetry.traced("drawing.normalize_edge_break")
def _normalize_metric_edge_break_note(adapter: Any, ddoc: Any) -> None:
    """Replace the template's inch-origin edge break with its metric value."""
    sheet_view = adapter._attempt(lambda: ddoc.GetFirstView())
    if sheet_view is None:
        raise RuntimeError("drawing template has no sheet view for note normalization")
    annotations = (
        adapter._attempt(
            lambda: adapter._get_attr_or_call(sheet_view, "GetAnnotations")
        )
        or []
    )
    matched = 0
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetType", "GetSpecificAnnotation"
        )
        if int(adapter._get_attr_or_call(annotation, "GetType") or 0) != _ANNOT_NOTE:
            continue
        specific = adapter._attempt(
            lambda a=annotation: adapter._get_attr_or_call(a, "GetSpecificAnnotation")
        )
        if specific is None:
            continue
        note = _sw_type_info.early_bound_or_flag(
            specific, "INote", "GetText", "SetText"
        )
        raw = str(adapter._get_attr_or_call(note, "GetText") or "")
        normalized = " ".join(raw.upper().split())
        if normalized not in {_OLD_EDGE_BREAK_NOTE, _METRIC_EDGE_BREAK_NOTE}:
            continue
        matched += 1
        if normalized == _METRIC_EDGE_BREAK_NOTE:
            continue
        changed = adapter._attempt(
            lambda n=note: n.SetText(_METRIC_EDGE_BREAK_NOTE), default=False
        )
        if not changed:
            raise RuntimeError("failed to replace drawing edge-break note")
        applied = " ".join(
            str(adapter._get_attr_or_call(note, "GetText") or "").upper().split()
        )
        if applied != _METRIC_EDGE_BREAK_NOTE:
            raise RuntimeError(
                f"drawing edge-break note replacement did not persist: {applied!r}"
            )
    if matched != 1:
        raise RuntimeError(
            "drawing template must contain exactly one recognized edge-break "
            f"note, found {matched}"
        )
    _telemetry.event("drawing.edge_break_normalized", value_mm=0.25)


def assert_asme_b_sheet(
    adapter: Any, sheet: Any, *, phase: str, scale: tuple[float, float] = (1.0, 1.0)
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
    if (
        abs(properties[5] - ASME_B_WIDTH_M) > 1e-6
        or abs(properties[6] - ASME_B_HEIGHT_M) > 1e-6
    ):
        raise RuntimeError(f"{phase}: drawing sheet is not ASME B size: {properties!r}")
