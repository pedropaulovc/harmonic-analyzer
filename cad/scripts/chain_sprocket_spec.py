r"""Pure-data dimensional contract shared by the chain sprocket and its drawing.

A roller-chain sprocket, not a gear -- so its data block is the SPROCKET analog
of the batch gear-drawing pattern (``cylinder_gear_spec``): chain pitch and
roller diameter replace diametral pitch / module, and the tooth form names the
chain standard. Sprocket math (3/8" pitch, 0.200" roller):
PD = p / sin(pi/N), OD = p (0.6 + cot(pi/N)).
"""

from __future__ import annotations

import math


MM_PER_IN = 25.4

TEETH = 17                         # counted on v4_transgear_012
CHAIN_PITCH = 0.375 * MM_PER_IN    # 9.525 (3/8"), ANSI #30
ROLLER_DIAMETER = 0.200 * MM_PER_IN  # 5.08
PITCH_DIA = CHAIN_PITCH / math.sin(math.pi / TEETH)          # 51.84
OUTSIDE_DIA = CHAIN_PITCH * (0.6 + 1.0 / math.tan(math.pi / TEETH))  # 56.67

BORE_DIA = 0.375 * MM_PER_IN       # 9.525 (3/8" crankshaft stock)
FACE_WIDTH = 4.5
SEAT_RADIUS = PITCH_DIA / 2.0 - ROLLER_DIAMETER / 2.0
NOTCH_OUTER_RADIUS = OUTSIDE_DIA / 2.0 + 1.2
SEAT_WIDTH = ROLLER_DIAMETER
NOTCH_OUTER_WIDTH = 8.0

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BoreProfile": {"BoreDia"},
}


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


# Sprocket analog of the gear-data block: same NUMBER OF TEETH / PITCH DIAMETER
# / OUTSIDE DIAMETER / TOOTH FORM anchors, with chain pitch + roller diameter in
# place of the gear tooth-system rows.
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("CHAIN PITCH (mm)", f"{CHAIN_PITCH:.3f}"),
        ("ROLLER DIAMETER (mm)", f"{ROLLER_DIAMETER:.2f}"),
        ("PITCH DIAMETER (mm)", f"{PITCH_DIA:.2f}"),
        ("OUTSIDE DIAMETER (mm)", f"{OUTSIDE_DIA:.2f} +0/-0.10"),
        ("FACE WIDTH (mm)", f"{FACE_WIDTH:.2f}"),
        ("REFERENCE CHAIN", "ANSI #30 (3/8 IN PITCH)"),
        ("TOOTH FORM", "17 RADIAL TRAPEZOID NOTCHES"),
        ("NOTCH AT SEAT", f"{SEAT_WIDTH:.2f} W AT R{SEAT_RADIUS:.2f}"),
        ("NOTCH OUTER", f"{NOTCH_OUTER_WIDTH:.2f} W AT R{NOTCH_OUTER_RADIUS:.2f}"),
    ],
    title="SPROCKET DATA",
)

DRAWING_NOTES = "\n".join(
    (
        "CUT 17 EQ-SPACED NOTCHES PER SPROCKET DATA.",
        "SPROCKET CONCENTRIC WITH BORE WITHIN 0.05 TIR.",
        "NOTCHES ARE STRAIGHT-FLANKED AND CUT THRU FULL FACE.",
        "2 REQUIRED (PLATEN FRONT + CRANKSHAFT; BOOK CH.23).",
    )
)
