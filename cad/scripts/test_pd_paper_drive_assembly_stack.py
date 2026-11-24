"""The paper-drive assembly's layout and tolerance stacks, checked offline.

These guards ran at import of ``build_pd_paper_drive_assembly.py``, so a COM leaf on the farm
paid for them before SolidWorks opened.  They are pure functions of the
spec modules and the builder's own placement constants, so they run here
under ``check:recipe`` instead.  Each stack reads the values the builder
places from.
"""

from __future__ import annotations

import pytest

import build_pd_paper_drive_assembly
import _sprocket_seat_geometry as seat_geometry
import build_pd_platen_clip
import build_pd_platen_guide
import math
import paper_drive_geom
import pd_cluster_air as CLUSTER_AIR
import pd_feed_rack_screw_spec as RACK_SCREW
import pd_feed_rack_spec
import pd_guide_lock_spec
import pd_latch_hook_geometry as HOOK
import pd_platen_bottom_guide_spec as BOTTOM_GUIDE
import pd_support_bar_spec as BAR
import pd_transgear_arm_geometry as ARM
import pd_transgear_arm_plate_geometry as ARM_PLATE
import pd_transgear_arm_spec as ARM_SPEC
import pd_transgear_disc_hub_geometry as DISC_HUB_GEOM
import pd_transgear_disc_hub_spec as DISC_HUB
import pd_transgear_drive_collar_spec as COLLAR
import pd_transgear_feed_pinion_spec as FEED
import pd_transgear_knob_bush_geometry as BUSH
import pd_transgear_knob_cup_spec as CUP
import pd_transgear_knob_shaft_spec as KNOB_SPEC
import pd_transgear_knob_thrust_ring_spec as RING
import pd_transgear_pin_spec as PIN
import pd_transgear_pivot_spacer_spec as SPACER
import pd_transgear_rear_bushing_spec as REAR_BUSHING
import pd_transgear_removable_spec as REMOVABLE
import pd_vn_transgear_arm_plate_locating_pin_spec as LOCATING_PIN
import pd_vn_transgear_hub_key_pin_spec as HUB_KEY_PIN
import pd_vn_transgear_knob_cup_screw_spec as CUP_SCREW
import pd_vn_transgear_knob_drive_pin_spec as KNOB_PIN
import pd_vn_transgear_latch_pin_spec as LATCH_PIN
import transgear_cluster_fit as CLUSTER
import transgear_hanger_joints as HANGER

# A running clearance under the support bar, with no contact at the printed
# worst case: the platen's bottom rail must not drag on the bar's bottom edge.
_BOTTOM_RAIL_RUNNING_FLOOR = 0.10


def _platen(paper) -> None:
    assert (
        abs(
            paper.GUIDE_Y[0]
            - paper.PLATE_Y0
            - BOTTOM_GUIDE.UNDERSIDE_ABOVE_PLATEN_BOTTOM
        )
        <= 1e-5
    ), "MHA-PD-27's underside is off the MHA-PD-26 strip's flat top"
    # The placement below names the member literally (the build graph reads it).
    assert (RACK_SCREW.STEM, RACK_SCREW.CONFIGURATION) == (
        "sh-vn-fillister-screw-91794a055",
        "RackScrew",
    ), "the rack-screw placement names another member"
    # BOTTOM_RAIL_CLEARANCE is derived (the bar hangs from the top rail's
    # underside, MHA-PD-27 sits at its own y), so hold the gap it leaves
    # against a running floor stated here, rebuilt from the parts' own
    # printed bands at the worst case: the bar at its tallest, the rail at its
    # tallest and highest on the platen (#3163 review).
    worst_gap = (
        paper.GUIDE_Y[1]
        - BAR.BAR_HEIGHT
        - BAR.BAR_HEIGHT_BAND
        - (
            paper.GUIDE_Y[0]
            + BOTTOM_GUIDE.GUIDE_HEIGHT
            + max(paper._RAIL_HEIGHT_DEVS[0][1], 0.0)
            + paper.BOTTOM_GUIDE_Y_BAND
        )
    )
    assert worst_gap >= _BOTTOM_RAIL_RUNNING_FLOOR, (
        f"the platen's bottom rail would rub the support bar ({worst_gap:.3f} mm)"
    )
    assert abs(BOTTOM_GUIDE.GUIDE_DEPTH - paper.GUIDE_DEPTH) <= 1e-9, (
        "the two rails' depths differ, so their lock plates do"
    )


