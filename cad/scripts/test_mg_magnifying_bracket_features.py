"""Feature-export contracts for the magnifying bracket (MHA-MG-01): the
declarations in ``draw_mg_magnifying_bracket`` name one STEP face each and
carry the bands the sheet prints."""

from __future__ import annotations

import pytest

import draw_mg_magnifying_bracket as drawing
import export_features
import magnifying_bracket_joint_layout as joint
import mg_lever_thread_joint as thread
import mg_magnifying_bracket_spec as spec
from _gtol_face import FaceGeometry
from _surface_finish import SEAT_UM, surface_finish_by_key
from mg_magnifying_bracket_finish_spec import SURFACE_FINISHES

_STEM = "mg_magnifying_bracket"
_MM_PER_IN = 25.4

_FEATURE_KINDS = {
    "seat": "face",
    "foot_underside": "face",
    "free_end": "face",
    "outer_face": "face",
    "neck_inner_face": "face",
    "low_side": "face",
    "high_side": "face",
    "nose": "arc",
    "lever_tap": "threaded_hole",
    "mounting_hole_1": "hole",
    "mounting_hole_2": "hole",
    "inside_corner": "fillet",
}


def _in(value_in: float) -> float:
    return value_in * _MM_PER_IN


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


def _manifest() -> dict:
    return export_features.requirement_manifest(_STEM)


def test_the_bracket_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert _STEM in export_features.SUPPORTED_PARTS
    manifest = _manifest()
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    # The sheet prints no numbered note: every requirement is a dimension or
    # the words under one.
    assert drawing.DRAWING_NOTES == ""
    assert manifest["notes"]["manufacturing"] == drawing.DRAWING_NOTES.splitlines()
    selectors = export_features.feature_selectors(_STEM)
    x0, x1 = joint.SIDE_PLATE_X
    y0, y1 = joint.SIDE_PLATE_Y
    z0, z1 = joint.SIDE_PLATE_Z
    half = thread.NECK_HALF_X
    nose_r = thread.NOSE_R
    tap_r = thread.TAP_DRILL_DIA / 2
    hole_r = joint.CLEARANCE_DIA / 2
    expected = {
        "seat": [_plane((0.0, 0.0, 1.0), z1)],
        "foot_underside": [_plane((0.0, 0.0, -1.0), -z0)],
        "free_end": [_plane((-1.0, 0.0, 0.0), -x0)],
        "outer_face": [_plane((1.0, 0.0, 0.0), x1)],
        "neck_inner_face": [_plane((-1.0, 0.0, 0.0), half)],
        "low_side": [_plane((0.0, -1.0, 0.0), -y0)],
        "high_side": [_plane((0.0, 1.0, 0.0), y1)],
        "nose": [
            _cylinder(2 * nose_r, (1.0, 0.0, 0.0), (-half, -nose_r, -nose_r, half, nose_r, 0.0))
        ],
        "lever_tap": [
            _cylinder(2 * tap_r, (1.0, 0.0, 0.0), (-half, -tap_r, -tap_r, half, tap_r, tap_r))
        ],
        **{
            f"mounting_hole_{index}": [
                _cylinder(
                    joint.CLEARANCE_DIA,
                    (0.0, 0.0, 1.0),
                    (x - hole_r, y - hole_r, z0, x + hole_r, y + hole_r, z1),
                )
            ]
            for index, (x, y, _z) in enumerate(joint.BRACKET_HOLE_POINTS, 1)
        },
        "inside_corner": [
            _cylinder(
                2 * spec.INSIDE_ROOT_R_MAX,
                (0.0, 1.0, 0.0),
                (
                    -half - spec.INSIDE_ROOT_R_MAX,
                    y0,
                    z0 - spec.INSIDE_ROOT_R_MAX,
                    -half,
                    y1,
                    z0,
                ),
            )
        ],
    }
    assert set(expected) == set(_FEATURE_KINDS)
    for name, faces in expected.items():
        for face in faces:
            owners = [
                owner
                for owner, specs in selectors.items()
                if any(selector.matches(face) for selector in specs)
            ]
            assert owners == [name], name
    # The Ra 125 flag's own face is the seat's.
    assert selectors["seat"] == (surface_finish_by_key(SURFACE_FINISHES, "foot_seat").face,)


