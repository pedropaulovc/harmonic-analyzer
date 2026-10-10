r"""MHA-VN-055 wheel-axle-front-washer: McMaster 92916A250 brass #4 washer.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One per wheel, on the mg-wheel-axle's #4-40 end between the
magnifying wheel's spigot face and the wheel-axle nut (``mg_wheel_group``).

Catalogue (mcmaster.com/92916A250, checked live 2026-10-10 for the rev 10
design): brass washer for #4 screw, ID 0.120 in, OD 0.281 in, thickness
0.018-0.032 in.

Part frame: washer axis local +Z; the washer runs z 0..MODEL_THICKNESS.
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4

SKU = "92916A250"
COUNT = 1
ID = 0.120 * MM_PER_IN  # 3.048
OD = 0.281 * MM_PER_IN  # 7.1374
THICKNESS_MIN = 0.018 * MM_PER_IN  # 0.4572
THICKNESS_MAX = 0.032 * MM_PER_IN  # 0.8128
MODEL_THICKNESS = 0.64  # the catalogue range's nominal, 0.025 in, to 0.01

if not THICKNESS_MIN < MODEL_THICKNESS < THICKNESS_MAX:
    raise AssertionError("92916A250 modelled thickness is outside the catalogue range")


def washer_volume() -> float:
    """The modelled solid, mm^3."""
    return math.pi / 4.0 * (OD**2 - ID**2) * MODEL_THICKNESS
