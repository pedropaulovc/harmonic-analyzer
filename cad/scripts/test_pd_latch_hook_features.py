"""Feature-export declarations of the latch hook (MHA-PD-14).

``draw_pd_latch_hook`` declares, in the part frame (origin at the ear's outer
face, the base's underside and its low-Y edge), the strip blank, the ear's
bend, the arm's roll and tab, the far face where the pin crosses the strip,
the screw holes, the pin hole, the root relief, the full round, the arm's
front edges and the taper. These tests build each face from the part's own
constants, prove exactly one declared feature owns it (and none owns the
faces no declaration names), and hold every band to the printed one.
"""

from __future__ import annotations

import math

import pytest

import export_features
import pd_latch_hook_geometry as geom
import pd_latch_hook_spec as spec
from _gtol_face import SURFACE_CYLINDER, SURFACE_PLANE, FaceGeometry

STEM = "pd_latch_hook"
IN = 25.4
_X, _MINUS_X = (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)
_Y, _MINUS_Y = (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)
_Z, _MINUS_Z = (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)
_U = (geom.ARM_U[0], geom.ARM_U[1], 0.0)
_MINUS_U = (-geom.ARM_U[0], -geom.ARM_U[1], 0.0)
_T = geom.SHEET_T
_FRONT_Z = geom.EAR_HEIGHT - geom.ARM_W
_LOW_Z = geom.EAR_HEIGHT - geom.LOW_W


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, SURFACE_PLANE, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float,
    axis: tuple[float, float, float],
    box_mm: tuple[float, float, float, float, float, float],
) -> FaceGeometry:
    return FaceGeometry(
        None,
        SURFACE_CYLINDER,
        (0.0, 0.0, 0.0, *axis, dia_mm / 2000),
        None,
        tuple(value / 1000 for value in box_mm),
    )


def _taper() -> FaceGeometry:
    dy = geom.TAPER_L[1] - geom.TAPER_L[0]
    dz = _LOW_Z - _FRONT_Z
    run = math.hypot(dy, dz)
    normal = (0.0, -dz / run, dy / run)
    return _plane(normal, normal[1] * geom.TAPER_L[0] + normal[2] * _FRONT_Z)


def _on_u(point: tuple[float, float], normal: tuple[float, float, float]) -> float:
    return point[0] * normal[0] + point[1] * normal[1]


_FAR = spec.FAR_FACE_POINT
_ARM_BAND = (geom.ARM_Z0, geom.ARM_Z1)
_FACES: dict[str, FaceGeometry] = {
    "strip": _plane(_Z, _T),
    "base_underside": _plane(_MINUS_Z, 0.0),
    "ear_face": _plane(_X, 0.0),
    "low_edge": _plane(_MINUS_Y, 0.0),
    "base_end": _plane(_MINUS_X, geom.BASE_LENGTH),
    "side_edge": _plane(_Y, geom.WIDTH),
    "ear_top": _plane(_Z, geom.EAR_HEIGHT),
    "ear_bend inside": _cylinder(
        2 * geom.INSIDE_BEND_R, _Y, (-2.08, 0.0, _T, -_T, geom.WIDTH, 2.08)
    ),
    "ear_bend outside": _cylinder(
        2 * geom.OUTSIDE_BEND_R, _MINUS_Y, (-2.08, 0.0, 0.0, 0.0, geom.WIDTH, 2.08)
    ),
    "roll inside": _cylinder(
        2 * geom.INNER_ROLL_R,
        _MINUS_Z,
        (-13.3, -59.8, _ARM_BAND[0], -_T, -17.0, _ARM_BAND[1]),
    ),
    "roll outside": _cylinder(
        2 * geom.OUTER_ROLL_R,
        _MINUS_Z,
        (-12.6, -60.3, _ARM_BAND[0], 0.0, -17.0, _ARM_BAND[1]),
    ),
    "tab inside": _cylinder(
        2 * geom.OUTER_TAB_R,
        _MINUS_Z,
        (-28.7, -88.5, _ARM_BAND[0], -26.8, -82.7, _ARM_BAND[1]),
    ),
    "tab outside": _cylinder(
        2 * geom.INNER_TAB_R,
        _MINUS_Z,
        (-29.5, -88.5, _ARM_BAND[0], -27.6, -82.5, _ARM_BAND[1]),
    ),
    "far_face": _plane(_U, _on_u(_FAR, _U)),
    "screw_holes far": _cylinder(
        geom.SCREW_HOLE_DIA, _MINUS_Z, (-14.26, 2.41, 0.0, -11.01, 5.66, _T)
    ),
    "screw_holes near": _cylinder(
        geom.SCREW_HOLE_DIA, _MINUS_Z, (-7.26, 2.41, 0.0, -4.01, 5.66, _T)
    ),
    "pin_hole": _cylinder(
        geom.PIN_HOLE_DIA, _MINUS_U, (-20.6, -71.7, 8.14, -18.2, -68.5, 11.39)
    ),
    "root_relief": _cylinder(2 * geom.ROOT_R, _X, (-_T, -2.03, 3.56, 0.0, 0.0, 5.59)),
    "tip_round": _cylinder(
        2 * geom.ROUND_R, _X, (-29.5, -88.5, _ARM_BAND[0], -26.8, -82.5, _ARM_BAND[1])
    ),
    "arm_front": _plane(_MINUS_Z, -_FRONT_Z),
    "arm_low_front": _plane(_MINUS_Z, -_LOW_Z),
    "taper": _taper(),
}
# Faces the sheet prints nothing on: the ear's and the vertical's inside face,
# the straight's near face.
_UNOWNED: dict[str, FaceGeometry] = {
    "ear inside face": _plane(_MINUS_X, _T),
    "straight near face": _plane(_MINUS_U, _on_u(_FAR, _MINUS_U) + _T),
}


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_each_face_has_exactly_one_owner() -> None:
    assert STEM in export_features.DECLARED_PARTS
    selectors = export_features.feature_selectors(STEM, None)
    assert set(selectors) == {name.split(" ")[0] for name in _FACES}
    for name, face in {**_FACES, **_UNOWNED}.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(spec_.matches(face) for spec_ in specs)
        ]
        assert owners == ([name.split(" ")[0]] if name in _FACES else []), name


