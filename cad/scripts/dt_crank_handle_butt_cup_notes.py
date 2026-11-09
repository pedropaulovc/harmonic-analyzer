r"""MHA-DT-35 butt-cup drawing prose -- its feature callouts and isometric label.

Split OUT of ``dt_crank_handle_butt_cup_spec`` (MHA-DT-35 machinist ENFORCE,
#1375): the MHA-DT-08 handle and MHA-DT-32 pivot-screw specs import
that module, so prose living there re-keyed both parts, their drawings and the
drive train on every wording edit.  The cup's part builder and drawing script
import this module; the mating parts never do.

Owner ruling B on #1375 restores the pocket-wall floor by enlarging the body.
Every requirement that has a feature sits on that feature's callout (rule 7:
flag it where it applies), naming the mate that sets it (rule 4); the pocket's
three tight dimensions share one numbered flag note.
"""

from __future__ import annotations

from dt_crank_handle_butt_cup_spec import (
    POCKET_CLEARANCE,
    POCKET_WALL_MIN,
)
from _title_block_units import MM_PER_INCH, render_number


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as this sheet prints it: ``.257``."""
    return render_number(round(value_mm / MM_PER_INCH, places), "in", places)


# The mating parts, quoted only to identify them (rule 7); the offline test
# checks them against the registry.
HANDLE_NUMBER = "MHA-DT-08"
SCREW_NUMBER = "MHA-DT-32"
SCREW_NAME = "PIVOT SCREW"

FLOOR_HOLE_CALLOUT = "DRILL THRU"
# The pocket is one feature with three tight dimensions (its reference
# diameter, its depth and its floor corner): it names its mate once, on one
# numbered flag note linked to all three (drawing-guidelines.md rule 4).  The
# matched fit on the first-made MHA-DT-32 head states the diametral clearance
# as REF; the largest head plus the widest clearance is the largest bore, so
# no separate cap prints (#290 review of eb22a22f1 called a Ø MAX row
# over-specification).  The governing wall the bore leaves, at the face with
# both edges broken (#2170), is stated as a plain fact on the bore's own
# callout (rule 20; RV-01).
POCKET_NOTE = 1
POCKET_FLAG = f"SEE NOTE {POCKET_NOTE}"
POCKET_FIT_CALLOUT = "\n".join((POCKET_FLAG, f"WALL {inch_text(POCKET_WALL_MIN, 3)} MIN"))
POCKET_NOTE_TEXT = "\n".join(
    (
        f"{POCKET_NOTE}. POCKET FOR {SCREW_NUMBER} {SCREW_NAME} HEAD: BORE TO THE",
        "   MEASURED HEAD, RUNNING FIT (CLEARANCE "
        f"{inch_text(POCKET_CLEARANCE[0], 3)}-{inch_text(POCKET_CLEARANCE[1], 3)}).",
    )
)
# The bottom chamfer's band reason: it clears the rounded corner of the
# MHA-DT-08 counterbore floor, so the cup seats with its face flush.
BODY_CHAMFER_CALLOUT = "\n".join(
    ("X 45°", f"CLEARS {HANDLE_NUMBER}", "COUNTERBORE CORNER")
)

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"
