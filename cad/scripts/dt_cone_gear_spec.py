r"""Closed-form stock-cutter authority shared by the cone family and its drawing.

Every count T006..T120 is cut by its standard 48DP PA20 rotary cutter (the
approved DT6-FORM1 tool for T006) set at the standard depth: the cutter's
reference pitch line lies on the gear's own pitch circle, so the nominal pitch
thickness is the cutter's. The blank is the AGMA standard outside diameter
(N + 2)/DP, capped where the cutter's finite form stops supporting a tip at
either thickness limit. Nothing here reads measured or proof data; the mesh
is checked in closed form by ``standard_mesh_checks`` and natively by the
assembly interference gate.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import _config
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from cone_pitch import SEAT_PITCH
from gear_face_band import GEAR_FACE_WIDTH_BAND
from cone_shaft_land_bands import (
    FLAT_AF_BAND,
    SECTION_CONE_GEAR_TEETH,
    SECTION_DIA_BANDS,
    SECTION_FLAT_AF,
    TERMINAL_DIA_MM,
)
from gear_seat_fit import flat_bore_af_band, seat_bore_band
from stock_form_cutter import (
    CustomSixCutter,
    StockFormProfile,
    TrochoidRelief,
    template_for_teeth,
    translation_for_pitch_tooth_thickness,
)


MM_PER_IN = 25.4

# #290: the family sheet's unit (its registry row's drawing_unit); every
# printed limit below is authored for, and judged on, its decimal-inch grid.
UNIT = drawing_unit("parts/dt-cone-gear", _config.parts("dt-cone-gear"))


def inch_grid_mm(value_mm: float, places: int, rounding: Any = round) -> float:
    """``value_mm`` taken to the ``places``-decimal inch grid by ``rounding``
    (``round``, ``math.floor`` or ``math.ceil``), back in exact-decimal mm.
    A value already on the grid (to float error) stays on it."""
    scale = 10**places
    scaled = value_mm / MM_PER_IN * scale
    if abs(scaled - round(scaled)) < 1e-6:
        scaled = round(scaled)
    return round(rounding(scaled) / scale * MM_PER_IN, 9)


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.0644``, ``2.5413``, ``-.0004``."""
    text = f"{abs(value_mm) / MM_PER_IN:.{places}f}"
    text = text[1:] if text.startswith("0.") else text
    return f"-{text}" if value_mm < 0 and text.strip(".0") else text


# Family alloy split (config-owned, cad/config/parts/dt-cone-gear.yaml): the
# title-block material (C36000) covers T030-T120; the four tip gears are the
# harder alloy below (dimensions.yaml ch.12 p.21).
_MFG = _config.parts("dt-cone-gear")
BODY_MATERIAL_SPEC = str(_MFG["material_specification"])
TIP_MATERIAL_SPEC = str(_MFG["material_tip_specification"])

TEETH = int(_config.machine("gear_train", "fundamental_cone_teeth"))
CONFIGURATION_TEETH = tuple(range(6, TEETH + 1, 6))
CONFIGS = tuple((f"T{n:03d}", n) for n in CONFIGURATION_TEETH)
DEFAULT_TEETH = CONFIGURATION_TEETH[-1]


def tooth_features(teeth: int) -> tuple[str, str, str]:
    """Distinct real topology for one configured finite cutter profile."""
    if teeth not in CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    suffix = f"T{teeth:03d}"
    return tuple(f"{stem}{suffix}" for stem in (
        "ToothGapProfile", "ToothGapCut", "ToothGapPattern"
    ))


# All cuts/patterns disappear in the derived assembly drawing configurations.
SIMPLIFIED_FEATURES = tuple(
    feature for teeth in CONFIGURATION_TEETH for feature in tooth_features(teeth)[1:]
)
SIMPLIFIED_FEATURES_BY_CONFIGURATION = {
    f"T{teeth:03d}": tooth_features(teeth)[1:] for teeth in CONFIGURATION_TEETH
}

DIAMETRAL_PITCH = _config.machine("gear_train", "diametral_pitch")
PRESSURE_ANGLE_DEG = _config.machine("gear_train", "pressure_angle_deg")
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH * MODULE_MM
# (upper, lower), actual pitch arc, about the standard-depth thickness: the
# ordinary cut-gear band (user ruling 2026-10-10, set-at-assembly cones;
# dt_mesh_checks.cone_check gates it at the RSS corner of cone_set_stack),
# +/-.003 in on the inch sheet.
TOOTH_THICKNESS_BAND = (0.0762, -0.0762)

