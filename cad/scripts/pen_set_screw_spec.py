r"""Pure-data dimensional contract shared by the pen set screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map.  A knurled ("reeded")
knob thumb screw: the knob OD (before reeding) is the end-view dimension; the
knob length and under-knob length (the extrude depths ``KnobLg``/``ShankLg``)
sit on the side view with the thread designation leadered to the shank; the
reeding form is called out in the notes.  Thread designation and the
catalog-owned shank nominals are re-derived from the fastener catalog row --
ONE hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _fastener_notes import reeded_head_notes, thread_length_note


_SPEC = fastener("pen-set-screw")

KNOB_DIA = 9.0  # knurled knob OD (the turned blank, before reeding)
KNOB_LENGTH = 5.0  # knurled knob length
GROOVE_COUNT = 22  # reeding grooves
GROOVE_DIA = 1.0  # ball-nose groove cutter, centred on the knob OD

SHANK_DIA = _SPEC.model_diameter_mm  # #4-40 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # exposed shank length below the knob
THREAD = _SPEC.thread  # "#4-40"
THREAD_DESIGNATION = f"{THREAD} UNC"  # leadered to the shank on the side view

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "KnobProfile": {"KnobDia"},
    "Knob": {"KnobLg"},
    "Shank": {"ShankLg"},
}

DRAWING_NOTES = "\n".join(
    (
        *thread_length_note(
            thread=THREAD, underhead_length_mm=SHANK_LEN, head_name="KNOB"
        ),
        *reeded_head_notes(
            head_name="KNOB", groove_count=GROOVE_COUNT, groove_dia_mm=GROOVE_DIA
        ),
    )
)
# The recipe's end view is *Right: it looks from the shank tip toward the
# knob, so the shank reads as the solid centre circle.
END_VIEW_NOTE = "VIEW FROM SHANK END"
