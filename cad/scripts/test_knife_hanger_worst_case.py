"""Worst case of the cut #10-24 plain hex knife hanger (MHA-SM-VN-52
in MHA-SM-02, new SAE washer, keyed by MHA-SM-VN-53), from real spec constants.

The retired 1/2-13 hanger broke its tap-drill point into the knife bore crown
and needed a drawing exception. The current proof charges the printed depth,
diameter and toolpoint-angle limits under cad/docs/drawing-guidelines.md:
rule 17 (walls and webs), rule 18 (thread engagement) and rule 19 (absorb
stacks). Even the old nominal toolpoint calculation fails. SolidWorks-free.
"""

from __future__ import annotations

import math

import pytest

import _ha_harmonic_analyzer_interference as top_interference
import _sm_summing_interference as summing_interference
import build_fr_top_frame
import build_sm_knife_mount
import build_sm_summing_assembly as asm
import fr_top_frame_spec as top_frame
import sm_knife_mount_spec as knife_mount
import sm_summing_lever_spec as lever
import sm_vn_knife_hanger_stud_spec as screw
import sm_vn_knife_hanger_washer_spec as washer
import sm_vn_knife_mount_dowel_spec as dowel
from _hole_spec import CLEARANCE_MM, TAP_DRILL_MM, THREAD_MAJOR_MM
from _printed_tolerance import drilled_oversize_mm


def test_the_tap_point_leaves_the_web_over_the_bore_crown() -> None:
    assert knife_mount.STUD_TAP_WEB_MIN == pytest.approx(2.032)  # .080
    # Reamed bore largest, axis highest, drill deepest, and the accepted
    # native toolpoint at its smallest included angle. The pilot proof
    # deliberately charges more diameter than the native accepted maximum.
    assert knife_mount.STUD_TAP_DIA == pytest.approx(3.797)
    assert knife_mount.STUD_TAP_DIA_BAND == pytest.approx((0.1016, 0.0))
    assert knife_mount.STUD_TAP_DIA_ACCEPTED == pytest.approx(
        (0.1495 * 25.4, 0.1495 * 25.4 + 0.1016), abs=1e-12
    )
    assert knife_mount.STUD_TAP_DIA_OVERSIZE == pytest.approx(
        max(knife_mount._XXX, drilled_oversize_mm(unit=knife_mount.UNIT))
    )
    assert knife_mount.STUD_TAP_DIA_OVERSIZE == pytest.approx(0.127)
    assert knife_mount.STUD_TAP_DIA_MAX == pytest.approx(3.924)
    assert knife_mount.STUD_TAP_DIA_MAX > max(knife_mount.STUD_TAP_DIA_ACCEPTED)
    assert knife_mount.STUD_TAP_POINT_ANGLE_DEG == pytest.approx(118.0)
    assert knife_mount.STUD_TAP_POINT_ANGLE_MIN_DEG == pytest.approx(117.0)
    point_height = 3.924 / (2.0 * math.tan(math.radians(117.0 / 2.0)))
    assert point_height == pytest.approx(1.2023151463)
    assert knife_mount.STUD_TAP_POINT_H == pytest.approx(point_height)
    assert knife_mount.STUD_TAP_DRILL_DEPTH_MAX == pytest.approx(11.176)
    # Top 14.866: crown depth 14.605, less the bore's position radius
    # (Ø.008, owner ruling 2026-10-27), bore radius oversize, maximum
    # cylindrical drill depth and point height.
    assert knife_mount.STUD_TAP_WEB_WORST == pytest.approx(
        14.605 - 0.1016 - 0.01905 - 11.176 - point_height
    )
    assert knife_mount.STUD_TAP_WEB_WORST == pytest.approx(2.1060348537)
    assert knife_mount.STUD_TAP_WEB_WORST >= knife_mount.STUD_TAP_WEB_MIN
    # The built top is the spec's 14.866.
    built = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        knife_mount.STUD_TAP_DRILL_DEPTH,
        knife_mount.STUD_TAP_DIA,
    )
    assert built == pytest.approx(2.1060348537)
    assert build_sm_knife_mount._TAP_WEB_WORST == pytest.approx(built)
    assert built >= knife_mount.STUD_TAP_WEB_MIN
    # A .004 wider drill-depth band consumes the remaining functional web.
    assert (
        knife_mount.tap_web_worst(
            build_sm_knife_mount.BLK_TOP,
            knife_mount.STUD_TAP_DRILL_DEPTH,
            knife_mount.STUD_TAP_DIA,
            drill_band=knife_mount.STUD_TAP_DRILL_DEPTH_BAND + 0.1016,
        )
        < knife_mount.STUD_TAP_WEB_MIN
    )


@pytest.mark.parametrize(
    ("drill_dia_oversize", "point_angle_deg"),
    [(0.0, 117.0), (0.13, 118.0), (0.0, 118.0)],
)
def test_omitting_pilot_oversize_or_point_angle_overstates_the_crown_web(
    drill_dia_oversize: float, point_angle_deg: float
) -> None:
    charged = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        knife_mount.STUD_TAP_DRILL_DEPTH,
        knife_mount.STUD_TAP_DIA,
    )
    undercharged = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        knife_mount.STUD_TAP_DRILL_DEPTH,
        knife_mount.STUD_TAP_DIA,
        drill_dia_oversize=drill_dia_oversize,
        point_angle_deg=point_angle_deg,
    )
    assert undercharged > charged


def test_previous_drill_depth_fails_when_pilot_and_point_limits_are_charged() -> None:
    # The mm sheet's deepest drill, 11.29, leaves no .080 web at the charged
    # pilot and point, nor even with the nominal pilot at an exact 118 deg.
    charged = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        11.29,
        knife_mount.STUD_TAP_DIA,
    )
    optimistic = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        11.29,
        knife_mount.STUD_TAP_DIA,
        drill_dia_oversize=0.0,
        point_angle_deg=118.0,
    )
    assert optimistic == pytest.approx(2.0028161148, abs=5e-6)
    assert charged == pytest.approx(1.9412348537)
    assert charged < optimistic < knife_mount.STUD_TAP_WEB_MIN


def test_the_tap_drill_runs_a_pitch_past_the_full_thread() -> None:
    # Full thread keeps its explicit functional ±.005 at three printed
    # places; the drill has its explicit ±.002 depth band. Nominal runout
    # 1.60 >= 1.5P.
    assert knife_mount.STUD_TAP_THREAD_DEPTH == pytest.approx(9.525)  # .375
    assert knife_mount.STUD_TAP_THREAD_DEPTH_BAND == knife_mount._XXX
    assert knife_mount._XXX == pytest.approx(0.127)
    assert knife_mount.STUD_TAP_THREAD_DEPTH_MIN == pytest.approx(9.398)
    assert knife_mount.STUD_TAP_DRILL_DEPTH == pytest.approx(11.1252)  # .438
    assert knife_mount.STUD_TAP_DRILL_DEPTH_BAND == pytest.approx(0.0508)
    assert knife_mount.STUD_TAP_RUNOUT == pytest.approx(1.6002)
    assert knife_mount.STUD_TAP_RUNOUT >= 1.5 * knife_mount.STUD_PITCH
    assert knife_mount.STUD_TAP_RUNOUT_MIN == pytest.approx(1.4224)
    assert knife_mount.STUD_TAP_RUNOUT_MIN == pytest.approx(
        knife_mount.STUD_TAP_DRILL_DEPTH
        - knife_mount.STUD_TAP_DRILL_DEPTH_BAND
        - knife_mount.STUD_TAP_THREAD_DEPTH
        - knife_mount.STUD_TAP_THREAD_DEPTH_BAND
    )
    assert knife_mount.STUD_PITCH == pytest.approx(25.4 / 24)
    assert knife_mount.STUD_TAP_RUNOUT_MIN >= knife_mount.STUD_PITCH


