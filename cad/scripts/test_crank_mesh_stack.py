"""Offline contracts for the crank-mesh fit-up stack (#906 R1)."""

from __future__ import annotations

import pytest

import cone_pivot_post_spec as post
import crank_eccentric_bushing_spec as bushing
import crank_mesh_stack as stack


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
    """The exact-solid study, from -0.35 to +0.15 of centre distance and at
    both R1 fit-up states, stays within LINEAR_RESIDUAL_MM of the model."""
    for dc, thin64, thin16, measured in stack.STUDY_CHECKS.values():
        linear = stack._linear_backlash(dc, thin64, thin16)
        assert abs(measured - linear) <= stack.LINEAR_RESIDUAL_MM + 1e-4
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
    assert stack.TIP_ROOT_AIR_WORST > 0.0


def test_bonding_leaves_the_fitter_a_reading_allowance() -> None:
    assert stack.RESEAT_DC == stack.SEAT_AT_MESH
    assert stack.READING_ALLOWANCE > 0.015


def test_frame_matches_the_assembly_c2c() -> None:
    assert stack.FRAME_C2C == pytest.approx(39.735, abs=0.001)
    assert stack.FRAME_DY == pytest.approx(39.332, abs=1e-9)
    assert stack.SPACING_PRINTED == round(stack.FRAME_DY - post.CRANK_BORE_DROP, 2)
