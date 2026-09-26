"""Offline contracts for the crank-mesh fit-up stack (#906 R1)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import cone_pivot_post_spec as post
import crank_drive_gear_spec as gear64
import crank_eccentric_bushing_spec as bushing
import crank_mesh_stack as stack
import crank_pinion_spec as pinion


def _terms(**overrides: float) -> dict[str, stack.Term]:
    kwargs = {
        "spacing_printed": stack.SPACING_PRINTED,
        "plan_limit_deg": stack.POST_ANGLE_DEG,
        "crank_angle_deg": stack.CRANK_ANGLE_DEG,
        "crank_bearing_length": stack.CRANK_BEARING_LENGTH,
        **overrides,
    }
    return {t.name: t for t in stack.stack_terms(**kwargs)}


def test_linear_model_reads_every_measured_case_within_its_residual() -> None:
    """The exact-solid study, from -0.35 to +0.15 of centre distance, at
    both R1 fit-up states and at the nominal fit-up the bushing throws the
    axis sideways to, stays within LINEAR_RESIDUAL_MM of the model; the
    residual is the worst of them rounded out to 0.001."""
    residuals = [
        abs(measured - stack._linear_backlash(dc, thin64, thin16))
        for dc, thin64, thin16, measured in stack.STUDY_CHECKS.values()
    ]
    assert max(residuals) <= stack.LINEAR_RESIDUAL_MM
    assert stack.LINEAR_RESIDUAL_MM == pytest.approx(
        math.ceil(max(residuals) / 0.001) * 0.001
    )
    assert max(residuals) == pytest.approx(0.0054, abs=1e-4)
    assert stack.STUDY_CHECKS["R1-fitaxis-nominal"][0] == pytest.approx(
        stack.FITUP_DC_NOMINAL, abs=1e-5
    )
    assert stack.KC == pytest.approx(0.5846, abs=1e-4)


def test_the_throw_reaches_both_ends() -> None:
    print(stack.stack_text())
    assert stack.THROW_REACH == bushing.ECCENTRICITY + bushing.ECCENTRICITY_BAND[1]
    assert stack.OPEN_MARGIN > 0.0
    assert stack.CLOSE_MARGIN > 0.0


def test_the_printed_drop_is_the_one_that_centres_the_reach() -> None:
    assert round(stack.IDEAL_DROP, 2) == post.CRANK_BORE_DROP
    assert abs(stack.OPEN_MARGIN - stack.CLOSE_MARGIN) < 0.02


def test_both_shafts_sag_at_rest_at_both_corners() -> None:
    terms = _terms()
    crank = terms["crank float at rest"]
    cone = terms["cone float at rest"]
    assert crank.tight < crank.loose < 0.0
    assert 0.0 < cone.tight < cone.loose


def test_every_angle_source_is_in_the_budget() -> None:
    assert stack.CRANK_ANGLE_DEG == pytest.approx(
        stack.POST_ANGLE_DEG + stack.BUSHING_ANGLE_DEG + stack.SEAT_COCK_DEG
    )
    assert stack.MESH_LEVER == pytest.approx(27.575, abs=1e-3)
    # The post frame's move at the mesh is the verifier's 0.038.
    assert stack.POST_ANGLE_AT_MESH == pytest.approx(0.038, abs=5e-4)


def test_the_angularity_frame_is_load_bearing() -> None:
    """At the title block's +/-1 deg in place of the frame, the stack no
    longer closes."""
    terms = _terms(plan_limit_deg=1.0, crank_angle_deg=1.0 + stack.BUSHING_ANGLE_DEG)
    tight = stack.NOMINAL_TIGHT_BACKLASH_MM + sum(t.tight for t in terms.values())
    assert stack.THROW_REACH - (stack.FITUP_BACKLASH_MM - tight) / stack.KC < 0.0


def test_no_worst_case_tip_reaches_a_root() -> None:
    """At the worst reading the fitter accepts (the bottom of the band), with
    both tips at the top of their printed band."""
    assert stack.WORST_ACCEPTED_BACKLASH_MM == pytest.approx(0.22)
    assert (
        stack.WORST_CLOSE_NEEDED <= bushing.ECCENTRICITY + bushing.ECCENTRICITY_BAND[0]
    )
    assert stack.TIP_ROOT_BAND_RADIAL == pytest.approx(
        max(pinion.OUTSIDE_DIA_TOLERANCE_MM, gear64.OUTSIDE_DIA_TOLERANCE_MM) / 2.0
    )
    assert stack.TIP_ROOT_AIR_WORST == pytest.approx(0.1804, abs=5e-4)


def test_the_tip_band_is_a_reach_term_measured_at_its_own_band() -> None:
    """Exact solids at +/-0.05 radial on both gears: the worst closing is the
    loose fit-up with large tips (-0.0043), the worst opening the worst
    accepted state with small ones (+0.0047); the term rounds each outward."""
    readings = stack._TIP_BAND_READINGS
    assert min(readings.values()) == pytest.approx(-0.00435, abs=1e-5)
    assert min(readings, key=readings.get) == ("loose fit-up", +1)
    assert max(readings.values()) == pytest.approx(+0.00474, abs=1e-5)
    assert max(readings, key=readings.get) == ("worst accepted", -1)
    term = {t.name: t for t in stack.TERMS}["tip diameter band"]
    assert term.tight == pytest.approx(-0.005)
    assert term.loose == pytest.approx(+0.005)
    assert term.tight <= min(readings.values())
    assert term.loose >= max(readings.values())
    assert stack.TIP_ROOT_BAND_RADIAL == stack._TIP_BAND_MEASURED_RADIAL


def test_r1_throw_margins_at_e_0625() -> None:
    assert bushing.ECCENTRICITY == 0.625
    assert stack.THROW_REACH == pytest.approx(0.600)
    assert stack.OPEN_MARGIN == pytest.approx(0.0338, abs=5e-4)
    assert stack.CLOSE_MARGIN == pytest.approx(0.0269, abs=5e-4)
    assert stack.IDEAL_DROP == pytest.approx(0.2135, abs=5e-4)


def test_bonding_leaves_the_fitter_a_reading_allowance() -> None:
    assert stack.RESEAT_DC == stack.SEAT_AT_MESH
    assert stack.READING_ALLOWANCE > 0.015


def test_frame_matches_the_assembly_c2c() -> None:
    assert stack.FRAME_C2C == pytest.approx(39.735, abs=0.001)
    assert stack.FRAME_DY == pytest.approx(39.332, abs=1e-9)
    assert stack.SPACING_PRINTED == round(stack.FRAME_DY - post.CRANK_BORE_DROP, 2)


def test_the_platform_crank_axis_is_the_fitup_axis_and_prints_nothing() -> None:
    """User ruling R1 (a): the plate's hidden crank-axis reference moves to
    the nominal fit-up axis by the stack's derived offsets, and no printed
    platform dimension is taken off it."""
    import build_cone_swing_platform as plat

    assert plat.CRANK_AXIS_OFF == pytest.approx(
        plat._CRANK_AXIS_OFF_FRAME - stack.FITUP_AXIS_DX, abs=1e-12
    )
    assert plat.CRANK_AXIS_Y == pytest.approx(
        plat._CRANK_AXIS_Y_FRAME + stack.FITUP_AXIS_DY, abs=1e-12
    )
    assert stack.FITUP_AXIS_DX == pytest.approx(0.6029, abs=5e-4)
    assert stack.FITUP_AXIS_DY == pytest.approx(-0.0454, abs=5e-4)
    assert plat._CRANK_AXIS_FEATURES.isdisjoint(plat.DRAWING_DIMENSIONS)
    # Each is a feature the build really names (once in the set, again where
    # it is created), so the guard cannot go stale on a rename.
    source = Path(plat.__file__).read_text(encoding="utf-8")
    for feature in plat._CRANK_AXIS_FEATURES:
        assert source.count(f'"{feature}"') >= 2, feature