def test_the_retired_half_inch_tap_fails_the_same_web_formula() -> None:
    # Historical optimistic calculation, NOT an accepted stock bound: nominal
    # 1/2-13 pilot at exact 118 degrees still broke into the crown under the
    # old 14.62 top (MOUNT_GAP 0.25), even before charging pilot and angle bands.
    old = knife_mount.tap_web_worst(
        14.62,
        12.0,
        TAP_DRILL_MM["1/2-13"],
        drill_band=0.51,  # the retired mm sheet's .XX
        bore_oversize=0.51,
        drill_dia_oversize=0.0,
        point_angle_deg=118.0,
    )
    assert old == pytest.approx(-1.727, abs=5e-4)
    assert old < knife_mount.STUD_TAP_WEB_MIN


def test_the_screw_reach_holds_engagement_and_stays_in_the_thread() -> None:
    asm._assert_knife_hanger_stack()
    assert asm.MOUNT_GAP == 0.0
    assert asm.CROSSBAR_TOP_Y == pytest.approx(top_frame.TOP_FRAME_RAIL_TOP_Y)
    assert asm.HANGER_WASHER_Y == pytest.approx(top_frame.TOP_FRAME_RAIL_TOP_Y)
    assert asm.HANGER_UNDERHEAD_Y == pytest.approx(1037.4757)
    assert asm.HANGER_STUD_Y == pytest.approx(990.7757)
    assert asm.HANGER_REACH == pytest.approx(8.9175)
    # MHA-SM-00 cuts each bolt to its measured stack plus .351, title-block
    # +/-.005 in.
    assert asm.HANGER_REACH_MIN == pytest.approx(8.7884)
    assert asm.HANGER_REACH_MAX == pytest.approx(9.0424)
    # Cut-tip lead costs one incomplete pitch: 7.7300667 >= 1.5D =7.239.
    assert asm.HANGER_ENGAGEMENT_MIN == pytest.approx(
        asm.HANGER_REACH_MIN - screw.INCOMPLETE_TIP_LEN_MAX
    )
    assert screw.INCOMPLETE_TIP_LEN_MAX == screw.PITCH
    assert asm.HANGER_ENGAGEMENT_MIN == pytest.approx(7.7300666667)
    assert asm.HANGER_ENGAGEMENT_FLOOR == pytest.approx(1.5 * screw.SHANK_DIA)
    assert asm.HANGER_ENGAGEMENT_MIN >= asm.HANGER_ENGAGEMENT_FLOOR
    assert asm.HANGER_ENGAGEMENT_FLOOR == pytest.approx(7.239)
    # Full tap's shallowest limit stays 0.36 beyond the longest reach.
    assert knife_mount.STUD_TAP_THREAD_DEPTH_MIN == pytest.approx(9.398)
    assert asm.HANGER_REACH_MAX <= knife_mount.STUD_TAP_THREAD_DEPTH_MIN
    assert asm.HANGER_TIP_CLEARANCE == pytest.approx(0.3556)
    # Modified-part incoming inspection proves this cut tail's full form;
    # catalogue "fully threaded" is not assumed to specify thread-to-head.
    assert screw.THREAD_LENGTH_MIN == pytest.approx(10.6172)  # .418 MIN
    assert screw.FULL_FORM_TAIL_MIN == pytest.approx(9.5588666667)
    assert asm.HANGER_THREAD_SPARE == pytest.approx(0.5164666667)
    assert (
        screw.THREAD_LENGTH_MIN - screw.INCOMPLETE_TIP_LEN_MAX >= asm.HANGER_REACH_MAX
    )
    assert asm.HANGER_SCREW_CLEARANCE == pytest.approx(1.3208)
    assert washer.THICKNESS == pytest.approx(1.2827)


def test_the_dowel_presses_deep_enough_and_never_bottoms_the_slip_hole() -> None:
    # Owner ruling 2026-10-24 (T+H3): each pin presses .47 up into the
    # crossbar's blind ream and slips .37 deep into the knife mount.
    assert dowel.PRESS_DEPTH == top_frame.HANGER_PIN_HOLE_DEPTH == pytest.approx(11.938)
    assert dowel.SLIP_DEPTH == knife_mount.PIN_HOLE_DEPTH == pytest.approx(9.398)
    assert dowel.PROUD == pytest.approx(7.112)
    # The longest proud pin carries the ream floor's corner lift: its largest
    # end flat sits on the R.003 MAX fillet (codjiflo round 5).
    assert dowel.PRESS_FLOOR_LIFT_MAX == pytest.approx(0.0043557, abs=5e-6)
    assert (dowel.PROUD_MIN, dowel.PROUD_MAX) == pytest.approx(
        (6.604, 7.62 + dowel.PRESS_FLOOR_LIFT_MAX)
    )
    assert dowel.SLIP_DEPTH_CLEARANCE_MIN == pytest.approx(1.519644, abs=5e-6)
    assert dowel.SLIP_DEPTH_CLEARANCE_MIN > 0.0
    assert dowel.PRESS_ENGAGEMENT_D_MIN == pytest.approx(3.5405, abs=5e-4)
    assert dowel.PRESS_ENGAGEMENT_D_MIN >= dowel.PRESS_ENGAGEMENT_MIN_D == 1.5
    # The slip keys over the shortest proud pin short of its rounded free end.
    assert dowel.SLIP_ENGAGEMENT_D_MIN == pytest.approx(
        (dowel.PROUD_MIN - dowel.FREE_END_LEN) / dowel.DIA
    )
    assert dowel.SLIP_ENGAGEMENT_D_MIN == pytest.approx(1.952, abs=5e-6)
    assert dowel.SLIP_ENGAGEMENT_D_MIN >= dowel.PRESS_ENGAGEMENT_MIN_D
    # F2: the ream's .1240 H7 (+.0005/0) band keeps the press at both
    # catalogue limits.
    assert dowel.PRESS_HOLE_DIA == pytest.approx(3.1496)
    assert dowel.PRESS_HOLE_DIA_BAND == pytest.approx((0.0127, 0.0))
    assert dowel.PRESS_INTERFERENCE == pytest.approx((0.01524, 0.03302))
    assert dowel.PRESS_INTERFERENCE[0] > 0.0
    assert dowel.PRESS_INTERFERENCE_PRINTED == pytest.approx((0.0152, 0.0331))
    # Owner ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1): one dowel
    # per mount, at the +X station (datum B) on both parts; no -X pin, slot
    # or -X ream remains.
    assert dowel.PER_MOUNT == 1 and dowel.QUANTITY == 2 and dowel.MOUNTS == 2
    station = (dowel.HANGER_OFFSET,)
    assert (knife_mount.PIN_HOLE_X,) == top_frame.HANGER_PIN_XS == station
    assert asm.KNIFE_DOWEL_X_OFFSETS == station
    for retired in ("SPAN", "SPAN_TOL"):
        assert not hasattr(dowel, retired), retired
    # The pressed end on the ream floor, the free end hanging PROUD below
    # the clamped seat, clear of the knife mount's slip-hole floor.
    assert asm.KNIFE_DOWEL_Y == pytest.approx(
        asm.KNIFE_MOUNT_TOP_Y + top_frame.HANGER_PIN_HOLE_DEPTH
    )
    assert asm.KNIFE_DOWEL_END_Y == pytest.approx(asm.KNIFE_DOWEL_Y - dowel.LENGTH)
    assert asm.KNIFE_MOUNT_TOP_Y - asm.KNIFE_DOWEL_END_Y == pytest.approx(dowel.PROUD)
    assert asm.KNIFE_DOWEL_END_Y - (
        asm.KNIFE_MOUNT_TOP_Y - knife_mount.PIN_HOLE_DEPTH
    ) == pytest.approx(2.286)


