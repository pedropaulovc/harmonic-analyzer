r"""Manufacturing drawing of the open-rebate brass stop block.

The sheet prints decimal inch (the part's ``drawing_unit: in``). The
cover-side view and end view show the rebate in solid lines. Standard
native Hole Wizard callouts define the orthogonal taps, including blind full
thread and drill depths; each native length variable prints .XXX. Every
controlling dimension is imported unchanged.
Hole-mouth points convert the shared millimetre frame to COM metres before
projection; the cover-side *Back view reverses X, not the coordinate units.
The *Bottom view is turned 180 degrees to preserve that X direction and
show the true third-angle underside; its current transform locates the tap.
Native callout positions centre their text; reserve the full two-line tap
instruction inside the print border and keep the thumb callout off the title.
The finalizer owns precise Shaded With Edges on the isometric. Its dark
source appearance is not overridden here: no verified drawing-view-only
lighting API is available, and even transient part appearance edits are banned.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _config
import _telemetry
import ms_stop_spec as part
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _feature_requirements import part_metadata, requirement
from _fit_deviations import deviations
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import drilled_limits, limits
from _printed_tolerance import angular_band_deg
from _surface_finish import surface_finish_by_key
from _drawing_leader_notes import add_attached_note, add_property_linked_callout
from _part_properties import part_drawing_unit
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from solidworks_mcp.adapters.solidworks.drawing import dimension_name
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _named_views import octant_view_name
from _machinist_review_mode import MachinistReviewMode
from _ms_drawing_contract import assert_manufacturing_dimensions
from ms_stop_block_notes import REBATE_NOTE, REBATE_NOTE_NUMBER
from solidworks_mcp.adapters.solidworks.drawing import add_note, auto_center_marks, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ms_stop_block"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (4.0, 1.0)
FRONT_CENTER = (0.155, 0.185)
RIGHT_CENTER = (0.315, FRONT_CENTER[1])
# 7 mm lower than the original 0.080 so the cover-tap callout's rows clear
# the underside view's top edge and its extension line.
BOTTOM_CENTER = (FRONT_CENTER[0], 0.073)
# Native 2:1 outline is 56.4 x 60.3 mm; fit above the title and below the end
# view, right of the four-line rebate callout.
ISO_CENTER = (0.372, 0.119)
FRONT_KEEP = {
    "BlockLength": (0.155, 0.235), "BlockHeight": (0.085, 0.185),
    "RoofChamferSize": (0.227, 0.240), "RoofChamferAngle": (0.207, 0.220),
    # Below the LOCATING EDGE label, between the hole-location witnesses.
    "PlateLeftFromEnd": (0.155, 0.132),
    "PlateRightFromEnd": (0.155, 0.116),
    "PlateFromHeadFace": (0.100, 0.163),
}
RIGHT_KEEP = {
    "BlockDepth": (0.315, 0.235), "WindowWidth": (0.262, 0.130),
    "WindowHeight": (0.370, 0.180), "RoofThickness": (0.355, 0.220),
    # Above the roof, left of the roof-thickness text, under the (.48).
    "BackWall": (0.345, 0.224),
    # Outside the open rebate mouth, its straight radial leader entering
    # through the open mouth below the Ra 63 finish symbol to the R.003 arc.
    "RebateCornerR": (0.240, 0.187),
}
BOTTOM_KEEP = {
    "ThumbFromEnd": (0.175, 0.031), "ThumbFromPlate": (0.090, 0.073),
}
# Rule 4: the rebate's two tight size bands and R.003 MAX corner carry SEE
# NOTE 1; the one numbered note (ms_stop_block_notes.REBATE_NOTE) names the
# stick that slides in it.
REBATE_NOTE_LINK = f"SEE NOTE {REBATE_NOTE_NUMBER}"
# Upper-left corner of the note text: the empty field left of the .84 and
# above the .56, clear of the cover-face view.
REBATE_NOTE_XY = (0.020, 0.262)
# Native horizontal size witnesses end at this corner rather than spanning
# the view; the shorter angle arc stays below the overall length dimension.
DIMENSION_CALLOUTS = {
    "RoofChamferSize": "2 CORNERS",
    "WindowWidth": REBATE_NOTE_LINK,
    "WindowHeight": REBATE_NOTE_LINK,
    "RebateCornerR": REBATE_NOTE_LINK,
}
# Leadered labels name the X=0 end and Y=0 edge the match-drill clamp aligns.
LOCATING_END_XY = (0.232, 0.160)
# The edge label sits wholly left of its leader's landing point, so the
# leader leaves the text's end, between the two hole witness lines.
LOCATING_EDGE_XY = (0.137, 0.150)
LOCATING_EDGE_X_MM = 5.0
# The title block owns the general internal thread class. Keep Hole Wizard's
# variable definitions, not the resolved text that would freeze drill/depths.
FINAL_SHEET_REMOVED_NOTES = ("Tapped Hole",)
# Rule 7: two lines of words under the native size and thread rows: the
# match-drill from its master, named by number and name as a matched pair
# (rule 4), and the clamp alignment. The ↧ depths run from the entry face by
# the symbol's own meaning.
COVER_HOLE_MATCH_DRILL = (
    f"MATCH-DRILL FROM {_config.parts('ms-stop-plate')['number']} STOP PLATE\n"
    f"WITH {part.MATCH_DRILL_DATUM_ALIGNMENT}"
)
# The 4-40 runs from the underside through the floor and opens into the
# rebate; THRU alone does not say which wall it stops at (rules 1, 12).
THUMB_HOLE_END = "INTO REBATE; ROOF NOT DRILLED"
# Hole Wizard length variables of each tap callout, by native name: the tap
# drill .XXX under DRILLED HOLES, the tap-drill and thread depths .XX (rule 3;
# ms_stop_spec.TAP_DEPTH_PRECISION).
COVER_TAP_PRECISION = {
    "hw-tapdrldia": part.HOLE_CALLOUT_PRECISION,
    "hw-tapdrldepth": part.TAP_DEPTH_PRECISION,
    "hw-threaddepth": part.TAP_DEPTH_PRECISION,
}
THUMB_TAP_PRECISION = {"hw-tapdrldia": part.HOLE_CALLOUT_PRECISION}
# Ra 63 uin symbol left of the right view's open rebate mouth, below the mating
# face label and above the RebateCornerR leader; its leader enters the mouth to
# the ceiling's mouth-side quarter.
SLIDE_FINISH_OFFSET = (-0.030, -0.012)

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, beside the constants of the
# code that prints it, in the part frame (ms_stop_block_spec: X = 0 is the
# LOCATING END, Y = 0 the LOCATING EDGE underside, Z = 0 the MHA-MS-03 mating
# face; the rebate runs through X and opens into Z = 0; the thumb tap runs +Y,
# the plate taps +Z). A band is the title block's row for the places the sheet
# prints (BLOCK_DRAWING_PRECISION_BY_NAME) on the printed nominal, the
# rebate's own +.010/0 (WINDOW_SIZE_TOLERANCE_MM) on the exact model nominal,
# or the DRILLED HOLES row on the native tap drills (HOLE_CALLOUT_PRECISION).
# The plate-tap stations print as references: the plate (MHA-MS-03) masters
# the match-drill, so they carry no band here. The declarations print nothing.
_P = part.BLOCK_DRAWING_PRECISION_BY_NAME
_SPEC = "ms_stop_spec"
_SELF = "draw_ms_stop_block"
_NOTES = "ms_stop_block_notes"
_FRAME = (_SPEC, "__frame__")
_BUILD = ("build_ms_stop_block", "build")
_PRECISION = (_SPEC, "BLOCK_DRAWING_PRECISION_BY_NAME")
_REBATE_BAND = (part.WINDOW_SIZE_TOLERANCE_MM[1], part.WINDOW_SIZE_TOLERANCE_MM[0])
_PLATE_NUMBER = _config.parts("ms-stop-plate")["number"]
_SLIDE_FINISH = surface_finish_by_key(part.BLOCK_SURFACE_FINISHES, "rebate_slide")


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


def _printed(
    name: str, value: float, *sources: Any
) -> tuple[list[float], tuple[Any, ...]]:
    """The title block's band for the printed places of dimension ``name``."""
    return (
        limits(value, _P[name], unit=part.UNIT),
        (*sources, (_SPEC, "UNIT"), _PRECISION),
    )


