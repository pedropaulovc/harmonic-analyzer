r"""MHA-PD-08 transgear-knob-shaft: the steel knob shaft with its integral pinion.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  ``build_pd_transgear_knob_shaft`` marks and tolerances exactly
``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model and
``draw_pd_transgear_knob_shaft`` keeps exactly the same names.

One turned SAE1018 shaft carries a standard-depth ``TEETH``-tooth 48DP PA20
integral pinion cut by the finite TTC stock form ``CUTTER_NUMBER``
(``CUTTER_SKU``, Ø44.45 cutter).
The gear front F and every chain/cup station remain unchanged.  Its front
Ø.191 solid D-core slides in the brass drive collar's round bore, and the
collar's pressed pin bears on the core's flat to drive it, without a cross
hole.  The collar's fitted rear face bears directly on F; the #8-32 stud
and same-outer custom thumbnut clamp it there, while the removable T24
still floats on the existing pilot and is driven by the two axial dowels.
The thread relief carries clamp, not torque.

The Ø.249 journal runs in the MHA-PD-28 bush's Ø.249 bore, reamed after the
bush is pressed into the arm plate.  The loose Ø.257-bore thrust ring bears
on the actual rear tooth ends.
Every gap is cut straight at full depth through the whole face (#2034); the
form root stands above the journal, so the cutter runs out in air over the
journal at the rear and over the neck and D-core at the front.  The journal
ends JOURNAL_STANDOUT behind the bush's rear face, inside the MHA-PD-16 cup's
pilot, and is tapped #2-56 on the axis in its rear end for the MHA-PD-VN-71
screw that holds the cup (owner ruling 2026-11-20 (Pedro), #2425).  No front
spring pin, cross hole or collar slot remains.

Part frame: the axis is local +Z through the origin (``Axis1``); +Z is
machine +Z (rearward), so the assembly places the part without rotation.  The
origin is F, the pinion's front face (machine z -148.1 at the stack pose,
R9-17): the teeth run z = 0..FACE_WIDTH, the journal FACE_WIDTH..REAR_END_Z,
the D-core CORE_FRONT_Z..CORE_REAR_Z, the front neck CORE_REAR_Z..0,
the thread relief THREAD_END_Z..CORE_FRONT_Z, and thread TIP_Z..THREAD_END_Z.
The indexed finite gap is centred on
GAP_AZIMUTH_DEG from local +X, CCW about +Z.

Named datums: ``Axis1`` (the shaft axis); ``Front Plane`` (F); planes
``PinionRear`` (the pinion's rear face, the thrust ring's seat), ``RearFace``
(the journal's rear end face), ``ThreadEnd`` (full thread ends) and
``StudTip`` (the tip face).

Decimal inch (#290): fabricated nominals are the exact millimetre values of
their printed inch sizes; the tooth form keeps its gear-derived values,
printed to the inch grid.
"""

from __future__ import annotations

import math

import pd_rack_pinion_spec as DISC
import _config

from _fit_close_running import SHAFT_G6_3_TO_6_MM
from _fit_deviations import deviations
from _gear_fit_limits import gear_tip_band_mm
from _gear_quality import (
    shaft_turned_runout_mm,
    toothspace_runout_tir_mm,
)
from paper_drive_stock_inspection import GaugeContact, toothspace_gauge_contact_mm
from _gtol_controls import GeometricControl, PartDatum
from _gtol_cylinder import CylinderFace
from _hole_spec import DRILL_POINT_H, THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, edge_break_chamfer_mm, printed_band_mm
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN, STACK_NAME
from pd_rack_pinion_spec import inch_ceil_mm, inch_floor_mm, inch_text
from _surface_finish import MACHINED_UM, SurfaceFinishControl
import pd_transgear_knob_bush_geometry as BUSH
from pd_transgear_knob_thrust_ring_spec import LENGTH as RING_LENGTH
from pd_transgear_knob_thrust_ring_spec import LENGTH_TOL as RING_LENGTH_TOL
from pd_transgear_knob_thrust_ring_spec import ID as RING_ID
from pd_transgear_knob_thrust_ring_spec import ID_BAND as RING_ID_BAND
from stock_form_cutter import (
    StockFormProfile,
    template_for_teeth,
    translation_for_tangent_span,
)

MM_PER_IN = 25.4
UNIT = drawing_unit("parts/pd-transgear-knob-shaft", _config.parts("pd-transgear-knob-shaft"))
EDGE_BREAK_MAX = edge_break_chamfer_mm(unit=UNIT)
ENGAGEMENT_FLOOR_D = 1.5

