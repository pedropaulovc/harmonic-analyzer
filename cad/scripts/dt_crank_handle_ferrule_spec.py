r"""Pure-data contract for MHA-DT-34, the crank handle's brass ferrule.

User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the bright ring at the
crank end of the ebonized handle is a separate brass ferrule, not a painted
band on the oak.  It is epoxied on a turned tenon of MHA-DT-08, seated against
the tenon's shoulder, and its outer end face is the face that runs against
the crank arm MHA-DT-06.

The oak tenon is turned to suit this bore, and the handle's end play is set by
facing the MHA-DT-32 shoulder at assembly (user ruling 2026-09-29, after the
MHA-DT-34 machinist review), so no length here is a stack term.  The bore
prints at .XXX (Codex P1/P2 on #1139, user ruling 2026-09-30): a looser bore
let the fitted tenon outgrow the MHA-DT-08 shoulder it seats on, and a small
one thinned the oak round the pivot bore under the rule-17 floor.  Both bore
mouths take only the title block's edge break (owner ruling 2026-10-24,
#1900).

Issue #290: the sheet prints decimal inch (``drawing_unit: in``); lengths
stay physical millimetres, each the exact decimal of its printed inch value.

Local frame: the axis is local +X, the part's origin plane is the arm-bearing
end face (x=0), and the seat face against the oak shoulder is at x=LENGTH --
the handle's own frame, so the drive train places both with one transform.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

import _config
from _inch_wall_limits import WALL_FLOOR_MM
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm

UNIT = drawing_unit(
    "parts/dt-crank-handle-ferrule", _config.parts("dt-crank-handle-ferrule")
)

# The ring leaves the bench at the 9/16-in rod's own OD and is skimmed to the
# grip contour with the MHA-DT-08 shoulder after the epoxy cures (user ruling
# 2026-10-01, local review of 47cb8a46b: glued on, the ring can sit off the
# reamed bore, so an oak shoulder turned true to the bore could not finish
# flush with a pre-turned OD).  The default configuration is the ring as made;
# INSTALLED is it skimmed, and the drive train places that.
STOCK_DIA = 0.5625 * 25.4
# Cold-drawn brass rod, 9/16 in, -0.002 in (ASSUMPTION, the supplier's
# commercial tolerance; not sourced in this repo).
STOCK_DIA_MIN = round(STOCK_DIA - 0.002 * 25.4, 6)
OUTER_DIA = STOCK_DIA
# Skimmed Ø.49 x .28 as installed (user ruling 2026-09-30, ch30
# eight-views-4: the ring reads ~Ø11-12, not the Ø15 first derived).
INSTALLED_OUTER_DIA = 12.446  # .49
INSTALLED_CONFIG = "INSTALLED"
# The fitted tenon keeps the rule-17 floor of oak over the reamed pivot bore
# with the bore's eccentricity between them (local review of 1f3067ef2).
BORE_DIA = 7.6962  # .303
BORE_DIA_TOL = printed_band_mm(3, unit=UNIT)
LENGTH = 7.112  # .28
# Joint dimensions shared with MHA-DT-08, whose spec imports this one.
# The shortest tenon must retain this much uninterrupted bonded length.
TENON_LENGTH = 5.08  # .20
TENON_GLUE_LENGTH_FLOOR = 3.5
# Owner ruling 2026-10-24 (#1900, option 4) supersedes owner ruling A on #1661
# (a chamfer) for the seat mouth: MHA-DT-08's tenon root is relieved into its
# shoulder, clear of the seat face, so this mouth takes only the title block's
# edge break, and the brass the chamfer took stays in the skimmed wall
# (dt_crank_handle_spec.FERRULE_MOUTH_WALL_MIN).  It is not modelled, as no
# other edge break is; the walls and the glue length budget it at its largest.
SEAT_MOUTH_BREAK_MAX = edge_break_chamfer_mm(unit=UNIT)

# Brass wall, on radius, as made: the smallest stock over the largest bore.
# The skimmed wall, with the ring off-centre, is MHA-DT-08's check.
WALL_WORST = (STOCK_DIA_MIN - (BORE_DIA + BORE_DIA_TOL)) / 2.0
if WALL_WORST < WALL_FLOOR_MM:
    raise AssertionError("MHA-DT-34 ferrule wall is under .060 at the worst case")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FerruleProfile": {"OuterDia", "BoreDia", "Length"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FerruleProfile": {"OuterDia": 4, "BoreDia": 3, "Length": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-DT-34 dimension needs authored places")
# The OD is the rod as supplied: a reference, printed as the rod's fraction.
REFERENCE_DIMENSIONS = frozenset({"OuterDia"})
STOCK_FRACTION_DENOMINATOR = 16

# The oak tenon is turned to suit this bore for an epoxy line (the handle spec
# reads it from here); the bore's callout states it, so the fitted joint has
# its acceptance.  The sheet's prose lives in dt_crank_handle_ferrule_notes,
# which the mating parts never import.
TENON_GLUE_LINE = (0.0508, 0.1524)  # .002-.006
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
