r"""Manufacturing drawing of the rocker-strap sub-plate (MHA-CH-13-TL-01).

Shop tooling (owner ask 2026-11-17). One B sheet, laid as the plate sits in
the vise (rule 11): the top view at 1:2 across the top, the fence along its
top and the end stop at its left, every X from the stop face (X0) above and
below it, the notch depth, the hub's and the clamp taps' Y, the fence width
and the overall width from the fence face (Y0) to its left, both taps'
callouts on it; under it two sections cut across the plate at 2:1, the
pocket walls as rows from Y0 over the cut (farm run 20261118T001932117Z:
seven Y lanes beside the top view piled their texts): partial section A-A
through clamp pocket 3, its walls from Y0, its depth and the overall
thickness; section B-B through the hub counterbore, the fence height and the
counterbore's depth (farm runs r13 and r14: B-B never imported the widths or
the thickness from chords on the back and front faces); the isometric at
1:4. Every number is the part's own (``ch_rocker_strap_tl_sub_plate_spec``),
imported from the model.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any, Callable

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    remove_notes_matching,
)

import _telemetry
import ch_rocker_strap_tl_sub_plate_spec as spec
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import visible_view_entities
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _printed_limits import limits
from _section_axis import position_section_caption
from _session import run_build

# Learn-mode machinist review: findings are recorded, the build does not fail.
MACHINIST_REVIEW = MachinistReviewMode.LEARN

SPEC = DRAWINGS_BY_NAME["ch_rocker_strap_tl_sub_plate"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
UNIT = spec.UNIT
_P = spec.DRAWING_PRECISION_BY_NAME

# --- Layout (sheet metres) ------------------------------------------------------------
# 1:2 prints the 13 in plate 165 mm long; the sections at 2:1 print the .140
# pocket 7 mm deep. The title block holds the lower right (x >= 0.216,
# y <= 0.066); the inner border runs 0.0127..0.4191 x 0.0127..0.2667.
# Farm run 20261118T001932117Z's audit sets the spacing: text 3.6 mm tall
# needs 3.57 mm to the next text (rows 8 mm apart, not 7) and 2 mm to any
# extension line; a cutting line's letter stands 15.75..21.9 mm past the
# line's end along its arrow, 6.1 mm across.
SHEET_SCALE = (1.0, 2.0)
TOP_SCALE = (1, 2)
SECTION_SCALE = (2, 1)
ISO_SCALE = (1, 4)
_T = TOP_SCALE[0] / TOP_SCALE[1] / 1000.0
_S = SECTION_SCALE[0] / SECTION_SCALE[1] / 1000.0
# The top view's model origin (X0, Y0): the plate's left end at x 0.075, Y0
# at y 0.204 (the back edge at 0.210, the front edge at 0.172), low enough
# that the hub tap's callout and the X rows above it fit under the border.
TOP_ORIGIN = (0.075 - spec.LEFT_END_X * _T, 0.204)
# Each section prints model +Z up and +Y to the left: its arrows point +X,
# so each letter stands right of its line. Its origin is the sheet point of
# its plane's (Y0, Z0), the fence face's foot.
SECTION_A_ORIGIN = (0.070, 0.085)
SECTION_B_ORIGIN = (0.266, 0.1088)
# The cutting lines (model X, Y), each from 12 mm behind the back edge (its
# letter 3 mm over the back edge, under the hub tap's callout); A-A's stops
# in the floor 4.4 mm past pocket 3's back wall (a partial section: its
# letter inside the plate, clear of every line), B-B's runs 12 mm past the
# front edge (its letter over the X rows, 2.2 mm clear of clamp 3's
# extension).
SECTION_A_END_Y = -52.0
SECTION_A_LINE = (
    (spec.SECTION_A_X, spec.BACK_EDGE_Y + 12.0),
    (spec.SECTION_A_X, SECTION_A_END_Y),
)
SECTION_B_LINE = (
    (spec.SECTION_B_X, spec.BACK_EDGE_Y + 12.0),
    (spec.SECTION_B_X, spec.FRONT_EDGE_Y - 12.0),
)
# Each section's caption under its view; each point is the caption's top
# centre. B-B's view stands 7 mm higher than r15's so its caption clears
# the title block (farm run r15: over the view, 40 mm off).
SECTION_A_CAPTION_XY = (0.112, 0.058)
SECTION_B_CAPTION_XY = (0.317, 0.084)
ISO_CENTER = (0.365, 0.232)
ISO_NOTE_XY = (0.335, 0.196)


def top_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """The top view's sheet point of model (x, y)."""
    return (TOP_ORIGIN[0] + x_mm * _T, TOP_ORIGIN[1] + y_mm * _T)


def section_a_xy(y_mm: float, z_mm: float) -> tuple[float, float]:
    """Section A-A's sheet point of model (y, z) on its cutting plane."""
    return (SECTION_A_ORIGIN[0] - y_mm * _S, SECTION_A_ORIGIN[1] + z_mm * _S)


def section_b_xy(y_mm: float, z_mm: float) -> tuple[float, float]:
    """Section B-B's sheet point of model (y, z) on its cutting plane."""
    return (SECTION_B_ORIGIN[0] - y_mm * _S, SECTION_B_ORIGIN[1] + z_mm * _S)


