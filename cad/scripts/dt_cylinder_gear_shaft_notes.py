"""Sheet text for the cylinder-gear arbor (MHA-DT-13), above its spec.

``dt_cylinder_gear_shaft_spec`` is imported across the fleet for the arbor's
size, so the words the sheet and the part's Manufacturing Notes print live
here: editing them re-keys only this part and its drawing.
"""

from __future__ import annotations

# The cup-point set screws that make the spots, and the pedestal whose taps
# they are drilled through, by drawing number (rule 4; fan-out screen
# 20261107T081227004Z: "SET-SCREW SPOTS" named no mate).  Hard-coded, not
# read from ``_config.parts``: a registry read would make two more part rows
# rebuild inputs; test_dt_cylinder_gear_shaft_drawing checks them offline.
SET_SCREW_NUMBER = "MHA-SH-VN-54"
PEDESTAL_NUMBER = "MHA-DT-02"

# drawing-guidelines.md rule 4 (tighten only for function, and name the mate):
# the O.D. band exists for the 20 MHA-DT-12 gears that run on it and the two
# MHA-DT-02 strap bores it fills, so the callout names both.  Its band is
# narrower than the shop's turned-diameter row, so the callout also names the
# fit route, purchased ground stock, at the feature (fan-out screen: the route
# sat in an unlinked general note).  One row: SOLIDWORKS stores a multi-line
# ABOVE callout but prints none of it (fan-out r1 57234c1d71 printed a bare
# Ø; draw_dt_pinion_lift_rod), and the below lane sits on the .06 dome.
SHAFT_DIA_CALLOUT = "RUNNING FIT IN MHA-DT-12 AND MHA-DT-02 BORES; 3/8 GROUND STOCK OK"

# Part-specific facts a machinist cannot read off the views (rule 7).  A
# 6.5:.375 slender bar is turned between centres, which may stay.  The length
# is cut at assembly, so the shop supplies the bar long (7-1/2 in covers the
# nominal span, both domes and facing stock) and domes the cut ends.
DRAWING_NOTES = "\n".join(
    (
        "CENTRES OK.",
        "SUPPLY 7-1/2 LONG, UNCUT; CUT AND DOME BOTH ENDS AT ASSEMBLY.",
    )
)
# The set screws' cup points bear in spots drilled through the pedestal taps
# at assembly (#743), so the bar is never flatted: a match-drill at assembly
# with its mates, a requirement (rule 7).  It prints at a leader on the bar's
# end under the pedestal strap, not in the unflagged block: the fan-out local
# repeat of e308920ca9 (3 of 3 runs) found nothing tied it to the shaft.
SPOT_NOTE = "\n".join(
    (
        f"NO FLATS; SPOTS FOR {SET_SCREW_NUMBER} SET SCREWS",
        f"DRILLED AT ASSEMBLY THROUGH {PEDESTAL_NUMBER} TAPS",
    )
)