def _inch(values: list[float], places: int = 3) -> list[float]:
    return [round(value / IN, places) for value in values]


# Every printed band, in inches: the title block's .XX ±.010 and .XXX
# ±.005 rows, DRILLED HOLES +.004/0, the formed arm's ±.020 on its printed
# .XX value and the angular row's ±1 deg.
_PRINTED = {
    ("strip", "width"): [1.19, 1.21],
    ("strip", "thickness"): [0.030, 0.034],
    ("base_end", "length"): [0.65, 0.67],
    ("side_edge", "width"): [0.31, 0.33],
    ("ear_top", "height"): [0.60, 0.62],
    ("ear_bend", "radius"): [0.04, 0.06],
    ("roll", "radius"): [3.11, 3.15],
    ("roll", "start"): [0.65, 0.69],
    ("tab", "radius"): [0.36, 0.40],
    ("tab", "end_x"): [1.11, 1.15],
    ("far_face", "x"): [0.73, 0.77],
    ("far_face", "y"): [2.75, 2.79],
    ("screw_holes", "dia"): [0.128, 0.132],
    ("screw_holes", "x_near"): [0.217, 0.227],
    ("screw_holes", "x_far"): [0.493, 0.503],
    ("screw_holes", "y"): [0.154, 0.164],
    ("pin_hole", "dia"): [0.128, 0.132],
    ("root_relief", "radius"): [0.07, 0.09],
    ("tip_round", "centre_station"): [3.52, 3.54],
    ("arm_front", "width"): [0.38, 0.40],
    ("arm_low_front", "width"): [0.44, 0.46],
    ("taper", "start"): [0.75, 0.77],
    ("taper", "end"): [1.14, 1.16],
}


@pytest.mark.parametrize(("feature", "key"), sorted(_PRINTED))
def test_bands_are_the_printed_ones(feature: str, key: str) -> None:
    value = _features()[feature]
    assert _inch(value[key]) == pytest.approx(_PRINTED[(feature, key)])
    nominal = value[f"{key}_nominal"]
    assert value[key][0] <= nominal <= value[key][1]


def test_the_formed_bands_are_the_spec_band_about_the_model() -> None:
    features = _features()
    formed = {
        "RollR": ("roll", "radius"),
        "RollStart": ("roll", "start"),
        "TabR": ("tab", "radius"),
        "TabEndX": ("tab", "end_x"),
        "FaceX": ("far_face", "x"),
        "FaceY": ("far_face", "y"),
    }
    for name, (feature, key) in formed.items():
        low, high = features[feature][key]
        model = spec.FORMED_VALUES[name]
        assert features[feature][f"{key}_nominal"] == pytest.approx(model)
        assert max(model - low, high - model) <= spec.FORMED_BAND + 1e-9, name


def test_the_bends_and_the_blank() -> None:
    features = _features()
    assert features["ear_bend"]["angle"] == [
        90.0 - spec.BEND_TOL_DEG,
        90.0 + spec.BEND_TOL_DEG,
    ]
    assert features["roll"]["angle"] == pytest.approx(geom.ROLL_TURN_DEG)
    assert features["tab"]["angle"] == pytest.approx(geom.TAB_TURN_DEG)
    strip = features["strip"]
    assert strip["section"] == "strip"
    assert strip["developed_length"] == pytest.approx(geom.WIDTH + geom.DEV_TIP)
    assert strip["k_factor"] == geom.K_BEND
    assert features["far_face"]["straight_length"] == pytest.approx(geom.STRAIGHT_LEN)
    assert features["tip_round"]["radius"] == pytest.approx(geom.ROUND_R)
    assert features["tip_round"]["overall_height"] == pytest.approx(spec.OVERALL_HEIGHT)


def test_the_holes_and_notes_are_the_sheet_text() -> None:
    features = _features()
    screws = features["screw_holes"]
    assert screws["count"] == 2
    assert screws["at"] == pytest.approx([geom.SCREW_HOLE_X[1], geom.SCREW_HOLE_Y, 0.0])
    assert (screws["callout"], screws["mate"], screws["wall"]) == (
        spec.SCREW_HOLE_CALLOUT,
        spec.SCREW_HOLE_MATE,
        spec.SCREW_HOLE_WALL_TEXT,
    )
    lines = spec.DRAWING_NOTES.split("\n")
    assert features["strip"]["radii_note"] == lines[0].removeprefix("1. ")
    pin = features["pin_hole"]
    assert pin["note"] == " ".join(line.strip() for line in lines[1:]).removeprefix(
        "2. "
    )
    assert pin["callout"] == spec.PIN_HOLE_CALLOUT
    assert features["strip"]["material"] == spec.MATERIAL_TITLE
