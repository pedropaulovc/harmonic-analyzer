r"""Create the drawing for the oblique-trammel jig's pivot block (MHA-CH-06-TL-22)."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Callable
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
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
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_dimension_import import curate_view_dimensions
import _drawing_hidden_sketches as hidden_sketches
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_hole_callout import (
    add_native_hole_callout,
    compose_hole_callout_prefix,
    set_hole_callout_precision,
)
from _drawing_leaders import dimension_segments, distance_to_box, set_near_side_diameter
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _hole_callout_thread_class import omit_title_block_thread_class
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _printed_limits import limits
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_pivot_block_spec as part_spec
from ch_rocker_arm_tl_oblique_pivot_block_spec import (
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    BLOCK_X0,
    BLOCK_X1,
    BOLT_X,
    BOLT_Y,
    BORE_X,
    CALLOUTS_ABOVE,
    CALLOUTS_BELOW,
    CBORE_FLOOR,
    CBORE_FLOOR_REFERENCE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GEOMETRIC_TOLERANCES_MM,
    SCREW_MATE_CALLOUT,
    SIDE_CALLOUT_BELOW,
    SIDE_CALLOUT_PRECISION,
    SIDE_CBORE_DIA,
    SIDE_HOLE_DIA,
    SIDE_SCREW_HOLES,
    SIDE_SCREW_REFERENCE,
)

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_pivot_block"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# The bearing/carriage sheet retains the original interfaces at 3:2.
# A separate 2:1 plan owns the wing's direct bearing-axis reach and four cap
# taps. Both reference the bearing axis directly, never a loose edge chain.
# Section A-A is on the bearing axis; full section B-B shows the remaining
# carriage-counterbore floor from the carriage seat. Removed view C, on its
# own sheet, looks at the original tail's +Y face and carries the nut-bracket
# hole stations. The register-depth section has its own parent/cutting line.
SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = (3, 2)
SHEET_NAMES = (
    "Bearing and carriage", "Capture wing", "Register recesses",
    "Register depth", "Nut bracket interface",
)
CAPTURE_SCALE = (2, 1)
ISO_SCALE = (1, 2)
PLAN_CENTER = (0.130, 0.192)
# Lower A-A 17 mm to reserve a complete outer overall tier below 67.500.
SECTION_A_CENTER = (PLAN_CENTER[0], 0.071)
ISO_CENTER = (0.385, 0.232)
# The single-row, 134 mm floor qualifier owns the upper lane over B-B.
# Keep sheet 1's pictorial 8 mm lower; the other sheets retain ISO_CENTER.
BEARING_ISO_CENTER = (ISO_CENTER[0], ISO_CENTER[1] - 0.008)
ISO_NOTE_XY = (0.355, 0.200)
BEARING_ISO_NOTE_XY = (ISO_NOTE_XY[0], ISO_NOTE_XY[1] - 0.008)
# Right of the Ø25's stack under the bore (SECTION_A_KEEP), clear of its
# +X witness; the seat frame stands above it.
CAPTION_A_XY = (0.161, 0.035)
# View C no longer shares B-B's caption/dimension lanes.
SIDE_CENTER = (0.210, 0.155)
SIDE_VIEW_LETTER = "C"
SIDE_VIEW_LETTER_HEIGHT = 0.005
SIDE_VIEW_ARROW_TIP = (5.0, BLOCK_WIDTH / 2.0, BLOCK_HEIGHT)
SIDE_VIEW_LETTER_OFFSET = (-0.0018, 0.0105)
SIDE_VIEW_CAPTION = f"VIEW {SIDE_VIEW_LETTER}"
SIDE_VIEW_CAPTION_XY = (0.210, 0.115)
# Cutting line on the top face, past the outline (model mm).
CUT_A_X = (BLOCK_X0 - 4.0, BLOCK_X1 + 4.0)
# Full-width B-B through the unchanged -X carriage-hole column.
CUT_B_Y = (-part_spec.WING_WIDTH / 2.0 - 4.0, part_spec.WING_WIDTH / 2.0 + 4.0)
# Aligned section: +Y reads up and +Z right (_orient_section_b proves both).
SECTION_B_CENTER = (0.320, 0.193)
SECTION_B_ANCHOR = (-BOLT_X, 0.0, BLOCK_HEIGHT / 2.0)
CAPTION_B_XY = (0.320, 0.132)
# The floor's witness lines extend beyond the complete wing, not the tail.
SECTION_B_KEEP: dict[str, tuple[float, float, float]] = {
    "CboreFloor": (-BOLT_X, part_spec.WING_WIDTH / 2.0 + 7.0, CBORE_FLOOR / 2.0),
}

# All dimension-text placements below are model points (mm), projected into
# the corresponding native view. Cap tap dimensions use their own sheet.
_H = BLOCK_HEIGHT
_HW = BLOCK_WIDTH / 2.0
_HOLE_PLACES = part_spec.HOLE_STATION_PLACES
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    "BoreStationX": (-41.0, -part_spec.WING_WIDTH / 2.0 - 4.0, _H),
    "HoleColumn1X": (-25.0, -part_spec.WING_WIDTH / 2.0 - 8.0, _H),
    "HoleColumn2X": (-5.0, -part_spec.WING_WIDTH / 2.0 - 12.0, _H),
    "BlockLength": (2.5, -part_spec.WING_WIDTH / 2.0 - 22.0, _H),
    # Y stations reference the original tail-side datum plane, not the wing.
    "HoleRow1Y": (30.0, -16.5, _H),
    # f441 native: 7/20/33 columns were only 7.5 mm apart. Give each value
    # its own column, 12 mm apart on paper; retain every baseline attachment.
    "BoreStationY": (38.0, -10.0, _H),
    "HoleRow2Y": (46.0, -3.5, _H),
    # ENFORCE review: at X52 the 33.000 line (X46) struck the centred
    # "SETS C'BORE / WALL 2.10 MIN" rows (~27 mm wide on paper). X60 stands
    # the whole block right of that line with ~7 mm of air.
    "BlockWidth": (60.0, 8.0, _H),
    "BoreDia": (BLOCK_X0 - 15.5, 15.5, _H),
}
# The 9 mm witnesses stay with A-A; its complete bracket identity has an
# independent shelf to the right of the folded web callout.
SECTION_A_TEXT_POSITIONS = {"SideScrewRowZ": (0.267, 0.126)}
CAPTURE_KEEP = {
    "WingAxisReach": ((BORE_X + part_spec.WING_X1) / 2.0, 41.0, _H),
    # 2X half-location replaces the full-width/symmetry-prose authority.
    # X283.5 is beyond the native plan's X275.088 right outline and left
    # of the upper cap-pattern block (native left edge X289.058).
    "WingHalfWidth": (27.0, 18.0, _H),
    "CapTapLeftX": (-39.5, -43.0, _H),
    "CapTapRightX": (-24.5, -51.0, _H),
    "CapTapLowerY": (35.0, -12.5, _H),
    "CapTapUpperY": (43.0, 12.5, _H),
}
# Offset only linear text, leaving each native dimension line outside the
# silhouette. None of these complete qualifiers sits between its witnesses.
CAPTURE_TEXT_POSITIONS = {
    "WingAxisReach": (0.300, 0.250),
    "CapTapLeftX": (0.070, 0.100),
    # f441: caption X283.558..336.442 struck the X299.5 lower-Y line.
    # Shift the complete native block 35 mm, not its value or witnesses.
    "CapTapRightX": (0.345, 0.105),
}
REGISTER_PLAN_CENTER = (0.170, 0.190)
REGISTER_SECTION_PLAN_CENTER = (0.140, 0.170)
REGISTER_SECTION_CENTER = (0.325, 0.165)
REGISTER_SECTION_REGION = (0.240, 0.070, 0.410, 0.260)
REGISTER_KEEP: dict[str, tuple[float, float, float]] = {
    "CapRegisterLeftX": (BORE_X - 8.0, -41.0, _H),
    "CapRegisterRightX": (BORE_X + 8.0, -49.0, _H),
    "CapRegisterLowerY": (35.0, -12.0, _H),
    "CapRegisterUpperY": (45.0, 12.0, _H),
    "CapRegister1Dia": (BLOCK_X0 - 17.0, -26.0, _H),
    # At 2:1, raising the entire native block 12 mm puts its bottom shoulder
    # above the upper-Y station's witness/line (native top Y238 mm).
    "CapRegister2Dia": (BLOCK_X1 + 10.0, 33.0, _H),
}
# Paper offsets from the cut register's projected mid-depth, after fitting:
# the line stands this far OUTBOARD of the register (away from the bearing
# bore), so both witnesses stay short. Its text has a separate shelf.
REGISTER_SECTION_KEEP = {"CapRegisterDepth": (0.0, 0.012)}
# A constant-X plane cuts one register diametrically, not both skewed
# stations. The unchanged common cut depth still controls both recesses (2X).
# ENFORCE review: through register 1, the depth's native floor witness rose
# from register 2's uncut floor, ~45 mm up the section across the bearing
# bore. Cut the register whose floor the native depth dimension references.
_REGISTER_CUT = part_spec.CAP_REGISTER_POINTS[1]
_REGISTER_CUT_Y_CLEARANCE = max(BLOCK_WIDTH, part_spec.WING_WIDTH) / 2.0 + 7.0
REGISTER_CUT_START = (_REGISTER_CUT[0], -_REGISTER_CUT_Y_CLEARANCE)
REGISTER_CUT_END = (_REGISTER_CUT[0], _REGISTER_CUT_Y_CLEARANCE)
# Sheet 4's (72.00) overall: picked 5 mm in from the -X end on each wing face,
# its line 7.5 mm (15 mm on paper) left of that end, text centred on it.
OVERALL_HEIGHT_PICK_X = BLOCK_X0 + 5.0
OVERALL_HEIGHT_LINE_X = BLOCK_X0 - 7.5
SECTION_A_KEEP: dict[str, tuple[float, float, float]] = {
    # In A-A, the carriage seat is model Z0, not the counterbored top face.
    "SideScrewRowZ": (BLOCK_X1 + 60.0, 0.0, -10.5),
    # Hang each seat-depth block outside its span, beside the left end face.
    "TopBoreDepth": (BLOCK_X0 - 7.0, 0.0, _H + 8.25),
    "BottomBoreDepth": (BLOCK_X0 - 7.0, 0.0, -8.75),
    # Below A-A, away from the plan (5bca52e review: above it, the line ran
    # 8 px under the plan's 74.50 to text beside the 9.000 block). Text block
    # centred on the bore between the witnesses, its top row ~2 model mm under
    # A-A's lower edge (the counterbored top face); the line runs along the
    # last row's baseline, ~11 model mm lower.
    "ShoulderHoleDia": (BORE_X, 0.0, _H + 12.5),
    # Route the actual corner-radius leader right of A-A, below its dimension tiers.
    "SeatFilletR": (31.0, 0.0, 18.0),
}
# Hung under the top face, the top seat's block runs beside its dimension
# line from the face down to its shoulder, the block's right edge on the
# line (tl22-r1: "NEEDS 3.0" ended 0.2 mm from it). Two trailing spaces on
# every row stand the glyphs ~2.5 mm off the line; the bottom seat's block
# stands over its shoulder, clear of its line, and keeps the spec's rows.
HUNG_BESIDE_LINE = ("TopBoreDepth",)
_HUNG_PAD = "  "


def _hung_clear(callouts: dict[str, str]) -> dict[str, str]:
    return callouts | {
        name: "\n".join(row + _HUNG_PAD for row in callouts[name].splitlines())
        for name in HUNG_BESIDE_LINE
    }


SIDE_KEEP: dict[str, tuple[float, float, float]] = {
    # Baseline X stations from the -X end, above the removed side view.
    "SideScrew1X": (-29.5, _HW, -4.0),
    "SideScrew2X": (-24.5, _HW, -8.0),
    # Height stays to the right; its carriage-seat datum is named in A-A.
    # ENFORCE review: 4 mm out, the centred "24.00" touched the +X outline;
    # 12 mm (18 mm on paper) stands the text clear of the part.
    "BlockHeight": (BLOCK_X1 + 12.0, _HW, _H / 2.0),
}
_OTHER_SHEET_DIMENSIONS = (
    set(CAPTURE_KEEP) | set(REGISTER_KEEP) | set(REGISTER_SECTION_KEEP)
    | set(SIDE_KEEP)
)

# The screw holes' native callout over the plan, under the top border:
# four rows, ~60 x 22 mm, projected at x ~182..242, y ~239..261.
# At X188 mm its native leader ran from (172.2,216.6) to (158.1,238.8)
# through the removed-view C letter and its leader. Move only the text 24 mm
# right: the leader now approaches the block to the right of C, whose pointer
# tip and view ownership stay unchanged. ``callout_xy`` centres the block;
# SCREW_CALLOUT_EDGE retains the same (+13,+13) counterbore rim selection.
SCREW_CALLOUT_XY = (0.212, 0.250)
_CBORE_R = part_spec.CBORE_DIA / 2.0
SCREW_CALLOUT_EDGE = (
    BOLT_X + _CBORE_R * math.sqrt(0.5),
    BOLT_Y + _CBORE_R * math.sqrt(0.5),
    _H,
)
# The counterbore row's depth prints as the floor's reference complement.
_CBORE_DEPTH_TOKEN = re.compile(r"(<HOLE-DEPTH>\s*)(<[^<>()]+>|[0-9.]+)\s*$")
SCREW_HOLE_PROCESS = "DRILL"

# Seat coaxiality (part_spec docstring): datum A on the bottom seat in A-A,
# the position frame on the top seat opposite it (review r12: on the plan's
# visible rim the reader could not tell the controlled bore from the datum
# bore). The tl22-r2 review read both inside their cavities as text on the
# part (rule 14); both now stand outside the outline.
#
# SolidWorks sets a datum triangle level with its box (jig-r11: over the
# seat's mouth it went onto the -X wall's extension above the face, read as
# "face A"), so the box stands left of the end wall, level with the bottom
# seat. These model-space targets follow the lowered A-A, rather than old
# sheet coordinates; the triangle lands across the unchanged 3 mm end wall.
SEAT_DATUM_EDGE = (BORE_X - part_spec.BORE_DIA / 2.0, 0.0, 3.0)
SEAT_DATUM_SYMBOL = (BLOCK_X0 - 1.5, 0.0, 5.0)
# The frame stays below A-A's top face and above its native caption, right
# of the Ø25's +X witness. Its attachment lands 1.5 mm inside the top face on
# the top seat's +X wall, so its leader runs down-right off the mouth, never
# across the Ø25 witness or its text under the bore.
SEAT_FRAME_EDGE = (BORE_X + part_spec.BORE_DIA / 2.0, 0.0, _H - 1.5)
SEAT_FRAME_CORNER = (BORE_X + 22.0, 0.0, _H + 2.0)
_SEAT_GDT_SOURCE = ("draw_ch_rocker_arm_tl_oblique_pivot_block", "_seat_gdt")

# The dedicated interface sheet keeps the full native hole callout above
# the view; the selected upper-right counterbore rim remains unchanged.
_SIDE_CBORE_R = SIDE_CBORE_DIA / 2.0
SIDE_CALLOUT_EDGE = (
    SIDE_SCREW_HOLES[1][0] + _SIDE_CBORE_R * math.sqrt(0.5),
    _HW,
    SIDE_SCREW_HOLES[1][1] - _SIDE_CBORE_R * math.sqrt(0.5),
)

_UP = [0.0, 0.0, 1.0]
_DOWN = [0.0, 0.0, -1.0]
_INTO_Y = [0.0, -1.0, 0.0]


part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        "SIDE_CALLOUT_PRECISION",
        ("_drawing_hole_callout", "add_native_hole_callout"),
        ("_drawing_hole_callout", "set_hole_callout_precision"),
    )
)
part_metadata(
    datums={
        part_spec.SEAT_DATUM: (
            {"feature": "bottom_bearing_seat", "surface": "bottom 6200 seat cylinder"},
            ("SEAT_DATUM", _SEAT_GDT_SOURCE),
        ),
    }
)

requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.BLOCK_HEIGHT),),
    requirements=("height", "length", "width"),
    fields={
        "normal": (_UP, ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.BLOCK_HEIGHT},
            ("BLOCK_HEIGHT",),
        ),
        "height": (limits(part_spec.BLOCK_HEIGHT, 2), ("BLOCK_HEIGHT",)),
        "height_nominal": (part_spec.BLOCK_HEIGHT, ("BLOCK_HEIGHT",)),
        "length": (limits(part_spec.BLOCK_LENGTH, 2), ("BLOCK_LENGTH",)),
        "length_nominal": (part_spec.BLOCK_LENGTH, ("BLOCK_LENGTH",)),
        "width": (limits(part_spec.BLOCK_WIDTH, 2), ("BLOCK_WIDTH",)),
        "width_nominal": (part_spec.BLOCK_WIDTH, ("BLOCK_WIDTH",)),
    },
    precision={"height": 2, "length": 2, "width": 2},
)

requirement(
    "carriage_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("height",),
    fields={
        "normal": (_DOWN, ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "height": (limits(part_spec.BLOCK_HEIGHT, 2), ("BLOCK_HEIGHT",)),
    },
    precision={"height": 2},
)

requirement(
    "minus_x_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), -part_spec.BLOCK_X0),),
    requirements=("length",),
    fields={
        "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
        # The datum every X station prints from; the +X end from it.
        "length": (limits(part_spec.BLOCK_LENGTH, 2), ("BLOCK_LENGTH", "DATUM_X")),
        "length_nominal": (part_spec.BLOCK_LENGTH, ("BLOCK_LENGTH",)),
    },
    precision={"length": 2},
)

for _side, _face_z, _entry_z, _axis, _coaxial in (
    (
        "top",
        part_spec.BLOCK_HEIGHT - part_spec.BORE_DEPTH / 2.0,
        part_spec.BLOCK_HEIGHT,
        _DOWN,
        {
            # The position frame to A (_seat_gdt), docstring "Seat coaxiality".
            "coaxiality_dia": (
                part_spec.SEAT_POSITION_DIA,
                ("SEAT_POSITION_DIA", "GEOMETRIC_TOLERANCES_MM", _SEAT_GDT_SOURCE),
            ),
            "coaxial_to": ("bottom_bearing_seat", (_SEAT_GDT_SOURCE,)),
            "position_datums": (
                [part_spec.SEAT_DATUM],
                ("SEAT_DATUM", _SEAT_GDT_SOURCE),
            ),
        },
    ),
    ("bottom", part_spec.BORE_DEPTH / 2.0, 0.0, _UP, {}),
):
    requirement(
        f"{_side}_bearing_seat",
        kind="hole",
        faces=(
            CylinderFace(
                part_spec.BORE_DIA,
                contains_x_mm=part_spec.BORE_X,
                contains_z_mm=_face_z,
            ),
        ),
        requirements=(
            "station",
            "width",
            "dia",
            "depth",
            "note",
            *(("coaxiality_dia",) if _coaxial else ()),
        ),
        fields={
            "at": (
                [part_spec.BORE_X, 0.0, _entry_z],
                ("BORE_X", "BLOCK_HEIGHT", "__frame__"),
            ),
            "axis": (_axis, ("__frame__",)),
            # From the -X end face and the -Y side face; two places, since
            # the carriages slide and the bore's place sets no radius.
            "station": (
                limits(part_spec.BORE_STATION_X, 2),
                ("BORE_X", "DATUM_X"),
            ),
            "station_nominal": (part_spec.BORE_STATION_X, ("BORE_X", "DATUM_X")),
            "width": (limits(part_spec.BORE_STATION_Y, 2), ("DATUM_Y",)),
            "width_nominal": (part_spec.BORE_STATION_Y, ("DATUM_Y",)),
            "dia": (
                limits(part_spec.BORE_DIA, 3, part_spec.BORE_BAND),
                ("BORE_DIA", "BORE_BAND", "N6_BAND"),
            ),
            "dia_nominal": (part_spec.BORE_DIA, ("BORE_DIA",)),
            "depth": (
                limits(part_spec.BORE_DEPTH, 3),
                ("BORE_DEPTH", "PULLER_GAP_MIN"),
            ),
            "depth_ref": (part_spec.BORE_DEPTH, ("BORE_DEPTH",)),
            "thru": (False, ("BORE_DEPTH",)),
            # The rule-4 matched-fit callout names the mate (BORE_MATE).
            "note": (
                " ".join(part_spec.BORE_CALLOUT.splitlines()),
                ("BORE_CALLOUT", "BORE_MATE"),
            ),
            **_coaxial,
        },
        precision={"station": 2, "width": 2, "dia": 3, "depth": 3}
        | ({"coaxiality_dia": 2} if _coaxial else {}),
    )

requirement(
    "shoulder_hole",
    kind="hole",
    faces=(
        CylinderFace(
            part_spec.SHOULDER_HOLE_DIA,
            contains_x_mm=part_spec.BORE_X,
            contains_z_mm=part_spec.BLOCK_HEIGHT / 2.0,
        ),
    ),
    requirements=("dia", "thru"),
    fields={
        "at": (
            [part_spec.BORE_X, 0.0, part_spec.BORE_DEPTH + part_spec.SHOULDER],
            ("BORE_X", "BORE_DEPTH", "SHOULDER"),
        ),
        "axis": (_DOWN, ("__frame__",)),
        "dia": (
            limits(part_spec.SHOULDER_HOLE_DIA, 1),
            ("SHOULDER_HOLE_DIA", "BEARING_DA_MAX", "BEARING_INNER_SHOULDER_D2"),
        ),
        "dia_nominal": (part_spec.SHOULDER_HOLE_DIA, ("SHOULDER_HOLE_DIA",)),
        "thru": (True, ("CALLOUTS_BELOW",)),
    },
    precision={"dia": 1},
)

for _index, (_x, _y) in enumerate(part_spec.BOLT_POINTS, start=1):
    requirement(
        f"screw_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.HOLE_DIA, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("station", "width", "dia", "thru"),
        fields={
            "at": ([_x, _y, part_spec.BLOCK_HEIGHT], ("BOLT_POINTS", "BLOCK_HEIGHT")),
            "axis": (_DOWN, ("__frame__",)),
            # From the -X end face and the -Y side face, hole to hole within
            # the M4 screws' float (spec SCREW_FLOAT).
            "station": (
                limits(_x - part_spec.DATUM_X, _HOLE_PLACES),
                ("BOLT_POINTS", "DATUM_X", "SCREW_FLOAT"),
            ),
            "station_nominal": (_x - part_spec.DATUM_X, ("BOLT_POINTS", "DATUM_X")),
            "width": (
                limits(_y - part_spec.DATUM_Y, _HOLE_PLACES),
                ("BOLT_POINTS", "DATUM_Y", "SCREW_FLOAT"),
            ),
            "width_nominal": (_y - part_spec.DATUM_Y, ("BOLT_POINTS", "DATUM_Y")),
            "dia": (
                limits(
                    part_spec.HOLE_DIA, part_spec.CALLOUT_PLACES, part_spec.DRILLED_BAND
                ),
                ("HOLE_DIA", "DRILLED_BAND"),
            ),
            "dia_nominal": (part_spec.HOLE_DIA, ("HOLE_DIA",)),
            "thru": (True, ("SCREW_HOLE_SPEC",)),
        },
        precision={
            "station": _HOLE_PLACES,
            "width": _HOLE_PLACES,
            "dia": part_spec.CALLOUT_PLACES,
        },
    )
    requirement(
        f"screw_hole_{_index}_counterbore",
        kind="counterbore",
        faces=(CylinderFace(part_spec.CBORE_DIA, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("dia", "height"),
        fields={
            "parent": (
                f"screw_hole_{_index}",
                ("HOLE_DIA", ("draw_ch_rocker_arm_tl_oblique_pivot_block", "build")),
            ),
            "dia": (
                limits(part_spec.CBORE_DIA, part_spec.CALLOUT_PLACES),
                ("CBORE_DIA", "SCREW_HEAD_DIA"),
            ),
            "dia_nominal": (part_spec.CBORE_DIA, ("CBORE_DIA",)),
            # The floor from the carriage seat (section B-B) sets the M4 x
            # 20's engagement in the carriage; the callout's depth is its
            # reference complement.
            "height": (
                limits(part_spec.CBORE_FLOOR, part_spec.CBORE_FLOOR_PLACES),
                ("CBORE_FLOOR", "ENGAGEMENT_MIN", "ENGAGEMENT_MAX"),
            ),
            "height_nominal": (part_spec.CBORE_FLOOR, ("CBORE_FLOOR",)),
            "height_from": ("carriage_seat", ("CBORE_FLOOR",)),
            "note": (part_spec.CBORE_FLOOR_CALLOUT, ("CBORE_FLOOR_CALLOUT",)),
            "depth_ref": (part_spec.CBORE_DEPTH, ("CBORE_DEPTH",)),
        },
        precision={
            "dia": part_spec.CALLOUT_PLACES,
            "height": part_spec.CBORE_FLOOR_PLACES,
        },
    )


_SIDE_PLACES = part_spec.SIDE_STATION_PLACES
_SIDE_CBORE_PLACES = part_spec.SIDE_CBORE_PLACES
_SIDE_DIA_PRINTED = round(SIDE_HOLE_DIA, part_spec.SIDE_THRU_PLACES)
for _index, (_x, _z) in enumerate(SIDE_SCREW_HOLES, start=1):
    # Stations from the -X end and the bottom face at .XXX: the pair holds
    # TL-29's tapped pair inside the #8 screws' float (spec SIDE_SCREW_FLOAT).
    requirement(
        f"side_screw_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(SIDE_HOLE_DIA, contains_x_mm=_x, contains_z_mm=_z),),
        requirements=("station", "height", "dia", "thru", "note"),
        fields={
            "at": ([_x, _HW, _z], ("SIDE_SCREW_HOLES", "BLOCK_WIDTH")),
            "axis": (_INTO_Y, ("__frame__",)),
            "station": (
                limits(_x - part_spec.DATUM_X, _SIDE_PLACES),
                ("SIDE_SCREW_HOLES", "DATUM_X", "SIDE_SCREW_FLOAT"),
            ),
            "station_nominal": (
                _x - part_spec.DATUM_X,
                ("SIDE_SCREW_HOLES", "DATUM_X"),
            ),
            "height": (
                limits(_z, _SIDE_PLACES),
                ("SIDE_SCREW_HOLES", "SIDE_SCREW_FLOAT"),
            ),
            "height_nominal": (_z, ("SIDE_SCREW_HOLES",)),
            # The row's dimension says so (CALLOUTS_BELOW, c4 review).
            "height_from": ("bottom_face", ("SIDE_ROW_CALLOUT", "CALLOUTS_BELOW")),
            "dia": (
                limits(
                    _SIDE_DIA_PRINTED,
                    part_spec.SIDE_THRU_PLACES,
                    part_spec.DRILLED_BAND,
                ),
                ("SIDE_HOLE_DIA", "SIDE_SCREW_HOLE_SPEC", "DRILLED_BAND"),
            ),
            "dia_nominal": (_SIDE_DIA_PRINTED, ("SIDE_HOLE_DIA",)),
            "thru": (True, ("SIDE_SCREW_HOLE_SPEC",)),
            # The pair's tight band names its mate; the walls' shortfall
            # (rule 20) prints under it.
            "note": (
                " ".join(SIDE_CALLOUT_BELOW.split("\n")),
                ("SIDE_CALLOUT_BELOW", "SIDE_SCREW_MATE", "SIDE_WALL_CALLOUT"),
            ),
        },
        precision={
            "station": _SIDE_PLACES,
            "height": _SIDE_PLACES,
            "dia": part_spec.SIDE_THRU_PLACES,
        },
    )
    requirement(
        f"side_screw_hole_{_index}_counterbore",
        kind="counterbore",
        faces=(CylinderFace(SIDE_CBORE_DIA, contains_x_mm=_x, contains_z_mm=_z),),
        requirements=("dia", "depth"),
        fields={
            "parent": (
                f"side_screw_hole_{_index}",
                (
                    "SIDE_HOLE_DIA",
                    ("draw_ch_rocker_arm_tl_oblique_pivot_block", "build"),
                ),
            ),
            "dia": (
                limits(SIDE_CBORE_DIA, _SIDE_CBORE_PLACES),
                ("SIDE_CBORE_DIA", "SIDE_SCREW_HEAD_DIA", "WORST_WALLS"),
            ),
            "dia_nominal": (SIDE_CBORE_DIA, ("SIDE_CBORE_DIA",)),
            "depth": (
                limits(part_spec.SIDE_CBORE_DEPTH, _SIDE_CBORE_PLACES),
                ("SIDE_CBORE_DEPTH", "SIDE_SCREW_HEAD_HEIGHT", "WORST_WALLS"),
            ),
            "depth_ref": (part_spec.SIDE_CBORE_DEPTH, ("SIDE_CBORE_DEPTH",)),
        },
        precision={"dia": _SIDE_CBORE_PLACES, "depth": _SIDE_CBORE_PLACES},
    )

requirement(
    "capture_wing",
    kind="face",
    faces=(
        PlanarFace((0.0, 1.0, 0.0), part_spec.WING_WIDTH / 2.0),
        PlanarFace((0.0, -1.0, 0.0), part_spec.WING_WIDTH / 2.0),
    ),
    requirements=("station",),
    fields={
        "station": (
            limits(part_spec.WING_WIDTH / 2.0, part_spec.WING_HALF_WIDTH_PLACES),
            ("WING_WIDTH", "WING_HALF_WIDTH_PLACES"),
        ),
        "station_nominal": (part_spec.WING_WIDTH / 2.0, ("WING_WIDTH",)),
    },
    precision={"station": part_spec.WING_HALF_WIDTH_PLACES},
)

requirement(
    "capture_wing_step",
    kind="face",
    # One selector names both coplanar +X steps outside the original tail.
    faces=(PlanarFace((1.0, 0.0, 0.0), part_spec.WING_X1),),
    requirements=("station", "note"),
    fields={
        "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "x", "value": part_spec.WING_X1},
            ("WING_X1",),
        ),
        "station": (
            limits(part_spec.WING_AXIS_REACH, part_spec.WING_AXIS_REACH_PLACES),
            ("WING_AXIS_REACH", "WING_AXIS_REACH_PLACES"),
        ),
        "station_nominal": (part_spec.WING_AXIS_REACH, ("WING_AXIS_REACH",)),
        "note": (
            " ".join(part_spec.WING_AXIS_REACH_CALLOUT.splitlines()),
            ("WING_AXIS_REACH_CALLOUT",),
        ),
    },
    precision={"station": part_spec.WING_AXIS_REACH_PLACES},
)

for _index, (_x, _y) in enumerate(part_spec.CAP_TAP_POINTS, start=1):
    requirement(
        f"cap_receiver_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.CAP_TAP_DRILL_DIA, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("station", "width", "thru", "note"),
        fields={
            "at": ([_x, _y, part_spec.BLOCK_HEIGHT], ("CAP_TAP_POINTS", "BLOCK_HEIGHT")),
            "axis": (_DOWN, ("__frame__",)),
            "station": (
                limits(abs(_x - part_spec.BORE_X), part_spec.CAP_TAP_LOCATION_PLACES),
                ("CAP_TAP_POINTS", "BORE_X", "CAP_TAP_LOCATION_PLACES"),
            ),
            "station_nominal": (abs(_x - part_spec.BORE_X), ("CAP_TAP_POINTS", "BORE_X")),
            "width": (
                limits(abs(_y), part_spec.CAP_TAP_LOCATION_PLACES),
                ("CAP_TAP_POINTS", "CAP_TAP_LOCATION_PLACES"),
            ),
            "width_nominal": (abs(_y), ("CAP_TAP_POINTS",)),
            "thru": (True, ("CAP_TAP_HOLE_SPEC",)),
            "note": (
                part_spec.CAP_TAP_HOLE_SPEC.size + " THRU; "
                + " ".join(part_spec.CAP_TAP_CALLOUT.splitlines()),
                ("CAP_TAP_HOLE_SPEC", "CAP_TAP_CALLOUT"),
            ),
        },
        precision={"station": part_spec.CAP_TAP_LOCATION_PLACES, "width": part_spec.CAP_TAP_LOCATION_PLACES},
    )

for _index, ((_x, _y), (_dx, _dy)) in enumerate(
    zip(part_spec.CAP_REGISTER_POINTS, part_spec.CAP_REGISTER_CENTERS, strict=True),
    start=1,
):
    requirement(
        f"cap_register_recess_{_index}",
        kind="hole",
        faces=(
            CylinderFace(
                part_spec.CAP_REGISTER_DIA,
                contains_x_mm=_x,
                contains_y_mm=_y,
                contains_z_mm=_H - part_spec.CAP_REGISTER_DEPTH / 2.0,
            ),
            PlanarFace(
                (0.0, 0.0, 1.0),
                _H - part_spec.CAP_REGISTER_DEPTH,
                contains_x_mm=_x,
            ),
        ),
        requirements=("station", "width", "dia", "depth", "note"),
        fields={
            "at": ([_x, _y, _H], ("CAP_REGISTER_POINTS", "BLOCK_HEIGHT")),
            "axis": (_DOWN, ("__frame__",)),
            "station": (
                limits(abs(_dx), part_spec.CAP_REGISTER_LOCATION_PLACES),
                ("CAP_REGISTER_CENTERS", "CAP_REGISTER_LOCATION_PLACES", "BORE_X"),
            ),
            "station_nominal": (abs(_dx), ("CAP_REGISTER_CENTERS",)),
            "width": (
                limits(abs(_dy), part_spec.CAP_REGISTER_LOCATION_PLACES),
                ("CAP_REGISTER_CENTERS", "CAP_REGISTER_LOCATION_PLACES"),
            ),
            "width_nominal": (abs(_dy), ("CAP_REGISTER_CENTERS",)),
            "dia": (
                limits(part_spec.CAP_REGISTER_DIA, 2, part_spec.CAP_REGISTER_DIA_BAND),
                ("CAP_REGISTER_DIA", "CAP_REGISTER_DIA_BAND"),
            ),
            "dia_nominal": (part_spec.CAP_REGISTER_DIA, ("CAP_REGISTER_DIA",)),
            "depth": (
                limits(part_spec.CAP_REGISTER_DEPTH, part_spec.CAP_REGISTER_DEPTH_PLACES),
                ("CAP_REGISTER_DEPTH", "CAP_REGISTER_DEPTH_PLACES"),
            ),
            "depth_ref": (part_spec.CAP_REGISTER_DEPTH, ("CAP_REGISTER_DEPTH",)),
            "thru": (False, ("CAP_REGISTER_DEPTH",)),
            "note": (
                " ".join(
                    (part_spec.CAP_REGISTER_CALLOUT + "\n"
                     + part_spec.CAP_REGISTER_DEPTH_CALLOUT).splitlines()
                ),
                ("CAP_REGISTER_CALLOUT", "CAP_REGISTER_DEPTH_CALLOUT"),
            ),
        },
        precision={
            "station": part_spec.CAP_REGISTER_LOCATION_PLACES,
            "width": part_spec.CAP_REGISTER_LOCATION_PLACES,
            "dia": 2,
            "depth": part_spec.CAP_REGISTER_DEPTH_PLACES,
        },
    )


def screw_hole_callout_definitions(
    definitions: dict[int, str], below: str, *, reference_depth: bool
) -> dict[int, str]:
    """DRILL in the native THRU row, ``below`` under the callout and, with
    ``reference_depth``, the counterbore depth as a reference.

    A counterbored callout prints its THRU row from the CalloutAbove part (7)
    and its counterbore row from the Prefix part (5), so a Prefix process
    would read "DRILL ⌴Ø8.00" (draw_ch_fulcrum_keeper). The process goes into
    the THRU part instead, after its instance count ("4X DRILL Ø4.50 THRU
    ALL"); the CalloutBelow part (8) carries ``below``: the mate the
    three-place hole stations serve (rule 4), and for the side screws the
    counterbore walls' rule-20 shortfall. For the carriage screws the
    counterbore row's one depth variable is bracketed, "↧ (8.40)": the
    floor's height from the carriage seat (section B-B) is the dimension
    (draw_mg_output_fixture's reference thread depth).
    """
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected screw-hole callout parts: {definitions!r}")
    thru_parts = [part for part, text in definitions.items() if "THRU" in text.upper()]
    if len(thru_parts) != 1 or thru_parts[0] == 8:
        raise RuntimeError(
            f"screw-hole THRU row is not one upper part: {definitions!r}"
        )
    if definitions[8].strip():
        raise RuntimeError(f"screw-hole callout already prints below: {definitions!r}")
    part = thru_parts[0]
    bracketed: dict[int, str] = {}
    if reference_depth:
        depth_parts = [p for p, text in definitions.items() if "<HOLE-DEPTH>" in text]
        depth = (
            _CBORE_DEPTH_TOKEN.search(definitions[depth_parts[0]])
            if len(depth_parts) == 1
            else None
        )
        if (
            depth is None
            or depth_parts[0] in (part, 8)
            or definitions[depth_parts[0]].count("<HOLE-DEPTH>") != 1
        ):
            raise RuntimeError(
                "screw-hole callout has no single bare counterbore depth: "
                f"{definitions!r}"
            )
        depth_text = definitions[depth_parts[0]]
        bracketed = {depth_parts[0]: f"{depth_text[: depth.start(2)]}({depth[2]})"}
    text = definitions[part]
    count = re.match(r"\s*<NUM_INST>X ", text)
    if count:
        updated = f"{text[: count.end()]}{SCREW_HOLE_PROCESS} {text[count.end() :]}"
    else:
        updated = compose_hole_callout_prefix(SCREW_HOLE_PROCESS, text)
    return {**definitions, part: updated, **bracketed, 8: below}


@_telemetry.traced("drawing.pivot_block.screw_hole_callout", label_param="label")
def _set_screw_hole_callout(
    display: Any, below: str, *, reference: str | None, label: str
) -> None:
    """Write a screw callout's process and lower rows, and its reference
    depth when ``reference`` names it; prove they persisted."""
    native = _early_bound(display, "IDisplayDimension")

    def read(parts: tuple[int, ...]) -> dict[int, str]:
        # Multi-line text may read back with CR LF (draw_pd_support_bar).
        return {
            part: str(native.GetText(part) or "").replace("\r", "") for part in parts
        }

    definitions = read((5, 6, 7, 8))
    updated = screw_hole_callout_definitions(
        definitions, below, reference_depth=reference is not None
    )
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = read((5, 6, 7, 8))
    resolved = read((1, 2, 3, 4))
    joined = "\n".join(resolved.values())
    if (
        persisted != updated
        or SCREW_HOLE_PROCESS not in (resolved[3] + resolved[1])
        or (reference is not None and joined.count(reference) != 1)
    ):
        raise RuntimeError(
            f"{label}: callout rows did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}, "
            f"expected reference depth {reference}"
        )
    _telemetry.info(f"{label} callout: {resolved!r}")


def _view_mapper(adapter: Any, view: Any):
    """Return model point (mm) -> sheet xy (m) through the view's transform."""
    transform = _early_bound(
        _early_bound(view, "IView").ModelToViewTransform, "IMathTransform"
    )
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def to_sheet(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([c / 1000.0 for c in model_mm])),
            "IMathPoint",
        )
        data = _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
        return float(data[0]), float(data[1])

    return to_sheet


def _seat_gdt(adapter: Any, section_a: Any, on_a: Any) -> None:
    """Datum A on the bottom seat (A-A's -X wall) and the top seat's native
    position frame to it on the top seat's +X wall: the seats are bored from
    opposite faces, and only this ties them on one axis (review r8); both in
    A-A, so the reader sees which seat is which (review r12)."""
    add_datum_feature(
        adapter,
        section_a,
        edge_xy=on_a(SEAT_DATUM_EDGE),
        symbol_xy=on_a(SEAT_DATUM_SYMBOL),
        datum=part_spec.SEAT_DATUM,
        label="pivot block bottom seat datum A",
    )
    add_feature_control_frame(
        adapter,
        section_a,
        edge_xy=on_a(SEAT_FRAME_EDGE),
        frame_xy=on_a(SEAT_FRAME_CORNER),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["top seat position to bottom seat"],
        datums=(part_spec.SEAT_DATUM,),
        diameter=True,
        label="pivot block top seat position to A",
    )


def _orient_section_b(adapter: Any, section: Any) -> None:
    """Turn section B-B into alignment with its cutting line: model +Y (the
    line's run up the plan) runs UP the sheet, so no ROTATED label is due
    (review r6). The cut direction stays the one SolidWorks gives it: a
    reversed partial section showing its far side imported nothing (carrier
    jig-r4). Seen along the +X arrows, +Z must then read right; anything
    else would contradict the arrows."""
    native = _early_bound(section, "IView")

    def axis(offset: tuple[float, float, float]) -> tuple[float, float]:
        on_b = _view_mapper(adapter, native)
        origin = on_b(SECTION_B_ANCHOR)
        moved = on_b(tuple(a + b for a, b in zip(SECTION_B_ANCHOR, offset)))
        return moved[0] - origin[0], moved[1] - origin[1]

    plus_y = axis((0.0, 1.0, 0.0))
    native.Angle = (
        float(native.Angle) + math.pi / 2.0 - math.atan2(plus_y[1], plus_y[0])
    )
    rebuild_drawing(adapter, label="pivot block section B-B aligned")
    plus_y, plus_z = axis((0.0, 1.0, 0.0)), axis((0.0, 0.0, 1.0))
    if plus_y[1] <= 0.0 or abs(plus_y[0]) > 1e-7:
        raise RuntimeError(f"pivot block section B-B is not +Y up: {plus_y=}")
    if plus_z[0] <= 0.0 or abs(plus_z[1]) > 1e-7:
        raise RuntimeError(
            f"pivot block section B-B does not read +Z right along +X: {plus_z=}"
        )


def _centre_section_b(adapter: Any, section: Any) -> None:
    """Land the strip's centre on SECTION_B_CENTER through a projected model
    point, not the outline (carrier ``_centre_section``)."""
    native = _early_bound(section, "IView")
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = _view_mapper(adapter, native)(SECTION_B_ANCHOR)
        if math.dist(projected, SECTION_B_CENTER) <= 1e-4:
            return
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_B_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre pivot block section B-B")
        rebuild_drawing(adapter, label=f"pivot block section B-B re-centred {attempt}")
    raise RuntimeError(
        f"pivot block section B-B centre {projected} missed {SECTION_B_CENTER}"
    )


def _cbore_floor_section(adapter: Any, source_model: Any, plan: Any) -> list[Any]:
    """Full section B-B through both -X counterbores, carrying the floor's
    height from the carriage seat.

    The floor's hidden owner sketch lies in the cutting plane; a derived view
    takes it from the part as it stands when cut and selects it through its
    base view, so the section is cut and curated while the part shows it
    (draw_pd_platen ``_floor_section``). A section shows no hidden lines.
    """
    on_plan = _view_mapper(adapter, plan)
    with hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        (CBORE_FLOOR_REFERENCE,),
        label="section B-B counterbore floor reference",
        base_view=plan,
    ):
        section = create_section_view(
            adapter,
            plan,
            line_start=on_plan((-BOLT_X, CUT_B_Y[0], _H)),
            line_end=on_plan((-BOLT_X, CUT_B_Y[1], _H)),
            view_xy=SECTION_B_CENTER,
            section_label="B",
            scale=VIEW_SCALE,
            partial=False,
            label="pivot block counterbore section",
        )
        _orient_section_b(adapter, section)
        set_hidden_lines_removed(adapter, section)
        _centre_section_b(adapter, section)
        on_b = _view_mapper(adapter, section)
        annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep={name: on_b(xyz) for name, xyz in SECTION_B_KEEP.items()},
            view_label="section B-B",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    position_section_caption(adapter, section, CAPTION_B_XY, label="pivot block B")
    return annotations


