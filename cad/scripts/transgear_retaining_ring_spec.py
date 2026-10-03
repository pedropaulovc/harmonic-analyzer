r"""McMaster 97431A260 dimensions in mm, no CAD imports (MHA-182, R9-68).

The transgear retaining ring: a side-mount (E-style) external retaining ring
for a 5/32 in shaft, phosphate-coated carbon steel, Rockwell C47 minimum,
170 lbf thrust (McMaster 97431A260 product page, user-pasted live,
2026-10-02).  It is pushed sideways into the MHA-179 pin's groove in front of
the MHA-181 front bushing and closes the disc cluster's float.

Catalogue: groove Ø0.116 in 0/+0.002, groove width 0.029 in 0/+0.003, ring
O.D. 0.282 in, thickness 0.025 in ±0.002.

Laws: the vendor model ``cad/references/mcmaster/97431A260.SLDPRT``
(user-supplied; harvested on amet 2026-10-02 by ``diag_dump_part``).  Its
named driving dimensions agree with the catalogue: "Ring OD@Sketch1"
7.1628, "Free Diameter@Sketch1" 2.8956 (the gap across the three prongs
before the ring is pushed on, under the groove so it grips), "Ring
Thickness@Sketch4" 0.635.  Vendor truth: volume 13.3124 mm^3, area
64.1486 mm^2, 26 faces.

Pure data: the pin's groove, the fit module and the assembly read these;
``diag_build_97431A260`` replicates the vendor body.

Part frame (``build_transgear_retaining_ring``): the ring's axis is +Z, its
rear face on the Front plane (z = 0) and its front face at z = THICKNESS;
the open side (the gap that is pushed over the groove) faces +X, and the
prongs' gripping circle Ø FREE_DIA is centred on the axis.  The replica
recipe builds it about +Y at mid-thickness; the part rotates it up.
"""

from __future__ import annotations

MM_PER_IN = 25.4

SKU = "97431A260"
SHAFT_DIA = 5.0 / 32.0 * MM_PER_IN  # 3.969, the catalogue's shaft size

# --- groove (the pin's sheet prints these as its groove) ----------------------
GROOVE_DIA = 0.116 * MM_PER_IN  # 2.9464
GROOVE_DIA_BAND = (0.002 * MM_PER_IN, 0.0)  # (upper, lower)
GROOVE_WIDTH = 0.029 * MM_PER_IN  # 0.7366
GROOVE_WIDTH_BAND = (0.003 * MM_PER_IN, 0.0)  # (upper, lower)

# --- ring --------------------------------------------------------------------
OD = 0.282 * MM_PER_IN  # 7.1628
FREE_DIA = 0.114 * MM_PER_IN  # 2.8956, "Free Diameter@Sketch1"
THICKNESS = 0.025 * MM_PER_IN  # 0.635
THICKNESS_TOL = 0.002 * MM_PER_IN  # ±0.0508
THRUST_LBF = 170
HARDNESS_HRC_MIN = 47

# Axial play of the ring in its groove: 0.102 nominal, 0.051 .. 0.229.
GROOVE_PLAY = (
    round(GROOVE_WIDTH - (THICKNESS + THICKNESS_TOL), 6),
    round(GROOVE_WIDTH + GROOVE_WIDTH_BAND[0] - (THICKNESS - THICKNESS_TOL), 6),
)

if not FREE_DIA < GROOVE_DIA < SHAFT_DIA:
    raise AssertionError(
        "97431A260 must grip its groove and the groove sit under the shaft"
    )
if GROOVE_PLAY[0] <= 0.0:
    raise AssertionError(f"97431A260 binds in its groove: {GROOVE_PLAY}")
