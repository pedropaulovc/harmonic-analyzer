r"""Pure-data dimensional contract shared by the cone pivot screw and drawing.

PURE DATA.  This is a SLOTTED SHOULDER screw: the modeled shank is the GROUND
Ø shoulder the swing platform pivots on (a real controlled diameter), NOT a
thread minor -- the 1/4-20 threaded end below the shoulder is unmodeled.  So the
shank Ø carries no thread callout; the thread designation lives in the note.
The catalog-owned thread + shoulder nominals are re-derived from the fastener
catalog row -- ONE hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SPEC = fastener("cone-pivot-screw")

HEAD_DIA = 9.5  # slotted head OD
HEAD_T = 3.0  # head thickness
SLOT_W = 1.6
SLOT_D = 1.2

SHANK_DIA = _SPEC.model_diameter_mm  # Ø6.35 ground shoulder (rides the Ø6.5 hole)
SHANK_LEN = _SPEC.length_mm  # shoulder length (plate + engagement)
THREAD = _SPEC.thread  # "1/4-20"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

# Both modeled diameters are real controlled dims (head OD + ground shoulder Ø);
# the head thickness and shoulder length are drawing-native linears.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDiaDim"},
    "ShankProfile": {"ShankDiaDim"},
}

DRAWING_NOTES = "\n".join(
    (
        f"COMMERCIAL {THREAD_DESIGNATION} SLOTTED SHOULDER SCREW, "
        f"Ø{SHANK_DIA:g} X {SHANK_LEN:g} SHOULDER, ACCEPTABLE IN PLACE OF A "
        "MADE PART.",
        f"SHANK IS THE GROUND Ø{SHANK_DIA:g} SHOULDER; THE {THREAD} THREADED END "
        "BELOW IT IS NOT MODELED (REF).",
        f"HEAD {HEAD_T:g} THICK; STRAIGHT DRIVER SLOT {SLOT_W:g} WIDE X "
        f"{SLOT_D:g} DEEP.",
        "THREADED-END LENGTH IS NOT DEFINED. DO NOT RELEASE AS A MADE-PART "
        "DRAWING; USE THE COMMERCIAL SHOULDER SCREW.",
    )
)
END_VIEW_NOTE = "HEAD-END VIEW"
