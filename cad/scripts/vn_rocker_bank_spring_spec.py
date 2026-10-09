r"""MHA-VN-053 rocker-bank-spring: McMaster 9714K24 stock wave disc spring.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One wave disc spring sits on the MHA-CH-005 pivot shaft between the
MHA-CH-009 thrust washer on hub 0 and the south MHA-CH-008 ear's inner face,
where the 0.45 end-play leaf used to be (#948 ruling R, PR #1292).  Squeezed
to INSTALLED_HEIGHT there, it holds the 20-hub stack and the shaft's shoulder
north on the DRO-set north ear, so the bank has no end play and the shaft no
float (``rocker_bank_layout``).

Catalogue (mcmaster.com/9714K24, read live 2026-10-09): Wave Disc Spring,
high-carbon steel, stackable; ID 0.265 in -0.02/+0.01, OD 0.367 in
-0.02/+0.01, thickness 0.006 in, height 0.03 in (free); compressed height
0.015 in and deflection 0.015 in at the 3 lb working load; pack of 25,
$16.31.  The page states no rate, no wave count and no shaft size.  A 3-D
SolidWorks model is offered but none was fetched, so the part is
catalogue-only.

The OD at its catalogue maximum stays under the rocker hub's O10.2, so the
ch0 amplitude bar's foot passes over the spring as it does over MHA-CH-009.
The nominal ID clears the O6.35 shaft by 0.19 a side, but the catalogue's
-0.02 in ID tolerance reaches under it: the channel assembly slides each
spring onto the shaft before fitting it and rejects one that does not run
free (SHAFT_CLEARANCE_NOMINAL; a pack holds 25).

Part frame: spring axis local +Z.  The model is the spring's installed
envelope: the ID x OD annulus from its south bearing face (on the south ear)
at z = 0 to its north bearing face (on the thrust washer) at
z = MODEL_HEIGHT, the nominal set gap.  [INFERENCE: the waves are not
modelled; the envelope is what the bank layout and the interference gate
see.]
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4
N_PER_LBF = 4.4482216

SKU = "9714K24"
COUNT = 1

ID = 0.265 * MM_PER_IN  # 6.731
ID_BAND = (0.01 * MM_PER_IN, -0.02 * MM_PER_IN)  # (upper, lower)
OD = 0.367 * MM_PER_IN  # 9.3218
OD_BAND = (0.01 * MM_PER_IN, -0.02 * MM_PER_IN)  # (upper, lower)
THICKNESS = 0.006 * MM_PER_IN  # 0.1524
FREE_HEIGHT = 0.03 * MM_PER_IN  # 0.762
WORKING_HEIGHT = 0.015 * MM_PER_IN  # 0.381, compressed at the working load
WORKING_DEFLECTION = 0.015 * MM_PER_IN  # 0.381
WORKING_LOAD_N = 3.0 * N_PER_LBF  # 13.34
# [INFERENCE: linear] The page gives one load point, no rate.
RATE_N_PER_MM = WORKING_LOAD_N / WORKING_DEFLECTION  # 35.02
# The set gap between the thrust washer and the south ear: one 0.60 blade
# (rocker_bank_layout.ROCKER_SPRING_SET).  Load there 5.7 N,
# (FREE_HEIGHT - INSTALLED_HEIGHT) x RATE [INFERENCE: linear].
INSTALLED_HEIGHT = 0.60
# The model shows the installed state.
MODEL_HEIGHT = INSTALLED_HEIGHT
# Nominal radial clearance a side on the O6.35 pivot shaft.
SHAFT_CLEARANCE_NOMINAL = (ID - 0.25 * MM_PER_IN) / 2.0  # 0.1905

if not math.isclose(FREE_HEIGHT - WORKING_DEFLECTION, WORKING_HEIGHT):
    raise AssertionError("9714K24 free height, deflection and working height disagree")
if not THICKNESS < WORKING_HEIGHT <= MODEL_HEIGHT < FREE_HEIGHT:
    raise AssertionError("9714K24 modelled height is outside the working range")


def spring_load(height: float) -> float:
    """Axial load, N, squeezed to ``height`` [INFERENCE: linear rate]."""
    return (FREE_HEIGHT - height) * RATE_N_PER_MM


def spring_volume() -> float:
    """The modelled solid, mm^3: the installed envelope annulus."""
    return math.pi / 4.0 * (OD**2 - ID**2) * MODEL_HEIGHT
