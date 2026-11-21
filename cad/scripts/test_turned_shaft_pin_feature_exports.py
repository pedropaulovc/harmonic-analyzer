"""Feature-export declarations of the turned shafts and pins.

Each part's drawing declares its faces in its own model frame; these tests
build each face from the part's own constants and prove exactly one declared
feature owns it, and that the bands are the printed ones.
"""

from __future__ import annotations

import pytest

import _config
import dt_crank_pinion_pin_spec as crank_pin
import dt_pinion_cam_pin_geometry as cam_pin
import dt_pinion_handle_geometry as handle
import export_features
import mg_lever_thread_joint as lever
import pn_pen_adjust_screw_spec as screw
from _gtol_face import (
    SURFACE_CYLINDER,
    SURFACE_PLANE,
    SURFACE_SPHERE,
    SURFACE_TORUS,
    FaceGeometry,
)

IN = 25.4
_X, _MINUS_X = (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)
_Y, _MINUS_Y = (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)
_Z, _MINUS_Z = (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, SURFACE_PLANE, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float,
    axis: tuple[float, float, float],
    span: tuple[float, float] = (-1e3, 1e3),
) -> FaceGeometry:
    """A cylinder on ``axis`` whose box runs ``span`` mm along it."""
    low = [-1.0, -1.0, -1.0]
    high = [1.0, 1.0, 1.0]
    index = [abs(value) for value in axis].index(1.0)
    low[index], high[index] = span[0] / 1000, span[1] / 1000
    return FaceGeometry(
        None,
        SURFACE_CYLINDER,
        (0.0, 0.0, 0.0, *axis, dia_mm / 2000),
        None,
        (*low, *high),
    )


def _sphere(dia_mm: float, center_mm: tuple[float, float, float]) -> FaceGeometry:
    center = tuple(value / 1000 for value in center_mm)
    return FaceGeometry(None, SURFACE_SPHERE, (*center, dia_mm / 2000), None, ())


def _torus(
    major_mm: float, minor_mm: float, center_mm: tuple[float, float, float]
) -> FaceGeometry:
    center = tuple(value / 1000 for value in center_mm)
    return FaceGeometry(
        None,
        SURFACE_TORUS,
        (*center, 0.0, 1.0, 0.0, major_mm / 1000, minor_mm / 1000),
        None,
        (),
    )


_CAM_APEX = cam_pin.PIN_LEN + cam_pin.CAP_SAG
_FACES: dict[str, dict[str, FaceGeometry]] = {
    "dt_crank_pinion_pin": {
        "datum_end": _plane(_MINUS_Z, 0.0),
        "far_end": _plane(_Z, crank_pin.PIN_LEN),
        "outer": _cylinder(crank_pin.PIN_DIA, _Z),
    },
    "dt_pinion_handle": {
        "datum_end": _plane(_MINUS_Y, handle.ROD_DOWN),
        "far_end": _plane(_Y, handle.ROD_UP),
        "outer": _cylinder(handle.ROD_DIA, _Y),
    },
    "dt_pinion_cam_pin": {
        "datum_end": _plane(_MINUS_Z, 0.0),
        "far_end": _sphere(
            2 * cam_pin.CAP_RADIUS, (0.0, 0.0, _CAM_APEX - cam_pin.CAP_RADIUS)
        ),
        "outer": _cylinder(cam_pin.PIN_DIA, _Z),
    },
    "mg_magnifying_lever": {
        "datum_end": _sphere(lever.ROD_DIA, (lever.ROD_DIA / 2, 0.0, 0.0)),
        "far_end": _plane(_X, lever.ROD_LENGTH),
        "outer": _cylinder(lever.ROD_DIA, _X, (lever.ROD_DIA / 2, lever.ROD_LENGTH)),
    },
    "pn_pen_adjust_screw": {
        "datum_end": _plane(_MINUS_Y, 0.0),
        "far_end": _plane(_Y, screw.OVERALL_LENGTH),
        "shoulder": _plane(_MINUS_Y, -screw.SHANK_LENGTH),
        "outer": _cylinder(screw.HEAD_DIA, _Y),
        "step": _cylinder(screw.THREAD_MAJOR, _Y, (0.0, screw.FULL_THREAD_LENGTH)),
        "step plain": _cylinder(
            screw.THREAD_MAJOR,
            _Y,
            (screw.FULL_THREAD_LENGTH, screw.SHANK_LENGTH - screw.SHOULDER_FILLET_R),
        ),
        "fillet_shoulder": _torus(
            screw.THREAD_MAJOR / 2 + screw.SHOULDER_FILLET_R,
            screw.SHOULDER_FILLET_R,
            (0.0, screw.SHANK_LENGTH - screw.SHOULDER_FILLET_R, 0.0),
        ),
        "cross_hole": _cylinder(screw.EYE_DIA, _X),
    },
}