# DT6-FORM1, T006 option (a) (user ruling 2026-10-10). T006 is pending
# exception ruling #971: against the shared 20 deg 120T drum no full-depth six-tooth form
# can reach a contact ratio of 1, so its tooth is sized for no binding and
# the drum-tip path instead.
# * Thickness 0.872 at the tool pitch, the band's upper limit
#   (CUSTOM_SIX_TOOTH_THICKNESS_BAND): every corner pair keeps >= 0.02
#   backlash at the RSS-closed centre (cone_set_stack, ~std + 0.095).
# * Root R 1.10 sets the plunge; the involute stops where the relief rejoins it.
# * Relief: the path of one virtual drum-tip point, held at C0 = standard +
#   CUSTOM_SIX_RELIEF_CENTRE_ABOVE_STANDARD_MM (0.09, just inside the RSS-closed
#   centre) with the thick tooth's flank in contact (TrochoidRelief), at radius
#   C0 - 1.10 so it grazes the root, led 0.0002 rad into the drum tooth. That
#   keeps every printed drum-tip corner >= 10 um clear of the T006 form at
#   both T006 thickness limits over the RSS centre range
#   (dt_mesh_checks.t006_relief_clearance_mm, gated in test_standard_mesh_checks).
# * Blank OD .1696 in (+0/-.0008, CUSTOM_SIX_BLANK_DIA_BAND), above the AGMA
#   (N+2)/DP 4.23 mm: the ruled 4.31 mm (the largest OD, floored to 0.01 mm,
#   whose thin corner keeps the 0.25 m tip land) floored to the printed .0001
#   in grid; the extra addendum raises the contact ratio (~0.77, REF).
CUSTOM_SIX_TOOL_THICKNESS_MM = 0.872
CUSTOM_SIX_ROOT_RADIUS_MM = 1.10
CUSTOM_SIX_TOOL_TIP_RADIUS_MM = 2.25
CUSTOM_SIX_RELIEF_LEAD_RAD = 0.0002
CUSTOM_SIX_OUTSIDE_DIA_MM = 4.30784  # .1696
CUSTOM_SIX_RELIEF_CENTRE_ABOVE_STANDARD_MM = 0.09


def _custom_six_relief(involute_only: CustomSixCutter) -> TrochoidRelief:
    """Phase the virtual drum-tip point from the conjugate involute contact.

    At the closing centre C0 the thick T006 flank's line of action leaves its
    base circle at the operating angle aw; the drum flank in contact starts at
    polar angle aw + pi - (C0 sin aw - (aw - k6) rb6) / rbD about the drum
    centre (k6 the tool's half-space base angle), and its involute reaches the
    virtual radius Rv = C0 - root a further inv(acos(rbD / Rv)) round.
    """
    drum_teeth = int(_config.machine("gear_train", "cylinder_teeth"))
    alpha = math.radians(PRESSURE_ANGLE_DEG)
    centre = (6 + drum_teeth) * MODULE_MM / 2.0 + CUSTOM_SIX_RELIEF_CENTRE_ABOVE_STANDARD_MM
    pitch_six, pitch_drum = 6 * MODULE_MM / 2.0, drum_teeth * MODULE_MM / 2.0
    base_six, base_drum = pitch_six * math.cos(alpha), pitch_drum * math.cos(alpha)
    aw = math.acos((pitch_six + pitch_drum) * math.cos(alpha) / centre)
    k6 = involute_only.half_space_base_angle_rad
    start = aw + math.pi - (centre * math.sin(aw) - (aw - k6) * base_six) / base_drum
    radius = centre - CUSTOM_SIX_ROOT_RADIUS_MM
    roll = math.acos(base_drum / radius)
    phase = start + (math.tan(roll) - roll) - CUSTOM_SIX_RELIEF_LEAD_RAD
    return TrochoidRelief(drum_teeth, centre, phase)


def cutter_template(teeth: int) -> Any:
    """Canonical stock master or the explicitly approved finite N6 tool."""
    _require_member(teeth)
    if teeth == 6:
        args = (
            DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG, CUSTOM_SIX_ROOT_RADIUS_MM,
            CUSTOM_SIX_TOOL_TIP_RADIUS_MM, CUSTOM_SIX_TOOL_THICKNESS_MM, "DT6-FORM1",
            "User ruling 2026-10-10 option (a): N6 PA20 working involute over a "
            "drum-tip trochoid relief; root R1.10; finite ground form",
        )
        return CustomSixCutter(*args, relief=_custom_six_relief(CustomSixCutter(*args)))
    return template_for_teeth(teeth, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG)


def _require_member(teeth: int) -> None:
    if type(teeth) is not int or teeth not in CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")


def standard_translation_mm(teeth: int) -> float:
    """Cutter reference pitch line on the gear's pitch circle (standard depth)."""
    return teeth * MODULE_MM / 2.0 - cutter_template(teeth).pitch_radius_mm


@dataclass(frozen=True)
class _Member:
    profile: StockFormProfile
    corners: tuple[StockFormProfile, ...]
    floor_limits_mm: tuple[float, float]


