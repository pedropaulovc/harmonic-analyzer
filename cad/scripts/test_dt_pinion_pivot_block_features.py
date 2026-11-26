"""Offline checks of the pinion pivot block's feature-export declarations."""

from __future__ import annotations

import inspect

import pytest

import _config
import draw_dt_pinion_pivot_block as drawing
import dt_pinion_pivot_block_geometry as geom
import dt_pinion_pivot_block_notes as notes
import export_features
from _drawing_common import new_project_drawing
from _gtol_face import FaceGeometry
from _surface_finish import MACHINED_UM

STEM = "dt_pinion_pivot_block"

_FEATURE_KINDS = {
    "west_end": "face",
    "east_end": "face",
    "bottom_face": "face",
    "top_face": "face",
    "back_face": "face",
    "front_face": "face",
    "pivot_bore": "hole",
    "lift_bore": "hole",
    "west_hold_down": "hole",
    "east_hold_down": "hole",
}


def _in(inches: float) -> float:
    return inches * 25.4


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


def test_the_note_prints_from_the_notes_module_the_export_reads() -> None:
    assert drawing.LIFT_BORE_NOTE is notes.LIFT_BORE_NOTE
    assert notes.DRAWING_NOTES == notes.LIFT_BORE_NOTE
    # Byte-identical to the string the sheet printed before the move.
    assert notes.DRAWING_NOTES == (
        f"1. .728 AND .085 SET {_config.parts('dt-pinion-cam')['number']} TO "
        f"{_config.parts('dt-pinion-cam-pin')['number']} CLEARANCE."
    )
    assert drawing.DIMENSION_CALLOUTS["LiftBoreDia"].endswith(
        f"SEE NOTE {notes.LIFT_BORE_NOTE_NUMBER}"
    )


def test_edge_dimensions_print_at_the_drawing_document_places() -> None:
    default = inspect.signature(new_project_drawing).parameters["decimals"].default
    assert drawing.EDGE_DIMENSION_PLACES == default == 2


def test_the_block_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert STEM in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest(STEM)
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    assert manifest["notes"]["manufacturing"] == notes.DRAWING_NOTES.split("\n")
    selectors = export_features.feature_selectors(STEM)
    west, east = geom.BLOCK_WEST, geom.BLOCK_EAST
    bottom, top, depth = geom.BLOCK_BOTTOM_Y, geom.BLOCK_TOP_Y, geom.BLOCK_DEPTH
    r = geom.PIVOT_BORE_DIA / 2
    rl = geom.LIFT_BORE_DIA / 2
    lx, ly = -geom.LIFT_BORE_SPACING, geom.LIFT_BORE_RISE
    s = geom.SCREW_HOLE_DIA / 2
    zc = depth / 2
    expected = {
        "west_end": _plane((-1.0, 0.0, 0.0), west),
        "east_end": _plane((1.0, 0.0, 0.0), east),
        "bottom_face": _plane((0.0, -1.0, 0.0), -bottom),
        "top_face": _plane((0.0, 1.0, 0.0), top),
        "back_face": _plane((0.0, 0.0, -1.0), 0.0),
        "front_face": _plane((0.0, 0.0, 1.0), depth),
        "pivot_bore": _cylinder(
            geom.PIVOT_BORE_DIA, (0.0, 0.0, 1.0), (-r, -r, 0.0, r, r, depth)
        ),
        "lift_bore": _cylinder(
            geom.LIFT_BORE_DIA,
            (0.0, 0.0, 1.0),
            (lx - rl, ly - rl, 0.0, lx + rl, ly + rl, depth),
        ),
    }
    for name, sign in (("west_hold_down", -1.0), ("east_hold_down", 1.0)):
        x = sign * geom.SCREW_HALF_SPACING
        expected[name] = _cylinder(
            geom.SCREW_HOLE_DIA,
            (0.0, 1.0, 0.0),
            (x - s, bottom, zc - s, x + s, top, zc + s),
        )
    # Every face the block has, owned by exactly the feature that names it.
    for name, face in expected.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(face) for selector in specs)
        ]
        assert owners == [name], name


def test_block_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest(STEM)["features"]
    assert features["west_end"]["plane"]["value"] == -geom.BLOCK_WEST
    east = features["east_end"]
    assert east["width"] == pytest.approx([_in(1.56), _in(1.58)])
    assert east["width_from"] == "west_end"
    top = features["top_face"]
    assert top["height"] == pytest.approx([_in(0.98), _in(1.00)])
    assert top["height_from"] == "bottom_face"
    front = features["front_face"]
    assert front["depth"] == pytest.approx([_in(0.43), _in(0.45)])
    assert front["depth_from"] == "back_face"
    assert features["back_face"]["plane"]["value"] == 0.0

    # The pivot bore at the .2510 reamer's size, its ANALYSIS band (owner
    # ruling 2026-11-24, fit audit question 12); the lift bore F drilled at
    # the DRILLED HOLES row (fit audit F26).  Both Ra 63.
    pivot, lift = features["pivot_bore"], features["lift_bore"]
    assert pivot["dia"] == pytest.approx([_in(0.2510), _in(0.2515)])
    assert pivot["process"] == "ream" and pivot["mate"] == "MHA-DT-19"
    assert pivot["callout"] == "REAM THRU\nMHA-DT-19 ENTERS,\nTURNS BY HAND"
    assert lift["dia"] == pytest.approx([_in(0.257), _in(0.261)])
    assert lift["process"] == "drill" and lift["drill"] == "F"
    assert lift["callout"].startswith("F DRILL THRU\nMHA-DT-17 TURNS FREELY")
    for bore in (pivot, lift):
        assert bore["thru"] is True
        assert bore["axis"] == [0.0, 0.0, -1.0]
        assert bore["finish_ra"] == MACHINED_UM
    pivot = features["pivot_bore"]
    assert pivot["at"] == [0.0, 0.0, geom.BLOCK_DEPTH]
    assert pivot["x_from_west"] == pytest.approx([_in(1.01), _in(1.03)])
    assert pivot["x_from_west_from"] == "west_end"
    assert pivot["height"] == pytest.approx([_in(0.65), _in(0.67)])
    assert pivot["height_from"] == "bottom_face"
    lift = features["lift_bore"]
    assert lift["spacing"] == pytest.approx([_in(0.723), _in(0.733)], abs=1e-3)
    assert (lift["spacing_from"], lift["spacing_axis"]) == ("pivot_bore", "x")
    assert lift["rise"] == pytest.approx([_in(0.080), _in(0.090)], abs=1e-3)
    assert (lift["rise_from"], lift["rise_axis"]) == ("pivot_bore", "y")
    assert lift["note"] == notes.LIFT_BORE_NOTE_TEXT
    assert lift["callout"].endswith(f"SEE NOTE {notes.LIFT_BORE_NOTE_NUMBER}")

    for name, station in (("west_hold_down", 0.69), ("east_hold_down", 1.35)):
        hole = features[name]
        # 2X Ø.196 THRU ALL: the drill at the title block's DRILLED HOLES +.004/0.
        assert hole["dia"] == pytest.approx([_in(0.196), _in(0.200)], abs=1e-3)
        assert hole["process"] == "drill" and hole["thru"] is True
        assert hole["axis"] == [0.0, -1.0, 0.0]
        assert hole["x_from_west"] == pytest.approx(
            [_in(station - 0.01), _in(station + 0.01)], abs=1e-3
        )
        assert hole["x_from_west_from"] == "west_end"
        assert hole["z_from_front"] == pytest.approx([_in(0.21), _in(0.23)], abs=1e-3)
        assert hole["z_from_front_from"] == "front_face"
