r"""Create the curated machinist drawing for the pinion cam-follower pin.

A short 5/32 drill-rod stud with a shallow domed outer end, bonded into the
MHA-DT-14 strap's follower seat (decimal-inch sheet, #290).  The sheet runs
at 8:1 so the short pin
reads at arm's length.  The side view lies as the pin is turned (drawing-guidelines.md rule 11 (turned parts read like the lathe)) and
carries every dimension: the diameter, the length, the crown radius and a
reference overall.  The end view projects to its left (third angle), and a
4:1 isometric sits clear of the title block.  The shank OD the cam rides carries
the one roughness symbol, explicitly distinguished from the free crown, and
the sheet has no general notes (dt_pinion_cam_pin_spec).

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_pinion_cam_pin.py dt-pinion-cam-pin
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_finish import add_surface_finish
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gtol_face_resolve import resolve_faces
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_pinion_cam_pin_spec import (
    CAP_RADIUS_CALLOUT,
    CAP_SAG,
    DEPTH_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    PIN_DIA as PIN_DIA,
    PIN_DIA_CALLOUT,
    PIN_LEN,
    SURFACE_FINISHES,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_pinion_cam_pin"]
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

# Machinist review of 7f7fc1717: the end view sat beside a vertical
# elevation, out of projection, and alone carried the diameter.  The *Right
# side view now lays the pin as it is turned (model +Z to the left: the crown
# on the left, the seated end on the right) and its Right-plane profiles put
# the diameter, the length and the crown radius on it.  Third angle: the
# *Front end view looks at the crown end, so it projects to the LEFT and
# shares the side view's Y station.  Its bbox centre is the pin's mid-length.
SHEET_SCALE = (8.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0
OVERALL = PIN_LEN + CAP_SAG
RIGHT_CENTER = (0.235, 0.165)
FRONT_CENTER = (0.065, RIGHT_CENTER[1])
ISO_CENTER = (0.375, 0.215)
ISO_NOTE_XY = (0.340, 0.178)
HALF_DIA = PIN_DIA / 2.0 * _S


def side_view_x(z_mm: float) -> float:
    """Sheet X of model station ``z_mm`` on the side view (+Z runs left)."""
    return RIGHT_CENTER[0] - (z_mm - OVERALL / 2.0) * _S


# Both lengths sit ABOVE the side view (Depth inner, the reference overall
# outer), so every extension line runs up and the crown's radius leader
# reaches it from the lower left without crossing one.  The diameter sits
# below, its dimension line right of centre so the axis-centerline pick at
# the view's middle lands on bare face.  The shank's roughness symbol sits
# above the shank between the crown-root extension line and the Depth text.
RIGHT_KEEP = {
    "PinDia": (RIGHT_CENTER[0] + 0.040, RIGHT_CENTER[1] - HALF_DIA - 0.030),
    # 39 mm above the shank (was 31): the shank's CAM CONTACT finish symbol
    # sits between it and the shank, and the crowding gap must exceed the
    # symbol's 11.5 mm height (machinist review r5 of #1009).
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] + HALF_DIA + 0.039),
    # Lower left, on the line from the crown centre through its lower flank,
    # so the radius leader lands on the crown below the axis.
    "CapR": (0.105, 0.110),
}
OVERALL_TEXT_XY = (RIGHT_CENTER[0], RIGHT_CENTER[1] + HALF_DIA + 0.067)
DIMENSION_CALLOUTS = {
    "PinDia": PIN_DIA_CALLOUT,
    "Depth": DEPTH_CALLOUT,
    "CapR": CAP_RADIUS_CALLOUT,
}

# A representative station on the exposed shank identifies the whole
# cylindrical finish face, not a restricted operating-contact band.  The
# finish leader falls to the right below the target and Ra text.  Assembly
# axis-distance geometry, not the unused free crown, establishes the contact
# surface (test_the_cam_rides_the_shank_short_of_the_crown).
CAM_CONTACT_FROM_SEATED_END_MM = 15.0
SHANK_FINISH_SYMBOL_XY = (0.168, RIGHT_CENTER[1] + HALF_DIA + 0.006)


def _shank_point() -> tuple[float, float, float]:
    """Model point on the shank's +Y silhouette (the side view's upper edge)
    at the cam-contact station, measured from the seated end."""
    return (0.0, PIN_DIA / 2000.0, CAM_CONTACT_FROM_SEATED_END_MM / 1000.0)


def _shank_face(view: Any) -> Any:
    """The shank's one controlled Ø4 cylindrical model face, for a FACE
    finish: resolved on the part ``view`` references, not hit-tested as a
    silhouette, which can re-solve to another face after insertion (farm run
    20261002T180658288Z, ``same_entity=False``)."""
    document = _early_bound(
        _early_bound(view, "IView").ReferencedDocument, "IModelDoc2"
    )
    control = surface_finish_by_key(SURFACE_FINISHES, "shank")
    return resolve_faces(document, {control.key: control.face})[control.key]


# swAnnotationType_e.swCenterMarkSym.  The template centre-marks the end
# view's circle as it is placed; an unconditional auto_center_marks printed a
# second identical mark over it (layout audit duplicate-annotation,
# DetailItem347/348 on r1-r2 of #1009), so the sheet adds one only if the
# template did not, and proves exactly one.
_CENTER_MARK_ANNOTATION = 13


def _center_mark_count(view: Any) -> int:
    """The view's centre-mark annotations (a bare view answers None)."""
    return len(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )


