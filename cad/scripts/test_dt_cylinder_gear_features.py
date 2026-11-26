"""Offline contracts for the cylinder gear's feature-export declarations."""

from __future__ import annotations

import pytest

import dt_cylinder_gear_notes as notes
import dt_cylinder_gear_phase_band as phase
import dt_cylinder_gear_spec as spec
import export_features
from _gtol_face import FaceGeometry

_STEM = "dt_cylinder_gear"
_FEATURE_KINDS = {
    "back_face": "face",
    "rim_face": "face",
    "cam_face": "face",
    "teeth": "outside_cylinder",
    "cam": "outside_cylinder",
    "bore": "hole",
    "notch": "notch",
}


def _in(value_in: float) -> float:
    return value_in * 25.4


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(dia_mm: float, box_mm: tuple[float, ...]) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, dia_mm / 2000), None, box)


def test_the_gear_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert _STEM in export_features.DECLARED_PARTS
    manifest = export_features.requirement_manifest(_STEM)
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    selectors = export_features.feature_selectors(_STEM)
    tip_r = spec.OUTSIDE_DIA / 2
    cam_x, cam_y = phase.CAM_CENTER_XY
    cam_r, bore_r = spec.CAM_DIA / 2, spec.BORE_DIA / 2
    wall = spec.NOTCH_WIDTH / 2
    face, total = spec.FACE_WIDTH, spec.OVERALL_THICKNESS
    expected = {
        "back_face": _plane((0.0, 0.0, -1.0), 0.0),
        "rim_face": _plane((0.0, 0.0, 1.0), face),
        "cam_face": _plane((0.0, 0.0, 1.0), total),
        # One tip land of the 120: a patch of the blank cylinder.
        "teeth": _cylinder(spec.OUTSIDE_DIA, (-0.2, tip_r - 0.01, 0.0, 0.2, tip_r, face)),
        "cam": _cylinder(
            spec.CAM_DIA,
            (cam_x - cam_r, cam_y - cam_r, face, cam_x + cam_r, cam_y + cam_r, total),
        ),
        "bore": _cylinder(spec.BORE_DIA, (-bore_r, -bore_r, 0.0, bore_r, bore_r, total)),
        "notch": _plane((1.0, 0.0, 0.0), spec.NOTCH_CENTER_X - wall),
    }
    others = (
        _plane((-1.0, 0.0, 0.0), -(spec.NOTCH_CENTER_X + wall)),
        _plane((0.0, 1.0, 0.0), spec.NOTCH_FLOOR_RADIUS),
    )
    for name, geometry in [*expected.items(), *(("notch", item) for item in others)]:
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(geometry) for selector in specs)
        ]
        assert owners == [name], name
    # A tooth's root arc (a small off-axis cylinder) and the rim's outer face
    # at the cam diameter's neighbour belong to no feature.
    stray = _cylinder(1.0, (0.0, 30.0, 0.0, 1.0, 31.0, face))
    assert not any(
        selector.matches(stray) for specs in selectors.values() for selector in specs
    )


def test_gear_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest(_STEM)["features"]
    teeth = features["teeth"]
    # Ø2.536 +.000/-.004; GEAR DATA: 120T, 48 DP, 20°, #2 cutter, plunge
    # .0440 +.0020/.0000, tooth runout .002 TIR MAX.
    assert teeth["dia"] == pytest.approx([_in(2.532), _in(2.536)])
    assert teeth["count"] == 120 and teeth["diametral_pitch"] == 48.0
    assert teeth["pressure_angle_deg"] == 20.0 and teeth["cutter_number"] == 2
    assert teeth["plunge"] == pytest.approx([_in(0.0440), _in(0.0460)])
    assert teeth["tooth_runout_tir_max"] == pytest.approx(_in(0.002))
    assert teeth["tooth_runout_tir_max"] == notes.TOOTH_RUNOUT_TIR_MM
    assert features["rim_face"]["face_width"] == pytest.approx([_in(0.116), _in(0.120)])
    assert features["cam_face"]["thickness"] == pytest.approx([_in(0.2990), _in(0.3010)])
    cam = features["cam"]
    assert cam["dia"] == pytest.approx([_in(1.203), _in(1.205)])
    assert cam["throw"] == pytest.approx([8.64 - _in(0.002), 8.64 + _in(0.002)])
    assert cam["notch_phase_deg"] == 3.0 and cam["notch_phase_tol_deg"] == 0.7
    bore = features["bore"]
    assert bore["dia"] == pytest.approx([_in(0.3760), _in(0.3765)])
    assert bore["process"] == "ream" and bore["thru"] is True
    notch = features["notch"]
    assert notch["width_max"] == pytest.approx(_in(0.016))
    assert notch["depth"] == pytest.approx([_in(0.11), _in(0.13)])
