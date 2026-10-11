r"""Pure-data dimensional contract shared by the feed-pinion sleeve and its drawing.

The transgear pinion sleeve (MHA-PD-010, R9-68): one turned steel sleeve that
runs on the MHA-PD-023 pin's Ø3.9 shank and carries, rear to front, the
independent 12T 32DP PA20 finite stock-form feed pinion and the Ø8.2 h6 boss.
The pinion meshes the purchased standard platen rack. The brass hub
slides on the boss; its rear spigot passes through
the 120T disc's (MHA-PD-006) bore, which pilots on it, and seats its end on the
step face, so the step is the rear stop of hub and disc; the hub drives
through the boss's D-flat, which is drive only (its end wall stands behind
the hub's own flat and never touches it).  The hub's front face is faced to
stand just behind the nose, so the MHA-PD-025 front bushing bears on the nose
and traps hub and disc against the step.  The rear face runs on the MHA-PD-024
rear bushing; both bushings and the hub are faced to fit
(``transgear_cluster_fit``, which reads this module).

Local frame: origin on the axis at the sleeve's REAR face, +Z toward the
machine FRONT.  The teeth occupy z 0..FACE_WIDTH, the boss
FACE_WIDTH..OVERALL_LENGTH; the D-flat (local -Y) runs from the nose back to
its end wall at FLAT_END_STATION.  Datums: ``RearFace`` is the Front Plane
(z 0), ``GearFace`` (the step face) an offset plane, ``Axis1`` the tooth
pattern's Top × Right axis; the sheet's datum A is the bore.

PURE DATA, no SolidWorks/COM imports: ``build_pd_transgear_feed_pinion`` marks and
tolerances exactly ``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION``;
``draw_pd_transgear_feed_pinion`` keeps exactly the same names.  Nothing here
imports ``transgear_cluster_fit``, the hub's spec or a bushing spec (they
import this; the hub's spec owns the hub-to-sleeve fits and the match-drilled
oil hole's location); the hub's spigot comes from the joint's pure-data
``pd_transgear_disc_hub_geometry``.
"""

from __future__ import annotations

import math

import pd_rack_pinion_spec
import pd_transgear_pin_spec
from _fit_deviations import deviations
from _gear_fit_limits import gear_tip_band_mm
from _gear_quality import (
    pinion_pitch_index_deviation_mm,
    pitch_index_measurement_uncertainty_mm,
    require_pitch_index_measurements_mm,
    toothspace_runout_tir_mm,
)
from _gtol_cylinder import CylinderFace
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pd_transgear_disc_hub_geometry import SPIGOT_LENGTH, SPIGOT_LENGTH_BAND
from paper_drive_stock_envelope import (
    cutter_end_section_area_bounds_mm2,
    cutter_end_volume_bounds_mm3,
)
from paper_drive_stock_inspection import toothspace_gauge_contact_mm
from stock_form_cutter import (
    CutterTemplate,
    StockFormProfile,
    translation_for_tangent_span,
)

MM_PER_IN = 25.4

# The part numbers the sheet names.  Hard-coded, not read from ``_config.parts``
# (dt_crank_pinion_spec's precedent: a registry read would make the part rows
# rebuild inputs of every importer); test_pd_transgear_feed_pinion_drawing checks
# them against the registry offline.
SLEEVE_NUMBER = "MHA-PD-010"
PIN_NUMBER = pd_transgear_pin_spec.PIN_NUMBER
HUB_NUMBER = "MHA-PD-017"
DISC_NUMBER = "MHA-PD-006"
RACK_NUMBER = "MHA-PD-005"
if pd_rack_pinion_spec.HUB_NUMBER != HUB_NUMBER:
    raise AssertionError("the disc's fit note names another hub than this sheet")