# --- Actual finite stock-form master, not an analytic generated shift -------
TEETH = DISC.MESH_PINION_TEETH
DIAMETRAL_PITCH = DISC.DIAMETRAL_PITCH
PRESSURE_ANGLE_DEG = DISC.PRESSURE_ANGLE_DEG
CUTTER_TEMPLATE = template_for_teeth(TEETH, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG)
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
RADIAL_SETTING = 0.266
_SPAN_DESIGN_SETTING_BAND = (0.005, -0.005)
# The disc's floor rule on the .0001 in grid (asserted below).
OUTSIDE_DIA = 8.97382  # .3533
OUTSIDE_DIA_BAND = gear_tip_band_mm("contact_critical")
OUTSIDE_DIA_PLACES = 4
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
# Outward onto the printed .0001 in grid.
SPAN_LIMITS = (
    inch_floor_mm(min(row[0] for row in _SPAN_CORNERS), SPAN_PLACES),
    inch_ceil_mm(max(row[1] for row in _SPAN_CORNERS), SPAN_PLACES),
)
SPAN_BAND = (SPAN_LIMITS[1] - SPAN_NOMINAL, SPAN_LIMITS[0] - SPAN_NOMINAL)
SPAN_DEVIATIONS = deviations(SPAN_BAND)
SPAN_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
SPAN_PREFIX = f"SPAN {SPAN_TEETH} TEETH "
_SPAN_SENSITIVITY = 2.0 * math.sin(math.pi * SPAN_TEETH / TEETH)
_SPAN_ROUNDING_ALLOWANCE = (
    10**-SPAN_PLACES * MM_PER_IN + 4.0 * _SPAN_GEOMETRY_ERROR
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
ROOT_DIA = 2.0 * STOCK_PROFILE.root_radius_min_mm
ROOT_DIA_PLACES = 3
ROOT_DIA_EXACT_MIN = min(2.0 * p.root_radius_min_mm for p in _PROFILE_CORNERS)
ROOT_DIA_MIN = inch_floor_mm(ROOT_DIA_EXACT_MIN, ROOT_DIA_PLACES)
# The root prints as a native MIN on a hidden Front-plane construction circle
# (RootProfile), the feed pinion's way: swTolType_e.swTolMIN prints the model
# value then "min.", so the modelled circle IS the printed limit.  The prefix
# lane replaces SolidWorks' own diameter symbol, so it carries it; the
# translated cutter's root arcs are not concentric, so the MIN bounds every
# root point and names itself an envelope.
ROOT_DIA_TOL_TYPE = 5  # swTolType_e.swTolMIN
ROOT_PREFIX = "ROOT ENVELOPE <MOD-DIAM>"
ROOT_DEPTH_X_MIN = min(
    p.root_point(p.root_half_angle_rad)[0] for p in _PROFILE_CORNERS
)
WHOLE_DEPTH = (OUTSIDE_DIA - ROOT_DIA) / 2.0
# The pinion's face width spaces F (its front face, the drive collar's seat)
# from the thrust ring: a term of the disc cluster's stack
# (transgear_cluster_fit) that sets the collar's air to the disc, so it
# prints .XXX at the cluster's +/-.001 (#2124).
FACE_WIDTH = 5.8928  # .232
FACE_WIDTH_PLACES = 3
FACE_WIDTH_BAND = FIT_LENGTH_BAND_IN
# drawing-guidelines rule 4: the band names the stack it serves and, by
# drawing number, the parts it stacks with to place F (transgear_cluster_fit
# F_CHAIN: the thrust ring's length and the MHA-PD-28 bush's hub face station).
FACE_WIDTH_CALLOUT = (
    f"{STACK_NAME} WITH\n"
    f"{_config.parts('pd-transgear-knob-thrust-ring')['number']}, "
    f"{_config.parts('pd-transgear-knob-bush')['number']}"
)
GAP_AZIMUTH_DEG = 180.0 / TEETH
# The assembly spins the shaft and its whole mounted front stack (collar,
# drive pins, wheel) about K so a pinion gap faces the reducer disc's tooth on
# the K -> S line (azimuth 180 + MESH_ANGLE_DEG from K): the nearest
# representative modulo one tooth pitch. The assembly drawing reads it to
# find the collar's rim seen edge-on.
_TOOTH_PITCH_DEG = 360.0 / TEETH
FRONT_STACK_PHASE_DEG = (180.0 + DISC.MESH_ANGLE_DEG - GAP_AZIMUTH_DEG) % _TOOTH_PITCH_DEG
if FRONT_STACK_PHASE_DEG > _TOOTH_PITCH_DEG / 2.0:
    FRONT_STACK_PHASE_DEG -= _TOOTH_PITCH_DEG
# --- #8-32 stud: passes the collar's round bore and its flat pin's crest ----
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
# Conservative thread-root estimate: a full basic half-depth below minimum 2A pitch.
THREAD_ROOT_2A_MIN = (THREAD_PD_2A_MIN_IN - 0.649519 / THREADS_PER_IN) * MM_PER_IN
# The #8-32 UNC-2A class (title block) governs the turned blank: the blank is
# printed as a reference nominal inside the 2A major window, and the window
# itself is the accepted blank (drawing-guidelines rule 2).
THREAD_BLANK_DIA = 4.064  # .160 (#290 fit F17)
THREAD_BLANK_DIA_PLACES = 3
THREAD_BLANK_LIMITS = THREAD_MAJOR_2A
if not THREAD_BLANK_LIMITS[0] < THREAD_BLANK_DIA < THREAD_BLANK_LIMITS[1]:
    raise AssertionError(
        f"MHA-PD-08 thread blank Ø{THREAD_BLANK_DIA:.3f} leaves the #8-32 UNC-2A "
        f"major {THREAD_MAJOR_2A[0]:.3f}..{THREAD_MAJOR_2A[1]:.3f}"
    )
# The tip chamfer runs 45 degrees down to the thread minor, so its size
# follows the as-turned blank rather than a printed three-place length.
TIP_CHAMFER = (THREAD_BLANK_DIA - THREAD_BASIC_MINOR) / 2.0
# The title block states the UN thread class, so the callout names no class;
# full thread runs to the relief, whose front shoulder is the PlainCore
# station (machinist review r8: the callout gave no thread length).
THREAD_CALLOUT = f"{THREAD} UNC\nTHREAD TO RELIEF"
TIP_CHAMFER_CALLOUT = "CHAMFER 45 DEG TO MINOR"
# The tip face is the stud chucking's faced end (rule 11): F prints as its
# station from the tip at the .XXX row (STUD_STATION_PLACES).  The thumbnut
# stack (the collar spec) still charges it the .XX row's ±.010
# (TIP_STATION_PLACES), a conservative band no tighter than the print.
TIP_STATION = 23.876  # .940
STUD_STATION_PLACES = 3
_STUD_STATION_BAND = printed_band_mm(STUD_STATION_PLACES, unit=UNIT)
TIP_STATION_PLACES = 2
if _STUD_STATION_BAND > printed_band_mm(TIP_STATION_PLACES, unit=UNIT):
    raise AssertionError("MHA-PD-08 prints F from the tip looser than its stacks charge")

# --- Solid D-core; no gear bore and no transverse torque hole ---------------
# Made to fit (fit audit 2026-11-23, pending owner confirmation; owner,
# 2026-11-23: "can the holes not be reamed in the first place").  The drive
# collar's bore is drilled #11 and this core is turned to slide in it by hand
# with no shake; the D-flat is then milled last, a little at a time, until the
# collar with its MHA-PD-VN-70 pin pressed slides on by hand.  Both sizes
# print as REF (.191, .084); the fit is the requirement (sheet note 2).  The
# nominals are the #11 drill's size and the flat the model is cut at.
#
# ANALYSIS numbers, never printed: what the stacks charge the two fits.
# - CORE_FIT_CLEARANCE: the diametral clearance a by-hand, no-shake slide
#   leaves in the actual bore, taken as wide as the reamed fit it replaces
#   allowed at its loosest (.0023).  What fails if it is .002 looser: the
#   collar, which seats the chain wheel, floats that much more on the core
#   (pd_transgear_drive_collar_spec.ROUND_FIT_FLOAT_MAX, charged to the root
#   corner air and the collar's bearing on F).
# - CORE_DIA_BAND: the core's size alone, for the stacks that read it without
#   the collar: the bore anywhere in the title block's DRILLED HOLES row
#   over the drill, less that clearance.  (upper, lower) about CORE_DIA.
# - CORE_FLAT_FIT_AIR: the radial air the flat's trial fit leaves under the
#   pin's crest, the collar centred: none to two cuts of the fitting step.
#   What fails if it is .002 looser: only the knob's lost motion grows
#   (pd-transgear-drive-collar RV-04); tighter, the crest binds on the flat.
# - CORE_FLAT_BAND: the flat as fitted, for the stacks that read it alone:
#   the collar's lowest crest less the widest air to its highest crest less
#   none (pd_transgear_drive_collar_spec asserts it against its own crest
#   limits, which this module cannot import).
CORE_DIA = 4.8514  # .191 REF: the collar's #11 drill
CORE_DIA_PLACES = 3
CORE_FIT_CLEARANCE = (0.0127, 0.05842)  # .0005 .. .0023 diametral, by feel
CORE_DIA_BAND = (
    drilled_oversize_mm(unit=UNIT) - min(CORE_FIT_CLEARANCE),
    -max(CORE_FIT_CLEARANCE),
)  # +.0035/-.0023, analysis only
CORE_FLAT_FROM_AXIS = 2.1336  # .084 REF
CORE_FLAT_PLACES = 3
CORE_FLAT_FIT_STEP = 0.0254  # .001: the most one fitting cut takes off
CORE_FLAT_FIT_AIR = (0.0, 2.0 * CORE_FLAT_FIT_STEP)  # 0 .. .002 radial
CORE_FLAT_BAND = (0.12065, -0.03429)  # +.00475/-.00135, analysis only
# The drawing's frames print GEOMETRIC_TOLERANCES_IN; readers take the
# derived mm.  The turned-shaft grade is the shared shaft_turned_runout_mm()
# on the .001 in grid (asserted below).
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "core_total_runout": ".002",
    "front_neck_total_runout": ".002",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * MM_PER_IN for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
CORE_TOTAL_RUNOUT = GEOMETRIC_TOLERANCES_MM["core_total_runout"]
if not math.isclose(
    CORE_TOTAL_RUNOUT,
    round(shaft_turned_runout_mm() / MM_PER_IN, 3) * MM_PER_IN,
    abs_tol=1e-9,
):
    raise AssertionError("knob shaft core runout is not the turned-shaft grade")
# Pattern runout is a toothspace inspection, not mounting plate position.
TOOTH_SPACE_RUNOUT_TIR_MM = toothspace_runout_tir_mm()
# The printed limit never exceeds the booked one: floored to the plain .001
# inch step (the shared grade is .002, delegated ruling 2026-11-07 (Main) F3).
TOOTH_SPACE_RUNOUT_TIR_TEXT = inch_text(inch_floor_mm(TOOTH_SPACE_RUNOUT_TIR_MM, 3), 3)
TOOTH_SPACE_GAUGE_PIN_DIA_MM = 1.016  # .040; use the actual certified diameter


def tooth_space_gauge_contacts(actual_pin_dia_mm: float) -> tuple[GaugeContact, ...]:
    """Qualify the actual certified pin against every accepted finite corner."""
    return tuple(
        toothspace_gauge_contact_mm(profile, actual_pin_dia_mm)
        for profile in _PROFILE_CORNERS
    )


_GAUGE_CORNERS = tooth_space_gauge_contacts(TOOTH_SPACE_GAUGE_PIN_DIA_MM)
TOOTH_SPACE_GAUGE_ROOT_AIR_MIN_MM = min(c.root_air_mm for c in _GAUGE_CORNERS)
TOOTH_SPACE_GAUGE_TIP_AIR_MIN_MM = min(c.tip_air_mm for c in _GAUGE_CORNERS)
# Spacing is held by the dividing head and is not inspected; one pin in
# every space on a radial indicator catches eccentricity and gross slips.
TOOTH_SPACE_CALLOUT_PROPERTY = "Tooth Space Inspection"
TOOTH_SPACE_CALLOUT = "\n".join(
    (
        f"TOOTH SPACE RUNOUT {TOOTH_SPACE_RUNOUT_TIR_TEXT} TIR TO A",
        f"\u00d8{inch_text(TOOTH_SPACE_GAUGE_PIN_DIA_MM, 3)} PIN, ALL {TEETH} SPACES",
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
# The core's front: printed as a station from the tip face (CORE_FRONT_FROM_
# TIP, .XXX), so from F it is the difference of two .XXX stations, at the
# .XX row's ±.010 (CORE_FRONT_FROM_F_PLACES, asserted below).  Its stacks
# (the collar's bore support and flat-pin engagement, the thumbnut's
# core-step air, the thread relief)
# all hold at that band.
CORE_FRONT_FROM_F = 5.334  # .21
CORE_FRONT_FROM_F_PLACES = 2
CORE_FRONT_FROM_TIP = TIP_STATION - CORE_FRONT_FROM_F  # .730

# Ordinary turned undercut at F: no tiny-radius grade or front disk cut.
# .155, not .157: paid the 0.05 tooth-space TIR under the earlier, smaller
# pinion.  The neck prints LIMITS .155/.150 (owner ruling, machinist review
# r8): the maximum keeps the neck's crown under the torqued core-flat plane,
# where the drive collar's pressed flat pin runs over it (the .XXX row would
# put the crown into that plane), and the minimum keeps the section that
# carries the drive torque (FRONT_RELIEF_AREA_MIN).
FRONT_RELIEF_DIA = 3.937  # .155
FRONT_RELIEF_DIA_PLACES = 3
FRONT_RELIEF_DIA_MAX = FRONT_RELIEF_DIA
FRONT_RELIEF_DIA_MIN = 3.81  # .150
FRONT_RELIEF_DIA_BAND = (0.0, FRONT_RELIEF_DIA_MIN - FRONT_RELIEF_DIA)
FRONT_RELIEF_DIA_TOL_TYPE = 3  # native LIMIT
FRONT_RELIEF_AREA_MIN = math.pi * FRONT_RELIEF_DIA_MIN**2 / 4.0
FRONT_RELIEF_WIDTH = 0.4064  # .016
FRONT_RELIEF_WIDTH_PLACES = 3
# The neck corners print R.004 MAX (rule 16): native swTolMAX prints the
# model value, so the modelled corner IS the largest acceptable radius.
FRONT_CORNER_RADIUS_MAX = 0.1016  # .004
FRONT_CORNER_RADIUS = FRONT_CORNER_RADIUS_MAX
FRONT_CORNER_RADIUS_PLACES = 3
FRONT_CORNER_RADIUS_BAND = (0.0, -FRONT_CORNER_RADIUS_MAX)
FRONT_CORNER_RADIUS_TOL_TYPE = 6  # swTolMAX: sharp up to R.004
FRONT_RELIEF_TOTAL_RUNOUT = GEOMETRIC_TOLERANCES_MM["front_neck_total_runout"]
FRONT_RELIEF_WIDTH_MIN = FRONT_RELIEF_WIDTH - printed_band_mm(
    FRONT_RELIEF_WIDTH_PLACES, unit=UNIT
)
FRONT_RELIEF_WIDTH_MAX = FRONT_RELIEF_WIDTH + printed_band_mm(
    FRONT_RELIEF_WIDTH_PLACES, unit=UNIT
)
CORE_ACTIVE_LENGTH = CORE_FRONT_FROM_F - FRONT_RELIEF_WIDTH  # REF only
CORE_ACTIVE_LENGTH_MIN = (
    CORE_FRONT_FROM_F - printed_band_mm(CORE_FRONT_FROM_F_PLACES, unit=UNIT)
    - FRONT_RELIEF_WIDTH_MAX
)
# Native cut-profile foremost point IS the actual physical rounded tool
# terminal, not an independently toleranced sketch centre plus a hidden R.
CORE_FLAT_CUT_END_FROM_F = 0.1016  # .004
CORE_FLAT_CUT_END_LIMITS = (0.0508, 0.1778)  # .002 .. .007
CORE_FLAT_CUT_END_BAND = (
    CORE_FLAT_CUT_END_LIMITS[1] - CORE_FLAT_CUT_END_FROM_F,
    CORE_FLAT_CUT_END_LIMITS[0] - CORE_FLAT_CUT_END_FROM_F,
)
CORE_FLAT_CUT_END_TOL_TYPE = 3
CORE_FLAT_CUT_END_PLACES = 3
CORE_FLAT_TOOL_END_RADIUS = 0.1016  # .004
CORE_FLAT_TOOL_END_RADIUS_MAX = 0.1016
CORE_FLAT_TOOL_END_RADIUS_BAND = (0.0, -CORE_FLAT_TOOL_END_RADIUS)
CORE_FLAT_TOOL_END_RADIUS_TOL_TYPE = 6
CORE_FLAT_TOOL_END_RADIUS_PLACES = 3
CORE_FLAT_GEAR_AIR_MIN = min(CORE_FLAT_CUT_END_LIMITS)
CORE_FLAT_REACH_PAST_SHOULDER_MIN = (
    FRONT_RELIEF_WIDTH_MIN - max(CORE_FLAT_CUT_END_LIMITS)
)
# The tool's rounded end lies in air under the neck floor.  Detail B prints
# both of its limits as the part's native FlatEnd (LIMIT, from F) and
# FlatToolRadius (MAX) dimensions, their values alone (a location prints its
# value and band).  Its reach past the core shoulder is the neck width's
# function (three places, the drawing's callout): the narrowest printed neck
# (FRONT_RELIEF_WIDTH_MIN) less the farthest allowed tool end is
# CORE_FLAT_REACH_PAST_SHOULDER_MIN, asserted below; the .XX row would leave
# none.
if (
    CORE_FLAT_GEAR_AIR_MIN < 0.050 - 1e-9
    or CORE_FLAT_REACH_PAST_SHOULDER_MIN < 0.100 - 1e-9
):
    raise AssertionError("the D-flat tool terminal violates its actual two-end reach limits")
if FRONT_RELIEF_WIDTH_MIN <= 2.0 * FRONT_CORNER_RADIUS_MAX:
    raise AssertionError("the front neck has no straight floor between its corner radii")

# --- Thread relief: single-point tool exit and thumbnut clearance (R9-53) ----
# Pedro's owner ruling 2026-11-05 (coordinator session): single-point the
# #8-32 UNC-2A thread on the lathe, not with a die. Full thread ends at
# PLAIN_CORE in front of F, on the relief's front shoulder, printed from the
# tip face (THREAD_END_FROM_TIP, .XXX) and so at the .XX row's band from F
# (PLAIN_CORE_PLACES). The relief provides a tool-exit space below the
# conservative thread-root estimate; the thumbnut at the collar's rearward
# stop runs on full thread or over that relief. Single-pointing removes the
# die's assumed 1.5-pitch lead requirement, not the functional relief or
# either shoulder station.
PLAIN_CORE = 7.62  # .30
PLAIN_CORE_PLACES = 2
THREAD_END_FROM_TIP = TIP_STATION - PLAIN_CORE  # .640
# Each F-referenced stud station is two .XXX stations from the tip apart, so
# its band is twice the .XXX row's: no wider than the .XX row its stacks
# (here, the collar's and the thumbnut's) charge.
if 2.0 * _STUD_STATION_BAND > min(
    printed_band_mm(CORE_FRONT_FROM_F_PLACES, unit=UNIT),
    printed_band_mm(PLAIN_CORE_PLACES, unit=UNIT),
) + 1e-9:
    raise AssertionError(
        "MHA-PD-08 core front or thread end from F, two .XXX stations from "
        "the tip, is looser than the band its stacks charge"
    )
# Ø.113 at the title block's .XXX row (.108-.118, #2419): the relief clears
# the thumbnut and lets the tool exit below the thread root, so its maximum
# stays under the root estimate (.11 at the .XX row would reach .120, over
# the .1196 root).  Its least is the stud's smallest section, where the
# threading load and the clamp both pass: the earlier Ø.10 at the .XX row
# (.090 at its least) sat .026 under the minor for no function.  Ø.108
# carries 1.7x the bending strength and 2.1x the stiffness of Ø.090.
RELIEF_DIA = 2.8702  # .113
RELIEF_DIA_PLACES = 3
RELIEF_DIA_MAX = RELIEF_DIA + printed_band_mm(RELIEF_DIA_PLACES, unit=UNIT)
RELIEF_DIA_MIN = RELIEF_DIA - printed_band_mm(RELIEF_DIA_PLACES, unit=UNIT)
_CORE_FRONT_TOL = printed_band_mm(CORE_FRONT_FROM_F_PLACES, unit=UNIT)
_PLAIN_CORE_TOL = printed_band_mm(PLAIN_CORE_PLACES, unit=UNIT)
RELIEF_WIDTH_MIN = (PLAIN_CORE - _PLAIN_CORE_TOL) - (
    CORE_FRONT_FROM_F + _CORE_FRONT_TOL
)  # .29 - .22 = .07
if RELIEF_WIDTH_MIN <= 0.0:
    raise AssertionError("MHA-PD-08 thread relief must separate the core and full thread")
if RELIEF_DIA_MAX > THREAD_ROOT_2A_MIN + 1e-9:
    raise AssertionError(
        f"MHA-PD-08 thread relief / root estimate: the largest relief "
        f"Ø{RELIEF_DIA_MAX:.3f} stands above the deepest thread-root estimate "
        f"Ø{THREAD_ROOT_2A_MIN:.3f}"
    )
# Nut clamp crosses the relief; drive torque enters the D-core behind it.
THREAD_STRESS_AREA = math.pi / 4.0 * (THREAD_MAJOR - 0.9743 * THREAD_PITCH) ** 2
RELIEF_AREA_MIN = math.pi / 4.0 * RELIEF_DIA_MIN**2
RELIEF_AREA_RATIO_MIN = RELIEF_AREA_MIN / THREAD_STRESS_AREA

# --- Journal: .249 g6 in the MHA-PD-28 bush's matching .249 reamed bore ------
# #290 fit D8 (owner ruling 2026-10-30: 6 mm -> .249): the bush (reamed after
# it is pressed into the arm plate) and the cup's pilot take the owned .2490
# reamer.
JOURNAL_DIA = 6.3246  # .249
JOURNAL_DIA_BAND = SHAFT_G6_3_TO_6_MM  # -.0002/-.0005
JOURNAL_DIA_PLACES = 4
# The cup's front face, from the pinion's rear face (R9-25): the thrust ring +
# the bush's hub face to rear face + the .008 end float, the cup running that
# far behind the bush's rear face at the stack pose.  The float is set at
# fit-up (owner ruling 2026-11-20 (Pedro), #2425): the cup's front face is
# faced until its pilot depth is the journal's measured stand-out less the
# float, and accepted within END_FLOAT_SET_TOL, so the journal's length does
# not enter it.
END_FLOAT = 0.2032  # .008
END_FLOAT_SET_TOL = 0.0508  # .002
CUP_FACE_STATION = RING_LENGTH + BUSH.LENGTH + END_FLOAT  # 1.418
# Where the fitter sets the cup on a real stack: the ring's and the bush's
# own bands, and the float's acceptance.
CUP_FACE_STATION_BAND = RING_LENGTH_TOL + BUSH.LENGTH_BAND + END_FLOAT_SET_TOL
# The journal ends JOURNAL_STANDOUT behind the bush's rear face at the stack
# pose: the cup's fitted pilot (.132, which centres the cup on the journal
# end) plus the float.  The rear chucking faces the rear end to the
# controlled overall length from the tip face (OVERALL_LENGTH, .XXX) and the
# pinion's rear face to the face width from F, so the journal (pinion rear
# face to rear end, REF) carries the overall's, F's (from the tip) and the
# face width's bands (#2169, Main delegated ruling 2026-11-04 under #989).
JOURNAL_STANDOUT = 3.556  # .140
JOURNAL_LENGTH = RING_LENGTH + BUSH.LENGTH + JOURNAL_STANDOUT  # 1.550 REF
JOURNAL_LENGTH_PLACES = 2
OVERALL_LENGTH_PLACES = 3  # controlled, tip face to rear face
_JOURNAL_LENGTH_BAND = (
    printed_band_mm(OVERALL_LENGTH_PLACES, unit=UNIT)
    + _STUD_STATION_BAND
    + FACE_WIDTH_BAND
)
# The stand-out on a real stack, the pinion pushed forward onto the ring and
# the ring onto the bush's hub face: the journal's, the ring's and the bush's
# bands.  The cup's facing at fit-up takes it up
# (pd_transgear_knob_cup_spec.FACING_REMOVAL, never negative only while the
# overall holds .XXX).
JOURNAL_STANDOUT_BAND = _JOURNAL_LENGTH_BAND + RING_LENGTH_TOL + BUSH.LENGTH_BAND
JOURNAL_DIA_MIN = JOURNAL_DIA + min(JOURNAL_DIA_BAND)

# --- Rear tap: the MHA-PD-VN-71 #2-56 on the axis -----------------------------
# Blind #2-56 UNC, drilled #50 and cut with the owned OSG bottoming tap
# (G9665591) in the journal's rear chucking, on the turned journal's own axis,
# so its wall pays no drill run-off.  Rule 12: the full thread prints as a
# MIN, the deeper tap drill as its own .XX depth; a bottoming tap's two-pitch
# lead stays inside the shallowest drill.
REAR_TAP_THREAD = "#2-56"
REAR_TAP_PITCH = MM_PER_IN / 56.0
REAR_TAP_FULL_THREAD_MIN = 8.636  # .34
REAR_TAP_DRILL_DIA = 1.778  # #50, .070
REAR_TAP_DRILL_DEPTH = 10.668  # .42
REAR_TAP_DRILL_DIA_PLACES = 3
REAR_TAP_DEPTH_PLACES = 2
REAR_TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    REAR_TAP_THREAD,
    end="blind",
    depth_mm=REAR_TAP_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": REAR_TAP_FULL_THREAD_MIN},
)
if blind_cut_dia_mm(REAR_TAP_SPEC) != REAR_TAP_DRILL_DIA:
    raise AssertionError("MHA-PD-08's rear tap drill is not the wizard's #50")
REAR_TAP_LEAD_ROOM_MIN = (
    REAR_TAP_DRILL_DEPTH
    - printed_band_mm(REAR_TAP_DEPTH_PLACES, unit=UNIT)
    - REAR_TAP_FULL_THREAD_MIN
    - 2.0 * REAR_TAP_PITCH
)
if REAR_TAP_LEAD_ROOM_MIN < 0.0:
    raise AssertionError("MHA-PD-08's rear tap drill leaves the bottoming tap no lead")
# Rule 17: the journal's wall over the thread's basic major, at the smallest
# g6 journal (.0813 against the .080 target).
REAR_TAP_WALL_WORST = (JOURNAL_DIA_MIN - THREAD_MAJOR_MM[REAR_TAP_THREAD]) / 2.0
if REAR_TAP_WALL_WORST < WALL_TARGET_MM - 1e-9:
    raise AssertionError(
        f"MHA-PD-08's journal wall over the rear tap {REAR_TAP_WALL_WORST:.4f} mm "
        "is under the .080 target"
    )
_REAR_TAP_R = REAR_TAP_DRILL_DIA / 2.0
REAR_TAP_VOLUME = math.pi * _REAR_TAP_R**2 * (
    REAR_TAP_DRILL_DEPTH + _REAR_TAP_R * DRILL_POINT_H / 3.0
)

# --- Rear end chamfer: the journal end seats flat on the cup's web ----------
# An explicit .015 X 45° (rule 16), not the title block's break: its least
# leg (.010) clears every point of the MHA-PD-16 pilot's R.005 MAX floor
# corner (a 45° chamfer of leg c clears a root fillet of radius r once
# c >= r; pd_transgear_knob_cup_spec asserts it), so the rear face, not its
# edge, bears on the web.  The chamfer stays inside the tap mouth's first
# pitch and break that the screw's engagement already discounts, so the tap's
# wall over its full thread is the full journal's.
REAR_CHAMFER = 0.381  # .015
REAR_CHAMFER_PLACES = 3
REAR_CHAMFER_MIN = REAR_CHAMFER - printed_band_mm(REAR_CHAMFER_PLACES, unit=UNIT)
REAR_CHAMFER_MAX = REAR_CHAMFER + printed_band_mm(REAR_CHAMFER_PLACES, unit=UNIT)
# Printed by its own sketch dimension (JournalProfile RearChamferSize, the
# axial leg), which the drawing places under the rear end with " X 45°" and
# the function of its third place (draw_pd_transgear_knob_shaft
# REAR_CHAMFER_FUNCTION).  .XXX: the title block's ±.005 holds .010-.020.
if REAR_CHAMFER_MAX > REAR_TAP_PITCH + EDGE_BREAK_MAX + 1e-9:
    raise AssertionError(
        "MHA-PD-08's rear chamfer runs past the tap mouth's discounted thread"
    )
# The rear face's flat land, between the chamfer and the tap mouth's break.
REAR_FACE_LAND_MIN = (
    JOURNAL_DIA_MIN / 2.0 - REAR_CHAMFER_MAX
    - (THREAD_MAJOR_MM[REAR_TAP_THREAD] / 2.0 + EDGE_BREAK_MAX)
)
if REAR_FACE_LAND_MIN <= 0.0:
    raise AssertionError("MHA-PD-08's rear face has no flat land on the cup's web")
REAR_CHAMFER_VOLUME = math.pi * REAR_CHAMFER**2 * (
    JOURNAL_DIA / 2.0 - REAR_CHAMFER / 3.0
)

# --- Local stations along +Z, from F ------------------------------------------
TIP_Z = -TIP_STATION
CORE_FRONT_Z = -CORE_FRONT_FROM_F
CORE_REAR_Z = -FRONT_RELIEF_WIDTH
CORE_FLAT_CUT_END_Z = -CORE_FLAT_CUT_END_FROM_F
THREAD_END_Z = -PLAIN_CORE
PINION_REAR_Z = FACE_WIDTH
CUP_FACE_Z = PINION_REAR_Z + CUP_FACE_STATION  # at the stack pose
REAR_END_Z = FACE_WIDTH + JOURNAL_LENGTH
OVERALL_LENGTH = REAR_END_Z - TIP_Z  # 2.722

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
        f"the journal must step up from the core and stay under the {TEETH}T"
    )

# --- Straight full-depth gaps through the face; actual Ø44.45 stock disk ---
# Owner ruling 2026-10-23 (#2034): every gap is one straight full-depth pass
# through FACE_WIDTH, the easiest set-up to machine; there is no rear endcut.
# The disk runs out in air at both ends: in front of F over the neck and the
# D-core (FRONT_NECK_AIR_MIN, FRONT_CORE_AIR_MIN above) and behind the rear
# face over the running journal, gated here.  The swept form's lowest point
# is the formed root, so the worst-case air over the largest g6 journal,
# charged with the tooth-space TIR to A (the journal itself) and the profile
# geometry error, is 0.280 over FRONT_CORE_AIR_MIN's 0.035 floor.
# TTC 10-289-487, 48DP PA20 #7 (14 to 16 T), the same Ø1-3/4 x 7/8-bore body
# as the #8 10-289-488; in stock at Travers, observed 2026-10-27:
# https://www.travers.com/product/ttc-10-289-487-involute-style-gear-cutter-10-289-487
CUTTER_DIA = 44.45
CUTTER_ARBOR_BORE = 22.225
CUTTER_SKU = "10-289-487"
JOURNAL_CUTTER_AIR_FLOOR = 0.035  # FRONT_CORE_AIR_MIN's floor
JOURNAL_CUTTER_AIR_MIN = (
    ROOT_DIA_EXACT_MIN - (JOURNAL_DIA + max(JOURNAL_DIA_BAND))
    - TOOTH_SPACE_RUNOUT_TIR_MM
) / 2.0 - max(p.geometry_error_bound_mm for p in _PROFILE_CORNERS)
if JOURNAL_CUTTER_AIR_MIN <= JOURNAL_CUTTER_AIR_FLOOR:
    raise AssertionError(
        f"the finite stock cutter running out behind the {TEETH}T leaves "
        f"{JOURNAL_CUTTER_AIR_MIN:.4f} over the journal, under the "
        f"{JOURNAL_CUTTER_AIR_FLOOR:.3f} floor"
    )
# Actual tooling fixture envelope, not a claimed purchased arbor SKU.
CUTTER_MOUNT_OD_MAX = 31.75
CUTTER_MOUNT_AIR_MIN = (
    CUTTER_DIA / 2.0 + ROOT_DEPTH_X_MIN - CUTTER_MOUNT_OD_MAX / 2.0
    - (OUTSIDE_DIA + max(OUTSIDE_DIA_BAND) + TOOTH_SPACE_RUNOUT_TIR_MM) / 2.0
)
if CUTTER_MOUNT_AIR_MIN <= 0.0:
    raise AssertionError("the actual arbor mounting envelope reaches shaft stock")

# The real tool master extends to its finite tip. Close the native tool only
# beyond the accepted blank; do not extend the working flank to fake support.
# The disc's convention: the finite translated tip VECTOR at the lowest
# accepted setting, less its numerical error, caps the blank (the master's
# reference tooth count is not this gear's, so its own tip radius is no bound).
_MIN_SETTING_SUPPORT = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, RADIAL_SETTING_LIMITS[0]
)
CUTTER_SUPPORT_MARGIN_MIN = (
    _MIN_SETTING_SUPPORT.support_radius_max_mm
    - _MIN_SETTING_SUPPORT.geometry_error_bound_mm
    - (OUTSIDE_DIA + max(OUTSIDE_DIA_BAND)) / 2.0
)
if CUTTER_SUPPORT_MARGIN_MIN <= 0.0:
    raise AssertionError("the accepted blank leaves the finite ground cutter support")
