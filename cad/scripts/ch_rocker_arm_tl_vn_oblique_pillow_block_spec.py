r"""Pure-data envelope of the purchased KP08 pillow block (MHA-CH-06-TL-VN-56).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_vn_oblique_pillow_block`` extrudes the section
below and the jig assembly mates its ``ScrewAxis`` and foot.

The item is a uxcell KP08 from a 6-pack bought on Amazon (two used, the near
and far blocks of the oblique-trammel jig's leadscrew feed): a mini pillow
block round an insert ball bearing, 8 mm bore. Each stands on a TL-28 end
bracket; its inner-ring set screws grip the Tr8 screw's set-screw flats.

datasheet-built: no vendor CAD obtained (the listing offers no CAD
download, checked 2026-11-04).

Evidence (read 2026-11-04):

- uxcell, https://www.amazon.com/dp/B0D2L8M4QR : "uxcell 6 Pcs KP08 Pillow
  Block Bearing 8mm Bore Zinc Alloy Inner Ball Mounted Bearing Block Insert
  Bearing Self-Alignment"; "Overall Size: 55 x 13 x 28mm (L*W*H)"; "Holes
  Centre Distance: 42mm"; "Width of Bearing: 12mm"; "Installation Hole
  Diameter: 5mm"; "Bore Diameter: 8mm"; Model KP08. The title says zinc
  alloy; the description says "Bearing housings are made of cast iron while
  bearings are made of zinc alloy". The two contradict each other and both
  are recorded, unverified. No centre (axis) height, foot thickness or
  set-screw size or count.
- The listing's photographs and dimension image show the KP shape: a round
  boss concentric with the bore whose sides run straight down to a two-hole
  foot (cast "P08"), no grease fitting, and the insert's inner ring standing
  proud of the housing face, one set-screw hole visible in it.

Source of each number:

- SOURCED (the listing above), FROM C4 (imported from
  ``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``, never retyped):
  ``LENGTH`` 55, ``WIDTH`` 13 (the overall W: the whole envelope's axial
  width; the bearing's own 12 sits inside it), ``HEIGHT`` 28,
  ``BOLT_SPACING`` 42, ``HOLE_DIA`` 5, ``BORE_DIA`` 8.
- UNVERIFIED, FROM C4 (verify on receipt): ``AXIS_HEIGHT`` 15, the KP08
  series' base-to-centre height (check: the bore axis stands 15 over the
  foot's bottom face, measured with an Ø8 pin in the bore; the leadscrew
  axis height is set by it), and ``FOOT_THICK`` 5 (check: the foot under the
  bolt holes is .196 to .292 thick: no thicker, so the #8-32 x 5/8 screw's
  worst-case full thread in TL-28 holds rule 18's 1.5 D,
  ``end_bracket.KP08_FOOT_THICK_MAX``; no thinner, so its tip stays clear of
  the bar screw's tip in TL-28's shared THRU thread,
  ``end_bracket.KP08_FOOT_THICK_MIN`` and ``SCREW_TIP_GAP_MIN``).
- DERIVED (shape ESTIMATED from the photographs): the boss is round and
  concentric with the bore, its crown the overall height, so
  ``BOSS_RADIUS`` = ``HEIGHT`` - ``AXIS_HEIGHT``; its sides drop straight to
  the foot, so the pedestal under it is ``2 * BOSS_RADIUS`` wide.
- No other dimension is introduced.

Envelope (Main ruling): one conservative solid of the full ``WIDTH``,
symmetric about its axial mid-plane: housing, foot and the insert's outer
and inner rings together. Whether the 13 overall also bounds the
photographed inner ring where it stands proud is a verify-on-receipt item.

Fit of the TL-28 screws (oblique simplification PR2, owner ruling Main
2026-11-06 option B): the listing's Ø5 holes at 42 centres float a #8-32
(major 4.166, 0.417 radial clearance), on the same 42 as TL-28's two
holes, each tapped from its top face for these screws.

Omitted, each documented: the inner-ring set screws and their tapped holes
(size and count unpublished), the foot's hex recesses round the bolt holes,
the casting fillets and the seal/ring steps: the envelope is solid.

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
as a stand-in for the zinc-alloy or cast-iron housing round its insert; the
jig uses no mass from it.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew

SUPPLIER = "Amazon (sold by uxcell)"
SKU = "B0D2L8M4QR"  # the 6-pack's ASIN
SOURCE_URL = "https://www.amazon.com/dp/B0D2L8M4QR"
MATERIAL = "Plain Carbon Steel"  # library stand-in: zinc-alloy or cast-iron housing
QUANTITY = len(leadscrew.KP08_S)  # the near and far blocks

# --- From C4 (leadscrew_spec's bought-items block) ---------------------------------
AXIS_HEIGHT = leadscrew.KP08_AXIS_HEIGHT  # base to centre, UNVERIFIED
BOLT_SPACING = leadscrew.KP08_BOLT_SPACING  # "Holes Centre Distance: 42mm"
LENGTH = leadscrew.KP08_LENGTH  # overall, across the axis
HEIGHT = leadscrew.KP08_HEIGHT  # overall
BORE_DIA = leadscrew.KP08_BORE
WIDTH = leadscrew.KP08_WIDTH  # the whole envelope's axial width
HOLE_DIA = leadscrew.KP08_HOLE_DIA  # "Installation Hole Diameter: 5mm"
FOOT_THICK = leadscrew.KP08_FOOT_THICK  # UNVERIFIED

# --- Derived shape (listing photographs) -------------------------------------------
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
# screws and the bracket named by drawing number, in plain shop words (no
# CAD term such as "envelope model": rule 26). The screws' number is the
# registry's (pinned by the drawing test; a spec stays pure data).
BRACKET_SCREW_NUMBER = "MHA-CH-06-TL-VN-62"
DRAWING_NOTES = (
    f"2X HOLES PASS {BRACKET_SCREW_NUMBER} SCREWS INTO"
    f" {leadscrew.END_BRACKET_NUMBER} TAPS."
)

# Reference sizes on the plan view (the Front Plane, sketch (u, v) = model
# (X, Y)): the listing's bolt-hole spacing and bolt hole, the receipt
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
# The TL-28 screw floats in the listing's hole.
if not HOLE_DIA > leadscrew.THREAD_MAJOR_MM[leadscrew.KP08_SCREW]:
    raise ValueError("KP08: the TL-28 screw does not pass the bolt hole")
