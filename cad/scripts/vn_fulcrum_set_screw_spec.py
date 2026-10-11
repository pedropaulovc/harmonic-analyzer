r"""Pure-data contract for the fulcrum-shaft set screw (MHA-VN-055).

One #1-72 x 5/32 in hex socket cup-point set screw in each MHA-CH-007 fulcrum
keeper: it drops vertically through the #1-72 tap in the keeper's lug crown
top onto the flat on the plain Ø6.35 fulcrum shaft, fixing the shaft axially
and in rotation.

PURCHASED: McMaster-Carr 91375A942, alloy steel cup-tip set screw, black
oxide, Rockwell C45, 0.035 in hex drive (family table: Class 3A, ASME B18.3 /
ASTM F912), read live 2026-10-09.

The part is the catalogue-only replica (diagnostics/diag_build_91375A942).
These are the few of its dimensions the keeper and the channel assembly read,
restated here so neither imports a SolidWorks recipe; test_vn_fulcrum_set_screw
pins the two in lockstep.
"""

from __future__ import annotations

from _hole_spec import THREAD_MAJOR_MM
from ch_fulcrum_keeper_spec import SET_SCREW_THREAD

MM_PER_IN = 25.4

# 5/32 chosen over 1/8 for rule-12 installed engagement: >= 1.52D worst (1/8
# gave 1.40D). The socket face sits 0.156 below the keeper crown apex at
# nominal. At the worst case (CrownDia .X min + shallowest flat) it stands up
# to 0.374 proud, in free air above the crown (Main ruling A, 2026-10-10).
SKU = "91375A942"
THREAD = SET_SCREW_THREAD  # #1-72 UNF
MAJOR_DIA = THREAD_MAJOR_MM[THREAD]  # 0.073 in
PITCH = MM_PER_IN / 72.0
LENGTH = 5.0 / 32.0 * MM_PER_IN  # 3.96875, nominal, cup end to socket face
HEX_AF = 0.035 * MM_PER_IN
# The plain point below the first full thread: the cup-end chamfer, one pitch
# long (the 91375A family law).
POINT_LENGTH = PITCH
# Cup-point outer diameter: the 2-D PDF gives none, so the ASME B18.3
# cup-point maximum for #1 (0.040 in).
CUP_DIA = 0.040 * MM_PER_IN

if POINT_LENGTH >= LENGTH:
    raise AssertionError("set-screw point overruns its length")
