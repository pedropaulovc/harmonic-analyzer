"""Feature-export declarations of the pinion return leaf spring (MHA-DT-24).

``draw_dt_pinion_spring`` declares the faces it prints in the part frame
(``dt_pinion_spring_geometry``). These tests build each face from the part's
own constants, prove exactly one declared feature owns it, hold every band to
the one the sheet prints, and hold the formed (FREE) bend angles to the
FreeForm profile the print locates the crest on.
"""

from __future__ import annotations

import math

import pytest

import dt_pinion_spring_geometry as geom
import export_features
from _gtol_face import SURFACE_CYLINDER, SURFACE_PLANE, FaceGeometry

STEM = "dt_pinion_spring"
IN = 25.4
_X, _MINUS_X = (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)
_Y, _MINUS_Y = (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)
_Z, _MINUS_Z = (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, SURFACE_PLANE, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, box_mm: tuple[float, float, float, float, float, float]
) -> FaceGeometry:
    return FaceGeometry(
        None,
        SURFACE_CYLINDER,
        (0.0, 0.0, 0.0, *_Z, dia_mm / 2000),
        None,
        tuple(value / 1000 for value in box_mm),
    )


def _arc_box(
    centre: tuple[float, float],
    radius: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float, float, float, float, float]:
    """The box of the arc of ``radius`` about ``centre`` swept the short way
    between the directions of its inside-surface ends ``start`` and ``end``."""
    a0 = math.atan2(start[1] - centre[1], start[0] - centre[0])
    a1 = math.atan2(end[1] - centre[1], end[0] - centre[0])
    sweep = (a1 - a0 + math.pi) % (2.0 * math.pi) - math.pi
    angles = [a0 + sweep * i / 64 for i in range(65)]
    xs = [centre[0] + radius * math.cos(a) for a in angles]
    ys = [centre[1] + radius * math.sin(a) for a in angles]
    half = geom.WIDTH / 2.0
    return (min(xs), min(ys), -half, max(xs), max(ys), half)


_BEND_C = (geom.BEND_CX, geom.BEND_CY)
_OUTER = geom.R_BEND + geom.THICK
_FLICK = tuple((geom.FLAT_TIP[i] - geom.KINK_EXIT[i]) / geom.FLAT_LEN for i in (0, 1))
_FACES: dict[str, FaceGeometry] = {
    "strip underside": _plane(_MINUS_Y, 0.0),
    "strip top": _plane(_Y, geom.THICK),
    "aft_edge": _plane(_MINUS_Z, geom.WIDTH / 2.0),
    "strip_edge": _plane(_Z, geom.WIDTH / 2.0),
    "pad_edge": _plane(_Z, geom.PAD_Z + geom.PAD_WIDTH / 2.0),
    "free_end": _plane(_X, geom.FOOT_END[0]),
    "pad_wing": _plane(_MINUS_X, -(geom.HOLE_X - geom.PAD_WING_FROM_HOLE)),
    "pad_relief": _cylinder(
        2.0 * geom.PAD_RELIEF_R, (8.056, 0.0, 3.175, 8.31, geom.THICK, 3.429)
    ),
    "hole": _cylinder(
        geom.HOLE_DIA,
        (
            geom.HOLE_X - geom.HOLE_DIA / 2.0,
            0.0,
            geom.PAD_Z - geom.HOLE_DIA / 2.0,
            geom.HOLE_X + geom.HOLE_DIA / 2.0,
            geom.THICK,
            geom.PAD_Z + geom.HOLE_DIA / 2.0,
        ),
    ),
    # Each arc's own span: the bend's and the kink's surfaces share both
    # diameters, so the box decides.
    "bend inside": _cylinder(
        2.0 * geom.R_BEND, _arc_box(_BEND_C, geom.R_BEND, geom.FOOT_TAN, geom.BEND_EXIT)
    ),
    "bend outside": _cylinder(
        2.0 * _OUTER, _arc_box(_BEND_C, _OUTER, geom.FOOT_TAN, geom.BEND_EXIT)
    ),
    "kink inside": _cylinder(
        2.0 * geom.R_KINK,
        _arc_box(geom.KINK_C, geom.R_KINK, geom.KINK_START, geom.KINK_EXIT),
    ),
    "kink outside": _cylinder(
        2.0 * (geom.R_KINK + geom.THICK),
        _arc_box(
            geom.KINK_C, geom.R_KINK + geom.THICK, geom.KINK_START, geom.KINK_EXIT
        ),
    ),
    "flat": _plane(
        (*_FLICK, 0.0), geom.FLAT_TIP[0] * _FLICK[0] + geom.FLAT_TIP[1] * _FLICK[1]
    ),
}


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_each_face_has_exactly_one_owner() -> None:
    assert STEM in export_features.DECLARED_PARTS
    selectors = export_features.feature_selectors(STEM, None)
    assert set(selectors) == {name.split(" ")[0] for name in _FACES}
    for name, face in _FACES.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(spec.matches(face) for spec in specs)
        ]
        assert owners == [name.split(" ")[0]], name


