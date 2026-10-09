"""Pure retained cone/drum placement and complete-source transport.

No diagnostic engine, selected factory output or native certificate is read.
Raise owns shaft support; this adapter only projects that authority into the
shared body's named coordinates. Missing tooth-to-bore runout authority is
UNKNOWN, never a zero tolerance or the unrelated crank mesh's grade.
"""
from __future__ import annotations

from dataclasses import asdict
import math


class SourceDomainUnknown(ValueError):
    """A real physical source authority needed by the full mesh is absent."""


BUDGET_CLOCK_EXCLUDED_TERMS = (
    "cone_flat_free_clock","BoreFlatClock","drum_tooth_to_cam_notch_clock",
)


def tooth_cutting_runout_tir_mm(body: str) -> float:
    """Read the shared part's required process/inspection TIR, not measured stock.

    These source keys receive grades only after actual all-profile margins
    establish an achievable observable requirement. Their absence is refusal.
    The drum grade is also the same 120T part's alignment-mesh input.
    """
    import _config
    if body not in ("cone", "drum"):
        raise ValueError("tooth runout body must be cone or drum")
    key = f"{body}_tooth_cutting_runout_tir_mm"
    try:
        value = _config.fit("cone_drum_oblique_mesh", key)
    except KeyError as error:
        raise SourceDomainUnknown(f"missing actual {body} tooth-to-bore TIR authority: {key}") from error
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0.0:
        raise SourceDomainUnknown(f"{body} tooth-to-bore TIR must be a finite positive source requirement")
    return float(value)


def drum_tooth_to_cam_notch_clock_deg() -> float:
    """Require the actual gear-pattern/CAM-NOTCH grade, not the lobe grade.

    Whole-body NOTCH-up setup is not this manufactured angular error.
    A proposed or full-pitch engineering band is not a production requirement.
    """
    import _config
    key = "drum_tooth_to_cam_notch_clock_deg"
    try:
        value = _config.fit("cone_drum_oblique_mesh", key)
    except KeyError as error:
        raise SourceDomainUnknown(f"missing actual drum tooth-to-CAM-NOTCH clock authority: {key}") from error
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0.0:
        raise SourceDomainUnknown("drum tooth-to-CAM-NOTCH clock must be a finite positive source requirement")
    return float(value)


def installed_axis_acceptance_from_record(record):
    """Reconstruct only Raise's validated whole observer, with no preset."""
    import dt_cone_support_pose as support
    if record is None:
        return None
    types = (support.InstalledAxisAcceptance, support.InstalledSupportMotionAcceptance)
    if isinstance(record, types):
        return record
    if not isinstance(record, dict):
        raise ValueError("installed axis authority must be a Raise record")
    if "north_radial_motion_max_mm" in record:
        return support.InstalledSupportMotionAcceptance(**record)
    return support.InstalledAxisAcceptance(**record)


def _member(teeth: int) -> None:
    if type(teeth) is not int or teeth not in range(6, 121, 6):
        raise ValueError("cone source member must be T006..T120")


def _station_and_frame(teeth: int):
    import cone_line
    import dt_cone_gear_spec as cone
    _member(teeth)
    j = (120 - teeth) // 6
    station = (cone_line.SHAFT_T120_STATION + cone_line.GEAR_AXIS_SHIFT
               + (cone_line.CONE_FACE_STATION_REFERENCE - cone.FACE_WIDTH) / 2
               + j * cone_line.SEAT_PITCH)
    c, s = cone_line.COS_I, cone_line.SIN_I
    return station, ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


