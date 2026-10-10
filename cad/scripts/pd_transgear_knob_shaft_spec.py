r"""MHA-PD-008 transgear-knob-shaft: the steel knob shaft with its integral 12T.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  ``build_pd_transgear_knob_shaft`` marks and tolerances exactly
``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model and
``draw_pd_transgear_knob_shaft`` keeps exactly the same names.

One turned SAE1018 shaft carries a standard-depth 12T48DP PA20 integral
pinion cut by the finite TTC #8 stock form (10-289-488, Ø44.45 cutter).
The gear front F and every chain/cup station remain unchanged.  Its front
Ø4.900 h6 solid D-core drives the matching brass D-collar without a cross
hole.  The collar's fitted rear face bears directly on F; the #8-32 stud
and same-outer custom thumbnut clamp it there, while the removable T24
still floats on the existing pilot and is driven by the two axial dowels.
The thread relief carries clamp, not torque.

The Ø6 g6 rear journal runs in the plate's Ø6 H7 bore.  The loose Ø6.1-bore
thrust ring retains its 5.2 length and bears on the actual rear tooth ends.
True finite disk endcuts run out within that ring, not in the active plate
bearing.  The rear cup is still set on the existing end-float feeler and
match-pinned by MHA-VN-048.  No front spring pin or collar slot remains.

Part frame: the axis is local +Z through the origin (``Axis1``); +Z is
machine +Z (rearward), so the assembly places the part without rotation.  The
origin is F, the 12T's front face (machine z -148.1 at the stack pose, R9-17):
the teeth run z = 0..FACE_WIDTH, the journal FACE_WIDTH..REAR_END_Z,
the D-core CORE_FRONT_Z..CORE_REAR_Z, the front neck CORE_REAR_Z..0,
the thread relief THREAD_END_Z..CORE_FRONT_Z, and thread TIP_Z..THREAD_END_Z.
The indexed finite gap is centred on
GAP_AZIMUTH_DEG from local +X, CCW about +Z.

Named datums: ``Axis1`` (the shaft axis); ``Front Plane`` (F); planes
``PinionRear`` (the 12T's rear face, the thrust ring's seat), ``RearFace``
(the journal's rear end face), ``ThreadEnd`` (full thread ends) and
``StudTip`` (the tip face).
"""

from __future__ import annotations

import math

import pd_rack_pinion_spec as DISC
import _config

from _fit_limits import SHAFT_G6_3_TO_6_MM, deviations
from _gear_fit_limits import gear_tip_band_mm
from _gear_quality import (
    pinion_pitch_index_deviation_mm,
    pitch_index_measurement_uncertainty_mm,
    require_pitch_index_measurements_mm,
    shaft_turned_runout_mm,
    toothspace_runout_tir_mm,
)
from paper_drive_stock_inspection import GaugeContact, toothspace_gauge_contact_mm
from _gtol_spec import CylinderFace, GeometricControl, PartDatum
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm, printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pd_transgear_arm_plate_geometry import HUB_TO_BOSS as PLATE_HUB_TO_BOSS
from pd_transgear_arm_plate_geometry import HUB_TO_BOSS_BAND as PLATE_HUB_TO_BOSS_BAND
from pd_transgear_knob_thrust_ring_spec import LENGTH as RING_LENGTH
from pd_transgear_knob_thrust_ring_spec import LENGTH_TOL as RING_LENGTH_TOL
from pd_transgear_knob_thrust_ring_spec import ID as RING_ID
from pd_transgear_knob_thrust_ring_spec import ID_BAND as RING_ID_BAND
from paper_drive_stock_envelope import cutter_end_volume_bounds_mm3
from stock_form_cutter import CutterTemplate, StockFormProfile, translation_for_tangent_span

MM_PER_IN = 25.4
WALL_FLOOR = 2.0
EDGE_BREAK_MAX = float(_config.title_block("edge_break")["chamfer_max_mm"])
ENGAGEMENT_FLOOR_D = 1.5

# --- Actual finite stock #8 master, not an analytic generated shift --------
TEETH = DISC.MESH_PINION_TEETH
DIAMETRAL_PITCH = DISC.DIAMETRAL_PITCH
PRESSURE_ANGLE_DEG = DISC.PRESSURE_ANGLE_DEG
CUTTER_TEMPLATE = CutterTemplate(12, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG)
CUTTER_NUMBER = CUTTER_TEMPLATE.cutter_number
CUTTER_TOOTH_RANGE = CUTTER_TEMPLATE.teeth_range
MODULE_MM = CUTTER_TEMPLATE.module_mm
ADDENDUM_FACTOR = (
    CUTTER_TEMPLATE.tip_radius_mm - CUTTER_TEMPLATE.pitch_radius_mm
) / MODULE_MM
DEDENDUM_FACTOR = (
    CUTTER_TEMPLATE.pitch_radius_mm - CUTTER_TEMPLATE.root_radius_mm
) / MODULE_MM
PITCH_DIA = TEETH * MODULE_MM
RADIAL_SETTING = 0.005
_SPAN_DESIGN_SETTING_BAND = (0.005, -0.005)
OUTSIDE_DIA = 7.40
OUTSIDE_DIA_BAND = gear_tip_band_mm("contact_critical")
OUTSIDE_DIA_PLACES = 2
STOCK_PROFILE = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, OUTSIDE_DIA / 2.0, RADIAL_SETTING
)
CUTTER_GROUND_PROFILE = StockFormProfile(
    CUTTER_TEMPLATE.reference_teeth, CUTTER_TEMPLATE, CUTTER_TEMPLATE.tip_radius_mm, 0.0
)

# Match the feed/disc convention: OUTWARD printed tangent-span limits, then
# invert those real limits and charge the evaluator error on both sides.
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
    math.floor(min(row[0] for row in _SPAN_CORNERS) * 10**SPAN_PLACES) / 10**SPAN_PLACES,
    math.ceil(max(row[1] for row in _SPAN_CORNERS) * 10**SPAN_PLACES) / 10**SPAN_PLACES,
)
SPAN_BAND = (SPAN_LIMITS[1] - SPAN_NOMINAL, SPAN_LIMITS[0] - SPAN_NOMINAL)
SPAN_DEVIATIONS = deviations(SPAN_BAND)
SPAN_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
SPAN_PREFIX = f"CONTROL SPAN {SPAN_TEETH} TEETH "
SPAN_ORIENTATION = "NORMAL TO SPANNED-TOOTH BISECTOR; MAXIMUM READING."
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
        TEETH, CUTTER_TEMPLATE, limit + sign * 2.0 * _SPAN_GEOMETRY_ERROR,
        SPAN_TEETH, translation_bounds_mm=_SPAN_INVERSE_BOUNDS,
    )
    for limit, sign in zip(SPAN_LIMITS, (-1.0, 1.0), strict=True)
)
RADIAL_SETTING_BAND = (
    RADIAL_SETTING_LIMITS[1] - RADIAL_SETTING,
    RADIAL_SETTING_LIMITS[0] - RADIAL_SETTING,
)


