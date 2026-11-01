r"""Create the curated machinist drawing for the column clamp, back arc.

The SLDPRT remains authoritative.  This recipe supplies only the back-arc
views, dimension layout and hole callout; sheet/template and export behavior
lives in ``_drawing_common``.  Dimension import and curation live in
``_drawing_dimension_import``.

The sheet prints decimal inch (the part's ``drawing_unit: in``) and runs at
2:1 (the arc is 1.890 ear tip to ear tip); the isometric carries an explicit
1:1 override so it stays clear of the title block.  Two views in third-angle
projection: the top view (the .590 x 1.890 plan carrying the column-relief
arc, the bore axis centre-marked .020 past the split face) and, projected to
its right, the split face (the 1.890 x .630 face the relief opens into,
turned so its 1.890 runs up the sheet beside the plan's, with the bore
axis drawn as a centerline the ear-hole stations measure from).  No frames
and no datums (drawing-guidelines.md rule 5; clamps are not on the
drawing-simplicity allowlist): the bore axis locates the split face, one side
face and the ear holes by +/- dimensions authored on the part.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sh_column_clamp_back.py sh-column-clamp-back
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    view_name,
)

from _check import check
from _column_clamp_drawing import (
    add_bore_axis_centerline,
    set_dimension_prefixes,
    set_linear_reference_dimensions,
)
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimensions,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from sh_column_clamp_back_spec import (
    ARC_HEIGHT,
    BORE_CLEARANCE_TEXT,
    COLUMN_BORE,
    COLUMN_MATE,
    DEPTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    EAR_HOLE_CALLOUT_PLACES,
    EAR_HOLE_Z,
    FRONT_ARC_MATE,
    GRIP_OFFSET,
    LINEAR_REFERENCE_DIMENSIONS,
    REFERENCE_DIMENSIONS,
    TAP_DRILL_DIA,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sh_column_clamp_back"]
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

SHEET_SCALE = (2.0, 1.0)
_M = SHEET_SCALE[0] / 1000.0  # model mm -> sheet meters

# Sheet layout (meters).  The model bbox runs -15.5..-0.5 in X (back face to
# split face; the bore axis is X = 0), +/-8 in Y (height) and +/-24 in Z
# (width); each view centres on that bbox.  At 2:1 the top view is 30 x 96 mm
# with +X right and +Z down, so the split face is its right edge and the bore
# axis sits 1 mm right of it, level with the view centre.  The split-face view
# is the *Right view (looking -X) turned a quarter turn counterclockwise: +Z
# runs down the sheet as in the top view and the top face (+Y) faces the top
# view, a true right-side projection of it; 32 x 96 mm.
TOP_CENTER = (0.175, 0.175)
FACE_CENTER = (0.290, 0.175)
FACE_VIEW_ANGLE = math.pi / 2.0
ISO_CENTER = (0.385, 0.205)
ISO_NOTE_XY = (0.352, 0.180)
# Ear-height text centre off the face view's centre (sheet m): the bottom-face
# witness stands ARC_HEIGHT / 2 at 2:1 = 0.016 off it, the widest callout
# line is ~0.040 wide, so 0.040 leaves ~4 mm between text and witness.
EAR_HEIGHT_TEXT_OFFSET = 0.040


def _face_xy(y_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a model (Y, Z) in the turned split-face view."""
    return (FACE_CENTER[0] - y_mm * _M, FACE_CENTER[1] - z_mm * _M)


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Top view (the block and bore sketches lie on the Top plane): the
# depth above the view, the width left of it, the bore axis to the near (+Z)
# side face on a dimension line right of the split face with its value on that
# line, the grip offset (split face to bore axis) under the view, and the
# bore's reference Ø leadered in through the upper half of the open mouth
# from above right, clear of both (the axis witnesses run right and down from
# the axis, so nothing crosses the leader).  Split-face view: the ear-hole
# station from the bore centerline right of it, its mate callout under the
# value; under the view, the ears' shared height off the bottom face
# (EarHoleHeight, from the part's hidden EarHeightReference sketch: its
# witnesses leave the bottom face and ear 1's centre), and the height below
# it.  The ears' height spans only 16 mm of sheet between its witnesses, far
# short of its ~40 mm callout block, so that block stands OUTSIDE them, past
# the bottom-face witness (which the height shares) and off the part, its
# dimension line run out under it as GripOffset's is: no witness, ear
# centreline or part edge crosses the text (farm round 20261015T1724 audit
# and machinist review, rule 14).
TOP_KEEP = {
    "Depth": (TOP_CENTER[0], 0.240),
    "GripOffset": (0.236, 0.104),
    "Width": (0.140, TOP_CENTER[1]),
    "AnchorZ": (0.215, 0.151),
    "BoreDia": (0.240, 0.205),
}
FACE_KEEP = {
    "Height": (FACE_CENTER[0], 0.090),
    "EarHole1Z": (0.335, 0.1575),
    "EarHoleHeight": (FACE_CENTER[0] + EAR_HEIGHT_TEXT_OFFSET, 0.113),
}

