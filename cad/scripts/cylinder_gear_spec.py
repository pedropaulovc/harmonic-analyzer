r"""Pure-data dimensional contract shared by the cylinder gear and its drawing.

The gear-drawing pattern (shared by every gear/pinion sheet in this batch): the
BLANK is dimensioned in the views (bore, face width) while the TEETH are
specified by the GEAR DATA block below -- an involute gear has no single
circular OD edge to dimension, so pitch/outside diameter and the tooth system
live in the data table (standard AGMA/ASME gear-drawing practice). Keep the
GEAR DATA field order/wording identical across the batch so the sheets diff
cleanly.
"""

from __future__ import annotations


MM_PER_IN = 25.4

# --- gear tooth system (build_cylinder_gear.py / gear_train.yaml) ------------
TEETH = 120
DIAMETRAL_PITCH = 49.82  # train DP (= 122*25.4/62.2), cad/config/machine/gear_train.yaml
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH          # 0.510
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN   # 61.18
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN  # 62.20
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN       # 1.10

# --- machinable blank (build_cylinder_gear.py) ------------------------------
BORE_DIA = 0.375 * MM_PER_IN   # 9.525 (3/8")
FACE_WIDTH = 3.0
CAM_DIA = 30.6                 # integral eccentric cam disc
CAM_THICKNESS = 3.5
ECCENTRICITY = 8.64            # cam axis offset from the bore axis
NOTCH_WIDTH = 0.4             # alignment saw-kerf
NOTCH_DEPTH = 3.0

# Only the bore is a marked MODEL dimension (the single source of the critical
# mounting fit). OD / pitch dia / tooth system are carried by the GEAR DATA
# note; face width is a drawing-added reference dimension.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BoreProfile": {"BoreDia"},
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
        ("WHOLE DEPTH (mm)", f"{WHOLE_DEPTH:.2f} +0.05/0"),
        ("FACE WIDTH (mm)", f"{FACE_WIDTH:.2f} +/-0.05"),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

DRAWING_NOTES = "\n".join(
    (
        "DIAMETRAL PITCH CONTROLS TEETH; MODULE/PD ARE REF.",
        "CUT TEETH PER GEAR DATA.",
        "GEAR TEETH: CIRCULAR RUNOUT 0.05 MAX TO DATUM A.",
        f"ECCENTRIC CAM (FAR FACE): Ø{CAM_DIA:.2f} +0/-0.05, {CAM_THICKNESS:.2f} +/-0.05 THK",
        f"  BEYOND GEAR FACE; AXIS OFFSET {ECCENTRICITY:.3f} +/-0.025 FROM BORE TOWARD NOTCH.",
        "CAM FOLLOWER O.D. SURFACE: Ra 1.6.",
        "CAM AXIS LIES IN THE RADIAL PLANE THROUGH BORE AXIS + NOTCH CENTERLINE.",
        f"NOTCH: {NOTCH_WIDTH:.2f} +0.10/0 WIDE X {NOTCH_DEPTH:.1f} +/-0.2 RADIAL DEEP,",
        "  TOOTH VALLEY AT TOP. CAM ECCENTRICITY TOTAL VARIATION 0.025 MAX ACROSS SET.",
    )
)
