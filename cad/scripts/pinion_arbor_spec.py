r"""Pure-data dimensional contract shared by the pinion arbor and drawing."""

from __future__ import annotations


SHAFT_DIA = 8.0
SHAFT_LEN = 226.25
CAP_SAG = 1.2
CAP_R = (SHAFT_DIA / 2.0) ** 2 / (2.0 * CAP_SAG) + CAP_SAG / 2.0  # 7.27

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
    "BackCapProfile": {"CapSagDim"},
}

DRAWING_NOTES = "\n".join(
    (
        "CENTRE MARKS 1.0 DEEP MAX.",
        "TURN OR CENTRELESS-GRIND FULL BEARING LENGTH; NO FLATS OR STEPS.",
        f"CROWN BACK END SR{CAP_R:.2f} X {CAP_SAG:g} HIGH; BLEND SMOOTH, NO SHARP RIM.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