def _overall_reference(adapter: Any, right: Any) -> None:
    """The (20.80) overall, seated end to crown apex (drawing-guidelines.md rule 10 (dimension from a real feature), Harvey #25)."""
    label = "cam-pin overall length reference"
    seated_end = model_point_in_view(
        adapter, right, (0.0, PIN_DIA / 4000.0, 0.0), label="cam-pin seated end"
    )
    apex = model_point_in_view(
        adapter, right, (0.0, 0.0, OVERALL / 1000.0), label="cam-pin crown apex"
    )
    display = add_edge_dimension(
        adapter,
        right,
        p0=seated_end,
        p1=apex,
        text_xy=OVERALL_TEXT_XY,
        label=label,
        orientation="horizontal",
        entity_types=("EDGE", "SILHOUETTE"),
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL) > 1e-4:
        # A line-to-arc pick may resolve to the crown's centre; the overall
        # runs to its far extreme.
        set_arc_endpoints_to_max(adapter, display, label=label)
        measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL) > 1e-4:
        raise RuntimeError(f"{label} measured {measured_mm:g}, expected {OVERALL:g}")
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-cam-pin source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("dt-pinion-cam-pin"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Cam-Follower Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion cam-follower pin; drill-rod stud; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(8, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(8, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # The end view is a bare circle with its center mark: every dimension
    # lives on the Right-plane profiles and imports into the side view only.
    annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if _center_mark_count(front) == 0 and not auto_center_marks(
        adapter, front, holes=True, size=0.0025
    ):
        raise RuntimeError("failed to add ASME center mark to pin end view")
    found = _center_mark_count(front)
    if found != 1:
        raise RuntimeError(f"expected 1 centre mark in the pin end view, found {found}")

    # Before the centreline, so the apex pick cannot land on the axis line.
    _overall_reference(adapter, right)
    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.004),
        label="pinion cam-pin shank axis centerline",
    )
    # drawing-guidelines.md rule 6: the shank is the cam-follower contact.
    shank_finish_point = model_point_in_view(
        adapter, right, _shank_point(), label="cam-pin shank finish point"
    )
    add_surface_finish(
        adapter,
        right,
        entity=_shank_face(right),
        leader_attach_xy=shank_finish_point,
        symbol_xy=SHANK_FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "shank"),
        label="cam-pin shank finish",
        entity_type="FACE",
        char_height=0.0025,  # the pivot-block size; the default read oversized at 8:1
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Cam-Follower Pin Manufacturing Drawing",
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