def test_the_slip_band_and_the_screw_float_absorb_the_dowel_stations() -> None:
    # S2: Ø.1280 +/-.0007 slip (a purchased .1280 reamer).
    assert dowel.SLIP_HOLE_DIA == pytest.approx(3.2512)
    assert dowel.SLIP_HOLE_DIA_BAND == pytest.approx((0.01778, -0.01778))
    assert dowel.SLIP_CLEARANCE_MIN == pytest.approx(0.0508)
    assert dowel.SLIP_CLEARANCE_MAX == pytest.approx(0.09144)
    assert 0.02 <= dowel.SLIP_CLEARANCE_MIN
    assert dowel.SLIP_CLEARANCE_MAX <= 0.10
    assert knife_mount.PIN_SLIP_PRINTED == pytest.approx((0.0020, 0.0036))  # in
    # Owner ruling 2026-11-06: the hanger holes are a letter C drill, .242,
    # the next drill over the #10 loose row's .238, pinned through the native
    # #10 clearance row's diameter override.
    assert top_frame.HANGER_HOLE_DRILL == "C"
    assert top_frame.HANGER_CLEARANCE_DIA == pytest.approx(0.242 * 25.4)
    assert top_frame.HANGER_CLEARANCE_DIA == pytest.approx(6.1468)
    assert top_frame.HANGER_CLEARANCE_DIA > CLEARANCE_MM[("#10", "loose")]
    hole = top_frame.HANGER_HOLE_SPEC
    assert (hole.kind, hole.size, hole.fit, hole.end) == (
        "clearance", "#10", "loose", "through_all",
    )
    assert hole.overrides_mm == {"HoleDiameter": top_frame.HANGER_CLEARANCE_DIA}
    # The title block's DRILLED HOLES row (+.004/0) is the hole's acceptance:
    # it never undersizes the drill.
    assert top_frame.HANGER_CLEARANCE_DIA_BAND == pytest.approx((0.1016, 0.0))
    assert top_frame.HANGER_CLEARANCE_DIA_MIN == pytest.approx(6.1468)
    assert top_frame.HANGER_CLEARANCE_DIA_MAX == pytest.approx(6.2484)
    assert top_frame.HANGER_SCREW_FLOAT == pytest.approx(
        (top_frame.HANGER_CLEARANCE_DIA_MIN - screw.SHANK_DIA) / 2.0
    )
    assert top_frame.HANGER_SCREW_FLOAT == pytest.approx(0.6604)
    # Owner ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1): one dowel
    # and the screw hang the block, which so fits one way round only.  Along
    # X: .005 ream station (.XXX from the screw axis) + the tap zone's radius
    # + B's half slip + B's datum simulator up to t/2 off its pin root within
    # ⊥Ø.001|A (codjiflo round 5).  Across: the same terms plus the turn the
    # gauge bar gives the block about its dowel, the tap PIN_HOLE_X from B
    # moving across by it.  The bar line runs through both bores, each off
    # its station by the #10 hole's centring on D (.005, ⌖.010|D, owner
    # ruling 2026-11-06), the ream station, B's slip and simulator and the
    # bore's ⌖Ø.008|A|B radius, at opposite limits over the 180.47 station
    # spacing.  Owner ruling 2026-11-10 (Pedro), #2334, S1: the tap is cut
    # on the part, clocked by the bore, so it turns with the block and its
    # zone's radius is charged once; margin option 1a of the same date makes
    # the zone ⌖Ø.005|A|B|C▷.
    assert knife_mount.STUD_TAP_POSITION_TOL == pytest.approx(0.127)
    assert knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL == pytest.approx(0.0254)
    assert top_frame.HANGER_PIN_X_TOL == pytest.approx(0.127)
    station_spacing = top_frame.STUD_Z_REAR - top_frame.STUD_Z_FRONT
    assert station_spacing == pytest.approx(180.47)
    block = (
        top_frame.HANGER_PIN_X_TOL
        + knife_mount.STUD_TAP_POSITION_TOL / 2.0
        + dowel.SLIP_CLEARANCE_MAX / 2.0
        + knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL / 2.0
    )
    assert asm.KNIFE_BLOCK_SHIFT == pytest.approx(block) == pytest.approx(0.24892)
    assert asm.KNIFE_BORE_LINE_OFFSET == pytest.approx(
        top_frame.HANGER_CROSSBAR_CENTER_TOL
        + top_frame.HANGER_PIN_X_TOL
        + dowel.SLIP_CLEARANCE_MAX / 2.0
        + knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL / 2.0
        + knife_mount.KNIFE_BORE_POSITION_TOL / 2.0
    )
    assert asm.KNIFE_BORE_LINE_OFFSET == pytest.approx(0.41402)
    assert asm.KNIFE_BAR_YAW_DEG == pytest.approx(
        math.degrees(math.atan(2.0 * asm.KNIFE_BORE_LINE_OFFSET / station_spacing))
    )
    assert asm.KNIFE_BAR_YAW_DEG == pytest.approx(0.2628850, abs=5e-7)
    # Each block also turns on the bar by the bar's .0017 maximum diametral
    # clearance over its shortest bore (owner review of #2334).
    assert asm.KNIFE_BAR_PLAY_YAW_DEG == pytest.approx(
        math.degrees(
            math.atan(
                asm.KNIFE_BAR_CLEARANCE
                / (knife_mount.SUPPORT_Z_THICK - knife_mount.BLOCK_SIZE_TOL)
            )
        )
    )
    assert asm.KNIFE_BAR_PLAY_YAW_DEG == pytest.approx(0.1803750, abs=5e-7)
    assert asm.KNIFE_TAP_YAW_DEG == pytest.approx(
        asm.KNIFE_BAR_YAW_DEG + asm.KNIFE_BAR_PLAY_YAW_DEG
    )
    assert asm.KNIFE_BAR_YAW_SHIFT == pytest.approx(
        knife_mount.PIN_HOLE_X * math.tan(math.radians(asm.KNIFE_TAP_YAW_DEG))
    )
    assert asm.KNIFE_BAR_YAW_SHIFT == pytest.approx(0.0589521, abs=5e-7)
    assert asm.HANGER_SCREW_MISMATCH_X == pytest.approx(0.24892)
    assert asm.HANGER_SCREW_MISMATCH_Z == pytest.approx(0.24892 + asm.KNIFE_BAR_YAW_SHIFT)
    assert asm.HANGER_SCREW_MISMATCH == pytest.approx(0.39591214033, abs=1e-9)
    # FR-02 replicates the same mismatch for its washer stack.
    assert build_fr_top_frame.HANGER_BAR_YAW_SHIFT == pytest.approx(
        asm.KNIFE_BAR_YAW_SHIFT, abs=1e-12
    )
    # Drift reaches the hole's top end at the faced top, over the longest
    # printed grip (1.437 + .005), not the retired one-place cast band.
    assert asm.HANGER_SCREW_DRIFT == pytest.approx(
        math.tan(math.radians(top_frame.KEEPER_TAP_DRILL_WANDER_DEG))
        * (top_frame.HANGER_GRIP + top_frame.HANGER_GRIP_TOL)
    )
    assert asm.HANGER_SCREW_DRIFT == pytest.approx(0.19177922892, abs=1e-9)
    assert asm.HANGER_SCREW_FLOAT_SPARE == pytest.approx(0.07270863075, abs=1e-9)
    assert (
        asm.HANGER_SCREW_MISMATCH + asm.HANGER_SCREW_DRIFT
        < top_frame.HANGER_SCREW_FLOAT
    )
    # The rear mount, re-hung on the lever at MHA-SM-00 and swung about its
    # dowel until the rock gauge passes, may need the bar line's whole turn
    # and the bar's play; its bolt float allows 1.11 deg.
    assert asm.KNIFE_REAR_YAW_RANGE_DEG == pytest.approx(1.1136266, abs=5e-7)
    assert asm.KNIFE_REAR_YAW_RANGE_DEG > asm.KNIFE_TAP_YAW_DEG

    # The tap zone closes with spare: the stack, each mismatch carrying the
    # zone's radius, closes at Ø0.230, so Ø.008 just fits (0.019, the margin
    # option 1a tightened away) and Ø.010 overruns the float.
    def spare_at(zone: float) -> float:
        shift = (zone - knife_mount.STUD_TAP_POSITION_TOL) / 2.0
        mismatch = math.hypot(
            asm.HANGER_SCREW_MISMATCH_X + shift, asm.HANGER_SCREW_MISMATCH_Z + shift
        )
        return top_frame.HANGER_SCREW_FLOAT - mismatch - asm.HANGER_SCREW_DRIFT

    assert spare_at(0.127) == pytest.approx(asm.HANGER_SCREW_FLOAT_SPARE, abs=1e-12)
    assert spare_at(0.1016) == pytest.approx(0.09056458, abs=1e-7)
    assert spare_at(0.1524) == pytest.approx(0.05484363, abs=1e-7)
    assert spare_at(0.1778) == pytest.approx(0.03697070, abs=1e-7)
    assert spare_at(0.2032) == pytest.approx(0.01909079, abs=1e-7)
    assert spare_at(0.254) == pytest.approx(-0.01668689, abs=1e-7)
    assert spare_at(0.3048) == pytest.approx(-0.05248429, abs=1e-7)
    assert (
        spare_at(0.3048)
        < spare_at(0.254)
        < 0.0
        < spare_at(0.2032)
        < spare_at(0.1778)
        < spare_at(0.1524)
        < spare_at(0.127)
        < spare_at(0.1016)
    )
    x0 = asm.HANGER_SCREW_MISMATCH_X - knife_mount.STUD_TAP_POSITION_TOL / 2.0
    z0 = asm.HANGER_SCREW_MISMATCH_Z - knife_mount.STUD_TAP_POSITION_TOL / 2.0
    reach = top_frame.HANGER_SCREW_FLOAT - asm.HANGER_SCREW_DRIFT
    half_zone_max = (
        -(x0 + z0) + math.sqrt((x0 + z0) ** 2 - 2.0 * (x0**2 + z0**2 - reach**2))
    ) / 2.0
    assert 2.0 * half_zone_max == pytest.approx(0.23031050, abs=1e-7)
    assert spare_at(2.0 * half_zone_max) == pytest.approx(0.0, abs=1e-12)
    assert 0.2032 < 2.0 * half_zone_max < 0.254
    # The C drill (owner ruling 2026-11-06) keeps the 0.073 spare; the #10
    # loose row's Ø.238 would leave only 0.022.
    loose_float = (CLEARANCE_MM[("#10", "loose")] - screw.SHANK_DIA) / 2.0
    assert loose_float == pytest.approx(0.6095)
    assert loose_float - (
        asm.HANGER_SCREW_MISMATCH + asm.HANGER_SCREW_DRIFT
    ) == pytest.approx(0.02180863, abs=1e-7)
    # Inheriting the general symmetric .XXX hole band would allow an
    # undersize hole leaving only 0.009; the explicit +.005/0 band keeps 0.073.
    undersize_float = (
        top_frame.HANGER_CLEARANCE_DIA
        - top_frame.PRINTED_LINEAR_BAND_MM[3]
        - screw.SHANK_DIA
    ) / 2.0
    assert undersize_float == pytest.approx(0.5969)
    assert undersize_float - (
        asm.HANGER_SCREW_MISMATCH + asm.HANGER_SCREW_DRIFT
    ) == pytest.approx(0.00920863, abs=1e-7)
    # Standard normal-fit #10 clearance cannot take this complete mismatch.
    normal_float = (CLEARANCE_MM[("#10", "normal")] - screw.SHANK_DIA) / 2.0
    assert normal_float == pytest.approx(0.3935)
    assert asm.HANGER_SCREW_MISMATCH + asm.HANGER_SCREW_DRIFT > normal_float


