r"""Pure-data dimensional contract shared by the cylinder-gear arbor and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace, GeometricControl, PartDatum
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

SHAFT_DIA = 0.375 * MM_PER_IN  # ch13: = cam bore (legacy parameters.kcl)
SHAFT_LENGTH = 187.0  # ch13 stack + journals; installed -54.585..+132.415:
SHAFT_DIA_BAND = SHAFT_H
LENGTH_TOLERANCE_MM = 0.25
# 7.0 mm seated in the north arbor-pedestal bore band
# (PR8, ch12 img09 -- the base-
# standing north clamp restored; the pedestal foot sits just clear of the
# rocker-arm-support footprint). Was 168, clear of the old solid
# rocker-arm-support north upright (shortened from 200, 2026-06-19); south end
# The fixed-post recenter moves the former -90..+97 envelope slightly rearward
# as a unit; the south end still stops inside its pedestal bore. See
# build_drive_train_assembly.ARBOR_LENGTH / ARBOR_SOUTH_Z.

# No geometric controls: the arbor is one plain cylinder whose running fit is
# the SHAFT_H band on the model diameter (cad/docs/drawing-simplicity-policy.md
# rule 3). The typed tuples stay so build_cylinder_gear_shaft's
# author_part_pmi call shape is unchanged.
PART_DATUMS: tuple[PartDatum, ...] = ()
GEOMETRIC_CONTROLS: tuple[GeometricControl, ...] = ()
# The arbor OD is the one running surface: the 20 cylinder gears run free on
# it (rule 5).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "arbor_bearing",
        MACHINED_UM,
        CylinderFace(SHAFT_DIA, contains_y_mm=SHAFT_LENGTH / 2.0),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6). "NO KEYSEAT" is the M6.2
# keyway refutation: the legacy drawings show a keyseat on this arbor, but the
# gears run free on it at different speeds, so the print must forbid cutting
# one -- a specific guard against a documented trap, not a restatement of the
# plain cylinder. The turned-or-ground finish and "no flats or steps" were
# what the title block and the views already say (machinist review,
# 2026-09-02).
DRAWING_NOTES = "\n".join(
    (
        "NO KEYSEAT.",
        "CENTRES OK.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
# The title block declares 1:1, so the off-scale pictorial must say so
# (codex machinist review).
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
