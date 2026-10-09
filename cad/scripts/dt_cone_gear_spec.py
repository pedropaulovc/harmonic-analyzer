r"""Pure-data dimensional contract shared by the cone-gear family and drawing.

The cone gear is a 20-member configured family (T006..T120 by 6).  The drawing
package gives every configuration its own complete sheet: configuration-owned
tip and bore diameters, common face width, and a native driving tooth-thickness
dimension with the cone-specific deepened-mesh band.

This module stays free of tolerances.yaml because assemblies import it.  The
bore bands -- the round bore and its across-flat -- derive from the shaft's
land bands (cone_shaft_land_bands) through the gear seat fit (gear_seat_fit),
two small import-free modules; every other band is a cone-specific constant.
The drawing merely imports the resulting native model dimensions, precision,
and tolerances.
"""

from __future__ import annotations

import math

import _config
from cone_pitch import SEAT_PITCH
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from cone_shaft_land_bands import (
    FLAT_AF_BAND,
    SECTION_CONE_GEAR_TEETH,
    SECTION_DIA_BANDS,
    SECTION_FLAT_AF,
    TERMINAL_DIA_MM,
)
from gear_seat_fit import flat_bore_af_band, seat_bore_band


MM_PER_IN = 25.4

# Family alloy split (config-owned, cad/config/parts/dt-cone-gear.yaml): the
# title-block material (C36000) covers T030-T120; the four tip gears are the
# harder alloy below (dimensions.yaml ch.12 p.21).
_MFG = _config.parts("dt-cone-gear")
BODY_MATERIAL_SPEC = str(_MFG["material_specification"])
TIP_MATERIAL_SPEC = str(_MFG["material_tip_specification"])

TEETH = int(_config.machine("gear_train", "fundamental_cone_teeth"))
CONFIGURATION_TEETH = tuple(range(6, TEETH + 1, 6))
DIAMETRAL_PITCH = _config.machine("gear_train", "diametral_pitch")
PRESSURE_ANGLE_DEG = _config.machine("gear_train", "pressure_angle_deg")
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH * MODULE_MM
TOOTH_FORM = "INVOLUTE FLANKS; FLOOR ANY SHAPE, NOT BELOW FLOOR DIA"
STANDARD_TOOTH_THICKNESS = math.pi * MODULE_MM / 2.0

# --- Deepened mesh (U38 option 1b, user ruling U42, 2026-09-23) ---------------
#
# The cone axis stays where it is.  Each custom tip/thickness pair controls
# engagement with the standard 120T drum (MHA-DT-012); the six-tooth special
# has a truncated standard tip, while the other blanks have long addenda.
# The tight corner must retain ``MESH_BACKLASH_MIN_MM`` with the thickest tooth
# and bore-on-land/drum-on-arbor runouts closing the deep transverse slice.
# Least engagement adds the journal and arbor float opening.  The configured
# PA20 family balances contact ratio against the smallest tip land and the
# standard drum root clearance.  Tips print at two places and thicknesses at
# three; ``test_dt_cone_gear_mesh_design`` reconstructs the retained backlash,
# tip-land, floor-air and contact-ratio guards.
#
# T006-T036 remain below 1.1 at the worst opening corner.  The shortfall set
# records the inherited small-cone contact-ratio screen, not stock-cutter
# approval or a continuous loaded-contact certificate.
MESH_BACKLASH_MIN_MM = 0.06
# (upper, lower) about the modelled mid thickness.  The 0.15 window is the
# configured cone<->cylinder backlash window (tolerances.yaml gear_mesh
# 0.05..0.20) that error_budget.yaml's tooth-thickness mesh-lag term is
# derived from.
TOOTH_THICKNESS_BAND = (0.075, -0.075)
# Backlash with MHA-DT-012, rocked by hand over a full turn at assembly, swing
# stop set.  The acceptance is that measurement's worst case and nothing more:
# thickest tooth with both runouts closing, to thinnest tooth with both runouts
# and both journal floats opening (rocking takes up the cone-shaft journal and
# drum-arbor clearances).  The upper limit is the loosest modeled printed
# corner, rounded up to the assembly acceptance's two places.
BACKLASH_ACCEPTANCE_MM = (0.06, 0.41)
CONTACT_RATIO_EXCEPTION_TEETH = (6, 12, 18, 24, 30, 36)
# teeth: (tip diameter, thickest circular tooth thickness at the standard
# pitch circle), mm.
DEEPENED_MESH_MM: dict[int, tuple[float, float]] = {
    6: (4.16, 0.893),
    12: (7.47, 0.893),
    18: (10.73, 0.893),
    24: (13.97, 0.893),
    30: (17.18, 0.893),
    36: (20.39, 0.893),
    42: (23.57, 0.893),
    48: (26.75, 0.893),
    54: (29.92, 0.893),
    60: (33.10, 0.893),
    66: (36.27, 0.893),
    72: (39.45, 0.892),
    78: (42.62, 0.892),
    84: (45.80, 0.892),
    90: (48.97, 0.892),
    96: (52.15, 0.892),
    102: (55.32, 0.892),
    108: (58.50, 0.892),
    114: (61.67, 0.892),
    120: (64.85, 0.892),
}


