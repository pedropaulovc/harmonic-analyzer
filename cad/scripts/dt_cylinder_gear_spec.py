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

from _fit_deviations import deviations
from _fit_ream_slide import REAM_SLIDE
from _gear_fit_limits import gear_tip_band_mm
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations
from _gtol_cylinder import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from stock_form_cutter import CutterTemplate, StockFormProfile


MM_PER_IN = 25.4

# #290: the registry row's drawing_unit (in) is this sheet's unit; the bands,
# places and roughness below are authored for it.
UNIT = drawing_unit("parts/dt-cylinder-gear", _config.parts("dt-cylinder-gear"))

# --- gear tooth system (build_dt_cylinder_gear.py / gear_train.yaml) ------------
TEETH = int(_config.machine("gear_train", "cylinder_teeth"))
DIAMETRAL_PITCH = _config.machine("gear_train", "diametral_pitch")
PRESSURE_ANGLE_DEG = float(_config.machine("gear_train", "pressure_angle_deg"))
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH * MODULE_MM
OUTSIDE_DIA_BAND = gear_tip_band_mm("standard")
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
# Inch places of the printed plunge (GEAR DATA): .0445.
WHOLE_DEPTH_PLACES = 4
WHOLE_DEPTH_BAND = (0.0508, 0.0)  # retained (upper, lower) plunge: +.002/0 in
# A printed plunge can round upward by half its final decimal.  Pay that
# plus the full depth band before choosing the native three-place inch blank.
_DEPTH_SUPPORT_PROFILE = StockFormProfile(
    TEETH,
    CUTTER_TEMPLATE,
    PITCH_DIA / 2.0,
    CUTTER_RADIAL_TRANSLATION_MM
    - WHOLE_DEPTH_BAND[0]
    - 0.5 * 10.0**-WHOLE_DEPTH_PLACES * MM_PER_IN,
)
MAX_DEPTH_SUPPORT_OUTSIDE_DIA_MM = 2.0 * _DEPTH_SUPPORT_PROFILE.support_radius_max_mm
# The blank is the largest .001 in the depth-paid support allows (printed at
# three places, so the print IS the model).
OUTSIDE_DIA_PLACES = 3
OUTSIDE_DIA = round(
    math.floor(
        (MAX_DEPTH_SUPPORT_OUTSIDE_DIA_MM - OUTSIDE_DIA_BAND[0])
        / MM_PER_IN
        * 10.0**OUTSIDE_DIA_PLACES
    )
    / 10.0**OUTSIDE_DIA_PLACES
    * MM_PER_IN,
    9,
)
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
# #290: every gear is reamed interchangeable on the MHA-DT-13 arbor (SHAFT_H),
# no longer bored to suit it: REAM_SLIDE's .3760-.3765 in, cut by the owned
# .3760 over reamer and printed .3760 +.0005/.0000.
BORE_DIA = round(arbor.SHAFT_DIA + REAM_SLIDE[1], 9)  # 9.5504, .3760
BORE_DIA_BAND = (round(REAM_SLIDE[0] - REAM_SLIDE[1], 9), 0.0)  # (upper, lower)
BORE_PLACES = 4
# (minimum, maximum) diametral clearance on the arbor: .0010-.0023 in.
BORE_DIAMETRAL_CLEARANCE_MM = (
    round(BORE_DIA + BORE_DIA_BAND[1] - (arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[0]), 9),
    round(BORE_DIA + BORE_DIA_BAND[0] - (arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[1]), 9),
)
FACE_WIDTH = 2.9972  # .118
# Face width controls mesh engagement across the mating cone-gear family and,
# with OVERALL_THICKNESS, the cam length the MHA-CH-03 rod ring rides in
# (cylinder_bank_layout.SLOT_MIN) and the gear-0 pitch stack.
FACE_WIDTH_TOLERANCE_MM = 0.0508  # +/-.002 in
CAM_DIA = 30.607  # 1.205, integral eccentric cam disc
CAM_DIA_BAND = (0.0, -0.0508)  # (upper, lower) deviations: 0/-.002 in
CAM_DIA_PLACES = 3
# Solid stack (#743): the overall thickness, cam face to back face, IS the
# channel station pitch (machine channels.station_pitch_mm, pinned by
# test_cylinder_bank_layout), so neighbouring gears bear cam face on back face
# and set the stations the way the rocker hubs do (ch_rocker_arm_spec.HUB_LENGTH).
# The band is centred (user ruling L20 d', #743): the same 0.05 wide as the
# one-sided +0.05/0 it replaces, so no harder to make, but 20 in-band gears
# now stack about nominal and the 20-gear acceptance
# (cylinder_bank_layout.STACK_L20_ACCEPT) passes first time. A long stack is
# re-faced at fit-up; a short one gets its thinnest gear remade.
# Exempt from the inch grid (#290): the station-pitch closure, 7.0565 mm, so
# it prints .2778 at four places (0.4 um under the model).
OVERALL_THICKNESS = 7.0565
OVERALL_THICKNESS_BAND = (0.0254, -0.0254)  # (upper, lower) deviations: +/-.0010 in
OVERALL_THICKNESS_PLACES = 4
CAM_THICKNESS = OVERALL_THICKNESS - FACE_WIDTH  # reference: the closed rod slot
# Exempt from the inch grid (#290): the throw is the channel's measured
# kinematic gain (dimensions.yaml ch. 13), 8.64 mm, printed .3402 at four
# places (1.1 um over the model).
ECCENTRICITY = 8.64  # cam axis offset from the bore axis
ECCENTRICITY_PLACES = 4
# The cam must merge wholly into the actual uncut web, not a fictitious
# actual-N circular root blank.  The native builder checks this same margin.
CAM_ROOT_WEB_MIN_MM = STOCK_FORM.root_radius_min_mm - (CAM_DIA / 2.0 + ECCENTRICITY)
# Per-gear band only: error_budget.yaml cam_eccentricity books each channel's
# throw independently, so no matched-set range is drawn (machinist review r1).
ECCENTRICITY_TOLERANCE_MM = 0.0254  # +/-.0010 in
_CAM_DIA_LOWER = printed_deviations(
    CAM_DIA, CAM_DIA_PLACES, deviations(CAM_DIA_BAND), unit=UNIT
)[0]
_ECC_UPPER = printed_deviations(
    ECCENTRICITY,
    ECCENTRICITY_PLACES,
    (-ECCENTRICITY_TOLERANCE_MM, ECCENTRICITY_TOLERANCE_MM),
    unit=UNIT,
)[1]
# Worst-case crescent wall between the bore and the cam OD, opposite the lobe,
# at the printed limits: smallest cam, largest throw, largest bore.  Floored
# to the printed .001 in.  Below the .080 in target, above the .060 in floor
# (rule 17): printed as a plain fact (rule 20); pending owner ruling (#992).
CAM_WALL_MIN_MM = round(
    math.floor(
        (
            (CAM_DIA + _CAM_DIA_LOWER) / 2.0
            - (ECCENTRICITY + _ECC_UPPER)
            - (BORE_DIA + BORE_DIA_BAND[0]) / 2.0
        )
        / MM_PER_IN
        * 1000.0
    )
    / 1000.0
    * MM_PER_IN,
    9,
)
# Cam-lobe direction vs the alignment-notch centreline (the channel's phase
# datum); error_budget.yaml cam_phase. Carried on the native NotchPhase
# angular dimension (build_dt_cylinder_gear), lobe axis to notch radial.
CAM_PHASE_TOLERANCE_DEG = 0.25
# The kerf is a sighted phase mark, engaged by nothing (no pin, gauge or
# mating part), so no lower limit carries a function.  Its one functional
# limit is the maximum: where the flanks meet the root the stock tooth gap is
# just over 0.41 mm wide, so a wider kerf nicks both neighbouring teeth (the
# old +0.10/0 band reached 0.50; machinist review e04fd60 r2/r3).  Printed as
# the single limit ".016 MAX": swTolMAX prints the nominal, so the modelled
# kerf IS the limit and the band runs from nothing up to it.
NOTCH_WIDTH = 0.4064  # .016 alignment saw-kerf
NOTCH_WIDTH_BAND = (0.0, -NOTCH_WIDTH)  # (upper, lower): any saw up to the MAX
NOTCH_WIDTH_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints ".016 MAX"
# Its depth only has to reach below the tooth root and clear the cam; the
# title-block .XX row (a check reads it, so never .X).
NOTCH_DEPTH = 3.048  # .12
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
# pi/N and the kerf ray is pi/2 + pi/N: thirty pitches, 90 deg. Printed as
# (90°), a reference: the kerf is sawn into a tooth root the indexing already
# cut, so it has no separate pattern-to-notch error to inspect. The phase the
# analyzer reads, cam lobe to notch, is NotchPhase's 1.5 ±0.25 above.
TOOTH_PATTERN_GAP_RAD = math.pi / TEETH
PATTERN_NOTCH_REF_ANGLE_DEG = 90.0


