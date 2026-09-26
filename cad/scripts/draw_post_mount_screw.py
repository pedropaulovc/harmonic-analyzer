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
the Front view carries no break dimension.  A 10:1 view of the tip carries
it instead as the single limit "0.1 MAX" (the model's CutEndBreak at
swTolMAX, generated from the spec band).  CutEndBreak is a driving
dimension of the deburr cutter's profile.  The tip view is NOT a detail
view: no detail child of the Front ever offered CutEndBreak to an import
(see ``cropped_tip_view``), so it is a standalone 10:1 *Front model view,
moved to the tip and cropped to the detail's fence, that imports the break
by feature.  It reads as a detail on the sheet: a "DETAIL A  SCALE 10:1"
label owned by the view, and a circle and letter "A" on the Front at the
tip.  The Front is re-activated before the notes so they do not land in
the tip view.  The only
note says to deburr the cut end and that the
undimensioned purchased geometry is reference.  No installation sequence, engagement figure or rule
number is printed: the sequence is an MHA-A03 assembly step and the
engagement a model assert (Main's eye pass of warm-c486, policy rule 6).

Run with SolidWorks open::

    uv run python cad\scripts\draw_post_mount_screw.py post-mount-screw
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _telemetry
from _common import _early_bound, check, run_build
import _drawing_common
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    finalize_drawing,
    new_project_drawing,
    dimension_name,
    model_point_in_view,
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
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FRONT_VIEW_DIMENSIONS,
    HEAD_H_MM,
    THREAD_DIA_MM,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view, view_name

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

# The 10:1 tip view (a cropped model view that reads as detail A): its crop
# centres on the axis 1 mm above the cut end with a 3.6 mm fence, so both
# ends of the break's radial leg (r 3.075 and 3.175 on the end face) sit
# inside the crop -- a cropped view drops any dimension whose reference lies
# outside it.  It sits between the Front view and the isometric, above the
# note block and clear of the title block.  TIP_DETAIL keeps the sheet
# constants: the crop fence, the label's place and the Front letter's offset.
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
TIP_LETTER = "A"
TIP_VIEW_LABEL = (
    f"DETAIL {TIP_LETTER}  SCALE {DETAIL_SCALE[0]:g}:{DETAIL_SCALE[1]:g}"
)
_CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError


def _detail_point(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet position of a Front-view model point inside the tip view."""
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


def _sketch_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    label: str,
) -> Any:
    """Sketch a circle in ``view``'s own sketch from SHEET coordinates.

    The sheet points go through the view sketch's ModelToSketchTransform
    (the cylinder-gear notch-fence recipe), so the circle lands where the
    sheet says whatever the view's scale.  The caller activates the view;
    the new circle is left SELECTED, which is what Crop2 consumes.
    """
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    circle = manager.CreateCircle(*points[0], *points[1])
    if circle is None:
        raise RuntimeError(f"cannot sketch the {label} circle")
    return circle


def _activate(adapter: Any, view: Any, *, label: str) -> str:
    name = view_name(adapter, view)
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _note_texts(view: Any) -> list[str]:
    return [
        str(_early_bound(note, "INote").GetText())
        for note in (_early_bound(view, "IView").GetNotes() or ())
    ]


def cropped_tip_view(adapter: Any) -> Any:
    """The 10:1 tip view: a standalone *Front model view, NOT a detail.

    Measured (diag/mha142-bisect, b6552f13b, farm worker swmaker000008): no
    detail child of the Front offered CutEndBreak to the model-item import
    under 10:1 HLR, 10:1 HLV, 5:1 and 2:1, imported before or after the
    Front's own import -- every one returned available=[], as the 10:1 HLR
    detail had in pms857-f543 (hidden reference sketch, source 1), -56f7
    (cutter profile, source 1), -6099 (cutter profile, source 0) and 918-top
    (source 0 after a visible-entity pre-read).  diag-9eca's lone detail
    success was not reproduced by replaying its pre-reads.  The same *Front
    placed at 10:1, moved so the tip lands on DETAIL_CENTER and cropped by a
    sketch circle (IView.Crop2 status 1, IsCropped True, HLR) imported
    CutEndBreak twice in that leaf.  So the crop, not a detail, carries it.

    Sequence: place_view at 10:1; move by the tip reference point's sheet
    error (ModelToViewTransform, SetViewPosition); ActivateView; a circle of
    the detail fence's sheet radius in the view's own sketch; Crop2 straight
    after it, while the circle is still the selection; an IsCropped
    read-back that raises.
    """
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != DETAIL_SCALE:
        raise RuntimeError(f"tip view scale {ratio!r}, expected {DETAIL_SCALE!r}")
    reference = tuple(value / 1000 for value in TIP_DETAIL.detail_reference_mm)
    tip = model_point_in_view(adapter, view, reference, label="tip view reference")
    position = tuple(float(value) for value in view.Position)
    target = [position[i] + DETAIL_CENTER[i] - tip[i] for i in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("cannot move the tip view onto its sheet position")
    draw.EditRebuild3()
    center = model_point_in_view(adapter, view, reference, label="tip view reference")
    if math.dist(center, DETAIL_CENTER) > 1e-6:
        raise RuntimeError(
            f"tip view reference sits at {center!r}, not {DETAIL_CENTER!r}"
        )
    _activate(adapter, view, label="tip view")
    _sketch_circle(adapter, view, center, DETAIL_RADIUS, label="tip view crop")
    status = int(view.Crop2(False, False, 5))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    cropped = bool(view.IsCropped())
    _telemetry.info(
        f"tip view {view_name(adapter, view)!r}: {ratio[0]:g}:{ratio[1]:g}, "
        f"Crop2 status {status}, IsCropped {cropped}"
    )
    if status != _CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"tip view is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    return view


def _curate_tip_view(adapter: Any, view: Any) -> list[Any]:
    """Import the break into the tip view by feature: only the deburr
    cutter's CutEndDeburrProfile is selected (source 1), never the entire
    model.  The cropped model view's entire-model import delivered it in
    b6552f13b; the targeted form is the one the Front already uses."""
    return _drawing_common.curate_view_dimensions(
        adapter,
        view,
        keep=DETAIL_KEEP,
        view_label="tip view break",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )


def label_tip_view(adapter: Any, view: Any) -> None:
    """Label the tip view "DETAIL A  SCALE 10:1".

    A model view has no native label the API can show (only detail, section
    and auxiliary views carry one; swDetailingOrthoViewLabelsEnableShow is
    documented "Not used"), so the label is a note inserted while the tip
    view is ACTIVE: the view owns it (IView.GetNotes) and it moves with the
    view.  Read back: the tip view carries exactly that one note.
    """
    _activate(adapter, view, label="tip view")
    if add_note(adapter, TIP_VIEW_LABEL, *TIP_DETAIL.detail_label_xy) is None:
        raise RuntimeError("failed to add the tip view label")
    texts = _note_texts(view)
    if texts != [TIP_VIEW_LABEL]:
        raise RuntimeError(
            f"tip view label did not land in the tip view: its notes are {texts!r}"
        )


def mark_tip_on_front(adapter: Any, front: Any) -> None:
    """Circle the tip on the Front and letter it "A", so the machinist finds
    detail A: a sketch circle of the tip view's crop fence (1:1) around the
    same reference point, and a note "A" owned by the Front.  Both are
    sheet-authored annotation, not dimensions."""
    _activate(adapter, front, label="Front view")
    reference = tuple(value / 1000 for value in TIP_DETAIL.detail_reference_mm)
    center = model_point_in_view(adapter, front, reference, label="Front tip mark")
    radius = DETAIL_FENCE_MM * SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
    _sketch_circle(adapter, front, center, radius, label="Front tip mark")
    adapter.currentModel.ClearSelection2(True)
    offset = TIP_DETAIL.parent_letter_offset
    if add_note(adapter, TIP_LETTER, center[0] + offset[0], center[1] + offset[1]) is None:
        raise RuntimeError("failed to letter the Front's tip mark")
    texts = _note_texts(front)
    if texts.count(TIP_LETTER) != 1:
        raise RuntimeError(f"Front tip letter did not land in the Front: {texts!r}")


def activate_front_for_notes(adapter: Any, front: Any) -> None:
    """Make the Front the active view before the property-linked notes.

    A note lands in the ACTIVE view: with a detail active, the four notes
    landed inside it (pms857-diag-9eca, "found 5" notes on the detail).
    """
    name = view_name(adapter, front)
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate the Front view {name!r} for the notes")


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


def _verify_tip_view(adapter: Any, front: Any, tip: Any) -> None:
    """Seat read-back: the tip view is cropped at its scale, carries the one
    break dimension as a MAX limit reading the spec's text, and the Front
    does not."""
    view = _early_bound(tip, "IView")
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != DETAIL_SCALE:
        raise RuntimeError(f"tip view scale {ratio!r}, expected {DETAIL_SCALE!r}")
    if not bool(view.IsCropped()):
        raise RuntimeError("tip view is no longer cropped")
    names = [name for name in _view_dimension_names(adapter, tip) if name]
    if names != [CUT_END_BREAK_DIMENSION]:
        raise RuntimeError(
            f"tip view must carry exactly one {CUT_END_BREAK_DIMENSION}: {names}"
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
            f"tip view break reads {text!r} (type {tol_type}, parenthesis "
            f"{parenthesis}), expected {CUT_END_BREAK_TEXT!r}"
        )
    _telemetry.success(f"tip view {ratio[0]:g}:{ratio[1]:g} reads {text}")


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

    # The break is the deburr cutter's own dimension, imported by feature
    # into the cropped 10:1 tip view (see cropped_tip_view), which is then
    # labelled as detail A and circled and lettered on the Front.
    with _telemetry.span("drawing.tip_view", scale=f"{DETAIL_SCALE[0]:g}:1"):
        tip = cropped_tip_view(adapter)
        set_hidden_lines_removed(adapter, tip)
        _early_bound(tip, "IView").UpdateViewDisplayGeometry()
        tip_annotations = _curate_tip_view(adapter, tip)
        assert_imported_precision(adapter, tip_annotations, DETAIL_PRECISION)
        _verify_tip_view(adapter, front, tip)
    label_tip_view(adapter, tip)
    mark_tip_on_front(adapter, front)

    activate_front_for_notes(adapter, front)
    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.003
    )
    for name, x, y in STOCK_ROWS:
        add_property_linked_note(adapter, name, x, y, char_height=0.003)

    set_hidden_lines_removed(adapter, front)
    # Re-read after the last rebuilds, before the save.
    _verify_tip_view(adapter, front, tip)
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