def manufactured_datum_mapping(teeth: int) -> dict:
    """Trace canonical GAP angles to fixed cone-lock and bank CAM-NOTCH rays.

    Cone native gaps are pi/T from the core; D-flat/tooth0 is local +X.
    Drum native gaps are pi/N and its notch is +Y plus NOTCH_PHASE_DEG.
    Ry180*Rz(-lock) reflects native theta to pi-lock-theta. The world
    notch-minus-gap angle is therefore minus their native difference.
    BANK +Y is the physical NOTCH-up reference. The documented zeroing
    operation ROTATES the drum to it; the raw saved-CAD bias is retained
    separately. Neither contact fitting nor numerical TE subtraction does so.
    """
    import _config
    import dt_cylinder_gear_spec as drum
    _member(teeth)
    lock = math.radians(_config.machine("gear_train", "cylinder_lock_phase_deg"))
    drum_gap = math.pi / drum.TEETH
    native_notch = math.pi / 2 + math.radians(drum.NOTCH_PHASE_DEG)
    world_notch_minus_gap = -(native_notch - drum_gap)
    bank_reference = math.pi / 2
    beta_zero = bank_reference - world_notch_minus_gap
    gap_clock = math.pi - lock - drum_gap
    return {
        "mechanical_zero_rad": {"driver": 0.0, "driven": beta_zero},
        "driver_canonical_gap_clock_rad": math.pi / teeth,
        "driven_canonical_gap_clock_rad": beta_zero,
        "saved_cad_driven_canonical_gap_clock_rad": gap_clock,
        "native_cam_notch_ray_rad": native_notch,
        "world_cam_notch_minus_canonical_gap_rad": world_notch_minus_gap,
        "bank_cam_notch_reference_ray_rad": bank_reference,
        "nominal_world_cam_notch_ray_rad": beta_zero + world_notch_minus_gap,
        "saved_cad_world_cam_notch_ray_rad": gap_clock + world_notch_minus_gap,
        "nominal_driven_mechanical_phase_rad": 0.0,
        "saved_cad_driven_mechanical_phase_rad": gap_clock - beta_zero,
        "operating_source_state": "OPERATING_NOTCH_UP",
        "physical_driven_setup_rotation_rad": beta_zero - gap_clock,
        "source": {
            "cone_gap": "build_dt_cone_gear.native_gap_segments: pi/T; keyed D-flat outward normal +X",
            "drum_gap": "_gear.build_stock_form_gear: default pi/N, tooth crest +X",
            "cam_notch": "dt_cylinder_gear_spec.NOTCH_PHASE_DEG and native NotchPhase: first root CCW from +Y cam lobe",
            "native_transform": "build_dt_drive_train_assembly cylinder_rows=Ry180*Rz(-CYLINDER_LOCK_PHASE_DEG)",
            "fixed_reference": "tolerance-policy.md: literal CAM-NOTCH-up cosine zeroing; cone lock and crank index establish subsequent cam datum",
            "not_lobe_waiver": "historical lobe-up/#749 assembly waiver is not this physical notch datum",
        },
        "alignment_zero_operation": "Documented physical drum rotation to literal NOTCH-up (quarter turn for sines), then park alignment drum and retain cone-lock/crank-index; signed setup rotation is applied to geometry, never subtracted from TE",
        "datum_tare_rad": None,
    }


def nominal_placement_record(teeth: int) -> dict:
    """Actual basic assembly placement in the engine's world-positive gauge.

    The symmetric straight cylinder's native Ry180*Rz(-lock) is reparameterized
    about world +Z, reflecting native axial coordinates and rotation sign.
    This changes neither solid nor the absolute CAM-NOTCH datum.
    """
    import cone_line
    import dt_cone_gear_spec as cone
    import dt_cylinder_gear_spec as drum
    station, frame = _station_and_frame(teeth)
    datum = manufactured_datum_mapping(teeth)
    j = (120 - teeth) // 6
    drum_z = cone_line.Z_DRUM0 + j * cone_line.Z_PITCH
    return {
        "driver_origin_mm": list(cone_line.cone_station(station)),
        "driven_origin_mm": [cone_line.DRUM_X, cone_line.Y_DRIVE, drum_z],
        "driver_frame": [list(row) for row in frame],
        "driven_frame": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "driver_face_mm": [-cone.FACE_WIDTH / 2, cone.FACE_WIDTH / 2],
        "driven_face_mm": [-drum.FACE_WIDTH / 2, drum.FACE_WIDTH / 2],
        "driver_clocking_rad": datum["driver_canonical_gap_clock_rad"],
        "driven_clocking_rad": datum["driven_canonical_gap_clock_rad"],
        "driver_shoulder_z_mm": None,
        "driver_turned_radius_mm": None,
    }


def _outward_radius(terms: dict[str, float]) -> float:
    if not terms or any(not math.isfinite(value) or value < 0 for value in terms.values()):
        raise SourceDomainUnknown("source eccentricity needs finite named radial allowances")
    return math.nextafter(math.fsum(terms.values()), math.inf)


