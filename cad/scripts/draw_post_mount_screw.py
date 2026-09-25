r"""Create the modified-stock drawing for the MHA-142 cone pivot post mount screw.

MSC 40923898 is bought by SKU and cut to length, so the sheet is a
modified-purchased-part drawing (the boss hook's pattern), not the purchased
reference sheet: a Front view carrying the cut length -- the part's hidden
reference-sketch dimension, imported at its model-owned places -- and an
isometric, both 1:1.  No single length suits every in-band post and plate
(post_mount_screw_spec's U27 check), so the length prints as a REFERENCE,
"(86.0)", with no band and the cut-to-fit acceptance beneath it: cut at
assembly, end flush to the spec band's allowance short of the MHA-091
underside, never proud (post_mount_screw_spec.CUT_TO_FIT_CALLOUT -- no MHA-A03
procedure sheet exists to carry it, Codex P1 on #857).  The cut end's break
is a deburr (Main's MHA-142 eye pass on #857): a 0.1 dimension at 1:1 is
illegible and its printed +0/-0.1 band read as allowing no break at all, so
the Front view carries no break dimension.  A 10:1 detail of the tip carries
it instead as the single limit "0.1 MAX" (the model's CutEndBreak at
swTolMAX, generated from the spec band).  CutEndBreak lives on a part-hidden
reference sketch, and a detail takes a hidden sketch's visibility from the
part when it is created, so the detail is created and dimensioned inside
``part_sketches_shown`` (the cone tip block's section A recipe, lever probe
c0514e35).  The only note says to deburr the cut end and that the
undimensioned purchased geometry is reference.  No installation sequence, engagement figure or rule
number is printed: the sequence is an MHA-A03 assembly step and the
engagement a model assert (Main's eye pass of warm-c486, policy rule 6).

Run with SolidWorks open::

    uv run python cad\scripts\draw_post_mount_screw.py post-mount-screw
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _stock_trim_drawing as trim_drawing
import _telemetry
from _common import _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    finalize_drawing,
    new_project_drawing,
    dimension_name,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _stock_trim_drawing import TrimSheet
from post_mount_screw_spec import (
    CUT_END_BREAK_DIMENSION,
    CUT_END_BREAK_MAX_MM,
    CUT_END_BREAK_TEXT,
    CUT_END_BREAK_TOL_TYPE,
    CUT_LENGTH_DIMENSION,
    CUT_LENGTH_MM,
    CUT_TO_FIT_CALLOUT,
    DETAIL_SKETCHES,
    DETAIL_VIEW_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FRONT_VIEW_DIMENSIONS,
    HEAD_H_MM,
    THREAD_DIA_MM,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["post_mount_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
TITLE = "Cone Pivot Post Mount Screw — Modified Stock Drawing"

SHEET_SCALE = (1.0, 1.0)
# The screw stands head up in the Front view: under-head face at model y 0,
# cut end at -CUT_LENGTH_MM, head top ~6 above.
FRONT_CENTER = (0.100, 0.165)
ISO_CENTER = (0.270, 0.185)
# The cut length reads on the left, where its reference line runs along the
# shank's silhouette, midway along the span, far enough out that its
# four-line acceptance callout (22 capitals at its widest) clears the head
# and stays inside the border.
# The cut end's break is not dimensioned in this 1:1 view (see the module
# docstring).  (The view is placed by its outline's centre: the end face is
# half the screw's overall height below it.)
TIP_Y = FRONT_CENTER[1] - (CUT_LENGTH_MM + HEAD_H_MM) / 2000.0
FRONT_KEEP = {
    CUT_LENGTH_DIMENSION: (FRONT_CENTER[0] - 0.047, FRONT_CENTER[1]),
}
DIMENSION_CALLOUTS = {CUT_LENGTH_DIMENSION: CUT_TO_FIT_CALLOUT}

# The 10:1 tip detail: its crop centres on the axis 1 mm above the cut end
# with a 3.6 mm fence, so both ends of the break's radial leg (r 3.075 and
# 3.175 on the end face) sit inside the crop -- a detail drops any dimension
# whose reference lies outside it.  It sits between the Front view and the
# isometric, above the note block and clear of the title block.
DETAIL_SCALE = (10.0, 1.0)
DETAIL_FENCE_MM = 3.6
DETAIL_OFFSET_MM = 1.0
DETAIL_CENTER = (0.190, 0.175)
DETAIL_RADIUS = DETAIL_FENCE_MM * DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
TIP_DETAIL = TrimSheet(
    sheet_scale=SHEET_SCALE,
    detail_center=DETAIL_CENTER,
    detail_scale=DETAIL_SCALE,
    fence_radius_mm=DETAIL_FENCE_MM,
    cut_end_y_mm=-CUT_LENGTH_MM,
    detail_offset_mm=DETAIL_OFFSET_MM,
    detail_label_xy=(
        DETAIL_CENTER[0] - 0.020,
        DETAIL_CENTER[1] - DETAIL_RADIUS - 0.010,
    ),
    parent_letter_offset=(0.008, 0.006),
)


def _detail_point(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet position of a Front-view model point inside the tip detail."""
    ratio = DETAIL_SCALE[0] / DETAIL_SCALE[1]
    ref_y = -CUT_LENGTH_MM + DETAIL_OFFSET_MM
    return (
        DETAIL_CENTER[0] + ratio * x_mm / 1000.0,
        DETAIL_CENTER[1] + ratio * (y_mm - ref_y) / 1000.0,
    )