_FRONT_Y = top_xy(0.0, spec.FRONT_EDGE_Y)[1]
_BACK_Y = top_xy(0.0, spec.BACK_EDGE_Y)[1]
_LEFT_X = top_xy(spec.LEFT_END_X, 0.0)[0]
_RIGHT_X = top_xy(spec.RIGHT_END_X, 0.0)[0]
_STATIONS = spec.CLAMP_STATIONS
_FENCE_TOP_A = section_a_xy(0.0, spec.FENCE_HEIGHT)[1]
_FENCE_TOP_B = section_b_xy(0.0, spec.FENCE_HEIGHT)[1]
# Top view: X sizes from X0 in rows at least 8 mm apart, above (the left end
# 12 mm over the back edge, the notch's end 20 mm, clear of the left end's
# outside arrow at X0, beside the hub tap's callout; over the callout the
# notch start and the overall length) and below (clamp 1's text right of its
# span, which is narrower than it; under the cutting lines' letters). Y sizes
# from Y0 to the left in five lanes, a span inner to every span holding one
# of its extension lines so no extension line crosses another's dimension
# line: the notch depth innermost, its text under its span (over it the fence
# width's and overall width's extension lines from the back corner); the
# fence width; the hub, its text low in its span, clear of the fence width's
# outside arrow; clamp 1's tap, its text between the hub's and the tap's
# levels; the overall width outermost, its text low in its span, under clamp
# 1's. The pocket length over pocket 1, right of its span, midway between the
# hub's Y extension line and the fence face; the radii and the counterbore's
# Ø right of the plate, each leader running out level from its feature.
TOP_KEEP: dict[str, tuple[float, float]] = {
    "LeftEnd": (_LEFT_X - 0.007, _BACK_Y + 0.012),
    "NotchLeftEnd": (top_xy(spec.NOTCH_LEFT_END / 2.0, 0.0)[0], _BACK_Y + 0.020),
    "NotchRightStart": (top_xy(spec.NOTCH_RIGHT_START / 2.0, 0.0)[0], _BACK_Y + 0.030),
    "PlateLength": (
        top_xy(spec.LEFT_END_X + spec.PLATE_LENGTH / 2.0, 0.0)[0],
        _BACK_Y + 0.038,
    ),
    "ClampTapX1": (top_xy(_STATIONS[0], 0.0)[0] + 0.008, _FRONT_Y - 0.013),
    "ClampTapX2": (top_xy(_STATIONS[1] / 2.0, 0.0)[0], _FRONT_Y - 0.021),
    "HubX": (top_xy(spec.HUB_X / 2.0, 0.0)[0], _FRONT_Y - 0.029),
    "ClampTapX3": (top_xy(_STATIONS[2] / 2.0, 0.0)[0], _FRONT_Y - 0.037),
    "ClampTapX4": (top_xy(_STATIONS[3] / 2.0, 0.0)[0], _FRONT_Y - 0.045),
    "HubY": (_LEFT_X - 0.027, top_xy(0.0, spec.HUB_Y)[1] + 0.0037),
    "FenceWidth": (_LEFT_X - 0.015, top_xy(0.0, spec.BACK_EDGE_Y / 2.0)[1]),
    "ClampTapY": (
        _LEFT_X - 0.045,
        top_xy(0.0, (spec.HUB_Y + spec.CLAMP_SCREW_Y) / 2.0)[1],
    ),
    "NotchDepth": (_LEFT_X - 0.003, top_xy(0.0, 0.0)[1] - 0.0045),
    "PlateWidth": (_LEFT_X - 0.055, _FRONT_Y + 0.00675),
    "PocketLength": (
        top_xy(_STATIONS[0], 0.0)[0] + 0.0135,
        top_xy(0.0, spec.HUB_Y / 2.0)[1],
    ),
    "NotchCornerR": (_RIGHT_X + 0.022, top_xy(0.0, spec.NOTCH_DEPTH / 2.0)[1]),
    "HubCboreDia": (_RIGHT_X + 0.024, top_xy(0.0, spec.HUB_Y)[1] + 0.0015),
    "PocketCornerR": (
        _RIGHT_X + 0.022,
        top_xy(0.0, spec.POCKET_BACK_WALL_Y)[1] - 0.0012,
    ),
}
# Section A-A: the pocket walls from Y0 in two rows over the cut, the back
# wall's (with its seat's words under its value) 14 mm over the near wall's;
# the pocket depth 4 mm right of the partial cut's end, its two rows beside
# its line (left clear of the title block, farm run r15) and under the
# floor's level so neither extension line runs through them (farm run
# 20261118T001932117Z: centred on its span, the floor's line struck it); the
# overall thickness left of the back face, its extension lines along the
# fence's top and the underside.
SECTION_A_KEEP: dict[str, tuple[float, float]] = {
    "PocketNearWallY": (
        section_a_xy(spec.POCKET_NEAR_WALL_Y / 2.0, 0.0)[0],
        _FENCE_TOP_A + 0.0085,
    ),
    "PocketBackWallY": (
        section_a_xy(spec.POCKET_BACK_WALL_Y / 2.0, 0.0)[0],
        _FENCE_TOP_A + 0.0225,
    ),
    "PocketDepth": (
        section_a_xy(SECTION_A_END_Y, 0.0)[0] + 0.004,
        section_a_xy(0.0, spec.POCKET_FLOOR_Z)[1] - 0.0075,
    ),
    "PlateThickness": (
        section_a_xy(spec.BACK_EDGE_Y, 0.0)[0] - 0.008,
        section_a_xy(0.0, (spec.FENCE_HEIGHT + spec.UNDERSIDE_Z) / 2.0)[1],
    ),
}
# Section B-B: the counterbore depth's two rows over the floor, beside its
# line in the counterbore's mouth, running right inside the border; the
# fence height's two rows above those, beside its line right of the fence
# face, the line passing left of the depth's text (farm run r15: the depth's
# line ran up through the fence height's text, and the depth's text off the
# right border, from the front wall).
SECTION_B_KEEP: dict[str, tuple[float, float]] = {
    "HubCboreDepth": (
        section_b_xy(spec.CBORE_SECTION_WALL_Y - 2.5, 0.0)[0],
        _FENCE_TOP_B + 0.0066,
    ),
    "FenceHeight": (section_b_xy(-18.0, 0.0)[0], _FENCE_TOP_B + 0.0195),
}
# Both taps' callouts on the top view (neither section cuts a tap). The clamp
# set's on clamp 4's drill, its text below right of the plate. The hub's on
# its drill, its text over B-B's cutting line's end (clear of its arrow and
# letter) and right of the notch's extension line, under the notch start's
# row: its leader rises across the back edge, the hub's shortest way out,
# right of B-B's line (farm run 20261118T001932117Z: led off section B-B, it
# ran 20 mm over the part).
CLAMP_TAP_CENTRE_MM = (_STATIONS[-1], spec.CLAMP_SCREW_Y)
CLAMP_TAP_CALLOUT_XY = (0.254, 0.165)
HUB_TAP_CENTRE_MM = (spec.HUB_X, spec.HUB_Y)
HUB_TAP_CALLOUT_XY = (0.1283, 0.2273)
# A drill circle's centre and radius read back from the view (mm).
_RIM_CENTRE_TOLERANCE_MM = 0.02
_RIM_RADIUS_TOLERANCE_MM = 0.01