@lru_cache(maxsize=None)
def _member(teeth: int) -> _Member:
    _require_member(teeth)
    cutter = cutter_template(teeth)
    translation = standard_translation_mm(teeth)
    pitch_radius = teeth * MODULE_MM / 2.0
    thickness = StockFormProfile(teeth, cutter, pitch_radius, translation).pitch_tooth_thickness_mm
    thickness_band, blank_band = tooth_thickness_band(teeth), blank_dia_band(teeth)
    translations = tuple(
        translation_for_pitch_tooth_thickness(teeth, cutter, thickness + side)
        for side in (thickness_band[1], thickness_band[0])
    )
    # AGMA standard blank, capped where either thickness limit's finite cutter
    # form stops supporting the tip at the blank band's upper limit. T006 takes
    # its ruled land-limited OD instead (CUSTOM_SIX_OUTSIDE_DIA_MM), still
    # under the same support cap.
    support = min(
        StockFormProfile(teeth, cutter, pitch_radius, shift).support_radius_max_mm
        for shift in translations
    )
    cap = 2.0 * support - blank_band[0]
    if teeth == 6:
        if CUSTOM_SIX_OUTSIDE_DIA_MM > cap:
            raise ValueError("T006: DT6-FORM1 finite tip does not support the ruled OD")
        od = CUSTOM_SIX_OUTSIDE_DIA_MM
    else:
        od = inch_grid_mm(
            min((teeth + 2) * MODULE_MM, cap), DRAWING_PRECISION["BlankProfile"]["BlankDia"],
            math.floor,
        )
    profile = StockFormProfile(teeth, cutter, od / 2.0, translation)
    corners = tuple(StockFormProfile(teeth, cutter, (od + side) / 2.0, shift)
                    for side, shift in itertools.product(blank_band, translations))
    required_land = max(0.10, 0.25 * MODULE_MM)
    for corner in (profile, *corners):
        corner.require_tip_land(required_land)
    root_min = min(corner.root_radius_min_mm for corner in corners)
    root_max = max(corner.root_radius_max_mm for corner in corners)
    # The printed root LIMIT pair encloses every corner's actual radial
    # envelope, rounded outward at the printed inch places.
    places = DRAWING_PRECISION["GapFloorReference"]["FloorDia"]
    error = max(corner.geometry_error_bound_mm for corner in corners)
    minimum = inch_grid_mm(2.0 * (root_min - error), places, math.floor)
    maximum = inch_grid_mm(2.0 * (root_max + error), places, math.ceil)
    maximum_bore = inch_grid_mm(
        bore_dia_mm(teeth) + BORE_DIA_BAND[0], BORE_BAND_PLACES, math.ceil
    )
    web_required = WEB_EXCEPTIONS_MM.get(teeth, MACHINED_WEB_TARGET_MM)
    if (minimum - maximum_bore) / 2.0 < web_required - 1e-9:
        raise ValueError(f"T{teeth:03d}: printed root misses the retained web")
    # T006 root (re-derived for option (a), replacing the D2.346 MIN of the
    # retired R1.491 tool): the standard-depth thick corner sits the tool root
    # R1.10 on the gear's own axis offset 0, so the root MAX is D2.20; the thin
    # corner's -0.032 translation gives the MIN. The web above is the strength
    # floor: D >= the MAX bore + 2 x 0.62.
    if teeth == 6 and not math.isclose(
        root_max, CUSTOM_SIX_ROOT_RADIUS_MM + max(translations), abs_tol=error
    ):
        raise ValueError("T006: root MAX is not the ruled R1.10 at standard depth")
    return _Member(profile, corners, (minimum, maximum))


def stock_form_profile(teeth: int) -> StockFormProfile:
    """The nominal native cut: standard depth, standard (or support-capped) blank."""
    return _member(teeth).profile


def manufacturing_corner_profiles(teeth: int) -> tuple[StockFormProfile, ...]:
    """All four OD/thickness corners: OD band outer, thickness band inner."""
    return _member(teeth).corners


def outside_dia_mm(teeth: int) -> float:
    """Printed blank diameter."""
    return 2.0 * stock_form_profile(teeth).blank_radius_mm


def tooth_thickness_mm(teeth: int) -> float:
    """Nominal circular pitch thickness cut by the standard-depth cutter."""
    return stock_form_profile(teeth).pitch_tooth_thickness_mm


