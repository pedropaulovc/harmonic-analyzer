"""Offline contracts for the magnifying-vertical-rod drawing (#1559)."""

from __future__ import annotations

import math

import pytest

import build_mg_magnifying_vertical_rod as part
import draw_mg_magnifying_vertical_rod as drawing
import mg_magnifying_vertical_rod_geom as geom
import mg_magnifying_vertical_rod_spec as spec
import mg_rod_clamp_joint as joint
from _printed_tolerance import printed_band_mm


def test_rod_is_the_threaded_bar_of_the_joint_contract() -> None:
    # As-bought 7/32 brass rod; the shoulder station keeps its 7.50 mm model.
    assert spec.ROD_DIA == pytest.approx(7.0 / 32.0 * 25.4)
    # The sheet prints the supplier band the fits are judged at.
    assert spec.ROD_DIA_CALLOUT.endswith(f"<MOD-PM>{geom.ROD_DIA_BAND[0] / 25.4:.3f}".replace("0.", "."))
    assert spec.ROD_LENGTH == pytest.approx(spec.SHOULDER_X + spec.BODY_LENGTH)
    assert spec.SHOULDER_X == spec.ROD_THREAD_LEN == joint.ROD_THREAD_LEN == 7.50
    # The relief mates with nothing (r1): its width at the title block's .XX
    # band, its Ø as the single limit MAX (the model value is the limit).
    band = printed_band_mm(joint.RELIEF_WIDTH_PLACES, unit="in")
    assert joint.PRINTED_XX_BAND == pytest.approx(band)
    assert (joint.RELIEF_WIDTH_MIN, joint.RELIEF_WIDTH_MAX) == pytest.approx(
        (spec.RELIEF_WIDTH - band, spec.RELIEF_WIDTH + band)
    )
    assert spec.RELIEF_DIA == joint.RELIEF_DIA_MAX
    assert spec.RELIEF_DIA_TOL_TYPE == 6  # swTolType_e.swTolMAX
    assert spec.THREAD == "#4-40"
    assert spec.THREAD_MAJOR == pytest.approx(2.845, abs=1e-3)
    assert spec.TIP_CHAMFER == pytest.approx(
        (spec.THREAD_MAJOR - spec.THREAD_BASIC_MINOR) / 2.0
    )
    assert spec.RELIEF_START_X == pytest.approx(spec.SHOULDER_X - spec.RELIEF_WIDTH)
    # Full thread only (rule 18): one pitch at the tip, the run-out in the
    # relief; the worst-case engagement holds 1.5D.
    assert spec.FULL_THREAD_START_X == pytest.approx(0.635)
    assert spec.FULL_THREAD_END_X == pytest.approx(spec.RELIEF_START_X)
    assert joint.ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN == pytest.approx(4.2675)
    assert joint.RELIEF_WIDTH_MIN >= joint.DIE_RUNOUT
    assert joint.RELIEF_DIA_MAX <= joint.THREAD_ROOT_2A_MIN
    assert geom.SEAT_LAND_WORST >= geom.SEAT_LAND_MIN
    assert spec.RELIEF_ROOT_R == joint.RELIEF_ROOT_R


def test_relief_root_volume_matches_the_revolved_spandrels() -> None:
    # Each root fills a (1 - pi/4) R^2 spandrel turned about the axis at its
    # centroid (Pappus): ~0.1 mm^3, far inside the 0.5 % volume gate.
    rr, q = spec.RELIEF_ROOT_R, spec.RELIEF_DIA / 2.0
    centroid = q + rr * (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi)
    roots = 2.0 * 2.0 * math.pi * centroid * (1.0 - math.pi / 4.0) * rr * rr
    assert part.V_TOTAL - part.V_PROFILE == pytest.approx(roots)
    assert 0.0 < roots < 0.005 * part.V_PROFILE