def manufactured_profiles() -> tuple[StockFormProfile, ...]:
    """Real PRINTED-span-derived setting × accepted tip corners."""
    return tuple(
        StockFormProfile(TEETH, CUTTER_TEMPLATE, (OUTSIDE_DIA + tip) / 2.0, setting)
        for setting in RADIAL_SETTING_LIMITS
        for tip in OUTSIDE_DIA_BAND
    )


_PROFILE_CORNERS = manufactured_profiles()
for _profile in _PROFILE_CORNERS:
    _profile.require_tip_land(0.25 * MODULE_MM)
TOOTH_THICKNESS = STOCK_PROFILE.pitch_tooth_thickness_mm
ROOT_DIA = 2.0 * STOCK_PROFILE.root_radius_min_mm
ROOT_DIA_PLACES = 2
ROOT_DIA_EXACT_MIN = min(2.0 * p.root_radius_min_mm for p in _PROFILE_CORNERS)
ROOT_DIA_MIN = math.floor(ROOT_DIA_EXACT_MIN * 10**ROOT_DIA_PLACES) / 10**ROOT_DIA_PLACES
ROOT_ACCEPTANCE = f"ACTUAL FORMED ROOT ENVELOPE Ø{ROOT_DIA_MIN:.2f} MIN; CHECK EVERY GAP."
ROOT_DEPTH_X_MIN = min(
    p.root_point(p.root_half_angle_rad)[0] for p in _PROFILE_CORNERS
)
WHOLE_DEPTH = (OUTSIDE_DIA - ROOT_DIA) / 2.0
FACE_WIDTH = 5.9
FACE_WIDTH_PLACES = 3
GAP_AZIMUTH_DEG = 180.0 / TEETH
# The assembly spins the shaft and its whole mounted front stack (collar,
# drive pins, wheel) about K so a 12T gap faces the reducer disc's tooth on
# the K -> S line (azimuth 180 + MESH_ANGLE_DEG from K): the nearest
# representative modulo one tooth pitch. The assembly drawing reads it to
# find the collar's rim seen edge-on.
_TOOTH_PITCH_DEG = 360.0 / TEETH
FRONT_STACK_PHASE_DEG = (180.0 + DISC.MESH_ANGLE_DEG - GAP_AZIMUTH_DEG) % _TOOTH_PITCH_DEG
if FRONT_STACK_PHASE_DEG > _TOOTH_PITCH_DEG / 2.0:
    FRONT_STACK_PHASE_DEG -= _TOOTH_PITCH_DEG
# --- #8-32 stud: passes the true D-bore, including its flat ------------------
THREAD = "#8-32"
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]
THREADS_PER_IN = 32
THREAD_PITCH = MM_PER_IN / THREADS_PER_IN
# ASME B1.1 basic minor diameter (D1 = D - 1.082532 P): the tip chamfer runs
# 45 degrees down to it, so the first full thread starts at the chamfer.
THREAD_BASIC_MINOR = THREAD_MAJOR - 1.082532 * THREAD_PITCH
# #8-32 UNC-2A ASME B1.1 limits as tabled by Engineers Edge (2026-10-08):
# https://www.engineersedge.com/screw_threads_chart.htm
THREAD_MAJOR_2A_IN = (0.1571, 0.1631)
THREAD_MAJOR_2A = tuple(v * MM_PER_IN for v in THREAD_MAJOR_2A_IN)
THREAD_PD_2A_MIN_IN = 0.1399
# Conservative die root: a full basic half-depth below minimum 2A pitch.
THREAD_ROOT_2A_MIN = (THREAD_PD_2A_MIN_IN - 0.649519 / THREADS_PER_IN) * MM_PER_IN
# Turn the blank inside the actual 2A major window, below the D-core.
THREAD_BLANK_DIA = 4.070
THREAD_BLANK_DIA_BAND = (0.050, -0.050)
THREAD_BLANK_DIA_PLACES = 3
THREAD_BLANK_LIMITS = (
    THREAD_BLANK_DIA + min(THREAD_BLANK_DIA_BAND),
    THREAD_BLANK_DIA + max(THREAD_BLANK_DIA_BAND),
)
if not (
    THREAD_MAJOR_2A[0] <= THREAD_BLANK_LIMITS[0]
    and THREAD_BLANK_LIMITS[1] <= THREAD_MAJOR_2A[1]
):
    raise AssertionError(
        f"MHA-PD-008 thread blank / #8-32 UNC-2A major: the blank "
        f"{THREAD_BLANK_LIMITS[0]:.3f}..{THREAD_BLANK_LIMITS[1]:.3f} leaves the "
        f"2A major {THREAD_MAJOR_2A[0]:.3f}..{THREAD_MAJOR_2A[1]:.3f}"
    )
TIP_CHAMFER = (THREAD_BLANK_DIA - THREAD_BASIC_MINOR) / 2.0
TIP_CHAMFER_PLACES = 3
# The title block states the UN thread class, so the callout names no class.
THREAD_CALLOUT = f"{THREAD} UNC"
CHAMFER_CALLOUT = "X 45 DEG"
# The tip prints as its station from F (.XX, R9-17), not as a thread length.
TIP_STATION = 23.9
TIP_STATION_PLACES = 2