# The break's text sits below the end face, under the right-hand rim.
BREAK_RIM_XY = _detail_point(THREAD_DIA_MM / 2.0, -CUT_LENGTH_MM)
DETAIL_KEEP = {
    CUT_END_BREAK_DIMENSION: (BREAK_RIM_XY[0] - 0.006, BREAK_RIM_XY[1] - 0.012)
}
FRONT_PRECISION = {
    CUT_LENGTH_DIMENSION: DRAWING_PRECISION_BY_NAME[CUT_LENGTH_DIMENSION]
}
DETAIL_PRECISION = {
    CUT_END_BREAK_DIMENSION: DRAWING_PRECISION_BY_NAME[CUT_END_BREAK_DIMENSION]
}
# Below the Front view (its lower end ~0.119), above the stock rows.
NOTES_XY = (0.016, 0.100)
STOCK_ROWS = (
    ("Supplier", 0.016, 0.060),
    ("Supplier SKUs", 0.080, 0.060),
    ("Stock Name", 0.016, 0.049),
)


def _view_dimension_names(adapter: Any, view: Any) -> list[str]:
    return [
        dimension_name(adapter, _early_bound(item, "IAnnotation"))
        for item in (_early_bound(view, "IView").GetAnnotations() or ())
    ]


def break_text(value_mm: float, places: int, tol_type: int, prefix: str, suffix: str) -> str:
    """The break dimension's printed text, composed from its read-back parts.

    The API exposes no rendered string for a toleranced value, so the seat
    check composes it: value at its places, the MAX limit when the type is
    swTolMAX, and whatever prefix and suffix the display carries.
    """
    limit = " MAX" if tol_type == CUT_END_BREAK_TOL_TYPE else ""
    return f"{prefix}{value_mm:.{places}f}{limit}{suffix}"


