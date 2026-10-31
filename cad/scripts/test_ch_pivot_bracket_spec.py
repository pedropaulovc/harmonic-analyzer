"""Offline contracts for MHA-CH-08's apex set-screw tap (user, 2026-10-10)."""

from __future__ import annotations

import math

import pytest

import build_ch_pivot_bracket as bracket_build
import ch_pivot_bracket_spec as bracket
import sh_vn_arbor_set_screw_spec as set_screw
from _hole_spec import TAP_DRILL_MM, blind_cut_dia_mm
from _holes import cross_hole_volume_mm3


def test_apex_tap_is_the_set_screws_thread_through_to_the_bore() -> None:
    assert bracket.SET_SCREW_THREAD == set_screw.THREAD == "#4-40"
    spec = bracket.SET_SCREW_HOLE_SPEC
    assert (spec.kind, spec.size, spec.end) == ("tapped", "#4-40", "through_next")
    assert bracket.SET_SCREW_MAJOR_DIA == set_screw.MAJOR_DIA
    assert bracket.SET_SCREW_PITCH == pytest.approx(set_screw.POINT_LENGTH)


def test_apex_tap_starts_on_the_arch_apex() -> None:
    assert bracket.EAR_TOP_Y == pytest.approx(
        bracket.BORE_H + bracket.ARCH_LIFT + bracket.EAR_ARCH_R
    )
    assert bracket.EAR_TOP_Y == pytest.approx(bracket.BORE_H + bracket.APEX_ABOVE_BORE)
    source = open(bracket_build.__file__, encoding="utf-8").read()
    assert "[0.0, EAR_TOP_Y, 0.0]" in source
    assert 'point_planes=("Front Plane", "Right Plane")' in source
    assert 'name="SetScrewTap"' in source


def test_set_screw_cup_is_the_vendors_point() -> None:
    """The shaft's flat must take the cup end: the major less the vendor's
    45 deg x one-pitch point chamfer each side."""
    assert bracket.SET_SCREW_POINT_DIA == pytest.approx(
        set_screw.MAJOR_DIA - 2.0 * set_screw.POINT_LENGTH
    )
    assert bracket.SET_SCREW_POINT_DIA == pytest.approx(1.575, abs=1e-3)


def test_apex_tap_keeps_its_walls_to_both_ear_faces() -> None:
    assert bracket.SET_SCREW_WALLS_MIN == pytest.approx(
        {"inboard face": 2.4891, "outboard face": 2.3875}
    )
    assert min(bracket.SET_SCREW_WALLS_MIN.values()) >= bracket.LIGAMENT_TARGET
    assert bracket.LIGAMENT_TARGET == pytest.approx(2.032)  # .080 in


def test_web_over_the_bore_keeps_the_floor() -> None:
    assert bracket.BORE_LIGAMENT == pytest.approx(6.6008)
    assert bracket.BORE_LIGAMENT >= bracket.LIGAMENT_FLOOR
    assert bracket.LIGAMENT_FLOOR == pytest.approx(1.524)  # .060 in


def test_set_screw_keeps_one_and_a_half_diameters_of_full_thread() -> None:
    """drawing-guidelines.md rule 18 (thread engagement): the apex stands
    1.38 over the seat, its arch's centre ARCH_LIFT over the bore, so the
    apex tap keeps 1.5D of full thread with the overall height at the title
    block's .XX and the bore height at its printed .99 plus that band (#1371;
    it was 3.10 / 1.08D with the arch about the bore)."""
    assert (bracket.EAR_TOP_Y, bracket.HEIGHT_BAND) == (
        pytest.approx(1.38 * 25.4),
        pytest.approx(0.01 * 25.4),
    )
    assert bracket.APEX_ABOVE_BORE == pytest.approx(9.852)
    assert bracket.ARCH_LIFT == pytest.approx(1.724)
    assert bracket.SET_SCREW_WALL_TERMS["apex over the bore at its minimum"] == (
        pytest.approx(bracket.EAR_TOP_Y - bracket.HEIGHT_BAND - (0.99 + 0.01) * 25.4)
    )
    assert bracket.SET_SCREW_FULL_THREAD_MIN == pytest.approx(5.009, abs=1e-3)
    assert bracket.SET_SCREW_ENGAGEMENT_D == pytest.approx(1.761, abs=1e-3)
    assert bracket.SET_SCREW_ENGAGEMENT_D >= bracket.SET_SCREW_MIN_ENGAGEMENT_D == 1.5


def test_set_screw_stays_inside_its_tap() -> None:
    """The 1/4 screw, its cup on the shaft flat, ends below the lifted apex,
    so all of its length is in the tap."""
    import build_ch_channel_assembly as channel

    assert channel.SET_SCREW_PROUD < 0.0


def test_apex_tap_volume_is_the_drill_from_the_arch_to_the_bore() -> None:
    drill = blind_cut_dia_mm(bracket.SET_SCREW_HOLE_SPEC)
    assert drill == TAP_DRILL_MM["#4-40"]
    assert bracket_build.V_TAP == pytest.approx(
        (
            cross_hole_volume_mm3(drill, 2.0 * bracket.EAR_ARCH_R)
            - cross_hole_volume_mm3(drill, bracket.BORE_DIA)
        )
        / 2.0
        + math.pi * (drill / 2.0) ** 2 * bracket.ARCH_LIFT
    )