def _transgear_arm_and_latch(paper) -> None:
    assert (
        abs(math.dist(paper.STUD_XY, paper.PIVOT_XY) - ARM.PIN_STATION)
        <= 0.5 * 10.0**-ARM_SPEC.STATION_PLACES
    ), "the stud is off the arm's printed station from the pivot"
    _PLATE_BORE_XY = paper._on_arm(ARM_PLATE.BORE_STATION, ARM_PLATE.BORE_OFFSET)
    assert math.dist(paper.KNOB_SHAFT_XY, _PLATE_BORE_XY) <= 1e-3, (
        f"arm plate bore {_PLATE_BORE_XY} is off the knob mesh axis {paper.KNOB_SHAFT_XY}"
    )
    assert abs(paper.SPACER_Z0 + SPACER.LENGTH - paper.ARM_Z0) <= 1e-9, (
        "the arm's front face is off the pivot spacer's rear face"
    )
    assert (
        paper.PLATE_Z0 - ARM.THICKNESS
        < paper.LOCATING_PIN_Z0 - LOCATING_PIN.LENGTH
        < paper.PLATE_Z0
        < paper.LOCATING_PIN_Z0
    ), "the locating dowels do not sit inside the arm's through reams"
    # The hook's arm lies square to the hanger's latched direction, its strip's
    # mid-plane crossing the pin's axis at PIN_AXIS_XY, HOLE_STATION from P.
    assert abs(HOOK.ARM_ANGLE_DEG - paper.ARM_ANGLE_DEG) <= 1e-9, (
        "the latch hook is formed to another hanger angle"
    )
    assert math.dist(HOOK.PIN_AXIS_XY, paper._on_arm(HOOK.HOLE_STATION)) <= 1e-9, (
        "the latch hook's pin crossing is off the arm's line"
    )
    # The pin's axis passes inside the hook's round pin hole (square to it, so
    # the pin's section is a circle on the hole's), and the largest pin bears on
    # the hole's lower (-N) edge: the latched hanger rests there with the feed
    # pinion in the rack.
    _pin_hole_offset = math.dist(HOOK.PIN_AXIS_XY, HOOK.PIN_HOLE_XY)
    assert abs(HOOK.PIN_HOLE_Z - ARM.PIN_MACHINE_Z) <= 1e-9, (
        "the latch hook's pin hole is off the pin's height"
    )
    assert (
        _pin_hole_offset + LATCH_PIN.DIA_MAX / 2.0 <= HOOK.PIN_HOLE_DIA / 2.0 + 1e-9
    ), f"latch pin axis is {_pin_hole_offset:.3f} off the hook's pin hole centre"
    _pin_hole_n = (HOOK.PIN_HOLE_XY[0] - HOOK.PIN_AXIS_XY[0]) * paper.ARM_N[0] + (
        HOOK.PIN_HOLE_XY[1] - HOOK.PIN_AXIS_XY[1]
    ) * paper.ARM_N[1]
    assert (
        abs(_pin_hole_n - _pin_hole_offset) <= 1e-9
        and abs(_pin_hole_n + LATCH_PIN.DIA_MAX / 2.0 - HOOK.PIN_HOLE_DIA / 2.0) <= 1e-6
    ), "the largest latch pin does not bear on the hook hole's lower edge"
    assert abs(paper.PIN_Z0 - (paper.ARM_Z0 + ARM.THICKNESS)) <= 1e-9, (
        "the pin's head is off the arm's rear face"
    )