# --- Independent 12T 32DP PA20 finite stock-form feed pinion -------------------
# Physical tooth count is NOT the reducer pinion count. The ordinary #8
# master is translated rigidly; this is not a generated profile shift x.
TEETH = 12
DIAMETRAL_PITCH = 32.0
PRESSURE_ANGLE_DEG = 20.0
CUTTER_TEMPLATE = CutterTemplate(12, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG)
CUTTER_NUMBER = CUTTER_TEMPLATE.cutter_number
CUTTER_TOOTH_RANGE = CUTTER_TEMPLATE.teeth_range
MODULE_MM = CUTTER_TEMPLATE.module_mm
DEDENDUM_FACTOR = (
    CUTTER_TEMPLATE.pitch_radius_mm - CUTTER_TEMPLATE.root_radius_mm
) / MODULE_MM
PITCH_DIA = TEETH * MODULE_MM
# The #8 form is translated s outward along each gap bisector. At 0.210
# (printed limits 0.19992..0.22002) the rack mesh at the loose 0.14 datum and
# the 11.48 minimum OD has contact ratio 1.245 by the closed form in
# paper_drive_mesh_check (translation treated as the untranslated involute
# with rack and tip moved in by s*cos(pi/N)) and 1.248 by stepping the
# generated flank through mesh (test_paper_drive_mesh_check). Both clear 1.2;
# the interference margin is 0.070 mm. A smaller s raises contact ratio but
# brings the rack crest nearer the pinion's interference point.
RADIAL_SETTING = 0.210
_SPAN_DESIGN_SETTING_BAND = (0.010, -0.010)
OUTSIDE_DIA = 11.50
GEAR_CONTACT_CLASS = "contact_critical"
OUTSIDE_DIA_BAND = gear_tip_band_mm(GEAR_CONTACT_CLASS)
STOCK_PROFILE = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, OUTSIDE_DIA / 2.0, RADIAL_SETTING
)
# A real parallel-tangent span controls the manufactured thickness. The
# provisional ±.010 translation defines the design span; OUTWARD printed
# limits then define the actual accepted translation family used everywhere.
SPAN_TEETH = 2
SPAN_PLACES = 4
SPAN_NOMINAL = STOCK_PROFILE.tangent_span_mm(SPAN_TEETH)
_SPAN_DESIGN_PROFILES = tuple(
    StockFormProfile(
        TEETH, CUTTER_TEMPLATE, (OUTSIDE_DIA + tip) / 2.0, RADIAL_SETTING + setting
    )
    for setting in _SPAN_DESIGN_SETTING_BAND
    for tip in OUTSIDE_DIA_BAND
)
_SPAN_GEOMETRY_ERROR = max(
    profile.geometry_error_bound_mm for profile in _SPAN_DESIGN_PROFILES
)
_SPAN_CORNERS = tuple(
    (
        profile.tangent_span_mm(SPAN_TEETH) - 2.0 * profile.geometry_error_bound_mm,
        profile.tangent_span_mm(SPAN_TEETH) + 2.0 * profile.geometry_error_bound_mm,
    )
    for profile in _SPAN_DESIGN_PROFILES
)
SPAN_LIMITS = (
    math.floor(min(row[0] for row in _SPAN_CORNERS) * 10**SPAN_PLACES)
    / 10**SPAN_PLACES,
    math.ceil(max(row[1] for row in _SPAN_CORNERS) * 10**SPAN_PLACES)
    / 10**SPAN_PLACES,
)
SPAN_BAND = (SPAN_LIMITS[1] - SPAN_NOMINAL, SPAN_LIMITS[0] - SPAN_NOMINAL)
SPAN_DEVIATIONS = deviations(SPAN_BAND)
SPAN_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
SPAN_PREFIX = f"SPAN {SPAN_TEETH} TEETH "
_SPAN_SENSITIVITY = 2.0 * math.sin(math.pi * SPAN_TEETH / TEETH)
_SPAN_ROUNDING_ALLOWANCE = (
    10**-SPAN_PLACES + 4.0 * _SPAN_GEOMETRY_ERROR
) / _SPAN_SENSITIVITY
_SPAN_INVERSE_BOUNDS = (
    RADIAL_SETTING + _SPAN_DESIGN_SETTING_BAND[1] - _SPAN_ROUNDING_ALLOWANCE,
    RADIAL_SETTING + _SPAN_DESIGN_SETTING_BAND[0] + _SPAN_ROUNDING_ALLOWANCE,
)
RADIAL_SETTING_LIMITS = tuple(
    translation_for_tangent_span(
        TEETH,
        CUTTER_TEMPLATE,
        limit + sign * 2.0 * _SPAN_GEOMETRY_ERROR,
        SPAN_TEETH,
        translation_bounds_mm=_SPAN_INVERSE_BOUNDS,
    )
    for limit, sign in zip(SPAN_LIMITS, (-1.0, 1.0), strict=True)
)
RADIAL_SETTING_BAND = (
    RADIAL_SETTING_LIMITS[1] - RADIAL_SETTING,
    RADIAL_SETTING_LIMITS[0] - RADIAL_SETTING,
)


def manufactured_profiles() -> tuple[StockFormProfile, ...]:
    """Actual PRINTED-span-derived translation × accepted tip corners."""
    return tuple(
        StockFormProfile(TEETH, CUTTER_TEMPLATE, (OUTSIDE_DIA + tip) / 2.0, setting)
        for setting in RADIAL_SETTING_LIMITS
        for tip in OUTSIDE_DIA_BAND
    )


