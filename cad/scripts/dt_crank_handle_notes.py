"""Callout and note text for the crank handle sheet (MHA-DT-08).

The fits, clearances and wall shortfalls the sheet prints, built from the part
specs so the drawing script owns only their placement.
"""

from __future__ import annotations

import math

from dt_crank_handle_pivot_screw_spec import (
    DIAMETRAL_CLEARANCE_MAX,
    DIAMETRAL_CLEARANCE_MIN,
)
from dt_crank_handle_spec import (
    COUNTERBORE_DIA_MAX,
    COUNTERBORE_GLUE_LINE,
    CUP_NUMBER,
    FERRULE_NUMBER,
    SCREW_NUMBER,
    TENON_GLUE_LINE,
    TENON_STRAIGHT_WALL_MIN,
    TENON_WALL_MIN,
    inch_text,
)


def _range(band: tuple[float, float], places: int) -> str:
    return f"{inch_text(band[0], places)}-{inch_text(band[1], places)}"


def _floor_thou(value_mm: float) -> str:
    """A wall floor rounded down to the printed thousandth (RV-01, RV-02)."""
    return inch_text(math.floor(value_mm / 0.0254) * 0.0254, 3)


# Rule 7: each callout is its size/process line plus at most two lines of
# words; anything longer is a numbered note its callout flags (SEE NOTE n).
# Rule 4: each fit by its standard name and mate number, the clearance its
# limits give as a reference.  The tenon and the counterbore are epoxied
# (dt_crank_handle_ferrule_spec, dt_crank_handle_butt_cup_spec), so bonded.
# The reamed bore runs on the MHA-DT-32 shoulder (#290 fit F12: .0050-.0075).
PIVOT_BORE_CALLOUT = (
    f"REAM THRU\nRUNNING FIT ON {SCREW_NUMBER}\n"
    f"(CLEARANCE {_range((DIAMETRAL_CLEARANCE_MIN, DIAMETRAL_CLEARANCE_MAX), 4)})"
)
TENON_NOTE_NUMBER = 1
COUNTERBORE_NOTE_NUMBER = 2
TENON_CALLOUT = (
    f"BONDED FIT IN {FERRULE_NUMBER}, EPOXY\n"
    f"(CLEARANCE {_range(TENON_GLUE_LINE, 3)}) SEE NOTE {TENON_NOTE_NUMBER}"
)
COUNTERBORE_CALLOUT = (
    f"BONDED FIT ON {CUP_NUMBER}, EPOXY\n"
    f"(CLEARANCE {_range(COUNTERBORE_GLUE_LINE, 3)}) SEE NOTE {COUNTERBORE_NOTE_NUMBER}"
)
# The wall shortfalls stay exact (owner exceptions RV-01 and RV-02); the
# counterbore's limit and the depth's acceptance (the depth is a reference).
TENON_NOTE = (
    f"{TENON_NOTE_NUMBER}. WALL {_floor_thou(TENON_STRAIGHT_WALL_MIN)} MIN; "
    f"WALL {_floor_thou(TENON_WALL_MIN)} MIN AT TENON END."
)
COUNTERBORE_NOTE = (
    f"{COUNTERBORE_NOTE_NUMBER}. <MOD-DIAM>{inch_text(COUNTERBORE_DIA_MAX, 3)} MAX; "
    f"DEPTH SETS {CUP_NUMBER} FACE\n   FLUSH WITH OAK END."
)
SHEET_NOTES = f"{TENON_NOTE}\n{COUNTERBORE_NOTE}"
# The inside corners' single limits name the part seating on each by number;
# the relief's band the ferrule seating outside it (rule 4).
TENON_ROOT_CALLOUT = f"{FERRULE_NUMBER}\nSEAT"
COUNTERBORE_FLOOR_CALLOUT = f"{CUP_NUMBER}\nSEAT"
TENON_ROOT_RELIEF_CALLOUT = f"X 45°\n{FERRULE_NUMBER}\nSEATS OUTSIDE"
