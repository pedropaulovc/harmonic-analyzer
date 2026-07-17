r"""Pure-data dimensional contract shared by the pinion lift rod and drawing."""

from __future__ import annotations


ROD_DIA = 6.35
ROD_LEN = 202.0
CAP_SAG = 1.2
CAP_R = round((ROD_DIA**2 / 4.0 + CAP_SAG**2) / (2.0 * CAP_SAG), 2)  # 4.80

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RodDia"},
    "Rod": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        f"CROWN BACK END SR{CAP_R} +/-0.25 FULL DOME TO THE {ROD_LEN} RIM "
        f"({CAP_SAG} REF PROUD; OAL {ROD_LEN + CAP_SAG} REF); "
        "BLEND SMOOTH, NO STEP.",
        f"TURN OR CENTRELESS-GRIND THE CYLINDRICAL OD OVER THE {ROD_LEN} "
        "LENGTH; NO FLATS OR STEPS.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
