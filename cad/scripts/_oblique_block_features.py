"""Sourced feature-requirement fields shared by the TL-22 and TL-32 sheets.

Both blocks print the same pivot seat, pivot tap and carriage pattern from
``ch_rocker_arm_tl_oblique_pivot_block_spec``; each ``draw_<stem>`` declares
its own module-level ``requirement(...)`` calls (``_feature_requirements``)
from the field maps built here, so the manifests share one shape. Model
frame: the carriage-pattern centre, the carriage seat at Z0 facing -Z and
the top face at Z = BLOCK_HEIGHT. Every plan X runs from the -X end; every
plan Y from one full-width side, TL-22's -Y and TL-32's +Y (the sheets'
``PlanDatumReference`` ordinates, ``part.DRAWING_VALUES``). The 3-place
column and row ordinates are the printed roundings of the vendor pattern's
exact offsets: each band is the title block's about that printed value.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot
from _printed_limits import drilled_limits, limits

PIVOT = "ch_rocker_arm_tl_oblique_pivot_block_spec"
FROM_TOP = ([0.0, 0.0, -1.0], ("__frame__",))
# Each carriage hole's plan column and row by its BOLT_POINTS sign.
COLUMNS = {-1: "PlanHole1X", 1: "PlanHole2X"}
ROWS = {1: "PlanHole2Y", -1: "PlanHole3Y"}
# TL-22's rows run from its -Y side, TL-32's from its +Y side.
ROW_FROM = {
    "ch-rocker-arm-tl-oblique-pivot-block": "minus_y_side",
    "ch-rocker-arm-tl-oblique-feed-block": "plus_y_side",
}
# Where each sheet prints the seat's ⌴ (flat floor) and the tap's DRILL THRU: TL-22's
# one stacked note, TL-32's dimension callouts.
SEAT_CALLOUT = {
    "ch-rocker-arm-tl-oblique-pivot-block": (
        "_oblique_block_drawing",
        "_pivot_stack_text",
    ),
    "ch-rocker-arm-tl-oblique-feed-block": ("_oblique_block_drawing", "BLOCK_CALLOUTS"),
}
CARRIAGE_CALLOUT = ("_oblique_block_drawing", "BLOCK_CALLOUTS")

Fields = dict[str, tuple[Any, tuple[Any, ...]]]


def printed(model: float, places: int) -> float:
    """The millimetres of ``model`` printed at ``places`` inch decimals."""
    return round(round(model / 25.4, places) * 25.4, 9)


def general(part: ModuleType, name: str) -> list[float]:
    """A printed plan dimension's title-block limits on ``part``'s sheet."""
    return limits(
        part.DRAWING_VALUES[name], part.DRAWING_PRECISION_BY_NAME[name], unit=part.UNIT
    )


def _sign(value: float) -> int:
    return 1 if value > 0 else -1


def plan_fields(part: ModuleType, column: str, row: str, row_from: str) -> Fields:
    """X from the -X end and Y from the plan's baseline side, as printed."""
    sources = ("DRAWING_VALUES", "DRAWING_PRECISION_BY_NAME", "PLAN_DATUM_REFERENCE")
    places = part.DRAWING_PRECISION_BY_NAME
    return {
        "station": (general(part, column), sources),
        "station_nominal": (
            printed(part.DRAWING_VALUES[column], places[column]),
            sources,
        ),
        "station_from": ("minus_x_end", ("PLAN_DATUM_REFERENCE",)),
        "row": (general(part, row), sources),
        "row_nominal": (printed(part.DRAWING_VALUES[row], places[row]), sources),
        "row_from": (row_from, ("PLAN_DATUM_REFERENCE", "DRAWING_VALUES")),
    }


def seat_fields(part: ModuleType, height: str) -> Fields:
    """The carriage seat: Z0 facing -Z, the block length and height."""
    return {
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "length": (
            general(part, "BlockLength"),
            ("BLOCK_LENGTH", "DRAWING_PRECISION_BY_NAME"),
        ),
        "length_nominal": (part.BLOCK_LENGTH, ("BLOCK_LENGTH",)),
        "height": (
            general(part, height),
            ("BLOCK_HEIGHT", "DRAWING_PRECISION_BY_NAME"),
        ),
        "height_nominal": (part.BLOCK_HEIGHT, ("BLOCK_HEIGHT",)),
    }