# OUTSIDE_DIA is the disc's floor rule (pd_rack_pinion_spec.OUTSIDE_DIA):
# the support diameter at the lowest accepted setting, less the numerical
# error and the + tip band, floored to the printed .0001 in. Its margin is
# that floor's remainder by construction; the gate claims containment, not
# clearance. The model support is the
# reference count's own tip circle, which the stock master must form to cut
# that standard gear, so the real ground form reaches at least this far.
# Inlined: the span limits that fix the lowest setting are built from
# OUTSIDE_DIA, so deriving it upstream would be circular.
_FLOOR_RULE_OUTSIDE_DIA = inch_floor_mm(
    2.0 * _MIN_SETTING_SUPPORT.support_radius_max_mm
    - 2.0 * _MIN_SETTING_SUPPORT.geometry_error_bound_mm
    - OUTSIDE_DIA_BAND[0],
    OUTSIDE_DIA_PLACES,
)
if not math.isclose(OUTSIDE_DIA, _FLOOR_RULE_OUTSIDE_DIA, abs_tol=1e-9):
    raise AssertionError(
        f"the {TEETH}T blank Ø{OUTSIDE_DIA} is not the floored cutter support "
        f"Ø{_FLOOR_RULE_OUTSIDE_DIA} (the disc's tip rule)"
    )


