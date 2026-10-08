"""SolidWorks-free stock-spur crank screen, not a substituted CAD assembly.

Run with ``uv run python cad/scripts/diagnostics/crank_parallel_stock_screen.py``.
Only two added-transmission layouts are evaluated: an external single Hooke
joint and an equal-angle double Cardan joint. Both retain the existing crank,
chain sprocket, post and cone-gear row. No source geometry is altered by this
investigation. Gear formula results describe an ideal full-depth PA20 pair;
actual catalog root fillets, tooth thinning and joint swept bodies need CAD.
"""
from __future__ import annotations

import json
import math

import _common  # noqa: F401 -- diagnostics' SolidWorks-free import-path shim
import cone_line as line
import crank_boss_rim
import crank_mesh_stack as baseline_stack
import dt_cone_pivot_post_spec as post
import dt_crank_drive_gear_spec as baseline_gear
import dt_crank_pinion_spec as baseline_pinion
import dt_crank_handle_spec as handle
import dt_crankshaft_spec as shaft
import pd_transgear_removable_spec as sprocket


PA = math.radians(20.0)
# The gear thickness allocation is an analytic assumption, not a measured KHK
# tooth form. The KHK SS table quotes 0.08..0.18 mm backlash, but it does not
# establish this assembly's print-worst pair backlash.
PAIR_THINNING_MM = 0.15
GEAR_SOURCE = "https://khkgears.net/pdf/ss.pdf"
JOINT_SOURCE = (
    "https://www.altraliterature.com/-/media/Files/Literature/Brand/"
    "huco-dynatork/catalogs/p-7293-hd-a4-sections/"
    "p-7293-hd-a4_plasticuniversaljointsandteleshafts.ashx"
)


def involute(angle: float) -> float:
    return math.tan(angle) - angle


def backlash(module: float, small: int, large: int, centre: float,
             thinning: float = PAIR_THINNING_MM) -> float:
    """Exact operating-circle backlash for a specified total tooth thinning."""
    r1, r2 = small * module / 2.0, large * module / 2.0
    working_pa = math.acos((r1 + r2) * math.cos(PA) / centre)
    rw1, rw2 = centre * r1 / (r1 + r2), centre * r2 / (r1 + r2)
    s1 = math.pi * module / 2.0
    s2 = s1 - thinning
    sw1 = 2.0 * rw1 * (s1 / (2.0 * r1) + involute(PA) - involute(working_pa))
    sw2 = 2.0 * rw2 * (s2 / (2.0 * r2) + involute(PA) - involute(working_pa))
    return 2.0 * math.pi * rw1 / small - sw1 - sw2


def pair(module: float, small: int, large: int, buy: tuple[str, ...]) -> dict:
    r1, r2 = small * module / 2.0, large * module / 2.0
    centre = r1 + r2
    ra1, ra2 = r1 + module, r2 + module
    rb1, rb2 = r1 * math.cos(PA), r2 * math.cos(PA)
    q1, q2 = math.sqrt(ra1**2 - rb1**2), math.sqrt(ra2**2 - rb2**2)
    contact_line = centre * math.sin(PA)
    base_pitch = math.pi * module * math.cos(PA)
    nominal_cr = (min(q1, contact_line) - max(contact_line - q2, 0.0)) / base_pitch
    # Inheriting the OLD stack is just a sensitivity screen. Joint/stub support
    # and catalog tolerances change the stack; do not label it a new worst gate.
    inherited_open = baseline_stack.OPEN_CENTRE_DISTANCE_MM
    opened = centre + inherited_open
    opened_line = math.sqrt(opened**2 - (rb1 + rb2)**2)
    open_q1 = math.sqrt((ra1 - 0.05)**2 - rb1**2)
    open_q2 = math.sqrt((ra2 - 0.05)**2 - rb2**2)
    open_cr = max(0.0, min(open_q1, opened_line) - max(opened_line - open_q2, 0.0)) / base_pitch
    return {
        "module_mm": module,
        "dp": 25.4 / module,
        "pa_deg": 20.0,
        "teeth": [small, large],
        "ratio": small / large,
        "centre_mm": centre,
        "centre_change_mm": centre - BASELINE_C2C,
        "centre_change_percent": 100.0 * (centre / BASELINE_C2C - 1.0),
        "outside_diameters_mm": [2.0 * ra1, 2.0 * ra2],
        "od_change_percent": [
            100.0 * (2.0 * ra1 / baseline_pinion.OUTSIDE_DIA - 1.0),
            100.0 * (2.0 * ra2 / baseline_gear.OUTSIDE_DIA - 1.0),
        ],
        "nominal_contact_ratio_ideal": nominal_cr,
        "large_tip_to_small_base_margin_mm": contact_line - q2,
        "nominal_tip_root_clearance_mm": 0.25 * module,
        "minimum_anti_undercut_shift": max(0.0, 1.0 - small * math.sin(PA)**2 / 2.0),
        "assumed_pair_thinning_mm": PAIR_THINNING_MM,
        "nominal_backlash_ideal_mm": backlash(module, small, large, centre),
        "tight_backlash_at_minus_0p085_centre_ideal_mm": backlash(module, small, large, centre - 0.085),
        "old_open_budget_sensitivity_mm": inherited_open,
        "cr_at_old_open_budget_and_both_tips_minus_0p1_dia": open_cr,
        "catalog_gears": list(buy),
    }


