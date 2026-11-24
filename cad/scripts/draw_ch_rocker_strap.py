r"""Create the manufacturing drawing for the rocker strap (MHA-CH-13).

Under ``cad/docs/drawing-guidelines.md``, in decimal inch (the part's
``drawing_unit: in``): the flat strap of the built-up rocker arm MHA-CH-06
(``ch_rocker_strap_spec``), every size a native model dimension of its one
profile sketch, located from the Ø.4000 hub hole's centre (rule 10): the top
edge's height over the hole and the bottom edge's depth under it, both on the
hole's vertical centreline (its centre mark's extended arms), which is the
part's symmetry axis and so carries both arcs' centres (~32 in off the
sheet); each arc's own radius; both tip corners' and both taper feet's
offsets, and the 2X radial tip land; the parenthesised overall length across
the tip corners ties the two offsets together (rule 10: the overall size is
conspicuous). The hole prints the .4000 reamer's size with no band, names
the MHA-CH-12 hub turned to it (rule 4, made to fit; the bond clearance is the
hub sheet's) and keeps both its edges sharp (the title block's break would
groove the bonded root); the thickness, on the end view, names the rod fork it
runs in. No notes, no datums, no frames, no roughness symbol (rule 6: a
bonded bore carries none). The decimal places and bands are the PART's
(``ch_rocker_strap_notes.DRAWING_PRECISION``); this script only reads them
back off the sheet.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_strap.py ch-rocker-strap
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

import _telemetry
from _check import check
from _com import _early_bound
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
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _printed_limits import limits
from _printed_tolerance import angular_band_deg
from _session import run_build
from ch_rocker_arm_spec import _ALPHA_TOP
from ch_rocker_hub_fit import STRAP_HOLE_BAND
from ch_rocker_strap_notes import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HOLE_CALLOUT,
    HOLE_EDGE_CALLOUT,
    STRAP_FIT_CALLOUT,
    TIP_LAND_ANGLE_PREFIX,
)
from ch_rocker_strap_spec import (
    ARM_THICKNESS,
    ARM_THICKNESS_BAND,
    BOT_END_X,
    BOT_END_Y,
    BOTTOM_EDGE_BAND,
    BOTTOM_EDGE_BELOW_PIVOT,
    CENTER_Y,
    DRAWING_REFERENCE_PRECISION,
    HOLE_DIA,
    HUB_NUMBER,
    PIVOT_MID_Y,
    R_BOTTOM,
    R_TOP,
    ROD_TIP_X,
    ROD_TIP_Y,
    TIP_FACE,
    TOP_EDGE_ABOVE_PIVOT,
    TOP_EDGE_BAND,
    TOP_END_X,
    TOP_END_Y,
    UNIT,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_strap"]
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

# The 292.5 mm strap at full size across the sheet's upper band, its 2.5 mm
# end view to the right; the isometric at 1:2 (captioned, it differs from the
# sheet scale) and the note sit left of the title block below. At 1:4 the
# 2.5 mm plate rendered stair-stepped (r1 and r4 machinist reviews), so the
# view is doubled: its diagonal runs ~(0.083, 0.115) to ~(0.187, 0.049),
# under the foot offsets' line (y 0.125) and left of the title block (x
# 0.215), the caption in the empty corner below its upper-left end.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 2)
FRONT_CENTER = (0.185, 0.185)
RIGHT_CENTER = (0.385, FRONT_CENTER[1])  # projected: same row as the front
ISO_CENTER = (0.135, 0.082)
ISO_CAPTION_XY = (0.105, 0.052)  # centred under the pictorial's low end


def _front(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a model (x, y) on the 1:1 front view, whose box is
    centred on FRONT_CENTER: x spans +-ROD_TIP_X, y 0..TOP_END_Y."""
    return (
        FRONT_CENTER[0] + x_mm / 1000.0,
        FRONT_CENTER[1] + (y_mm - TOP_END_Y / 2.0) / 1000.0,
    )


