r"""Pure-data dimensional contract shared by the pivot shaft and drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_LENGTH = 203.2

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SectionProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

# The length tolerance rides the 203.20 dimension itself (a machinist review
# flagged a tolerance living only in a general note as easy to miss), so the
# note carries just the finishing requirements.
DRAWING_NOTES = "\n".join(
    (
        "CENTRE MARKS 1.0 DEEP MAX.",
        "TURN OR CENTRELESS-GRIND FULL BEARING LENGTH; NO FLATS OR STEPS.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