def _rebate(
    name: str, value: float, *sources: Any
) -> tuple[list[float], tuple[Any, ...]]:
    """The rebate's own +.010/0 on the exact model nominal (SEE NOTE 1)."""
    return (
        limits(value, _P[name], _REBATE_BAND, unit=part.UNIT),
        (*sources, (_SPEC, "WINDOW_SIZE_TOLERANCE_MM"), (_SELF, "DIMENSION_CALLOUTS")),
    )


part_metadata(
    model_sources=(
        _FRAME,
        _BUILD,
        (_SPEC, "BLOCK_LENGTH"),
        (_SPEC, "BLOCK_HEIGHT"),
        (_SPEC, "BLOCK_DEPTH"),
    ),
    precision_sources=(
        _PRECISION,
        (_SPEC, "HOLE_CALLOUT_PRECISION"),
        (_SPEC, "TAP_DEPTH_PRECISION"),
        (_SELF, "COVER_TAP_PRECISION"),
        (_SELF, "THUMB_TAP_PRECISION"),
    ),
)
# The X = 0 end, labelled LOCATING END: the match-drill clamp sets it flush
# with the plate's, and the .84, the thumb tap's .42 and the plate taps'
# (.150)/(.690) run from it. The rebate splits it.
requirement(
    "locating_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": (_plane("x", 0.0), (_FRAME, _BUILD)),
        "note": (
            part.LOCATING_END_NOTE,
            ((_SPEC, "LOCATING_END_NOTE"), (_SELF, "_label_locating_edges")),
        ),
    },
)
requirement(
    "far_end",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), part.BLOCK_LENGTH),),
    requirements=("length",),
    fields={
        "plane": (_plane("x", part.BLOCK_LENGTH), ((_SPEC, "BLOCK_LENGTH"),)),
        "length": _printed(
            "BlockLength",
            part.BLOCK_LENGTH,
            (_SPEC, "BLOCK_LENGTH"),
            (_SELF, "FRONT_KEEP"),
        ),
        "length_nominal": (part.BLOCK_LENGTH, ((_SPEC, "BLOCK_LENGTH"),)),
        "length_from": ("locating_end", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"length": _P["BlockLength"]},
)
# The Y = 0 underside, labelled LOCATING EDGE (its edge on the mating face):
# the match-drill clamp sets it flush with the plate's; the .56 and the plate
# taps' (.160) run from it, and the thumb tap enters it.
requirement(
    "locating_edge",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": (_plane("y", 0.0), (_FRAME, _BUILD)),
        "note": (
            part.LOCATING_EDGE_NOTE,
            ((_SPEC, "LOCATING_EDGE_NOTE"), (_SELF, "_label_locating_edges")),
        ),
    },
)
requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), part.BLOCK_HEIGHT),),
    requirements=("height",),
    fields={
        "plane": (_plane("y", part.BLOCK_HEIGHT), ((_SPEC, "BLOCK_HEIGHT"),)),
        "height": _printed(
            "BlockHeight",
            part.BLOCK_HEIGHT,
            (_SPEC, "BLOCK_HEIGHT"),
            (_SELF, "FRONT_KEEP"),
        ),
        "height_nominal": (part.BLOCK_HEIGHT, ((_SPEC, "BLOCK_HEIGHT"),)),
        "height_from": ("locating_edge", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"height": _P["BlockHeight"]},
)
# The Z = 0 face the stop plate covers (MHA-MS-03 MATING FACE): the rebate
# opens into it, splitting it into the roof lip and the floor; the plate taps
# and the thumb tap's .17 run from it.
requirement(
    "mating_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), part.PLATE_Z_MAX),),
    requirements=("plane",),
    fields={
        "plane": (_plane("z", part.PLATE_Z_MAX), ((_SPEC, "PLATE_Z_MAX"), _FRAME)),
        "note": (
            part.BLOCK_MATING_FACE_NOTE,
            ((_SPEC, "BLOCK_MATING_FACE_NOTE"), (_SELF, "build")),
        ),
        "mates": (
            _PLATE_NUMBER,
            ((_SPEC, "BLOCK_MATING_FACE_NOTE"), ("_config", "parts")),
        ),
    },
)
# The back face: the .15 back wall from the rebate's back face (RIGHT_KEEP
# "BackWall") controls it; the (.48) overall depth prints as a reference.
requirement(
    "back_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part.BLOCK_DEPTH),),
    requirements=("back_wall",),
    fields={
        "plane": (_plane("z", part.BLOCK_DEPTH), ((_SPEC, "BLOCK_DEPTH"),)),
        "back_wall": _printed(
            "BackWall",
            part.BACK_WALL_THICKNESS,
            (_SPEC, "BACK_WALL_THICKNESS"),
            (_SELF, "RIGHT_KEEP"),
        ),
        "back_wall_nominal": (
            part.BACK_WALL_THICKNESS,
            ((_SPEC, "BACK_WALL_THICKNESS"),),
        ),
        "back_wall_from": ("rebate_back", ((_SELF, "RIGHT_KEEP"),)),
        "depth_ref": (
            part.BLOCK_DEPTH,
            ((_SPEC, "BLOCK_DEPTH"), (_SPEC, "BLOCK_REFERENCE_DIMENSIONS")),
        ),
        "dimension_type": (
            "reference",
            (
                (_SPEC, "BLOCK_REFERENCE_DIMENSIONS"),
                ("build_ms_stop_block", "_author_reference_dimensions"),
            ),
        ),
    },
    precision={"back_wall": _P["BackWall"], "depth_ref": _P["BlockDepth"]},
)
# The rebate, through X and open into the mating face: its ceiling (the roof
# underside, .09 from the top: RoofThickness) is the one graded surface, Ra 63,
# where the stick's graduated face slides (BLOCK_SURFACE_FINISHES).
requirement(
    "rebate_ceiling",
    kind="face",
    faces=(_SLIDE_FINISH.face,),
    requirements=("roof_thickness", "finish_ra"),
    fields={
        "plane": (_plane("y", part.WINDOW_Y_MAX), ((_SPEC, "WINDOW_Y_MAX"),)),
        "roof_thickness": _printed(
            "RoofThickness",
            part.ROOF_THICKNESS,
            (_SPEC, "ROOF_THICKNESS"),
            (_SELF, "RIGHT_KEEP"),
        ),
        "roof_thickness_nominal": (part.ROOF_THICKNESS, ((_SPEC, "ROOF_THICKNESS"),)),
        "roof_thickness_from": ("top_face", ((_SELF, "RIGHT_KEEP"),)),
        "finish_ra": (_SLIDE_FINISH.roughness_um, ((_SPEC, "BLOCK_SURFACE_FINISHES"),)),
        "open_to": ("mating_face", (("ms_stop_geom", "rebate_profile"),)),
    },
    precision={"roof_thickness": _P["RoofThickness"], "finish_ra": 1},
)
# The rebate's two sliding-fit sizes (.134 and .330 +.010/0, SEE NOTE 1): the
# height on its floor from the ceiling, the width on its back face from the
# mating face (RIGHT_KEEP "WindowHeight", "WindowWidth"; DIMENSION_CALLOUTS).
_FIT = (
    REBATE_NOTE,
    ((_NOTES, "REBATE_NOTE"), (_NOTES, "DRAWING_NOTES")),
)
_FIT_LINK = (
    REBATE_NOTE_LINK,
    ((_SELF, "REBATE_NOTE_LINK"), (_SELF, "DIMENSION_CALLOUTS")),
)
requirement(
    "rebate_floor",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), part.WINDOW_Y_MIN),),
    requirements=("rebate_height",),
    fields={
        "plane": (_plane("y", part.WINDOW_Y_MIN), ((_SPEC, "WINDOW_Y_MIN"),)),
        "rebate_height": _rebate(
            "WindowHeight",
            part.WINDOW_HEIGHT,
            (_SPEC, "WINDOW_HEIGHT"),
            (_SELF, "RIGHT_KEEP"),
        ),
        "rebate_height_nominal": (part.WINDOW_HEIGHT, ((_SPEC, "WINDOW_HEIGHT"),)),
        "rebate_height_from": ("rebate_ceiling", ((_SELF, "RIGHT_KEEP"),)),
        "callout": _FIT_LINK,
        "note": _FIT,
    },
    precision={"rebate_height": _P["WindowHeight"]},
)
requirement(
    "rebate_back",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -part.WINDOW_Z_MAX),),
    requirements=("rebate_width",),
    fields={
        "plane": (_plane("z", part.WINDOW_Z_MAX), ((_SPEC, "WINDOW_Z_MAX"),)),
        "rebate_width": _rebate(
            "WindowWidth",
            part.WINDOW_WIDTH,
            (_SPEC, "WINDOW_WIDTH"),
            (_SELF, "RIGHT_KEEP"),
        ),
        "rebate_width_nominal": (part.WINDOW_WIDTH, ((_SPEC, "WINDOW_WIDTH"),)),
        "rebate_width_from": ("mating_face", ((_SELF, "RIGHT_KEEP"),)),
        "callout": _FIT_LINK,
        "note": _FIT,
    },
    precision={"rebate_width": _P["WindowWidth"]},
)
# The rebate's roof-to-back inside corner along X: the single limit R.003 MAX
# (RIGHT_KEEP "RebateCornerR", SEE NOTE 1), cut directly by the square 1/8 in
# carbide end mill so the stick seats flat on the roof without a corner relief
# (owner ruling 2026-11-26, #3739 Option A).
_CORNER_SOURCES = (
    (_SPEC, "REBATE_CORNER_R_MAX"),
    (_SPEC, "REBATE_CORNER_R_BAND"),
    (_SPEC, "REBATE_CORNER_R_TOL_TYPE"),
    (_SELF, "RIGHT_KEEP"),
    (_SELF, "_dress_rebate_corner_radius"),
)
requirement(
    "rebate_corner",
    kind="fillet",
    faces=(CylinderFace(2.0 * part.REBATE_CORNER_R_MAX),),
    requirements=("radius",),
    fields={
        "at": (
            [0.0, part.WINDOW_Y_MAX, part.WINDOW_Z_MAX],
            ((_SPEC, "WINDOW_Y_MAX"), (_SPEC, "WINDOW_Z_MAX"), _BUILD),
        ),
        "axis": ((1.0, 0.0, 0.0), (_FRAME,)),
        "radius": (
            limits(
                part.REBATE_CORNER_R_MAX,
                _P["RebateCornerR"],
                part.REBATE_CORNER_R_BAND,
                unit=part.UNIT,
            ),
            (*_CORNER_SOURCES, (_SPEC, "UNIT"), _PRECISION),
        ),
        "radius_nominal": (part.REBATE_CORNER_R_MAX, ((_SPEC, "REBATE_CORNER_R_MAX"),)),
        "corner_radius_max_design": (part.REBATE_CORNER_R_MAX, _CORNER_SOURCES),
        "callout": _FIT_LINK,
        "note": _FIT,
    },
    precision={"radius": _P["RebateCornerR"]},
)
# The two roof end chamfers, .04 x 45 deg, 2 CORNERS (FRONT_KEEP
# "RoofChamferSize", "RoofChamferAngle"): each breaks the roof's end edge,
# which runs +Z from ``at`` (chamfer 1 at the locating end, 2 at the far end).
_ANGULAR_BAND = angular_band_deg(unit=part.UNIT)
for _index, _x, _sign in ((1, 0.0, -1.0), (2, part.BLOCK_LENGTH, 1.0)):
    requirement(
        f"roof_chamfer_{_index}",
        kind="chamfer",
        faces=(
            PlanarFace(
                (_sign, 1.0, 0.0),
                (_sign * _x + part.BLOCK_HEIGHT - part.ROOF_END_CHAMFER)
                / math.sqrt(2.0),
            ),
        ),
        requirements=("size", "angle_deg"),
        fields={
            "at": (
                [_x, part.BLOCK_HEIGHT, 0.0],
                ((_SPEC, "BLOCK_LENGTH"), (_SPEC, "BLOCK_HEIGHT"), _BUILD),
            ),
            "axis": ((0.0, 0.0, 1.0), (_BUILD,)),
            "size": _printed(
                "RoofChamferSize",
                part.ROOF_END_CHAMFER,
                (_SPEC, "ROOF_END_CHAMFER"),
                (_SELF, "FRONT_KEEP"),
            ),
            "size_nominal": (part.ROOF_END_CHAMFER, ((_SPEC, "ROOF_END_CHAMFER"),)),
            "angle_deg": (
                [
                    round(part.ROOF_CHAMFER_ANGLE - _ANGULAR_BAND, 12),
                    round(part.ROOF_CHAMFER_ANGLE + _ANGULAR_BAND, 12),
                ],
                (
                    (_SPEC, "ROOF_CHAMFER_ANGLE"),
                    ("_printed_tolerance", "angular_band_deg"),
                    (_SELF, "FRONT_KEEP"),
                ),
            ),
            "angle_nominal_deg": (
                part.ROOF_CHAMFER_ANGLE,
                ((_SPEC, "ROOF_CHAMFER_ANGLE"),),
            ),
            "callout": (
                DIMENSION_CALLOUTS["RoofChamferSize"],
                ((_SELF, "DIMENSION_CALLOUTS"),),
            ),
        },
        precision={"size": _P["RoofChamferSize"], "angle_deg": _P["RoofChamferAngle"]},
    )
