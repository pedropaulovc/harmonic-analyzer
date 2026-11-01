r"""Create the curated machinist drawing for the rocker arm.

The SLDPRT remains authoritative.  This recipe supplies only the rocker-arm
views, dimension layout, hole callouts, and manufacturing notes;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.
Exported shared profile-radius values and citations belong to
``_rocker_interface.CURVE_RADIUS``; the full part spec owns only local geometry.

The strap is a long thin curved seesaw (~292 mm tip to tip, 16 mm deep, .098
in thick). The sheet prints decimal inch (the part's ``drawing_unit: in``);
the model keeps its millimetre nominals. The front carries the BASIC arc
system and A-to-pin coordinates; parent-linked D (4:1) and E (2:1) carry the
hub and rod-end controls. The 3:1 view F carries thickness/hub width; the 1:4
isometric supplements them.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm.py ch-rocker-arm
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import itertools
import json
import math
import re
import struct
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import dispatch_array, double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_name,
)

import _surface_finish
import ch_rocker_arm_notes as rocker_notes
import ch_rocker_arm_spec as rocker
import _rocker_interface as rocker_interface
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits as _band
from _printed_tolerance import drilled_oversize_mm, drilled_undersize_mm
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _gtol_torus import TorusFace
from _check import check
from _com import _early_bound
from _drawing_attachment import (
    _assert_attached_to,
    _assert_leader_lands,
    _is_same_attachment,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_detail_crop import (
    DETAIL_GEOMETRY_TOL_M,
    native_circle_geometry,
    read_circular_detail_crop,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdge, scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_datum_feature, add_feature_control_frame, add_frame_datum_feature

# The part saves TopEdgeReference hidden (#880): this form shows it in the
# view that imports its dimension.
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_layout_audit import _DISPLAY_PRIMITIVES, _Reader, _dump_annotation, _dump_display
from _drawing_layout_collect import check_drawing_layout
from _drawing_leader_notes import add_leader_note
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _drawing_projection import model_points_in_view
from _drawing_selection import _select_view_entity
from _drawing_sheet_region import sheet_drawable_region
from _part_properties import part_drawing_unit
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _gear_drawing_entities import visible_circle_edge
from _layout_audit import (
    _detail_circles,
    _registered_leaders,
    annotation_geometry,
    polygon_segments,
    polyline_segments,
    triangle_segments,
    calibrate_sheet_advance,
)
from _layout_geometry import (
    ARROW_TEXT_CLEARANCE_M, Box, Segment, clip_segment_to_circle, point_segment_distance,
    segment_box_distance, segment_circle_distance, text_overlap, union_boxes,
)
from _gtol_frame import gtol_frame_signature, gtol_frame_xml
from _gtol_symbols import GTOL_SYMBOLS
from _hole_spec import blind_cut_dia_mm, drill_process
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _seat_forensics
import _telemetry
from ch_channel_assembly_steps import step_ref as channel_step_ref
from ch_rocker_arm_notes import (
    DEFAULT_DRAWING_PRECISION,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
)
from _rocker_interface import CENTER_Y, PIVOT_MID_Y, R_BOTTOM, ROD_HOLE_X, ROD_HOLE_Y
from ch_rocker_arm_spec import (
    ARM_THICKNESS,
    BOT_END_X,
    GEOMETRIC_TOLERANCES_IN,
    HUB_DIA,
    PIVOT_HOLE_DIA,
    PIVOT_HOLE_BAND,
    R_TOP,
    ROD_HOLE_SPEC,
    ROD_TIP_X,
    SURFACE_FINISHES,
    TIP_FACE,
    TOP_ARC_LEN,
    TOP_EDGE_BAND,
    TOP_END_X,
    TOP_END_Y,
    UNIT,
    _ALPHA_TOP,
    inch_text,
)


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2

_ROD_HOLE_DIA = blind_cut_dia_mm(ROD_HOLE_SPEC)
# Hole Wizard drill diameters print three places on the inch sheet (rule 3).
_DRILL_P = 3
_DRILLED_BAND = (drilled_oversize_mm(unit=UNIT), -drilled_undersize_mm(unit=UNIT))
# Geometric-frame zones print three places.
_FRAME_P = 3
_PIVOT_P = rocker_notes.DRAWING_PRECISION["PivotHoleProfile"]["PivotDia"]
_RADIUS_P = rocker_notes.DRAWING_PRECISION["StrapProfile"]["TopRadius"]
# The sheet's own dimensions (the BASIC land, taper and pin stations from A,
# the overall width) are kinematic values: three inch places keep each within
# .0005 of the model.
SHEET_DECIMALS = 3
ROD_CALLOUT_PRECISION = {"hw-diam": _DRILL_P}
# Names the lower arc each taper-foot BASIC lands on.
TAPER_LABEL = f"R{inch_text(R_BOTTOM, _RADIUS_P)}/TAPER"

_P = rocker_notes.DEFAULT_DRAWING_PRECISION
_AXIS = ((0.0, 0.0, 1.0), ("__frame__",))
_CENTRE = ([0.0, rocker_interface.PIVOT_MID_Y, 0.0], (("_rocker_interface", "PIVOT_MID_Y"),))

part_metadata(
    fields={
        "precision": (_P, (("ch_rocker_arm_notes", "DEFAULT_DRAWING_PRECISION"),)),
        "material.thickness": (rocker.ARM_THICKNESS, ("ARM_THICKNESS",)),
    },
    model_sources=("ARM_THICKNESS", "HUB_LENGTH"),
    precision_sources=(("ch_rocker_arm_notes", "DRAWING_PRECISION"), ("ch_rocker_arm_notes", "DEFAULT_DRAWING_PRECISION"), ("ch_rocker_arm_notes", "DRAWING_NOTES"), ("_surface_finish", "ra")),
)

FRONT_CENTER = (0.180, 0.175)
# View F (3:1) stands alone in the free band left of the front view, between
# the 292.5 row's left witness (x 0.107) and the border, above the notes.
RIGHT_CENTER = (0.075, 0.195)
RIGHT_SCALE = (rocker_notes.RIGHT_VIEW_SCALE, 1)
ISO_CENTER = (0.345, 0.205)
ROD_HOLE = requirement(
    "rod_hole", kind="hole", faces=(CylinderFace(blind_cut_dia_mm(rocker.ROD_HOLE_SPEC)),),
    requirements=("at", "dia", "thru", "position_dia"), fields={
        "at": ([rocker_interface.ROD_HOLE_X, rocker_interface.ROD_HOLE_Y, 0.0], (("_rocker_interface", "ROD_HOLE_X"), ("_rocker_interface", "ROD_HOLE_Y"))),
        "axis": _AXIS, "drill": (rocker.ROD_HOLE_SPEC.size, ("ROD_HOLE_SPEC",)),
        "dia": (_band(blind_cut_dia_mm(rocker.ROD_HOLE_SPEC), _DRILL_P, _DRILLED_BAND), ("ROD_HOLE_SPEC", "UNIT", ("_hole_spec", "NUMBER_DRILL_MM"), ("_drawing_hole_callout", "add_native_hole_callout"))),
        "nominal_dia": (blind_cut_dia_mm(rocker.ROD_HOLE_SPEC), ("ROD_HOLE_SPEC", ("_hole_spec", "NUMBER_DRILL_MM"))),
        "thru": (rocker.ROD_HOLE_SPEC.end == "through_all", ("ROD_HOLE_SPEC", ("_drawing_hole_callout", "add_native_hole_callout"))),
        "position_dia": (float(rocker.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"]), ("GEOMETRIC_TOLERANCES_MM",)),
        # Datum C clocks the arm from the rod pin, which sets the arm's angle
        # (Pedro, option 4). Its own position can only refer to A|B: rotation
        # about A is free, so the Ø.008 holds its distance from A.
        "position_datums": (["A", "B"], (("draw_ch_rocker_arm", "build"),)),
        "dimension_type": ("basic", (("draw_ch_rocker_arm", "build"),)),
        "datum": ("C", (("draw_ch_rocker_arm", "build"),)),
    }, precision={"at": "unknown", "dia": _DRILL_P, "position_dia": _FRAME_P},
)
HUB_CENTER = (0.180, 0.095)
END_CENTER = (0.330, 0.110)
HUB_SCALE = (4.0, 1.0)
END_SCALE = (2.0, 1.0)
# D's letter sits below-right of its small parent fence around A, clear of the
# R800/R816 texts below the strap's left half; DETAIL_STYLE leads it to the fence.
DETAIL_LETTER_XY = {"D": (0.188, 0.161), "E": (0.264, 0.155)}
# D's crop is a view boundary, not a third concentric manufactured diameter.
# Keep its persisted circular fence; omit only the printed detail-view outline.
DETAIL_NO_OUTLINE = {"D": True, "E": False}
# swDetViewStyle_e. D's fence is close to the hub OD on the 1:2 front;
# a free letter made it read as a third concentric circle. Both letters sit
# away from their source circles to clear the profile controls (#1590/#1442).
# Native leaders keep those displaced labels unambiguous.
DETAIL_STYLE = {"D": 2, "E": 2}  # swDetViewLEADER
# DOT on the printed south centre-mark arm, at the actual hole's south rim.
# Keep the circular model edge attached; never move an FCF attachment by setter.
FCF_XY = (0.262, 0.1001)
# Datum C's symbol hangs under the rod-pin frame at the middle of its width
# (Y14.5 puts a feature of size's datum feature symbol on its frame; a tag on
# the hole callout attaches to nothing -- _drawing_gdt.add_frame_datum_feature).
# v43 printed ⌖|Ø0.20|A|B|C as 7.0+16.3+6.2+5.6+6.6 mm cells, one 7.0 mm row:
# without C the frame is ~35.1 mm wide. The helper holds x to the frame and
# fails the sheet past 3 mm; 5 mm of stem stand above the 7 mm letter box,
# whose bottom middle this is.
ROD_FRAME_SIZE = (0.0351, 0.0070)
DATUM_TAG_BOX = 0.007
ROD_DATUM_C_XY = (
    FCF_XY[0] + ROD_FRAME_SIZE[0] / 2.0,
    FCF_XY[1] - ROD_FRAME_SIZE[1] - 0.005 - DATUM_TAG_BOX,
)
# Short leftward hole leader exits E without tracing the tapered material edge.
ROD_CALLOUT_XY = (0.279, 0.115)
# The iso caption's top-left, under the iso's right half and right of the end
# view. Beside the end view (0.315, 0.150) it read as that
# view's label, 0.4 mm from HubLength's "+0.05" (r743-p1s-B2 render). Raised
# from 0.183: the r1 render put the strap thickness value on its baseline.
ISO_CAPTION_XY = (0.325, 0.189)
# View F's own label (Opus review #1020: unlabeled at a scale other than the
# sheet's): under the view, below the hub width's row.
RIGHT_CAPTION_XY = (0.052, 0.119)
# Its viewing arrow (Opus #1020 r1: an enlarged view off the 1:2 front's
# projection line reads as a removed view only with one): a letter note whose
# straight leader points -X at the rod tip's radial land, level with the
# land's midpoint, the tip just outside E's parent circle (right edge ~0.255
# at that level). The letter (centred on that level, ~0.181) sits over the
# 8.46 pin witness (~0.176) and left of the 8.46 dimension line (PIN_Y_TEXT_XY
# x): r4's leader, from right of that line, crossed its outside-arrow tail.
VIEW_ARROW_TEXT_X = 0.2625
VIEW_ARROW_TIP_GAP = 0.0035
VIEW_LETTER_HEIGHT = 0.005

# Re-express the part-owned one-sided height envelope as a normal profile zone:
# no second numeric tolerance lives in the drawing prose. The zero lower limit
# is pinned by the rocker contract; it is Ⓤ0 on the lower (inside-material)
# outline: the R816 arc, both tapers and both tip lands, between J and K. The
# amplitude bar's foot rides the top edge (its named mate, below the frame).
ARC_PROFILE_ZONE_MM = f"{TOP_EDGE_BAND[0]:g}"
ARC_PROFILE_OUTSIDE_MM = {
    "TopRadius": ARC_PROFILE_ZONE_MM,
    "BottomRadius": f"{TOP_EDGE_BAND[1]:g}",
}


def _zone_text(zone_mm: str) -> str:
    """A frame zone (mm) as the inch sheet prints it; a nil zone is a bare 0."""
    return inch_text(float(zone_mm), _FRAME_P) if float(zone_mm) else "0"


# The frames' own printed text, decimal inch; the zone is the spec's FCF row.
ARC_PROFILE_ZONE_TEXT = rocker.GEOMETRIC_TOLERANCES_IN["top edge surface profile"]
ARC_PROFILE_OUTSIDE_TEXT = {
    frame: _zone_text(zone) for frame, zone in ARC_PROFILE_OUTSIDE_MM.items()
}
ARC_PROFILE_DATUMS = ("A", "B", "C")

# The two frames control one nominal concentric arc system. Their material
# sides differ: top outside is +Y, bottom inside is +Y. A single shared frame
# would put one of the zones on the wrong side of its basic arc.
# Top-lefts. The top frame's below-frame mate row (1.1 mm under, 3.4 mm tall)
# clears the BASIC 8.00 box (top ~0.195), the frame's top the raised overall
# width line (~0.2185). View F holds the sheet's left band, so the lower frame
# sits under the strap's right half, between the D and E letters and above the
# 132.76 R816/TAPER row; its leader rises left of the frame to R816.
ARC_PROFILE_FRAME_XY = {
    "TopRadius": (0.130, 0.211),
    "BottomRadius": (0.207, 0.163),
}
ARC_PROFILE_PICK_X_MM = {"TopRadius": -130.0, "BottomRadius": 40.0}
# Both arcs keep the exterior radius-leader dressing.
ARC_RADIUS_NAMES = ("TopRadius", "BottomRadius")
# The lower frame's between symbol: its zone runs from the top-arc end at -X
# (J), down the land and taper, along R816, and up to the top-arc end at +X (K).
# Both letters point at their corners in the front view, the frame's view.
# Sheet offsets from the projected corner (v43 render): J sits left of the
# (292.51) witness. K's outboard side is view F's arrow letter: any K text right
# of its corner puts K's leader box over F's (main-r1 farm audit, 0.9 mm), so K
# sits above its corner, centred between the 133.07 and (292.51) extension
# lines (2.2 mm each side) and 2 mm above the E circle.
PROFILE_BETWEEN = ("J", "K")
BETWEEN_POINT_OFFSET = {"J": (-0.007, 0.002), "K": (-0.0039, 0.008)}
LAND_LABEL = "LAND"
# Sheet-layout clearance, NOT a manufacturing tolerance. SIDE_SMART may put
# the native junction on either frame edge; prove its rebuilt route, not a
# junction inferred from the requested top-left or a fixed frame width.
ARC_PROFILE_TEXT_CLEARANCE_M = 0.001

# General notes. The linked block renders ~4.1 mm a line, so its 18 lines run
# ~75 mm. Anchored by its top at y 0.082, the last two ran past the bottom
# border into the zone band (r743-p1s-B2 render). The block is now seated from
# its MEASURED extent: rendered bottom NOTES_BORDER_CLEARANCE above the
# sheet's drawable region, left edge on NOTES_LEFT. A block that then reaches
# NOTES_CEILING, reserved below the front-view callouts, fails the build.
NOTES_LEFT = 0.020
NOTES_BORDER_CLEARANCE = 0.003
NOTES_CEILING = 0.110
# The shorter (9-line) block starts farther above its seat: a fourth pass keeps
# a lagging native move (0.8 tracking) inside the settle tolerance.
NOTES_SEAT_PASSES = 4
NOTES_SEAT_SETTLE = 0.00005
# Below any note text height this sheet prints (the linked block pitches ~4.1).
NOTES_MIN_LINE_PITCH = 0.0025

# Tip-face midpoint (model mm): the top-arc endpoint pushed half the tip face
# outward along the end radius -- on the +Z land edge detail E's 5.59 measures.
_TIP_FACE_MID_X = TOP_END_X + (TIP_FACE / 2.0) * (TOP_END_X / R_TOP)
_TIP_FACE_MID_Y = TOP_END_Y - (TIP_FACE / 2.0) * math.cos(TOP_ARC_LEN / 2.0 / R_TOP)
_ROD_TIP_Y = TOP_END_Y - TIP_FACE * math.cos(_ALPHA_TOP)
_BOT_END_Y = CENTER_Y - math.sqrt(R_BOTTOM**2 - BOT_END_X**2)

# Full witnesses connect the overall row to the actual physical tips. The
# overall row and both A-to-land rows sit above the top-edge profile frame (top
# 0.211); the left taper vertex gets its own row from A, under the left half,
# below the R800/R816 texts.
# The longest dimension is outermost (#1440), above both BASIC land locators.
OVERALL_WIDTH_TEXT_XY = (FRONT_CENTER[0], 0.254)
# Right taper: its BASIC box at 0.132 printed 1.6 mm into Detail D's view box
# (r3 layout audit; D's top ~0.1309); at 0.137 it clears it.
# Left taper: its native BASIC box reaches y ~0.1498, not the request y.
# R800 therefore uses one below-text row above it; a two-row block would
# route the radius shoulder through this box (PR #1746 native-audit review).
TAPER_INTERSECTION_TEXT_XY = (0.219, 0.137)
LEFT_TAPER_TEXT_XY = (0.127, 0.142)
LAND_LOCATION_TEXT_XY = (0.219, 0.242)
# The J land's row mirrors the K land's about A (FRONT_CENTER x 0.180): both
# ends are dimensioned on the view, not left to a mirror note (main-r1 Opus).
LEFT_LAND_LOCATION_TEXT_XY = (0.141, 0.242)
PIN_X_TEXT_XY = (0.219, 0.197)
# Its dimension line runs at the text's x, right of the view-F letter.
PIN_Y_TEXT_XY = (0.2715, 0.162)
TAPER_WITNESS_LENGTH = 0.008



def _plane_between(
    start: tuple[float, float], end: tuple[float, float],
) -> PlanarFace:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    normal = (-dy / length, dx / length, 0.0)
    return PlanarFace(normal, normal[0] * start[0] + normal[1] * start[1])


def _rocker_points() -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    top = (rocker.TOP_END_X, rocker.TOP_END_Y)
    bottom = (rocker.BOT_END_X, rocker_interface.CENTER_Y - math.sqrt(rocker_interface.R_BOTTOM**2 - rocker.BOT_END_X**2))
    tip = (rocker.ROD_TIP_X, rocker.TOP_END_Y + rocker.TIP_FACE * (rocker.TOP_END_Y - rocker_interface.CENTER_Y) / rocker_interface.CURVE_RADIUS)
    return top, tip, bottom


_TOP, _TIP, _BOTTOM = _rocker_points()
_RIGHT = (_plane_between(_TOP, _TIP), _plane_between(_TIP, _BOTTOM))
_TIPS = tuple(PlanarFace((-face.normal[0], face.normal[1], 0.0), face.offset_mm) for face in _RIGHT)
_LAND_ANGLE = math.degrees(rocker._ALPHA_TOP)
_XY = tuple[float, float]


def _least_tip_land_mm() -> float:
    """The shortest tip land the J↔K and top-edge zones permit (+X; mirrored).

    The land is BASIC 5.59 inside the lower Ⓤ0 zone: its top end is on the top
    arc, whose zone lies wholly outside it (toward the arc centre), and its foot
    is on the taper. Each of the land and taper lines may lie anywhere in its
    zone, tilted too, so each line's two ends move independently between the
    zone's outside and inside limits, and the top arc between its own. The
    length is near-linear in those five offsets, so the least is at a vertex:
    the taper tilted in by the whole zone at the land's foot only (4.969).
    prechips 0.1.2's ``tilt_across`` takes this as the land_angle extent (C2).
    """
    zone, lower_outside = TOP_EDGE_BAND
    cx, cy = 0.0, rocker_interface.CENTER_Y
    mx, my = (_TOP[0] + _BOTTOM[0]) / 2.0, (_TOP[1] + _BOTTOM[1]) / 2.0

    def inward(start: _XY, end: _XY) -> _XY:
        dx, dy = end[0] - start[0], end[1] - start[1]
        nx, ny = -dy / math.hypot(dx, dy), dx / math.hypot(dx, dy)
        side = (mx - start[0]) * nx + (my - start[1]) * ny
        return (nx, ny) if side > 0.0 else (-nx, -ny)

    def moved(point: _XY, normal: _XY, by: float) -> _XY:
        return (point[0] + by * normal[0], point[1] + by * normal[1])

    land_in, taper_in = inward(_TOP, _TIP), inward(_TIP, _BOTTOM)
    lower = (-lower_outside, zone - lower_outside)  # into the material
    top_radii = (rocker_interface.CURVE_RADIUS - zone, rocker_interface.CURVE_RADIUS)  # wholly outside: centreward
    lengths = []
    for offsets in itertools.product(lower, repeat=4):
        p0, p1 = moved(_TOP, land_in, offsets[0]), moved(_TIP, land_in, offsets[1])
        q0, q1 = moved(_TIP, taper_in, offsets[2]), moved(_BOTTOM, taper_in, offsets[3])
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        ex, ey = q1[0] - q0[0], q1[1] - q0[1]
        s = ((q0[0] - p0[0]) * ey - (q0[1] - p0[1]) * ex) / (dx * ey - dy * ex)
        foot = (p0[0] + s * dx, p0[1] + s * dy)
        fx, fy = p0[0] - cx, p0[1] - cy
        a, b = dx**2 + dy**2, 2.0 * (fx * dx + fy * dy)
        for radius in top_radii:
            root = math.sqrt(b * b - 4.0 * a * (fx**2 + fy**2 - radius**2))
            u = min(((-b + root) / (2.0 * a), (-b - root) / (2.0 * a)), key=abs)
            lengths.append(math.dist((p0[0] + u * dx, p0[1] + u * dy), foot))
    return min(lengths)


TIP_LAND_LEAST_MM = math.floor(_least_tip_land_mm() * 1e3) / 1e3  # 4.969

# A printed profile frame as prechips 0.1.2 reads it (docs/features.md, Surface
# profiles): t, U and the datum frame are the frame's own printed strings. The
# frame's material sides (ARC_PROFILE_FRAME_XY) give each governed BASIC's sense.
_ZONE_SOURCES = ("TOP_EDGE_BAND", ("draw_ch_rocker_arm", "ARC_PROFILE_ZONE_MM"), ("draw_ch_rocker_arm", "_add_arc_profiles"))


def _profile_zone(frame: str, governs: dict[str, Any], governs_sources: tuple[Any, ...]) -> dict[str, tuple[Any, tuple[Any, ...]]]:
    """``frame`` keys ARC_PROFILE_OUTSIDE_MM; ``governs`` names this feature's own BASICs."""
    return {
        "surface_profile": (float(ARC_PROFILE_ZONE_MM), _ZONE_SOURCES),
        "surface_profile_u": (float(ARC_PROFILE_OUTSIDE_MM[frame]), (*_ZONE_SOURCES, ("draw_ch_rocker_arm", "ARC_PROFILE_OUTSIDE_MM"))),
        "surface_profile_datums": (ARC_PROFILE_DATUMS, (("draw_ch_rocker_arm", "ARC_PROFILE_DATUMS"), ("draw_ch_rocker_arm", "_add_arc_profiles"))),
        "surface_profile_governs": (governs, (("draw_ch_rocker_arm", "ARC_PROFILE_FRAME_XY"), *governs_sources)),
    }


# The J↔K zone covers both lands, whose faces stay with their own features: one
# STEP face carries one feature name (_export_feature_faces). So each land
# declares the lower frame's identical zone (profile_outer's) and governs only
# its own BASICs; no requirement is read through two zones.
for _name, _sign, _face in (("tip_land_pos_x", 1, _RIGHT[0]), ("tip_land_neg_x", -1, _TIPS[0])):
    requirement(
        _name, kind="face", faces=(_face,), requirements=("land_angle_deg", "station", "surface_profile"), fields={
            # BASIC with no acceptance of its own: the J↔K zone bounds the land.
            "tip_land": (rocker.TIP_FACE, ("TIP_FACE", ("draw_ch_rocker_arm", "_dress_detail_dimensions"))),
            "land_angle_deg": (round(_LAND_ANGLE, _P), ("_ALPHA_TOP", ("draw_ch_rocker_arm", "_dress_detail_dimensions"))),
            "land_angle_nominal_deg": (_LAND_ANGLE, ("_ALPHA_TOP",)),
            "dimension_type": ("basic", (("draw_ch_rocker_arm", "_dress_detail_dimensions"),)),
            "radial_tip_end": ([_sign * _TIP[0], _TIP[1]], ("ROD_TIP_X", "TOP_END_Y", "TIP_FACE", ("_rocker_interface", "CURVE_RADIUS"), ("_rocker_interface", "CENTER_Y"))),
            "top_edge_feature": ("top_edge", (("draw_ch_rocker_arm", "_dress_detail_dimensions"),)),
            # Each land's own BASIC LAND row from A (the J row, main-r1 Opus).
            "station": (rocker.ROD_TIP_X, ("ROD_TIP_X", ("draw_ch_rocker_arm", "_add_rocker_outline_dimensions"))),
            "station_nominal": (rocker.ROD_TIP_X, ("ROD_TIP_X",)),
            # The land angle is read across the shortest land the zones allow.
            # The station is read along X, off the land's normal by the land
            # angle; material added on the land moves it outward.
            **_profile_zone("BottomRadius", {
                "land_angle_deg": {"tilt_across": TIP_LAND_LEAST_MM},
                "station": {"sense": "increases", "obliquity_deg": _LAND_ANGLE},
            }, (("draw_ch_rocker_arm", "TIP_LAND_LEAST_MM"), ("draw_ch_rocker_arm", "_least_tip_land_mm"), "_ALPHA_TOP")),
        }, precision={"tip_land": _P, "land_angle_deg": _P, "station": _P},
    )

part_metadata(datums={
    "C": ({"feature": "rod_hole", "surface": "#47 rod-pin hole"}, (("draw_ch_rocker_arm", "build"),)),
})


def _project(adapter: Any, view: Any, points: Any, *, label: str) -> list[tuple[float, float]]:
    """Native geometry barrier precedes every detail-centre/attachment projection."""
    _early_bound(view, "IView").UpdateViewDisplayGeometry()  # VT_VOID
    projected = model_points_in_view(adapter, view, points, label=label)
    if (len(projected) != len(points)
            or any(len(xy) != 2 or not all(math.isfinite(v) for v in xy) for xy in projected)):
        raise RuntimeError(f"{label}: invalid native projected points: {projected!r}")
    return projected


def _outline(view: Any, *, label: str) -> tuple[float, float, float, float]:
    """Native view extent, which is not the detail's bare crop-circle box."""
    outline = tuple(float(v) for v in (_early_bound(view, "IView").GetOutline() or ()))
    if (len(outline) != 4 or not all(math.isfinite(v) for v in outline)
            or outline[0] >= outline[2] or outline[1] >= outline[3]):
        raise RuntimeError(f"{label} has invalid native outline: {outline!r}")
    return outline