def _require_member(teeth: int) -> None:
    if teeth not in CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")


def outside_dia_mm(teeth: int) -> float:
    """Return the configuration's nominal tip (blank) diameter."""
    _require_member(teeth)
    return DEEPENED_MESH_MM[teeth][0]


def tooth_thickness_mm(teeth: int) -> float:
    """Return the modelled (mid-band) circular tooth thickness at pitch."""
    _require_member(teeth)
    return DEEPENED_MESH_MM[teeth][1] - TOOTH_THICKNESS_BAND[0]


OUTSIDE_DIA = outside_dia_mm(TEETH)
TOOTH_THICKNESS = tooth_thickness_mm(TEETH)

BORE_DIA = 0.375 * MM_PER_IN  # 9.525 (3/8") at T120; smaller on the tip gears
# Face width (user ruling 2026-09-28): the cone set is a solid stack.  Every
# gear is one seat pitch thick, so each bears on its neighbour and the stack
# on MHA-DT-007 sets every station (dt_cone_gear_stack); no gear is bonded.  The
# face is SEAT_PITCH floored to the four places it prints, so the modelled
# stack closes without interference.  Every gear grew SOUTH: its north face
# stays on the station layout (cone_line), so T006's north face -- the
# datum the MHA-VN-016 stack collar is feelered off -- does not move.  The band
# is the cylinder bank's L20 d' rule (+/-0.025 per gear, the 20-gear stack
# accepted at +/-0.20), so it is faced to a micrometer on both sides.
FACE_WIDTH = math.floor(SEAT_PITCH * 1e4) / 1e4
FACE_WIDTH_BAND = (0.025, -0.025)
# Flat clock (user ruling 2026-09-28): the bore's D-flat is the gear's
# angular datum on MHA-DT-004, and its outward normal passes through the centre
# of the phase-0 tooth on local +X, so every gear keeps the clock it is
# placed at.  Index the teeth off the flat on one setup; the native
# BoreFlatClock angular dimension carries this band (error_budget.yaml
# cone_flat_clock), the cylinder gear's CAM_PHASE_TOLERANCE_DEG precedent.
FLAT_CLOCK_TOLERANCE_DEG = 0.25


def chord_floor_radius_mm(
    teeth: int, *, thickness_mm: float, tmin: float = 0.0
) -> float:
    """Return the radius, on the gap centre line, of the straight feet chord.

    The chord joins the two flank feet at involute parameter ``tmin`` (0: on
    the base circle) for a tooth ``thickness_mm`` thick at the standard pitch
    circle.  A thicker tooth pulls the feet together, so the chord rises.
    This mirrors ``involute_gear.floor_point`` with no dip.
    """
    _require_member(teeth)
    pressure_angle = math.radians(PRESSURE_ANGLE_DEG)
    pitch_radius = teeth * MODULE_MM / 2.0
    base_radius = pitch_radius * math.cos(pressure_angle)
    delta = (
        thickness_mm / (2.0 * pitch_radius)
        + math.tan(pressure_angle)
        - pressure_angle
    )
    roll = tmin - math.atan(tmin)
    half_gap_angle = math.pi / teeth - delta + roll
    return base_radius * math.hypot(1.0, tmin) * math.cos(half_gap_angle)


