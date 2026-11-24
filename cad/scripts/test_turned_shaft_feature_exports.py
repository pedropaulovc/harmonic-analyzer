"""Feature-export declarations of the turned shafts and pins.

Each part's drawing declares its turned faces (domed ends, flats, cross holes,
the thread blank and its relief) in its own model frame; these tests build
each face from the part's own constants and prove exactly one declared
feature owns it, and that the bands are the printed ones.
"""

from __future__ import annotations

import pytest

import ch_fulcrum_shaft_spec as fulcrum
import ch_pivot_shaft_spec as rocker_pivot
import rocker_bank_layout as rocker_bank
import cylinder_bank_layout as bank
import dt_cylinder_gear_shaft_spec as arbor
import dt_pinion_lever_geometry as lever
import dt_pinion_lift_rod_spec as lift
import dt_pinion_pivot_shaft_spec as pivot
import export_features
import mg_wheel_axle_spec as axle
from _gtol_face import SURFACE_CYLINDER, SURFACE_PLANE, SURFACE_SPHERE, FaceGeometry

IN = 25.4
_X = (1.0, 0.0, 0.0)
_Y = (0.0, 1.0, 0.0)
_Z = (0.0, 0.0, 1.0)


def _box(
    axis: tuple[float, float, float], low_mm: float, high_mm: float
) -> tuple[float, ...]:
    """A face's bounding box running low..high along ``axis``, wide across it."""
    low = tuple(low_mm / 1000 if a else -1.0 for a in axis)
    high = tuple(high_mm / 1000 if a else 1.0 for a in axis)
    return (*low, *high)


def _plane(
    normal: tuple[float, float, float], offset_mm: float, box: tuple[float, ...] = ()
) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, SURFACE_PLANE, (*normal, *point), normal, box)


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box: tuple[float, ...] = ()
) -> FaceGeometry:
    return FaceGeometry(
        None, SURFACE_CYLINDER, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box
    )


def _sphere(dia_mm: float, centre_mm: tuple[float, float, float]) -> FaceGeometry:
    centre = tuple(value / 1000 for value in centre_mm)
    return FaceGeometry(None, SURFACE_SPHERE, (*centre, dia_mm / 2000), None, ())


def _cap_radius(radius: float, height: float) -> float:
    """The sphere of a cap ``height`` high on a bar of ``radius``."""
    return (radius**2 + height**2) / (2.0 * height)


_ARBOR_R = _cap_radius(arbor.SHAFT_RADIUS, bank.ARBOR_DOME_HEIGHT)
_FULCRUM_FLAT_Z = fulcrum.FLAT_PITCH / 2.0
_LIFT_FLAT_Z = {
    "flat_back": lift.ROD_LEN - lift.BACK_FLAT_EDGE_FROM_RIM - lift.BACK_FLAT_LEN / 2,
    "flat_front": lift.ROD_LEN
    - lift.FRONT_FLAT_EDGE_FROM_RIM
    - lift.FRONT_FLAT_LEN / 2,
}