# R12 native caption air read 22.761 -> 3.221 -> 3.221 -> 2.745 mm:
# GetExtent moved by 0.476569 mm, one pixel at the logged 2.098 px/mm.
# Aim at 4 mm so that readback quantization cannot chase the 3 mm hard guard.
# Half the extra 1 mm permits one-pixel ink settling, not less required air.
_DETAIL_CAPTION_TARGET_AIR_M = 0.004
_DETAIL_CAPTION_SETTLE_M = (_DETAIL_CAPTION_TARGET_AIR_M - 0.003) / 2.0
# Leave the native land-angle witness clear of Detail E's linked caption.
_END_CAPTION_OFFSET_X_M = -0.008


def _detail_fence(label: str) -> tuple[tuple[float, float, float], float]:
    """Source model point/radius for a cosmetic, recipe-private detail fence."""
    if label == "D":
        return (0.0, PIVOT_MID_Y / 1000.0, 0.0), HUB_DIA / 2.0 + PIVOT_HOLE_DIA / 4.0
    if label != "E":
        raise RuntimeError(f"unknown rocker detail {label!r}")
    centre_mm = ((BOT_END_X + ROD_TIP_X) / 2.0, (_BOT_END_Y + TOP_END_Y) / 2.0)
    radius_mm = max(
        math.dist(centre_mm, point)
        for point in ((BOT_END_X, _BOT_END_Y), (ROD_TIP_X, _ROD_TIP_Y),
                      (TOP_END_X, TOP_END_Y))
    )
    radius_mm = max(
        radius_mm, math.dist(centre_mm, (ROD_HOLE_X, ROD_HOLE_Y)) + _ROD_HOLE_DIA / 2.0,
    ) + 0.5  # Cosmetic crop air, not a feature dimension.
    return (centre_mm[0] / 1000.0, centre_mm[1] / 1000.0, 0.0), radius_mm


def _view_scale_ratio(view: Any, *, label: str) -> tuple[float, float]:
    ratio = tuple(float(v) for v in (_early_bound(view, "IView").ScaleRatio or ()))
    if len(ratio) != 2 or not all(math.isfinite(v) and v > 0.0 for v in ratio):
        raise RuntimeError(f"{label}: invalid native ScaleRatio={ratio!r}")
    return ratio


def _detail_crop(adapter: Any, view: Any, *, label: str) -> tuple[float, float, float, float]:
    """Shared persisted crop, checked against every independent rocker invariant."""
    view = _early_bound(view, "IView")
    readback = read_circular_detail_crop(adapter, view, label=f"detail {label}")
    bbox = readback.outline
    detail_circle = _early_bound(view.GetDetail(), "IDetailCircle")
    if detail_circle is None:
        raise RuntimeError(f"detail {label}: missing persisted detail circle")
    # Full/jagged outline accessors are valid only when NoOutline is False.
    # D uses the cone-gear-shaft non-feature boundary convention; E stays full.
    no_outline = detail_circle.NoOutline
    required_no_outline = DETAIL_NO_OUTLINE[label]
    if no_outline is not required_no_outline:
        raise RuntimeError(f"detail {label}: actual circle NoOutline={no_outline!r}, "
                           f"required={required_no_outline!r}, native_view_bbox={bbox}")
    actual_flags = (detail_circle.GetLabel(), int(detail_circle.GetDisplay()),
                    int(detail_circle.GetStyle()), no_outline)
    required_flags = (label, 1, DETAIL_STYLE[label], required_no_outline)
    if not no_outline:
        actual_flags += (detail_circle.JaggedOutline, detail_circle.HasFullOutline())
        required_flags += (False, True)
    if actual_flags != required_flags:
        raise RuntimeError(f"detail {label}: actual circle label/display/style/outline flags={actual_flags!r}, "
                           f"required={required_flags!r}, native_view_bbox={bbox}")
    if readback.label != label:
        raise RuntimeError(f"detail {label}: persisted native circle label changed to {readback.label!r}")
    parent = readback.parent
    parent_centre = readback.parent_centre
    parent_radius = readback.parent_radius
    radius_y = readback.parent_radius_y
    centre, radius_mm = _detail_fence(label)
    parent_ratio = readback.parent_ratio
    parent_scale = parent_ratio[0] / parent_ratio[1]
    expected_parent_radius = radius_mm / 1000.0 * parent_scale
    expected_parent_centre, projected_rim = _project(
        adapter, parent, (centre, (centre[0] + radius_mm / 1000.0, centre[1], centre[2])),
        label=f"detail {label} independent parent fence",
    )
    projected_radius = math.dist(expected_parent_centre, projected_rim)
    context = (f"detail {label}: inverse_parent_sheet_centre={parent_centre}, "
               f"required_parent_sheet_centre={expected_parent_centre}, "
               f"actual_parent_sheet_radius_mm={parent_radius * 1000.0:.6f}, radius_y_mm={radius_y * 1000.0:.6f}, "
               f"projected_parent_radius_mm={projected_radius * 1000.0:.6f}, "
               f"required_parent_radius_mm={expected_parent_radius * 1000.0:.6f}, parent_scale={parent_ratio}, "
               f"geometry_tolerance_mm={DETAIL_GEOMETRY_TOL_M * 1000.0:.6f}, native_view_bbox={bbox}")
    _telemetry.info(context)
    if (math.dist(parent_centre, expected_parent_centre) > DETAIL_GEOMETRY_TOL_M
            or abs(parent_radius - expected_parent_radius) > DETAIL_GEOMETRY_TOL_M
            or abs(projected_radius - expected_parent_radius) > DETAIL_GEOMETRY_TOL_M
            or abs(radius_y - parent_radius) > DETAIL_GEOMETRY_TOL_M):
        raise RuntimeError(f"{context}: persisted native circle geometry/frame/parent scale mismatch")
    ratio = readback.detail_ratio
    expected_ratio = {"D": HUB_SCALE, "E": END_SCALE}[label]
    scale = ratio[0] / ratio[1]
    if (not math.isclose(scale, expected_ratio[0] / expected_ratio[1], abs_tol=1e-10)
            or view.UseParentScale is not False or int(view.UseSheetScale) != 0):
        raise RuntimeError(f"{context}: native detail scale/independence changed: {ratio!r}")
    (physical,) = _project(adapter, view, (centre,), label=f"detail {label} actual physical centre")
    magnification = scale / parent_scale
    # Independent R18-proven formula validates the NEW parent view inverse hop
    # in both directions, rather than trusting a generic box that merely fits.
    crop_centre = tuple(physical[i] + (parent_centre[i] - expected_parent_centre[i]) * magnification
                        for i in range(2))
    radius = parent_radius * magnification
    legacy_crop = (crop_centre[0] - radius, crop_centre[1] - radius,
                   crop_centre[0] + radius, crop_centre[1] + radius)
    deltas = tuple(actual - expected for actual, expected in zip(readback.crop, legacy_crop, strict=True))
    _telemetry.info(f"{context}, actual_detail_projected_centre={physical}, native_detail_scale={ratio}, "
                    f"shared_crop_box={readback.crop}, independent_legacy_crop_box={legacy_crop}, "
                    f"shared_minus_legacy_m={deltas}, native_view_bbox={bbox}")
    if any(abs(delta) > DETAIL_GEOMETRY_TOL_M for delta in deltas):
        raise RuntimeError(f"{context}: shared/independent legacy crop mismatch; shared_crop_box={readback.crop}, "
                           f"independent_legacy_crop_box={legacy_crop}, shared_minus_legacy_m={deltas}")
    return readback.crop


def _sheet_points_in_sketch(
    adapter: Any, view: Any, sheet_points: Any, *, label: str, kind: str, owner: str
) -> list[tuple[float, float, float]]:
    """Sheet points in ``view``'s own drawing-sketch frame (ModelToSketchTransform)."""
    sketch = _early_bound(view.GetSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError(f"{label}: {owner} has no native drawing sketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    if transform is None or utility is None:
        raise RuntimeError(f"{label}: missing native sketch transform or math utility")
    mapped = []
    for x, y in sheet_points:
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        if point is None:
            raise RuntimeError(f"{label}: cannot create native {kind} point")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        if projected is None:
            raise RuntimeError(f"{label}: cannot map native {kind} point to sketch")
        coordinates = tuple(float(v) for v in (projected.ArrayData or ()))
        if len(coordinates) != 3 or not all(math.isfinite(v) for v in coordinates):
            raise RuntimeError(
                f"{label}: invalid native sketch {kind} point={coordinates!r}"
            )
        mapped.append(coordinates)
    return mapped


def _create_detail(
    adapter: Any, parent: Any, *, centre: tuple[float, float, float],
    radius_mm: float, target: tuple[float, float], scale: tuple[float, float], label: str,
) -> Any:
    """Rocker-private cone-gear-shaft native circle/barrier/settling pattern."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent, "IView")
    if drawing.ActivateView(view_name(adapter, parent)) is not True:
        raise RuntimeError(f"detail {label}: cannot activate parent")
    draw.ClearSelection2(True)
    rim = (centre[0] + radius_mm / 1000.0, centre[1], centre[2])
    sheet_points = _project(adapter, parent, (centre, rim), label=f"detail {label} fence")
    mapped = _sheet_points_in_sketch(
        adapter,
        parent,
        sheet_points,
        label=f"detail {label}",
        kind="fence",
        owner="parent",
    )
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*mapped[0], *mapped[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError(f"detail {label}: native fence creation failed")
    actual_centre, actual_radius = native_circle_geometry(circle, label=f"detail {label} created fence")
    asked_radius = math.dist(mapped[0], mapped[1])
    parent_ratio = _view_scale_ratio(parent, label=f"detail {label} parent")
    parent_radius = radius_mm / 1000.0 * parent_ratio[0] / parent_ratio[1]
    projected_radius = math.dist(*sheet_points)
    if parent_radius <= 0.0 or asked_radius <= 0.0:
        raise RuntimeError(f"detail {label}: invalid requested native fence radius")
    tolerance = DETAIL_GEOMETRY_TOL_M * asked_radius / parent_radius
    context = (f"detail {label} created fence: requested_sketch_centre={mapped[0]}, "
               f"actual_sketch_centre={actual_centre}, requested_sketch_radius={asked_radius}, "
               f"actual_sketch_radius={actual_radius}, geometry_tolerance_sketch_units={tolerance}, "
               f"projected_parent_sheet_radius={projected_radius}, required_parent_sheet_radius={parent_radius}, "
               f"native_parent_scale={parent_ratio}")
    _telemetry.info(context)
    if (math.dist(actual_centre, mapped[0]) > tolerance
            or abs(actual_radius - asked_radius) > tolerance
            or abs(projected_radius - parent_radius) > DETAIL_GEOMETRY_TOL_M):
        raise RuntimeError(f"{context}: created native circle geometry or parent projection scale mismatch")
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = _early_bound(selection.CreateSelectData(), "ISelectData")
    data.View = parent
    if _early_bound(circle, "ISketchSegment").Select4(False, data) is not True:
        raise RuntimeError(f"detail {label}: cannot select parent fence")
    no_outline = DETAIL_NO_OUTLINE[label]
    style = DETAIL_STYLE[label]
    native = drawing.CreateDetailViewAt4(
        *target, 0.0, style, *scale, label, 1, not no_outline, False, no_outline, 5,
    )
    draw.ClearSelection2(True)
    if native is None:
        raise RuntimeError(f"detail {label}: CreateDetailViewAt4 returned no view")
    detail = _early_bound(native, "IView")
    # IDetailCircle::SetStyle is the documented setter; _detail_crop reads
    # the persisted style back on every settling pass.
    fence = _early_bound(detail.GetDetail(), "IDetailCircle")
    if fence is None or (int(fence.GetStyle()) != style and fence.SetStyle(style) is not True):
        raise RuntimeError(f"detail {label}: native detail circle refused style {style}")
    detail.UseParentScale = False
    detail.UseSheetScale = 0
    detail.ScaleRatio = double_array(list(scale))
    set_hidden_lines_removed(adapter, detail)
    rebuild_drawing(adapter, label=f"create detail {label}")
    base = detail.GetBaseView()
    if base is None or int(adapter.swApp.IsSame(base, parent)) != 1:
        raise RuntimeError(f"detail {label}: native parent link is not the front")
    for attempt in range(4):
        ratio = _view_scale_ratio(detail, label=f"detail {label}")
        if (not math.isclose(ratio[0] / ratio[1], scale[0] / scale[1], abs_tol=1e-10)
                or detail.UseParentScale is not False or int(detail.UseSheetScale) != 0):
            raise RuntimeError(f"detail {label}: native scale is {ratio}, not {scale}")
        crop = _detail_crop(adapter, detail, label=label)
        outline = _outline(detail, label=f"detail {label} view bbox")
        landed = ((crop[0] + crop[2]) / 2.0, (crop[1] + crop[3]) / 2.0)
        (physical,) = _project(adapter, detail, (centre,), label=f"detail {label} centre {attempt}")
        _telemetry.info(f"detail {label}: pass={attempt}, native_view_bbox={outline}, actual_crop={crop}, physical_centre={physical}, scale={ratio}")
        if math.dist(physical, target) <= DETAIL_GEOMETRY_TOL_M:
            if math.dist(landed, target) > DETAIL_GEOMETRY_TOL_M:
                raise RuntimeError(f"detail {label}: settled physical centre={physical} but actual crop centre={landed}, "
                                   f"required_centre={target}, tolerance_m={DETAIL_GEOMETRY_TOL_M}, "
                                   f"actual_crop={crop}, native_view_bbox={outline}")
            break
        anchor = tuple(float(v) for v in (detail.Position or ()))
        if len(anchor) != 2 or not all(math.isfinite(v) for v in anchor):
            raise RuntimeError(f"detail {label}: invalid Position={anchor!r}")
        move = [anchor[i] + target[i] - physical[i] for i in range(2)]
        if detail.SetViewPosition(double_array(move), False) is not True:
            raise RuntimeError(f"detail {label}: native position refused")
        rebuild_drawing(adapter, label=f"settle detail {label}")
    else:
        raise RuntimeError(f"detail {label}: unsettled native crop/physical centre: view_bbox={outline}, crop={crop}, projected={physical}, target={target}")
    return detail


def _place_detail_letters(adapter: Any, front: Any) -> None:
    circles = tuple(_early_bound(front, "IView").GetDetailCircles() or ())
    labels = [_early_bound(circle, "IDetailCircle").GetLabel() for circle in circles]
    if len(circles) != 2 or sorted(labels) != ["D", "E"]:
        raise RuntimeError(f"rocker requires exactly D/E native parent circles, got {labels!r}")
    for label, xy in DETAIL_LETTER_XY.items():
        circle = _early_bound(circles[labels.index(label)], "IDetailCircle")
        circle.SetLabelPosition(*xy)  # VT_VOID; getter returns two out doubles
        rebuild_drawing(adapter, label=f"place detail {label} parent letter")
        actual = tuple(float(v) for v in circle.GetLabelPosition())
        if len(actual) != 2 or not all(math.isfinite(v) for v in actual) or math.dist(actual, xy) > 1e-8:
            raise RuntimeError(f"detail {label}: native letter stayed at {actual!r}, requested {xy}")


def _pin_sheet_scale(adapter: Any, sheet: Any) -> None:
    sheet = _early_bound(sheet, "ISheet")
    if sheet.SetScale(*SHEET_SCALE, False, False) is not True:
        raise RuntimeError("cannot pin rocker sheet scale before native captions")
    properties = tuple(float(v) for v in (sheet.GetProperties2() or ()))
    if len(properties) < 4 or tuple(properties[2:4]) != SHEET_SCALE:
        raise RuntimeError(f"rocker sheet scale did not persist: {properties!r}")


def _title_block_top(adapter: Any, sheet: Any) -> float:
    """Read the actual template's top rule; registry coordinates identify its span."""
    sketch = _early_bound(_early_bound(sheet, "ISheet").GetTemplateSketch(), "ISketch")
    if sketch is None:
        raise RuntimeError("detail E: cannot read native title-block sketch")
    template = DRAWING_TEMPLATES[SPEC.layout]
    tops = []
    for raw in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw, "ISketchSegment")
        if int(segment.GetType()) != 0:  # swSketchLINE
            continue
        line = _early_bound(raw, "ISketchLine")
        a = _early_bound(line.GetStartPoint2(), "ISketchPoint")
        b = _early_bound(line.GetEndPoint2(), "ISketchPoint")
        if a is None or b is None:
            raise RuntimeError("detail E: native title-block rule endpoint unavailable")
        values = (float(a.X), float(a.Y), float(b.X), float(b.Y))
        if not all(math.isfinite(v) for v in values):
            raise RuntimeError("detail E: invalid native title-block rule")
        x0, x1 = sorted((values[0], values[2]))
        if (abs(values[1] - values[3]) < 1e-8
                and abs(x0 - template.title_block_left_m) < 0.001
                and x1 > template.width_m - 0.020
                and 0.0 < values[1] < NOTES_CEILING):
            tops.append(values[1])
    if not tops:
        raise RuntimeError("detail E: native title-block top rule could not be measured")
    return max(tops)


def _record_detail_caption(adapter: Any, view: Any, sheet: Any, *, label: str, stage: str) -> None:
    """Read-only R14 probe; decoder boxes are estimates, NEVER a guard fallback.

    GetExtent documents a note box, not individual printed glyph bounds. Keep
    its native six coordinates separate from DisplayData's native fragments
    and the existing layout decoder's estimated text boxes until a failure
    sheet shows what actually printed. Refused reads remain explicit errors.
    """
    report: dict[str, Any] = {"label": label, "stage": stage}
    reader = _Reader(adapter)
    try:
        bound_view = reader.bind(view, "IView")
        raw_notes = reader.call(lambda: bound_view.GetNotes())
        notes = tuple(raw_notes or ())
        report["native_note_count"] = (
            len(notes) if not {"GetNotes", "bind IView"}.intersection(reader.errors) else None
        )
        report["native_title_rule_top_m"] = reader.need(lambda: _title_block_top(adapter, sheet))
        report["notes"] = []
        for raw_note in notes:
            note = reader.bind(raw_note, "INote")
            text = reader.need(lambda: note.GetText())
            lines = (text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
                     if type(text) is str and text else [] if text == "" else None)
            entry: dict[str, Any] = {
                "native_property_linked_text": reader.need(lambda: note.PropertyLinkedText),
                "native_get_text": text,
                "resolved_lines": lines,
                "resolved_line_count": len(lines) if lines is not None else None,
                "native_note_get_extent": reader.need(lambda: note.GetExtent()),
                "native_note_get_height": reader.need(lambda: note.GetHeight()),
                "native_note_get_height_in_points": reader.need(lambda: note.GetHeightInPoints()),
                "native_has_multiple_fonts": reader.need(lambda: note.HasMultipleFonts),
            }
            report["notes"].append(entry)
            annotation = reader.bind(reader.need(lambda: note.GetAnnotation()), "IAnnotation")
            count = reader.need(lambda: annotation.GetTextFormatCount())
            entry["native_text_format_count"] = count
            formats = []
            entry["native_text_formats"] = formats
            for index in range(count if type(count) is int and count >= 0 else 0):
                text_format = reader.bind(
                    reader.need(lambda i=index: annotation.GetTextFormat(i)), "ITextFormat"
                )
                formats.append({
                    "index": index,
                    "use_doc_text_format": reader.need(lambda i=index: annotation.GetUseDocTextFormat(i)),
                    "char_height_m": reader.need(lambda: text_format.CharHeight),
                    "char_height_pts": reader.need(lambda: text_format.CharHeightInPts),
                    "is_height_specified_in_pts": reader.need(lambda: text_format.IsHeightSpecifiedInPts()),
                    "type_face_name": reader.need(lambda: text_format.TypeFaceName),
                    "line_spacing": reader.need(lambda: text_format.LineSpacing),
                })
            data = reader.need(lambda: annotation.GetDisplayData())
            before_display = dict(reader.errors)
            display = _dump_display(reader, data)
            # Font/spacing are optional to the shared audit, but native fields
            # in THIS probe must not turn a None answer into "" or zero.
            bound_data = reader.bind(data, "IDisplayData")
            for index, fragment in enumerate(display.get("texts", [])):
                fragment["font"] = reader.need(lambda i=index: bound_data.GetTextFontAtIndex(i))
                fragment["ls"] = reader.need(lambda i=index: bound_data.GetTextLineSpacingAtIndex(i))
            display_errors = {
                name: count - before_display.get(name, 0)
                for name, count in reader.errors.items() if count > before_display.get(name, 0)
            }
            # The shared tolerant reader uses audit defaults after a refusal.
            # Do not present those defaults as native observations in this probe.
            refused_fields = {
                "GetTextAtIndex": "t", "GetTextPositionAtIndex": "pos",
                "GetTextHeightAtIndex": "h", "GetTextRefPositionAtIndex": "ref",
                "GetTextAngleAtIndex": "ang", "GetTextFontAtIndex": "font",
                "GetTextLineSpacingAtIndex": "ls",
            }
            fragments = display.get("texts", [])
            for accessor, field in refused_fields.items():
                if accessor in display_errors:
                    for fragment in fragments:
                        fragment[field] = None
            entry["native_display_data"] = display
            entry["native_display_read_errors"] = display_errors
            entry["display_fragment_count"] = (
                len(fragments) if data is not None and not {
                    "GetTextCount", "bind IDisplayData"
                }.intersection(display_errors) else None
            )
            entry["native_display_fragment_positions"] = [fragment["pos"] for fragment in fragments]
            entry["native_display_position_basis"] = "offsets from DisplayData origin per API; not measured sheet glyph bounds"
            # Deliberately omit note.GetExtent from the decoder input: otherwise
            # the free-note branch would just echo it as an "exact" text box.
            record = {"type": 6, "name": f"detail {label} caption", "display": display}
            advance = calibrate_sheet_advance((record,)) if not display_errors else None
            geometry = (annotation_geometry(record, owner=f"detail {label}", advance=advance)
                        if advance is not None else None)
            boxes = list(geometry.text_boxes) if geometry is not None else []
            estimated = union_boxes(boxes)
            entry["display_decoder_estimate"] = {
                "coordinate_basis": "existing decoder interpretation of native DisplayData; not printed glyph ink",
                "advance_ratio": advance,
                "text_boxes_m": [(box.xmin, box.ymin, box.xmax, box.ymax) for box in boxes],
                "extent_m": ((estimated.xmin, estimated.ymin, estimated.xmax, estimated.ymax)
                             if estimated is not None else None),
            }
    except Exception as exc:  # noqa: BLE001 - instrumentation cannot replace the guard
        report["diagnostic_error"] = f"{type(exc).__name__}: {exc}"
    report["native_read_errors"] = reader.take_errors()
    with contextlib.suppress(Exception):
        _telemetry.info(f"detail {label} caption native diagnostics: {json.dumps(report, default=str, sort_keys=True)}")

# The shared DisplayData audit records heights to 0.1 um. Permit that native
# numeric quantization, not a pixel-sized or point-sized font mismatch.
_NOTE_HEIGHT_READBACK_TOL_M = 1e-7
_CAPTION_FIELDS = ("<VLNAME>", "<VLLABEL>", "<VLSCALE>", "<VLSCALEV>")
# Document Properties > Views and > Views > Detail scope these font families.
# Values are installed SW2026 swconst 34.4.0.78 enum literals (no COM activation),
# not application preferences or an assumed shared option-0 detail slot.
_DETAIL_DOCUMENT_TEXT_FORMATS = (
    ("swDetailingViewTextFormat", 18, 0),  # swDetailingNoOptionSpecified
    ("swDetailingDetailTextFormat", 3, 301),  # swDetailingDetailView
    ("swDetailingDetailView_NameTextFormat", 42, 301),
    ("swDetailingDetailView_LabelTextFormat", 43, 301),
    ("swDetailingDetailView_ScaleTextFormat", 44, 301),
    ("swDetailingDetailView_DelimiterTextFormat", 45, 301),
)


def _caption_fields(note: Any, *, label: str) -> tuple[str, ...]:
    linked = note.PropertyLinkedText
    if type(linked) is not str:
        raise RuntimeError(f"detail {label}: unavailable native caption links")
    fields = tuple(re.findall(r"<VL[^>]*>", linked))
    if fields != _CAPTION_FIELDS:
        raise RuntimeError(f"detail {label}: native caption field identities/order/counts={fields!r}")
    return fields


def _native_note_fragments(note: Any, *, label: str) -> tuple[tuple[str, float, str], ...]:
    """Strict native text/height/font reads, never tolerant decoder defaults."""
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"{label}: missing native annotation")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    if data is None:
        raise RuntimeError(f"{label}: missing native DisplayData")
    count = data.GetTextCount()
    if type(count) is not int or count <= 0:
        raise RuntimeError(f"{label}: missing/invalid native text fragment count={count!r}")
    fragments = []
    for index in range(count):
        text = data.GetTextAtIndex(index)
        height = data.GetTextHeightAtIndex(index)
        font = data.GetTextFontAtIndex(index)
        if (type(text) is not str or type(height) not in (float, int)
                or not math.isfinite(height) or height <= 0.0
                or type(font) is not str or not font.strip()):
            raise RuntimeError(f"{label}: invalid native fragment {index}: {(text, height, font)!r}")
        fragments.append((text, float(height), font))
    if not any(text.strip() for text, _height, _font in fragments):
        raise RuntimeError(f"{label}: native DisplayData has no displayed text fragments")
    return tuple(fragments)


def _native_text_format_authority(text_format: Any, *, label: str) -> dict[str, Any]:
    if text_format is None:
        raise RuntimeError(f"{label}: missing native text format")
    text_format = _early_bound(text_format, "ITextFormat")
    in_points = text_format.IsHeightSpecifiedInPts()
    if type(in_points) is not bool:
        raise RuntimeError(f"{label}: unavailable native height authority={in_points!r}")
    return {
        "is_height_specified_in_pts": in_points,
        "char_height_m": text_format.CharHeight,
        "char_height_pts": text_format.CharHeightInPts,
        "font": text_format.TypeFaceName,
    }


def _native_font_authority(text_format: Any, use_doc: Any, *, label: str) -> dict[str, Any]:
    if type(use_doc) is not bool:
        raise RuntimeError(f"{label}: missing native font/format authority")
    return {"use_doc": use_doc, **_native_text_format_authority(text_format, label=label)}


def _require_sourced_font(authority: dict[str, Any], height: float, font: str, *, label: str) -> None:
    actual = authority["char_height_m"]
    if (authority["is_height_specified_in_pts"] is not False
            or type(actual) not in (int, float) or not math.isfinite(actual) or actual <= 0.0
            or abs(actual - height) > _NOTE_HEIGHT_READBACK_TOL_M
            or type(authority["font"]) is not str or authority["font"] != font):
        raise RuntimeError(f"{label}: native source-font readback mismatch: source_height_m={height}, source_font={font!r}, authority={authority!r}")


