r"""Pure-data dimensional contract shared by the feed-pinion sleeve and its drawing.

The transgear pinion sleeve (MHA-PD-10, R9-68): one turned steel sleeve that
runs on the MHA-PD-23 pin's 1/8 shank and carries, rear to front, the
independent 12T 32DP PA20 finite stock-form feed pinion and the Ø.313 boss.
The pinion meshes the purchased standard platen rack. The brass hub
slides on the boss; its rear spigot passes through
the 120T disc's (MHA-PD-06) bore, which pilots on it, and seats its end on the
step face, so the step is the rear stop of hub and disc; the hub drives
through the boss's D-flat, which is drive only (its end wall stands behind
the hub's own flat and never touches it).  The hub's printed overall leaves
its front face never proud of the nose (``transgear_cluster_fit.RECESS_RANGE``),
so the MHA-PD-25 front bushing bears on the nose and traps hub and disc
against the step.  The rear face runs on the MHA-PD-24 rear bushing; both
bushings and the hub are lengths of the disc cluster's stack, its end float
shimmed at assembly (#2124; ``transgear_cluster_fit``, which reads this module).

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

Decimal inch (#290): fabricated nominals are the exact millimetre values of
their printed inch sizes; the tooth form keeps its gear-derived values.
"""

from __future__ import annotations

import math

import _config
import pd_rack_pinion_spec
import pd_transgear_pin_spec
from _fit_deviations import deviations
from _fit_ream_slide import REAM_SLIDE
from _gear_fit_limits import gear_tip_band_mm
from _gear_quality import toothspace_runout_tir_mm
from _gtol_cylinder import CylinderFace
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pd_rack_pinion_spec import inch_ceil_mm, inch_floor_mm, inch_text
from pd_transgear_disc_hub_geometry import SPIGOT_LENGTH, SPIGOT_LENGTH_BAND
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN
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

UNIT = drawing_unit(
    "parts/pd-transgear-feed-pinion", _config.parts("pd-transgear-feed-pinion")
)

# The part numbers the sheet names.  Hard-coded, not read from ``_config.parts``
# (dt_crank_pinion_spec's precedent: a registry read would make the part rows
# rebuild inputs of every importer); test_pd_transgear_feed_pinion_drawing checks
# them against the registry offline.
SLEEVE_NUMBER = "MHA-PD-10"
PIN_NUMBER = pd_transgear_pin_spec.PIN_NUMBER
HUB_NUMBER = "MHA-PD-17"
DISC_NUMBER = "MHA-PD-06"
RACK_NUMBER = "MHA-PD-05"
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
# the 11.40 minimum OD has contact ratio 1.215 by the closed form in
# paper_drive_mesh_check (translation treated as the untranslated involute
# with rack and tip moved in by s*cos(pi/N)), and stepping the generated flank
# through mesh agrees (test_paper_drive_mesh_check). Both clear 1.2; the
# interference margin is 0.070 mm. A smaller s raises contact ratio but
# brings the rack crest nearer the pinion's interference point.
RADIAL_SETTING = 0.210
_SPAN_DESIGN_SETTING_BAND = (0.010, -0.010)
# Gear geometry, kept at its design size and printed at four inch places
# (.4528, 0.0011 over the former 11.50) so the model is its printed value.
OUTSIDE_DIA = 11.50112  # .4528
OUTSIDE_DIA_PLACES = 4
# Standard tip grade, +0/-.004 (machinist review, stack6: +0/-0.02 on Ø11.500
# was over-specified). The tip only shortens the path of contact. At the
# 11.48 MIN of the old grade the rack mesh had CR 1.245, at 11.45 it has 1.234
# and at 11.40 it has 1.215: still above the 1.2 floor. Backlash, root air
# (0.499 against 0.25) and the interference margin do not depend on the tip.
GEAR_CONTACT_CLASS = "standard"
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
ROOT_DIA = 2.0 * STOCK_PROFILE.root_radius_min_mm
ROOT_DIA_PLACES = 3
# A native physical lower-limit witness owns the wall floor. Translated root
# arcs are not concentric; deepest ground X is a distinct run-out quantity.
ROOT_DIA_MIN = inch_floor_mm(
    min(2.0 * profile.root_radius_min_mm for profile in _PROFILE_CORNERS),
    ROOT_DIA_PLACES,
)
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
# The printed limit never exceeds the booked one: floored to four inch places.
TOOTH_SPACE_RUNOUT_TIR_TEXT = inch_text(inch_floor_mm(TOOTH_SPACE_RUNOUT_TIR_MM, 4), 4)
if not math.isfinite(TOOTH_SPACE_RUNOUT_TIR_MM) or TOOTH_SPACE_RUNOUT_TIR_MM <= 0.0:
    raise ValueError("feed toothspace inspection requires a positive configured TIR limit")
