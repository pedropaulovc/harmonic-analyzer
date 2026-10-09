"""Pure physical/tolerance inputs to the actual crossed-crank qualification.

No fitted backlash sensitivities or diagnostic engine belongs in a native
part dependency. These are dimensional stack terms, in mm, consumed by the
offline 3D study and checked against its frozen calibration at publication.
"""
from __future__ import annotations

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


def _journal_origin_motion(clearance_mm, support_span_mm, origin_from_north_contact_mm):
    """One finite-journal float, then only the OUTSIDE-support tilt lever.

    At either retained contact the centre lies within c/2; between contacts
    its linear interpolation does too. Extrapolation beyond the nearest
    retained contact adds one rigid-axis chord, 2*g*sin(theta/2), where
    tan(theta)<=c/S. The material's rotation about this origin is paid by the
    body pose, not a second origin lever or another radial-clearance debit.
    """
    low,high = origin_from_north_contact_mm
    if (any(type(v) not in (int,float) or not math.isfinite(v)
            for v in (clearance_mm,support_span_mm,low,high))
            or clearance_mm < 0 or support_span_mm <= 0 or low > high):
        raise ValueError("journal origin needs finite own clearance, retained span and ordered contact coordinates")
    angle = math.nextafter(math.atan(clearance_mm/support_span_mm),math.inf) if clearance_mm else 0.0
    outside = max(0.0,high,-support_span_mm-low)
    tilt = 2*outside*math.sin(angle/2)
    motion = math.nextafter(clearance_mm/2+tilt,math.inf) if tilt else clearance_mm/2
    return {
        "diametral_clearance_upper_mm":clearance_mm,
        "retained_contact_span_min_mm":support_span_mm,
        "origin_from_north_contact_interval_mm":[low,high],
        "outside_support_lever_upper_mm":outside,
        "angle_upper_rad":angle,
        "radial_float_upper_mm":clearance_mm/2,
        "outside_support_rotation_upper_mm":tilt,
        "origin_motion_upper_mm":motion,
    }


