r"""MHA-CH-VN-54 rocker-bank-spring: McMaster 9714K24 stock wave disc spring.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One wave disc spring sits on the MHA-CH-05 pivot shaft between the
south MHA-CH-VN-56 thrust washer on hub 0 and the south MHA-CH-08 ear's inner
face, where the 0.45 end-play leaf used to be (#948 ruling R, PR #1292).
Squeezed to INSTALLED_HEIGHT there, it holds the 20-hub stack north through the
north washer on the DRO-set north ear, so the bank has no end play; the set
screws hold the shaft (``rocker_bank_layout``).

Catalogue (mcmaster.com/9714K24, read live 2026-10-09): Wave Disc Spring,
high-carbon steel, stackable; ID 0.265 in -0.02/+0.01, OD 0.367 in
-0.02/+0.01, thickness 0.006 in, height 0.03 in (free); compressed height
0.015 in and deflection 0.015 in at the 3 lb working load; pack of 25,
$16.31. The page states no rate, no wave count and no shaft size. Read-only
source inspection recorded 2026-10-19 establishes nominal dimension datums,
not a physical free-stock recipe. The installed envelope remains unchanged.

The OD at its catalogue maximum stays under the rocker hub's O10.2, so the
ch0 amplitude bar's foot passes over the spring as it does over the hubs.
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

# Supplier drawing spelling; catalogue-only compressed sizes are not drawing content.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260115/21A4CCD6/"
    "9714K24_Wave%20Disc%20SpringX.GIF"
)
SUPPLIER_DRAWING_UNITS = "in"
# Read-only source provenance; no vendor asset is downloaded or loaded by the build.
SUPPLIER_NATIVE_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260115/0671B8A7/"
    "9714K24_Wave%20Disc%20Spring.SLDPRT"
)
SUPPLIER_NATIVE_SHA256 = "24e8c9b1408cbf980b55c97458546e8b4e16c2ebe3618e984f1f1c83d55dc0cf"
SUPPLIER_DRAWING_PRECISION = {
    "ID": 3, "OD": 3, "FREE_HEIGHT": 2, "THICKNESS": 3,
}
SUPPLIER_APPLICATION_DIMENSIONS = ()

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
