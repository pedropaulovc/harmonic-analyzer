"""Pure physical/tolerance inputs to the actual crossed-crank qualification.

No fitted backlash sensitivities or diagnostic engine belongs in a native
part dependency. These are dimensional stack terms, in mm, consumed by the
offline 3D study and checked against its frozen calibration at publication.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import _config
import dt_cone_pivot_post_spec as post
import dt_crank_drive_gear_spec as gear64
import dt_crank_pinion_spec as pinion
import dt_crankshaft_spec as shaft
import cone_line
from cone_line import COS_I, POST_STATION, SIN_I
from cone_stack_end_play import CONE_FLOAT_NORTH
from dt_cone_pivot_post_installation import GEAR_AXIS_SHIFT
from gear_seat_fit import GEAR_SEAT_CLEARANCE

R64 = gear64.PITCH_DIA / 2.0
R16 = pinion.PITCH_DIA / 2.0
FRAME_C2C = R64 + R16 + _config.fit("crank_mesh", "c2c_slack_mm")
FRAME_DY = post.CRANK_BORE_HEIGHT - post.BORE_HEIGHT
FRAME_DX = math.sqrt(FRAME_C2C**2 - FRAME_DY**2)
DC_PER_DY = FRAME_DY / FRAME_C2C
DC_PER_DX = FRAME_DX / FRAME_C2C
GEAR64_POST_OFFSET = gear64.LAYOUT_CENTRE_STATION + GEAR_AXIS_SHIFT + gear64.CENTRE_SHIFT_NORTH - POST_STATION
CRANK_RUNNING = shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM
CRANK_BEARING_LENGTH = shaft.JOURNAL_SUPPORT_SPAN_MIN_MM
CRANK_SUPPORT_NORTH_MIN = shaft.SHAFT_LENGTH + shaft.SHAFT_LENGTH_BAND[1] - shaft.JOURNAL_INBOARD_STATION - shaft.STATION_ROW
FACE_UPPER = pinion.printed_deviations(pinion.FACE_WIDTH, pinion.FACE_WIDTH_PLACES, pinion.FACE_WIDTH_LIMITS)[1]
PINION_HALF_FACE_MAX = (pinion.FACE_WIDTH+FACE_UPPER)/2.0
CRANK_OVERHANG = shaft.SEAT_PINION + pinion.SEAT_GAP_MAX_MM - pinion.SEAT_FEELER_MM + PINION_HALF_FACE_MAX - CRANK_SUPPORT_NORTH_MIN
CONE_OVERHANG = GEAR64_POST_OFFSET-post.CONE_BOSS_LENGTH/2.0
MESH_LEVER = post.CRANK_BOSS_NORTH_FACE + pinion.SEAT_GAP_MAX_MM + PINION_HALF_FACE_MAX
POST_ANGLE_DEG = post.CRANK_BORE_ANGLE_LIMIT_DEG
TOOTH_RUNOUT_TIR_MM = gear64.TOOTH_RUNOUT_TIR_MM
TIP_ROOT_BAND_RADIAL = max(pinion.OUTSIDE_DIA_TOLERANCE_MM, gear64.OUTSIDE_DIA_TOLERANCE_MM)/2.0
SPACING_PRINTED = round(post.CRANK_ABOVE_CONE, post.DRAWING_PRECISION_BY_NAME["CrankAboveCone"])

# Physical station and plan-angle bounds; derive them from the published
# station grades rather than carrying former ideal-profile fit constants.
import dt_cone_gear_shaft_spec as cone_shaft
CONE_RUNNING = cone_shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM
CONE_BEARING_LENGTH = cone_shaft.JOURNAL_SUPPORT_SPAN_MIN_MM

BOSS_BAND = pinion.printed_deviations(post.CONE_BOSS_LENGTH, post.DRAWING_PRECISION_BY_NAME["ConeBossLen"])
COLLAR_BAND = pinion.printed_deviations(cone_shaft.COLLAR_THICKNESS, cone_shaft.DRAWING_PRECISION_BY_NAME["CollarWidth"])
STATION_TRAVEL_MM = max(abs(v) for v in BOSS_BAND)/2.0 + max(abs(v) for v in COLLAR_BAND) + max(abs(v) for v in gear64.FACE_WIDTH_BAND)/2.0


def float_at_rest(clearance: float, bearing_length: float, overhang: float) -> float:
    return clearance/2.0 + clearance/bearing_length*overhang


def closing_y_terms(*, spacing_printed: float = SPACING_PRINTED,
                    crank_bearing_length: float = CRANK_BEARING_LENGTH) -> dict[str,float]:
    """Actual world-Y location/gravity terms; rotations are not scalar C fits."""
    return {
        "crank bore spacing":spacing_printed+post.CRANK_ABOVE_CONE_BAND[1]-FRAME_DY,
        "crank float at rest":-float_at_rest(CRANK_RUNNING[1],crank_bearing_length,CRANK_OVERHANG),
        "cone float at rest":float_at_rest(CONE_RUNNING[0],CONE_BEARING_LENGTH,CONE_OVERHANG),
    }


def opening_y_terms(*, spacing_printed: float = SPACING_PRINTED,
                    crank_bearing_length: float = CRANK_BEARING_LENGTH) -> dict[str,float]:
    return {
        "crank bore spacing":spacing_printed+post.CRANK_ABOVE_CONE_BAND[0]-FRAME_DY,
        "crank float at rest":float_at_rest(CRANK_RUNNING[1],crank_bearing_length,CRANK_OVERHANG),
        "cone float at rest":float_at_rest(CONE_RUNNING[1],CONE_BEARING_LENGTH,CONE_OVERHANG),
    }


CLOSING_Y_TERMS = closing_y_terms()
OPENING_Y_TERMS = opening_y_terms()


@dataclass(frozen=True)
class UniformPoseDomain:
    """A continuous source-grade enclosure, not nine sampled orientations."""

    radial_error_mm: float
    axial_error_mm: float
    components_mm: tuple[tuple[str,float,float], ...]
    angularity_full_cone: bool
    all_runout_angles: bool = True
    required_root_air_mm: float = 0.0
    correlated_pose_parameters: tuple[tuple[str,tuple[float,float]], ...] = ()

    def record(self) -> dict:
        return asdict(self)


def uniform_pose_domain(pose: dict) -> UniformPoseDomain:
    """Pay all runout directions and real rigid-axis motion without double C.

    The single crank-bore angularity is relative to datum A (cone bore)
    and B (foot). There is no second independent 'cone plan angle' grade.
    Zero-axis representatives enclose its complete orientation cone;
    nonzero axis cases remain additional manufactured-corner witnesses.
    """
    full = pose["yaw_deg"] == pose["tilt_deg"] == 0.0
    theta = math.radians(POST_ANGLE_DEG)
    # Ry(yaw)Rx(tilt), cos(yaw)cos(tilt)>=cos(theta): this bounds the
    # complete rotation, including its second-order retention-clock roll.
    post_angle = 2*math.acos((1+math.sqrt(math.cos(theta)))/2) if full else 0.0
    journal16 = math.atan(CRANK_RUNNING[1]/CRANK_BEARING_LENGTH)
    journal64 = math.atan(CONE_RUNNING[1]/CONE_BEARING_LENGTH)
    beta = min(math.pi/2,math.asin(abs(SIN_I))+abs(math.radians(pose["yaw_deg"]))
               +abs(math.radians(pose["tilt_deg"]))+post_angle+journal16+journal64)
    radial16 = (pinion.OUTSIDE_DIA+pinion.OUTSIDE_DIA_TOLERANCE_MM)/2
    radial64 = (gear64.OUTSIDE_DIA+gear64.OUTSIDE_DIA_TOLERANCE_MM)/2
    face16 = pinion.FACE_WIDTH+max(pinion.FACE_WIDTH_BAND)
    face64 = gear64.FACE_WIDTH+max(gear64.FACE_WIDTH_BAND)
    run16 = pinion.BORE_DIAMETRAL_CLEARANCE[1]/2+pinion.TOOTH_RUNOUT_TIR_MM/2
    run64 = GEAR_SEAT_CLEARANCE[1]/2+gear64.TOOTH_RUNOUT_TIR_MM/2
    components = [
        ("all rotating bore and tooth runout angles",run16+run64,
         run64*math.sin(beta)+run16*math.sin(post_angle+journal16)),
        ("actual 64T axial station interval",STATION_TRAVEL_MM*math.sin(beta),STATION_TRAVEL_MM),
    ]

    def rotation(name, radial, axial, angle, inclination):
        # Rodrigues: transverse tilt moves radial points along the gear
        # axis, axial points transversely. The quadratic term also pays
        # the small Ry/Rx composition roll, rather than assuming zero.
        quadratic = (2*radial+axial)*(1-math.cos(angle))
        components.append((
            name,(radial*math.sin(inclination)+axial)*math.sin(angle)+quadratic,
            (radial+axial*math.sin(inclination))*math.sin(angle)+quadratic,
        ))

    rotation("crank angularity about actual post-axis datum",radial16,
             -post.CRANK_BOSS_START_Z+pinion.SEAT_GAP_MAX_MM+face16,post_angle,0.0)
    rotation("crank journal slope about booked tooth centre",radial16,face16/2,journal16,0.0)
    rotation("cone journal slope about booked gear centre",radial64,face64/2,journal64,beta)
    # The continuation solve uses ONE set of physical source coordinates
    # for both branches. These boxes are conservative rigid-pose supersets,
    # not independent point-displacement balls that may be cancelled.
    # Rotations act about each declared body origin; pay the translation
    # needed to represent the actual post/shaft pivot about that origin.
    lever16 = -post.CRANK_BOSS_START_Z+pinion.SEAT_FEELER_MM+pose["pinion_north_mm"]
    origin16 = 2*abs(lever16)*math.sin(post_angle/2)+face16*math.sin(journal16/2)
    station_transverse = STATION_TRAVEL_MM*math.sin(journal64)
    rotation16,rotation64 = post_angle+journal16,journal64
    if max(rotation16,rotation64) >= math.pi/4:
        raise ValueError("source axis motion exceeds the small-angle Euler enclosure")
    # For geodesic angle a<pi/4, each Rz Ry Rx Euler coordinate is within
    # +/-2a. The extra rectangular corners only make certification harder.
    limits = {
        "driver_dx_mm":origin16,"driver_dy_mm":origin16,"driver_dz_mm":origin16,
        "driven_dx_mm":station_transverse,"driven_dy_mm":station_transverse,
        "driven_dz_mm":STATION_TRAVEL_MM,
        "driver_rx_rad":2*rotation16,"driver_ry_rad":2*rotation16,"driver_rz_rad":2*rotation16,
        "driven_rx_rad":2*rotation64,"driven_ry_rad":2*rotation64,"driven_rz_rad":2*rotation64,
        "driver_ecc_x_mm":run16,"driver_ecc_y_mm":run16,
        "driven_ecc_x_mm":run64,"driven_ecc_y_mm":run64,
    }
    correlated = tuple((name,(-limit,limit)) for name,limit in sorted(limits.items()))
    return UniformPoseDomain(
        sum(row[1] for row in components),sum(row[2] for row in components),
        tuple(components),full,correlated_pose_parameters=correlated,
    )


def qualification_inputs() -> dict:
    """Geometry identity bound into the measured calibration, not old pins."""
    return {
        "centre_mm": FRAME_C2C,
        "frame_dy_mm": FRAME_DY,
        "closed_world_y_terms_mm":CLOSING_Y_TERMS,
        "open_world_y_terms_mm":OPENING_Y_TERMS,
        "selected_phase_offset_deg": _config.machine("gear_train").get("crank_mesh_phase_offset_deg"),
        "post_angle_deg": POST_ANGLE_DEG,
        "pinion_face_mm": pinion.FACE_WIDTH,
        "pinion_face_band_mm": pinion.FACE_WIDTH_BAND,
        "pinion_shoulder_mm": pinion.SHOULDER_LENGTH,
        "pinion_shoulder_band_mm": pinion.SHOULDER_LENGTH_BAND,
        "pinion_turned_dia_mm": pinion.TURNED_DIA,
        "pinion_turned_dia_band_mm": pinion.TURNED_DIA_TOLERANCE_MM,
        "pinion_turn_fitup_min_mm": pinion.TURNED_DIA_FITUP_MIN,
        "pinion_seat_gap_mm": (pinion.SEAT_FEELER_MM,pinion.SEAT_GAP_MAX_MM),
        "gear_face_mm": gear64.FACE_WIDTH,
        "gear_face_band_mm": gear64.FACE_WIDTH_BAND,
        "cone_float_north_mm": CONE_FLOAT_NORTH,
        "station_travel_mm": STATION_TRAVEL_MM,
        "normal_module_mm": gear64.NORMAL_MODULE_MM,
        "helix_deg": gear64.HELIX_ANGLE_DEG,
        "pinion_span_limits_mm":pinion.BASE_TANGENT_SPAN_LIMITS_MM,
        "gear_span_limits_mm":gear64.BASE_TANGENT_SPAN_LIMITS_MM,
        "pinion_span_teeth":pinion.BASE_TANGENT_SPAN_TEETH,
        "gear_span_teeth":gear64.BASE_TANGENT_SPAN_TEETH,
        "pinion_tool_translation_limits_mm":pinion.STOCK_TOOL_TRANSLATION_LIMITS_MM,
        "gear_tool_translation_limits_mm":gear64.STOCK_TOOL_TRANSLATION_LIMITS_MM,
    }


def calibration_case_parameters() -> tuple[dict,...]:
    """Exact source-owned manufactured profiles and physical pose Cartesian set."""
    slack = FRAME_C2C-R16-R64
    nominal = {
        "extra_mm":slack,"yaw_deg":0.0,"tilt_deg":0.0,"cone_float_mm":0.0,
        "pinion_north_mm":0.0,"pinion_face_mm":pinion.FACE_WIDTH,
        "shoulder_mm":pinion.SHOULDER_LENGTH,"turned_radius_mm":pinion.TURNED_DIA/2,
        "gear_face_mm":gear64.FACE_WIDTH,"dx_mm":0.0,"dy_mm":0.0,"cone_dy_mm":0.0,
    }
    closed = dict(nominal,
        dy_mm=CLOSING_Y_TERMS["crank bore spacing"]+CLOSING_Y_TERMS["crank float at rest"],
        cone_dy_mm=-CLOSING_Y_TERMS["cone float at rest"])
    opened = dict(nominal,
        dy_mm=OPENING_Y_TERMS["crank bore spacing"]+OPENING_Y_TERMS["crank float at rest"],
        cone_dy_mm=-OPENING_Y_TERMS["cone float at rest"],
        cone_float_mm=CONE_FLOAT_NORTH,
        pinion_north_mm=pinion.SEAT_GAP_MAX_MM-pinion.SEAT_FEELER_MM,
        pinion_face_mm=pinion.FACE_WIDTH+min(pinion.FACE_WIDTH_BAND),
        shoulder_mm=pinion.SHOULDER_LENGTH+min(pinion.SHOULDER_LENGTH_BAND),
        turned_radius_mm=(pinion.TURNED_DIA-pinion.TURNED_DIA_TOLERANCE_MM)/2,
        gear_face_mm=gear64.FACE_WIDTH+max(gear64.FACE_WIDTH_BAND),
    )
    rows = []
    def add(name,pose,driver="nominal",driven="nominal"):
        rows.append({"name":name,"driver_profile_label":driver,"driven_profile_label":driven,
                     "pose":dict(pose),"pose_domain":uniform_pose_domain(pose).record()})
    add("nominal",nominal)
    add("booked_closed",closed)
    add("booked_open",opened)
    add("centre_minus",dict(nominal,extra_mm=slack-0.15))
    add("centre_plus",dict(nominal,extra_mm=slack+0.15))
    add("turned_fitup_floor",dict(opened,turned_radius_mm=pinion.TURNED_DIA_FITUP_MIN/2))
    angles = (-POST_ANGLE_DEG,0.0,POST_ANGLE_DEG)
    for label16,_ in pinion.STOCK_PROFILE_CORNERS:
        for label64,_ in gear64.STOCK_PROFILE_CORNERS:
            for end,pose in (("closed",closed),("open",opened),
                             ("fitup",dict(opened,turned_radius_mm=pinion.TURNED_DIA_FITUP_MIN/2))):
                for yaw in angles:
                    for tilt in angles:
                        suffix = "" if yaw == tilt == 0.0 else f"_yaw{yaw:+.8f}_tilt{tilt:+.8f}"
                        add(f"profile_corner_{label16}_{label64}_{end}{suffix}",
                            dict(pose,yaw_deg=yaw,tilt_deg=tilt),label16,label64)
    for end,pose in (("closed",closed),("open",opened)):
        for yaw in angles:
            for tilt in angles:
                if yaw != 0.0 or tilt != 0.0:
                    add(f"axis_corner_{end}_{yaw:+.8f}_{tilt:+.8f}",dict(pose,yaw_deg=yaw,tilt_deg=tilt))
    return tuple(rows)


def required_calibration_case_names() -> frozenset[str]:
    return frozenset(case["name"] for case in calibration_case_parameters())


def placement_record(pose: dict) -> dict:
    """Pure exact physical pose shared by the 3D study and its frozen receiver."""
    gear_station = gear64.LAYOUT_CENTRE_STATION+GEAR_AXIS_SHIFT+gear64.CENTRE_SHIFT_NORTH
    seat = cone_line.cone_station(gear_station)
    x = cone_line.X_CRANK+pose["dx_mm"]
    base_dx = (seat[0]-cone_line.X_CRANK)*COS_I
    c = R16+R64+pose["extra_mm"]
    y = cone_line.Y_DRIVE+math.sqrt(c*c-base_dx*base_dx)+pose["dy_mm"]
    yaw,tilt = math.radians(pose["yaw_deg"]),math.radians(pose["tilt_deg"])
    cy,sy,ct,st = math.cos(yaw),math.sin(yaw),math.cos(tilt),math.sin(tilt)
    frame = [[cy,sy*st,sy*ct],[0.0,ct,-st],[-sy,cy*st,cy*ct]]
    # BoreSpacingReference locates the crank axis at the post axis (local
    # z=0). Angularity turns the whole pinion about that physical datum,
    # including its overhang; it does not turn only about the tooth centre.
    pivot = [x, y, cone_line.cone_station(POST_STATION)[2]]
    back_face_lever = (
        -post.CRANK_BOSS_START_Z + pinion.SEAT_FEELER_MM + pose["pinion_north_mm"]
    )
    origin = [
        pivot[i] + frame[i][2] * back_face_lever
        for i in range(3)
    ]
    # Retention clock is one manufactured datum, not re-clocked at every
    # clearance/runout/axis corner. All cases share the nominal station.
    dx = seat[0]-cone_line.X_CRANK
    dy = math.sqrt(FRAME_C2C**2-base_dx*base_dx)
    a64,a16 = math.atan2(dy,dx*COS_I),math.atan2(dy,dx)
    pitch64,pitch16 = 2*math.pi/gear64.TEETH,2*math.pi/pinion.TEETH
    delta64 = round(a64/pitch64)*pitch64-a64
    seed = (a16+math.pi-delta64*gear64.TEETH/pinion.TEETH-pitch16/2)%pitch16
    return {
        "driver_origin_mm":origin,
        "driven_origin_mm":[seat[0]+pose["cone_float_mm"]*SIN_I,seat[1]+pose["cone_dy_mm"],seat[2]+pose["cone_float_mm"]*COS_I],
        "driver_frame":frame,"driven_frame":[[COS_I,0.0,SIN_I],[0.0,1.0,0.0],[-SIN_I,0.0,COS_I]],
        "driver_face_mm":[0.0,pose["pinion_face_mm"]],
        "driven_face_mm":[-pose["gear_face_mm"]/2,pose["gear_face_mm"]/2],
        "driver_clocking_rad":-seed,"driven_clocking_rad":0.0,
        "driver_shoulder_z_mm":pose["shoulder_mm"],
        "driver_turned_radius_mm":pose["turned_radius_mm"],
    }


def calibration_case_domains() -> dict[str,dict]:
    return {case["name"]:case["pose_domain"] for case in calibration_case_parameters()}


def calibration_case_placements() -> dict[str,dict]:
    return {case["name"]:placement_record(case["pose"]) for case in calibration_case_parameters()}