def uniform_pose_domain(
    pose: dict, *, conditional_lateral_origin_half_width_mm: float | None = None,
    conditional_driver_clock_half_width_rad: float | None = None,
    conditional_driven_clock_half_width_rad: float | None = None,
) -> dict:
    """Whole relative SAME-post source, with explicit unprovided origin grade.

    Common mounting motions cancel. The two real shaft journals remain
    independent, each using its own retained cylindrical contact span. The
    Cartesian/Euler boxes are conservative supersets, shared by every branch;
    they are not independently movable point balls or observed stock passes.
    """
    if pose["yaw_deg"] != 0 or pose["tilt_deg"] != 0:
        raise ValueError("continuous relative source replaces sampled yaw/tilt representatives")
    assumptions = {
        "relative_running_bore_lateral_origin_half_width_mm":conditional_lateral_origin_half_width_mm,
        "driver_material_clock_half_width_rad":conditional_driver_clock_half_width_rad,
        "driven_material_clock_half_width_rad":conditional_driven_clock_half_width_rad,
    }
    if any(value is not None and (type(value) not in (float,int) or not math.isfinite(value) or value < 0)
           for value in assumptions.values()):
        raise ValueError("conditional DESIGN assumptions must be explicit finite nonnegative bounds")
    assumptions = {name:value for name,value in assumptions.items() if value is not None}
    unbound = [] if conditional_lateral_origin_half_width_mm is not None else [
        "finished crank running-bore lateral origin relative to cone datum A at the SAME post station"]
    boss16 = pinion.printed_deviations(post.CRANK_BOSS_LENGTH,post.DRAWING_PRECISION_BY_NAME["CrankBossLen"])
    boss64 = pinion.printed_deviations(post.CONE_BOSS_LENGTH,post.DRAWING_PRECISION_BY_NAME["ConeBossLen"])
    north = pinion.printed_deviations(post.CRANK_BOSS_NORTH_FACE,post.DRAWING_PRECISION_BY_NAME["CrankBossStartZ"])
    collar = pinion.printed_deviations(cone_shaft.COLLAR_THICKNESS,cone_shaft.DRAWING_PRECISION_BY_NAME["CollarWidth"])
    post_angle = math.nextafter(math.atan(post.CRANK_BORE_ANGULARITY_MM/(post.CRANK_BOSS_LENGTH+boss16[0])),math.inf)
    # The feeler/fit-up sets the actual SOUTH pinion face from the finished
    # boss face. It can run south onto that face. Shaft overall length and
    # step standoff are not added again after this installed face condition.
    seat16 = (north[0]-pinion.SEAT_FEELER_MM,
              north[1]+pinion.SEAT_GAP_MAX_MM-pinion.SEAT_FEELER_MM)
    # The 64T south face bears on the real collar. Its face-width variation
    # grows NORTH from that face (anchor 0 below), not another centre float.
    seat64 = (boss64[0]/2+collar[0],boss64[1]/2+collar[1]+CONE_FLOAT_NORTH)
    post_lever16 = post.CRANK_BOSS_NORTH_FACE+north[1]+pinion.SEAT_GAP_MAX_MM
    # The native shaft's common world-Z offset cancels: this is the pinion
    # SOUTH-face origin minus its own retained inboard journal end, both in
    # shaft stations. It is not the complete boss length plus a face gap.
    support16 = (
        math.nextafter(math.fsum((shaft.SHAFT_LENGTH,min(shaft.SHAFT_LENGTH_BAND),
                                 -shaft.JOURNAL_INBOARD_STATION,-shaft.STATION_ROW)),-math.inf),
        math.nextafter(math.fsum((shaft.SHAFT_LENGTH,max(shaft.SHAFT_LENGTH_BAND),
                                 -shaft.JOURNAL_INBOARD_STATION,shaft.STATION_ROW)),math.inf))
    near16 = (
        math.nextafter(math.fsum((shaft.SEAT_PINION,seat16[0],-support16[1])),-math.inf),
        math.nextafter(math.fsum((shaft.SEAT_PINION,seat16[1],-support16[0])),math.inf))
    # Both cone gear seat and near bore rim use the SAME actual boss north
    # face, so boss-length variation cancels here. Withdrawal shortens the
    # published MIN span and extends this one lever; it is not another float.
    near64 = (
        math.nextafter(math.fsum((GEAR64_POST_OFFSET,-post.CONE_BOSS_LENGTH/2,collar[0])),-math.inf),
        math.nextafter(math.fsum((GEAR64_POST_OFFSET,-post.CONE_BOSS_LENGTH/2,collar[1],
                                 CONE_FLOAT_NORTH,cone_shaft.THRUST_EDGE_BREAK_MAX)),math.inf))
    journal_motion16 = _journal_origin_motion(CRANK_RUNNING[1],CRANK_BEARING_LENGTH,near16)
    journal_motion64 = _journal_origin_motion(CONE_RUNNING[1],CONE_BEARING_LENGTH,near64)
    journal16,journal64 = journal_motion16["angle_upper_rad"],journal_motion64["angle_upper_rad"]
    rotation16 = math.nextafter(post_angle+journal16,math.inf)
    if max(rotation16,journal64) >= math.pi/4:
        raise ValueError("actual source rotations exceed the declared Euler enclosure")
    motion16 = math.nextafter(
        2*post_lever16*math.sin(post_angle/2)+journal_motion16["origin_motion_upper_mm"],math.inf)
    motion64 = journal_motion64["origin_motion_upper_mm"]
    reference = placement_record(pose)
    relative_height = reference["driver_origin_mm"][1]-reference["driven_origin_mm"][1]
    candidate = pose["extra_mm"] != FRAME_C2C-R16-R64
    printed_height = (round(relative_height,post.DRAWING_PRECISION_BY_NAME["CrankAboveCone"])
                      if candidate else SPACING_PRINTED)
    height = (printed_height+post.CRANK_ABOVE_CONE_BAND[1]-relative_height,
              printed_height+post.CRANK_ABOVE_CONE_BAND[0]-relative_height)
    def outer(lo,hi):
        return [math.nextafter(lo,-math.inf),math.nextafter(hi,math.inf)]
    lateral = conditional_lateral_origin_half_width_mm
    axes = {
        "driver_dx_mm":None if lateral is None else outer(-lateral-motion16,lateral+motion16),
        "driver_dy_mm":outer(height[0]-motion16,height[1]+motion16),
        "driver_dz_mm":outer(seat16[0]-motion16,seat16[1]+motion16),
        "driven_dx_mm":outer(-motion64,motion64),"driven_dy_mm":outer(-motion64,motion64),
        "driven_dz_mm":outer(seat64[0]-motion64,seat64[1]+motion64),
    }
    for body,angle in (("driver",rotation16),("driven",journal64)):
        for axis in "xyz":
            axes[f"{body}_r{axis}_rad"] = outer(-2*angle,2*angle)
    disks = {}
    for body,terms in (
        ("driver",{"pinion bore radial running clearance":pinion.BORE_DIAMETRAL_CLEARANCE[1]/2,
                   "16T tooth radial runout to finished bore":pinion.TOOTH_RUNOUT_TIR_MM/2}),
        ("driven",{"64T bore radial seat clearance":GEAR_SEAT_CLEARANCE[1]/2,
                   "64T tooth radial runout to finished bore":gear64.TOOTH_RUNOUT_TIR_MM/2})):
        radius = 0.0
        for value in terms.values():
            radius = math.nextafter(radius+value,math.inf)
        disks[body] = {"shape":"closed_disk","centre_mm":[0.0,0.0],"radius_mm":radius,"source_terms_mm":terms}
        axes[f"{body}_ecc_x_mm"] = axes[f"{body}_ecc_y_mm"] = [-radius,radius]
    for body,teeth,assumed in (("driver",pinion.TEETH,conditional_driver_clock_half_width_rad),
                              ("driven",gear64.TEETH,conditional_driven_clock_half_width_rad)):
        radius = math.nextafter(math.pi/teeth,math.inf) if assumed is None else assumed
        axes[f"{body}_clock_rad"] = [-radius,radius]
    conditional = bool(assumptions) or candidate
    return {
        "scope":"DESIGN_CONDITIONAL_SOURCE_DOMAIN" if conditional else "FULL_PRODUCTION_SOURCE_DOMAIN",
        "production_source_domain":not conditional and not unbound,
        "source_domain_status":"UNKNOWN" if unbound else "BOUND","unbound_sources":unbound,
        "conditional_design_assumptions":assumptions,
        **({"candidate_post_spacing_mm":printed_height} if candidate else {}),
        "correlated_pose_parameters":[[name,bounds] for name,bounds in sorted(axes.items())],
        "nominal_source_parameters":{name:0.0 for name in sorted(axes)},
        "source_parameter_origin":"deviations from the actual manufactured placement datum; fixed absolute settings remain in placement",
        "source_eccentricity_disks":disks,"mechanical_zero_rad":{"driver":0.0,"driven":0.0},
        "root_air_requirements_mm":{"driver":0.0,"driven":0.0},
        "finite_face_width_limits_mm":{
            "driver":[pinion.FACE_WIDTH+min(pinion.FACE_WIDTH_BAND),pinion.FACE_WIDTH+max(pinion.FACE_WIDTH_BAND)],
            "driven":[gear64.FACE_WIDTH+min(gear64.FACE_WIDTH_BAND),gear64.FACE_WIDTH+max(gear64.FACE_WIDTH_BAND)]},
        "finite_face_anchor_fraction":{"driver":0.0,"driven":0.0},
        "driver_retained_band_limits_mm":{
            "shoulder_z":[pinion.SHOULDER_LENGTH_FITUP_MIN,pinion.SHOULDER_LENGTH+max(pinion.SHOULDER_LENGTH_BAND)],
            "turned_radius":[pinion.TURNED_DIA_FITUP_MIN/2,(pinion.TURNED_DIA+pinion.TURNED_DIA_TOLERANCE_MM)/2]},
        "physical_source_ledger":{
            "post_direction_diametral_mm":post.CRANK_BORE_ANGULARITY_MM,
            "post_relative_height_deviation_mm":list(height),"post_direction_rad":post_angle,
            "driver_journal_clearance_mm":list(CRANK_RUNNING),"driver_contact_span_mm":CRANK_BEARING_LENGTH,
            "driven_journal_clearance_mm":list(CONE_RUNNING),"driven_contact_span_mm":CONE_BEARING_LENGTH,
            "driver_actual_face_seat_deviation_mm":list(seat16),"driven_actual_south_seat_deviation_mm":list(seat64),
            "driver_journal_origin_lever_upper_mm":journal_motion16["outside_support_lever_upper_mm"],
            "driven_journal_origin_lever_upper_mm":journal_motion64["outside_support_lever_upper_mm"],
            "driver_journal_origin_enclosure":journal_motion16,
            "driven_journal_origin_enclosure":journal_motion64,
            "driver_retained_north_contact_shaft_station_interval_mm":list(support16),
            "driver_origin_anchor":"pinion SOUTH face; common shaft/world offset cancels against retained inboard journal end",
            "driven_origin_anchor":"64T nominal midplane; common actual boss north face cancels against retained near bore rim",
            "journal_coupling":"c/2 inside retained span; c/2 plus ONE outside-support rotation; body-point rotation remains in pose",
            "common_post_mount_motion":"cancels; not an independent global two-support debit",
            "clock_scope":"full tooth-pattern pitch unless an explicitly conditional DESIGN band is supplied",
            "gravity_scope":"all opposed running-journal seats retained; no pre-booked gravity translation",
            "north_float_scope":"one axial seat interval, also used only as lever reach in rotation",
            "origin_scope":"relative finite post bores at one physical axial station; direction is not a lateral-origin grade",
        },
        "qualification_scope":"conditional/source outer enclosure only; no manufactured stock observation",
    }


