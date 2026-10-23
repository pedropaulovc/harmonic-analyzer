r"""MHA-DT-VN-68 cylinder-bank-spring: McMaster 9714K392 stock wave disc spring.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure. One wave disc spring sits on the MHA-DT-13 arbor directly between
gear 19's north planar face and the north MHA-DT-02 strap's inner face
(user ruling 2026-10-20). Squeezed to INSTALLED_HEIGHT there, it holds the
20-gear stack south on the brass MHA-DT-26 disc and the DRO-set south strap,
so the bank has no end play (``cylinder_bank_layout``).

Catalogue (mcmaster.com/9714K392, read live 2026-10-09): Wave Disc Spring,
steel, stackable; ID 0.385 in -0.01/+0.01, OD 0.5 in -0.01/+0.01, thickness
0.005 in, height 0.05 in (free); compressed height 0.024 in and deflection
0.026 in at the 1.5 lb working load; pack of 10, $11.18.  The page states no
rate and no wave count. Read-only source inspection recorded 2026-10-19
establishes nominal dimension datums, not a physical free-stock recipe.
The zero-solid ``SUPPLIER_REFERENCE`` diagram never changes this installed envelope.

Part frame: spring axis local +Z.  The model is the spring's installed
envelope: the ID x OD annulus from its south bearing face (on gear 19)
at z = 0 to its north bearing face (on the north strap) at
z = MODEL_HEIGHT, the nominal set gap. [INFERENCE: the waves are not
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
# The set gap between gear 19's north face and the north strap: one 0.95 blade
# (cylinder_bank_layout.BANK_SPRING_SET). Load there 3.2 N,
# (FREE_HEIGHT - INSTALLED_HEIGHT) x RATE [INFERENCE: linear].
INSTALLED_HEIGHT = 0.95
# The model shows the installed state.
MODEL_HEIGHT = INSTALLED_HEIGHT

# Exact source values above remain independent of their supplier inch spelling.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260323/3100F2B3/"
    "9714K392_Wave%20Disc%20SpringX.GIF"
)
SUPPLIER_DRAWING_UNITS = "in"
# Read-only source provenance; no vendor asset is downloaded or loaded by the build.
SUPPLIER_NATIVE_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260323/2E7D4C94/"
    "9714K392_Wave%20Disc%20Spring.SLDPRT"
)
SUPPLIER_NATIVE_SHA256 = "5597d77be331b24286107f0337bbabe25477a35d8255f1c67f2791f74572508e"
SUPPLIER_DRAWING_PRECISION = {
    "ID": 3, "OD": 3, "FREE_HEIGHT": 3, "THICKNESS": 3,
    "WORKING_HEIGHT": 3, "WORKING_DEFLECTION": 3,
}
SUPPLIER_APPLICATION_DIMENSIONS = ("WORKING_HEIGHT", "WORKING_DEFLECTION")

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