# The #4-40 thumbscrew tap, up from the underside through the floor and into
# the rebate, the roof not drilled (THUMB_HOLE_END): its tap drill prints .XXX
# on the DRILLED HOLES row (THUMB_TAP_PRECISION); .42 from the locating end
# and .17 from the mating face (BOTTOM_KEEP). THRU means through the floor
# only: the drill breaks out into the rebate floor and must stop short of the
# roof (``thru_length_ref``, the floor's thickness, is not printed).
_TAP_CALLOUT = ((_SELF, "build"), (_SELF, "_remove_general_thread_class"))
requirement(
    "thumb_tap",
    kind="threaded_hole",
    faces=(CylinderFace(part.THUMB_TAP_DRILL),),
    requirements=(
        "thread",
        "dia",
        "thru",
        "location_from_end",
        "location_from_mating_face",
    ),
    fields={
        "at": (list(part.THUMB_HOLE_POINTS[0]), ((_SPEC, "THUMB_HOLE_POINTS"),)),
        "axis": ((0.0, 1.0, 0.0), ((_SPEC, "THUMB_HOLE_NORMAL"),)),
        "thread": (
            f"{part.THUMB_TAP_SPEC.size} UNC-{part.THUMB_TAP_SPEC.thread_class}",
            ((_SPEC, "THUMB_TAP_SPEC"), *_TAP_CALLOUT),
        ),
        "dia": (
            drilled_limits(
                part.THUMB_TAP_DRILL,
                THUMB_TAP_PRECISION["hw-tapdrldia"],
                unit=part.UNIT,
            ),
            (
                (_SPEC, "THUMB_TAP_DRILL"),
                (_SPEC, "UNIT"),
                (_SELF, "THUMB_TAP_PRECISION"),
            ),
        ),
        "nominal_dia": (part.THUMB_TAP_DRILL, ((_SPEC, "THUMB_TAP_DRILL"),)),
        "thru": (True, ((_SPEC, "THUMB_TAP_SPEC"), *_TAP_CALLOUT)),
        "process": ("drill", ((_SPEC, "THUMB_TAP_SPEC"),)),
        "exit_face": ("rebate_floor", ((_SELF, "THUMB_HOLE_END"),)),
        "thru_length_ref": (part.FLOOR_THICKNESS, ((_SPEC, "FLOOR_THICKNESS"),)),
        "end_note": (THUMB_HOLE_END, ((_SELF, "THUMB_HOLE_END"),)),
        "location_from_end": _printed(
            "ThumbFromEnd",
            part.THUMB_AXIS_X,
            (_SPEC, "THUMB_AXIS_X"),
            (_SELF, "BOTTOM_KEEP"),
        ),
        "location_from_end_nominal": (part.THUMB_AXIS_X, ((_SPEC, "THUMB_AXIS_X"),)),
        "location_from_end_from": ("locating_end", ((_SELF, "BOTTOM_KEEP"),)),
        "location_from_mating_face": _printed(
            "ThumbFromPlate",
            part.THUMB_AXIS_Z,
            (_SPEC, "THUMB_AXIS_Z"),
            (_SELF, "BOTTOM_KEEP"),
        ),
        "location_from_mating_face_nominal": (
            part.THUMB_AXIS_Z,
            ((_SPEC, "THUMB_AXIS_Z"),),
        ),
        "location_from_mating_face_from": ("mating_face", ((_SELF, "BOTTOM_KEEP"),)),
    },
    precision={
        "dia": THUMB_TAP_PRECISION["hw-tapdrldia"],
        "location_from_end": _P["ThumbFromEnd"],
        "location_from_mating_face": _P["ThumbFromPlate"],
    },
)
# The two #2-56 blind plate taps (2X Ø.073 ↧.30, 2-56 UNC ↧.25 and
# COVER_HOLE_MATCH_DRILL): the tap drill is match-drilled through the stop
# plate MHA-MS-03, its master, clamped with the locating ends and edges flush,
# in that plate's traveler (``made_at = "pair_drill"``); this part's traveler
# taps them (bottoming tap, PLATE_TAP_SPEC). Depths run from the mating face
# and print .XX, the drill .XXX (COVER_TAP_PRECISION). Their stations print
# as references (.150)/(.690) from the locating end and (.160) from the
# locating edge: the plate's bands locate them.
_COVER_SOURCES = (
    (_SPEC, "PLATE_TAP_SPEC"),
    *_TAP_CALLOUT,
    (_SELF, "COVER_TAP_PRECISION"),
)
_PAIR = ((_SELF, "COVER_HOLE_MATCH_DRILL"), (_SPEC, "MATCH_DRILL_DATUM_ALIGNMENT"))
_REFERENCE = (
    (_SPEC, "PLATE_LOCATION_DIMENSIONS"),
    ("build_ms_stop_block", "_author_reference_dimensions"),
    (_SELF, "FRONT_KEEP"),
)
for _index, (_point, _end_dimension) in enumerate(
    zip(
        part.BLOCK_PLATE_HOLE_POINTS,
        ("PlateLeftFromEnd", "PlateRightFromEnd"),
        strict=True,
    ),
    1,
):
    requirement(
        f"plate_tap_{_index}",
        kind="threaded_hole",
        faces=(CylinderFace(part.PLATE_TAP_DRILL_DIA, contains_x_mm=_point[0]),),
        requirements=("thread", "dia", "thread_depth", "drill_depth"),
        fields={
            "at": (list(_point), ((_SPEC, "BLOCK_PLATE_HOLE_POINTS"),)),
            "axis": ((0.0, 0.0, 1.0), ((_SPEC, "PLATE_HOLE_NORMAL"),)),
            "thread": (
                f"{part.PLATE_TAP_SPEC.size} UNC-{part.PLATE_TAP_SPEC.thread_class}",
                _COVER_SOURCES,
            ),
            "dia": (
                drilled_limits(
                    part.PLATE_TAP_DRILL_DIA,
                    COVER_TAP_PRECISION["hw-tapdrldia"],
                    unit=part.UNIT,
                ),
                ((_SPEC, "PLATE_TAP_DRILL_DIA"), (_SPEC, "UNIT"), *_COVER_SOURCES),
            ),
            "nominal_dia": (
                part.PLATE_TAP_DRILL_DIA,
                ((_SPEC, "PLATE_TAP_DRILL_DIA"),),
            ),
            "process": ("drill", ((_SPEC, "PLATE_TAP_SPEC"),)),
            "thread_depth": (
                limits(
                    part.PLATE_TAP_THREAD_DEPTH,
                    COVER_TAP_PRECISION["hw-threaddepth"],
                    unit=part.UNIT,
                ),
                ((_SPEC, "PLATE_TAP_THREAD_DEPTH"), (_SPEC, "UNIT"), *_COVER_SOURCES),
            ),
            "thread_depth_nominal": (
                part.PLATE_TAP_THREAD_DEPTH,
                ((_SPEC, "PLATE_TAP_THREAD_DEPTH"),),
            ),
            "drill_depth": (
                limits(
                    part.PLATE_TAP_DRILL_DEPTH,
                    COVER_TAP_PRECISION["hw-tapdrldepth"],
                    unit=part.UNIT,
                ),
                ((_SPEC, "PLATE_TAP_DRILL_DEPTH"), (_SPEC, "UNIT"), *_COVER_SOURCES),
            ),
            "drill_depth_nominal": (
                part.PLATE_TAP_DRILL_DEPTH,
                ((_SPEC, "PLATE_TAP_DRILL_DEPTH"),),
            ),
            "tap_style": ("bottoming", ((_SPEC, "PLATE_TAP_SPEC"),)),
            "made_at": ("pair_drill", _PAIR),
            "pair_drill_master": (_PLATE_NUMBER, (*_PAIR, ("_config", "parts"))),
            "pair_drill_alignment": (part.MATCH_DRILL_DATUM_ALIGNMENT, _PAIR),
            "tapped_in": (
                _config.parts("ms-stop-block")["number"],
                (("_config", "parts"), _BUILD),
            ),
            "callout": (COVER_HOLE_MATCH_DRILL, ((_SELF, "COVER_HOLE_MATCH_DRILL"),)),
            "location_from_end_ref": (
                _point[0],
                ((_SPEC, "PLATE_HOLE_XS"), *_REFERENCE),
            ),
            "location_from_edge_ref": (
                _point[1],
                ((_SPEC, "PLATE_HOLE_Y"), *_REFERENCE),
            ),
            "location_from_end_ref_from": ("locating_end", _REFERENCE),
            "location_from_edge_ref_from": ("locating_edge", _REFERENCE),
            "dimension_type": ("reference", _REFERENCE),
        },
        precision={
            "dia": COVER_TAP_PRECISION["hw-tapdrldia"],
            "thread_depth": COVER_TAP_PRECISION["hw-threaddepth"],
            "drill_depth": COVER_TAP_PRECISION["hw-tapdrldepth"],
            "location_from_end_ref": _P[_end_dimension],
            "location_from_edge_ref": _P["PlateFromHeadFace"],
        },
    )


