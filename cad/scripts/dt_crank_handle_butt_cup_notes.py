r"""MHA-DT-035 butt-cup drawing prose -- its feature callouts and isometric label.

Split OUT of ``dt_crank_handle_butt_cup_spec`` (MHA-DT-035 machinist ENFORCE,
#1375): the MHA-DT-008 handle and MHA-DT-032 pivot-screw specs import
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
    POCKET_DIA_MAX,
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
# The depth band's mate and reason (r1 finding 4).  The floor corner's
# separate model-owned radial MAX dimension controls head seating (finding 5).
POCKET_DEPTH_CALLOUT = "\n".join((f"KEEPS {SCREW_NUMBER} HEAD", "BELOW FACE"))
# The bottom chamfer's band reason: it clears the rounded corner of the
# MHA-DT-008 counterbore floor, so the cup seats with its face flush.
BODY_CHAMFER_CALLOUT = "\n".join(
    ("X 45 DEG", f"CLEARS {HANDLE_NUMBER}", "COUNTERBORE CORNER")
)

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"