def source_eccentricity_disks(teeth: int) -> dict:
    """Full body-fixed disks, including actual bore/land clearance and own TIR."""
    import cone_shaft_land_bands as lands
    import dt_cone_gear_spec as cone
    import dt_cylinder_gear_spec as drum
    _member(teeth)
    cone_tir = tooth_cutting_runout_tir_mm("cone")
    drum_tir = tooth_cutting_runout_tir_mm("drum")
    section = cone.land_section(teeth)
    diameter = cone.bore_dia_mm(teeth)
    shaft_low, _ = lands.land_finished_dia_limits_mm(diameter, section)
    bore_places = cone.DRAWING_PRECISION_BY_NAME["BoreCutDia"]
    bore_high = round(diameter, bore_places) + cone.BORE_DIA_BAND[0]
    terms = {
        "driver": {
            "gear_bore_radial_clearance_upper": (bore_high - shaft_low) / 2,
            "tooth_runout_radius_upper": cone_tir / 2,
        },
        "driven": {
            "gear_bore_radial_clearance_upper": drum.BORE_DIAMETRAL_CLEARANCE_MM[1] / 2,
            "tooth_runout_radius_upper": drum_tir / 2,
        },
    }
    return {
        body: {"shape": "closed_disk", "centre_mm": [0.0, 0.0],
               "radius_mm": _outward_radius(values), "source_terms_mm": values}
        for body, values in terms.items()
    }


def _interval_product(a, b):
    values = tuple(x*y for x in a for y in b)
    return math.nextafter(min(values),-math.inf),math.nextafter(max(values),math.inf)


def _interval_sum(values):
    rows = tuple(values)
    return (math.nextafter(math.fsum(row[0] for row in rows),-math.inf),
            math.nextafter(math.fsum(row[1] for row in rows),math.inf))


