r"""MHA-DT-035 butt-cup drawing prose -- the note and callouts only its sheet prints.

Split OUT of ``dt_crank_handle_butt_cup_spec`` (MHA-DT-035 machinist ENFORCE,
#1375): the MHA-DT-008 handle and MHA-DT-032 pivot-screw specs import that
module, so prose living there re-keyed both parts, their drawings and the
drive train on every wording edit.  The cup's part builder (the Manufacturing
Notes property) and its drawing script import this module; the mating parts
never do.

The sheet carries one note line, the stated pocket-wall shortfall (drawing-
guidelines.md rule 20); every requirement that has a feature sits on that
feature's callout (rule 7: flag it where it applies), naming the mate that
sets it (rule 4).
"""

from __future__ import annotations

from dt_crank_handle_butt_cup_spec import (
    POCKET_CLEARANCE,
    POCKET_DIA_MAX,
    POCKET_FLOOR_CORNER_R_MAX,
    POCKET_WALL_MIN,
)

# The mating parts, quoted only to identify them (rule 7); the offline test
# checks them against the registry.
HANDLE_NUMBER = "MHA-DT-008"
SCREW_NUMBER = "MHA-DT-032"
SCREW_NAME = "PIVOT SCREW"

FLOOR_HOLE_CALLOUT = "DRILL THRU"
# The body is epoxied into the MHA-DT-008 counterbore, which is bored to suit
# it; the band's mate is that bore (r1 finding 3).
BODY_FIT_CALLOUT = f"EPOXY FIT IN {HANDLE_NUMBER}"
# Matched fit on the first-made MHA-DT-032 head: name and number, the
# diametral clearance and the hard limit (rule 4; r1 finding 2).
POCKET_FIT_CALLOUT = "\n".join(
    (
        f"BORE TO SUIT {SCREW_NUMBER}",
        f"{SCREW_NAME} HEAD, {POCKET_CLEARANCE[0]:.1f}-{POCKET_CLEARANCE[1]:.1f}",
        "DIAMETRAL CLEARANCE,",
        f"<MOD-DIAM>{POCKET_DIA_MAX:.1f} MAX",
    )
)
# The depth band's reason, and the floor corner the head bears against
# (rule 16: say the largest radius acceptable; r1 findings 4 and 5).
POCKET_DEPTH_CALLOUT = "\n".join(
    (
        f"KEEPS {SCREW_NUMBER} HEAD",
        "BELOW FACE;",
        f"FLOOR CORNER R{POCKET_FLOOR_CORNER_R_MAX:.1f} MAX",
    )
)

# Pending owner ruling on the MHA-DT-035 pocket wall (#1375): stated as a plain
# fact, never argued (rule 20).
DRAWING_NOTES = f"POCKET WALL {POCKET_WALL_MIN:.1f} MIN"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"
