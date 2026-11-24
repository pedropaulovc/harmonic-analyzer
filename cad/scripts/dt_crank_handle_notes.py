"""Callout and note text for the crank handle sheet (MHA-DT-08).

The fits, clearances and wall shortfalls the sheet prints, built from the part
specs so the drawing script owns only their placement.
"""

from __future__ import annotations

import math

from dt_crank_handle_spec import (
    COUNTERBORE_GLUE_LINE,
    CUP_NAME,
    CUP_NUMBER,
    FERRULE_NAME,
    FERRULE_NUMBER,
    PIVOT_BORE_FIT_MAX,
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
# Rule 4: each fit by its standard name and its mate by name and full
# number, the clearance its limits give as a reference.  The tenon and the
# counterbore are epoxied (dt_crank_handle_ferrule_spec,
# dt_crank_handle_butt_cup_spec), so bonded.  The bore is drilled #20 and the
# MHA-DT-32 shoulder, made last, is turned to it: the fit's acceptance prints
# once, on MHA-DT-32 (owner ruling 2026-11-23, tool audit Q14: "DRILL #20";
# owner ruling 2026-11-24, fit audit question 14: "handle stays DRILL #20;
# DT-32 shoulder by trial").  The .1635 MAX cap is the largest bore the
# tenon walls are judged at (dt_crank_handle_spec.PIVOT_BORE_FIT_MAX; the
# shoulder's .1635 trial step must not enter).
PIVOT_BORE_DRILL = "#20"
PIVOT_BORE_CALLOUT = (
    f"{PIVOT_BORE_DRILL} DRILL THRU, <MOD-DIAM>{inch_text(PIVOT_BORE_FIT_MAX, 4)} MAX\n"
    f"{SCREW_NUMBER} SHOULDER IS\nTURNED TO THIS BORE"
)
TENON_NOTE_NUMBER = 1
COUNTERBORE_NOTE_NUMBER = 2
TENON_CALLOUT = (
    f"BONDED FIT IN {FERRULE_NUMBER} {FERRULE_NAME}\n"
    f"WITH EPOXY, SEE NOTE {TENON_NOTE_NUMBER}\n"
    f"(CLEARANCE {_range(TENON_GLUE_LINE, 3)})"
)
COUNTERBORE_CALLOUT = (
    f"BONDED FIT ON {CUP_NUMBER} {CUP_NAME}\n"
    f"WITH EPOXY, SEE NOTE {COUNTERBORE_NOTE_NUMBER}\n"
    f"(CLEARANCE {_range(COUNTERBORE_GLUE_LINE, 3)})"
)
# The wall shortfalls stay exact (owner exceptions RV-01 and RV-02).  The
# counterbore's diameter is controlled by its bonded-fit clearance alone:
# the largest cup plus the widest glue line stays under the Ø.435 the butt
# wall is budgeted at (dt_crank_handle_spec.COUNTERBORE_DIA_MAX keeps .002
# of margin), so no second limit prints (round 1 f08277cd).  The depth is a
# reference, so note 2 states its acceptance.
TENON_NOTE = (
    f"{TENON_NOTE_NUMBER}. WALL {_floor_thou(TENON_STRAIGHT_WALL_MIN)} MIN; "
    f"WALL {_floor_thou(TENON_WALL_MIN)} MIN AT TENON END."
)
COUNTERBORE_NOTE = (
    f"{COUNTERBORE_NOTE_NUMBER}. DEPTH SETS {CUP_NUMBER} FACE FLUSH WITH OAK END."
)
# The tenon root's relief band and its R.012 MAX corner serve one function:
# the relief keeps the root round behind the ferrule's seat face and leaves
# it enough shoulder face (owner ruling 2026-10-24, #1900).  The mate and
# that reason print once, in note 3, which both callouts flag (rules 4 and
# 7; round 2 d6ae2a44: naming them on each callout repeated them).
FERRULE_SEAT_NOTE_NUMBER = 3
FERRULE_SEAT_NOTE = (
    f"{FERRULE_SEAT_NOTE_NUMBER}. {FERRULE_NUMBER} {FERRULE_NAME} SEATS ON TENON SHOULDER."
)
SHEET_NOTES = f"{TENON_NOTE}\n{COUNTERBORE_NOTE}\n{FERRULE_SEAT_NOTE}"
TENON_ROOT_CALLOUT = f"SEE NOTE {FERRULE_SEAT_NOTE_NUMBER}"
TENON_ROOT_RELIEF_CALLOUT = f"X 45°\nSEE NOTE {FERRULE_SEAT_NOTE_NUMBER}"
# The counterbore floor's single limit names the cup seating on it.
COUNTERBORE_FLOOR_CALLOUT = f"{CUP_NUMBER}\nSEAT"
