r"""Create the drawing for the cone pivot post's bond cradle (MHA-DT-005-TL-01)."""

from __future__ import annotations

import argparse
import math
import sys
import textwrap
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import place_view

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
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimensions,
)
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gtol_face_read import face_geometry
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
import dt_cone_pivot_post_tl_bond_cradle_spec as part_spec
from _feature_requirements import requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from dt_cone_pivot_post_tl_bond_cradle_spec import (
    BODY_SADDLE_THICK,
    BODY_SADDLE_Y,
    BODY_SEAT_CALLOUT,
    CONE_PIN_TOPS_NOTE,
    CONE_PIN_Y,
    CRANK_PIN_Y,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    SECTION_REFERENCE_SKETCHES,
    SURFACE_FINISHES,
    TAIL_SADDLE_Y,
    TAIL_SEAT_CALLOUT,
    TAIL_SECTION_Y,
)

SPEC = DRAWINGS_BY_NAME["dt_cone_pivot_post_tl_bond_cradle"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 134 x 80 x 25 block: 1:1 fits plan, elevation and two sections on a B
# sheet; the pictorial goes 1:2 and says so in its note.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 2)
# Plan ("*Front", looking down -Z) and elevation ("*Right") are both turned
# so the post axis (+Y) runs left to right from foot B; the elevation sits
# elevation: A-A through both cone pins' axes looks back at the body saddle
# (-Y), B-B between the crank pins and the tail saddle looks on to the tail
# saddle (+Y), so each shows one seat alone, on a saddle face it does not cut.
PLAN_CENTER = (0.115, 0.196)
ELEVATION_CENTER = (0.115, 0.096)
# A-A stands right enough that its seat callout fits between the plan's 80.0
# and the post axis (run-16 audit; run-15 review). B-B and the isometric
# stand left enough that B-B's seat-axis height prints outboard of its +X
# side, away from A-A's (run-17 review: the two 30.0s crowded each other
# between the sections), and B-B's seat callout fits between the isometric
# and the border.
SECTION_A_CENTER = (0.265, 0.130)
SECTION_B_CENTER = (0.366, 0.130)
ISO_CENTER = (0.345, 0.228)
ISO_NOTE_XY = (0.232, 0.250)
NOTES_XY = (0.020, 0.062)
# Cutting lines run from just above the saddle tops to just below the base.
CUT_TOP_Z = -9.0
CUT_FOOT_Z = -43.0
# The section captions drop clear of the tilt under A-A.
CAPTION_DROP = 0.018
# Seat finish symbols stand outboard of the seat on the model's +X side
# (X, Z in mm), under the plan's dimensions and inside the sheet border;
# their leaders land on the arc 38 degrees off its bottom, clear of the
# diameter leader, the saddle-top corner and the cone pin. B-B's stands
# under its seat axis's extension line to the +X side 30.0.
SEAT_FINISH_SYMBOL = {"body_seat": (32.0, -6.0), "tail_seat": (22.0, -9.0)}
SEAT_FINISH_LANDING_DEG = 38.0

# Dimension text positions as MODEL points (mm); each view projects its own
# after it is placed and turned. Stations print from foot B, heights from
# the base top, transverse locations from the base's west side (X -40; the
# plan's top edge).
PLAN_KEEP = {
    "StopWidth": (0.0, -30.0, 0.0),
    "StopSideX": (-28.0, -21.0, 0.0),
    # The tail saddle's side offset, the saddle width, crank pin spots and
    # base width stack as baselines off the west edge, outside the base's
    # right end.
    "SaddleSideX": (-35.0, 128.0, 0.0),
    "SaddleWidth": (0.0, 136.0, 0.0),
    "CrankPinWestX": (-23.0, 144.0, 0.0),
    "CrankPinEastX": (-17.0, 152.0, 0.0),
    "BaseWidth": (0.0, 160.0, 0.0),
    "ConePinY": (-48.0, CONE_PIN_Y / 2.0, 0.0),
    "CrankPinY": (-64.0, CRANK_PIN_Y / 2.0, 0.0),
    "CrankPinDia": (-52.0, 100.0, 0.0),
}


_POST = "dt_cone_pivot_post_spec"
_UP = ([0.0, 0.0, 1.0], ("__frame__",))
_POST_AXIS = ([0.0, 1.0, 0.0], ("__frame__",))
_HEIGHT_FROM = "body_seat"
_FROM_BASE_TOP = ("base_top", ("BASE_TOP_Z",))


def _width(nominal: float, printed: str, sources: tuple[str, ...]) -> dict:
    """A transverse location or size: its band and nominal at printed places.

    Every exported ``*_nominal`` is the PRINTED value (FixtureCAD ruling:
    prechips refuses a nominal outside its band), never the raw model one.
    """
    places = part_spec.DRAWING_PRECISION_BY_NAME[printed]
    return {
        "width": (limits(nominal, places), sources),
        "width_nominal": (round(nominal, places), sources),
    }


def _block_face(
    axis: str,
    outward: float,
    at: float,
    key: str,
    printed: str,
    nominal: float,
    sources: tuple[str, ...],
    *,
    picks: tuple[float | None, ...] = (None,),
) -> dict:
    """One printed block dimension, owned by the face(s) it ends on: the plane
    at model ``axis`` = ``at`` facing ``outward``. Heights read from the base
    top, stations from foot B, widths from the side named above."""
    normal = [0.0, 0.0, 0.0]
    normal["xyz".index(axis)] = outward
    places = part_spec.DRAWING_PRECISION_BY_NAME[printed]
    fields = {
        "normal": (normal, ("__frame__",)),
        "plane": ({"frame": "model", "axis": axis, "value": at}, sources),
        key: (limits(nominal, places), sources),
        f"{key}_nominal": (round(nominal, places), sources),
    }
    if key == "height":
        fields["height_from"] = _FROM_BASE_TOP
    return {
        'kind': "face",
        'faces': tuple(PlanarFace(tuple(normal), outward * at, contains_x_mm=x) for x in picks),
        'requirements': (key,),
        'fields': fields,
        'precision': {key: places},
    }


def _seat_finish_fields(key: str) -> dict:
    control = next(item for item in part_spec.SURFACE_FINISHES if item.key == key)
    return {"finish_ra": (control.roughness_um, ("SURFACE_FINISHES",))}


def _crank_pin(x: float) -> dict:
    return {
        'kind': "pin",
        'faces': (
            CylinderFace(part_spec.PIN_DIA, contains_x_mm=x, contains_y_mm=part_spec.CRANK_PIN_Y),
            PlanarFace((0.0, 0.0, 1.0), part_spec.CRANK_PIN_TOP_Z, contains_x_mm=x),
        ),
        'requirements': ("height", "station", "width"),
        'fields': {
            "at": ([x, part_spec.CRANK_PIN_Y, part_spec.CRANK_PIN_TOP_Z], ("CRANK_PIN_X", "CRANK_PIN_Y", "CRANK_PIN_TOP_Z")),
            "axis": _UP,
            "height": (
                limits(
                    part_spec.CRANK_PIN_FROM_AXIS,
                    part_spec.DRAWING_PRECISION_BY_NAME["CrankPinFromAxis"],
                    (part_spec.CRANK_PIN_FROM_AXIS_TOL, -part_spec.CRANK_PIN_FROM_AXIS_TOL),
                ),
                (
                    "CRANK_PIN_FROM_AXIS",
                    (_POST, "CRANK_BOSS_NORTH_FACE"),
                    "CRANK_PIN_FROM_AXIS_TOL",
                    (_POST, "DRAWING_PRECISION"),
                ),
            ),
            "height_nominal": (part_spec.CRANK_PIN_FROM_AXIS, ("CRANK_PIN_FROM_AXIS",)),
            "height_from": (_HEIGHT_FROM, ("CRANK_PIN_FROM_AXIS", "SEAT_AXIS_HEIGHT")),
            "station": (
                limits(part_spec.CRANK_PIN_Y, part_spec.DRAWING_PRECISION_BY_NAME["CrankPinY"]),
                ("CRANK_PIN_Y", (_POST, "CRANK_BORE_HEIGHT")),
            ),
            "station_nominal": (
                round(
                    part_spec.CRANK_PIN_Y,
                    part_spec.DRAWING_PRECISION_BY_NAME["CrankPinY"],
                ),
                ("CRANK_PIN_Y",),
            ),
            "dia_nominal": (part_spec.PIN_DIA, ("PIN_DIA",)),
            **_width(
                x - part_spec.SIDE_W_X,
                "CrankPinWestX" if x < 0.0 else "CrankPinEastX",
                ("CRANK_PIN_WEST_FROM_SIDE" if x < 0.0 else "CRANK_PIN_EAST_FROM_SIDE",),
            ),
        },
        'precision': {
            "height": part_spec.DRAWING_PRECISION_BY_NAME["CrankPinFromAxis"],
            "station": part_spec.DRAWING_PRECISION_BY_NAME["CrankPinY"],
            "width": part_spec.DRAWING_PRECISION_BY_NAME["CrankPinWestX" if x < 0.0 else "CrankPinEastX"],
        },
    }


def _cone_pin(name: str) -> dict:
    pin = part_spec.CONE_PINS[name]
    pin_name = f"CONE_PIN_{name.upper()}"
    entry = f"ConePinEntry{name.title()}X"
    return {
        'kind': "pin",
        'faces': (CylinderFace(part_spec.PIN_DIA, contains_x_mm=pin.top_x, contains_y_mm=part_spec.CONE_PIN_Y),),
        'requirements': ("height", "station", "width", "land_angle_deg", "note"),
        'fields': {
            "at": (
                [pin.top_x, part_spec.CONE_PIN_Y, pin.top_z],
                (pin_name, "CONE_PIN_Y", "CONE_PIN_SPREAD", (_POST, "CONE_BOSS_LENGTH")),
            ),
            "axis": (list(part_spec.CONE_PIN_AXIS), ("CONE_PIN_AXIS", (_POST, "INCLINE_DEG"))),
            # Along the pin's own axis, from the post axis to the tops' plane.
            "height": (
                limits(
                    part_spec.CONE_PIN_FROM_AXIS,
                    part_spec.DRAWING_PRECISION_BY_NAME["ConePinFromAxis"],
                    (part_spec.CONE_PIN_FROM_AXIS_TOL, -part_spec.CONE_PIN_FROM_AXIS_TOL),
                ),
                (
                    "CONE_PIN_FROM_AXIS",
                    (_POST, "CONE_BOSS_LENGTH"),
                    "CONE_PIN_FROM_AXIS_TOL",
                    (_POST, "DRAWING_PRECISION"),
                ),
            ),
            "height_nominal": (part_spec.CONE_PIN_FROM_AXIS, ("CONE_PIN_FROM_AXIS",)),
            "height_from": (_HEIGHT_FROM, ("CONE_PIN_FROM_AXIS", "SEAT_AXIS_HEIGHT")),
            "station": (
                limits(part_spec.CONE_PIN_Y, part_spec.DRAWING_PRECISION_BY_NAME["ConePinY"]),
                ("CONE_PIN_Y", (_POST, "BORE_HEIGHT")),
            ),
            "station_nominal": (
                round(part_spec.CONE_PIN_Y, part_spec.DRAWING_PRECISION_BY_NAME["ConePinY"]),
                ("CONE_PIN_Y",),
            ),
            "angle_deg": (part_spec.post.INCLINE_DEG, ((_POST, "INCLINE_DEG"),)),
            # The printed 12.5 deg tilt, +/- the general angular band.
            "land_angle_deg": (
                [part_spec.CONE_PIN_TILT - part_spec.CONE_PIN_TILT_TOL, part_spec.CONE_PIN_TILT + part_spec.CONE_PIN_TILT_TOL],
                ("CONE_PIN_TILT", "CONE_PIN_TILT_TOL", (_POST, "INCLINE_DEG")),
            ),
            "land_angle_nominal_deg": (part_spec.CONE_PIN_TILT, ("CONE_PIN_TILT", (_POST, "INCLINE_DEG"))),
            # The hole's entry into the base top, from the west side.
            **_width(part_spec.CONE_PIN_ENTRY_FROM_SIDE[name], entry, ("CONE_PIN_ENTRY_FROM_SIDE",)),
            "dia_nominal": (part_spec.PIN_DIA, ("PIN_DIA",)),
            "note": (part_spec.CONE_PIN_TOPS_NOTE, ("CONE_PIN_TOPS_NOTE", "CONE_PIN_TOPS_MATCH")),
        },
        'precision': {
            "height": part_spec.DRAWING_PRECISION_BY_NAME["ConePinFromAxis"],
            "station": part_spec.DRAWING_PRECISION_BY_NAME["ConePinY"],
            "width": part_spec.DRAWING_PRECISION_BY_NAME[entry],
            "land_angle_deg": part_spec.DRAWING_PRECISION_BY_NAME["ConePinTilt"],
        },
    }


# The face every transverse location prints from.
requirement("base_west_side",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), -part_spec.SIDE_W_X),),
    requirements=("plane",),
    fields={
        "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "x", "value": part_spec.SIDE_W_X}, ("SIDE_W_X",)),
    },
)