# The actual rear-face flank edge of the indexed straight stock pass.
TOOTH_SPACE_INSPECTION_PHASE_RAD = math.pi / TEETH
TOOTH_SPACE_INSPECTION_END_MM = 0.0

for _profile in _PROFILE_CORNERS:
    _profile.require_tip_land(0.25 * MODULE_MM)
    toothspace_gauge_contact_mm(_profile, TOOTHSPACE_GAUGE_DIA_MM)
    _tip_air = (
        math.hypot(*_profile.flank_point(CUTTER_TEMPLATE.flank_parameter_max))
        - _profile.blank_radius_mm
    )
    if _tip_air <= _profile.geometry_error_bound_mm:
        raise AssertionError("finite ground tip/closure reaches the accepted blank")


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
# The overall and the tooth length are terms of the disc cluster's stack
# (transgear_cluster_fit): the overall sets the hub's recess behind the nose,
# the tooth length's end is the step face the hub's spigot seats on.  The
# shims set the end float (owner ruling 2026-11-01, #2124); the recess still
# needs both, so they print +/-.001.
# STATION_TOL is the allowance the flat's reach and the hub's flat-end check
# keep on the sleeve's other stations (R9-5's former overall band).
STATION_TOL = 0.0508  # .002
STATION_PLACES = 3
FACE_WIDTH = 13.589  # .535, the tooth length: rear face to the step onto the boss
FACE_WIDTH_PLACES = 3
FACE_WIDTH_BAND = FIT_LENGTH_BAND_IN
OVERALL_LENGTH = 27.3558  # 1.077
OVERALL_LENGTH_BAND = FIT_LENGTH_BAND_IN

# --- diameters -----------------------------------------------------------------
# The boss is the hub's locating fit: turned .313 +.0005/.0000 under the
# hub's .313 +.0010/+.0005 bore, .0000-.0010 diametral clearance, the
# locational feel of the old H7/h6 pair (InchPd ruling, fit doc F12 note;
# pd_transgear_disc_hub_spec consumes this diameter and checks the pair).
BOSS_DIA = 7.9502  # .313
BOSS_DIA_BAND = (0.0127, 0.0)  # (upper, lower) deviations: +.0005/.0000
BOSS_DIA_PLACES = 4

# --- the step face: the hub's seat ----------------------------------------------
# The hub's spigot bears on the step face's tooth ends, so the face is held
# square to the bore (datum A), faced in the setup that reams the bore; the
# zone is the face's extent, the 12T's tip circle.
BORE_DATUM = "A"
# Spacing is held by the dividing head and is not inspected; one pin in
# every space on a radial indicator catches eccentricity and gross slips.
TOOTH_SPACE_CALLOUT_PROPERTY = "Tooth Space Inspection"
TOOTH_SPACE_CALLOUT = "\n".join(
    (
        f"TOOTH SPACE RUNOUT {TOOTH_SPACE_RUNOUT_TIR_TEXT} TIR TO {BORE_DATUM}",
        f"\u00d8{inch_text(TOOTHSPACE_GAUGE_DIA_MM, 4)} PIN, ALL {TEETH} SPACES",
    )
)
# The frame prints GEOMETRIC_TOLERANCES_IN; readers take the derived mm.
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "step face perpendicularity to bore": ".0002",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * MM_PER_IN for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
STEP_FACE_PERPENDICULARITY = float(
    GEOMETRIC_TOLERANCES_MM["step face perpendicularity to bore"]
)
STEP_FACE_PERPENDICULARITY_ZONE_DIA = OUTSIDE_DIA