def _centre_source_ledger(teeth, pose, disks, axial, drum_axial, pivot_radial, pivot_axial, booked):
    """Directed horizontal-section centre OUTER, not independent engaged corners.

    At fixed drum Z, C=x_drum-x_cone-(z_drum-z_cone)*u_x/u_z.
    Origin translations and shortest-transport rotations are the SAME Raise
    source already supplied to the contact engine. No extra bearing coupon
    is added. The Cartesian/Euler/eccentricity-box outer may be unattainable;
    exceeding this envelope is not a physical no-solution certificate.
    """
    import cone_line
    import cone_shaft_land_bands as lands
    import dt_cone_gear_spec as cone
    import dt_cylinder_gear_spec as drum
    if not math.isfinite(booked) or booked<0:
        raise SourceDomainUnknown("booked total opening is not finite/nonnegative")
    nominal = nominal_placement_record(teeth)
    c,s = cone_line.COS_I,cone_line.SIN_I
    incline = math.atan2(s,c)
    rotations = pose["shortest_transport_euler_intervals_rad"]
    angle = math.fsum(max(abs(lo),abs(hi)) for lo,hi in rotations)
    if abs(incline)+angle>=math.pi/2:
        raise SourceDomainUnknown("operating shaft source permits a horizontal-section axis singularity")
    guard = 128*math.ulp(1.0)*(1+abs(incline)+angle)
    slope = (math.nextafter(math.tan(incline-angle)-guard,-math.inf),
             math.nextafter(math.tan(incline+angle)+guard,math.inf))
    driver_x = (c+s*slope[0]-guard,c+s*slope[1]+guard)
    driver_z_values = (s-c*slope[0],s-c*slope[1])
    driver_z = (min(driver_z_values)-guard,max(driver_z_values)+guard)
    negate = lambda interval:(-interval[1],-interval[0])
    translations = pose["translation_intervals_mm"]
    z_reference = nominal["driven_origin_mm"][2]-nominal["driver_origin_mm"][2]
    slope_change = (slope[0]-s/c-guard,slope[1]-s/c+guard)
    terms = {
        "driver_whole_support_local_x":negate(_interval_product(driver_x,translations[0])),
        "driver_whole_support_local_z":negate(_interval_product(driver_z,translations[2])),
        "driver_material_axial_stack":negate(_interval_product(driver_z,axial)),
        "driven_bank_axial_stack":negate(_interval_product(slope,drum_axial)),
        "driven_full_bore_pivot_x":(-pivot_radial,pivot_radial),
        "driven_full_bore_pivot_z":negate(_interval_product(slope,(-pivot_axial,pivot_axial))),
        "driver_axis_transport_at_reference_z":negate(_interval_product(slope_change,(z_reference,z_reference))),
    }
    # The solver's Cartesian eccentricity boxes enclose the physical disks.
    # Pay that SAME conservative box here, not an invented own-tooth grade.
    eccentricity_projection = math.nextafter(
        math.sqrt(2)*math.hypot(1,max(abs(value) for value in slope))+guard,math.inf)
    for body,disk in disks.items():
        radius = math.nextafter(disk["radius_mm"]*eccentricity_projection,math.inf)
        terms[f"{body}_body_eccentricity"] = (-radius,radius)
    derived = _interval_sum(terms.values())
    closing,opening = max(0.0,-derived[0]),max(0.0,derived[1])
    opening_remainder = max(0.0,booked-opening)
    if opening_remainder>0:
        opening_remainder = math.nextafter(opening_remainder,math.inf)
    legacy_terms = {
        "global_cone_gear_bore_land":(cone.BORE_DIA_BAND[0]-lands.GEAR_SEAT_BAND[1])/2,
        "drum_running_bore":drum.BORE_DIAMETRAL_CLEARANCE_MM[1]/2,
    }
    legacy_close = math.fsum(legacy_terms.values())
    closing_remainder = max(0.0,legacy_close-closing)
    if closing_remainder>0:
        closing_remainder = math.nextafter(closing_remainder,math.inf)
    remainder = (-closing_remainder,opening_remainder)
    completed = _interval_sum((derived,remainder))
    known_radial = math.fsum(
        disk["source_terms_mm"]["gear_bore_radial_clearance_upper"] for disk in disks.values())
    return {
        "reference":"actual horizontal section at source drum-face-centre Z",
        "source_class":"whole operating source Cartesian OUTER; no full-P1 trajectory or attainable-corner claim",
        "directed_source_terms_mm":{name:list(value) for name,value in terms.items()},
        "driver_support_projection_ledgers_mm":pose["source_projection_ledgers_mm"],
        "physical_body_eccentricity_source":disks,
        "axis_slope_interval":list(slope),
        "derived_closing_total":closing,"derived_opening_total":opening,
        "booked_closing_total":legacy_close,"booked_closing_source_terms_mm":legacy_terms,
        "required_closing_total":max(legacy_close,closing),
        "booked_total":booked,"derived_total":opening,"selected_total":max(booked,opening),
        "positive_opening_axis":opening_remainder,
        "negative_closing_axis":closing_remainder,
        "booked_centre_radial_remainder_mm":list(remainder),
        "actual_source_plus_remainder_enclosure_mm":list(completed),
        "remainder_coordinate":"existing driven_dx_mm, together with the retained full-bore pivot; no second independent coupon axis",
        "radial_booking_scope":"directed centre OUTER composed from the same source coordinates; no physical attainment or radial inclusion inferred from a Cartesian bound",
        "known_bore_radial_total_before_other_sources":known_radial,
        "closing_book_remainder_before_other_sources":max(0.0,legacy_close-known_radial),
        "closing_remainder_is_tolerance_grant":False,
        "post_running_fit_added_again":False,
        "rule":"retain actual source coordinates and correlations once; one directed radial remainder supplements ONLY positive shortfalls of each retained TOTAL book; max(book,derived), never clip physical source or grant a negative coupon",
    }



