r"""Crank pin drawing prose -- the fit callout and the numbered notes.

Imported ONLY by ``draw_dt_crank_pin`` and its offline test (the
``dt_crankshaft_notes`` pattern), so a wording edit re-keys the drawing, never
the part or the many modules that read ``dt_crank_pin_spec``.
"""

from __future__ import annotations

from dt_crank_pin_spec import DESIGNATION, SKU, STANDARD

# Note 1: the stock, named once (rule 7: no method), in the MHA-DT-39
# bought-and-reworked form (owner ruling 2026-11-20, #2368: a bought No. 3
# taper pin, cross-drilled only).  Rule 7 allows four short lines, so the
# stock and the reference statement share one note (Codjiflo on #3158: six
# lines).
STOCK_NOTE = "\n".join(
    (
        f"1. McMASTER-CARR {SKU}, {DESIGNATION} ({STANDARD}):",
        "   ADD THE RING HOLE ONLY; UNDIMENSIONED GEOMETRY IS REFERENCE.",
    )
)

# The ring hole's station runs from the big end's RIM, not the crown's apex
# (dt_crank_pin_spec: the bought pin's ends are crowned about .03 high;
# Codjiflo on #3158).  Words over the station's value: below it the rows would
# run into the pin outline, which the value's text clears by only ~10 mm.
# One row: an above-callout with a line break does not print (r2 of #3158's
# layout audit, text-unmatched; dt_cone_tip_gear_notes.CALLOUTS_ABOVE).
RING_HOLE_STATION_CALLOUT_ABOVE = "FROM END RIM"

# The taper's leader callout links the fit note (drawing-guidelines.md rule 7:
# a flagged note, at most two lines of words).
TAPER_NOTE_NUMBER = 2
TAPER_CALLOUT = f"DRIVE FIT\nSEE NOTE {TAPER_NOTE_NUMBER}"

# The matched fit (rule 4): both mates by name and number, the fit by its
# standard name (rule 26: DRIVE, not LIGHT DRIVE) and the ream at assembly
# that makes it.  The acceptance that ends the ream (#2231: the driven pin's
# keeper ring MHA-DT-27 still clears the hub; dt_crank_pin_ring_spec.PIN_PROUD
# books that clearance) sits on the reamed parts, the crank hub's and the
# crankshaft's note 1: the bought pin is not cut, so on its sheet the clause
# was an assembly requirement (machinist review of 3d3ad23a09).
TAPER_NOTE = "\n".join(
    (
        f"{TAPER_NOTE_NUMBER}. DRIVE FIT IN CRANK HUB MHA-DT-31 AND CRANKSHAFT MHA-DT-11, REAMED",
        "   1:48 TOGETHER AT ASSEMBLY.",
    )
)

SHEET_NOTES = "\n".join((STOCK_NOTE, TAPER_NOTE))
