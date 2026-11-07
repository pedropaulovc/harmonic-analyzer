"""Sheet text for the crank handle pivot screw (MHA-DT-32), above its spec.

``dt_crank_handle_pivot_screw_spec`` feeds the crank arm, the handle, the
keeper chain and MHA-DT-00, so the words only this drawing prints live here:
editing them re-keys only this sheet.
"""

from __future__ import annotations

from dt_crank_handle_pivot_screw_spec import (
    CHAMFER_CALLOUT,
    END_PLAY_RANGE,
    THREAD_CALLOUT,
    inch_text,
)

# The fitted shoulder, stated once (user ruling 2026-09-29, after the
# MHA-DT-32 machinist review): under-head to seat face is the bonded handle's
# ferrule outer face to cup floor plus the end play (#290 review of
# b28d38a16).  The handle is measured, not the arm: the shoulder seats on the
# arm face and the handle runs between it and the head (#290 review of
# d72bdd039).  A fit-up requirement too long for a two-line callout, so the
# length prints as a reference flagged to numbered note 1 (rule 7; fan-out
# screen 20261107T081227004Z: "FACED TO SUIT" on the dimension, a private
# phrase and a method word).
SHOULDER_LENGTH_NOTE_NUMBER = 1
SHOULDER_LENGTH_CALLOUT = f"SEE NOTE {SHOULDER_LENGTH_NOTE_NUMBER}"
SHOULDER_LENGTH_NOTE = "\n".join(
    (
        f"{SHOULDER_LENGTH_NOTE_NUMBER}. SHOULDER LENGTH: MEASURED",
        "   MHA-DT-34 OUTER FACE TO MHA-DT-35",
        "   FLOOR ON BONDED HANDLE MHA-DT-08,",
        f"   PLUS {inch_text(END_PLAY_RANGE[0], 3)}-"
        f"{inch_text(END_PLAY_RANGE[1], 3)} END PLAY.",
    )
)
# The head's bands.  Its length keeps it below the cup's face, which it
# clears (rule 3's CLEARS form; KEEPS HEAD BELOW read as design rationale).
# Its three-place diameter is what MHA-DT-35's pocket is bored to (that
# sheet's matched pocket fit), so the callout names that mate (rule 4): the
# fan-out local repeat of e308920ca9 (2 of 3 runs) found "BEARS ON MHA-DT-35
# FLOOR" named a face's job, not the diameter's.  Rows of 15 characters at
# most: on one 52-mm row the block's left end ran into the head face's
# extension line (fan-out r2 5065c806b3, rule 14).
HEAD_DIA_CALLOUT = "SETS MHA-DT-35\nPOCKET BORE"
HEAD_LENGTH_CALLOUT = "CLEARS\nMHA-DT-35 FACE"
# The slender screw wants tailstock support.  The thread end only screws into
# the arm's tap, so a centre there touches no running, seating or slotted
# face; the slotted head end is the end the collet holds, so it takes none
# (rule 11: say CENTRES OK where they do no harm; fan-out local repeat of
# e308920ca9, 2 of 3 runs).  Its own row under the thread size, at that end's
# leader, so it reads as this end only.
THREAD_NOTE = f"{THREAD_CALLOUT}\nCENTRE OK"
# The relief's 45-degree lead keeps the seat annulus flat by staying inside
# the arm's tapped thread (dt_crank_handle_pivot_screw_spec), said in plain
# words (fan-out r2: "LEAD, INSIDE" is a private phrase, rule 26).  Rows of
# 18 characters at most, as the spec's callouts.
RELIEF_LEAD_CALLOUT = f"{CHAMFER_CALLOUT}\nSTAYS INSIDE\nMHA-DT-06 THREAD"
# The shoulder's running mate, at its band, by the standard fit name (rule 4);
# wrapped so the widest row (21 characters) clears the Ra 63 leader.
SHOULDER_FIT_CALLOUT = "RUNNING FIT IN\nMHA-DT-08 REAMED BORE"
