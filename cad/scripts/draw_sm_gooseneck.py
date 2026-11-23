r"""Create the curated machinist drawing for MHA-SM-01, the gooseneck tube.

The SLDPRT remains authoritative.  This recipe supplies the views, places the
part's marked dimensions and links the notes; sheet/template and export
behaviour lives in ``_drawing_common``.

The gooseneck is a 1/2 in 4130-N tube bent R3.0 on a simple form, both ends
sawn and faced after the bend (owner rulings 2026-10-27, #1951; 2026-11-08
(Pedro), #2315; 2026-11-14 (Pedro), #2401).  The end plug bonded into the
arm end is its own part and sheet (MHA-SM-05), and the leg carries no
sleeve.  The sheet carries, at 1:3, the ELEVATION (``*Front``): the
reference leg length (foot to the bend's entry tangent) and arm straight
(the bend's exit tangent to the faced arm end) on the tube's axes, from the
part's hidden ``StationReference``; the bend's reference centreline radius;
the tube's reference stock Ø with its wall; and where the two ends finish,
the overall reach (faced arm end to the leg's outer side) and overall height
(foot face to the arm's top), from the part's hidden ``OverallReference``.
The bend's acceptance
stands at its own leader on the bend.  The isometric is at 1:4.  The sheet
prints decimal inch (#290, the registry row's drawing_unit).

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_gooseneck.py sm-gooseneck
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _gtol_torus import TorusFace
from _machinist_review_mode import MachinistReviewMode
from _named_views import octant_view_name
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _printed_limits import limits
from _printed_tolerance import angular_band_deg
from _session import run_build
import _telemetry
from sm_gooseneck_geom import (
    ARM_Y,
    BEND_R,
    LEG_BOTTOM,
    LEG_LENGTH,
    LEG_TOP,
    TUBE_BORE_DIA,
    TUBE_DIA,
    TUBE_DIA_MAX,
    TUBE_DIA_MIN,
    TUBE_END_X,
    TUBE_STRAIGHT,
    WALL_T,
    WALL_T_MAX,
    WALL_T_MIN,
)
from sm_gooseneck_spec import (
    DIMENSION_CALLOUTS_BY_NAME,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    ISOMETRIC_OCTANT,
    OVERALL_HEIGHT_TOLERANCE_MM,
    TUBE_OD_REF_Y,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_gooseneck"]
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

SHEET_SCALE = (1.0, 3.0)  # 1:3 whole sheet (~500 mm tall gooseneck)
VIEW_SCALE = (1, 3)
ISO_SCALE = (1, 4)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm

# A placed view centres its model bounding box: x from the faced arm end to
# the leg's far side, y from the leg's foot to the arm's top.
_TUBE_R = TUBE_DIA / 2.0
_BOX_MID_X = (TUBE_END_X + _TUBE_R) / 2.0
_BOX_MID_Y = (LEG_BOTTOM + ARM_Y + _TUBE_R) / 2.0

# Sheet layout (metres): the elevation with its dimensions on the leg's right
# left of centre, its foot clear of the title block's left edge (x 0.216) and
# above the notes, and the isometric right of centre over the title block, so
# the two views spread across the usable region (rule 15).
FRONT_CENTER = (0.130, 0.150)
ISO_CENTER = (0.310, 0.165)


def _front_x(model_x: float) -> float:
    return FRONT_CENTER[0] + (model_x - _BOX_MID_X) * _S


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - _BOX_MID_Y) * _S


LEG_AXIS_X = _front_x(0.0)
ARM_AXIS_Y = _front_y(ARM_Y)
ARM_END_X = _front_x(TUBE_END_X)
FOOT_Y = _front_y(LEG_BOTTOM)
BEND_TANGENT_Y = _front_y(LEG_TOP)

# The elevation's dimensions: both vertical runs on the leg's right, the leg
# length's text level with the tube's reference Ø, which crosses the leg on
# its left, level with the hidden reference line; the arm straight over the
# arm; the bend radius outside the bend, its block centred 25 mm right of the
# leg's axis so the 37.5-mm "TUBE CENTERLINE" row clears the bend's inner
# edge by 3.6 mm (farm run 20261107T102825912Z: "TO TUBE CENTERLINE" centred
# 19 mm right ran under the arc) and ends 8 mm short of the overall height's
# line, its bottom row over the leg length's upper extension line.
# The overall height (foot face to the arm's top, ±.10) stands outermost
# on the leg's right, beyond the leg length (its text ended at x 0.310 in farm
# run 20261101T004958072Z) and short of the title block's left edge, so its
# foot extension line stays off the title block; its text at the view's
# mid-height, 21 mm below the leg length's.  The overall reach (faced arm end
# to the leg's outer side) runs over the arm straight.  Machinist review r5 of
# that run.  The arm straight's text stands outside its short span, left of
# the faced arm end: centred over the span it straddled the end's extension
# line, which the reach shares (text-on-line, farm run 20261101T022045634Z).
FRONT_KEEP = {
    "LegLength": (LEG_AXIS_X + 0.034, _front_y(TUBE_OD_REF_Y)),
    "TubeOdRef": (LEG_AXIS_X - 0.030, _front_y(TUBE_OD_REF_Y)),
    "ArmStraight": (ARM_END_X - 0.010, ARM_AXIS_Y + 0.014),
    "BendRadius": (LEG_AXIS_X + 0.025, ARM_AXIS_Y - 0.0176),
    "OverallHeight": (
        LEG_AXIS_X + 0.052,
        (FOOT_Y + _front_y(ARM_Y + _TUBE_R)) / 2.0,
    ),
    "OverallReach": (
        (ARM_END_X + _front_x(_TUBE_R)) / 2.0,
        ARM_AXIS_Y + 0.021,
    ),
}
if set(FRONT_KEEP) != {
    name for names in DRAWING_DIMENSIONS.values() for name in names
}:
    raise AssertionError("the gooseneck sheet does not place every marked dimension")

# The bend's acceptance is short, so it prints at its own leader on the bend,
# not as a numbered note in the corner (drawing-guidelines.md rule 7, "flag
# it where it applies"; machinist review of the v49 release, acd9e8f84d: note
# 1 stood alone with no flag at the R3.0 callout).  One row since #2401
# dropped the ovality limit, ~21 mm wide at ~2.62 mm a glyph (farm run
# 20261112T194827228Z), left of the faced arm end and just under the arm:
# the block still ends ~4.7 mm left of the arm end and its
# top 5.5 mm under the arm's inner edge, far over the tube Ø's text.  Its
# leader runs right, under the arm, to the bend's inner arc 55° up from the
# leg, so it stays well above the bend's centre: the R3.0 dimension's line
# runs in from the leg's tangent toward that centre, and the leader of the
# first placement (block under the centre, tip 35° up) crossed it (machinist
# review of that run, r1-r3).  The text is the part's Manufacturing Notes
# property (spec DRAWING_NOTES) without its number and "BEND:", which the
# leader now says.  The elevation is a projected principal view at the
# sheet's scale, so it carries no label (drawing-guidelines.md rule 9).  The
# isometric's note sits under it, over the title block.
BEND_ACCEPTANCE = "NO KINKS"
_BEND_INNER_R = BEND_R - _TUBE_R
_BEND_TIP_ANGLE = math.radians(55.0)
BEND_NOTE_TIP = (
    _front_x(-BEND_R + _BEND_INNER_R * math.cos(_BEND_TIP_ANGLE)),
    _front_y(LEG_TOP + _BEND_INNER_R * math.sin(_BEND_TIP_ANGLE)),
)
BEND_NOTE_XY = (ARM_END_X - 0.026, _front_y(ARM_Y - _TUBE_R) - 0.0055)
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, 0.085)

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (build_sm_gooseneck: the leg's axis on model Y through the origin at the
# leg's mid-height, the foot face at y = LEG_BOTTOM; the arm's axis at
# y = ARM_Y running toward -X to the faced arm end at x = TUBE_END_X; the
# bend's centre at (-BEND_R, LEG_TOP), its axis on Z). The governing sizes
# are where the two ends finish: the overall height (foot face to the arm's
# top, OVERALL_HEIGHT_TOLERANCE_MM) and the overall reach (faced arm end to
# the leg's outer side, .XX); the leg and arm stay square at the title
# block's implied 90 deg. The leg length, the arm straight, the bend's
# centreline radius and the tube's Ø and wall are references; the blank is
# the straight tube's length through the bend at those references. The
# declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_sm_gooseneck"
_GEOM = "sm_gooseneck_geom"
UNIT = part_drawing_unit(PART_STEM)
_ARM_MID_X = (TUBE_END_X - BEND_R) / 2.0
_OVERALL_HEIGHT = ARM_Y + _TUBE_R - LEG_BOTTOM
_OVERALL_REACH = _TUBE_R - TUBE_END_X
_DEVELOPED = LEG_LENGTH + math.pi / 2.0 * BEND_R + TUBE_STRAIGHT
part_metadata(
    model_sources=(
        (_GEOM, "TUBE_DIA"),
        (_GEOM, "ARM_Y"),
        (_GEOM, "BEND_R"),
        (_GEOM, "LEG_BOTTOM"),
        (_GEOM, "TUBE_END_X"),
    ),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)
requirement(
    "foot",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), -LEG_BOTTOM),),
    requirements=("plane",),
    fields={
        "plane": (
            {"frame": "model", "axis": "y", "value": LEG_BOTTOM},
            ((_GEOM, "LEG_BOTTOM"),),
        ),
        "outward": ([0.0, -1.0, 0.0], ((_GEOM, "LEG_BOTTOM"),)),
    },
)
requirement(
    "leg",
    kind="boss",
    faces=(CylinderFace(TUBE_DIA, contains_y_mm=0.0),),
    requirements=("leg_length_ref",),
    fields={
        "axis": ([0.0, 1.0, 0.0], ((_GEOM, "LEG_TOP"),)),
        "at": ([0.0, LEG_BOTTOM, 0.0], ((_GEOM, "LEG_BOTTOM"),)),
        "leg_length_ref": (
            LEG_LENGTH,
            ((_GEOM, "LEG_LENGTH"), "REFERENCE_DIMENSIONS", (_SELF, "FRONT_KEEP")),
        ),
        "leg_length_from": ("foot", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"leg_length_ref": _P["LegLength"]},
)
requirement(
    "arm",
    kind="boss",
    faces=(CylinderFace(TUBE_DIA, contains_x_mm=_ARM_MID_X),),
    requirements=("height", "arm_straight_ref"),
    fields={
        "axis": ([-1.0, 0.0, 0.0], ((_GEOM, "ARM_Y"),)),
        "at": ([-BEND_R, ARM_Y, 0.0], ((_GEOM, "BEND_R"), (_GEOM, "ARM_Y"))),
        "height": (
            limits(
                _OVERALL_HEIGHT,
                _P["OverallHeight"],
                (OVERALL_HEIGHT_TOLERANCE_MM, -OVERALL_HEIGHT_TOLERANCE_MM),
                unit=UNIT,
            ),
            ("OVERALL_HEIGHT_TOLERANCE_MM", (_SELF, "FRONT_KEEP")),
        ),
        "height_nominal": (_OVERALL_HEIGHT, ((_GEOM, "ARM_Y"), (_GEOM, "LEG_BOTTOM"))),
        "height_from": ("foot", ((_SELF, "FRONT_KEEP"),)),
        "arm_straight_ref": (
            TUBE_STRAIGHT,
            ((_GEOM, "TUBE_STRAIGHT"), "REFERENCE_DIMENSIONS", (_SELF, "FRONT_KEEP")),
        ),
    },
    precision={"height": _P["OverallHeight"], "arm_straight_ref": _P["ArmStraight"]},
)
requirement(
    "arm_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), -TUBE_END_X),),
    requirements=("reach",),
    fields={
        "plane": (
            {"frame": "model", "axis": "x", "value": TUBE_END_X},
            ((_GEOM, "TUBE_END_X"),),
        ),
        "outward": ([-1.0, 0.0, 0.0], ((_GEOM, "TUBE_END_X"),)),
        "reach": (
            limits(_OVERALL_REACH, _P["OverallReach"], unit=UNIT),
            ((_GEOM, "TUBE_END_X"), (_SELF, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "reach_nominal": (_OVERALL_REACH, ((_GEOM, "TUBE_END_X"), (_GEOM, "TUBE_DIA"))),
        "reach_from": ("leg", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"reach": _P["OverallReach"]},
)
requirement(
    "bend",
    kind="bend",
    faces=(TorusFace(BEND_R, _TUBE_R, (-BEND_R, LEG_TOP, 0.0)),),
    requirements=("centreline_radius", "angle", "callout"),
    fields={
        "centreline_radius": (
            BEND_R,
            ((_GEOM, "BEND_R"), "BEND_RADIUS_CALLOUT", (_SELF, "FRONT_KEEP")),
        ),
        "angle": (
            [90.0 - angular_band_deg(unit=UNIT), 90.0 + angular_band_deg(unit=UNIT)],
            ((_SELF, "UNIT"),),
        ),
        "angle_nominal": (90.0, ((_GEOM, "BEND_R"),)),
        "at": ([-BEND_R, LEG_TOP, 0.0], ((_GEOM, "BEND_R"), (_GEOM, "LEG_TOP"))),
        "callout": (BEND_ACCEPTANCE, ((_SELF, "BEND_ACCEPTANCE"),)),
    },
    precision={"centreline_radius": _P["BendRadius"]},
)
requirement(
    "blank",
    kind="blank",
    faces=(
        CylinderFace(TUBE_BORE_DIA, contains_y_mm=0.0),
        CylinderFace(TUBE_BORE_DIA, contains_x_mm=_ARM_MID_X),
        TorusFace(BEND_R, TUBE_BORE_DIA / 2.0, (-BEND_R, LEG_TOP, 0.0)),
    ),
    requirements=("od", "wall", "callout"),
    fields={
        "section": ("tube", ((_GEOM, "TUBE_DIA"), (_GEOM, "WALL_T"))),
        "od": (
            [TUBE_DIA_MIN, TUBE_DIA_MAX],
            ((_GEOM, "TUBE_DIA_MIN"), (_GEOM, "TUBE_DIA_MAX")),
        ),
        "od_nominal": (TUBE_DIA, ((_GEOM, "TUBE_DIA"), (_SELF, "FRONT_KEEP"))),
        "wall": (
            [WALL_T_MIN, WALL_T_MAX],
            ((_GEOM, "WALL_T_MIN"), (_GEOM, "WALL_T_MAX")),
        ),
        "wall_nominal": (WALL_T, ((_GEOM, "WALL_T"), "TUBE_OD_CALLOUT")),
        "developed_length": (
            _DEVELOPED,
            ((_GEOM, "LEG_LENGTH"), (_GEOM, "BEND_R"), (_GEOM, "TUBE_STRAIGHT")),
        ),
        "callout": (DIMENSION_CALLOUTS_BY_NAME["TubeOdRef"], ("DIMENSION_CALLOUTS",)),
    },
    precision={"od": _P["TubeOdRef"], "wall": _P["TubeOdRef"]},
)


def _assert_part_callouts(adapter: Any, annotations: list[Any]) -> None:
    """The part authors every callout below its dimension's value; the
    import must carry each one unchanged (the drawing never writes them,
    #1942)."""
    # swDimensionTextCalloutBelow = 4.
    expected = {(4, name): text for name, text in DIMENSION_CALLOUTS_BY_NAME.items()}
    found: dict[tuple[int, str], str] = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        slots = [slot for slot, expected_name in expected if expected_name == name]
        if not slots:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        for slot in slots:
            found[(slot, name)] = str(display.GetText(slot) or "").replace("\r\n", "\n")
    if found != expected:
        raise RuntimeError(
            f"gooseneck dimension callouts did not import: {found!r} != {expected!r}"
        )


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck source", adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
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
    acceptance = " ".join(BEND_ACCEPTANCE.split())
    if properties["Manufacturing Notes"] != f"1. BEND: {acceptance}":
        raise RuntimeError(
            "gooseneck bend acceptance does not match the part's notes: "
            f"{properties['Manufacturing Notes']!r}"
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
            0: "Gooseneck Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "gooseneck; bent 4130 tube; spring post",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    iso = place_view(
        adapter,
        str(SOURCE),
        octant_view_name(*ISOMETRIC_OCTANT),
        *ISO_CENTER,
        scale=ISO_SCALE,
    )
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="elevation",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_part_callouts(adapter, annotations)

    add_leader_note(
        adapter,
        BEND_ACCEPTANCE,
        text_xy=BEND_NOTE_XY,
        attach_xy=BEND_NOTE_TIP,
        label="bend acceptance",
        view=front,
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Post Manufacturing Drawing",
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