@pytest.mark.parametrize("stem", sorted(_FACES))
def test_each_face_has_exactly_one_owner(stem: str) -> None:
    assert stem in export_features.SUPPORTED_PARTS
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


@pytest.mark.parametrize("stem", sorted(_FACES))
def test_every_end_and_diameter_lies_on_the_datum_ends_axis(stem: str) -> None:
    features = export_features.requirement_manifest(stem)["features"]
    datum = features["datum_end"]
    axis = datum["plane"]["axis"]
    for name, feature in features.items():
        if "plane" in feature:
            assert feature["plane"]["axis"] == axis, name
        if feature["kind"] == "diameter":
            assert [abs(value) for value in feature["axis"]] == [
                float(axis == letter) for letter in "xyz"
            ]
            assert feature["at"] == [0.0, 0.0, 0.0]
            assert feature["span"][0] < feature["span"][1]
    assert features["far_end"]["length_from"] == "datum_end"


def _inch(values: list[float]) -> list[float]:
    return [round(value / IN, 4) for value in values]


def test_printed_bands_are_the_sheets() -> None:
    manifest = export_features.requirement_manifest
    pin = manifest("dt_crank_pinion_pin")["features"]
    assert _inch(pin["far_end"]["length"]) == [0.55, 0.57]
    assert pin["outer"]["dia_ref"] == pytest.approx(IN / 8)
    assert pin["outer"]["stock"] == "STOCK, AS SUPPLIED"

    rod = manifest("dt_pinion_handle")["features"]
    assert _inch(rod["far_end"]["length"]) == [2.55, 2.57]
    assert rod["outer"]["dia_ref"] == pytest.approx(IN / 4)

    cam = manifest("dt_pinion_cam_pin")["features"]
    assert _inch(cam["outer"]["dia"]) == [0.1558, 0.1568]
    assert _inch(cam["far_end"]["root_station"]) == [0.78, 0.80]
    assert _inch(cam["far_end"]["radius"]) == [0.11, 0.13]
    assert round(cam["far_end"]["length_ref"] / IN, 2) == 0.82

    arm = manifest("mg_magnifying_lever")["features"]
    assert _inch(arm["far_end"]["length"]) == [6.58, 6.60]
    assert _inch(arm["outer"]["thread_length"]) == [0.70, 0.72]
    assert _inch([arm["outer"]["thread_incomplete_max"]]) == [0.075]
    assert (arm["outer"]["thread"], arm["outer"]["thread_process"]) == (
        "1/4-20 UNC-2A",
        "single_point",
    )
    assert arm["datum_end"]["radius_ref"] == pytest.approx(IN / 8)

    stud = manifest("pn_pen_adjust_screw")["features"]
    assert _inch(stud["far_end"]["length"]) == [1.01, 1.03]
    assert _inch(stud["shoulder"]["station"]) == [0.31, 0.33]
    assert stud["shoulder"]["station_from"] == "far_end"
    assert _inch(stud["outer"]["dia"]) == [0.23, 0.25]
    assert _inch(stud["step"]["dia"]) == [0.0563, 0.0595]
    assert _inch(stud["step"]["thread_length"]) == [0.57, 0.59]
    assert (stud["step"]["thread"], stud["step"]["thread_process"]) == (
        "#0-80 UNF",
        "die",
    )
    assert _inch(stud["fillet_shoulder"]["radius"]) == [0.01, 0.03]
    assert _inch(stud["cross_hole"]["dia"]) == [0.055, 0.059]
    assert _inch(stud["cross_hole"]["station"]) == [0.15, 0.17]


def test_manifest_notes_are_the_printed_notes() -> None:
    notes = {
        stem: export_features.requirement_manifest(stem)["notes"]["manufacturing"]
        for stem in _FACES
    }
    assert notes.pop("dt_pinion_handle") == ["USE COLD-FINISHED BAR AS RECEIVED."]
    assert all(value == [] for value in notes.values())


def test_thread_processes_are_the_registry_rows() -> None:
    parts = _config._doc("parts")["parts"]
    stud = export_features.requirement_manifest("pn_pen_adjust_screw")["features"]
    assert stud["step"]["thread_process"] == "die"
    assert "die-cut" in parts["pn-pen-adjust-screw"]["process"]


def test_the_screw_blank_is_accepted_at_the_2a_major() -> None:
    step = export_features.requirement_manifest("pn_pen_adjust_screw")["features"][
        "step"
    ]
    # The (Ø.060) printed on the plain shank is the basic major: a reference,
    # above the class 2A band the whole turned blank is accepted to.
    assert step["dia_nominal"] == pytest.approx(screw.THREAD_MAJOR)
    assert round(screw.THREAD_MAJOR / IN, 3) == 0.060
    assert step["dia"][1] < screw.THREAD_MAJOR
