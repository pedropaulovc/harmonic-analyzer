r"""McMaster 90325A174 catalogue inputs; pure data, no diagnostic imports.

Catalogue (https://www.mcmaster.com/90325A174/, read 2026-10-14): 18-8
stainless precision shoulder screw, shoulder Ø3/16 (-0.001/0 in) x 1/2
(0/+0.002 in); 8-32 UNC-2A x 3/8; hex-socket head Ø5/16 x 5/32, 3/32 drive.
The page states no thread-length tolerance, socket depth, head-rim chamfer or
thread neck; ASME B18.3-2012 Table 13 (hexagon socket head shoulder screws,
3/16 row) bounds them: thread length at -0.020 in (note 12, up to 3/8 size),
key engagement T 0.079 MIN, head chamfer C 0.012 MAX, thread neck G
0.112..0.120 in diameter and I 0.069 in MAX wide.

The neck is the replica-gated 91829A205 vendor law (ruling R9-7) kept as the
depiction: a R0.5715 fillet under the shoulder's END face into a Ø3.0226
land (inside G), flat to 1.1938 below that face, then a 45° ramp back to the
thread major, so the full thread starts FULL_THREAD_START = 1.7653 below the
shoulder's end face -- at or beyond ASME I MAX (1.7526), the conservative
reading for engagement.

Stock frame (the stock recipe's): axis +Y, head up, the under-head shoulder
face at y = 0 (Top Plane); the shoulder runs down to y = -SHOULDER_LEN and the
thread below it.
"""

from __future__ import annotations

IN = 25.4

SKU = "90325A174"
CATALOG_URL = "https://www.mcmaster.com/90325A174/"
CATALOG_CHECKED_DATE = "2026-10-14"
CATALOG_MATERIAL = "18-8 Stainless Steel"
SHOULDER_DIA = 3.0 / 16.0 * IN
SHOULDER_DIA_LIMITS = (-0.001 * IN, 0.0)
SHOULDER_LEN = 0.5 * IN
SHOULDER_LEN_LIMITS = (0.0, 0.002 * IN)
THREAD = "#8-32"
THREAD_CLASS = "2A"
THREAD_MAJOR = 0.164 * IN
THREAD_LEN = 3.0 / 8.0 * IN
# ASME B18.3 Table 13 note 12: thread length -0.020 in, sizes to 3/8.
THREAD_LEN_LIMITS = (-0.020 * IN, 0.0)
PITCH = IN / 32.0
HEAD_DIA = 5.0 / 16.0 * IN
HEAD_H = 5.0 / 32.0 * IN
SOCKET_AF = 3.0 / 32.0 * IN  # catalogue drive size
SOCKET_DEPTH = 0.079 * IN  # ASME T, key engagement MIN
HEAD_CHAMFER = 0.012 * IN  # ASME C MAX, 45°
# The stock point chamfer (the retired vendor law: 0.09 x thread major, 45°),
# removed when the tip is faced.
TIP_CHAMFER = 0.374904
# Thread neck under the shoulder's end face (the 91829A205 vendor law).
NECK_DIA = 3.0226
NECK_FILLET_R = 0.5715  # shoulder end-face corner into the neck
NECK_FLAT_END = 1.1938  # flat neck ends this far below the shoulder end face
# The 45° ramp regains the major here, measured from the shoulder end face.
FULL_THREAD_START = NECK_FLAT_END + (THREAD_MAJOR - NECK_DIA) / 2.0
ASME_NECK_WIDTH_MAX = 0.069 * IN
STOCK_THREAD_LEN_MIN = THREAD_LEN + THREAD_LEN_LIMITS[0]

if not 0.112 * IN <= NECK_DIA <= 0.120 * IN:
    raise AssertionError("the depicted neck leaves ASME B18.3's G band")
if FULL_THREAD_START < ASME_NECK_WIDTH_MAX:
    raise AssertionError("the full thread starts inside ASME B18.3's neck width")