# --- D-flat (local -Y): drive only ------------------------------------------------
# The hub drives through it.  The flat plane prints from the boss axis at
# .138 0/-.0006: the hub's flat sits .0008...0020 off it (the hub owns its
# band and checks the pair).
FLAT_TO_AXIS = 3.5052  # .138
FLAT_TO_AXIS_BAND = (0.0, -0.01524)  # (upper, lower) deviations: 0/-.0006
FLAT_TO_AXIS_PLACES = 4
FLAT_DEPTH = BOSS_DIA / 2.0 - FLAT_TO_AXIS  # .0185
# The flat runs from the nose rearward to an end wall at FLAT_END_STATION,
# cut by an end mill on an axis parallel to the sleeve's, plunged from the
# nose.  The wall stops nothing: the hub's flat starts at its flange's rear
# face, the spigot's length ahead of the step, so the wall stands clear
# behind it (pd_transgear_disc_hub_spec.FLAT_END_CLEARANCE_WORST), and it
# stays clear of the step the hub's spigot seats on, so the flat never
# notches that face.  Those are its only functions, so it prints as limits
# at two inch places (2026-10-27 ENFORCE review: ±0.05 was unneeded
# precision; codjiflo P1 on 65a022125: a MAX alone left the step unguarded).
# The MAX is the modelled station.  The MIN stands behind the longest tooth
# length plus the title block's .010 edge break, and behind the cutter's
# run-out (asserted below).  The hub's check keeps its conservative
# STATION_TOL allowance on top of the MAX.  The MAX stands far enough behind
# the hub's flat that the title block's R.040 inside corner, where the
# flat's floor meets the wall, stays under the flats' .0008 minimum clearance
# where the hub's flat starts (codjiflo P2 on edb402b/482fbdc: at 16.6 an
# R1.0 corner rose 0.21 there; #2006).  The drawing test holds that envelope.
FLAT_END_STATION = 16.002  # .63
FLAT_END_MIN = 13.97  # .55
FLAT_END_PLACES = 2
FLAT_END_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
FLAT_LENGTH = OVERALL_LENGTH - FLAT_END_STATION  # .447
# The reach the end mill's flutes must cover: the flat cut to its MAX
# station on the longest sleeve.  Stopping there is always accepted; a
# longer flat, toward the MIN, is the shop's choice of a longer cutter.
FLAT_REACH = OVERALL_LENGTH + STATION_TOL - FLAT_END_STATION  # .449
FLAT_CUTTER_FLUTE_MIN = 12.0
if FLAT_CUTTER_FLUTE_MIN < FLAT_REACH + 0.5:
    raise AssertionError("the flat's end mill cannot reach the end wall on its flutes")
for _limit in (FLAT_END_MIN, FLAT_END_STATION):
    if not math.isclose(inch_floor_mm(_limit, FLAT_END_PLACES), _limit, abs_tol=1e-9):
        raise AssertionError("a flat end limit does not print at its places")

