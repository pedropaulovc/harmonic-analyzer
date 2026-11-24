"""The drive-train assembly's layout and tolerance stacks, checked offline.

These guards ran at import of ``build_dt_drive_train_assembly.py``, so a COM leaf on the farm
paid for them before SolidWorks opened.  They are pure functions of the
spec modules and the builder's own placement constants, so they run here
under ``check:recipe`` instead.  Each stack reads the values the builder
places from; ``STACKS`` also re-checks a freshly executed builder (negative
controls perturb an upstream spec and observe these gates).
"""

from __future__ import annotations

import pytest

import build_dt_drive_train_assembly
import _cone_axis_constants
import _config
import _mcmaster_91794a112
import _mcmaster_91794a559
import _sprocket_seat_geometry as seat_geometry
import build_dt_arbor_pedestal
import build_dt_cone_pivot_post
import build_dt_crankshaft
import build_fr_harmonic_base
import channel_frame_geom
import cone_tip_cluster as tip_cluster
import crank_boss_rim
import crank_mesh_stack as crank_mesh
import cylinder_bank_layout as _bank
import dt_alignment_pinion_spec
import dt_arbor_pedestal_spec
import dt_cone_gear_shaft_spec
import dt_cone_pivot_post_spec
import dt_cone_swing_platform_crank_axis
import dt_cone_swing_platform_geometry
import dt_cone_swing_platform_spec
import dt_cone_tip_block_spec
import dt_cone_tip_gear_spec
import dt_crank_arm_spec
import dt_crank_drive_gear_spec
import dt_crank_handle_pivot_screw_spec
import dt_crank_hub_geometry
import dt_crank_pin_ring_spec
import dt_crank_pin_spec
import dt_crank_pinion_spec
import dt_crankshaft_spec
import dt_cylinder_end_disc_spec
import dt_drum_station_setting_spec as drum_station_setting
import dt_pinion_arbor_geometry
import dt_pinion_bracket_geometry
import dt_pinion_cam_geometry
import dt_pinion_cam_pin_geometry
import dt_pinion_handle_geometry
import dt_pinion_lift_rod_spec as _LIFT_ROD
import dt_pinion_spring_geometry
import dt_swing_stop_screw_spec
import dt_vn_cone_lock_knob_spec
import dt_vn_cone_shaft_key_spec as cone_key
import dt_vn_cone_tip_block_screw_spec
import dt_vn_crank_seat_drive_pin_spec as SEAT_PIN
import dt_vn_cylinder_bank_spring_spec as BANK_SPRING
import dt_vn_keeper_chain_screw_spec
import dt_vn_keeper_chain_spec
import dt_vn_pedestal_hold_down_screw_spec
import dt_vn_slotted_screw_spec
import math
import pinion_rig_layout as RIG
import pinion_rig_park_geometry
import sh_vn_arbor_set_screw_spec
import sh_vn_fillister_screw_90280a108_spec


def _drive_axis_and_cone_seats(drive) -> None:
    assert (
        abs(drive.Y_DRIVE - channel_frame_geom.CAM_SHAFT_XY[1]) <= 1e-9
        and abs(_cone_axis_constants.DRUM_X - channel_frame_geom.CAM_SHAFT_XY[0])
        <= 1e-9
    ), (
        f"drum shaft axis ({_cone_axis_constants.DRUM_X}, {drive.Y_DRIVE}) drifted from channel_frame_geom"
        f".CAM_SHAFT_XY {channel_frame_geom.CAM_SHAFT_XY} (gear_train.drive_axis_y_mm) -- the channel"
        " assembly and the error budget read that one"
    )
    # The drum z-pitch, incline and pitch-radius step come from cone_line (the
    # working train is recentered along the post's unchanged inclined journal).
    assert drive.POST_ROTATION_Y_DEG == 180.0, (
        "v2 post installation must preserve the exact Ry180 journal line"
    )
    # (ch30 p004 post fit).  The cone seats are derived from this same anchor, so
    # the complete cone and cylinder families retain all 20 radial mesh depths.
    # solved -52.3 +/- 0.9). The drum sits directly UNDER the rocker arms' rod-side
    # tips: the rocker pivot (+72.9) is the seesaw mid-span, its rod-pin hole 127.37
    # out, and every connecting rod hangs PLUMB from tip to cam (ch30 photos + GT
    # rocker-corner triangulation; the earlier "line-2 photogrammetry" oblique-rod
    # reading -- drum well clear of the support, LONG rods -- is refuted).
    # The whole cone/64T/crank train cascades rigidly off this (DRUM_TIP_X -> X_PITCH ...).
    # The cone/crank cluster extends EAST of the drum (machine east = -x, the
    # crank side), so every radial x-extent in the cascade below SUBTRACTS.
    # Z_DRUM0 (cone_line) is the shared station anchor. Cone seats, cylinder
    # faces, and channels translate as one rigid family without re-indexing the
    # j-to-j pairs.
    assert abs(drive.Z_DRUM0 - _cone_axis_constants.CHANNEL_Z0) <= 1e-9, (
        "channel station_z0 does not carry the fixed-post recenter"
    )
    # Exact-tracking self-check: the 20 mesh-derived seats lie on the shaft.
    for _j in range(20):
        _x, _z = drive.cone_seat(_j)
        _p = drive.cone_station(
            drive.SHAFT_T120_STATION + drive.GEAR_AXIS_SHIFT + _j * drive.SEAT_PITCH
        )
        assert abs(_p[0] - _x) <= 1e-9 and abs(_p[2] - _z) <= 1e-9, (
            f"cone seat {_j} off the shaft line: {(_x, _z)} vs {_p}"
        )


def _crank_mesh(drive) -> None:
    assert math.isclose(
        drive.GEAR64_CENTRE_STATION - drive.GEAR64_FACE / 2.0,
        drive.GEAR64_STATION
        + drive.GEAR_AXIS_SHIFT
        - dt_crank_drive_gear_spec.LAYOUT_FACE_WIDTH / 2.0
        + dt_crank_drive_gear_spec.SOUTH_FACE_SHIFT_NORTH,
        abs_tol=1e-9,
    ) and math.isclose(
        drive.GEAR64_CENTRE_STATION + drive.GEAR64_FACE / 2.0,
        drive._T120_SOUTH_FACE_STATION,
        abs_tol=1e-9,
    ), (
        "64T must keep its south face on the collar and bear on T120's south face "
        "(user ruling 2026-09-28)"
    )
    # Interleave of the two printed blanks at the fixed centre. Above ~1.2*ADD
    # the teeth are really engaged; below 2*ADD less 0.1 the tips keep root air.
    TIP16_C2C = (drive._GEAR64_TIP_DIA + dt_crank_pinion_spec.OUTSIDE_DIA) / 2.0
    CRANK_MESH_DEPTH = TIP16_C2C - drive.MESH16_C2C
    assert 1.2 * drive.ADD16 < CRANK_MESH_DEPTH < 2.0 * drive.ADD16 - 0.1, (
        "crank pair mesh depth left its derived band"
    )
    assert drive._DX16 > 0.0, (
        "the 64T no longer lies +x of the crank (crank_mesh_stack premise)"
    )
    assert math.isclose(
        drive.CRANK_ACTUAL_C2C, drive.MESH16_C2C, rel_tol=0.0, abs_tol=1e-9
    ) and math.isclose(
        drive.CRANK_ACTUAL_C2C, crank_mesh.FRAME_C2C, rel_tol=0.0, abs_tol=1e-9
    ), "crank physical centre must equal the normal-pitch mesh and stack reference"
    assert math.isclose(
        drive.CRANK_FACE_Z + dt_crankshaft_spec.SEAT_PINION,
        drive.PINION_TOOTH_Z - drive.PINION_FACE / 2.0,
        abs_tol=1e-6,
    ), "crankshaft pinion seat must match the restored boss-face feeler"


def _crank_hub_and_sprocket_seat(drive) -> None:
    # The common crank face keeps its photo-backed station.  The arm occupies
    # -183..-175 and the hub continues behind it to its rear face.
    # The shaft cylinder starts flush at -183; only its dome projects outboard.
    assert (
        abs(
            drive.CRANK_ARM_ORIGIN_Z
            - (drive.CRANK_FACE_Z + dt_crank_hub_geometry.HUB_SEAT_LENGTH)
        )
        <= 1e-9
    ), "arm inboard face left the hub shoulder station"
    # The selected crank sprocket MHA-PD-09 is the front chain wheel: its plate
    # spans BAND_FRONT_Z..SEAT_FACE_Z, the rear face on the crankshaft's integral
    # collar, one chain plane with the selected knob sprocket (ch. 23 p.56).
    # The sprocket itself lives in paper-drive; this module owns its seat.
    assert (
        abs(
            (drive.CRANKSHAFT_Z0 + dt_crankshaft_spec.SEAT_COLLAR)
            - seat_geometry.SEAT_FACE_Z
        )
        <= 1e-9
    ), "crankshaft SeatCollar datum off _sprocket_seat_geometry.SEAT_FACE_Z"
    assert (
        abs(drive.CRANK_HUB_SPROCKET_AIR - drive.CRANK_HUB_SPROCKET_AIR_CONTRACT)
        <= 1e-9
    ), (
        f"crank hub rear/sprocket air {drive.CRANK_HUB_SPROCKET_AIR:.3f} left the contracted "
        f"{drive.CRANK_HUB_SPROCKET_AIR_CONTRACT}"
    )
    assert drive.CRANK_HUB_SPROCKET_AIR_WORST > 0.0, (
        "crank hub rear/sprocket air closes at the SeatCollar band: "
        f"{drive.CRANK_HUB_SPROCKET_AIR_WORST:.3f}"
    )
    # The collar is one Ø17.5 seat spigot (SEAT_FACE_Z..CRANK_COLLAR_Z1) ahead of
    # the post boss; the hub's rear Ø16.5 relief runs from its barrel's rear
    # shoulder to the hub rear face.  Both let the #25 plates wrapping the crank
    # sprocket pass inside the boss/barrel diameters (Main's ruling, 2026-09-30).
    CRANK_HUB_BARREL_REAR_Z = (
        drive.CRANK_HUB_REAR_Z - drive.HUB_RELIEF_LENGTH
    )  # -161.65
    # The fitter lines the hub's front face up flush with the shaft's dome root
    # (CRANK_FACE_Z) before the match-ream, so the hub rear face is CRANK_FACE_Z
    # + the printed hub length; the arm's stock thickness is out of the stack.
    _HUB_REAR_Z_WORST = drive.CRANK_HUB_REAR_Z + dt_crank_hub_geometry.HUB_LENGTH_TOL
    _SEAT_FACE_Z_WORST = seat_geometry.SEAT_FACE_Z + min(drive.SEAT_COLLAR_BAND)
    CHAIN_BARREL_AXIAL_AIR = drive._STACK_A["seated"]  # 1.0635
    CHAIN_BARREL_AXIAL_AIR_WORST = drive._STACK_A["seated_worst"]  # 0.4135
    CHAIN_BARREL_AXIAL_AIR_FLOATED_WORST = drive._STACK_A["floated_worst"]  # 0.2135
    _STACK_A_MODELLED = (
        seat_geometry.SEAT_FACE_Z
        - seat_geometry.CHAIN_REACH_FRONT
        - CRANK_HUB_BARREL_REAR_Z
    )
    assert abs(CHAIN_BARREL_AXIAL_AIR - _STACK_A_MODELLED) <= 1e-9, (
        "stack A left the modelled hub shoulder station"
    )
    # B: thickest wheel, seat forward, hub long.
    CRANK_HUB_SPROCKET_AIR_PRINT_WORST = (
        _SEAT_FACE_Z_WORST - (seat_geometry.PLATE + max(seat_geometry.PLATE_BAND))
    ) - _HUB_REAR_Z_WORST  # 0.10
    for _what, _air in (
        ("chain / hub relief shoulder, wheel seated", CHAIN_BARREL_AXIAL_AIR_WORST),
        (
            "chain / hub relief shoulder, wheel floated onto the hub",
            CHAIN_BARREL_AXIAL_AIR_FLOATED_WORST,
        ),
        (
            "hub rear face / crank sprocket front face",
            CRANK_HUB_SPROCKET_AIR_PRINT_WORST,
        ),
        ("chain / post boss south face", drive.CHAIN_SPIGOT_AXIAL_AIR_WORST),
    ):
        assert _air > 0.0, f"{_what} axial air closes at print-worst: {_air:.4f}"
    assert (
        abs(
            dt_crankshaft_spec.DRIVE_PIN_DEPTH
            - (SEAT_PIN.LENGTH - seat_geometry.DRIVE_PIN_PROUD)
        )
        <= 1e-9
    ), "crank drive-pin depth left the pin length less its proud"
    assert (
        abs(drive.CRANK_DRIVE_PIN_Z0 - SEAT_PIN.LENGTH - seat_geometry.DRIVE_PIN_TIP_Z)
        <= 1e-9
    ), "crank drive-pin tips are off the removable's DRIVE_PIN_TIP_Z"
    assert abs(SEAT_PIN.DIA - seat_geometry.DRIVE_PIN_DIA) <= 1e-12, (
        "crank-seat-drive-pin is not the removable's drive pin"
    )


