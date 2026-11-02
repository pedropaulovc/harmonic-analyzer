r"""Pure-data envelope of the purchased KP08 pillow block (MHA-CH-06-TL-VN-56).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_vn_oblique_pillow_block`` extrudes the section
below and the jig assembly mates its ``ScrewAxis`` and foot.

The item is an AMPEC KP08 bought from Bearings Direct (two off, the near and
far blocks of the oblique-trammel jig's leadscrew feed): a mini zinc-alloy
pillow block round a set-screw-locking insert ball bearing, 8 mm bore. Each
stands on a TL-28 end bracket; its inner-ring set screws grip the Tr8
screw's plain thread.

datasheet-built: no vendor CAD obtained (AMPEC publishes none: the Bearings
Direct listing and its AMPEC brand page carry no CAD/STEP/PDF/DWG link,
checked 2026-10-17 UTC). Other makers' KP08 models and drawings exist; none is
AMPEC's and none of their values is used here.

Evidence (read 2026-10-17 UTC):

- Bearings Direct, AMPEC KP08,
  https://bearingsdirect.com/8mm-bore-kp08-mini-zinc-pillow-set-screw-block-bearing-kp8uu/ :
  inner diameter 8 mm, overall height 29 mm, overall length 55 mm, bolt hole
  to bolt hole 42 mm, base to centre 15 mm, zinc-alloy housing, SAE 52100
  chrome-steel bearing, two set screws 120 degrees apart on the inner ring.
  No axial width, foot thickness, bolt-hole diameter or set-screw size.
- The listing's six photographs are the series' stock photographs (the
  housing is cast "P005" and the insert "K005", the 25 mm-bore size), so they
  show the KP shape only: a round boss concentric with the bore whose sides
  run straight down to a two-hole foot, no grease fitting, and the insert's
  inner ring standing proud of the housing face on its set-screw side.

Source of each number:

- SOURCED (the listing above), FROM C4 (imported from
  ``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``, never retyped):
  ``AXIS_HEIGHT`` 15, ``BOLT_SPACING`` 42, ``LENGTH`` 55, ``HEIGHT`` 29,
  ``BORE_DIA`` 8.
- UNVERIFIED, FROM C4 (verify on receipt): ``WIDTH`` 13, the axial width;
  ``HOLE_DIA`` 4.5, the smallest hole the M4 screw passes; ``FOOT_THICK`` 5.
- DERIVED (shape ESTIMATED from the series photographs): the boss is round
  and concentric with the bore, its crown the overall height, so
  ``BOSS_RADIUS`` = ``HEIGHT`` - ``AXIS_HEIGHT``; its sides drop straight to
  the foot, so the pedestal under it is ``2 * BOSS_RADIUS`` wide.
- No other dimension is introduced.

Envelope (Main ruling): the axial width is unpublished, so the block is ONE
conservative solid of the full ``WIDTH``, symmetric about its axial
mid-plane: housing, foot and the insert's outer and inner rings together.
The photographed inner ring stands proud of the housing face on its set-screw
side; whether 13 also bounds that ring, and the housing's own width, are
verify-on-receipt items, as are the bolt-hole diameter and the foot
thickness.

Omitted, each documented: the two inner-ring set screws and their tapped
holes (AMPEC publishes no size; another maker's is not transferred), the
foot's cored underside pockets, the casting fillets and the seal/ring steps:
the envelope is solid.

Part frame: the origin is on the foot's bottom face, on the bore axis's
vertical plane and the block's axial mid-plane. +Z is up (the bore axis at
z = ``AXIS_HEIGHT``), +Y runs along the bore axis and X across it (the bolt
holes at x = +/- ``BOLT_SPACING`` / 2). Front Plane = the foot's bottom face,
Top Plane = the axial mid-plane, Right Plane = the vertical plane through the
axis. The bore axis is published as ``ScrewAxis``.

Volume (closed form): the section is the foot (``LENGTH`` x ``FOOT_THICK``),
the pedestal above it (``2 * BOSS_RADIUS`` x ``AXIS_HEIGHT - FOOT_THICK``)
and the boss's upper half disc (radius ``BOSS_RADIUS``), less the bore; it is
extruded ``WIDTH``; the two bolt holes each remove a ``HOLE_DIA`` cylinder
``FOOT_THICK`` long.

Material: the native envelope takes "Plain Carbon Steel" (SOLIDWORKS library)
as a stand-in for the zinc-alloy housing round its 52100 insert; the jig uses
no mass from it.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew

SUPPLIER = "Bearings Direct (AMPEC)"
SKU = "KP08"
SOURCE_URL = "https://bearingsdirect.com/8mm-bore-kp08-mini-zinc-pillow-set-screw-block-bearing-kp8uu/"
MATERIAL = "Plain Carbon Steel"  # library stand-in: zinc-alloy housing, 52100 insert
QUANTITY = len(leadscrew.KP08_S)  # the near and far blocks

# --- From C4 (leadscrew_spec's bought-items block) ---------------------------------
AXIS_HEIGHT = leadscrew.KP08_AXIS_HEIGHT  # base to centre
BOLT_SPACING = leadscrew.KP08_BOLT_SPACING  # bolt hole to bolt hole
LENGTH = leadscrew.KP08_LENGTH  # overall, across the axis
HEIGHT = leadscrew.KP08_HEIGHT  # overall
BORE_DIA = leadscrew.KP08_BORE
WIDTH = leadscrew.KP08_WIDTH  # UNVERIFIED: the whole envelope's axial width
HOLE_DIA = leadscrew.KP08_HOLE_DIA  # UNVERIFIED
FOOT_THICK = leadscrew.KP08_FOOT_THICK  # UNVERIFIED

# --- Derived shape (series photographs) --------------------------------------------
BOSS_RADIUS = HEIGHT - AXIS_HEIGHT  # round boss on the bore axis, crown at HEIGHT
HOLE_X = (-BOLT_SPACING / 2.0, BOLT_SPACING / 2.0)

# Foot and pedestal outline in the axis-normal section, (x, z), counter-clockwise
# from the foot's bottom-left corner; the boss disc sits on the pedestal's top.
BASE_OUTLINE: tuple[tuple[float, float], ...] = (
    (-LENGTH / 2.0, 0.0),
    (LENGTH / 2.0, 0.0),
    (LENGTH / 2.0, FOOT_THICK),
    (BOSS_RADIUS, FOOT_THICK),
    (BOSS_RADIUS, AXIS_HEIGHT),
    (-BOSS_RADIUS, AXIS_HEIGHT),
    (-BOSS_RADIUS, FOOT_THICK),
    (-LENGTH / 2.0, FOOT_THICK),
)

BASE_AREA = LENGTH * FOOT_THICK + 2.0 * BOSS_RADIUS * (AXIS_HEIGHT - FOOT_THICK)
BOSS_UPPER_AREA = (
    math.pi * BOSS_RADIUS**2 / 2.0
)  # the disc's lower half is in the pedestal
BORE_AREA = math.pi * (BORE_DIA / 2.0) ** 2
HOLE_VOLUME = math.pi * (HOLE_DIA / 2.0) ** 2 * FOOT_THICK
VOLUME_MM3 = WIDTH * (BASE_AREA + BOSS_UPPER_AREA - BORE_AREA) - 2.0 * HOLE_VOLUME

# The bolt holes are the interface: on receipt, the end bracket's screws must
# pass both holes into its taps (the pass condition; machinist review), the
# bracket named by drawing number.
DRAWING_NOTES = (
    f"ENVELOPE MODEL: {leadscrew.KP08_SCREW} SCREWS MUST PASS BOTH HOLES INTO"
    " MHA-CH-06-TL-28 TAPS."
)

# Reference sizes on the plan view (the Front Plane, sketch (u, v) = model
# (X, Y)): the listing's bolt-hole spacing and C4's bolt hole, the receipt
# check's interface. The chords lie on the bolt holes' centreline (y = 0,
# through both centre marks) and the -X hole's vertical centre-mark arm; laid
# along the foot's edges they printed as dashed residue over the outline
# (machinist review). The overall length would need a second chord on that
# same centreline or an edge, so it stays in the listing (no clean carrier).
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierBoltSpacing", BOLT_SPACING, "horizontal"),
    ("SupplierBoltHoleDiameter", HOLE_DIA, "vertical"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierBoltSpacing": (HOLE_X[0], 0.0),
    "SupplierBoltHoleDiameter": (HOLE_X[0], -HOLE_DIA / 2.0),
}
SUPPLIER_REFERENCE_PLANES: dict[str, str] = {}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierBoltSpacing": "top",
    "SupplierBoltHoleDiameter": "left",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierBoltSpacing": (0, "length", None, None),
    "SupplierBoltHoleDiameter": (1, "diameter", None, "2X"),
}
SUPPLIER_REFERENCE_UNITS = {
    name: "mm" for name, _, _ in SUPPLIER_REFERENCE_DIMENSIONS
}

# --- Import-time checks --------------------------------------------------------------
if not BOSS_RADIUS < LENGTH / 2.0:
    raise ValueError("KP08: the boss must be narrower than the foot")
if not AXIS_HEIGHT - BORE_DIA / 2.0 > FOOT_THICK:
    raise ValueError("KP08: the bore must clear the foot")
if not BOLT_SPACING / 2.0 - HOLE_DIA / 2.0 > BOSS_RADIUS:
    raise ValueError("KP08: the bolt holes must clear the pedestal")
if not BOLT_SPACING / 2.0 + HOLE_DIA / 2.0 < LENGTH / 2.0:
    raise ValueError("KP08: the bolt holes must lie inside the foot")
