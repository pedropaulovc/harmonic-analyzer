r"""MHA-DT-34 ferrule drawing prose -- its feature callouts and isometric label.

Split OUT of ``dt_crank_handle_ferrule_spec`` (MHA-DT-34 machinist ENFORCE),
as ``dt_crank_handle_butt_cup_notes`` was for the cup: the MHA-DT-08 handle
spec and the drive train import that module, so prose living there re-keyed
both on every wording edit.  The ferrule's part builder and drawing script
import this module; the mating parts never do.

No general note remains (MHA-DT-34 machinist ENFORCE, r1-r3).  Every
requirement that has a feature sits on that feature's callout (rule 7: flag it
where it applies), naming the mate that sets it (rule 4): the bore's matched
fit, the OD's skim with the handle, and both limits of the seat mouth's
chamfer.  The section already shows the bore running through, so THRU rides
on its callout; bonding the ring on is the assembly's business, not this
part's.
"""

from __future__ import annotations

from dt_crank_handle_ferrule_spec import INSTALLED_OUTER_DIA, TENON_GLUE_LINE

# The mating part, quoted only to identify it (rule 7); the offline test
# checks it against the registry.
HANDLE_NUMBER = "MHA-DT-08"
# The tenon root's largest radius on MHA-DT-08, quoted for the chamfer's
# callout: dt_crank_handle_spec.INSIDE_CORNER_R_MAX, which the ferrule's
# modules cannot import (that spec imports the ferrule's); the offline test
# checks it.
HANDLE_ROOT_R_MAX = 0.3

# The bore's +/-0.10 band is a matched fit: the oak tenon is turned to suit
# this bore for an epoxy line (r1-r3 finding 1: name the mate and the
# clearance at the callout, not in a general note).  Short rows keep the block
# between the bore's extension lines.
BORE_FIT_CALLOUT = "\n".join(
    (
        f"THRU; {HANDLE_NUMBER} TENON",
        f"TURNED TO SUIT, {TENON_GLUE_LINE[0]:.2f}-{TENON_GLUE_LINE[1]:.2f}",
        "DIAMETRAL CLEARANCE",
    )
)
# The OD is the 9/16-in rod as supplied (a reference), skimmed to the grip
# contour with the handle after the epoxy cures (user ruling 2026-10-01); the
# finished size sits on the OD itself (r1-r3 finding 2).
OUTER_DIA_CALLOUT = "\n".join(
    (
        "9/16 ROD STOCK;",
        f"SKIM TO <MOD-DIAM>{INSTALLED_OUTER_DIA:.1f}",
        f"WITH {HANDLE_NUMBER}",
        "AFTER CURE",
    )
)
# Both limits of the seat mouth's band are functional (owner ruling A on
# #1661): the minimum clears the MHA-DT-08 tenon root so the ring seats on its
# shoulder, and the maximum keeps the tenon's glue-length floor (r2-r3
# finding 4: a callout naming only the clearance left the upper limit
# unexplained).
SEAT_MOUTH_CHAMFER_CALLOUT = "\n".join(
    (
        "X 45 DEG SEAT END;",
        f"MIN CLEARS {HANDLE_NUMBER}",
        f"TENON ROOT R{HANDLE_ROOT_R_MAX:.1f}, MAX",
        "KEEPS GLUE LENGTH",
    )
)

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
