r"""Create the curated machinist drawing for the fulcrum-shaft end keeper.

The SLDPRT remains authoritative.  This recipe supplies only the keeper's
views, dimension layout, hole callout, and manufacturing notes;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The sheet runs at 2:1 (the bracket is ~16.5 x 32.2 x 14); the isometric
carries an explicit 1:1 override so it stays clear of the title block.  Four
views: the side profile (front), the plan (top, which carries the foot
screw's stations and the drilled foot-hole and crown set-screw tap callouts),
the end view (right, which carries the width / shaft-axis-height / crown /
bore stack), and the isometric.  A bracket carries no frames and no datums
(drawing-guidelines.md): every location is a plain coordinate dimension off a
named face.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_fulcrum_keeper.py ch-fulcrum-keeper
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
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
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import (
    add_native_hole_callout,
    set_hole_callout_precision,
)
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _printed_limits import drilled_limits, limits
from _session import run_build
import _telemetry
from ch_fulcrum_keeper_notes import (
    BORE_CALLOUT,
    CORNER_CALLOUT,
    CROWN_CALLOUT,
    FOOT_HOLE_MATE,
    FOOT_RISE_CALLOUT,
    SET_SCREW_QUALIFIER,
)
from ch_fulcrum_keeper_spec import (
    BORE_CENTRE_BAND_MM,
    BORE_CENTRE_CALLOUT,
    BORE_DIA,
    BORE_DIA_BAND,
    BORE_HOLE_SPEC,
    BORE_FROM_SIDE,
    CORNER_R_BAND,
    CORNER_R_MAX,
    CORNER_R_PLACES,
    CORNER_R_TOL_TYPE,
    CROWN_LEAST_R,
    CROWN_MOST_R,
    CROWN_R,
    CROWN_TOP_Y,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FOOT_H,
    FOOT_HOLE_CALLOUT_PRECISION,
    FOOT_TIP_X,
    HOLE_DIA_MM,
    KEEPER_WIDTH,
    LUG_HALF_T,
    OVERALL_LENGTH,
    REFERENCE_DIMENSIONS,
    SCREW_FROM_SIDE,
    SCREW_FROM_TIP,
    SCREW_X,
    SET_SCREW_HOLE_SPEC,
    SET_SCREW_THREAD,
    SHAFT_AXIS_H,
    UNIT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["ch_fulcrum_keeper"]
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

# Sheet layout (meters).  The front (side-profile) view's model bbox is
# X -4..+12.5 (lug inner face to foot tip) by Y 0..32.2; at 2:1 that is
# ~33 x 64.4 mm.  Third angle: the plan (top view) rides above the front,
# the end view (right) sits to its right, the isometric top-right.
FRONT_CENTER = (0.110, 0.130)
TOP_CENTER = (0.110, 0.228)
RIGHT_CENTER = (0.225, 0.130)
ISO_CENTER = (0.330, 0.190)

# Model bbox centre the projected views are laid out around (front and plan
# share model X).
_X_MID = (-LUG_HALF_T + FOOT_TIP_X) / 2.0  # 4.25


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - _X_MID) * SHEET_SCALE[0] / 1000.0


# Handy picks derived from the layout above.
HOLE_X_SHEET = _front_x(SCREW_X)  # screw-hole station, shared by the top view
HOLE_R_SHEET = HOLE_DIA_MM * SHEET_SCALE[0] / 2000.0
# Pick the lower-right rim off the 0°/90° center-mark crosshairs.
FOOT_HOLE_EDGE_XY = (
    HOLE_X_SHEET + 0.6 * HOLE_R_SHEET,
    TOP_CENTER[1] - 0.8 * HOLE_R_SHEET,
)
# The crown tap seen end-on in the plan, on the lug mid-plane (x = 0).
TAP_X_SHEET = _front_x(0.0)
TAP_R_SHEET = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC) * SHEET_SCALE[0] / 2000.0
# The foot-hole callout stands below-right of the plan, so its leader drops
# from the text's left end to the hole's lower-right rim and leaves the plan
# through its bottom edge ~6 mm in from the foot-tip corner, away from the
# crown tap left of the hole. With the counterbore retired (#3744 Panel F),
# the callout has two rows: "Ø .094 DRILL THRU" and "CENTERS MHA-FR-02 TAP".
FOOT_HOLE_CALLOUT_XY = (0.157, 0.196)
# The crown tap stops at the bore (MR-fleet r2, 0eca37c). The native sizes
# lead and say where they stop (both "<hw-thru>" extents read TO BORE; the
# thread class is the title block's), and the mate closes the thread's own
# part (SET_SCREW_QUALIFIER, two rows; its staking is MHA-CH-00's step).
SET_SCREW_EXTENT = "TO BORE"
SET_SCREW_CALLOUT_XY = (0.069, 0.196)
_THREAD_CLASS = re.compile(r"\s*(?:-\s*)?<hw-threadclass>\s*", re.IGNORECASE)
# The foot hole's process, after its size in the through row (rules 12 and
# 26): the native "<hw-thru>" extent becomes FOOT_HOLE_THRU.
FOOT_HOLE_PROCESS = "DRILL"
FOOT_HOLE_THRU = f"{FOOT_HOLE_PROCESS} THRU"
# The crown tap's native drill size prints .XXX.
SET_SCREW_CALLOUT_PRECISION = {"hw-tapdrldia": 3}
# Front-view callouts (#3744 Panel F): FootRise (.227 at .XXX) states the
# screw engagement it sets in MHA-FR-02, and CornerRadius (R.02 MAX) states
# the MHA-CH-VN-52 head it clears. End-view callouts: the bore names the
# process and the shaft it slides on, the crown its full round, and the
# bore's (.275) reference station off the side face states its place on the
# width's centre plane.
FRONT_DIMENSION_CALLOUTS = {
    "FootRise": FOOT_RISE_CALLOUT,
    "CornerRadius": CORNER_CALLOUT,
}
RIGHT_DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "CrownRadius": CROWN_CALLOUT,
    "BoreFromSide": BORE_CENTRE_CALLOUT,
}
DIMENSION_CALLOUTS = {**FRONT_DIMENSION_CALLOUTS, **RIGHT_DIMENSION_CALLOUTS}
# Per-view survivors of the marked-dimension import: parametric name ->
# sheet position. The front view baselines its lengths off the inner lug face:
# the lug thickness below the seat, its text out to the left of the inner lug
# face, and under it the overall length. FootRise (.227) keeps its vertical
# dimension line just right of the foot tip while offset_dimension_text parks
# its three-row block in the clear paper below-right of the seat
# (FOOT_RISE_TEXT_XY). CornerRadius (R.02 MAX) sits in the open L-corner above
# the foot and right of the lug.
FRONT_KEEP = {
    "LugThickness": (0.080, 0.086),
    "OverallLength": (FRONT_CENTER[0], 0.068),
    "FootRise": (0.136, 0.1036),
    "CornerRadius": (0.148, 0.136),
    "OverallHeight": (0.080, FRONT_CENTER[1]),
}
FOOT_RISE_TEXT_XY = (0.167, 0.080)
# The manufacturing notes' top-left corner's height (MR-fleet r4: 4 mm lower
# to make room for the overall length above them).
NOTES_TOP = 0.058
TOP_KEEP = {
    "SetScrewLocation": (0.082, 0.2535),
    "ScrewFromTip": (_front_x((FOOT_TIP_X + SCREW_X) / 2.0), 0.252),
    "ScrewFromSide": (0.178, 0.214),
}
RIGHT_KEEP = {
    "Depth": (0.225, 0.090),
    "LugRise": (0.196, 0.126),
    "CrownRadius": (0.168, 0.171),
    "BoreDia": (0.304, 0.1225),
    "BoreFromSide": (0.273, 0.182),
}
NEAR_SIDE_DIAMETERS = ("BoreDia",)
_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
# The front view's reference sketches lay their construction lines ON the
# outline (the heights up the inner lug face, the length along the seat) and
# the curate leaves each sketch shown so its dimension prints; drawn in black
# they match the outline edges.
REFERENCE_WITNESS_COLOR = 0  # COLORREF black, the outline's colour.
FRONT_REFERENCE_WITNESSES = {
    "OverallHeightReference": CROWN_TOP_Y,
    "OverallLengthReference": OVERALL_LENGTH,
}
SW_SEL_EXT_SKETCH_SEGS = 24  # swSelectType_e.swSelEXTSKETCHSEGS
REFERENCE_WITNESS_LEN_TOL = 0.01  # mm; the lines are fully defined sketch lengths

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, beside the constants of the
# code that prints it, in the part frame (ch_fulcrum_keeper_spec: +X along the
# shaft, outboard, x 0 the lug mid-plane; +Y up from the seat; +Z across the
# width, z 0 its centre plane).
_P = {name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()}
_SELF = "draw_ch_fulcrum_keeper"
_NOTES = "ch_fulcrum_keeper_notes"
_FRAME = "__frame__"
_HALF_W = KEEPER_WIDTH / 2.0
_TAP_DRILL = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC)


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


part_metadata(
    model_sources=(
        "LUG_HALF_T",
        "KEEPER_WIDTH",
        "SHAFT_AXIS_H",
        "FOOT_H",
        "FOOT_TIP_X",
        "CROWN_TOP_Y",
    ),
    precision_sources=(
        "DRAWING_PRECISION",
        "CORNER_R_PLACES",
        "FOOT_HOLE_CALLOUT_PRECISION",
        (_SELF, "SET_SCREW_CALLOUT_PRECISION"),
    ),
)
# The seat: the whole underside, every height runs from it.
requirement(
    "seat",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("y", 0.0), (_FRAME,))},
)
# The foot top: the stepped foot .227 off the seat (FRONT_KEEP "FootRise").
requirement(
    "foot_top",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), FOOT_H),),
    requirements=("height",),
    fields={
        "plane": (_plane("y", FOOT_H), ("FOOT_H",)),
        "height": (
            limits(FOOT_H, _P["FootRise"], unit=UNIT),
            ("FOOT_H", "UNIT", (_SELF, "FRONT_KEEP")),
        ),
        "height_nominal": (FOOT_H, ("FOOT_H",)),
        "height_from": ("seat", ((_SELF, "FRONT_KEEP"),)),
        "callout": (
            FOOT_RISE_CALLOUT,
            ((_NOTES, "FOOT_RISE_CALLOUT"), (_SELF, "FRONT_DIMENSION_CALLOUTS")),
        ),
    },
    precision={"height": _P["FootRise"]},
)
# The lug's inner face (toward the lever bank): every length along X runs
# from it (FRONT_KEEP, TOP_KEEP "SetScrewLocation").
requirement(
    "inner_face",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), LUG_HALF_T),),
    requirements=("plane",),
    fields={"plane": (_plane("x", -LUG_HALF_T), (_FRAME, "LUG_HALF_T"))},
)
# The lug's outer face: the lug thickness .32 off the inner face
# (FRONT_KEEP "LugThickness").
requirement(
    "lug_outer_face",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), LUG_HALF_T),),
    requirements=("thickness",),
    fields={
        "plane": (_plane("x", LUG_HALF_T), (_FRAME, "LUG_HALF_T")),
        "thickness": (
            limits(2.0 * LUG_HALF_T, _P["LugThickness"], unit=UNIT),
            ("LUG_HALF_T", "UNIT", (_SELF, "FRONT_KEEP")),
        ),
        "thickness_nominal": (2.0 * LUG_HALF_T, ("LUG_HALF_T",)),
        "thickness_from": ("inner_face", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"thickness": _P["LugThickness"]},
)
# The foot tip: the overall length .65 off the inner face (FRONT_KEEP
# "OverallLength", a real size; the foot length prints nowhere).
requirement(
    "foot_tip",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), FOOT_TIP_X),),
    requirements=("length",),
    fields={
        "plane": (_plane("x", FOOT_TIP_X), ("FOOT_TIP_X",)),
        "length": (
            limits(OVERALL_LENGTH, _P["OverallLength"], unit=UNIT),
            ("OVERALL_LENGTH", "UNIT", (_SELF, "FRONT_KEEP")),
        ),
        "length_nominal": (OVERALL_LENGTH, ("OVERALL_LENGTH",)),
        "length_from": ("inner_face", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"length": _P["OverallLength"]},
)
# The two side faces, each one flat down the lug and the foot: the -Z one
# locates the foot hole (TOP_KEEP "ScrewFromSide"); the +Z one closes the
# width .55 (RIGHT_KEEP "Depth").
requirement(
    "near_side",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), _HALF_W),),
    requirements=("plane",),
    fields={"plane": (_plane("z", -_HALF_W), (_FRAME, "KEEPER_WIDTH"))},
)
requirement(
    "far_side",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), _HALF_W),),
    requirements=("width",),
    fields={
        "plane": (_plane("z", _HALF_W), (_FRAME, "KEEPER_WIDTH")),
        "width": (
            limits(KEEPER_WIDTH, _P["Depth"], unit=UNIT),
            ("KEEPER_WIDTH", "UNIT", (_SELF, "RIGHT_KEEP")),
        ),
        "width_nominal": (KEEPER_WIDTH, ("KEEPER_WIDTH",)),
        "width_from": ("near_side", ((_SELF, "RIGHT_KEEP"),)),
    },
    precision={"width": _P["Depth"]},
)
# The foot-to-lug inside corner (the .227 foot top meets the lug's outer face,
# along Z): the single limit R.02 MAX (FRONT_KEEP "CornerRadius", #3744 Panel F).
requirement(
    "inside_corner",
    kind="fillet",
    faces=(CylinderFace(2.0 * CORNER_R_MAX),),
    requirements=("radius",),
    fields={
        "at": ([LUG_HALF_T, FOOT_H, 0.0], ("LUG_HALF_T", "FOOT_H")),
        "axis": ((0.0, 0.0, 1.0), (_FRAME,)),
        "radius": (
            limits(CORNER_R_MAX, CORNER_R_PLACES, CORNER_R_BAND, unit=UNIT),
            (
                "CORNER_R_MAX",
                "CORNER_R_BAND",
                "CORNER_R_TOL_TYPE",
                (_SELF, "FRONT_KEEP"),
            ),
        ),
        "radius_nominal": (CORNER_R_MAX, ("CORNER_R_MAX",)),
        "callout": (
            CORNER_CALLOUT,
            ((_NOTES, "CORNER_CALLOUT"), (_SELF, "FRONT_DIMENSION_CALLOUTS")),
        ),
    },
    precision={"radius": CORNER_R_PLACES},
)
# The crown: a full round about the bore axis, tangent to both side faces
# (RIGHT_KEEP "CrownRadius", printed as the reference (R.275) with FULL R).
requirement(
    "crown",
    kind="arc",
    faces=(CylinderFace(2.0 * CROWN_R),),
    requirements=("radius",),
    fields={
        "center": ([0.0, SHAFT_AXIS_H, 0.0], ("SHAFT_AXIS_H",)),
        "axis": ((1.0, 0.0, 0.0), (_FRAME,)),
        "apex": ((0.0, 1.0, 0.0), (_FRAME,)),
        "radius": (
            [CROWN_LEAST_R, CROWN_MOST_R],
            ("CROWN_LEAST_R", "CROWN_MOST_R", (_SELF, "RIGHT_KEEP")),
        ),
        "radius_nominal": (CROWN_R, ("CROWN_R",)),
        "callout": (CROWN_CALLOUT, ((_NOTES, "CROWN_CALLOUT"),)),
        "overall_height_ref": (CROWN_TOP_Y, ("CROWN_TOP_Y", (_SELF, "FRONT_KEEP"))),
    },
    precision={
        "radius": _P["CrownRadius"],
        "overall_height_ref": _P["OverallHeight"],
    },
)
# The shaft bore, F-drilled through the lug from its outer face: Ø.257
# F DRILL THRU, SLIDING CLEARANCE ON MHA-CH-04 (RIGHT_KEEP "BoreDia").
_BORE_CALLOUT = ((_SELF, "RIGHT_DIMENSION_CALLOUTS"),)
requirement(
    "bore",
    kind="hole",
    faces=(CylinderFace(BORE_DIA),),
    requirements=("dia", "thru", "height", "off_centre"),
    fields={
        "at": ([LUG_HALF_T, SHAFT_AXIS_H, 0.0], ("LUG_HALF_T", "SHAFT_AXIS_H")),
        "axis": ((-1.0, 0.0, 0.0), (_FRAME,)),
        "dia": (
            limits(BORE_DIA, _P["BoreDia"], BORE_DIA_BAND, unit=UNIT),
            ("BORE_DIA", "BORE_DIA_BAND", (_SELF, "RIGHT_KEEP")),
        ),
        "nominal_dia": (BORE_DIA, ("BORE_DIA",)),
        "drill": (BORE_HOLE_SPEC.size, ("BORE_HOLE_SPEC",)),
        "process": ("drill", _BORE_CALLOUT),
        "thru": (True, _BORE_CALLOUT),
        "callout": (BORE_CALLOUT, ((_NOTES, "BORE_CALLOUT"), *_BORE_CALLOUT)),
        "height": (
            limits(SHAFT_AXIS_H, _P["LugRise"], unit=UNIT),
            ("SHAFT_AXIS_H", "UNIT", (_SELF, "RIGHT_KEEP")),
        ),
        "height_nominal": (SHAFT_AXIS_H, ("SHAFT_AXIS_H",)),
        "height_from": ("seat", ((_SELF, "RIGHT_KEEP"),)),
        "off_centre": (
            [-BORE_CENTRE_BAND_MM, BORE_CENTRE_BAND_MM],
            ("BORE_CENTRE_BAND_MM", "BORE_CENTRE_CALLOUT"),
        ),
        "off_centre_nominal": (0.0, ("BORE_CENTRE_BAND_MM",)),
        "lateral_ref": (BORE_FROM_SIDE, ("BORE_FROM_SIDE", (_SELF, "RIGHT_KEEP"))),
        "lateral_ref_from": ("near_side", ((_SELF, "RIGHT_KEEP"),)),
        "centre_callout": (BORE_CENTRE_CALLOUT, ("BORE_CENTRE_CALLOUT",)),
    },
    precision={
        "dia": _P["BoreDia"],
        "height": _P["LugRise"],
        "off_centre": _P["BoreFromSide"],
        "lateral_ref": _P["BoreFromSide"],
    },
)
# The crown set-screw tap, #1-72 down through the crown top on the lug
# mid-plane into the bore, its station .16 off the inner face.
_TAP_CALLOUT = (
    "SET_SCREW_HOLE_SPEC",
    (_SELF, "set_screw_callout_definitions"),
    (_SELF, "SET_SCREW_CALLOUT_PRECISION"),
)
_TAP_DRILL_SOURCES = ("SET_SCREW_HOLE_SPEC", ("_hole_spec", "blind_cut_dia_mm"))
requirement(
    "crown_tap",
    kind="threaded_hole",
    faces=(CylinderFace(_TAP_DRILL),),
    requirements=("thread", "dia", "into", "station"),
    fields={
        "at": ([0.0, CROWN_TOP_Y, 0.0], ("CROWN_TOP_Y", "SET_SCREW_HOLE_SPEC")),
        "axis": ((0.0, -1.0, 0.0), (_FRAME, "SET_SCREW_HOLE_SPEC")),
        "thread": (
            f"{SET_SCREW_THREAD} UNF-{SET_SCREW_HOLE_SPEC.thread_class}",
            ("SET_SCREW_THREAD", *_TAP_CALLOUT),
        ),
        "dia": (
            drilled_limits(
                _TAP_DRILL, SET_SCREW_CALLOUT_PRECISION["hw-tapdrldia"], unit=UNIT
            ),
            (*_TAP_DRILL_SOURCES, "UNIT", *_TAP_CALLOUT),
        ),
        "nominal_dia": (_TAP_DRILL, _TAP_DRILL_SOURCES),
        "into": ("bore", ("SET_SCREW_HOLE_SPEC", (_SELF, "SET_SCREW_EXTENT"))),
        "extent": (SET_SCREW_EXTENT, ((_SELF, "SET_SCREW_EXTENT"),)),
        "mates": (SET_SCREW_QUALIFIER, ((_NOTES, "SET_SCREW_QUALIFIER"),)),
        "station": (
            limits(LUG_HALF_T, _P["SetScrewLocation"], unit=UNIT),
            ("LUG_HALF_T", "UNIT", (_SELF, "TOP_KEEP")),
        ),
        "station_nominal": (LUG_HALF_T, ("LUG_HALF_T",)),
        "station_from": ("inner_face", ((_SELF, "TOP_KEEP"),)),
    },
    precision={
        "dia": SET_SCREW_CALLOUT_PRECISION["hw-tapdrldia"],
        "station": _P["SetScrewLocation"],
    },
)
# The foot hole, drilled through the .227 stepped foot (#3744 Panel F;
# Ø.094 DRILL THRU, CENTERS MHA-FR-02 TAP), its station .18 off the foot tip
# and .275 off the -Z side face (TOP_KEEP "ScrewFromTip", "ScrewFromSide").
_FOOT_CALLOUT = (
    "SCREW_HOLE_SPEC",
    "FOOT_HOLE_CALLOUT_PRECISION",
    (_SELF, "foot_hole_callout_definitions"),
)
_FOOT_PLACES = FOOT_HOLE_CALLOUT_PRECISION["hw-diam"]
requirement(
    "foot_hole",
    kind="hole",
    faces=(CylinderFace(HOLE_DIA_MM),),
    requirements=(
        "dia",
        "thru",
        "station",
        "lateral",
    ),
    fields={
        "at": ([SCREW_X, FOOT_H, 0.0], ("SCREW_X", "FOOT_H")),
        "axis": ((0.0, -1.0, 0.0), (_FRAME,)),
        "dia": (
            drilled_limits(HOLE_DIA_MM, _FOOT_PLACES, unit=UNIT),
            ("HOLE_DIA_MM", "UNIT", *_FOOT_CALLOUT),
        ),
        "nominal_dia": (HOLE_DIA_MM, ("HOLE_DIA_MM",)),
        "process": ("drill", ((_SELF, "FOOT_HOLE_THRU"),)),
        "thru": (True, ((_SELF, "FOOT_HOLE_THRU"),)),
        "mates": (FOOT_HOLE_MATE, ((_NOTES, "FOOT_HOLE_MATE"),)),
        "station": (
            limits(SCREW_FROM_TIP, _P["ScrewFromTip"], unit=UNIT),
            ("SCREW_FROM_TIP", "UNIT", (_SELF, "TOP_KEEP")),
        ),
        "station_nominal": (SCREW_FROM_TIP, ("SCREW_FROM_TIP",)),
        "station_from": ("foot_tip", ((_SELF, "TOP_KEEP"),)),
        "lateral": (
            limits(SCREW_FROM_SIDE, _P["ScrewFromSide"], unit=UNIT),
            ("SCREW_FROM_SIDE", "UNIT", (_SELF, "TOP_KEEP")),
        ),
        "lateral_nominal": (SCREW_FROM_SIDE, ("SCREW_FROM_SIDE",)),
        "lateral_from": ("near_side", ((_SELF, "TOP_KEEP"),)),
    },
    precision={
        "dia": _FOOT_PLACES,
        "station": _P["ScrewFromTip"],
        "lateral": _P["ScrewFromSide"],
    },
)


def _one(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    return matches[0]


@_telemetry.traced("drawing.fulcrum_keeper.corner_radius")
def _dress_corner_radius(adapter: Any, annotations: list[Any]) -> None:
    """Prove the front view's CornerRadius prints the part's R.02 MAX and stop
    its leader at the arc (draw_ch_pivot_bracket._dress_corner_radius)."""
    annotation = _early_bound(_one(adapter, annotations, "CornerRadius"), "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported corner radius is not radial")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != CORNER_R_TOL_TYPE:
        raise RuntimeError(
            f"CornerRadius lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), CORNER_R_MAX / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError("CornerRadius does not measure the corner fillet")
    display.ArcExtensionLineOrOppositeSide = False
    if bool(display.ArcExtensionLineOrOppositeSide):
        raise RuntimeError("CornerRadius leader still runs to the opposite side")
    _telemetry.info(f"corner radius: text {display.GetText(1)!r}, MAX type")


@_telemetry.traced("drawing.fulcrum_keeper.crown_radius")
def _dress_crown_radius(adapter: Any, annotations: list[Any]) -> None:
    """Print the end view's CrownRadius as the radial reference "(R.275)" and
    stop its leader at the arc (draw_dt_arbor_pedestal._show_crown_radius)."""
    annotation = _early_bound(_one(adapter, annotations, "CrownRadius"), "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if not math.isclose(float(dimension.SystemValue), CROWN_R / 1000.0, abs_tol=1e-9):
        raise RuntimeError(f"CrownRadius does not measure the {CROWN_R:g} mm full round")
    if bool(display.Diametric):
        raise RuntimeError("the imported crown dimension is not radial")
    existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
    prefix = "(" + existing
    display.SetText(1, prefix)
    display.SetText(2, ")")  # swDimensionTextSuffix
    applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    _telemetry.info(
        f"CrownRadius: radial reference prefix {existing!r} -> {applied[0]!r}, "
        f"suffix {applied[1]!r}, tolerance type {int(tolerance.Type)}"
    )
    if applied != (prefix, ")"):
        raise RuntimeError(f"failed to mark CrownRadius as a radial reference: {applied}")
    display.ArcExtensionLineOrOppositeSide = False
    display.ArrowSide = _ARROWS_OUTSIDE
    display.SolidLeader = False
    if (
        bool(display.Diametric)
        or bool(display.ArcExtensionLineOrOppositeSide)
        or int(display.ArrowSide) != _ARROWS_OUTSIDE
        or bool(display.SolidLeader)
    ):
        raise RuntimeError("crown radius kept its leader to the arc's centre")


def _reference_line_in_view(view: Any, sketch_name: str, length_mm: float) -> Any:
    """The drawing-view instance of one reference sketch's construction line,
    chosen on the model (the sketch's one construction segment of that
    length) and mapped into ``view`` -- a point pick on the outline would
    resolve to the edge under it."""
    native = _early_bound(view, "IView")
    model = native.ReferencedDocument
    if model is None:
        raise RuntimeError(f"{sketch_name}: the front view references no model")
    feature = _early_bound(model, "IPartDoc").FeatureByName(sketch_name)
    if feature is None:
        raise RuntimeError(f"{sketch_name}: no such feature in the keeper model")
    sketch = _early_bound(
        _early_bound(feature, "IFeature").GetSpecificFeature2(), "ISketch"
    )
    matches = []
    for raw in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw, "ISketchSegment")
        length = float(segment.GetLength()) * 1000.0
        if (
            bool(segment.ConstructionGeometry)
            and abs(length - length_mm) <= REFERENCE_WITNESS_LEN_TOL
        ):
            matches.append(segment)
    if len(matches) != 1:
        raise RuntimeError(
            f"{sketch_name}: {len(matches)} construction segments are "
            f"{length_mm:.3f} mm long; the reference line must be exactly one"
        )
    in_view = native.GetCorresponding(matches[0])
    if in_view is None:
        raise RuntimeError(f"{sketch_name}: its line has no instance in the front view")
    return _early_bound(in_view, "ISketchSegment")


@_telemetry.traced("drawing.fulcrum_keeper.blacken_reference_lines")
def _blacken_reference_lines(adapter: Any, view: Any) -> None:
    """Draw each FRONT_REFERENCE_WITNESSES line in the outline's black."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the keeper front view for its references")
    for sketch_name, expected in FRONT_REFERENCE_WITNESSES.items():
        line = _reference_line_in_view(view, sketch_name, expected)
        draw.ClearSelection2(True)
        selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
        selection_data = selection.CreateSelectData()
        selection_data.View = view
        if not line.Select4(False, selection_data):
            raise RuntimeError(f"failed to select the {sketch_name} line")
        kind = int(selection.GetSelectedObjectType3(1, -1))
        if kind != SW_SEL_EXT_SKETCH_SEGS:
            raise RuntimeError(f"{sketch_name} line pick resolved to type {kind}")
        segment = _early_bound(selection.GetSelectedObject6(1, -1), "ISketchSegment")
        length = float(segment.GetLength()) * 1000.0
        construction = bool(segment.ConstructionGeometry)
        if abs(length - expected) > REFERENCE_WITNESS_LEN_TOL or not construction:
            raise RuntimeError(
                f"{sketch_name} line pick resolved to {segment.GetName()} "
                f"({length:.3f} mm, want {expected:.3f}; construction={construction})"
            )
        drawing.SetLineColor(REFERENCE_WITNESS_COLOR)
        draw.ClearSelection2(True)
        _telemetry.info(f"fulcrum-keeper: {sketch_name} line drawn black")
    draw.EditRebuild3()