def test_profile_volume_matches_the_stepped_rod_and_dome() -> None:
    r, t, m, q = (
        spec.ROD_DIA / 2.0,
        spec.THREAD_MAJOR / 2.0,
        spec.THREAD_BASIC_MINOR / 2.0,
        spec.RELIEF_DIA / 2.0,
    )
    c = spec.TIP_CHAMFER
    v = (
        math.pi * c / 3.0 * (m * m + m * t + t * t)
        + math.pi * t * t * (spec.RELIEF_START_X - c)
        + math.pi * q * q * spec.RELIEF_WIDTH
        + math.pi * r * r * (spec.BODY_LENGTH - r)
        + 2.0 / 3.0 * math.pi * r**3
    )
    assert part.V_PROFILE == pytest.approx(v)


def test_relief_root_radius_reads_clear_in_detail_a() -> None:
    """The "2X R MAX" stands under the thread, opposite the shoulder's
    lower root arc; its leader toward the root centre passes under the Ø's
    lower arrow stub and the Ø's line stays off the thread-side root."""
    x_mm, y_mm = drawing.RELIEF_ROOT_CENTRE_MM
    assert (x_mm, y_mm) == pytest.approx(
        (spec.SHOULDER_X - spec.RELIEF_ROOT_R, -(spec.RELIEF_DIA / 2.0 + spec.RELIEF_ROOT_R))
    )
    cx, cy = drawing._detail_xy(x_mm, y_mm)
    tx, ty = drawing.DETAIL_KEEP["ReliefRootR"]
    # Down-left of the centre: opposite the arc's up-right quarter, so the
    # arrow lands on the arc's extension, the circle's down-left side.
    assert tx < cx and ty < cy
    # Under the thread's lower silhouette, over the thread length's block and
    # right of its tip extension line.
    thread_bottom = drawing._detail_xy(0.0, -spec.THREAD_MAJOR / 2.0)[1]
    assert thread_bottom - ty >= 0.015
    assert ty - drawing.DETAIL_KEEP["ThreadLength"][1] >= 0.020
    assert tx - 0.012 > drawing._detail_xy(0.0, 0.0)[0]
    # The leader from the text's right end (~10 mm from its centre) passes
    # >= 8 mm under the relief's lower silhouette at the Ø's line.
    dia_x = drawing.DETAIL_KEEP["ReliefDia"][0]
    end_x = tx + 0.010
    leader_y = cy + (cy - ty) / (cx - end_x) * (dia_x - cx)
    relief_bottom = drawing._detail_xy(0.0, -spec.RELIEF_DIA / 2.0)[1]
    assert end_x < dia_x < cx
    assert relief_bottom - leader_y >= 0.008
    # The Ø's line meets the floor >= 2 mm (sheet) clear of the thread-side
    # root's tangent.
    tangent_x = drawing._detail_xy(spec.RELIEF_START_X + spec.RELIEF_ROOT_R, 0.0)[0]
    assert dia_x - tangent_x >= 0.002
    # The root's far edge (its tangent on the shoulder face) stays inside the
    # fence, so the crop keeps it.
    fx, fy = drawing.DETAIL_FOCUS_MM
    assert math.hypot(spec.SHOULDER_X - fx, y_mm - fy) < drawing.DETAIL_RADIUS_MM


def test_upper_root_radius_reads_clear_over_the_body() -> None:
    """Landed on the mirror-image upper root, the "2X R MAX" stands over the
    body just right of the shoulder: its leader from the text's left end
    toward the root centre stays between the Ø's line and the shoulder face,
    and the text clears the body and the Ø's value."""
    x_mm, y_mm = drawing.UPPER_RELIEF_ROOT_CENTRE_MM
    assert (x_mm, y_mm) == pytest.approx(
        (spec.SHOULDER_X - spec.RELIEF_ROOT_R, spec.RELIEF_DIA / 2.0 + spec.RELIEF_ROOT_R)
    )
    cx, cy = drawing._detail_xy(x_mm, y_mm)
    tx, ty = drawing.UPPER_ROOT_KEEP["ReliefRootR"]
    end_x = tx - 0.011  # the text's left end, ~11 mm from its centre
    body_top = drawing._detail_xy(0.0, spec.ROD_DIA / 2.0)[1]
    shoulder_x = drawing.DETAIL_SHOULDER_X
    dia_x, dia_y = drawing.DETAIL_KEEP["ReliefDia"]
    # The leader reaches the body's top >= 2 mm left of the shoulder face,
    # and stays >= 3 mm right of the Ø's line all the way down.
    leader_x = end_x + (cx - end_x) * (ty - body_top) / (ty - cy)
    assert shoulder_x - leader_x >= 0.002
    assert min(end_x, cx) - dia_x >= 0.003
    # The tip lands on the circle's upper half, facing the text.
    assert ty > cy
    # Text >= 6 mm over the body and >= 10 mm under the Ø's value.
    assert ty - body_top >= 0.006
    assert dia_y - ty >= 0.010
    # The fence keeps the upper root.
    fx, fy = drawing.DETAIL_FOCUS_MM
    assert math.hypot(spec.SHOULDER_X - fx, y_mm - fy) < drawing.DETAIL_RADIUS_MM


