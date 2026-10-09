r"""MHA-VN-052 cylinder-bank-spring: McMaster 9714K392 stock wave disc spring.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One wave disc spring sits on the MHA-DT-013 arbor between the front
MHA-DT-026 thrust washer and the front MHA-DT-002 strap's inner face, where
the 0.45 end-play leaf used to be (#948 ruling R, PR #1292).  Squeezed to
INSTALLED_HEIGHT there, it holds the 20-gear stack north on the back washer
and the DRO-set back strap, so the bank has no end play
(``cylinder_bank_layout``).

Catalogue (mcmaster.com/9714K392, read live 2026-10-09): Wave Disc Spring,
steel, stackable; ID 0.385 in -0.01/+0.01, OD 0.5 in -0.01/+0.01, thickness
0.005 in, height 0.05 in (free); compressed height 0.024 in and deflection
0.026 in at the 1.5 lb working load; pack of 10, $11.18.  The page states no
rate and no wave count.  A 3-D SolidWorks model is offered but none was
fetched, so the part is catalogue-only.

Part frame: spring axis local +Z.  The model is the spring's installed
envelope: the ID x OD annulus from its south bearing face (on the front
strap) at z = 0 to its north bearing face (on the front washer) at
z = MODEL_HEIGHT, the nominal set gap.  [INFERENCE: the waves are not
modelled; the envelope is what the bank layout and the interference gate
see.]
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4
N_PER_LBF = 4.4482216

SKU = "9714K392"
COUNT = 1

ID = 0.385 * MM_PER_IN  # 9.779
ID_BAND = (0.01 * MM_PER_IN, -0.01 * MM_PER_IN)  # (upper, lower)
OD = 0.5 * MM_PER_IN  # 12.7
OD_BAND = (0.01 * MM_PER_IN, -0.01 * MM_PER_IN)  # (upper, lower)
THICKNESS = 0.005 * MM_PER_IN  # 0.127
FREE_HEIGHT = 0.05 * MM_PER_IN  # 1.27
WORKING_HEIGHT = 0.024 * MM_PER_IN  # 0.6096, compressed at the working load
WORKING_DEFLECTION = 0.026 * MM_PER_IN  # 0.6604
WORKING_LOAD_N = 1.5 * N_PER_LBF  # 6.672
# [INFERENCE: linear] The page gives one load point, no rate.
RATE_N_PER_MM = WORKING_LOAD_N / WORKING_DEFLECTION  # 10.10
# The set gap between the front washer and the front strap: one 0.95 blade
# (cylinder_bank_layout.BANK_SPRING_SET).  Load there 3.2 N,
# (FREE_HEIGHT - INSTALLED_HEIGHT) x RATE [INFERENCE: linear].
INSTALLED_HEIGHT = 0.95
# The model shows the installed state.
MODEL_HEIGHT = INSTALLED_HEIGHT

if not math.isclose(FREE_HEIGHT - WORKING_DEFLECTION, WORKING_HEIGHT):
    raise AssertionError("9714K392 free height, deflection and working height disagree")
if not THICKNESS < WORKING_HEIGHT <= MODEL_HEIGHT < FREE_HEIGHT:
    raise AssertionError("9714K392 modelled height is outside the working range")


def spring_load(height: float) -> float:
    """Axial load, N, squeezed to ``height`` [INFERENCE: linear rate]."""
    return (FREE_HEIGHT - height) * RATE_N_PER_MM


def spring_volume() -> float:
    """The modelled solid, mm^3: the installed envelope annulus."""
    return math.pi / 4.0 * (OD**2 - ID**2) * MODEL_HEIGHT