# --- Solid D-core; no gear bore and no transverse torque hole ---------------
CORE_DIA = 4.900
CORE_DIA_BAND = (0.0, -0.008)  # ISO h6, over 3 THROUGH 6 mm
CORE_DIA_PLACES = 3
CORE_FLAT_FROM_AXIS = 2.150
CORE_FLAT_BAND = (0.0, -0.015)
CORE_FLAT_PLACES = 3
# The drawing's frames print these strings; the turned-shaft grade is the
# shared shaft_turned_runout_mm() (asserted below).
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "core_total_runout": "0.050",
    "front_neck_total_runout": "0.050",
}
CORE_TOTAL_RUNOUT = float(GEOMETRIC_TOLERANCES_MM["core_total_runout"])
if CORE_TOTAL_RUNOUT != shaft_turned_runout_mm():
    raise AssertionError("knob shaft core runout is not the turned-shaft grade")
# Pattern runout is a toothspace inspection, not mounting plate position.
TOOTH_SPACE_RUNOUT_TIR_MM = toothspace_runout_tir_mm()
TOOTH_SPACE_GAUGE_PIN_DIA_MM = 1.000  # use the actual certified diameter
# Relative angular index is separate from radial TIR and span thickness.
# Correct measured contact angles using the certified actual pin, then
# convert against this real pitch-reference radius, NOT the pin centre.
PITCH_INDEX_REFERENCE_RADIUS_MM = PITCH_DIA / 2.0
PITCH_INDEX_DEVIATION_MM = pinion_pitch_index_deviation_mm()
PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM = pitch_index_measurement_uncertainty_mm()
PITCH_INDEX_STATIONS = tuple(range(TEETH + 1))  # include the full-circle wrap


def tooth_space_gauge_contacts(actual_pin_dia_mm: float) -> tuple[GaugeContact, ...]:
    """Qualify the actual certified pin against every accepted finite corner."""
    return tuple(
        toothspace_gauge_contact_mm(profile, actual_pin_dia_mm)
        for profile in _PROFILE_CORNERS
    )


def require_pitch_index_errors_mm(measured_index_errors_mm: dict[int, float]) -> float:
    """Receive every space and the wrap about actual running journal A.

    Station i is R_ref * (unwrapped corrected angle_i - datum_angle -
    2*pi*i/TEETH), using ONE physical index datum without a floating best-fit
    tooth axis. This does not replace radial TIR, thickness or absolute clock.
    The returned max-minus-min range pays both calibration uncertainties.
    """
    return require_pitch_index_measurements_mm(
        measured_index_errors_mm=measured_index_errors_mm,
        required_stations=PITCH_INDEX_STATIONS,
        relative_deviation_limit_mm=PITCH_INDEX_DEVIATION_MM,
        absolute_measurement_uncertainty_mm=PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM,
    )


_GAUGE_CORNERS = tooth_space_gauge_contacts(TOOTH_SPACE_GAUGE_PIN_DIA_MM)
TOOTH_SPACE_GAUGE_ROOT_AIR_MIN_MM = min(c.root_air_mm for c in _GAUGE_CORNERS)
TOOTH_SPACE_GAUGE_TIP_AIR_MIN_MM = min(c.tip_air_mm for c in _GAUGE_CORNERS)
TOOTH_SPACE_CALLOUT_PROPERTY = "Tooth Space Inspection"
TOOTH_SPACE_CALLOUT = "\n".join(
    (
        f"TOOTH SPACE RADIAL INDICATOR TIR {TOOTH_SPACE_RUNOUT_TIR_MM:.3f} MAX TO A",
        f"PITCH INDEX RANGE+2U {PITCH_INDEX_DEVIATION_MM} mm MAX AT REF Ø{PITCH_DIA:.3f}",
        f"ALL SPACES + WRAP; ABS POSITION U {PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM} mm MAX",
        f"CERTIFIED PIN Ø{TOOTH_SPACE_GAUGE_PIN_DIA_MM:.3f} mm; ALL {TEETH} SPACES",
    )
)
_GAUGE_CONTACT = toothspace_gauge_contact_mm(STOCK_PROFILE, TOOTH_SPACE_GAUGE_PIN_DIA_MM)
_GAUGE_COS = math.cos(math.pi / TEETH)
_GAUGE_SIN = math.sin(math.pi / TEETH)
_GAUGE_X, _GAUGE_Y = _GAUGE_CONTACT.flank_point_mm
TOOTH_SPACE_CALLOUT_POINT_MM = (
    _GAUGE_COS * _GAUGE_X - _GAUGE_SIN * _GAUGE_Y,
    _GAUGE_SIN * _GAUGE_X + _GAUGE_COS * _GAUGE_Y,
    0.0,
)
# FRONT STATION from F, not the shortened active D length.
CORE_FRONT_FROM_F = 5.25
CORE_FRONT_FROM_F_PLACES = 3

