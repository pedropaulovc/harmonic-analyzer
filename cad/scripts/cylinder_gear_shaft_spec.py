r"""Pure-data dimensional contract shared by the cylinder-gear arbor and drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

SHAFT_DIA = 0.375 * MM_PER_IN  # ch13: = cam bore (legacy parameters.kcl)
SHAFT_LENGTH = 187.0  # ch13 stack + journals; installed -54.585..+132.415:
# 7.0 mm seated in the north arbor-pedestal bore band
# (PR8, ch12 img09 -- the base-
# standing north clamp restored; the pedestal foot sits just clear of the
# rocker-arm-support footprint). Was 168, clear of the old solid
# rocker-arm-support north upright (shortened from 200, 2026-06-19); south end
# The fixed-post recenter moves the former -90..+97 envelope slightly rearward
# as a unit; the south end still stops inside its pedestal bore. See
# build_drive_train_assembly.ARBOR_LENGTH / ARBOR_SOUTH_Z.

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "TURN OR CENTRELESS-GRIND FULL LENGTH; NO FLATS, STEPS OR KEYSEAT.",
        "STATIONARY ARBOR: 20 CYLINDER GEARS RUN FREE ON THE FULL O.D.; "
        "CLAMPED IN PEDESTALS AT BOTH ENDS.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
# The title block declares 1:1, so the off-scale pictorial must say so
# (codex machinist review).
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