_FACES: dict[str, dict[str, FaceGeometry]] = {
    "ch_fulcrum_shaft": {
        "datum_end": _sphere(fulcrum.SHAFT_DIA, (0.0, 0.0, -fulcrum.CYLINDER_HALF)),
        "far_end": _sphere(fulcrum.SHAFT_DIA, (0.0, 0.0, fulcrum.CYLINDER_HALF)),
        "outer": _cylinder(fulcrum.SHAFT_DIA, _Z),
        "flat_datum": _plane(
            _Y,
            fulcrum.FLAT_HEIGHT,
            _box(_Z, -_FULCRUM_FLAT_Z - 2, -_FULCRUM_FLAT_Z + 2),
        ),
        "flat_far": _plane(
            _Y, fulcrum.FLAT_HEIGHT, _box(_Z, _FULCRUM_FLAT_Z - 2, _FULCRUM_FLAT_Z + 2)
        ),
    },
    "ch_pivot_shaft": {
        "datum_end": _sphere(
            2 * rocker_pivot.DOME_SPHERE_RADIUS,
            (0.0, 0.0, rocker_pivot.DOME_HEIGHT - rocker_pivot.DOME_SPHERE_RADIUS),
        ),
        "far_end": _sphere(
            2 * rocker_pivot.DOME_SPHERE_RADIUS,
            (
                0.0,
                0.0,
                -rocker_bank.PIVOT_SHAFT_LENGTH
                + rocker_pivot.DOME_SPHERE_RADIUS
                - rocker_pivot.DOME_HEIGHT,
            ),
        ),
        "outer": _cylinder(
            rocker_pivot.SHAFT_DIA,
            _Z,
            _box(_Z, -rocker_bank.PIVOT_SHAFT_LENGTH, 0.0),
        ),
        **{
            f"flat_{side}": _plane(
                _Y,
                rocker_pivot.FLAT_AF - rocker_pivot.SHAFT_DIA / 2,
                _box(_Z, -station - 2, -station + 2),
            )
            for side, station in zip(
                ("south", "north"), rocker_bank.PIVOT_SHAFT_FLAT_STATIONS, strict=True
            )
        },
    },
    "dt_cylinder_gear_shaft": {
        "datum_end": _sphere(
            2 * _ARBOR_R, (0.0, _ARBOR_R - bank.ARBOR_DOME_HEIGHT, 0.0)
        ),
        "far_end": _sphere(
            2 * _ARBOR_R,
            (0.0, bank.ARBOR_LENGTH + bank.ARBOR_DOME_HEIGHT - _ARBOR_R, 0.0),
        ),
        "outer": _cylinder(arbor.SHAFT_DIA, _Y),
    },
    "dt_pinion_pivot_shaft": {
        "datum_end": _sphere(
            2 * pivot.CAP_RADIUS, (0.0, 0.0, pivot.CAP_RADIUS - pivot.CAP_SAG)
        ),
        "far_end": _sphere(
            2 * pivot.CAP_RADIUS,
            (0.0, 0.0, pivot.SHAFT_LEN + pivot.CAP_SAG - pivot.CAP_RADIUS),
        ),
        "outer": _cylinder(pivot.SHAFT_DIA, _Z),
        "cross_hole_front": _cylinder(
            pivot.PIN_HOLE_DIA,
            _X,
            _box(_Z, pivot.PIN_HOLE_Z[0] - 1, pivot.PIN_HOLE_Z[0] + 1),
        ),
        "cross_hole_back": _cylinder(
            pivot.PIN_HOLE_DIA,
            _X,
            _box(_Z, pivot.PIN_HOLE_Z[1] - 1, pivot.PIN_HOLE_Z[1] + 1),
        ),
    },
    "dt_pinion_lift_rod": {
        "datum_end": _plane((0.0, 0.0, -1.0), 0.0),
        "far_end": _sphere(
            2 * lift.CAP_R, (0.0, 0.0, lift.ROD_LEN + lift.CAP_SAG - lift.CAP_R)
        ),
        "outer": _cylinder(lift.ROD_DIA, _Z),
        **{
            name: _plane(
                lift.FLAT_NORMAL_LOCAL, lift.FLAT_HEIGHT, _box(_Z, z - 1, z + 1)
            )
            for name, z in _LIFT_FLAT_Z.items()
        },
        "cross_hole": _cylinder(lever.PIN_HOLE_DIA, _X),
    },
    "mg_wheel_axle": {
        "datum_end": _plane((0.0, -1.0, 0.0), -axle.BACK_Y),
        "shoulder": _plane(_Y, axle.STEP_Y),
        "far_end": _sphere(2 * axle.DOME_R, (0.0, axle.TIP_Y - axle.DOME_R, 0.0)),
        "outer": _cylinder(axle.PIN_DIA, _Y),
        "step": _cylinder(axle.THREAD_MAJOR, _Y),
        "groove": _cylinder(axle.RELIEF_DIA, _Y),
    },
}


@pytest.mark.parametrize("stem", sorted(_FACES))
def test_each_shaft_face_has_exactly_one_owner(stem: str) -> None:
    assert stem in export_features.SUPPORTED_PARTS
    selectors = export_features.feature_selectors(stem, None)
    assert set(selectors) == set(_FACES[stem])
    for name, face in _FACES[stem].items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(spec.matches(face) for spec in specs)
        ]
        assert owners == [name], name


@pytest.mark.parametrize("stem", sorted(_FACES))
def test_shaft_ends_lie_on_one_axis_with_the_length_between_them(stem: str) -> None:
    features = export_features.requirement_manifest(stem)["features"]
    datum, far = features["datum_end"], features["far_end"]
    axis = datum["plane"]["axis"]
    assert far["plane"]["axis"] == axis
    assert far["length_from"] == "datum_end"
    length = far.get("length_nominal", far.get("length_ref"))
    assert length == pytest.approx(abs(far["plane"]["value"] - datum["plane"]["value"]))
    for feature in features.values():
        if feature["kind"] == "diameter":
            assert [abs(value) for value in feature["axis"]] == [
                float(axis == letter) for letter in "xyz"
            ]


def _inch(values: list[float]) -> list[float]:
    return [round(value / IN, 4) for value in values]


