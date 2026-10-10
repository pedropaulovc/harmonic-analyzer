"""Pure McMaster 94025A164 dimensions shared by recipe and assembly placement.

Separate from the COM recipe and part-save wrapper to limit cache blast radius.
"""

from __future__ import annotations

SS_MAJOR_R = 2.413  # Screw Size Decimal Equivalent@Sketch1 / 2
SS_LEN = 9.525  # Length@Sketch1 (full, slot face to cup rim)
SS_HALF = SS_LEN / 2.0  # vendor origin sits mid-length; mine too
SS_PITCH = 0.79375  # Pitch@Sketch1 (#10-32: 25.4/32)
SS_REVS = 14.0  # vendor 13 from the face; +1 lead-in rev in air
SS_CHAM_R = 2.155222  # slot-end rim chamfer inner radius (Sketch2 Line1)
SS_CHAM_H = 4.7625 - 4.582002  # its axial extent (0.180498)
SS_TIP_R = 1.2065  # tip cone end radius = cup rim radius (Sketch2)
SS_CONE_Y = 3.556  # tip cone start / cup apex |y| (Sketch2 Line7)
SS_SLOT_W = 0.804333  # D3@Sketch1 (slot width = major / 6)
SS_SLOT_D = 0.79375  # Drive Depth@Sketch1 (slot depth = P)
# Thread cutter (vendor Sketch7, exact): UN V capped at 15P/16, root flat
# P/8, centred 7P/16 past the slot-end face in air.
SS_CUT_TOP_R = 2.455963
SS_CUT_TOP_W = 0.744141  # 15P/16
SS_CUT_ROOT_R = 1.897444  # major_r - 0.75 * (P*sqrt(3)/2)
SS_CUT_ROOT_W = 0.099219  # P/8
SS_CUT_CY = SS_HALF + SS_PITCH + 7.0 * SS_PITCH / 16.0  # 7P/16 past the raised start
# The cone-tip adjuster's cup depth: apex to rim, 45 deg.
SS_CUP_DEPTH = SS_HALF - SS_CONE_Y
assert abs(SS_CUP_DEPTH - SS_TIP_R) < 1e-9


THREAD = "#10-32"
BODY_DIA = 2.0 * SS_MAJOR_R
BODY_LEN = SS_LEN
CUP_DIA = 2.0 * SS_TIP_R
CUP_DEPTH = SS_HALF - SS_CONE_Y