def qualification_inputs() -> dict:
    """Geometry identity bound into the measured calibration, not old pins."""
    return {
        "centre_mm": FRAME_C2C,
        "frame_dy_mm": FRAME_DY,
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
        "normal_module_mm": gear64.NORMAL_MODULE_MM,
        "helix_deg": gear64.HELIX_ANGLE_DEG,
        "pinion_span_limits_mm":pinion.BASE_TANGENT_SPAN_LIMITS_MM,
        "gear_span_limits_mm":gear64.BASE_TANGENT_SPAN_LIMITS_MM,
        "pinion_span_teeth":pinion.BASE_TANGENT_SPAN_TEETH,
        "gear_span_teeth":gear64.BASE_TANGENT_SPAN_TEETH,
        "pinion_tool_translation_limits_mm":pinion.STOCK_TOOL_TRANSLATION_LIMITS_MM,
        "gear_tool_translation_limits_mm":gear64.STOCK_TOOL_TRANSLATION_LIMITS_MM,
    }


def calibration_case_parameters(*, centre_shift_mm: float = 0.0, conditional_source: dict | None = None) -> tuple[dict,...]:
    """Nominal and EVERY printed profile corner, each over one whole source.

    Pose, fit-up, face, journal, clock and axial-seat corners are continuous
    coordinates/material families, not a sampled Cartesian witness grid.
    """
    if type(centre_shift_mm) not in (float,int) or not math.isfinite(centre_shift_mm):
        raise ValueError("candidate centre shift must be finite")
    slack = FRAME_C2C-R16-R64+centre_shift_mm
    nominal = {
        "extra_mm":slack,"yaw_deg":0.0,"tilt_deg":0.0,"cone_float_mm":0.0,
        "pinion_north_mm":0.0,"pinion_face_mm":pinion.FACE_WIDTH,
        "shoulder_mm":pinion.SHOULDER_LENGTH,"turned_radius_mm":pinion.TURNED_DIA/2,
        "gear_face_mm":gear64.FACE_WIDTH,"dx_mm":0.0,"dy_mm":0.0,"cone_dy_mm":0.0,
    }
    rows = []
    def add(name,driver="nominal",driven="nominal"):
        rows.append({"name":name,"driver_profile_label":driver,"driven_profile_label":driven,
                     "pose":dict(nominal),"continuous_source_domain":uniform_pose_domain(nominal,**(conditional_source or {}))})
    add("nominal")
    for label16,_ in pinion.STOCK_PROFILE_CORNERS:
        for label64,_ in gear64.STOCK_PROFILE_CORNERS:
            add(f"profile_corner_{label16}_{label64}",label16,label64)
    return tuple(rows)


