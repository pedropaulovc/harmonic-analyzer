r"""Pure-data dimensional contract shared by the wheel axle and drawing."""

from __future__ import annotations


FLANGE_DIA = 35.0
FLANGE_LEN = 3.0
STUD_DIA = 5.0
STUD_LEN = 14.0
COLLAR_DIA = 9.0
COLLAR_LEN = 4.0

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FlangeProfile": {"FlangeDia"},
    "StudProfile": {"StudDia"},
    "CollarProfile": {"CollarDia"},
    "Flange": {"FlangeLength"},
    "Stud": {"StudLength"},
    "Collar": {"CollarLength"},
}

DRAWING_NOTES = "\n".join(
    (
        "UOS, DIMENSIONS IN MM: DIAMETERS +/-0.05, LENGTHS +/-0.25. DEBURR; "
        "BREAK EDGES 0.15 MAX.",
        "TURN COMPLETE IN ONE SETUP; STUD OD IS THE WHEEL BEARING SURFACE -- "
        "NO TOOL MARKS OR STEPS.",
    )
)
