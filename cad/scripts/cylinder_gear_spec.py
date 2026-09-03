r"""Pure-data dimensional contract shared by the cylinder gear and its drawing.

The gear-drawing pattern (shared by every gear/pinion sheet in this batch): the
BLANK is dimensioned in the views (bore, and here the cam and its notch) while
the TEETH are specified by the GEAR DATA block below -- an involute gear has no
single circular OD edge to dimension, so pitch/outside diameter and the tooth
system live in the data table (standard AGMA/ASME gear-drawing practice), and
the one thing a micrometer can check, the measurement over two pins, is
computed by ``_gear_inspection`` rather than typed.  Keep the GEAR DATA field
order/wording identical across the batch so the sheets diff cleanly.
"""

from __future__ import annotations

import math

from _gear_inspection import (
    diametral_pitch_text,
    over_pins_row,
    pin_measurement,
    preferred_pin_dia_mm,
)
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

# --- gear tooth system (build_cylinder_gear.py / gear_train.yaml) ------------
TEETH = 120
DIAMETRAL_PITCH = (
    49.82  # train DP (= 122*25.4/62.2), cad/config/machine/gear_train.yaml
)
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH  # 0.510
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN  # 61.18
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN  # 62.20
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN  # 1.10

# --- machinable blank (build_cylinder_gear.py) ------------------------------
BORE_DIA = 0.375 * MM_PER_IN  # 9.525 (3/8")
BORE_DIA_BAND = (0.05, 0.00)  # admits a nominal 3/8 in reamer
FACE_WIDTH = 3.0
CAM_DIA = 30.6  # integral eccentric cam disc
CAM_THICKNESS = 3.5
ECCENTRICITY = 8.64  # cam axis offset from the bore axis
NOTCH_WIDTH = 0.4  # alignment saw-kerf
NOTCH_DEPTH = 3.0
# The kerf is a saw cut: its narrow width and dedicated band are stated
# together in the plain note adjacent to DETAIL B rather than imported as a
# fragile model dimension.
NOTCH_WIDTH_TOLERANCE_MM = 0.05
# Where the kerf sits (build_cylinder_gear: an axis-aligned slot in the tooth
# gap nearest +Y, its floor NOTCH_DEPTH below the tooth tips); the detail note
# sits beside the enlarged view.
NOTCH_FLOOR_MM = OUTSIDE_DIA / 2.0 - NOTCH_DEPTH
NOTCH_X_MM = (NOTCH_FLOOR_MM + OUTSIDE_DIA / 2.0) / 2.0 * math.cos(
    math.pi / 2.0 + math.pi / TEETH
)
# The plain note adjacent to DETAIL B owns the complete saw-cut width,
# tolerance and depth from the tooth tips.
KERF_CALLOUT = (
    f"SAW KERF {NOTCH_WIDTH:.2f} +/-{NOTCH_WIDTH_TOLERANCE_MM:.2f} WIDE, "
    f"{NOTCH_DEPTH:.1f} DEEP FROM O.D., FULL FACE"
)

# The bore RUNS: the gear spins free on the cylinder-gear shaft, so its bore is
# a shaft_in_bushing journal; the cam O.D. is the follower track the
# connecting-rod ring rides (build_channel_assembly: rod rings concentric on
# the cams), a cam_follower_contact face (drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES = (
    SurfaceFinishControl("cylinder_gear_bore", MACHINED_UM, CylinderFace(BORE_DIA)),
    SurfaceFinishControl("cam_track", MACHINED_UM, CylinderFace(CAM_DIA)),
)

# The marked MODEL dimensions are the bore (the critical mounting fit), plus
# the cam disc and its offset from the bore in the front view.  The kerf is
# fully specified by the plain DETAIL B saw note; OD / pitch dia / tooth
# system are carried by GEAR DATA.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BoreProfile": {"BoreDia"},
    "CamProfile": {"CamDia", "CamOffset"},
}

# Over-pins acceptance (Machinery's Handbook 1.92/P wire, see _gear_inspection).
PIN_DIA_MM = preferred_pin_dia_mm(DIAMETRAL_PITCH)
OVER_PINS = pin_measurement(
    teeth=TEETH,
    diametral_pitch=DIAMETRAL_PITCH,
    pressure_angle_deg=PRESSURE_ANGLE_DEG,
    pin_dia_mm=PIN_DIA_MM,
)


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", diametral_pitch_text(DIAMETRAL_PITCH)),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        # A cutter setting, not an inspection: the over-pins row is the
        # acceptance, so the depth reads as reference.
        ("WHOLE DEPTH (REF)", f"{WHOLE_DEPTH:.2f}"),
        # 20 of these stack on one drum, so the face width is held tighter
        # than the .XX block row; it is not a view dimension, so the band
        # lives in the blank's data row.
        ("FACE WIDTH", f"{FACE_WIDTH:.2f} +/-0.05"),
        over_pins_row(OVER_PINS),
        ("TOOTH FORM", "INVOLUTE, FULL DEPTH"),
    ]
)

# Notes: part-specific process facts only (drawing-simplicity-policy.md rule
# 6).  The cam and the kerf are dimensioned in the views (front view and
# DETAIL B), so the notes carry only what no view can: the set-matching of
# the 20 cam throws, the kerf's angular station, and what runs on what.
DRAWING_NOTES = "\n".join(
    (
        "SET OF 20: CAM OFFSETS WITHIN 0.025 OF EACH OTHER.",
        "NOTCH IN A TOOTH GAP ON THE CAM CENTRELINE, LOBE SIDE (DETAIL B).",
        "RUNS FREE ON THE CYLINDER-GEAR SHAFT; THE ROD RING RIDES THE CAM.",
    )
)
