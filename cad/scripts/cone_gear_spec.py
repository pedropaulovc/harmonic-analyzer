r"""Pure-data dimensional contract shared by the cone gear and its drawing.

The cone gear is a 20-member configured family (T006..T120 by 6); this sheet
documents the fundamental T120 configuration and the shared tooth system, and
two configuration tables give every member its outside diameter, whole depth,
bore and over-pins reading (the machinist review of 2026-09-02 rejected a
family note that named only T120). See the batch gear-drawing pattern in
``cylinder_gear_spec``.
"""

from __future__ import annotations

import math

import _config
from _gear_inspection import (
    diametral_pitch_text,
    over_pins_row,
    pin_measurement,
    preferred_pin_dia_mm,
)
from _surface_finish import SurfaceFinishControl


MM_PER_IN = 25.4

# Family alloy split (config-owned, cad/config/parts/cone-gear.yaml): the
# title-block material (C36000) covers T030-T120; the four tip gears are the
# harder alloy below (dimensions.yaml ch.12 p.21).
_MFG = _config.parts("cone-gear")
BODY_MATERIAL_SPEC = str(_MFG["material_specification"])
TIP_MATERIAL_SPEC = str(_MFG["material_tip_specification"])

TEETH = 120  # drawn (fundamental) configuration
DIAMETRAL_PITCH = 49.82  # cad/config/machine/gear_train.yaml
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 0.375 * MM_PER_IN  # 9.525 (3/8") at T120; smaller on the tip gears
BORE_DIA_BAND = (0.05, 0.00)  # admits each nominal reamer; all configurations
FACE_WIDTH = 6.5
FAMILY_TEETH = tuple(range(6, 121, 6))
FAMILY_BORES_MM = {
    6: 0.03125 * MM_PER_IN,
    12: 0.125 * MM_PER_IN,
    18: 0.25 * MM_PER_IN,
    24: 0.375 * MM_PER_IN,
}

# Below this tooth count a 14.5 deg full-depth tooth undercuts when generated
# (2 / sin^2(14.5 deg) = 31.9, Machinery's Handbook), and the modelled gap
# floor (build_cone_gear: the chord at the base circle) is shallower than the
# standard 2.157/DP -- so T006..T030 are cut STUB, to the base circle.
UNDERCUT_TEETH_LIMIT = 32

# No roughness callouts: every cone gear is soldered to its shaft seat, so
# nothing runs on the bore; the title block's Ra 3.2 covers every face
# (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BoreProfile": {"BoreCutDia"},
}

# Over-pins acceptance: one pin serves the whole family (see _gear_inspection).
PIN_DIA_MM = preferred_pin_dia_mm(DIAMETRAL_PITCH)


def family_bore_mm(teeth: int) -> float:
    """The configured bore (mirrors ``build_cone_gear.bore_dia_in``)."""
    for limit in (6, 12, 18, 24):
        if teeth <= limit:
            return FAMILY_BORES_MM[limit]
    return FAMILY_BORES_MM[24]


def outside_dia_mm(teeth: int) -> float:
    return (teeth + 2) / DIAMETRAL_PITCH * MM_PER_IN


def base_dia_mm(teeth: int) -> float:
    return teeth / DIAMETRAL_PITCH * MM_PER_IN * math.cos(math.radians(PRESSURE_ANGLE_DEG))


def is_stub(teeth: int) -> bool:
    return teeth < UNDERCUT_TEETH_LIMIT


def whole_depth_mm(teeth: int) -> float:
    """Standard 2.157/DP, or tip-to-base-circle on the stub tip gears."""
    if is_stub(teeth):
        return (outside_dia_mm(teeth) - base_dia_mm(teeth)) / 2.0
    return WHOLE_DEPTH


def over_pins(teeth: int):
    return pin_measurement(
        teeth=teeth,
        diametral_pitch=DIAMETRAL_PITCH,
        pressure_angle_deg=PRESSURE_ANGLE_DEG,
        pin_dia_mm=PIN_DIA_MM,
    )


OVER_PINS = over_pins(TEETH)


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


# The shared tooth system at the drawn T120; the per-member numbers are in the
# two configuration tables below (one property-linked note each).
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH} (SHEET); 6-120 BY 6, SEE TABLES"),
        ("DIAMETRAL PITCH", diametral_pitch_text(DIAMETRAL_PITCH)),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        ("WHOLE DEPTH (REF)", f"{WHOLE_DEPTH:.2f}"),
        ("FACE WIDTH", f"{FACE_WIDTH:.2f}"),
        ("BORE BAND (ALL CONFIGS)", "+0.05/0.00"),
        over_pins_row(OVER_PINS),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH; T006-T030 STUB TO THE BASE CIRCLE"),
        (
            "TABLES",
            f"OD / DEPTH / BORE / OVER 2 PINS {PIN_DIA_MM:.2f} DIA, BANDS AS ABOVE",
        ),
    ]
)


def _table_row(teeth: int) -> str:
    depth = f"{whole_depth_mm(teeth):.2f}" + (" STUB" if is_stub(teeth) else "")
    return (
        f"T{teeth:03d}:  {outside_dia_mm(teeth):.2f} / {depth} / "
        f"{family_bore_mm(teeth):.3f} / {over_pins(teeth).over_pins_mm:.2f}"
    )


def configuration_table(teeth: tuple[int, ...]) -> str:
    """Ten members, one line each; the column legend is the GEAR DATA
    ``TABLES`` row so the two notes stay narrow enough to sit side by side."""
    header = f"T{teeth[0]:03d}-T{teeth[-1]:03d}:  OD / DEPTH / BORE / PINS"
    return "\n".join([header] + [_table_row(n) for n in teeth])


# Two ten-member halves so each property-linked note stays the size of a
# gear-data block and the two sit side by side under it.
CONFIGURATION_TABLE_A = configuration_table(FAMILY_TEETH[:10])
CONFIGURATION_TABLE_B = configuration_table(FAMILY_TEETH[10:])

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        "MAKE 1 OF EACH CONFIGURATION, T006-T120 BY 6 (20 GEARS); SHEET SHOWS T120.",
        "PLAIN REAMED BORE, NO KEYWAY; SOLDER TO THE SHAFT SEAT AT ASSEMBLY.",
        f"T006-T024: {TIP_MATERIAL_SPEC.upper()} ROD (TITLE-BLOCK BRASS IS T030-T120).",
        "T006-T030: CUT TO THE STUB DEPTH IN THE TABLE (FULL DEPTH WOULD UNDERCUT).",
    )
)
