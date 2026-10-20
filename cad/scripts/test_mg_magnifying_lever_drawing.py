"""Offline physical interval/fit/travel checks for the threaded MG lever."""

from __future__ import annotations

import itertools
import math

import pytest

import build_mg_magnifier_assembly as assembly
import draw_mg_magnifying_lever as drawing
import mg_lever_thread_joint as joint
import mg_magnifier_assembly_spec as installed
import mg_magnifying_clamp_geom as clamp
import mg_magnifying_lever_geom as geom
import mg_magnifying_lever_spec as spec
from _printed_tolerance import drilled_oversize_mm


def _intersection(first, second):
    return max(0.0, min(first[1], second[1]) - max(first[0], second[0]))


def test_installed_full_thread_excludes_both_leads_and_both_mouths() -> None:
    overlaps = []
    for length, thread, thickness in itertools.product(
        (joint.ROD_LENGTH - joint.ROD_LENGTH_TOL, joint.ROD_LENGTH + joint.ROD_LENGTH_TOL),
        (joint.THREAD_LENGTH - joint.THREAD_LENGTH_TOL, joint.THREAD_LENGTH + joint.THREAD_LENGTH_TOL),
        (joint.NECK_THICKNESS - joint.NECK_THICKNESS_TOL, joint.NECK_THICKNESS + joint.NECK_THICKNESS_TOL),
    ):
        receiver = (geom.BRACKET_LOCAL_X - thickness / 2.0 + joint.MOUTH_CHAMFER_MAX, geom.BRACKET_LOCAL_X + thickness / 2.0 - joint.MOUTH_CHAMFER_MAX)
        male = (length - thread + joint.INCOMPLETE_THREAD_MAX, length - joint.INCOMPLETE_THREAD_MAX)
        overlaps.append(_intersection(receiver, male))
        assert length >= geom.BRACKET_LOCAL_X + thickness / 2.0
    assert geom.FULL_THREAD_OVERLAP_MIN <= min(overlaps) + 1e-9
    assert geom.FULL_THREAD_OVERLAP_MIN >= joint.REQUIRED_FULL_ENGAGEMENT
    assert geom.FULL_THREAD_OVERLAP_MIN == pytest.approx(10.745)


def test_native_tip_projection_guarantees_full_overlap_independently_of_part_length() -> None:
    overlaps = []
    for thickness, projection, thread in itertools.product(
        (joint.NECK_THICKNESS - joint.NECK_THICKNESS_TOL, joint.NECK_THICKNESS + joint.NECK_THICKNESS_TOL),
        (installed.THREAD_PROJECTION - installed.THREAD_PROJECTION_TOL, installed.THREAD_PROJECTION + installed.THREAD_PROJECTION_TOL),
        (joint.THREAD_LENGTH - joint.THREAD_LENGTH_TOL, joint.THREAD_LENGTH + joint.THREAD_LENGTH_TOL),
    ):
        tip = thickness + projection
        overlaps.append(_intersection((joint.MOUTH_CHAMFER_MAX, thickness - joint.MOUTH_CHAMFER_MAX), (tip - thread + joint.INCOMPLETE_THREAD_MAX, tip - joint.INCOMPLETE_THREAD_MAX)))
    assert installed.INSTALLED_FULL_ENGAGEMENT_MIN <= min(overlaps) + 1e-9
    assert installed.INSTALLED_FULL_ENGAGEMENT_MIN >= joint.REQUIRED_FULL_ENGAGEMENT
    assert installed.THREAD_PROJECTION - installed.THREAD_PROJECTION_TOL > 0.0


@pytest.mark.parametrize("change", ({"thickness": 11.0}, {"thread_length": 14.0}, {"incomplete": 3.5}, {"projection_tol": 2.0}))
def test_full_thread_proof_detects_short_neck_thread_and_overlong_runout(change) -> None:
    arguments = {"projection_tol": installed.THREAD_PROJECTION_TOL, **change}
    overlap = joint.installation_full_overlap(installed.THREAD_PROJECTION, **arguments)
    assert overlap < joint.REQUIRED_FULL_ENGAGEMENT


def test_root_runout_is_wholly_outside_receiver_at_actual_printed_corners() -> None:
    latest_full_start = joint.ROD_LENGTH + joint.ROD_LENGTH_TOL - (joint.THREAD_LENGTH - joint.THREAD_LENGTH_TOL) + joint.INCOMPLETE_THREAD_MAX
    earliest_near_face = geom.BRACKET_LOCAL_X - (joint.NECK_THICKNESS + joint.NECK_THICKNESS_TOL) / 2.0
    assert latest_full_start < earliest_near_face
    assert geom.ROOT_RUNOUT_CLEARANCE_MIN == pytest.approx(earliest_near_face - latest_full_start)
    assert spec.SINGLE_LIMITS["ThreadExtent", "IncompleteLength"][0] == joint.INCOMPLETE_THREAD_MAX


def test_quarter_inch_body_has_real_drilled_slip_clearance() -> None:
    stock_low = joint.ROD_DIA + joint.ROD_DIA_BAND[1]
    stock_high = joint.ROD_DIA + joint.ROD_DIA_BAND[0]
    minimum = clamp.LEVER_BORE_DIA - stock_high
    maximum = clamp.LEVER_BORE_DIA + drilled_oversize_mm() - stock_low
    assert minimum == pytest.approx(0.15)
    assert maximum == pytest.approx(0.30)
    assert minimum > 0.0 and maximum < 0.5


def test_clamp_entire_bore_stays_on_plain_body_at_nominal_travel_limits() -> None:
    radii = geom.clamp_radius_band(clamp.BLOCK_DEPTH)
    centres = [geom.KNIFE_LOCAL_X - radius for radius in radii]
    half = clamp.BLOCK_DEPTH / 2.0
    assert max(centres) + half <= joint.THREAD_ROOT_X
    assert min(centres) - half >= -1e-9
    assert centres[1] == geom.CLAMP_LOCAL_X
    assert assembly.LEVER_X0 - geom.BRACKET_LOCAL_X == assembly.BRACKET_X
    assert assembly.LEVER_X0 - geom.KNIFE_LOCAL_X == assembly.KNIFE[0]


def test_small_thread_requirements_have_a_legible_enlarged_native_home() -> None:
    kept = [*drawing.FRONT_KEEP, *drawing.DETAIL_KEEP]
    assert len(kept) == len(set(kept))
    assert set(kept) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] > drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1]
    # Every actual rod corner at the threaded flat end lies inside its circle.
    tip_offset = joint.ROD_LENGTH - drawing.DETAIL_FOCUS[0] * 1000.0
    assert math.hypot(tip_offset, joint.ROD_DIA / 2.0) < drawing.DETAIL_RADIUS_MM
