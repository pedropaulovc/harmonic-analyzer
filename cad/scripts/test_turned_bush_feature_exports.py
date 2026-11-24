"""Feature-export declarations of the turned bushes, spacers and rings.

Each part's drawing declares its turned faces in its own model frame; these
tests build each face from the part's own constants and prove exactly one
declared feature owns it, and that the bands are the printed ones.
"""

from __future__ import annotations

import math

import pytest

import ch_rocker_hub_spec as hub
import ch_rocker_strap_tl_hub_plug_spec as plug
import dt_cone_gear_tl_arbor_collar_spec as collar
import dt_crank_handle_butt_cup_seat_spec as cup_seat
import dt_crank_handle_butt_cup_spec as cup
import dt_crank_handle_ferrule_spec as ferrule
import dt_cylinder_end_disc_spec as disc
import export_features
import mg_wheel_axle_spacer_spec as spacer
import pd_transgear_knob_bush_geometry as knob_bush
import pd_transgear_knob_thrust_ring_spec as thrust_ring
import pd_transgear_pivot_spacer_spec as pivot_spacer
import sm_gooseneck_geom as gooseneck
import sm_gooseneck_spring_joint as joint
from _gtol_face import SURFACE_CONE, SURFACE_CYLINDER, SURFACE_PLANE, FaceGeometry

IN = 25.4


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, SURFACE_PLANE, (*normal, *point), normal, ())


def _cylinder(dia_mm: float, axis: tuple[float, float, float]) -> FaceGeometry:
    return FaceGeometry(
        None, SURFACE_CYLINDER, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, ()
    )


def _cone_x(x0_mm: float, x1_mm: float) -> FaceGeometry:
    box = (x0_mm / 1000, -1.0, -1.0, x1_mm / 1000, 1.0, 1.0)
    return FaceGeometry(
        None, SURFACE_CONE, (0.0,) * 7 + (math.radians(45.0),), None, box
    )


def _cone(z0_mm: float, z1_mm: float) -> FaceGeometry:
    return FaceGeometry(
        None,
        SURFACE_CONE,
        (0.0,) * 7 + (math.radians(45.0),),
        None,
        (-1.0, -1.0, z0_mm / 1000, 1.0, 1.0, z1_mm / 1000),
    )


_Z = (0.0, 0.0, 1.0)
_X = (1.0, 0.0, 0.0)
_MINUS_Z = (0.0, 0.0, -1.0)
_MINUS_X = (-1.0, 0.0, 0.0)
_Y = (0.0, 1.0, 0.0)
_MINUS_Y = (0.0, -1.0, 0.0)


def _annulus(length: float, od: float, bore: float) -> dict[str, FaceGeometry]:
    """A Front-plane annulus extruded +Z by ``length``."""
    return {
        "datum_end": _plane(_MINUS_Z, 0.0),
        "far_end": _plane(_Z, length),
        "outer": _cylinder(od, _Z),
        "bore": _cylinder(bore, _Z),
    }