POST_POINT = line.cone_station(line.POST_STATION)
GEAR_OFFSET = crank_boss_rim.seated_gear_offset()
GEAR_CENTRE = line.cone_station(line.POST_STATION + GEAR_OFFSET)
POST_NORTH_Z = POST_POINT[2] + post.CRANK_BOSS_NORTH_FACE
BASELINE_DX = (GEAR_CENTRE[0] - line.X_CRANK) * line.COS_I
BASELINE_DY = line.Y_CRANK - line.Y_DRIVE
BASELINE_C2C = math.hypot(BASELINE_DX, BASELINE_DY)
BETA = math.radians(line.INCLINE_DEG)


def stub_geometry(centre: float) -> dict:
    """Output-axis pose for unchanged input crank line and cone gear row.

    The output pinion plane passes through the large gear's centre plane.
    Choose the negative in-plane X offset, as in the original near-vertical
    crank mesh. A Hooke joint's cross must lie at the two axes' intersection.
    """
    offset = -math.sqrt(centre**2 - BASELINE_DY**2)
    pinion = [
        GEAR_CENTRE[0] + offset * line.COS_I,
        line.Y_CRANK,
        GEAR_CENTRE[2] - offset * line.SIN_I,
    ]
    joint_z = GEAR_CENTRE[2] + ((line.X_CRANK - GEAR_CENTRE[0]) * line.COS_I - offset) / line.SIN_I
    along = (line.X_CRANK - pinion[0]) * line.SIN_I + (joint_z - pinion[2]) * line.COS_I
    return {
        "pinion_centre_mm": pinion,
        "pinion_centre_change_mm": [
            pinion[0] - line.X_CRANK,
            0.0,
            pinion[2] - BASELINE_PINION_CENTRE_Z,
        ],
        "perpendicular_x_offset_mm": offset,
        "joint_cross_mm": [line.X_CRANK, line.Y_CRANK, joint_z],
        "joint_north_of_pinion_along_output_mm": along,
        "post_north_to_pinion_south_z_mm": pinion[2] - 5.0 * line.COS_I - POST_NORTH_Z,
    }


BASELINE_PINION_CENTRE_Z = POST_NORTH_Z + baseline_pinion.SEAT_FEELER_MM + baseline_pinion.FACE_WIDTH / 2.0