def sheet_dimension_names() -> set[str]:
    return set().union(*spec.DRAWING_DIMENSIONS.values())


_KEEPS = (TOP_KEEP, SECTION_A_KEEP, SECTION_B_KEEP)
if sorted(name for keep in _KEEPS for name in keep) != sorted(sheet_dimension_names()):
    raise AssertionError("every marked sub-plate dimension prints once, in one view")

# --- Hole callouts -----------------------------------------------------------------
# Native Hole Wizard THRU tap rows (draw_ch_fulcrum_keeper's layout: the
# thread in part 5, the drill in part 7) kept in their order: the thread
# without its class (the title block states 2B), then the drill's Ø and
# DRILL. The clamp set's count opens the callout as one nX (rule 10); the hub
# tap's engagement is its last row (rule 20: the worst case as a plain fact).
DRILL_PROCESS = "DRILL"
_DRILL_TOKENS = ("<hw-tapdrldia>", "<hw-thrutapdrldia>")
_NATIVE_COUNT = re.compile(r"<NUM_INST>\s*X\s*")
_THREAD_CLASS = re.compile(r"\s*(?:-\s*)?<hw-threadclass>\s*", re.IGNORECASE)
TAP_PRECISION_PLACES = 3


def tap_callout_definitions(
    definitions: dict[int, str],
    *,
    count: str | None = None,
    last_row: str | None = None,
) -> dict[int, str]:
    """A native THRU tap callout's definition parts (5..8) in the shop's form:
    DRILL after the drill's Ø, the thread class dropped, the native instance
    count dropped from whichever row SolidWorks put it on (a THRU tap's drill
    row: farm run 20261118T000009756Z read "4-40 UNC THRU ALL / 4X Ø.09
    DRILL THRU ALL") and ``count`` opening the first row instead, and
    ``last_row`` appended under the native rows."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    joined = "\n".join(definitions.values())
    drills = [token for token in _DRILL_TOKENS if token in joined]
    if len(drills) != 1 or joined.count(drills[0]) != 1:
        raise RuntimeError(f"tap callout has no single drill size: {definitions!r}")
    if DRILL_PROCESS in joined:
        raise RuntimeError(f"tap callout already carries its rows: {definitions!r}")
    (drill,) = drills
    updated = {
        key: text.replace(drill, f"{drill} {DRILL_PROCESS}", 1)
        for key, text in definitions.items()
    }
    thread_parts = [
        key for key, text in updated.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(f"tap thread line is not in one callout part: {updated!r}")
    key = thread_parts[0]
    updated[key] = re.sub(r" {2,}", " ", _THREAD_CLASS.sub(" ", updated[key])).rstrip()
    owners = [key for key, text in updated.items() if _NATIVE_COUNT.search(text)]
    if len(owners) > 1:
        raise RuntimeError(f"tap callout carries more than one count: {updated!r}")
    for owner in owners:
        updated[owner] = _NATIVE_COUNT.sub("", updated[owner], count=1)
    if count:
        first = next(key for key in (5, 6, 7, 8) if updated[key].strip())
        updated[first] = f"{count} {updated[first].lstrip()}"
    if last_row:
        below = updated[8].rstrip()
        updated[8] = f"{below}\n{last_row}" if below else last_row
    return updated


def clamp_tap_definitions(definitions: dict[int, str]) -> dict[int, str]:
    return tap_callout_definitions(definitions, count=spec.CLAMP_TAP_COUNT)


def hub_tap_definitions(definitions: dict[int, str]) -> dict[int, str]:
    return tap_callout_definitions(definitions, last_row=spec.HUB_ENGAGEMENT_STATEMENT)


# --- Feature requirements (out/features/ch_rocker_strap_tl_sub_plate) ------------------
_SELF = "draw_ch_rocker_strap_tl_sub_plate"
_TOP = (_SELF, "TOP_KEEP")
_SEC_A = (_SELF, "SECTION_A_KEEP")
_SEC_B = (_SELF, "SECTION_B_KEEP")
_BAND = (spec.POCKET_BACK_WALL_TOL, -spec.POCKET_BACK_WALL_TOL)
_HUB_BAND = (spec.HUB_LOCATION_TOL, -spec.HUB_LOCATION_TOL)


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


part_metadata(
    fields={
        "material.thickness": (spec.PLATE_THICKNESS, ("PLATE_THICKNESS",)),
        "volume_mm3": (spec.V_FINISHED, ("V_FINISHED",)),
    },
    model_sources=("FENCE_HEIGHT", "UNDERSIDE_Z", "LEFT_END_X", "BACK_EDGE_Y"),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)

requirement(
    "plate_top",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), spec.PLATE_TOP_Z),),
    requirements=("plane",),
    fields={"plane": (_plane("z", spec.PLATE_TOP_Z), ("__frame__", "PLATE_TOP_Z"))},
)
requirement(
    "faced_top",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), spec.FENCE_HEIGHT),),
    requirements=("height",),
    fields={
        "plane": (_plane("z", spec.FENCE_HEIGHT), ("__frame__", "FENCE_HEIGHT")),
        "height": (
            limits(spec.FENCE_HEIGHT, _P["FenceHeight"], unit=UNIT),
            ("FENCE_HEIGHT", _SEC_B),
        ),
        "height_max_for": (
            "strap face cut",
            ("FACE_CUT_CLEARANCE_MIN", "STRAP_THICKNESS_MIN"),
        ),
    },
    precision={"height": _P["FenceHeight"]},
)
requirement(
    "underside",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -spec.UNDERSIDE_Z),),
    requirements=("thickness",),
    fields={
        "plane": (_plane("z", spec.UNDERSIDE_Z), ("__frame__", "UNDERSIDE_Z")),
        "thickness": (
            limits(spec.PLATE_THICKNESS, _P["PlateThickness"], unit=UNIT),
            ("PLATE_THICKNESS", _SEC_A),
        ),
        "finish": ("as received", ("__frame__",)),
    },
    precision={"thickness": _P["PlateThickness"]},
)
requirement(
    "fence_face",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("y", 0.0), ("__frame__",))},
)
requirement(
    "stop_face",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("x", 0.0), ("__frame__",))},
)
requirement(
    "front_edge",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), -spec.FRONT_EDGE_Y),),
    requirements=("width",),
    fields={
        "plane": (_plane("y", spec.FRONT_EDGE_Y), ("FRONT_EDGE_Y",)),
        "width": (
            limits(spec.PLATE_WIDTH, _P["PlateWidth"], unit=UNIT),
            ("PLATE_WIDTH", _TOP),
        ),
    },
    precision={"width": _P["PlateWidth"]},
)
requirement(
    "back_edge",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), spec.BACK_EDGE_Y),),
    requirements=("y",),
    fields={
        "plane": (_plane("y", spec.BACK_EDGE_Y), ("BACK_EDGE_Y",)),
        "y": (
            limits(spec.FENCE_WIDTH, _P["FenceWidth"], unit=UNIT),
            ("FENCE_WIDTH", _TOP),
        ),
    },
    precision={"y": _P["FenceWidth"]},
)
# The sawn ends: the stock length a traveler's stock fit reads.
requirement(
    "left_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), -spec.LEFT_END_X),),
    requirements=("plane",),
    fields={"plane": (_plane("x", spec.LEFT_END_X), ("LEFT_END_X",))},
)
requirement(
    "right_end",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), spec.RIGHT_END_X),),
    requirements=("length",),
    fields={
        "plane": (_plane("x", spec.RIGHT_END_X), ("RIGHT_END_X",)),
        "length": (
            limits(spec.PLATE_LENGTH, _P["PlateLength"], unit=UNIT),
            ("PLATE_LENGTH", _TOP),
        ),
    },
    precision={"length": _P["PlateLength"]},
)
for _name, _x_range, _end, _end_name, _inside_x in (
    (
        "fence_notch_left",
        (0.0, spec.NOTCH_LEFT_END),
        spec.NOTCH_LEFT_END,
        "NotchLeftEnd",
        10.0,
    ),
    (
        "fence_notch_right",
        (spec.NOTCH_RIGHT_START, spec.RIGHT_END_X),
        spec.NOTCH_RIGHT_START,
        "NotchRightStart",
        300.0,
    ),
):
    requirement(
        _name,
        kind="profile",
        faces=(
            PlanarFace((0.0, -1.0, 0.0), -spec.NOTCH_DEPTH, contains_x_mm=_inside_x),
        ),
        requirements=("x", "end_x", "depth", "corner_radius_max"),
        fields={
            "x": (
                list(_x_range),
                ("NOTCH_LEFT_END", "NOTCH_RIGHT_START", "RIGHT_END_X"),
            ),
            "end_x": (
                limits(_end, _P[_end_name], unit=UNIT),
                ("NOTCH_LEFT_END", "NOTCH_RIGHT_START", _TOP),
            ),
            "depth": (
                limits(spec.NOTCH_DEPTH, _P["NotchDepth"], unit=UNIT),
                ("NOTCH_DEPTH", _TOP),
            ),
            "floor_z": (spec.NOTCH_FLOOR_Z, ("NOTCH_FLOOR_Z",)),
            "corner_radius_max": (spec.CORNER_RADIUS, ("CORNER_RADIUS", _TOP)),
            "covers": (
                [list(station) for station in spec.PLAN_NOTCH_STATIONS],
                ("PLAN_NOTCH_STATIONS", "PLAN_FENCE_NOTCH_DEPTH"),
            ),
        },
        precision={"end_x": _P[_end_name], "depth": _P["NotchDepth"]},
    )
for _index, _station in enumerate(_STATIONS, 1):
    requirement(
        f"clamp_pocket_{_index}",
        kind="profile",
        faces=(
            PlanarFace((0.0, 0.0, 1.0), spec.POCKET_FLOOR_Z, contains_x_mm=_station),
        ),
        requirements=(
            "centre_x",
            "back_wall_y",
            "length",
            "depth",
            "corner_radius_max",
        ),
        fields={
            "centre_x": (_station, ("CLAMP_STATIONS", _TOP)),
            "y_walls": (
                [spec.POCKET_BACK_WALL_Y, spec.POCKET_NEAR_WALL_Y],
                ("POCKET_BACK_WALL_Y", "POCKET_NEAR_WALL_Y"),
            ),
            "back_wall_y": (
                limits(
                    -spec.POCKET_BACK_WALL_Y, _P["PocketBackWallY"], _BAND, unit=UNIT
                ),
                ("POCKET_BACK_WALL_Y", "POCKET_BACK_WALL_TOL", _SEC_A),
            ),
            "near_wall_y": (
                limits(-spec.POCKET_NEAR_WALL_Y, _P["PocketNearWallY"], unit=UNIT),
                ("POCKET_NEAR_WALL_Y", _SEC_A),
            ),
            "length": (
                limits(spec.POCKET_LENGTH, _P["PocketLength"], unit=UNIT),
                ("POCKET_LENGTH", _TOP),
            ),
            "depth": (
                limits(spec.POCKET_DEPTH, _P["PocketDepth"], unit=UNIT),
                ("POCKET_DEPTH", _SEC_A),
            ),
            "floor_z": (spec.POCKET_FLOOR_Z, ("POCKET_FLOOR_Z",)),
            "corner_radius_max": (spec.CORNER_RADIUS, ("CORNER_RADIUS", _TOP)),
            "seats": (spec.CLAMP_NUMBER, ("CLAMP_NUMBER",)),
        },
        precision={
            "back_wall_y": _P["PocketBackWallY"],
            "near_wall_y": _P["PocketNearWallY"],
            "length": _P["PocketLength"],
            "depth": _P["PocketDepth"],
        },
    )
    requirement(
        f"clamp_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(spec.CLAMP_TAP_DRILL, contains_x_mm=_station),),
        requirements=("at", "thread", "thru"),
        fields={
            "at": (
                [_station, spec.CLAMP_SCREW_Y, spec.POCKET_FLOOR_Z],
                ("CLAMP_STATIONS", "CLAMP_SCREW_Y", "POCKET_FLOOR_Z", _TOP),
            ),
            "axis": ((0.0, 0.0, 1.0), ("__frame__",)),
            "thread": (spec.CLAMP_TAP_THREAD, ("CLAMP_TAP_THREAD",)),
            "drill_dia": (spec.CLAMP_TAP_DRILL, ("CLAMP_TAP_DRILL",)),
            "thru": (True, ("CLAMP_TAP_SPEC",)),
            "thread_length": (spec.CLAMP_THREAD_LENGTH, ("CLAMP_THREAD_LENGTH",)),
        },
    )
requirement(
    "hub_counterbore",
    kind="counterbore",
    faces=(CylinderFace(spec.HUB_CBORE_DIA),),
    requirements=("at", "x", "y", "dia", "depth"),
    fields={
        "at": ([spec.HUB_X, spec.HUB_Y, spec.PLATE_TOP_Z], ("HUB_X", "HUB_Y", _TOP)),
        "axis": ((0.0, 0.0, 1.0), ("__frame__",)),
        "x": (
            limits(spec.HUB_X, _P["HubX"], _HUB_BAND, unit=UNIT),
            ("HUB_X", "HUB_LOCATION_TOL", _TOP),
        ),
        "y": (
            limits(-spec.HUB_Y, _P["HubY"], _HUB_BAND, unit=UNIT),
            ("HUB_Y", "HUB_LOCATION_TOL", _TOP),
        ),
        "dia": (
            limits(spec.HUB_CBORE_DIA, _P["HubCboreDia"], unit=UNIT),
            ("HUB_CBORE_DIA", _TOP),
        ),
        "depth": (
            limits(spec.HUB_CBORE_DEPTH, _P["HubCboreDepth"], unit=UNIT),
            ("HUB_CBORE_DEPTH", _SEC_B),
        ),
        "floor_z": (spec.COUNTERBORE_FLOOR_Z, ("COUNTERBORE_FLOOR_Z",)),
        "locates": (spec.PLUG_NUMBER, ("PLUG_NUMBER",)),
    },
    precision={
        "x": _P["HubX"],
        "y": _P["HubY"],
        "dia": _P["HubCboreDia"],
        "depth": _P["HubCboreDepth"],
    },
)
requirement(
    "hub_tap",
    kind="hole",
    faces=(CylinderFace(spec.HUB_TAP_DRILL),),
    requirements=("at", "thread", "thru", "engagement_min"),
    fields={
        "at": (
            [spec.HUB_X, spec.HUB_Y, spec.COUNTERBORE_FLOOR_Z],
            ("HUB_X", "HUB_Y", "COUNTERBORE_FLOOR_Z", _TOP),
        ),
        "axis": ((0.0, 0.0, 1.0), ("__frame__",)),
        "thread": (spec.HUB_TAP_THREAD, ("HUB_TAP_THREAD",)),
        "drill_dia": (spec.HUB_TAP_DRILL, ("HUB_TAP_DRILL",)),
        "thru": (True, ("HUB_TAP_SPEC",)),
        "engagement_nominal": (spec.HUB_THREAD_LENGTH, ("HUB_THREAD_LENGTH",)),
        "engagement_min": (
            spec.HUB_THREAD_LENGTH_MIN,
            ("HUB_THREAD_LENGTH_MIN", "HUB_ENGAGEMENT_STATEMENT"),
        ),
    },
)


# --- Native drawing ------------------------------------------------------------------
def _metres(point_mm: tuple[float, float, float]) -> tuple[float, float, float]:
    return (point_mm[0] / 1000.0, point_mm[1] / 1000.0, point_mm[2] / 1000.0)


def _sheet_steps(
    adapter: Any, view: Any, anchor_mm: tuple[float, float, float], *, label: str
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """The sheet steps ``view`` prints model +X, +Y and +Z in, 1 mm from
    ``anchor_mm`` (an end-on axis reads a zero step)."""
    x, y, z = anchor_mm
    base, east, north, up = model_points_in_view(
        adapter,
        view,
        tuple(
            _metres(point)
            for point in ((x, y, z), (x + 1.0, y, z), (x, y + 1.0, z), (x, y, z + 1.0))
        ),
        label=label,
    )
    return tuple(
        (float(p[0] - base[0]), float(p[1] - base[1])) for p in (east, north, up)
    )


def _place_point(
    adapter: Any,
    view: Any,
    point_mm: tuple[float, float, float],
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    """Move ``view`` so the model point lands on ``target`` (sheet m); a
    section's Position is its cut-plane origin, so this is read back."""
    native = _early_bound(view, "IView")
    point = _metres(point_mm)
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        here = model_point_in_view(
            adapter, native, point, label=f"{label} pass {attempt}"
        )
        if math.dist(here, target) <= 1e-4:
            return
        position = tuple(float(value) for value in native.Position)
        moved = [position[i] + target[i] - here[i] for i in range(2)]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError(f"failed to move the {label}")
        rebuild_drawing(adapter, label=f"place {label}")
    raise RuntimeError(f"{label}: point sits at {here!r}, not {target!r}")


