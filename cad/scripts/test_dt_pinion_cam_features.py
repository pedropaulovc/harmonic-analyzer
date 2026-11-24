"""Offline contracts for the pinion lift cam's feature-export declarations."""

from __future__ import annotations

import pytest

import draw_dt_pinion_cam as drawing
import dt_pinion_cam_spec as spec
import export_features
from _gtol_face import FaceGeometry

_STEM = "dt_pinion_cam"
_FEATURE_KINDS = {
    "front_face": "face",
    "rear_face": "face",
    "cam_od": "outside_cylinder",
    "bore": "hole",
    "set_screw_tap": "threaded_hole",
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


def _native_band(band: list[float], low_in: float, high_in: float, places: int) -> None:
    """An explicit native band on the exact model nominal: the sheet's limits
    to within half a printed unit (the nominal prints rounded), its width
    exactly the printed tolerance."""
    assert band == pytest.approx([_in(low_in), _in(high_in)], abs=_in(0.5 / 10**places))
    assert band[1] - band[0] == pytest.approx(_in(high_in - low_in))


def test_the_cam_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert _STEM in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest(_STEM)
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    selectors = export_features.feature_selectors(_STEM)
    length, ecc = spec.CAM_LEN, spec.ECC
    od_r, bore_r = spec.CAM_OD / 2, spec.BORE / 2
    tap_r, tap_z = spec.TAP_DRILL_DIA / 2, spec.SET_SCREW_Z
    expected = {
        "front_face": _plane((0.0, 0.0, -1.0), 0.0),
        "rear_face": _plane((0.0, 0.0, 1.0), length),
        "cam_od": _cylinder(
            spec.CAM_OD,
            (0.0, 0.0, 1.0),
            (-od_r, -ecc - od_r, 0, od_r, od_r - ecc, length),
        ),
        "bore": _cylinder(
            spec.BORE, (0.0, 0.0, 1.0), (-bore_r, -bore_r, 0, bore_r, bore_r, length)
        ),
        "set_screw_tap": _cylinder(
            spec.TAP_DRILL_DIA,
            (0.0, 1.0, 0.0),
            (-tap_r, -ecc - od_r, tap_z - tap_r, tap_r, -bore_r, tap_z + tap_r),
        ),
    }
    for name, face in expected.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(face) for selector in specs)
        ]
        assert owners == [name], name


def test_cam_frame_puts_the_od_below_the_bore_and_the_tap_on_the_heavy_side() -> None:
    features = export_features.requirement_manifest(_STEM)["features"]
    assert features["front_face"]["plane"] == {
        "frame": "model",
        "axis": "z",
        "value": 0.0,
    }
    assert features["rear_face"]["plane"]["value"] == spec.CAM_LEN
    od, bore, tap = features["cam_od"], features["bore"], features["set_screw_tap"]
    assert od["at"] == [0.0, -spec.ECC, 0.0] and od["axis"] == [0.0, 0.0, 1.0]
    assert bore["at"] == [0.0, 0.0, 0.0] and bore["axis"] == [0.0, 0.0, 1.0]
    assert bore["thin_side"] == [0.0, 1.0, 0.0]
    # The tap enters at the OD's lowest line, opposite the thin side, and runs
    # up into the bore.
    assert tap["at"] == pytest.approx(
        [0.0, -(spec.ECC + spec.CAM_OD / 2), spec.SET_SCREW_Z]
    )
    assert tap["axis"] == [0.0, 1.0, 0.0]
    assert tap["into"] == "bore" and "thru" not in tap
    assert tap["angle_from_thin_side_deg"] == pytest.approx(180.0)


def test_cam_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest(_STEM)["features"]
    od = features["cam_od"]
    # Ø.575 ±.002 and .35 (title block .XX ±.01), Ra 63 µin on the OD.
    _native_band(od["dia"], 0.573, 0.577, 3)
    assert od["length"] == pytest.approx([_in(0.34), _in(0.36)])
    assert od["finish_ra"] == 1.6 and od["mates"] == "MHA-DT-25"
    assert od["callout"] == drawing.DIMENSION_CALLOUTS["CollarOd"] == "SEE NOTE 1"
    bore = features["bore"]
    # Ø.2510 REAM THRU, the MHA-DT-17 rod slides in by hand (fit audit F19);
    # dia and clearance are the reamer's ANALYSIS band.
    assert bore["dia"] == pytest.approx([_in(0.2510), _in(0.2515)])
    assert bore["process"] == "ream" and bore["thru"] is True
    assert bore["callout"] == drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert bore["mates"] == "MHA-DT-17"
    assert bore["diametral_clearance"] == pytest.approx(
        [_in(0.0010), _in(0.0023)], abs=_in(0.00005)
    )
    # .079 ±.002 from the OD's axis (SEE NOTE 1); the thin side .0797 MIN.
    _native_band(bore["eccentricity"], 0.077, 0.081, 3)
    assert bore["eccentricity_from"] == "cam_od" and bore["eccentricity_axis"] == "y"
    assert bore["eccentricity_callout"] == drawing.DIMENSION_CALLOUTS["CollarCy"]
    assert bore["thin_wall_min"] == pytest.approx(_in(0.0797))
    assert bore["thin_wall_callout"] == drawing.DIMENSION_CALLOUTS["ThinWallMin"]
    tap = features["set_screw_tap"]
    # Ø.070 TAP DRILL THRU TO BORE #2-56 UNC at the DRILLED HOLES +.004/0, .16
    # (title block .XX ±.01) from the front face on VIEW A.
    assert tap["thread"] == "#2-56 UNC-2B"
    assert tap["dia"] == pytest.approx([_in(0.070), _in(0.074)], abs=1e-3)
    assert tap["station"] == pytest.approx([_in(0.15), _in(0.17)])
    assert tap["station_from"] == "front_face"
    assert tap["callout"] == drawing.DIMENSION_CALLOUTS["TapDrillDia"]
    assert tap["view"] == "VIEW A"
    assert tap["precision"] == {"dia": 3, "station": 2}


def test_cam_manifest_notes_are_the_sheets() -> None:
    manifest = export_features.requirement_manifest(_STEM)
    notes = manifest["notes"]["manufacturing"]
    assert notes == spec.DRAWING_NOTES.split("\n")
    assert notes == [
        "1. \N{LATIN CAPITAL LETTER O WITH STROKE}.575 AND .079 SET THE LIFT OF "
        "FOLLOWER PIN MHA-DT-25.",
        "2. SUPPLY ASME B18.3 #2-56 UNC X 3/16 FLAT-POINT SOCKET SET SCREW LOOSE.",
    ]
    features = manifest["features"]
    assert features["cam_od"]["note"] == notes[0]
    assert features["set_screw_tap"]["hardware_note"] == notes[1]
