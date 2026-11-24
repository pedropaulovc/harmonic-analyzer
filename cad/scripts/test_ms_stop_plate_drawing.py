"""MHA-MS-03 stop plate: the feature-export declarations on its drawing.

The sheet's print and geometry contract is ``test_ms_stop_drawing`` (shared
with MHA-MS-02); this file covers what ``draw_ms_stop_plate`` declares for the
feature bundle.
"""

from __future__ import annotations

import math

import pytest

import draw_ms_stop_plate as drawing
import export_features
import ms_stop_plate_notes as notes
import ms_stop_spec as spec
from _gtol_face import FaceGeometry


def _in(value_in: float) -> float:
    return value_in * 25.4


_FEATURE_KINDS = {
    "locating_end": "face",
    "locating_edge": "face",
    "far_end": "face",
    "roof_edge": "face",
    "seating_face": "face",
    "outer_face": "face",
    "roof_chamfers": "chamfer",
    "clearance_hole_1": "hole",
    "clearance_hole_2": "hole",
}


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


def test_the_plate_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert "ms_stop_plate" in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest("ms_stop_plate")
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    assert manifest["notes"]["manufacturing"] == notes.DRAWING_NOTES.split("\n")
    assert manifest["material"]["thickness"] == spec.PLATE_THICKNESS
    selectors = export_features.feature_selectors("ms_stop_plate")
    s = math.sqrt(0.5)
    length, height, chamfer = (
        spec.BLOCK_LENGTH,
        spec.BLOCK_HEIGHT,
        spec.ROOF_END_CHAMFER,
    )
    r = spec.PLATE_CLEARANCE_DIA / 2
    expected = {
        "locating_end": [_plane((-1.0, 0.0, 0.0), 0.0)],
        "locating_edge": [_plane((0.0, -1.0, 0.0), 0.0)],
        "far_end": [_plane((1.0, 0.0, 0.0), length)],
        "roof_edge": [_plane((0.0, 1.0, 0.0), height)],
        "seating_face": [_plane((0.0, 0.0, 1.0), 0.0)],
        "outer_face": [_plane((0.0, 0.0, -1.0), spec.PLATE_THICKNESS)],
        "roof_chamfers": [
            _plane((-s, s, 0.0), s * (height - chamfer)),
            _plane((s, s, 0.0), s * (length + height - chamfer)),
        ],
    }
    for index, x in enumerate(spec.PLATE_HOLE_XS, 1):
        y = spec.PLATE_HOLE_Y
        box = (x - r, y - r, spec.PLATE_Z_MIN, x + r, y + r, spec.PLATE_Z_MAX)
        expected[f"clearance_hole_{index}"] = [
            _cylinder(spec.PLATE_CLEARANCE_DIA, (0.0, 0.0, 1.0), box)
        ]
    for name, faces in expected.items():
        for face in faces:
            owners = [
                owner
                for owner, specs in selectors.items()
                if any(selector.matches(face) for selector in specs)
            ]
            assert owners == [name], name


def test_plate_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest("ms_stop_plate")["features"]
    assert features["far_end"]["length"] == pytest.approx([_in(0.83), _in(0.85)])
    assert features["roof_edge"]["height"] == pytest.approx([_in(0.55), _in(0.57)])
    # The sheet's (.040) prints as a reference over SHEET AS SUPPLIED; its
    # band is the receiving range, the title block's .XXX.
    outer = features["outer_face"]
    assert outer["thickness"] == pytest.approx([_in(0.035), _in(0.045)])
    assert outer["dimension_type"] == "reference" and outer["as_supplied"] is True
    assert outer["callout"] == "SHEET AS SUPPLIED"
    chamfers = features["roof_chamfers"]
    assert chamfers["size"] == pytest.approx([_in(0.03), _in(0.05)])
    assert chamfers["angle_deg"] == pytest.approx([44.0, 46.0])
    for index, station in ((1, 0.150), (2, 0.690)):
        hole = features[f"clearance_hole_{index}"]
        # #2 close clearance at the title block's DRILLED HOLES +.004/0.
        assert hole["dia"] == pytest.approx([_in(0.094), _in(0.098)], abs=1e-3)
        assert hole["thru"] is True and hole["axis"] == [0.0, 0.0, 1.0]
        # The locations print as references (rule 4 form 2: made with
        # MHA-MS-02 in the pair drill); the band is the one the web proofs
        # take for the pair drill's places.
        assert hole["dimension_type"] == "reference"
        assert hole["station"] == pytest.approx(
            [_in(station - 0.005), _in(station + 0.005)], abs=1e-3
        )
        assert hole["height"] == pytest.approx([_in(0.155), _in(0.165)], abs=1e-3)
        # The pair's #49 pilot, to MHA-MS-02's .30 (.XX) below its mating face.
        assert hole["pair_pilot_dia"] == pytest.approx(_in(0.073))
        assert hole["pair_pilot_depth_in_mate"] == pytest.approx(
            [_in(0.29), _in(0.31)], abs=1e-3
        )
        assert hole["callout"] == drawing.NOTE_LINK


def test_the_matched_pair_note_is_the_one_the_sheet_prints() -> None:
    assert drawing.MATCHED_PAIR_NOTE is notes.MATCHED_PAIR_NOTE
    assert notes.DRAWING_NOTES == notes.MATCHED_PAIR_NOTE
    assert notes.MATCHED_PAIR_NOTE.splitlines() == [
        "1. MATCHED PAIR WITH MHA-MS-02 STOP BLOCK: LOCATING ENDS AND EDGES FLUSH.",
        "    2X MHA-MS-VN-51 SCREWS ENTER FREELY INTO MHA-MS-02 TAPS.",
    ]
