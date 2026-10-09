"""Actual-stock crossed-crank qualification, consumed without a solver import.

Dimensional grades live in crank_mesh_geometry. The frozen design payload
must qualify every retained corner before native assembly or drawing callers
publish a phase, backlash, STOCK-FORM COVERAGE or row figure. Former ideal-N
nine-phase slopes and Tredgold contact-ratio equations are intentionally gone.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from pathlib import Path

import _config
from crank_mesh_calibration import CALIBRATION,require_current_packet_bytes
import crank_mesh_geometry as geometry
import stock_form_contact_certificate as contact_certificate
from crank_mesh_requirements import (
    HANDOVER_JUMP_MAX_MM,POSITIVE_BACKLASH_MIN_MM,
    ROW_ENGAGEMENT_MIN,STOCK_FORM_COVERAGE_MIN,
)

# Physical dimensional receivers remain pure and are independent of whether
# the chosen stock-form tooth system qualifies at the current fixed centre.
R64 = geometry.R64
R16 = geometry.R16
FRAME_C2C = geometry.FRAME_C2C
FRAME_DY = geometry.FRAME_DY
FRAME_DX = geometry.FRAME_DX
DC_PER_DY = geometry.DC_PER_DY
DC_PER_DX = geometry.DC_PER_DX
GEAR64_POST_OFFSET = geometry.GEAR64_POST_OFFSET
CRANK_BEARING_LENGTH = geometry.CRANK_BEARING_LENGTH
CRANK_SUPPORT_NORTH_MIN = geometry.CRANK_SUPPORT_NORTH_MIN
PINION_HALF_FACE_MAX = geometry.PINION_HALF_FACE_MAX
CRANK_OVERHANG = geometry.CRANK_OVERHANG
CONE_OVERHANG = geometry.CONE_OVERHANG
MESH_LEVER = geometry.MESH_LEVER
POST_ANGLE_DEG = geometry.POST_ANGLE_DEG
TOOTH_RUNOUT_TIR_MM = geometry.TOOTH_RUNOUT_TIR_MM
TIP_ROOT_BAND_RADIAL = geometry.TIP_ROOT_BAND_RADIAL
SPACING_PRINTED = geometry.SPACING_PRINTED
GEAR64_TOOTH_THICKNESS_DEVIATIONS = geometry.gear64.TOOTH_THICKNESS_DEVIATIONS
TIP_DIA_LOW_16 = geometry.pinion.OUTSIDE_DIA-geometry.pinion.OUTSIDE_DIA_TOLERANCE_MM
TIP_DIA_LOW_64 = geometry.gear64.OUTSIDE_DIA-geometry.gear64.OUTSIDE_DIA_TOLERANCE_MM
CALIBRATION_CASES = CALIBRATION["cases"]


def required_calibration_case_names() -> frozenset[str]:
    return geometry.required_calibration_case_names()





def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def _require_source_identity(payload,parameters,profiles):
    sources = payload["measurement_engine_sources_sha256"]
    expected = {"crank_mesh_backlash_study.py","crossed_mesh_study.py","stock_form_contact_3d.py",
                "stock_form_root_angles.py","stock_form_root_sweep.py","stock_form_contact_continuation.py"}
    def sha(value):
        return isinstance(value,str) and len(value) == 64 and all(v in "0123456789abcdef" for v in value)
    if (not isinstance(sources,dict) or sources.keys() != expected or not all(map(sha,sources.values()))
            or payload["measurement_engine_sha256"] != _digest(sources)):
        raise ValueError("actual crank qualification lacks its exact SIX-source measurement manifest")
    receipt = payload["source_identity"]
    before,compiled,parsed,after = (receipt[name] for name in
                                   ("before_sha256","compiled_sha256","parsed_sha256","after_sha256"))
    if (receipt["source_bytes_stable"] is not True or not compiled or not parsed
            or before != after or compiled != receipt["actual_compiled_sha256"]
            or before.keys() != compiled.keys() | parsed.keys()
            or any(not sha(value) or before.get(path) != value
                   for path,value in (*compiled.items(),*parsed.items()))):
        raise ValueError("crank observations are not authentic stable BEFORE/compiled/parsed/AFTER source")
    relative = {}
    root = Path(__file__).resolve().parent
    for path,value in compiled.items():
        marker = "/cad/scripts/"
        normalized = path.replace("\\","/")
        if marker not in normalized:
            raise ValueError("compiled physical source is outside the actual project script scope")
        name = normalized.split(marker,1)[1]
        if not name or ".." in Path(name).parts or name in relative:
            raise ValueError("ambiguous compiled crank source identity")
        relative[name] = value
        # Native readers never import/read diagnostic solvers. Their exact
        # captured bytes remain the separate authenticated measuring manifest.
        if not name.startswith("diagnostics/"):
            try:
                current = hashlib.sha256((root/name).read_bytes()).hexdigest()
            except OSError as exc:
                raise ValueError(f"actual physical source unavailable: {name}") from exc
            if current != value:
                raise ValueError(f"actual compiled physical source changed: {name}")
    if any(relative.get(f"diagnostics/{name}") != value for name,value in sources.items()):
        raise ValueError("six-source manifest is not the actual compiled measuring implementation")
    if not {"stock_form_cutter.py","crank_mesh_geometry.py"} <= relative.keys():
        raise ValueError("actual compiled physical cutter/geometry sources are missing")
    descriptor = receipt["consumed_input"]
    if (_digest(descriptor) != receipt["consumed_input_sha256"]
            or payload["consumed_input_sha256"] != receipt["consumed_input_sha256"]
            or descriptor["pure_current_geometry_sha256"] != payload["geometry_sha256"]
            or descriptor["design_centre_shift_mm"] != 0 or descriptor["conditional_source_assumptions"]
            or descriptor["requested_cases"] is not None
            or not contact_certificate.same_numeric_tree(descriptor["parameters"],parameters)
            or not contact_certificate.same_numeric_tree(descriptor["nominal_reference_domain"],
                geometry.nominal_reference_domain(parameters["nominal"]["continuous_source_domain"],parameters["nominal"]["pose"]))
            or descriptor["actual_selected_read_driver_phases_rad"] != [4*math.pi*index for index in range(21)]
            or not contact_certificate.same_numeric_tree(descriptor["cases"],profiles)):
        raise ValueError("actual consumed source/grades/conditional scope do not match the production geometry")


def _case_phase_component(case,driver,driven):
    ratio = contact_certificate._bound_divide((driver.teeth,)*2,(driven.teeth,)*2)
    lower,upper = -math.inf,math.inf
    for row in case["full_period_cells"]:
        sides = row["side_branch_envelopes"]
        low = max(value["signed_running_te_interval_rad"][1] for value in sides["lower"])
        high = min(value["signed_running_te_interval_rad"][0] for value in sides["upper"])
        lower = max(lower,contact_certificate._bound_divide((-high,)*2,ratio)[1])
        upper = min(upper,contact_certificate._bound_divide((-low,)*2,ratio)[0])
    return [lower,upper] if lower < upper else None


def _qualified_payload(payload: dict | None = None) -> dict:
    """Admit complete actual physical branch/material/source transport only."""
    payload = require_current_packet_bytes() if payload is None else payload
    if payload["qualified"] is not True:
        raise ValueError(payload["refusal"])
    if (payload["family"] != "dt_crank_stock_form" or type(payload["schema_version"]) is not int
            or payload["schema_version"] != 1 or payload["native_certificate"] is not False
            or payload["geometry_sha256"] != geometry.geometry_sha256()
            or payload["design_centre_shift_mm"] != 0
            or payload["production_source_domain_proved"] is not True):
        raise ValueError("actual crank calibration is stale, conditional or lacks its production source identity")
    phase = payload["phase_qualification"]
    selected = payload["phase_seed_deg"]
    configured = _config.machine("gear_train","crank_mesh_phase_offset_deg")
    if (any(type(value) not in (float,int) or not math.isfinite(value)
            for value in (selected,configured,phase["CERTIFIED_PHASE_OFFSET_DEG"]))
            or not configured == selected == phase["CERTIFIED_PHASE_OFFSET_DEG"]
            or phase["qualified"] is not True or phase["CONE_SHAFT_SENSE"] != -1
            or phase["scope"] != "actual signed running cone-shaft radians; all profiles and the whole continuous physical source/joint period"
            or phase["alignment_zero_subtracted"] is not False
            or phase["geometry_sha256"] != payload["geometry_sha256"]
            or phase["measurement_engine_sha256"] != payload["measurement_engine_sha256"]):
        raise ValueError("configured, packet and certified actual crank phase are not exactly the same finite datum")
    cases = payload["cases"]
    parameters = {row["name"]:row for row in geometry.calibration_case_parameters()}
    if (cases.keys() != parameters.keys() or set(payload["required_case_names"]) != parameters.keys()
            or len(payload["required_case_names"]) != len(parameters)
            or payload["selected_phase_transports"].keys() != parameters.keys()
            or payload["selected_read_cases"].keys() != parameters.keys()):
        raise ValueError("actual crank proof omits a physical profile corner or selected read/transport")
    drivers = dict(geometry.pinion.STOCK_PROFILE_CORNERS,nominal=geometry.pinion.STOCK_PROFILE)
    driven = dict(geometry.gear64.STOCK_PROFILE_CORNERS,nominal=geometry.gear64.STOCK_PROFILE)
    def profile(value):
        return {"teeth":value.teeth,"reference_teeth":value.template.reference_teeth,
                "dp":value.template.diametral_pitch,"pa_deg":value.template.pressure_angle_deg,
                "blank_radius_mm":value.blank_radius_mm,"radial_translation_mm":value.radial_translation_mm,
                "helix_angle_deg":value.helix_angle_deg}
    descriptors = {}
    selected_lags,read_rows = {},{}
    common = [-geometry.pinion.STOCK_PROFILE.angular_pitch_rad/2,geometry.pinion.STOCK_PROFILE.angular_pitch_rad/2]
    for name,case in cases.items():
        source = parameters[name]
        domain = source["continuous_source_domain"]
        driver,mate = drivers[source["driver_profile_label"]],driven[source["driven_profile_label"]]
        placement = geometry.placement_record(source["pose"])
        descriptors[name] = {"placement":placement,"driver_profile":profile(driver),"driven_profile":profile(mate)}
        if (domain.get("scope") != "FULL_PRODUCTION_SOURCE_DOMAIN" or domain.get("production_source_domain") is not True
                or domain.get("unbound_sources") or domain.get("source_domain_status") == "UNKNOWN"):
            raise ValueError(f"{name}: actual production source has an unbound or conditional manufactured grade")
        if (not contact_certificate.finite_evidence(case)
                or not contact_certificate.same_numeric_tree(case["continuous_source_domain"],domain)
                or any(not contact_certificate.same_numeric_tree(case[field],value)
                       for field,value in descriptors[name].items())
                or case["qualified"] is not True or case["source_domain_proved"] is not True
                or case["production_source_qualified"] is not True
                or case["metric"] != "STOCK-FORM COVERAGE" or case["is_conjugate"] is not False
                or case["native_certificate"] is not False or case["operating_driver_sense"] != 1
                or case["uncovered_phase_rad"] != 0 or case["continuous_carrying_contact"] is not True):
            raise ValueError(f"{name}: finite common-source physical manufacturing evidence is incomplete or mislabelled")
        contact_certificate.require_continuous_certificate(
            case,domain,driver,mate,case["continuous_contact_certificate"],
            coverage_floor=STOCK_FORM_COVERAGE_MIN,row_floor=ROW_ENGAGEMENT_MIN,handover_max_mm=HANDOVER_JUMP_MAX_MM)
        contact_certificate.require_whole_period_envelope(case,domain,driver,mate)
        running = case["continuous_contact_certificate"]["sides"]["upper"]
        if any(not contact_certificate.same_numeric_tree(case[field],running[field])
               for field in ("handovers","periodic_seam")):
            raise ValueError(f"{name}: published carrying/handover summary differs from its actual operating proof")
        rows = case["full_period_cells"]
        tight = min(row["correlated_backlash_interval_mm"][0] for row in rows)
        loose = max(row["correlated_backlash_interval_mm"][1] for row in rows)
        if (case["tight_backlash_lower_mm"] != tight or case["loose_backlash_upper_mm"] != loose
                or tight <= POSITIVE_BACKLASH_MIN_MM):
            raise ValueError(f"{name}: full-source first-contact backlash is not strictly positive")
        component = _case_phase_component(case,driver,mate)
        if (component is None or not contact_certificate.same_numeric_tree(case["phase_components_rad"],[component])
                or not contact_certificate.same_numeric_tree(case["phase_window_rad"],component)):
            raise ValueError(f"{name}: physical phase window is not the actual complete source envelope")
        common = [max(common[0],component[0]),min(common[1],component[1])]
        selected_placement = geometry.placement_record(source["pose"],selected_phase_offset_deg=selected)
        transport = payload["selected_phase_transports"][name]
        selected_lags[name] = contact_certificate.require_selected_driver_clock_transport(
            case,domain,driver,mate,transport,selected_placement=selected_placement,
            selected_phase_offset_deg=selected,base_geometry_sha256=payload["geometry_sha256"],
            measurement_engine_sha256=payload["measurement_engine_sha256"])
        delta = transport["effective_driver_material_delta_rad"]
        if not component[0] < delta[0] <= delta[1] < component[1]:
            raise ValueError(f"{name}: actual native material-clock delta leaves the qualified source phase window")
        reads = payload["selected_read_cases"][name]
        if (reads["proof_schema"] != "finite-stock-actual-read-points/1"
                or reads["point_source_domain_proved"] is not True or reads["native_certificate"] is not False
                or reads["production_source_qualified"] is not False
                or reads["operating_driver_sense"] != 1
                or not contact_certificate.same_numeric_tree(reads["placement"],selected_placement)
                or not contact_certificate.same_numeric_tree(reads["continuous_source_domain"],domain)
                or not contact_certificate.same_numeric_tree(reads["driver_profile"],profile(driver))
                or not contact_certificate.same_numeric_tree(reads["driven_profile"],profile(mate))
                or not contact_certificate.same_numeric_tree(reads["numerical_error_bounds"],case["numerical_error_bounds"])
                or len(reads["actual_read_phases"]) != 21):
            raise ValueError(f"{name}: selected datum lacks fresh actual full-source 21-point material queries")
        read_rows[name] = reads["actual_read_phases"]
        for index,row in enumerate(read_rows[name]):
            contact_certificate.require_actual_read_phase(
                reads,domain,driver,mate,row,expected_phase_rad=4*math.pi*index)
            if row["correlated_backlash_interval_mm"][0] <= POSITIVE_BACKLASH_MIN_MM:
                raise ValueError(f"{name}: actual selected read has no strictly positive source backlash")
    if (not common[0] < common[1]
            or not contact_certificate.same_numeric_tree(payload["phase_components_rad"],[common])
            or not contact_certificate.same_numeric_tree(payload["phase_window_rad"],common)):
        raise ValueError("common crank phase window is not the complete actual corner intersection")
    _require_source_identity(payload,parameters,descriptors)
    lag = [min(value[0] for value in selected_lags.values()),max(value[1] for value in selected_lags.values())]
    if not contact_certificate.same_numeric_tree(phase["CONE_SHAFT_LAG_INTERVAL_RAD"],lag):
        raise ValueError("crank whole-period lag interval omits actual source/profile/selected-clock payment")
    source = parameters["nominal"]
    nominal_domain = geometry.nominal_reference_domain(source["continuous_source_domain"],source["pose"])
    reference_packet = payload["nominal_reference_read_case"]
    nominal_driver,nominal_driven = drivers["nominal"],driven["nominal"]
    if (reference_packet["proof_schema"] != "finite-stock-actual-read-points/1"
            or reference_packet["point_source_domain_proved"] is not True
            or reference_packet["production_source_qualified"] is not False
            or reference_packet["native_certificate"] is not False or reference_packet["operating_driver_sense"] != 1
            or not contact_certificate.same_numeric_tree(reference_packet["continuous_source_domain"],nominal_domain)
            or not contact_certificate.same_numeric_tree(reference_packet["placement"],
                geometry.placement_record(source["pose"],selected_phase_offset_deg=selected))
            or not contact_certificate.same_numeric_tree(reference_packet["driver_profile"],profile(nominal_driver))
            or not contact_certificate.same_numeric_tree(reference_packet["driven_profile"],profile(nominal_driven))
            or not contact_certificate.same_numeric_tree(reference_packet["numerical_error_bounds"],cases["nominal"]["numerical_error_bounds"])
            or len(reference_packet["actual_read_phases"]) != 21):
        raise ValueError("21 nominal references are not fresh actual declared nominal face/band/profile/source point queries")
    nominal = reference_packet["actual_read_phases"]
    for index,row in enumerate(nominal):
        contact_certificate.require_actual_read_phase(
            reference_packet,nominal_domain,nominal_driver,nominal_driven,row,expected_phase_rad=4*math.pi*index)
    expected_fields = {
        "STALL_DRIVER_RAD":[row["actual_driver_phase_rad"] for row in nominal],
        "CONE_SHAFT_LAG_RAD":[row["reference_signed_running_te_rad"] for row in nominal],
        "BOUND_RAD":[],
    }
    for index,reference in enumerate(nominal):
        actual = (min(rows[index]["signed_running_te_interval_rad"][0] for rows in read_rows.values()),
                  max(rows[index]["signed_running_te_interval_rad"][1] for rows in read_rows.values()))
        difference = contact_certificate._bound_subtract(actual,(reference["reference_signed_running_te_rad"],)*2)
        expected_fields["BOUND_RAD"].append(max(abs(value) for value in difference))
    if any(not contact_certificate.same_numeric_tree(phase[field],value) for field,value in expected_fields.items()):
        raise ValueError("crank 21 signed readings/bounds are not the actual selected point roots and full-source envelopes")
    return payload


def require_qualified(payload: dict | None = None) -> dict:
    """Validate complete source-bound evidence or raise a deliberate refusal."""
    try:
        return _qualified_payload(payload)
    except (KeyError,TypeError,IndexError,AttributeError,ArithmeticError) as exc:
        raise ValueError(f"incomplete actual3D stock-form calibration payload: {exc}") from exc


def require_selected_pin_clocking() -> float:
    """Refuse native publication until the physical measured phase is selected."""
    phase = _config.machine("gear_train").get("crank_mesh_phase_offset_deg")
    if phase is None:
        raise RuntimeError(
            "UNQUALIFIED crank phase: select the actual stock-form physical phase "
            "before publishing the crankshaft retention hole"
        )
    if type(phase) not in (int, float) or not math.isfinite(phase):
        raise ValueError("selected crank mesh phase must be finite")
    # A numeric config edit alone may never publish a retention hole.
    measured = require_qualified()["phase_seed_deg"]
    if not math.isclose(phase, measured, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError("crankshaft retention clock is stale relative to the qualified physical phase")
    clock = geometry.pinion._PINION_DATUM_CLOCK_DEG + phase
    if not 0.0 <= clock < 360.0 / geometry.pinion.TEETH:
        raise ValueError("pinion retention-hole clocking must lie within one physical tooth pitch")
    return clock


@dataclass(frozen=True)
class RowQualification:
    case_name: str
    driver_face_mm: tuple[float,float]
    driver_shoulder_z_mm: float
    driver_turned_radius_mm: float
    driven_face_mm: tuple[float,float]
    driver_origin_mm: tuple[float,float,float]
    driven_origin_mm: tuple[float,float,float]
    driver_frame: tuple[tuple[float,float,float],...]
    driven_frame: tuple[tuple[float,float,float],...]
    supported_driven_station_intervals_mm: tuple[tuple[float,float],...]
    row_fraction_lower: float
    coverage_lower: float
    continuous_carrier: bool


def row_qualification(case_name: str) -> RowQualification:
    """Read a measured physical row case; never interpolate an unstudied pose."""
    payload = require_qualified()
    try:
        case = payload["cases"][case_name]
    except KeyError as exc:
        raise ValueError(f"no actual3D row qualification for {case_name!r}") from exc
    pose = case["placement"]
    return RowQualification(
        case_name,tuple(pose["driver_face_mm"]),pose["driver_shoulder_z_mm"],
        pose["driver_turned_radius_mm"],tuple(pose["driven_face_mm"]),
        tuple(pose["driver_origin_mm"]),tuple(pose["driven_origin_mm"]),
        tuple(tuple(row) for row in pose["driver_frame"]),
        tuple(tuple(row) for row in pose["driven_frame"]),
        tuple(tuple(interval) for interval in case["row_available_intervals_mm"]),
        case["row_available_fraction_lower"],case["stock_form_coverage_lower"],
        case["continuous_carrying_contact"],
    )


# None means unavailable, never zero. Callers must require_qualified() before
# using these manufacturing values; a refused design cannot silently build.
if CALIBRATION["qualified"]:
    require_qualified()
    NOMINAL_TIGHT_BACKLASH_MM = CALIBRATION_CASES["nominal"]["tight_backlash_lower_mm"]
    TIGHT_BACKLASH_MM = min(case["tight_backlash_lower_mm"] for case in CALIBRATION_CASES.values())
    STOCK_FORM_COVERAGE_NOMINAL = CALIBRATION_CASES["nominal"]["stock_form_coverage_lower"]
    STOCK_FORM_COVERAGE_WORST = min(case["stock_form_coverage_lower"] for case in CALIBRATION_CASES.values())
    ROW_ENGAGEMENT_FRACTION_WORST = min(case["row_available_fraction_lower"] for case in CALIBRATION_CASES.values())
    CONTINUOUS_CARRYING_CONTACT = True
    MAX_HANDOVER_JUMP_MM = max(
        receipt["pitch_displacement_jump_upper_mm"]
        for case in CALIBRATION_CASES.values()
        for receipt in (*case["handovers"],case["periodic_seam"]))
    PHASE_WINDOW_RAD = tuple(CALIBRATION["phase_window_rad"])
    MESH_WINDOW_CENTRE_DEG = CALIBRATION["phase_seed_deg"]
else:
    NOMINAL_TIGHT_BACKLASH_MM = None
    TIGHT_BACKLASH_MM = None
    STOCK_FORM_COVERAGE_NOMINAL = None
    STOCK_FORM_COVERAGE_WORST = None
    ROW_ENGAGEMENT_FRACTION_WORST = None
    CONTINUOUS_CARRYING_CONTACT = False
    MAX_HANDOVER_JUMP_MM = None
    PHASE_WINDOW_RAD = None
    MESH_WINDOW_CENTRE_DEG = None


def stack_text() -> str:
    payload = require_qualified()
    return "\n".join((
        f"actual stock-form crossed crank C {FRAME_C2C:.5f} mm",
        f"worst positive backlash {TIGHT_BACKLASH_MM:.6f} mm",
        f"STOCK-FORM COVERAGE {STOCK_FORM_COVERAGE_WORST:.6f}; row {ROW_ENGAGEMENT_FRACTION_WORST:.6f}",
        f"continuous carrying handover <= {MAX_HANDOVER_JUMP_MM:.6f} mm driven pitch displacement",
        f"geometry identity {payload['geometry_sha256']}",
        "offline3D design qualification; native assembly interference gate still required",
    ))