def _ordinary_note_font(adapter: Any, note: Any) -> tuple[Any, float, str, dict[str, Any], tuple[Any, ...]]:
    """Use the existing normal note's unmodified format, proved by native ink."""
    adapter.currentModel.GraphicsRedraw2()  # VT_VOID; native reads carry signal.
    note = _early_bound(note, "INote")
    if note is None:
        raise RuntimeError("Manufacturing Notes: missing native source note")
    fragments = _native_note_fragments(note, label="Manufacturing Notes")
    height, font = fragments[0][1:]
    if any(abs(actual - height) > _NOTE_HEIGHT_READBACK_TOL_M or actual_font != font
           for _text, actual, actual_font in fragments):
        raise RuntimeError(f"Manufacturing Notes: mixed native source fragments={fragments!r}")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
    authority = _native_font_authority(
        text_format, annotation.GetUseDocTextFormat(0), label="Manufacturing Notes",
    )
    _require_sourced_font(authority, height, font, label="Manufacturing Notes")
    _telemetry.info(
        f"Manufacturing Notes native font source: font_authority={authority!r}, "
        f"display_fragments={fragments!r}, source=existing ITextFormat verified against IDisplayData"
    )
    return text_format, height, font, authority, fragments


def _pin_detail_document_font(adapter: Any, text_format: Any, height: float, font: str) -> Any:
    """Pin the inherited source, never the native caption's rich-text runs."""
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    if extension is None:
        raise RuntimeError("detail styles: missing native document extension")
    for name, preference, option in _DETAIL_DOCUMENT_TEXT_FORMATS:
        if extension.SetUserPreferenceTextFormat(preference, option, text_format) is not True:
            raise RuntimeError(f"detail styles: document font setter refused for {name}, option={option}")
        authority = _native_text_format_authority(
            extension.GetUserPreferenceTextFormat(preference, option), label=f"document {name}",
        )
        _require_sourced_font(authority, height, font, label=f"document {name}, option={option}")
        _telemetry.info(f"detail styles: document font pinned: preference={name}, option={option}, authority={authority!r}")
    return extension


def _require_detail_document_fonts(extension: Any, height: float, font: str) -> None:
    for name, preference, option in _DETAIL_DOCUMENT_TEXT_FORMATS:
        authority = _native_text_format_authority(
            extension.GetUserPreferenceTextFormat(preference, option), label=f"document {name} after rebuild",
        )
        _require_sourced_font(authority, height, font, label=f"document {name} after rebuild, option={option}")


def _caption_view_state(adapter: Any, view: Any, front: Any, *, label: str) -> tuple[Any, ...]:
    parent = view.GetBaseView()
    if parent is None or int(adapter.swApp.IsSame(parent, front)) != 1:
        raise RuntimeError(f"detail {label}: native caption view lost front ownership")
    position = tuple(float(value) for value in (view.Position or ()))
    if len(position) != 2 or not all(math.isfinite(value) for value in position):
        raise RuntimeError(f"detail {label}: invalid native view position={position!r}")
    return (position, _view_scale_ratio(view, label=f"detail {label} caption style"),
            view.UseParentScale, view.UseSheetScale)


def _caption_style_state(adapter: Any, view: Any, front: Any, *, label: str) -> dict[str, Any]:
    view = _early_bound(view, "IView")
    notes = tuple(view.GetNotes() or ())
    if len(notes) != 1:
        raise RuntimeError(f"detail {label}: expected one native caption, got {len(notes)}")
    note = _early_bound(notes[0], "INote")
    fields = _caption_fields(note, label=label)
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"detail {label}: missing native caption annotation")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    if len(position) != 3 or not all(math.isfinite(value) for value in position):
        raise RuntimeError(f"detail {label}: invalid native caption position={position!r}")
    return {
        "note": note, "fields": fields, "linked": note.PropertyLinkedText,
        "view": _caption_view_state(adapter, view, front, label=label),
        "position": position,
        "fragments": _native_note_fragments(note, label=f"detail {label} caption"),
    }


def _require_detail_caption_style(
    adapter: Any, view: Any, front: Any, height: float, font: str,
    before: dict[str, Any], *, label: str,
) -> None:
    """Verify inherited native caption ink without editing its linked string."""
    after = _caption_style_state(adapter, view, front, label=label)
    note = after["note"]
    if (int(adapter.swApp.IsSame(note, before["note"])) != 1
            or any(after[key] != before[key] for key in ("fields", "linked", "view", "position"))):
        raise RuntimeError(f"detail {label}: native caption links/identity/view/position changed during document font pin")
    # Native run boundaries can merge; preserve the actual resolved glyphs,
    # including the generated SCALE/ratio separator, not INote.GetText blanks.
    before_text = "".join(text for text, _height, _font in before["fragments"])
    after_text = "".join(text for text, _height, _font in after["fragments"])
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    has_multiple = note.HasMultipleFonts
    if (after_text != before_text or has_multiple is not False
            or annotation.GetUseDocTextFormat(0) is not True
            or any(abs(actual - height) > _NOTE_HEIGHT_READBACK_TOL_M or actual_font != font
                   for _text, actual, actual_font in after["fragments"])):
        raise RuntimeError(f"detail {label}: native caption font/content readback mismatch: source_height_m={height}, source_font={font!r}, before={before['fragments']!r}, after={after['fragments']!r}, has_multiple_fonts={has_multiple!r}")
    _telemetry.info(f"detail {label}: native caption inherited document font verified: source_height_m={height}, source_font={font!r}, fields={after['fields']!r}, native_fragments={after['fragments']!r}, has_multiple_fonts={has_multiple!r}")


def _detail_circle_style_state(
    adapter: Any, front: Any, view: Any, *, label: str,
) -> tuple[Any, tuple[float, ...]]:
    front = _early_bound(front, "IView")
    circles = tuple(front.GetDetailCircles() or ())
    bound = [_early_bound(circle, "IDetailCircle") for circle in circles]
    labels = [circle.GetLabel() for circle in bound]
    if len(bound) != 2 or sorted(labels) != ["D", "E"]:
        raise RuntimeError(f"detail {label}: expected exactly D/E native source circles, got {labels!r}")
    circle = bound[labels.index(label)]
    position = tuple(float(value) for value in circle.GetLabelPosition())
    if len(position) != 2 or not all(math.isfinite(value) for value in position):
        raise RuntimeError(f"detail {label}: invalid source-circle label position={position!r}")
    for owner, expected in ((circle.GetView(), front), (circle.GetDetailView(), view)):
        if owner is None or int(adapter.swApp.IsSame(owner, expected)) != 1:
            raise RuntimeError(f"detail {label}: native source-circle ownership mismatch")
    return circle, position


def _normalize_detail_circle(
    adapter: Any, front: Any, view: Any, height: float, font: str,
    original: tuple[Any, tuple[float, ...]], *, label: str,
) -> None:
    circle, position = _detail_circle_style_state(adapter, front, view, label=label)
    if int(adapter.swApp.IsSame(circle, original[0])) != 1 or position != original[1]:
        raise RuntimeError(f"detail {label}: native source-circle identity/position changed during document font pin")
    text_format = _early_bound(circle.GetTextFormat(), "ITextFormat")
    before = _native_font_authority(text_format, circle.GetUseDocTextFormat(), label=f"detail {label} circle")
    # Both labels take the same sheet-sourced size, including a changed normal
    # note size. This is local to the existing native circles, never a doc pref.
    text_format.CharHeight = height
    if circle.SetTextFormat(False, text_format) is not True:
        raise RuntimeError(f"detail {label}: native source-circle font setter refused")
    rebuild_drawing(adapter, label=f"normalize detail {label} source-circle font")
    adapter.currentModel.GraphicsRedraw2()
    after = _native_font_authority(
        circle.GetTextFormat(), circle.GetUseDocTextFormat(), label=f"detail {label} circle readback",
    )
    if (after["use_doc"] is not False or after["is_height_specified_in_pts"] is not False
            or type(after["char_height_m"]) not in (int, float)
            or not math.isfinite(after["char_height_m"])
            or abs(after["char_height_m"] - height) > _NOTE_HEIGHT_READBACK_TOL_M
            or type(after["font"]) is not str or after["font"] != font):
        raise RuntimeError(f"detail {label}: native source-circle format/height mismatch: source_height_m={height}, before={before!r}, after={after!r}")
    if circle.GetLabel() != label or tuple(circle.GetLabelPosition()) != position:
        raise RuntimeError(f"detail {label}: source-circle label/position changed during font normalization")
    for owner, expected in ((circle.GetView(), front), (circle.GetDetailView(), view)):
        if owner is None or int(adapter.swApp.IsSame(owner, expected)) != 1:
            raise RuntimeError(f"detail {label}: source-circle ownership changed during font normalization")
    _telemetry.info(f"detail {label}: native source-circle font normalized: source_height_m={height}, before={before!r}, after={after!r}, label_position={position!r}")


def _require_detail_circle_display_heights(front: Any, height: float) -> None:
    """Prove both native displayed heights after BOTH circles are normalized."""
    # GetDetailCircleInfo2 textPt is not promised to equal GetLabelPosition.
    # Every entry must have the same sourced height, so no anchor/order join
    # is needed. Keep the complete flat-record/arrow validation before decoding.
    front = _early_bound(front, "IView")
    metadata = front.GetDetailCircleCount2()
    if (type(metadata) is not tuple or len(metadata) != 2
            or any(type(value) is not int for value in metadata)
            or metadata[0] != 2 or metadata[1] <= 0):
        raise RuntimeError(f"detail D/E: invalid native circle display data metadata={metadata!r}")
    count, size = metadata
    info = front.GetDetailCircleInfo2()
    if (type(info) not in (tuple, list) or not info
            or any(type(value) not in (float, int) or not math.isfinite(value) for value in info)):
        raise RuntimeError(f"detail D/E: invalid native circle display data={info!r}")
    if info[0] != count or len(info) != size:
        raise RuntimeError(f"detail D/E: native circle display data count/size mismatch: metadata={metadata!r}, info={info!r}")
    index = 1
    for number in range(count):
        if index + 16 > size:
            raise RuntimeError(f"detail D/E: truncated native circle display data={info!r}")
        arrows = info[index + 15]
        if arrows < 0 or arrows != int(arrows):
            raise RuntimeError(f"detail D/E: invalid native circle arrow count={arrows!r}")
        next_index = index + 16 + int(arrows) * 9
        if next_index > size:
            raise RuntimeError(f"detail D/E: truncated native circle arrow record: circle_index={number}, info={info!r}")
        index = next_index
    # The official example checks count/allocated size and loops declared
    # records only. R16 observed unused allocation; accept only exact zeroes.
    if any(info[unused] != 0 for unused in range(index, size)):
        raise RuntimeError(f"detail D/E: nonzero unused native circle display data={info!r}")
    decoded = _detail_circles(info)
    if len(decoded) != 2:
        raise RuntimeError(f"detail D/E: expected exactly two native circle display-height readbacks={decoded!r}")
    heights = tuple(entry[4][0] for entry in decoded)
    if any(not math.isfinite(actual) or abs(actual - height) > _NOTE_HEIGHT_READBACK_TOL_M
           for actual in heights):
        raise RuntimeError(f"detail D/E: native circle displayed-height mismatch: actual_heights_m={heights!r}, source_height_m={height}")
    _telemetry.info(f"detail D/E: native source-circle displayed heights verified after both font writes: source_height_m={height}, displayed_heights_m={heights!r}")


def _capture_caption_failure(adapter: Any, label: str, exc: Exception) -> None:
    """Capture while the seat is open; never replace the original refusal."""
    try:
        _seat_forensics.capture_com_failure(
            adapter, f"{PART_STEM}-detail-{label}-caption", str(exc),
            api="rocker native caption guard", exception=exc, sheet_png=True,
            detail_label=label,
        )
    except Exception as capture_exc:  # noqa: BLE001 - always retain the original guard
        if capture_exc is not exc:
            with contextlib.suppress(Exception):
                _telemetry.warn(f"detail {label} caption secondary capture failure: {capture_exc!r}")


def _capture_layout_failure(adapter: Any, phase: str, exc: Exception) -> None:
    """Use the existing drawing/PNG capture before any R24 refusal closes it."""
    try:
        native_contexts = {}
        rod_dot_native = getattr(exc, "rod_dot_native_context", None)
        if rod_dot_native:
            native_contexts["rod_dot_native"] = rod_dot_native
        _seat_forensics.capture_com_failure(
            adapter, f"{PART_STEM}-post-caption-finalize", str(exc),
            api="rocker post-caption audit/finalize", exception=exc, sheet_png=True,
            phase=phase, **native_contexts,
        )
    except Exception as capture_exc:  # noqa: BLE001 - always retain the original guard
        if capture_exc is not exc:
            with contextlib.suppress(Exception):
                _telemetry.warn(f"rocker post-caption/finalize secondary capture failure: phase={phase}, {capture_exc!r}")


def _require_ordinary_note_unchanged(adapter: Any, font_source: dict[str, Any]) -> None:
    note = font_source["note"]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    source_after = _ordinary_note_font(adapter, note)
    if (source_after[1:] != font_source["font"][1:]
            or (note.PropertyLinkedText, tuple(annotation.GetPosition())) != font_source["state"]):
        raise RuntimeError("Manufacturing Notes: source format/content/position changed during document font pin")


def _pin_detail_caption_font_source(adapter: Any, source_note: Any) -> dict[str, Any]:
    """Establish inherited defaults before creating native detail views/circles."""
    try:
        source = _ordinary_note_font(adapter, source_note)
        source_note = _early_bound(source_note, "INote")
        annotation = _early_bound(source_note.GetAnnotation(), "IAnnotation")
        font_source = {
            "note": source_note, "font": source,
            "state": (source_note.PropertyLinkedText, tuple(annotation.GetPosition())),
            "extension": _pin_detail_document_font(adapter, *source[:3]),
        }
        rebuild_drawing(adapter, label="pin native detail document fonts")
        adapter.currentModel.GraphicsRedraw2()
        _require_detail_document_fonts(font_source["extension"], source[1], source[2])
        _require_ordinary_note_unchanged(adapter, font_source)
        return font_source
    except Exception as exc:
        _capture_caption_failure(adapter, "styles", exc)
        raise


def _normalize_detail_caption_styles(
    adapter: Any, front: Any, hub: Any, end: Any, font_source: dict[str, Any],
) -> None:
    """Verify inherited captions and normalize parent letters before seating."""
    label = "styles"
    try:
        _text_format, height, font = font_source["font"][:3]
        views = (("D", hub), ("E", end))
        captions = {
            name: _caption_style_state(adapter, view, front, label=name) for name, view in views
        }
        circles = {
            name: _detail_circle_style_state(adapter, front, view, label=name) for name, view in views
        }
        for label, view in views:
            _require_detail_caption_style(adapter, view, front, height, font, captions[label], label=label)
            _normalize_detail_circle(adapter, front, view, height, font, circles[label], label=label)
        label = "styles"
        _require_detail_document_fonts(font_source["extension"], height, font)
        _require_ordinary_note_unchanged(adapter, font_source)
        for label, view in views:
            _require_detail_caption_style(adapter, view, front, height, font, captions[label], label=label)
            circle, position = _detail_circle_style_state(adapter, front, view, label=label)
            if int(adapter.swApp.IsSame(circle, circles[label][0])) != 1 or position != circles[label][1]:
                raise RuntimeError(f"detail {label}: native source-circle identity/position changed after font normalization")
        label = "styles"
        _require_detail_circle_display_heights(front, height)
    except Exception as exc:
        _capture_caption_failure(adapter, label, exc)
        raise



def _seat_detail_caption(adapter: Any, view: Any, sheet: Any, *, label: str) -> None:
    """Seat the native note box; any refusal preserves the active failed sheet."""
    try:
        _record_detail_caption(adapter, view, sheet, label=label, stage="before guards")
        _pin_sheet_scale(adapter, sheet)
        notes = tuple(_early_bound(view, "IView").GetNotes() or ())
        if len(notes) != 1:
            raise RuntimeError(f"detail {label}: expected one native caption, got {len(notes)}")
        note = _early_bound(notes[0], "INote")
        linked = note.PropertyLinkedText
        if type(linked) is not str or not linked:
            raise RuntimeError(f"detail {label}: caption has no native linked fields")
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        crop = _detail_crop(adapter, view, label=label)
        ceiling = crop[1] - 0.003
        lower_boundary = (_title_block_top(adapter, sheet) if label == "E"
                          else float(_early_bound(sheet, "ISheet").GetZoneMargin(1)))
        floor = lower_boundary + 0.003
        slot = (f"detail {label}: native_crop={crop}, native_lower_boundary_m={lower_boundary!r}, "
                f"native_title_rule_top_m={lower_boundary if label == 'E' else None!r}, "
                f"floor_m={floor!r}, ceiling_m={ceiling!r}, slot_height_mm={(ceiling - floor) * 1000.0:.6f}, "
                "required_air_mm=3.000")
        _telemetry.info(slot)
        if not math.isfinite(floor) or floor >= ceiling:
            raise RuntimeError(f"{slot}: invalid native caption slot")
        target_x = (crop[0] + crop[2]) / 2.0
        if label == "E":
            target_x += _END_CAPTION_OFFSET_X_M
        for attempt in range(4):
            _record_detail_caption(adapter, view, sheet, label=label, stage=f"placement {attempt}")
            box = _note_extent(adapter, note, label=f"detail {label} caption")
            context = (f"{slot}, native_caption_get_extent_box={box}, "
                       f"actual_crop_air_mm={(crop[1] - box[3]) * 1000.0:.3f}, "
                       f"actual_lower_air_mm={(box[1] - lower_boundary) * 1000.0:.3f}")
            _telemetry.info(context)
            if box[3] - box[1] > ceiling - floor:
                raise RuntimeError(f"{context}: actual caption cannot fit between crop and lower boundary")
            error = (target_x - (box[0] + box[2]) / 2.0,
                     crop[1] - _DETAIL_CAPTION_TARGET_AIR_M - box[3])
            if max(abs(v) for v in error) <= _DETAIL_CAPTION_SETTLE_M:
                break
            position = tuple(float(v) for v in (annotation.GetPosition() or ()))
            if len(position) != 3 or not all(math.isfinite(v) for v in position):
                raise RuntimeError(f"detail {label}: invalid native caption position")
            if annotation.SetPosition2(position[0] + error[0], position[1] + error[1], position[2]) is not True:
                raise RuntimeError(f"detail {label}: native caption placement refused")
            rebuild_drawing(adapter, label=f"seat detail {label} caption {attempt}")
        else:
            raise RuntimeError(f"{context}: caption ink did not settle")
        if note.PropertyLinkedText != linked or box[1] < floor - 1e-9 or box[3] > ceiling + 1e-9:
            raise RuntimeError(f"{context}: native caption lost links or required air")
        if label == "D" and box[2] > DRAWING_TEMPLATES[SPEC.layout].title_block_left_m - 0.003:
            air = DRAWING_TEMPLATES[SPEC.layout].title_block_left_m - box[2]
            raise RuntimeError(f"{context}: caption must stay left of title block: actual_horizontal_air_mm={air * 1000.0:.3f}, required_air_mm=3.000")
        _telemetry.info(f"detail {label} caption native GetExtent box={box}, crop={crop}, lower_limit={floor}")
    except Exception as exc:
        _capture_caption_failure(adapter, label, exc)
        raise


def _bound_view_annotations(view: Any, *, label: str) -> tuple[Any, ...]:
    """Read the counted native annotation array and bind without fallbacks."""
    native = _early_bound(view, "IView")
    count = native.GetAnnotationCount()
    if type(count) is not int or count < 0:
        raise RuntimeError(f"{label}: invalid native annotation count: {count!r}")
    raw = native.GetAnnotations()
    if raw is None:
        _telemetry.info(f"{label}: native GetAnnotationCount={count}, GetAnnotations=None")
        if count != 0:
            raise RuntimeError(f"{label}: native annotation count {count} returned no annotation array")
        return ()
    if type(raw) not in (tuple, list):
        raise RuntimeError(f"{label}: invalid native annotation array for count {count}: {raw!r}")
    _telemetry.info(f"{label}: native GetAnnotationCount={count}, GetAnnotations length={len(raw)}")
    if len(raw) != count:
        raise RuntimeError(f"{label}: native annotation array length {len(raw)}, expected count {count}")
    annotations = []
    for index, item in enumerate(raw):
        if item is None:
            raise RuntimeError(f"{label}: native annotation #{index} is null")
        annotations.append(_early_bound(item, "IAnnotation"))
    return tuple(annotations)


def _center_mark_display(annotation: Any, evidence: dict[str, Any]) -> dict[str, Any]:
    """Read every native count and row without the shared dump's lossy filtering."""
    def read(member: str, *args: Any) -> Any:
        try:
            value = getattr(data, member)(*args)
        except Exception as exc:
            raise RuntimeError(f"unreadable native {member}{args!r}: {exc}") from exc
        if value is None:
            raise RuntimeError(f"unreadable native {member}{args!r}: NULL")
        return value

    raw = annotation.GetDisplayData()
    if raw is None:
        raise RuntimeError("unreadable native IAnnotation.GetDisplayData: NULL")
    data = _early_bound(raw, "IDisplayData")
    if data is None:
        raise RuntimeError("unreadable native IDisplayData binding: NULL")
    counts = {}
    for key, member, _getters in (*_DISPLAY_PRIMITIVES, ("texts", "GetTextCount", ())):
        count = read(member)
        if type(count) is not int or count < 0:
            raise RuntimeError(f"invalid native {member} count={count!r}")
        counts[key] = count
        if key == "lines":
            evidence["line_count"] = count
    evidence["primitive_counts"] = counts
    if counts["texts"]:
        # Text positions are display-origin offsets, not absolute sheet points;
        # text-in-box width is a table-cell property, not an annotation extent.
        raise RuntimeError(
            f"cannot certify primitive containment: native centre-mark GetTextCount={counts['texts']} "
            "has no contracted absolute text bounds"
        )
    display: dict[str, Any] = {}
    for key, _member, getters in _DISPLAY_PRIMITIVES:
        rows = []
        for index in range(counts[key]):
            row = None
            for getter in getters:
                try:
                    candidate = getattr(data, getter)(index)
                except Exception:
                    continue
                if candidate is None or (type(candidate) in (tuple, list) and not candidate):
                    continue
                # Only the contracted line 3 -> 2 refusal route may fall back.
                # False/0 and malformed nonempty rows are data failures, not refusals.
                row = candidate
                break
            if row is None:
                raise RuntimeError(f"unreadable native {'/'.join(getters)} row #{index}")
            try:
                _validate_center_mark_display({key: [row]})
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"native {getter} row #{index}: {exc}") from exc
            rows.append(row)
        display[key] = rows
    display["texts"] = []
    _validate_center_mark_display(display)
    if any(len(display[key]) != count for key, count in counts.items()):
        raise RuntimeError(f"native display row/count mismatch: {counts!r}")
    return display


def _center_mark_primitive_box(key: str, row: Any) -> Box:
    """Bound a validated native primitive, never a sampled curve or just its centre."""
    if key == "lines":
        return Box.from_points(((row[4], row[5]), (row[7], row[8])))
    if key == "arcs":
        start, end, centre = (row[4], row[5]), (row[7], row[8]), (row[10], row[11])
        if (row[13] != 0.0 or row[14] != 0.0 or row[15] == 0.0
                or row[16] not in (-1.0, 0.0, 1.0) or not row[6] == row[9] == row[12]):
            raise ValueError(f"invalid native arcs plane/direction={row!r}")
        radius, end_radius = math.dist(start, centre), math.dist(end, centre)
        if not math.isfinite(radius) or radius <= 0.0 or radius != end_radius:
            raise ValueError(f"invalid native arcs radius: inconsistent endpoint radii; raw={row!r}")
        # A nearly closed native circle can have unequal start/end points.
        # Certify the complete circle analytically; never infer a tiny sweep
        # or invent a closure tolerance or a normal-sign convention.
        return Box(centre[0] - radius, centre[1] - radius,
                   centre[0] + radius, centre[1] + radius)
    if key == "ellipses":
        # The row has no sweep direction. The complete analytic envelope safely
        # bounds a partial ellipse too, without guessing which arc was rendered.
        cx, cy = row[10], row[11]
        major = (row[13] - cx, row[14] - cy)
        minor = (row[16] - cx, row[17] - cy)
        if major[0] * minor[1] == major[1] * minor[0]:
            raise ValueError(f"invalid native ellipses axes={row!r}")
        rx, ry = math.hypot(major[0], minor[0]), math.hypot(major[1], minor[1])
        return Box.from_points((
            (cx - rx, cy - ry), (cx + rx, cy + ry),
            (row[4], row[5]), (row[7], row[8]),
        ))
    if key == "arrows":
        length = math.hypot(row[3], row[4])
        if (not math.isfinite(length) or length == 0.0 or row[5] != 0.0 or row[6] < 0.0 or row[7] < 0.0
                or row[9] != 0.0 or row[10] != 0.0 or row[11] == 0.0
                or row[8] != int(row[8]) or not 0 <= row[8] <= 12):
            raise ValueError(f"invalid native arrows direction/size/plane/style={row!r}")
        if row[8] not in (0.0, 1.0):
            raise ValueError(
                f"cannot certify primitive containment: native arrows style={row[8]!r} "
                f"has no contracted glyph envelope; raw={row!r}"
            )
        # For open/filled arrows, width is along the direction and height
        # across it. This two-sided certificate covers either base side and
        # any tip placement within that documented width/height rectangle.
        ux, uy = row[3] / length, row[4] / length
        return Box.from_points([
            (row[0] + along * ux - across * uy, row[1] + along * uy + across * ux)
            for along in (-row[6], row[6]) for across in (-row[7], row[7])
        ])
    if key == "polylines" and (row[0] != 0.0 or row[1] != 0.0):
        raise ValueError(
            "cannot certify primitive containment: native polylines type-1 GeomData "
            f"layout is unproved without an additional size read; raw={row!r}"
        )
    decoders = {
        "polylines": polyline_segments, "polygons": polygon_segments,
        "triangles": triangle_segments,
    }
    if key in ("polylines", "polygons"):
        offset = 7 if key == "polylines" else 5
        if len(row) == offset:
            raise ValueError(f"unmeasurable native {key}: no points")
        # A one-point sequence is still present data and must not disappear.
        if len(row) == offset + 3:
            return Box.from_points(((row[offset], row[offset + 1]),))
    segments = decoders[key](row)
    if not segments:
        raise ValueError(f"unmeasurable native {key} primitive={row!r}")
    return Box.from_points([
        point for segment in segments
        for point in ((segment.x0, segment.y0), (segment.x1, segment.y1))
    ])


def _validated_center_mark_crop(crop: Any) -> tuple[float, float, float, float]:
    if not _native_finite_row(crop) or len(crop) != 4 or crop[0] >= crop[2] or crop[1] >= crop[3]:
        raise ValueError(f"invalid native centre-mark crop bbox={crop!r}")
    return tuple(crop)