def _lower_row_witness_gap(
    label_box: tuple[float, float, float, float], attachment_x: float, column_x: float
) -> float:
    """Clear A's complete letter with 2 mm of air and a visible witness."""
    start = label_box[2] + 0.002
    if start <= attachment_x or column_x - start < 0.002:
        raise RuntimeError("7.000 upper witness has no clear, visible exterior lane")
    return start - attachment_x


def _plan_lower_row_witness(
    adapter: Any, annotations: list[Any], section_a: Any, on_plan: Any, *, place: bool
) -> None:
    """Gap only the upper 7 mm witness; never detach it or move the cut plane."""
    matches = [a for a in annotations if dimension_name(adapter, a) == "HoleRow1Y"]
    if len(matches) != 1:
        raise RuntimeError("plan needs exactly one native HoleRow1Y")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = str(dimension.FullName).split("@")
    if (
        len(owner) < 2 or owner[:2] != ["HoleRow1Y", "TopBoreProfile"]
        or bool(annotation.IsDangling())
        or not math.isclose(
            float(dimension.SystemValue) * 1000.0, part_spec.HOLE_ROWS_Y[0],
            rel_tol=0.0, abs_tol=1e-6,
        )
    ):
        raise RuntimeError("7.000 lost its native face-to-hole-row authority")
    cut = _early_bound(_early_bound(section_a, "IView").GetSection(), "IDrSection")
    texts = tuple(float(value) for value in cut.GetTextInfo())
    height = float(_early_bound(cut.GetTextFormat(), "ITextFormat").CharHeight)
    if len(texts) != 6 or not all(math.isfinite(v) for v in (*texts, height)) or height <= 0:
        raise RuntimeError("A cutting-line letters have no finite native text bounds")
    right = max((texts[:3], texts[3:]), key=lambda point: point[0])
    box = (right[0], right[1] - height, right[0] + height, right[1])
    attachment = on_plan((BOLT_X, -BOLT_Y, _H))
    column_x = on_plan(PLAN_KEEP["HoleRow1Y"])[0]
    gap = _lower_row_witness_gap(box, attachment[0], column_x)
    # TopBoreProfile emits datum -> row.end at BOLT_X, not BLOCK_X1.
    # cf3 native used the face 7 model mm too far right: its gap read back
    # correctly, but the witness started 10.5 paper mm short of its clear lane.
    if place:
        if display.SetWitnessLineGap(1, False, gap) is not True:
            raise RuntimeError("7.000 upper witness gap was refused")
        rebuild_drawing(adapter, label="7.000 upper witness clears section A")
    ok, use_doc, actual_gap = display.GetWitnessLineGap(1, False, 0.0)
    if ok is not True or use_doc or not math.isclose(float(actual_gap), gap, rel_tol=0.0, abs_tol=1e-8):
        raise RuntimeError("7.000 upper witness gap did not persist")
    witnesses = [
        line for line in dimension_segments(annotation)
        if all(abs(point[1] - attachment[1]) <= 1e-7 for point in line)
    ]
    if len(witnesses) != 1:
        raise RuntimeError("7.000 upper witness is missing or ambiguous")
    xs = sorted(point[0] for point in witnesses[0])
    if (
        abs(xs[0] - (attachment[0] + gap)) > 1e-6
        or xs[1] < column_x or column_x - xs[0] < 0.002
        or distance_to_box(witnesses[0], box) < 0.002 - 1e-8
    ):
        raise RuntimeError(f"7.000 upper witness does not clear A: {witnesses[0]}, {box}")