_FACES: dict[tuple[str, str | None], dict[str, FaceGeometry]] = {
    ("ch_rocker_hub", None): {
        "datum_end": _plane(_MINUS_Z, hub.SUPPLY_LENGTH_MIN / 2),
        "far_end": _plane(_Z, hub.SUPPLY_LENGTH_MIN / 2),
        "outer": _cylinder(hub.LAND_DIA, _Z),
        "bore": _cylinder(hub.SUPPLY_BORE_DIA, _Z),
    },
    ("ch_rocker_strap_tl_hub_plug", None): {
        "datum_end": _plane(_MINUS_Z, 0.0),
        "shoulder": _plane(_Z, plug.BODY_LENGTH),
        "far_end": _plane(_Z, plug.OVERALL_LENGTH),
        "outer": _cylinder(plug.BODY_DIA, _Z),
        "step": _cylinder(plug.PILOT_DIA, _Z),
        "bore": _cylinder(plug.BORE_DIA, _Z),
        "chamfer_far": _cone(plug.OVERALL_LENGTH - plug.CHAMFER, plug.OVERALL_LENGTH),
    },
    ("dt_cone_gear_tl_arbor_collar", None): _annulus(
        collar.LENGTH, collar.OD_BY_CONFIGURATION["C175"], collar.BORE
    ),
    ("dt_cone_gear_tl_arbor_collar", "C100"): {
        "outer_c100": _cylinder(collar.OD_BY_CONFIGURATION["C100"], _Z)
    },
    ("dt_cone_gear_tl_arbor_collar", "C050"): {
        "outer_c050": _cylinder(collar.OD_BY_CONFIGURATION["C050"], _Z)
    },
    ("dt_cylinder_end_disc", None): _annulus(
        disc.WASHER_THICK, disc.WASHER_OD, disc.WASHER_BORE
    ),
    ("mg_wheel_axle_spacer", None): _annulus(spacer.LENGTH, spacer.OD, spacer.BORE_DIA),
    ("dt_crank_handle_ferrule", None): {
        "datum_end": _plane(_MINUS_X, 0.0),
        "far_end": _plane(_X, ferrule.LENGTH),
        "outer": _cylinder(ferrule.OUTER_DIA, _X),
        "bore": _cylinder(ferrule.BORE_DIA, _X),
    },
    ("dt_crank_handle_butt_cup", None): {
        "datum_end": _plane(_X, 0.0),
        "far_end": _plane(_MINUS_X, cup.OVERALL_LENGTH),
        "outer": _cylinder(cup.BODY_DIA, _X),
        "pocket": _plane(_X, -cup.POCKET_DEPTH),
        "bore": _cylinder(cup.FLOOR_HOLE_DIA, _X),
        "chamfer_far": _cone_x(
            -cup.OVERALL_LENGTH, -(cup.OVERALL_LENGTH - cup.BODY_CHAMFER)
        ),
        "chamfer_bore": _cone_x(
            -(cup.POCKET_DEPTH + cup_seat.FLOOR_HOLE_CHAMFER), -cup.POCKET_DEPTH
        ),
    },
    ("sm_gooseneck_end_plug", None): {
        "datum_end": _plane(_MINUS_X, 0.0),
        "shoulder": _plane(_X, gooseneck.PLUG_HEAD_LENGTH),
        "far_end": _plane(_X, gooseneck.PLUG_LENGTH),
        "outer": _cylinder(gooseneck.PLUG_DIA, _X),
        "step": _cylinder(joint.PLUG_SHANK_DIA, _X),
        "tap": _cylinder(joint.TAP_DRILL_DIA, _X),
    },
    ("pd_transgear_knob_thrust_ring", None): {
        "datum_end": _plane(_MINUS_Y, 0.0),
        "far_end": _plane(_Y, thrust_ring.LENGTH),
        "outer": _cylinder(thrust_ring.OD, _Y),
        "bore": _cylinder(thrust_ring.ID, _Y),
    },
    ("pd_transgear_pivot_spacer", None): _annulus(
        pivot_spacer.LENGTH, pivot_spacer.OD, pivot_spacer.BORE_DIA
    ),
    ("pd_transgear_knob_bush", None): {
        "datum_end": _plane(_MINUS_Y, 0.0),
        "shoulder": _plane(_Y, knob_bush.HUB_LENGTH),
        "far_end": _plane(_Y, knob_bush.LENGTH),
        "outer": _cylinder(knob_bush.HUB_DIA, _Y),
        "step": _cylinder(knob_bush.PRESS_DIA, _Y),
        "bore": _cylinder(knob_bush.BORE_DIA, _Y),
    },
}
_POCKET_WALL = ("dt_crank_handle_butt_cup", "pocket", _cylinder(cup.POCKET_DIA, _X))


