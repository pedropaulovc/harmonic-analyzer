r"""Pure-data dimensional contract shared by the fulcrum shaft and drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_LENGTH = 182.0

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SectionProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "CENTRE MARKS 1.0 DEEP MAX.",
        "TURN OR CENTRELESS-GRIND FULL BEARING LENGTH; NO FLATS OR STEPS.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