_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside


def _web_diameter_under_section(
    adapter: Any, annotations: list[Any], section_a: Any, on_a: Any, *, place: bool
) -> None:
    """The Ø25 web hole in A-A's own lane: both arrows inside its witnesses,
    its line under the section, nothing past the hole's rims (5bca52e review:
    a near-side line ran under the plan's 74.50 to text 37 mm right of A-A)."""
    matches = [
        a for a in annotations if dimension_name(adapter, a) == "ShoulderHoleDia"
    ]
    if len(matches) != 1:
        raise RuntimeError("section A-A needs exactly one native ShoulderHoleDia")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if place:
        display.Diametric = True
        display.ArrowSide = _ARROWS_INSIDE
    if not bool(display.Diametric) or int(display.ArrowSide) != _ARROWS_INSIDE:
        raise RuntimeError("Ø25 web hole lost its two-arrow diametric style")
    if place:
        return
    outline = tuple(
        float(value) for value in _early_bound(section_a, "IView").GetOutline()
    )
    rims = sorted(
        on_a((BORE_X + side * part_spec.SHOULDER_HOLE_DIA / 2.0, 0.0, 0.0))[0]
        for side in (-1.0, 1.0)
    )
    segments = dimension_segments(annotation)
    lines = [
        line
        for line in segments
        if abs(line[0][1] - line[1][1]) <= 1e-7 and abs(line[0][0] - line[1][0]) > 1e-4
    ]
    if (
        not lines
        or any(point[1] > outline[1] - 0.003 for line in lines for point in line)
        or any(
            not rims[0] - 0.0015 <= point[0] <= rims[1] + 0.0015
            for line in segments
            for point in line
        )
    ):
        raise RuntimeError(
            f"Ø25 web hole left its lane under A-A: segments={segments}, "
            f"outline={outline}, rims={rims}"
        )


