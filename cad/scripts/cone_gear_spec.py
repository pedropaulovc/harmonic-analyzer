r"""Pure-data dimensional contract shared by the cone-gear family and drawing.

The cone gear is a 20-member configured family (T006..T120 by 6).  The drawing
package gives every configuration its own complete sheet: configuration-owned
tip and bore diameters, common face width, and a native driving tooth-thickness
dimension with the cone-specific deepened-mesh band.

This module stays free of tolerances.yaml because assemblies import it.  The
bore band derives from the shaft's land bands (cone_shaft_land_bands) through
the shared bonded-joint fit (retained_joint_fit), two small import-free
modules; every other band is a cone-specific constant.  The drawing merely
imports the resulting native model dimensions, precision, and tolerances.
"""

from __future__ import annotations

import math

import _config
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from cone_shaft_land_bands import SECTION_CONE_GEAR_TEETH, SECTION_DIA_BANDS
from retained_joint_fit import bonded_bore_band


MM_PER_IN = 25.4

# Family alloy split (config-owned, cad/config/parts/cone-gear.yaml): the
# title-block material (C36000) covers T030-T120; the four tip gears are the
# harder alloy below (dimensions.yaml ch.12 p.21).
_MFG = _config.parts("cone-gear")
BODY_MATERIAL_SPEC = str(_MFG["material_specification"])
TIP_MATERIAL_SPEC = str(_MFG["material_tip_specification"])

TEETH = 120  # default/fundamental configuration
CONFIGURATION_TEETH = tuple(range(6, 121, 6))
DIAMETRAL_PITCH = 49.82  # cad/config/machine/gear_train.yaml
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH * MODULE_MM
TOOTH_FORM = "INVOLUTE FLANKS; FLOOR ANY SHAPE, NOT BELOW FLOOR DIA"
STANDARD_TOOTH_THICKNESS = math.pi * MODULE_MM / 2.0

