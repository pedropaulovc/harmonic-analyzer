r"""McMaster 97431A240 dimensions in mm, no CAD imports (MHA-PD-VN-61, R9-68).

The transgear retaining ring: a side-mount (E-style) external retaining ring
for a 1/8 in shaft, phosphate-coated carbon steel, Rockwell C47 minimum,
60 lbf thrust (https://www.mcmaster.com/97431A240/, read live 2026-10-31).
It is pushed sideways into the MHA-PD-23 pin's groove in front of the
MHA-PD-25 front bushing and closes the disc cluster's float.  #290 (owner
ruling 2026-10-30): the pin went from 3.9 mm to 1/8 in, so the 5/32 shaft
97431A260 gave way to this ring.

Catalogue: groove Ø0.095 in 0/+0.002, groove width 0.020 in 0/+0.002, ring
O.D. 0.230 in, thickness 0.015 in ±0.002.  The vendor's 2-D drawing on the
same page (97431A240 X.GIF) gives the free diameter across the three prongs,
0.094 in.  The CAD download is refused (HTTP 403), so the ring is
catalogue-only: ``diag_build_97431A240`` draws it on the 97431A260 harvest's
outline law, which that drawing matches.

Pure data: the pin's groove, the fit module and the assembly read these.

Part frame (``build_pd_vn_transgear_retaining_ring``): the ring's axis is +Z, its
rear face on the Front plane (z = 0) and its front face at z = THICKNESS;
the open side (the gap that is pushed over the groove) faces +X, and the
prongs' gripping circle Ø FREE_DIA is centred on the axis.  The recipe
builds it about +Y at mid-thickness; the part rotates it up.
"""

from __future__ import annotations

MM_PER_IN = 25.4

SKU = "97431A240"
SHAFT_DIA = 0.125 * MM_PER_IN  # 3.175, the catalogue's shaft size

# --- groove (the pin's sheet prints these as its groove) ----------------------
GROOVE_DIA = 0.095 * MM_PER_IN  # 2.413
GROOVE_DIA_BAND = (0.002 * MM_PER_IN, 0.0)  # (upper, lower)
GROOVE_WIDTH = 0.020 * MM_PER_IN  # 0.508
GROOVE_WIDTH_BAND = (0.002 * MM_PER_IN, 0.0)  # (upper, lower)

# --- ring --------------------------------------------------------------------
OD = 0.230 * MM_PER_IN  # 5.842
FREE_DIA = 0.094 * MM_PER_IN  # 2.3876, the vendor drawing's prong gap
THICKNESS = 0.015 * MM_PER_IN  # 0.381
THICKNESS_TOL = 0.002 * MM_PER_IN  # ±0.0508
THRUST_LBF = 60
HARDNESS_HRC_MIN = 47

# Axial play of the ring in its groove: 0.127 nominal, 0.0762 .. 0.2286.
GROOVE_PLAY = (
    round(GROOVE_WIDTH - (THICKNESS + THICKNESS_TOL), 6),
    round(GROOVE_WIDTH + GROOVE_WIDTH_BAND[0] - (THICKNESS - THICKNESS_TOL), 6),
)

if not FREE_DIA < GROOVE_DIA < SHAFT_DIA:
    raise AssertionError(
        "97431A240 must grip its groove and the groove sit under the shaft"
    )
if GROOVE_PLAY[0] <= 0.0:
    raise AssertionError(f"97431A240 binds in its groove: {GROOVE_PLAY}")