_HOLE = _front(0.0, PIVOT_MID_Y)
# The tip corners' offsets on one dimension line above the strap, the taper
# feet's on one below it, each pair meeting on the hole centre's extension
# line. Between the strap and the lower line: the R31.5's text (far left,
# below both arcs, so its leader stays outside its circle --
# draw_ch_rocker_arm _dress_arc_radii), the bottom edge's depth under the
# hole, the hole's callout (right, its leader short) and the R32.1's text
# right of that callout, short of the end view's thickness block. The top
# edge's height reads left of the hole, under the upper line. A vertical
# dimension's text stands LEFT of its dimension line, ending at the requested
# x (r3: the depth's ~55 mm rows ran x 0.093..0.147 over the R31.5 at x
# 0.100), so the depth's line sits 12 mm left of the hole and the R31.5
# moves to x 0.090, right of the left foot's extension line at x 0.052,
# raised so its leader up to the top arc clears those rows.
TIP_LINE_Y = 0.232
FOOT_LINE_Y = 0.125
# The overall length (ENFORCE r3: only the two 146.25 offsets gave it) on its
# own row above the offsets' line, the longest outermost, under the border
# (~0.267).
OVERALL_LINE_Y = 0.249
FRONT_KEEP = {
    "TailTipX": (FRONT_CENTER[0] - ROD_TIP_X / 2000.0, TIP_LINE_Y),
    "RodTipX": (FRONT_CENTER[0] + ROD_TIP_X / 2000.0, TIP_LINE_Y),
    "BottomTailX": (FRONT_CENTER[0] - BOT_END_X / 2000.0, FOOT_LINE_Y),
    "BottomRodX": (FRONT_CENTER[0] + BOT_END_X / 2000.0, FOOT_LINE_Y),
    "TopRadius": (FRONT_CENTER[0] - 0.095, 0.166),
    "BottomRadius": (FRONT_CENTER[0] + 0.115, 0.166),
    "BottomBelowPivot": (_HOLE[0] - 0.012, 0.160),
    # The callout's rows stack UP from the requested y: with its sharp-edge
    # row at 0.160 (strap-sharp-r1) the +0.018 limit sat on the strap's bottom
    # edge. Dropped one row for that row (0.153, r2: clear), then 4 mm more
    # for its reason row (r3), whose last row still clears the foot line.
    "HoleDia": (_HOLE[0] + 0.060, 0.149),
    "TopAbovePivot": (_HOLE[0] - 0.035, 0.207),
    # The land's two extension lines run ~5.6 mm apart, rising ~10 deg to the
    # right (perpendicular to the radial land); the upper one passes y ~0.206
    # at x 0.365. Between them (r1, r2) a line struck the text, so it stands
    # above both, the dimension line carried up to it.
    "RodTipLen": (_front(ROD_TIP_X, 0.0)[0] + 0.031, 0.226),
    # The land's angle from vertical (r4: "RADIAL" named a centre the sheet
    # does not show). Inside the 10.5 deg wedge (25 mm down its bisector, r5)
    # the ~18 mm text was struck by its own arc and extension line, so it
    # stands right of the land's extension line at the same 25 mm radius,
    # 2 mm clear of it, the arc carried out (detail E on MHA-CH-06): above the
    # thickness callout (y < 0.159), left of the end view.
    "TipLandAngle": (
        _front(TOP_END_X, TOP_END_Y)[0] + 0.025 * math.sin(_ALPHA_TOP) + 0.002 + 0.009,
        _front(TOP_END_X, TOP_END_Y)[1] - 0.025 * math.cos(_ALPHA_TOP),
    ),
}

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, each beside the code that
# prints it, in the part's model frame (ch_rocker_strap_spec: origin on the
# mirror axis at the book bottom edge, +X the rod side, the hub hole
# PIVOT_MID_Y up on that axis, the strap extruded mid-plane in Z). A band is
# the dimension's own native band, else the title block's row for the places
# it prints at (DRAWING_PRECISION); the declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
part_metadata(
    fields={
        "material.thickness": (
            ARM_THICKNESS,
            (("ch_rocker_arm_spec", "ARM_THICKNESS"),),
        ),
    },
    model_sources=(
        ("ch_rocker_arm_spec", "ARM_THICKNESS"),
        ("_rocker_interface", "PIVOT_MID_Y"),
    ),
    precision_sources=(
        ("ch_rocker_strap_notes", "DRAWING_PRECISION"),
        ("ch_rocker_strap_notes", "DRAWING_PRECISION_BY_NAME"),
        "DRAWING_REFERENCE_PRECISION",
    ),
)
# The hub hole's Ø, its callout (FRONT_KEEP "HoleDia", DIMENSION_CALLOUTS)
# and the reamer's modelled cut, STRAP_HOLE_BAND (an analysis band: the sheet
# prints REAM with no band): every printed location runs from its centre.
_HOLE_CALLOUT_SOURCES = (
    ("ch_rocker_strap_notes", "HOLE_CALLOUT"),
    ("ch_rocker_strap_notes", "DIMENSION_CALLOUTS"),
    ("draw_ch_rocker_strap", "build"),
)
requirement(
    "hub_hole",
    kind="hole",
    faces=(CylinderFace(HOLE_DIA),),
    requirements=("dia", "thru"),
    fields={
        "at": ([0.0, PIVOT_MID_Y, 0.0], (("_rocker_interface", "PIVOT_MID_Y"),)),
        "axis": ((0.0, 0.0, 1.0), ("__frame__",)),
        "dia": (
            limits(HOLE_DIA, _P["HoleDia"], STRAP_HOLE_BAND),
            (
                "HOLE_DIA",
                ("ch_rocker_hub_fit", "STRAP_HOLE_BAND"),
                ("draw_ch_rocker_strap", "FRONT_KEEP"),
            ),
        ),
        "nominal_dia": (HOLE_DIA, ("HOLE_DIA",)),
        "thru": (True, _HOLE_CALLOUT_SOURCES),
        "process": ("ream", _HOLE_CALLOUT_SOURCES),
        "mate": (HUB_NUMBER, ("HUB_NUMBER", *_HOLE_CALLOUT_SOURCES)),
        "edge_note": (
            HOLE_EDGE_CALLOUT,
            (("ch_rocker_strap_notes", "HOLE_EDGE_CALLOUT"), *_HOLE_CALLOUT_SOURCES),
        ),
        "callout": (HOLE_CALLOUT, _HOLE_CALLOUT_SOURCES),
    },
    precision={"dia": _P["HoleDia"]},
)

