r"""Pure-data dimensional contract shared by the cone gear and its drawing.

The cone gear is a 20-member configured family (T006..T120 by 6); this sheet
documents the fundamental T120 configuration and the shared tooth system, with a
family note. See the batch gear-drawing pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations

import _config
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
FACE_WIDTH = 6.5
FAMILY_BORES_MM = {
    6: 0.03125 * MM_PER_IN,
    12: 0.125 * MM_PER_IN,
    18: 0.25 * MM_PER_IN,
    24: 0.375 * MM_PER_IN,
}

# No roughness callouts: every cone gear is soldered to its shaft seat, so
# nothing runs on the bore; the title block's Ra 3.2 covers every face
# (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BoreProfile": {"BoreCutDia"},
}


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


# The tooth system plus the family bore table -- the one thing a machinist
# cannot read off a T120 sheet is which bore goes with which tooth count.
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        ("WHOLE DEPTH", f"{WHOLE_DEPTH:.2f}"),
        ("FACE WIDTH", f"{FACE_WIDTH:.2f}"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
        (
            "FAMILY T006 / T012 / T018",
            f"BORE {FAMILY_BORES_MM[6]:.3f} / {FAMILY_BORES_MM[12]:.3f} / "
            f"{FAMILY_BORES_MM[18]:.3f}",
        ),
        ("FAMILY T024-T120 BY 6", f"BORE {FAMILY_BORES_MM[24]:.3f}"),
    ]
)

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        "MAKE 1 OF EACH CONFIGURATION, T006-T120 BY 6 (20 GEARS); SHEET SHOWS T120.",
        "PLAIN BORE, NO KEYWAY; SOLDER TO THE SHAFT SEAT AT ASSEMBLY.",
        f"T006-T024: {TIP_MATERIAL_SPEC.upper()} ROD (TITLE-BLOCK BRASS IS T030-T120).",
        "SMALLEST TIP GEARS: CUT STUB DEPTH WHERE FULL DEPTH WOULD UNDERCUT.",
    )
)