def _cluster_stack_and_hub_key_pin(paper) -> None:
    assert (
        abs(paper.REAR_BUSHING_Z0 - (paper.ARM_Z0 - CLUSTER.SHIM_STACK_MODEL)) <= 1e-9
    ), "the rear bushing is off the shims on the arm's front face"
    assert abs(paper.DISC_Z0 - CLUSTER.DISC_FRONT_Z) <= 1e-9, (
        "the disc is off the cluster stack's station"
    )
    assert abs(paper.FRONT_BUSHING_Z0 - CLUSTER.FRONT_BUSHING_REAR_Z) <= 1e-9, (
        "the front bushing is off the sleeve's nose"
    )
    assert abs(paper.HUB_FRONT_Z - CLUSTER.HUB_FRONT_Z) <= 1e-9, (
        "the hub's front face is off the cluster stack's station"
    )
    assert abs(paper.DISC_Z0 + DISC_HUB_GEOM.SPIGOT_LENGTH - CLUSTER.STEP_Z) <= 1e-9, (
        "the hub's spigot end is off the sleeve's step face"
    )
    assert (
        abs(paper.HUB_FRONT_Z - paper.FRONT_BUSHING_Z0 - CLUSTER.RECESS_NOMINAL) <= 1e-9
    ), "the hub's front face is off its nominal recess behind the nose"
    assert abs(CLUSTER.RING_FRONT_Z - (paper.PIN_Z0 - PIN.GROOVE_STATION)) <= 1e-9, (
        "the ring is off the pin groove's load wall"
    )
    _HUB_KEY_PIN_X_SPAN = (
        DISC_HUB.KEY_PIN_STOP_X,
        DISC_HUB.KEY_PIN_STOP_X + HUB_KEY_PIN.LENGTH,
    )
    # The modelled pin's side stands off the modelled flat inside the hub spec's
    # band (no contact row). Beyond the flat's width the boss's round falls away
    # from the pin faster than the flat's plane, so the same air clears it too.
    HUB_KEY_PIN_FLAT_AIR = (
        DISC_HUB.KEY_PIN_CHORD_OFFSET - HUB_KEY_PIN.DIA / 2.0 - FEED.FLAT_TO_AXIS
    )
    assert 0.0 < HUB_KEY_PIN_FLAT_AIR <= max(DISC_HUB.KEY_PIN_FLAT_AIR), (
        f"the hub key pin's side does not stand off the sleeve flat: {HUB_KEY_PIN_FLAT_AIR:.4f}"
    )
    # Sleeve stations run forward (machine -Z) from its rear face at FEED_Z0: the
    # pin's whole section lies over the flat, ahead of its end wall and short of
    # the nose.
    _HUB_KEY_PIN_SLEEVE_STATION = paper.FEED_Z0 - paper.HUB_KEY_PIN_Z
    assert (
        FEED.FLAT_END_STATION + HUB_KEY_PIN.DIA / 2.0
        < _HUB_KEY_PIN_SLEEVE_STATION
        < FEED.OVERALL_LENGTH - HUB_KEY_PIN.DIA / 2.0
    ), "the hub key pin is off the sleeve's flat"
    # Both ends' outer corners stay under the hub's O.D.
    assert (
        max(
            math.hypot(x, DISC_HUB.KEY_PIN_CHORD_OFFSET + HUB_KEY_PIN.DIA / 2.0)
            for x in _HUB_KEY_PIN_X_SPAN
        )
        < DISC_HUB.HUB_DIA / 2.0
    ), "a hub key pin end stands proud of the hub body"
    assert (
        paper.HUB_FRONT_Z < paper.HUB_KEY_PIN_Z < paper.DISC_Z0 - DISC_HUB.FLANGE_THICK
    ), "the hub key pin is off the hub body"
    assert seat_geometry.PIN_HOLE_ANGLES_DEG == (90.0, 270.0), (
        "identity-placed removables expect pin holes on +/-Y"
    )