# --- Gap floor (U38/U40, Main + user rulings 2026-09-23) ----------------------
#
# The floor prints as native MIN/MAX limits independent of tooth thickness.
# A cutter's stamped count range does not prove that its actual profile can
# meet those limits and the required flanks, thickness and backlash together.
# Three constructions retain the same six-entity gap sketch:
#
# * T006-T024: the floor bows below the thickened tooth's base chord to the
#   configured dipped MIN.  T006's reduced root-to-bore web is experimental;
#   production approval requires a new ruling, not the historical U40 value.
# * T030-T036: the chord between the flank feet on the base circle.
# * T042-T120: ``GAP_FLOOR_TMIN`` starts the flanks above the base circle.
#   The retained raised-floor air and gap-foot width are checked independently
#   of any stock form cutter's profile/root compatibility.
#
# Every gear also prints a MAX (Main, 2026-09-23 for T006/T012; 2026-09-26
# for the rest, after the #834 machinist review found sheets 3-20 left the
# gap depth open): the shallowest floor that keeps 0.02 of drum-tip clearance
# with every runout closing, floored to the printed three places.  A floor
# above it would rub the drum tip; test_dt_cone_gear_mesh_design re-derives each
# value from the assembly pose.
DIPPED_FLOOR_MIN_MM: dict[int, float] = {6: 2.346, 12: 5.521, 18: 8.696, 24: 11.871}
FLOOR_MAX_DIA_MM: dict[int, float] = {
    6: 2.406,
    12: 5.581,
    18: 8.756,
    24: 11.931,
    30: 15.106,
    36: 18.281,
    42: 21.456,
    48: 24.631,
    54: 27.806,
    60: 30.981,
    66: 34.156,
    72: 37.331,
    78: 40.506,
    84: 43.681,
    90: 46.856,
    96: 50.031,
    102: 53.206,
    108: 56.381,
    114: 59.556,
    120: 62.731,
}
GAP_FLOOR_TMIN: dict[int, float] = {
    42: 0.0410,
    48: 0.1320,
    54: 0.1725,
    60: 0.1995,
    66: 0.2190,
    72: 0.2345,
    78: 0.2465,
    84: 0.2565,
    90: 0.2650,
    96: 0.2720,
    102: 0.2780,
    108: 0.2835,
    114: 0.2880,
    120: 0.2925,
}


def floor_tmin(teeth: int) -> float:
    """Return the involute parameter where the flanks meet the floor."""
    _require_member(teeth)
    return GAP_FLOOR_TMIN.get(teeth, 0.0)


def floor_radius_mm(teeth: int) -> float:
    """Return the modelled gap-floor radius, printed as the MIN diameter."""
    if teeth in DIPPED_FLOOR_MIN_MM:
        return DIPPED_FLOOR_MIN_MM[teeth] / 2.0
    return chord_floor_radius_mm(
        teeth, thickness_mm=tooth_thickness_mm(teeth), tmin=floor_tmin(teeth)
    )


def floor_limits_mm(teeth: int) -> tuple[float, float]:
    """Return the printed (MIN, MAX) gap-floor diameters.

    The MIN is the modelled floor floored to the printed three places: a band
    rounds outward, so the sheet never demands a floor above the model's
    (rounding to nearest raised nine of the twenty MINs by up to 0.0005).
    """
    _require_member(teeth)
    minimum = math.floor(2.0 * floor_radius_mm(teeth) * 1000.0 + 1e-6) / 1000.0
    return minimum, FLOOR_MAX_DIA_MM[teeth]


def floor_dip_mm(teeth: int) -> float:
    """Return how far the modelled floor bows below its feet chord."""
    chord = chord_floor_radius_mm(
        teeth, thickness_mm=tooth_thickness_mm(teeth), tmin=floor_tmin(teeth)
    )
    return chord - floor_radius_mm(teeth)


def bore_dia_mm(teeth: int) -> float:
    """Return the configured bore that fits the matching stepped-shaft land."""
    _require_member(teeth)
    # T006/T012 share the actual terminal reader. Their strength acceptance
    # is rederived below from the current cutter-owned printed floor MINs.
    if teeth <= 12:
        return TERMINAL_DIA_MM
    if teeth == 18:
        return 0.125 * MM_PER_IN
    if teeth == 24:
        return 0.25 * MM_PER_IN
    return BORE_DIA


def material_specification(teeth: int) -> str:
    """Return the configuration-owned alloy printed in that sheet's title block."""
    _require_member(teeth)
    return TIP_MATERIAL_SPEC if teeth <= 24 else BODY_MATERIAL_SPEC