def _check_top_view(adapter: Any, view: Any) -> None:
    """The top view prints model +X to the sheet's right and +Y up (the
    fence at the top, the stop at the left)."""
    east, north, _up = _sheet_steps(
        adapter, view, (0.0, 0.0, 0.0), label="top view axes"
    )
    if not (
        east[0] > 0.0
        and abs(east[1]) < 1e-7
        and north[1] > 0.0
        and abs(north[0]) < 1e-7
    ):
        raise RuntimeError(
            f"top view prints +X toward {east!r} and +Y toward {north!r}"
        )


def _orient_section(
    adapter: Any, section: Any, anchor_mm: tuple[float, float, float], *, label: str
) -> None:
    """Turn ``section`` until model +Z runs up the sheet, then look the cut
    the way that prints model +Y to the left: looking along +X, so the arrows
    point +X and each letter stands right of its cutting line."""
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    for attempt in range(4):
        _east, north, up = _sheet_steps(
            adapter, native, anchor_mm, label=f"{label} axes"
        )
        if up[1] > 0.0 and abs(up[0]) <= 1e-7 and north[0] < 0.0:
            _telemetry.info(f"{label}: +Y left, +Z up after {attempt} step(s)")
            return
        if up[1] > 0.0 and abs(up[0]) <= 1e-7:
            reversed_cut = not bool(cut.GetReversedCutDirection())
            cut.SetReversedCutDirection(reversed_cut)
            rebuild_drawing(adapter, label=f"{label} cut reversed")
            continue
        native.Angle = float(native.Angle) + math.pi / 2.0 - math.atan2(up[1], up[0])
        rebuild_drawing(adapter, label=f"{label} turned")
    raise RuntimeError(f"{label} does not print +Y left and +Z up: {north!r}, {up!r}")