def continuous_source_domain(teeth: int, *, installed_axis_acceptance=None) -> dict:
    """Retain every source band; interval boxes are not attainable corners.

    Nonrigid finite-face limits remain explicit. A receiver must cover those
    cap motions, not silently reinterpret them as a rigid axial shift. The
    observer's closed radial/axial condition is retained in its authority
    record; a Cartesian OUTER does not implicitly encode that correlation.
    """
    import _config
    import cone_stack_end_play as endplay
    import cylinder_bank_layout as bank
    import dt_cone_gear_stack as stack
    import dt_cone_gear_spec as cone
    import dt_cylinder_gear_spec as drum
    import dt_cone_support_pose as support
    import cone_shaft_land_bands as lands
    from gear_seat_fit import connected_home_clock_angle_bound_rad

    disks = source_eccentricity_disks(teeth)
    installed = installed_axis_acceptance_from_record(installed_axis_acceptance)
    station, frame = _station_and_frame(teeth)
    pose = support.cone_axis_local_pose_enclosure(station, frame, installed=installed)
    j = (120 - teeth) // 6
    south, north = stack.face_band(j, "south"), stack.face_band(j, "north")
    axial = (min(south[1], north[1]), max(south[0], north[0]) + endplay.CONE_FLOAT_NORTH)
    bank_high, bank_low = bank.partial_stack_band(bank.COUNT - 1 - j)
    drum_axial = (-bank_high - bank.BANK_END_PLAY[1] - drum.FACE_WIDTH_TOLERANCE_MM / 2,
                  -bank_low + drum.FACE_WIDTH_TOLERANCE_MM / 2)
    minimum_bore_span = drum.OVERALL_THICKNESS + min(drum.OVERALL_THICKNESS_BAND)
    cock = math.atan(drum.BORE_DIAMETRAL_CLEARANCE_MM[1] / minimum_bore_span)
    pivot_reach = (drum.OVERALL_THICKNESS + max(drum.OVERALL_THICKNESS_BAND)
                   - (drum.FACE_WIDTH - drum.FACE_WIDTH_TOLERANCE_MM) / 2)
    pivot_radial = pivot_reach * math.sin(cock)
    pivot_axial = pivot_reach * (1 - math.cos(cock))

    section = cone.land_section(teeth)
    shaft_dia = lands.land_finished_dia_limits_mm(cone.bore_dia_mm(teeth), section)
    shaft_af = lands.land_finished_af_limits_mm(section)
    bore_af_nominal = round(cone.bore_flat_af_mm(teeth), cone.BORE_AF_PLACES)
    bore_af = (bore_af_nominal + cone.BORE_AF_BAND[1], bore_af_nominal + cone.BORE_AF_BAND[0])
    if section == len(lands.SECTION_DIA_BANDS) - 1:
        edge = lands.TERMINAL_FLAT_EDGE_BREAK_MAX
    else:
        edge_row = _config.title_block("edge_break")
        edge = max(float(edge_row["radius_mm"]), float(edge_row["chamfer_max_mm"]))
    free_clock = connected_home_clock_angle_bound_rad(shaft_dia, shaft_af, bore_af, edge_break_mm=edge)
    clock = math.nextafter(free_clock + math.radians(cone.FLAT_CLOCK_TOLERANCE_DEG), math.inf)

    booked = float(_config.fit("cone_drum_oblique_mesh", "centre_opening_mm"))
    pattern_clock_deg = drum_tooth_to_cam_notch_clock_deg()
    pattern_clock_rad = math.nextafter(math.radians(pattern_clock_deg),math.inf)
    centre_ledger = _centre_source_ledger(teeth,pose,disks,axial,drum_axial,
        pivot_radial,pivot_axial,booked)
    closing_remainder = centre_ledger["negative_closing_axis"]
    opening_remainder = centre_ledger["positive_opening_axis"]
    translations = pose["translation_intervals_mm"]
    rotations = pose["shortest_transport_euler_intervals_rad"]
    axes = [
        ("driver_dx_mm", translations[0]), ("driver_dy_mm", translations[1]),
        ("driver_dz_mm", (translations[2][0] + axial[0], translations[2][1] + axial[1])),
        ("driver_rx_rad", rotations[0]), ("driver_ry_rad", rotations[1]), ("driver_rz_rad", rotations[2]),
        ("driver_clock_rad", (-clock, clock)),
        ("driven_dx_mm", (math.nextafter(-pivot_radial-closing_remainder,-math.inf),
                          math.nextafter(opening_remainder+pivot_radial,math.inf))),
        ("driven_dy_mm", (-pivot_radial, pivot_radial)),
        ("driven_dz_mm", (drum_axial[0] - pivot_axial, drum_axial[1] + pivot_axial)),
        ("driven_rx_rad", (-cock, cock)), ("driven_ry_rad", (-cock, cock)),
        ("driven_rz_rad", (-cock, cock)),
        ("driven_clock_rad", (-pattern_clock_rad, pattern_clock_rad)),
    ]
    for body, disk in disks.items():
        radius = disk["radius_mm"]
        axes.extend(((f"{body}_ecc_x_mm", (-radius, radius)), (f"{body}_ecc_y_mm", (-radius, radius))))
    datum = manufactured_datum_mapping(teeth)
    return {
        "scope": "FULL_PRODUCTION_SOURCE_DOMAIN" if installed is None else "DESIGN_CONDITIONAL_SOURCE_DOMAIN",
        "production_source_domain": installed is None,
        "correlated_pose_parameters": [[name, list(interval)] for name, interval in axes],
        "source_eccentricity_disks": disks,
        "mechanical_zero_rad": datum["mechanical_zero_rad"],
        "manufactured_datum_mapping": datum,
        "root_air_requirements_mm": {"driver": cone.ROOT_AIR_MIN_MM, "driven": cone.DRUM_ROOT_AIR_MIN_MM},
        "finite_face_width_limits_mm": {
            "driver": [cone.FACE_WIDTH + cone.FACE_WIDTH_BAND[1], cone.FACE_WIDTH + cone.FACE_WIDTH_BAND[0]],
            "driven": [drum.FACE_WIDTH - drum.FACE_WIDTH_TOLERANCE_MM, drum.FACE_WIDTH + drum.FACE_WIDTH_TOLERANCE_MM],
        },
        "finite_face_anchor_fraction": {"driver":0.5,"driven":0.5},
        "support_authority": pose,
        "installed_axis_acceptance": asdict(installed) if installed is not None else None,
        "centre_opening_source_mm": centre_ledger,
        "material_axial_source_mm": {"driver": list(axial), "driven": list(drum_axial)},
        "clock_source_rad": {"driver_free_outer": free_clock,
                             "driver_index_half_width": math.radians(cone.FLAT_CLOCK_TOLERANCE_DEG),
                             "driven_tooth_to_cam_notch_half_width": pattern_clock_rad},
        "driven_pattern_clock_source": {
            "fit_key":"cone_drum_oblique_mesh.drum_tooth_to_cam_notch_clock_deg",
            "half_width_deg":pattern_clock_deg,
            "definition":"material beta_star = physical beta_absolute + driven_clock_rad",
            "physical_angle":"beta_absolute = beta_star - driven_clock_rad; no datum tare",
            "whole_body_setup":"independent recorded NOTCH-up operation, not an additional pattern-clock coupon",
        },
        "qualification_scope": "whole retained source OUTER; refusal is not physical infeasibility; no observed stock pass",
    }


