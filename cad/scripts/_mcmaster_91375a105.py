"""Pure McMaster 91375A105 catalogue dimensions for its recipe and assemblies.

McMaster 91375A105 product page read live on 2026-10-13:
https://www.mcmaster.com/91375A105/. Alloy steel cup-tip set screw, black
oxide, 4-40 UNC Class 3A, 3/16 in long, 0.050 in hex drive, Rockwell C45,
ASME B18.3 / ASTM F912. Only a 2-D PDF is offered; no vendor solid was
harvested. It is the 1/4 in long 91375A106 (MHA-VN-034, vendor-verified
replica) cut 1/16 in shorter, so the recipe takes that replica's laws.

Frame of the recipe: axis +Y, origin mid-length; the stock part lifts the
cup end onto y = 0 with the socket face at y = +LENGTH.
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4
ALLOY_STEEL_G_PER_MM3 = 7.7e-3  # SOLIDWORKS "Alloy Steel"

SKU = "91375A105"
THREAD = "#4-40"
MAJOR_DIA = 0.112 * MM_PER_IN  # 2.8448, "Screw Size Decimal Equivalent"
PITCH = MM_PER_IN / 40.0
LENGTH = 3.0 / 16.0 * MM_PER_IN  # 4.7625, cup end to socket face
HEX_AF = 0.050 * MM_PER_IN
# The 91375A106 cup-end law: 45 deg x one pitch down to the cup diameter.
POINT_LENGTH = PITCH
CUP_DIA = MAJOR_DIA - 2.0 * POINT_LENGTH  # 1.5748

# Mass estimate: the 91375A106 vendor solid (25.8601 mm^3 at 1/4 in) less
# 1/16 in of threaded shank at the UN pitch-diameter section.
_PITCH_DIA = MAJOR_DIA - 0.649519 * PITCH
_VOLUME_MM3 = 25.8601 - (0.25 * MM_PER_IN - LENGTH) * math.pi / 4.0 * _PITCH_DIA**2
MASS_G = _VOLUME_MM3 * ALLOY_STEEL_G_PER_MM3

if POINT_LENGTH >= LENGTH:
    raise AssertionError("set-screw point overruns its length")