def _bore_axis_section(
    adapter: Any, source_model: Any, plan: Any
) -> tuple[Any, list[Any]]:
    """Section A-A on the bore axis, with the side screws' row height.

    The row's 9.000 lives on SideScrewReference, a sketch the part saves
    hidden on the Top plane (Y = 0, A-A's cutting plane), so the section is
    cut and curated while the part shows it, as B-B is
    (``_cbore_floor_section``).
    """
    on_plan = _view_mapper(adapter, plan)
    with hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        (SIDE_SCREW_REFERENCE,),
        label="section A-A side screw reference",
        base_view=plan,
    ):
        section = create_section_view(
            adapter,
            plan,
            line_start=on_plan((CUT_A_X[0], 0.0, _H)),
            line_end=on_plan((CUT_A_X[1], 0.0, _H)),
            view_xy=SECTION_A_CENTER,
            section_label="A",
            scale=VIEW_SCALE,
            label="pivot block bore-axis section",
        )
        set_hidden_lines_removed(adapter, section)
        on_a = _view_mapper(adapter, section)
        annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep={name: on_a(xyz) for name, xyz in SECTION_A_KEEP.items()},
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    position_section_caption(adapter, section, CAPTION_A_XY, label="pivot block A")
    return section, annotations


def _label_side_view(adapter: Any, plan: Any, on_plan: Any) -> None:
    """Name the removed side view: its letter arrow on the plan's +Y edge
    and its caption (review c4r3: out of projection, unlabelled)."""
    tip = on_plan(SIDE_VIEW_ARROW_TIP)
    note = add_leader_note(
        adapter,
        SIDE_VIEW_LETTER,
        text_xy=(
            tip[0] + SIDE_VIEW_LETTER_OFFSET[0],
            tip[1] + SIDE_VIEW_LETTER_OFFSET[1],
        ),
        attach_xy=tip,
        view=plan,
        height=SIDE_VIEW_LETTER_HEIGHT,
        label=f"view {SIDE_VIEW_LETTER} viewing arrow",
    )
    if note is None:
        raise RuntimeError(f"failed to add the view {SIDE_VIEW_LETTER} arrow")
    if add_note(adapter, f"{SIDE_VIEW_CAPTION} ON SHEET 5", 0.300, 0.100) is None:
        raise RuntimeError("failed to cross-reference the removed side view")