# Ordinary turned undercut at F: no tiny-radius grade or front disk cut.
FRONT_RELIEF_DIA = 4.000
FRONT_RELIEF_DIA_PLACES = 3
FRONT_RELIEF_WIDTH = 0.400
FRONT_RELIEF_WIDTH_PLACES = 3
FRONT_CORNER_RADIUS = 0.050
FRONT_CORNER_RADIUS_MAX = 0.100
FRONT_CORNER_RADIUS_PLACES = 3
FRONT_CORNER_RADIUS_BAND = (
    FRONT_CORNER_RADIUS_MAX - FRONT_CORNER_RADIUS, -FRONT_CORNER_RADIUS
)
FRONT_CORNER_RADIUS_TOL_TYPE = 3  # native LIMIT0..0.100, actual nominal0.050
FRONT_RELIEF_TOTAL_RUNOUT = float(GEOMETRIC_TOLERANCES_MM["front_neck_total_runout"])
FRONT_RELIEF_DIA_MIN = FRONT_RELIEF_DIA - printed_band_mm(FRONT_RELIEF_DIA_PLACES)
FRONT_RELIEF_DIA_MAX = FRONT_RELIEF_DIA + printed_band_mm(FRONT_RELIEF_DIA_PLACES)
FRONT_RELIEF_WIDTH_MIN = FRONT_RELIEF_WIDTH - printed_band_mm(FRONT_RELIEF_WIDTH_PLACES)
FRONT_RELIEF_WIDTH_MAX = FRONT_RELIEF_WIDTH + printed_band_mm(FRONT_RELIEF_WIDTH_PLACES)
CORE_ACTIVE_LENGTH = CORE_FRONT_FROM_F - FRONT_RELIEF_WIDTH  # REF only
CORE_ACTIVE_LENGTH_MIN = (
    CORE_FRONT_FROM_F - printed_band_mm(CORE_FRONT_FROM_F_PLACES) - FRONT_RELIEF_WIDTH_MAX
)
# Native cut-profile foremost point IS the actual physical rounded tool
# terminal, not an independently toleranced sketch centre plus a hidden R.
CORE_FLAT_CUT_END_FROM_F = 0.110
CORE_FLAT_CUT_END_LIMITS = (0.050, 0.170)
CORE_FLAT_CUT_END_BAND = (
    CORE_FLAT_CUT_END_LIMITS[1] - CORE_FLAT_CUT_END_FROM_F,
    CORE_FLAT_CUT_END_LIMITS[0] - CORE_FLAT_CUT_END_FROM_F,
)
CORE_FLAT_CUT_END_PLACES = 3
CORE_FLAT_CUT_END_TOL_TYPE = 3
CORE_FLAT_TOOL_END_RADIUS = 0.100
CORE_FLAT_TOOL_END_RADIUS_MAX = 0.100
CORE_FLAT_TOOL_END_RADIUS_PLACES = 3
CORE_FLAT_TOOL_END_RADIUS_BAND = (0.0, -CORE_FLAT_TOOL_END_RADIUS)
CORE_FLAT_TOOL_END_RADIUS_TOL_TYPE = 6
CORE_FLAT_GEAR_AIR_MIN = min(CORE_FLAT_CUT_END_LIMITS)
CORE_FLAT_REACH_PAST_SHOULDER_MIN = (
    FRONT_RELIEF_WIDTH_MIN - max(CORE_FLAT_CUT_END_LIMITS)
)
CORE_FLAT_TOOL_REACH_NOTE = (
    "FLAT TOOL REACH .10 MIN PAST ACTUAL CORE SHOULDER; .05 MIN SHORT OF F. "
    "FLAT END LIMIT IS THE FOREMOST PHYSICAL POINT, INCLUDING TOOL ROUNDING."
)
FRONT_RELIEF_AREA_MIN = math.pi * FRONT_RELIEF_DIA_MIN**2 / 4.0
if (
    CORE_FLAT_GEAR_AIR_MIN < 0.050 - 1e-9
    or CORE_FLAT_REACH_PAST_SHOULDER_MIN < 0.100 - 1e-9
):
    raise AssertionError("the D-flat tool terminal violates its actual two-end reach limits")
if FRONT_RELIEF_WIDTH_MIN <= 2.0 * FRONT_CORNER_RADIUS_MAX:
    raise AssertionError("the front neck has no straight floor between its corner radii")

# --- Thread relief: the die's run-out lies in it (R9-53) -----------------------
# Full thread ends PLAIN_CORE in front of F, on the relief's front shoulder
# (.XXX).  The die runs rearward until its leading face meets the core's
# step, so it cuts full thread to the step plus its chamfered lead; the
# narrowest printed relief holds a lead of DIE_RUNOUT_PITCHES (a die run
# with its chamfer leading [INFERENCE: 1.5 P is the shorter of the common
# die leads]).  The relief's floor stands under the deepest die-cut root,
# so the lead's incomplete threads lie in air, and the thumbnut at the
# collar's rearward stop runs only on full thread or over the relief.
PLAIN_CORE = 7.5
PLAIN_CORE_PLACES = 3
THREAD_LENGTH_REF = TIP_STATION - PLAIN_CORE  # 16.4 REF
DIE_RUNOUT_PITCHES = 1.5
DIE_RUNOUT_MAX = DIE_RUNOUT_PITCHES * THREAD_PITCH
RELIEF_DIA = 2.800
RELIEF_DIA_PLACES = 3
_CORE_FRONT_TOL = printed_band_mm(CORE_FRONT_FROM_F_PLACES)
_PLAIN_CORE_TOL = printed_band_mm(PLAIN_CORE_PLACES)
RELIEF_DIA_MAX = RELIEF_DIA + printed_band_mm(RELIEF_DIA_PLACES)
RELIEF_DIA_MIN = RELIEF_DIA - printed_band_mm(RELIEF_DIA_PLACES)
RELIEF_WIDTH_MIN = (PLAIN_CORE - _PLAIN_CORE_TOL) - (
    CORE_FRONT_FROM_F + _CORE_FRONT_TOL
)  # 7.37 - 5.38 = 1.99
if RELIEF_WIDTH_MIN < DIE_RUNOUT_MAX - 1e-9:
    raise AssertionError(
        f"MHA-PD-008 thread relief / die run-out: the narrowest relief "
        f"{RELIEF_WIDTH_MIN:.3f} is under the {DIE_RUNOUT_MAX:.3f} "
        f"({DIE_RUNOUT_PITCHES}P) a die's lead runs out over"
    )
if RELIEF_DIA_MAX > THREAD_ROOT_2A_MIN + 1e-9:
    raise AssertionError(
        f"MHA-PD-008 thread relief / die root: the largest relief "
        f"Ø{RELIEF_DIA_MAX:.3f} stands above the deepest die-cut root "
        f"Ø{THREAD_ROOT_2A_MIN:.3f}"
    )
# Nut clamp crosses the relief; drive torque enters the D-core behind it.
THREAD_STRESS_AREA = math.pi / 4.0 * (THREAD_MAJOR - 0.9743 * THREAD_PITCH) ** 2
RELIEF_AREA_MIN = math.pi / 4.0 * RELIEF_DIA_MIN**2
RELIEF_AREA_RATIO_MIN = RELIEF_AREA_MIN / THREAD_STRESS_AREA

# --- Journal: ISO g6 in the arm plate's matching 6 H7 bore ------------------
JOURNAL_DIA = 6.0
JOURNAL_DIA_BAND = SHAFT_G6_3_TO_6_MM
JOURNAL_DIA_PLACES = 3
# The cup's front face, from the 12T's rear face (R9-25): the thrust ring +
# the plate's hub-to-boss + the 0.2 end float, the cup running that far
# behind the rear boss at the stack pose.  K-1 (R9-70): the float is set at
# assembly, the cup slid on the journal against a 0.2 feeler at the boss and
# pinned there, and accepted within END_FLOAT_SET_TOL; the journal's length
# no longer enters it.
END_FLOAT = 0.2
END_FLOAT_SET_TOL = 0.05
CUP_FACE_STATION = RING_LENGTH + PLATE_HUB_TO_BOSS + END_FLOAT  # 34.4375
if abs(CUP_FACE_STATION - 34.4375) > 1e-9:
    raise AssertionError(
        f"cup face station {CUP_FACE_STATION:.4f} is off the contract's 34.4375 "
        "(ring 5.2 + hub-to-boss 29.0375 + 0.2 float, R9-25)"
    )