def set_screw_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Rewrite the native crown-tap callout's definition parts (5..8)."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    if "\n".join(definitions.values()).count("<hw-thru>") != 2:
        raise RuntimeError(f"tap callout lacks its two native extents: {definitions!r}")
    updated = {
        part: text.replace("<hw-thru>", SET_SCREW_EXTENT)
        for part, text in definitions.items()
    }
    thread_parts = [
        part for part, text in updated.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(f"tap thread line is not in one callout part: {updated!r}")
    part = thread_parts[0]
    without_class = re.sub(r" {2,}", " ", _THREAD_CLASS.sub(" ", updated[part]))
    updated[part] = f"{without_class.rstrip()}\n{SET_SCREW_QUALIFIER}"
    return updated


@_telemetry.traced("drawing.fulcrum_keeper.tap_callout_text")
def _set_tap_callout_text(display: Any) -> None:
    """Write the rewritten definitions and prove they persisted."""
    native = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = set_screw_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(native.GetText(part) or "") for part in (1, 2, 3, 4)}
    joined = "\n".join(resolved.values())
    if (
        persisted != updated
        or joined.count(SET_SCREW_EXTENT) != 2
        or "2B" in joined
        or not any(
            text.rstrip().endswith(SET_SCREW_QUALIFIER) for text in resolved.values()
        )
    ):
        raise RuntimeError(
            "crown tap callout text did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
    _telemetry.info(f"crown tap callout: {resolved!r}")


def foot_hole_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Write the native THRU row's extent as FOOT_HOLE_THRU (size, DRILL,
    THRU) and put FOOT_HOLE_MATE in the CalloutBelow part (8)."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected foot-hole callout parts: {definitions!r}")
    thru_parts = [part for part, text in definitions.items() if "THRU" in text.upper()]
    if len(thru_parts) != 1 or thru_parts[0] == 8:
        raise RuntimeError(f"foot-hole THRU row is not in one part: {definitions!r}")
    part = thru_parts[0]
    if definitions[part].count("<hw-thru>") != 1:
        raise RuntimeError(f"foot-hole THRU row has no single native extent: {definitions!r}")
    below = definitions[8].rstrip()
    return {
        **definitions,
        part: definitions[part].replace("<hw-thru>", FOOT_HOLE_THRU),
        8: f"{below}\n{FOOT_HOLE_MATE}" if below else FOOT_HOLE_MATE,
    }