_PROFILE_CORNERS = manufactured_profiles()
TOOTH_THICKNESS = STOCK_PROFILE.pitch_tooth_thickness_mm
ROOT_DIA = 2.0 * STOCK_PROFILE.root_radius_min_mm
ROOT_DIA_PLACES = 2
# A native physical lower-limit witness owns the wall floor. Translated root
# arcs are not concentric; deepest ground X is a distinct run-out quantity.
ROOT_DIA_MIN = math.floor(
    min(2.0 * profile.root_radius_min_mm for profile in _PROFILE_CORNERS)
    * 10**ROOT_DIA_PLACES
) / 10**ROOT_DIA_PLACES
ROOT_DEPTH_X_MIN = min(
    profile.root_point(profile.root_half_angle_rad)[0]
    for profile in _PROFILE_CORNERS
)
WHOLE_DEPTH = (OUTSIDE_DIA - ROOT_DIA) / 2.0
ROOT_DIA_TOL_TYPE = 5  # swTolType_e.swTolMIN
TIP_LAND_MIN = min(profile.tip_land_mm for profile in _PROFILE_CORNERS)
FINITE_GROUND_TIP_AIR_MIN = min(
    math.hypot(*profile.flank_point(CUTTER_TEMPLATE.flank_parameter_max))
    - profile.blank_radius_mm
    for profile in _PROFILE_CORNERS
)
# Inspection uses one certified actual-size pin at each space, with the
# mandrel centred in the running bore. A free span does not inspect runout.
TOOTHSPACE_GAUGE_DIA_IN = 1.0 / 16.0
TOOTHSPACE_GAUGE_DIA_MM = TOOTHSPACE_GAUGE_DIA_IN * MM_PER_IN
TOOTH_SPACE_RUNOUT_TIR_MM = toothspace_runout_tir_mm()
if not math.isfinite(TOOTH_SPACE_RUNOUT_TIR_MM) or TOOTH_SPACE_RUNOUT_TIR_MM <= 0.0:
    raise ValueError("feed toothspace inspection requires a positive configured TIR limit")
# The actual rear-face flank edge of the indexed straight stock pass.
TOOTH_SPACE_INSPECTION_PHASE_RAD = math.pi / TEETH
TOOTH_SPACE_INSPECTION_END_MM = 0.0
# Relative angular index is a separate inspection from radial TIR and span
# thickness. Its linear errors refer to the drawn pitch-reference circle,
# not the certified measuring pin's centre radius.
PITCH_INDEX_REFERENCE_RADIUS_MM = PITCH_DIA / 2.0
PITCH_INDEX_DEVIATION_MM = pinion_pitch_index_deviation_mm()
PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM = pitch_index_measurement_uncertainty_mm()
PITCH_INDEX_STATIONS = tuple(range(TEETH + 1))  # station TEETH is the full wrap

for _profile in _PROFILE_CORNERS:
    _profile.require_tip_land(0.25 * MODULE_MM)
    toothspace_gauge_contact_mm(_profile, TOOTHSPACE_GAUGE_DIA_MM)
    _tip_air = (
        math.hypot(*_profile.flank_point(CUTTER_TEMPLATE.flank_parameter_max))
        - _profile.blank_radius_mm
    )
    if _tip_air <= _profile.geometry_error_bound_mm:
        raise AssertionError("finite ground tip/closure reaches the accepted blank")


def require_pitch_index_errors_mm(measured_index_errors_mm: dict[int, float]) -> float:
    """Receive every calibrated space index, including the full-circle wrap.

    At station i the error is R_ref * (observed_angle_i - datum_angle -
    2*pi*i/TEETH). Angles are unwrapped, actual-pin/contact corrected, and
    measured about the actual running bore A against one physical index
    datum; a floating best-fit tooth axis must not remove eccentricity.
    This relative-index receiving control does not replace radial TIR,
    tooth-span thickness, or the separately controlled absolute drive clock.
    The returned range includes both stations' calibration uncertainty.
    """
    return require_pitch_index_measurements_mm(
        measured_index_errors_mm=measured_index_errors_mm,
        required_stations=PITCH_INDEX_STATIONS,
        relative_deviation_limit_mm=PITCH_INDEX_DEVIATION_MM,
        absolute_measurement_uncertainty_mm=PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM,
    )