# Where the fitter sets the cup on a real stack: the ring's and the hub-to-
# boss's own bands, and the feeler setting.
CUP_FACE_STATION_BAND = RING_LENGTH_TOL + PLATE_HUB_TO_BOSS_BAND + END_FLOAT_SET_TOL
# The journal runs on behind the cup's front face to carry the cup's pin
# (K-1); 12T rear face to the rear end face, at the title block's .XXX.
JOURNAL_REAR_EXTENSION = 6.5
JOURNAL_LENGTH = CUP_FACE_STATION + JOURNAL_REAR_EXTENSION  # 40.9375
JOURNAL_LENGTH_PLACES = 3
_JOURNAL_LENGTH_BAND = printed_band_mm(JOURNAL_LENGTH_PLACES)
# The journal behind the cup's front face at the printed worst case:
# 6.5 - 0.13 - 0.15 = 6.22 .. 6.78.
JOURNAL_REAR_EXTENSION_MIN = JOURNAL_REAR_EXTENSION - (
    _JOURNAL_LENGTH_BAND + CUP_FACE_STATION_BAND
)
JOURNAL_REAR_EXTENSION_MAX = JOURNAL_REAR_EXTENSION + (
    _JOURNAL_LENGTH_BAND + CUP_FACE_STATION_BAND
)
JOURNAL_DIA_MIN = JOURNAL_DIA + min(JOURNAL_DIA_BAND)

# --- Local stations along +Z, from F ------------------------------------------
TIP_Z = -TIP_STATION
CORE_FRONT_Z = -CORE_FRONT_FROM_F
CORE_REAR_Z = -FRONT_RELIEF_WIDTH
CORE_FLAT_CUT_END_Z = -CORE_FLAT_CUT_END_FROM_F
THREAD_END_Z = -PLAIN_CORE
PINION_REAR_Z = FACE_WIDTH
CUP_FACE_Z = PINION_REAR_Z + CUP_FACE_STATION  # 40.3375, at the stack pose
REAR_END_Z = FACE_WIDTH + JOURNAL_LENGTH
OVERALL_LENGTH = REAR_END_Z - TIP_Z  # 70.74 REF

FRONT_CORE_AIR_MIN = (
    ROOT_DIA_EXACT_MIN - CORE_DIA - max(CORE_DIA_BAND)
    - CORE_TOTAL_RUNOUT - TOOTH_SPACE_RUNOUT_TIR_MM
) / 2.0 - max(p.geometry_error_bound_mm for p in _PROFILE_CORNERS)
FRONT_NECK_AIR_MIN = (
    ROOT_DIA_EXACT_MIN / 2.0 - FRONT_RELIEF_DIA_MAX / 2.0
    - FRONT_CORNER_RADIUS_MAX - FRONT_RELIEF_TOTAL_RUNOUT / 2.0
    - TOOTH_SPACE_RUNOUT_TIR_MM / 2.0
    - max(p.geometry_error_bound_mm for p in _PROFILE_CORNERS)
)
if FRONT_NECK_AIR_MIN <= 0.0:
    raise AssertionError("the finite stock cutter enters a front neck corner")
if FRONT_CORE_AIR_MIN <= 0.0:
    raise AssertionError("the finite stock cutter enters the solid D-core envelope")
if not CORE_DIA < JOURNAL_DIA < OUTSIDE_DIA:
    raise AssertionError(
        "the journal must step up from the core and stay under the 12T"
    )

# --- Actual finite Ø44.45 stock disk, both axial terminal positions ---------
FULL_DEPTH = 4.65
FULL_DEPTH_PLACES = 3
CUTTER_RUNOUT_MAX = 10.5
CUTTER_RUNOUT_PLACES = 2
CUTTER_DIA = 44.45
CUTTER_ARBOR_BORE = 22.225
CUTTER_SKU = "10-289-488"
FULL_DEPTH_BAND = printed_band_mm(FULL_DEPTH_PLACES)
FULL_DEPTH_MIN = FULL_DEPTH - FULL_DEPTH_BAND  # 4.52
FULL_DEPTH_MAX = FULL_DEPTH + FULL_DEPTH_BAND  # 4.78
# swTolMAX prints the dimension's NOMINAL followed by "MAX", so the witness
# sits at the limit; its deviations record "anywhere behind the shortest full
# depth, up to the limit".
CUTTER_RUNOUT_TOL_TYPE = 6  # swTolType_e.swTolMAX
CUTTER_RUNOUT_DEVIATIONS = (FULL_DEPTH_MIN - CUTTER_RUNOUT_MAX, 0.0)
if round(CUTTER_RUNOUT_MAX, CUTTER_RUNOUT_PLACES) != CUTTER_RUNOUT_MAX:
    raise AssertionError("the run-out limit does not print at its places")
FULL_DEPTH_PREFIX = "12T FULL DEPTH "
CUTTER_RUNOUT_PREFIX = "CUTTER RUN-OUT "
CUTTER_NOTE = (
    f"TTC {CUTTER_SKU}, STOCK #{CUTTER_NUMBER}, {DIAMETRAL_PITCH:g}DP PA20; "
    f"TRUE FINITE GROUND FORM, CUTTER Ø{CUTTER_DIA:.2f}, ARBOR Ø{CUTTER_ARBOR_BORE:.3f}. "
    "TERMINAL CENTRES AT F AND FULL DEPTH; NO END-MILL SLOT SUBSTITUTE."
)


def cutter_runout(cutter_dia: float, rise: float) -> float:
    """Axial length behind the full-depth station over which a form cutter of
    ``cutter_dia`` still cuts a surface ``rise`` above the gap floor: the
    chord half-length of its circle at that height, √(Rc² − (Rc − rise)²)."""
    radius = cutter_dia / 2.0
    if not 0.0 <= rise <= radius:
        raise ValueError(f"rise {rise} is off a Ø{cutter_dia} cutter")
    return (radius**2 - (radius - rise) ** 2) ** 0.5