def required_calibration_case_names() -> frozenset[str]:
    return frozenset(case["name"] for case in calibration_case_parameters())


def placement_record(pose: dict, *, selected_phase_offset_deg: float | None = None) -> dict:
    """Physical manufactured datum; None means the unselected reference ONLY."""
    if selected_phase_offset_deg is not None and (
            type(selected_phase_offset_deg) not in (float,int) or not math.isfinite(selected_phase_offset_deg)):
        raise ValueError("selected physical crank phase must be finite")
    gear_station = gear64.LAYOUT_CENTRE_STATION+GEAR_AXIS_SHIFT+gear64.CENTRE_SHIFT_NORTH
    seat = cone_line.cone_station(gear_station)
    x = cone_line.X_CRANK+pose["dx_mm"]
    base_dx = (seat[0]-cone_line.X_CRANK)*COS_I
    c = FRAME_C2C+(pose["extra_mm"]-(FRAME_C2C-R16-R64))
    reference_dy = math.sqrt(FRAME_C2C*FRAME_C2C-base_dx*base_dx)
    nominal_y = cone_line.Y_CRANK+(math.sqrt(c*c-base_dx*base_dx)-reference_dy)
    y = nominal_y+pose["dy_mm"]
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
    dy = nominal_y-cone_line.Y_DRIVE
    a64,a16 = math.degrees(math.atan2(dy,dx*COS_I)),math.degrees(math.atan2(dy,dx))
    pitch64,pitch16 = 360.0/gear64.TEETH,360.0/pinion.TEETH
    delta64 = round(a64/pitch64)*pitch64-a64
    seed_deg = ((a16+180.0)-delta64*(gear64.TEETH/pinion.TEETH)-pitch16/2)%pitch16
    # Native assembly and matched-hole manufacture use this degree arithmetic.
    # The final conversion is not replaced by a post-hoc driven-angle tare.
    selected_clock_deg = seed_deg+(selected_phase_offset_deg if selected_phase_offset_deg is not None else 0.0)
    return {
        "driver_origin_mm":origin,
        "driven_origin_mm":[seat[0]+pose["cone_float_mm"]*SIN_I,seat[1]+pose["cone_dy_mm"],seat[2]+pose["cone_float_mm"]*COS_I],
        "driver_frame":frame,"driven_frame":[[COS_I,0.0,SIN_I],[0.0,1.0,0.0],[-SIN_I,0.0,COS_I]],
        "driver_face_mm":[0.0,pose["pinion_face_mm"]],
        "driven_face_mm":[-pose["gear_face_mm"]/2,pose["gear_face_mm"]/2],
        "driver_clocking_rad":-math.radians(selected_clock_deg),"driven_clocking_rad":0.0,
        "driver_shoulder_z_mm":pose["shoulder_mm"],
        "driver_turned_radius_mm":pose["turned_radius_mm"],
    }