@pytest.mark.parametrize(("stem", "configuration"), sorted(_FACES, key=str))
def test_each_turned_face_has_exactly_one_owner(
    stem: str, configuration: str | None
) -> None:
    assert stem in export_features.SUPPORTED_PARTS
    selectors = export_features.feature_selectors(stem, configuration)
    expected = dict(_FACES[stem, configuration])
    assert set(selectors) == set(expected)
    if (stem, configuration) == (_POCKET_WALL[0], None):
        expected["pocket wall"] = _POCKET_WALL[2]
    for name, face in expected.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(spec.matches(face) for spec in specs)
        ]
        assert owners == [name.removesuffix(" wall")], name


@pytest.mark.parametrize("stem", sorted({stem for stem, _ in _FACES}))
def test_turned_parts_declare_a_datum_end_and_a_coaxial_axis(stem: str) -> None:
    features = export_features.requirement_manifest(stem)["features"]
    datum = features["datum_end"]
    axis = datum["plane"]["axis"]
    for feature in features.values():
        if "axis" in feature:
            assert [abs(value) for value in feature["axis"]] == [
                float(axis == letter) for letter in "xyz"
            ]
            assert feature["at"] == [0.0, 0.0, 0.0]
        if "span" in feature:
            assert feature["span"][0] < feature["span"][1]
    far = features["far_end"]
    length = far.get("length_nominal")
    assert length == pytest.approx(abs(far["plane"]["value"] - datum["plane"]["value"]))


def _inch(values: list[float]) -> list[float]:
    return [round(value / IN, 4) for value in values]


def test_printed_bands_are_the_sheets() -> None:
    manifest = export_features.requirement_manifest
    hub_features = manifest("ch_rocker_hub")["features"]
    # Owner ruling 2026-11-21, matched fit only: the land is a reference
    # turned to the measured strap hole, no band of its own.
    assert "dia" not in hub_features["outer"]
    assert _inch([hub_features["outer"]["dia_ref"]]) == [0.4]
    assert _inch(hub_features["outer"]["diametral_interference"]) == [0.0004, 0.0013]
    assert hub_features["far_end"]["length_min"] == pytest.approx(0.32 * IN)
    assert _inch(hub_features["bore"]["dia"]) == [0.246, 0.25]

    plug_features = manifest("ch_rocker_strap_tl_hub_plug")["features"]
    assert _inch(plug_features["step"]["dia"]) == [0.3985, 0.3995]
    assert _inch(plug_features["outer"]["diametral_clearance"]) == [0.0005, 0.0015]
    assert _inch(plug_features["shoulder"]["station"]) == [0.165, 0.175]
    assert _inch(plug_features["far_end"]["length"]) == [0.267, 0.277]
    assert _inch(plug_features["chamfer_far"]["leg"]) == [0.01, 0.03]

    collar_features = manifest("dt_cone_gear_tl_arbor_collar")["features"]
    assert [
        collar_features[name]["dia_ref"]
        for name in ("outer", "outer_c100", "outer_c050")
    ] == pytest.approx([value * IN for value in (1.75, 1.0, 0.5)])
    assert _inch(collar_features["far_end"]["length"]) == [0.32, 0.34]
    # Owner ruling 2026-11-21: the spacer prints .732 at the title block.
    assert _inch(manifest("mg_wheel_axle_spacer")["features"]["far_end"]["length"]) == [
        0.727,
        0.737,
    ]
    disc_features = manifest("dt_cylinder_end_disc")["features"]
    assert _inch(disc_features["outer"]["dia"]) == [2.16, 2.18]
    assert _inch(disc_features["far_end"]["length"]) == [0.10, 0.12]
    ferrule_features = manifest("dt_crank_handle_ferrule")["features"]
    assert _inch(ferrule_features["bore"]["dia"]) == [0.298, 0.308]
    # Fit audit question 15: the N drill names the hole's process.
    assert ferrule_features["bore"]["process"] == "drill"
    cup_features = manifest("dt_crank_handle_butt_cup")["features"]
    assert _inch(cup_features["pocket"]["depth"]) == [0.212, 0.222]
    # The pocket's own limits, unmatched to the head (fit audit question 15).
    assert _inch(cup_features["pocket"]["dia"]) == [0.248, 0.257]
    assert _inch(cup_features["chamfer_bore"]["leg"]) == [0.005, 0.01]
    plug_end = manifest("sm_gooseneck_end_plug")["features"]
    assert plug_end["tap"]["thread"] == "#10-24 UNC-2B"
    assert _inch(plug_end["tap"]["drill_depth"]) == [0.55, 0.57]
    assert _inch(plug_end["tap"]["thread_depth"]) == [0.43, 0.45]
    assert _inch(plug_end["step"]["diametral_clearance"]) == [0.004, 0.009]