# Window (i): full depth covers the disc's worst-corner rear face.  That face
# is the assembly stack's (contract §13.2): nominal 3.70 from F + arm 0.0254
# + plate 0.13 + ring 0.05 + 12T face 0.13 + stud 0.05 + disc seat 0.05 +
# the knob float forward 0.35.
DISC_REAR_FROM_F_WORST = 4.4854
# Window (ii): the run-out ends in front of the plate hub's running bore.  At
# the stack pose (12T rear tooth ends -> ring -> hub) the hub face lies the
# face width plus the ring behind F, nearest at their short limits.
HUB_BORE_FROM_F_WORST = (FACE_WIDTH - printed_band_mm(FACE_WIDTH_PLACES)) + (
    RING_LENGTH - RING_LENGTH_TOL
)  # 10.92
# Use deepest ground X for the rear disk chord, not the polar root radius.
# Internal toothspace TIR is the only profile/journal axis term here.
_JOURNAL_R_MAX = (JOURNAL_DIA + max(JOURNAL_DIA_BAND)) / 2.0
RUNOUT_RISE_WORST = _JOURNAL_R_MAX + TOOTH_SPACE_RUNOUT_TIR_MM / 2.0 - ROOT_DEPTH_X_MIN
CUTTER_RUNOUT_END_WORST = FULL_DEPTH_MAX + cutter_runout(
    CUTTER_DIA, RUNOUT_RISE_WORST
)
# Actual tooling fixture envelope, not a claimed purchased arbor SKU.
CUTTER_MOUNT_OD_MAX = 31.75
CUTTER_MOUNT_AIR_MIN = (
    CUTTER_DIA / 2.0 + ROOT_DEPTH_X_MIN - CUTTER_MOUNT_OD_MAX / 2.0
    - (OUTSIDE_DIA + max(OUTSIDE_DIA_BAND) + TOOTH_SPACE_RUNOUT_TIR_MM) / 2.0
)
if CUTTER_MOUNT_AIR_MIN <= 0.0:
    raise AssertionError("the actual arbor mounting envelope reaches shaft stock")
if FULL_DEPTH_MIN < DISC_REAR_FROM_F_WORST - 1e-9:
    raise AssertionError(
        f"12T full depth may stop at F + {FULL_DEPTH_MIN:.3f}, in front of the "
        f"disc's worst rear face F + {DISC_REAR_FROM_F_WORST:.4f}"
    )
if CUTTER_RUNOUT_END_WORST > CUTTER_RUNOUT_MAX + 1e-9:
    raise AssertionError(
        f"a Ø{CUTTER_DIA:.2f} cutter's run-out reaches F + "
        f"{CUTTER_RUNOUT_END_WORST:.3f}, past the printed {CUTTER_RUNOUT_MAX:.2f}"
    )
if CUTTER_RUNOUT_MAX >= HUB_BORE_FROM_F_WORST:
    raise AssertionError(
        f"the printed run-out limit F + {CUTTER_RUNOUT_MAX:.2f} reaches the plate "
        f"hub bore (F + {HUB_BORE_FROM_F_WORST:.2f} worst)"
    )

# The real tool master extends to its finite tip. Close the native tool only
# beyond the accepted blank; do not extend the working flank to fake support.
CUTTER_SUPPORT_MARGIN_MIN = (
    CUTTER_TEMPLATE.tip_radius_mm + min(0.0, RADIAL_SETTING_LIMITS[0])
    - (OUTSIDE_DIA + max(OUTSIDE_DIA_BAND)) / 2.0
)
if CUTTER_SUPPORT_MARGIN_MIN <= 0.0:
    raise AssertionError("the accepted blank leaves the finite ground cutter support")
CUTTER_AXIS_R = STOCK_PROFILE.root_point(STOCK_PROFILE.root_half_angle_rad)[0] + CUTTER_DIA / 2.0
CUTTER_AXIS_Z = FULL_DEPTH
CUTTER_RUNOUT_END_Z = FULL_DEPTH + cutter_runout(
    CUTTER_DIA,
    JOURNAL_DIA / 2.0 - STOCK_PROFILE.root_point(STOCK_PROFILE.root_half_angle_rad)[0],
)
if not PINION_REAR_Z < CUTTER_RUNOUT_END_Z < HUB_BORE_FROM_F_WORST:
    raise AssertionError("the actual finite endcuts leave the thrust ring's span")


def gear_bearing_area_lower(profile: StockFormProfile, inner_radius: float) -> float:
    """Phase-independent tooth-end area outside an enclosing removed disk.

    The caller MUST include its edge break, relative-axis error and transverse
    fit float in ``inner_radius``. Rear finite terminal gaps are subsets of
    straight gaps, so this is also a conservative rear tooth-end lower bound.
    Area evaluation error is charged in the refusing direction twice.
    """
    if not math.isfinite(inner_radius) or inner_radius < 0.0:
        raise ValueError("bearing inner radius must be finite and nonnegative")
    if inner_radius >= profile.blank_radius_mm:
        return 0.0
    outer = math.pi * profile.blank_radius_mm**2 - TEETH * (
        profile.gap_area_mm2 + profile.gap_area_error_bound_mm2
    )
    inner = math.pi * inner_radius**2
    if inner_radius > profile.root_radius_min_mm:
        inner_profile = StockFormProfile(
            TEETH, CUTTER_TEMPLATE, inner_radius, profile.radial_translation_mm
        )
        inner -= TEETH * (
            inner_profile.gap_area_mm2 - inner_profile.gap_area_error_bound_mm2
        )
    return outer - inner


# The ring overlaps the slotted runout, not a full circular journal. Twelve
# retained tooth-centre caps still limit its offset: the nearest cap is at
# most half an index pitch from any offset direction. Charge pattern runout
# against the support radius before solving the exact chord enclosure.
_RING_CAP_R_MIN = JOURNAL_DIA_MIN / 2.0 - TOOTH_SPACE_RUNOUT_TIR_MM / 2.0
_RING_CAP_ANGLE = math.pi / TEETH
if not all(
    profile.contains_material(
        _RING_CAP_R_MIN * math.cos(_RING_CAP_ANGLE),
        _RING_CAP_R_MIN * math.sin(_RING_CAP_ANGLE),
    )
    for profile in _PROFILE_CORNERS
):
    raise AssertionError("the ring's declared retained journal caps are cut away")
