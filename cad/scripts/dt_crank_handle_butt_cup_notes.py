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

from dt_crank_handle_butt_cup_spec import POCKET_WALL_MIN
from dt_crank_handle_spec import COUNTERBORE_GLUE_LINE
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
# The pocket is one feature with three tight dimensions (its limits, its
# depth and its floor corner): it names its mate once, on one numbered flag
# note linked to all three (drawing-guidelines.md rule 4).  Cut to its own
# limits, it clears the MHA-DT-32 head at its own band: no matching, no
# clearance to read (owner ruling 2026-11-24, fit audit question 15; the note
# had bored the pocket to the head while the travelers turned the head to the
# pocket).  The tool (the 1/4 end mill, plunged) is the traveler's, not the
# note's (rule 7; machinist review r1, farm run 20261124T110807008Z).  Notes
# carry no dimensions.  The governing wall the pocket's upper limit leaves,
# at the face with both edges broken (#2170), is stated as a plain fact on
# the pocket's own callout (rule 20; RV-01).
POCKET_NOTE = 1
POCKET_FLAG = f"SEE NOTE {POCKET_NOTE}"
POCKET_FIT_CALLOUT = "\n".join((POCKET_FLAG, f"WALL {inch_text(POCKET_WALL_MIN, 3)} MIN"))
POCKET_NOTE_TEXT = "\n".join(
    (
        f"{POCKET_NOTE}. POCKET: CLEARS {SCREW_NUMBER}",
        f"   {SCREW_NAME} HEAD.",
    )
)
# The bottom chamfer's band reason: it clears the rounded corner of the
# MHA-DT-08 counterbore floor, so the cup seats with its face flush.
BODY_CHAMFER_CALLOUT = "\n".join(
    ("X 45°", f"CLEARS {HANDLE_NUMBER}", "COUNTERBORE CORNER")
)
# The floor hole's pocket-side mouth break (#1757) names the MHA-DT-32 corner
# it clears, so the head seats flat on the floor (rule 3's CLEARS form).
FLOOR_HOLE_CHAMFER_CALLOUT = "\n".join(
    ("X 45°", f"CLEARS {SCREW_NUMBER}", "UNDER-HEAD RADIUS")
)
# The body is bonded in the MHA-DT-08 counterbore: a matched bonded fit,
# turned to the measured counterbore, whose diametral clearance is the
# handle's glue line, REF (rules 4 and 26; rule 23: epoxy, wood to metal).
# The fit lives on flag note 2: printed on the dimension (round 2) its two
# lines ran into the floor-hole dimension line, and the .XXX grade alone
# cannot give a .004-wide clearance, so the matched route must be printed.
_MM_PER_IN = 25.4
BODY_NOTE = POCKET_NOTE + 1
BODY_FLAG = f"SEE NOTE {BODY_NOTE}"
BODY_NOTE_TEXT = "\n".join(
    (
        f"{BODY_NOTE}. BODY: BONDED FIT IN {HANDLE_NUMBER} CRANK HANDLE, EPOXY:",
        "   TURN TO THE MEASURED COUNTERBORE (CLEARANCE "
        + "-".join(
            f"{value / _MM_PER_IN:.3f}".removeprefix("0")
            for value in COUNTERBORE_GLUE_LINE
        )
        + ").",
    )
)
# The sheet's numbered notes, printed by draw_dt_crank_handle_butt_cup and
# read by the feature export (export_features).
DRAWING_NOTES = f"{POCKET_NOTE_TEXT}\n{BODY_NOTE_TEXT}"

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"
