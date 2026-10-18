r"""Create the curated machinist drawing for the pinion engage lever.

A turned hub slipped over the MHA-DT-017 lift rod's front end, with a straight Ø6
grip rod rising out of it; the MHA-DT-030 pin (U36) match-drilled through hub and rod at
assembly carries the drive.  The 1:1 front view carries the hub and grip sizes,
the projected top view the crown, and section A-A (in the side view's place)
cuts the lever down the grip axis so the blind bore, its flat floor and the
end wall print in solid lines (rule 9).  A 3:1 detail of the section carries
the hub's axial stations -- grip axis, pin hole, bore depth and overall
length to the crown apex, all baselined from the flat mouth face B.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_pinion_lever.py dt-pinion-lever
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from dt_drive_train_steps import step_ref
from dt_pinion_lever_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HUB_OD,
    LIFT_ROD_NUMBER,
    PIN_HOLE_CALLOUT,
    REFERENCE_SKETCHES,
    ROD_LEN,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_pinion_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0

# Third-angle orthographic views stay aligned around the front view: section
# A-A takes the side view's place on its Y station, the top view shares its X
# station.  The front view's box spans the hub's bottom (-HUB_OD/2) to the
# grip tip (ROD_LEN).
FRONT_BBOX_CY = (ROD_LEN - HUB_OD / 2.0) / 2.0
FRONT_CENTER = (0.070, 0.160)
SECTION_CENTER = (0.135, FRONT_CENTER[1])
TOP_CENTER = (FRONT_CENTER[0], 0.240)
# ENFORCE r1 (#1011): the blind bore was never drawn (the side view showed only
# the outside, its 8.0 FLAT BOTTOM ran to an undrawn floor).  Section A-A cuts
# the front view down the grip axis, model x 0, from below the hub to past the
# grip tip; its caption rides above the grip tip, where the sheet is empty
# (below, the front view's bore callout and the isometric note crowd it).
SECTION_LINE_MODEL_MM = ((0.0, -HUB_OD / 2.0 - 3.0, 0.0), (0.0, ROD_LEN + 4.0, 0.0))
SECTION_SCALE = (1, 1)
SECTION_LABEL_XY = (SECTION_CENTER[0], 0.218)
# Between section A-A (x <= 0.142) and the detail fence (x >= 0.218), so the
# field right of the detail is free for the pin-hole callout.
ISO_CENTER = (0.184, 0.142)
DETAIL_CENTER = (0.245, 0.170)
DETAIL_SCALE = (3, 1)
DETAIL_RADIUS_MM = 9.0
# r7 eye-pass: at (0.228, 0.128) the label sat on the 8.0 FLAT BOTTOM text;
# the label rides right of the detail, clear of the fence (x <= 0.263 at
# this height).
DETAIL_LABEL_XY = (0.300, 0.150)
_DS = DETAIL_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * _S


ROD_DIA_TEXT_Y = 20.0  # model height of the rod-diameter text, clear of the hub


FRONT_KEEP = {
    "HubOd": (0.030, _front_y(-HUB_OD / 2.0) - 0.010),
    "HubBore": (0.105, _front_y(-HUB_OD / 2.0) - 0.014),
    "RodTipY": (0.035, FRONT_CENTER[1] + 0.010),
    "RodDia": (0.105, _front_y(ROD_DIA_TEXT_Y)),
}
TOP_KEEP = {"CapR": (0.105, TOP_CENTER[1] + 0.012)}
# Section A-A keeps the old side view's frame (B, the mouth face at model
# z +5, the LEFT end; the crown the right; the grip up), and its detail keeps
# it at 3:1, so a model (z, y) lands at DETAIL_CENTER + (-z, y) * 3:1.
# r7 eye-pass: the pin-hole callout sat across the hub outline.  Converged-r7
# review: a leader dropping between the top stations read as the GRIP AXIS
# extension line, so the callout sits right of the detail with its underline
# at hole height and a short, near-horizontal leader (the isometric moved out
# of that field).  ENFORCE r1 (#1011): every axial station is a baseline from
# B, stacked below the hub with the overall length outermost, so no witness
# line crosses another dimension: the bore depth reads left of B, the pin
# station and the overall length between their witness lines.
DETAIL_TEXT_MODEL_MM = {
    "GripFromB": (6.7, 10.7),
    "PinHoleFromB": (3.0, -10.3),
    "BoreDepthFromB": (10.0, -14.8),
    "OverallFromB": (-1.0, -19.3),
    "PinHoleDia": (-28.3, 2.7),
}
DETAIL_KEEP = {
    name: (DETAIL_CENTER[0] - z * _DS, DETAIL_CENTER[1] + y * _DS)
    for name, (z, y) in DETAIL_TEXT_MODEL_MM.items()
}
LEVER_PIN_SET_STEP_KEY = "lever-pin-set"
DIMENSION_CALLOUTS = {
    "HubBore": f"BORE OR REAM\nSLIP ON {LIFT_ROD_NUMBER}",
    "BoreDepthFromB": "FLAT BOTTOM",
    "RodTipY": "FROM HUB AXIS",
    "GripFromB": "GRIP AXIS",
    # Drilled at MHA-DT-000's LEVER PIN SET; the pointer comes from the registry.
    "PinHoleDia": f"{PIN_HOLE_CALLOUT},\nPER {step_ref(LEVER_PIN_SET_STEP_KEY)}",
}


def _section_axes(
    adapter: Any, native: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet directions of model -z (B to the crown) and +y (up the grip)."""
    native.UpdateViewDisplayGeometry()
    origin, crown, grip = model_points_in_view(
        adapter,
        native,
        ((0.0, 0.0, 0.0), (0.0, 0.0, -0.001), (0.0, 0.001, 0.0)),
        label="lever section A-A axes",
        names=("origin", "crown", "grip"),
    )
    return (
        (crown[0] - origin[0], crown[1] - origin[1]),
        (grip[0] - origin[0], grip[1] - origin[1]),
    )