def gear_bearing_area_lower(profile: StockFormProfile, inner_radius: float) -> float:
    """Phase-independent tooth-end area outside an enclosing removed disk.

    The caller MUST include its edge break, relative-axis error and transverse
    fit float in ``inner_radius``. Every gap runs straight at full depth
    through the face, so the bound holds at the rear tooth ends as at F.
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


# The ring's bore runs over the full round journal: the straight-through
# cutter clears it (JOURNAL_CUTTER_AIR_MIN), so its true float is (ring ID
# max - journal min) / 2.  The bound kept here is wider, hence conservative:
# only TEETH tooth-centre caps at the journal's smallest radius less the
# pattern runout limit its offset, the nearest at most half an index pitch
# from any offset direction, solved as an exact chord enclosure.
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
if RING_TRANSVERSE_FLOAT_MAX < ((RING_ID + max(RING_ID_BAND)) - JOURNAL_DIA_MIN) / 2.0:
    raise AssertionError("the ring float bound is under its round-journal float")
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


def expected_volume_bounds_mm3() -> tuple[float, float]:
    """Complete NOMINAL shaft: true D, two neck fillets, straight full-face gaps.

    Thread uses the existing cosmetic-thread turned-blank convention; the
    rear Hole Wizard tap cuts its #50 drill (cylinder and 118 deg point).
    Nominal round fillets lie wholly inside the D-flat plane; the flat tool
    ends in neck air.  Every gap runs straight through FACE_WIDTH and its
    cutter run-out removes no neck, core or journal (FRONT_NECK_AIR_MIN,
    FRONT_CORE_AIR_MIN, JOURNAL_CUTTER_AIR_MIN), so the exact 2D gap area
    times the face width is the whole removal.  Unsupported geometry refuses
    rather than fake volume.
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
        -REAR_TAP_VOLUME,
        -REAR_CHAMFER_VOLUME,
    ))
    straight = TEETH * STOCK_PROFILE.gap_area_mm2 * FACE_WIDTH
    area_error = TEETH * STOCK_PROFILE.gap_area_error_bound_mm2 * FACE_WIDTH
    arithmetic_error = 512.0 * math.ulp(turned)
    return (
        math.nextafter(turned - straight - area_error - arithmetic_error, -math.inf),
        math.nextafter(turned - straight + area_error + arithmetic_error, math.inf),
    )