requirement("base_east_side", **_block_face(
    "x", 1.0, -part_spec.SIDE_W_X, "width", "BaseWidth", part_spec.BASE_WIDTH, ("BASE_WIDTH", "SIDE_W_X")
))

requirement("stop_west_side", **_block_face(
    "x",
    -1.0,
    -part_spec.STOP_WIDTH / 2.0,
    "width",
    "StopSideX",
    part_spec.STOP_SIDE_OFFSET,
    ("STOP_SIDE_OFFSET", "STOP_WIDTH", "SIDE_W_X"),
))

requirement("stop_east_side", **_block_face(
    "x", 1.0, part_spec.STOP_WIDTH / 2.0, "width", "StopWidth", part_spec.STOP_WIDTH, ("STOP_WIDTH",)
))

# Both saddles' side faces share each plane.
requirement("saddle_west_sides", **_block_face(
    "x",
    -1.0,
    -part_spec.SADDLE_WIDTH / 2.0,
    "width",
    "SaddleSideX",
    part_spec.SADDLE_SIDE_OFFSET,
    ("SADDLE_SIDE_OFFSET", "SADDLE_WIDTH", "SIDE_W_X"),
))

requirement("saddle_east_sides", **_block_face(
    "x", 1.0, part_spec.SADDLE_WIDTH / 2.0, "width", "SaddleWidth", part_spec.SADDLE_WIDTH, ("SADDLE_WIDTH",)
))