def _register_recess_sheet(adapter: Any) -> Any:
    """Native register XY ordinates; return the independent note-bearing root."""
    plan = place_view(
        adapter, str(SOURCE), "*Front", *REGISTER_PLAN_CENTER, scale=CAPTURE_SCALE
    )
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", 0.385, 0.230, scale=ISO_SCALE
    )
    for view in (plan, iso):
        set_hidden_lines_removed(adapter, view)
    on_plan = _view_mapper(adapter, plan)
    annotations = curate_view_dimensions(
        adapter, plan,
        keep={name: on_plan(xyz) for name, xyz in REGISTER_KEEP.items()},
        view_label="register recess plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    names = set(REGISTER_KEEP)
    set_dimension_callouts(
        adapter, annotations,
        {name: text for name, text in CALLOUTS_BELOW.items() if name in names},
    )
    for annotation in annotations:
        if dimension_name(adapter, annotation) in ("CapRegister1Dia", "CapRegister2Dia"):
            set_near_side_diameter(annotation, "pivot block register recess diameter")
    assert_imported_precision(
        adapter, annotations,
        {name: DRAWING_PRECISION_BY_NAME[name] for name in names},
    )
    add_property_linked_note(adapter, "Isometric View Note", 0.350, 0.195)
    if add_note(adapter, "REGISTER DEPTH: SECTION D-D ON SHEET 4", 0.025, 0.080) is None:
        raise RuntimeError("failed to cross-reference the register-depth sheet")
    return plan


def _fit_register_section(adapter: Any, section: Any) -> tuple[float, ...]:
    """Fit the native outline without changing its orientation or scale."""
    native = _early_bound(section, "IView")
    x0, y0, x1, y1 = REGISTER_SECTION_REGION
    target = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        outline = tuple(float(value) for value in native.GetOutline())
        if outline[2] - outline[0] > x1 - x0 or outline[3] - outline[1] > y1 - y0:
            raise RuntimeError(f"register-depth section exceeds its reserved region: {outline}")
        center = ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0)
        if x0 <= outline[0] < outline[2] <= x1 and y0 <= outline[1] < outline[3] <= y1:
            return outline
        position = tuple(float(value) for value in native.Position)
        moved = [position[axis] + target[axis] - center[axis] for axis in (0, 1)]
        # Respect whatever native movement constraints exist. The shared
        # section creator requests NotAligned; no alignment is inferred here.
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to centre register-depth section")
        rebuild_drawing(adapter, label=f"register-depth section centred {attempt}")
    raise RuntimeError("native register-depth section cannot fit its reserved region")