def _cylinder_bank_and_arbor_pedestals(drive) -> None:
    assert (
        abs(drive.Z_DRUM0 - _bank.STATION_Z0) <= 1e-9
        and abs(drive.Z_PITCH - _bank.BANK_PITCH) <= 1e-9
    ), "drive-train drum ladder left the cylinder-bank stations"
    assert (
        abs(
            dt_cylinder_end_disc_spec.WASHER_THICK
            - (_bank.SOUTH_DISC_Z[1] - _bank.SOUTH_DISC_Z[0])
        )
        <= 1e-9
    ), "placed end disc is not the bank layout's disc"
    assert (
        abs(_bank.BANK_SPRING_Z[1] - _bank.BANK_SPRING_Z[0] - BANK_SPRING.MODEL_HEIGHT)
        <= 1e-9
    ), "placed bank spring is not the layout's north-strap gap"
    assert abs(drive.BANK_SPRING_Z0 - _bank.G19_BACK_FACE_Z) <= 1e-9, (
        "bank spring does not bear directly on gear 19"
    )
    ARBOR_STRAP_SOUTH_Z = _bank.FRONT_STRAP_INNER_Z
    ARBOR_STRAP_NORTH_Z = _bank.BACK_STRAP_INNER_Z
    assert (
        abs(
            -drive.ARBOR_PEDESTAL_Z
            + drive.ARBOR_PED_STRAP_INNER_Z
            - ARBOR_STRAP_SOUTH_Z
        )
        <= 1e-9
        and abs(
            drive.ARBOR_PEDESTAL_NORTH_Z
            - drive.ARBOR_PED_STRAP_INNER_Z
            - ARBOR_STRAP_NORTH_Z
        )
        <= 1e-9
    ), "a pedestal origin no longer puts its strap on the bank face"
    _ARBOR_NORTH = drive.ARBOR_SOUTH_Z + drive.ARBOR_LENGTH
    for _label, _end, _outer in (
        (
            "south",
            drive.ARBOR_SOUTH_Z,
            -drive.ARBOR_PEDESTAL_Z + dt_arbor_pedestal_spec.STRAP_ROOT_Z,
        ),
        (
            "north",
            _ARBOR_NORTH,
            drive.ARBOR_PEDESTAL_NORTH_Z - dt_arbor_pedestal_spec.STRAP_ROOT_Z,
        ),
    ):
        assert abs(_end - _outer) <= 1e-9, (
            f"arbor {_label} end is not flush with its strap face"
        )
    _CROWN_APEX_Y = (
        drive.Y_BASE_TOP
        + dt_arbor_pedestal_spec.BORE_HEIGHT
        + dt_arbor_pedestal_spec.TOP_RADIUS
    )
    assert (
        abs(drive.Y_DRIVE - (drive.Y_BASE_TOP + dt_arbor_pedestal_spec.BORE_HEIGHT))
        <= 1e-6
    ), "arbor pedestal bore is off the drive axis"
    assert (
        abs(
            drive.SET_SCREW_TIP_Y
            + sh_vn_arbor_set_screw_spec.LENGTH
            - _CROWN_APEX_Y
            - _bank.SET_SCREW_SOCKET_PROUD
        )
        <= 1e-6
    ), "arbor set screw's socket is not SET_SCREW_SOCKET_PROUD over the apex"
    assert _bank.SET_SCREW_POINT_MARGIN >= _bank.SET_SCREW_POINT_MARGIN_MIN, (
        "arbor set screw's cup point spans the bore clearance by < SET_SCREW_POINT_MARGIN_MIN"
    )
    assert abs(drive.END_DISC_SOUTH_Z0 - ARBOR_STRAP_SOUTH_Z) <= 1e-9, (
        "south end disc does not bear directly on the datum strap"
    )
    assert abs(ARBOR_STRAP_NORTH_Z - _bank.BANK_SPRING_Z[1]) <= 1e-9, (
        "north spring does not bear directly on the adjustable strap"
    )
    for _band in (drive.ARBOR_PED_SOUTH_Z_BAND, drive.ARBOR_PED_NORTH_Z_BAND):
        _gap_x = (drive._SUPPORT_X - drive._SUPPORT_FOOT_HALF_X) - (
            drive.X_DRUM + build_dt_arbor_pedestal.FOOT_WIDTH / 2.0
        )
        _gap_z = max(
            _band[0] - (drive._SUPPORT_Z + drive._SUPPORT_FOOT_HALF_Z),
            (drive._SUPPORT_Z - drive._SUPPORT_FOOT_HALF_Z) - _band[1],
        )
        assert max(_gap_x, _gap_z) >= 0.5, (
            "an arbor pedestal foot reaches the rocker-support foot"
        )
    # The pinion must sit fully on the crankshaft.
    assert (
        drive.PINION_TOOTH_Z + drive.PINION_FACE / 2.0
        <= drive.CRANKSHAFT_Z0 + dt_crankshaft_spec.SHAFT_LENGTH
    ), "crankshaft too short for the M6.7 pinion station"


def _keeper_chain_and_crank_pinion(drive) -> None:
    assert (
        dt_crank_pin_spec.RING_HOLE_DIA - dt_crank_pin_ring_spec.WIRE_DIA
    ) / 2.0 >= 0.1, "keeper-ring wire does not clear the crank-pin cross-hole"
    assert (
        abs((drive.CRANKSHAFT_Z0 + drive.PIN_HOLE_HEIGHT) - drive.CRANK_PIN_Z) <= 1e-6
    ), "shaft and hub MHA-DT-09 stations do not coincide"
    assert (
        drive.CRANK_PIN_X0 + dt_crank_pin_spec.PIN_LENGTH
        >= drive.X_CRANK + drive.HUB_BARREL_DIA / 2.0 + 2.0
    ), "crank pin does not run out the far side of the hub"
    for _got, _want, _what in (
        (
            (*dt_vn_keeper_chain_spec.SCREW_XY, dt_vn_keeper_chain_spec.SCREW_HEAD_Z),
            (*drive.ANCHOR_SCREW_XY, drive.ANCHOR_HEAD_Z),
            "screw under-head point",
        ),
        (
            dt_vn_keeper_chain_spec.ANCHOR_EYE_CENTRE,
            (*drive.ANCHOR_SCREW_XY, drive.ANCHOR_EYE_Z),
            "end-link screw eye centre",
        ),
        (
            (dt_vn_keeper_chain_spec.RING_X, 0.0, dt_vn_keeper_chain_spec.PIN_Z),
            (
                drive.CRANK_PIN_X0 + drive.PIN_RING_HOLE_X,
                drive.CRANK_RING_Y,
                drive.CRANK_PIN_Z,
            ),
            "keeper-ring through leg",
        ),
    ):
        _placed = tuple(g + o for g, o in zip(_got, drive.CRANK_FRAME_ORIGIN))
        assert max(abs(p - w) for p, w in zip(_placed, _want)) <= 1e-9, (
            f"dt_vn_keeper_chain_spec {_what} {_placed} != placed {_want}"
        )
    assert tuple(drive.CRANK_RING_ROWS[0]) == dt_vn_keeper_chain_spec.RING_HANG, (
        f"keeper ring placed hanging along {drive.CRANK_RING_ROWS[0]}, "
        f"dt_vn_keeper_chain_spec hangs it along {dt_vn_keeper_chain_spec.RING_HANG}"
    )
    assert min(dt_vn_keeper_chain_spec.clearance_report().values()) >= 0.0, (
        "keeper chain touches a part it must clear"
    )
    assert dt_crank_arm_spec.ANCHOR_HOLE_SPEC.end == "through_all", (
        "crank-arm anchor tap is no longer through the arm"
    )
    assert (
        dt_crank_arm_spec.ANCHOR_HOLE_SPEC.size == dt_vn_keeper_chain_screw_spec.THREAD
    ), "crank-arm anchor tap does not match the keeper-chain screw"
    # drawing-guidelines.md rule 18: 1.5D of the #2-56's full thread (the screw
    # is threaded to the head).
    assert (
        drive.ANCHOR_THREAD_ENGAGEMENT >= 1.5 * dt_vn_keeper_chain_screw_spec.SHANK_DIA
    ), "anchor screw has under 1.5D thread engagement in the arm"
    assert drive.ANCHOR_TIP_RESERVE >= 0.5, (
        "anchor screw tip stands within 0.5 of the arm's inboard face"
    )
    assert abs(drive.CS_SHAFT_LENGTH - dt_crankshaft_spec.SHAFT_LENGTH) <= 1e-9, (
        "crankshaft part length does not cover the moved pinion"
    )
    assert (
        abs(
            (drive.CRANKSHAFT_Z0 + build_dt_crankshaft.SEAT_PINION)
            - (drive.PINION_TOOTH_Z - drive.PINION_FACE / 2.0)
        )
        <= 1e-6
    ), "crankshaft SeatPinion datum off the 16T station"
    assert abs(dt_crank_pinion_spec.FACE_WIDTH - drive.PINION_FACE) <= 1e-9, (
        "dt_crank_pinion_spec.FACE_WIDTH disagrees with PINION_FACE"
    )
    assert abs(dt_crank_pinion_spec.PIN_CLOCKING_DEG - drive.PINION_SEED_DEG) <= 1e-9, (
        "crankshaft matched-hole clock differs from the pinion seed"
    )
    assert (
        abs(
            (drive.CRANKSHAFT_Z0 + build_dt_crankshaft.PINION_PIN_STATION_Y)
            - drive.PINION_PIN_Z
        )
        <= 1e-6
    ), "crankshaft pin hole station off the pinion's pin station"
    assert abs(drive.PINION_PIN_LENGTH - dt_crank_pinion_spec.BOSS_DIA) <= 1e-9, (
        "pinion pin is not flush with the boss"
    )