# Both ear holes stand on the one station and the one height the part prints
# (EarHole1Z, EarHoleHeight).
DIMENSION_PREFIXES = {"EarHole1Z": "2X ", "EarHoleHeight": "2X "}
# The bands that are tighter than the title block name their mate and why
# (drawing-guidelines.md rule 4): the bore is matched to the purchased column
# (sh_column_clamp_fit), the bore axis stands off the split face so the clamp
# faces stay apart once both bores seat, and the ear stations and height line
# up with the front arc's clearance holes.  All under the value: SOLIDWORKS
# prints nothing of an above-callout holding a line break
# (draw_dt_cone_gear_shaft._printable_above_callouts).
DIMENSION_CALLOUTS = {
    "BoreDia": f"{BORE_CLEARANCE_TEXT} DIAMETRAL\nCLEARANCE ON\n{COLUMN_MATE}",
    "GripOffset": f"BORE AXIS OUTSIDE\nSPLIT FACE\nGRIP GAP TO {FRONT_ARC_MATE}",
    "EarHole1Z": f"ALIGNS WITH\n{FRONT_ARC_MATE} EARS",
    "EarHoleHeight": f"ALIGNS WITH\n{FRONT_ARC_MATE} EARS",
}

# Model points (mm) the sheet picks project from, on the split face (X =
# -GRIP_OFFSET).  The tap callout lands on ear 2's rim up and right of its
# centre; the bore centerline runs midway between the two straight edges
# where the relief meets the split face.
_TAP_R = TAP_DRILL_DIA / 2.0
_SPLIT_X = -GRIP_OFFSET
_EAR_2_RIM_MM = (_SPLIT_X, -0.6 * _TAP_R, -EAR_HOLE_Z - 0.8 * _TAP_R)
_RELIEF_EDGE_Z = math.sqrt((COLUMN_BORE / 2.0) ** 2 - GRIP_OFFSET**2)
_RELIEF_EDGES_MM = tuple((_SPLIT_X, 4.0, s * _RELIEF_EDGE_Z) for s in (1.0, -1.0))
# The relief arc's far point on the top face, where its centre mark picks it.
_RELIEF_ARC_MM = (-COLUMN_BORE / 2.0, ARC_HEIGHT / 2.0, 0.0)
HOLE_CALLOUT_XY = (0.320, 0.250)
# Native Hole Wizard through-tap drill diameter at the sheet's .XXX (.136).
HOLE_CALLOUT_PRECISION = {"hw-thrutapdrldia": EAR_HOLE_CALLOUT_PLACES}
# A turned view that is off by a sign misplaces every recipe position, so the
# build proves ear 1's centre lands where _face_xy puts it.
_PROJECTION_TOL = 0.0005
# The top view's frame: the bbox centre in X (model mm), for the same proof.
_X_MID = -(DEPTH + GRIP_OFFSET) / 2.0


def _mm_to_m(point: tuple[float, float, float]) -> tuple[float, float, float]:
    return (point[0] / 1000.0, point[1] / 1000.0, point[2] / 1000.0)