def _register_section_layout(
    outline: tuple[float, ...], register_xy: tuple[float, float]
) -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float]], tuple[float, float]]:
    """Paper anchors following the fitted outline and the actual cut register.

    The line stands outboard of the register (toward the nearer outline end,
    away from the bore); the text shelf stands inboard of it, right of the
    outline."""
    outboard = 1.0 if register_xy[1] >= (outline[1] + outline[3]) / 2.0 else -1.0
    keep = {
        name: (register_xy[0] + dx, register_xy[1] + outboard * dy)
        for name, (dx, dy) in REGISTER_SECTION_KEEP.items()
    }
    text = {"CapRegisterDepth": (outline[2] + 0.030, register_xy[1] - outboard * 0.020)}
    caption = ((outline[0] + outline[2]) / 2.0, outline[1])
    return keep, text, caption


def _position_register_depth(
    adapter: Any,
    annotations: list[Any],
    *,
    line_xy: tuple[float, float],
    text_positions: dict[str, tuple[float, float]],
    witnesses: tuple[tuple[float, float], tuple[float, float]],
) -> Callable[[], None]:
    """Prime the native origin; retain its read-only settled line/text proof."""
    matches = [
        annotation for annotation in annotations
        if dimension_name(adapter, annotation) == "CapRegisterDepth"
    ]
    if len(matches) != 1:
        raise RuntimeError("D-D needs exactly one native register-depth dimension")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    expected_x = sorted(point[0] for point in witnesses)
    tolerance_m = 1e-6
    axis_tolerance_m = 1e-7
    text_xy = text_positions["CapRegisterDepth"]

    def error_text(exc: Exception) -> str:
        try:
            return str(exc)
        except Exception:
            return f"{type(exc).__name__} (message unavailable)"

    def emit(state: dict[str, Any]) -> str:
        serialized = f"register-depth placement stage={state['stage']} reason={state['reason']}"
        try:
            serialized = json.dumps(state, sort_keys=True)
        except Exception as exc:
            state["serialization_error"] = f"{type(exc).__name__}: {error_text(exc)}"
            serialized += f" serialization_error={state['serialization_error']}"
        try:
            _telemetry.event(
                "drawing.pivot_block.register_depth_placement",
                stage=state["stage"],
                reason=state["reason"],
                diagnostics_json=serialized,
            )
        except Exception as exc:
            state["telemetry_event_error"] = f"{type(exc).__name__}: {error_text(exc)}"
        try:
            _telemetry.info(f"register-depth placement {serialized}")
        except Exception as exc:
            state["telemetry_log_error"] = f"{type(exc).__name__}: {error_text(exc)}"
        try:
            return json.dumps(state, sort_keys=True)
        except Exception:
            return serialized

    def observe(
        stage: str, *, tolerate_read_errors: bool = False
    ) -> dict[str, Any]:
        read_errors = []
        exceptions = []

        def capture(getter: str, operation: Any) -> Any:
            try:
                return operation()
            except Exception as exc:
                read_errors.append({
                    "getter": getter, "error_type": type(exc).__name__, "error": error_text(exc),
                })
                exceptions.append(exc)
                return None

        position = capture(
            "IAnnotation.GetPosition",
            lambda: tuple(float(value) for value in annotation.GetPosition()),
        )
        data = capture(
            "IDisplayDimension.GetDisplayData",
            lambda: _early_bound(display.GetDisplayData(), "IDisplayData"),
        )
        count = (
            capture("IDisplayData.GetArrowHeadCount", lambda: int(data.GetArrowHeadCount()))
            if data is not None else None
        )
        points = []
        for index in range(count or 0):
            point = capture(
                f"IDisplayData.GetArrowHeadAtIndex2[{index}]",
                lambda index=index: tuple(
                    float(value) for value in data.GetArrowHeadAtIndex2(index)[:3]
                ),
            )
            if point is not None:
                points.append(point)
        points.sort()
        offset_text = capture("IDisplayDimension.OffsetText", lambda: bool(display.OffsetText))
        text_miss = (
            (position[0] - text_xy[0], position[1] - text_xy[1])
            if position is not None else None
        )
        line_origin_miss = (
            (position[0] - line_xy[0], position[1] - line_xy[1])
            if position is not None else None
        )
        state = {
            "operation": "position_register_depth",
            "stage": stage,
            "reason": "observed",
            "attempt": None,
            "requested_line_xy_m": line_xy,
            "requested_text_xyz_m": (*text_xy, 0.0),
            "actual_annotation_xyz_m": position,
            "actual_arrow_tips_m": points,
            "expected_witnesses_xy_m": witnesses,
            "offset_text": offset_text,
            "arrow_count": count,
            "tolerance_m": tolerance_m,
            "axis_tolerance_m": axis_tolerance_m,
            "line_y_misses_m": [point[1] - line_xy[1] for point in points],
            "witness_x_misses_m": (
                [point[0] - x for point, x in zip(points, expected_x, strict=True)]
                if count == len(points) == 2 else None
            ),
            "arrow_y_spread_m": (
                max(point[1] for point in points) - min(point[1] for point in points)
                if points else None
            ),
            "section_witness_y_spread_m": abs(witnesses[0][1] - witnesses[1][1]),
            "text_xy_miss_m": text_miss,
            "text_distance_m": math.dist(position[:2], text_xy) if position is not None else None,
            "line_origin_xy_miss_m": line_origin_miss,
            "line_origin_distance_m": (
                math.dist(position[:2], line_xy) if position is not None else None
            ),
            "read_errors": read_errors,
        }
        emit(state)
        if exceptions and not tolerate_read_errors:
            refuse(state, "native_readback_failed", cause=exceptions[0])
        return state

    def refuse(
        state: dict[str, Any], reason: str, *, cause: Exception | None = None
    ) -> None:
        failure = state | {"reason": reason}
        if cause is not None:
            failure |= {"cause_type": type(cause).__name__, "cause": error_text(cause)}
        raise RuntimeError(emit(failure)) from cause

    def require_arrows(state: dict[str, Any]) -> None:
        if state["arrow_count"] != 2:
            refuse(state, "arrow_count_mismatch")
        if any(abs(miss) > tolerance_m for miss in state["witness_x_misses_m"]):
            refuse(state, "arrow_witness_mismatch")
        if state["arrow_y_spread_m"] > axis_tolerance_m:
            refuse(state, "dimension_arrows_skewed")

    def check_layout(stage: str = "settled") -> None:
        state = observe(stage)
        require_arrows(state)
        if state["section_witness_y_spread_m"] > axis_tolerance_m:
            refuse(state, "section_witnesses_skewed")
        if not state["offset_text"]:
            refuse(state, "offset_text_not_enabled")
        if any(abs(miss) > tolerance_m for miss in state["line_y_misses_m"]):
            refuse(state, "text_move_changed_dimension_line")
        if state["text_distance_m"] > tolerance_m:
            refuse(state, "text_origin_missed_shelf")

    state = observe("pre_line")
    if state["section_witness_y_spread_m"] > axis_tolerance_m:
        refuse(state, "section_witnesses_skewed")
    try:
        display.OffsetText = False
    except Exception as exc:
        refuse(
            observe("line_offset_reset_exception", tolerate_read_errors=True),
            "offset_text_reset_failed", cause=exc,
        )
    state = observe("line_offset_reset")
    if state["offset_text"]:
        refuse(state, "offset_text_disable_refused")
    rebuild_drawing(adapter, label="register-depth dimension line")
    state = observe("line_move")
    require_arrows(state)
    # 9bb native before/after shows FALSE-mode arrows below GetPosition and
    # the combined offset/text handoff leaving the line at that prior origin.
    # Prime the origin; never calibrate FALSE-mode arrows or compensate for
    # the qualifier-dependent gap. The toggle alone was not measured.
    try:
        moved = annotation.SetPosition2(line_xy[0], line_xy[1], 0.0)
    except Exception as exc:
        refuse(
            observe("line_move_exception", tolerate_read_errors=True),
            "line_position_setter_failed", cause=exc,
        )
    if not moved:
        refuse(
            observe("line_move_setter", tolerate_read_errors=True),
            "line_position_setter_rejected",
        )
    rebuild_drawing(adapter, label="register-depth dimension line placed")
    state = observe("post_line")
    require_arrows(state)
    if state["line_origin_distance_m"] > tolerance_m:
        refuse(state, "line_origin_missed_lane")
    try:
        offset_dimension_text(adapter, annotations, text_positions)
    except Exception as exc:
        refuse(
            observe("text_move_exception", tolerate_read_errors=True),
            "offset_text_helper_failed", cause=exc,
        )
    check_layout("post_text")
    return check_layout