# The tip chamfer, cut to the minor of the largest accepted 2A blank, never
# grows past the one pitch the thumbnut's engagement budget already takes off
# for it (contract §7).
TIP_CHAMFER_MAX = (max(THREAD_BLANK_LIMITS) - THREAD_BASIC_MINOR) / 2.0
if TIP_CHAMFER_MAX > THREAD_PITCH + 1e-9:
    raise AssertionError(
        f"the stud tip chamfer can reach {TIP_CHAMFER_MAX:.2f}, past the one "
        f"pitch ({THREAD_PITCH:.2f}) the thumbnut engagement allows for it"
    )


# The drive collar MHA-PD-22: its round bore slides on the D-core and its
# pressed MHA-PD-VN-70 pin drives on the flat.
DRIVE_COLLAR_NUMBER = _config.parts("pd-transgear-drive-collar")["number"]


# One running surface: the journal in the MHA-PD-28 bush's bore.  The D-core is a
# sliding seat for the collar, not a running surface (rule 6), and the rest
# is the title block's process.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl(
        "journal", MACHINED_UM, CylinderFace(JOURNAL_DIA), display_unit=UNIT
    ),
)

# Standard full-length turned-core runout grade, not a new 5 micron grade:
# cad/docs/tolerance-gdt-assessment.md §5.2, total runout <=0.05 mm TIR (.002).
PART_DATUMS = (
    PartDatum("A", CylinderFace(JOURNAL_DIA, contains_z_mm=CUP_FACE_Z / 2.0)),
)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "core_total_runout", "total_runout", GEOMETRIC_TOLERANCES_IN["core_total_runout"],
        CylinderFace(CORE_DIA, contains_z_mm=(CORE_FRONT_Z + CORE_REAR_Z) / 2.0), ("A",),
    ),
    GeometricControl(
        "front_neck_total_runout", "total_runout",
        GEOMETRIC_TOLERANCES_IN["front_neck_total_runout"],
        CylinderFace(FRONT_RELIEF_DIA, contains_z_mm=CORE_REAR_Z / 2.0), ("A",),
    ),
)

