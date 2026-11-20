r"""Crank pin drawing prose -- the fit callout and the numbered notes.

Imported ONLY by ``draw_dt_crank_pin`` and its offline test (the
``dt_crankshaft_notes`` pattern), so a wording edit re-keys the drawing, never
the part or the many modules that read ``dt_crank_pin_spec``.
"""

from __future__ import annotations

from dt_crank_pin_spec import DESIGNATION, SKU, STANDARD

# Notes 1 and 2: the stock, named once (rule 7: no method), in the MHA-DT-39
# bought-and-reworked form (owner ruling 2026-11-20, #2368: a bought No. 3
# taper pin, cross-drilled only).
STOCK_NOTE = "\n".join(
    (
        f"1. MAKE FROM McMASTER-CARR {SKU}, {DESIGNATION}",
        f"   ({STANDARD}); ADD THE RING HOLE ONLY.",
        "2. UNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE.",
    )
)

# The taper's leader callout links the fit note (drawing-guidelines.md rule 7:
# a flagged note, at most two lines of words).
TAPER_NOTE_NUMBER = 3
TAPER_CALLOUT = f"DRIVE FIT\nSEE NOTE {TAPER_NOTE_NUMBER}"

# The matched fit (rule 4): both mates by name and number, the fit by its
# standard name (rule 26: DRIVE, not LIGHT DRIVE), the ream at assembly that
# makes it, and the acceptance that ends the ream.  The acceptance is the
# crank hub's note 1 for this same joint (#2231: the driven pin's keeper ring
# MHA-DT-27 still clears the hub; dt_crank_pin_ring_spec.PIN_PROUD books that
# clearance).
TAPER_NOTE = "\n".join(
    (
        f"{TAPER_NOTE_NUMBER}. DRIVE FIT IN CRANK HUB MHA-DT-31 AND CRANKSHAFT MHA-DT-11,",
        "   TAPER-REAMED 1:48 TOGETHER AT ASSEMBLY. STOP THE REAM WHILE",
        "   KEEPER RING MHA-DT-27, HUNG FROM THE DRIVEN PIN, STILL CLEARS THE HUB.",
    )
)

SHEET_NOTES = "\n".join((STOCK_NOTE, TAPER_NOTE))