# .125 REAM_SLIDE bore (an owned .1260 reamer) on the MHA-PD-23 1/8 pin's
# +.0001/-.0002: .0009...0017 diametral clearance.  The true finite root at
# every radial-setting corner retains the .080 wall.
BORE_DIA = pd_transgear_pin_spec.DIA
BORE_DIA_BAND = REAM_SLIDE  # (upper, lower): +.0015/+.0010
BORE_PLACES = 4
_PIN_UPPER, _PIN_LOWER = pd_transgear_pin_spec.DIA_BAND
BORE_DIAMETRAL_CLEARANCE = (
    round(BORE_DIA_BAND[1] - _PIN_UPPER, 6),
    round(BORE_DIA_BAND[0] - _PIN_LOWER, 6),
)
if BORE_DIAMETRAL_CLEARANCE[0] <= 0.0:
    raise AssertionError(f"sleeve bore binds on the pin: {BORE_DIAMETRAL_CLEARANCE}")
BORE_PROCESS_CALLOUT = "REAM THRU"
# The bore's fit prints under its size on the section's own dimension, as
# the boss's does: a separate fit note crowded the end view (run
# 20261101T054343686Z failed the layout audit on it).
BORE_FIT_CALLOUT = "\n".join(
    (
        f"MATE PIN {PIN_NUMBER},",
        f"{inch_text(BORE_DIAMETRAL_CLEARANCE[0], 4)}-"
        f"{inch_text(BORE_DIAMETRAL_CLEARANCE[1], 4)} DIA CLR",
    )
)
BORE_CALLOUT = f"{BORE_PROCESS_CALLOUT}\n{BORE_FIT_CALLOUT}"

# --- the hub and disc on the step ------------------------------------------------
# The hub's spigot seats on the step face and passes the disc's bore; the
# hub's flange clamps the disc's front face, so that face stands the
# spigot's length ahead of the step and the disc's rear face stands in air
# ahead of it, the spigot's length less the disc's thickness (.026 nominal;
# the hub's spec takes the worst case with the tilts).  The disc's bore is
# the spigot's, outside the 12T's tips, so the two never overlap radially.
DISC_THICKNESS = pd_rack_pinion_spec.FACE_WIDTH
DISC_FRONT_STATION = FACE_WIDTH + SPIGOT_LENGTH  # .679, the hub flange's seat
DISC_FRONT_STATION_BAND = FACE_WIDTH_BAND + SPIGOT_LENGTH_BAND
DISC_REAR_STATION = DISC_FRONT_STATION - DISC_THICKNESS  # .561
DISC_REAR_MIN = (
    DISC_FRONT_STATION - DISC_FRONT_STATION_BAND - pd_rack_pinion_spec.FACE_WIDTH_MAX
)
if pd_rack_pinion_spec.BORE_DIA_MIN <= OUTSIDE_DIA + OUTSIDE_DIA_BAND[0]:
    raise AssertionError("the disc's bore overlaps the 12T's tips radially")

# --- Physical finite-disc cutter run-out (R9-67) -------------------------------
# A straight pass from the rear face stops at FULL_DEPTH; the actual disc
# cutter then leaves its revolved finite ground-form end envelope. The
# remaining face has partial-depth gaps, not full-depth analytic teeth.
# CUTTER_RUNOUT_MAX is the retained native maximum station; the geometric
# endpoint over the boss uses the deepest template X, never a root norm.
# The full depth has one function, covering the rack (the assembly's
# RACK_FRONT_FROM_SLEEVE_REAR_WORST), so it prints as a MIN at the modelled
# station; the run-out MAX caps how deep the cutter may go (2026-10-27
# ENFORCE review, r1, r3: a three-place hold served nothing).  Any cutter's
# full depth stands behind its own run-out, so the print bounds it only by
# that MAX (FULL_DEPTH_MAX, below).
FULL_DEPTH = 10.16  # .400
FULL_DEPTH_PLACES = 3
FULL_DEPTH_TOL_TYPE = 5  # swTolType_e.swTolMIN
FULL_DEPTH_DEVIATIONS = (0.0, 0.0)
FULL_DEPTH_MIN = FULL_DEPTH
CUTTER_RUNOUT_MAX = 13.7922  # .543 from the rear face, a limit
CUTTER_RUNOUT_PLACES = 3
CUTTER_DIA_MAX_IN = 2.25
CUTTER_DIA_MAX = CUTTER_DIA_MAX_IN * MM_PER_IN
CUTTER_SKU = "10-289-328"
# swTolMAX prints the dimension's NOMINAL followed by "MAX", so the witness
# sits at the limit; its deviations record "anywhere behind the shortest full
# depth, up to the limit".
CUTTER_RUNOUT_TOL_TYPE = 6  # swTolType_e.swTolMAX
CUTTER_RUNOUT_DEVIATIONS = (FULL_DEPTH_MIN - CUTTER_RUNOUT_MAX, 0.0)
FLAT_END_DEVIATIONS = (FLAT_END_MIN - FLAT_END_STATION, 0.0)
_TITLE_BLOCK_EDGE_BREAK = edge_break_chamfer_mm(unit=UNIT)
if FLAT_END_MIN < max(
    FACE_WIDTH + FACE_WIDTH_BAND + _TITLE_BLOCK_EDGE_BREAK, CUTTER_RUNOUT_MAX
):
    raise AssertionError("the flat's end wall may notch the step or the run-out")