ELEVATION_KEEP = {
    "BaseLength": (0.0, 55.0, -50.0),
    "BaseThick": (0.0, -22.0, -35.0),
    "StopHeight": (0.0, -22.0, -22.0),
    "StopThick": (0.0, -6.0, 6.0),
    "BodySaddleThick": (0.0, 15.0, 6.0),
    "TailSaddleThick": (0.0, 110.0, 6.0),
    # The saddle stations stack as baselines off foot B, one row each.
    "BodySaddleY": (0.0, 5.0, 15.0),
    "TailSaddleY": (0.0, 50.0, 24.0),
    # In the gap between the foot stop and the body saddle, outside the
    # silhouette and beside the saddle it measures.
    "BodySaddleHeight": (0.0, 5.0, -22.0),
    # Pin tops from the post axis (the reference sketch's line at Z0): the
    # dimension stands beside the crank pin on its foot-B side, its upper
    # extension on the axis line, its lower on the pins' top edge.
    "CrankPinFromAxis": (0.0, CRANK_PIN_Y - 10.7, -8.0),
    "TailSaddleHeight": (0.0, 130.0, -22.0),
}


requirement("foot_stop",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), 0.0),),
    requirements=("plane", "thickness"),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "thickness": (
            limits(part_spec.STOP_THICK, part_spec.DRAWING_PRECISION_BY_NAME["StopThick"]),
            ("STOP_THICK",),
        ),
        "thickness_nominal": (part_spec.STOP_THICK, ("STOP_THICK",)),
    },
    precision={"thickness": part_spec.DRAWING_PRECISION_BY_NAME["StopThick"]},
)