def test_the_slip_fit_takes_the_perpendicularity_tilt() -> None:
    # Owner ruling 2026-10-27 (#2016 option A), restated 2026-11-06: the
    # crossbar reams ⊥Ø.001 to the faced underside (the shop row's floor);
    # the block's round hole ⊥Ø.001 to A (delegated ruling sm Q1,
    # 2026-11-07; was ⊥Ø.0006).  Each
    # zone tilts its axis by atan(zone / length) over the hole's straight,
    # full-size wall: the shortest printed depth less the floor's corner
    # (the crossbar ream's CORNER R.003 MAX; the block's title-block R.040
    # MAX, machinist review, farm run 20261027T233328148Z) and the reamer's
    # 0.5 bevel lead (11.108 ream, 7.628 hole; codjiflo round 6).  An assumed
    # .0004 seat conformity across the block's shortest .540 seat depth adds
    # its tilt.  Together they stay inside the tilt the tightest slip takes
    # over the longest proud pin (its floor lift included) short of its
    # rounded free end.
    assert top_frame.HANGER_PRESS_HOLE_PERPENDICULARITY_TOL == pytest.approx(0.0254)
    assert knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL == pytest.approx(0.0254)
    assert not hasattr(knife_mount, "DOWEL_SLOT_PERPENDICULARITY_TOL")
    assert dowel.PRESS_FLOOR_CORNER_R_MAX == pytest.approx(0.0762)
    assert knife_mount.DOWEL_HOLE_FLOOR_CORNER_R_MAX == pytest.approx(1.016)
    assert asm.KNIFE_REAM_LEAD_ALLOWANCE == 0.5
    assert asm.KNIFE_SEAT_CONFORMITY == 0.01
    lead = asm.KNIFE_REAM_LEAD_ALLOWANCE
    ream_wall = (
        dowel.PRESS_DEPTH
        - dowel.PRESS_DEPTH_TOL
        - dowel.PRESS_FLOOR_CORNER_R_MAX
        - lead
    )
    hole_wall = (
        dowel.SLIP_DEPTH
        - dowel.SLIP_DEPTH_TOL
        - knife_mount.DOWEL_HOLE_FLOOR_CORNER_R_MAX
        - lead
    )
    assert (ream_wall, hole_wall) == pytest.approx((11.1078, 7.628))
    seat_depth = knife_mount.SUPPORT_Z_THICK - knife_mount.BLOCK_SIZE_TOL
    assert seat_depth == pytest.approx(13.716)
    assert dowel.FREE_END_LEN == pytest.approx(dowel.ENDS.crown_r)
    assert dowel.PROUD_MAX == pytest.approx(7.62 + dowel.PRESS_FLOOR_LIFT_MAX)
    entry = dowel.PROUD_MAX - dowel.FREE_END_LEN
    assert entry == pytest.approx(7.217956, abs=5e-6)

    def tilt(
        ream_zone: float,
        hole_zone: float,
        conformity: float = asm.KNIFE_SEAT_CONFORMITY,
        ream: float = ream_wall,
        hole: float = hole_wall,
    ) -> float:
        return (
            math.degrees(math.atan(ream_zone / ream))
            + math.degrees(math.atan(hole_zone / hole))
            + math.degrees(math.atan(conformity / seat_depth))
        )

    allowed = math.degrees(math.atan(dowel.SLIP_CLEARANCE_MIN / entry))
    assert asm.KNIFE_DOWEL_TILT_ALLOWED_DEG == pytest.approx(allowed)
    assert asm.KNIFE_DOWEL_TILT_ALLOWED_DEG == pytest.approx(0.4032413, abs=5e-7)
    # The pin leans in B's round hole (Owner ruling 2026-11-08 (Pedro),
    # #2144 item 11.3: the slot is gone).
    assert asm.KNIFE_DOWEL_TILT_CHARGED_DEG == pytest.approx(
        tilt(
            top_frame.HANGER_PRESS_HOLE_PERPENDICULARITY_TOL,
            knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL,
        )
    )
    assert asm.KNIFE_DOWEL_TILT_REAM_DEG == pytest.approx(0.1310170, abs=5e-7)
    assert asm.KNIFE_DOWEL_TILT_CHARGED_DEG == pytest.approx(0.3635748, abs=5e-7)
    assert asm.KNIFE_DOWEL_TILT_ALLOWED_DEG - asm.KNIFE_DOWEL_TILT_CHARGED_DEG > 0.03
    # RV-07: with the ream and hole terms fixed, the seats bind only past
    # about .0008 of conformity.
    conformity_bind = seat_depth * math.tan(
        math.radians(
            allowed - asm.KNIFE_DOWEL_TILT_REAM_DEG - asm.KNIFE_DOWEL_TILT_HOLE_DEG
        )
    )
    assert conformity_bind / 25.4 == pytest.approx(0.0007675, abs=5e-7)
    # Negative controls: ⊥Ø.0014 on the ream, ⊥Ø.0014 on the block's hole,
    # or a .0008 seat conformity binds the tightest slip; the next step down
    # (Ø.0012, Ø.0012, .0006) still passes.
    inch = 25.4
    assert tilt(0.0014 * inch, 0.0254) == pytest.approx(0.4159813, abs=5e-7)
    assert tilt(0.0254, 0.0014 * inch) == pytest.approx(0.4398879, abs=5e-7)
    assert tilt(0.0254, 0.0254, 0.0008 * inch) == pytest.approx(0.4066845, abs=5e-7)
    assert (
        min(
            tilt(0.0014 * inch, 0.0254),
            tilt(0.0254, 0.0014 * inch),
            tilt(0.0254, 0.0254, 0.0008 * inch),
        )
        > allowed
    )
    assert (
        max(
            tilt(0.0012 * inch, 0.0254),
            tilt(0.0254, 0.0012 * inch),
            tilt(0.0254, 0.0254, 0.0006 * inch),
        )
        < allowed
    )
    # The old Ø3.24 +/-0.03 band's tightest slip (0.02738) takes only
    # 0.2173 deg: the full charge binds it.
    old_allowed = math.degrees(math.atan(0.02738 / entry))
    assert old_allowed == pytest.approx(0.2173401, abs=5e-7)
    assert old_allowed < asm.KNIFE_DOWEL_TILT_CHARGED_DEG
    # Dropping the reamer lead, or the lead and the seat, understates the tilt.
    no_lead = tilt(0.0254, 0.0254, ream=ream_wall + lead, hole=hole_wall + lead)
    no_lead_no_seat = tilt(
        0.0254, 0.0254, 0.0, ream=ream_wall + lead, hole=hole_wall + lead
    )
    assert no_lead == pytest.approx(0.3461952, abs=5e-7)
    assert no_lead_no_seat == pytest.approx(0.3044222, abs=5e-7)
    assert no_lead_no_seat < no_lead < asm.KNIFE_DOWEL_TILT_CHARGED_DEG
    # Counting the bearing length to the chamfer, not the rounded free end,
    # would overstate the slip's allowance.
    chamfer_allowed = math.degrees(
        math.atan(dowel.SLIP_CLEARANCE_MIN / (dowel.PROUD_MAX - dowel.CHAMFER_LEN))
    )
    assert chamfer_allowed == pytest.approx(0.4052908, abs=5e-7)
    assert chamfer_allowed > asm.KNIFE_DOWEL_TILT_ALLOWED_DEG