RING_TRANSVERSE_FLOAT_MAX = math.sqrt(
    ((RING_ID + max(RING_ID_BAND)) / 2.0)**2
    - (_RING_CAP_R_MIN * math.sin(_RING_CAP_ANGLE))**2
) - _RING_CAP_R_MIN * math.cos(_RING_CAP_ANGLE)
REAR_BEARING_INNER_RADIUS_MAX = (
    (RING_ID + max(RING_ID_BAND)) / 2.0 + EDGE_BREAK_MAX
    + RING_TRANSVERSE_FLOAT_MAX + TOOTH_SPACE_RUNOUT_TIR_MM / 2.0
)
REAR_BEARING_AREA_MIN = min(
    gear_bearing_area_lower(profile, REAR_BEARING_INNER_RADIUS_MAX)
    for profile in _PROFILE_CORNERS
)
if REAR_BEARING_AREA_MIN <= 0.0:
    raise AssertionError("the loose rear ring has no actual tooth-end support")


def endcut_volume_bounds_mm3(
    *,
    profile: StockFormProfile = STOCK_PROFILE,
    face_width_mm: float = FACE_WIDTH,
    full_depth_mm: float = FULL_DEPTH,
    journal_radius_mm: float = JOURNAL_DIA / 2.0,
    rear_end_z_mm: float = REAR_END_Z,
    absolute_error_mm3: float = 0.02,
) -> tuple[float, float]:
    """ONE gap's extra rear endcut, excluding the straight0..FD pass.

    The front terminal cannot touch core, undercut or either allowed corner.
    The two rear stock intervals are disjoint at the actual gear rear.
    """
    if (
        profile.teeth != TEETH or profile.helix_angle_deg != 0.0
        or profile.template != CUTTER_TEMPLATE
    ):
        raise ValueError("knob endcut requires the declared straight stock master")
    if not 0.0 < full_depth_mm < face_width_mm < rear_end_z_mm:
        raise ValueError("invalid knob full-depth/gear/journal stations")
    bounds = tuple(
        cutter_end_volume_bounds_mm3(
            profile, CUTTER_DIA, outer_radius_mm=radius, inner_radius_mm=0.0,
            start_offset_mm=start, end_offset_mm=end,
            absolute_error_mm3=absolute_error_mm3 / 2.0,
        )
        for radius, start, end in (
            (profile.blank_radius_mm, 0.0, face_width_mm - full_depth_mm),
            (journal_radius_mm, face_width_mm - full_depth_mm, rear_end_z_mm - full_depth_mm),
        )
    )
    return (
        max(0.0, math.nextafter(math.fsum(row[0] for row in bounds), -math.inf)),
        math.nextafter(math.fsum(row[1] for row in bounds), math.inf),
    )


def expected_volume_bounds_mm3(*, absolute_error_mm3: float = 0.05) -> tuple[float, float]:
    """Complete NOMINAL shaft: true D, two neck fillets, actual rear endcuts.

    Thread uses the existing cosmetic-thread turned-blank convention.
    Nominal round fillets lie wholly inside the D-flat plane; the flat tool
    ends in neck air. Unsupported geometry refuses rather than fake volume.
    """
    r_core = CORE_DIA / 2.0
    flat = CORE_FLAT_FROM_AXIS
    r_neck = FRONT_RELIEF_DIA / 2.0
    radius = FRONT_CORNER_RADIUS
    if not (
        0.0 < flat < r_core and 0.0 < r_neck + radius < flat
        and 2.0 * radius < FRONT_RELIEF_WIDTH
    ):
        raise ValueError("nominal neck/D corner geometry leaves the exact volume domain")
    d_area = math.pi * r_core**2 - (
        r_core**2 * math.acos(flat / r_core)
        - flat * math.sqrt(r_core**2 - flat**2)
    )
    # Exact quarter-torus for each concave neck transition:
    # π∫[(r+R−sqrt(R²−u²))²−r²]du, u=0..R.
    fillets = 2.0 * math.pi * (
        (2.0 - math.pi / 2.0) * r_neck * radius**2
        + (5.0 / 3.0 - math.pi / 2.0) * radius**3
    )
    r_blank = THREAD_BLANK_DIA / 2.0
    turned = math.fsum((
        d_area * CORE_ACTIVE_LENGTH,
        math.pi * r_neck**2 * FRONT_RELIEF_WIDTH,
        fillets,
        math.pi * (RELIEF_DIA / 2.0)**2 * (PLAIN_CORE - CORE_FRONT_FROM_F),
        math.pi * r_blank**2 * (TIP_STATION - PLAIN_CORE)
        - math.pi * TIP_CHAMFER**2 * (r_blank - TIP_CHAMFER / 3.0),
        math.pi * STOCK_PROFILE.blank_radius_mm**2 * FACE_WIDTH,
        math.pi * (JOURNAL_DIA / 2.0)**2 * JOURNAL_LENGTH,
    ))
    end_lo, end_hi = endcut_volume_bounds_mm3(
        absolute_error_mm3=absolute_error_mm3 / TEETH
    )
    straight = TEETH * STOCK_PROFILE.gap_area_mm2 * FULL_DEPTH
    area_error = TEETH * STOCK_PROFILE.gap_area_error_bound_mm2 * FULL_DEPTH
    arithmetic_error = 512.0 * math.ulp(turned)
    return (
        math.nextafter(turned - straight - TEETH * end_hi - area_error - arithmetic_error, -math.inf),
        math.nextafter(turned - straight - TEETH * end_lo + area_error + arithmetic_error, math.inf),
    )

# The tip chamfer at its printed worst never grows past the one pitch the
# thumbnut's engagement budget already takes off for it (contract §7).
_CHAMFER_LOWER, _CHAMFER_UPPER = printed_deviations(TIP_CHAMFER, TIP_CHAMFER_PLACES)
TIP_CHAMFER_MAX = TIP_CHAMFER + _CHAMFER_UPPER
if TIP_CHAMFER_MAX > THREAD_PITCH + 1e-9:
    raise AssertionError(
        f"the stud tip chamfer can reach {TIP_CHAMFER_MAX:.2f}, past the one "
        f"pitch ({THREAD_PITCH:.2f}) the thumbnut engagement allows for it"
    )


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