# The 2.5 mm end view is narrower than its four-row callout: centred over it
# (r1) both extension lines ran through the text, so the text stands below
# the view, left of its left extension line, the dimension line carried out.
RIGHT_KEEP = {"StrapThickness": (RIGHT_CENTER[0] - 0.027, 0.150)}

# Both broad faces, finished to the end view's thickness (RIGHT_KEEP) and
# never cut again (ch_rocker_strap_spec).
_THICKNESS = (ARM_THICKNESS, (("ch_rocker_arm_spec", "ARM_THICKNESS"),))
for _name, _sign in (("broad_face_pos_z", 1), ("broad_face_neg_z", -1)):
    requirement(
        _name,
        kind="face",
        faces=(PlanarFace((0, 0, _sign), ARM_THICKNESS / 2.0),),
        requirements=("thickness",),
        fields={
            "thickness": (
                limits(ARM_THICKNESS, _P["StrapThickness"], ARM_THICKNESS_BAND),
                (
                    ("ch_rocker_arm_spec", "ARM_THICKNESS"),
                    ("ch_rocker_arm_spec", "ARM_THICKNESS_BAND"),
                    ("draw_ch_rocker_strap", "RIGHT_KEEP"),
                ),
            ),
            "thickness_nominal": _THICKNESS,
            "plane": (
                {"frame": "model", "axis": "z", "value": _sign * ARM_THICKNESS / 2.0},
                _THICKNESS[1],
            ),
            "callout": (
                STRAP_FIT_CALLOUT,
                (
                    ("ch_rocker_arm_notes", "STRAP_FIT_CALLOUT"),
                    ("ch_rocker_strap_notes", "DIMENSION_CALLOUTS"),
                ),
            ),
        },
        precision={"thickness": _P["StrapThickness"]},
    )

ARC_RADIUS_NAMES = ("TopRadius", "BottomRadius")
# The hub hole's template centre mark, its vertical arms extended past both
# edges: the drawn centreline the edges' heights stand on, the part's
# symmetry axis and so the line both arcs' centres lie on (rule 26: a
# location is a dimension or a drawn line, never "CENTRE ABOVE HOLE").
# Extended lengths run from the hole's rim, in sheet metres (the view is
# 1:1); swCenterMarkHandle_e Up 0, Left 1, Down 2, Right 3.
CENTRE_LINE_OVERRUN_MM = 3.0
CENTRE_MARK_ARMS_MM = {
    0: TOP_EDGE_ABOVE_PIVOT - HOLE_DIA / 2.0 + CENTRE_LINE_OVERRUN_MM,
    1: CENTRE_LINE_OVERRUN_MM,
    2: BOTTOM_EDGE_BELOW_PIVOT - HOLE_DIA / 2.0 + CENTRE_LINE_OVERRUN_MM,
    3: CENTRE_LINE_OVERRUN_MM,
}