def _knob_collar_and_drive_pins(paper) -> None:
    assert paper.KNOB_COLLAR_FRONT_GAP >= -1e-9, (
        f"the drive collar's nominal front overlaps the knob wheel by "
        f"{-paper.KNOB_COLLAR_FRONT_GAP:.4f}"
    )
    assert (
        COLLAR.LENGTH_FITTED_MIN
        <= paper.KNOB_COLLAR_FITTED_LENGTH
        <= COLLAR.LENGTH_FITTED_MAX
    ), (
        f"the collar faced to F is {paper.KNOB_COLLAR_FITTED_LENGTH:.4f}, outside its fitted "
        f"{COLLAR.LENGTH_FITTED_MIN}..{COLLAR.LENGTH_FITTED_MAX}"
    )
    assert (
        abs(
            paper.KNOB_COLLAR_SEAT_Z
            - seat_geometry.DRIVE_PIN_TIP_Z
            - COLLAR.DRIVE_PIN_PROUD
        )
        <= 1e-9
    ), "the wheel seat's drive-pin tips are off the collar's DRIVE_PIN_PROUD"
    assert paper.KNOB_DRIVE_PIN_TIP_Z < paper.KNOB_COLLAR_SEAT_Z, (
        "knob drive-pin tips stand clear of the knob wheel's pin holes"
    )
    assert abs(KNOB_PIN.DIA - seat_geometry.DRIVE_PIN_DIA) <= 1e-12, (
        "transgear-knob-drive-pin is not the removable's drive pin"
    )
    assert COLLAR.PIN_CIRCLE_RADIUS == seat_geometry.PIN_CIRCLE_RADIUS, (
        "the collar's pin circle is not the removable's"
    )
    # #2425: the thrust ring's rear face on the MHA-PD-28 bush's hub face, the
    # bush's shoulder on the plate's face A.
    assert abs(paper.KNOB_RING_Z0 + RING.LENGTH - paper.KNOB_BUSH_Z0) <= 1e-9, (
        "the thrust ring does not reach the knob bush's hub face"
    )
    assert abs(paper.KNOB_BUSH_Z0 + BUSH.HUB_LENGTH - paper.PLATE_Z0) <= 1e-9, (
        "the knob bush's shoulder is off the plate's face A"
    )
    assert abs(paper.KNOB_BUSH_REAR_Z - paper.KNOB_BUSH_Z0 - BUSH.LENGTH) <= 1e-9, (
        "the knob bush's rear face is off its length from the hub face"
    )
    # The cup's front face END_FLOAT behind the bush's rear face (faced to it at
    # fit-up); the journal's end its stand-out behind that face, in the pilot.
    assert abs(paper.KNOB_END_FLOAT - KNOB_SPEC.END_FLOAT) <= 1e-9
    assert (
        abs(
            paper.KNOB_SHAFT_REAR_Z
            - paper.KNOB_BUSH_REAR_Z
            - KNOB_SPEC.JOURNAL_STANDOUT
        )
        <= 1e-9
    ), "the journal's end is off its stand-out behind the bush's rear face"
    KNOB_CUP_REAR_Z = paper.KNOB_CUP_Z0 + CUP.LENGTH
    assert (
        paper.KNOB_CUP_Z0
        < paper.KNOB_SHAFT_REAR_Z
        <= paper.KNOB_CUP_Z0 + CUP.PILOT_DEPTH
    ), "the knob shaft's rear end is not inside the knob cup's pilot"
    # MHA-PD-VN-71: under its head on the web's rear face (the counterbore
    # floor), its head inside the cup, its fully threaded shank through the
    # web into the journal's tap: rule 18 engagement, tip short of the tap's
    # full thread.
    assert abs(paper.KNOB_CUP_SCREW_Z0 - (KNOB_CUP_REAR_Z - CUP.CBORE_DEPTH)) <= 1e-9
    assert paper.KNOB_CUP_SCREW_Z0 + CUP_SCREW.HEAD_H <= KNOB_CUP_REAR_Z
    engaged = paper.KNOB_SHAFT_REAR_Z - (paper.KNOB_CUP_SCREW_Z0 - CUP_SCREW.LENGTH)
    assert abs(engaged - paper.KNOB_CUP_SCREW_ENGAGED) <= 1e-9
    assert (
        KNOB_SPEC.ENGAGEMENT_FLOOR_D * CUP_SCREW.MAJOR_DIA
        <= engaged
        <= KNOB_SPEC.REAR_TAP_FULL_THREAD_MIN
    ), f"the cup screw engages {engaged:.4f} of the journal's tap"
    # F, the knob shaft's 15T front face (the drive collar's seat), stands the
    # bush's hub, thrust ring and 15T chain ahead of the arm's rear face.
    # The disc is not fitted to it: the cluster's stack places the disc from the
    # same rear face (transgear_cluster_fit), and the model's m is the cluster
    # rearward, m_fwd plus the model's shimmed end float.
    _F_FROM_ARM_Z = (
        paper.ARM_Z0
        + ARM.THICKNESS
        - BUSH.HUB_LENGTH
        - RING.LENGTH
        - KNOB_SPEC.FACE_WIDTH
    )
    assert (
        abs(_F_FROM_ARM_Z - paper.KNOB_SHAFT_Z0) <= 1e-9
        and abs(CLUSTER.F_Z - paper.KNOB_SHAFT_Z0) <= 1e-9
    ), "F is off the arm, bush hub and thrust ring chain"
    assert abs(paper.DISC_Z0 - paper.KNOB_SHAFT_Z0 - CLUSTER.MODEL_M) <= 1e-9, (
        "the model's disc is off the cluster stack's station from F"
    )