FAMILY_BORES_MM = {teeth: bore_dia_mm(teeth) for teeth in CONFIGURATION_TEETH}

# Worst web uses the CURRENT cutter-owned printed MIN and maximum fit bore.
# The sole special web is the user's T006 >=0.62 ruling; T012 must achieve
# the ordinary 2.0 target, not merely the 1.5 hard floor.
MACHINED_WEB_FLOOR_MM = 1.5
MACHINED_WEB_TARGET_MM = 2.0
WEB_EXCEPTIONS_MM: dict[int, float] = {6: 0.62}
TERMINAL_WEB_REQUIREMENTS_MM = {
    6: WEB_EXCEPTIONS_MM[6],
    12: MACHINED_WEB_TARGET_MM,
}

# Printed places of the bore band (model-owned, DRAWING_PRECISION).
BORE_BAND_PLACES = 3


# The band is UNIFORM, not per land, for two reasons.  BoreCutDia is one model
# dimension across all 20 configurations, and SOLIDWORKS 2026 rejects the
# per-configuration IDimensionTolerance.SetValues2 on some dimension types
# (_drawing_marks). The one band is the intersection of the retained seat
# fit and BOTH terminal-web guards, using current cutter floor readers.
def _seat_fit_band() -> tuple[float, float]:
    """(upper, lower): the round seat fit that holds on every gear land."""
    carried = [
        seat_bore_band(band)
        for band, teeth in zip(SECTION_DIA_BANDS, SECTION_CONE_GEAR_TEETH)
        if teeth
    ]
    return (min(band[0] for band in carried), max(band[1] for band in carried))


def _terminal_web_upper() -> float:
    """Largest bore deviation satisfying both current terminal floor MINs."""
    scale = 10**BORE_BAND_PLACES
    cap = min(
        floor_limits_mm(teeth)[0] - 2.0 * minimum
        - math.ceil(bore_dia_mm(teeth) * scale - 1e-9) / scale
        for teeth, minimum in TERMINAL_WEB_REQUIREMENTS_MM.items()
    )
    return math.floor(cap * scale + 1e-9) / scale


BORE_BAND_FIT_UPPER, BORE_BAND_LOWER = _seat_fit_band()
BORE_BAND_WEB_UPPER = _terminal_web_upper()
# No named fit changes: the current floor cap may permit a looser bore, but
# it can never exceed the retained gear-seat clearance class.
BORE_DIA_BAND = (
    round(min(BORE_BAND_FIT_UPPER, BORE_BAND_WEB_UPPER), BORE_BAND_PLACES),
    round(BORE_BAND_LOWER, BORE_BAND_PLACES),
)
if BORE_DIA_BAND[0] - BORE_DIA_BAND[1] < 0.02 - 1e-9:
    raise AssertionError(
        f"cone-gear seat bore band {BORE_DIA_BAND[0]:+.3f}/"
        f"{BORE_DIA_BAND[1]:+.3f} is under 0.02 wide"
    )


def terminal_web_mm(teeth: int) -> float:
    """Print-worst radial ligament, read from the actual cutter and fit."""
    if teeth not in TERMINAL_WEB_REQUIREMENTS_MM:
        raise ValueError(f"T{teeth:03d} is not carried by the terminal land")
    scale = 10**BORE_BAND_PLACES
    maximum_bore = math.ceil((bore_dia_mm(teeth) + BORE_DIA_BAND[0]) * scale - 1e-9) / scale
    return (floor_limits_mm(teeth)[0] - maximum_bore) / 2.0


for _teeth, _minimum in TERMINAL_WEB_REQUIREMENTS_MM.items():
    if terminal_web_mm(_teeth) < _minimum - 1e-9:
        raise AssertionError(f"T{_teeth:03d} current cutter floor misses its web guard")


# --- D-bore (user ruling 2026-09-28) -----------------------------------------
#
# Every bore is a D: the round bore above plus one flat, parallel to the
# land's flat, whose outward normal is local +X (through the phase-0 tooth,
# FLAT_CLOCK_TOLERANCE_DEG).  Across-flat (AF) is measured from the flat to
# the far side of the round bore, the land's own AF nominal; the band keeps
# 0.01-0.03 AF clearance on the land's FLAT_AF_BAND.  One band for all twenty,
# so one BoreAF tolerance serves every configuration.
BORE_AF_BAND = flat_bore_af_band(FLAT_AF_BAND)  # (+0.020, +0.010)
BORE_AF_PLACES = 3