def test_one_dowel_and_the_gauge_bar_replace_the_slot_and_datum_c() -> None:
    # Owner ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1): one dowel
    # + screw per mount, the Ø.4720 gauge bar through both bores at MHA-SM-00;
    # slot C, its notch and datum C deleted; the bore ⌖Ø.008|A|B + ∥.002|A;
    # MHA-FR-02 loses the two -X press reams and their frames; VN-53 qty 2.
    for retired in (
        "SLOT_X",
        "SLOT_WIDTH",
        "SLOT_WIDTH_BAND",
        "SLOT_END_FROM_B",
        "SLOT_POSITION_TOL",
        "SLOT_TAP_WEB",
        "SLOT_PIN_LOCATION_MARGIN",
        "SLOT_MOUTH_PIN_MARGIN",
        "DOWEL_SLOT_PERPENDICULARITY_TOL",
        "KNIFE_BORE_ORIENTATION_TOL",
    ):
        assert not hasattr(knife_mount, retired), retired
    for retired in (
        "PIN_HOLE_NEG_X",
        "HANGER_NEG_PIN_X_TOL",
        "HANGER_PRESS_HOLE_POSITION_TOL",
        "HANGER_DATUM_LINE_YAW_SHIFT",
    ):
        assert not hasattr(top_frame, retired), retired
    assert not any("slot" in key for key in knife_mount.GEOMETRIC_TOLERANCES_IN)
    assert "knife-hanger press ream position" not in top_frame.GEOMETRIC_TOLERANCES_IN
    assert len(top_frame.HANGER_PIN_XS) == 1
    assert len(build_fr_top_frame.HANGER_PIN_CONTOURS) == 2
    assert dowel.QUANTITY == 2
    # The bar enters every conforming bore and is a gauge pin, not a part.
    assert knife_mount.KNIFE_GAUGE_BAR_DIA_IN == 0.4720
    assert knife_mount.KNIFE_GAUGE_BAR_DIA == pytest.approx(2.0 * knife_mount.BORE_R_MIN)
    assert not any("gauge" in stem for stem in asm.spec.QUANTITIES)


