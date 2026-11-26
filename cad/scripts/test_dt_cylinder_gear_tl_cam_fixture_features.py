"""Offline contracts for the cam turning fixture's feature-export declarations."""

from __future__ import annotations

import pytest

import draw_dt_cylinder_gear_tl_cam_fixture as drawing
import dt_cylinder_gear_tl_cam_fixture_spec as spec
import export_features
from _gtol_face import FaceGeometry

_STEM = "dt_cylinder_gear_tl_cam_fixture"
_FEATURE_KINDS = {
    "back_face": "face",
    "front_face": "face",
    "register": "outside_cylinder",
    "stub_hole": "hole",
    "pin_hole": "hole",
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


def test_the_fixture_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert _STEM in export_features.SUPPORTED_PARTS
    assert _STEM in export_features.DECLARED_PARTS
    manifest = export_features.requirement_manifest(_STEM)
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    selectors = export_features.feature_selectors(_STEM)
    thick, body_r = spec.THICKNESS, spec.BODY_DIA / 2
    stub_r, stub_y = spec.STUB_HOLE_DIA / 2, -spec.STUB_OFFSET
    pin_r, pin_x, pin_y = spec.PIN_HOLE_DIA / 2, spec.PIN_X, spec.PIN_Y
    floor = thick - spec.PIN_HOLE_DEPTH
    expected = {
        "back_face": _plane((0.0, 0.0, -1.0), 0.0),
        "front_face": _plane((0.0, 0.0, 1.0), thick),
        "register": _cylinder(
            spec.BODY_DIA, (0.0, 0.0, 1.0), (-body_r, -body_r, 0, body_r, body_r, thick)
        ),
        "stub_hole": _cylinder(
            spec.STUB_HOLE_DIA,
            (0.0, 0.0, 1.0),
            (-stub_r, stub_y - stub_r, 0, stub_r, stub_y + stub_r, thick),
        ),
        "pin_hole": _cylinder(
            spec.PIN_HOLE_DIA,
            (0.0, 0.0, 1.0),
            (pin_x - pin_r, pin_y - pin_r, floor, pin_x + pin_r, pin_y + pin_r, thick),
        ),
    }
    # The blind ream's flat floor (the model's; the reamer leaves its lead).
    pin_floor = _plane((0.0, 0.0, 1.0), floor)
    for name, face in {**expected, "pin_floor": pin_floor}.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(face) for selector in specs)
        ]
        assert owners == ["pin_hole" if name == "pin_floor" else name], name


def test_fixture_frame_puts_the_stub_below_the_axis_and_both_reams_in_the_front() -> (
    None
):
    features = export_features.requirement_manifest(_STEM)["features"]
    assert features["back_face"]["plane"] == {
        "frame": "model",
        "axis": "z",
        "value": 0.0,
    }
    assert features["front_face"]["plane"]["value"] == spec.THICKNESS
    register = features["register"]
    assert register["at"] == [0.0, 0.0, 0.0] and register["axis"] == [0.0, 0.0, 1.0]
    stub, pin = features["stub_hole"], features["pin_hole"]
    # Both reams enter the gear-seat face and run -Z into the body.
    assert stub["at"] == pytest.approx([0.0, -spec.STUB_OFFSET, spec.THICKNESS])
    assert pin["at"] == pytest.approx([spec.PIN_X, spec.PIN_Y, spec.THICKNESS])
    assert stub["axis"] == pin["axis"] == [0.0, 0.0, -1.0]
    assert stub["thru"] is True and "depth" not in stub
    assert "thru" not in pin and "into" not in pin
    # The pin sits left of the vertical centreline seen from the tailstock (-X).
    assert pin["at"][0] < 0.0 < pin["at"][1] and stub["at"][1] < 0.0


def test_fixture_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest(_STEM)["features"]
    register = features["register"]
    # Ø3.25 and 1.00, each on the title block's .XX ±.01.
    assert register["dia"] == pytest.approx([_in(3.24), _in(3.26)])
    assert register["length"] == pytest.approx([_in(0.99), _in(1.01)])
    assert register["precision"] == {"dia": 2, "length": 2}
    stub = features["stub_hole"]
    # Ø.3740 +.0005/.0000 REAM THRU, .3402 ±.0020 from the register axis.
    assert stub["dia"] == pytest.approx([_in(0.3740), _in(0.3745)])
    assert stub["process"] == "ream"
    assert stub["station_y"] == pytest.approx([_in(0.3382), _in(0.3422)])
    assert stub["station_y_from"] == "register" and stub["station_y_axis"] == "y"
    assert stub["callout"] == spec.CALLOUTS_BELOW["StubHoleDia"]
    assert stub["mates"] == spec.STUB_NUMBER == "MHA-DT-12-TL-VN-50"
    assert min(stub["diametral_interference"]) > 0.0
    assert stub["precision"] == {"dia": 4, "station_y": 4}
    pin = features["pin_hole"]
    # Ø.0365 +.0005/.0000 REAM .20 deep (.XX ±.01), .0704 / .9246 ±.0020.
    assert pin["dia"] == pytest.approx([_in(0.0365), _in(0.0370)])
    assert pin["process"] == "ream"
    assert pin["depth"] == pytest.approx([_in(0.19), _in(0.21)])
    assert pin["station_x"] == pytest.approx([_in(0.0684), _in(0.0724)])
    assert pin["station_y"] == pytest.approx([_in(0.9226), _in(0.9266)])
    assert pin["station_x_axis"] == "x" and pin["station_y_axis"] == "y"
    assert pin["station_x_from"] == pin["station_y_from"] == "register"
    assert pin["callout"] == spec.CALLOUTS_BELOW["PinHoleDia"]
    assert pin["mates"] == spec.CLOCK_PIN_NUMBER == "MHA-DT-12-TL-VN-51"
    assert min(pin["diametral_interference"]) > 0.0
    assert pin["precision"] == {"dia": 4, "depth": 2, "station_x": 4, "station_y": 4}


def test_every_located_band_cites_the_printed_dimension_place() -> None:
    features = export_features.requirement_manifest(_STEM)["features"]
    for name, key, keep in (
        ("register", "dia", "BODY_DIA_ON_EDGE"),
        ("register", "length", "EDGE_KEEP"),
        ("stub_hole", "station_y", "FACE_KEEP"),
        ("pin_hole", "station_x", "FACE_KEEP"),
        ("pin_hole", "station_y", "FACE_KEEP"),
    ):
        assert any(cite.endswith(f"#{keep}") for cite in features[name]["cite"][key]), (
            name,
            key,
        )
    for keep in ("StubOffset", "PinX", "PinY", "StubHoleDia", "PinHoleDia"):
        assert keep in drawing.FACE_KEEP


def test_fixture_manifest_has_no_notes_and_the_title_block_edge_break() -> None:
    manifest = export_features.requirement_manifest(_STEM)
    assert manifest["notes"]["manufacturing"] == []
    assert manifest["notes"]["edge_break"] == (
        "REMOVE BURRS AND BREAK SHARP EDGES R.010 OR CHAMFER .010 MAX"
    )
