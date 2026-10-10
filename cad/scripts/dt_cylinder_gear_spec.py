r"""Pure-data dimensional contract for the cylinder gear and its drawing.

The tooth system and ordinary blank, cam and notch geometry are shared by
part and assembly recipes. General drawing prose lives in
``dt_cylinder_gear_notes``; this spec owns the separate BASIC pattern locator
and its manufacturing callout. The published angular grade is read lazily
when the drawing is requested, never while importing the mechanical spec.
"""

from __future__ import annotations

import math

import _config
import dt_cylinder_gear_shaft_spec as arbor

from _fit_limits import deviations
from _gear_fit_limits import gear_tip_band_mm
from _printed_tolerance import printed_deviations
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from stock_form_cutter import CutterTemplate, StockFormProfile


MM_PER_IN = 25.4

# --- gear tooth system (build_dt_cylinder_gear.py / gear_train.yaml) ------------
TEETH = int(_config.machine("gear_train", "cylinder_teeth"))
DIAMETRAL_PITCH = _config.machine("gear_train", "diametral_pitch")
PRESSURE_ANGLE_DEG = float(_config.machine("gear_train", "pressure_angle_deg"))
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH * MODULE_MM
OUTSIDE_DIA_BAND = gear_tip_band_mm("contact_critical")
DEDENDUM_FACTOR = 1.25  # reference cutter root, not a gear-axis circular floor
CUTTER_NUMBER = 2
CUTTER_TEETH_RANGE = (55, 134)
CUTTER_REFERENCE_TEETH = CUTTER_TEETH_RANGE[0]
CUTTER_TEMPLATE = CutterTemplate(
    CUTTER_REFERENCE_TEETH, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG
)
CUTTER_RADIAL_TRANSLATION_MM = PITCH_DIA / 2.0 - CUTTER_TEMPLATE.pitch_radius_mm
_SUPPORT_PROFILE = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, PITCH_DIA / 2.0, CUTTER_RADIAL_TRANSLATION_MM
)
SUPPORT_OUTSIDE_DIA_MM = 2.0 * _SUPPORT_PROFILE.support_radius_max_mm
WHOLE_DEPTH_PLACES = 3
WHOLE_DEPTH_BAND = (0.05, 0.0)  # retained (upper, lower) plunge requirement
# A printed plunge can round upward by half its final decimal.  Pay that
# plus the full depth band before choosing the native two-place blank.
_DEPTH_SUPPORT_PROFILE = StockFormProfile(
    TEETH,
    CUTTER_TEMPLATE,
    PITCH_DIA / 2.0,
    CUTTER_RADIAL_TRANSLATION_MM
    - WHOLE_DEPTH_BAND[0]
    - 0.5 * 10.0**-WHOLE_DEPTH_PLACES,
)
MAX_DEPTH_SUPPORT_OUTSIDE_DIA_MM = 2.0 * _DEPTH_SUPPORT_PROFILE.support_radius_max_mm
OUTSIDE_DIA = math.floor(
    (MAX_DEPTH_SUPPORT_OUTSIDE_DIA_MM - OUTSIDE_DIA_BAND[0]) * 100.0
) / 100.0
STOCK_FORM = StockFormProfile(
    TEETH, CUTTER_TEMPLATE, OUTSIDE_DIA / 2.0, CUTTER_RADIAL_TRANSLATION_MM
)
ROOT_ENVELOPE_DIA_MM = (
    2.0 * STOCK_FORM.root_radius_min_mm,
    2.0 * STOCK_FORM.root_radius_max_mm,
)
WHOLE_DEPTH = STOCK_FORM.plunge_mm
MAX_CUT_DEPTH_MM = STOCK_FORM.blank_radius_mm - STOCK_FORM.root_radius_min_mm
PITCH_TOOTH_THICKNESS_MM = STOCK_FORM.pitch_tooth_thickness_mm