def _verify_tip_detail(adapter: Any, front: Any, detail: Any) -> None:
    """Seat read-back: the detail exists at its scale, carries the one break
    dimension as a MAX limit reading the spec's text, and the Front does not."""
    view = _early_bound(detail, "IView")
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != DETAIL_SCALE:
        raise RuntimeError(f"tip detail scale {ratio!r}, expected {DETAIL_SCALE!r}")
    names = _view_dimension_names(adapter, detail)
    if names.count(CUT_END_BREAK_DIMENSION) != 1:
        raise RuntimeError(
            f"tip detail must carry one {CUT_END_BREAK_DIMENSION}: {names}"
        )
    front_names = _view_dimension_names(adapter, front)
    if CUT_END_BREAK_DIMENSION in front_names:
        raise RuntimeError(f"Front view still carries the 1:1 break: {front_names}")
    annotation = next(
        _early_bound(item, "IAnnotation")
        for item in view.GetAnnotations()
        if dimension_name(adapter, _early_bound(item, "IAnnotation"))
        == CUT_END_BREAK_DIMENSION
    )
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    value_mm = float(dimension.SystemValue) * 1000.0
    places = int(display.GetPrimaryPrecision2())
    tol_type = int(tolerance.Type)
    parenthesis = bool(display.ShowParenthesis)
    text = break_text(
        value_mm,
        places,
        tol_type,
        str(display.GetText(1) or ""),  # swDimensionTextPrefix
        str(display.GetText(2) or ""),  # swDimensionTextSuffix
    )
    _telemetry.event(
        "drawing.tip_detail_break",
        text=text,
        value_mm=value_mm,
        places=places,
        tol_type=tol_type,
        parenthesis=parenthesis,
        scale=f"{ratio[0]:g}:{ratio[1]:g}",
    )
    if (
        tol_type != CUT_END_BREAK_TOL_TYPE
        or abs(value_mm - CUT_END_BREAK_MAX_MM) > 1e-9
        or parenthesis
        or text != CUT_END_BREAK_TEXT
    ):
        raise RuntimeError(
            f"tip detail break reads {text!r} (type {tol_type}, parenthesis "
            f"{parenthesis}), expected {CUT_END_BREAK_TEXT!r}"
        )
    _telemetry.success(f"tip detail {ratio[0]:g}:{ratio[1]:g} reads {text}")


def _reference_cut_length(adapter: Any, annotations: list[Any]) -> None:
    """Re-read the imported cut length, then mark it reference.

    It must be the model's nominal and carry NO band (swTolNONE): a band
    would promise a fixed length the post and plate bands cannot honour.
    """
    for annotation in annotations:
        if dimension_name(adapter, annotation) != CUT_LENGTH_DIMENSION:
            continue
        display = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if abs(float(dimension.SystemValue) - CUT_LENGTH_MM / 1000.0) > 1e-9:
            raise RuntimeError(
                f"cut length {float(dimension.SystemValue)!r} m is not the "
                f"modelled {CUT_LENGTH_MM} mm"
            )
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 0:  # swTolNONE
            raise RuntimeError("cut length carries a band; it must be reference")
        set_reference_dimension(adapter, annotation, label="cut length")
        return
    raise RuntimeError("Front view has no cut length to mark reference")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open cut post mount screw", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Stock Name",
        "Supplier",
        "Supplier SKUs",
        "Manufacturing Notes",
    )
    read_required_properties(adapter.currentModel, required, required=required)
    source_model = adapter.currentModel
    draw, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: TITLE,
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-142; MSC Industrial Supply 40923898",
            4: "Native dimension-driven cut length",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    # The cut length lives on a part-hidden reference sketch, so the Front
    # view takes the opt-in curation that shows it in this view only.
    annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="cut length",
        dimensions_by_feature=FRONT_VIEW_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, FRONT_PRECISION)
    _reference_cut_length(adapter, annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)

    # The break lives on a part-hidden sketch: create and dimension the
    # detail while the part shows it (a detail ignores per-view overrides).
    with _telemetry.span("drawing.tip_detail", scale=f"{DETAIL_SCALE[0]:g}:1"):
        with hidden_sketches.part_sketches_shown(
            adapter, source_model, DETAIL_SKETCHES, label="tip detail break"
        ):
            detail = trim_drawing.end_detail(adapter, front, TIP_DETAIL)
            set_hidden_lines_removed(adapter, detail)
            _early_bound(detail, "IView").UpdateViewDisplayGeometry()
            detail_annotations = hidden_sketches.curate_view_dimensions(
                adapter,
                detail,
                keep=DETAIL_KEEP,
                view_label="tip detail break",
                dimensions_by_feature=DETAIL_VIEW_DIMENSIONS,
            )
        assert_imported_precision(adapter, detail_annotations, DETAIL_PRECISION)
        _verify_tip_detail(adapter, front, detail)

    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.003
    )
    for name, x, y in STOCK_ROWS:
        add_property_linked_note(adapter, name, x, y, char_height=0.003)

    set_hidden_lines_removed(adapter, front)
    trim_drawing.position_detail_label(adapter, detail, TIP_DETAIL)
    trim_drawing.position_parent_detail_letter(adapter, front, TIP_DETAIL)
    # Re-read after the label moves and the last rebuilds, before the save.
    _verify_tip_detail(adapter, front, detail)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title=TITLE,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