def _add_rebate_slide_finish(adapter: Any, right: Any) -> None:
    """Rule 6: grade the rebate ceiling the stick's graduated face slides on."""
    window_depth = part.WINDOW_Z_MAX - part.WINDOW_Z_MIN
    ceiling_xy = model_point_in_view(
        adapter, right, (
            part.BLOCK_LENGTH / 2000.0,
            part.WINDOW_Y_MAX / 1000.0,
            (part.WINDOW_Z_MIN + window_depth / 4.0) / 1000.0,
        ), label="rebate ceiling",
    )
    add_surface_finish(
        adapter, right,
        edge_xy=ceiling_xy,
        leader_attach_xy=ceiling_xy,
        symbol_xy=(ceiling_xy[0] + SLIDE_FINISH_OFFSET[0], ceiling_xy[1] + SLIDE_FINISH_OFFSET[1]),
        control=surface_finish_by_key(part.BLOCK_SURFACE_FINISHES, "rebate_slide"),
        label="rebate slide finish",
        char_height=0.0025,
    )


def _remove_general_thread_class(display: Any, *, last_line: str | None = None) -> None:
    """Suppress only the native class token; leave thread/drill variables live.

    ``last_line`` is appended below the native rows, e.g. where a THRU ends."""
    native = _early_bound(display, "IDisplayDimension")
    if not native.IsHoleCallout():
        raise RuntimeError("general thread class removal requires a native hole callout")
    definition = str(native.GetText(5) or "")  # swDimensionTextPrefixDefinition
    token = "<hw-threadclass>"
    if definition.count(token) != 1:
        raise RuntimeError(f"native tap callout lacks one thread-class variable: {definition!r}")
    before, _token, after = definition.partition(token)
    before = before.rstrip(" \t")
    if before.endswith("-"):
        before = before[:-1].rstrip(" \t")
    revised = before + after
    if last_line:
        revised = revised.rstrip("\r\n") + "\n" + last_line
    native.SetText(1, revised)  # swDimensionTextPrefix; void return
    if str(native.GetText(5) or "") != revised:
        raise RuntimeError("native tap class-token removal did not persist")