def nominal_source_subdomain(placement: dict, physical_domain: dict) -> dict:
    """An explicit mathematical q=0 comparison, NEVER a production fit grade."""
    from copy import deepcopy
    domain = deepcopy(physical_domain)
    domain["physical_parent_domain"] = physical_domain
    domain["scope"] = "DESIGN_NOMINAL_SUBDOMAIN"
    domain["production_source_domain"] = False
    domain["correlated_pose_parameters"] = [
        [name,[0.0,0.0]] for name,_ in physical_domain["correlated_pose_parameters"]]
    domain["source_eccentricity_disks"] = {
        body:{"shape":"closed_disk","centre_mm":[0.0,0.0],"radius_mm":0.0,
              "source_terms_mm":{"nominal_subdomain_radius_upper_mm":0.0}}
        for body in ("driver","driven")}
    domain["finite_face_width_limits_mm"] = {
        body:[width,width] for body,width in (
            ("driver",placement["driver_face_mm"][1]-placement["driver_face_mm"][0]),
            ("driven",placement["driven_face_mm"][1]-placement["driven_face_mm"][0]))}
    return domain


def budget_clock_subdomain(physical_domain: dict) -> dict:
    """Hold the three independently booked driver/drum pattern-clock terms."""
    from copy import deepcopy
    domain = deepcopy(physical_domain)
    domain["physical_parent_domain"] = physical_domain
    domain["scope"] = "BUDGET_CLOCK_NOMINAL_SUBDOMAIN"
    domain["production_source_domain"] = False
    domain["correlated_pose_parameters"] = [
        [name,[0.0,0.0] if name in ("driver_clock_rad","driven_clock_rad") else list(limits)]
        for name,limits in physical_domain["correlated_pose_parameters"]]
    domain["oblique_phase_bound_excluded_terms"] = list(BUDGET_CLOCK_EXCLUDED_TERMS)
    return domain