def _tip_block_hold_down(drive) -> None:
    # User ruling 2026-09-29 (eight-views-4.png, lower right): the tip block is a
    # straight prism standing directly on the platform, its station fixed by ONE
    # hold-down hole under its centre.  Owner decision C1 keyed (2026-11-09, PR
    # #1992): dt_cone_tip_block_spec owns its stations on the .001 grid off the
    # pivot (TIP_BLOCK_PIVOT_OFFSET, set so the end screw's stack keeps its reach),
    # the block grows north from its south face, and MHA-DT-04 ends inside T024's
    # bore.  The platform's hole and the block spec must agree, and the hole sits
    # as far off the cone line as the block's foot tap sits off its end-screw axis,
    # so the block stands centred on the line.
    assert (
        abs(
            drive.TIP_BLOCK_STATION
            + drive.TIP_BLOCK_Z / 2.0
            - dt_cone_tip_block_spec.TIP_BLOCK_NORTH_FACE
        )
        <= 1e-9
        and abs(
            drive.TIP_BLOCK_STATION
            - drive.TIP_BLOCK_Z / 2.0
            - dt_cone_tip_block_spec.TIP_BLOCK_SOUTH_FACE
        )
        <= 1e-9
        and abs(
            dt_cone_tip_block_spec.TIP_BLOCK_NORTH_FACE
            - (
                drive.PIVOT_STATION
                - dt_cone_tip_block_spec.TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET
            )
        )
        <= 1e-9
        and abs(
            drive.TIP_BLOCK_STATION
            - (drive.PIVOT_STATION - dt_cone_tip_block_spec.TIP_BLOCK_PIVOT_OFFSET)
        )
        <= 1e-9
        and abs(
            dt_cone_swing_platform_spec.HOLDDOWN_LOCAL_Z
            + dt_cone_tip_block_spec.TIP_BLOCK_PIVOT_OFFSET
        )
        <= 1e-9
        and abs(drive.PLAT_HOLDDOWN_LOCAL_X - drive.TIP_FOOT_TAP_OFFSET_X) <= 1e-9
        and abs(dt_cone_tip_block_spec.FOOT_TAP_Z - drive.TIP_BLOCK_Z / 2.0) <= 1e-9
        and abs(drive.TIP_BLOCK_Z - tip_cluster.BLOCK_DEPTH_MM) <= 1e-9
        and abs(
            drive.SHAFT_FRONT_STATION
            + dt_cone_gear_shaft_spec.SECTIONS[-1][1]
            - dt_cone_gear_shaft_spec.TIP_END_STATION
        )
        <= 1e-9
    ), "cone_line tip-end stack drifted from the platform/shaft/block parts"
    # MHA-DT-VN-69 (rule-23 retention, owner ruling 2026-11-07, PR #2248):
    # the plate's dowel ream and the block foot's stand on the hold-down line, one
    # DOWEL_FROM_TAP along the plate's local x from the hold-down/foot tap.
    assert (
        abs(
            dt_cone_swing_platform_spec.TIP_DOWEL_LOCAL_Z
            - dt_cone_swing_platform_spec.HOLDDOWN_LOCAL_Z
        )
        <= 1e-9
        and abs(
            drive.PLAT_TIP_DOWEL_LOCAL_X
            - (drive.PLAT_HOLDDOWN_LOCAL_X + drive.TIP_DOWEL_FROM_TAP)
        )
        <= 1e-9
    ), "tip dowel ream left the hold-down line or its foot station"
    assert (
        drive.Y_BASE_TOP < drive.TIP_DOWEL_BOTTOM_Y < drive.Y_BASE_TOP + drive.PLAT_T
    ), "tip dowel's lower end left the plate's slip ream"
    # One journal drive height across the platform and both riders: plate
    # thickness under each foot + bore height = 54 above the base top.  The block
    # stands straight on PlateTop (no shim).
    assert (
        abs(
            (drive.Y_DRIVE - drive.Y_BASE_TOP)
            - (drive.PLAT_T + build_dt_cone_pivot_post.BORE_HEIGHT)
        )
        <= 1e-9
        and abs(
            (drive.Y_DRIVE - drive.Y_BASE_TOP)
            - (drive.PLAT_T + dt_cone_tip_block_spec.ADJUSTER_AXIS_HEIGHT)
        )
        <= 1e-9
    ), "cone axis height drifted between platform/post/block"
    assert (
        drive.HOLDDOWN_THREAD == dt_cone_tip_block_spec.HOLDDOWN_THREAD
        and abs(
            dt_vn_cone_tip_block_screw_spec.SHANK_LEN
            - dt_cone_tip_block_spec.HOLDDOWN_SCREW_LENGTH
        )
        <= 1e-9
        and abs(
            dt_vn_cone_tip_block_screw_spec.HEAD_DIA
            - dt_cone_swing_platform_spec.HOLDDOWN_SCREW_HEAD_DIA
        )
        <= 1e-9
        and abs(
            dt_vn_cone_tip_block_screw_spec.HEAD_H
            - dt_cone_swing_platform_spec.HOLDDOWN_SCREW_HEAD_H
        )
        <= 1e-9
    ), "MHA-DT-VN-60 is not the screw the tip block and platform were sized for"
    assert (
        dt_cone_swing_platform_spec.HOLDDOWN_HOLE_SPEC.size
        == drive.HOLDDOWN_THREAD.split("-", 1)[0]
    ), "platform hold-down counterbore is not sized for MHA-DT-VN-60"
    assert not any(
        abs(_have - _want) > 1e-9
        for _have, _want in zip(
            dt_cone_swing_platform_spec.HOLDDOWN_LEDGE_RANGE,
            dt_cone_tip_block_spec.HOLDDOWN_LEDGE_RANGE_MM,
            strict=True,
        )
    ), (
        f"platform hold-down ledge {dt_cone_swing_platform_spec.HOLDDOWN_LEDGE_RANGE} differs from the "
        f"range the tip block's engagement stack reads {dt_cone_tip_block_spec.HOLDDOWN_LEDGE_RANGE_MM}"
    )
    assert drive.POST_SCREW_INTO_PLATE <= drive.PLAT_T, (
        "MHA-DT-VN-61 stands proud of the MHA-DT-20 underside"
    )
    assert (
        drive.POST_SCREW_INTO_PLATE
        - 2.0 * dt_cone_swing_platform_spec.POST_MOUNT_TAP_EDGE_BREAK
        >= 0.84 * drive.POST_MOUNT_THREAD_DIA
        and dt_cone_swing_platform_spec.POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS >= 0.84
    ), "MHA-DT-VN-61 engages the MHA-DT-20 tap under 0.84D"
    # The shaft is placed by its front stub end; keep the station in lockstep with
    # the part's FRONT_STUB.
    assert abs(drive.SHAFT_FRONT_STATION + drive.SHAFT_FRONT_STUB) <= 1e-9, (
        "SHAFT_FRONT_STATION out of sync with the shaft FRONT_STUB"
    )


def _platform_containment(drive) -> None:
    assert drive.POST_PLATFORM_CONTAINMENT_MM >= drive.PLATFORM_CONTAINMENT_FLOOR_MM, (
        f"pivot post overhangs the swing platform: {drive.POST_PLATFORM_CONTAINMENT_MM:.3f}"
        f" mm inside its outline"
    )
    for _lbl, (_south, _north, _hx) in drive.PLATFORM_RIDER_SPANS.items():
        for _end in (_south, _north):
            assert (
                drive._plat_half_width(_end)
                >= _hx + drive.PLATFORM_CONTAINMENT_FLOOR_MM
            ), f"{_lbl} overhangs the swing platform at station {_end:g}"


def _tip_block_station(drive) -> None:
    # The stub end stands 1.0 mm proud of the post's inclined journal face.
    _STUB_END_Z = drive.cone_station(drive.SHAFT_FRONT_STATION)[2]
    _POST_SOUTH_STATION = drive.POST_STATION - drive.POST_CONE_BOSS_LENGTH / 2.0
    _POST_SOUTH_Z = drive.cone_station(_POST_SOUTH_STATION)[2]
    assert drive.SHAFT_FRONT_STATION <= _POST_SOUTH_STATION - 1.0 + 1e-9, (
        f"cone-shaft stub end {_STUB_END_Z:.2f} not proud of the post's south "
        f"flank {_POST_SOUTH_Z:.2f}"
    )
    assert (
        abs(
            drive.SHAFT_FRONT_STATION
            + dt_cone_gear_shaft_spec.COLLAR_START_STATION
            - drive._POST_NORTH_STATION
        )
        <= 1e-9
    ), "cone-shaft collar face is not on the post's north boss face"
    assert (
        abs(
            drive.SHAFT_FRONT_STATION
            + drive.SHAFT_COLLAR_END
            - drive._GEAR64_SOUTH_STATION
        )
        <= 1e-9
    ), "64T south face is not on the cone-shaft collar"
    _CONE_KEY_NORTH_MAX_LOCAL_Z = (
        drive.CONE_KEY_SOUTH_LOCAL_Z
        + cone_key.LENGTH
        + drive._printed_band_mm(cone_key.LENGTH_PLACES, unit=cone_key.UNIT)
    )
    _T024_SOUTH_LOCAL_Z = (
        drive.SHAFT_FRONT_STUB + dt_cone_gear_shaft_spec.gear_faces(16)[0]
    )
    assert (
        _config.cone_teeth(16) == 24
        and _CONE_KEY_NORTH_MAX_LOCAL_Z < _T024_SOUTH_LOCAL_Z
    ), (
        f"MHA-DT-VN-71's north end reaches {_CONE_KEY_NORTH_MAX_LOCAL_Z:.3f} at its print "
        f"maximum, not short of T024's south face {_T024_SOUTH_LOCAL_Z:.3f}"
    )


