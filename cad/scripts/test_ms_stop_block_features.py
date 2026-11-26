"""Feature-export contract of the brass stop block (MHA-MS-02): what its sheet
prints, declared in ``draw_ms_stop_block`` for the drilled_block traveler."""

from __future__ import annotations

import math

import pytest

import _config
import draw_ms_stop_block as drawing
import export_features
import ms_stop_block_notes as notes
import ms_stop_spec as spec
from _gtol_face import FaceGeometry

STEM = "ms_stop_block"

_FEATURE_KINDS = {
    "locating_end": "face",
    "far_end": "face",
    "locating_edge": "face",
    "top_face": "face",
    "mating_face": "face",
    "back_face": "face",
    "rebate_ceiling": "face",
    "rebate_floor": "face",
    "rebate_back": "face",
    "relief_back": "face",
    "relief_floor": "face",
    "roof_chamfer_1": "chamfer",
    "roof_chamfer_2": "chamfer",
    "thumb_tap": "threaded_hole",
    "plate_tap_1": "threaded_hole",
    "plate_tap_2": "threaded_hole",
}


def _in(value_in: float) -> float:
    """Millimetres of a printed inch value."""
    return value_in * 25.4


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    length = math.sqrt(sum(value * value for value in normal))
    unit = tuple(value / length for value in normal)
    point = tuple(value * offset_mm / 1000 for value in unit)
    return FaceGeometry(None, 4001, (*unit, *point), unit, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return export_features.requirement_manifest(STEM)


def test_the_block_is_a_feature_export_part_with_one_owner_per_face(
    manifest: dict,
) -> None:
    assert STEM in export_features.SUPPORTED_PARTS
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    assert manifest["notes"]["manufacturing"] == [drawing.REBATE_NOTE]
    assert manifest["notes"]["manufacturing"] == notes.DRAWING_NOTES.split("\n")
    selectors = export_features.feature_selectors(STEM)
    length, height, depth = spec.BLOCK_LENGTH, spec.BLOCK_HEIGHT, spec.BLOCK_DEPTH
    chamfer = spec.ROOF_END_CHAMFER
    relief_back = spec.WINDOW_Z_MAX + spec.RELIEF_DEPTH
    relief_floor = spec.WINDOW_Y_MAX - spec.RELIEF_HEIGHT
    thumb_r = spec.THUMB_TAP_DRILL / 2
    tap_r = spec.PLATE_TAP_DRILL_DIA / 2
    x, _y, z = spec.THUMB_HOLE_POINTS[0]
    expected = {
        "locating_end": [_plane((-1.0, 0.0, 0.0), 0.0)],
        "far_end": [_plane((1.0, 0.0, 0.0), length)],
        "locating_edge": [_plane((0.0, -1.0, 0.0), 0.0)],
        "top_face": [_plane((0.0, 1.0, 0.0), height)],
        "mating_face": [_plane((0.0, 0.0, -1.0), 0.0)],
        "back_face": [_plane((0.0, 0.0, 1.0), depth)],
        "rebate_ceiling": [_plane((0.0, -1.0, 0.0), -spec.WINDOW_Y_MAX)],
        "rebate_floor": [_plane((0.0, 1.0, 0.0), spec.WINDOW_Y_MIN)],
        "rebate_back": [_plane((0.0, 0.0, -1.0), -spec.WINDOW_Z_MAX)],
        "relief_back": [_plane((0.0, 0.0, -1.0), -relief_back)],
        "relief_floor": [_plane((0.0, 1.0, 0.0), relief_floor)],
        "roof_chamfer_1": [
            _plane((-1.0, 1.0, 0.0), (height - chamfer) / math.sqrt(2.0))
        ],
        "roof_chamfer_2": [
            _plane((1.0, 1.0, 0.0), (length + height - chamfer) / math.sqrt(2.0))
        ],
        "thumb_tap": [
            _cylinder(
                spec.THUMB_TAP_DRILL,
                (0.0, 1.0, 0.0),
                (
                    x - thumb_r,
                    0.0,
                    z - thumb_r,
                    x + thumb_r,
                    spec.WINDOW_Y_MIN,
                    z + thumb_r,
                ),
            )
        ],
    }
    for index, (px, py, pz) in enumerate(spec.BLOCK_PLATE_HOLE_POINTS, 1):
        box = (
            px - tap_r,
            py - tap_r,
            pz,
            px + tap_r,
            py + tap_r,
            spec.PLATE_TAP_DRILL_DEPTH,
        )
        expected[f"plate_tap_{index}"] = [
            _cylinder(spec.PLATE_TAP_DRILL_DIA, (0.0, 0.0, 1.0), box)
        ]
    assert expected.keys() == _FEATURE_KINDS.keys()
    for name, faces in expected.items():
        for face in faces:
            owners = [
                owner
                for owner, specs in selectors.items()
                if any(selector.matches(face) for selector in specs)
            ]
            assert owners == [name], name


def test_the_envelope_is_the_printed_block(manifest: dict) -> None:
    features = manifest["features"]
    assert features["far_end"]["length"] == pytest.approx([_in(0.83), _in(0.85)])
    assert features["far_end"]["length_from"] == "locating_end"
    assert features["top_face"]["height"] == pytest.approx([_in(0.55), _in(0.57)])
    assert features["top_face"]["height_from"] == "locating_edge"
    back = features["back_face"]
    assert back["back_wall"] == pytest.approx([_in(0.14), _in(0.16)])
    assert back["back_wall_from"] == "rebate_back"
    # (.48) prints as a reference: the rebate and the back wall control it.
    assert back["depth_ref"] == pytest.approx(_in(0.48))
    assert back["dimension_type"] == "reference" and "depth" not in back
    assert features["locating_end"]["note"] == "LOCATING END"
    assert features["locating_edge"]["note"] == "LOCATING EDGE"
    plate_number = _config.parts("ms-stop-plate")["number"]
    mating = features["mating_face"]
    assert mating["note"] == f"{plate_number} MATING FACE"
    assert mating["mates"] == plate_number
    planes = [
        feature["plane"] for feature in features.values() if feature["kind"] == "face"
    ]
    for axis, size in (
        ("x", spec.BLOCK_LENGTH),
        ("y", spec.BLOCK_HEIGHT),
        ("z", spec.BLOCK_DEPTH),
    ):
        values = [plane["value"] for plane in planes if plane["axis"] == axis]
        assert (min(values), max(values)) == pytest.approx((0.0, size))


def test_the_rebate_bands_are_the_printed_ones(manifest: dict) -> None:
    features = manifest["features"]
    ceiling = features["rebate_ceiling"]
    assert ceiling["roof_thickness"] == pytest.approx([_in(0.08), _in(0.10)])
    assert ceiling["roof_thickness_from"] == "top_face"
    # Ra 63 uin on the stick's sliding face.
    assert ceiling["finish_ra"] == pytest.approx(1.6)
    for name, key, low in (
        ("rebate_floor", "rebate_height", 0.134),
        ("rebate_back", "rebate_width", 0.330),
    ):
        rebate = features[name]
        # +.010/0 (owner ruling 2026-11-21).
        assert rebate[key] == pytest.approx([_in(low), _in(low + 0.010)], abs=1e-6)
        assert rebate["callout"] == "SEE NOTE 1"
        assert rebate["note"] == drawing.REBATE_NOTE
    assert features["rebate_floor"]["rebate_height_from"] == "rebate_ceiling"
    assert features["rebate_back"]["rebate_width_from"] == "mating_face"
    assert features["relief_back"]["relief_depth"] == pytest.approx(
        [_in(0.04), _in(0.06)]
    )
    assert features["relief_back"]["relief_depth_from"] == "rebate_back"
    assert features["relief_floor"]["relief_height"] == pytest.approx(
        [_in(0.05), _in(0.07)]
    )
    assert features["relief_floor"]["relief_height_from"] == "rebate_ceiling"
    for index in (1, 2):
        chamfer = features[f"roof_chamfer_{index}"]
        assert chamfer["size"] == pytest.approx([_in(0.03), _in(0.05)])
        assert chamfer["angle_deg"] == pytest.approx([44.0, 46.0])
        assert chamfer["callout"] == "2 CORNERS"


def test_the_tap_bands_are_the_printed_ones(manifest: dict) -> None:
    features = manifest["features"]
    thumb = features["thumb_tap"]
    assert thumb["thread"] == "#4-40 UNC-2B"
    # The #43 tap drill at the title block's DRILLED HOLES +.004/0.
    assert thumb["dia"] == pytest.approx([_in(0.089), _in(0.093)], abs=1e-3)
    assert thumb["thru"] is True and thumb["axis"] == [0.0, 1.0, 0.0]
    assert thumb["at"] == pytest.approx([spec.THUMB_AXIS_X, 0.0, spec.THUMB_AXIS_Z])
    assert thumb["exit_face"] == "rebate_floor"
    assert thumb["end_note"] == "INTO REBATE; ROOF NOT DRILLED"
    assert thumb["location_from_end"] == pytest.approx([_in(0.41), _in(0.43)])
    assert thumb["location_from_end_from"] == "locating_end"
    assert thumb["location_from_mating_face"] == pytest.approx([_in(0.16), _in(0.18)])
    assert thumb["location_from_mating_face_from"] == "mating_face"
    plate_number = _config.parts("ms-stop-plate")["number"]
    for index, station in ((1, 0.150), (2, 0.690)):
        tap = features[f"plate_tap_{index}"]
        assert tap["thread"] == "#2-56 UNC-2B"
        # The #49 tap drill at DRILLED HOLES +.004/0, ↧.30; thread ↧.25
        # (rule 3: tap and tap-drill depths at .XX).
        assert tap["dia"] == pytest.approx([_in(0.073), _in(0.077)], abs=1e-3)
        assert tap["drill_depth"] == pytest.approx([_in(0.29), _in(0.31)])
        assert tap["thread_depth"] == pytest.approx([_in(0.24), _in(0.26)])
        assert tap["axis"] == [0.0, 0.0, 1.0] and "thru" not in tap
        # Drilled with the plate in its traveler; tapped in this one.
        assert tap["made_at"] == "pair_drill"
        assert tap["pair_drill_master"] == plate_number
        assert tap["pair_drill_alignment"] == "LOCATING ENDS AND EDGES FLUSH"
        assert tap["tapped_in"] == _config.parts("ms-stop-block")["number"]
        assert tap["callout"] == drawing.COVER_HOLE_MATCH_DRILL
        assert tap["dimension_type"] == "reference"
        assert tap["location_from_end_ref"] == pytest.approx(_in(station))
        assert tap["location_from_edge_ref"] == pytest.approx(_in(0.160))
        assert tap["location_from_end_ref_from"] == "locating_end"
        assert tap["location_from_edge_ref_from"] == "locating_edge"
    for name, feature in features.items():
        for key, value in feature.items():
            if key.endswith("_from"):
                assert isinstance(value, str) and value in features, (name, key)