def joint_layouts(stub: dict) -> dict:
    # Huco-Pol 103.13/111.13: 6.35 maximum bore, 14.3 OD. Existing 9.525
    # crank requires a new stepped end. Catalogue dimensions, not invented SKUs.
    single_length, joint_od = 46.2, 14.3
    double_length, cross_span = 62.1, 15.9
    along = stub["joint_north_of_pinion_along_output_mm"]
    # A south-to-north inline output socket + 10-mm stock gear face must fit
    # entirely before the pinion, even before adding the separate stub bearing.
    single_gap = -along - single_length / 2.0 - 5.0
    joint_z = stub["joint_cross_mm"][2]
    # Coplanar W configuration: intermediate shaft bisects the total angle.
    # The two joint centres are separated by catalog L4, not overall L.
    first_z = joint_z + cross_span * (
        math.cos(BETA) / math.sin(BETA) * math.sin(BETA / 2.0)
        - math.cos(BETA / 2.0)
    )
    second_z = first_z + cross_span * math.cos(BETA / 2.0)
    second_along = (second_z - stub["pinion_centre_mm"][2]) / line.COS_I
    output_extension = (double_length - cross_span) / 2.0
    second_x = line.X_CRANK + cross_span * math.sin(BETA / 2.0)
    # Both crosses must lie on their respective shaft axes, and each bend
    # must be beta/2. This guards the wrong-sign bisector (not constant velocity).
    assert math.isclose(
        (second_x - line.X_CRANK) / (second_z - joint_z),
        math.tan(BETA), abs_tol=1e-12,
    )
    input_socket_intrusion = POST_NORTH_Z - (first_z - output_extension)
    double_gap = -second_along - output_extension - 5.0
    phase_error = math.atan((1.0 - math.cos(BETA)) / (2.0 * math.sqrt(math.cos(BETA))))
    # Even the smallest catalog envelopes cannot fit this inline output:
    # 103.06 / 111.06, OD7.1, max bore3.18; reduced shafts are not assumed safe.
    compact_span = 8.1
    compact_second_z = joint_z + compact_span * math.cos(BETA) / math.sin(BETA) * math.sin(BETA / 2.0)
    compact_second_along = (compact_second_z - stub["pinion_centre_mm"][2]) / line.COS_I
    return {
        "single_hooke": {
            "catalog_family": "Huco-Pol 103.13; order a verified 6.35/6.35 bore configuration",
            "catalog_length_mm": single_length,
            "catalog_od_mm": joint_od,
            "catalog_max_bore_mm": 6.35,
            "ideal_velocity_ratio_min_max": [math.cos(BETA), 1.0 / math.cos(BETA)],
            "maximum_input_output_phase_error_deg": math.degrees(phase_error),
            "maximum_cone_phase_error_deg": math.degrees(phase_error) / 4.0,
            "maximum_T006_drum_phase_error_deg": math.degrees(phase_error) / 80.0,
            "available_inline_joint_to_gear_gap_mm": single_gap,
            "smallest_catalog_103p06_inline_gap_mm": -along - 27.2 / 2.0 - 5.0,
            "verdict": "dead under variant tried: output joint envelope overlaps the gear row; single Hooke also violates the uniform crank/cone phase law",
        },
        "double_cardan": {
            "catalog_family": "Huco-Pol 111.13; order a verified 6.35/6.35 bore configuration",
            "catalog_length_mm": double_length,
            "catalog_cross_span_mm": cross_span,
            "catalog_od_mm": joint_od,
            "catalog_max_bore_mm": 6.35,
            "joint_centre_z_mm": [first_z, second_z],
            "input_socket_inside_original_post_mm": input_socket_intrusion,
            "available_inline_joint_to_gear_gap_mm": double_gap,
            "smallest_catalog_111p06_inline_gap_mm": -compact_second_along - (35.3 - compact_span) / 2.0 - 5.0,
            "ideal_velocity_ratio_if_equal_angles_and_phased": 1.0,
            "verdict": "dead under variant tried: input socket enters the original post and output joint envelope overlaps the pinion; new bearing housing/post pocket and relocated gear row needed",
        },
    }


def full_tilt_displacement(z: float) -> dict:
    """Visual-only rigid yaw about the original crank/post intersection.

    This is the requested original proposal's movement, not a third joint
    layout and not a working paper chain: the knob axis would also need yaw.
    """
    relative_z = z - POST_POINT[2]
    dx = relative_z * line.SIN_I
    dz = relative_z * (line.COS_I - 1.0)
    return {"dx_mm": dx, "dz_mm": dz, "distance_mm": math.hypot(dx, dz)}