def _tip_end_play(drive) -> None:
    TIP_SOUTH_STATION = dt_cone_tip_block_spec.TIP_BLOCK_SOUTH_FACE
    _PIVOT_END_STATION = drive.BUSHING_SOUTH_STATION + tip_cluster.PIVOT_LENGTH_MM
    _SPIGOT_END_STATION = drive.TIP_GEAR_SOUTH_STATION - tip_cluster.SPIGOT_LENGTH_MM
    assert abs(dt_cone_tip_gear_spec.FACE_WIDTH - drive.CONE_FACE) <= 1e-9, (
        "MHA-DT-37's leaves are not one cone face wide"
    )
    assert (
        abs(drive.END_SCREW_END_STATION - dt_cone_tip_block_spec.END_SCREW_END_STATION)
        <= 1e-9
    ), (
        f"end screw end {drive.END_SCREW_END_STATION:.4f} is not the block spec's "
        f"{dt_cone_tip_block_spec.END_SCREW_END_STATION:.4f}"
    )
    assert (
        abs(
            dt_cone_tip_block_spec.TIP_BLOCK_NORTH_FACE
            - drive.END_SCREW_END_STATION
            - drive.TIP_END_SCREW_EMBED
        )
        <= 1e-9
    ), "end screw embed drifted from the block spec"
    assert (
        drive.SHAFT_END_PLAY[0]
        <= drive.END_SCREW_MODEL_END_PLAY_MM
        <= drive.SHAFT_END_PLAY[1]
    ), "modelled end play is outside SHAFT_END_PLAY"
    assert (
        _mcmaster_91794a559.SKU == tip_cluster.END_SCREW_SKU
        and dt_cone_tip_block_spec.END_SCREW_SKU == tip_cluster.END_SCREW_SKU
        and drive.END_SCREW_THREAD == tip_cluster.ADJUSTER_THREAD
    ), "MHA-DT-39 is not the end screw the tip block was sized for"
    # The head stands clear north of the block, the reamed end proud of its
    # south face toward the bushing.
    assert (
        drive.END_SCREW_HEAD_STATION > dt_cone_tip_block_spec.TIP_BLOCK_NORTH_FACE
        and drive.END_SCREW_END_STATION < TIP_SOUTH_STATION
    ), "end screw head or end is not outside MHA-DT-21"
    # The pivot runs in the end screw's reamed hole and never bottoms there; the
    # spigot stops short of the socket floor with MHA-DT-04's end inside T024.
    assert (
        drive.END_SCREW_END_STATION
        < _PIVOT_END_STATION
        < drive.END_SCREW_END_STATION + tip_cluster.END_HOLE_DEPTH_MM
    ), "MHA-DT-37's pivot leaves the end screw's hole or bottoms in it"
    assert (
        dt_cone_gear_shaft_spec.SOCKET_FLOOR_STATION < _SPIGOT_END_STATION
        and dt_cone_gear_shaft_spec.TIP_END_STATION
        <= dt_cone_gear_shaft_spec.T024_NORTH_FACE_STATION
        - tip_cluster.TIP_END_RECESS_MM
        + 1e-9
    ), "MHA-DT-37's spigot bottoms in the socket or the shaft end leaves T024"
    # r3: the screw threads only into the FAR jaw, from the slit's far wall on,
    # and that wall stands at most WORST_PINCH_FAR_WALL_MM from the head's (+X)
    # face at the printed limits; the placed screw must be the one the block's
    # stack was sized for.
    assert (
        _mcmaster_91794a112.SKU == dt_cone_tip_block_spec.PINCH_SCREW_SKU
        and abs(
            _mcmaster_91794a112.SHANK_LEN - dt_cone_tip_block_spec.PINCH_SCREW_LENGTH
        )
        <= 1e-9
    ), (
        f"placed pinch screw {_mcmaster_91794a112.SKU} ({_mcmaster_91794a112.SHANK_LEN}) is not the tip "
        f"block's {dt_cone_tip_block_spec.PINCH_SCREW_SKU} ({dt_cone_tip_block_spec.PINCH_SCREW_LENGTH})"
    )
    assert (
        _mcmaster_91794a112.SHANK_LEN - dt_cone_tip_block_spec.WORST_PINCH_FAR_WALL_MM
        >= 1.5 * drive.THREAD_MAJOR_MM[drive.PINCH_THREAD]
    ), "pinch screw lacks 1.5D of far-jaw thread at the printed worst case"


def _platform_on_base_and_crank_boss(drive) -> None:
    for _x_local, _z_local in drive._PLATFORM_VERTICES:
        _x_machine = drive._PPIVOT[0] + _x_local * drive.COS_I + _z_local * drive.SIN_I
        _z_machine = drive._PPIVOT[2] - _x_local * drive.SIN_I + _z_local * drive.COS_I
        assert (
            abs(_x_machine) <= drive._BASE_X_LIMIT + 1e-9
            and abs(_z_machine) <= drive._BASE_Z_LIMIT + 1e-9
        ), (
            f"cone swing platform vertex ({_x_machine:.3f}, {_z_machine:.3f}) "
            f"is outside harmonic-base top ({drive._BASE_X_LIMIT:.3f}, {drive._BASE_Z_LIMIT:.3f})"
        )
    # CRANK_AXIS_OFF is the distance the plate's crank axis sits EAST of the
    # pivot (east = machine -x).  The crank train mates to it, so it is the
    # fixed axis: pivot.x - X_CRANK, at Y_CRANK.
    assert (
        abs(
            dt_cone_swing_platform_crank_axis.CRANK_AXIS_OFF
            - (drive._PPIVOT[0] - drive.X_CRANK)
        )
        <= 1e-6
    ), (
        f"platform CRANK_AXIS_OFF {dt_cone_swing_platform_crank_axis.CRANK_AXIS_OFF} != pivot.x - X_CRANK "
        f"{drive._PPIVOT[0] - drive.X_CRANK:.6f}"
    )
    assert (
        abs(
            dt_cone_swing_platform_crank_axis.CRANK_AXIS_Y
            - (drive.Y_CRANK - drive.Y_BASE_TOP)
        )
        <= 1e-6
    ), "platform CRANK_AXIS_Y != Y_CRANK - Y_BASE_TOP"
    assert abs(drive._PPOST[0] - drive.X_CRANK) <= 1e-9, (
        "v2 crank boss no longer shares the post body centre x"
    )
    assert (
        abs(
            dt_cone_pivot_post_spec.CRANK_BORE_HEIGHT
            - (drive.Y_CRANK - drive.Y_BASE_TOP - drive.PLAT_T)
        )
        <= 1e-6
    ), "column CRANK_BORE_Y != Y_CRANK - Y_BASE_TOP - PLAT_T"
    _GAP_LO, _GAP_HI = drive.PINION_BOSS_NORTH_GAP_RANGE
    # (1) The modelled collar bears on the cast south face: the spec floors its
    # length to the two-place print, so the model stands under 0.01 off it.
    assert (
        abs(drive.CRANK_COLLAR_BOSS_AIR - dt_crankshaft_spec.COLLAR_BOSS_AIR) <= 1e-6
    ), (
        f"crank collar rear face {drive.CRANK_COLLAR_BOSS_AIR:.4f} off the post boss in the "
        f"layout; the crankshaft spec closes it to {dt_crankshaft_spec.COLLAR_BOSS_AIR:.4f}"
    )
    assert _GAP_LO - 1e-6 <= drive._BOSS_NORTH_GAP < _GAP_HI, (
        "v2 crank boss north/pinion clearance left its derived band"
    )
    assert (
        max(
            abs(
                drive._GEAR64_FROM_POST[0]
                - drive.GEAR64_POST_OFFSET * crank_boss_rim.SIN_I
            ),
            abs(drive._GEAR64_FROM_POST[1]),
            abs(
                drive._GEAR64_FROM_POST[2]
                - drive.GEAR64_POST_OFFSET * crank_boss_rim.COS_I
            ),
            abs(drive.Y_CRANK - drive.Y_DRIVE - crank_boss_rim.CRANK_AXIS_Y),
        )
        <= 1e-3
    ), "crank_boss_rim's post frame no longer matches this layout"
    assert (
        drive.GEAR64_POST_CLEARANCES
        and min(drive.GEAR64_POST_CLEARANCES.values())
        >= crank_boss_rim.FLOOR_CLEARANCE_MM
    ), "user ruling 2026-09-28"


def _crankshaft_proud_end(drive) -> None:
    # The model sits the 16T on its feeler and the collar within a print step of
    # the boss, so its proud length is the stack's nominal less the collar air.
    assert (
        abs(
            drive.CRANK_SHAFT_END_PROUD_NOMINAL_MODEL
            - (
                drive.CS_SHAFT_END_PROUD_NOMINAL
                - drive.CRANK_COLLAR_BOSS_AIR
                - (drive._BOSS_NORTH_GAP - drive.PINION_SEAT_FEELER)
            )
        )
        <= 1e-6
    ), (
        f"crankshaft end stands {drive.CRANK_SHAFT_END_PROUD_NOMINAL_MODEL:.4f} past the 16T in "
        f"the layout, off the spec's proud stack {drive.CS_SHAFT_END_PROUD_NOMINAL:.4f}"
    )
    assert (
        -1e-9
        <= drive.CS_SHAFT_END_PROUD_RANGE[0]
        <= drive.CRANK_SHAFT_END_PROUD_NOMINAL_MODEL
        <= drive.CS_SHAFT_END_PROUD_RANGE[1] + 1e-9
    ), (
        f"crankshaft end proud range {drive.CS_SHAFT_END_PROUD_RANGE} misses the 16T or the model"
    )


def _pinion_under_t120(drive) -> None:
    assert (
        drive.PINION_T120_CONCENTRIC["shoulder air"] >= drive.T120_PINION_AIR_FLOOR
    ), (
        f"16T full-OD shoulder leaves {drive.PINION_T120_CONCENTRIC['shoulder air']:.3f} mm to "
        f"the inclined T120 on its nominal axis, below the {drive.T120_PINION_AIR_FLOOR:.2f}-mm "
        "axial-air floor"
    )
    assert (
        drive.PINION_T120_CONCENTRIC["turned band radial"]
        >= drive.T120_TURNED_BAND_RADIAL_FLOOR
    ), (
        f"16T turned band passes {drive.PINION_T120_CONCENTRIC['turned band radial']:.3f} mm "
        "inside the T120 rim on its nominal axis, below the "
        f"{drive.T120_TURNED_BAND_RADIAL_FLOOR:.2f}-mm radial floor"
    )
    assert drive.CRANK_SHAFT_END_Z_MAX >= drive._SHAFT_NORTH_END - 1e-9, (
        "the crankshaft end's print-worst top falls below its model"
    )
    assert (
        drive.CRANK_SHAFT_END_NORTH_AIR_WORST >= drive.T120_TURNED_BAND_RADIAL_FLOOR
    ), (
        f"the proud crankshaft end (top z {drive.CRANK_SHAFT_END_Z_MAX:.3f}) passes "
        f"{drive.CRANK_SHAFT_END_NORTH_AIR_WORST:.3f} mm from the {drive.CRANK_SHAFT_END_NORTH_NEIGHBOUR} "
        f"at print-worst, below the {drive.T120_TURNED_BAND_RADIAL_FLOOR:.2f}-mm radial floor"
    )
    assert set(drive.T120_RUNNING_PLAY.values()) <= set(
        drive.PINION_T120_FITUP_PUSHED
    ), "the T120 fit-up check leaves running play unpushed"
    # So what the check reads is the pair's worst in service: a band or shoulder
    # that passes the feeler keeps that clearance however the plays then move.
    T120_FITUP_READING = drive.t120_fitup_reading()
    for _name, _reading in T120_FITUP_READING.items():
        assert _reading <= drive.PINION_T120_CLEARANCES[_name] + 1e-9, (
            f"the T120 fit-up check reads {_name} {_reading:.4f}, more than its service "
            f"worst {drive.PINION_T120_CLEARANCES[_name]:.4f}: its pose is not the closing one"
        )
    # The fit-up can always close: a band turned down to its fit-up minimum, or a
    # shoulder faced back to its short limit, passes the fit-up feeler at every
    # corner of the same stack.  The minimum is an actual size, not a toleranced one.
    T120_FITUP_LIMIT_CLEARANCES = {
        "turned band radial": drive.t120_fitup_reading(
            turned_dia=drive.PINION_TURNED_DIA_FITUP_MIN
            - 2.0 * drive._PINION_TURNED_RADIUS_UP
        )["turned band radial"],
        "shoulder air": drive.t120_fitup_reading(
            shoulder_length=dt_crank_pinion_spec.SHOULDER_LENGTH_FITUP_MIN
        )["shoulder air"],
    }
    for _name, _clearance in T120_FITUP_LIMIT_CLEARANCES.items():
        assert _clearance >= drive.PINION_T120_FITUP_FEELER, (
            f"16T {_name} to T120 at its fit-up limit is {_clearance:.3f} mm, under the "
            f"{drive.PINION_T120_FITUP_FEELER:.2f} fit-up feeler"
        )
    # T120's distance from the crank axis never falls as the crank rises, so the
    # band-turn heights run from the bottom of the printed band to one height.
    assert drive.Y_CRANK + min(drive._CRANK_HEIGHT_BAND) > drive.Y_DRIVE, (
        "the T120 band reading is not monotonic over the crank height band"
    )
    assert math.isclose(
        drive.gear64_contact_z(0.0), drive._GEAR64_CONTACT_Z, abs_tol=1e-9
    ), "gear64_contact_z disagrees with the seated pitch-cylinder azimuth"
    assert (
        drive.CRANK_ROW_ENGAGEMENT_FRACTION_WORST >= drive.CRANK_ROW_ENGAGEMENT_FLOOR
    ), (
        f"16T covers {drive.CRANK_ROW_ENGAGEMENT_FRACTION_WORST:.1%} of the 64T tooth row at worst, "
        f"below {drive.CRANK_ROW_ENGAGEMENT_FLOOR:.0%}"
    )


