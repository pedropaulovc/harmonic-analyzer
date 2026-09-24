"""Offline contracts for the gooseneck drawing."""

from __future__ import annotations

import counter_spring_stock_geom as counter_stock
import gooseneck_geom as geom


def test_counter_spring_eye_fits_the_clamped_screw_envelope() -> None:
    radial_retention = (geom.SCREW_HEAD_DIA - counter_stock.EYE_ID_MM) / 2.0
    radial_clearance = (counter_stock.EYE_ID_MM - geom.SCREW_SHANK_DIA) / 2.0

    assert radial_retention >= 1.0
    assert radial_clearance >= 0.25
    # Natively calibrated: the loop seats on the tube's OD corner, so both the
    # head gap and the loop centre fall inside the purchased end band.
    assert (
        0.0
        < geom.SPRING_EYE_CENTRE_FROM_ARM_END_MM
        < geom.SPRING_SCREW_CLAMPED_GAP_MM
        < counter_stock.END_OCCUPIED_WIDTH_MM
    )
    assert geom.SPRING_SCREW_TRAVEL_MM > 0.0


def test_brazed_plug_has_capillary_clearance_in_the_nominal_tube_bore() -> None:
    tube_id = geom.TUBE_DIA - 2.0 * geom.WALL_T
    nominal_radial_gap = (tube_id - geom.PLUG_DIA) / 2.0

    assert geom.PLUG_T > 0.0
    assert 0.051 <= nominal_radial_gap <= 0.127


def test_adjustment_screw_thread_and_slot_fit_the_body() -> None:
    assert geom.SCREW_THREAD_MAJOR_DIA <= geom.SCREW_SHANK_DIA
    assert (
        geom.SPRING_SCREW_UNDERHEAD_LENGTH_MM
        == geom.SPRING_SCREW_PLUG_ENGAGEMENT_MM + geom.SPRING_SCREW_OPEN_GAP_MM
    )
    assert geom.SPRING_SCREW_PLUG_ENGAGEMENT_MM == geom.PLUG_T
    assert geom.SCREW_SLOT_DEPTH < geom.SCREW_HEAD_T
    assert geom.SCREW_SLOT_W < geom.SCREW_HEAD_DIA


def test_screw_slot_leaves_a_two_millimetre_web_at_the_printed_worst_case() -> None:
    """User ruling: machined webs >= 2 mm (1.5 floor) at the worst case of the
    printed bands, fixed by geometry (a thicker head), not a tighter band."""
    import _config
    import gooseneck_spec

    rows = {1: "linear_1pl", 2: "linear_2pl", 3: "linear_3pl"}

    def band(name: str) -> float:
        places = gooseneck_spec.DRAWING_PRECISION_BY_NAME[name]
        return float(_config.title_block(rows[places])["value_in"]) * 25.4

    worst = (geom.SCREW_HEAD_T - band("HeadThickness")) - (
        geom.SCREW_SLOT_DEPTH + band("SlotDepth")
    )
    assert worst >= 2.0


def test_screw_engages_one_and_a_half_diameters_at_the_printed_worst_case() -> None:
    """Policy rule 12 (U27): full-thread engagement >= 1.5D at worst case, with
    the screw clamped and at the open (eye-installation) gap."""
    import _config
    import gooseneck_spec

    rows = {1: "linear_1pl", 2: "linear_2pl", 3: "linear_3pl"}

    def band(name: str) -> float:
        places = gooseneck_spec.DRAWING_PRECISION_BY_NAME[name]
        return float(_config.title_block(rows[places])["value_in"]) * 25.4

    plug = geom.PLUG_T - band("PlugDepth")
    shank = geom.SPRING_SCREW_UNDERHEAD_LENGTH_MM - band("UnderHeadLength")
    need = 1.5 * geom.SCREW_THREAD_MAJOR_DIA
    for gap in (geom.SPRING_SCREW_CLAMPED_GAP_MM, geom.SPRING_SCREW_OPEN_GAP_MM):
        assert min(plug, shank - gap) >= need


def test_thicker_head_clears_the_counter_spring_half_turn() -> None:
    """The head grows outboard only; the raised half-turn keeps 1.5 mm to it."""
    import spring_mount_geom

    pose = spring_mount_geom.COUNTER_REFERENCE_POSE
    screw_y = spring_mount_geom.GOOSENECK_ORIGIN_Y + geom.ARM_Y
    _tube_gap, head_gap = spring_mount_geom.counter_half_turn_clearances(pose, screw_y)
    assert head_gap >= 1.5




def test_gooseneck_consumers_import_against_this_geometry() -> None:
    # The assembly-side consumers read gooseneck_geom at import time; a renamed
    # or removed constant must fail here, on the gooseneck PR, not at merge.
    import build_motion_study_springs
    import build_summing_assembly
    import spring_mount_geom

    assert spring_mount_geom.COUNTER_UPPER_EYE_X == (
        spring_mount_geom.GOOSENECK_END_X + geom.SPRING_EYE_CENTRE_FROM_ARM_END_MM
    )
    assert build_summing_assembly.gooseneck_geom is geom
    assert build_motion_study_springs.GOOSENECK_EYE[0] == (
        geom.ARM_END_X - geom.SPRING_EYE_CENTRE_FROM_ARM_END_MM
    )


def test_stock_tube_wall_holds_the_floor_through_the_bend() -> None:
    """The purchased tube's worst-case wall (A519 Table 9, +/-10%) stays >= the
    1.5 mm floor straight and at the outer fibre of the R51 bend."""
    import gooseneck_spec

    straight = geom.WALL_T * (1.0 - gooseneck_spec.TUBE_STOCK_WALL_TOL)
    bend = straight * 2.0 * geom.BEND_R / (2.0 * geom.BEND_R + geom.TUBE_DIA)
    assert round(straight, 9) >= 1.8
    assert bend >= 1.5


def test_material_fits_one_title_block_line() -> None:
    """Farm r20: a 51-character material wrapped into the DRAWN PER row; the
    former 36-character string printed on one line. The printed field keeps
    CDS: the 1.80 wall minimum is A519's cold-worked (Table 9) band."""
    import _config

    material = str(_config.parts("gooseneck")["material"])
    assert len(material) <= 36
    assert "CDS" in material