SURFACE_FINISHES = (
    SurfaceFinishControl(
        "cylinder_gear_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA),
        production_method="BORE",
        display_unit=UNIT,
    ),
    SurfaceFinishControl(
        "cam_follower", MACHINED_UM, CylinderFace(CAM_DIA), display_unit=UNIT
    ),
)

# Marked model dimensions locate the blank, bore, cam, stacking thickness and
# kerf.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "GearBlankProfile": {"OutsideDia"},
    "BoreProfile": {"BoreDia"},
    "CamProfile": {"CamDia", "CamCy"},
    "CamBoss": {"OverallThickness"},
    "NotchProfile": {"NotchDepth", "NotchWidth", "NotchPhase", "PatternNotchPhase"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`
# ), so the MODEL owns them: build_dt_cylinder_gear applies this map to the
# .SLDPRT and draw_dt_cylinder_gear only reads it back.  Inch places: four on
# the reamed bore (its +.0005 band) and on the two kinematic values held to
# +/-.0010 (the stacking thickness that IS the station pitch and the cam
# throw); three where a +/-.002-class band rides the dimension (tooth tip, cam
# OD, face width) and on the .016 MAX kerf; two (.XX) on the kerf depth.  The
# cam-lobe phase is an angle read to the tenth of a degree; the separate
# pattern locator is BASIC.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": 3},
    "GearBlankProfile": {"OutsideDia": OUTSIDE_DIA_PLACES},
    "BoreProfile": {"BoreDia": BORE_PLACES},
    "CamProfile": {"CamDia": CAM_DIA_PLACES, "CamCy": ECCENTRICITY_PLACES},
    "CamBoss": {"OverallThickness": OVERALL_THICKNESS_PLACES},
    "NotchProfile": {
        "NotchDepth": 2,
        "NotchWidth": 3,
        "NotchPhase": 1,
        "PatternNotchPhase": 0,
    },
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
# import.  Three places: it is the closed rod slot, and two would print .16
# for the .1598 the ring runs in.  Its places are still specification, so the
# sheet reads them here.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"cam thickness reference": 3}


def outside_dia_limits_mm() -> tuple[float, float]:
    """Accepted tooth-tip MIN/MAX; includes the printed nominal's rounding."""
    lower, upper = printed_deviations(
        OUTSIDE_DIA,
        DRAWING_PRECISION_BY_NAME["OutsideDia"],
        deviations(OUTSIDE_DIA_BAND),
        unit=UNIT,
    )
    return round(OUTSIDE_DIA + lower, 12), round(OUTSIDE_DIA + upper, 12)


def whole_depth_limits_mm() -> tuple[float, float]:
    """Accepted cutter plunge MIN/MAX from the actual printed process row."""
    lower, upper = printed_deviations(
        WHOLE_DEPTH, WHOLE_DEPTH_PLACES, deviations(WHOLE_DEPTH_BAND), unit=UNIT
    )
    return round(WHOLE_DEPTH + lower, 12), round(WHOLE_DEPTH + upper, 12)


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