# This band is a named tooth-centred rack-normal DATUM setup, not all-phase
# running backlash. Invert the actual translated-profile normal-contact law:
# b=2(H-r)tan(a)-2s*sin(a+pi/N)/cos(a).
RACK_BACKLASH = 0.13
RACK_BACKLASH_RANGE = (0.12, 0.14)
_PA = math.radians(PRESSURE_ANGLE_DEG)
RACK_MESH_EXTENSION = (
    RACK_BACKLASH
    + 2.0 * RADIAL_SETTING * math.sin(_PA + math.pi / TEETH) / math.cos(_PA)
) / (2.0 * math.tan(_PA))
RACK_AXIS_DISTANCE = PITCH_DIA / 2.0 + RACK_MESH_EXTENSION

# --- axial stations from the rear face (z 0) -----------------------------------
# OVERALL_LENGTH and FLAT_END_STATION print ±0.05 (R9-5; the knob chain and
# the fitted bands read the overall: transgear_cluster_fit).  The tooth length
# prints .XXX: its end is the step face the hub's spigot seats on, so it
# places hub and disc with the spigot's own .XXX length (the bushings and the
# hub are faced to fit over both bands).
STATION_TOL = 0.05
STATION_PLACES = 2
FACE_WIDTH = 13.60  # the tooth length: rear face to the step onto the boss
FACE_WIDTH_PLACES = 3
FACE_WIDTH_BAND = printed_band_mm(FACE_WIDTH_PLACES)
OVERALL_LENGTH = 27.35

# --- diameters -----------------------------------------------------------------
# The boss is the hub's locating fit: turned h6 under the matching H7 bore
# (pd_transgear_disc_hub_spec consumes this diameter and checks the pair).
BOSS_DIA = 8.2
BOSS_DIA_BAND = (0.0, -0.009)  # (upper, lower) deviations, h6
BOSS_DIA_PLACES = 3

# --- the step face: the hub's seat ----------------------------------------------
# The hub's spigot bears on the step face's tooth ends, so the face is held
# square to the bore (datum A), faced in the setup that reams the bore; the
# zone is the face's extent, the 12T's tip circle.
BORE_DATUM = "A"
TOOTH_SPACE_CALLOUT_PROPERTY = "Tooth Space Inspection"
TOOTH_SPACE_CALLOUT = "\n".join(
    (
        f"TOOTH SPACE RUNOUT {TOOTH_SPACE_RUNOUT_TIR_MM:.2f} TIR TO {BORE_DATUM}",
        f"\u00d8{TOOTHSPACE_GAUGE_DIA_IN:.4f} in PIN, ALL {TEETH} SPACES",
        f"INDEX RANGE {PITCH_INDEX_DEVIATION_MM:.2f} MAX",
    )
)
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "step face perpendicularity to bore": "0.005",
}
STEP_FACE_PERPENDICULARITY = float(
    GEOMETRIC_TOLERANCES_MM["step face perpendicularity to bore"]
)
STEP_FACE_PERPENDICULARITY_ZONE_DIA = OUTSIDE_DIA

# --- D-flat (local -Y): drive only ------------------------------------------------
# The hub drives through it.  The flat plane prints from the boss axis with
# its own (0, −0.015): the hub's flat sits 0.020..0.050 off it (the hub owns
# its band and checks the pair).
FLAT_TO_AXIS = 3.5
FLAT_TO_AXIS_BAND = (0.0, -0.015)  # (upper, lower) deviations
FLAT_TO_AXIS_PLACES = 3
FLAT_DEPTH = BOSS_DIA / 2.0 - FLAT_TO_AXIS  # 1.0
# The flat runs from the nose rearward to an end wall at FLAT_END_STATION,
# cut by an end mill on an axis parallel to the sleeve's, plunged from the
# nose.  The wall stops nothing: the hub's flat starts at its flange's rear
# face, the spigot's length ahead of the step, so the wall stands clear
# behind it (pd_transgear_disc_hub_spec.FLAT_END_CLEARANCE_WORST).
FLAT_END_STATION = 16.60
FLAT_LENGTH = OVERALL_LENGTH - FLAT_END_STATION  # 10.75
FLAT_LENGTH_MAX = FLAT_LENGTH + 2.0 * STATION_TOL  # 10.85
FLAT_CUTTER_FLUTE_MIN = 12.0
if FLAT_CUTTER_FLUTE_MIN < FLAT_LENGTH_MAX + 0.5:
    raise AssertionError("the flat's end mill cannot reach the end wall on its flutes")