def test_the_crossbar_webs_hold_round_the_press_reams_and_knockouts() -> None:
    # Owner ruling 2026-10-24 (T+H3): each crossbar dowel hole is a Ø.1240
    # REAM H7 (+.0005/0) blind ream, .47 deep from the faced underside,
    # pierced by a #51 knockout drilled up from its floor on the ream's drawn
    # axis.  Owner ruling 2026-11-08 (Pedro), #2144 item 11.3: one ream per
    # station, .300 +/-.005 from its screw axis (the -X reams are gone).
    stations = tuple(build_fr_top_frame.HANGER_X + x for x in top_frame.HANGER_PIN_XS)
    assert stations == pytest.approx((-7.38,))
    assert build_fr_top_frame.PIN_HOLE_X == pytest.approx(-7.38)
    assert build_fr_top_frame.BAR_X1 - build_fr_top_frame.BAR_X0 == pytest.approx(
        25.146
    )
    assert (
        build_fr_top_frame.BAR_X1 + build_fr_top_frame.BAR_X0
    ) / 2.0 == pytest.approx(-15.0)
    # Owner rulings B2 and B5 (#2333): the crossbar is as cast, .99 ±.03, and
    # D is its sides' median, so a face stands (25.146 - 0.762) / 2 from D.
    assert build_fr_top_frame.HANGER_BAR_HALF_WIDTH_MIN == pytest.approx(12.192)
    assert top_frame.HANGER_CROSSBAR_CENTER_TOL == pytest.approx(0.127)
    assert (top_frame.HANGER_PIN_HOLE_DIA, top_frame.HANGER_PIN_HOLE_DIA_BAND) == (
        dowel.PRESS_HOLE_DIA,
        dowel.PRESS_HOLE_DIA_BAND,
    )
    # Every wall at its print-worst less the drill drift each hole takes up
    # its depth: drawing-guidelines.md rule 17 (walls and webs)'s .080 target
    # holds, charged at the ream's .005 station from its screw axis and,
    # toward the bar face, the #10 axis's .005 centring on D (⌖.010|D, owner
    # ruling 2026-11-06; the faces are D's median).
    assert not hasattr(top_frame, "HANGER_PIN_NEG_STATION_TOL")
    assert not hasattr(build_fr_top_frame, "NEG_PIN_HOLE_BAR_WALL")
    pin_r = top_frame.HANGER_PIN_HOLE_DIA_MAX / 2.0
    drift_floor = build_fr_top_frame.HANGER_DRIFT_AT_REAM_FLOOR
    assert build_fr_top_frame.PIN_HOLE_BAR_WALL == pytest.approx(
        build_fr_top_frame.HANGER_BAR_HALF_WIDTH_MIN
        - top_frame.HANGER_CROSSBAR_CENTER_TOL
        - top_frame.HANGER_PIN_X
        - top_frame.HANGER_PIN_X_TOL
        - pin_r
        - drift_floor
    )
    assert build_fr_top_frame.PIN_HOLE_SCREW_WALL == pytest.approx(
        top_frame.HANGER_PIN_X
        - top_frame.HANGER_PIN_X_TOL
        - pin_r
        - top_frame.HANGER_CLEARANCE_DIA_MAX / 2.0
        - 2.0 * drift_floor
    )
    walls = {
        "ream to bar face": (build_fr_top_frame.PIN_HOLE_BAR_WALL, 2.673012),
        "ream to screw hole": (build_fr_top_frame.PIN_HOLE_SCREW_WALL, 2.659975),
        "knockout to bar face": (build_fr_top_frame.KNOCKOUT_BAR_WALL, 3.094861),
        "knockout to screw hole": (build_fr_top_frame.KNOCKOUT_SCREW_WALL, 2.953882),
    }
    for label, (wall, expected) in walls.items():
        assert wall == pytest.approx(expected, abs=5e-6), label
        assert wall >= 2.032, label
    lands = {
        "knockout to top-rim break": (build_fr_top_frame.KNOCKOUT_TOP_BREAK_LAND, 1.316861),
        "washer to bar top break": (build_fr_top_frame.HANGER_WASHER_BAR_TOP_MARGIN, 2.254569),
        "washer bearing annulus": (build_fr_top_frame.HANGER_WASHER_BEARING_MIN, 1.670369),
        "washer ring inside knockouts": (
            build_fr_top_frame.HANGER_WASHER_KNOCKOUT_RING_MIN,
            0.161798,
        ),
    }
    for label, (land, expected) in lands.items():
        assert land == pytest.approx(expected, abs=5e-6), label
        assert land > 0.0, label
    # Across the line the ream and knockout sit their implied-zero .XXX off
    # the screw axis's line (SAME Z), so each keeps one pocket-end wall.  The
    # pocket ends are as cast (owner ruling B2, #2333): the rear end, chained
    # from the front one, stands two ±.03 bands out.
    pocket = build_fr_top_frame.BAR_POCKET_HOLE_WALLS
    assert set(pocket) == {"hanger clearance hole", "dowel ream", "dowel knockout"}
    assert pocket["dowel ream"] == pytest.approx(17.890600, abs=5e-6)
    assert pocket["dowel knockout"] == pytest.approx(18.312449, abs=5e-6)
    assert pocket["hanger clearance hole"] == pytest.approx(16.385177, abs=5e-6)
    # Owner ruling 2026-10-27, option (c): the knockout prints plain #51
    # DRILL, Ø.067 at three places (MAX .071 with the drilled-hole band),
    # drawn coaxial to its ream, so it may stand the implied .XXX .005 off
    # the ream axis on each axis.  The walls are charged where each knockout
    # leaves the faced top: the ream's drift at its deepest floor, that .005
    # along the wall's axis and the knockout's own drift.
    assert top_frame.HANGER_KNOCKOUT_DIA_PRINTED == pytest.approx(1.7018)
    assert top_frame.HANGER_KNOCKOUT_DIA_MAX == pytest.approx(1.8034)
    assert top_frame.HANGER_KNOCKOUT_COAXIAL_TOL == pytest.approx(0.127)
    assert build_fr_top_frame.HANGER_KNOCKOUT_SHIFT_AT_TOP == pytest.approx(
        build_fr_top_frame.HANGER_DRIFT_AT_REAM_FLOOR
        + top_frame.HANGER_KNOCKOUT_COAXIAL_TOL
        + build_fr_top_frame.HANGER_KNOCKOUT_DRIFT
    )
    assert build_fr_top_frame.HANGER_KNOCKOUT_SHIFT_AT_TOP == pytest.approx(
        0.321439, abs=5e-6
    )
    # Shortest finished grip (1.437 - .005) less the deepest ream floor
    # (.47 + .010).
    assert build_fr_top_frame.PIN_HOLE_FLOOR_MARGIN == pytest.approx(24.1808)
    # On the floor the knockout may sit the coaxial zone's corner off the
    # ream's centre, hypot(0.13, 0.13).  It leaves a metal ring: (ream MIN
    # less knockout MAX) / 2 less that eccentricity.
    assert top_frame.HANGER_KNOCKOUT_FLOOR_ECCENTRICITY == pytest.approx(
        math.hypot(
            top_frame.HANGER_KNOCKOUT_COAXIAL_TOL,
            top_frame.HANGER_KNOCKOUT_COAXIAL_TOL,
        )
    )
    ream_min = dowel.PRESS_HOLE_DIA + dowel.PRESS_HOLE_DIA_BAND[1]
    assert top_frame.HANGER_PIN_FLOOR_LAND_MIN == pytest.approx(
        (ream_min - top_frame.HANGER_KNOCKOUT_DIA_MAX) / 2.0
        - top_frame.HANGER_KNOCKOUT_FLOOR_ECCENTRICITY
    )
    assert top_frame.HANGER_PIN_FLOOR_LAND_MIN == pytest.approx(0.493495, abs=5e-6)
    # The pressed pin bears on that ring only inside its end's flat point (ASME
    # B18.8.2 point Ø MIN 2.794) and outside the floor's corner radius
    # (R.003 MAX), whichever is smaller, less the knockout MAX's radius and
    # the same eccentricity.  The land falls short of the 0.4 target,
    # accepted by the owner (option (c), RV-06 minor), but stays positive.
    assert dowel.POINT_DIA_MIN == pytest.approx(2.794)
    assert top_frame.HANGER_PIN_FLOOR_CORNER_R_MAX == pytest.approx(0.0762)
    assert top_frame.HANGER_PIN_FLOOR_BEARING_R == pytest.approx(
        min(
            dowel.POINT_DIA_MIN / 2.0,
            ream_min / 2.0 - top_frame.HANGER_PIN_FLOOR_CORNER_R_MAX,
        )
    )
    assert top_frame.HANGER_PIN_FLOOR_BEARING_R == pytest.approx(1.397)
    assert top_frame.HANGER_PIN_FLOOR_BEARING_LAND_MIN == pytest.approx(
        top_frame.HANGER_PIN_FLOOR_BEARING_R
        - top_frame.HANGER_KNOCKOUT_DIA_MAX / 2.0
        - top_frame.HANGER_KNOCKOUT_FLOOR_ECCENTRICITY
    )
    assert top_frame.HANGER_PIN_FLOOR_BEARING_LAND_MIN == pytest.approx(
        0.315695, abs=5e-6
    )
    assert top_frame.HANGER_PIN_FLOOR_BEARING_LAND_TARGET == 0.4
    assert (
        0.0
        < top_frame.HANGER_PIN_FLOOR_BEARING_LAND_MIN
        < top_frame.HANGER_PIN_FLOOR_BEARING_LAND_TARGET
    )
    # The crossbar's washer stack charges the assembly's very mismatch.
    assert build_fr_top_frame.HANGER_SEAT_BOLT_MISMATCH == pytest.approx(
        asm.HANGER_SCREW_MISMATCH, abs=1e-12
    )