requirement("base_top",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.BASE_TOP_Z),),
    requirements=("thickness",),
    fields={
        "normal": _UP,
        "plane": ({"frame": "model", "axis": "z", "value": part_spec.BASE_TOP_Z}, ("BASE_TOP_Z",)),
        "thickness": (
            limits(part_spec.BASE_THICK, part_spec.DRAWING_PRECISION_BY_NAME["BaseThick"]),
            ("BASE_THICK",),
        ),
        "thickness_nominal": (part_spec.BASE_THICK, ("BASE_THICK",)),
    },
    precision={"thickness": part_spec.DRAWING_PRECISION_BY_NAME["BaseThick"]},
)

requirement("base_far_end", **_block_face(
    "y",
    1.0,
    part_spec.BASE_END_Y + part_spec.BASE_LENGTH,
    "length",
    "BaseLength",
    part_spec.BASE_LENGTH,
    ("BASE_LENGTH", "BASE_END_Y"),
))

requirement("stop_top", **_block_face(
    "z",
    1.0,
    part_spec.BLOCK_TOP_Z,
    "height",
    "StopHeight",
    part_spec.BLOCK_HEIGHT,
    ("BLOCK_HEIGHT", "BLOCK_TOP_Z"),
    picks=(0.0,),
))

# Both saddles' tops, either side of each seat: one plane, one height.
requirement("saddle_tops", **_block_face(
    "z",
    1.0,
    part_spec.BLOCK_TOP_Z,
    "height",
    "BodySaddleHeight",
    part_spec.BLOCK_HEIGHT,
    ("BLOCK_HEIGHT", "BLOCK_TOP_Z", "SADDLE_TOP_PICK_X"),
    picks=(-part_spec.SADDLE_TOP_PICK_X, part_spec.SADDLE_TOP_PICK_X),
))