# G7 bore on the preserved MHA-PD-023 h6 pin: +0.016/+0.004 over 0/-0.008
# gives 0.004..0.024 diametral clearance. The true finite root at every
# radial-setting corner retains the 2.0 mm wall.
BORE_DIA = pd_transgear_pin_spec.DIA
BORE_DIA_BAND = (0.016, 0.004)  # (upper, lower), G7 at 3-6 mm
BORE_PLACES = 3
_PIN_UPPER, _PIN_LOWER = pd_transgear_pin_spec.DIA_BAND
BORE_DIAMETRAL_CLEARANCE = (
    round(BORE_DIA_BAND[1] - _PIN_UPPER, 3),
    round(BORE_DIA_BAND[0] - _PIN_LOWER, 3),
)
if BORE_DIAMETRAL_CLEARANCE[0] <= 0.0:
    raise AssertionError(f"sleeve bore binds on the pin: {BORE_DIAMETRAL_CLEARANCE}")
BORE_PROCESS_CALLOUT = "REAM THRU"
BORE_FIT_CALLOUT = "\n".join(
    (
        "BORE LIMITS GOVERN",
        f"MATE PIN {PIN_NUMBER}",
        f"(\N{DIAMETER SIGN}{BORE_DIA:.3f} +{_PIN_UPPER:.3f}/{_PIN_LOWER:.3f})",
        f"(DIA CLR {BORE_DIAMETRAL_CLEARANCE[0]:.3f}-{BORE_DIAMETRAL_CLEARANCE[1]:.3f} mm)",
    )
)

_BAND = {places: printed_band_mm(places) for places in (1, 2, 3)}

# --- the hub and disc on the step ------------------------------------------------
# The hub's spigot seats on the step face and passes the disc's bore; the
# hub's flange clamps the disc's front face, so that face stands the
# spigot's length ahead of the step and the disc's rear face stands in air
# ahead of it, the spigot's length less the disc's thickness (0.65 nominal;
# the hub's spec takes the worst case with the tilts).  The disc's bore is
# the spigot's, outside the 12T's tips, so the two never overlap radially.
DISC_THICKNESS = pd_rack_pinion_spec.FACE_WIDTH
DISC_FRONT_STATION = FACE_WIDTH + SPIGOT_LENGTH  # 17.25, the hub flange's seat
DISC_FRONT_STATION_BAND = FACE_WIDTH_BAND + SPIGOT_LENGTH_BAND  # 0.26
DISC_REAR_STATION = DISC_FRONT_STATION - DISC_THICKNESS  # 14.25
DISC_REAR_MIN = (
    DISC_FRONT_STATION - DISC_FRONT_STATION_BAND - pd_rack_pinion_spec.FACE_WIDTH_MAX
)  # 13.86
if pd_rack_pinion_spec.BORE_DIA_MIN <= OUTSIDE_DIA + OUTSIDE_DIA_BAND[0]:
    raise AssertionError("the disc's bore overlaps the 12T's tips radially")

# --- Physical finite-disc cutter run-out (R9-67) -------------------------------
# A straight pass from the rear face stops at FULL_DEPTH; the actual disc
# cutter then leaves its revolved finite ground-form end envelope. The
# remaining face has partial-depth gaps, not full-depth analytic teeth.
# CUTTER_RUNOUT_MAX is the retained native maximum station; the geometric
# endpoint over the boss uses the deepest template X, never a root norm.
FULL_DEPTH = 10.15
FULL_DEPTH_PLACES = 3
CUTTER_RUNOUT_MAX = 13.80  # from the rear face, a limit
CUTTER_RUNOUT_PLACES = 2
CUTTER_DIA_MAX_IN = 2.25
CUTTER_DIA_MAX = CUTTER_DIA_MAX_IN * MM_PER_IN
CUTTER_SKU = "10-289-328"
FULL_DEPTH_BAND = printed_band_mm(FULL_DEPTH_PLACES)
FULL_DEPTH_MIN = FULL_DEPTH - FULL_DEPTH_BAND
FULL_DEPTH_MAX = FULL_DEPTH + FULL_DEPTH_BAND
# swTolMAX prints the dimension's NOMINAL followed by "MAX", so the witness
# sits at the limit; its deviations record "anywhere behind the shortest full
# depth, up to the limit".
CUTTER_RUNOUT_TOL_TYPE = 6  # swTolType_e.swTolMAX
CUTTER_RUNOUT_DEVIATIONS = (FULL_DEPTH_MIN - CUTTER_RUNOUT_MAX, 0.0)
if round(CUTTER_RUNOUT_MAX, CUTTER_RUNOUT_PLACES) != CUTTER_RUNOUT_MAX:
    raise AssertionError("the run-out limit does not print at its places")
