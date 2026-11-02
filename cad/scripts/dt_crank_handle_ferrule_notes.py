r"""MHA-DT-34 ferrule drawing prose -- its feature callouts and isometric label.

Split OUT of ``dt_crank_handle_ferrule_spec`` (MHA-DT-34 machinist ENFORCE),
as ``dt_crank_handle_butt_cup_notes`` was for the cup: the MHA-DT-08 handle
spec and the drive train import that module, so prose living there re-keyed
both on every wording edit.  Only the ferrule's drawing script imports this
module, so a callout edit re-keys neither the part nor its mates; it reads
the stated walls from the MHA-DT-08 spec, which owns their stack.

No general note remains (MHA-DT-34 machinist ENFORCE, r1-r3).  Every
requirement that has a feature sits on that feature's callout (rule 7: flag it
where it applies), naming the mate that sets it (rule 4): the bore's matched
fit, and the OD's skim with the handle and the walls that skim leaves.  The
section already shows the bore running through, so THRU rides on its callout;
bonding the ring on is the assembly's business, not this part's.
"""

from __future__ import annotations

import math

from dt_crank_handle_ferrule_spec import (
    INSTALLED_OUTER_DIA,
    TENON_GLUE_LINE,
)
from dt_crank_handle_spec import (
    FERRULE_ARM_FACE_WALL_MIN,
    FERRULE_MOUTH_WALL_MIN,
    MM_PER_IN,
    inch_text,
)

# The mating part, quoted only to identify it (rule 7); the offline test
# checks it against the registry.
HANDLE_NUMBER = "MHA-DT-08"


def _floor_3pl(value_mm: float) -> float:
    """A stated minimum never rounds up past the derived worst case: the
    printed thousandth below ``value_mm``, in millimetres."""
    return math.floor(round(value_mm / MM_PER_IN * 1000.0, 6)) / 1000.0 * MM_PER_IN


# The skimmed brass at each end at the worst case, stated as plain facts
# (rule 20): owner rulings 2026-10-24 (#1900, seat face) and 2026-10-26
# (#1900, arm face), declared as minor exceptions RV-01 and RV-02 in
# dt-crank-handle-ferrule.yaml.
SEAT_FACE_WALL_MIN = _floor_3pl(FERRULE_MOUTH_WALL_MIN)
ARM_FACE_WALL_MIN = _floor_3pl(FERRULE_ARM_FACE_WALL_MIN)

# The bore's .XXX band is a matched fit: the oak tenon is turned to suit
# this bore for an epoxy line (r1-r3 finding 1: name the mate and the
# clearance at the callout, not in a general note).  BORE names the process,
# so the .XXX row, not DRILLED HOLES, sets its limits (#290 review of
# eb22a22f1).  Short rows keep the block between the bore's extension lines.
BORE_FIT_CALLOUT = "\n".join(
    (
        f"BORE THRU; {HANDLE_NUMBER} TENON",
        f"TURNED TO SUIT, {inch_text(TENON_GLUE_LINE[0], 3)}-"
        f"{inch_text(TENON_GLUE_LINE[1], 3)}",
        "DIAMETRAL CLEARANCE",
    )
)
# The OD is the 9/16-in rod as supplied: an untoleranced reference whose
# supplier tolerance governs (owner rule; #290 reviews asked for a printed
# band), skimmed to the grip contour with the handle after the epoxy cures
# (user ruling 2026-10-01); the finished size sits on the OD itself (r1-r3
# finding 2), with the walls the skim leaves.
OUTER_DIA_CALLOUT = "\n".join(
    (
        "9/16 ROD AS SUPPLIED;",
        f"SKIM TO <MOD-DIAM>{inch_text(INSTALLED_OUTER_DIA, 2)}",
        f"WITH {HANDLE_NUMBER}",
        "AFTER CURE;",
        f"WALL {inch_text(SEAT_FACE_WALL_MIN, 3)} MIN AT SEAT FACE;",
        f"WALL {inch_text(ARM_FACE_WALL_MIN, 3)} MIN AT ARM FACE",
    )
)