def _orient_bottom_view(adapter: Any, view: Any) -> None:
    """Make *Bottom the third-angle underside of the displayed *Back face."""
    native = _early_bound(view, "IView")
    native.Angle = math.pi
    rebuild_drawing(adapter, label="stop block underside orientation")
    applied = float(native.Angle)
    if not math.isfinite(applied) or abs(math.remainder(applied - math.pi, math.tau)) > 1e-9:
        raise RuntimeError(
            f"stop block underside rotation did not take: {applied!r} rad, expected pi"
        )


def _assert_reference_dimensions(adapter: Any, annotations: list[Any]) -> None:
    """Read back the source-owned parentheses and absence of bands on the
    receiver's plate locations and the reference envelope depth."""
    remaining = set(part.PLATE_LOCATION_DIMENSIONS | part.BLOCK_REFERENCE_DIMENSIONS)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        remaining.remove(name)
        display = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if (
            int(tolerance.Type) != 0
            or (str(display.GetText(1) or ""), str(display.GetText(2) or "")) != ("(", ")")
            or not bool(display.ShowDimensionValue)
        ):
            raise RuntimeError(f"{name}: imported reference lost its source display")
    if remaining:
        raise RuntimeError(f"missing reference dimensions: {sorted(remaining)}")


def _hide_tangent_edges(view: Any, *, label: str) -> None:
    """Hide the R.003 rebate-corner fillet's tangent edge on the cover-face view."""
    native = _early_bound(view, "IView")
    native.SetDisplayTangentEdges2(0)  # swTangentEdgesHidden
    if int(native.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError(f"failed to hide {label} tangent edges")
    native.UpdateViewDisplayGeometry()


def _dress_rebate_corner_radius(adapter: Any, annotations: list[Any]) -> None:
    """Keep RebateCornerR radial, single-limit MAX, non-reference, and outside-arrowed."""
    found = [
        item for item in annotations if dimension_name(adapter, item) == "RebateCornerR"
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one RebateCornerR on the sheet, found {len(found)}"
        )
    label = "MHA-MS-02 RebateCornerR"
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric) or int(display.Type2) != 5:  # swRadialDimension
        raise RuntimeError(f"{label}: imported as a non-radial dimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    lower, upper = deviations(part.REBATE_CORNER_R_BAND)
    if (
        not math.isclose(
            float(dimension.SystemValue),
            part.REBATE_CORNER_R_MAX / 1000.0,
            abs_tol=1e-9,
        )
        or int(tolerance.Type) != part.REBATE_CORNER_R_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: imported radius lost its model MAX limit")
    if (
        bool(dimension.IsReference())
        or bool(display.ShowParenthesis)
        or any(
            "(" in str(display.GetText(index) or "")
            or ")" in str(display.GetText(index) or "")
            for index in (1, 2)
        )
    ):
        raise RuntimeError(f"{label}: imported as a reference")
    display.ArcExtensionLineOrOppositeSide = False
    display.ArrowSide = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
    display.SolidLeader = False
    if (
        bool(display.ArcExtensionLineOrOppositeSide)
        or int(display.ArrowSide) != 1
        or bool(display.SolidLeader)
    ):
        raise RuntimeError(f"{label}: radial leader style did not persist")


def _label_locating_edges(adapter: Any, front: Any) -> None:
    """Leader the match-drill X=0 end and Y=0 edge on the cover-face view."""
    face_z = part.PLATE_Z_MAX / 1000.0
    for text, model_xyz, note_xy in (
        (part.LOCATING_END_NOTE, (0.0, 2.0 / 1000.0, face_z), LOCATING_END_XY),
        (part.LOCATING_EDGE_NOTE, (LOCATING_EDGE_X_MM / 1000.0, 0.0, face_z), LOCATING_EDGE_XY),
    ):
        edge_xy = model_point_in_view(adapter, front, model_xyz, label=text.lower())
        add_attached_note(adapter, front, text=text, entity_xy=edge_xy,
                          note_xy=note_xy, label=text.lower())


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source stop block missing: {SOURCE}")
    check("open stop block", adapter.open_model(str(SOURCE)))
    properties = ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity")
    read_required_properties(adapter.currentModel, properties,
                             required=("Number", "Material Specification", "Finish", "Quantity"))
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM,
                                        scale=SHEET_SCALE, layout=SPEC.layout,
                                        unit=part_drawing_unit("ms-stop-block"))
    stamp_drawing_summary(adapter, drawing, {
        0: "Measuring Stick Stop Block Manufacturing Drawing",
        1: "Harmonic Analyzer hobby-machinist book drawing",
        2: "Harmonic Analyzer Project", 3: "brass stop block; open rebate; native taps",
        4: "Generated from the project-owned ASME B drawing standard",
    })
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(SOURCE), "*Left", *RIGHT_CENTER, scale=SHEET_SCALE)
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=SHEET_SCALE)
    _orient_bottom_view(adapter, bottom)
    iso = place_view(adapter, str(SOURCE), octant_view_name(*part.BLOCK_ISOMETRIC_OCTANT),
                     *ISO_CENTER, scale=(2.0, 1.0))
    annotations = []
    for view, keep, label in ((front, FRONT_KEEP, "cover face"),
                              (right, RIGHT_KEEP, "open rebate end"),
                              (bottom, BOTTOM_KEEP, "thumbscrew face")):
        set_hidden_lines_removed(adapter, view)
        if view is front:
            _hide_tangent_edges(front, label="cover face")
        annotations += curate_view_dimensions(adapter, view, keep=keep, view_label=label,
                                               dimensions_by_feature=part.BLOCK_DRAWING_DIMENSIONS)
    set_hidden_lines_removed(adapter, iso)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _dress_rebate_corner_radius(adapter, annotations)
    if add_note(adapter, REBATE_NOTE, *REBATE_NOTE_XY) is None:
        raise RuntimeError("failed to add the stop block rebate note")
    plate_edge = model_point_in_view(
        adapter, front, (
            (part.PLATE_HOLE_XS[1] + part.PLATE_TAP_DRILL_DIA / 2.0) / 1000.0,
            part.PLATE_HOLE_Y / 1000.0, part.PLATE_Z_MAX / 1000.0,
        ), label="plate tap mouth")
    plate_callout = add_native_hole_callout(
        adapter, front, edge_xy=plate_edge, callout_xy=(0.072, 0.127),
        label="two cover blind taps",
    )
    _remove_general_thread_class(plate_callout, last_line=COVER_HOLE_MATCH_DRILL)
    set_hole_callout_precision(plate_callout, COVER_TAP_PRECISION, label="two cover blind taps")
    thumb_edge = model_point_in_view(
        adapter, bottom, (
            (part.THUMB_AXIS_X + part.THUMB_TAP_DRILL / 2.0) / 1000.0,
            0.0, part.THUMB_AXIS_Z / 1000.0,
        ), label="thumb tap mouth")
    thumb_callout = add_native_hole_callout(
        adapter, bottom, edge_xy=thumb_edge, callout_xy=(0.060, 0.056),
        label="thumbscrew tap through floor",
    )
    _remove_general_thread_class(thumb_callout, last_line=THUMB_HOLE_END)
    set_hole_callout_precision(thumb_callout, THUMB_TAP_PRECISION,
                               label="thumbscrew tap through floor")
    mating_edge = model_point_in_view(
        adapter, right, (
            part.BLOCK_LENGTH / 2000.0,
            (part.WINDOW_Y_MAX + (part.ROOF_THICKNESS - part.ROOF_END_CHAMFER) / 2.0) / 1000.0,
            part.PLATE_Z_MAX / 1000.0,
        ), label="cover mating face",
    )
    add_property_linked_callout(
        adapter, right, property_name="Mating Face Note",
        edge_xy=mating_edge, note_xy=(0.220, 0.210),
    )
    _add_rebate_slide_finish(adapter, right)
    _label_locating_edges(adapter, front)
    for view in (front, bottom):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError("stop tap centre marks failed")
    assert_manufacturing_dimensions(
        adapter, annotations, part.BLOCK_DRAWING_VALUES_BY_NAME,
        part.BLOCK_DRAWING_PRECISION_BY_NAME,
        bands={
            **{name: part.WINDOW_SIZE_TOLERANCE_MM for name in ("WindowWidth", "WindowHeight")},
            "RebateCornerR": deviations(part.REBATE_CORNER_R_BAND),
        },
        angular=frozenset({"RoofChamferAngle"}),
    )
    _assert_reference_dimensions(adapter, annotations)
    for view in (front, right, bottom):
        set_hidden_lines_removed(adapter, view)
    _hide_tangent_edges(front, label="cover face")
    add_property_linked_note(adapter, "Isometric View Note", ISO_CENTER[0] - 0.030, 0.085)
    return finalize_drawing(adapter, OUTPUTS,
                                  pdf_title="Measuring Stick Stop Block Manufacturing Drawing",
                                  scale=SHEET_SCALE, layout=SPEC.layout,
                                  redundant_note_substrings=FINAL_SHEET_REMOVED_NOTES,
                                  expected_redundant_notes=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