def test_the_paper_drive_bushes_print_the_sheets_bands() -> None:
    manifest = export_features.requirement_manifest
    ring = manifest("pd_transgear_knob_thrust_ring")["features"]
    assert _inch(ring["far_end"]["length"]) == [0.266, 0.268]
    assert _inch(ring["outer"]["dia"]) == [0.51, 0.53]
    assert _inch(ring["bore"]["dia"]) == [0.257, 0.261]
    assert ring["bore"]["process"] == "drill"

    pivot = manifest("pd_transgear_pivot_spacer")["features"]
    # The sheet prints .197 ±.001 about the exact 5.0 mm model.
    assert _inch(pivot["far_end"]["length"]) == [0.196, 0.198]
    assert _inch(pivot["outer"]["dia"]) == [0.43, 0.45]
    assert _inch(pivot["bore"]["dia"]) == [0.189, 0.193]
    assert pivot["bore"]["process"] == "drill"
    assert _inch(pivot["bore"]["diametral_clearance_ref"]) == [0.0015, 0.0065]
    assert "parallelism" not in pivot["far_end"]
    assert "datum_feature" not in pivot["datum_end"]
    assert "perpendicularity" not in pivot["datum_end"]
    assert _inch([pivot["outer"]["runout"]]) == [0.016]

    bush = manifest("pd_transgear_knob_bush")["features"]
    assert _inch(bush["outer"]["dia"]) == [0.51, 0.53]
    # Made to the plate's measured hole: the export declares the (Ø.4385)
    # reference and the interference, no diameter band, so the traveler's
    # pictures print the fit to the measured mate (traveler review r2).
    assert "dia" not in bush["step"]
    assert _inch([bush["step"]["dia_ref"]]) == [0.4385]
    assert _inch(bush["step"]["diametral_interference"]) == [0.0005, 0.0016]
    assert _inch(bush["shoulder"]["station"]) == [0.808, 0.81]
    assert _inch([bush["shoulder"]["root_radius_max"]]) == [0.005]
    assert _inch(bush["far_end"]["length"]) == [1.141, 1.145]
    # Reamed through after pressing, at MHA-PD-00: the bush's own traveler
    # leaves its drilled hole for that ream.
    assert _inch(bush["bore"]["dia"]) == [0.249, 0.2495]
    assert bush["bore"]["made_at"] == "assembly"
    assert _inch([bush["bore"]["wall_min"]]) == [0.068]


def test_manifest_notes_are_the_printed_notes() -> None:
    import draw_dt_crank_handle_butt_cup as cup_drawing
    import dt_crank_handle_ferrule_notes as ferrule_notes

    notes = export_features.requirement_manifest("dt_crank_handle_butt_cup")["notes"][
        "manufacturing"
    ]
    assert notes == cup_drawing.NOTES_TEXT.splitlines()
    ferrule_manifest = export_features.requirement_manifest("dt_crank_handle_ferrule")
    assert (
        ferrule_manifest["notes"]["manufacturing"]
        == ferrule_notes.SHEET_NOTES.replace("<MOD-DIAM>", "Ø").splitlines()
    )
    for stem in (
        "ch_rocker_strap_tl_hub_plug",
        "dt_cone_gear_tl_arbor_collar",
        "dt_cylinder_end_disc",
        "mg_wheel_axle_spacer",
    ):
        assert (
            export_features.requirement_manifest(stem)["notes"]["manufacturing"] == []
        )