FULL_DEPTH_PREFIX = "12T FULL DEPTH "
CUTTER_RUNOUT_PREFIX = "CUTTER RUN-OUT "
# Numerical interval widths, not manufacturing tolerance or runout grades.
ENDCUT_VOLUME_ERROR_MM3 = 0.02
STEP_SEAT_AREA_ERROR_MM2 = 0.002


def cutter_runout(cutter_dia: float, rise: float) -> float:
    """Axial length behind the full-depth station over which a form cutter of
    ``cutter_dia`` still cuts a surface ``rise`` above the gap floor: the
    chord half-length of its circle at that height, √(Rc² − (Rc − rise)²)."""
    radius = cutter_dia / 2.0
    if not 0.0 <= rise <= radius:
        raise ValueError(f"rise {rise} is off a Ø{cutter_dia} cutter")
    return (radius**2 - (radius - rise) ** 2) ** 0.5

def endcut_volume_bounds_mm3(
    *,
    profile: StockFormProfile = STOCK_PROFILE,
    face_width_mm: float = FACE_WIDTH,
    full_depth_mm: float = FULL_DEPTH,
    boss_radius_mm: float = BOSS_DIA / 2.0,
    overall_length_mm: float = OVERALL_LENGTH,
    absolute_error_mm3: float = ENDCUT_VOLUME_ERROR_MM3,
) -> tuple[float, float]:
    """ONE indexed gap's extra endcut behind its straight axial pass."""
    if profile.teeth != TEETH or profile.template != CUTTER_TEMPLATE:
        raise ValueError("feed end-envelope requires its declared stock master")
    if not 0.0 < full_depth_mm < face_width_mm < overall_length_mm:
        raise ValueError("invalid straight-pass/face/boss stations")
    intervals = (
        (profile.blank_radius_mm, 0.0, face_width_mm - full_depth_mm),
        (boss_radius_mm, face_width_mm - full_depth_mm, overall_length_mm - full_depth_mm),
    )
    bounds = [
        cutter_end_volume_bounds_mm3(
            profile, CUTTER_DIA_MAX, outer_radius_mm=radius, inner_radius_mm=0.0,
            start_offset_mm=start, end_offset_mm=end,
            absolute_error_mm3=absolute_error_mm3 / 2.0,
        )
        for radius, start, end in intervals
    ]
    return (
        max(0.0, math.nextafter(math.fsum(row[0] for row in bounds), -math.inf)),
        math.nextafter(math.fsum(row[1] for row in bounds), math.inf),
    )


def step_seat_area_bounds_mm2(
    inner_radius_mm: float,
    outer_radius_mm: float,
    *,
    profile: StockFormProfile = STOCK_PROFILE,
    station_mm: float = FACE_WIDTH,
    full_depth_mm: float = FULL_DEPTH,
    absolute_error_mm2: float = STEP_SEAT_AREA_ERROR_MM2,
) -> tuple[float, float]:
    """Retained annular step material after ALL actual finite end-envelope gaps."""
    if profile.teeth != TEETH or profile.template != CUTTER_TEMPLATE:
        raise ValueError("feed step envelope requires its declared stock master")
    outer = min(outer_radius_mm, profile.blank_radius_mm)
    if not (
        math.isfinite(inner_radius_mm)
        and math.isfinite(outer_radius_mm)
        and 0.0 <= inner_radius_mm <= outer
        and math.isfinite(station_mm)
        and math.isfinite(full_depth_mm)
        and station_mm >= full_depth_mm >= 0.0
    ):
        raise ValueError("invalid step annulus or end-envelope station")
    if inner_radius_mm == outer:
        return 0.0, 0.0
    lower_cut, upper_cut = cutter_end_section_area_bounds_mm2(
        profile, CUTTER_DIA_MAX, outer_radius_mm=outer, inner_radius_mm=inner_radius_mm,
        offset_mm=station_mm - full_depth_mm,
        absolute_error_mm2=absolute_error_mm2 / profile.teeth,
    )
    annulus = math.pi * (outer * outer - inner_radius_mm * inner_radius_mm)
    padding = 256 * math.ulp(annulus)
    return (
        max(0.0, math.nextafter(annulus - profile.teeth * upper_cut - padding, -math.inf)),
        min(annulus, math.nextafter(annulus - profile.teeth * lower_cut + padding, math.inf)),
    )