requirement("body_saddle_south", **_block_face(
    "y", -1.0, part_spec.BODY_SADDLE_Y, "station", "BodySaddleY", part_spec.BODY_SADDLE_Y, ("BODY_SADDLE_Y",)
))

requirement("body_saddle_north", **_block_face(
    "y",
    1.0,
    part_spec.BODY_SADDLE_Y + part_spec.BODY_SADDLE_THICK,
    "thickness",
    "BodySaddleThick",
    part_spec.BODY_SADDLE_THICK,
    ("BODY_SADDLE_THICK", "BODY_SADDLE_Y"),
))

requirement("tail_saddle_south", **_block_face(
    "y", -1.0, part_spec.TAIL_SADDLE_Y, "station", "TailSaddleY", part_spec.TAIL_SADDLE_Y, ("TAIL_SADDLE_Y",)
))

requirement("tail_saddle_north", **_block_face(
    "y",
    1.0,
    part_spec.TAIL_SADDLE_Y + part_spec.TAIL_SADDLE_THICK,
    "thickness",
    "TailSaddleThick",
    part_spec.TAIL_SADDLE_THICK,
    ("TAIL_SADDLE_THICK", "TAIL_SADDLE_Y"),
))

requirement("crank_pin_west", **_crank_pin(-part_spec.CRANK_PIN_X))

requirement("crank_pin_east", **_crank_pin(part_spec.CRANK_PIN_X))

# Each seat's profile sketch is parallel to its section, so the section
# imports its diameter. Each seat is a matched fit: its diameter prints as a
# reference size with its narrow callout (the spec's *_SEAT_CALLOUT) below
# it. The leader joins the shoulder at the end nearer the seat axis and runs
# through the axis, so each block stands wholly on the seat's +X side, clear
# of the axis, with the 40.0 to the axis off the west side: the leader then
# neither crosses that dimension nor runs along its axis extension line
# (run-13 review: A-A's callout sat inside the saddle; run 14's callout above
# the value bent its leader across the view; run 15's crossed the 40.0s; run
# 16's shoulder crossed A-A's axis extension). A-A's block stands above the
# plan's 80.0 text and right of its dimension line, B-B's right of the
# isometric.
SECTION_A_KEEP = {
    "BodySeatDia": (25.0, CONE_PIN_Y, 63.0),
    # High enough to clear the pin tops' relation under it.
    "BodySeatAxisX": (-20.0, CONE_PIN_Y, 50.0),
    "BodySeatAxisHeight": (-48.0, CONE_PIN_Y, -12.0),
    # Under the base, one baseline row per hole off the west side: the
    # nearer (west) hole on the upper row.
    "ConePinEntryWestX": (-27.0, CONE_PIN_Y, -46.0),
    "ConePinEntryEastX": (-20.0, CONE_PIN_Y, -54.0),
    # Under the base, outside the acute wedge on the east gauge line's +X
    # side, 33 mm from its hole entry: the inclined pin-axis line and the
    # entry rows stay clear of the text (run-13 review); the caption drops
    # clear of it (CAPTION_DROP).
    "ConePinTilt": (15.0, CONE_PIN_Y, -61.0),
    # The tops' plane from the post axis, along the pins: on the line's -X
    # side between the seat axis's extension line and the west side's, above
    # the rising extension line from the axis, under the 40.0 and clear of
    # the seat's leader, its narrow callout reading below the value (run 17:
    # one wide line ran over both extension lines and the seat's leader).
    "ConePinFromAxis": (-20.0, CONE_PIN_Y, 26.0),
}