def _assert_lands(
    adapter: Any,
    view: Any,
    point_mm: tuple[float, float, float],
    expected: tuple[float, float],
    *,
    label: str,
) -> None:
    landed = model_point_in_view(adapter, view, _mm_to_m(point_mm), label=label)
    if math.dist(landed, expected) > _PROJECTION_TOL:
        raise RuntimeError(f"{label} projects to {landed}, not {expected}")


def _turn_face_view(adapter: Any, drawing_model: Any, view: Any) -> None:
    """Turn the split-face view upright beside the plan and prove its frame."""
    native = _early_bound(view, "IView")
    native.Angle = FACE_VIEW_ANGLE
    if abs(math.remainder(float(native.Angle) - FACE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to turn the split-face view beside the plan")
    drawing_model.EditRebuild3()
    _assert_lands(
        adapter,
        view,
        (_SPLIT_X, 0.0, EAR_HOLE_Z),
        _face_xy(0.0, EAR_HOLE_Z),
        label="split-face view ear 1 centre",
    )


def _add_relief_center_mark(adapter: Any, top: Any) -> None:
    """Centre-mark the relief arc: the bore axis the plan dimensions from,
    0.5 outside the split face, is drawn rather than implied."""
    _assert_lands(
        adapter,
        top,
        (0.0, ARC_HEIGHT / 2.0, 0.0),
        (TOP_CENTER[0] - _X_MID * _M, TOP_CENTER[1]),
        label="top view bore axis",
    )
    draw = adapter.currentModel
    drawing_doc = _sw_type_info.early_bound_or_flag(
        draw, "IDrawingDoc", "ActivateView", "InsertCenterMark3"
    )
    if not drawing_doc.ActivateView(view_name(adapter, top)):
        raise RuntimeError("failed to activate the clamp-back top view")
    arc_xy = model_point_in_view(
        adapter, top, _mm_to_m(_RELIEF_ARC_MM), label="relief arc"
    )
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        "", "EDGE", arc_xy[0], arc_xy[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("failed to select the column-relief arc")
    center_mark = drawing_doc.InsertCenterMark3(2, False, False)
    draw.ClearSelection2(True)
    if center_mark is None:
        raise RuntimeError("failed to centre-mark the bore axis")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open column-clamp-back source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Column Clamp Back Arc Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "column clamp; back arc; tapped #8-32 ears; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    face = place_view(adapter, str(SOURCE), "*Right", *FACE_CENTER, scale=(2, 1))
    _turn_face_view(adapter, drawing_model, face)
    # finalize_drawing shades the pictorial isometric with edges; the iso
    # first gets local HLR settings so its cosmetic threads export at full
    # quality (_drawing_common.set_high_quality_shaded_with_edges).
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (top, face, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="top",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            face,
            keep=FACE_KEEP,
            view_label="split face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places and bands are authored on the part; the sheet only proves the
    # import kept the places, then marks the reference bore, the pair count
    # and the mates.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)
    set_linear_reference_dimensions(adapter, annotations, LINEAR_REFERENCE_DIMENSIONS)
    set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)

    _add_relief_center_mark(adapter, top)
    picks = model_points_in_view(
        adapter,
        face,
        [_mm_to_m(point) for point in (_EAR_2_RIM_MM, *_RELIEF_EDGES_MM)],
        label="split-face picks",
        names=("ear 2 rim", "relief edge +Z", "relief edge -Z"),
    )
    ear_2_rim, *relief_edges = picks
    # The ear-hole stations measure from the bore axis: draw it.
    add_bore_axis_centerline(adapter, face, relief_edges)
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the split-face view")

    ear_taps = add_native_hole_callout(
        adapter,
        face,
        edge_xy=ear_2_rim,
        callout_xy=HOLE_CALLOUT_XY,
        label="ear taps",
    )
    set_hole_callout_precision(ear_taps, HOLE_CALLOUT_PRECISION, label="ear taps")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Column Clamp Back Arc Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#8-32 Tapped Hole" note to the face view
        # once the tap carries a hole callout; the callout already states it.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
