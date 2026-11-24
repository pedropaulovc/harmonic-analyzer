"""Feature-export contracts for the arbor pedestal (MHA-DT-02): the
declarations in ``draw_dt_arbor_pedestal`` name one STEP face each and carry
the bands the sheet prints."""

from __future__ import annotations

from math import hypot

import pytest

import draw_dt_arbor_pedestal as drawing
import dt_arbor_pedestal_notes as notes
import dt_arbor_pedestal_spec as spec
import export_features
from _gtol_face import FaceGeometry
from _hole_spec import blind_cut_dia_mm
from _surface_finish import SEAT_UM

_STEM = "dt_arbor_pedestal"

_FEATURE_KINDS = {
    "foot_seat": "face",
    "foot_top": "face",
    "far_face": "face",
    "near_end": "face",
    "strap_outer_face": "face",
    "west_side": "face",
    "east_side": "face",
    "flanks": "tapered_side",
    "crown": "arc",
    "arbor_bore": "hole",
    "hold_down_hole": "hole",
    "apex_tap": "threaded_hole",
}


def _in(value_in: float) -> float:
    return value_in * spec.MM_PER_IN


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


def _flank(sign: float) -> FaceGeometry:
    """One tapered flank as the model cuts it: the straight line from the
    foot's top corner to its tangent point on the crown, extruded along Z."""
    root = (sign * spec.FOOT_WIDTH / 2, spec.FOOT_HEIGHT)
    tangent = (sign * spec.TAPER_TANGENT_X, spec.TAPER_TANGENT_Y)
    run, rise = tangent[0] - root[0], tangent[1] - root[1]
    length = hypot(run, rise)
    normal = (sign * rise / length, -sign * run / length, 0.0)
    point = (root[0] / 1000, root[1] / 1000, spec.STRAP_INNER_Z / 1000)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _manifest() -> dict:
    return export_features.requirement_manifest(_STEM)