def test_printed_bands_are_the_sheets() -> None:
    manifest = export_features.requirement_manifest

    shaft = manifest("ch_fulcrum_shaft")["features"]
    assert _inch(shaft["outer"]["dia"]) == [0.2492, 0.25]
    assert _inch(shaft["far_end"]["length"]) == [7.0, 7.02]
    assert _inch(shaft["flat_datum"]["station"]) == [0.23, 0.25]
    assert _inch(shaft["flat_far"]["station"]) == [6.59, 6.61]
    assert _inch(shaft["flat_far"]["length"]) == [0.16, 0.18]
    assert _inch(shaft["flat_datum"]["across"]) == [0.233, 0.243]
    assert shaft["far_end"]["radius_ref"] == pytest.approx(0.125 * IN)

    rocker = manifest("ch_pivot_shaft")["features"]
    assert _inch(rocker["outer"]["dia"]) == [0.2492, 0.25]
    assert _inch(rocker["far_end"]["length"]) == [6.84, 6.86]
    assert _inch(rocker["datum_end"]["height"]) == [0.05, 0.07]
    for side in ("north", "south"):
        assert _inch(rocker[f"flat_{side}"]["station"]) == [0.21, 0.23]
        assert _inch(rocker[f"flat_{side}"]["across"]) == [0.2, 0.22]
        assert _inch(rocker[f"flat_{side}"]["length"]) == [0.23, 0.25]
        assert rocker[f"flat_{side}"]["station_to"] == "centre"
    assert rocker["flat_south"]["station_from"] == "far_end"
    assert rocker["far_end"]["radius_ref"] == pytest.approx(
        rocker_pivot.DOME_SPHERE_RADIUS
    )

    cylinder = manifest("dt_cylinder_gear_shaft")["features"]
    assert cylinder["outer"]["dia_ref"] == pytest.approx(arbor.SHAFT_DIA)
    assert cylinder["outer"]["stock"].startswith("3/8 GROUND STOCK, AS SUPPLIED")
    assert _inch(cylinder["far_end"]["height"]) == [0.05, 0.07]
    assert _inch(cylinder["far_end"]["supply_length"]) == [7.4, 7.6]
    assert (
        cylinder["far_end"]["made_at"] == cylinder["datum_end"]["made_at"] == "assembly"
    )

    pivot_shaft = manifest("dt_pinion_pivot_shaft")["features"]
    assert _inch(pivot_shaft["far_end"]["body_length"]) == [7.7, 7.72]
    assert _inch(pivot_shaft["datum_end"]["height"]) == [0.04, 0.06]
    assert _inch(pivot_shaft["cross_hole_back"]["dia"]) == [0.0625, 0.065]
    assert pivot_shaft["cross_hole_front"]["made_at"] == "assembly"

    rod = manifest("dt_pinion_lift_rod")["features"]
    assert _inch(rod["far_end"]["body_length"]) == [8.14, 8.16]
    assert _inch(rod["far_end"]["radius"]) == [0.18, 0.2]
    assert _inch(rod["flat_back"]["station"]) == [0.58, 0.6]
    # #3042: the three feeler terms book their leaf tolerance, so the front
    # flat is one .01 step longer, toward the rim.
    assert _inch(rod["flat_front"]["station"]) == [6.95, 6.97]
    assert _inch(rod["flat_front"]["length"]) == [0.22, 0.24]
    assert rod["flat_back"]["station_from"] == "far_root"
    assert _inch(rod["cross_hole"]["dia"]) == [0.064, 0.068]
    assert _inch(rod["cross_hole"]["station"]) == [0.15, 0.17]

    pin = manifest("mg_wheel_axle")["features"]
    assert _inch(pin["shoulder"]["station"]) == [1.84, 1.86]
    assert _inch(pin["step"]["thread_length"]) == [0.314, 0.334]
    assert pin["step"]["thread"] == "#4-40 UNC"
    assert _inch(pin["step"]["dia"]) == [0.1061, 0.1112]
    assert _inch(pin["groove"]["dia"]) == [0.066, 0.076]
    assert _inch(pin["groove"]["width"]) == [0.028, 0.043]
    assert _inch(pin["far_end"]["radius"]) == [0.06, 0.08]
    assert pin["outer"]["dia_ref"] == pytest.approx(3 / 16 * IN)


def test_manifest_notes_are_the_printed_notes() -> None:
    import ch_fulcrum_shaft_notes
    import dt_cylinder_gear_shaft_notes

    notes = {
        stem: export_features.requirement_manifest(stem)["notes"]["manufacturing"]
        for stem in _FACES
    }
    assert (
        notes["ch_fulcrum_shaft"] == ch_fulcrum_shaft_notes.DRAWING_NOTES.splitlines()
    )
    assert (
        notes["dt_cylinder_gear_shaft"]
        == dt_cylinder_gear_shaft_notes.DRAWING_NOTES.splitlines()
    )
    assert notes["dt_pinion_pivot_shaft"] == [pivot.DRAWING_NOTES]
    assert notes["ch_pivot_shaft"] == rocker_pivot.DRAWING_NOTES.splitlines()
    assert notes["dt_pinion_lift_rod"] == notes["mg_wheel_axle"] == []
    # The supply length the arbor declares is the one its note prints.
    assert "SUPPLY 7-1/2 LONG" in dt_cylinder_gear_shaft_notes.DRAWING_NOTES
