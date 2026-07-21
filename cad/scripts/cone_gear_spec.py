r"""Pure-data dimensional contract shared by the cone gear and its drawing.

The cone gear is a 20-member configured family (T006..T120 by 6); this sheet
documents the fundamental T120 configuration and the shared tooth system, with a
family note. See the batch gear-drawing pattern in ``cylinder_gear_spec``.
"""

from __future__ import annotations


MM_PER_IN = 25.4

TEETH = 120                       # drawn (fundamental) configuration
DIAMETRAL_PITCH = 49.82           # cad/config/machine/gear_train.yaml
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN

BORE_DIA = 0.375 * MM_PER_IN      # 9.525 (3/8") at T120; smaller on the tip gears
FACE_WIDTH = 6.5
FAMILY_BORES_MM = {
    6: 0.03125 * MM_PER_IN,
    12: 0.125 * MM_PER_IN,
    18: 0.25 * MM_PER_IN,
    24: 0.375 * MM_PER_IN,
}

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BoreProfile": {"BoreCutDia"},
}


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("MODULE (mm, REF)", f"{MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER (mm)", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        ("WHOLE DEPTH (mm)", f"{WHOLE_DEPTH:.2f}"),
        ("FACE WIDTH (mm)", f"{FACE_WIDTH:.2f}"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
        ("FAMILY T006", f"6T; BORE {FAMILY_BORES_MM[6]:.3f}"),
        ("FAMILY T012", f"12T; BORE {FAMILY_BORES_MM[12]:.3f}"),
        ("FAMILY T018", f"18T; BORE {FAMILY_BORES_MM[18]:.3f}"),
        ("FAMILY T024-T120", f"24T TO 120T BY 6; BORE {FAMILY_BORES_MM[24]:.3f}"),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "CUT TEETH PER GEAR DATA.",
        "GEAR BLANK CONCENTRIC WITH BORE WITHIN 0.05 TIR.",
        "CONE SET: MAKE 1 OF EACH CONFIGURATION (T006-T120 BY 6; 20 GEARS TOTAL).",
        "ALL 20 GEARS PLAIN-BORED (NO KEYWAY); SOLDER TO MATCHING SHAFT SEATS.",
        "THIS SHEET SHOWS T120; FAMILY ROWS ABOVE GOVERN TOOTH COUNT AND BORE.",
        "  PITCH DIA=N×25.4/DP; OUTSIDE DIA=(N+2)×25.4/DP.",
    )
)
