"""Feature-export declarations of the bench-made parts (cnc/bench-b).

The pinion lever pin (MHA-DT-30), the keyed arbor's key (MHA-DT-03-TL-06),
the cone tip gears' phasing comb (MHA-DT-03-TL-02) and the gooseneck
(MHA-SM-01) each declare their faces in their own model frame. These tests
build each face from the part's own constants, prove exactly one declared
feature owns it, and hold the bands to the printed ones.
"""

from __future__ import annotations

import math

import pytest

import dt_cone_gear_tl_arbor_key_spec as key
import dt_cone_gear_tl_phasing_comb_spec as comb
import dt_pinion_lever_pin_geometry as lever_pin
import export_features
import sm_gooseneck_geom as goose
from _gtol_face import SURFACE_CYLINDER, SURFACE_PLANE, SURFACE_TORUS, FaceGeometry

IN = 25.4
_X, _MINUS_X = (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)
_Y, _MINUS_Y = (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)
_Z, _MINUS_Z = (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)


def _plane(
    normal: tuple[float, float, float],
    offset_mm: float,
    box_mm: tuple[float, ...] = (),
) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, SURFACE_PLANE, (*normal, *point), normal, box)


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


def _torus(
    major_mm: float, minor_mm: float, center_mm: tuple[float, float, float]
) -> FaceGeometry:
    center = tuple(value / 1000 for value in center_mm)
    return FaceGeometry(
        None,
        SURFACE_TORUS,
        (*center, *_Z, major_mm / 1000, minor_mm / 1000),
        None,
        (),
    )


_PIN_HALF = lever_pin.PIN_LEN / 2.0
_PIN_R = lever_pin.PIN_DIA / 2.0
_KEY_HALF = key.SIZE / 2.0
_FAR = comb.GRIP_SPAN + comb.SPRING_WIDTH
_TUBE_R = goose.TUBE_DIA / 2.0
_BORE_R = goose.TUBE_BORE_DIA / 2.0
_BEND_CENTER = (-goose.BEND_R, goose.LEG_TOP, 0.0)
_LEG_BOX = (-_TUBE_R, goose.LEG_BOTTOM, -_TUBE_R, _TUBE_R, goose.LEG_TOP, _TUBE_R)
_ARM_BOX = (
    goose.TUBE_END_X,
    goose.ARM_Y - _TUBE_R,
    -_TUBE_R,
    -goose.BEND_R,
    goose.ARM_Y + _TUBE_R,
    _TUBE_R,
)


def _comb_blades() -> dict[str, FaceGeometry]:
    faces = {}
    for teeth in comb.BONDED_TEETH:
        name = f"blade_{comb.gear_tag(teeth).lower()}"
        faces[f"{name} riser"] = _plane(_MINUS_X, -comb.BLADE_START_MM[teeth])
        faces[f"{name} level"] = _plane(_MINUS_Y, comb.BLADE_DEPTH_MM[teeth])
    faces["blade_t006 return"] = _plane(_X, comb.LEVEL_END_MM)
    return faces


_FACES: dict[str, dict[str, FaceGeometry]] = {
    "dt_pinion_lever_pin": {
        "datum_end": _plane(_MINUS_X, _PIN_HALF),
        "far_end": _plane(_X, _PIN_HALF),
        "outer": _cylinder(
            lever_pin.PIN_DIA,
            _X,
            (-_PIN_HALF, -_PIN_R, -_PIN_R, _PIN_HALF, _PIN_R, _PIN_R),
        ),
    },
    "dt_cone_gear_tl_arbor_key": {
        "datum_end": _plane(_MINUS_Z, 0.0),
        "far_end": _plane(_Z, key.LENGTH),
        "section bottom": _plane(_MINUS_X, 0.0),
        "section top": _plane(_X, key.SIZE),
        "section side": _plane(_MINUS_Y, _KEY_HALF),
        "section other side": _plane(_Y, _KEY_HALF),
    },
    "dt_cone_gear_tl_phasing_comb": {
        "south_end": _plane(_MINUS_X, 0.0),
        "north_end": _plane(_X, comb.SHEET_LENGTH),
        "seat": _plane(_MINUS_Y, 0.0),
        "spring_inner": _plane(_Y, -comb.GRIP_SPAN),
        "far_edge": _plane(_MINUS_Y, _FAR),
        "back": _plane(_Y, comb.ARM_WIDTH),
        "slot_end": _cylinder(
            comb.GRIP_SPAN,
            _Z,
            (
                comb.SLOT_LENGTH,
                -comb.GRIP_SPAN,
                0.0,
                comb.SLOT_END_MM,
                0.0,
                comb.SHEET_THICK,
            ),
        ),
        **_comb_blades(),
        "underside": _plane(_MINUS_Z, 0.0),
        "top": _plane(_Z, comb.SHEET_THICK),
    },
    "sm_gooseneck": {
        "foot": _plane(_MINUS_Y, -goose.LEG_BOTTOM),
        "arm_end": _plane(_MINUS_X, -goose.TUBE_END_X),
        "leg": _cylinder(goose.TUBE_DIA, _Y, _LEG_BOX),
        "arm": _cylinder(goose.TUBE_DIA, _X, _ARM_BOX),
        "bend": _torus(goose.BEND_R, _TUBE_R, _BEND_CENTER),
        "blank leg bore": _cylinder(goose.TUBE_BORE_DIA, _Y, _LEG_BOX),
        "blank arm bore": _cylinder(goose.TUBE_BORE_DIA, _X, _ARM_BOX),
        "blank bend bore": _torus(goose.BEND_R, _BORE_R, _BEND_CENTER),
    },
}