def _display_coordinate_ulp_m(actual: float, boundary: float) -> float:
    """One positive float32 spacing at float32(max(abs(actual), abs(boundary)))."""
    if not _native_finite_scalar(actual) or not _native_finite_scalar(boundary):
        raise ValueError(f"invalid native display precision coordinates: {actual!r}, {boundary!r}")
    magnitude = max(abs(actual), abs(boundary))
    try:
        # '>f' rounds to IEEE-754 binary32, including exponent-boundary carries.
        bits = struct.unpack(">I", struct.pack(">f", magnitude))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError(f"cannot certify native float32 display precision at {magnitude!r}") from exc
    if bits >= 0x7F7FFFFF:
        # The largest finite float32's next value is infinity; spacing is not
        # a finite containment allowance. Overflow must never admit a row.
        raise ValueError(f"nonfinite native float32 display spacing at {magnitude!r}")
    exponent = (bits >> 23) & 0xFF
    return math.ldexp(1.0, -149 if exponent == 0 else exponent - 150)


def _display_bbox_comparisons(box: Box, crop: Any) -> list[dict[str, Any]]:
    """Apply the display-only one-float32-ULP rule separately to all four sides."""
    comparisons = []
    for coordinate, actual, boundary, lower in (
        ("xmin", box.xmin, crop[0], True), ("ymin", box.ymin, crop[1], True),
        ("xmax", box.xmax, crop[2], False), ("ymax", box.ymax, crop[3], False),
    ):
        overrun = max(0.0, boundary - actual if lower else actual - boundary)
        tolerance, error = None, None
        try:
            tolerance = _display_coordinate_ulp_m(actual, boundary)
            if not math.isfinite(overrun):
                raise ValueError("nonfinite native display coordinate overrun")
        except (TypeError, ValueError, OverflowError) as exc:
            error = str(exc)
        comparisons.append({
            "coordinate": coordinate, "actual_m": actual, "crop_m": boundary,
            "tolerance_m": tolerance, "overrun_m": overrun,
            "accepted": error is None and overrun <= tolerance,
            "precision_error": error,
        })
    return comparisons


def _center_mark_bucket(
    position: Any, display: dict[str, Any], crop: Any, *,
    primitive_evidence: list[dict[str, Any]] | None = None,
) -> str:
    """PRINTED uses display precision only; empty-display ghost anchors stay exact."""
    crop = _validated_center_mark_crop(crop)
    if not _native_finite_row(position) or len(position) != 3:
        raise ValueError(f"invalid native centre-mark GetPosition={position!r}")
    _validate_center_mark_display(display)
    if display.get("texts"):
        raise ValueError(
            "cannot certify primitive containment: native centre-mark text "
            f"has no contracted absolute bounds; raw={display['texts']!r}"
        )
    if not any(display.values()):
        if crop[0] <= position[0] <= crop[2] and crop[1] <= position[1] <= crop[3]:
            raise ValueError("empty native centre-mark display inside crop")
        return "GHOST"
    checked, failures = 0, []
    for key, rows in display.items():
        for index, row in enumerate(rows):
            box = _center_mark_primitive_box(key, row)
            if (not all(math.isfinite(v) for v in (box.xmin, box.ymin, box.xmax, box.ymax))
                    or box.xmin > box.xmax or box.ymin > box.ymax):
                raise ValueError(f"invalid native {key} primitive bbox={box!r}")
            comparisons = _display_bbox_comparisons(box, crop)
            accepted = all(item["accepted"] for item in comparisons)
            if primitive_evidence is not None:
                primitive_evidence.append({
                    "kind": key, "index": index, "raw": row, "bbox": box,
                    "crop": crop, "accepted": accepted, "comparisons": comparisons,
                })
            checked += 1
            precision_errors = [item["precision_error"] for item in comparisons if item["precision_error"]]
            if precision_errors:
                failures.append(
                    f"cannot certify primitive containment: native {key} #{index} "
                    f"display precision failed: {precision_errors!r}; raw={row!r}, bbox={box!r}, crop={crop!r}"
                )
                continue
            if not accepted:
                endpoints_inside = key in ("arcs", "ellipses") and all(
                    crop[0] <= row[offset] <= crop[2] and crop[1] <= row[offset + 1] <= crop[3]
                    for offset in (4, 7)
                )
                if key == "ellipses" and endpoints_inside and row[4:7] != row[7:10]:
                    reason = f"partial native ellipses #{index} has no encoded sweep direction"
                elif key == "arcs" and endpoints_inside and row[4:7] != row[7:10]:
                    reason = f"partial native arcs #{index} has a full-circle envelope crossing crop with endpoints inside"
                elif key == "arrows" and crop[0] <= row[0] <= crop[2] and crop[1] <= row[1] <= crop[3]:
                    reason = f"native arrows #{index} has a two-sided envelope crossing crop with tip inside"
                else:
                    extent_status = (
                        "envelope not certified inside crop within one float32 ULP"
                        if key in ("arcs", "ellipses", "arrows")
                        else "outside crop beyond one float32 ULP"
                    )
                    failures.append(
                        f"nonempty native centre-mark {key} #{index} {extent_status}: "
                        f"raw={row!r}, bbox={box!r}, crop={crop!r}, comparisons={comparisons!r}"
                    )
                    continue
                failures.append(
                    f"cannot certify primitive containment: {reason}; "
                    f"raw={row!r}, envelope={box!r}, crop={crop!r}, comparisons={comparisons!r}"
                )
    if failures:
        raise ValueError("; ".join(failures))
    if checked == 0:
        raise ValueError("nonempty native centre-mark display has no accounted primitives")
    return "PRINTED"


def _center_mark_census_totals(buckets: Any, total: int) -> dict[str, int]:
    counts = dict.fromkeys(("NON_MARK", "PRINTED", "GHOST", "FAIL"), 0)
    for bucket in buckets:
        if bucket not in counts:
            raise RuntimeError(f"native centre-mark bucket fallthrough: {bucket!r}")
        counts[bucket] += 1
    if len(buckets) != total or sum(counts.values()) != total:
        raise RuntimeError(f"native centre-mark bucket/count mismatch: total={total}, buckets={counts!r}")
    return counts


def _require_center_mark_census(
    adapter: Any, view: Any, *, label: str, required: int, detail: str | None = None,
) -> dict[str, int]:
    """Account for every native annotation; retained zero-ink ghosts never count."""
    # Ordinary front outline only; D/E retain the existing persisted-crop proof.
    # Do not float-coerce a malformed native bbox into apparently valid numbers.
    raw_crop = (_early_bound(view, "IView").GetOutline() if detail is None
                else _detail_crop(adapter, view, label=detail))
    crop = _validated_center_mark_crop(raw_crop)
    annotations = _bound_view_annotations(view, label=f"{label} template center marks")
    buckets, failures = [], []
    for index, annotation in enumerate(annotations):
        evidence: dict[str, Any] = {
            "id": f"annotation #{index}", "position": "unreadable", "line_count": "unreadable",
        }
        primitive_evidence: list[dict[str, Any]] = []
        try:
            kind = annotation.GetType()
            if type(kind) is not int or not 1 <= kind <= 19:
                raise RuntimeError(f"invalid native annotation type={kind!r}")
            if kind != 13:  # swAnnotationType_e.swCenterMarkSym
                buckets.append("NON_MARK")
                continue
            name = annotation.GetName()
            if type(name) is not str or not name:
                raise RuntimeError(f"unreadable native IAnnotation.GetName={name!r}")
            evidence["id"] = name
            evidence["position"] = annotation.GetPosition()
            display = _center_mark_display(annotation, evidence)
            bucket = _center_mark_bucket(
                evidence["position"], display, crop, primitive_evidence=primitive_evidence,
            )
            if bucket not in ("PRINTED", "GHOST"):
                raise RuntimeError(f"native centre-mark bucket fallthrough: {bucket!r}")
        except Exception as exc:
            bucket = "FAIL"
            failures.append(f"{evidence['id']!r}: {exc}")
        buckets.append(bucket)
        _telemetry.info(
            f"{label} centre-mark id={evidence['id']!r}, position={evidence['position']!r}, "
            f"line_count={evidence['line_count']!r}, class={bucket}, "
            f"primitive_counts={evidence.get('primitive_counts')!r}, crop={crop!r}"
            + (f", reason={failures[-1]}" if bucket == "FAIL" else "")
        )
        for primitive in primitive_evidence:
            coordinate_details = "; ".join(
                f"{item['coordinate']}: actual_m={item['actual_m']!r}, crop_m={item['crop_m']!r}, "
                f"tolerance_m={item['tolerance_m']!r}, overrun_m={item['overrun_m']!r}, "
                f"accepted={item['accepted']}, precision_error={item['precision_error']!r}"
                for item in primitive["comparisons"]
            )
            _telemetry.info(
                f"{label} centre-mark primitive id={evidence['id']!r}, "
                f"kind={primitive['kind']}, index={primitive['index']}, accepted={primitive['accepted']}, "
                f"bbox={primitive['bbox']!r}, crop={primitive['crop']!r}, raw={primitive['raw']!r}, "
                f"coordinate_comparisons=[{coordinate_details}]"
            )
    counts = _center_mark_census_totals(buckets, len(annotations))
    _telemetry.info(
        f"{label} centre-mark totals: total_view_annotations={len(annotations)}, "
        f"non_mark={counts['NON_MARK']}, printed={counts['PRINTED']}, ghost={counts['GHOST']}, "
        f"fail={counts['FAIL']}, required_printed={required}"
    )
    if failures:
        raise RuntimeError(f"{label} centre-mark census FAIL: {failures!r}; totals={counts!r}")
    if counts["PRINTED"] != required:
        raise RuntimeError(
            f"expected {required} {label} PRINTED hole center marks, found {counts['PRINTED']}; "
            f"totals={counts!r}"
        )
    return counts


def _require_dimension_census(adapter: Any, views: Any) -> None:
    marked = set().union(*DRAWING_DIMENSIONS.values())
    total = []
    for label, view, keep in views:
        annotations = _bound_view_annotations(view, label=f"rocker {label}")
        names = []
        for index, annotation in enumerate(annotations):
            name = dimension_name(adapter, annotation)
            if not name:
                kind = annotation.GetType()
                if type(kind) is not int or not 1 <= kind <= 19:
                    raise RuntimeError(f"rocker {label}: native annotation #{index} has invalid type: {kind!r}")
                if kind == 4:  # swAnnotationType_e.swDisplayDimension
                    specific = annotation.GetSpecificAnnotation()
                    if specific is None:
                        raise RuntimeError(f"rocker {label}: native dimension #{index} has no native display dimension")
                    display = _early_bound(specific, "IDisplayDimension")
                    if display.GetDimension2(0) is not None:
                        raise RuntimeError(f"rocker {label}: native dimension #{index} has no readable name")
                    hole_callout = display.IsHoleCallout()
                    if type(hole_callout) is not bool:
                        raise RuntimeError(f"rocker {label}: native dimension #{index} has invalid hole-callout identity: {hole_callout!r}")
                    if hole_callout is not True:
                        raise RuntimeError(f"rocker {label}: native dimension #{index} has no underlying model dimension")
            if name in marked:
                names.append(name)
        _telemetry.info(f"rocker {label} native annotations={len(annotations)} marked-dimension census={names!r}")
        if sorted(names) != sorted(keep):
            raise RuntimeError(f"rocker {label}: native dimension owners {names!r}, expected {sorted(keep)!r}")
        total.extend(names)
    if len(total) != len(marked) or set(total) != marked:
        raise RuntimeError(f"rocker native marked-dimension union is not exact: {total!r}")




# Detail D makes the two concentric rims distinguishable at their actual 4:1
# projection. A coordinate pick must still resolve to the diameter-picked bore.
PIVOT_DATUM_STANDOFF = 0.020
PIVOT_DATUM_ANGLE = math.radians(135.0)
PIVOT_PICK_FRACTIONS = (1.0, 0.6)

PIVOT_BORE = requirement(
    "pivot_bore", kind="hole", faces=(CylinderFace(rocker.PIVOT_HOLE_DIA),),
    requirements=("dia", "thru", "finish_ra", "process"), fields={
        "at": _CENTRE, "axis": _AXIS,
        "dia": (_band(rocker.PIVOT_HOLE_DIA, _PIVOT_P, rocker.PIVOT_HOLE_BAND), ("PIVOT_HOLE_DIA", "PIVOT_HOLE_BAND")),
        "nominal_dia": (rocker.PIVOT_HOLE_DIA, ("PIVOT_HOLE_DIA",)),
        "thru": (True, (("draw_ch_rocker_arm", "_dress_detail_dimensions"),)),
        "finish_ra": (_surface_finish.MACHINED_UM, ("SURFACE_FINISHES",)),
        "process": ("ream", (("draw_ch_rocker_arm", "_dress_detail_dimensions"),)), "datum": ("A", (("draw_ch_rocker_arm", "build"),)),
    }, precision={"dia": _PIVOT_P, "finish_ra": 1},
)

part_metadata(
    frames={
        name: ({"origin": [0.0, rocker_interface.PIVOT_MID_Y, sign * rocker.HUB_LENGTH / 2], "x": [1.0, 0.0, 0.0], "y": [0.0, float(sign), 0.0], "z": [0.0, 0.0, float(sign)], "binding": "unknown"}, (("_rocker_interface", "PIVOT_MID_Y"), "HUB_LENGTH"))
        for name, sign in (("A", 1), ("B", -1))
    },
    datums={"A": ({"feature": "pivot_bore", "surface": "pivot bore cylinder"}, (("draw_ch_rocker_arm", "build"),))},
)


def _assert_pivot_precision(
    adapter: Any, drawing_model: Any, annotations: list[Any]
) -> None:
    """Read PivotDia's effective primary precision without rewriting its import."""
    expected = PIVOT_BORE.precision["dia"]
    for annotation in annotations:
        annotation = adapter._attempt(
            lambda a=annotation: _early_bound(a, "IAnnotation")
        )
        name = adapter._attempt(lambda a=annotation: dimension_name(adapter, a))
        if type(name) is not str or not name:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; unreadable dimension name"
            )
        if name != "PivotDia":
            continue
        display = adapter._attempt(
            lambda a=annotation: _early_bound(
                a.GetSpecificAnnotation(), "IDisplayDimension"
            )
        )
        primary = adapter._attempt(lambda d=display: d.GetPrimaryPrecision2())
        if type(primary) is not int:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; "
                f"unreadable primary precision {primary!r}"
            )
        effective = primary
        # swDimensionPrecisionSettings_e.swPrecisionFollowsDocumentSetting = -2.
        if primary == -2:
            extension = adapter._attempt(
                lambda: _early_bound(
                    _early_bound(drawing_model, "IModelDoc2").Extension,
                    "IModelDocExtension",
                )
            )
            # swconst R2026x: swDetailingLinearDimPrecision = 24;
            # swDetailingDiameterDimension = 204. Units decimals are not this getter.
            effective = adapter._attempt(
                lambda: extension.GetUserPreferenceInteger(24, 204)
            )
        if type(effective) is not int or effective < 0:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; "
                f"unreadable effective precision {effective!r} (primary {primary})"
            )
        if effective != expected:
            raise RuntimeError(
                f"PivotDia precision: expected {expected}; "
                f"effective {effective} decimal places (primary {primary})"
            )
        return
    raise RuntimeError(
        f"PivotDia precision: expected {expected}; missing dimension, "
        "effective precision unreadable"
    )


def _pivot_datum_request(centre: tuple[float, float], radius: float) -> tuple[float, float]:
    """Detail-space junction on the upper-left ray, using its projected bore."""
    reach = radius + PIVOT_DATUM_STANDOFF
    return (
        centre[0] + reach * math.cos(PIVOT_DATUM_ANGLE),
        centre[1] + reach * math.sin(PIVOT_DATUM_ANGLE),
    )


def _pick_pivot_bore(
    adapter: Any, view: Any, bore_edge: Any, centre: tuple[float, float], radius: float,
) -> tuple[float, float]:
    """Return a detail-space point whose EDGE pick resolves to the bore."""
    results = []
    for fraction in PIVOT_PICK_FRACTIONS:
        radius_at_pick = radius * fraction
        xy = (
            centre[0] + radius_at_pick * math.cos(PIVOT_DATUM_ANGLE),
            centre[1] + radius_at_pick * math.sin(PIVOT_DATUM_ANGLE),
        )
        try:
            picked = _select_view_entity(
                adapter, view, "EDGE", xy, label="pivot bore datum pick"
            )
        except RuntimeError as error:
            results.append((fraction, str(error)))
            _telemetry.event("datum.bore_pick", fraction=fraction, same=-2)
            continue
        same = int(adapter.swApp.IsSame(picked, bore_edge))
        results.append((fraction, same))
        _telemetry.event("datum.bore_pick", fraction=fraction, same=same)
        adapter.currentModel.ClearSelection2(True)
        if same == 1:
            return xy
    raise RuntimeError(
        "no pick on datum A's ray resolves to the O6.5 pivot bore "
        f"(fraction of bore radius, IsSame or error): {results!r}"
    )