def test_bracket_feature_bands_are_the_printed_ones() -> None:
    features = _manifest()["features"]
    assert features["seat"]["finish_ra"] == SEAT_UM
    underside = features["foot_underside"]
    # .125 MHA-MG-VN-53 SCREW GRIP at the title block's .XXX.
    assert underside["thickness"] == pytest.approx([_in(0.120), _in(0.130)])
    assert underside["callout"] == spec.DIMENSION_CALLOUTS["FlangeProfile"]["FlangeDepth"]
    assert features["outer_face"]["length"] == pytest.approx([_in(2.13), _in(2.15)])
    assert features["neck_inner_face"]["thickness"] == pytest.approx([_in(0.48), _in(0.50)])
    assert features["high_side"]["width"] == pytest.approx([_in(0.42), _in(0.44)])

    nose = features["nose"]
    # R.217 ±.002 RETAINS TAP WALL, on the printed .217.
    assert nose["radius"] == pytest.approx([_in(0.215), _in(0.219)])
    assert nose["callout"] == spec.DIMENSION_CALLOUTS["NeckProfile"]["NoseR"]
    assert nose["concentric_with"] == "lever_tap"
    assert nose["apex"] == [0.0, 0.0, -1.0]
    assert nose["overall_height_ref"] == pytest.approx(_in(3.92), abs=_in(0.005))
    assert nose["precision"]["overall_height_ref"] == spec.DRAWING_REFERENCE_PRECISION["OverallHeight"]

    tap = features["lever_tap"]
    # Ø.201 DRILL THRU ALL / 1/4-20 UNC THRU ALL / MATES MHA-MG-03 LEVER, the
    # class from the title block.
    assert tap["thread"] == "1/4-20 UNC-2B"
    assert tap["dia"] == pytest.approx([_in(0.201), _in(0.205)], abs=1e-3)
    assert tap["thru"] is True and "into" not in tap
    assert tap["note"] == spec.TAP_PROCESS
    assert tap["height"] == pytest.approx([_in(3.69), _in(3.71)])
    assert tap["from_tip"] == pytest.approx([_in(0.215), _in(0.219)])
    assert tap["from_tip_datum"] == "nose"
    assert tap["lateral"] == pytest.approx([_in(0.215), _in(0.219)])
    assert tap["location_callout"] == spec.DIMENSION_CALLOUTS["TapCoordinates"]["TapFromTip"]

    for name, station in (("mounting_hole_1", 0.354), ("mounting_hole_2", 0.894)):
        hole = features[name]
        # 2X Ø.102 DRILL THRU ALL / MATES MHA-SM-03 TAPPED HOLES.
        assert hole["dia"] == pytest.approx([_in(0.102), _in(0.106)], abs=1e-3)
        assert hole["process"] == "drill" and hole["thru"] is True
        assert hole["clearance_for"] == "#2" and hole["count"] == 2
        assert hole["note"] == spec.MOUNTING_HOLE_PROCESS
        assert hole["station"] == pytest.approx([_in(station - 0.005), _in(station + 0.005)])
        assert hole["lateral"] == pytest.approx([_in(0.221), _in(0.231)])

    corner = features["inside_corner"]
    assert corner["radius"] == pytest.approx([0.0, _in(0.02)])
    assert corner["radius_nominal"] == pytest.approx(spec.INSIDE_ROOT_R_MAX)
    assert corner["axis"] == [0.0, 1.0, 0.0]
    assert corner["at"] == [-thread.NECK_HALF_X, 0.0, joint.SIDE_PLATE_Z[0]]


def _coordinate(feature: dict, axis: int) -> float:
    if feature["kind"] == "arc":
        return feature["center"][axis]
    if "at" in feature:
        return feature["at"][axis]
    return feature["plane"]["value"]


def test_every_location_closes_on_the_face_it_is_printed_from() -> None:
    features = _manifest()["features"]
    checked = 0
    for name, feature in features.items():
        for key, target in feature.items():
            stem = key.removesuffix("_from")
            if stem == key or f"{stem}_nominal" not in feature:
                continue
            plane = features[target]["plane"]
            axis = "xyz".index(plane["axis"])
            if feature["kind"] == "face":
                assert feature["plane"]["axis"] == plane["axis"], (name, key)
            distance = abs(_coordinate(feature, axis) - plane["value"])
            assert distance == pytest.approx(abs(feature[f"{stem}_nominal"])), (
                name,
                key,
            )
            checked += 1
    assert checked == 10


def test_the_tap_sits_one_nose_radius_inside_the_tip_and_the_envelope_is_the_part() -> None:
    features = _manifest()["features"]
    tap, nose = features["lever_tap"], features["nose"]
    # The tip is the nose's apex: the tap's location from it is the nose
    # radius along the apex direction, and the nose is concentric with it.
    assert nose["center"][1:] == tap["at"][1:]
    tip = [c + nose["radius_nominal"] * a for c, a in zip(nose["center"], nose["apex"], strict=True)]
    assert abs(tap["at"][2] - tip[2]) == pytest.approx(tap["from_tip_nominal"])
    # The tap runs through the neck, outer face to inner face.
    assert tap["at"][0] == features["outer_face"]["plane"]["value"]
    assert tap["axis"] == [-1.0, 0.0, 0.0]
    planes = {
        name: feature["plane"]
        for name, feature in features.items()
        if feature["kind"] == "face"
    }
    lows = {
        axis: min(p["value"] for p in planes.values() if p["axis"] == axis)
        for axis in "xyz"
    }
    highs = {
        axis: max(p["value"] for p in planes.values() if p["axis"] == axis)
        for axis in "xyz"
    }
    lows["z"] = min(lows["z"], tip[2])
    assert highs["x"] - lows["x"] == pytest.approx(_in(2.14), abs=_in(0.005))
    assert highs["y"] - lows["y"] == pytest.approx(_in(0.43), abs=_in(0.005))
    assert highs["z"] - lows["z"] == pytest.approx(nose["overall_height_ref"])
    # Both foot holes enter the underside and run through the foot's grip.
    for name in ("mounting_hole_1", "mounting_hole_2"):
        hole = features[name]
        assert hole["at"][2] == features["foot_underside"]["plane"]["value"]
        assert hole["axis"] == [0.0, 0.0, 1.0]