@pytest.mark.parametrize("stem", sorted(_FACES))
def test_each_face_has_exactly_one_owner(stem: str) -> None:
    assert stem in export_features.DECLARED_PARTS
    selectors = export_features.feature_selectors(stem, None)
    expected = _FACES[stem]
    assert set(selectors) == {name.split(" ")[0] for name in expected}
    for name, face in expected.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(spec.matches(face) for spec in specs)
        ]
        assert owners == [name.split(" ")[0]], name


def _inch(values: list[float], places: int = 4) -> list[float]:
    return [round(value / IN, places) for value in values]


def test_the_lever_pin_prints_its_stock_and_cut_length() -> None:
    pin = export_features.requirement_manifest("dt_pinion_lever_pin")["features"]
    assert _inch(pin["far_end"]["length"]) == [0.62, 0.64]
    assert _inch(pin["outer"]["dia"]) == [0.0622, 0.0628]
    assert pin["far_end"]["length_from"] == "datum_end"


def test_the_key_prints_its_cut_length_on_undersized_stock() -> None:
    features = export_features.requirement_manifest("dt_cone_gear_tl_arbor_key")[
        "features"
    ]
    assert _inch(features["far_end"]["length"]) == [0.14, 0.16]
    assert _inch(features["section"]["stock"]) == [0.0605, 0.0625]
    assert features["section"]["size_ref"] == pytest.approx(IN / 16)


def test_the_comb_prints_its_steps_depths_and_grip() -> None:
    features = export_features.requirement_manifest("dt_cone_gear_tl_phasing_comb")[
        "features"
    ]
    assert _inch(features["north_end"]["length"], 2) == [3.64, 3.66]
    assert _inch(features["back"]["height"], 2) == [0.89, 0.91]
    assert _inch(features["spring_inner"]["grip_span"], 3) == [0.552, 0.562]
    assert _inch(features["slot_end"]["slot_length"], 2) == [3.11, 3.13]
    depths = {
        name: _inch(feature["depth"], 3)
        for name, feature in features.items()
        if name.startswith("blade_")
    }
    assert depths == {
        "blade_t024": [0.040, 0.050],
        "blade_t018": [0.102, 0.112],
        "blade_t012": [0.164, 0.174],
        "blade_t006": [0.223, 0.233],
    }
    starts = [
        round(features[f"blade_t{teeth:03d}"]["start_nominal"] / IN, 2)
        for teeth in (24, 18, 12, 6)
    ]
    assert starts == [0.37, 0.67, 0.96, 1.26]
    assert round(features["blade_t006"]["level_end_nominal"] / IN, 2) == 1.46
    assert _inch(features["top"]["stock_thickness"], 3) == [0.018, 0.022]


def test_the_gooseneck_prints_where_its_ends_finish() -> None:
    features = export_features.requirement_manifest("sm_gooseneck")["features"]
    assert _inch(features["arm"]["height"], 2) == [19.55, 19.75]
    assert round(features["arm_end"]["reach_nominal"] / IN, 2) == 3.72
    assert features["bend"]["angle"] == [89.0, 91.0]
    assert features["bend"]["centreline_radius"] == pytest.approx(3.0 * IN)
    blank = features["blank"]
    assert blank["section"] == "tube"
    # The developed length runs the tube's centreline: leg, quarter bend, arm.
    assert blank["developed_length"] == pytest.approx(
        goose.LEG_LENGTH + math.pi / 2.0 * goose.BEND_R + goose.TUBE_STRAIGHT
    )