def test_the_datum_frame_is_the_zone_the_stacks_were_derived_on() -> None:
    # Owner ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1): the
    # block's frame is A (top seat) and B (the round slip hole); the bore
    # carries ⌖Ø.008|A|B with a stacked ∥.002|A (its pitch).  Its yaw about
    # B is free on the part and set at MHA-SM-00 by the gauge bar, so the
    # rock charges the bar's clearance, not a part zone.  Delegated ruling
    # 2026-11-07 (Main): B ⊥.001 (sm Q1).  Owner ruling 2026-11-10 (Pedro),
    # #2334, S1: the tap is cut on the part, superseding sm Q3's spot through
    # MHA-FR-02; margin option 1a of the same date: ⌖Ø.005|A|B|C▷.
    assert knife_mount.GEOMETRIC_TOLERANCES_IN == {
        "knife-bore position": ".008",
        "knife-bore parallelism": ".002",
        "dowel hole perpendicularity": ".001",
        "knife-hanger tap position": ".005",
    }
    assert knife_mount.KNIFE_BORE_POSITION_TOL == pytest.approx(0.2032)
    assert knife_mount.KNIFE_BORE_PARALLELISM_TOL == pytest.approx(0.0508)
    assert asm.HANGER_SCREW_MISMATCH == pytest.approx(0.395912, abs=5e-6)
    assert asm.KNIFE_FREE_ROCK_WORST_DEG == pytest.approx(7.760722, abs=5e-6)

    # The bore's position zone enters the screw float only through the bar
    # line's turn about the dowel, on top of the bar's own play.  Ø.008
    # closes with 0.073 spare; the float holds up to about Ø.091.
    hole_perp = knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL
    block = asm.KNIFE_BLOCK_SHIFT
    spacing = top_frame.STUD_Z_REAR - top_frame.STUD_Z_FRONT

    def spare_at_bore(zone: float) -> float:
        line = (
            top_frame.HANGER_CROSSBAR_CENTER_TOL
            + top_frame.HANGER_PIN_X_TOL
            + dowel.SLIP_CLEARANCE_MAX / 2.0
            + hole_perp / 2.0
            + zone / 2.0
        )
        z = block + knife_mount.PIN_HOLE_X * math.tan(
            math.atan(2.0 * line / spacing) + math.radians(asm.KNIFE_BAR_PLAY_YAW_DEG)
        )
        return (
            top_frame.HANGER_SCREW_FLOAT - math.hypot(block, z) - asm.HANGER_SCREW_DRIFT
        )

    inch = 25.4
    assert spare_at_bore(0.008 * inch) == pytest.approx(
        asm.HANGER_SCREW_FLOAT_SPARE, abs=1e-12
    )
    assert spare_at_bore(0.016 * inch) == pytest.approx(0.06600037, abs=1e-7)
    assert spare_at_bore(0.050 * inch) == pytest.approx(0.03674984, abs=1e-7)
    assert spare_at_bore(0.092 * inch) < 0.0 < spare_at_bore(0.091 * inch)

    # The bar-set far-end offset is the bar's diametral clearance in the
    # largest bore plus the ridge's yaw over the mouth span; the bore's
    # ∥.002|A (pitch) does not enter the lateral rock.  The floor holds to a
    # .0119 bar clearance (t 0.328), seven times the class ZZ bar's .0017.
    block_depth = knife_mount.SUPPORT_Z_THICK + knife_mount.BLOCK_SIZE_TOL

    def rock_at_clearance(clearance: float) -> float:
        offset = clearance + block_depth * clearance / asm.KNIFE_RIDGE_MOUTH_SPAN_MIN
        return knife_mount.free_rock_deg(
            offset,
            hex_w=2.0 * lever.KNIFE_SHOULDER_X_MAX,
            r_bore=knife_mount.BORE_R_MIN,
            shoulder_drop=lever.KNIFE_SHOULDER_DROP_MIN,
        )

    assert rock_at_clearance(asm.KNIFE_BAR_CLEARANCE) == pytest.approx(
        asm.KNIFE_FREE_ROCK_WORST_DEG
    )
    assert rock_at_clearance(0.0035 * inch) == pytest.approx(7.281181, abs=5e-6)
    assert rock_at_clearance(0.0100 * inch) == pytest.approx(5.520964, abs=5e-6)
    assert rock_at_clearance(0.0120 * inch) == pytest.approx(4.970705, abs=5e-6)
    assert (
        rock_at_clearance(0.0120 * inch)
        < asm.KNIFE_FREE_ROCK_FLOOR_DEG
        <= rock_at_clearance(0.0118 * inch)
    )


def test_the_knife_mount_webs_hold_round_the_hole() -> None:
    assert knife_mount.PIN_HOLE_X == pytest.approx(dowel.HANGER_OFFSET)
    # Same face-location scheme, 1.00 wide; the +X hole (datum B) stands .20
    # .XX from its face, the row .275 from front with its .XX band printed.
    assert knife_mount.BLK_HALF_X == 12.7
    assert knife_mount.PIN_HOLE_SIDE_DISTANCE == pytest.approx(5.08)
    assert knife_mount.PIN_HOLE_SIDE_TOL == knife_mount._XX
    assert knife_mount.HOLE_ROW_FACE_DISTANCE == pytest.approx(6.985)
    assert knife_mount.HOLE_ROW_FACE_TOL == knife_mount._XX
    assert knife_mount.BLOCK_SIZE_TOL == knife_mount._XX
    assert knife_mount.BLOCK_HEIGHT_PRINTED == pytest.approx(29.718)
    assert knife_mount.BORE_DIA_BAND == pytest.approx((0.0381, 0.0))
    # The bore's yaw about B is free under A|B: the side web charges the
    # title-block 1 deg over half the deepest block (0.124).
    yaw_at_face = (
        (knife_mount.SUPPORT_Z_THICK + knife_mount.BLOCK_SIZE_TOL)
        / 2.0
        * math.tan(math.radians(1.0))
    )
    assert knife_mount._BORE_YAW_AT_FACE == pytest.approx(yaw_at_face)
    assert yaw_at_face == pytest.approx(0.124140, abs=5e-6)
    webs = {
        "round hole to +X face": (knife_mount.PIN_HOLE_SIDE_WEB, 3.19151),
        "round hole to Z faces": (knife_mount.PIN_HOLE_Z_WEB, 4.84251),
        "tap to Z faces": (knife_mount.STUD_TAP_Z_WALL, 3.867492),
        "bore to side faces": (knife_mount.BORE_SIDE_WEB, 5.952810),
        "bore to bottom face": (knife_mount.BORE_BOTTOM_WALL, 2.74955),
        "round hole to tap": (knife_mount.PIN_HOLE_TAP_WEB, 3.50901),
        "round hole to bore": (knife_mount.PIN_HOLE_BORE_WEB, 6.325585),
    }
    for label, (web, expected) in webs.items():
        assert web == pytest.approx(expected, abs=5e-4), label
        assert web >= knife_mount.STUD_TAP_WEB_MIN, label
    assert min(web for web, _ in webs.values()) == knife_mount.BORE_BOTTOM_WALL


