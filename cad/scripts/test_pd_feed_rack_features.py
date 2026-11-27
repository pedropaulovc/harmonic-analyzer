"""Feature-export declarations of the MHA-PD-26 feed rack.

The rack declares its faces in its own model frame (pd_feed_rack_spec: length
+X from the left cut end, the flat top at Y=0 with the teeth toward +Y, the
front face at Z=0). These tests build each face from the spec's constants,
prove exactly one declared feature owns it (and that the tooth flanks and
roots, which the sheet does not dimension, belong to none), and hold the
bands to the printed ones.
"""

from __future__ import annotations

import math

import pytest

import export_features
import pd_feed_rack_callouts as callouts
import pd_feed_rack_spec as spec
from _gtol_face import SURFACE_CONE, SURFACE_CYLINDER, SURFACE_PLANE, FaceGeometry

IN = 25.4
STEM = "pd_feed_rack"
_X, _MINUS_X = (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)
_Y, _MINUS_Y = (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)
_Z, _MINUS_Z = (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)
_FLANK = (math.cos(math.radians(spec.PA_DEG)), math.sin(math.radians(spec.PA_DEG)), 0.0)


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, SURFACE_PLANE, (*normal, *point), normal, ())


def _tap_box(x_mm: float, low_y: float, high_y: float) -> tuple[float, ...]:
    radius = spec.TAP_DRILL_DIA / 2.0
    box = (
        x_mm - radius,
        low_y,
        spec.TAP_Z - radius,
        x_mm + radius,
        high_y,
        spec.TAP_Z + radius,
    )
    return tuple(value / 1000 for value in box)


def _tap_bore(x_mm: float) -> FaceGeometry:
    return FaceGeometry(
        None,
        SURFACE_CYLINDER,
        (x_mm / 1000, 0.0, spec.TAP_Z / 1000, *_MINUS_Y, spec.TAP_DRILL_DIA / 2000),
        None,
        _tap_box(x_mm, 0.0, spec.TAP_DRILL_DEPTH),
    )


def _tap_point(x_mm: float) -> FaceGeometry:
    return FaceGeometry(
        None,
        SURFACE_CONE,
        (
            x_mm / 1000,
            spec.TAP_DRILL_DEPTH / 1000,
            spec.TAP_Z / 1000,
            *_Y,
            spec.TAP_DRILL_DIA / 2000,
            math.radians(spec.TAP_SPEC.drill_angle_deg / 2.0),
            *_X,
        ),
        None,
        _tap_box(x_mm, spec.TAP_DRILL_DEPTH, spec.TAP_DRILL_DEPTH + 0.36),
    )


_FACES: dict[str, FaceGeometry] = {
    "left_end": _plane(_MINUS_X, 0.0),
    "right_end": _plane(_X, spec.BAR_LENGTH),
    "flat_top": _plane(_MINUS_Y, 0.0),
    "teeth": _plane(_Y, spec.RACK_HEIGHT),
    "front_face": _plane(_MINUS_Z, 0.0),
    "back_face": _plane(_Z, spec.RACK_THICKNESS),
    **{f"tap_{index} bore": _tap_bore(x) for index, x in enumerate(spec.TAP_X, 1)},
    **{f"tap_{index} point": _tap_point(x) for index, x in enumerate(spec.TAP_X, 1)},
}
# Faces the sheet does not dimension: the tooth roots and one flank.
_UNOWNED = {
    "root": _plane(_Y, spec.ROOT_Y),
    "flank": _plane(_FLANK, 1.9432),
}


def _selectors() -> dict:
    return export_features.feature_selectors(STEM, None)


def test_each_face_has_exactly_one_owner() -> None:
    assert STEM in export_features.DECLARED_PARTS
    selectors = _selectors()
    assert set(selectors) == {name.split(" ")[0] for name in _FACES}
    for name, face in _FACES.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(face) for selector in specs)
        ]
        assert owners == [name.split(" ")[0]], name


@pytest.mark.parametrize("name", sorted(_UNOWNED))
def test_undimensioned_tooth_faces_have_no_owner(name: str) -> None:
    face = _UNOWNED[name]
    assert not any(
        selector.matches(face) for specs in _selectors().values() for selector in specs
    )


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def _inch(values: list[float], places: int = 4) -> list[float]:
    return [round(value / IN, places) for value in values]


def test_the_cut_length_prints_two_places_from_the_left_end() -> None:
    right = _features()["right_end"]
    assert _inch(right["length"], 2) == [10.61, 10.63]
    assert right["length_nominal"] == pytest.approx(spec.BAR_LENGTH)
    assert right["length_from"] == "left_end"


def test_the_section_and_teeth_are_the_purchased_strips_references() -> None:
    features = _features()
    assert _inch([features["teeth"]["height_ref"]]) == [0.1875]
    assert _inch([features["back_face"]["depth_ref"]]) == [0.1875]
    assert features["teeth"]["height_ref_from"] == "flat_top"
    assert features["back_face"]["depth_ref_from"] == "front_face"
    assert features["teeth"]["gear_data"] == spec.GEAR_DATA
    assert features["teeth"]["pitch_ref"] == pytest.approx(math.pi / spec.DP * IN)


def test_the_taps_print_their_callout_and_stations() -> None:
    features = _features()
    taps = [features[f"tap_{index}"] for index in range(1, 5)]
    first = taps[0]
    # TapStart: 2.06 with its own ±.05 window about the exact tooth centre.
    assert first["station_from"] == "left_end"
    assert round(first["station_nominal"] / IN, 2) == 2.06
    assert first["station"][1] - first["station_nominal"] == pytest.approx(0.05 * IN)
    assert first["station_nominal"] - first["station"][0] == pytest.approx(0.05 * IN)
    # TapStation2-4: 2.160, 4.320, 6.480 ±.005 from the first tap.
    for tap, printed in zip(taps[1:], (2.160, 4.320, 6.480), strict=True):
        assert tap["station_from"] == "tap_1"
        assert tap["station_axis"] == "x"
        assert _inch(tap["station"], 3) == [
            round(printed - 0.005, 3),
            round(printed + 0.005, 3),
        ]
    for tap, x in zip(taps, spec.TAP_X, strict=True):
        assert tap["at"] == pytest.approx([x, 0.0, spec.TAP_Z])
        assert tap["axis"] == [0.0, 1.0, 0.0]
        assert tap["thread"] == "#0-80 UNF-2B"
        assert _inch(tap["dia"], 3) == [0.047, 0.051]
        assert _inch(tap["drill_depth"], 3) == [0.124, 0.134]
        assert _inch(tap["thread_depth"], 3) == [0.105, 0.115]
        assert _inch(tap["inset"], 3) == [0.089, 0.099]
        assert tap["inset_from"] == "front_face"
        assert _inch([tap["tooth_offset_max"]], 3) == [0.005]
        assert tap["callout"] == callouts.TAP_CALLOUT_BELOW
        assert tap["walls"] == spec.TAP_FACE_WALL_STATEMENT


def test_the_taps_stand_22_pitches_apart_on_tooth_centres() -> None:
    taps = [_features()[f"tap_{index}"] for index in range(1, 5)]
    for left, right in zip(taps, taps[1:]):
        assert right["at"][0] - left["at"][0] == pytest.approx(22 * spec.PITCH)
    for tap in taps:
        teeth = (tap["at"][0] - spec.TOOTH_CENTRE_PHASE_X) / spec.PITCH
        assert teeth == pytest.approx(round(teeth))