# Tooth-thickness acceptance on the bench: every gear is measured over two
# pins in opposite gaps (all twenty tooth counts are even) with an ordinary
# micrometer. T006 first (machinist review of the stack build: the DT6-FORM1
# form cannot be checked without an optical comparator); then every sheet
# (ENFORCE round 1 of #971: T012-T120 printed a circular thickness no shop can
# measure). Ø.040 gauge pins bear inside every stock-cut flank and stand
# ~0.46-0.56 mm proud of the tips; T006 takes Ø.047, which bears on its
# working involute well above the relief junction and stands ~0.8 mm proud.
# Either way the reading follows the tooth thickness alone.
OVER_PINS_PIN_DIA_MM = 1.016  # .040
CUSTOM_SIX_PIN_DIA_MM = 1.1938  # .047
# The acceptance readings print at four inch places, rounded inward.
OVER_PINS_PLACES = 4
_OVER_PINS_SAMPLES = 2000


def over_pins_pin_dia_mm(teeth: int) -> float:
    _require_member(teeth)
    return CUSTOM_SIX_PIN_DIA_MM if teeth == 6 else OVER_PINS_PIN_DIA_MM


def _over_pins_mm(profile: StockFormProfile, pin_dia_mm: float) -> tuple[float, float, bool]:
    """Measurement over two pins in opposite gaps, the flank contact radius,
    and whether that contact is inside a flank (not at either end of it).

    A pin lowered along the gap bisector (+X) stops on the first sampled
    ACTUAL flank point it meets: the one that puts its centre furthest out,
    x + sqrt(r^2 - y^2). Even tooth counts put the other pin diametrically
    opposite, so M = 2 (X + r).
    """
    radius = pin_dia_mm / 2.0
    best: tuple[float, float, bool] | None = None
    for segment in profile.gap_segments():
        if segment.kind != "flank":
            continue
        for index in range(_OVER_PINS_SAMPLES + 1):
            x, y = segment.point(index / _OVER_PINS_SAMPLES)
            if abs(y) > radius:
                continue
            centre = x + math.sqrt(radius * radius - y * y)
            if best is None or centre > best[0]:
                best = (centre, math.hypot(x, y), 0 < index < _OVER_PINS_SAMPLES)
    if best is None:
        raise ValueError(f"T{profile.teeth:03d}: a Ø{pin_dia_mm} pin reaches no flank")
    centre, contact, interior = best
    return 2.0 * (centre + radius), contact, interior


@lru_cache(maxsize=None)
def over_pins_limits_mm(teeth: int) -> tuple[float, float]:
    """Over-pins acceptance at the thickness and blank limits, rounded inward."""
    pin = over_pins_pin_dia_mm(teeth)
    readings = []
    for profile in manufacturing_corner_profiles(teeth):
        over_pins, contact, interior = _over_pins_mm(profile, pin)
        floor = profile.template.relief_junction_radius_mm if teeth == 6 else 0.0
        if not interior or not floor < contact < profile.blank_radius_mm:
            raise ValueError(f"T{teeth:03d}: over-pins contact leaves the working flank")
        if over_pins <= outside_dia_mm(teeth):
            raise ValueError(f"T{teeth:03d}: pins do not stand clear of the tips")
        readings.append(over_pins)
    return (
        inch_grid_mm(min(readings), OVER_PINS_PLACES, math.ceil),
        inch_grid_mm(max(readings), OVER_PINS_PLACES, math.floor),
    )


BORE_DIA = 9.525  # 3/8 (.3750) at T120; smaller on the tip gears
# Face width (user ruling 2026-09-28): the cone set is a solid stack.  Every
# gear is one seat pitch thick, so each bears on its neighbour and the stack
# on MHA-DT-07 sets every station (dt_cone_gear_stack); no gear is bonded.  The
# face is SEAT_PITCH floored to four millimetre places, so the modelled stack
# closes without interference; it is a stack closure, so it is not snapped
# to the inch grid and prints .2707 at four inch places, inside its band.
# Every gear grew SOUTH: its north face
# stays on the station layout (cone_line), so T006's north face -- the
# datum the MHA-DT-VN-54 stack collar is feelered off -- does not move.  The band
# is the cylinder bank's L20 d' rule (+/-.001 in per gear, the 20-gear stack
# accepted at +/-0.20 mm), so it is faced to a micrometer on both sides.
FACE_WIDTH = math.floor(SEAT_PITCH * 1e4) / 1e4
FACE_WIDTH_BAND = GEAR_FACE_WIDTH_BAND
# Flat clock (user ruling 2026-09-28): the bore's D-flat is the gear's
# angular datum on MHA-DT-04, and its outward normal passes through the centre
# of the phase-0 tooth on local +X, so every gear keeps the clock it is
# placed at.  Index the teeth off the flat on one setup; the native
# BoreFlatClock angular dimension carries this band (error_budget.yaml
# cone_flat_clock), the cylinder gear's CAM_PHASE_TOLERANCE_DEG precedent.
FLAT_CLOCK_TOLERANCE_DEG = 0.25


def floor_radius_min_mm(teeth: int) -> float:
    """Minimum radial envelope of the actual translated finite root arc."""
    return stock_form_profile(teeth).root_radius_min_mm