def calibration_case_domains(*, centre_shift_mm: float = 0.0, conditional_source: dict | None = None) -> dict[str,dict]:
    return {case["name"]:case["continuous_source_domain"] for case in calibration_case_parameters(
        centre_shift_mm=centre_shift_mm,conditional_source=conditional_source)}


def calibration_case_placements(*, centre_shift_mm: float = 0.0, conditional_source: dict | None = None,
                                selected_phase_offset_deg: float | None = None) -> dict[str,dict]:
    return {case["name"]:placement_record(case["pose"],selected_phase_offset_deg=selected_phase_offset_deg)
            for case in calibration_case_parameters(centre_shift_mm=centre_shift_mm,conditional_source=conditional_source)}


def geometry_sha256() -> str:
    """Pure actual geometry/grades identity, excluding selected phase OUTPUT.

    No measurement implementation or frozen calibration is imported. Exact
    measuring-source authentication belongs to the separate six-file manifest.
    """
    import hashlib
    import json
    from pathlib import Path
    def profile(value):
        return (value.teeth,value.template.reference_teeth,value.template.diametral_pitch,
                value.template.pressure_angle_deg,value.blank_radius_mm,
                value.radial_translation_mm,value.helix_angle_deg)
    values = qualification_inputs()
    values["profiles"] = [profile(spec.STOCK_PROFILE) for spec in (pinion,gear64)]
    values["manufactured_corners"] = [
        [(label,profile(value)) for label,value in spec.STOCK_PROFILE_CORNERS] for spec in (pinion,gear64)]
    values["physical_case_placements"] = calibration_case_placements()
    values["physical_case_domains"] = calibration_case_domains()
    root = Path(__file__).resolve().parent
    values["geometry_source_sha256"] = {
        name:hashlib.sha256((root/name).read_bytes()).hexdigest()
        for name in ("stock_form_cutter.py","crank_mesh_geometry.py")}
    return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def nominal_reference_domain(source: dict,pose: dict) -> dict:
    """Actual declared nominal semantic point, not an interval-centre alias."""
    axes = dict(source["correlated_pose_parameters"])
    nominal = source["nominal_source_parameters"]
    if source.get("unbound_sources") or axes.keys() != nominal.keys():
        raise ValueError("nominal crank reference has an unbound or undeclared physical source")
    for name,value in nominal.items():
        if (type(value) not in (float,int) or not math.isfinite(value)
                or axes[name] is None or not axes[name][0] <= value <= axes[name][1]):
            raise ValueError(f"declared nominal crank source is outside its actual domain: {name}")
    if any(value != 0 for name,value in nominal.items() if "_ecc_" in name):
        raise ValueError("nominal eccentricity point must be the source-declared physical bore-centred datum")
    faces = {"driver":pose["pinion_face_mm"],"driven":pose["gear_face_mm"]}
    band = {"shoulder_z":pose["shoulder_mm"],"turned_radius":pose["turned_radius_mm"]}
    for body,value in faces.items():
        lo,hi = source["finite_face_width_limits_mm"][body]
        if not lo <= value <= hi:
            raise ValueError("nominal actual face width leaves its source-grade family")
    for name,value in band.items():
        lo,hi = source["driver_retained_band_limits_mm"][name]
        if not lo <= value <= hi:
            raise ValueError("nominal actual retained band leaves its source-grade family")
    return {
        **source,"scope":"DESIGN_NOMINAL_SUBDOMAIN","production_source_domain":False,
        "nominal_reference_of_source":source,
        "correlated_pose_parameters":[[name,[nominal[name],nominal[name]]] for name in axes],
        "source_eccentricity_disks":{
            body:{"shape":"closed_disk","centre_mm":[0.0,0.0],"radius_mm":0.0,
                  "source_terms_mm":{name:0.0 for name in disk["source_terms_mm"]}}
            for body,disk in source["source_eccentricity_disks"].items()},
        "finite_face_width_limits_mm":{body:[value,value] for body,value in faces.items()},
        "driver_retained_band_limits_mm":{name:[value,value] for name,value in band.items()},
        "qualification_scope":"actual declared nominal profile/face/band/source point only; never a production uncertainty waiver",
    }