@_telemetry.traced("drawing.pivot_block.overall_height_reference")
def _overall_height_reference(adapter: Any, plan: Any, on_plan: Any) -> None:
    """The body's (72.00) overall, wing face to wing face (rule 10).

    ENFORCE review: the overall height printed nowhere; only the 2X 36.00
    from the bearing axis (sheet 2), which still control both faces. This
    plan has no other dimensions, so the reference stands clear left of the
    -X end, its witnesses on the two wing faces' -X corners. It prints at the
    sheet's default places, read back equal to the 36.00 halves it sums."""
    label = "pivot block overall height reference"
    half = part_spec.WING_WIDTH / 2.0
    display = add_edge_dimension(
        adapter, plan,
        p0=on_plan((OVERALL_HEIGHT_PICK_X, half, _H)),
        p1=on_plan((OVERALL_HEIGHT_PICK_X, -half, _H)),
        text_xy=on_plan((OVERALL_HEIGHT_LINE_X, 0.0, _H)),
        label=label,
        orientation="vertical",
    )
    # Value-only: the two coordinate picks land on the wing's only Y-extreme
    # edges at this X, and no other edge pair spans 72 mm vertically.
    assert_dimension_measures(
        adapter, display, expected_mm=part_spec.WING_WIDTH, label=label
    )
    display = set_reference_dimension(
        adapter, _early_bound(display, "IDisplayDimension").GetAnnotation(), label=label
    )
    # A fresh drawing dimension follows the document's linear places
    # (new_project_drawing's two): GetPrimaryPrecision2 reads -2
    # (swPrecisionFollowsDocumentSetting), so read the drawing's linear
    # default, as draw_ch_pivot_bracket and draw_sm_summing_lever do
    # (swDetailingLinearDimPrecision = 24, swDetailingLinearDimension = 206).
    places = int(display.GetPrimaryPrecision2())
    printed = places
    if places == -2:
        extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
        printed = int(extension.GetUserPreferenceInteger(24, 206))
    if printed != part_spec.WING_HALF_WIDTH_PLACES:
        raise RuntimeError(
            f"{label} prints {printed} places (dimension {places}), not the "
            f"36.00 halves' {part_spec.WING_HALF_WIDTH_PLACES}"
        )


def _register_section_sheet(adapter: Any) -> tuple[Any, Callable[[], None]]:
    """Return D-D's note-census parent and its retained native layout check."""
    plan = place_view(
        adapter, str(SOURCE), "*Front", *REGISTER_SECTION_PLAN_CENTER, scale=CAPTURE_SCALE
    )
    set_hidden_lines_removed(adapter, plan)
    on_plan = _view_mapper(adapter, plan)
    section = create_section_view(
        adapter, plan,
        line_start=on_plan((*REGISTER_CUT_START, _H)),
        line_end=on_plan((*REGISTER_CUT_END, _H)),
        view_xy=REGISTER_SECTION_CENTER,
        section_label="D", scale=CAPTURE_SCALE, partial=False,
        label="flat-bottom register recess section",
    )
    set_hidden_lines_removed(adapter, section)
    outline = _fit_register_section(adapter, section)
    on_section = _view_mapper(adapter, section)
    register_xy = on_section(
        (*_REGISTER_CUT, _H - part_spec.CAP_REGISTER_DEPTH / 2.0)
    )
    keep, text_positions, caption_xy = _register_section_layout(outline, register_xy)
    annotations = curate_view_dimensions(
        adapter, section, keep=keep,
        view_label="register recess section D-D",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter, annotations, {name: CALLOUTS_BELOW[name] for name in REGISTER_SECTION_KEEP},
    )
    assert_imported_precision(
        adapter, annotations, {name: DRAWING_PRECISION_BY_NAME[name] for name in REGISTER_SECTION_KEEP},
    )
    check_depth = _position_register_depth(
        adapter, annotations,
        line_xy=keep["CapRegisterDepth"],
        text_positions=text_positions,
        witnesses=(
            on_section((*_REGISTER_CUT, _H)),
            on_section((*_REGISTER_CUT, _H - part_spec.CAP_REGISTER_DEPTH)),
        ),
    )
    position_section_caption(adapter, section, caption_xy, label="pivot block D")
    _overall_height_reference(adapter, plan, on_plan)
    # ENFORCE review: at the top-left (0.025, 0.260) the note's final "3"
    # touched the D-D cutting line's upper end; the lower-left corner is clear.
    if add_note(adapter, "REGISTER XY LOCATIONS ON SHEET 3", 0.025, 0.045) is None:
        raise RuntimeError("failed to identify the register-ordinate sheet")
    return plan, check_depth


