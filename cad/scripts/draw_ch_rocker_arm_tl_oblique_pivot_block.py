r"""Create the drawing for the oblique-trammel jig's pivot block (MHA-CH-06-TL-22)."""

from __future__ import annotations

import argparse
import math
import re
import sys
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
from _drawing_dimensions import assert_imported_precision, offset_dimension_text, set_dimension_callouts
from _drawing_hole_callout import (
    add_native_hole_callout,
    compose_hole_callout_prefix,
    set_hole_callout_precision,
)
from _drawing_leaders import set_near_side_diameter
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
# A-A remains vertically aligned with the plan.
SECTION_A_CENTER = (PLAN_CENTER[0], 0.088)
ISO_CENTER = (0.385, 0.232)
ISO_NOTE_XY = (0.355, 0.200)
CAPTION_A_XY = (0.155, 0.035)
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
    "BlockLength": (2.5, -part_spec.WING_WIDTH / 2.0 - 19.0, _H),
    # Y stations reference the original tail-side datum plane, not the wing.
    "HoleRow1Y": (30.0, -16.5, _H),
    "BoreStationY": (35.0, -10.0, _H),
    "HoleRow2Y": (40.0, -3.5, _H),
    "BlockWidth": (52.0, 8.0, _H),
    "BoreDia": (BLOCK_X0 - 11.5, 15.5, _H),
}
CAPTURE_KEEP = {
    "WingAxisReach": ((BORE_X + part_spec.WING_X1) / 2.0, 41.0, _H),
    "WingWidth": (59.0, 0.0, _H),
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
    "CapTapRightX": (0.310, 0.090),
}
REGISTER_PLAN_CENTER = (0.170, 0.190)
REGISTER_SECTION_PLAN_CENTER = (0.140, 0.170)
REGISTER_SECTION_CENTER = (0.325, 0.165)
REGISTER_SECTION_REGION = (0.240, 0.070, 0.410, 0.260)
REGISTER_CAPTION_XY = (0.140, 0.065)
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
REGISTER_SECTION_KEEP = {"CapRegisterDepth": (0.140, 0.095)}
# One straight vertical section through both receivers and the bearing axis.
# Extending beyond both wing sides makes the cylindrical flat floors visible.
_REGISTER_FIRST, _REGISTER_SECOND = part_spec.CAP_REGISTER_POINTS
_REGISTER_DELTA = tuple(
    b - a for a, b in zip(_REGISTER_FIRST, _REGISTER_SECOND, strict=True)
)
_REGISTER_CUT_Y_CLEARANCE = max(BLOCK_WIDTH, part_spec.WING_WIDTH) / 2.0 + 7.0
_REGISTER_START_FACTOR = (
    -_REGISTER_CUT_Y_CLEARANCE - _REGISTER_FIRST[1]
) / _REGISTER_DELTA[1]
_REGISTER_END_FACTOR = (
    _REGISTER_CUT_Y_CLEARANCE - _REGISTER_FIRST[1]
) / _REGISTER_DELTA[1]
REGISTER_CUT_START = tuple(
    a + _REGISTER_START_FACTOR * d
    for a, d in zip(_REGISTER_FIRST, _REGISTER_DELTA, strict=True)
)
REGISTER_CUT_END = tuple(
    a + _REGISTER_END_FACTOR * d
    for a, d in zip(_REGISTER_FIRST, _REGISTER_DELTA, strict=True)
)
SECTION_A_KEEP: dict[str, tuple[float, float, float]] = {
    # In A-A, the carriage seat is model Z0, not the counterbored top face.
    "SideScrewRowZ": (BLOCK_X1 + 4.0, 0.0, -10.5),
    # Hang each seat-depth block outside its span, beside the left end face.
    "TopBoreDepth": (BLOCK_X0 - 7.0, 0.0, _H + 8.25),
    "BottomBoreDepth": (BLOCK_X0 - 7.0, 0.0, -8.75),
    # A short near-side diameter leader puts the full puller callout in the
    # open lane right of A-A, not on its lower edge or between its witnesses.
    "ShoulderHoleDia": (BLOCK_X1 + 25.0, 0.0, -1.0),
    # Seat-corner fillets share one native maximum-radius callout.
    "SeatFilletR": (-20.0, 0.0, -4.0),
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
    "BlockHeight": (BLOCK_X1 + 4.0, _HW, _H / 2.0),
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
# seat (z 5, y 87): its leader edge here (x 57, between the depths' line at
# x 46 and the outline at x 60; the box x ~50..57, y ~84..91, between the
# seat's witness lines at y 77 and 97), the triangle on the -X wall (x 66)
# across the 3 mm end wall.
SEAT_DATUM_EDGE = (BORE_X - part_spec.BORE_DIA / 2.0, 0.0, 3.0)
SEAT_DATUM_SYMBOL = (BLOCK_X0 - 1.5, 0.0, 5.0)
# The frame (~29 x 7 mm, its top-left corner here: x ~123..152, y ~38..45)
# under the top face, right of the Ø25's right witness line (x 121) and
# over the caption (y <= 24). Its leader rises from the frame's left end
# through the top seat's open mouth (crossing the face's y 49 ~2 mm inside
# the +X wall at x 126) to that wall 1.5 mm over the floor (sheet ~(126,
# 66)), crossing no line.
SEAT_FRAME_EDGE = (
    BORE_X + part_spec.BORE_DIA / 2.0,
    0.0,
    part_spec.BORE_DEPTH + part_spec.SHOULDER + 1.5,
)
SEAT_FRAME_CORNER = (BORE_X + part_spec.SHOULDER_HOLE_DIA / 2.0 + 1.0, 0.0, _H + 2.0)
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
    requirements=("width",),
    fields={
        "width": (limits(part_spec.WING_WIDTH, 2), ("WING_WIDTH",)),
        "width_nominal": (part_spec.WING_WIDTH, ("WING_WIDTH",)),
    },
    precision={"width": 2},
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


def _fit_register_section(adapter: Any, section: Any) -> None:
    """Fit the native outline while retaining its section-parent alignment."""
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
            return
        position = tuple(float(value) for value in native.Position)
        moved = [position[axis] + target[axis] - center[axis] for axis in (0, 1)]
        # SetViewPosition preserves native alignment and may constrain this
        # request to its alignment vector. Accept any clear aligned result,
        # not an unattainable preferred centre; never break the alignment.
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to centre register-depth section")
        rebuild_drawing(adapter, label=f"register-depth section centred {attempt}")
    raise RuntimeError("aligned register-depth section cannot fit its reserved region")


def _register_section_sheet(adapter: Any) -> Any:
    """Native D-D; return its independent cutting-line parent for the note census."""
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
    _fit_register_section(adapter, section)
    annotations = curate_view_dimensions(
        adapter, section, keep=REGISTER_SECTION_KEEP,
        view_label="register recess section D-D",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter, annotations, {name: CALLOUTS_BELOW[name] for name in REGISTER_SECTION_KEEP},
    )
    assert_imported_precision(
        adapter, annotations, {name: DRAWING_PRECISION_BY_NAME[name] for name in REGISTER_SECTION_KEEP},
    )
    position_section_caption(adapter, section, REGISTER_CAPTION_XY, label="pivot block D")
    if add_note(adapter, "REGISTER XY LOCATIONS ON SHEET 3", 0.025, 0.260) is None:
        raise RuntimeError("failed to identify the register-ordinate sheet")
    return plan


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



def _wing_axis_manufacturing_dimension(adapter: Any, annotations: list[Any]) -> None:
    """Keep the imported measured reach as ordinary manufacturing ink, not REF."""
    matches = [
        annotation for annotation in annotations
        if dimension_name(adapter, annotation) == "WingAxisReach"
    ]
    if len(matches) != 1:
        raise RuntimeError("capture wing needs exactly one native WingAxisReach")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = str(dimension.FullName).split("@")
    measured = float(dimension.SystemValue) * 1000.0
    if (
        len(owner) < 2 or owner[1] != part_spec.WING_AXIS_REFERENCE
        or int(dimension.DrivenState) != 1
        or not math.isclose(measured, part_spec.WING_AXIS_REACH, rel_tol=0.0, abs_tol=1e-6)
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
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
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
    annotations += side_row
    on_a = _view_mapper(adapter, section_a)
    # The floor height lives on CboreFloorReference, a sketch the part saves
    # hidden: _drawing_hidden_sketches shows it while B-B is cut and curated.
    annotations += _cbore_floor_section(adapter, source_model, plan)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(
        adapter, annotations,
        {name: text for name, text in _hung_clear(CALLOUTS_BELOW).items() if name not in _OTHER_SHEET_DIMENSIONS},
    )
    for name in ("BoreDia", "ShoulderHoleDia"):
        diameters = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(diameters) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(diameters)}")
        set_near_side_diameter(diameters[0], f"pivot block {name}")
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
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

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
    offset_dimension_text(adapter, capture_annotations, CAPTURE_TEXT_POSITIONS)
    _wing_axis_manufacturing_dimension(adapter, capture_annotations)
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
    thread_note_views.append(_register_section_sheet(adapter))
    if not ddoc.ActivateSheet(SHEET_NAMES[4]):
        raise RuntimeError("cannot activate nut-bracket interface sheet")
    thread_note_views.append(_side_screw_sheet(adapter))

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
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
