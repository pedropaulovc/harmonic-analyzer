r"""Pure-data dimensional contract shared by the cylinder-gear arbor and drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

SHAFT_DIA = 0.375 * MM_PER_IN  # ch13: = cam bore (legacy parameters.kcl)
SHAFT_LENGTH = 187.0  # ch13 stack + journals; north end at machine +97: 7.0
# seated in the NORTH arbor-pedestal bore band (PR8, ch12 img09 -- the base-
# standing north clamp restored; the pedestal foot sits just clear of the
# rocker-arm-support footprint). Was 168, clear of the old solid
# rocker-arm-support north upright (shortened from 200, 2026-06-19); south end
# pulled back to machine z -90 (ch30 GT cyl_front, 2026-07-02: the end stops
# INSIDE the arbor-pedestal bore, blind-bearing look). See
# build_drive_train_assembly.ARBOR_LENGTH / ARBOR_SOUTH_Z.

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "CENTRE MARKS 1.0 DEEP MAX.",
        "TURN OR CENTRELESS-GRIND FULL LENGTH; NO FLATS, STEPS OR KEYSEAT.",
        "STATIONARY ARBOR: 20 CYLINDER GEARS RUN FREE ON THE FULL O.D.; "
        "CLAMPED IN PEDESTALS AT BOTH ENDS.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
# The title block declares 1:1, so the off-scale pictorial must say so
# (codex machinist review).
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
