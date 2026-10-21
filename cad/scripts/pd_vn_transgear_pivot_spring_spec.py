r"""MHA-PD-VN-63 transgear-pivot-spring: McMaster 9715K43 stock curved disc spring.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One curved disc spring sits on the MHA-PD-VN-57 pivot shoulder screw's
shoulder, between the underside of its head and the floor of the MHA-PD-18
transgear arm's spot face; squeezed there, it preloads the arm forward onto
the MHA-PD-20 pivot spacer.

Catalogue (mcmaster.com/9715K43, read live 2026-10-02): Curved Disc Springs,
for 0.190 in shaft diameter; ID 0.200 in, OD 0.423 in, thickness 0.0113 in,
height 0.047 in (free); compressed height 0.027 in and deflection 0.020 in at
the 9 lb working load; high-carbon steel; disc spring type "Curved"; pack of
10, $10.11.  The page states no flat load and no rate, says the spring has
"only two contact points" and that these springs cannot be stacked to raise
the working load. Read-only source inspection recorded 2026-10-19 establishes
nominal dimension datums, not a physical free-stock recipe.

Part frame: spring axis local +Z.  The model shows the spring as installed
at the nominal room under the screw head: the OD rim's bearing face (on the
arm's spot-face floor) is at z = 0 and the ID rim's top (under the screw
head) at z = MODEL_HEIGHT, between the catalogue working height and the free
height.  [INFERENCE: the page's two contact points describe a bowed washer;
the model is the axisymmetric cone spanning the same ID, OD and thickness at
that height (``diag_build_9715K43``).]
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4
N_PER_LBF = 4.4482216

SKU = "9715K43"
COUNT = 1

ID = 0.200 * MM_PER_IN  # 5.08
OD = 0.423 * MM_PER_IN  # 10.7442
THICKNESS = 0.0113 * MM_PER_IN  # 0.28702
FREE_HEIGHT = 0.047 * MM_PER_IN  # 1.1938
WORKING_HEIGHT = 0.027 * MM_PER_IN  # 0.6858, compressed at the working load
WORKING_DEFLECTION = 0.020 * MM_PER_IN  # 0.508
WORKING_LOAD_N = 9.0 * N_PER_LBF  # 40.03
# [INFERENCE: linear] The page gives one load point, no rate.
RATE_N_PER_MM = WORKING_LOAD_N / WORKING_DEFLECTION  # 78.81
# The installed height at the nominal room under the MHA-PD-VN-57 head (room
# 0.70..0.9508, inside the catalogue deflection);
# transgear_hanger_joints.SPRING_ROOM_NOMINAL asserts it.  Load there 31.0 N,
# (FREE_HEIGHT - INSTALLED_HEIGHT) x RATE [INFERENCE: linear].
INSTALLED_HEIGHT = 0.80
# The model shows the installed state.
MODEL_HEIGHT = INSTALLED_HEIGHT

# The inspected drawing prints .011, but native strip thickness remains .0113 in.
SHAFT_DIA = 0.190 * MM_PER_IN
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260115/90C63C6C/"
    "9715K43_Curved%20Disc%20SpringsX.GIF"
)
SUPPLIER_DRAWING_UNITS = "in"
# Read-only source provenance; no vendor asset is downloaded or loaded by the build.
SUPPLIER_NATIVE_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260115/0FAE8731/"
    "9715K43_Curved%20Disc%20Springs.SLDPRT"
)
SUPPLIER_NATIVE_SHA256 = "30ffa536a8a0b2531d8f1711fddbd8089ed58caee40448ff34addd8d4a9f8822"
SUPPLIER_DRAWING_PRECISION = {
    "ID": 1, "OD": 3, "FREE_HEIGHT": 3, "THICKNESS": 3,
    "WORKING_HEIGHT": 3, "SHAFT_DIA": 2,
}
SUPPLIER_APPLICATION_DIMENSIONS = ("WORKING_HEIGHT", "SHAFT_DIA")

if not math.isclose(FREE_HEIGHT - WORKING_DEFLECTION, WORKING_HEIGHT):
    raise AssertionError("9715K43 free height, deflection and working height disagree")
if not THICKNESS < WORKING_HEIGHT <= MODEL_HEIGHT < FREE_HEIGHT:
    raise AssertionError("9715K43 modelled height is outside the working range")


def spring_volume() -> float:
    """The modelled solid, mm^3.  Pappus: the cone section's parallelogram,
    area THICKNESS x (OD - ID) / 2, swept round its centroid radius
    (ID + OD) / 4 -- the same as a flat washer of the spring's thickness."""
    return math.pi / 4.0 * (OD**2 - ID**2) * THICKNESS