def floor_radius_max_mm(teeth: int) -> float:
    """Maximum radial envelope, not a filled RootMAX material disk."""
    return stock_form_profile(teeth).root_radius_max_mm


def floor_limits_mm(teeth: int) -> tuple[float, float]:
    """Printed root-envelope diameters enclosing every tool corner."""
    return _member(teeth).floor_limits_mm


def gap_floor_deviations_mm(teeth: int) -> tuple[float, float]:
    """FloorDia's (lower, upper) LIMIT deviations from the modelled floor.

    The printed limits are ``floor_limits_mm``; the dimension's nominal is the
    modelled floor, so each limit is stored as its offset from it.
    """
    minimum, maximum = floor_limits_mm(teeth)
    nominal = 2.0 * floor_radius_min_mm(teeth)
    return minimum - nominal, maximum - nominal


def bore_dia_mm(teeth: int) -> float:
    """Return the configured bore that fits the matching stepped-shaft land."""
    _require_member(teeth)
    # T006/T012 share the actual terminal reader. Their strength acceptance
    # is rederived below from the current cutter-owned printed floor MINs.
    if teeth <= 12:
        return TERMINAL_DIA_MM
    if teeth == 18:
        return 3.175  # 1/8 (.1250)
    if teeth == 24:
        return 6.35  # 1/4 (.2500)
    return BORE_DIA


def material_specification(teeth: int) -> str:
    """Return the configuration-owned alloy printed in that sheet's title block."""
    _require_member(teeth)
    return TIP_MATERIAL_SPEC if teeth <= 24 else BODY_MATERIAL_SPEC


FAMILY_BORES_MM = {teeth: bore_dia_mm(teeth) for teeth in CONFIGURATION_TEETH}

# The special webs: the user's T006 >=0.62 ruling, and T012's .0797 in on the
# .031 terminal land (#290; owner minor RV-03 in cad/config/parts/
# dt-cone-gear.yaml: .0003 in under the .080 target, above the .060 floor).
# Every other gear must achieve the ordinary .080 in target, not merely the
# hard floor (rule 17 on an inch sheet, _inch_wall_limits).  These are
# acceptance inputs; the factory checks every actual cutter corner.
MACHINED_WEB_FLOOR_MM = WALL_FLOOR_MM
MACHINED_WEB_TARGET_MM = WALL_TARGET_MM
WEB_EXCEPTIONS_MM: dict[int, float] = {6: 0.62, 12: 2.02438}  # T012: .0797
TERMINAL_WEB_REQUIREMENTS_MM = {
    6: WEB_EXCEPTIONS_MM[6],
    12: WEB_EXCEPTIONS_MM[12],
}

# Printed inch places of the bore band (model-owned): four hold the
# +.0018/+.0010 in class and the .0310/.3750 nominals exactly.
BORE_BAND_PLACES = 4


# The band is UNIFORM: BoreCutDia is one model dimension across all twenty
# configurations. Keep the retained seat class independent of selected cutter
# settings so numerical qualification does not require its own output first.
def _seat_fit_band() -> tuple[float, float]:
    """(upper, lower): the round seat fit that holds on every gear land."""
    carried = [
        seat_bore_band(band)
        for band, teeth in zip(SECTION_DIA_BANDS, SECTION_CONE_GEAR_TEETH)
        if teeth
    ]
    return (min(band[0] for band in carried), max(band[1] for band in carried))


def terminal_web_bore_upper_mm() -> float:
    """Largest bore deviation admitted by the qualified terminal root limits."""
    cap = min(
        floor_limits_mm(teeth)[0] - 2.0 * minimum
        - inch_grid_mm(bore_dia_mm(teeth), BORE_BAND_PLACES, math.ceil)
        for teeth, minimum in TERMINAL_WEB_REQUIREMENTS_MM.items()
    )
    return inch_grid_mm(cap, BORE_BAND_PLACES, math.floor)


# The inch class is authored as exact millimetre decimals (gear_seat_fit), so
# it rides the model unrounded.
BORE_BAND_FIT_UPPER, BORE_BAND_LOWER = _seat_fit_band()
BORE_DIA_BAND = (BORE_BAND_FIT_UPPER, BORE_BAND_LOWER)
BORE_BAND_MIN_WIDTH_MM = 0.02032  # .0008
if BORE_DIA_BAND[0] - BORE_DIA_BAND[1] < BORE_BAND_MIN_WIDTH_MM - 1e-9:
    raise AssertionError(
        f"cone-gear seat bore band +{inch_text(BORE_DIA_BAND[0], 4)}/"
        f"+{inch_text(BORE_DIA_BAND[1], 4)} is under .0008 wide"
    )