def _section(
    adapter: Any,
    source_model: Any,
    top: Any,
    *,
    letter: str,
    line_mm: tuple[tuple[float, float], tuple[float, float]],
    origin: tuple[float, float],
    reference: str,
    keep: dict[str, tuple[float, float]],
    caption_xy: tuple[float, float],
    label: str,
) -> tuple[Any, list[Any]]:
    """A section on the cutting line ``line_mm`` (model X, Y at Z0) across
    the plate, oriented and placed with its plane's (Y0, Z0) on ``origin``,
    its sizes imported from ``reference`` and its caption at ``caption_xy``.

    A section imports no sketch or extrusion size (farm run
    20261117T234245842Z), so each is owned by a hidden reference sketch lying
    in the cutting plane. A derived view takes that sketch as the part shows
    it when cut and selects it through its base view, so the section is cut
    and curated while the part shows it (draw_pd_platen's ``_floor_section``).
    The sketch's chords run along Z, so the top view, which keeps it shown,
    sees each one end-on."""
    (x0, y0), (x1, y1) = line_mm
    start = model_point_in_view(
        adapter, top, _metres((x0, y0, 0.0)), label=f"{label} start"
    )
    end = model_point_in_view(
        adapter, top, _metres((x1, y1, 0.0)), label=f"{label} end"
    )
    anchor_mm = (x0, 0.0, 0.0)
    with part_sketches_shown(
        adapter, source_model, (reference,), label=f"{label} reference", base_view=top
    ):
        section = create_section_view(
            adapter,
            top,
            line_start=(float(start[0]), float(start[1])),
            line_end=(float(end[0]), float(end[1])),
            view_xy=origin,
            section_label=letter,
            scale=SECTION_SCALE,
            partial=True,
            label=label,
        )
        _orient_section(adapter, section, anchor_mm, label=label)
        _place_point(adapter, section, anchor_mm, origin, label=label)
        set_hidden_lines_removed(adapter, section)
        annotations = curate_view_dimensions(
            adapter,
            section,
            keep=keep,
            view_label=label,
            dimensions_by_feature=spec.DRAWING_DIMENSIONS,
        )
    position_section_caption(adapter, section, caption_xy, label=label)
    return section, annotations