# --- Marked-dimension contract ------------------------------------------------
# ``StudProfile`` is the Right-plane revolve in front of F (the core, the
# thread relief, the thread blank and the tip chamfer).  The stud chucking
# dimensions from its faced tip: F (TipStation), the core's front
# (CoreFromTip) and the thread's end (ThreadEndFromTip) are stations from
# the tip face.  It also carries two construction-only witnesses, the
# tooth-tip blank across the face (OutsideDia) and the controlled overall
# length from the tip face to the rear face (OverallLength) that the rear
# chucking faces to, drawing-simplicity-policy.md `How the repository
# implements the guidelines`'s reference-sketch allowance, so every turned
# size imports natively beside its axial extent.  ``CoreFlatProfile``
# carries the D-flat's in-air tool end (FlatEnd, FlatToolRadius).  The
# flat's distance from the axis (FlatToAxis) prints from
# ``CoreFlatReference``, a hidden Front-plane reference sketch driven by the
# same ``CoreFlat`` global, in the end view from the tip where the flat
# shows true.  The gear's acceptance prints natively in an enlarged view
# from the tip: ``SpanProfile`` carries the tangent span over two teeth as
# its driven LIMIT carrier, and ``RootProfile``, a hidden Front-plane
# construction circle, the root envelope's MIN.
# ``JournalProfile`` is the revolve behind the teeth; its length, the rest
# of the overall, prints as a reference.  ``GearBlank`` owns the face width,
# which is also the straight gaps' depth.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "CoreFlatProfile": {"FlatEnd", "FlatToolRadius"},
    "CoreFlatReference": {"FlatToAxis"},
    "SpanProfile": {"ToothSpan"},
    "RootProfile": {"RootDia"},
    "StudProfile": {
        "CoreDia",
        "CoreFromTip",
        "FrontReliefDia",
        "FrontReliefWidth",
        "FrontCornerRadius",
        "ReliefDia",
        "ThreadEndFromTip",
        "ThreadBlankDia",
        "TipStation",
        "OutsideDia",
        "OverallLength",
    },
    "JournalProfile": {"JournalDia", "JournalLength", "RearChamferSize"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": FACE_WIDTH_PLACES},
    "CoreFlatProfile": {
        "FlatEnd": CORE_FLAT_CUT_END_PLACES,
        "FlatToolRadius": CORE_FLAT_TOOL_END_RADIUS_PLACES,
    },
    "CoreFlatReference": {"FlatToAxis": CORE_FLAT_PLACES},
    "SpanProfile": {"ToothSpan": SPAN_PLACES},
    "RootProfile": {"RootDia": ROOT_DIA_PLACES},
    "StudProfile": {
        "CoreDia": CORE_DIA_PLACES,
        "CoreFromTip": STUD_STATION_PLACES,
        "FrontReliefDia": FRONT_RELIEF_DIA_PLACES,
        "FrontReliefWidth": FRONT_RELIEF_WIDTH_PLACES,
        "FrontCornerRadius": FRONT_CORNER_RADIUS_PLACES,
        "ReliefDia": RELIEF_DIA_PLACES,
        "ThreadEndFromTip": STUD_STATION_PLACES,
        "ThreadBlankDia": THREAD_BLANK_DIA_PLACES,
        "TipStation": STUD_STATION_PLACES,
        "OutsideDia": OUTSIDE_DIA_PLACES,
        "OverallLength": OVERALL_LENGTH_PLACES,
    },
    "JournalProfile": {
        "JournalDia": JOURNAL_DIA_PLACES,
        "JournalLength": JOURNAL_LENGTH_PLACES,
        "RearChamferSize": REAR_CHAMFER_PLACES,
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