def test_the_pedestal_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert _STEM in export_features.SUPPORTED_PARTS
    manifest = _manifest()
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    # The sheet prints no numbered note: every requirement is a dimension or
    # the words under one.
    assert notes.DRAWING_NOTES == ""
    assert manifest["notes"]["manufacturing"] == notes.DRAWING_NOTES.splitlines()
    selectors = export_features.feature_selectors(_STEM)
    half = spec.FOOT_WIDTH / 2
    top = spec.BORE_HEIGHT + spec.TOP_RADIUS
    bore_r = spec.BORE_DIA / 2
    hole_r = spec.SCREW_HOLE_DIA / 2
    tap_dia = blind_cut_dia_mm(spec.SET_SCREW_HOLE_SPEC)
    tap_r = tap_dia / 2
    strap_z = (spec.STRAP_ROOT_Z, spec.STRAP_INNER_Z)
    expected = {
        "foot_seat": [_plane((0.0, -1.0, 0.0), 0.0)],
        "foot_top": [_plane((0.0, 1.0, 0.0), spec.FOOT_HEIGHT)],
        "far_face": [_plane((0.0, 0.0, 1.0), spec.STRAP_INNER_Z)],
        "near_end": [_plane((0.0, 0.0, -1.0), -spec.FOOT_NEAR_Z)],
        "strap_outer_face": [_plane((0.0, 0.0, -1.0), -spec.STRAP_ROOT_Z)],
        "west_side": [_plane((-1.0, 0.0, 0.0), half)],
        "east_side": [_plane((1.0, 0.0, 0.0), half)],
        # A 1.47 deg lean is inside the selectors' normal tolerance of the
        # foot sides; the plane offsets alone keep the owners apart.
        "flanks": [_flank(1.0), _flank(-1.0)],
        "crown": [
            _cylinder(
                2 * spec.TOP_RADIUS,
                (0.0, 0.0, 1.0),
                (
                    -spec.TAPER_TANGENT_X,
                    spec.TAPER_TANGENT_Y,
                    strap_z[0],
                    spec.TAPER_TANGENT_X,
                    top,
                    strap_z[1],
                ),
            )
        ],
        "arbor_bore": [
            _cylinder(
                spec.BORE_DIA,
                (0.0, 0.0, 1.0),
                (
                    -bore_r,
                    spec.BORE_HEIGHT - bore_r,
                    strap_z[0],
                    bore_r,
                    spec.BORE_HEIGHT + bore_r,
                    strap_z[1],
                ),
            )
        ],
        "hold_down_hole": [
            _cylinder(
                spec.SCREW_HOLE_DIA,
                (0.0, 1.0, 0.0),
                (
                    -hole_r,
                    0.0,
                    spec.SCREW_Z - hole_r,
                    hole_r,
                    spec.FOOT_HEIGHT,
                    spec.SCREW_Z + hole_r,
                ),
            )
        ],
        "apex_tap": [
            _cylinder(
                tap_dia,
                (0.0, 1.0, 0.0),
                (
                    -tap_r,
                    spec.BORE_HEIGHT + bore_r,
                    spec.SET_SCREW_Z - tap_r,
                    tap_r,
                    top,
                    spec.SET_SCREW_Z + tap_r,
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


def test_pedestal_feature_bands_are_the_printed_ones() -> None:
    features = _manifest()["features"]
    assert features["foot_seat"]["finish_ra"] == SEAT_UM
    assert features["foot_top"]["height"] == pytest.approx([_in(0.19), _in(0.21)])
    assert features["near_end"]["depth"] == pytest.approx([_in(1.09), _in(1.11)])
    assert features["strap_outer_face"]["depth"] == pytest.approx(
        [_in(0.39), _in(0.41)]
    )
    assert features["east_side"]["width"] == pytest.approx([_in(0.93), _in(0.95)])

    flanks = features["flanks"]
    # The (91.47 deg) reference and the owner's parallel-sides option under it.
    assert flanks["angle_ref_deg"] == pytest.approx(91.47, abs=0.005)
    assert flanks["angle_ref_deg"] == drawing.FLANK_ANGLE_DEG
    assert flanks["dimension_type"] == "reference"
    assert flanks["parallel_sides_ok"] is True
    assert flanks["callout"] == drawing.FLANK_ANGLE_CALLOUT
    assert flanks["tangent_to"] == "crown"
    # Parallel sides tangent to the crown stand .04 inside the foot's sides.
    assert flanks["root_half_width_nominal"] - flanks[
        "parallel_half_width_nominal"
    ] == pytest.approx(_in(0.04))

    crown = features["crown"]
    assert crown["radius"] == pytest.approx([_in(0.42), _in(0.44)])
    assert crown["callout"] == drawing.CROWN_CALLOUT
    assert crown["concentric_with"] == "arbor_bore"
    assert crown["overall_height_ref"] == pytest.approx(_in(2.18), abs=_in(0.005))

    bore = features["arbor_bore"]
    # Ø.377 V DRILL THRU, ARBOR MHA-DT-13 ENTERS BY HAND (fit audit F01).
    assert bore["dia"] == pytest.approx([_in(0.377), _in(0.381)])
    assert bore["precision"]["dia"] == 3
    assert bore["process"] == "drill" and bore["drill"] == "V"
    assert bore["thru"] is True
    assert bore["callout"] == drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert bore["mates"] == drawing.ARBOR_NUMBER
    assert bore["finish_ra"] == SEAT_UM
    assert bore["height"] == pytest.approx([_in(1.74), _in(1.76)])
    assert bore["lateral"] == pytest.approx([_in(0.46), _in(0.48)])

    hold_down = features["hold_down_hole"]
    # Ø.180 DRILL THRU ALL at the title block's DRILLED HOLES +.004/0.
    assert hold_down["dia"] == pytest.approx([_in(0.180), _in(0.184)], abs=1e-3)
    assert hold_down["process"] == "drill" and hold_down["thru"] is True
    assert hold_down["station"] == pytest.approx([_in(0.74), _in(0.76)])
    assert hold_down["lateral"] == pytest.approx([_in(0.46), _in(0.48)])

    tap = features["apex_tap"]
    # Ø.089 TO BORE / TAP 4-40 UNC TO BORE, the class from the title block.
    assert tap["thread"] == "#4-40 UNC-2B"
    assert tap["dia"] == pytest.approx([_in(0.089), _in(0.093)], abs=1e-3)
    assert tap["into"] == "arbor_bore" and "thru" not in tap
    assert tap["callout_extent"] == drawing.SET_SCREW_EXTENT
    assert tap["station"] == pytest.approx([_in(0.19), _in(0.21)])
    assert tap["lateral"] == pytest.approx([_in(0.46), _in(0.48)])


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


def test_the_apex_tap_runs_into_the_arbor_bore_and_the_envelope_is_the_blank() -> None:
    features = _manifest()["features"]
    tap, bore = features["apex_tap"], features["arbor_bore"]
    # The tap's axis line crosses the bore's: same X, square to it, and its
    # station inside the strap the bore runs through.
    assert tap["at"][0] == bore["at"][0]
    assert sum(a * b for a, b in zip(tap["axis"], bore["axis"])) == 0.0
    assert spec.STRAP_ROOT_Z < tap["at"][2] < spec.STRAP_INNER_Z
    assert tap["at"][1] > bore["at"][1]
    crown = features["crown"]
    assert crown["center"] == bore["at"]
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
    highs["y"] = max(highs["y"], crown["center"][1] + crown["radius_nominal"])
    assert highs["x"] - lows["x"] == pytest.approx(spec.FOOT_WIDTH)
    assert highs["y"] - lows["y"] == pytest.approx(_in(2.18), abs=_in(0.005))
    assert highs["z"] - lows["z"] == pytest.approx(spec.FOOT_DEPTH)