def _platen_rack_and_chain_air(paper) -> None:
    assert (
        abs(
            paper.PLATEN_AIR.terms["MHA-PD-20 spacer rear face perpendicularity"]
            + paper.PLATEN_AIR.terms["MHA-PD-20 spacer front face perpendicularity"]
            - paper.HANGER_TILT_AT_DISC_RIM
        )
        <= 1e-9
    ), "the platen stack's spacer terms are not the hanger's tilt"
    assert FEED.FULL_DEPTH_MIN >= paper.RACK_FRONT_FROM_SLEEVE_REAR_WORST, (
        f"MHA-PD-10 12T full depth may stop {FEED.FULL_DEPTH_MIN:.3f} from the rear "
        f"face, inside the rack's worst reach {paper.RACK_FRONT_FROM_SLEEVE_REAR_WORST:.3f}"
    )
    # The MHA-PD-24 rear bushing's front face to the MHA-PD-26 strip's back face (its
    # Ø9 .X can reach the rack's crests radially): the arm forward on the
    # shortest spacer, the bar thinnest, the strip set rearmost at its widest,
    # the bushing (and its
    # shims) following the sleeve forward to the sleeve's most forward rear face,
    # and the hanger's tilt at the bushing's far rim.
    BUSHING_RACK_AIR_NOMINAL = (
        paper.REAR_BUSHING_Z0 - REAR_BUSHING.LENGTH - paper.RACK_BACK_Z
    )  # 3.03
    BUSHING_RACK_AIR_WORST = (
        BUSHING_RACK_AIR_NOMINAL
        - SPACER.LENGTH_BAND
        - BAR.BAR_DEPTH_REACH
        - paper._RACK_BACK_REARWARD_BAND
        - (
            CLUSTER.SLEEVE_REAR_FORWARD_FROM_ARM[1]
            - REAR_BUSHING.LENGTH
            - CLUSTER.SHIM_STACK_MODEL
        )
        - HANGER.HANGER_TILT
        * (
            paper._P_TO_S
            + (
                REAR_BUSHING.OD
                + paper.printed_band_mm(REAR_BUSHING.OD_PLACES, unit=REAR_BUSHING.UNIT)
            )
            / 2.0
        )
    )  # 1.69
    assert BUSHING_RACK_AIR_WORST >= 0.0, (
        "MHA-PD-24 rear bushing enters the MHA-PD-26 rack at the printed worst case: "
        f"air {BUSHING_RACK_AIR_WORST:.4f} (R9-68)"
    )
    CHAIN_DISC_AXIAL_AIR_WORST = paper.DISC_Z0 - (
        seat_geometry.SEAT_FACE_Z + paper.CHAIN_REACH_REAR_WORST
    )  # 3.0635 = 6.65 - 3.5865
    assert CHAIN_DISC_AXIAL_AIR_WORST > 0.0, (
        f"bought #25 chain reaches the reducer disc: air {CHAIN_DISC_AXIAL_AIR_WORST:.4f}"
    )
    assert abs(paper.KNOB_COLLAR_R_WORST - CLUSTER_AIR.COLLAR_RIM_R) <= 1e-9, (
        "the collar air stack's rim is not the collar's print-worst rim"
    )
    assert (
        paper.KNOB_COLLAR_R_WORST + paper.KNOB_WHEEL_SEAT_FLOAT
        < paper.KNOB_CHAIN_INNER_R
    ), "knob drive collar reaches the knob chain plates' inner edge"