def _cone_pivot_screw(drive) -> None:
    # The base's pivot-screw hole sits exactly under the swing pivot -- both are
    # authored in the machine frame, so the coordinates agree directly (pre-#151
    # this module derived in the mirrored frame and the hole's x was the NEGATED
    # pivot x).  Both now read cone_line, so the check is exact, not a fit
    # window: it catches the base seat being sourced from anywhere else.
    assert (
        abs(drive.BASE_PIVOT_XZ[0] - drive._PPIVOT[0]) <= 1e-9
        and abs(drive.BASE_PIVOT_XZ[1] - drive._PPIVOT[2]) <= 1e-9
    ), (
        f"harmonic-base pivot-screw hole {drive.BASE_PIVOT_XZ} != machine swing pivot "
        f"({drive._PPIVOT[0]!r}, {drive._PPIVOT[2]!r})"
    )
    # The plate's reamed pivot bore runs on the stock shoulder as an H/h location
    # fit: least clearance zero at both maximum-material limits (bore at its
    # minimum, shoulder at its maximum), never negative (cone_set_stack).
    assert (
        drive.PLAT_PIVOT_HOLE_DIA + drive.PLAT_PIVOT_HOLE_BAND[1]
        >= drive.PSCREW_SHOULDER_DIA + drive.PSCREW_SHOULDER_DIA_BAND[0] - 1e-9
    ), "platform pivot bore does not clear the screw shoulder"
    assert (
        abs(
            drive.PSCREW_SHOULDER_LEN
            - dt_cone_swing_platform_spec.PIVOT_BEARING_THICKNESS
            - 0.25
        )
        <= 1e-9
    ), "pivot screw no longer provides 0.25 axial plate clearance"
    assert (
        dt_cone_swing_platform_spec.PIVOT_BEARING_RELIEF_DIAMETER
        - drive.PSCREW_HEAD_DIA
    ) / 2.0 + 1e-9 >= dt_cone_swing_platform_spec.PIVOT_HEAD_RADIAL_CLEARANCE, (
        "platform pivot relief lacks required radial head clearance"
    )


def _tip_print_worst(drive) -> None:
    # Owner ruling 2026-11-20 (#2726): the 3/4 end screw keeps rule 18's 1.5 D
    # at the print-worst embed, so MHA-DT-00 step 3A prints no shortfall.
    assert drive.END_SCREW_ENGAGEMENT_FLOOR_D == 1.5
    assert drive.END_SCREW_ENGAGEMENT_WORST_D >= 1.5, (
        f"end screw print-worst full thread {drive.END_SCREW_ENGAGEMENT_WORST_D:.4f}D "
        "is under rule 18's 1.5 D"
    )


def _lock_knob_and_swing_stop(drive) -> None:
    assert (
        dt_cone_swing_platform_geometry.SLOT_W - dt_vn_cone_lock_knob_spec.STUD_DIA
        >= 0.5
    ), "lock stud has <0.5 clearance in the platform notch"
    assert (
        abs(
            build_fr_harmonic_base.LOCK_STUD_ENGAGEMENT
            - (drive.KNOB_STUD_LEN - drive.PLAT_T)
        )
        <= 1e-9
    ), "base lock engagement does not use the stock stud excess"
    # Keep the stock knurled head's base seat outside a conservative plan-envelope
    # of every adjacent gear; the real solids must therefore have clearance at
    # every tooth phase.
    _KNOB_GEAR_CLEARANCE = 0.25
    _KNOB_R = dt_vn_cone_lock_knob_spec.HEAD_DIA / 2.0
    assert (
        math.hypot(
            drive.KNOB_X - drive.GEAR64_SEAT[0], drive.KNOB_Z - drive.GEAR64_SEAT[2]
        )
        - _KNOB_R
        - drive._GEAR64_TIP_R
        >= _KNOB_GEAR_CLEARANCE
    ), "cone-lock knob head crowds the 64T crank-drive gear"
    for _j in range(20):
        _cone_tip_r = drive._cone_tip_radius_max(120 - 6 * _j)
        _cone_x, _cone_z = drive.cone_seat(_j)
        assert (
            math.hypot(drive.KNOB_X - _cone_x, drive.KNOB_Z - _cone_z)
            - _KNOB_R
            - _cone_tip_r
            >= _KNOB_GEAR_CLEARANCE
        ), f"cone-lock knob head crowds cone gear {_j + 1}"
    assert abs(drive._SEAT_ANCHOR_M[0] - drive.X_CRANK) <= 1e-6, (
        f"platform CRANK_SEAT_ANCHOR maps to machine x {drive._SEAT_ANCHOR_M[0]:.6f}"
        f" != X_CRANK {drive.X_CRANK:.6f} -- anchor sign convention broke"
    )
    assert math.dist((drive.STOP_X, drive.STOP_Z), drive.BASE_STOP_XZ) <= 1e-9, (
        "shared swing-stop station drifted from the base seat"
    )
    assert (
        abs(
            drive.STOP_PROUD_LEN
            - (dt_swing_stop_screw_spec.SHANK_LEN - dt_swing_stop_screw_spec.EMBED_LEN)
        )
        <= 1e-9
    ), "swing-stop proud length is not stock length minus embed"
    assert drive._STOP_ENGAGED_GAP >= 2.0, (
        f"stop screw within {drive._STOP_ENGAGED_GAP:.2f} of the engaged plate edge "
        f"(needs >= 2.0)"
    )
    assert (
        math.hypot(drive.STOP_X - drive.KNOB_X, drive.STOP_Z - drive.KNOB_Z)
        >= (dt_vn_cone_lock_knob_spec.HEAD_DIA + dt_swing_stop_screw_spec.HEAD_DIA)
        / 2.0
        + 0.25
    ), "swing-stop head envelope fouls the lock-knob head"
    _KNOB_HEAD_POST_GAP = (
        math.hypot(
            dt_cone_swing_platform_geometry.SLOT_E_X,
            dt_cone_swing_platform_geometry.SLOT_E_Z - drive._POST_LOCAL_Z,
        )
        - dt_vn_cone_lock_knob_spec.HEAD_DIA / 2.0
        - drive.POST_BLOCK_DIA / 2.0
    )
    assert (
        _KNOB_HEAD_POST_GAP
        >= dt_cone_swing_platform_geometry.LOCK_HEAD_POST_CLEARANCE - 1e-9
    ), (
        f"lock-knob head within {_KNOB_HEAD_POST_GAP:.2f} of the pivot-post "
        f"foot (needs >= {dt_cone_swing_platform_geometry.LOCK_HEAD_POST_CLEARANCE:.2f})"
    )


def _alignment_pinion(drive) -> None:
    _CONFIG_ENGAGED_C2C = float(
        _config.machine("alignment_pinion", "engaged_center_distance_mm")
    )
    assert abs(drive.ENGAGED_C2C - _CONFIG_ENGAGED_C2C) <= 1e-6, (
        "alignment-pinion configured and derived engaged centre distances disagree: "
        f"{_CONFIG_ENGAGED_C2C:.6f} vs {drive.ENGAGED_C2C:.6f} mm"
    )
    assert (
        abs(
            math.hypot(drive.PIVOT_X - drive.APINION_X, drive.APINION_Y - drive.PIVOT_Y)
            - drive.STRAP_C2C
        )
        <= 0.001
    ), "strap c2c does not span pivot -> pinion axis"
    assert drive.Z_DRUM0 - drive.DRUM_FACE / 2.0 >= drive.APINION_Z_FRONT + 1.0, (
        "alignment pinion too short at the front station"
    )
    assert (
        drive.Z_DRUM0 + 19 * drive.Z_PITCH + drive.DRUM_FACE / 2.0
        <= drive.APINION_Z_BACK + 0.5
    ), "alignment pinion misses the j = 19 station"
    J19_ENGAGEMENT_WORST = (
        min(drive.APINION_BACK_WORST_Z, drive._G19_FACE_Z[1]) - drive._G19_FACE_Z[0]
    )
    assert J19_ENGAGEMENT_WORST >= 2.0, (
        f"j = 19 engages only {J19_ENGAGEMENT_WORST:.3f} at the worst stack"
    )
    assert drive.J19_FULL_FACE_MARGIN >= -1e-9, (
        f"j = 19 loses {-drive.J19_FULL_FACE_MARGIN:.3f} of its full face at the worst stack"
    )
    assert RIG.RIG_SET_D_RANGE[0] <= RIG.RIG_SET_LEAF_D <= RIG.RIG_SET_D_RANGE[1], (
        "RIG_SET_LEAF_D is outside the owner's D range (audit part 2 C7)"
    )
    # The rig reads the bank's configured-grid datum; the independently placed
    # gear and drum must still put the drum's back end exactly D off that face.
    assert abs(drive._G19_FACE_Z[1] - RIG.G19_BACK_FACE_Z) <= 1e-9, (
        "pinion_rig_layout.G19_BACK_FACE_Z drifted from the gear grid"
    )
    assert (
        abs(drive.APINION_Z_BACK - drive._G19_FACE_Z[1] - RIG.RIG_SET_LEAF_D) <= 1e-9
    ), "the drum's back end is not RIG_SET_LEAF_D off g19"
    assert drive.J0_SLACK_WORST >= 0.0, (
        f"the drum uncovers j = 0 by {-drive.J0_SLACK_WORST:.3f} at the worst stack"
    )
    assert (
        math.hypot(drive.APINION_X - drive.X_DRUM, drive.Y_DRIVE - drive.APINION_Y)
        >= pinion_rig_park_geometry.TIP_DRUM120 + drive.TIP_APINION + 1.0
    ), "alignment pinion crowds the cylinder train"
    assert (
        math.hypot(drive.PIVOT_X - drive.X_DRUM, drive.Y_DRIVE - drive.PIVOT_Y)
        <= drive.ENGAGED_C2C + drive.STRAP_C2C - 0.25
    ), "engage swing cannot reach the meshed centre distance"
    for _j in range(20):
        _tip = drive._cone_tip_radius_max(120 - 6 * _j)
        assert (
            math.hypot(
                drive.APINION_X - drive.cone_seat(_j)[0],
                drive.Y_DRIVE - drive.APINION_Y,
            )
            >= _tip + drive.TIP_APINION + 0.25
        ), f"pinion drum crowds cone gear {_j}"
    assert (
        math.hypot(
            drive.APINION_X - drive.GEAR64_SEAT[0], drive.Y_DRIVE - drive.APINION_Y
        )
        >= drive._GEAR64_TIP_R + drive.TIP_APINION + 0.25
    ), "pinion drum crowds the 64T crank-drive gear"
    assert drive.STRAP_C2C >= drive.TIP_APINION + 3.175 + 0.25, (
        "pivot shaft fouls the pinion drum tips"
    )
    assert (
        math.hypot(drive.LIFT_X - drive.APINION_X, drive.APINION_Y - drive.PIVOT_Y)
        >= drive.TIP_APINION + 3.175 + 0.25
    ), "lift rod fouls the pinion drum tips"
    assert abs(drive.LIFT_X - drive.PIVOT_X) >= drive.STRAP_R_END + 3.175 + 0.25, (
        "lift rod fouls the strap's swinging pivot end cap"
    )
    assert drive.LEVER_Z + drive.LEVER_HUB_LEN / 2.0 <= drive.BLOCK_FRONT_Z0 - 0.25, (
        "lever hub reaches the front pivot block"
    )
    assert (
        abs(
            (drive.LEVER_Z - (drive.LEVER_HUB_LEN / 2.0 - drive.LEVER_WALL_T))
            - drive.LIFT_ROD_Z0
        )
        <= 1e-9
    ), "lever hub bore floor off the lift rod's front end"
    assert (
        drive._LEV_STUB_D
        >= (drive._ARBOR_DIA_AT_LEVER + drive.LEVER_ROD_DIA) / 2.0 + 0.25
    ), "lever shaft crowds the pinion arbor"


