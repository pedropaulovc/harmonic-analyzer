r"""Crank pin drawing prose -- the taper callout and its numbered note.

Imported ONLY by ``draw_dt_crank_pin`` and its offline test (the
``dt_crankshaft_notes`` pattern), so a wording edit re-keys the drawing, never
the part or the many modules that read ``dt_crank_pin_spec``.
"""

from __future__ import annotations

# The taper's leader callout: the ratio (the end diameters' .XX bands do not
# control it) and SEE NOTE 1 (drawing-guidelines.md rule 7: size and process
# lines plus at most two lines of words).
TAPER_NOTE_NUMBER = 1
TAPER_CALLOUT = f"1:48 TAPER ON DIAMETER\nSEE NOTE {TAPER_NOTE_NUMBER}"

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