DISC_NUMBER = "MHA-PD-006"
DISC_TEETH = DISC.TEETH
# Tooth system inputs are REF. The native span and accepted tip limits, not a
# generating-rack x or circular-thickness surrogate, control the real cutter.
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("MODULE (mm, REF)", f"{MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("CUTTER RADIAL SETTING (mm, REF)", f"{RADIAL_SETTING:+.3f}"),
        ("CONTROL", f"NATIVE PARALLEL-TANGENT SPAN {SPAN_TEETH} TEETH; MAXIMUM READING"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.2f}"),
        ("WHOLE DEPTH (mm, REF)", f"{WHOLE_DEPTH:.3f}"),
        ("CIRCULAR THICKNESS AT PD (mm, REF)", f"{TOOTH_THICKNESS:.3f}"),
        ("TOOTH FORM", "RIGID TRANSLATION OF FINITE STOCK #8 / TEMPLATE 12"),
        ("CUTTER RANGE", f"#{CUTTER_NUMBER}, {CUTTER_TOOTH_RANGE[0]}-{CUTTER_TOOTH_RANGE[1]}T"),
        ("QUALITY CLASS", "CONTACT CRITICAL"),
        ("INSPECTION PIN", f"SAME CERTIFIED {TOOTH_SPACE_GAUGE_PIN_DIA_MM:.3f} mm NOM; ACTUAL DIA"),
        ("INSPECTION", f"EACH {TEETH} TOOTHSPACES; FIXED RADIAL STATION"),
        ("UNCERTAINTY", "PIN / INDICATOR / DATUM INCLUDED IN TIR"),
        ("MATES WITH", f"DISC {DISC_NUMBER}, {DISC_TEETH}T"),
    ]
)

# The title block's 0.25 edge break is a sixth of this fine tooth's whole
# depth, so the sheet carries the one part-specific exception it needs.
TOOTH_EDGE_NOTE = "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
DRAWING_NOTES = "\n".join((
    TOOTH_EDGE_NOTE, CUTTER_NOTE,
    "FRONT D-CORE SOLID; COLLAR REAR FACE BEARS ON F. NO FRONT CROSS HOLE.",
))


# Two running surfaces: the journal in the plate bore and the core under the
# sliding collar.  Nothing else runs; the rest is the title block's process.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("journal", MACHINED_UM, CylinderFace(JOURNAL_DIA)),
    SurfaceFinishControl(
        "core",
        MACHINED_UM,
        CylinderFace(CORE_DIA, contains_z_mm=(CORE_FRONT_Z + CORE_REAR_Z) / 2.0),
    ),
)

# Standard full-length turned-core runout grade, not a new 5 micron grade:
# cad/docs/tolerance-gdt-assessment.md §5.2, total runout <=0.05 mm TIR.
PART_DATUMS = (
    PartDatum("A", CylinderFace(JOURNAL_DIA, contains_z_mm=CUP_FACE_Z / 2.0)),
)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "core_total_runout", "total_runout", GEOMETRIC_TOLERANCES_MM["core_total_runout"],
        CylinderFace(CORE_DIA, contains_z_mm=(CORE_FRONT_Z + CORE_REAR_Z) / 2.0), ("A",),
    ),
    GeometricControl(
        "front_neck_total_runout", "total_runout",
        GEOMETRIC_TOLERANCES_MM["front_neck_total_runout"],
        CylinderFace(FRONT_RELIEF_DIA, contains_z_mm=CORE_REAR_Z / 2.0), ("A",),
    ),
)

# --- Marked-dimension contract ------------------------------------------------
# ``StudProfile`` is the Right-plane revolve in front of F (the core, the
# thread relief, the thread blank and the tip chamfer); it also carries
# construction-only witnesses, the tooth-tip blank across the face (OutsideDia,
# rule 2's reference-sketch allowance) and the cutter's full-depth station and
# run-out limit from F (R9-21), so every turned size imports natively beside
# its axial extent.  ``JournalProfile`` is the revolve behind the teeth.
# ``GearBlank`` owns the face width.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "CoreFlatProfile": {"FlatToAxis", "FlatEnd", "FlatToolRadius"},
    "RootInspectionProfile": {"RootEnvelope"},
    "SpanProfile": {"ToothSpan"},
    "StudProfile": {
        "CoreDia",
        "CoreFront",
        "FrontReliefDia",
        "FrontReliefWidth",
        "FrontCornerRadius",
        "ReliefDia",
        "PlainCore",
        "ThreadBlankDia",
        "TipStation",
        "TipChamfer",
        "OutsideDia",
        "FullDepth",
        "CutterRunout",
    },
    "JournalProfile": {"JournalDia", "JournalLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": FACE_WIDTH_PLACES},
    "CoreFlatProfile": {
        "FlatToAxis": CORE_FLAT_PLACES,
        "FlatEnd": CORE_FLAT_CUT_END_PLACES,
        "FlatToolRadius": CORE_FLAT_TOOL_END_RADIUS_PLACES,
    },
    "RootInspectionProfile": {"RootEnvelope": ROOT_DIA_PLACES},
    "SpanProfile": {"ToothSpan": SPAN_PLACES},
    "StudProfile": {
        "CoreDia": CORE_DIA_PLACES,
        "CoreFront": CORE_FRONT_FROM_F_PLACES,
        "FrontReliefDia": FRONT_RELIEF_DIA_PLACES,
        "FrontReliefWidth": FRONT_RELIEF_WIDTH_PLACES,
        "FrontCornerRadius": FRONT_CORNER_RADIUS_PLACES,
        "ReliefDia": RELIEF_DIA_PLACES,
        "PlainCore": PLAIN_CORE_PLACES,
        "ThreadBlankDia": THREAD_BLANK_DIA_PLACES,
        "TipStation": TIP_STATION_PLACES,
        "TipChamfer": TIP_CHAMFER_PLACES,
        "OutsideDia": OUTSIDE_DIA_PLACES,
        "FullDepth": FULL_DEPTH_PLACES,
        "CutterRunout": CUTTER_RUNOUT_PLACES,
    },
    "JournalProfile": {
        "JournalDia": JOURNAL_DIA_PLACES,
        "JournalLength": JOURNAL_LENGTH_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(map(len, DRAWING_PRECISION.values())):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _names in DRAWING_PRECISION.items():
    if set(_names) != DRAWING_DIMENSIONS[_feature]:
        raise AssertionError(f"{_feature}: marked dimensions without places")
