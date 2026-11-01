r"""MHA-DT-35 butt-cup drawing prose -- its feature callouts and isometric label.

Split OUT of ``dt_crank_handle_butt_cup_spec`` (MHA-DT-35 machinist ENFORCE,
#1375): the MHA-DT-08 handle and MHA-DT-32 pivot-screw specs import
that module, so prose living there re-keyed both parts, their drawings and the
drive train on every wording edit.  The cup's part builder and drawing script
import this module; the mating parts never do.

Owner ruling B on #1375 restores the pocket-wall floor by enlarging the body,
so no general note remains.  Every requirement that has a feature sits on that
feature's callout (rule 7: flag it where it applies), naming the mate that
sets it (rule 4).
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
# The body is epoxied into the MHA-DT-08 counterbore, which is bored to suit
# it; the band's mate is that bore (r1 finding 3).
BODY_FIT_CALLOUT = f"EPOXY FIT IN {HANDLE_NUMBER}"
# Matched fit on the first-made MHA-DT-32 head: name and number and the
# diametral clearance (rule 4; r1 finding 2).  The largest head plus the
# widest clearance is the largest bore, so no separate cap prints (#290 review
# of eb22a22f1 called a Ø MAX row over-specification); the wall it leaves
# inside the smallest body is stated as a plain fact (rule 20).
POCKET_FIT_CALLOUT = "\n".join(
    (
        f"BORE TO SUIT {SCREW_NUMBER}",
        f"{SCREW_NAME} HEAD, {inch_text(POCKET_CLEARANCE[0], 3)}-"
        f"{inch_text(POCKET_CLEARANCE[1], 3)}",
        "DIAMETRAL CLEARANCE;",
        f"WALL {inch_text(POCKET_WALL_MIN, 3)} MIN",
    )
)
# The depth band's mate and reason (r1 finding 4).  The floor corner's
# separate model-owned radial MAX dimension controls head seating (finding 5).
POCKET_DEPTH_CALLOUT = "\n".join((f"KEEPS {SCREW_NUMBER} HEAD", "BELOW FACE"))
# The local corner limit is tighter than the title block: identify the head
# and its flat seating function at the radius itself (rules 4 and 7).
POCKET_FLOOR_RADIUS_CALLOUT = "\n".join((f"{SCREW_NUMBER} HEAD", "SEATS ON FLOOR"))
# The bottom chamfer's band reason: it clears the rounded corner of the
# MHA-DT-08 counterbore floor, so the cup seats with its face flush.
BODY_CHAMFER_CALLOUT = "\n".join(
    ("X 45 DEG", f"CLEARS {HANDLE_NUMBER}", "COUNTERBORE CORNER")
)

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"