# --- machinable blank (build_dt_cylinder_gear.py) ------------------------------
BORE_DIAMETRAL_CLEARANCE_MM = (0.030, 0.070)  # (minimum, maximum), matched fit
# Representative finished geometry at the midpoint of the matched running fit.
# Manufacturing still matches every bore to the actual finished arbor.
BORE_DIA = arbor.SHAFT_DIA + sum(BORE_DIAMETRAL_CLEARANCE_MM) / 2.0
FACE_WIDTH = 3.0
# Face width controls mesh engagement across the mating cone-gear family.
FACE_WIDTH_TOLERANCE_MM = 0.05
CAM_DIA = 30.6  # integral eccentric cam disc
CAM_DIA_BAND = (0.0, -0.05)  # (upper, lower) deviations
# Solid stack (#743): the overall thickness, cam face to back face, IS the
# channel station pitch (machine channels.station_pitch_mm, pinned by
# test_cylinder_bank_layout), so neighbouring gears bear cam face on back face
# and set the stations the way the rocker hubs do (ch_rocker_arm_spec.HUB_LENGTH).
# The band is centred (user ruling L20 d', #743): the same 0.05 wide as the
# one-sided +0.05/0 it replaces, so no harder to make, but 20 in-band gears
# now stack about nominal and the 20-gear acceptance
# (cylinder_bank_layout.STACK_L20_ACCEPT) passes first time. A long stack is
# re-faced at fit-up; a short one gets its thinnest gear remade.
OVERALL_THICKNESS = 7.0565
OVERALL_THICKNESS_BAND = (0.025, -0.025)  # (upper, lower) deviations
CAM_THICKNESS = OVERALL_THICKNESS - FACE_WIDTH  # reference: the closed rod slot
ECCENTRICITY = 8.64  # cam axis offset from the bore axis
# The cam must merge wholly into the actual uncut web, not a fictitious
# actual-N circular root blank.  The native builder checks this same margin.
CAM_ROOT_WEB_MIN_MM = STOCK_FORM.root_radius_min_mm - (CAM_DIA / 2.0 + ECCENTRICITY)
ECCENTRICITY_TOLERANCE_MM = 0.025
SET_ECCENTRICITY_RANGE_MM = 0.025
# Cam-lobe direction vs the alignment-notch centreline (the channel's phase
# datum); error_budget.yaml cam_phase. Carried on the native NotchPhase
# angular dimension (build_dt_cylinder_gear), lobe axis to notch radial.
CAM_PHASE_TOLERANCE_DEG = 0.25
NOTCH_WIDTH = 0.4  # alignment saw-kerf
NOTCH_WIDTH_BAND = (0.10, 0.0)  # (upper, lower) deviations
NOTCH_DEPTH = 3.0
NOTCH_DEPTH_TOLERANCE_MM = 0.2
TIP_RADIUS = OUTSIDE_DIA / 2.0
NOTCH_FLOOR_RADIUS = TIP_RADIUS - NOTCH_DEPTH
NOTCH_MEAN_RADIUS = (NOTCH_FLOOR_RADIUS + TIP_RADIUS) / 2.0
# +Y is a tooth crest (the cam lobe direction).  The phase kerf is the first
# root counter-clockwise from the cam lobe, half a circular pitch away, and is
# cut as a vertical slot whose centreline crosses the mean notch radius at
# NOTCH_PHASE_DEG from the lobe axis.
NOTCH_PHASE_DEG = 180.0 / TEETH
NOTCH_CENTER_X = -NOTCH_MEAN_RADIUS * math.sin(math.radians(NOTCH_PHASE_DEG))
# The native stock profile is patterned with the canonical seed-gap ray at
# pi/N. The existing kerf ray is pi/2 + pi/N, so this separate locator is 90
# BASIC; it is not the cam-lobe-to-kerf NotchPhase/cam_phase control above.
TOOTH_PATTERN_GAP_RAD = math.pi / TEETH
PATTERN_NOTCH_BASIC_ANGLE_DEG = 90.0
BASIC_DIMENSIONS = frozenset({"PatternNotchPhase"})
PATTERN_NOTCH_SHOP_CANDIDATE_DEG = 0.02


def pattern_notch_clock_grade_deg() -> float:
    """Read the post-F4 published drum pattern-to-CAM-NOTCH half-width lazily."""
    from _gear_fit_limits import SourceDomainUnknown, drum_tooth_to_cam_notch_clock_deg

    grade = drum_tooth_to_cam_notch_clock_deg()
    if grade < PATTERN_NOTCH_SHOP_CANDIDATE_DEG:
        raise SourceDomainUnknown(
            f"actual drum pattern-to-CAM-NOTCH grade +/-{grade:g} deg is tighter "
            f"than the +/-{PATTERN_NOTCH_SHOP_CANDIDATE_DEG:g} deg shop candidate; "
            "report the admissible grade, do not issue the production drawing"
        )
    return grade