def _inch(values: list[float], places: int = 4) -> list[float]:
    return [round(value / IN, places) for value in values]


def test_the_blank_is_the_rolled_strip_and_its_developed_mid_surface() -> None:
    strip = _features()["strip"]
    assert strip["kind"] == "blank"
    assert strip["section"] == "strip"
    assert round(strip["width"] / IN, 4) == 0.25
    # McMaster-Carr 2325K19: .015 +/-.00075 as bought.
    assert _inch(strip["thickness"], 5) == [0.01425, 0.01575]
    arcs = math.radians(90.0 - geom.BLADE_LEAN_DEG + geom.KINK_DEG)
    assert strip["developed_length"] == pytest.approx(
        geom.PATH_LEN + arcs * geom.THICK / 2.0
    )
    assert strip["note"].startswith("CUT BLANK ALONG ROLL LENGTH")


@pytest.mark.parametrize(
    ("feature", "field", "printed", "places"),
    [
        ("strip_edge", "width", [0.24, 0.26], 2),
        ("pad_edge", "width", [0.37, 0.39], 2),
        ("pad_wing", "length", [0.14, 0.16], 2),
        ("hole", "x", [0.17, 0.19], 2),
        ("hole", "z", [0.18, 0.20], 2),
        ("hole", "dia", [0.1285, 0.1325], 4),
        ("bend", "radius", [0.110, 0.150], 3),
        ("bend", "foot_len", [0.177, 0.217], 3),
        ("kink", "radius", [0.110, 0.150], 3),
        ("kink", "free_h", [0.502, 0.542], 3),
        ("kink", "free_v", [1.424, 1.464], 3),
        ("flat", "length", [0.07, 0.09], 2),
    ],
)
def test_bands_equal_the_printed_ones(
    feature: str, field: str, printed: list[float], places: int
) -> None:
    assert _inch(_features()[feature][field], places) == printed


def test_datums_chain_to_the_hole_and_the_blank_edges() -> None:
    features = _features()
    assert features["strip_edge"]["width_from"] == "aft_edge"
    assert features["pad_edge"]["width_from"] == "aft_edge"
    assert features["pad_wing"]["length_from"] == "hole"
    assert features["hole"]["x_from"] == "free_end"
    assert features["hole"]["z_from"] == "pad_edge"
    assert features["bend"]["foot_len_from"] == "hole"
    assert features["kink"]["free_h_from"] == "hole"
    assert features["kink"]["free_v_from"] == "strip"
    assert features["flat"]["length_from"] == "kink"
    assert features["hole"]["drill"] == "#30 DRILL"
    assert features["pad_wing"]["callout"] == "HOLE WEB .076 MIN"
    assert round(features["pad_relief"]["radius_max"] / IN, 3) == 0.010
    assert features["kink"]["callout"] == "FREE"


def _heading(start: tuple[float, float], end: tuple[float, float]) -> float:
    return math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))


def test_the_formed_angles_are_the_free_forms() -> None:
    """The foot runs west into the bend (heading 180); the FREE blade leaves
    it toward the FREE kink start, and the flat leaves the kink."""
    features = _features()
    free_blade = _heading(geom.FREE_BEND_EXIT, geom.FREE_KINK_START)
    free_flat = _heading(geom.FREE_KINK_EXIT, geom.FREE_FLAT_TIP)
    assert features["bend"]["angle"] == pytest.approx(180.0 - free_blade)
    assert features["bend"]["angle"] == pytest.approx(
        features["bend"]["installed_angle_deg"] - geom.PRESET_DEG
    )
    assert round(features["bend"]["angle"], 2) == 81.60
    assert features["kink"]["angle"] == pytest.approx(free_blade - free_flat)
    assert features["kink"]["included_angle_deg"] == [154.0, 156.0]
    assert features["kink"]["nominal_included_angle_deg"] == 155.0