# --- Deepened mesh (U38 option 1b, user ruling U42, 2026-09-23) ---------------
#
# The cone axis stays where it is; each gear reaches deeper into its 120T drum
# (MHA-027, cut standard) through a long addendum -- an oversize blank -- and a
# tooth thickened so the tightest printed case still keeps
# ``MESH_BACKLASH_MIN_MM``.  Tightest case: thickest tooth with the cone
# bore-on-land and drum bore-on-arbor runouts closing the deep-edge centre
# distance at the as-posed interleave.  The cone runout is sized for the
# 0/-0.05 soldered shaft seats (#839) under this +0.05/0 bore: 0.05 radial.
# Least engagement adds the journal and arbor float opening.  Each OD is the
# smallest that reaches worst-case CR 1.20 (T060+), else the largest
# that keeps the tip land >= 0.10 at the thinnest tooth and largest OD and the
# cone tip >= 0.10 off the drum's chord floor (T006-T054).  ODs print two
# places and are floored to them; thicknesses print three places, floored
# toward more backlash.  ``test_cone_gear_mesh_design`` re-derives every
# constraint from these printed values.
#
# Contact ratio stays below 1.1 at the worst case of the printed bands on
# T006-T042: the tooth comes to a point before it reaches deeper.  The user
# accepted that as a named book-fidelity exception (U42): it costs wear on the
# tooth-tip corners, not position error (rigid transmission error at most
# 0.023 mm at the drum pitch line, on T006; <= 0.004 on the rest).
MESH_BACKLASH_MIN_MM = 0.06
# (upper, lower) about the modelled mid thickness.  The 0.15 window is the
# configured cone<->cylinder backlash window (tolerances.yaml gear_mesh
# 0.05..0.20) that error_budget.yaml's tooth-thickness mesh-lag term is
# derived from.
TOOTH_THICKNESS_BAND = (0.075, -0.075)
# Backlash with MHA-027, rocked by hand over a full turn at assembly, swing
# stop set.  The acceptance is that measurement's worst case and nothing more:
# thickest tooth with both runouts closing, to thinnest tooth with both runouts
# and both journal floats opening (rocking takes up the cone-shaft journal and
# drum-arbor clearances).  The upper, 0.374 on T006, is rounded up to two
# places.
BACKLASH_ACCEPTANCE_MM = (0.06, 0.38)
CONTACT_RATIO_EXCEPTION_TEETH = (6, 12, 18, 24, 30, 36, 42)
# teeth: (tip diameter, thickest circular tooth thickness at the standard
# pitch circle), mm.
DEEPENED_MESH_MM: dict[int, tuple[float, float]] = {
    6: (4.28, 1.006),
    12: (7.55, 1.005),
    18: (10.74, 1.004),
    24: (13.90, 1.003),
    30: (17.04, 1.002),
    36: (20.17, 1.001),
    42: (23.29, 1.001),
    48: (26.39, 1.000),
    54: (29.49, 0.999),
    60: (32.52, 0.999),
    66: (35.55, 0.998),
    72: (38.58, 0.998),
    78: (41.62, 0.997),
    84: (44.66, 0.997),
    90: (47.70, 0.996),
    96: (50.74, 0.996),
    102: (53.79, 0.995),
    108: (56.84, 0.995),
    114: (59.88, 0.995),
    120: (62.93, 0.994),
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
# U27 face width (Main ruling, 2026-09-23): 6.0 at the .X band keeps the
# widest gear (6.8) inside the 6.889 seat pitch; 6.5 +/-0.51 could reach
# 7.01 and overlap a neighbour.  The drum's engaged zone spans
# [-0.75, +1.35] mm about the narrowed gear's centre, inside the 5.2 minimum.
FACE_WIDTH = 6.0


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
# The floor is cut to depth and printed as a MIN diameter; the tooth reaches
# its thickness by widening the gap with an indexing offset, never by sinking
# the cutter, so the floor does not move with the tooth band.  Three
# constructions, all one six-entity gap sketch:
#
# * T006, T012: the thicker tooth's chord would sit in the drum tip's path
#   (+0.030 at T006), so the floor bows below the feet chord to the printed
#   MIN.  These two also print a MAX (Main, 2026-09-23): the drum tip clears
#   them by as little as 0.05, so a shallow plunge would rub.  MAX is the
#   shallowest floor that keeps 0.02 of drum-tip clearance with every runout
#   closing.  MIN is the web limit: T006 keeps the 0.621 web the user ruled
#   on as its named exception (U40); T012 trades its web from 2.12 down to
#   2.05, still over the 2.0 target, for a 0.25 window instead of 0.11.
# * T018-T042: the chord between the flank feet on the base circle.
# * T048-T120: the flanks start at ``GAP_FLOOR_TMIN`` above the base circle,
#   which raises the floor until the drum tip clears it by 0.30 at the worst
#   case.  The gap is then shallower and wider at the floor, so one fly
#   cutter at least 0.43 wide fits every gear.
FLOOR_LIMITS_MM: dict[int, tuple[float, float]] = {
    6: (2.880, 2.929),
    12: (5.738, 5.988),
}
GAP_FLOOR_TMIN: dict[int, float] = {
    48: 0.0900,
    54: 0.1200,
    60: 0.1400,
    66: 0.1540,
    72: 0.1650,
    78: 0.1740,
    84: 0.1815,
    90: 0.1875,
    96: 0.1925,
    102: 0.1970,
    108: 0.2010,
    114: 0.2040,
    120: 0.2070,
}


def floor_tmin(teeth: int) -> float:
    """Return the involute parameter where the flanks meet the floor."""
    _require_member(teeth)
    return GAP_FLOOR_TMIN.get(teeth, 0.0)


def floor_radius_mm(teeth: int) -> float:
    """Return the modelled gap-floor radius, printed as the MIN diameter."""
    if teeth in FLOOR_LIMITS_MM:
        return FLOOR_LIMITS_MM[teeth][0] / 2.0
    return chord_floor_radius_mm(
        teeth, thickness_mm=tooth_thickness_mm(teeth), tmin=floor_tmin(teeth)
    )


def floor_dip_mm(teeth: int) -> float:
    """Return how far the modelled floor bows below its feet chord."""
    chord = chord_floor_radius_mm(
        teeth, thickness_mm=tooth_thickness_mm(teeth), tmin=floor_tmin(teeth)
    )
    return chord - floor_radius_mm(teeth)


def bore_dia_mm(teeth: int) -> float:
    """Return the configured bore that fits the matching stepped-shaft land."""
    _require_member(teeth)
    # T006 and T012 share the 1/16 in terminal land (24.7 long after E1).
    # U40 S1: T012 1/16, T018 1/8 and T024 1/4 in, one land down each, so
    # their webs meet the U27 target.
    if teeth <= 12:
        return 0.0625 * MM_PER_IN
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

# U27 / policy rule 12: machined webs target >= 2.0 mm with a hard floor of
# 1.5 mm, between the printed MIN floor diameter and the maximum bore.  U40
# (user, 2026-09-23): T012, T018 and T024 each drop one shaft land so their
# webs meet the target; T006 has no compliant construction (its floor sits at
# r 1.44) and its web is the one named exception (book fidelity).
MACHINED_WEB_FLOOR_MM = 1.5
MACHINED_WEB_TARGET_MM = 2.0
WEB_EXCEPTIONS_MM: dict[int, float] = {6: 0.621}

# Printed places of the bore band (model-owned, DRAWING_PRECISION).
BORE_BAND_PLACES = 3


# The band is UNIFORM, not per land, for two reasons.  BoreCutDia is one model
# dimension across all 20 configurations, and SOLIDWORKS 2026 rejects the
# per-configuration IDimensionTolerance.SetValues2 on some dimension types
# (_drawing_marks).  And T006's named web (U40) caps the largest bore under its
# printed MIN floor: a per-land +0.085 would cut that web to 0.604.  So the one
# band is the intersection of the shared retained-joint fit (Main,
# 2026-09-25) over every land that carries a gear, with its upper limit the
# lower of two named limits.
def _bonded_fit_band() -> tuple[float, float]:
    """(upper, lower): the retained-joint fit that holds on every gear land."""
    carried = [
        bonded_bore_band(band)
        for band, teeth in zip(SECTION_DIA_BANDS, SECTION_CONE_GEAR_TEETH)
        if teeth
    ]
    return (min(band[0] for band in carried), max(band[1] for band in carried))


def _t006_web_upper() -> float:
    """Largest bore deviation that leaves T006 its named web, to print places."""
    web_cap = FLOOR_LIMITS_MM[6][0] - 2.0 * WEB_EXCEPTIONS_MM[6] - bore_dia_mm(6)
    scale = 10**BORE_BAND_PLACES
    return math.floor(web_cap * scale + 1e-9) / scale


BORE_BAND_FIT_UPPER, BORE_BAND_LOWER = _bonded_fit_band()  # +0.055, +0.025
BORE_BAND_WEB_UPPER = _t006_web_upper()  # +0.050 (0.0505 floored)
# (upper, lower): +0.050/+0.025.  Clearance 0.025-0.100 on the soldered seat
# lands, 0.025-0.070 on the running terminal land.
BORE_DIA_BAND = (
    round(min(BORE_BAND_FIT_UPPER, BORE_BAND_WEB_UPPER), BORE_BAND_PLACES),
    round(BORE_BAND_LOWER, BORE_BAND_PLACES),
)
if BORE_DIA_BAND[0] - BORE_DIA_BAND[1] < 0.02 - 1e-9:
    raise AssertionError(
        f"cone-gear bonded bore band {BORE_DIA_BAND[0]:+.3f}/"
        f"{BORE_DIA_BAND[1]:+.3f} is under 0.02 wide"
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

# The three blank sizes and the tooth-system acceptance size.  ToothThickness
# is a DRIVING dimension in a construction-only authoring sketch: policy rule 2
# permits that pattern when the printed value is not itself a solid feature
# dimension.  It is not a reference-status drawing dimension, so its native
# asymmetric tolerance remains meaningful.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlankProfile": {"BlankDia"},
    "Blank": {"FaceWidth"},
    "BoreProfile": {"BoreCutDia"},
    "ToothThicknessReference": {"ToothThickness"},
}

# Tip-diameter band, (upper, lower) deviations.  The tip sets how deep the
# cone teeth reach into the 120T drum on the backed-off oblique mesh, so the
# title-block .XX +/-0.51 (a whole addendum) is too loose: at -0.51 the
# nominal 0.470 mm interleave halves (Fable review, 2026-09-23).  Main ruled
# the band by contact ratio (U27: the looser +/-0.25 only if it keeps CR >= 1.1
# at the worst case).  Worst case of every printed band -- this band, drum OD
# +0/-0.10, bore-on-land, journal, drum-bore and arbor float -- leaves CR
# 0.09/0.42/0.46 (T006/T060/T120) at +/-0.10 and 0.01/0.28/0.30 at +/-0.25,
# with the drum floor still clear (+0.83 / +0.75), so +/-0.10 prints: turning
# the blank OD to a micrometer before cutting teeth is a novice-holdable step.
BLANK_DIA_BAND = (0.10, -0.10)


def configuration_number(part_number: str, teeth: int) -> str:
    """Return one configuration sheet's drawing number, e.g. ``MHA-013-T006``."""
    _require_member(teeth)
    number = part_number.strip().upper()
    if not number:
        raise ValueError("cone-gear part number must not be blank")
    return f"{number}-T{teeth:03d}"


# --- Decimal places, authored ON THE PART ------------------------------------
#
# Policy rule 2: places and bands are model properties.  Three places belong
# on the two fit dimensions: the bore and circular tooth thickness.  Tip
# diameter prints two places with its own BLANK_DIA_BAND (below); face
# width takes one place, the loosest title-block band (.X +/-0.8), which the
# 6.0 nominal clears against the 6.889 seat pitch.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlankProfile": {"BlankDia": 2},
    "Blank": {"FaceWidth": 1},
    "BoreProfile": {"BoreCutDia": 3},
    "ToothThicknessReference": {"ToothThickness": 3},
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