def bore_fields(part: ModuleType) -> Fields:
    """The pivot seat: .375 under DRILLED HOLES, flat-bottomed .359 deep from the top."""
    depth_places = pivot.DRAWING_PRECISION_BY_NAME["TopBoreDepth"]
    return {
        "at": (
            [pivot.BORE_X, pivot.BORE_Y, part.BLOCK_HEIGHT],
            ((PIVOT, "BORE_X"), "BLOCK_HEIGHT"),
        ),
        "axis": FROM_TOP,
        "dia": (
            drilled_limits(pivot.BORE_DIA, pivot.BORE_PLACES, unit=pivot.UNIT),
            ((PIVOT, "BORE_DIA"), (PIVOT, "BORE_PLACES")),
        ),
        "dia_nominal": (pivot.BORE_DIA, ((PIVOT, "BORE_DIA"),)),
        "depth": (
            limits(pivot.BORE_DEPTH, depth_places, unit=pivot.UNIT),
            ((PIVOT, "BORE_DEPTH"), (PIVOT, "DRAWING_PRECISION_BY_NAME")),
        ),
        "depth_nominal": (pivot.BORE_DEPTH, ((PIVOT, "BORE_DEPTH"),)),
        "floor": ("flat", ((PIVOT, "BORE_DEPTH"), SEAT_CALLOUT[part.PART_NAME])),
        **plan_fields(part, "PlanBoreX", "BlockSideY", ROW_FROM[part.PART_NAME]),
    }


def pivot_tap_fields(part: ModuleType) -> Fields:
    """The 5/16-18 tap drilled through below the seat."""
    places = pivot.DRAWING_PRECISION_BY_NAME["TapDrillDia"]
    drill = printed(pivot.PIVOT_TAP_DRILL, places)
    return {
        "at": (
            [pivot.BORE_X, pivot.BORE_Y, part.BLOCK_HEIGHT],
            ((PIVOT, "BORE_X"), "BLOCK_HEIGHT"),
        ),
        "axis": FROM_TOP,
        "thread": (f"{pivot.PIVOT_TAP} UNC-2B", ((PIVOT, "PIVOT_TAP"),)),
        "tap_drill_mm": (pivot.PIVOT_TAP_DRILL, ((PIVOT, "PIVOT_TAP_DRILL"),)),
        "dia": (
            drilled_limits(drill, places, unit=pivot.UNIT),
            ((PIVOT, "PIVOT_TAP_DRILL"), (PIVOT, "DRAWING_PRECISION_BY_NAME")),
        ),
        "dia_nominal": (drill, ((PIVOT, "PIVOT_TAP_DRILL"),)),
        "thru": (True, ((PIVOT, "PIVOT_TAP"), SEAT_CALLOUT[part.PART_NAME])),
        "parent": ("pivot_bore", ((PIVOT, "PIVOT_THREAD_LENGTH"),)),
    }


def carriage_hole_fields(part: ModuleType, x: float, y: float) -> Fields:
    """One .180 clearance drilled through on the vendor M4 pattern."""
    places = pivot.DRAWING_PRECISION_BY_NAME["CarriageDrills1Dia"]
    drill = printed(pivot.HOLE_DIA, places)
    return {
        "at": ([x, y, part.BLOCK_HEIGHT], ((PIVOT, "BOLT_POINTS"), "BLOCK_HEIGHT")),
        "axis": FROM_TOP,
        "dia": (drilled_limits(drill, places, unit=pivot.UNIT), ((PIVOT, "HOLE_DIA"),)),
        "dia_nominal": (drill, ((PIVOT, "HOLE_DIA"),)),
        "thru": (True, (CARRIAGE_CALLOUT,)),
        **plan_fields(
            part, COLUMNS[_sign(x)], ROWS[_sign(y)], ROW_FROM[part.PART_NAME]
        ),
    }


def counterbore_fields(parent: str) -> Fields:
    """The M4 head counterbore from the top: its size, and its floor from the
    carriage seat (B-B's .570); the depth prints REF."""
    dia_places = pivot.DRAWING_PRECISION_BY_NAME["CarriageCounterbores3Dia"]
    floor_places = pivot.DRAWING_PRECISION_BY_NAME["CboreFloor"]
    return {
        "parent": (parent, ((PIVOT, "BOLT_POINTS"),)),
        "dia": (
            limits(pivot.CBORE_DIA, dia_places, unit=pivot.UNIT),
            ((PIVOT, "CBORE_DIA"), (PIVOT, "DRAWING_PRECISION_BY_NAME")),
        ),
        "dia_nominal": (pivot.CBORE_DIA, ((PIVOT, "CBORE_DIA"),)),
        "floor": (
            limits(pivot.CBORE_FLOOR, floor_places, unit=pivot.UNIT),
            ((PIVOT, "CBORE_FLOOR"), (PIVOT, "DRAWING_PRECISION_BY_NAME")),
        ),
        "floor_nominal": (pivot.CBORE_FLOOR, ((PIVOT, "CBORE_FLOOR"),)),
        "floor_from": ("carriage_seat", ((PIVOT, "CBORE_FLOOR_REFERENCE"),)),
        "depth_ref": (pivot.CBORE_DEPTH, ((PIVOT, "CBORE_DEPTH"),)),
    }