if not math.isclose(
    inch_floor_mm(CUTTER_RUNOUT_MAX, CUTTER_RUNOUT_PLACES), CUTTER_RUNOUT_MAX, abs_tol=1e-9
):
    raise AssertionError("the run-out limit does not print at its places")
# The outside view's cutter-station witnesses run along the floor of the
# gap that faces it (model 195°, a gap centre, seen from -X): the section
# B-B plane passes through teeth, so neither station has an edge there.
GAP_FLOOR_WITNESS_Y = -(ROOT_DIA_MIN / 2.0) * math.sin(math.pi / TEETH)
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
# With only the MIN printed, any cutter of the form may be used: a smaller
# one, or a shallower accepted profile, runs out sooner and so cuts full
# depth further forward.  Over every accepted part the full depth and the
# cutter's end are bounded only by the run-out MAX (codjiflo P2, 0247213),
# and the hub's round engagement and seat take them there.
FULL_DEPTH_MAX = CUTTER_RUNOUT_MAX
CUTTER_RUNOUT_END_WORST = CUTTER_RUNOUT_MAX
RUNOUT_DISC_CLEARANCE = 0.0508  # .002
if FULL_DEPTH_MIN + cutter_runout(CUTTER_DIA_MAX, RUNOUT_RISE_WORST) > CUTTER_RUNOUT_MAX:
    raise AssertionError("the largest cutter at the full-depth MIN overruns the run-out MAX")
if FULL_DEPTH_MIN >= FACE_WIDTH - FACE_WIDTH_BAND:
    raise AssertionError("the 12T full-depth MIN reaches the step")
if CUTTER_RUNOUT_MAX > DISC_REAR_MIN - RUNOUT_DISC_CLEARANCE + 1e-9:
    raise AssertionError("the run-out limit reaches the disc's rear face")

# --- oil hole (R9-8) -----------------------------------------------------------
# A #57 drill (.043, +.004/0) on +Y, centred on the hub body (R9-60), through hub
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

# --- walls (drawing-guidelines.md rule 17 (walls and webs): target .080, floor .060, at the printed bands) --------------
WALL_TARGET = WALL_TARGET_MM
WALL_FLOOR = WALL_FLOOR_MM
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
# The D-flat wall (.138 flat over the .125 bore, both contract fits) sits
# under the .080 target and keeps the .060 floor: owner minor RV-03.
FLAT_WALL = FLAT_TO_AXIS - BORE_DIA / 2.0
FLAT_WALL_WORST = round(FLAT_TO_AXIS + FLAT_TO_AXIS_BAND[1] - _BORE_MAX / 2.0, 6)
FLAT_WALL_PRINTED = inch_floor_mm(FLAT_WALL_WORST, 3)  # .074
if FLAT_WALL_WORST < WALL_FLOOR:
    raise AssertionError(f"the D-flat wall {FLAT_WALL_WORST:.3f} is under the floor")

