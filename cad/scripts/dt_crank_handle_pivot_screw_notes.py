"""Sheet text for the crank handle pivot screw (MHA-DT-32), above its spec.

``dt_crank_handle_pivot_screw_spec`` feeds the crank arm, the handle, the
keeper chain and MHA-DT-00, so the words only this drawing prints live here:
editing them re-keys only this sheet.
"""

from __future__ import annotations

from dt_crank_handle_pivot_screw_spec import END_PLAY_RANGE, inch_text

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
# The head's bands: its diameter keeps a bearing annulus on the cup floor
# outside the floor hole, its length keeps it below the cup's face, which it
# clears (rule 3's CLEARS form; KEEPS HEAD BELOW read as design rationale).
HEAD_DIA_CALLOUT = "BEARS ON\nMHA-DT-35 FLOOR"
HEAD_LENGTH_CALLOUT = "CLEARS MHA-DT-35 FACE"
# The shoulder's running mate, at its band, by the standard fit name (rule 4);
# wrapped so the widest row (21 characters) clears the Ra 63 leader.
SHOULDER_FIT_CALLOUT = "RUNNING FIT IN\nMHA-DT-08 REAMED BORE"