def _thumbnut(paper) -> None:
    assert paper.THUMBNUT_THREAD == KNOB_SPEC.THREAD, (
        f"thumbnut tap {paper.THUMBNUT_THREAD} is not the knob shaft's {KNOB_SPEC.THREAD}"
    )
    assert paper.THUMBNUT_AIR > 0.0, (
        "the thumbnut clamps the knob wheel: its pilot is not proud"
    )
    assert paper.THUMBNUT_FRONT_Z < paper.KNOB_SHAFT_FRONT_Z < paper.THUMBNUT_Z0, (
        f"knob shaft front {paper.KNOB_SHAFT_FRONT_Z} must end inside the thumbnut"
        f" ({paper.THUMBNUT_FRONT_Z} .. {paper.THUMBNUT_Z0})"
    )
    # The flange must still RETAIN the wheel: cover its bore with a shoulder.
    # The drive-pin tips end inside the wheel's plate, behind the flange's seat.
    assert paper.THUMBNUT_FLANGE_DIA >= seat_geometry.BORE_DIA + 1.0, (
        "thumbnut flange slips into the removable's bore -- retains nothing"
    )
    assert paper.KNOB_DRIVE_PIN_TIP_Z - paper.THUMBNUT_Z0 > 0.0, (
        "knob drive-pin tips reach the thumbnut flange"
    )
    assert paper.THUMBNUT_HEAD_DIA / 2.0 <= paper._chain_inner_wrap_r, (
        "thumbnut head reaches the chain's inner plate wrap"
    )
    assert (
        max(paper.THUMBNUT_HEAD_DIA, paper.THUMBNUT_FLANGE_DIA) / 2.0
        <= paper.KNOB_CHAIN_INNER_R
    ), "thumbnut reaches the bought chain's inner plate edge"


def _latch_hook_frame(paper) -> None:
    assert [list(row) for row in HOOK.LOCAL_TO_MACHINE] == paper.IDENTITY, (
        "the latch hook's frame is not the machine's"
    )
    assert (
        abs(HOOK.BAR_BACK_FACE_Z - paper.BAR_BACK_Z) <= 1e-9
        and abs(HOOK.BAR_CENTRE_Y - paper.BAR_CY) <= 1e-9
    ), "the latch hook's bar anchors are off the support bar"
    assert HOOK.BBOX_Z[0] >= paper.BAR_BACK_Z - 1e-9, (
        f"latch hook reaches z {HOOK.BBOX_Z[0]:.2f}, bar back face {paper.BAR_BACK_Z}"
    )
    # The part's hole positions are rounded to 1e-6 (pd_latch_hook_geometry).
    for _screw, _tap_x, _hole_x in zip(
        paper.HOOK_BRACKET_SCREW_POS, BAR.BRACKET_TAP_X, HOOK.SCREW_HOLE_X, strict=True
    ):
        assert (
            abs(_screw[0] - _tap_x) <= 1e-9
            and abs(_screw[1] - (paper.BAR_CY + BAR.HANGER_TAP_Y)) <= 1e-9
            and abs(HOOK.PART_ORIGIN_MACHINE[0] + _hole_x - _screw[0]) <= 1e-6
            and abs(HOOK.PART_ORIGIN_MACHINE[1] + HOOK.SCREW_HOLE_Y - _screw[1]) <= 1e-6
        ), "a latch-hook screw hole is off its tap in the bar"


def _flat_pin_and_platen_phasing(paper) -> None:
    assert (
        abs(paper.KNOB_FLAT_PIN_Z0 + COLLAR.FLAT_PIN_LENGTH - paper.KNOB_COLLAR_REAR_Z)
        <= 1e-9
    ), "the faced flat pin is not flush with the model collar's rear"
    assert paper.KNOB_FLAT_PIN_CREST_AIR > 0.0, (
        "the collar's flat pin crest reaches the knob shaft's D-flat"
    )
    assert abs(paper.PLATE_X0_PHASING) <= paper.RACK_PITCH / 2.0, (
        f"platen phasing {paper.PLATE_X0_PHASING:.4f} exceeds half the rack pitch"
    )
    assert abs(pd_feed_rack_spec.BAR_LENGTH - paper.PLATE_WIDTH) <= 1e-9, (
        "the rack's ends cannot both be flush with the platen's"
    )
    assert math.isclose(
        paper_drive_geom.NET_RACK_TRAVEL_PER_CRANK_REV,
        (REMOVABLE.CRANK_TEETH / REMOVABLE.KNOB_TEETH)
        * (paper.THIRD_TEETH / paper.DISC_TEETH)
        * math.pi
        * paper.FEED_PD,
        rel_tol=1e-12,
    ), "paper_drive_geom feed law drifted from the assembly's mounted train"


