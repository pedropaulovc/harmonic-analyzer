"""Offline contracts for MHA-CH-008's apex set-screw tap (user, 2026-10-10)."""

from __future__ import annotations

import pytest

import build_ch_pivot_bracket as bracket_build
import ch_pivot_bracket_spec as bracket
import vn_arbor_set_screw_spec as set_screw
from _hole_spec import TAP_DRILL_MM, blind_cut_dia_mm
from _holes import cross_hole_volume_mm3


def test_apex_tap_is_the_set_screws_thread_through_to_the_bore() -> None:
    assert bracket.SET_SCREW_THREAD == set_screw.THREAD == "#4-40"
    spec = bracket.SET_SCREW_HOLE_SPEC
    assert (spec.kind, spec.size, spec.end) == ("tapped", "#4-40", "through_next")
    assert bracket.SET_SCREW_MAJOR_DIA == set_screw.MAJOR_DIA
    assert bracket.SET_SCREW_PITCH == pytest.approx(set_screw.POINT_LENGTH)


def test_apex_tap_starts_on_the_arch_apex() -> None:
    assert bracket.EAR_TOP_Y == pytest.approx(bracket.BORE_H + bracket.EAR_ARCH_R)
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
        {"inboard face": 2.4275, "outboard face": 2.3275}
    )
    assert min(bracket.SET_SCREW_WALLS_MIN.values()) >= bracket.LIGAMENT_TARGET == 2.0


def test_web_over_the_bore_keeps_the_floor() -> None:
    assert bracket.BORE_LIGAMENT == pytest.approx(4.75)
    assert bracket.BORE_LIGAMENT >= bracket.LIGAMENT_FLOOR == 1.5


def test_set_screw_engagement_is_the_named_exception_value() -> None:
    """Short of rule 12's 1.5D: the R8 arch over the bore is all the thread
    there is (named exception, drawing-simplicity-policy.md)."""
    assert bracket.SET_SCREW_FULL_THREAD_MIN == pytest.approx(3.098, abs=1e-3)
    assert bracket.SET_SCREW_ENGAGEMENT_D == pytest.approx(1.089, abs=1e-3)
    assert bracket.SET_SCREW_ENGAGEMENT_PRINTED == 1.08
    assert (
        bracket.SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT
        == "#4-40 ENGAGEMENT 3.10 MIN (1.08D)."
    )


def test_apex_tap_volume_is_the_drill_from_the_arch_to_the_bore() -> None:
    drill = blind_cut_dia_mm(bracket.SET_SCREW_HOLE_SPEC)
    assert drill == TAP_DRILL_MM["#4-40"]
    assert bracket_build.V_TAP == pytest.approx(
        (
            cross_hole_volume_mm3(drill, 2.0 * bracket.EAR_ARCH_R)
            - cross_hole_volume_mm3(drill, bracket.BORE_DIA)
        )
        / 2.0
    )
    assert bracket_build.V_TAP == pytest.approx(19.19, abs=0.01)