def test_the_knife_edge_keeps_five_degrees_of_rock_at_the_worst_case() -> None:
    # Ruling B: HEX_W 8.080, HEX_H 10.268 (.XXX, +/-.005); ridge 115.1 deg.
    assert (lever.HEX_W, lever.HEX_H, lever.HEX_BAND) == (8.080, 10.268, 0.127)
    assert lever.RIDGE_ANGLE_DEG == pytest.approx(115.137, abs=5e-3)
    # Owner ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1): the
    # gauge bar through both bores sets the front mount's yaw, so the
    # far-end offset is the bar's diametral clearance in the largest bore,
    # .4735 - (.4720 - .0002) = .0017, plus the lever ridge's yaw: the
    # ridge spans both mounts' bores, so that clearance yaws it over the
    # 159.90 minimum mouth span, across the block (codjiflo round 3).  The
    # rear mount's yaw is accepted by the rock gauge itself (sheet check 2),
    # which directly proves the 5.0 deg floor.
    for retired in ("KNIFE_DOWEL_SPAN_MIN", "KNIFE_MOUNT_YAW_DEG"):
        assert not hasattr(asm, retired), retired
    assert asm.KNIFE_BAR_CLEARANCE == pytest.approx(
        2.0 * knife_mount.BORE_R_MAX - knife_mount.KNIFE_GAUGE_BAR_DIA_MIN
    )
    assert asm.KNIFE_BAR_CLEARANCE == pytest.approx(0.0017 * 25.4)
    block_depth = knife_mount.SUPPORT_Z_THICK + knife_mount.BLOCK_SIZE_TOL
    assert block_depth == pytest.approx(14.224)
    assert asm.KNIFE_RIDGE_MOUTH_SPAN_MIN == pytest.approx(
        top_frame.STUD_Z_REAR - top_frame.STUD_Z_FRONT - block_depth
    )
    assert asm.KNIFE_RIDGE_MOUTH_SPAN_MIN == pytest.approx(166.246)
    assert asm.KNIFE_RIDGE_YAW_OFFSET == pytest.approx(
        block_depth * asm.KNIFE_BAR_CLEARANCE / asm.KNIFE_RIDGE_MOUTH_SPAN_MIN
    )
    assert asm.KNIFE_RIDGE_YAW_OFFSET == pytest.approx(0.0036945, abs=5e-7)
    assert asm.KNIFE_BORE_FAR_END_OFFSET == pytest.approx(
        asm.KNIFE_BAR_CLEARANCE + asm.KNIFE_RIDGE_YAW_OFFSET
    )
    assert asm.KNIFE_BORE_FAR_END_OFFSET == pytest.approx(0.0468745, abs=5e-7)
    # Code review C09 (owner ruling T1): the print holds the ridge .159
    # +/-.002 from each side face and each upper flank 122.4 +/-0.5 deg to its
    # side face.  The worst shoulder is .161 (4.0894) out on a flank 58.1 deg
    # off the vertical, so 2.5454 under the ridge: 7.759 deg in the smallest bore.
    assert lever.KNIFE_SHOULDER_X_MAX == pytest.approx(4.0894)
    assert lever.KNIFE_FLANK_HALF_MAX_DEG == pytest.approx(58.1)
    assert lever.KNIFE_SHOULDER_DROP_MIN == pytest.approx(2.545427, abs=5e-6)
    assert asm.KNIFE_FREE_ROCK_WORST_DEG == pytest.approx(7.760722, abs=5e-6)
    assert asm.KNIFE_FREE_ROCK_WORST_DEG >= asm.KNIFE_FREE_ROCK_FLOOR_DEG == 5.0
    assert knife_mount.BORE_R_MIN == pytest.approx(5.9944)

    def rock(ridge_from_side: float, flank_to_side_deg: float) -> float:
        half = math.radians(180.0 - flank_to_side_deg)
        return knife_mount.free_rock_deg(
            asm.KNIFE_BORE_FAR_END_OFFSET,
            hex_w=2.0 * ridge_from_side,
            r_bore=knife_mount.BORE_R_MIN,
            shoulder_drop=ridge_from_side / math.tan(half),
        )

    # Every corner of the two printed bands: the proof's corner is the least.
    # The side band is about the printed .159, not the 4.040 model value.
    printed_ridge = round(lever.RIDGE_FROM_SIDE / 25.4, 3) * 25.4
    x_tol, a_tol = lever.RIDGE_FROM_SIDE_TOL, lever.KNIFE_FLANK_TO_SIDE_TOL_DEG
    corners = {
        (dx, da): rock(printed_ridge + dx, lever.KNIFE_FLANK_TO_SIDE_DEG + da)
        for dx in (-x_tol, 0.0, x_tol)
        for da in (-a_tol, 0.0, a_tol)
    }
    assert min(corners, key=corners.get) == (x_tol, -a_tol)
    assert min(corners.values()) == pytest.approx(asm.KNIFE_FREE_ROCK_WORST_DEG)
    assert corners[(0.0, 0.0)] == pytest.approx(8.435, abs=5e-3)
    assert max(corners.values()) == pytest.approx(9.110, abs=5e-3)
    # The counterexample the old controls admitted (code review C09): the
    # included angle at its nominal, held by HexWidth and the angle only, with
    # the flanks split unevenly about the vertical at the widest .XXX
    # section.  One flank 2, 3 or 5 deg flatter drops the rock to 6.59, 5.84,
    # 4.30: under the floor at 5 deg.  T1 bounds each flank to its side
    # face, so no split past 0.5 deg passes the print.
    widest_half = (lever.HEX_W + lever.HEX_BAND) / 2.0
    split_rock = {}
    for split, expected in ((2.0, 6.5934), (3.0, 5.8409), (5.0, 4.2986)):
        flank_to_side = 180.0 - (lever.RIDGE_ANGLE_DEG / 2.0 + split)
        split_rock[split] = rock(widest_half, flank_to_side)
        assert split_rock[split] == pytest.approx(expected, abs=5e-4)
        assert flank_to_side < lever.KNIFE_FLANK_TO_SIDE_DEG - a_tol
        assert widest_half > printed_ridge + x_tol
    assert split_rock[5.0] < asm.KNIFE_FREE_ROCK_FLOOR_DEG <= split_rock[3.0]
    assert split_rock[3.0] < split_rock[2.0]
    # The width, now a reference, cannot reach the old widest section.
    assert 2.0 * lever.KNIFE_SHOULDER_X_MAX < lever.HEX_W + lever.HEX_BAND
    # Nominal geometry, straight bore: 8.90 deg.
    assert knife_mount.KNIFE_FREE_ROCK_DEG == pytest.approx(8.900, abs=5e-3)
    assert math.isclose(
        lever.KNIFE_FACE_NORMAL[0] ** 2 + lever.KNIFE_FACE_NORMAL[1] ** 2, 1.0
    )


def test_the_summing_interference_rows_match_their_owners() -> None:
    # _sm_summing_interference (reach) and _ha_harmonic_analyzer_interference
    # (dowel press) keep the knife-mount-owned terms as literals.
    # The literal stays on the 36.50 grip the stud's cut length reads
    # (sm_vn_knife_hanger_stud_spec); the 1.437 grip moves the reach 0.0002.
    assert summing_interference._KNIFE_HANGER_REACH == pytest.approx(
        asm.HANGER_REACH, abs=5e-4
    )
    # Owner ruling 2026-10-24 (T+H3): the dowel press row is the crossbar
    # ream's (smallest Ø.1240, .47 deep), checked at the top level.
    assert top_interference._KNIFE_DOWEL_HOLE_MIN == pytest.approx(
        dowel.PRESS_HOLE_DIA + min(dowel.PRESS_HOLE_DIA_BAND)
    )
    assert top_interference._KNIFE_DOWEL_DIA_MAX == pytest.approx(dowel.DIA_MAX)
    assert top_interference._KNIFE_DOWEL_PRESS_DEPTH == pytest.approx(
        dowel.PRESS_DEPTH
    )
    assert top_interference._KNIFE_DOWEL_PRESS_DEPTH == pytest.approx(
        top_frame.HANGER_PIN_HOLE_DEPTH
    )
    assert screw.THREAD == knife_mount.STUD_THREAD == "#10-24"
    assert THREAD_MAJOR_MM["#10-24"] == knife_mount.STUD_THREAD_MAJOR
    assert TAP_DRILL_MM["#10-24"] == knife_mount.STUD_TAP_DIA
