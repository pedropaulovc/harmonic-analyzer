"""Offline: the pinion swing bracket's (MHA-DT-14) feature declarations.

``draw_dt_pinion_bracket`` declares what its sheet prints for the feature
export (export_features): each declared face selector owns exactly one STEP
patch, and every band is the one the sheet prints, in inches.
"""

from __future__ import annotations

import pytest

import draw_dt_pinion_bracket as drawing
import dt_pinion_bracket_spec as spec
import export_features
from _gtol_face import FaceGeometry

STEM = "dt_pinion_bracket"

_FEATURE_KINDS = {
    "broad_face_a": "face",
    "broad_face_b": "face",
    "seat_flank": "face",
    "far_flank": "face",
    "pivot_end": "arc",
    "arbor_end": "arc",
    "pivot_bore": "hole",
    "arbor_bore": "hole",
    "follower_seat": "hole",
    "cross_hole": "hole",
}


def _in(value_in: float) -> float:
    return value_in * 25.4


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


def test_the_strap_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert STEM in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest(STEM)
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    # The sheet prints no numbered general notes.
    assert manifest["notes"]["manufacturing"] == spec.DRAWING_NOTES.splitlines() == []
    selectors = export_features.feature_selectors(STEM)
    r, t, c2c = spec.R_END, spec.THICKNESS, spec.C2C
    z_axis, x_axis = (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)
    pivot_r, arbor_r = spec.PIVOT_BORE / 2, spec.ARBOR_BORE / 2
    seat_r, seat_y, seat_z = spec.PIN_BORE / 2, -spec.PIN_DROP, t / 2
    cross_r = spec.CROSS_HOLE_DIA / 2
    floor_x = -r + spec.PIN_SEAT
    expected = {
        "broad_face_a": [_plane((0.0, 0.0, -1.0), 0.0)],
        "broad_face_b": [_plane((0.0, 0.0, 1.0), t)],
        "seat_flank": [_plane((-1.0, 0.0, 0.0), r)],
        "far_flank": [_plane((1.0, 0.0, 0.0), r)],
        "pivot_end": [_cylinder(2 * r, z_axis, (-r, -r, 0.0, r, 0.0, t))],
        "arbor_end": [_cylinder(2 * r, z_axis, (-r, c2c, 0.0, r, c2c + r, t))],
        "pivot_bore": [
            _cylinder(
                spec.PIVOT_BORE, z_axis, (-pivot_r, -pivot_r, 0.0, pivot_r, pivot_r, t)
            )
        ],
        "arbor_bore": [
            _cylinder(
                spec.ARBOR_BORE,
                z_axis,
                (-arbor_r, c2c - arbor_r, 0.0, arbor_r, c2c + arbor_r, t),
            )
        ],
        "follower_seat": [
            _cylinder(
                spec.PIN_BORE,
                x_axis,
                (
                    -r,
                    seat_y - seat_r,
                    seat_z - seat_r,
                    floor_x,
                    seat_y + seat_r,
                    seat_z + seat_r,
                ),
            ),
            # The flat floor faces the mouth (-X).
            _plane((-1.0, 0.0, 0.0), -floor_x),
        ],
        # One wall each side of the pivot bore.
        "cross_hole": [
            _cylinder(
                spec.CROSS_HOLE_DIA,
                x_axis,
                (x0, -cross_r, seat_z - cross_r, x1, cross_r, seat_z + cross_r),
            )
            for x0, x1 in ((-r, -pivot_r), (pivot_r, r))
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


def test_strap_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest(STEM)["features"]
    # .36 thickness on the title block's .XX row.
    face_b = features["broad_face_b"]
    assert face_b["thickness"] == pytest.approx([_in(0.35), _in(0.37)])
    assert face_b["thickness_from"] == "broad_face_a"
    # Both R.30 ends, .XX; the (1.7) overall is a one-place reference.
    for name in ("pivot_end", "arbor_end"):
        assert features[name]["radius"] == pytest.approx([_in(0.29), _in(0.31)])
        assert features[name]["axis"] == [0.0, 0.0, 1.0]
    assert features["arbor_end"]["overall_length_ref"] == spec.OVERALL_LENGTH
    assert round(spec.OVERALL_LENGTH / 25.4, 1) == 1.7
    assert features["arbor_end"]["precision"]["overall_length_ref"] == 1
    # The .2510 reamer's size, no printed band (its ANALYSIS band .2510-.2515);
    # the MHA-DT-19 shaft is the gauge (fit audit F16).
    pivot = features["pivot_bore"]
    assert pivot["dia"] == pytest.approx([_in(0.2510), _in(0.2515)])
    assert (pivot["process"], pivot["thru"]) == ("ream", True)
    assert pivot["callout"] == drawing.DIMENSION_CALLOUTS["PivotBoreDia"]
    # 5/16 DRILL THRU at the DRILLED HOLES row, the MHA-DT-22 journals turned
    # to it (owner ruling 2026-11-24, fit audit question 12), Ra 63, 1.10
    # from the pivot bore.
    arbor = features["arbor_bore"]
    assert arbor["dia"] == pytest.approx([_in(0.3125), _in(0.3165)])
    assert (arbor["process"], arbor["thru"]) == ("drill", True)
    assert arbor["drill"] == "5/16"
    assert arbor["callout"] == drawing.DIMENSION_CALLOUTS["ArborBoreDia"]
    assert arbor["center_distance"] == pytest.approx([_in(1.09), _in(1.11)])
    assert (arbor["center_distance_from"], arbor["center_distance_axis"]) == (
        "pivot_bore",
        "y",
    )
    assert arbor["finish_ra_printed"] == "63"
    # Ø.157 +.003/.000 FLAT BOTTOM, end-milled (owner ruling 2026-11-23, tool
    # audit Q8), .16 deep (Section B-B), floor corners R.008 max, .276 above
    # the pivot axis and .180 from face A.
    seat = features["follower_seat"]
    assert seat["dia"] == pytest.approx([_in(0.157), _in(0.160)])
    assert (seat["process"], seat["flat_bottom"]) == ("drill", True)
    assert "thru" not in seat
    assert seat["depth"] == pytest.approx([_in(0.15), _in(0.17)])
    assert seat["floor_corner_r_max"] == pytest.approx(_in(0.008))
    assert seat["height"] == pytest.approx([_in(0.271), _in(0.281)])
    assert seat["station"] == pytest.approx([_in(0.175), _in(0.185)])
    assert seat["axis"] == [1.0, 0.0, 0.0]
    assert seat["callout"] == drawing.DIMENSION_CALLOUTS["PinSeatDia"]
    # Ø.0625 +.0025/.0000 match-drilled THRU at assembly with MHA-DT-19 for the
    # MHA-DT-VN-63 spring pin (owner ruling 2026-11-21), on the seat's .180
    # centreline and across the pivot bore: no process, the traveler skips it.
    cross = features["cross_hole"]
    assert cross["dia"] == pytest.approx([_in(0.0625), _in(0.0650)])
    assert (cross["made_at"], cross["thru"], cross["crosses"]) == (
        "assembly",
        True,
        "pivot_bore",
    )
    assert "process" not in cross
    assert cross["station"] == seat["station"]
    assert cross["callout"] == drawing.DIMENSION_CALLOUTS["CrossHoleDia"]


def _coordinate(feature: dict, axis: str) -> float:
    index = "xyz".index(axis)
    if feature["kind"] == "face":
        assert feature["plane"]["axis"] == axis
        return feature["plane"]["value"]
    return feature["center" if feature["kind"] == "arc" else "at"][index]


def test_every_located_nominal_is_the_model_distance_inside_its_band() -> None:
    features = export_features.requirement_manifest(STEM)["features"]
    checked = 0
    for feature in features.values():
        for key in feature["requirements"]:
            nominal = feature.get(f"{key}_nominal")
            band = feature.get(key)
            if nominal is not None:
                assert band[0] <= nominal <= band[1], key
            reference = feature.get(f"{key}_from")
            if reference is None:
                continue
            other = features[reference]
            axis = feature.get(f"{key}_axis") or other["plane"]["axis"]
            distance = abs(_coordinate(feature, axis) - _coordinate(other, axis))
            assert distance == pytest.approx(abs(nominal), abs=1e-3), key
            checked += 1
    # The thickness, the 1.10, the seat's .276 and .180, the cross hole's .180.
    assert checked == 5