def _orient_section(adapter: Any, native: Any, cut: Any) -> None:
    """Face B left, the crown right, the grip up: the old side view's frame.

    Looking along -x with +y up puts -z on the right, a right-handed pair on
    the sheet; a left-handed pair is the cut looking along +x, so the cut
    direction is reversed.  The view then turns until -z reads right
    (draw_pn_pen_hanger ``_orient_section``).
    """
    right, up = _section_axes(adapter, native)
    if right[0] * up[1] - right[1] * up[0] < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="lever section reversed")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("lever section A-A cut direction did not persist")
        right, up = _section_axes(adapter, native)
    native.Angle = float(native.Angle) - math.atan2(right[1], right[0])
    rebuild_drawing(adapter, label="lever section turned")
    right, up = _section_axes(adapter, native)
    tolerance = 1e-7
    if (
        right[0] <= 0.0
        or abs(right[1]) > tolerance
        or up[1] <= 0.0
        or abs(up[0]) > tolerance
    ):
        raise RuntimeError(
            f"lever section A-A is not in the side view's frame: {right=}, {up=}"
        )
    _telemetry.info(f"lever section A-A angle={float(native.Angle):.6f} rad")


def _centre_section(adapter: Any, native: Any) -> None:
    """Land the front view's box centre on SECTION_CENTER, level with it.

    Placed by projection (``SetViewPosition`` moves the ink by the difference
    from the Position it reads, draw_pn_pen_hanger), so the section stays on
    the front view's Y station like the side view it replaces.
    """
    anchor = (0.0, FRONT_BBOX_CY / 1000.0, 0.0)
    for attempt in range(5):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"lever section A-A centre, pass {attempt}"
        )
        if math.dist(projected, SECTION_CENTER) <= 1e-4:
            return
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre lever section A-A")
        rebuild_drawing(adapter, label="lever section re-centred")
    raise RuntimeError(f"lever section A-A did not settle on {SECTION_CENTER}")


