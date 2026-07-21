r"""Pure-data dimensional contract shared by the pen set screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map.  A knurled ("reeded")
knob thumb screw: the knob OD and shank/thread minor Ø are marked model dims;
the knurl and cosmetic thread are called out in the notes.  Thread designation
and the catalog-owned shank nominals are re-derived from the fastener catalog
row -- ONE hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SPEC = fastener("pen-set-screw")

KNOB_DIA = 9.0  # knurled knob OD
KNOB_LENGTH = 5.0  # knurled knob length
GROOVE_COUNT = 22  # reeding grooves

SHANK_DIA = _SPEC.model_diameter_mm  # #4-40 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # exposed shank length below the knob
THREAD = _SPEC.thread  # "#4-40"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "KnobProfile": {"KnobDia"},
}

DRAWING_NOTES = "\n".join(
    (
        f"{THREAD_DESIGNATION} FULL THREAD OVER {SHANK_LEN:.2f} LENGTH BELOW KNOB; "
        "THREAD FORM, RUNOUT, AND LIMITS PER ASME B1.1.",
        "THREAD GEOMETRY OMITTED IN VIEWS; CYLINDRICAL SHANK OUTLINE IS "
        "REFERENCE ONLY.",
        "END FACE SQUARE TO THREAD AXIS; END EDGES PER TITLE BLOCK.",
        f"KNOB Ø{KNOB_DIA:.2f} X {KNOB_LENGTH:.2f} LONG; {GROOVE_COUNT} EQUALLY "
        "SPACED AXIAL Ø1.00 CYLINDRICAL GROOVES, CUTTER AXIS ON KNOB OD, FULL "
        "KNOB LENGTH.",
    )
)
END_VIEW_NOTE = "KNOB-END VIEW"