def _pinion_return_spring(drive) -> None:
    _SPR_PIVOT = drive._spring_machine(
        (drive.SPR_PIVOT_LX, dt_pinion_spring_geometry.PIVOT_LY)
    )
    assert (
        math.hypot(_SPR_PIVOT[0] - drive.PIVOT_X, _SPR_PIVOT[1] - drive.PIVOT_Y) <= 0.01
    ), "spring part frame disagrees with the strap pivot"
    assert (
        abs(dt_pinion_spring_geometry.STRAP_LEAN_DEG - drive.STRAP_LEAN_DEG) <= 0.01
    ), "spring geometry assumes another parked strap lean"
    assert (
        abs(dt_pinion_spring_geometry.STRAP_HALF_WIDTH - drive.STRAP_R_END) <= 1e-9
    ), "spring geometry assumes another strap width"
    # Crest station and air, parked: on the straight flank at CONTACT_T, clear of
    # the arbor end cap (the flank is straight from the pivot to STRAP_C2C).
    _CREST_T, _CREST_N = drive._strap_frame(drive.SPRING_CREST)
    assert abs(_CREST_T - dt_pinion_spring_geometry.CONTACT_T) <= 0.01, (
        "spring crest is off its contact station"
    )
    assert (
        abs(_CREST_N - drive.STRAP_R_END - drive.SPR_PARKED_AIR) <= 0.01
        and drive.SPR_PARKED_AIR >= 0.1
    ), "spring crest does not hover its parked air off the flank"
    assert _CREST_T <= drive.STRAP_C2C - 1.0, (
        "spring crest bears on the arbor end cap, not the flank"
    )
    assert (
        drive.SPRING_BLADE_INSET >= 0.0
        and drive.SPRING_BLADE_INSET + drive.SPRING_W <= drive.STRAP_T
    ), "spring blade overhangs the strap flank axially"
    # The return leaf rides axially past gear 19 at worst fit-up (RIG_MARGINS).
    # The north end disc is gone; the remaining south disc is at the other end
    # of the bank. Parked, the crest and flick tip also clear the gear circle
    # radially. Each check books the strip's full thickness on the east side.
    for _label, _p in (
        ("crest", drive.SPRING_CREST),
        ("flick tip", drive.SPRING_FLAT_TIP),
    ):
        assert (
            math.hypot(drive.X_DRUM - _p[0], drive.Y_DRIVE - _p[1]) - drive.SPRING_T
            >= pinion_rig_park_geometry.TIP_DRUM120 + 0.25
        ), f"spring {_label} crowds the cylinder-gear tips"
    # The flick turns back east: its tip stays off the parked flank and the cap.
    assert (
        drive._strap_frame(drive.SPRING_FLAT_TIP)[1] - drive.SPRING_T
        >= drive.STRAP_R_END + 0.25
    ), "spring flick tip re-enters the parked strap flank"
    assert (
        math.hypot(
            drive.SPRING_FLAT_TIP[0] - drive.APINION_X,
            drive.SPRING_FLAT_TIP[1] - drive.APINION_Y,
        )
        - drive.SPRING_T
        >= drive.STRAP_R_END + 0.25
    ), "spring flick tip reaches the strap's arbor end cap"
    assert drive.SPRING_Z + drive.SPRING_W / 2.0 <= drive.BLOCK_BACK_Z0 - 0.25, (
        "spring reaches the back pivot block"
    )
    assert drive._SPR_PAD_Z_HI <= drive.BLOCK_BACK_Z0 - 0.25, (
        "spring foot pad reaches the back pivot block"
    )
    # The screw head sits on the pad: clear of the free end and of the bend.
    assert (
        drive.SPRING_HOLE_X - sh_vn_fillister_screw_90280a108_spec.HEAD_DIA / 2.0
    ) - drive.SPRING_FOOT_END_X >= 0.25, (
        "spring foot screw head overhangs the foot's free end"
    )
    assert (
        drive.SPRING_FOOT_TAN_X
        - (drive.SPRING_HOLE_X + sh_vn_fillister_screw_90280a108_spec.HEAD_DIA / 2.0)
        >= 0.25
    ), "spring foot screw head crowds the bend"


def _cam_engage_path(drive) -> None:
    # Each strap carries a Ø4 follower STUD in a blind edge seat FPIN_DROP
    # below the pivot (negative = above, 2026-09) (build_dt_pinion_bracket); it RESTS ON the eccentric cam collar
    # (build_dt_pinion_cam) pinned to the lift rod in the reclosed WEST bore
    # the pivot shaft in the blocks' reclosed west bores. Turning the lever spins rod +
    # collars as one; the rising OD lifts the pin -- an upward push ~15 west of
    # the pivot -- rotating the strap top EAST into mesh. Parked (ecc down, the
    # authored pose) the collar top hovers a designed ~0.15 under the pin (exact
    # tangency tips the interference gate on FP noise -- the PR5 gap lesson); the
    # return spring holds the strap west on it.
    # U27: the drill-rod stud slips into the reamed seat and is bonded (LOCTITE
    # 638); #290's .1563 rod in the .157 seat leaves the nominal solids apart.
    assert 0.0 < dt_pinion_bracket_geometry.PIN_BORE - drive.FPIN_DIA < 0.25, (
        "follower pin nominal does not slip into its seat"
    )
    assert abs(drive.FPIN_SEAT - dt_pinion_cam_pin_geometry.SEAT_LEN) <= 1e-9, (
        "pin SEAT_LEN disagrees with the bracket PIN_SEAT"
    )
    # U27 slip fit: the set-screwed cam needs only 0.02-0.10 diametral clearance on
    # the Ø6.35 lift rod (dt_pinion_cam_spec proves it at the printed limits).
    assert 0.02 <= dt_pinion_cam_geometry.BORE - 6.35 <= 0.10, (
        "cam bore nominal is outside its 0.02-0.10 slip clearance"
    )
    assert dt_pinion_cam_geometry.THIN_SIDE_WALL >= 1.5, (
        "cam thin-side wall is below the 1.5 mm U27 floor"
    )
    assert (
        math.hypot(drive._FPIN_S0, dt_pinion_bracket_geometry.PIN_DROP)
        - drive.FPIN_DIA / 2.0
        - drive.STRAP_PIVOT_BORE / 2.0
        >= 0.15
    ), "blind pin seat cuts too close to the pivot bore"
    assert drive._FPIN_TIP_S - drive._S_CAM >= 2.0, (
        "follower pin ends short of the cam axis"
    )
    assert drive._S_CAM - drive._FPIN_S0 >= 2.0, (
        "cam contact lands inside the strap edge, not the pin"
    )
    _FPIN_Y_AT_CAM = drive._FPIN_C[1] - drive._S_CAM * drive._SPR_N[1]  # 64.04
    for _z0 in drive.CAM_Z0:
        assert (
            _z0 >= drive.LIFT_ROD_Z0 + 1.0
            and _z0 + dt_pinion_cam_geometry.CAM_LEN
            <= drive.LIFT_ROD_Z0 + RIG.LIFT_ROD_LEN - 1.0
        ), "cam collar overhangs the lift rod"
    assert (
        max(drive.CAM_PIN_STATION) <= dt_pinion_cam_geometry.CAM_LEN - 1.0
        and min(drive.CAM_PIN_STATION) >= 1.0
    ), "follower pin rides off a collar face"
    assert (
        drive.CAM_Z0[0]
        >= drive.BLOCK_FRONT_Z0 + drive.BLOCK_DEPTH + RIG.FRONT_BLOCK_FEELER - 1e-9
    ), "front cam collar crowds the front pivot block"
    assert 0.10 <= drive._PARK_GAP <= 0.25, (
        f"park gap {drive._PARK_GAP:.3f} outside the 0.10..0.25 design band"
    )
    # The pure parked/engaged pose owner solves the same physical c2c triangle
    # for assembly placement, the drawing and the alignment-zero contact datum.
    assert 0.01 < drive._PHI_ENG < math.radians(10.0), (
        "engage swing angle out of the expected band"
    )
    _FPIN_Y_AT_CAM_ENG = drive._FPIN_C_ENG[1] - drive._S_CAM_ENG * drive._N_ENG[1]
    _NEED_LIFT = _FPIN_Y_AT_CAM_ENG - _FPIN_Y_AT_CAM  # ~1.57 up for the 32T rig
    assert _NEED_LIFT > 0.2, "engage swing does not RAISE the follower over the cam"
    assert (drive.FPIN_DIA + drive.CAM_OD) / 2.0 - drive._D_ENG >= 0.25, (
        "cam lift cannot reach the engaged follower"
    )
    assert drive._FPIN_TIP_S - drive._S_CAM_ENG >= 1.0, (
        "engaged pin slides off the cam axis"
    )
    assert (
        drive._engaged_cam_gap(drive.CAM_ROT_BRACKET[0])
        < 0.0
        < drive._engaged_cam_gap(drive.CAM_ROT_BRACKET[1])
    ), "engaged cam-contact root is not bracketed by down/up"
    assert -85.0 < drive.CAM_ENGAGE_ROTATION_DEG < -75.0, (
        "pinion cam engage rotation left the photo-backed range"
    )
    assert -80.0 < drive.LEVER_ENGAGED_TILT_DEG < -65.0, (
        "engaged pinion lever left the photographed +X-side range"
    )
    # Follower-seat integrity in the uncut strap. The complete Ø4 mouth must land
    # on the straight -X flank, and the 4-deep blind seat must leave solid stock
    # before the opposite flank.
    _PIN_SEAT_Y = -dt_pinion_bracket_geometry.PIN_DROP
    _PIN_SEAT_R = drive.FPIN_DIA / 2.0
    assert (
        _PIN_SEAT_Y - _PIN_SEAT_R >= 0.0
        and _PIN_SEAT_Y + _PIN_SEAT_R <= drive.STRAP_C2C
    ), "follower-seat mouth leaves the bracket's straight flank"
    _PIN_SEAT_ENTRY_X = -drive.STRAP_R_END
    _PIN_SEAT_BOTTOM_X = _PIN_SEAT_ENTRY_X + drive.FPIN_SEAT
    _PIN_SEAT_REMAINING_WALL = drive.STRAP_R_END - _PIN_SEAT_BOTTOM_X
    assert _PIN_SEAT_REMAINING_WALL >= _PIN_SEAT_R, (
        f"follower seat leaves only {_PIN_SEAT_REMAINING_WALL:.3f} mm "
        "before the opposite flank"
    )
    assert drive.LIFT_Y - drive._CAM_SWEEP_R - drive.Y_BASE_TOP >= 0.25, (
        "cam collar sweep reaches the base top"
    )
    assert (
        math.hypot(drive.PIVOT_X - drive.LIFT_X, drive.PIVOT_Y - drive.LIFT_Y)
        - drive._CAM_SWEEP_R
        - 3.175
        >= 0.25
    ), "cam sweep reaches the pivot shaft"
    assert drive.SPRING_TO_LIFT_ROD >= 0.25, (
        "spring leaf reaches the lift rod's collar sweep"
    )