def terminal_web_mm(teeth: int) -> float:
    """Print-worst radial ligament, read from the actual cutter and fit."""
    if teeth not in TERMINAL_WEB_REQUIREMENTS_MM:
        raise ValueError(f"T{teeth:03d} is not carried by the terminal land")
    maximum_bore = inch_grid_mm(
        bore_dia_mm(teeth) + BORE_DIA_BAND[0], BORE_BAND_PLACES, math.ceil
    )
    return (floor_limits_mm(teeth)[0] - maximum_bore) / 2.0




# --- D-bore (user ruling 2026-09-28) -----------------------------------------
#
# Every bore is a D: the round bore above plus one flat, parallel to the
# land's flat, whose outward normal is local +X (through the phase-0 tooth,
# FLAT_CLOCK_TOLERANCE_DEG).  Across-flat (AF) is measured from the flat to
# the far side of the round bore, the land's own AF nominal; the band keeps
# .0004-.0012 in AF clearance on the land's FLAT_AF_BAND.  One band for all twenty,
# so one BoreAF tolerance serves every configuration.
BORE_AF_BAND = flat_bore_af_band(FLAT_AF_BAND)  # +.0008/+.0004 in
BORE_AF_PLACES = 4


def land_section(teeth: int) -> int:
    """Index of the MHA-DT-04 land (cone_shaft_land_bands) carrying ``teeth``."""
    _require_member(teeth)
    for section, carried in enumerate(SECTION_CONE_GEAR_TEETH):
        if teeth in carried:
            return section
    raise AssertionError(f"no MHA-DT-04 land carries the T{teeth:03d} cone gear")


def bore_flat_af_mm(teeth: int) -> float:
    """Return the configuration's nominal bore across-flat."""
    across_flat = SECTION_FLAT_AF[land_section(teeth)]
    if across_flat is None:
        raise AssertionError(f"the T{teeth:03d} land has no flat")
    return across_flat


def bore_flat_offset_mm(teeth: int) -> float:
    """Distance from the bore axis to the flat (AF minus the bore radius)."""
    return bore_flat_af_mm(teeth) - bore_dia_mm(teeth) / 2.0


def bore_flat_segment_area_mm2(teeth: int) -> float:
    """Area the flat leaves standing inside the round bore (a circular
    segment), per unit face: the solid gains this over a round bore."""
    radius = bore_dia_mm(teeth) / 2.0
    offset = bore_flat_offset_mm(teeth)
    return radius * radius * math.acos(offset / radius) - offset * math.sqrt(
        radius * radius - offset * offset
    )


for _teeth in CONFIGURATION_TEETH:
    if not 0.0 < bore_flat_offset_mm(_teeth) < bore_dia_mm(_teeth) / 2.0:
        raise AssertionError(
            f"T{_teeth:03d} bore AF {bore_flat_af_mm(_teeth)} does not cut a "
            f"flat into its Ø{bore_dia_mm(_teeth)} bore"
        )


# The part's construction-only authoring sketches.  The part saves them
# hidden (they would otherwise render in every assembly that places a gear);
# a sheet's front view shows one again only to import its dimensions.
TOOTH_REFERENCE_SKETCH = "ToothThicknessReference"
GAP_FLOOR_SKETCH = "GapFloorReference"
WEB_REFERENCE_SKETCH = "WebReference"
REFERENCE_SKETCHES = (TOOTH_REFERENCE_SKETCH, GAP_FLOOR_SKETCH, WEB_REFERENCE_SKETCH)

# RV-03's accepted T012 web (rule 20: on a native dimension, never in note
# text, the dt-pinion-cam RV-01 form): a hidden construction line from the
# largest printed bore out to the smallest printed root envelope, along the
# T012 gap bisector at WEB_REFERENCE_ANGLE_DEG (tooth zero on +X, gaps every
# 30 deg from 15), printed as the single limit ".0797 MIN".  Only the T012
# sheet imports it; the line's geometry is T012's, whichever configuration
# is active.
WEB_REFERENCE_TEETH = 12
WEB_REFERENCE_ANGLE_DEG = 225.0
WEB_MIN_PLACES = 4
WEB_MIN_TOL_TYPE = 5  # swTolType_e.swTolMIN


@lru_cache(maxsize=None)
def web_reference_mm() -> tuple[float, float, tuple[float, float]]:
    """(start radius, printed MIN, band up to the printed best case) of the
    T012 web reference line: the largest printed bore's radius, the ruled
    web floored to the printed places, and that MIN's (upper, 0) band."""
    teeth = WEB_REFERENCE_TEETH
    start = inch_grid_mm(
        bore_dia_mm(teeth) + BORE_DIA_BAND[0], BORE_BAND_PLACES, math.ceil
    ) / 2.0
    minimum = inch_grid_mm(terminal_web_mm(teeth), WEB_MIN_PLACES, math.floor)
    if minimum < WEB_EXCEPTIONS_MM[teeth] - 1e-9:
        raise AssertionError("T012 web falls below RV-03's ruled .0797 in")
    best = (floor_limits_mm(teeth)[1] - bore_dia_mm(teeth) - BORE_DIA_BAND[1]) / 2.0
    return start, minimum, (round(best - minimum, 6), 0.0)