def land_section(teeth: int) -> int:
    """Index of the MHA-DT-004 land (cone_shaft_land_bands) carrying ``teeth``."""
    _require_member(teeth)
    for section, carried in enumerate(SECTION_CONE_GEAR_TEETH):
        if teeth in carried:
            return section
    raise AssertionError(f"no MHA-DT-004 land carries the T{teeth:03d} cone gear")


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


def bore_surface_finish(teeth: int) -> SurfaceFinishControl:
    """Return the bore finish control qualified by this configuration's bore."""
    return SurfaceFinishControl(
        "cone_gear_bore",
        MACHINED_UM,
        CylinderFace(bore_dia_mm(teeth)),
        native_attachment="model",
    )


# Part PMI is authored while the default T120 configuration is active.  Each
# drawing sheet resolves "cone_gear_bore" from ITS configuration's finish rows
# in ``BORE_SURFACE_FINISHES`` so native face validation follows that sheet's
# bore (the T120 row would reject the T006 1/16 in bore).
SURFACE_FINISHES = (bore_surface_finish(TEETH),)
BORE_SURFACE_FINISHES: dict[int, tuple[SurfaceFinishControl, ...]] = {
    teeth: (bore_surface_finish(teeth),) for teeth in CONFIGURATION_TEETH
}

# The part's two construction-only authoring sketches.  The part saves both
# hidden (they would otherwise render in every assembly that places a gear);
# the sheet's front view shows them again to import their dimensions.
TOOTH_REFERENCE_SKETCH = "ToothThicknessReference"
GAP_FLOOR_SKETCH = "GapFloorReference"
REFERENCE_SKETCHES = (TOOTH_REFERENCE_SKETCH, GAP_FLOOR_SKETCH)

# The three blank sizes, the tooth-system acceptance size and the gap-floor
# limits.  ToothThickness and FloorDia are DRIVING dimensions in
# construction-only authoring sketches: policy rule 2 permits that pattern
# when the printed value is not itself a solid feature dimension (the gap
# floor is an involute-profile chord bowed by FloorDip, with no diameter of
# its own).  Neither is a reference-status drawing dimension, so their native
# tolerances remain meaningful: ToothThickness a bilateral band, FloorDia the
# per-configuration floor_limits_mm pair as LIMIT tolerance.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlankProfile": {"BlankDia"},
    "Blank": {"FaceWidth"},
    "BoreProfile": {"BoreCutDia", "BoreAF", "BoreFlatClock"},
    TOOTH_REFERENCE_SKETCH: {"ToothThickness"},
    GAP_FLOOR_SKETCH: {"FloorDia"},
}

# The long-addendum oblique mesh requires a controlled cone tip to retain
# engagement at the worst opening corner.  The existing tip band is unchanged;
# tests reconstruct its contact ratio, tip land and standard drum-root air.
BLANK_DIA_BAND = (0.10, -0.10)


def configuration_number(part_number: str, teeth: int) -> str:
    """Return one configuration sheet's drawing number, e.g. ``MHA-DT-003-T006``."""
    _require_member(teeth)
    number = part_number.strip().upper()
    if not number:
        raise ValueError("cone-gear part number must not be blank")
    return f"{number}-T{teeth:03d}"


# --- Decimal places, authored ON THE PART ------------------------------------
#
# Policy rule 2: places and bands are model properties.  Three places belong
# on the fitted bore, across-flat, tooth thickness and gap-floor limits, so
# both ends of each narrow floor window print without rounding inward.
# Tip diameter prints two places with its own BLANK_DIA_BAND (below); face
# width prints four, like the cylinder gear's OverallThickness under the same
# rule: three would round one limit of the +/-0.025 band inward.  The flat
# clock prints one place of degrees, the cylinder gear's NotchPhase precedent:
# +/-0.25 needs no more.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlankProfile": {"BlankDia": 2},
    "Blank": {"FaceWidth": 4},
    "BoreProfile": {"BoreCutDia": 3, "BoreAF": BORE_AF_PLACES, "BoreFlatClock": 1},
    TOOTH_REFERENCE_SKETCH: {"ToothThickness": 3},
    GAP_FLOOR_SKETCH: {"FloorDia": 3},
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