def _return_spring_across_swing(drive) -> None:
    assert (
        abs(
            sum(n * v * rho * 1e-6 for n, v, rho in drive.SWING_GRAVITY_BASIS.values())
            - drive.SWING_GRAVITY_MASS_G
        )
        <= 0.01
    ), "SWING_GRAVITY_BASIS no longer sums to its mass"
    _PRELOAD_MARGIN = 1.5  # over gravity, at the soft corner
    _STRESS_SF = 1.5  # on yield, at the stiff corner
    for _label, _ratio in zip(
        ("parked", "engaged"), drive.SPRING_PRELOAD_RATIO, strict=True
    ):
        assert _ratio >= _PRELOAD_MARGIN, (
            f"spring preload {_ratio:.2f}x loses to gravity {_label} at the soft corner"
        )
    assert drive.SPRING_STRESS_SF >= _STRESS_SF, (
        f"spring root stress SF {drive.SPRING_STRESS_SF:.2f} engaged at the stiff corner"
    )


def _full_rotation_clearances(drive) -> None:
    _CRANK_TO_GRIP_AXIS = math.hypot(
        drive.X_CRANK - drive.APINION_X, drive.Y_CRANK - drive.APINION_Y
    )
    for _lo, _hi, _what in (
        *drive._SWING_RIG_BANDS,
        *((lo, hi, what) for lo, hi, _dia, what in drive.CRANK_COLUMN_BANDS),
        (drive.CRANK_ARM_Z0, drive.CRANK_ARM_Z0 + drive.ARM_THICKNESS, "crank arm"),
        (drive.CRANK_HUB_Z0, drive.CRANK_HUB_REAR_Z, "crank hub"),
    ):
        assert not (
            drive._GRIP_ROD_Z[1] > _lo - 0.25 and drive._GRIP_ROD_Z[0] < _hi + 0.25
        ), f"grip-crossrod sweep band reaches the {_what}"
    # At its worst south travel (RIG_MARGINS' stack) the crossrod enters the
    # washer's z band, so the crank column is cleared radially as well: the rod's
    # farther reach plus its radius against each body's radius.
    _GRIP_ROD_REACH = (
        max(dt_pinion_handle_geometry.ROD_DOWN, dt_pinion_handle_geometry.ROD_UP)
        + drive.HANDLE_ROD_DIA / 2.0
    )
    for _lo, _hi, _dia, _what in drive.CRANK_COLUMN_BANDS:
        assert _CRANK_TO_GRIP_AXIS - _GRIP_ROD_REACH - _dia / 2.0 >= 0.25, (
            f"grip-crossrod sweep circle reaches the {_what}"
        )
    # The integral head's own band (front crown apex to neck shoulder) spins with
    # the arbor and is wider than the crossrod's, so it is proved against the same
    # swing-rig bodies directly rather than inferred from the rod band.
    for _lo, _hi, _what in drive._SWING_RIG_BANDS:
        assert not (
            drive._GRIP_HEAD_Z[1] > _lo - 0.25 and drive._GRIP_HEAD_Z[0] < _hi + 0.25
        ), f"integral grip-head band reaches the {_what}"
    # The head's wider z band clips the crank column (collar and washer), so a
    # column body sharing its band is cleared radially instead.  The crank
    # arm/hub/handle sweep is axially disjoint from the integral head.
    for _lo, _hi, _dia, _what in drive.CRANK_COLUMN_BANDS:
        assert not (
            drive._GRIP_HEAD_Z[1] > _lo - 0.25
            and drive._GRIP_HEAD_Z[0] < _hi + 0.25
            and _CRANK_TO_GRIP_AXIS < drive.ARBOR_HEAD_DIA / 2.0 + _dia / 2.0 + 0.25
        ), f"integral grip head reaches the {_what}"
    assert drive._GRIP_HEAD_Z[0] >= drive.CRANK_HUB_REAR_Z + 0.25, (
        "integral grip-head band reaches the crank hub"
    )
    assert abs(drive.HANDLE_SCREW_TIP_Z - drive.CRANK_ARM_ORIGIN_Z) <= 1e-9, (
        "MHA-DT-32's filed tip is not flush with the arm's inboard face"
    )
    for _lo, _what in (
        (seat_geometry.BAND_FRONT_Z, "crank chain wheel"),
        (drive._GRIP_HEAD_Z[0], "integral grip head"),
        (drive._GRIP_ROD_Z[0], "grip crossrod"),
    ):
        assert drive.HANDLE_SCREW_TIP_Z <= _lo - 0.25, (
            f"MHA-DT-32's filed tip reaches the {_what}"
        )
    assert (
        drive.ARM_C2C - dt_crank_handle_pivot_screw_spec.THREAD_MODEL_DIA / 2.0
        >= drive.HUB_BARREL_DIA / 2.0 + 0.25
    ), "MHA-DT-32 thread reaches the crank hub barrel"
    # Lever full throw: sample the solved cam-contact path from the photographed
    # +10-degree parked pose to about -72 degrees engaged.  Clearance improves
    # after the parked endpoint, but the complete crossing through vertical is
    # checked rather than inferred.
    _LEV_SWEEP_STEPS = math.ceil(abs(drive.CAM_ENGAGE_ROTATION_DEG) / 0.25)
    for _step in range(_LEV_SWEEP_STEPS + 1):
        _angle = (
            drive.LEVER_TILT_DEG
            + drive.CAM_ENGAGE_ROTATION_DEG * _step / _LEV_SWEEP_STEPS
        )
        _t = math.radians(_angle)
        _u = (-math.sin(_t), math.cos(_t))
        _foot = drive._LEV_REL[0] * _u[0] + drive._LEV_REL[1] * _u[1]
        if 0.0 <= _foot <= drive.LEVER_LEN:
            _d = abs(drive._LEV_REL[0] * _u[1] - drive._LEV_REL[1] * _u[0])
        else:
            _end = min(max(_foot, 0.0), drive.LEVER_LEN)
            _d = math.hypot(
                drive._LEV_REL[0] - _end * _u[0],
                drive._LEV_REL[1] - _end * _u[1],
            )
        assert _d >= (drive._ARBOR_DIA_AT_LEVER + drive.LEVER_ROD_DIA) / 2.0 + 0.25, (
            "lever shaft crowds the arbor mid-throw"
        )
    assert not (
        drive._LEV_Z[0] < drive.BLOCK_FRONT_Z0 + drive.BLOCK_DEPTH + 0.25
        and drive._LEV_Z[1] > drive.BLOCK_FRONT_Z0 - 0.25
    ), "lever throw plane reaches the front pivot block"
    assert drive._LEV_Z[1] <= drive.PIVOT_SHAFT_Z0 - 0.25, (
        "lever throw plane reaches the pivot shaft front end"
    )
    assert drive._LEV_Z[0] >= drive._GRIP_HEAD_Z[1] + 0.25, (
        "lever throw plane reaches the integral grip head"
    )
    # The rig layout sizes MHA-DT-17 from the lever's nominal throw plane; the pose
    # must put it there.
    assert (
        abs(drive._LEV_Z[1] - (drive.LIFT_ROD_Z0 + RIG.LEVER_PLANE_NORTH_FROM_ROD_END))
        <= 1e-9
    ), "the lever throw plane drifted from the rig layout's"
    assert not drive._THIN, (
        "rig margins under their floor (+ RIG_MARGIN_SPARE where no owner range rules): "
        + "; ".join(f"{n} {v:.3f} (floor {f})" for n, (v, f) in drive._THIN.items())
    )
    # The MHA-DT-33 collar rides the arbor outboard of the front strap.  It must
    # stand clear of the strap's outer face (the printed-band stack lives in
    # dt_pinion_arbor_collar_spec) and of every rig body whose z band it shares:
    # the lift rod and pivot shaft by radial distance between parallel axes (the
    # front pivot block, by height, once BLOCK_TOP_Y is derived below).
    assert drive.ARBOR_COLLAR_Z[1] <= RIG.STRAP_Z_OUTER[0] - 0.25, (
        "arbor collar reaches the front strap's outer face"
    )
    assert drive.ARBOR_COLLAR_Z[0] >= drive._GRIP_HEAD_Z[1] + 0.25, (
        "arbor collar reaches the integral grip head's neck"
    )
    for _lo, _hi, _axis_xy, _r, _what in (
        (
            drive.LIFT_ROD_Z0,
            drive.LIFT_ROD_Z0 + RIG.LIFT_ROD_LEN,
            (drive.LIFT_X, drive.LIFT_Y),
            3.175,
            "lift rod",
        ),
        (
            drive.PIVOT_SHAFT_Z0,
            drive.PIVOT_SHAFT_Z0 + RIG.TORQUE_SHAFT_LEN,
            (drive.PIVOT_X, drive.PIVOT_Y),
            3.175,
            "pivot shaft",
        ),
    ):
        if _hi < drive.ARBOR_COLLAR_Z[0] - 0.25 or _lo > drive.ARBOR_COLLAR_Z[1] + 0.25:
            continue
        assert (
            math.hypot(_axis_xy[0] - drive.APINION_X, _axis_xy[1] - drive.APINION_Y)
            >= drive.ARBOR_COLLAR_OD / 2.0 + _r + 0.25
        ), f"arbor collar crowds the {_what}"