@_telemetry.traced("drawing.strap_hole_centreline")
def _extend_hole_centreline(front: Any) -> None:
    """Extend the template's one centre mark (the hub hole's) per
    CENTRE_MARK_ARMS_MM (draw_dt_cone_gear_tl_index_plate._centre_mark_bore)."""
    view = _early_bound(front, "IView")
    raw = view.GetFirstCenterMark2()
    if raw is None:
        raise RuntimeError("the strap front view has no hub-hole centre mark")
    mark = _early_bound(raw, "ICenterMark")
    if mark.GetNext() is not None:
        raise RuntimeError("the strap front view carries more than one centre mark")
    mark.UseDocDisplaySettings = False
    mark.ShowLines = True
    for handle, arm_mm in CENTRE_MARK_ARMS_MM.items():
        if not mark.SetExtendedLength(0, handle, arm_mm / 1000.0):
            raise RuntimeError(f"hub-hole centre mark arm {handle} did not extend")
    if bool(mark.UseDocDisplaySettings) or not bool(mark.ShowLines):
        raise RuntimeError("hub-hole centre mark lost its extended lines")
    _telemetry.success(
        "hub-hole centre mark arms: "
        + ", ".join(
            f"{float(mark.GetExtendedLength(0, handle)):.4f}"
            for handle in CENTRE_MARK_ARMS_MM
        )
    )


def _exterior_radius_leaders(adapter: Any, annotations: list[Any]) -> None:
    """Exterior leader on each radius (draw_ch_rocker_arm._dress_arc_radii):
    the ~32 in centre is off the sheet, so no centre-directed leader."""
    remaining = set(ARC_RADIUS_NAMES)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ShortenedRadius = False
        display.ArcExtensionLineOrOppositeSide = False
        display.ArrowSide = 1  # swDimArrowsOutside
        display.SolidLeader = False
        if (
            bool(display.ShortenedRadius)
            or bool(display.ArcExtensionLineOrOppositeSide)
            or int(display.ArrowSide) != 1
            or bool(display.SolidLeader)
        ):
            raise RuntimeError(f"{name} retained its centre-directed radius leader")
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"strap radius dimensions missing: {sorted(remaining)}")