# The assembly's RACK_FRONT_FROM_SLEEVE_REAR_WORST asserts FULL_DEPTH_MIN
# covers the complete axial rack reach. The boss at its largest radius over the
# deepest finite root X bounds any boss run-out at the latest full-depth
# station. The retained limit keeps the cutting envelope behind the disc
# and under the hub spigot; no particular boss slot is presumed.
RUNOUT_RISE_WORST = (BOSS_DIA + BOSS_DIA_BAND[0]) / 2.0 - ROOT_DEPTH_X_MIN
CUTTER_RUNOUT_END_WORST = FULL_DEPTH_MAX + cutter_runout(
    CUTTER_DIA_MAX, RUNOUT_RISE_WORST
)
RUNOUT_DISC_CLEARANCE = 0.05
if FULL_DEPTH_MAX >= FACE_WIDTH - _BAND[FACE_WIDTH_PLACES]:
    raise AssertionError("the 12T full-depth window reaches the step")
if CUTTER_RUNOUT_END_WORST > CUTTER_RUNOUT_MAX + 1e-9:
    raise AssertionError(
        f"a Ø{CUTTER_DIA_MAX_IN:.2f} in cutter runs out to "
        f"{CUTTER_RUNOUT_END_WORST:.3f}, past the {CUTTER_RUNOUT_MAX} limit"
    )
if CUTTER_RUNOUT_END_WORST > DISC_REAR_MIN - RUNOUT_DISC_CLEARANCE + 1e-9:
    raise AssertionError(
        f"the cutter runs out to {CUTTER_RUNOUT_END_WORST:.3f}, within "
        f"{RUNOUT_DISC_CLEARANCE} of the disc's rear face {DISC_REAR_MIN:.3f}"
    )
if CUTTER_RUNOUT_MAX > DISC_REAR_MIN - RUNOUT_DISC_CLEARANCE + 1e-9:
    raise AssertionError("the run-out limit reaches the disc's rear face")

# --- oil hole (R9-8) -----------------------------------------------------------
# Ø1.2 drilled (+0.10/0) on +Y, centred on the hub body (R9-60), through hub
# and boss wall in one operation at assembly.  The hub's spec owns its size,
# its sleeve-local station (pd_transgear_disc_hub_spec.OIL_HOLE_SLEEVE_Z) and
# the ligament to this nose; this sheet's drawing carries the drill note
# (draw_pd_transgear_feed_pinion.OIL_HOLE_NOTE, which reads the hub's size).
OIL_HOLE_AZIMUTH_DEG = 90.0  # local +Y, opposite the flat

# Tooth phase: the seed gap is centred half a pitch CCW of local +X
# (involute_gear.gear_facts: (ThetaL + ThetaU) / 2 = Gamma / 2) and the pattern
# steps a pitch, so gap centres sit at 15° + k·30°.  +Y (90°) is a TOOTH
# centre; the oil hole is on the boss well in front of the teeth anyway, so
# no clocking is needed.
TOOTH_PITCH_DEG = 360.0 / TEETH
GAP_CENTRE_PHASE_DEG = TOOTH_PITCH_DEG / 2.0
OIL_HOLE_TOOTH_OFFSET_DEG = (
    OIL_HOLE_AZIMUTH_DEG - GAP_CENTRE_PHASE_DEG
) % TOOTH_PITCH_DEG
if abs(OIL_HOLE_TOOTH_OFFSET_DEG - GAP_CENTRE_PHASE_DEG) > 1e-9:
    raise AssertionError("the +Y oil hole is no longer on a tooth centre")

# --- walls (rule 12: target 2.0, floor 1.5, at the printed bands) --------------
WALL_TARGET = 2.0
WALL_FLOOR = 1.5
_BORE_MAX = BORE_DIA + BORE_DIA_BAND[0]
# The native root MIN is below every true translated-root corner.
ROOT_WALL = (ROOT_DIA - BORE_DIA) / 2.0
ROOT_WALL_WORST = (ROOT_DIA_MIN - _BORE_MAX) / 2.0
BOSS_WALL = (BOSS_DIA - BORE_DIA) / 2.0
BOSS_WALL_WORST = (BOSS_DIA + BOSS_DIA_BAND[1] - _BORE_MAX) / 2.0
WALLS = (
    ("under the root", ROOT_WALL, ROOT_WALL_WORST),
    ("boss", BOSS_WALL, BOSS_WALL_WORST),
)
for _name, _nominal, _worst in WALLS:
    if _worst < WALL_TARGET:
        raise AssertionError(f"sleeve wall {_name} {_worst:.3f} under {WALL_TARGET}")