def _fixture_screw_reach() -> tuple[float, float]:
    """Rod stations (from the thread tip) the MHA-MG-06 thumb screw can bear
    on: its axis rides the fixture's hex axis, the hex reaches a corner radius
    along the rod each way (its top corner stops on MHA-MG-02's bottom face,
    at the shoulder; its bore stays on the body down to the dome tangent), and
    the tip widens the band by its radius."""
    import mg_output_fixture_geom as fixture
    from sh_vn_thumb_screw_spec import SHANK_DIA

    half = fixture.HEX_CORNER_RADIUS
    tip = SHANK_DIA / 2.0
    return (
        spec.SHOULDER_X + half - tip,
        spec.ROD_LENGTH - spec.DOME_R - half + tip,
    )


def test_fixture_thumb_screw_bears_on_the_as_bought_body() -> None:
    """MHA-MG-06's axial thumb screw (MHA-SH-VN-55) locks the fixture wherever
    the operator sets it along the rod (ch. 20 p. 46). Its reach lies on the
    body's one 7/32 cylinder and covers nearly all of it. No MHA-MG-02 screw
    bears on the rod."""
    import build_mg_magnifier_assembly as assembly
    import mg_magnifying_clamp_geom as clamp
    import mg_output_fixture_geom as fixture

    # The body, shoulder to dome tangent, is the part's only full-Ø cylinder.
    assert spec.RELIEF_DIA < spec.THREAD_MAJOR < spec.ROD_DIA
    body = (spec.SHOULDER_X, spec.ROD_LENGTH - spec.DOME_R)
    reach = _fixture_screw_reach()
    assert body[0] < reach[0] < reach[1] < body[1]
    assert (reach[1] - reach[0]) / (body[1] - body[0]) > 0.9
    # The compensated installation keeps the hook fixed under the thread tip,
    # the screw's tip tangent to the rod.
    station = assembly.VROD_TOP_Y - fixture.FIXTURE_AXIS_Y
    half = fixture.HEX_CORNER_RADIUS
    assert body[0] + half <= station <= body[1] - half
    assert assembly.FIXTURE_SCREW_TIP_X == spec.ROD_DIA / 2.0
    # MHA-MG-02: its thumb screw enters the top face and stops on the lever
    # (the drill to the lever bore's axis); the rod's threaded end, screwed
    # into the bottom face, stops under that bore, so no clamp screw meets it.
    assert clamp.THUMB_TAP_DRILL_DEPTH == pytest.approx(
        clamp.BLOCK_HEIGHT - clamp.LEVER_BORE_Y
    )
    assert spec.SHOULDER_X < clamp.LEVER_BORE_Y - clamp.LEVER_BORE_DIA / 2.0


def test_detail_crop_contains_the_tip_and_shoulder() -> None:
    # The fence holds the tip face and the shoulder's outer corner.
    fx, fy = drawing.DETAIL_FOCUS_MM
    for x, y in ((0.0, 0.0), (spec.SHOULDER_X, spec.ROD_DIA / 2.0)):
        assert math.hypot(x - fx, y - fy) < drawing.DETAIL_RADIUS_MM