def _pinion_arbor_and_rig_fasteners(drive) -> None:
    # The steel Ø5/16 arbor slips through the drum (bonded) and journals in both
    # straps' top bores.  Its turned head/neck are integral; MHA-DT-15 is only the
    # separate crossrod, bonded into the head's reamed hole at the unchanged
    # head/cross-hole station.
    assert abs(drive.HANDLE_Z - (drive.ARBOR_Z0 + drive.ARBOR_HEAD_CENTER_Z)) <= 1e-9, (
        "grip crossrod is not centred in the integral head"
    )
    # MHA-DT-22 runs in the straps on its two journal lands, so each land must
    # cover its strap in the pose, past both faces (the worst case over every
    # printed band and both drum stops is dt_pinion_arbor_geometry's own stack).
    for _land_z, _strap_faces, _which in (
        (
            dt_pinion_arbor_geometry.FRONT_JOURNAL_Z,
            (RIG.STRAP_Z_OUTER[0], RIG.STRAP_Z_INNER[0]),
            "front",
        ),
        (
            dt_pinion_arbor_geometry.BACK_JOURNAL_Z,
            (RIG.STRAP_Z_INNER[1], RIG.STRAP_Z_OUTER[1]),
            "back",
        ),
    ):
        _land = (
            drive.ARBOR_Z0 + _land_z,
            drive.ARBOR_Z0 + _land_z + dt_pinion_arbor_geometry.JOURNAL_LEN,
        )
        assert (
            min(_strap_faces[0] - _land[0], _land[1] - _strap_faces[1])
            >= drive.ARBOR_MIN_LAND_OVER_STRAP - 1e-9
        ), f"MHA-DT-22's {_which} journal land misses its strap"
    assert (
        drive.ARBOR_DIA
        == dt_alignment_pinion_spec.BORE_DIA
        == dt_pinion_bracket_geometry.ARBOR_BORE
    ), "arbor dia disagrees with drum and strap bores"
    # MHA-DT-00's drum-station setting (dt_drum_station_setting_spec) is a Right-
    # plane leg on the arbor axis: it is true length only while the arbor's local
    # +Z stays machine +Z, and it must end on the head rear face and the drum's
    # front end exactly where this pose puts them (the parked pose it is built in).
    assert [row[2] for row in drive.ARBOR_ROWS] == [0.0, 0.0, 1.0] and drive.ARBOR_ROWS[
        2
    ] == [0.0, 0.0, 1.0], (
        "the arbor axis left machine Z; the drum-station leg is foreshortened"
    )
    assert (
        abs(
            drum_station_setting.HEAD_REAR_FACE_Z
            - (drive.ARBOR_Z0 + drive.ARBOR_HEAD_REAR_Z)
        )
        <= 1e-9
        and abs(drum_station_setting.DRUM_FRONT_END_Z - drive.APINION_Z_FRONT) <= 1e-9
        and abs(drum_station_setting.AXIS_Y - drive.APINION_Y) <= 1e-9
    ), "the drum-station setting leg left the placed arbor head and drum"
    # R1: the crossrod is a bonded slip fit.  Fit audit F14: the head hole is
    # the .2510 reamer's size on the 1/4 rod; the bond's limits (rod enters,
    # gap inside Loctite 638) are dt_pinion_arbor_geometry's asserts.
    assert abs(drive.HANDLE_ROD_DIA - 6.35) <= 1e-9, "grip crossrod left 1/4 in"
    assert abs(dt_pinion_arbor_geometry.CROSS_HOLE_DIA - 0.2510 * 25.4) <= 1e-9, (
        "the head hole is no longer the .2510 reamer"
    )
    # Fit audit F16: the strap pivot bore is the .2510 reamer's size on the
    # 1/4 in MHA-DT-19 shaft, whose nominal the strap pin's ligament reads
    # from the bracket geometry (lockstep).
    import dt_pinion_pivot_shaft_spec

    assert abs(drive.STRAP_PIVOT_BORE - 0.2510 * 25.4) <= 1e-9, (
        "strap pivot bore is no longer the .2510 reamer"
    )
    assert (
        dt_pinion_bracket_geometry.PIVOT_SHAFT_DIA
        == dt_pinion_pivot_shaft_spec.SHAFT_DIA
        == 6.35
    ), "the strap pin's shaft nominal left the MHA-DT-19 shaft"
    assert (
        drive.BLOCK_SCREW_HALF + dt_vn_slotted_screw_spec.HEAD_DIA / 2.0
        <= min(drive.BLOCK_EAST, drive.BLOCK_WIDTH - drive.BLOCK_EAST) - 0.25
    ), "block screw head overhangs the block end"
    # Both machine-handed: the base holes agree directly.
    for _want, _have in zip(drive._BLOCK_SCREW_XZ, drive.BASE_BLOCK_XZ, strict=True):
        assert abs(_want[0] - _have[0]) <= 0.05 and abs(_want[1] - _have[1]) <= 0.05, (
            f"harmonic-base block-screw hole {_have} != machine derived "
            f"({_want[0]:.3f}, {_want[1]:.3f})"
        )


def _swing_occupant_seats(drive) -> None:
    for _occupant, _seats in drive.SWING_OCCUPANT_SEATS.items():
        assert len(_seats) != 0 and all(
            drive._point_in_polygon(_seat, drive.SWING_FOOTPRINTS[_occupant])
            for _seat in _seats
        ), f"the {_occupant} footprint misses its base seats {_seats}"
    assert (
        sum(len(_seats) for _seats in drive.SWING_OCCUPANT_SEATS.values())
        == len(drive.BASE_HOLE_XZ)
        + len(drive.BASE_BLOCK_XZ)
        + len(drive.BASE_FOOT_XZ)
        + len(drive.BASE_NAMEPLATE_XZ)
        + 1
    ), "a base seat is claimed by no swing occupant, or by two"
    for (_rider, _occupant), (_gap, _swing) in drive.SWING_RIDER_CLEARANCE.items():
        assert _gap >= drive.SWING_SEAT_RUNNING_CLEARANCE, (
            f"swinging {_rider} within {_gap:.3f} of the {_occupant} at swing "
            f"{_swing:.3f} deg (needs >= {drive.SWING_SEAT_RUNNING_CLEARANCE})"
        )
    # The MHA-DT-33 collar can share the front pivot block's z band; its underside
    # must then clear the block's flat top.
    assert not (
        drive.BLOCK_FRONT_Z0 < drive.ARBOR_COLLAR_Z[1] + 0.25
        and drive.BLOCK_FRONT_Z0 + drive.BLOCK_DEPTH > drive.ARBOR_COLLAR_Z[0] - 0.25
        and drive.APINION_Y - drive.ARBOR_COLLAR_OD / 2.0 < drive.BLOCK_TOP_Y + 0.25
    ), "arbor collar sits on the front pivot block"


def _pedestal_hold_down_and_collar_pins(drive) -> None:
    # The head sits on the 18 ledge, clear of the strap root and the ledge end.
    assert dt_vn_pedestal_hold_down_screw_spec.HEAD_DIA / 2.0 <= min(
        drive.ARBOR_PED_SCREW_Z - drive.ARBOR_PED_FOOT_NEAR_Z,
        dt_arbor_pedestal_spec.STRAP_ROOT_Z - drive.ARBOR_PED_SCREW_Z,
    ), "pedestal hold-down head overhangs the ledge"
    # Both machine-handed: the base holes agree directly.
    for _label, _derived, _base in (
        ("spring foot screw", drive._FOOT_SCREW_XZ, drive.BASE_FOOT_XZ),
        ("pedestal hold-down", drive._PEDESTAL_SCREW_XZ, drive.BASE_PEDESTAL_XZ),
    ):
        for _want, _have in zip(_derived, _base, strict=True):
            assert (
                abs(_want[0] - _have[0]) <= 0.05 and abs(_want[1] - _have[1]) <= 0.05
            ), (
                f"harmonic-base {_label} hole {_have} != machine derived "
                f"({_want[0]:.3f}, {_want[1]:.3f})"
            )
    for _z_strap, _z_hole in zip(
        drive.STRAP_CROSS_HOLE_Z, RIG.TORQUE_SHAFT_PIN_HOLE_Z, strict=True
    ):
        assert (
            abs(
                drive.PIVOT_SHAFT_Z0
                + _z_hole * drive.TORQUE_SHAFT_ROWS[2][2]
                - _z_strap
            )
            <= 1e-9
        ), "a strap cross hole is not coaxial with its torque-shaft hole"
    assert not any(
        abs(a - b) > 1e-9 for a, b in zip(drive.COLLAR_PIN_ROWS[0], drive.ARBOR_ROWS[1])
    ), "collar spring pin axis is not the arbor's pin-hole axis"
    assert abs(drive.COLLAR_PIN_Z - (drive.ARBOR_Z0 + drive.ARBOR_PIN_Z)) <= 1e-9, (
        "collar pin hole is off the arbor's pin station"
    )
    assert abs(_LIFT_ROD.ROD_PHASE_DEG - drive.LEVER_TILT_DEG) <= 1e-9 and not any(
        abs(a - b) > 1e-9
        for a, b in zip(drive._CAM_TAP_IN_ROD, _LIFT_ROD.FLAT_NORMAL_LOCAL, strict=True)
    ), (
        f"MHA-DT-17 flat normal {_LIFT_ROD.FLAT_NORMAL_LOCAL} is not the cams' tap axis "
        f"{drive._CAM_TAP_IN_ROD} in the rod's frame"
    )


STACKS = (
    _drive_axis_and_cone_seats,
    _crank_mesh,
    _crank_hub_and_sprocket_seat,
    _cylinder_bank_and_arbor_pedestals,
    _keeper_chain_and_crank_pinion,
    _tip_block_hold_down,
    _platform_containment,
    _tip_block_station,
    _tip_end_play,
    _platform_on_base_and_crank_boss,
    _crankshaft_proud_end,
    _pinion_under_t120,
    _cone_pivot_screw,
    _tip_print_worst,
    _lock_knob_and_swing_stop,
    _alignment_pinion,
    _pinion_return_spring,
    _cam_engage_path,
    _return_spring_across_swing,
    _full_rotation_clearances,
    _pinion_arbor_and_rig_fasteners,
    _swing_occupant_seats,
    _pedestal_hold_down_and_collar_pins,
)


@pytest.mark.parametrize("stack", STACKS, ids=lambda stack: stack.__name__.lstrip("_"))
def test_stack_closes(stack) -> None:
    stack(build_dt_drive_train_assembly)


def test_pinion_clears_t120_and_covers_the_64t_row_up_to_the_seat_gap_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#1145: MHA-DT-00 step 4F sets MHA-DT-10 on a feeler at the seat gap's
    floor, and the stacks above prove the T120 air and the 64T row there and
    run south onto the boss (PINION_END_PLAY).  PINION_BOSS_NORTH_GAP_RANGE
    runs on to SEAT_GAP_MAX_MM, which the crankshaft's seat-step standoff and
    crank_mesh_stack's overhang and lever book, so the same gates and the
    16T sheet's stated T120 worst hold with the 16T anywhere up to it."""
    drive = build_dt_drive_train_assembly
    floor, ceiling = drive.PINION_BOSS_NORTH_GAP_RANGE
    assert floor == drive.PINION_SEAT_FEELER == dt_crank_pinion_spec.SEAT_FEELER_MM
    assert ceiling == dt_crank_pinion_spec.SEAT_GAP_MAX_MM
    north = ceiling - floor
    plays = (*drive.PINION_END_PLAY, north / 2.0, north)
    concentric = drive.pinion_t120_clearances(end_plays=plays, pose_radial=0.0, pose_axial=0.0)
    assert concentric["shoulder air"] >= drive.T120_PINION_AIR_FLOOR
    assert concentric["turned band radial"] >= drive.T120_TURNED_BAND_RADIAL_FLOOR
    worst = drive.pinion_t120_clearances(end_plays=plays)
    assert worst["shoulder air"] >= dt_crank_pinion_spec.T120_SHOULDER_AIR_WORST
    assert worst["turned band radial"] >= dt_crank_pinion_spec.T120_TURNED_BAND_RADIAL_WORST
    # Control: north is the opening direction for T120; a 16T run far north
    # of the ceiling stands further off the rim, so the end play is live here.
    assert (
        drive.pinion_t120_clearances(end_plays=(north + 4.0,))["turned band radial"]
        > worst["turned band radial"]
    )
    monkeypatch.setattr(drive, "PINION_END_PLAY", plays)
    assert (
        drive.crank_row_engagement(drive.CONE_FLOAT_NORTH)
        >= drive.CRANK_ROW_ENGAGEMENT_FLOOR
    )
    # Negative control: 5 mm north of its feeler set the 16T leaves the 64T row.
    monkeypatch.setattr(drive, "PINION_END_PLAY", (5.0,))
    assert (
        drive.crank_row_engagement(drive.CONE_FLOAT_NORTH)
        < drive.CRANK_ROW_ENGAGEMENT_FLOOR
    )