# The blank sizes, actual circular pitch-thickness acceptance and
# functional root-envelope limits. ToothThickness and FloorDia are driving
# dimensions in construction-only INSPECTION sketches, not cutter controls.
# The finite translated root is an off-centre arc, not a bowed ideal chord.
# Native tolerances remain meaningful: the pitch thickness has its retained
# bilateral band; the root envelope has the qualified per-count LIMIT pair.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlankProfile": {"BlankDia"},
    "Blank": {"FaceWidth"},
    "BoreProfile": {"BoreCutDia", "BoreAF", "BoreFlatClock"},
    TOOTH_REFERENCE_SKETCH: {"ToothThickness"},
    GAP_FLOOR_SKETCH: {"FloorDia"},
    WEB_REFERENCE_SKETCH: {"WebMin"},
}

# Blank band below the printed outside diameter, undersize only, so the
# closing corner keeps root clearance (user ruling 2026-10-10: ordinary
# 0/-.002 in). Every corner must still keep finite cutter support, tip land,
# root air and web before construction.
BLANK_DIA_BAND = (0.0, -0.0508)
# T006 keeps its own bands (pending exception ruling #971, user ruling 2026-10-10):
# DT6-FORM1's relief leaves no flank for a tooth thicker than the tool, and a
# thinner or smaller T006 loses the tip land. build_dt_cone_gear writes every
# configuration's band into that configuration (IDimensionTolerance.SetValues2).
CUSTOM_SIX_TOOTH_THICKNESS_BAND = (0.0, -0.04064)  # 0/-.0016 in
CUSTOM_SIX_BLANK_DIA_BAND = (0.0, -0.02032)  # 0/-.0008 in


def tooth_thickness_band(teeth: int) -> tuple[float, float]:
    _require_member(teeth)
    return CUSTOM_SIX_TOOTH_THICKNESS_BAND if teeth == 6 else TOOTH_THICKNESS_BAND


def blank_dia_band(teeth: int) -> tuple[float, float]:
    _require_member(teeth)
    return CUSTOM_SIX_BLANK_DIA_BAND if teeth == 6 else BLANK_DIA_BAND


# DT6-FORM1's cutting edge, defined for the toolmaker (machinist review of the
# stack build: reference widths left the relief undefined). T006 is a spur
# gear cut on centre, so the tool's edge IS the T006 gap. Each point is given
# at its radius R from the gear axis, in the tool's frame: X across from the
# tool centerline, Y along it from the tip center (the root on the gap
# centerline). The tip is the root arc; above the junction the edge is the
# standard involute, and its rows are check points on it.
#
# Between the tip and the junction the edge is the straight lines between the
# rows (machinist review of the round-2 build: points alone let templates
# differ between them). The model's relief is a drum-tip trochoid, which no
# shop can lay out, so its rows are the corners where tangents to it at the
# relief stations meet. The relief bulges toward the tooth, so those tangent
# lines never cut inside it: the drawn relief is the model's or wider (by at
# most 0.006 mm), and a wider relief only adds drum-tip air. The
# corners print rounded toward the tooth on the .0001 in grid, the end rows
# (on the tip arc and on the involute) to the nearest place.
#
# The edge may grind wide, never narrow, by half the T006 thinning band: a
# uniformly wide tool cuts the thin-limit tooth that the backlash, drum-tip
# relief clearance and over-pins limits already cover.
CUSTOM_SIX_FORM_TOLERANCE_MM = -CUSTOM_SIX_TOOTH_THICKNESS_BAND[1] / 2.0
CUSTOM_SIX_FORM_TOLERANCE_NOTE = (
    f"FORM TOLERANCE: X +{inch_text(CUSTOM_SIX_FORM_TOLERANCE_MM, 4)} / -.0000"
)
_CUSTOM_SIX_RELIEF_STATIONS_MM = (1.110, 1.125, 1.150, 1.200, 1.250, 1.300, 1.400, 1.500)
_CUSTOM_SIX_INVOLUTE_RADII_MM = (1.750, 1.900, 2.000)
# The table prints decimal inch at four places.
FORM_PLACES = 4


def custom_six_gap_half_angle_rad(radius_mm: float) -> float:
    """Half the T006 gap's angle at ``radius_mm``: the relief below the
    junction, the standard involute (closed form) above it."""
    template = cutter_template(6)
    if radius_mm < template.relief_junction_radius_mm:
        return template.relief_half_angle_rad(radius_mm)
    roll = math.sqrt((radius_mm / template.base_radius_mm) ** 2 - 1.0)
    return template.half_space_base_angle_rad + roll - math.atan(roll)