def main() -> None:
    assert math.isclose(BASELINE_C2C, 39.76920825753658, abs_tol=1e-9)
    pairs = [
        pair(1.0, 16, 64, ("KHK SS1-16", "KHK SS1-64")),
        pair(1.0, 20, 80, ("KHK SS1-20", "KHK SS1-80")),
        pair(25.4 / 24.0, 16, 64, ()),
    ]
    for item in pairs:
        assert item["ratio"] == 0.25
        assert item["nominal_contact_ratio_ideal"] > 1.1
        assert item["nominal_tip_root_clearance_mm"] > 0.0
        assert math.isclose(item["nominal_backlash_ideal_mm"], PAIR_THINNING_MM, abs_tol=1e-12)
        item["stub_layout"] = stub_geometry(item["centre_mm"])
    stub = pairs[0]["stub_layout"]
    layouts = joint_layouts(stub)
    assert layouts["single_hooke"]["available_inline_joint_to_gear_gap_mm"] < 0.0
    assert layouts["double_cardan"]["available_inline_joint_to_gear_gap_mm"] < 0.0
    assert layouts["double_cardan"]["input_socket_inside_original_post_mm"] > 0.0
    crank_face_z = POST_NORTH_Z - shaft.POST_BORE_END
    report = {
        "status": "analytical comparison only; no CAD cutover and no farm build",
        "sources": {"gears": GEAR_SOURCE, "joints": JOINT_SOURCE},
        "baseline": {
            "cone_train_dp_unchanged": line.DP_TRAIN,
            "incline_deg": line.INCLINE_DEG,
            "crank_axis_xy_mm": [line.X_CRANK, line.Y_CRANK],
            "post_north_z_mm": POST_NORTH_Z,
            "gear64_centre_mm": GEAR_CENTRE,
            "centre_mm": BASELINE_C2C,
            "outside_diameters_mm": [baseline_pinion.OUTSIDE_DIA, baseline_gear.OUTSIDE_DIA],
            "tight_backlash_from_original_measured_stack_mm": baseline_stack.TIGHT_BACKLASH_MM,
        },
        "candidate_pairs": pairs,
        "two_layouts_tried": layouts,
        "visual_movement": {
            "two_stub_layouts_crank_handle_shift_mm": 0.0,
            "two_stub_layouts_crank_sprocket_shift_mm": 0.0,
            "m1_pinion_centre_translation_mm": math.dist(stub["pinion_centre_change_mm"], [0.0, 0.0, 0.0]),
            "full_crank_tilt_about_original_post_intersection_not_applied": {
                "crank_arm_face": full_tilt_displacement(crank_face_z),
                "handle_butt": full_tilt_displacement(crank_face_z - handle.HANDLE_LENGTH),
                "crank_sprocket_midplane": full_tilt_displacement(sprocket.CHAIN_MID_Z),
                "chain_axis_nonparallel_deg_if_knob_not_moved": line.INCLINE_DEG,
            },
        },
        "catalog_geometry_adaptations": {
            "SS1_16": {"face_mm": 10.0, "bore_mm": 8.0, "total_length_mm": 30.0},
            "SS1_64": {"face_mm": 10.0, "bore_mm": 10.0, "total_length_mm": 20.0},
            "existing_64_face_mm": baseline_gear.FACE_WIDTH,
            "unmodified_stock_64_axial_overlap_with_T120_mm": 10.0 - baseline_gear.FACE_WIDTH,
            "existing_cone_shaft_gear_land_mm": baseline_gear.BORE_DIA,
            "stock_64_bore_excess_over_existing_land_mm": 10.0 - baseline_gear.BORE_DIA,
            "note": "Face and remove hub as required; SS1-16 can be bored from 8 to 9; SS1-64's 10 bore cannot be bored down to the 9.525 D-seat",
        },
        "gate_boundary": "Negative layout gaps are axial envelope screens, not native interference volumes. Stock tooth form and new tight-corner backlash are uncertified; old crossed-mesh sensitivities cannot be reused.",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