def _lever_section(adapter: Any, front: Any) -> Any:
    """Section A-A: the front view cut down the grip axis (model x 0).

    The cut opens the blind bore, its flat floor and the end wall, and hatches
    the grip rod and the hub as one piece.  Not a surface cut: the pin hole
    lies in the bore, past the plane, and must print beyond it.
    """
    line = [
        model_point_in_view(
            adapter,
            front,
            tuple(value / 1000.0 for value in point),
            label="section A-A cutting line",
        )
        for point in SECTION_LINE_MODEL_MM
    ]
    section = create_section_view(
        adapter,
        front,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="lever section A-A",
    )
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    # R2026x declares the setter void; only the getter is tested.
    if bool(cut.GetDisplayOnlySurfaceCut()):
        cut.SetDisplayOnlySurfaceCut(False)
        rebuild_drawing(adapter, label="lever section shows the pin hole beyond")
        if bool(cut.GetDisplayOnlySurfaceCut()):
            raise RuntimeError("lever section A-A hides the pin hole beyond the cut")
    ratio = tuple(float(value) for value in native.ScaleRatio)
    if not math.isclose(ratio[0] / ratio[1], SECTION_SCALE[0] / SECTION_SCALE[1]):
        raise RuntimeError(f"lever section A-A scale did not persist: {ratio}")
    _orient_section(adapter, native, cut)
    # A section shows no hidden lines (rule 9); set before centring so the
    # display change cannot shift the placed ink.
    set_hidden_lines_removed(adapter, section)
    _centre_section(adapter, native)
    position_section_caption(
        adapter, section, SECTION_LABEL_XY, label="lever section A-A"
    )
    return section


def _hub_detail(adapter: Any, section: Any) -> Any:
    """A native 3:1 detail B of the hub in section A-A."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(section, "IView")
    if not drawing.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate hub-detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(adapter, section, (0.0, 0.0, 0.0), label="hub centre")
    radius = DETAIL_RADIUS_MM * _S
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create hub-detail fence")
    detail = drawing.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *DETAIL_SCALE,
        "B",
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create hub detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("hub detail has invalid bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position hub detail")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position hub detail label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"hub detail label position did not persist: {actual}")
    return detail


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-lever source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Engage Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion engage lever; pinned hub; straight grip rod",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # drawing-guidelines.md rule 9 (internal shape in solid lines): the blind
    # bore, its floor and the end wall print in section A-A and its detail,
    # where the pin hole shows true on the far bore wall -- no feature needs a
    # hidden line.
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="lever front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="lever top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The axial stations live in reference sketches the part saves hidden
    # (#880).  Section A-A and its detail are created, and the detail
    # dimensioned, while the part shows them, and the front view the section
    # is cut from shows them too, because the derived views' items select
    # through it (draw_pd_platen's floor section): with only the part showing
    # them, pc-p1r's import delivered neither station.  The front view sees
    # every station line end-on, along the hub axis.
    with part_sketches_shown(
        adapter,
        source_model,
        REFERENCE_SKETCHES,
        label="hub detail stations",
        base_view=front,
    ):
        section = _lever_section(adapter, front)
        detail = _hub_detail(adapter, section)
        set_hidden_lines_removed(adapter, detail)
        detail_annotations = curate_view_dimensions(
            adapter,
            detail,
            keep=DETAIL_KEEP,
            view_label="hub detail",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    annotations = [*front_annotations, *top_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    if not auto_center_marks(adapter, detail, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin hole")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    # Top-left anchored under the relocated isometric (bottom y ~0.102).
    add_property_linked_note(adapter, "Isometric View Note", 0.1545, 0.097)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Engage Lever Manufacturing Drawing",
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