# Each edge's height from the hole on its extended vertical centreline
# (FRONT_KEEP, CENTRE_MARK_ARMS_MM), with the band the finished MHA-CH-06's
# arc-system zone gives it, and each arc's own radius
# (_exterior_radius_leaders) about the shared centre on that line.
_HEIGHT_SOURCES = (
    ("draw_ch_rocker_strap", "FRONT_KEEP"),
    ("draw_ch_rocker_strap", "CENTRE_MARK_ARMS_MM"),
)
_RADIUS_SOURCES = (
    "UNIT",
    ("draw_ch_rocker_strap", "ARC_RADIUS_NAMES"),
    ("draw_ch_rocker_strap", "_exterior_radius_leaders"),
)
_ARC_CENTRE = ([0.0, CENTER_Y, 0.0], (("_rocker_interface", "CENTER_Y"),))
_TOP_EDGE = (
    ("ch_rocker_arm_spec", "TOP_EDGE_ABOVE_PIVOT"),
    ("ch_rocker_arm_spec", "TOP_EDGE_BAND"),
)
_BOTTOM_EDGE = (
    ("ch_rocker_arm_spec", "BOTTOM_EDGE_BELOW_PIVOT"),
    ("ch_rocker_arm_spec", "BOTTOM_EDGE_BAND"),
)
requirement(
    "top_arc",
    kind="profile",
    faces=(CylinderFace(2.0 * R_TOP),),
    requirements=("height_above_pivot", "radius"),
    fields={
        "height_above_pivot": (
            limits(TOP_EDGE_ABOVE_PIVOT, _P["TopAbovePivot"], TOP_EDGE_BAND),
            (*_TOP_EDGE, *_HEIGHT_SOURCES),
        ),
        "height_above_pivot_nominal": (TOP_EDGE_ABOVE_PIVOT, _TOP_EDGE[:1]),
        "height_from": ("hub_hole", _HEIGHT_SOURCES),
        "edge_on_axis": (
            [0.0, PIVOT_MID_Y + TOP_EDGE_ABOVE_PIVOT, 0.0],
            (("_rocker_interface", "PIVOT_MID_Y"), *_TOP_EDGE[:1]),
        ),
        "radius": (
            limits(R_TOP, _P["TopRadius"], unit=UNIT),
            (("ch_rocker_arm_spec", "R_TOP"), *_RADIUS_SOURCES),
        ),
        "radius_nominal": (R_TOP, (("ch_rocker_arm_spec", "R_TOP"),)),
        "arc_centre": _ARC_CENTRE,
        "ends": (
            [[-TOP_END_X, TOP_END_Y, 0.0], [TOP_END_X, TOP_END_Y, 0.0]],
            (("ch_rocker_arm_spec", "TOP_END_X"), ("ch_rocker_arm_spec", "TOP_END_Y")),
        ),
    },
    precision={"height_above_pivot": _P["TopAbovePivot"], "radius": _P["TopRadius"]},
)
requirement(
    "bottom_arc",
    kind="profile",
    faces=(CylinderFace(2.0 * R_BOTTOM),),
    requirements=("height_below_pivot", "radius"),
    fields={
        "height_below_pivot": (
            limits(BOTTOM_EDGE_BELOW_PIVOT, _P["BottomBelowPivot"], BOTTOM_EDGE_BAND),
            (*_BOTTOM_EDGE, *_HEIGHT_SOURCES),
        ),
        "height_below_pivot_nominal": (BOTTOM_EDGE_BELOW_PIVOT, _BOTTOM_EDGE[:1]),
        "height_from": ("hub_hole", _HEIGHT_SOURCES),
        "edge_on_axis": (
            [0.0, PIVOT_MID_Y - BOTTOM_EDGE_BELOW_PIVOT, 0.0],
            (("_rocker_interface", "PIVOT_MID_Y"), *_BOTTOM_EDGE[:1]),
        ),
        "radius": (
            limits(R_BOTTOM, _P["BottomRadius"], unit=UNIT),
            (("_rocker_interface", "R_BOTTOM"), *_RADIUS_SOURCES),
        ),
        "radius_nominal": (R_BOTTOM, (("_rocker_interface", "R_BOTTOM"),)),
        "arc_centre": _ARC_CENTRE,
        "ends": (
            [[-BOT_END_X, BOT_END_Y, 0.0], [BOT_END_X, BOT_END_Y, 0.0]],
            (("ch_rocker_arm_spec", "BOT_END_X"), "BOT_END_Y"),
        ),
    },
    precision={
        "height_below_pivot": _P["BottomBelowPivot"],
        "radius": _P["BottomRadius"],
    },
)


def _dress_tip_land_angle(adapter: Any, annotations: list[Any]) -> None:
    """The imported land angle still measures the real radial land from
    vertical (draw_ch_rocker_arm._dress_detail_dimensions) and counts both
    ends."""
    for annotation in annotations:
        if dimension_name(adapter, annotation) != "TipLandAngle":
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        model_dimension = _early_bound(display.GetDimension2(0), "IDimension")
        actual = None if model_dimension is None else model_dimension.SystemValue
        if (
            int(display.Type2) != 3  # swAngularDimension
            or type(actual) not in (int, float)
            or not math.isfinite(actual)
            or not math.isclose(abs(actual), _ALPHA_TOP, abs_tol=1e-8)
        ):
            raise RuntimeError("tip-land angle lost its native radial-land measurement")
        display.SetText(1, TIP_LAND_ANGLE_PREFIX)
        if str(display.GetText(1) or "") != TIP_LAND_ANGLE_PREFIX:
            raise RuntimeError("tip land angle lost its 2X count")
        return
    raise RuntimeError("strap tip land angle dimension missing")


_TOP_END = (TOP_END_X, TOP_END_Y)
_TIP_CORNER = (ROD_TIP_X, ROD_TIP_Y)
_FOOT = (BOT_END_X, BOT_END_Y)
_CORNER_SOURCES = (("ch_rocker_arm_spec", "ROD_TIP_X"), "ROD_TIP_Y")