requirement("body_seat",
    kind="seat",
    faces=(CylinderFace(part_spec.BODY_SEAT_DIA),),
    requirements=("note", "height", "width", "finish_ra"),
    fields={
        "at": ([0.0, part_spec.BODY_SADDLE_Y, 0.0], ("BODY_SADDLE_Y", "__frame__")),
        "axis": _POST_AXIS,
        "dia_nominal": (part_spec.BODY_SEAT_DIA, ("BODY_SEAT_DIA", (_POST, "BLOCK_DIA"))),
        "note": (part_spec.BODY_SEAT_CALLOUT, ("BODY_SEAT_CALLOUT", "POST_NUMBER")),
        "height": (
            limits(part_spec.SEAT_AXIS_HEIGHT, part_spec.DRAWING_PRECISION_BY_NAME["BodySeatAxisHeight"]),
            ("SEAT_AXIS_HEIGHT", "BASE_TOP_Z"),
        ),
        "height_nominal": (part_spec.SEAT_AXIS_HEIGHT, ("SEAT_AXIS_HEIGHT",)),
        **_width(part_spec.SEAT_AXIS_FROM_SIDE, "BodySeatAxisX", ("SEAT_AXIS_FROM_SIDE",)),
        **_seat_finish_fields("body_seat"),
    },
    precision={
        "height": part_spec.DRAWING_PRECISION_BY_NAME["BodySeatAxisHeight"],
        "width": part_spec.DRAWING_PRECISION_BY_NAME["BodySeatAxisX"],
        "finish_ra": 1,
    },
)

requirement("cone_pin_east", **_cone_pin("east"))

requirement("cone_pin_west", **_cone_pin("west"))

# B-B's callout reads below the value, above the finish symbol; its seat-axis
# height stands outboard of its +X side, below the finish symbol.
SECTION_B_KEEP = {
    "TailSeatDia": (25.0, TAIL_SECTION_Y, 52.0),
    "TailSeatAxisX": (-20.0, TAIL_SECTION_Y, 12.0),
    "TailSeatAxisHeight": (44.0, TAIL_SECTION_Y, -20.0),
}


requirement("tail_seat",
    kind="seat",
    faces=(CylinderFace(part_spec.TAIL_SEAT_DIA),),
    requirements=("note", "height", "width", "finish_ra"),
    fields={
        "at": ([0.0, part_spec.TAIL_SADDLE_Y, 0.0], ("TAIL_SADDLE_Y", "__frame__")),
        "axis": _POST_AXIS,
        "dia_nominal": (part_spec.TAIL_SEAT_DIA, ("TAIL_SEAT_DIA",)),
        "note": (part_spec.TAIL_SEAT_CALLOUT, ("TAIL_SEAT_CALLOUT", "POST_NUMBER")),
        "height": (
            limits(part_spec.SEAT_AXIS_HEIGHT, part_spec.DRAWING_PRECISION_BY_NAME["TailSeatAxisHeight"]),
            ("SEAT_AXIS_HEIGHT", "BASE_TOP_Z"),
        ),
        "height_nominal": (part_spec.SEAT_AXIS_HEIGHT, ("SEAT_AXIS_HEIGHT",)),
        **_width(part_spec.SEAT_AXIS_FROM_SIDE, "TailSeatAxisX", ("SEAT_AXIS_FROM_SIDE",)),
        **_seat_finish_fields("tail_seat"),
    },
    precision={
        "height": part_spec.DRAWING_PRECISION_BY_NAME["TailSeatAxisHeight"],
        "width": part_spec.DRAWING_PRECISION_BY_NAME["TailSeatAxisX"],
        "finish_ra": 1,
    },
)

DIMENSION_CALLOUTS = {
    "CrankPinDia": "4X DOWEL",
    "SaddleWidth": "2X",
    "SaddleSideX": "2X",
    "ConePinTilt": "2X",
    # One relation for both tops, how far apart their errors may be and the
    # mate that needs it, wrapped to fit between the axis and the west side.
    "ConePinFromAxis": "\n".join(
        textwrap.wrap("2X " + CONE_PIN_TOPS_NOTE, 14, break_on_hyphens=False)
    ),
    "CrankPinFromAxis": "2X",
}


def _sheet(adapter: Any, view: Any, xyz_mm: tuple[float, float, float], label: str) -> tuple[float, float]:
    return model_point_in_view(
        adapter, view, tuple(v / 1000.0 for v in xyz_mm), label=label
    )


def _direction(adapter: Any, view: Any, axis: tuple[float, float, float], label: str) -> tuple[float, float]:
    """Sheet direction of a model axis in ``view``."""
    origin = _sheet(adapter, view, (0.0, 0.0, 0.0), f"{label} origin")
    tip = _sheet(adapter, view, axis, f"{label} axis")
    return tip[0] - origin[0], tip[1] - origin[1]