@_telemetry.traced("drawing.fulcrum_keeper.foot_hole_process")
def _set_foot_hole_process(display: Any) -> None:
    """Write the foot hole's process and mate row and prove they persisted."""
    native = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = foot_hole_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(native.GetText(part) or "") for part in (1, 2, 3, 4)}
    first = resolved[3] or resolved[1]
    if (
        persisted != updated
        or FOOT_HOLE_THRU not in first
        or not resolved[4].rstrip().endswith(FOOT_HOLE_MATE)
    ):
        raise RuntimeError(
            "foot-hole process/mate rows did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
    _telemetry.info(f"foot-hole callout: {resolved!r}")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open fulcrum-keeper source", adapter.open_model(str(SOURCE)))
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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-fulcrum-keeper"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Fulcrum Keeper Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fulcrum keeper; shaft end bracket; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, top, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        _P,
    )
    for name in NEAR_SIDE_DIAMETERS:
        set_near_side_diameter(_one(adapter, right_annotations, name), f"keeper {name}")
    _dress_corner_radius(adapter, front_annotations)
    _dress_crown_radius(adapter, right_annotations)
    offset_dimension_text(
        adapter, front_annotations, {"FootRise": FOOT_RISE_TEXT_XY}
    )
    kept = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, kept, DIMENSION_CALLOUTS)
    for name in REFERENCE_DIMENSIONS:
        set_reference_dimension(
            adapter, _one(adapter, kept, name), label=f"keeper {name}"
        )
    _blacken_reference_lines(adapter, front)

    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")

    foot_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=FOOT_HOLE_EDGE_XY,
        callout_xy=FOOT_HOLE_CALLOUT_XY,
        label="keeper foot screw hole",
    )
    _set_foot_hole_process(foot_callout)
    set_hole_callout_precision(
        foot_callout, FOOT_HOLE_CALLOUT_PRECISION, label="keeper foot screw hole"
    )
    tap_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TAP_X_SHEET - TAP_R_SHEET, TOP_CENTER[1]),
        callout_xy=SET_SCREW_CALLOUT_XY,
        label="crown set-screw tap",
    )
    _set_tap_callout_text(tap_callout)
    set_hole_callout_precision(
        tap_callout, SET_SCREW_CALLOUT_PRECISION, label="crown set-screw tap"
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, NOTES_TOP)
    add_property_linked_note(adapter, "Isometric View Note", 0.310, 0.163)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Keeper Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
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
