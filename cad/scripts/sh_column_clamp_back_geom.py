r"""Column-clamp-back nominal geometry -- the drawing-FREE constant block shared
by the part build, its ``_spec`` (drawing contract) and the paper-drive
assembly's clamp-screw stack checks.

PURE DATA, no SolidWorks/COM and no drawing imports.  Kept SEPARATE from
``sh_column_clamp_back_spec`` for the reason ``sh_column_clamp_front_geom``
gives: an assembly depends on whatever module it imports a constant from, so a
print-note edit must not move the assembly's recipe digest.

Envelope constants mirror ``_clamp_arc`` (the shared semi-arc builder) through
``sh_column_clamp_front_geom``; the offline drawing test pins the mirror.
"""

from __future__ import annotations

from _hole_spec import HoleSpec, blind_cut_dia_mm

# Column axis to the back face. 15.5 (was 14.0, a 1.2 wall past the column):
# user ruling 2026-10-14, a 2.7 nominal wall that holds 2.0 at the printed
# worst case (sh_column_clamp_back_spec.BACK_WALL_MIN).
DEPTH = 15.5
# The mating face stops this far short of the column axis (user ruling
# 2026-10-14). With both half-bores at Ø25.6 and both mating faces on the axis
# the faces met before the bores closed on the Ø25.4 column, so the clamp
# could not grip; the offset keeps a gap between the faces once the screws
# seat both bores on the column (sh_column_clamp_fit.GRIP_GAP_MIN).
GRIP_OFFSET = 0.5
BLOCK_DEPTH = DEPTH - GRIP_OFFSET  # 15.0: mating face to back face
# The Ø4.17 clamp-screw shanks THREAD IN here (back arc = last in the stack):
# tapped #8-32 through (nearest UNC to the ~Ø4 screw;
# memory/fastener-policy-us-customary). The tapped length is BLOCK_DEPTH.
HOLE_SPEC = HoleSpec("tapped", "#8-32")
TAP_DRILL_DIA = blind_cut_dia_mm(HOLE_SPEC)