def pattern_notch_phase_callouts() -> tuple[str, str]:
    """Print the actual published pattern-to-notch grade without a fallback."""
    grade_deg = pattern_notch_clock_grade_deg()
    return (
        "TOOTH PATTERN TO CAM NOTCH\n"
        f"ANGULAR ERROR +/-{grade_deg:g} DEG FROM BASIC",
        "INSPECT FROM THE ACTUAL SEED TOOTH GAP,\n"
        "NOT FROM THE ECCENTRIC CAM LOBE.",
    )


SURFACE_FINISHES = (
    SurfaceFinishControl(
        "cylinder_gear_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA),
        production_method="BORE",
    ),
    SurfaceFinishControl("cam_follower", MACHINED_UM, CylinderFace(CAM_DIA)),
)

# Marked model dimensions locate the blank, bore, cam, stacking thickness and
# kerf. Bore diameter is a reference nominal with a finished-fit callout.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "GearBlankProfile": {"OutsideDia"},
    "BoreProfile": {"BoreDia"},
    "CamProfile": {"CamDia", "CamCy"},
    "CamBoss": {"OverallThickness"},
    "NotchProfile": {"NotchDepth", "NotchWidth", "NotchPhase", "PatternNotchPhase"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity policy rule
# 2), so the MODEL owns them: build_dt_cylinder_gear applies this map to the
# .SLDPRT and draw_dt_cylinder_gear only reads it back.  Three places where a
# three-place band rides the dimension (the matched running bore's reference
# nominal, the cam eccentricity, the +0.05/0 stacking thickness that sets
# the station pitch); two where the band is a two-place one (cam OD, face
# width, kerf width); one on the kerf depth. The existing cam-lobe phase is an
# angle read to the tenth of a degree; the separate pattern locator is BASIC.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": 2},
    "GearBlankProfile": {"OutsideDia": 2},
    "BoreProfile": {"BoreDia": 3},
    "CamProfile": {"CamDia": 2, "CamCy": 3},
    # Four places: 7.0565 is the station pitch, exact only at four (user
    # ruling L20 d'); three would round one limit of the band inward.
    "CamBoss": {"OverallThickness": 4},
    "NotchProfile": {"NotchDepth": 1, "NotchWidth": 2, "NotchPhase": 1, "PatternNotchPhase": 0},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
if any(
    name not in {name for names in DRAWING_PRECISION.values() for name in names}
    for names in DRAWING_DIMENSIONS.values()
    for name in names
):
    raise AssertionError("a marked dimension prints without part-authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

# The one sheet-derived dimension: the parenthesised cam thickness (overall
# less face width, #743), a read-only difference with no model dimension to
# import.  Two places: it is the closed rod slot, and one place would print
# 4.1 for the 4.0565 the ring runs in.  Its places are still specification,
# so the sheet reads them here.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"cam thickness reference": 2}


def matched_bore_limits(finished_shaft_dia_mm: float) -> tuple[float, float]:
    """Return finished bore MIN/MAX for the measured mating MHA-DT-013 arbor."""
    minimum, maximum = BORE_DIAMETRAL_CLEARANCE_MM
    return finished_shaft_dia_mm + minimum, finished_shaft_dia_mm + maximum


def outside_dia_limits_mm() -> tuple[float, float]:
    """Accepted tooth-tip MIN/MAX; includes the printed nominal's rounding."""
    lower, upper = printed_deviations(
        OUTSIDE_DIA,
        DRAWING_PRECISION_BY_NAME["OutsideDia"],
        deviations(OUTSIDE_DIA_BAND),
    )
    return round(OUTSIDE_DIA + lower, 12), round(OUTSIDE_DIA + upper, 12)


def whole_depth_limits_mm() -> tuple[float, float]:
    """Accepted cutter plunge MIN/MAX from the actual printed process row."""
    nominal = round(WHOLE_DEPTH, WHOLE_DEPTH_PLACES)
    upper, lower = WHOLE_DEPTH_BAND
    return round(nominal + lower, 12), round(nominal + upper, 12)


def manufacturing_corner_profiles() -> tuple[StockFormProfile, ...]:
    """Four finite profiles paying both printed tip and plunge limits."""
    return tuple(
        StockFormProfile(
            TEETH,
            CUTTER_TEMPLATE,
            tip / 2.0,
            tip / 2.0 - CUTTER_TEMPLATE.root_radius_mm - depth,
        )
        for tip in outside_dia_limits_mm()
        for depth in whole_depth_limits_mm()
    )
