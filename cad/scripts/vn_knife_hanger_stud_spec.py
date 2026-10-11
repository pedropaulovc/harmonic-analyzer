r"""Stock knife-hanger screw (McMaster 91251A157) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread, length and head dims the summing assembly's reach stack
and the crossbar counterbore read to prove MHA-VN-024 is the screw the knife
mount and the crossbar were sized for.  The vendor dims are ``DIMS`` in
``_mcmaster_91251a157.py`` (SolidWorks-free at import), as
``vn_cone_tip_block_screw_spec`` reads 91251A108's.

Catalogue (https://www.mcmaster.com/91251A157/): black-oxide alloy steel
socket head screw, 6-32 UNC class 3A, 1-1/2 in under the head, partially
threaded (3/4 in minimum thread length), flat tip; head Ø0.226 x 0.138 in,
7/64 hex; 170 ksi, Rockwell C37, ASTM A574.
"""

from __future__ import annotations

from _mcmaster_91251a157 import DIMS

SKU = DIMS.part_no
THREAD = "#6-32"
SHANK_DIA = DIMS.major_dia  # 3.505
PITCH = DIMS.pitch  # 0.794
LENGTH = DIMS.length  # 38.1 under the head
# The part frame's thread tip is at local y = 0, so the under-head face is
# LENGTH up the +Y axis.
UNDERHEAD_LEN = LENGTH
HEAD_DIA = DIMS.head_dia  # 5.7404
HEAD_H = DIMS.head_h  # 3.5052
# Catalogue minimum thread length from the tip; the shank above it is plain.
THREAD_LENGTH = DIMS.thread_length  # 19.05
# ASME B18.3 socket head cap screw length tolerance over 1 in through
# 2-1/2 in: -0.04 in, as (upper, lower) deviations.
LENGTH_BAND = (0.0, -0.04 * 25.4)
LENGTH_MIN = LENGTH + LENGTH_BAND[1]  # 37.084
LENGTH_MAX = LENGTH + LENGTH_BAND[0]  # 38.1
# The rule-12 thread engagement floor.
ENGAGEMENT_MIN_D = 1.5