def _fasteners(paper) -> None:
    assert math.isclose(
        paper.PLATEN_SOCKET_XY[0][1],
        paper._CLIP_Y0_LOCAL + build_pd_platen_clip.HOLE_INSET,
        abs_tol=1e-6,
    )
    assert math.isclose(
        paper.PLATEN_SOCKET_XY[1][1],
        paper.PLATE_HEIGHT - build_pd_platen_clip.HOLE_INSET,
        abs_tol=1e-6,
    )
    _clip_expected_y = sorted(
        (
            paper.PLATE_Y0 + paper.PLATEN_SOCKET_XY[0][1],
            paper.PLATE_Y0 + paper.PLATEN_SOCKET_XY[1][1],
        )
    )
    _plate_mid_x = paper.PLATE_X0 + paper.PLATE_WIDTH / 2.0
    for _sx, _origin_x, _origin_y, _rz in paper.CLIP_PLACEMENTS:
        _sin_rz = math.sin(math.radians(_rz))
        _socket_x = paper.PLATE_X0 + paper.PLATE_WIDTH - _sx
        assert math.isclose(
            _origin_x - _sin_rz * paper.CLIP_HOLE_Y, _socket_x, abs_tol=1e-9
        )
        _clip_hole_y = sorted(
            _origin_y + _sin_rz * local_x
            for local_x in (
                build_pd_platen_clip.HOLE_INSET,
                paper.CLIP_LENGTH - build_pd_platen_clip.HOLE_INSET,
            )
        )
        assert all(
            math.isclose(actual, expected, abs_tol=1e-9)
            for actual, expected in zip(_clip_hole_y, _clip_expected_y, strict=True)
        )
        assert (_socket_x - _plate_mid_x) * (-_sin_rz) < 0.0
    # Guide screws: 2 rows of 5, heads exactly 0.2 sub-flush of the platen front
    # and shanks engaged 5.2678 mm in blind #4-40 guide receivers.
    assert build_pd_platen_guide.SCREW_STATION_X == paper.PLATEN_GUIDE_HOLE_X
    assert tuple(sorted(BOTTOM_GUIDE.LOCK_TAP_X)) == tuple(
        sorted(paper.GUIDE_LOCK_HOLE_X)
    ), "the bottom rail's lock taps are off the top rail's stations"
    # The guide-lock stations ride the platen: each lock plate bridges the bar
    # behind one guide rail, its two screws on the rail's lock-tap row (holes
    # LOCK_HOLE_Y in from the plate's rail-side edge). The top rail's plate laps
    # past its top face (R9-59, LOCK_LIP); the bottom rail MHA-PD-27 reaches down
    # to the strip, so its plate lies wholly on the rail's back face, bridging up
    # across the running clearance onto the bar.
    LOCK_LIP = paper.LOCK_HOLE_Y - (paper.GUIDE_HEIGHT - paper.GUIDE_TAP_Y)
    assert (
        not any(
            abs(y - paper.LOCK_HOLE_Y) > 1e-9 for _, y in pd_guide_lock_spec.HOLE_XY
        )
        and LOCK_LIP >= 0.0
    ), "guide-lock screw holes are off the guide rail's tap row"
    assert paper.LOCK_TAP_ROW_Y[0] - paper.LOCK_HOLE_Y >= paper.GUIDE_Y[0], (
        "the bottom lock plate hangs below MHA-PD-27's underside"
    )


STACKS = (
    _platen,
    _transgear_arm_and_latch,
    _cluster_stack_and_hub_key_pin,
    _knob_collar_and_drive_pins,
    _platen_rack_and_chain_air,
    _thumbnut,
    _latch_hook_frame,
    _flat_pin_and_platen_phasing,
    _fasteners,
)


@pytest.mark.parametrize("stack", STACKS, ids=lambda stack: stack.__name__.lstrip("_"))
def test_stack_closes(stack) -> None:
    stack(build_pd_paper_drive_assembly)
