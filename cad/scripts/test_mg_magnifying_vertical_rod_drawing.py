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
    assert (spec.ROD_DIA, spec.ROD_LENGTH) == (5.0, 132.5)
    assert spec.BODY_LENGTH == 125.0
    assert spec.SHOULDER_X == spec.ROD_THREAD_LEN == joint.ROD_THREAD_LEN == 7.50
    assert spec.ROD_THREAD_LEN_BAND == joint.ROD_THREAD_LEN_BAND == (0.25, -0.25)
    # The relief mates with nothing (r1): its width at the title block's .XX
    # band, its Ø as the single limit MAX (the model value is the limit).
    assert (spec.RELIEF_WIDTH, joint.RELIEF_WIDTH_PLACES) == (1.50, 2)
    assert joint.PRINTED_XX_BAND == printed_band_mm(joint.RELIEF_WIDTH_PLACES)
    assert (joint.RELIEF_WIDTH_MIN, joint.RELIEF_WIDTH_MAX) == pytest.approx((0.99, 2.01))
    assert spec.RELIEF_DIA == joint.RELIEF_DIA_MAX == 1.85
    assert spec.RELIEF_DIA_TOL_TYPE == 6  # swTolType_e.swTolMAX
    assert spec.THREAD == "#4-40"
    assert spec.THREAD_MAJOR == pytest.approx(2.845, abs=1e-3)
    assert spec.TIP_CHAMFER == pytest.approx(
        (spec.THREAD_MAJOR - spec.THREAD_BASIC_MINOR) / 2.0
    )
    assert spec.RELIEF_START_X == pytest.approx(7.50 - 1.50)
    # Full thread only (rule 18): one pitch at the tip, the run-out in the
    # relief; the worst-case engagement holds 1.5D.
    assert spec.FULL_THREAD_START_X == pytest.approx(0.635)
    assert spec.FULL_THREAD_END_X == pytest.approx(spec.RELIEF_START_X)
    assert joint.ENGAGEMENT_WORST == pytest.approx(7.25 - 2.01 - 0.635)
    assert joint.ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN == pytest.approx(4.2675)
    assert joint.RELIEF_WIDTH_MIN >= joint.DIE_RUNOUT
    assert joint.RELIEF_DIA_MAX <= joint.THREAD_ROOT_2A_MIN
    assert geom.SEAT_LAND_WORST >= geom.SEAT_LAND_MIN
    # Both relief roots "R0.2 MAX" (r2): the model at the printed limit.
    assert spec.RELIEF_ROOT_R == joint.RELIEF_ROOT_R == 0.2


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
    """The "2X R0.2 MAX" stands under the thread, opposite the shoulder's
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


def test_body_cylinder_is_the_fixture_thumb_screw_seat() -> None:
    """Owner ruling 2026-10-17 (rule 6, a static seat, Ra 3.2): MHA-MG-06's
    axial thumb screw (MHA-SH-VN-55) locks the fixture wherever the operator
    sets it along the rod (ch. 20 p. 46). Its reach lies on the body's one Ø5
    cylinder and covers nearly all of it, so the control qualifies that whole
    face, with no zone lengths. No MHA-MG-02 screw bears on the rod."""
    import build_mg_magnifier_assembly as assembly
    import mg_magnifying_clamp_geom as clamp
    import mg_output_fixture_geom as fixture
    from _gtol_cylinder import CylinderFace
    from _surface_finish import SEAT, SEAT_UM, SurfaceFinishControl, surface_finish_by_key

    assert spec.SURFACE_FINISHES == (
        SurfaceFinishControl("screw_seat", SEAT_UM, CylinderFace(spec.ROD_DIA)),
    )
    control = surface_finish_by_key(spec.SURFACE_FINISHES, "screw_seat")
    assert control.roughness_ra == SEAT == "3.2"
    # The Ø5 body, shoulder to dome tangent, is the part's only Ø5 cylinder.
    assert spec.RELIEF_DIA < spec.THREAD_MAJOR < spec.ROD_DIA
    body = (spec.SHOULDER_X, spec.ROD_LENGTH - spec.DOME_R)
    reach = _fixture_screw_reach()
    assert body[0] < reach[0] < reach[1] < body[1]
    assert reach[0] - spec.SHOULDER_X == pytest.approx(4.993, abs=1e-3)
    assert spec.ROD_LENGTH - reach[1] == pytest.approx(7.493, abs=1e-3)
    assert (reach[1] - reach[0]) / (body[1] - body[0]) > 0.9
    # The compensated installation keeps the hook fixed, 47.55 under the tip.
    # under the thread tip, its tip tangent to the rod.
    station = assembly.VROD_TOP_Y - fixture.FIXTURE_AXIS_Y
    assert station == pytest.approx(47.55, abs=1e-9)
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


def test_seat_finish_reason_reads_at_its_symbol() -> None:
    """The symbol lands on the body's top silhouette inside the screw's reach;
    its reason reads on the symbol's own row, just right of its "Ra 3.2" (r4
    review: a label floating near detail A did not read as the symbol's),
    clear of detail A's stack and of the Ø value. Ink sizes are the r5 farm
    render's (20261017T070700133Z) measures against each anchor."""
    pick_x, pick_y = drawing.SEAT_FINISH_PICK
    assert pick_y == pytest.approx(
        drawing.SIDE_CENTER[1] + spec.ROD_DIA / 2.0 * drawing._S / 1000.0
    )
    model_x = (pick_x - drawing.SIDE_CENTER[0]) * 1000.0 / drawing._S + drawing._MID_X
    reach = _fixture_screw_reach()
    assert reach[0] < model_x < reach[1]
    symbol_x, symbol_y = drawing.SEAT_FINISH_SYMBOL
    reason_x, reason_y = drawing.SEAT_REASON_XY
    assert pick_y < symbol_y and abs(symbol_x - pick_x) < 0.005
    # The symbol's "Ra 3.2" ends 14.9 mm right of its anchor and spans 3.7..
    # 7.0 mm over it; the reason (a note: position = top-left) prints 3.9 mm
    # tall and 2.8 mm a character.
    ra_right = symbol_x + 0.0149
    ra_mid_y = symbol_y + (0.0037 + 0.0070) / 2.0
    reason_right = reason_x + 0.0028 * len(spec.SEAT_FINISH_REASON)
    reason_mid_y = reason_y - 0.0039 / 2.0
    assert 0.001 < reason_x - ra_right < 0.005  # beside it, not touching
    assert abs(reason_mid_y - ra_mid_y) < 0.001  # on its row
    # Clear of the Ø value's text (~12.5 mm left of its dimension line).
    assert reason_right < drawing.SIDE_KEEP["RodDia"][0] - 0.0125 - 0.010
    # The symbol's leader shoulder (~5 mm left of its anchor) stands right of
    # detail A's shoulder extension line, and its top (8 mm over the anchor)
    # under the detail's thread-length row (dimension line ~33 mm under the
    # crop's bottom).
    assert symbol_x - 0.005 > drawing.DETAIL_SHOULDER_X + 0.008
    assert symbol_y + 0.008 < drawing._DETAIL_BOTTOM - 0.030
    assert reason_y < drawing._DETAIL_BOTTOM - 0.030


def test_detail_crop_contains_the_tip_and_shoulder() -> None:
    # The fence holds the tip face and the shoulder's outer corner.
    fx, fy = drawing.DETAIL_FOCUS_MM
    for x, y in ((0.0, 0.0), (spec.SHOULDER_X, spec.ROD_DIA / 2.0)):
        assert math.hypot(x - fx, y - fy) < drawing.DETAIL_RADIUS_MM