# One roughness, on the one running surface: the bore.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE_DIA), display_unit=UNIT),
)

# --- Marked-dimension contract -------------------------------------------------
# ``GearBlank`` is the tooth blank's extrude (its depth is the tooth length).
# ``SleeveProfile`` is the Right-plane revolve of the boss, with
# construction-only witnesses for the tooth tip and the bore, so every turned
# diameter prints beside its axial extent on the longitudinal section
# (drawing-simplicity-policy.md `How the repository implements the guidelines` and drawing-guidelines.md rule 11 (turned parts read like the lathe)), and for the cutter's full-depth station and
# its run-out limit (R9-67), which run along the facing gap's floor
# (GAP_FLOOR_WITNESS_Y) and print on an outside view in the section's
# direction.  Lengths are baselined from the rear face.
# ``RootProfile`` is a construction circle on the Front plane (the rear face)
# at the root's MIN: the root prints on the rear-face view, where the
# full-depth gaps show their floors (the section cuts through teeth).
# ``FlatProfile`` is the flat's cut sketch on the Right plane (the section
# plane): the flat from the axis and its end wall from the rear face print on
# the section, where the flat shows edge-on.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "SleeveProfile": {
        "OutsideDia",
        "BoreDia",
        "BossDia",
        "OverallLength",
        "FullDepth",
        "CutterRunout",
    },
    "RootProfile": {"RootDia"},
    "FlatProfile": {"FlatToAxis", "FlatEnd"},
    "SpanProfile": {"ToothSpan"},
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": FACE_WIDTH_PLACES},
    "SleeveProfile": {
        "OutsideDia": OUTSIDE_DIA_PLACES,
        "BoreDia": BORE_PLACES,
        "BossDia": BOSS_DIA_PLACES,
        "OverallLength": STATION_PLACES,
        "FullDepth": FULL_DEPTH_PLACES,
        "CutterRunout": CUTTER_RUNOUT_PLACES,
    },
    "RootProfile": {"RootDia": ROOT_DIA_PLACES},
    "FlatProfile": {
        "FlatToAxis": FLAT_TO_AXIS_PLACES,
        "FlatEnd": FLAT_END_PLACES,
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
        ("PITCH DIAMETER (REF)", inch_text(PITCH_DIA, 4)),
        ("WHOLE DEPTH (REF)", inch_text(WHOLE_DEPTH, 4)),
        ("CUTTER", f"#{CUTTER_NUMBER}, {CUTTER_TOOTH_RANGE[0]}-{CUTTER_TOOTH_RANGE[1]}T"),
        (
            f"SPAN OVER {SPAN_TEETH} TEETH",
            f"{inch_text(min(SPAN_LIMITS), SPAN_PLACES)}-{inch_text(max(SPAN_LIMITS), SPAN_PLACES)}",
        ),
        ("MATES WITH", f"PLATEN RACK {RACK_NUMBER}"),
    ]
)

# The title block's .010 edge break is 14% of this fine tooth's whole depth,
# and the tooth ends seat the hub's spigot.  The drawing flags it at the
# teeth with a leader (rule 7; 2026-10-27 ENFORCE review, r2, r3: loose in
# the notes block it reached no feature), so the notes block omits it.
TOOTH_EDGE_NOTE = "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
# Emits approved declaration pd-transgear-feed-pinion RV-03 (owner ruling
# 2026-10-27, #1378).
# A shop note states the requirement, not the measuring method or the cutter
# choice (Main ruling 2026-10-10): the run-out length is dimensioned.
FLAT_WALL_NOTE = f"D-FLAT WALL TO BORE {inch_text(FLAT_WALL_PRINTED, 3)} MIN."
DRAWING_NOTES = FLAT_WALL_NOTE
