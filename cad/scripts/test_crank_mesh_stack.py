"""Offline contracts for the crank-mesh fit-up stack (#906 R1)."""

from __future__ import annotations

import pytest

import cone_pivot_post_spec as post
import crank_eccentric_bushing_spec as bushing
import crank_mesh_stack as stack

_CENTRE_DISTANCE_TERMS = (
    "crank bore spacing (printed band, from the frame)",
    "cone bore plan angle",
    "64T axial station",
    "crank float at rest",
    "cone float at rest",
    "gear bore runout (16T slip, 64T bonded)",
)


def test_terms_rebuild_the_study_corners_centre_distances() -> None:
    """The study's corners were cut at the pre-R1 prints: spacing 39.33
    +0.37/0 against the frame, plan +/-1 deg, the crank in the post's own
    72.03 bore.  The named centre-distance terms must land on the offsets the
    study actually built, or a term is mis-derived."""
    terms = {
        t.name: t
        for t in stack.stack_terms(
            spacing_printed=39.33,
            plan_limit_deg=1.0,
            crank_bearing_length=post.CRANK_BOSS_LENGTH,
        )
    }
    tight = sum(terms[name].tight for name in _CENTRE_DISTANCE_TERMS) / stack.KC
    loose = sum(terms[name].loose for name in _CENTRE_DISTANCE_TERMS) / stack.KC
    assert tight == pytest.approx(stack.STUDY_CORNERS["tight"][0], abs=0.002)
    assert loose == pytest.approx(stack.STUDY_CORNERS["loose"][0], abs=0.002)


def test_linear_model_plus_excess_reads_the_measured_corners() -> None:
    for dc, thin64, thin16, measured in stack.STUDY_CORNERS.values():
        linear = stack._linear_backlash(dc, thin64, thin16)
        assert abs(measured - linear) < 0.025
    (excess,) = [
        t for t in stack.TERMS if t.name == "study excess over the linear model"
    ]
    assert excess.tight == 0.0  # the tight corner read looser than linear
    assert excess.loose == pytest.approx(0.0188, abs=0.0005)


def test_the_throw_reaches_both_ends_with_margin() -> None:
    print(stack.stack_text())
    assert stack.THROW_REACH == bushing.ECCENTRICITY + bushing.ECCENTRICITY_BAND[1]
    assert stack.OPEN_MARGIN > 0.05
    assert stack.CLOSE_MARGIN > 0.05


def test_the_bore_drop_centres_the_reach_on_the_window() -> None:
    assert post.CRANK_BORE_DROP == 0.26
    assert abs(stack.OPEN_MARGIN - stack.CLOSE_MARGIN) < 0.02


def test_the_angularity_frame_is_load_bearing() -> None:
    """At the title block's +/-1 deg in place of the frame, the throw no
    longer reaches the open end."""
    assert post.CRANK_BORE_ANGLE_LIMIT_DEG < 0.1
    terms = stack.stack_terms(
        spacing_printed=stack.SPACING_PRINTED,
        plan_limit_deg=1.0,
        crank_bearing_length=bushing.LENGTH - 0.8,
    )
    tight = stack.NOMINAL_TIGHT_BACKLASH_MM + sum(t.tight for t in terms)
    assert stack.THROW_REACH - (stack.FITUP_BACKLASH_MM - tight) / stack.KC < 0.0


def test_bonding_leaves_the_fitter_a_reading_allowance() -> None:
    # g6 in H7: half of 0.018 + 0.017 of seat clearance.
    assert stack.RESEAT_DC == pytest.approx(0.0175)
    assert stack.READING_ALLOWANCE > 0.015


def test_frame_matches_the_assembly_c2c() -> None:
    assert stack.FRAME_C2C == pytest.approx(39.735, abs=0.001)
    assert stack.FRAME_DY == pytest.approx(39.332, abs=1e-9)
    assert stack.SPACING_PRINTED == 39.07