def _drill_rim(
    view: Any, centre_mm: tuple[float, float], diameter_mm: float, *, label: str
) -> Any:
    """A tap's drill circle in the top view, found among the view's visible
    circles by centre and radius (draw_pd_platen's ``_front_hole_rims``: at
    1:2 a coordinate pick can take the concentric thread or counterbore)."""
    found = []
    for raw in visible_view_entities(view, 1, label=f"{label} rims"):
        edge = _early_bound(raw, "IEdge")
        raw_curve = edge.GetCurve()
        if raw_curve is None:
            continue
        curve = _early_bound(raw_curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        if (
            math.dist(params[:2], centre_mm) <= _RIM_CENTRE_TOLERANCE_MM
            and abs(params[6] - diameter_mm / 2.0) <= _RIM_RADIUS_TOLERANCE_MM
        ):
            found.append(edge)
    if len(found) != 1:
        raise RuntimeError(f"{label}: {len(found)} drill circles at {centre_mm!r}")
    return found[0]


def _rewrite_callout_definitions(
    display: Any, rewrite: Callable[[dict[int, str]], dict[int, str]]
) -> str:
    """Write a native hole callout's rewritten definitions, prove they
    persisted and return the resolved text."""
    native = _early_bound(display, "IDisplayDimension")
    definitions = {key: str(native.GetText(key) or "") for key in (5, 6, 7, 8)}
    updated = rewrite(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {key: str(native.GetText(key) or "") for key in (5, 6, 7, 8)}
    if persisted != updated:
        raise RuntimeError(f"callout definitions did not persist: {persisted!r}")
    return "\n".join(str(native.GetText(key) or "") for key in (1, 2, 3, 4))


def _tap_callout(
    adapter: Any,
    top: Any,
    centre_mm: tuple[float, float],
    drill_mm: float,
    callout_xy: tuple[float, float],
    rewrite: Callable[[dict[int, str]], dict[int, str]],
    *,
    label: str,
) -> str:
    """The native tap callout on its drill circle in the top view, picked on
    the rim's side toward ``callout_xy``, rewritten."""
    centre = top_xy(*centre_mm)
    angle = math.atan2(callout_xy[1] - centre[1], callout_xy[0] - centre[0])
    rim = drill_mm / 2.0 * _T
    display = add_native_hole_callout(
        adapter,
        top,
        edge_xy=(centre[0] + rim * math.cos(angle), centre[1] + rim * math.sin(angle)),
        edge=_drill_rim(top, centre_mm, drill_mm, label=label),
        callout_xy=callout_xy,
        label=label,
    )
    resolved = _rewrite_callout_definitions(display, rewrite)
    if (
        resolved.count(DRILL_PROCESS) != 1
        or "2B" in resolved
        or "<NUM_INST>" in resolved
    ):
        raise RuntimeError(f"{label} callout text did not resolve: {resolved!r}")
    native = _early_bound(display, "IDisplayDimension")
    definition = "\n".join(str(native.GetText(part) or "") for part in (5, 6, 7, 8))
    names = [token.strip("<>") for token in _DRILL_TOKENS if token in definition]
    set_hole_callout_precision(display, {names[0]: TAP_PRECISION_PLACES}, label=label)
    return resolved


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source sub-plate missing: {SOURCE}")
    check("open sub-plate", adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    required = ("Number", "Material Specification", "Finish", "Quantity")
    read_required_properties(
        adapter.currentModel,
        ("Revision", "Title", *required, "Isometric View Note"),
        required=required,
    )
    drawing, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=UNIT,
    )
    stamp_drawing_summary(
        adapter,
        drawing,
        {
            0: "Rocker Strap Sub-Plate Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: "sub-plate for the rocker strap MHA-CH-13; MHA-CH-13-TL-01",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    top = place_view(adapter, str(SOURCE), "*Front", *TOP_ORIGIN, scale=TOP_SCALE)
    _check_top_view(adapter, top)
    _place_point(adapter, top, (0.0, 0.0, 0.0), TOP_ORIGIN, label="top view")
    set_hidden_lines_removed(adapter, top)
    annotations: list[Any] = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top view",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    section_a, section_a_dims = _section(
        adapter,
        source_model,
        top,
        letter="A",
        line_mm=SECTION_A_LINE,
        origin=SECTION_A_ORIGIN,
        reference=spec.SECTION_A_REFERENCE,
        keep=SECTION_A_KEEP,
        caption_xy=SECTION_A_CAPTION_XY,
        label="section A-A",
    )
    section_b, section_b_dims = _section(
        adapter,
        source_model,
        top,
        letter="B",
        line_mm=SECTION_B_LINE,
        origin=SECTION_B_ORIGIN,
        reference=spec.SECTION_B_REFERENCE,
        keep=SECTION_B_KEEP,
        caption_xy=SECTION_B_CAPTION_XY,
        label="section B-B",
    )
    annotations += section_a_dims + section_b_dims
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The iso too (draw_dt_cone_tip_gear_tl_cutter_bar): from HLR the shaded
    # display really changes and the taps' cosmetic threads take precision.
    set_hidden_lines_removed(adapter, iso)
    printed = sorted(dimension_name(adapter, annotation) for annotation in annotations)
    if printed != sorted(sheet_dimension_names()):
        raise RuntimeError(
            f"sheet prints {printed}, the part marks {sorted(sheet_dimension_names())}"
        )
    assert_imported_precision(adapter, annotations, spec.DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, spec.DIMENSION_CALLOUTS)

    adapter.currentModel.GraphicsRedraw2()
    clamp = _tap_callout(
        adapter,
        top,
        CLAMP_TAP_CENTRE_MM,
        spec.CLAMP_TAP_DRILL,
        CLAMP_TAP_CALLOUT_XY,
        clamp_tap_definitions,
        label="clamp taps",
    )
    if not clamp.lstrip().startswith(f"{spec.CLAMP_TAP_COUNT} "):
        raise RuntimeError(f"clamp tap callout does not open with its count: {clamp!r}")
    hub = _tap_callout(
        adapter,
        top,
        HUB_TAP_CENTRE_MM,
        spec.HUB_TAP_DRILL,
        HUB_TAP_CALLOUT_XY,
        hub_tap_definitions,
        label="hub tap",
    )
    if spec.HUB_ENGAGEMENT_STATEMENT not in hub:
        raise RuntimeError(f"hub tap callout lost its engagement row: {hub!r}")
    for view in (top, section_a, section_b):
        set_hidden_lines_removed(adapter, view)

    drawing.ClearSelection2(True)
    _early_bound(drawing, "IDrawingDoc").EditSheet()
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # Each tap is stated once, on its native callout: SolidWorks' automatic
    # "Tapped Hole" labels on the cosmetic threads go, and the final sweep
    # fails on any that appear later (draw_dt_cone_tip_gear_tl_cutter_bar).
    import_cosmetic_threads(adapter, iso)
    removed_tap_labels = remove_notes_matching(adapter, "Tapped Hole")
    _telemetry.info(f"removed {removed_tap_labels} automatic tapped-hole label(s)")
    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Strap Sub-Plate Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=0,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