def _turn(
    adapter: Any,
    view: Any,
    axis: tuple[float, float, float],
    sheet_angle: float,
    *,
    label: str,
) -> None:
    """Turn ``view`` about its centre until model ``axis`` points along
    ``sheet_angle`` (radians, counter-clockwise from sheet +x)."""
    native = _early_bound(view, "IView")
    dx, dy = _direction(adapter, native, axis, label)
    angle = float(native.Angle) + sheet_angle - math.atan2(dy, dx)
    native.Angle = angle
    adapter.currentModel.EditRebuild3()
    dx, dy = _direction(adapter, native, axis, label)
    if abs(math.remainder(math.atan2(dy, dx) - sheet_angle, 2.0 * math.pi)) > 1e-6:
        raise RuntimeError(f"{label}: model {axis} points {math.atan2(dy, dx):g} rad after the turn")


def _require_up(adapter: Any, view: Any, *, label: str) -> None:
    dx, dy = _direction(adapter, view, (0.0, 0.0, 1.0), label)
    if dy <= 0.0 or abs(dx) > 1e-9:
        raise RuntimeError(f"{label}: model +Z is not sheet-up ({dx:g}, {dy:g})")


def _orient_section(adapter: Any, section: Any, *, x_right: bool, label: str) -> None:
    """Turn a section +Z up and make it look the intended way along the post.

    Looking down -Y with +Z up puts model -X on the sheet's right; looking
    down +Y puts +X there. A section that looks the wrong way has its cut
    direction reversed, then is turned again.
    """
    native = _early_bound(section, "IView")
    _turn(adapter, native, (0.0, 0.0, 1.0), math.pi / 2.0, label=label)
    dx, _ = _direction(adapter, native, (1.0, 0.0, 0.0), label)
    if (dx > 0.0) != x_right:
        drawing_section = _early_bound(native.GetSection(), "IDrSection")
        reversed_cut = not bool(drawing_section.GetReversedCutDirection())
        drawing_section.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label=f"reverse {label}")
        if bool(drawing_section.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError(f"{label}: cutting direction did not persist")
        _turn(adapter, native, (0.0, 0.0, 1.0), math.pi / 2.0, label=label)
        dx, _ = _direction(adapter, native, (1.0, 0.0, 0.0), label)
        if (dx > 0.0) != x_right:
            raise RuntimeError(f"{label}: still looks the wrong way after reversing")
    _require_up(adapter, native, label=label)


def _cut(
    adapter: Any,
    elevation: Any,
    y: float,
    *,
    center: tuple[float, float],
    letter: str,
    x_right: bool,
    label: str,
) -> Any:
    section = create_section_view(
        adapter,
        elevation,
        line_start=_sheet(adapter, elevation, (0.0, y, CUT_TOP_Z), f"{label} line top"),
        line_end=_sheet(adapter, elevation, (0.0, y, CUT_FOOT_Z), f"{label} line foot"),
        view_xy=center,
        section_label=letter,
        scale=VIEW_SCALE,
        label=label,
    )
    _orient_section(adapter, section, x_right=x_right, label=label)
    set_hidden_lines_removed(adapter, section)
    return section


def _keep(adapter: Any, view: Any, points: dict[str, tuple[float, float, float]], label: str) -> dict[str, tuple[float, float]]:
    return {name: _sheet(adapter, view, xyz, f"{label} {name}") for name, xyz in points.items()}


def _curate(adapter: Any, view: Any, points: dict[str, tuple[float, float, float]], label: str) -> list[Any]:
    return curate_view_dimensions(
        adapter,
        view,
        keep=_keep(adapter, view, points, label),
        view_label=label,
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )


def _seat_finish(adapter: Any, view: Any, key: str, face_y: float, *, label: str) -> Any:
    """Hang a seat's finish symbol on its arc in a section.

    Each section looks on to a saddle face it does not cut, so the seat's
    arc there is a model edge of the seat face; the seat's straight edges
    along the post run end-on and drop out by their equal X.
    """
    control = surface_finish_by_key(SURFACE_FINISHES, key)
    arcs = []
    for raw in visible_view_entities(view, 1, label=f"{label} seat edges"):
        edge = _early_bound(raw, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = _early_bound(start, "IVertex").GetPoint()
        p1 = _early_bound(end, "IVertex").GetPoint()
        if abs(float(p0[0]) - float(p1[0])) * 1000.0 < 1.0:
            continue
        for face in edge.GetTwoAdjacentFaces2() or ():
            geometry = None if face is None else face_geometry(face)
            if geometry is not None and control.face.matches(geometry):
                arcs.append(raw)
                break
    if len(arcs) != 1:
        raise RuntimeError(f"{label}: expected one visible {key} arc, found {len(arcs)}")
    radius = control.face.diameter_mm / 2.0
    angle = math.radians(SEAT_FINISH_LANDING_DEG)
    symbol_x, symbol_z = SEAT_FINISH_SYMBOL[key]
    return add_surface_finish(
        adapter,
        view,
        symbol_xy=_sheet(adapter, view, (symbol_x, face_y, symbol_z), f"{label} finish symbol"),
        control=control,
        label=f"{label} {key} finish",
        char_height=0.0025,
        entity=arcs[0],
        leader_attach_xy=_sheet(
            adapter,
            view,
            (radius * math.sin(angle), face_y, -radius * math.cos(angle)),
            f"{label} finish landing",
        ),
    )


def _lower_caption(adapter: Any, view: Any, drop: float) -> None:
    """Move a section's native caption down the sheet by ``drop`` metres,
    keeping its linked fields (``draw_fr_top_frame._position_view_caption``)."""
    view = _early_bound(view, "IView")
    captions = []
    for raw_note in view.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(token in linked_text for token in ("<VLNAME>", "<VLLABEL>", "<VLSCALEV>")):
            captions.append((note, linked_text))
    if len(captions) != 1:
        raise RuntimeError(f"expected one native linked view caption, found {len(captions)}")
    note, linked_text = captions[0]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    x, y = (float(value) for value in tuple(annotation.GetPosition())[:2])
    target = (x, y - drop)
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError("failed to position native view caption")
    rebuild_drawing(adapter, label="lower section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], target) > 1e-6:
        raise RuntimeError("native view caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("view caption lost its native view-label fields")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open bond-cradle source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet_model = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Post Bond Cradle Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "cone pivot post bond cradle; steel, built up and doweled; MHA-DT-005-TL-01",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    elevation = place_view(adapter, str(SOURCE), "*Right", *ELEVATION_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    _turn(adapter, plan, (0.0, 1.0, 0.0), 0.0, label="plan")
    _turn(adapter, elevation, (0.0, 1.0, 0.0), 0.0, label="elevation")
    _require_up(adapter, elevation, label="elevation")
    for view in (plan, elevation):
        set_hidden_lines_removed(adapter, view)

    plan_annotations = _curate(adapter, plan, PLAN_KEEP, "plan")
    elevation_annotations = _curate(adapter, elevation, ELEVATION_KEEP, "elevation")

    # Each section's reference sketch (seat axis from the west side; the cone
    # pin's tilt, hole position and gauge height) lies in its cutting plane
    # and is saved hidden: the sections are cut and dimensioned while the
    # part shows them.
    with part_sketches_shown(
        adapter,
        source_model,
        SECTION_REFERENCE_SKETCHES,
        label="seat sections",
        base_view=elevation,
    ):
        section_a = _cut(
            adapter,
            elevation,
            CONE_PIN_Y,
            center=SECTION_A_CENTER,
            letter="A",
            x_right=False,
            label="section A-A",
        )
        section_b = _cut(
            adapter,
            elevation,
            TAIL_SECTION_Y,
            center=SECTION_B_CENTER,
            letter="B",
            x_right=True,
            label="section B-B",
        )
        section_a_annotations = _curate(adapter, section_a, SECTION_A_KEEP, "section A-A")
        section_b_annotations = _curate(adapter, section_b, SECTION_B_KEEP, "section B-B")

    annotations = [
        *plan_annotations,
        *elevation_annotations,
        *section_a_annotations,
        *section_b_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Matched-fit seats (policy rule 2): the diameter is a reference size; the
    # callout names the mate and states the acceptance.
    set_reference_dimensions(adapter, annotations, ("BodySeatDia", "TailSeatDia"))
    set_dimension_callouts(adapter, section_a_annotations, {"BodySeatDia": BODY_SEAT_CALLOUT})
    set_dimension_callouts(adapter, section_b_annotations, {"TailSeatDia": TAIL_SEAT_CALLOUT})
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for view, key, face_y, label in (
        (section_a, "body_seat", BODY_SADDLE_Y + BODY_SADDLE_THICK, "section A-A"),
        (section_b, "tail_seat", TAIL_SADDLE_Y, "section B-B"),
    ):
        _seat_finish(adapter, view, key, face_y, label=label)
        _lower_caption(adapter, view, CAPTION_DROP)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Post Bond Cradle Drawing",
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