# The D-flat wall retains its existing named 1.5 mm floor. Its size and band
# are unchanged; the smaller G7 bore raises rather than spends that margin.
FLAT_WALL = FLAT_TO_AXIS - BORE_DIA / 2.0
FLAT_WALL_WORST = round(FLAT_TO_AXIS + FLAT_TO_AXIS_BAND[1] - _BORE_MAX / 2.0, 6)
FLAT_WALL_PRINTED = math.floor(FLAT_WALL_WORST * 100.0) / 100.0  # 1.52
if FLAT_WALL_WORST < WALL_FLOOR:
    raise AssertionError(f"the D-flat wall {FLAT_WALL_WORST:.3f} is under the floor")

# One roughness, on the one running surface: the bore.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)

# --- Marked-dimension contract -------------------------------------------------
# ``GearBlank`` is the tooth blank's extrude (its depth is the tooth length).
# ``SleeveProfile`` is the Right-plane revolve of the boss, with
# construction-only witnesses for the tooth tip, the root and the bore, so
# every turned diameter prints beside its axial extent on the longitudinal
# section (rules 2 and 7), and for the cutter's full-depth station, its
# run-out limit (R9-67).  Lengths are baselined from the rear face.
# ``FlatProfile`` is the flat's cut sketch on the Right plane (the section
# plane): the flat from the axis and its end wall from the rear face print on
# the section, where the flat shows edge-on.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "SleeveProfile": {
        "OutsideDia",
        "RootDia",
        "BoreDia",
        "BossDia",
        "OverallLength",
        "FullDepth",
        "CutterRunout",
    },
    "FlatProfile": {"FlatToAxis", "FlatEnd"},
    "SpanProfile": {"ToothSpan"},
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": FACE_WIDTH_PLACES},
    "SleeveProfile": {
        "OutsideDia": 3,
        "RootDia": ROOT_DIA_PLACES,
        "BoreDia": BORE_PLACES,
        "BossDia": BOSS_DIA_PLACES,
        "OverallLength": STATION_PLACES,
        "FullDepth": FULL_DEPTH_PLACES,
        "CutterRunout": CUTTER_RUNOUT_PLACES,
    },
    "FlatProfile": {
        "FlatToAxis": FLAT_TO_AXIS_PLACES,
        "FlatEnd": STATION_PLACES,
    },
    "SpanProfile": {"ToothSpan": SPAN_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(len(d) for d in DRAWING_PRECISION.values()):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    if set(_dimensions) != DRAWING_DIMENSIONS[_feature]:
        raise AssertionError(f"{_feature}: precision and marks disagree")

# The bands the build applies, by dimension (``(lower, upper)`` deviations).
STATION_DEVIATIONS = (-STATION_TOL, STATION_TOL)
BORE_DEVIATIONS = deviations(BORE_DIA_BAND)
BOSS_DIA_DEVIATIONS = deviations(BOSS_DIA_BAND)
FLAT_TO_AXIS_DEVIATIONS = deviations(FLAT_TO_AXIS_BAND)
OUTSIDE_DIA_DEVIATIONS = deviations(OUTSIDE_DIA_BAND)
# The root witness's nominal IS the printed physical MIN limit.
ROOT_DIA_DEVIATIONS = (0.0, 0.0)
RADIAL_SETTING_DEVIATIONS = deviations(RADIAL_SETTING_BAND)


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


# What a machinist needs to cut and check the teeth; design parameters stay
# in this module (Main ruling 2026-10-10).
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.3f}"),
        ("CIRCULAR THICKNESS AT PD (mm, REF)", f"{TOOTH_THICKNESS:.3f}"),
        ("WHOLE DEPTH (mm, REF)", f"{WHOLE_DEPTH:.3f}"),
        ("CUTTER", f"#{CUTTER_NUMBER}, {CUTTER_TOOTH_RANGE[0]}-{CUTTER_TOOTH_RANGE[1]}T"),
        (
            f"SPAN OVER {SPAN_TEETH} TEETH",
            f"{min(SPAN_LIMITS):.{SPAN_PLACES}f}-{max(SPAN_LIMITS):.{SPAN_PLACES}f}",
        ),
        ("MATES WITH", f"PLATEN RACK {RACK_NUMBER}"),
    ]
)

# The title block's 0.25 edge break is 14% of this fine tooth's whole depth,
# and the tooth ends seat the hub's spigot.
TOOTH_EDGE_NOTE = "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
# Named exception: MHA-PD-010 flat wall (drawing-simplicity-policy.md, "Named exceptions").
# A shop note states the requirement, not the measuring method or the cutter
# choice (Main ruling 2026-10-10): the run-out length is dimensioned.
FLAT_WALL_NOTE = f"D-FLAT WALL TO BORE {FLAT_WALL_PRINTED:.2f} MIN."
DRAWING_NOTES = "\n".join((TOOTH_EDGE_NOTE, FLAT_WALL_NOTE))
