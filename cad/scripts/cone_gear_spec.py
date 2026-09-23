r"""Pure-data dimensional contract shared by the cone-gear family and drawing.

The cone gear is a 20-member configured family (T006..T120 by 6).  The drawing
package gives every configuration its own complete sheet: configuration-owned
tip and bore diameters, common face width, and a native driving tooth-thickness
dimension whose band comes from the configured gear-mesh backlash.

This module stays fit-free because assemblies import it.  The part builder
derives the bore and tooth-thickness bands from ``cone_gear_shaft_spec`` and
``_config.fit`` at authoring time; the drawing merely imports the resulting
native model dimensions, precision, and tolerances.
"""

from __future__ import annotations

import math

import _config
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


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
OUTSIDE_DIA = (TEETH + 2) * MODULE_MM
BASE_CHORD_ROOT_FORM = "INVOLUTE FLANKS; GAP FLOOR CHORD AT BASE CIRCLE"
TOOTH_THICKNESS = math.pi * MODULE_MM / 2.0

BORE_DIA = 0.375 * MM_PER_IN  # 9.525 (3/8") at T120; smaller on the tip gears
# U27 face width (Main ruling, 2026-09-23): 6.0 at the .X band keeps the
# widest gear (6.8) inside the 6.889 seat pitch; 6.5 +/-0.51 could reach
# 7.01 and overlap a neighbour.  The drum's engaged zone spans
# [-0.75, +1.35] mm about the narrowed gear's centre, inside the 5.2 minimum.
FACE_WIDTH = 6.0


def base_chord_root_radius_mm(teeth: int) -> float:
    """Return the minimum radius of the equation-driven gap-floor chord.

    This mirrors ``build_cone_gear.gear_facts`` and its A2-to-A1 equation
    curve exactly.  It is deliberately not the standard full-depth dedendum:
    every configured solid is cut by involute flanks closed with this chord.
    """
    if teeth not in CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    pressure_angle = math.radians(PRESSURE_ANGLE_DEG)
    base_radius = teeth * MODULE_MM * math.cos(pressure_angle) / 2.0
    delta = (
        math.pi / (2.0 * teeth)
        + math.tan(pressure_angle)
        - pressure_angle
    )
    half_gap_angle = math.pi / teeth - delta
    return base_radius * math.cos(half_gap_angle)


def as_cut_tooth_depth_mm(teeth: int) -> float:
    """Return tip radius minus the configured base-chord root radius."""
    tip_radius = (teeth + 2.0) * MODULE_MM / 2.0
    return tip_radius - base_chord_root_radius_mm(teeth)

def bore_dia_mm(teeth: int) -> float:
    """Return the configured bore that fits the matching stepped-shaft land."""
    if teeth not in CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    # T006 is 1/16", not 1/32": its native-verified base-chord root leaves
    # 0.638684 mm nominal web (0.611184 mm at maximum bore); shaft-tip L/D is 13.
    if teeth == 6:
        return 0.0625 * MM_PER_IN
    if teeth == 12:
        return 0.125 * MM_PER_IN
    if teeth == 18:
        return 0.25 * MM_PER_IN
    return BORE_DIA


def material_specification(teeth: int) -> str:
    """Return the configuration-owned alloy printed in that sheet's title block."""
    if teeth not in CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    return TIP_MATERIAL_SPEC if teeth <= 24 else BODY_MATERIAL_SPEC


FAMILY_BORES_MM = {teeth: bore_dia_mm(teeth) for teeth in CONFIGURATION_TEETH}

# U27 (drive-train ruling): machined webs target >= 2.0 mm with a hard floor
# of 1.5 mm at the worst case of the printed bands.  The four smallest gears
# sit on the stepped shaft's 1/16, 1/8, 1/4 and 3/8 in lands and fall under
# the floor between the base-chord root and the maximum bore.  USER ruling
# 2026-09-23 (~02:50Z, via Main-cc): "Smallest gears will probably be an
# exception to the 1.5mm floor ... the gears match well the book pics" --
# book-fidelity evidence: comparison pair ch12-p002-img09 (cone set plan
# view) overlays the taper down to T006.  Each entry is the accepted web at
# maximum bore (mm); every other configuration must meet the U27 target.
MACHINED_WEB_FLOOR_MM = 1.5
MACHINED_WEB_TARGET_MM = 2.0
SMALL_GEAR_WEB_EXCEPTIONS_MM: dict[int, float] = {
    6: 0.611,
    12: 1.323,
    18: 1.225,
    24: 1.123,
}

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
# nominal 0.459 mm interleave halves (Fable review, 2026-09-23).  Main ruled
# the band by contact ratio (U27: the looser +/-0.25 only if it keeps CR >= 1.1
# at the worst case).  Worst case of every printed band -- this band, drum OD
# +0/-0.10, bore-on-land, journal, drum-bore and arbor float -- leaves CR
# 0.09/0.42/0.46 (T006/T060/T120) at +/-0.10 and 0.01/0.28/0.30 at +/-0.25,
# with the drum floor still clear (+0.83 / +0.75), so +/-0.10 prints: turning
# the blank OD to a micrometer before cutting teeth is a novice-holdable step.
BLANK_DIA_BAND = (0.10, -0.10)


def configuration_number(part_number: str, teeth: int) -> str:
    """Return one configuration sheet's drawing number, e.g. ``MHA-013-T006``."""
    if teeth not in CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
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