def _side_screw_sheet(adapter: Any) -> Any:
    """Removed nut-bracket interface; return its orthographic note-bearing root."""
    side = place_view(adapter, str(SOURCE), "*Top", *SIDE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, iso):
        set_hidden_lines_removed(adapter, view)
    on_side = _view_mapper(adapter, side)
    annotations = hidden_sketches.curate_view_dimensions(
        adapter, side,
        keep={name: on_side(xyz) for name, xyz in SIDE_KEEP.items()},
        view_label="nut-bracket side view C",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(
        adapter, annotations, {name: DRAWING_PRECISION_BY_NAME[name] for name in SIDE_KEEP},
    )
    side_callout = add_native_hole_callout(
        adapter, side, edge_xy=on_side(SIDE_CALLOUT_EDGE),
        callout_xy=(0.300, 0.225), label="nut-bracket screw counterbores",
    )
    _set_screw_hole_callout(
        side_callout, SIDE_CALLOUT_BELOW, reference=None, label="side screw holes",
    )
    set_hole_callout_precision(
        side_callout, SIDE_CALLOUT_PRECISION, label="nut-bracket screw counterbores",
    )
    if add_note(adapter, SIDE_VIEW_CAPTION, *SIDE_VIEW_CAPTION_XY) is None:
        raise RuntimeError("failed to caption the removed side view")
    if add_note(adapter, "VIEWING DIRECTION C ON SHEET 1", 0.025, 0.260) is None:
        raise RuntimeError("failed to cross-reference the side viewing direction")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return side



def _assert_capture_text_layout(adapter: Any, annotations: list[Any], on_capture: Any) -> None:
    """Read back the three horizontal offset lines and their complete text origins."""
    for name, text_xy in CAPTURE_TEXT_POSITIONS.items():
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"capture wing needs exactly one native {name}")
        annotation = _early_bound(matches[0], "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        position = tuple(float(value) for value in annotation.GetPosition())
        data = _early_bound(display.GetDisplayData(), "IDisplayData")
        tips = [
            tuple(float(value) for value in data.GetArrowHeadAtIndex2(index)[:2])
            for index in range(int(data.GetArrowHeadCount()))
        ]
        line_xy = on_capture(CAPTURE_KEEP[name])
        if (
            not bool(display.OffsetText)
            or math.dist(position[:2], text_xy) > 1e-6
            or len(tips) != 2
            or any(abs(tip[1] - line_xy[1]) > 1e-6 for tip in tips)
            or abs(tips[0][1] - tips[1][1]) > 1e-7
        ):
            raise RuntimeError(
                f"{name} lost its native offset line/text layout: "
                f"position={position}, text_xy={text_xy}, "
                f"arrow_tips={tips}, line_xy={line_xy}, OffsetText={display.OffsetText}"
            )


def _wing_axis_manufacturing_dimension(
    adapter: Any, annotations: list[Any], name: str = "WingAxisReach"
) -> None:
    """Keep each imported measured location as manufacturing ink, not REF."""
    matches = [
        annotation for annotation in annotations
        if dimension_name(adapter, annotation) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"capture wing needs exactly one native {name}")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = str(dimension.FullName).split("@")
    measured = float(dimension.SystemValue) * 1000.0
    if (
        len(owner) < 2 or owner[1] != part_spec.WING_AXIS_REFERENCE
        or int(dimension.DrivenState) != 1
        or not math.isclose(measured, part_spec.DRAWING_VALUES[name], rel_tol=0.0, abs_tol=1e-6)
        or bool(annotation.IsDangling())
    ):
        raise RuntimeError("capture wing reach lost its native measured authority")
    display.ShowParenthesis = False
    if (
        bool(display.ShowParenthesis)
        or str(display.GetText(1) or "")
        or str(display.GetText(2) or "")
        or int(_early_bound(dimension.Tolerance, "IDimensionTolerance").Type) != 0
    ):
        raise RuntimeError("capture wing reach is not ordinary title-block manufacturing ink")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot block source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="pivot block package")
    ddoc = _early_bound(drawing_model, "IDrawingDoc")
    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot activate bearing/carriage sheet")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel Pivot Block Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel pivot block; 6061-T6; MHA-CH-06-TL-22",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    # Census the independent orthographic view families, not the eventual
    # annotation owners: model-item import can attach a feature note to a
    # section within its family. Splitting D-D onto its own sheet adds its
    # *Front cutting-line parent; A/B and D are not independent roots, and
    # the pictorials import no model items. Native 695c4b02eebe removed five
    # notes in aggregate; keep exact missing/extra cleanup, not observed count.
    thread_note_views = [plan]
    on_plan = _view_mapper(adapter, plan)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *BEARING_ISO_CENTER, scale=ISO_SCALE)
    for view in (plan, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        plan,
        keep={name: on_plan(xyz) for name, xyz in PLAN_KEEP.items()},
        view_label="plan view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_a, side_row = _bore_axis_section(adapter, source_model, plan)
    _plan_lower_row_witness(adapter, annotations, section_a, on_plan, place=True)
    annotations += side_row
    on_a = _view_mapper(adapter, section_a)
    # The floor height lives on CboreFloorReference, a sketch the part saves
    # hidden: _drawing_hidden_sketches shows it while B-B is cut and curated.
    annotations += _cbore_floor_section(adapter, source_model, plan)
    set_dimension_callouts(
        adapter, annotations,
        {name: text for name, text in CALLOUTS_ABOVE.items() if name not in _OTHER_SHEET_DIMENSIONS},
        location="above",
    )
    set_dimension_callouts(
        adapter, annotations,
        {name: text for name, text in _hung_clear(CALLOUTS_BELOW).items() if name not in _OTHER_SHEET_DIMENSIONS},
    )
    offset_dimension_text(adapter, annotations, SECTION_A_TEXT_POSITIONS)
    diameters = [a for a in annotations if dimension_name(adapter, a) == "BoreDia"]
    if len(diameters) != 1:
        raise RuntimeError(f"expected one BoreDia dimension, found {len(diameters)}")
    set_near_side_diameter(diameters[0], "pivot block BoreDia")
    _web_diameter_under_section(adapter, annotations, section_a, on_a, place=True)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(
        adapter, annotations,
        {name: places for name, places in DRAWING_PRECISION_BY_NAME.items() if name not in _OTHER_SHEET_DIMENSIONS},
    )
    _set_screw_hole_callout(
        add_native_hole_callout(
            adapter,
            plan,
            edge_xy=on_plan(SCREW_CALLOUT_EDGE),
            callout_xy=SCREW_CALLOUT_XY,
            label="carriage screw counterbores",
        ),
        SCREW_MATE_CALLOUT,
        reference=f"({part_spec.CBORE_DEPTH:.{part_spec.CALLOUT_PLACES}f})",
        label="carriage screw holes",
    )
    _seat_gdt(adapter, section_a, on_a)
    _label_side_view(adapter, plan, on_plan)
    add_property_linked_note(adapter, "Isometric View Note", *BEARING_ISO_NOTE_XY)

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate captured-wing sheet")
    capture = place_view(adapter, str(SOURCE), "*Front", 0.195, 0.160, scale=CAPTURE_SCALE)
    thread_note_views.append(capture)
    capture_iso = place_view(adapter, str(SOURCE), "*Isometric", 0.385, 0.230, scale=ISO_SCALE)
    for view in (capture, capture_iso):
        set_hidden_lines_removed(adapter, view)
    on_capture = _view_mapper(adapter, capture)
    capture_annotations = hidden_sketches.curate_view_dimensions(
        adapter, capture,
        keep={name: on_capture(xyz) for name, xyz in CAPTURE_KEEP.items()},
        view_label="capture wing plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(
        adapter, capture_annotations,
        {name: DRAWING_PRECISION_BY_NAME[name] for name in CAPTURE_KEEP},
    )
    set_dimension_callouts(
        adapter, capture_annotations,
        {name: text for name, text in CALLOUTS_BELOW.items() if name in CAPTURE_KEEP},
    )
    set_dimension_callouts(
        adapter, capture_annotations, {"WingHalfWidth": CALLOUTS_ABOVE["WingHalfWidth"]},
        location="above",
    )
    offset_dimension_text(adapter, capture_annotations, CAPTURE_TEXT_POSITIONS)
    _assert_capture_text_layout(adapter, capture_annotations, on_capture)
    for name in ("WingAxisReach", "WingHalfWidth"):
        _wing_axis_manufacturing_dimension(adapter, capture_annotations, name)
    tap_x, tap_y = part_spec.CAP_TAP_POINTS[1]
    cap_tap_callout = add_native_hole_callout(
        adapter, capture,
        edge_xy=on_capture((tap_x, tap_y + part_spec.CAP_TAP_DRILL_DIA / 2.0, _H)),
        callout_xy=(0.069, 0.246),
        label="four cap receiver taps",
    )
    # The title block's THREADS row owns the general thread class.
    omit_title_block_thread_class(cap_tap_callout, label="four cap receiver taps")
    add_property_linked_note(adapter, "Isometric View Note", 0.350, 0.195)
    if not ddoc.ActivateSheet(SHEET_NAMES[2]):
        raise RuntimeError("cannot activate register-recess sheet")
    thread_note_views.append(_register_recess_sheet(adapter))
    if not ddoc.ActivateSheet(SHEET_NAMES[3]):
        raise RuntimeError("cannot activate register-depth sheet")
    register_plan, check_register_depth = _register_section_sheet(adapter)
    thread_note_views.append(register_plan)
    if not ddoc.ActivateSheet(SHEET_NAMES[4]):
        raise RuntimeError("cannot activate nut-bracket interface sheet")
    thread_note_views.append(_side_screw_sheet(adapter))

    def settled_checks() -> None:
        if not ddoc.ActivateSheet(SHEET_NAMES[0]):
            raise RuntimeError("cannot recheck the bearing/carriage witness")
        _plan_lower_row_witness(adapter, annotations, section_a, on_plan, place=False)
        _web_diameter_under_section(adapter, annotations, section_a, on_a, place=False)
        if not ddoc.ActivateSheet(SHEET_NAMES[1]):
            raise RuntimeError("cannot recheck the capture-wing authorities")
        for name in ("WingAxisReach", "WingHalfWidth"):
            _wing_axis_manufacturing_dimension(adapter, capture_annotations, name)
        _assert_capture_text_layout(adapter, capture_annotations, on_capture)
        if not ddoc.ActivateSheet(SHEET_NAMES[3]):
            raise RuntimeError("cannot recheck the register-depth layout")
        check_register_depth()

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Pivot Block Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales={
            SHEET_NAMES[0]: SHEET_SCALE,
            SHEET_NAMES[1]: CAPTURE_SCALE,
            SHEET_NAMES[2]: CAPTURE_SCALE,
            SHEET_NAMES[3]: CAPTURE_SCALE,
            SHEET_NAMES[4]: SHEET_SCALE,
        },
        redundant_note_substrings=("5/16-18 Tapped Hole",),
        expected_redundant_notes=len(thread_note_views),
        settled_checks=(settled_checks,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