def _require_datum_on_bore(app: Any, tag: Any, bore_edge: Any) -> None:
    """Raise unless datum A is attached to the pivot bore edge alone."""
    annotation = _early_bound(tag.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError("datum A has no native annotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 1 or attached[0] is None:
        raise RuntimeError(
            f"datum A needs one attached edge, has {len(attached)}: {attached!r}"
        )
    # swObjectSame = 1; different (0) and unknown (-1) both fail.
    if int(app.IsSame(attached[0], bore_edge)) != 1:
        raise RuntimeError(
            "datum A is attached to an edge other than the O6.5 pivot bore "
            "(r743-4D: the concentric O10 hub)"
        )
    if annotation.IsDangling():
        raise RuntimeError("datum A is dangling")


# Bore finish in D's lower-right quadrant; never either hub end face.
PIVOT_FINISH_ANGLE = math.radians(-45.0)
PIVOT_FINISH_OFFSET = (0.012, -0.013)
PIVOT_FINISH_CHAR_HEIGHT = 0.0025


def _pivot_finish_placement(
    adapter: Any, hub: Any,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Project the real bore rim through D's native transform."""
    radius = PIVOT_HOLE_DIA / 2.0
    (rim,) = _project(
        adapter, hub,
        [(radius * math.cos(PIVOT_FINISH_ANGLE) / 1000.0,
          (PIVOT_MID_Y + radius * math.sin(PIVOT_FINISH_ANGLE)) / 1000.0, 0.0)],
        label="detail D bore finish rim",
    )
    return rim, (rim[0] + PIVOT_FINISH_OFFSET[0], rim[1] + PIVOT_FINISH_OFFSET[1])


# Every marked model dimension has exactly one face-view owner.
# The radius texts sit below the strap's left half, outside both parent
# circles, between the left taper row and the strap: R816's leader lands on
# the lower arc well left of A's centreline (Opus #1020 review). R800 has one
# below-text row and sits 40 mm left of R816's two-row block; its extra 4 mm
# height keeps the shoulder above the left taper's native BASIC box.
FRONT_KEEP = {
    "TopRadius": (0.120, 0.160),
    "BottomRadius": (0.160, 0.156),
    "TopAbovePivot": (0.165, 0.191),
}

_TOP_P = rocker_notes.DRAWING_PRECISION["TopEdgeReference"]["TopAbovePivot"]
TOP_EDGE = requirement(
    "top_edge", kind="profile", faces=(CylinderFace(2 * rocker_interface.CURVE_RADIUS),),
    requirements=("height_above_pivot", "radius", "surface_profile"), fields={
        "height_above_pivot": (rocker.TOP_EDGE_ABOVE_PIVOT, ("TOP_EDGE_ABOVE_PIVOT", ("draw_ch_rocker_arm", "_basic_profile_dimensions"))),
        "height_from": ("pivot_bore", (("draw_ch_rocker_arm", "build"),)),
        "radius": (rocker_interface.CURVE_RADIUS, (("_rocker_interface", "CURVE_RADIUS"), ("draw_ch_rocker_arm", "_basic_profile_dimensions"))), "radius_nominal": (rocker_interface.CURVE_RADIUS, (("_rocker_interface", "CURVE_RADIUS"),)),
        "dimension_type": ("basic", (("draw_ch_rocker_arm", "_basic_profile_dimensions"),)),
        # The printed frame, kept whole as text; the zone below is what reads it.
        "note": (f"SURFACE PROFILE {ARC_PROFILE_ZONE_TEXT} U{ARC_PROFILE_OUTSIDE_TEXT['TopRadius']} TO {'|'.join(ARC_PROFILE_DATUMS)}", ("TOP_EDGE_BAND", ("draw_ch_rocker_arm", "_add_arc_profiles"))),
        # Material added on the top edge moves it toward the arc centre.
        **_profile_zone("TopRadius", {"radius": "decreases", "height_above_pivot": "increases"}, (("draw_ch_rocker_arm", "_basic_profile_dimensions"),)),
        "arc_len": (rocker.TOP_ARC_LEN, ("TOP_ARC_LEN",)),
        "arc_centre": ([0.0, rocker_interface.CENTER_Y, 0.0], (("_rocker_interface", "CENTER_Y"),)),
        "centre_from_pivot_ref": (rocker_interface.CENTER_Y - rocker_interface.PIVOT_MID_Y, (("_rocker_interface", "CENTER_Y"), ("_rocker_interface", "PIVOT_MID_Y"))),
        "end": (list(_TOP), ("TOP_END_X", "TOP_END_Y")),
    }, precision={"height_above_pivot": _TOP_P, "radius": _RADIUS_P},
)
# One Ⓤ0 zone over the lower outline between J and K: the R816 arc, both
# tapers and both tip lands, all filed to the one scribed line (option 4).
PROFILE_OUTER = requirement(
    "profile_outer", kind="profile", faces=(CylinderFace(2 * rocker_interface.R_BOTTOM), _RIGHT[1], _TIPS[1]),
    requirements=("bottom_radius", "mirror_symmetric", "surface_profile"), fields={
        "bottom_radius": (rocker_interface.R_BOTTOM, (("_rocker_interface", "R_BOTTOM"), ("draw_ch_rocker_arm", "_basic_profile_dimensions"))),
        "bottom_radius_nominal": (rocker_interface.R_BOTTOM, (("_rocker_interface", "R_BOTTOM"),)),
        "dimension_type": ("basic", (("draw_ch_rocker_arm", "_basic_profile_dimensions"),)),
        "note": (f"SURFACE PROFILE {ARC_PROFILE_ZONE_TEXT} U{ARC_PROFILE_OUTSIDE_TEXT['BottomRadius']} TO {'|'.join(ARC_PROFILE_DATUMS)}, BETWEEN {PROFILE_BETWEEN[0]} AND {PROFILE_BETWEEN[1]}", ("TOP_EDGE_BAND", ("draw_ch_rocker_arm", "_add_arc_profiles"))),
        # Material added on the lower outline moves it away from the arc centre.
        # The tip lands declare this same zone themselves (see the tip-land loop).
        **_profile_zone("BottomRadius", {"bottom_radius": "increases"}, (("draw_ch_rocker_arm", "_basic_profile_dimensions"),)),
        "arc_centre": ([0.0, rocker_interface.CENTER_Y, 0.0], (("_rocker_interface", "CENTER_Y"),)), "top_edge_feature": ("top_edge", (("ch_rocker_arm_notes", "BOTTOM_RADIUS_CALLOUT"),)),
        "bottom_arc_len": (rocker.BOT_ARC_LEN, ("BOT_ARC_LEN",)),
        "mirror_symmetric": (True, (("draw_ch_rocker_arm", "_add_rocker_outline_dimensions"), ("draw_ch_rocker_arm", "_dress_detail_dimensions"))), "depth_ref": (rocker_interface.ARM_DEPTH, (("_rocker_interface", "ARM_DEPTH"),)),
        "bottom_end": (list(_BOTTOM), ("BOT_END_X", ("_rocker_interface", "R_BOTTOM"), ("_rocker_interface", "CENTER_Y"))),
        "radial_tip_end": (list(_TIP), ("ROD_TIP_X", "TOP_END_Y", "TIP_FACE", ("_rocker_interface", "CURVE_RADIUS"), ("_rocker_interface", "CENTER_Y"))),
    }, precision={"bottom_radius": _RADIUS_P},
)
HUB_OD = requirement(
    "hub_od", kind="boss", faces=(CylinderFace(rocker.HUB_DIA),),
    requirements=("dia", "coaxiality_dia"), fields={
        "at": _CENTRE, "axis": _AXIS,
        "dia": (_band(rocker.HUB_DIA, _P, (rocker.LINEAR_2PL, -rocker.LINEAR_2PL)), ("HUB_DIA", "LINEAR_2PL")),
        "dia_nominal": (rocker.HUB_DIA, ("HUB_DIA",)),
        # A position frame to A under the Ø10.20 in detail D carries the zone.
        "coaxiality_dia": (rocker.HUB_COAXIALITY_DIA, ("HUB_COAXIALITY_DIA", ("draw_ch_rocker_arm", "_hub_position_frame"))),
        "coaxial_to": ("pivot_bore", (("draw_ch_rocker_arm", "_hub_position_frame"),)),
        "position_datums": (["A"], (("draw_ch_rocker_arm", "_hub_position_frame"),)),
    }, precision={"dia": _P, "coaxiality_dia": _FRAME_P},
)
# The Ø10.20's attached position frame takes its leader shoulder and lifts the
# value ~11 mm above the requested point (main-r1 farm screen: from 0.122 onto
# the 132.76 R816/TAPER row). Requested lower, the stack lands in the free
# band right of D's crop and under that dimension line (~0.131) either way.
HUB_KEEP = {
    "PivotDia": (0.120, 0.086),
    "HubDia": (0.212, 0.108),
}
# The 2X 5.59 box sits between its own witnesses: the upper one passes its
# top-left corner (0.05 mm at the plain 5.59, main-r1 PDF), so the widened
# text is requested 2 mm lower, centred in the 124.0-133.4 mm clear band.
END_KEEP = {
    "RodTipLen": (0.377, 0.128),
    "TipLandAngle": (0.372, 0.082),
}
# View F at 3:1 (RIGHT_CENTER; strap faces x 0.0713/0.0788, hub ends
# 0.0644/0.0856, part y 0.151-0.239, hub y 0.160-0.190). Native centres each
# value-plus-three-row block on its request and runs the dimension line under
# the block (r4: the 2.500 line at the block's bottom, 158 mm, through the
# hub). Both blocks sit left of the view, clear of the border (0.0125):
# * the strap thickness with its fork-fit rows high, so its line (~0.214,
#   model y ~21) crosses the strap alone, above the hub (Opus #1020 r2 C3);
#   its position frame to G hangs under that line, over the hub;
# * the hub length low, its line (~0.142) under the strap's bottom edge.
# The root fillets' single limit reads left of the view between the two
# blocks, under the strap's position frame and over the hub, its leader short
# down-right to the +Z hub-root corner it measures (r3 run: requested right of
# the view, the leader crossed the strap to that corner).
STRAP_THICKNESS_TEXT_XY = (0.044, 0.2246)
# The hub width's below rows end on the fit-up step that takes up the 20-hub
# stack's excess (r5 Opus C2, drawing-guidelines.md rule 19 (absorb stacks at
# fit-up)): MHA-CH-00 step "rocker-stack-accepted" re-faces a long stack.
ROCKER_STACK_STEP_KEY = "rocker-stack-accepted"
HUB_LENGTH_TEXT = (
    f"{rocker_notes.HUB_LENGTH_CALLOUT} PER\n{channel_step_ref(ROCKER_STACK_STEP_KEY)}"
)
# Half a row up for that fourth row keeps the line (~0.142) where it was; the
# widest row ("MHA-CH-00 STEP 1") clears the hub end.
HUB_LENGTH_TEXT_XY = (0.040, 0.1578)
HUB_ROOT_TEXT_XY = (0.047, 0.199)
# Datum G is the hub's -Z end face (#1579 owner ruling, option 1): the face
# each arm registers on in the 20X stack, one a shop can set up on, where the
# hub-width centre plane it replaces could only be derived. The strap frame's
# ⌖0.10|G holds the strap's centre plane at a BASIC from that face to view
# F's centreline. Both stand in the view's one free column, right of the -Z
# face (x ~0.0856) and short of the front view's 132.8 left witness
# (FRONT_LEFT_WITNESS_X): G's triangle on the face's lower half, its box
# straight out right; the BASIC's line above the hub (top ~0.190), its boxed
# text out right of the face.
HUB_FACE_DATUM_LANDING_Y_MM = rocker_interface.PIVOT_MID_Y - rocker.HUB_DIA / 4.0
HUB_FACE_DATUM_STANDOFF_M = 0.0075
HUB_FACE_BASIC_TEXT_XY = (0.0945, 0.199)
FRONT_LEFT_WITNESS_X = 0.105
RIGHT_KEEP: dict[str, tuple[float, float]] = {
    "HubLength": HUB_LENGTH_TEXT_XY,
    "StrapThickness": STRAP_THICKNESS_TEXT_XY,
    "HubRootRadius": HUB_ROOT_TEXT_XY,
}
# Datum B on the +Z strap face (view F's left line) near the strap's top
# end, above the thickness block; its box up-left of the pick.
DATUM_B_PICK_MODEL_Y = 28.0
DATUM_B_SYMBOL_XY = (0.057, 0.247)

_HUB_P = rocker_notes.DRAWING_PRECISION["Hub"]["HubLength"]
_STRAP_P = rocker_notes.DRAWING_PRECISION["Strap"]["StrapThickness"]
_STRAP_BAND = (_band(rocker.ARM_THICKNESS, _STRAP_P, rocker.ARM_THICKNESS_BAND), ("ARM_THICKNESS", "ARM_THICKNESS_BAND"))
HUB_FACES = requirement(
    "hub_faces", kind="face",
    faces=tuple(PlanarFace((0, 0, sign), rocker.HUB_LENGTH / 2) for sign in (-1, 1)),
    requirements=("length",), fields={
        "length": (_band(rocker.HUB_LENGTH, _HUB_P, rocker.HUB_LENGTH_BAND), ("HUB_LENGTH", "HUB_LENGTH_BAND")),
        "length_nominal": (rocker.HUB_LENGTH, ("HUB_LENGTH",)),
        "upper_z": (rocker.HUB_LENGTH / 2, ("HUB_LENGTH",)),
        "lower_z": (-rocker.HUB_LENGTH / 2, ("HUB_LENGTH",)),
        "datum": ("G", (("draw_ch_rocker_arm", "_hub_face_datum"),)),
    }, precision={"length": _HUB_P},
)
STRAP_FACES = requirement(
    "strap_faces", kind="face", faces=(PlanarFace((0, 0, -1), rocker.ARM_THICKNESS / 2),),
    requirements=("thickness",), fields={
        "thickness": _STRAP_BAND,
        "thickness_nominal": (rocker.ARM_THICKNESS, ("ARM_THICKNESS",)),
        "upper_z": (rocker.ARM_THICKNESS / 2, ("ARM_THICKNESS",)),
        "lower_z": (-rocker.ARM_THICKNESS / 2, ("ARM_THICKNESS",)),
        "position_datums": (["G"], (("draw_ch_rocker_arm", "_strap_position_frame"),)),
    }, precision={"thickness": _STRAP_P},
)
STRAP_DATUM_B = requirement(
    "strap_datum_b", kind="face", faces=(PlanarFace((0, 0, 1), rocker.ARM_THICKNESS / 2),),
    requirements=("thickness",), fields={
        "thickness": _STRAP_BAND,
        "thickness_nominal": (rocker.ARM_THICKNESS, ("ARM_THICKNESS",)),
        "plane": ({"frame": "model", "axis": "z", "value": rocker.ARM_THICKNESS / 2}, ("ARM_THICKNESS",)),
        "datum": ("B", (("draw_ch_rocker_arm", "build"),)),
    }, precision={"thickness": _STRAP_P},
)
# The hub-to-strap root fillets, both strap faces: a torus about the pivot
# axis whose tube centre stands HUB_ROOT_RADIUS_MAX off the hub wall and off
# the strap face. View F prints the single limit "2X R0.2 MAX", so the band
# runs from sharp to the modelled radius, and that radius is the largest
# corner the work may leave there (prechips corner_radius_max_design).
_ROOT_P = rocker_notes.DRAWING_PRECISION["HubRoot"]["HubRootRadius"]
_ROOT_SOURCES = ("HUB_ROOT_RADIUS_MAX", ("ch_rocker_arm_notes", "HUB_ROOT_R_TOL_TYPE"), ("draw_ch_rocker_arm", "_dress_hub_root"))
HUB_ROOT = requirement(
    "hub_root", kind="fillet",
    faces=tuple(
        TorusFace(
            rocker.HUB_DIA / 2 + rocker.HUB_ROOT_RADIUS_MAX, rocker.HUB_ROOT_RADIUS_MAX,
            center_mm=(0.0, rocker_interface.PIVOT_MID_Y, sign * (rocker.ARM_THICKNESS / 2 + rocker.HUB_ROOT_RADIUS_MAX)),
        )
        for sign in (-1, 1)
    ),
    requirements=("radius",), fields={
        "radius": (
            _band(rocker.HUB_ROOT_RADIUS_MAX, _ROOT_P, rocker_notes.HUB_ROOT_R_BAND),
            (*_ROOT_SOURCES, ("ch_rocker_arm_notes", "HUB_ROOT_R_BAND")),
        ),
        "radius_nominal": (rocker.HUB_ROOT_RADIUS_MAX, ("HUB_ROOT_RADIUS_MAX",)),
        "corner_radius_max_design": (rocker.HUB_ROOT_RADIUS_MAX, _ROOT_SOURCES),
        "note": (
            rocker_notes.HUB_ROOT_NOTE,
            (*_ROOT_SOURCES, ("ch_rocker_arm_notes", "HUB_ROOT_NOTE")),
        ),
    }, precision={"radius": _ROOT_P},
)
part_metadata(
    datums={
        "B": (
            {"feature": "strap_datum_b", "surface": "+Z broad strap face"},
            (("draw_ch_rocker_arm", "build"),),
        ),
        "G": (
            {
                "feature": "hub_faces",
                "surface": "-Z hub end face (20X stack registration)",
            },
            (("draw_ch_rocker_arm", "_hub_face_datum"),),
        ),
    }
)
BASIC_PROFILE_DIMENSIONS = {"TopRadius", "BottomRadius", "TopAbovePivot"}


def _basic_profile_dimensions(adapter: Any, annotations: list[Any]) -> None:
    """Make the imported profile nominals BASIC without saving the source part."""
    remaining = set(BASIC_PROFILE_DIMENSIONS)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        set_basic_dimension(adapter, display, label=f"arc-system {name}")
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"arc-system BASIC dimensions missing: {sorted(remaining)}")


def _dress_arc_radii(adapter: Any, annotations: list[Any]) -> None:
    """Exterior leaders on both BASIC radii; each states the shared centre in
    below text: R800 locates it above A (the former general note 1), R816 its
    concentricity with R800 (Opus #1020 r2 B1)."""
    remaining = set(ARC_RADIUS_NAMES)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        # Dress exterior radius callouts with the pinion-arbor and
        # arbor-pedestal leader pattern. The text must also be outside
        # its parent circle: these flags alone did not remove the centre
        # line when the R800 text was inside that circle.
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
        if name == "TopRadius":
            display.SetText(4, rocker_notes.TOP_RADIUS_CALLOUT)
            if str(display.GetText(4) or "") != rocker_notes.TOP_RADIUS_CALLOUT:
                raise RuntimeError("R800 centre-above-A callout did not persist")
        if name == "BottomRadius":
            display.SetText(4, rocker_notes.BOTTOM_RADIUS_CALLOUT)
            if str(display.GetText(4) or "") != rocker_notes.BOTTOM_RADIUS_CALLOUT:
                raise RuntimeError("R816 concentric callout did not persist")
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"arc radius dimensions missing: {sorted(remaining)}")


def _dress_detail_dimensions(
    adapter: Any, annotations: list[Any], *, keep: dict[str, tuple[float, float]],
) -> None:
    """Read D/E imported sizes; preserve the native pivot size and ream band."""
    expected = {
        "RodTipLen": TIP_FACE,
        "TipLandAngle": _ALPHA_TOP,
        "HubDia": HUB_DIA,
        "PivotDia": PIVOT_HOLE_DIA,
    }
    remaining = {name: expected[name] for name in keep}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if name == "TipLandAngle":
            model_dimension = _early_bound(display.GetDimension2(0), "IDimension")
            actual = None if model_dimension is None else model_dimension.SystemValue
            if (
                int(display.Type2) != 3
                or type(actual) not in (int, float)
                or not math.isfinite(actual)
                or not math.isclose(abs(actual), remaining.pop(name), abs_tol=1e-8)
            ):
                raise RuntimeError("tip-land angle lost its native radial-land measurement")
            set_basic_dimension(adapter, display, label="tip land angle")
            display.SetText(1, rocker_notes.TIP_LAND_ANGLE_PREFIX)
            if str(display.GetText(1) or "") != rocker_notes.TIP_LAND_ANGLE_PREFIX:
                raise RuntimeError("tip land angle lost its 2X count")
            continue
        assert_dimension_measures(
            adapter, display, expected_mm=remaining.pop(name), label=f"imported {name}"
        )
        if name == "RodTipLen":
            # The land runs inside the J↔K profile: BASIC, the zone is its band.
            set_basic_dimension(adapter, display, label="tip land length")
            # Both tip lands are this BASIC: the J land is counted here, not
            # left to a mirror note (main-r1 Opus).
            display.SetText(1, rocker_notes.TIP_LAND_PREFIX)
            if str(display.GetText(1) or "") != rocker_notes.TIP_LAND_PREFIX:
                raise RuntimeError("tip land length lost its 2X count")
            continue
        # Single exterior arrows, not diametral lines through both concentric
        # circles: otherwise the new hub OD and pivot bore leaders intersect.
        display.ArrowSide = 1  # swDimArrowsOutside
        display.SetSecondArrow(False, False)
        display.SolidLeader = False
        if (
            int(display.ArrowSide) != 1
            or display.GetUseDocSecondArrow()
            or display.GetSecondArrow()
            or display.SolidLeader
        ):
            raise RuntimeError(f"{name} retained a centre-crossing diameter leader")
        if name != "PivotDia":
            continue
        model_dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(model_dimension.Tolerance, "IDimensionTolerance")
        band = (float(tolerance.GetMaxValue()), float(tolerance.GetMinValue()))
        if not all(math.isfinite(value) for value in band) or any(
            abs(actual - expected / 1000.0) > 1e-9
            for actual, expected in zip(band, PIVOT_HOLE_BAND)
        ):
            raise RuntimeError(f"pivot bore lost its part-owned ream tolerance: {band}")
        tolerance_type = int(model_dimension.GetToleranceType())
        # The ream band reads as clearance on its named mate (Opus #1020).
        display.SetText(4, rocker_notes.PIVOT_FIT_CALLOUT)
        if str(display.GetText(4) or "") != rocker_notes.PIVOT_FIT_CALLOUT:
            raise RuntimeError("pivot bore fit callout did not persist")
        prefix = str(display.GetText(5) or "")  # native prefix definition
        suffix = str(display.GetText(6) or "")  # native suffix definition
        callouts = (str(display.GetText(7) or ""), str(display.GetText(8) or ""))
        # A custom prefix replaces the automatic diameter glyph, so retain its
        # native symbol token when the original prefix compartment is empty.
        ream_prefix = "REAM " + (prefix if prefix else "<MOD-DIAM>")
        through_suffix = suffix.rstrip() + " THRU"
        display.SetText(1, ream_prefix)
        display.SetText(2, through_suffix)
        if (
            str(display.GetText(5) or "") != ream_prefix
            or str(display.GetText(6) or "") != through_suffix
            or (str(display.GetText(7) or ""), str(display.GetText(8) or "")) != callouts
            or not display.ShowDimensionValue
            or int(model_dimension.GetToleranceType()) != tolerance_type
            or (float(tolerance.GetMaxValue()), float(tolerance.GetMinValue())) != band
        ):
            raise RuntimeError("pivot ream/through text did not preserve its native dimension")
    if remaining:
        raise RuntimeError(f"detail source dimensions missing: {sorted(remaining)}")
    if any(dimension_name(adapter, ann) == "HubDia" for ann in annotations):
        assert_imported_precision(
            adapter, annotations, {"HubDia": DEFAULT_DRAWING_PRECISION}
        )


def _add_rocker_outline_dimensions(
    adapter: Any, front: Any,
) -> tuple[list[Any], Any, tuple[Any, Any], Any, tuple[Any, Any]]:
    """Import profile nominals and return their annotations with the outline."""
    annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _basic_profile_dimensions(adapter, annotations)
    _dress_arc_radii(adapter, annotations)
    edges = scan_view_edges(front, label="rocker front outline")
    width_points = (
        (-ROD_TIP_X, _ROD_TIP_Y, ARM_THICKNESS / 2.0),
        (ROD_TIP_X, _ROD_TIP_Y, ARM_THICKNESS / 2.0),
    )
    vertices = tuple(
        edges.exact_vertex_at(point, label=f"overall width tip {index}")
        for index, point in enumerate(width_points)
    )
    width_xy = model_points_in_view(
        adapter, front, [tuple(v / 1000.0 for v in point) for point in width_points],
        label="overall width vertices",
    )
    width = add_edge_dimension(
        adapter, front, p0=width_xy[0], p1=width_xy[1],
        text_xy=OVERALL_WIDTH_TEXT_XY, label="rocker overall width",
        orientation="horizontal", entities=vertices, entity_types=("VERTEX", "VERTEX"),
    )
    width = _early_bound(width, "IDisplayDimension")
    width_annotation = _early_bound(width.GetAnnotation(), "IAnnotation")
    if width_annotation is None:
        raise RuntimeError("rocker overall width has no native annotation")
    assert_dimension_measures(
        adapter, width, expected_mm=2.0 * ROD_TIP_X, label="rocker overall width",
        entities=vertices, entity_types=("VERTEX", "VERTEX"),
    )
    # Overall span is derived from the controlled profile, not a second size band.
    set_reference_dimension(adapter, width_annotation, label="rocker overall width")
    pivot = visible_circle_edge(adapter, front, PIVOT_HOLE_DIA)
    taper_point = (BOT_END_X, _BOT_END_Y, ARM_THICKNESS / 2.0)
    taper = edges.exact_vertex_at(taper_point, label="+Z taper/lower-arc intersection")
    taper_xy, pivot_xy = model_points_in_view(
        adapter, front,
        [tuple(v / 1000.0 for v in taper_point), (0.0, PIVOT_MID_Y / 1000.0, 0.0)],
        label="taper intersection and pivot mirror axis",
    )
    taper_dimension = add_edge_dimension(
        adapter, front, p0=pivot_xy, p1=taper_xy,
        text_xy=TAPER_INTERSECTION_TEXT_XY, label="taper intersection X",
        orientation="horizontal", entities=(pivot, taper),
        entity_types=("EDGE", "VERTEX"),
    )
    set_arc_endpoints_to_center(adapter, taper_dimension, label="taper mirror-axis origin")
    assert_dimension_measures(
        adapter, taper_dimension, expected_mm=BOT_END_X, label="taper intersection X",
        entities=(pivot, taper), entity_types=("EDGE", "VERTEX"),
    )
    # The taper's foot is a J↔K profile station: BASIC, the zone is its band.
    set_basic_dimension(adapter, taper_dimension, label="taper intersection X")
    taper_dimension = _early_bound(taper_dimension, "IDisplayDimension")
    taper_dimension.SetText(4, TAPER_LABEL)
    if str(taper_dimension.GetText(4) or "") != TAPER_LABEL:
        raise RuntimeError("taper endpoint identity label did not persist")
    taper_dimension.MaxWitnessLineLength = TAPER_WITNESS_LENGTH
    if (not _native_finite_scalar(taper_dimension.MaxWitnessLineLength)
            or abs(taper_dimension.MaxWitnessLineLength - TAPER_WITNESS_LENGTH) > 1e-9):
        raise RuntimeError("132.76 retained full-height witnesses through parent E")
    # The mirrored left taper vertex gets its own BASIC row from A: the same
    # J↔K profile station as the right one.
    left_taper_point = (-BOT_END_X, _BOT_END_Y, ARM_THICKNESS / 2.0)
    left_taper = edges.exact_vertex_at(
        left_taper_point, label="+Z left taper/lower-arc intersection"
    )
    (left_taper_xy,) = model_points_in_view(
        adapter, front, [tuple(v / 1000.0 for v in left_taper_point)],
        label="left taper intersection",
    )
    left_taper_dimension = add_edge_dimension(
        adapter, front, p0=pivot_xy, p1=left_taper_xy,
        text_xy=LEFT_TAPER_TEXT_XY, label="left taper intersection X",
        orientation="horizontal", entities=(pivot, left_taper),
        entity_types=("EDGE", "VERTEX"),
    )
    set_arc_endpoints_to_center(adapter, left_taper_dimension, label="left taper mirror-axis origin")
    assert_dimension_measures(
        adapter, left_taper_dimension, expected_mm=BOT_END_X, label="left taper intersection X",
        entities=(pivot, left_taper), entity_types=("EDGE", "VERTEX"),
    )
    set_basic_dimension(adapter, left_taper_dimension, label="left taper intersection X")
    left_taper_dimension = _early_bound(left_taper_dimension, "IDisplayDimension")
    left_taper_dimension.SetText(4, TAPER_LABEL)
    if str(left_taper_dimension.GetText(4) or "") != TAPER_LABEL:
        raise RuntimeError("left taper endpoint identity label did not persist")
    left_taper_dimension.MaxWitnessLineLength = TAPER_WITNESS_LENGTH
    if (not _native_finite_scalar(left_taper_dimension.MaxWitnessLineLength)
            or abs(left_taper_dimension.MaxWitnessLineLength - TAPER_WITNESS_LENGTH) > 1e-9):
        raise RuntimeError("left 132.76 retained full-height witnesses")
    land_entities = (pivot, vertices[1])
    land_dimension = add_edge_dimension(
        adapter, front, p0=pivot_xy, p1=width_xy[1],
        text_xy=LAND_LOCATION_TEXT_XY, label="tip land X location",
        orientation="horizontal", entities=land_entities, entity_types=("EDGE", "VERTEX"),
    )
    set_arc_endpoints_to_center(adapter, land_dimension, label="tip land X location")
    land_dimension = _early_bound(land_dimension, "IDisplayDimension")
    model = _early_bound(land_dimension.GetDimension2(0), "IDimension")
    if model.GetArcEndCondition(1) != 1:
        raise RuntimeError("tip land X location: physical A endpoint must be centred")
    assert_dimension_measures(
        adapter, land_dimension, expected_mm=ROD_TIP_X, label="tip land X location",
        entities=land_entities, entity_types=("EDGE", "VERTEX"),
    )
    set_basic_dimension(adapter, land_dimension, label="tip land X location")
    land_dimension.SetText(4, LAND_LABEL)
    if str(land_dimension.GetText(4) or "") != LAND_LABEL:
        raise RuntimeError("tip land X location: native label did not persist")
    land_dimension.MaxWitnessLineLength = TAPER_WITNESS_LENGTH
    if (not _native_finite_scalar(land_dimension.MaxWitnessLineLength)
            or abs(land_dimension.MaxWitnessLineLength - TAPER_WITNESS_LENGTH) > 1e-9):
        raise RuntimeError("tip land X location retained full-height witnesses")
    # The J land's own BASIC row from A: the K land's mirror, on the view.
    left_land_entities = (pivot, vertices[0])
    left_land_dimension = add_edge_dimension(
        adapter, front, p0=pivot_xy, p1=width_xy[0],
        text_xy=LEFT_LAND_LOCATION_TEXT_XY, label="left tip land X location",
        orientation="horizontal", entities=left_land_entities, entity_types=("EDGE", "VERTEX"),
    )
    set_arc_endpoints_to_center(adapter, left_land_dimension, label="left tip land X location")
    left_land_dimension = _early_bound(left_land_dimension, "IDisplayDimension")
    if _early_bound(left_land_dimension.GetDimension2(0), "IDimension").GetArcEndCondition(1) != 1:
        raise RuntimeError("left tip land X location: physical A endpoint must be centred")
    assert_dimension_measures(
        adapter, left_land_dimension, expected_mm=ROD_TIP_X, label="left tip land X location",
        entities=left_land_entities, entity_types=("EDGE", "VERTEX"),
    )
    set_basic_dimension(adapter, left_land_dimension, label="left tip land X location")
    left_land_dimension.SetText(4, LAND_LABEL)
    if str(left_land_dimension.GetText(4) or "") != LAND_LABEL:
        raise RuntimeError("left tip land X location: native label did not persist")
    left_land_dimension.MaxWitnessLineLength = TAPER_WITNESS_LENGTH
    if (not _native_finite_scalar(left_land_dimension.MaxWitnessLineLength)
            or abs(left_land_dimension.MaxWitnessLineLength - TAPER_WITNESS_LENGTH) > 1e-9):
        raise RuntimeError("left tip land X location retained full-height witnesses")
    return annotations, taper_dimension, (pivot, taper), land_dimension, land_entities


def _add_pin_coordinates(adapter: Any, front: Any) -> None:
    """Two centred native circular endpoints locate the pin from physical A."""
    pivot_bore_edge = visible_circle_edge(adapter, front, PIVOT_HOLE_DIA)
    rod_hole_edge = visible_circle_edge(adapter, front, _ROD_HOLE_DIA)
    pivot_xy, rod_xy = _project(
        adapter, front,
        ((0.0, PIVOT_MID_Y / 1000.0, 0.0),
         (ROD_HOLE_X / 1000.0, ROD_HOLE_Y / 1000.0, 0.0)),
        label="physical A and rod-pin axes",
    )
    for axis, orientation, expected, text_xy in (
        ("X", "horizontal", ROD_HOLE_X, PIN_X_TEXT_XY),
        ("Y", "vertical", ROD_HOLE_Y - PIVOT_MID_Y, PIN_Y_TEXT_XY),
    ):
        label = f"rod-pin {axis} location"
        dimension = add_edge_dimension(
            adapter, front, p0=pivot_xy, p1=rod_xy, text_xy=text_xy,
            label=label, orientation=orientation, entities=(pivot_bore_edge, rod_hole_edge),
        )
        set_arc_endpoints_to_center(adapter, dimension, label=label)
        model = _early_bound(_early_bound(dimension, "IDisplayDimension").GetDimension2(0), "IDimension")
        if any(int(model.GetArcEndCondition(index)) != 1 for index in (1, 2)):
            raise RuntimeError(f"{label}: both physical bore endpoints must be centred")
        assert_dimension_measures(
            adapter, dimension, expected_mm=expected, label=label,
            entities=(pivot_bore_edge, rod_hole_edge),
        )
        set_basic_dimension(adapter, dimension, label=label)
        display = _early_bound(dimension, "IDisplayDimension")
        display.SetText(4, "PIN AXIS")
        if str(display.GetText(4) or "") != "PIN AXIS":
            raise RuntimeError(f"{label}: native PIN AXIS label did not persist")


def _require_land_location(
    adapter: Any, views: Any, dimension: Any, entities: tuple[Any, Any],
) -> None:
    """Recheck the K land's front-view BASIC locator after the final rebuild."""
    display = _early_bound(dimension, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    name = dimension_name(adapter, annotation)
    if not name:
        raise RuntimeError("tip land X location has no native dimension name")
    owners = [
        label for label, view in views
        for candidate in _bound_view_annotations(view, label=f"rocker {label}")
        if dimension_name(adapter, candidate) == name
    ]
    if owners != ["front"]:
        raise RuntimeError(f"tip land X location census owners {owners!r}, expected ['front']")
    assert_dimension_measures(
        adapter, display, expected_mm=ROD_TIP_X, label="tip land X location",
        entities=entities, entity_types=("EDGE", "VERTEX"),
    )
    model = _early_bound(display.GetDimension2(0), "IDimension")
    if (model.GetArcEndCondition(1) != 1
            or model.GetToleranceType() != 1
            or display.ShowDimensionValue is not True
            or str(display.GetText(4) or "") != LAND_LABEL
            or any(str(display.GetText(part) or "") for part in (1, 2))
            or not _native_finite_scalar(display.MaxWitnessLineLength)
            or abs(display.MaxWitnessLineLength - TAPER_WITNESS_LENGTH) > 1e-9):
        raise RuntimeError("tip land X location lost its centred BASIC label/value or witness cap")


def _require_rod_through_callout(callout: Any) -> None:
    """Read actual Hole Wizard ink, not unsupported GetText compartments."""
    display = _early_bound(callout, "IDisplayDimension")
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    if data is None:
        raise RuntimeError("detail E rod-pin callout has no native rendered display data")
    count = data.GetTextCount()
    if type(count) is not int or count <= 0:
        raise RuntimeError(f"detail E rod-pin callout has invalid native rendered text count: {count!r}")
    texts = tuple(data.GetTextAtIndex(index) for index in range(count))
    if any(type(text) is not str for text in texts):
        raise RuntimeError(f"detail E rod-pin callout has unreadable native rendered text: {texts!r}")
    native_text = " ".join(texts)
    _telemetry.info(f"detail E rod-pin callout: actual_native_rendered_text={native_text!r}, required='THRU'")
    if "THRU" not in native_text.upper():
        raise RuntimeError(f"detail E rod-pin callout lost its native through condition: {native_text!r}")


def _require_ream_clearance(
    adapter: Any, hub: Any, notes_box: tuple[float, float, float, float],
) -> None:
    """Prove actual native REAM text clears D and the seated notes by 1 mm."""
    reader = _Reader(adapter)
    annotations = _bound_view_annotations(hub, label="detail D REAM")
    matches = [ann for ann in annotations if dimension_name(adapter, ann) == "PivotDia"]
    if len(matches) != 1:
        raise RuntimeError("detail D: expected one native pivot REAM dimension")
    record = _dump_annotation(reader, matches[0])
    errors = reader.take_errors()
    if record is None or errors:
        raise RuntimeError(f"detail D: cannot measure native REAM text: {errors!r}")
    geometry = _arc_callout_geometry(record, calibrate_sheet_advance([record]))
    crop = Box(*_detail_crop(adapter, hub, label="D"))
    notes = Box(*notes_box)
    for box in geometry.text_boxes:
        for label, obstacle in (("D crop", crop), ("seated notes", notes)):
            gap = _box_air(box, obstacle)
            detail = f"detail D REAM: requested_xy_mm={tuple(v * 1000.0 for v in HUB_KEEP['PivotDia'])}, actual_GetPosition={record.get('pos')}, text_ink={box.format_mm()}, obstacle={label}:{obstacle.format_mm()}, actual_air_mm={gap * 1000.0:.3f}, required_air_mm=1.000"
            _telemetry.info(detail)
            if gap < 0.001 - 1e-12:
                raise RuntimeError(detail)


def _box_air(box: Box, obstacle: Box) -> float:
    return math.hypot(
        max(obstacle.xmin - box.xmax, box.xmin - obstacle.xmax, 0.0),
        max(obstacle.ymin - box.ymax, box.ymin - obstacle.ymax, 0.0),
    )


def _require_front_detail_air(adapter: Any, front: Any, hub: Any, end: Any) -> None:
    """Every actual front-callout text box clears both settled detail crops."""
    reader = _Reader(adapter)
    records = [_dump_annotation(reader, ann)
               for ann in _bound_view_annotations(front, label="front/detail text air")]
    errors = reader.take_errors()
    if not records or any(record is None for record in records) or errors:
        raise RuntimeError(f"front/detail text air cannot be measured: {errors!r}")
    advance = calibrate_sheet_advance(records)
    obstacles = (("D", Box(*_detail_crop(adapter, hub, label="D"))),
                 ("E", Box(*_detail_crop(adapter, end, label="E"))))
    checked_boxes = 0
    for record in records:
        if record.get("visible") in (2, 3) or record.get("type") in (13, 15):
            continue
        geometry = _arc_callout_geometry(record, advance)
        for box in geometry.text_boxes:
            checked_boxes += 1
            for label, obstacle in obstacles:
                air = _box_air(box, obstacle)
                detail = f"front {record.get('name')!r}: actual_GetPosition={record.get('pos')}, native_text_bbox_mm={box.format_mm()}, detail_{label}_crop_mm={obstacle.format_mm()}, actual_air_mm={air * 1000.0:.3f}, required_air_mm=1.000"
                _telemetry.info(detail)
                if air < 0.001 - 1e-12:
                    raise RuntimeError(detail)
    if checked_boxes == 0:
        raise RuntimeError("front/detail text air: no visible native callout text was checked")
    _telemetry.info(f"front/detail text air: checked_text_boxes={checked_boxes}, detail_crops=2, required_air_mm=1.000")


def _require_radius_exterior(adapter: Any, front: Any) -> None:
    """Native projected parent circles, not front-only scale predictions."""
    reader = _Reader(adapter)
    annotations = _bound_view_annotations(front, label="BASIC radius parent circles")
    centre, top_rim, bottom_rim = _project(
        adapter, front,
        ((0.0, CENTER_Y / 1000.0, 0.0),
         (R_TOP / 1000.0, CENTER_Y / 1000.0, 0.0),
         (R_BOTTOM / 1000.0, CENTER_Y / 1000.0, 0.0)),
        label="BASIC radius parent circles",
    )
    for name, rim in (("TopRadius", top_rim), ("BottomRadius", bottom_rim)):
        matches = [ann for ann in annotations if dimension_name(adapter, ann) == name]
        if len(matches) != 1:
            raise RuntimeError(f"{name}: expected one native BASIC radius")
        record = _dump_annotation(reader, matches[0])
        errors = reader.take_errors()
        if record is None or errors:
            raise RuntimeError(f"{name}: cannot measure native BASIC radius ink: {errors!r}")
        radius = math.dist(centre, rim)
        if not math.isfinite(radius) or radius <= 0.0:
            raise RuntimeError(f"{name}: invalid native projected circle radius={radius!r}")
        geometry = _arc_callout_geometry(record, calibrate_sheet_advance([record]))
        for box in geometry.text_boxes:
            distance = math.hypot(
                max(box.xmin - centre[0], centre[0] - box.xmax, 0.0),
                max(box.ymin - centre[1], centre[1] - box.ymax, 0.0),
            )
            detail = f"{name}: requested_xy_mm={tuple(v * 1000.0 for v in FRONT_KEEP[name])}, actual_GetPosition={record.get('pos')}, native_text_bbox_mm={box.format_mm()}, native_circle_centre={centre}, native_circle_radius_mm={radius * 1000.0:.3f}, actual_exterior_air_mm={(distance - radius) * 1000.0:.3f}, required_exterior_air_mm=0.000"
            _telemetry.info(detail)
            if distance <= radius:
                raise RuntimeError(detail)


def _dress_hub_root(adapter: Any, annotations: list[Any]) -> None:
    """Prove view F's HubRootRadius prints the part's 2X R MAX and stop its
    leader at the arc (draw_ch_pivot_bracket._dress_corner_radius)."""
    found = [ann for ann in annotations if dimension_name(adapter, ann) == "HubRootRadius"]
    if len(found) != 1:
        raise RuntimeError(f"view F must import one HubRootRadius, found {len(found)}")
    display = _early_bound(found[0].GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported hub root radius is not radial")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != rocker_notes.HUB_ROOT_R_TOL_TYPE:
        raise RuntimeError(f"HubRootRadius lost its native MAX type: {int(tolerance.Type)}")
    if not math.isclose(float(dimension.SystemValue), rocker.HUB_ROOT_RADIUS_MAX / 1000.0, abs_tol=1e-9):
        raise RuntimeError("HubRootRadius does not measure the hub root fillet")
    if str(display.GetText(1) or "") != rocker_notes.HUB_ROOT_PREFIX:
        raise RuntimeError("hub root radius lost its part-owned 2X")
    display.ArcExtensionLineOrOppositeSide = False
    if bool(display.ArcExtensionLineOrOppositeSide):
        raise RuntimeError("HubRootRadius leader still runs to the opposite side")


def _select_view_dimension(adapter: Any, view: Any, annotation: Any, *, label: str) -> tuple[Any, Any]:
    """Re-resolve one imported dimension in ``view`` and select it alone.

    draw_fr_top_frame._crossbar_median_datum's recipe: the view's own display
    dimension (same selection name and FullName), selected on the documented
    DIMENSION channel and read back as one swSelDIMENSIONS item.
    """
    wanted = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    name = str(wanted.GetNameForSelection() or "")
    full_name = str(_early_bound(wanted.GetDimension2(0), "IDimension").FullName or "")
    if not name or not full_name:
        raise RuntimeError(f"{label}: dimension has no selection name / FullName")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    where = view_name(adapter, view)
    if not _early_bound(model, "IDrawingDoc").ActivateView(where):
        raise RuntimeError(f"{label}: failed to activate {where}")
    model.ClearSelection2(True)
    matches = [
        display for display in (
            _early_bound(raw, "IDisplayDimension")
            for raw in _early_bound(view, "IView").GetDisplayDimensions() or ()
        )
        if display.GetNameForSelection() == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected one {name!r} in {where}, found {len(matches)}")
    display = matches[0]
    dimension_annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if (int(dimension_annotation.GetType()) != 4  # swDisplayDimension
            or str(_early_bound(display.GetDimension2(0), "IDimension").FullName) != full_name):
        raise RuntimeError(f"{label}: {name!r} re-resolved to another dimension")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    if extension.SelectByID2(name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0) is not True:
        raise RuntimeError(f"{label}: failed to select {name!r}")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    count = int(selection.GetSelectedObjectCount2(-1))
    kind = int(selection.GetSelectedObjectType3(count, -1)) if count else 0
    picked = selection.GetSelectedObject6(count, -1) if count else None
    if (count != 1 or kind != 14 or picked is None  # swSelDIMENSIONS
            or _early_bound(picked, "IDisplayDimension").GetNameForSelection() != name):
        model.ClearSelection2(True)
        raise RuntimeError(f"{label}: selecting {name!r} gave {count} object(s) of type {kind}")
    return display, dimension_annotation


def _attach_to_dimension(
    adapter: Any, annotation: Any, display: Any, dimension_annotation: Any, *, label: str,
) -> None:
    """Hold ``annotation`` on the selected dimension, then prove it after a rebuild.

    InsertDatumTag2 on a selected dimension leaves the tag attached to nothing
    (draw_fr_top_frame, runs 20261009T155421516Z and 20261014T032231012Z);
    IAnnotation::SetAttachedEntities takes the display dimension, else its
    annotation. The proof is one swSelDIMENSIONS attachment that IS it.
    """
    attempts = []
    if int(annotation.GetAttachedEntityCount3()) == 0:
        for kind, target in (("display_dimension", display), ("annotation", dimension_annotation)):
            accepted = bool(annotation.SetAttachedEntities(dispatch_array([target])))
            attached = int(annotation.GetAttachedEntityCount3())
            attempts.append(f"{kind}:{accepted}:{attached}")
            if accepted and attached:
                break
    adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label=label)
    kinds = tuple(int(value) for value in annotation.GetAttachedEntityTypes() or ())
    entities = tuple(annotation.GetAttachedEntities3() or ())
    _telemetry.info(f"{label}: attach attempts={attempts}, types={kinds}")
    if kinds != (14,) or len(entities) != 1 or entities[0] is None or annotation.IsDangling():
        raise RuntimeError(f"{label}: not attached to its dimension: types={kinds}, attempts={attempts}")
    attached = _early_bound(entities[0], "IDisplayDimension")
    if int(adapter.swApp.IsSame(attached, display)) != 1:
        raise RuntimeError(f"{label}: attached to another dimension")


def _dimension_position_frame(
    adapter: Any, view: Any, size: Any, *, label: str, tolerance: str,
    datums: tuple[str, ...], diameter: bool = False,
) -> Any:
    """A native position frame on the selected size dimension, never a
    leader to one face; read back before and after its attaching rebuild."""
    xml = gtol_frame_xml("position", tolerance, datums=datums, diameter=diameter)
    expected = gtol_frame_signature(xml)
    display, dimension_annotation = _select_view_dimension(adapter, view, size, label=label)
    raw = adapter.currentModel.InsertGtol()
    if raw is None:
        raise RuntimeError(f"{label}: InsertGtol returned nothing")
    gtol = _early_bound(raw, "IGtol")
    if int(gtol.GetFrameCount() or 0) == 0 and gtol.AddFrame() is not True:
        raise RuntimeError(f"{label}: failed to create a frame")
    frame = gtol.GetFrame(1)
    if frame is None:
        # An old-format empty frame from the template: seed, then convert
        # (_drawing_gdt.add_feature_control_frame's migration order).
        gtol.SetFrameSymbols2(1, f"<{GTOL_SYMBOLS['position']}>", diameter, "", False, "", "", "", "")
        if gtol.SetFrameValues2(1, tolerance, "", *[*datums, "", ""][:3]) is not True:
            raise RuntimeError(f"{label}: failed to seed the frame for migration")
        if gtol.CanConvertFormat() is not True or int(gtol.ConvertFormat()) != 0:
            raise RuntimeError(f"{label}: frame migration failed")
        frame = _early_bound(gtol.GetFrame(1), "IGtolFrame")
    else:
        frame = _early_bound(frame, "IGtolFrame")
        if frame.SetSymbolXml(xml) is not True:
            raise RuntimeError(f"{label}: SOLIDWORKS rejected the frame XML")
    if gtol_frame_signature(str(frame.GetSymbolXml() or "")) != expected or int(gtol.GetFormat()) != 2:
        raise RuntimeError(f"{label}: frame did not persist: {frame.GetSymbolXml()!r}")
    _attach_to_dimension(
        adapter, _early_bound(gtol.GetAnnotation(), "IAnnotation"), display,
        dimension_annotation, label=label,
    )
    applied = _early_bound(gtol.GetFrame(1), "IGtolFrame").GetSymbolXml()
    if gtol_frame_signature(str(applied or "")) != expected:
        raise RuntimeError(f"{label}: frame changed after rebuild: {applied!r}")
    return gtol


def _strap_position_frame(adapter: Any, view: Any, strap_thickness: Any) -> Any:
    """Position the strap width's centre plane to G under its 2.500 size
    (#948 ruling R's symmetry), at the BASIC from G view F prints
    (_hub_face_basic)."""
    return _dimension_position_frame(
        adapter, view, strap_thickness, label="strap position to G",
        tolerance=GEOMETRIC_TOLERANCES_IN["strap position to hub"],
        datums=tuple(STRAP_FACES.fields["position_datums"][0]),
    )


# View F's one centreline: the strap's centre plane (model Z = 0), from just
# under the bottom arc's midpoint to just over the top-arc ends. The strap
# frame's ⌖0.10|G locates that plane, so its BASIC from G (the hub's -Z end
# face) is dimensioned to this line (#1579: reviews read the frame with no
# basic as a defect, drawing-guidelines.md's complete-frame rule).
CENTRE_PLANE_OVERSHOOT_MM = 1.0
CENTRE_PLANE_Y_MM = (-CENTRE_PLANE_OVERSHOOT_MM, TOP_END_Y + CENTRE_PLANE_OVERSHOOT_MM)
CENTRE_PLANE_READBACK_TOL = 1e-9


def _strap_centre_plane(adapter: Any, view: Any) -> Any:
    """Draw the strap's centre plane through the hub and the strap in view
    F, direct to the database (an inferred end snaps onto nearby ink), and
    read its ends and black colour back."""
    label = "view F hub/strap centre plane"
    draw = adapter.currentModel
    view_f = view_name(adapter, view)
    if _early_bound(draw, "IDrawingDoc").ActivateView(view_f) is not True:
        raise RuntimeError(f"{label}: cannot activate view F")
    draw.ClearSelection2(True)
    ends = tuple((0.0, y / 1000.0, 0.0) for y in CENTRE_PLANE_Y_MM)
    sheet_points = _project(adapter, view, ends, label=label)
    mapped = _sheet_points_in_sketch(
        adapter, view, sheet_points, label=label, kind="centreline", owner="view F"
    )
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateCenterLine(*mapped[0], *mapped[1])
    finally:
        manager.AddToDB = previous
    if segment is None:
        raise RuntimeError(f"{label}: CreateCenterLine returned nothing")
    line = _early_bound(segment, "ISketchLine")
    for expected, accessor in zip(mapped, ("GetStartPoint2", "GetEndPoint2")):
        point = _early_bound(getattr(line, accessor)(), "ISketchPoint")
        actual = tuple(float(getattr(point, axis)) for axis in ("X", "Y", "Z"))
        drift = max(abs(a - b) for a, b in zip(actual, expected, strict=True))
        if drift > CENTRE_PLANE_READBACK_TOL:
            raise RuntimeError(
                f"{label}: {accessor} sits at {actual}, not the authored {expected}"
            )
    segment = _early_bound(segment, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError(f"{label}: black colour did not persist")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=label)
    return segment


# G's BASIC: the -Z hub face to the strap's centre plane, both off the face
# requirements (the half hub length, 3.52825, printed at its places).
HUB_FACE_BASIC_MM = (
    STRAP_FACES.fields["upper_z"][0] + STRAP_FACES.fields["lower_z"][0]
) / 2.0 - HUB_FACES.fields["lower_z"][0]
_SEL_EDGES = 1  # swSelectType_e.swSelEDGES


def _hub_face_datum_g(
    adapter: Any,
    view: Any,
    centre_plane: Any,
    hub_length: Any,
) -> tuple[Any, Any]:
    """Datum G on the hub's -Z end face, its BASIC to the strap's centre
    plane, then both read back from their printed ink."""
    label = "hub -Z end face datum G"
    face_z = HUB_FACES.fields["lower_z"][0]
    face = (
        scan_view_edges(view, label="view F hub -Z end face")
        .circle_at(
            (0.0, rocker_interface.PIVOT_MID_Y, face_z),
            rocker.HUB_DIA / 2.0,
            axis=(0.0, 0.0, 1.0),
            label=label,
        )
        .edge
    )
    landing, plane_point = _project(
        adapter,
        view,
        (
            (0.0, HUB_FACE_DATUM_LANDING_Y_MM / 1000.0, face_z / 1000.0),
            (0.0, HUB_FACE_DATUM_LANDING_Y_MM / 1000.0, 0.0),
        ),
        label=f"{label} landing",
    )
    tag = _hub_face_datum(adapter, view, face, landing)
    basic = _hub_face_basic(
        adapter, view, centre_plane, face, picks=(plane_point, landing)
    )
    _assert_hub_face_datum_clear(
        adapter,
        tag,
        {"G BASIC": basic.GetAnnotation(), "hub width": hub_length},
        face_x=landing[0],
        label=label,
    )
    return tag, basic


def _hub_face_datum(
    adapter: Any,
    view: Any,
    face: Any,
    landing: tuple[float, float],
) -> Any:
    """Datum G's tag on the hub's -Z end face, picked by the face's own rim
    (edge-on in view F), its triangle landed on the face's lower half and
    proved there from ink, its box straight out right."""
    return add_datum_feature(
        adapter,
        view,
        edge_entity=face,
        leader_attach_xy=landing,
        symbol_xy=(landing[0] + HUB_FACE_DATUM_STANDOFF_M, landing[1]),
        datum=HUB_FACES.fields["datum"][0],
        label="hub -Z end face datum G",
    )


def _hub_face_basic(
    adapter: Any,
    view: Any,
    centre_plane: Any,
    face: Any,
    *,
    picks: tuple[tuple[float, float], tuple[float, float]],
) -> Any:
    """The BASIC from G to the strap's centre plane: view F's centreline to
    the -Z face's rim, each picked by entity, boxed at the hub length's places.

    The +Z face stands the same distance off the centreline, so the value
    alone cannot tell the faces apart: the one attached edge must BE the -Z
    rim (IsSame), beside one other attachment, the centreline.
    """
    label = "datum G to strap centre plane BASIC"
    display = _early_bound(
        add_edge_dimension(
            adapter,
            view,
            p0=picks[0],
            p1=picks[1],
            text_xy=HUB_FACE_BASIC_TEXT_XY,
            label=label,
            orientation="horizontal",
            entity_types=("SKETCHSEGMENT", "EDGE"),
            entities=(centre_plane, face),
        ),
        "IDisplayDimension",
    )
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    entities = tuple(annotation.GetAttachedEntities3() or ())
    types = tuple(int(kind) for kind in annotation.GetAttachedEntityTypes() or ())
    edges = [item for item, kind in zip(entities, types) if kind == _SEL_EDGES]
    dangling = bool(annotation.IsDangling())
    if (
        len(entities) != 2
        or len(types) != 2
        or len(edges) != 1
        or dangling
        or not _is_same_attachment(adapter, edges[0], face, "EDGE")
    ):
        raise RuntimeError(
            f"{label}: not the dimension from the centreline to the -Z face: "
            f"entities={len(entities)}, types={types}, dangling={dangling}"
        )
    assert_dimension_measures(
        adapter, display, expected_mm=HUB_FACE_BASIC_MM, label=label
    )
    places = HUB_FACES.precision["length"]
    display.SetPrecision3(places, -1, -1, -1)  # -1: swDoNotChangePrecisionSetting
    if display.GetPrimaryPrecision2() != places:
        raise RuntimeError(f"{label}: did not take {places} places")
    set_basic_dimension(adapter, display, label=label)
    return display


def _assert_hub_face_datum_clear(
    adapter: Any,
    tag: Any,
    neighbours: dict[str, Any],
    *,
    face_x: float,
    label: str,
) -> Box:
    """Read G back from its printed ink, as the layout audit measures it, and
    fail unless it stands where it was put.

    Its letter must stand out right of the -Z face and short of the front
    view's 132.8 left witness, ARROW_TEXT_CLEARANCE_M clear of each
    neighbour's arrows (``find_arrows_near_text``'s arrow and outside-arrow
    tail segments) and text, its triangle as clear of their text, every
    neighbour's text short of that witness, and the tag still attached. The
    hub-width tag G replaces rebuilt 1.89 mm onto an arrow from a placement
    main printed clear (run 20261017T024838726Z), and an edge-attached tag
    re-solves along its edge (add_datum_feature), so no unread placement ships.
    """
    tag_annotation = _early_bound(tag.GetAnnotation(), "IAnnotation")
    if tag_annotation.IsDangling():
        raise RuntimeError(f"{label}: dangling after its placement")
    names = list(neighbours)
    reader = _Reader(adapter)
    records = [
        _dump_annotation(reader, tag_annotation),
        *(_dump_annotation(reader, neighbours[name]) for name in names),
    ]
    errors = reader.take_errors()
    if any(record is None for record in records) or errors:
        raise RuntimeError(f"{label}: cannot measure its ink: {errors!r}")
    advance = calibrate_sheet_advance(records)
    datum, *others = (
        annotation_geometry(record, owner="right", advance=advance)
        for record in records
    )
    letter = union_boxes(list(datum.text_boxes)) if datum is not None else None
    if letter is None or any(other is None for other in others):
        raise RuntimeError(f"{label}: no printed letter or neighbour to measure")
    triangle = [segment for segment in datum.segments if segment.role == "arrow"]
    witness = FRONT_LEFT_WITNESS_X - ARROW_TEXT_CLEARANCE_M
    problems = []
    if letter.xmin - face_x < ARROW_TEXT_CLEARANCE_M:
        problems.append("letter not out right of the -Z face")
    if letter.xmax > witness:
        problems.append("letter runs onto the front view's left witness")
    readings = [
        f"letter_mm={letter.format_mm()}",
        f"face_x={face_x:.5f}",
        f"xmax_limit={witness:.5f}",
    ]
    for name, geometry in zip(names, others):
        arrows = [
            *(segment for segment in geometry.segments if segment.role == "arrow"),
            *getattr(geometry, "arrow_tails", ()),
        ]
        gap = min(
            (segment_box_distance(segment, letter) for segment in arrows),
            default=math.inf,
        )
        text_air = min(
            (_box_air(letter, box) for box in geometry.text_boxes), default=math.inf
        )
        crowding = min(
            (
                segment_box_distance(segment, box)
                for segment in triangle
                for box in geometry.text_boxes
            ),
            default=math.inf,
        )
        readings.append(
            f"{name}: arrow_gap_mm={gap * 1000.0:.3f}, text_air_mm={text_air * 1000.0:.3f}, "
            f"triangle_air_mm={crowding * 1000.0:.3f}"
        )
        if min(gap, text_air, crowding) < ARROW_TEXT_CLEARANCE_M:
            problems.append(f"crowds the {name}")
        if any(box.xmax > witness for box in geometry.text_boxes):
            problems.append(f"the {name} text runs onto the front view's left witness")
    detail = f"{label}: " + "; ".join(readings)
    _telemetry.info(detail)
    if problems:
        raise RuntimeError(f"{label}: {', '.join(problems)}: {detail}")
    return letter


def _hub_position_frame(adapter: Any, hub: Any, hub_dia: Any) -> Any:
    """Position the hub OD's axis to A under its Ø10.20 in detail D: the
    zone the hub wall minimum is computed with (regate-r1 #2, not a note)."""
    return _dimension_position_frame(
        adapter, hub, hub_dia, label="hub OD position to A",
        tolerance=GEOMETRIC_TOLERANCES_IN["hub OD position to bore"],
        datums=tuple(HUB_OD.fields["position_datums"][0]), diameter=True,
    )


def _add_between_points(adapter: Any, front: Any) -> dict[str, Any]:
    """Point J and K at the top-arc ends: the lower profile's two limits."""
    corners = _project(
        adapter, front,
        ((-TOP_END_X / 1000.0, TOP_END_Y / 1000.0, 0.0),
         (TOP_END_X / 1000.0, TOP_END_Y / 1000.0, 0.0)),
        label="profile J/K top-arc ends",
    )
    if not corners[0][0] < corners[1][0]:
        raise RuntimeError(f"profile J/K: -X end does not print left of +X: {corners!r}")
    notes = {}
    for letter, corner in zip(PROFILE_BETWEEN, corners):
        dx, dy = BETWEEN_POINT_OFFSET[letter]
        notes[letter] = add_leader_note(
            adapter, letter, text_xy=(corner[0] + dx, corner[1] + dy),
            attach_xy=corner, label=f"profile limit {letter}", view=front,
        )
    return notes


def _set_profile_between(adapter: Any, gtol: Any) -> None:
    """Native J↔K between symbol under the lower profile frame, read back."""
    gtol = _early_bound(gtol, "IGtol")
    gtol.SetBetweenTwoPoints(True, *PROFILE_BETWEEN)  # VT_VOID
    rebuild_drawing(adapter, label="lower profile between symbol")
    texts = tuple(str(gtol.GetBetweenTwoPointsText(index) or "") for index in (0, 1))
    if gtol.GetBetweenTwoPoints() is not True or texts != PROFILE_BETWEEN:
        raise RuntimeError(
            f"lower profile between symbol read back {gtol.GetBetweenTwoPoints()!r} "
            f"{texts!r}, expected True {PROFILE_BETWEEN!r}"
        )


def _arc_profile_point(name: str) -> tuple[float, float, float]:
    """Real model point on a supported arc, away from the taper vertex."""
    radius = {"TopRadius": R_TOP, "BottomRadius": R_BOTTOM}[name]
    limit = {"TopRadius": TOP_END_X, "BottomRadius": BOT_END_X}[name]
    x = ARC_PROFILE_PICK_X_MM[name]
    if abs(x) >= limit:
        raise RuntimeError(f"{name}: profile landing lies outside the actual arc domain")
    return (x / 1000.0, (CENTER_Y - math.sqrt(radius**2 - x**2)) / 1000.0, 0.0)


def _add_arc_profiles(adapter: Any, front: Any) -> dict[str, Any]:
    """Attach and retain native frames: Ⓤ0.5 top (its mate below it), Ⓤ0 bottom J↔K, total zone 0.5."""
    profiles = {}
    for name, radius in (("TopRadius", R_TOP), ("BottomRadius", R_BOTTOM)):
        edge = visible_circle_edge(adapter, front, 2.0 * radius)
        (landing,) = _project(adapter, front, (_arc_profile_point(name),), label=f"{name} profile landing")
        profiles[name] = add_feature_control_frame(
            adapter,
            front,
            edge_entity=edge,
            leader_attach_xy=landing,
            frame_xy=ARC_PROFILE_FRAME_XY[name],
            characteristic="profile_surface",
            tolerance=GEOMETRIC_TOLERANCES_IN["top edge surface profile"],
            outside_disposition=ARC_PROFILE_OUTSIDE_TEXT[name],
            datums=ARC_PROFILE_DATUMS,
            # The amplitude bar's foot rides the top edge (rule 4: name the mate).
            quantity=rocker_notes.TOP_EDGE_MATE_CALLOUT if name == "TopRadius" else "",
            label=f"arc-system {name} profile",
        )
    _set_profile_between(adapter, profiles["BottomRadius"])
    _add_between_points(adapter, front)
    return profiles


def _add_view_arrow(adapter: Any, front: Any) -> None:
    """Letter-note viewing arrow naming the 3:1 removed view F.

    The native projected-view arrow is not switchable through the API
    (``IProjectionArrow.Visible`` is get-only; draw_dt_cone_tip_block's C1
    verdict), so a letter note's straight leader is the arrow.
    """
    land_mid = (
        (TOP_END_X + ROD_TIP_X) / 2000.0, (TOP_END_Y + _ROD_TIP_Y) / 2000.0, 0.0,
    )
    ((land_x, land_y),) = _project(adapter, front, (land_mid,), label="view F arrow land")
    tip_xy = (max(land_x, _project(
        adapter, front, ((ROD_TIP_X / 1000.0, _ROD_TIP_Y / 1000.0, 0.0),),
        label="view F arrow rod tip",
    )[0][0]) + VIEW_ARROW_TIP_GAP, land_y)
    letter = rocker_notes.VIEW_ARROW_LETTER
    note = add_leader_note(
        adapter,
        letter,
        text_xy=(VIEW_ARROW_TEXT_X, land_y + VIEW_LETTER_HEIGHT / 2.0),
        attach_xy=tip_xy,
        view=front,
        label=f"view {letter} viewing arrow",
    )
    # add_note leaves text at the document height; size the letter (the
    # draw_dt_cone_tip_block recipe) and prove the leader tip did not move.
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"view {letter} arrow note has no text format")
    text_format.CharHeight = VIEW_LETTER_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size the view {letter} arrow letter")
    rebuild_drawing(adapter, label=f"view {letter} arrow letter")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
        raise RuntimeError(f"view {letter} arrow tip moved when its letter was sized")


def _native_finite_scalar(value: Any) -> bool:
    """Native numbers only: False, strings and coercible objects are not zero."""
    return type(value) in (int, float) and math.isfinite(value)


def _native_finite_row(values: Any) -> bool:
    return type(values) in (list, tuple) and all(_native_finite_scalar(v) for v in values)


def _validate_center_mark_display(display: Any) -> None:
    """Census-only strict row schemas; downstream callout guards stay independent."""
    def count(value: float) -> bool:
        # SAFEARRAY counts become doubles in _dump_display's _round.
        return value >= 0.0 and value == int(value)

    if not isinstance(display, dict):
        raise ValueError(f"invalid native display data={display!r}")
    texts = display.get("texts", ())
    if not isinstance(texts, (list, tuple)):
        raise ValueError(f"invalid native texts collection={texts!r}")
    # Official IDisplayData rows: both line overloads have ten doubles.
    # Empty primitive sets are omitted by the dump; no class must be present.
    lengths = {"lines": 10, "arcs": 17, "arrows": 12, "triangles": 11, "ellipses": 19}
    for key, rows in display.items():
        if key == "texts":
            continue
        if key not in {item[0] for item in _DISPLAY_PRIMITIVES}:
            raise ValueError(f"invalid native display primitive class={key!r}")
        if not isinstance(rows, (list, tuple)):
            raise ValueError(f"invalid native {key} collection={rows!r}")
        for row in rows:
            if not _native_finite_row(row):
                raise ValueError(f"invalid native {key} geometry={row!r}")
            if key in lengths and len(row) != lengths[key]:
                raise ValueError(f"invalid native {key} geometry={row!r}")
            if key == "polylines":
                # GetPolylineAtIndex2 lists seven header values, then N XYZs.
                # DataSize names GeomData but documents no extra payload/offset.
                if (
                    len(row) < 7
                    or row[0] not in (0.0, 1.0)
                    or not count(row[1])
                    or (row[0] == 0.0 and row[1] != 0.0)
                    or not count(row[6])
                    or len(row) != 7 + 3 * int(row[6])
                ):
                    raise ValueError(
                        f"invalid native polylines geometry: header={row[:7]!r}, "
                        f"type={row[0] if row else None!r}, "
                        f"DataSize={row[1] if len(row) > 1 else None!r}, "
                        f"N={row[6] if len(row) > 6 else None!r}, row_length={len(row)}; "
                        f"documented length=7+3*N; type1 GeomData layout unproven; row={row!r}"
                    )
            elif key == "polygons":
                if len(row) < 5 or not count(row[4]) or len(row) != 5 + 3 * int(row[4]):
                    raise ValueError(f"invalid native polygons geometry={row!r}")


def _arc_callout_geometry(record: dict[str, Any], advance: float) -> Any:
    """Validate required native data before the audit's tolerant geometry parser."""
    def finite_scalar(value: Any) -> bool:
        # The dump contains actual numbers, not bools or float-coercible objects.
        return type(value) in (int, float) and math.isfinite(value)

    def finite_row(values: Any) -> bool:
        return isinstance(values, (list, tuple)) and all(finite_scalar(v) for v in values)

    def count(value: float) -> bool:
        # SAFEARRAY counts become doubles in _dump_display's _round.
        return value >= 0.0 and value == int(value)

    position = record.get("pos", ())
    if not finite_row(position) or len(position) != 3:
        raise ValueError(f"invalid native GetPosition={position!r}")
    display = record.get("display") or {}
    if not isinstance(display, dict):
        raise ValueError(f"invalid native display data={display!r}")
    texts = display.get("texts", ())
    if not isinstance(texts, (list, tuple)) or not texts:
        raise ValueError("missing native callout text")
    for item in texts:
        if (
            not isinstance(item, dict)
            or type(item.get("t")) is not str
            or not finite_row(item.get("pos"))
            or len(item["pos"]) != 3
            or not finite_scalar(item.get("h")) or item["h"] <= 0.0
            or not finite_scalar(item.get("ang"))
            or type(item.get("ref")) is not int or item["ref"] not in range(6)
            or ("w" in item and (not finite_scalar(item["w"]) or item["w"] < 0.0))
            or ("ls" in item and not finite_scalar(item["ls"]))
        ):
            raise ValueError(f"invalid native text geometry={item!r}")
    if not any(item["t"].strip() for item in texts):
        raise ValueError("missing native callout text")
    # Official IDisplayData rows: both line overloads have ten doubles.
    # Empty primitive sets are omitted by the dump; no class must be present.
    lengths = {"lines": 10, "arcs": 17, "arrows": 12, "triangles": 11, "ellipses": 19}
    for key, rows in display.items():
        if key == "texts":
            continue
        if not isinstance(rows, (list, tuple)):
            raise ValueError(f"invalid native {key} collection={rows!r}")
        for row in rows:
            if not finite_row(row):
                raise ValueError(f"invalid native {key} geometry={row!r}")
            if key in lengths and len(row) != lengths[key]:
                raise ValueError(f"invalid native {key} geometry={row!r}")
            if key == "polylines":
                # GetPolylineAtIndex2 lists seven header values, then N XYZs.
                # DataSize names GeomData but documents no extra payload/offset.
                if (
                    len(row) < 7
                    or row[0] not in (0.0, 1.0)
                    or not count(row[1])
                    or (row[0] == 0.0 and row[1] != 0.0)
                    or not count(row[6])
                    or len(row) != 7 + 3 * int(row[6])
                ):
                    raise ValueError(
                        f"invalid native polylines geometry: header={row[:7]!r}, "
                        f"type={row[0] if row else None!r}, "
                        f"DataSize={row[1] if len(row) > 1 else None!r}, "
                        f"N={row[6] if len(row) > 6 else None!r}, row_length={len(row)}; "
                        f"documented length=7+3*N; type1 GeomData layout unproven; row={row!r}"
                    )
            elif key == "polygons":
                if len(row) < 5 or not count(row[4]) or len(row) != 5 + 3 * int(row[4]):
                    raise ValueError(f"invalid native polygons geometry={row!r}")
    leaders = record.get("leaders", ())
    if not isinstance(leaders, (list, tuple)):
        raise ValueError(f"invalid native leader collection={leaders!r}")
    for row in leaders:
        # GetLeaderPointsAtIndex: straight/underlined or bent. The dump omits
        # zero-point/no-leader rows; ordinary leader collections may be empty.
        if not finite_row(row) or len(row) not in (6, 9):
            raise ValueError(f"invalid native leader geometry={row!r}")
    geometry = annotation_geometry(record, owner="front", advance=advance)
    if geometry is None or not geometry.text_boxes:
        raise ValueError("missing native callout text bbox")
    for box in geometry.text_boxes:
        if (
            not all(math.isfinite(v) for v in (box.xmin, box.ymin, box.xmax, box.ymax))
            or box.xmin >= box.xmax or box.ymin >= box.ymax
        ):
            raise ValueError(f"invalid native callout text bbox={box!r}")
    return geometry


def _r24_record(adapter: Any, annotation: Any, *, label: str) -> tuple[dict[str, Any], Any]:
    """Strict native inputs to the existing dump/geometry parser, without COM fallbacks.

    R24 is recipe-local. No census ULP, crop padding, shared-audit allowance or
    triangle approximation of a DOT is introduced here.
    """
    annotation = _early_bound(annotation, "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"{label}: missing native annotation")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    if data is None:
        raise RuntimeError(f"{label}: missing native display data")
    raw_display = {}
    for key, count_member, getters in _DISPLAY_PRIMITIVES:
        count = getattr(data, count_member)()
        if type(count) is not int or count < 0:
            raise RuntimeError(f"{label}: invalid {count_member}={count!r}")
        rows = [getattr(data, getters[0])(index) for index in range(count)]
        if any(not _native_finite_row(row) for row in rows):
            raise RuntimeError(f"{label}: unreadable native {key} rows={rows!r}")
        if rows:
            raw_display[key] = rows
    count = data.GetTextCount()
    if type(count) is not int or count <= 0:
        raise RuntimeError(f"{label}: invalid native text count={count!r}")
    raw_texts = []
    width_reader = _Reader(adapter)
    for index in range(count):
        position = data.GetTextPositionAtIndex(index)
        height = data.GetTextHeightAtIndex(index)
        angle = data.GetTextAngleAtIndex(index)
        anchor = data.GetTextRefPositionAtIndex(index)
        text = data.GetTextAtIndex(index)
        width = width_reader.optional(lambda i=index: data.GetTextInBoxWidthAtIndex(i))
        if (type(text) is not str
                or not _native_finite_row(position) or len(position) != 3
                or not _native_finite_scalar(height) or height <= 0.0
                or not _native_finite_scalar(angle)
                or type(anchor) is not int or anchor not in range(6)
                or (width is not None and (not _native_finite_scalar(width) or width < 0.0))):
            raise RuntimeError(f"{label}: invalid native text scalar at {index}")
        native_text = {"t": text, "pos": position, "h": height, "ang": angle, "ref": anchor}
        # This reports table-cell text-in-box width, NOT glyph ink. Legitimate
        # zero (styleNone) retains the existing calibrated advance estimate.
        if width:
            native_text["w"] = width
        raw_texts.append(native_text)
    reader = _Reader(adapter)
    display = _dump_display(reader, data)
    errors = reader.take_errors()
    if errors:
        raise RuntimeError(f"{label}: native display reads refused: {errors!r}")
    # Keep unrounded primitives for fixed-ink, landing and crossing equations.
    display.update(raw_display)
    display["texts"] = raw_texts
    count = annotation.GetLeaderCount()
    if type(count) is not int or count < 0:
        raise RuntimeError(f"{label}: invalid native leader count={count!r}")
    record = {
        "name": label, "type": annotation.GetType(),
        "owner_type": annotation.OwnerType, "visible": annotation.Visible,
        "pos": annotation.GetPosition(), "display": display,
        "leaders": [annotation.GetLeaderPointsAtIndex(index) for index in range(count)],
    }
    if (any(type(record[key]) is not int for key in ("type", "owner_type", "visible"))
            or record["owner_type"] != 0 or record["visible"] != 1):
        raise RuntimeError(f"{label}: native annotation is not visible/view-owned")
    try:
        geometry = _arc_callout_geometry(record, calibrate_sheet_advance([record]))
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        raise RuntimeError(f"{label}: invalid native ink: {exc}") from exc
    return record, geometry


def _r24_straight_ink(record: dict[str, Any]) -> list[Segment]:
    display = record["display"]
    return [
        *(Segment(row[4], row[5], row[7], row[8]) for row in display.get("lines", ())),
        *(segment for row in display.get("polylines", ()) for segment in polyline_segments(row)),
        *_registered_leaders(record),
    ]


def _r24_no_crossings(source: list[Segment], target: list[Segment], *, label: str) -> None:
    segments = [
        LeaderSegment(owner, "R24 ink", s.x0, s.y0, s.x1, s.y1, "sheet")
        for owner, rows in (("source", source), ("target", target)) for s in rows
        if s.length > 0.0
    ]
    # No shared-terminus exemption: these are dimension/model lines, not two
    # leaders legitimately converging under a common arrowhead.
    crossings = find_leader_leader_crossings(segments, tol=1e-12, shared_terminus=0.0)
    if crossings:
        raise RuntimeError(f"{label}: native connector crosses line: {crossings[0].describe()}")


def _rod_tip_witness_gaps(display: Any) -> tuple[float, float]:
    """Read the effective gaps, including a standard-controlled document gap."""
    display = _early_bound(display, "IDisplayDimension")
    gaps = []
    for index in (0, 1):
        # Official GetWitnessLineGap returns the document gap when UseDoc is
        # true. Generated DISPID104 returns (BOOL status, BOOL UseDoc, R8 Gap).
        # SP4 can retain (True, True, .001); C5 does not require a local zero.
        result = display.GetWitnessLineGap(index, False, 0.0)
        if (type(result) not in (list, tuple) or len(result) != 3
                or result[0] is not True or type(result[1]) is not bool
                or not _native_finite_scalar(result[2]) or result[2] < 0.0):
            raise RuntimeError(f"detail E 5.59: unreadable native witness gap {index}: {result!r}")
        gaps.append(result[2])
    return tuple(gaps)


def _rod_position_frame_signature(gtol: Any) -> Any:
    gtol = _early_bound(gtol, "IGtol")
    count = gtol.GetFrameCount()
    if type(count) is not int or count != 1:
        raise RuntimeError(f"rod-pin DOT: expected one unchanged native frame, got {count!r}")
    frame = _early_bound(gtol.GetFrame(1), "IGtolFrame")
    if frame is None:
        raise RuntimeError("rod-pin DOT: missing native frame")
    xml = frame.GetSymbolXml()
    if type(xml) is not str:
        raise RuntimeError("rod-pin DOT: unreadable native frame XML")
    return gtol_frame_signature(xml)


def _record_rod_dot_failure(adapter: Any, annotation: Any, exc: Exception, record: Any = None) -> None:
    """Failure-only actual leader/style evidence; diagnostics never replace refusal."""
    with contextlib.suppress(Exception):
        if getattr(exc, "rod_dot_native_context", None):
            return
        context = {}
        for key, member, args in (
            ("leader_points", "GetLeaderPointsAtIndex", (0,)),
            ("leader_count", "GetLeaderCount", ()),
            ("leader_side", "GetLeaderSide", ()),
            ("leader_style", "GetLeaderStyle", ()),
            ("arrow_style", "GetArrowHeadStyleAtIndex", (0,)),
            ("smart_arrowhead", "GetSmartArrowHeadStyle", ()),
        ):
            with contextlib.suppress(Exception):
                context[key] = copy.deepcopy(getattr(annotation, member)(*args))
        with contextlib.suppress(Exception):
            if record is None:
                record, _geometry = _r24_record(adapter, annotation, label="rod-pin DOT failure")
            context["record"] = copy.deepcopy(record)
        exc.rod_dot_native_context = context


def _configure_rod_position_dot(adapter: Any, gtol: Any, edge: Any, landing: tuple[float, float]) -> Any:
    """Official/generated GTol route; new native behavior must pass every readback."""
    annotation = _early_bound(_early_bound(gtol, "IGtol").GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError("rod-pin DOT: missing native annotation")
    try:
        signature = _rod_position_frame_signature(gtol)
        if annotation.GetLeaderAllAround() is not False:
            raise RuntimeError("rod-pin DOT: unexpected all-around control")
        status = int(annotation.SetLeader3(2, 2, False, False, False, False))  # BENT, RIGHT
        if status != 0:
            raise RuntimeError(f"rod-pin DOT: SetLeader3 status={status!r}")
        status = int(annotation.SetArrowHeadStyleAtIndex(0, 3))  # swDOT_ARROWHEAD
        if status != 0:
            raise RuntimeError(f"rod-pin DOT: SetArrowHeadStyleAtIndex status={status!r}")
        adapter.currentModel.GraphicsRedraw2()
        rebuild_drawing(adapter, label="rod-pin DOT native readback")
        _require_rod_position_dot(adapter, gtol, edge, landing, signature)
        return signature
    except Exception as exc:
        _record_rod_dot_failure(adapter, annotation, exc)
        raise


def _require_rod_position_dot(adapter: Any, gtol: Any, edge: Any, landing: tuple[float, float], signature: Any) -> None:
    annotation = _early_bound(_early_bound(gtol, "IGtol").GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError("rod-pin DOT: missing native annotation")
    record = None
    try:
        expected = {
            "GetArrowHeadStyleAtIndex": (3, (0,)), "GetArrowHeadCount": (1, ()),
            "GetLeaderCount": (1, ()), "GetLeaderStyle": (2, ()), "GetLeaderSide": (2, ()),
            "GetSmartArrowHeadStyle": (False, ()), "GetLeaderAllAround": (False, ()),
            "GetLeaderPerpendicular": (False, ()), "GetDashedLeader": (False, ()),
            "GetAttachedEntityCount3": (1, ()),
        }
        for member, (wanted, args) in expected.items():
            actual = getattr(annotation, member)(*args)
            if type(actual) is not type(wanted) or actual != wanted:
                raise RuntimeError(f"rod-pin DOT: {member}={actual!r}, required={wanted!r}")
        points = annotation.GetLeaderPointsAtIndex(0)
        if not _native_finite_row(points) or len(points) != 9:
            raise RuntimeError("rod-pin DOT: missing native bent leader polyline")
        types = annotation.GetAttachedEntityTypes()
        if (type(types) not in (list, tuple) or len(types) != 1
                or type(types[0]) is not int or types[0] != 1):  # swSelEDGES
            raise RuntimeError("rod-pin DOT: invalid native attached edge type")
        _assert_attached_to(adapter, annotation, edge, entity_type="EDGE", what="rod-pin DOT", label="position")
        _assert_leader_lands(annotation, landing, what="rod-pin DOT", label="position", tolerance=5e-5)
        if _rod_position_frame_signature(gtol) != signature:
            raise RuntimeError("rod-pin DOT: frame semantics changed")
        record, _geometry = _r24_record(adapter, annotation, label="rod-pin DOT")
        arrows = record["display"].get("arrows", ())
        if len(arrows) != 1 or arrows[0][8] != 3 or math.dist(tuple(arrows[0][:2]), landing) > 5e-5:
            raise RuntimeError("rod-pin DOT: native display arrow style/landing disagrees")
        position = record["pos"]
        if math.dist(tuple(position[:2]), FCF_XY) > 1e-5:
            raise RuntimeError("rod-pin DOT: native frame position moved")
    except Exception as exc:
        _record_rod_dot_failure(adapter, annotation, exc, record)
        raise


def _require_rod_tip_endpoints(
    adapter: Any, end: Any, land: ViewEdge, annotation: Any,
    *, expected_attachments: tuple[Any, ...] | None = None,
) -> tuple[Any, ...]:
    """Prove real corners and their native gap/line/arrow routes, not zero gap.

    A normal extension-line gap is blank paper, not a missing manufactured
    corner. Its outward projection must agree with the effective native gap,
    and the SAME line must remain visible in E and reach its dimension arrow.
    No global standard change, attachment edit or substitute line is allowed.
    """
    annotation = _early_bound(annotation, "IAnnotation")
    if annotation is None:
        raise RuntimeError("detail E 5.59: missing native annotation")
    kind = annotation.GetType()
    if type(kind) is not int or kind != 4:
        raise RuntimeError("detail E 5.59: annotation is not a native display dimension")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if display is None:
        raise RuntimeError("detail E 5.59: missing native display dimension")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if not attached or any(entity is None for entity in attached) or annotation.IsDangling() is not False:
        raise RuntimeError("detail E 5.59: missing/dangling native attachments")
    if expected_attachments is not None:
        remaining = list(attached)
        for expected in expected_attachments:
            index = next((i for i, actual in enumerate(remaining)
                          if type(status := adapter.swApp.IsSame(actual, expected)) is int and status == 1), None)
            if index is None:
                raise RuntimeError("detail E 5.59: native attachments changed")
            remaining.pop(index)
        if remaining:
            raise RuntimeError("detail E 5.59: native attachments changed")
    assert_dimension_measures(adapter, display, expected_mm=TIP_FACE, label="imported RodTipLen")
    gaps = _rod_tip_witness_gaps(display)
    record, geometry = _r24_record(adapter, annotation, label="detail E 5.59")
    crop = _detail_crop(adapter, end, label="E")
    circle = ((crop[0] + crop[2]) / 2.0, (crop[1] + crop[3]) / 2.0,
              (crop[2] - crop[0]) / 2.0)
    endpoints = _project(adapter, end, [tuple(v / 1000.0 for v in p) for p in land.line],
                         label="detail E exact 5.59 end-face endpoints")
    dx, dy = endpoints[1][0] - endpoints[0][0], endpoints[1][1] - endpoints[0][1]
    length = math.hypot(dx, dy)
    if length <= 0.0:
        raise RuntimeError("detail E 5.59: missing actual end-face span")
    normal = (-dy / length, dx / length)
    if normal[0] < 0.0:
        normal = (-normal[0], -normal[1])
    ink = [Segment(row[4], row[5], row[7], row[8]) for row in record["display"].get("lines", ())]
    arrows = record["display"].get("arrows", ())
    if len(arrows) != 2:
        raise RuntimeError("detail E 5.59: missing native dimension arrow pair")
    if any(row[6] <= 0.0 or row[7] <= 0.0 or math.hypot(row[3], row[4]) == 0.0 for row in arrows):
        raise RuntimeError("detail E 5.59: unreadable native arrow footprint")
    observed_gaps, used_arrows, witnesses = [], set(), []
    for index, point in enumerate(endpoints):
        # Exact persisted circle containment; NO display-census ULP here.
        if math.dist(point, circle[:2]) > circle[2]:
            raise RuntimeError(f"detail E 5.59: actual end-face endpoint {index} outside unchanged crop")
        candidates = []
        for segment in ink:
            start, finish = sorted(((segment.x0, segment.y0), (segment.x1, segment.y1)),
                                   key=lambda p: math.dist(p, point))
            start_offset = (start[0] - point[0], start[1] - point[1])
            finish_offset = (finish[0] - point[0], finish[1] - point[1])
            gap = start_offset[0] * normal[0] + start_offset[1] * normal[1]
            reach = finish_offset[0] * normal[0] + finish_offset[1] * normal[1]
            if (gap < 0.0 or reach <= gap
                    or any(abs(offset[0] * normal[1] - offset[1] * normal[0]) > DETAIL_GEOMETRY_TOL_M
                           for offset in (start_offset, finish_offset))):
                continue
            matches = [i for i, arrow in enumerate(arrows)
                       if point_segment_distance(tuple(arrow[:2]), segment) <= DETAIL_GEOMETRY_TOL_M
                       and math.dist(point, tuple(arrow[:2])) > gap]
            if len(matches) == 1:
                candidates.append((segment, gap, matches[0]))
        if len(candidates) != 1 or candidates[0][2] in used_arrows:
            raise RuntimeError(f"detail E 5.59: endpoint {index} has no unambiguous native witness-to-arrow route")
        witness, gap, arrow_index = candidates[0]
        span = clip_segment_to_circle(witness, circle)
        visible = 0.0 if span is None else witness.length * (span[1] - span[0])
        if visible <= 0.0:
            raise RuntimeError(f"detail E 5.59: endpoint {index} has no visible native witness")
        if any(segment_box_distance(witness, box) <= 0.0 for box in geometry.text_boxes):
            raise RuntimeError(f"detail E 5.59: endpoint {index} native witness crosses its text")
        used_arrows.add(arrow_index)
        observed_gaps.append(gap)
        witnesses.append(witness)
        _telemetry.info(f"detail E 5.59 endpoint {index}: projected_endpoint={point}, "
                        f"persisted_crop={circle}, effective_native_gaps={gaps!r}, "
                        f"native_witness={witness!r}, projected_gap_mm={gap * 1000.0:.6f}, "
                        f"visible_witness_mm={visible * 1000.0:.6f}")
    # Native display/edge enumeration order need not be witness-index order.
    # Both measured gaps must consume the complete effective native gap pair.
    if any(abs(actual - expected) > DETAIL_GEOMETRY_TOL_M
           for actual, expected in zip(sorted(observed_gaps), sorted(gaps), strict=True)):
        raise RuntimeError("detail E 5.59: native witness lines disagree with effective gap readback")
    _r24_no_crossings(witnesses[:1], witnesses[1:], label="detail E 5.59 own witnesses")
    return attached


def _require_rod_dot_route(adapter: Any, end: Any, gtol: Any, landing: tuple[float, float]) -> None:
    annotation = _early_bound(_early_bound(gtol, "IGtol").GetAnnotation(), "IAnnotation")
    record = None
    try:
        record, geometry = _r24_record(adapter, annotation, label="rod-pin DOT route")
        centre, south = _project(
            adapter, end,
            ((ROD_HOLE_X / 1000.0, ROD_HOLE_Y / 1000.0, 0.0),
             (ROD_HOLE_X / 1000.0, (ROD_HOLE_Y - _ROD_HOLE_DIA / 2.0) / 1000.0, 0.0)),
            label="detail E actual circular edge south rim",
        )
        if math.dist(landing, south) > 5e-5:
            raise RuntimeError("rod-pin DOT: landing is not the actual circular edge south rim")
        arms = []
        for mark in _bound_view_annotations(end, label="rod-pin DOT printed centre-mark arm"):
            if mark.GetType() != 13:
                continue
            display = _center_mark_display(mark, {})
            for row in display.get("lines", ()):
                s = Segment(row[4], row[5], row[7], row[8])
                if (point_segment_distance(centre, s) <= 5e-5
                        and point_segment_distance(landing, s) <= 5e-5
                        and min(s.y0, s.y1) < centre[1]):
                    arms.append(s)
        if len(arms) != 1:
            raise RuntimeError("rod-pin DOT: south-rim landing is not on one actual printed centre-mark arm")
        tapered = scan_view_edges(end, label="detail E DOT taper").exact_line_through(
            ((ROD_TIP_X + BOT_END_X) / 2.0, (_ROD_TIP_Y + _BOT_END_Y) / 2.0, ARM_THICKNESS / 2.0),
            label="+Z actual taper boundary",
        )
        points = _project(adapter, end, [tuple(v / 1000.0 for v in p) for p in tapered.line],
                          label="detail E actual taper boundary")
        taper = Segment(*points[0], *points[1])
        route = _registered_leaders(record)
        if len(route) != 2 or any(s.length <= 0.0 for s in route):
            raise RuntimeError("rod-pin DOT: unreadable native bent route")
        _r24_no_crossings(_r24_straight_ink(record), [taper], label="rod-pin DOT frame/route taper")
        _telemetry.info(f"rod-pin DOT: native_south_arm={arms!r}, native_route={route!r}, "
                        f"actual_taper={taper!r}, display_dot_size={record['display']['arrows'][0][6:8]!r}")
    except Exception as exc:
        _record_rod_dot_failure(adapter, annotation, exc, record)
        raise


def _require_r24_detail_layout(
    adapter: Any, end: Any, right: Any,
    taper: Any, taper_entities: tuple[Any, Any], land: ViewEdge,
    rod_tip_attached: tuple[Any, ...],
) -> None:
    """Reprove the independent 5.59, datum C, strap and taper state after regeneration."""
    annotations = _bound_view_annotations(end, label="R24 final detail E")
    tip_annotations = [
        ann for ann in annotations
        if ann.GetType() == 4 and dimension_name(adapter, ann) == "RodTipLen"
    ]
    tags = [ann for ann in annotations if ann.GetType() == 2]  # swDatumTag
    if len(tip_annotations) != 1:
        raise RuntimeError("R24: missing native 5.59")
    if (len(tags) != 1
            or str(_early_bound(tags[0].GetSpecificAnnotation(), "IDatumTag").GetLabel() or "")
            != ROD_HOLE.fields["datum"][0]):
        raise RuntimeError("R24: detail E must carry exactly one datum tag, C on the rod-pin frame")
    _require_rod_tip_endpoints(
        adapter, end, land, tip_annotations[0], expected_attachments=rod_tip_attached,
    )
    thickness = [
        ann for ann in _bound_view_annotations(right, label="R24 thickness")
        if dimension_name(adapter, ann) == "StrapThickness"
    ]
    if len(thickness) != 1:
        raise RuntimeError("R24: missing native strap thickness text")
    _r24_record(adapter, thickness[0], label="strap thickness")
    _require_taper_witnesses(adapter, end, taper, taper_entities)


def _require_taper_witnesses(adapter: Any, end: Any, taper: Any, taper_entities: tuple[Any, Any]) -> None:
    """Actual capped ink clears the persisted parent fence, with attachment unchanged."""
    taper = _early_bound(taper, "IDisplayDimension")
    if (not _native_finite_scalar(taper.MaxWitnessLineLength)
            or abs(taper.MaxWitnessLineLength - TAPER_WITNESS_LENGTH) > 1e-9):
        raise RuntimeError("132.76: final native witness cap changed")
    assert_dimension_measures(adapter, taper, expected_mm=BOT_END_X, label="final 132.76 taper",
                              entities=taper_entities, entity_types=("EDGE", "VERTEX"))
    taper_record, _g = _r24_record(adapter, taper.GetAnnotation(), label="132.76 taper")
    # The BASIC frame's two sides are vertical ink too: a witness is the
    # vertical line carrying one of the dimension's two arrow tips.
    tips = [tuple(row[:2]) for row in taper_record["display"].get("arrows", ())]
    witnesses = [
        s for s in _r24_straight_ink(taper_record)
        if abs(s.x1 - s.x0) <= DETAIL_GEOMETRY_TOL_M
        and any(point_segment_distance(tip, s) <= DETAIL_GEOMETRY_TOL_M for tip in tips)
    ]
    if (len(tips) != 2 or len(witnesses) != 2
            or any(sum(point_segment_distance(tip, s) <= DETAIL_GEOMETRY_TOL_M for s in witnesses) != 1
                   for tip in tips)
            or any(s.length > TAPER_WITNESS_LENGTH + DETAIL_GEOMETRY_TOL_M for s in witnesses)):
        raise RuntimeError("132.76: missing/uncapped native witness pair")
    readback = read_circular_detail_crop(adapter, end, label="R24 parent E circle")
    parent_circle = (*readback.parent_centre, readback.parent_radius)
    if any(segment_circle_distance(s, parent_circle) <= 0.0 for s in witnesses):
        raise RuntimeError("132.76: native witness crosses/touches parent E circle")
    _telemetry.info(f"132.76: native_witnesses={witnesses!r}, unchanged_parent_E_circle={parent_circle!r}")


def _require_arc_profile_clearance(
    adapter: Any, front: Any, profiles: dict[str, Any]
) -> None:
    """After the final rebuild, prove native profile leaders clear other callouts.

    This is PDF-free: the final enforced ink audit remains authoritative for
    printed glyphs. Native text positions/heights and the audit's existing row
    width model give an early refusal, not a claim of exact PDF text widths.
    """
    reader = _Reader(adapter)
    records = []
    profile_names = {}
    problems = []
    for name in ARC_PROFILE_FRAME_XY:
        try:
            gtol = reader.bind(profiles.get(name), "IGtol")
            if gtol is None:
                raise ValueError("missing native IGtol")
            annotation = reader.bind(reader.need(lambda: gtol.GetAnnotation()), "IAnnotation")
            if annotation is None:
                raise ValueError("missing native IAnnotation")
            native_name = reader.need(lambda: annotation.GetName(), "")
            if type(native_name) is not str or not native_name:
                raise ValueError(f"invalid native annotation name={native_name!r}")
            profile_names[name] = native_name
        except (TypeError, ValueError) as exc:
            problems.append(f"arc-system {name} profile: {exc}")
    if len(set(profile_names.values())) != len(profile_names):
        problems.append("native arc-profile frames have duplicate annotation names")
    try:
        raw_annotations = _bound_view_annotations(front, label="arc profile front annotations")
        for raw in raw_annotations:
            try:
                record = _dump_annotation(reader, raw)
                if record is None:
                    problems.append("front-view annotation could not be read")
                else:
                    records.append(record)
            except (TypeError, ValueError, OverflowError) as exc:
                bound = reader.bind(raw, "IAnnotation")
                label = reader.need(lambda: bound.GetName(), "<unreadable>")
                problems.append(f"front-view callout {label!r}: invalid native readback: {exc}")
    except (TypeError, ValueError, OverflowError) as exc:
        problems.append(f"invalid native front-view readback: {exc}")

    def mm(values: Any) -> tuple[float, ...]:
        return tuple(round(value * 1000.0, 3) for value in values)

    # Log every available native read before any refusal, on success too.
    for name in ARC_PROFILE_FRAME_XY:
        matches = [r for r in records if r.get("name") == profile_names.get(name)]
        if len(matches) != 1:
            problems.append(f"arc-system {name} profile: expected one native front-view frame, got {len(matches)}")
        for record in matches:
            _telemetry.info(
                f"arc-system {name} profile native readback: "
                f"requested_frame_mm={mm(ARC_PROFILE_FRAME_XY[name])!r}, "
                f"actual_GetPosition_mm={mm(record.get('pos', ()))!r}, "
                f"native_leader_points_mm={[mm(p) for p in record.get('leaders', ())]!r}, "
                f"landing_mm={[mm(p[-3:]) for p in record.get('leaders', ())]!r}"
            )
    refused = reader.take_errors()
    if refused:
        problems.append(f"native COM reads refused: {refused!r}")
    geometries = {}
    try:
        advance = calibrate_sheet_advance(records)
        for record in records:
            if record.get("owner_type") == 2 or record.get("visible") in (2, 3):
                continue
            # Construction marks carry no callout text; every other annotation
            # must be measurable, rather than quietly dropping a foreign box.
            if record.get("type") in (1, 13, 15):
                continue
            try:
                geometries[id(record)] = _arc_callout_geometry(record, advance)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                problems.append(f"front-view callout {record.get('name')!r}: {exc}")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        problems.append(f"invalid native text calibration: {exc}")
    measured = []
    for name in ARC_PROFILE_FRAME_XY:
        matches = [r for r in records if r.get("name") == profile_names.get(name)]
        if len(matches) != 1:
            continue
        record = matches[0]
        source = geometries.get(id(record))
        context = (
            f"arc-system {name} profile requested_frame_mm={mm(ARC_PROFILE_FRAME_XY[name])!r}, "
            f"actual_GetPosition_mm={mm(record.get('pos', ()))!r}, "
            f"native_leader_points_mm={[mm(p) for p in record.get('leaders', ())]!r}"
        )
        leaders = record.get("leaders", ())
        if (
            record.get("type") != 5 or record.get("owner_type") != 0
            or source is None or len(leaders) != 1
            or any(len(p) != 9 or not all(math.isfinite(v) for v in p) for p in leaders)
        ):
            problems.append(f"{context}: missing/invalid native bent-profile geometry")
            continue
        segments = _registered_leaders(record)
        if any(segment.length <= 0.0 for segment in segments):
            problems.append(f"{context}: invalid zero-length native leader segment")
            continue
        frame_lines = [
            s for s in source.segments
            if s.role not in ("leader", "arrow") and s.length > 0.0
        ]
        frame_box = union_boxes([*source.text_boxes, *(s.box() for s in frame_lines)])
        if not frame_lines or frame_box is None:
            problems.append(f"{context}: missing native frame ink bbox")
            continue
        context += f", native_frame_ink_bbox_mm={frame_box.format_mm()}"
        _telemetry.info(context)
        native_segments = [
            LeaderSegment(source.label, source.kind, s.x0, s.y0, s.x1, s.y1, "front")
            for s in segments
        ]
        for other in records:
            target = geometries.get(id(other))
            if other is record or target is None:
                continue
            native_segments.extend(
                LeaderSegment(target.label, target.kind, s.x0, s.y0, s.x1, s.y1, "front")
                for s in target.leader_segments()
            )
        for crossing in find_leader_leader_crossings(native_segments):
            if source.label not in (crossing.a.label, crossing.b.label):
                continue
            detail = f"{context}: actual native leader crossing: {crossing.describe()}, intersection_mm={(crossing.x * 1000.0, crossing.y * 1000.0)}"
            _telemetry.info(detail)
            problems.append(detail)
        distances = [
            (segment_box_distance(segment, box), target, box, segment)
            for other in records if other is not record
            for target in (geometries.get(id(other)),) if target is not None
            for box in target.text_boxes for segment in segments
        ]
        if not distances:
            problems.append(f"{context}: missing other native front-view callout bboxes")
            continue
        distance, target, box, segment = min(distances, key=lambda item: item[0])
        penetration, _span = text_overlap(segment, target, box)
        detail = (
            f"{context}, minimum_clearance_mm={distance * 1000.0:.3f}, "
            f"required_clearance_mm={ARC_PROFILE_TEXT_CLEARANCE_M * 1000.0:.3f}, "
            f"offending_callout={target.label!r}, bbox_mm={box.format_mm()}, "
            f"native_segment={segment.format_mm()}, penetration_mm={penetration * 1000.0:.3f}"
        )
        _telemetry.info(detail)
        measured.append(detail)
        if distance < ARC_PROFILE_TEXT_CLEARANCE_M and not math.isclose(
            distance, ARC_PROFILE_TEXT_CLEARANCE_M, rel_tol=0.0, abs_tol=1e-12
        ):
            problems.append(detail)
    if problems:
        raise RuntimeError(
            "rocker arc-profile native clearance failed:\n"
            + "\n".join(problems + [d for d in measured if d not in problems])
        )


def _note_extent(adapter: Any, note: Any, *, label: str = "manufacturing notes") -> tuple[float, float, float, float]:
    """Native GetExtent sheet-space note BOX, not proven printed glyph ink."""
    adapter.currentModel.GraphicsRedraw2()
    extent = tuple(
        float(value) for value in (_early_bound(note, "INote").GetExtent() or ())
    )
    if (len(extent) != 6 or not all(math.isfinite(v) for v in extent)
            or extent[3] <= extent[0] or extent[4] <= extent[1]):
        raise RuntimeError(f"{label} have no rendered extent: {extent!r}")
    return (extent[0], extent[1], extent[3], extent[4])


def _seat_notes_on_border(
    adapter: Any, note: Any, sheet: Any
) -> tuple[float, float, float, float]:
    """Steer the notes' RENDERED bottom-left corner onto NOTES_LEFT,
    NOTES_BORDER_CLEARANCE above the sheet's drawable region (the insertion
    point is neither the text box's corner nor tracked by it 1:1)."""
    template = DRAWING_TEMPLATES[SPEC.layout]
    region = sheet_drawable_region(
        adapter, sheet, width=template.width_m, height=template.height_m
    )
    target = (NOTES_LEFT, region.ymin + NOTES_BORDER_CLEARANCE)
    annotation = _early_bound(
        _early_bound(note, "INote").GetAnnotation(), "IAnnotation"
    )
    # A property-linked note shows its resolved text only after a rebuild; an
    # extent read before it would seat the one-line link token, not the block.
    rebuild_drawing(adapter, label="manufacturing notes link resolve")
    extent = _note_extent(adapter, note)
    lines = len(DRAWING_NOTES.splitlines())
    if extent[3] - extent[1] < lines * NOTES_MIN_LINE_PITCH:
        raise RuntimeError(
            f"manufacturing notes render {(extent[3] - extent[1]) * 1000.0:.1f} mm "
            f"tall, under {lines} lines at {NOTES_MIN_LINE_PITCH * 1000.0:.1f} mm: "
            "the property link has not resolved"
        )
    for _pass in range(NOTES_SEAT_PASSES):
        shift = (target[0] - extent[0], target[1] - extent[1])
        if max(abs(shift[0]), abs(shift[1])) <= NOTES_SEAT_SETTLE:
            break
        position = tuple(float(value) for value in (annotation.GetPosition() or ()))
        if len(position) != 3:
            raise RuntimeError(f"manufacturing notes position unreadable: {position!r}")
        if not annotation.SetPosition(
            position[0] + shift[0], position[1] + shift[1], position[2]
        ):
            raise RuntimeError("manufacturing notes SetPosition failed")
        extent = _note_extent(adapter, note)
    extent_mm = tuple(round(value * 1000.0, 2) for value in extent)
    _telemetry.info(
        f"manufacturing notes seated: extent_mm={extent_mm!r}, "
        f"drawable bottom {region.ymin * 1000.0:.2f} mm"
    )
    if extent[1] < region.ymin or extent[3] > NOTES_CEILING:
        raise RuntimeError(
            "manufacturing notes do not fit between the border "
            f"({region.ymin * 1000.0:.2f} mm) and the front view's annotations "
            f"({NOTES_CEILING * 1000.0:.1f} mm): rendered extent {extent_mm!r}"
        )
    return extent


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm source", await adapter.open_model(str(SOURCE)))
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
            "Right View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "Right View Note",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
        unit=part_drawing_unit("ch-rocker-arm"), decimals=SHEET_DECIMALS,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm; tapered strap; seesaw pivot",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # Explicit per-view scale (an auto-scaled view shifts every coordinate pick).
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    # View F, the 3:1 removed right end view: the 2.50 x ~29 strap section --
    # prints the strap thickness, the hub width, datum G on the hub's -Z end
    # face with its BASIC to the strap's centre plane, and the hub-root
    # fillets, gives the through direction, and carries datum B (the broad
    # face) so the rod-pin position frame has an orientation datum.
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=RIGHT_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    # Import the source radii and top height too: these are the BASIC nominal
    # geometry of the profile zone, not independent radius/height bands.
    front_annotations, taper_dimension, taper_entities, land_dimension, land_entities = _add_rocker_outline_dimensions(adapter, front)
    try:
        notes = add_property_linked_note(
            adapter, "Manufacturing Notes", NOTES_LEFT, NOTES_CEILING
        )
        notes_box = _seat_notes_on_border(adapter, notes, sheet)
    except Exception as exc:
        _capture_caption_failure(adapter, "styles", exc)
        raise
    caption_font_source = _pin_detail_caption_font_source(adapter, notes)
    hub_centre, hub_radius_mm = _detail_fence("D")
    hub = _create_detail(
        adapter, front, centre=hub_centre, radius_mm=hub_radius_mm,
        target=HUB_CENTER, scale=HUB_SCALE, label="D",
    )
    end_centre, end_radius_mm = _detail_fence("E")
    end = _create_detail(
        adapter, front, centre=end_centre, radius_mm=end_radius_mm,
        target=END_CENTER, scale=END_SCALE, label="E",
    )
    hub_annotations = curate_view_dimensions(
        adapter, hub, keep=HUB_KEEP, view_label="detail D",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _dress_detail_dimensions(adapter, hub_annotations, keep=HUB_KEEP)
    try:
        phase = "R24 detail E dimension import"
        end_annotations = curate_view_dimensions(
            adapter, end, keep=END_KEEP, view_label="detail E",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        _dress_detail_dimensions(adapter, end_annotations, keep=END_KEEP)
        phase = "R24 native 5.59 witnesses"
        rod_land = scan_view_edges(end, label="detail E rod land").exact_line_through(
            (_TIP_FACE_MID_X, _TIP_FACE_MID_Y, ARM_THICKNESS / 2.0),
            label="+Z rod-side radial land",
        )
        (rod_tip,) = [ann for ann in end_annotations if dimension_name(adapter, ann) == "RodTipLen"]
        rod_tip_attached = _require_rod_tip_endpoints(adapter, end, rod_land, rod_tip)
    except Exception as exc:  # noqa: BLE001 - the imported native drawing still exists
        _capture_layout_failure(adapter, phase, exc)
        raise
    # The hub length and the strap thickness only show in the end view; the
    # front looks down their direction. Codex #936 (PRRT_kwDOPHDy386mRk__):
    # RIGHT_KEEP was declared but never curated, so the +0.05/0 band that sets
    # all 20 channel stations never printed. Targeted by feature, so only
    # Hub's and Strap's dimensions arrive, each selected by its feature name.
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    imported_annotations = [
        *front_annotations, *hub_annotations, *end_annotations, *right_annotations,
    ]
    _assert_pivot_precision(adapter, drawing_model, imported_annotations)
    assert_imported_precision(
        adapter,
        imported_annotations,
        {
            "TopAbovePivot": TOP_EDGE.precision["height_above_pivot"],
            "HubLength": HUB_FACES.precision["length"],
            "StrapThickness": STRAP_DATUM_B.precision["thickness"],
            "HubRootRadius": rocker_notes.DRAWING_PRECISION["HubRoot"]["HubRootRadius"],
            "TipLandAngle": rocker_notes.DRAWING_PRECISION["StrapProfile"]["TipLandAngle"],
        },
    )
    # Each band names what it serves (Opus #1020): hub length spaces the
    # pivot-shaft stack; the strap's thickness is the rod fork's side clearance.
    # Both multi-row callouts sit below their values: above-text line breaks
    # print as one run.
    set_dimension_callouts(
        adapter, right_annotations, {
            "HubLength": HUB_LENGTH_TEXT,
            "StrapThickness": rocker_notes.STRAP_FIT_CALLOUT,
        },
        location="below",
    )
    for annotation in right_annotations:
        name = dimension_name(adapter, annotation)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if name == "HubLength" and str(display.GetText(4) or "") != HUB_LENGTH_TEXT:
            raise RuntimeError("hub length stack callout did not persist")
        if name == "StrapThickness" and str(display.GetText(4) or "") != rocker_notes.STRAP_FIT_CALLOUT:
            raise RuntimeError("strap thickness fork-fit callout did not persist")
    try:
        phase = "view F hub-root radius"
        _dress_hub_root(adapter, right_annotations)
        phase = "view F strap position frame"
        (strap_thickness,) = [ann for ann in right_annotations if dimension_name(adapter, ann) == "StrapThickness"]
        _strap_position_frame(adapter, right, strap_thickness)
        phase = "view F hub/strap centre plane"
        centre_plane = _strap_centre_plane(adapter, right)
        phase = "view F datum G"
        (hub_length,) = [
            ann
            for ann in right_annotations
            if dimension_name(adapter, ann) == "HubLength"
        ]
        _hub_face_datum_g(adapter, right, centre_plane, hub_length)
    except Exception as exc:  # noqa: BLE001 - the imported native drawing still exists
        _capture_layout_failure(adapter, phase, exc)
        raise

    # Template marks already exist. Count printed primitives, not type-13
    # objects: native detail arrays also retain readable, zero-ink off-crop
    # ghosts. Do not delete those ghosts or repeat the duplicate batch insert.
    for label, view, required, detail in (
        ("front", front, 2, None),
        ("detail D", hub, 1, "D"),
        ("detail E", end, 1, "E"),
    ):
        _require_center_mark_census(
            adapter, view, label=label, required=required, detail=detail,
        )

    # E's native wizard-hole callout keeps the source through condition; its
    # first row names the pin that runs in it (Opus #1020 r3 C5).
    rod_hole_edge = visible_circle_edge(adapter, end, _ROD_HOLE_DIA)
    rod_callout = add_native_hole_callout(
        adapter,
        end,
        edge=rod_hole_edge,
        callout_xy=ROD_CALLOUT_XY,
        label="rod-pin hole",
        process=rocker_notes.ROD_PIN_MATE_CALLOUT + "\n" + drill_process(ROD_HOLE_SPEC) + "\n",
    )
    _require_rod_through_callout(rod_callout)
    set_hole_callout_precision(rod_callout, ROD_CALLOUT_PRECISION, label="rod-pin hole")

    _add_pin_coordinates(adapter, front)

    pivot_bore_edge = visible_circle_edge(adapter, hub, PIVOT_HOLE_DIA)
    pivot_centre, bore_right = _project(
        adapter, hub,
        ((0.0, PIVOT_MID_Y / 1000.0, 0.0),
         (PIVOT_HOLE_DIA / 2000.0, PIVOT_MID_Y / 1000.0, 0.0)),
        label="detail D bore centre and radius",
    )
    projected_radius = math.dist(pivot_centre, bore_right)
    pivot_datum_pick = _pick_pivot_bore(
        adapter, hub, pivot_bore_edge, pivot_centre, projected_radius,
    )
    datum_a = add_datum_feature(
        adapter, hub, edge_xy=pivot_datum_pick,
        symbol_xy=_pivot_datum_request(pivot_centre, projected_radius),
        datum=PIVOT_BORE.fields["datum"][0], label="pivot bore cylindrical datum feature", shoulder=True,
    )
    _require_datum_on_bore(adapter.swApp, datum_a, pivot_bore_edge)
    pivot_finish_rim, pivot_finish_symbol = _pivot_finish_placement(adapter, hub)
    add_surface_finish(
        adapter,
        hub,
        edge_entity=pivot_bore_edge,
        symbol_xy=pivot_finish_symbol,
        leader_attach_xy=pivot_finish_rim,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
        char_height=PIVOT_FINISH_CHAR_HEIGHT,
    )
    # The hub OD's coaxiality to A rides its own Ø10.20 in D (regate-r1 #2).
    try:
        (hub_dia,) = [ann for ann in hub_annotations if dimension_name(adapter, ann) == "HubDia"]
        _hub_position_frame(adapter, hub, hub_dia)
    except Exception as exc:  # noqa: BLE001 - the imported native drawing still exists
        _capture_layout_failure(adapter, "detail D hub OD position frame", exc)
        raise
    # Then a position FCF tying the rod-pin hole to A|B: B (broad face, on the
    # end view) orients the hole axes, and the BASIC X/Y above hold its 133.34
    # from A. Rotation about A is free -- the hole itself is datum C, which
    # clocks the profile frames (Pedro, option 4).
    # Datum B on the strap's broad face in view F, picked ABOVE the hub band
    # (the O10 hub hides the flank over y 3..13 since 2026-09-02) and above the
    # thickness block's line, projected natively at the view's 3:1.
    (broad_face,) = _project(
        adapter, right,
        ((0.0, DATUM_B_PICK_MODEL_Y / 1000.0, ARM_THICKNESS / 2000.0),),
        label="datum B broad-face pick",
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=broad_face,
        symbol_xy=DATUM_B_SYMBOL_XY,
        datum=STRAP_DATUM_B.fields["datum"][0],
        label="broad face",
    )
    (rod_position_landing,) = _project(
        adapter, end,
        ((ROD_HOLE_X / 1000.0, (ROD_HOLE_Y - _ROD_HOLE_DIA / 2.0) / 1000.0, 0.0),),
        label="detail E south rod-hole centre-mark-arm landing",
    )
    rod_position_gtol = add_feature_control_frame(
        adapter,
        end,
        edge_entity=rod_hole_edge,
        leader_attach_xy=rod_position_landing,
        frame_xy=FCF_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["rod-pin hole position"],
        datums=tuple(ROD_HOLE.fields["position_datums"][0]),
        diameter=True,
        label="rod-pin hole position",
    )
    try:
        rod_position_signature = _configure_rod_position_dot(
            adapter, rod_position_gtol, rod_hole_edge, rod_position_landing,
        )
    except Exception as exc:  # noqa: BLE001 - capture native DOT readback failures too
        _capture_layout_failure(adapter, "R24 native DOT configuration", exc)
        raise
    try:
        add_frame_datum_feature(
            adapter, end, rod_position_gtol,
            datum=ROD_HOLE.fields["datum"][0], symbol_xy=ROD_DATUM_C_XY,
            label="rod-pin hole datum feature",
        )
    except Exception as exc:  # noqa: BLE001 - capture the frame/tag readback
        _capture_layout_failure(adapter, "R24 datum C on the rod-pin frame", exc)
        raise
    arc_profiles = _add_arc_profiles(adapter, front)
    _add_view_arrow(adapter, front)

    add_property_linked_note(adapter, "Isometric View Note", *ISO_CAPTION_XY)
    add_property_linked_note(adapter, "Right View Note", *RIGHT_CAPTION_XY)
    _place_detail_letters(adapter, front)
    _normalize_detail_caption_styles(adapter, front, hub, end, caption_font_source)
    # Record BOTH native labels before D can abort and discard E's evidence.
    _record_detail_caption(adapter, hub, sheet, label="D", stage="before either caption guard")
    _record_detail_caption(adapter, end, sheet, label="E", stage="before either caption guard")
    _seat_detail_caption(adapter, hub, sheet, label="D")
    _seat_detail_caption(adapter, end, sheet, label="E")
    # The shared gate: no overlaps, border crossings or leader crossings.
    try:
        phase = "rebuild"
        rebuild_drawing(adapter, label="rocker-arm layout audit")
        phase = "dimension census"
        _require_dimension_census(adapter, (
            ("front", front, FRONT_KEEP), ("detail D", hub, HUB_KEEP),
            ("detail E", end, END_KEEP), ("right", right, RIGHT_KEEP), ("iso", iso, {}),
        ))
        phase = "tip land location"
        _require_land_location(
            adapter, (("front", front), ("detail D", hub), ("detail E", end),
                      ("right", right), ("iso", iso)),
            land_dimension, land_entities,
        )
        phase = "REAM clearance"
        _require_ream_clearance(adapter, hub, notes_box)
        phase = "front-detail air"
        _require_front_detail_air(adapter, front, hub, end)
        phase = "radius exterior"
        _require_radius_exterior(adapter, front)
        phase = "arc profile clearance"
        _require_arc_profile_clearance(adapter, front, arc_profiles)
        phase = "R24 native detail routes"
        _require_r24_detail_layout(
            adapter, end, right, taper_dimension, taper_entities, rod_land, rod_tip_attached,
        )
        _require_rod_position_dot(adapter, rod_position_gtol, rod_hole_edge,
                                  rod_position_landing, rod_position_signature)
        _require_rod_dot_route(adapter, end, rod_position_gtol, rod_position_landing)
        phase = "shared layout"
        check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)

        phase = "finalize"
        return await finalize_drawing(
            adapter,
            OUTPUTS,
            pdf_title="Rocker Arm Manufacturing Drawing",
            scale=SHEET_SCALE,
            layout=SPEC.layout,
        )
    except Exception as exc:  # noqa: BLE001 - capture before the native seat closes
        _capture_layout_failure(adapter, phase, exc)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