def _outline_face(
    start: tuple[float, float], end: tuple[float, float], side: int
) -> PlanarFace:
    """The +X outline face from vertex ``start`` to ``end``, its outward
    normal left of that direction (draw_ch_rocker_arm._plane_between), or for
    ``side`` -1 its mirror about the YZ plane."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    nx, ny = -dy / length, dx / length
    return PlanarFace((side * nx, ny, 0.0), nx * start[0] + ny * start[1])


# Both radial tip lands: the 2X land length and its 2X angle from the hole's
# vertical centreline (_dress_tip_land_angle, under the title block's angular
# row), each tip corner's offset from the hole (FRONT_KEEP "RodTipX" and
# "TailTipX").
_LAND_ANGLE_DEG = math.degrees(_ALPHA_TOP)
_LAND_ANGLE_PRINTED = round(_LAND_ANGLE_DEG, _P["TipLandAngle"])
_ANGULAR_BAND_DEG = angular_band_deg(unit=UNIT)
for _name, _side, _corner_dimension in (
    ("tip_land_pos_x", 1, "RodTipX"),
    ("tip_land_neg_x", -1, "TailTipX"),
):
    requirement(
        _name,
        kind="face",
        faces=(_outline_face(_TOP_END, _TIP_CORNER, _side),),
        requirements=("land_length", "land_angle_deg", "corner_station"),
        fields={
            "land_length": (
                limits(TIP_FACE, _P["RodTipLen"], unit=UNIT),
                (
                    ("ch_rocker_arm_spec", "TIP_FACE"),
                    "UNIT",
                    ("ch_rocker_strap_notes", "TIP_LAND_PREFIX"),
                    ("draw_ch_rocker_strap", "FRONT_KEEP"),
                ),
            ),
            "land_length_nominal": (TIP_FACE, (("ch_rocker_arm_spec", "TIP_FACE"),)),
            "land_angle_deg": (
                [
                    round(_LAND_ANGLE_PRINTED - _ANGULAR_BAND_DEG, 12),
                    round(_LAND_ANGLE_PRINTED + _ANGULAR_BAND_DEG, 12),
                ],
                (
                    ("ch_rocker_arm_spec", "_ALPHA_TOP"),
                    "UNIT",
                    ("ch_rocker_strap_notes", "TIP_LAND_ANGLE_PREFIX"),
                    ("draw_ch_rocker_strap", "_dress_tip_land_angle"),
                ),
            ),
            "land_angle_nominal_deg": (
                _LAND_ANGLE_DEG,
                (("ch_rocker_arm_spec", "_ALPHA_TOP"),),
            ),
            "land_angle_from": (
                "vertical",
                (("draw_ch_rocker_strap", "_dress_tip_land_angle"),),
            ),
            "corner_station": (
                limits(ROD_TIP_X, _P[_corner_dimension], unit=UNIT),
                (
                    ("ch_rocker_arm_spec", "ROD_TIP_X"),
                    "UNIT",
                    ("draw_ch_rocker_strap", "FRONT_KEEP"),
                ),
            ),
            "corner_station_nominal": (
                ROD_TIP_X,
                (("ch_rocker_arm_spec", "ROD_TIP_X"),),
            ),
            "station_from": ("hub_hole", (("draw_ch_rocker_strap", "FRONT_KEEP"),)),
            "inner_end": (
                [_side * TOP_END_X, TOP_END_Y, 0.0],
                (
                    ("ch_rocker_arm_spec", "TOP_END_X"),
                    ("ch_rocker_arm_spec", "TOP_END_Y"),
                ),
            ),
            "corner": ([_side * ROD_TIP_X, ROD_TIP_Y, 0.0], _CORNER_SOURCES),
        },
        precision={
            "land_length": _P["RodTipLen"],
            "land_angle_deg": _P["TipLandAngle"],
            "corner_station": _P[_corner_dimension],
        },
    )


@_telemetry.traced("drawing.strap_overall_length")
def _add_overall_length(adapter: Any, front: Any) -> None:
    """Parenthesised overall length across both tip corners (rule 10), a
    native vertex-to-vertex sheet dimension (draw_ch_rocker_arm's overall
    width): a band-free restatement of the two offsets, so no band and no
    second model size."""
    label = "OverallLength"
    # The +Z face's tip corners: the strap is extruded mid-plane in Z.
    tips = (
        (-ROD_TIP_X, ROD_TIP_Y, ARM_THICKNESS / 2.0),
        (ROD_TIP_X, ROD_TIP_Y, ARM_THICKNESS / 2.0),
    )
    edges = scan_view_edges(front, label="strap front outline")
    vertices = tuple(
        edges.exact_vertex_at(point, label=f"strap tip corner {index}")
        for index, point in enumerate(tips)
    )
    # The vertices are selected as entities and the dimension is forced
    # horizontal, so add_edge_dimension never reads p0/p1: the 1:1 view's
    # nominal sheet points stand in, no COM projection needed (codjiflo P3).
    dimension = add_edge_dimension(
        adapter,
        front,
        p0=_front(-ROD_TIP_X, ROD_TIP_Y),
        p1=_front(ROD_TIP_X, ROD_TIP_Y),
        text_xy=(FRONT_CENTER[0], OVERALL_LINE_Y),
        label="strap overall length",
        orientation="horizontal",
        entities=vertices,
        entity_types=("VERTEX", "VERTEX"),
    )
    dimension = _early_bound(dimension, "IDisplayDimension")
    assert_dimension_measures(
        adapter,
        dimension,
        expected_mm=2.0 * ROD_TIP_X,
        label="strap overall length",
        entities=vertices,
        entity_types=("VERTEX", "VERTEX"),
    )
    annotation = _early_bound(dimension.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError("strap overall length has no native annotation")
    display = set_reference_dimension(adapter, annotation, label="strap overall length")
    # Its places are the spec's (drawing-simplicity-policy.md: a pure
    # reference dimension); -1 leaves the dual and tolerance places alone.
    display = _early_bound(display, "IDisplayDimension")
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != DRAWING_REFERENCE_PRECISION[label]:
        raise RuntimeError(
            f"strap overall length prints {applied} decimal places, "
            f"not {DRAWING_REFERENCE_PRECISION[label]}"
        )


# Both tapered end faces, from the tip corner down to the foot on the bottom
# arc: each foot's offset from the hole (FRONT_KEEP "BottomRodX" and
# "BottomTailX"), and the parenthesised overall length across both tip
# corners (_add_overall_length), a band-free reference.
for _name, _side, _foot_dimension, _land in (
    ("end_face_pos_x", 1, "BottomRodX", "tip_land_pos_x"),
    ("end_face_neg_x", -1, "BottomTailX", "tip_land_neg_x"),
):
    requirement(
        _name,
        kind="face",
        faces=(_outline_face(_TIP_CORNER, _FOOT, _side),),
        requirements=("foot_station",),
        fields={
            "foot_station": (
                limits(BOT_END_X, _P[_foot_dimension], unit=UNIT),
                (
                    ("ch_rocker_arm_spec", "BOT_END_X"),
                    "UNIT",
                    ("draw_ch_rocker_strap", "FRONT_KEEP"),
                ),
            ),
            "foot_station_nominal": (
                BOT_END_X,
                (("ch_rocker_arm_spec", "BOT_END_X"),),
            ),
            "station_from": ("hub_hole", (("draw_ch_rocker_strap", "FRONT_KEEP"),)),
            "foot": (
                [_side * BOT_END_X, BOT_END_Y, 0.0],
                (("ch_rocker_arm_spec", "BOT_END_X"), "BOT_END_Y"),
            ),
            "corner": ([_side * ROD_TIP_X, ROD_TIP_Y, 0.0], _CORNER_SOURCES),
            "corner_feature": (_land, (("draw_ch_rocker_strap", "FRONT_KEEP"),)),
            "overall_length_ref": (
                2.0 * ROD_TIP_X,
                (
                    ("ch_rocker_arm_spec", "ROD_TIP_X"),
                    "DRAWING_REFERENCE_PRECISION",
                    ("draw_ch_rocker_strap", "_add_overall_length"),
                ),
            ),
        },
        precision={
            "foot_station": _P[_foot_dimension],
            "overall_length_ref": DRAWING_REFERENCE_PRECISION["OverallLength"],
        },
    )


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-strap source", adapter.open_model(str(SOURCE)))
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
        unit=part_drawing_unit("ch-rocker-strap"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Strap Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker strap; 1018 flat; hub hole reamed, hub bonded",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # A flat plate: every edge reads on the face view; hidden lines off
    # everywhere (drawing-guidelines.md rule 9).
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *right_annotations]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _exterior_radius_leaders(adapter, front_annotations)
    _dress_tip_land_angle(adapter, front_annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _add_overall_length(adapter, front)
    # The template centre-marks the hub hole as the view is placed
    # (draw_mg_wheel_drum: a second AutoInsertCenterMarks2 printed a
    # duplicate); its vertical arms become the drawn centreline.
    _extend_hole_centreline(front)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_CAPTION_XY)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Strap Manufacturing Drawing",
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