def _relief_point_and_tangent(radius_mm: float):
    """Table (X, Y) and tangent of the model relief at ``radius_mm``."""
    template = cutter_template(6)
    phi = template.relief_parameter_at_radius(radius_mm)
    radial, across = template.relief_point(phi)
    d_radial, d_across = template.relief_derivative(phi)
    return (across, radial - template.root_radius_mm), (d_across, d_radial)


def _row(x: float, y: float, root: float) -> tuple[float, float, float]:
    return math.hypot(x, y + root), x, y


@lru_cache(maxsize=None)
def custom_six_form_points_mm() -> tuple[tuple[float, float, float], ...]:
    """(R, X, Y) along DT6-FORM1's edge, tip center first, up to the blank OD."""
    template = cutter_template(6)
    profile = stock_form_profile(6)
    root = template.root_radius_mm
    junction = template.relief_junction_radius_mm
    stations = (root, *_CUSTOM_SIX_RELIEF_STATIONS_MM, junction)
    if not all(a < b for a, b in zip(stations, stations[1:])):
        raise ValueError("T006 relief stations must rise from the root to the junction")
    tangents = [_relief_point_and_tangent(radius) for radius in stations]
    corners = []
    for (p0, d0), (p1, d1) in zip(tangents, tangents[1:]):
        # Rising toward the tip, the edge must turn toward the centerline.
        cross = d0[0] * d1[1] - d0[1] * d1[0]
        if cross <= 0.0:
            raise ValueError("T006 relief must bulge toward the tooth between stations")
        reach = ((p1[0] - p0[0]) * d1[1] - (p1[1] - p0[1]) * d1[0]) / cross
        corners.append((p0[0] + reach * d0[0], p0[1] + reach * d0[1]))

    def nearest(value: float) -> float:
        return inch_grid_mm(value, FORM_PLACES)

    (tip_x, tip_y), (junction_x, junction_y) = tangents[0][0], tangents[-1][0]
    points = [(root, 0.0, 0.0), _row(nearest(tip_x), nearest(tip_y), root)]
    points += [
        _row(
            inch_grid_mm(x, FORM_PLACES, math.ceil),
            inch_grid_mm(y, FORM_PLACES, math.floor),
            root,
        )
        for x, y in corners
    ]
    points.append(_row(nearest(junction_x), nearest(junction_y), root))
    for radius in sorted({*_CUSTOM_SIX_INVOLUTE_RADII_MM, profile.pitch_radius_mm,
                          profile.blank_radius_mm}):
        if not junction < radius <= profile.blank_radius_mm:
            raise ValueError("T006 involute check points must lie above the junction")
        angle = custom_six_gap_half_angle_rad(radius)
        points.append((radius, radius * math.sin(angle), radius * math.cos(angle) - root))
    return tuple(points)


def configuration_number(part_number: str, teeth: int) -> str:
    """Return one configuration sheet's drawing number, e.g. ``MHA-DT-03-T006``."""
    _require_member(teeth)
    number = part_number.strip().upper()
    if not number:
        raise ValueError("cone-gear part number must not be blank")
    return f"{number}-T{teeth:03d}"


# --- Decimal places, authored ON THE PART ------------------------------------
#
# drawing-simplicity-policy.md `How the repository implements the guidelines`: places and bands are model properties.  Decimal inch (#290):
# four places on the fitted bore and across-flat (their +.0018/+.0010 and
# +.0008/+.0004 bands), the tooth thickness and the gap-floor limits, so
# both ends of each narrow floor window print without rounding inward.  The
# tip diameter prints four too: its own BLANK_DIA_BAND (below) needs them on
# T006, and every blank is floored to that grid, so the printed size is the
# modelled one.  The face width prints four, like the cylinder gear's
# OverallThickness under the same rule: three would round its nominal by a
# third of the +/-.001 band.  The flat clock prints one place of degrees,
# the cylinder gear's NotchPhase precedent: +/-0.25 needs no more.  RV-03's
# T012 web prints its ruled .0797 MIN at four.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlankProfile": {"BlankDia": 4},
    "Blank": {"FaceWidth": 4},
    "BoreProfile": {
        "BoreCutDia": BORE_BAND_PLACES, "BoreAF": BORE_AF_PLACES, "BoreFlatClock": 1,
    },
    TOOTH_REFERENCE_SKETCH: {"ToothThickness": 4},
    GAP_FLOOR_SKETCH: {"FloorDia": 4},
    WEB_REFERENCE_SKETCH: {"WebMin": WEB_MIN_PLACES},
}

# The drawing reads this flat view back off the sheet: a dimension name is
# unique across the features that expose one, and a marked dimension nobody
# authored places for would otherwise print SolidWorks' template default.
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"{_feature}: precision authored for unmarked dimensions {_unmarked}"
        )
