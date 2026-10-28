r"""Pure-data envelope of the bought Tr8x2 brass flange nut, ZYLtech (MHA-CH-06-TL-VN-55).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_vn_oblique_leadscrew_nut`` revolves ``PROFILE``
and cuts the flange holes from here.

The item is the shop-inventory ``fixtures.trammel-tr8-flange-nut``: the
regular brass T8x2 flange nut that ships with the ZYLtech HW-SC-T8x2-600
screw (standalone replacement SKU HW-SC-T8x2-NUT). It has a round flange with
four plain holes and a body that runs through it: a short spigot on one side,
the long body on the other. Four #4-40 screws fix it to the integral lug
of feed block TL-32, with the spigot in TL-32's counterbore.

Datasheet-built: no vendor CAD obtained (ZYLtech publishes no STEP, IGES, STL
or drawing download, checked 2026-10-17 UTC; see
``C:/src/dt-logs/trammel-bought/vendor-cad/HW-SC-T8x2-600.provenance.md``).

Sources:

- FROM C4 (imported from ``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``, never
  retyped): the flange (Ø22 x 3.5), the 4 x Ø3.5 holes on PCD 16 at 45°, 135°,
  225° and 315°, the body Ø10.2, and the axial split, a 1.5 spigot plus the
  3.5 flange plus a 10 body for 15 overall.
- SOURCED, ZYLtech's product-197 drawings, read 2026-10-16 (inventory cites;
  copies in ``C:/src/dt-logs/trammel-leadscrew/zyltech/``, ``kit197-nut-front.webp``
  and ``kit197-nut-side.webp``): the front view gives Ø22, Ø10.2, Ø16 and
  4-Ø3.5, and the side view gives 1.5, 3.5 and 10. They agree with C4.
- FROM the bought-parts contract: the nut's internal Tr8x2 thread is modelled
  as a plain bore at the thread MINOR diameter, Ø6.0. It is not in
  ``_hole_spec.TAP_DRILL_MM``. The screw enters it as a plain Ø8 cylinder, so
  the assembly carries a volume-bounded thread-engagement contract.
- CROSS-REFERENCE ONLY (the superseded Ooznest LSRFN-TR8-2-2P-B vendor STEP):
  its thread crest bore is Ø6.6 (``OOZNEST_CREST_DIA``), with 1 x 45° entry
  countersinks and 0.25 x 45° edge chamfers. Not modelled.
- UNVERIFIED (verify on receipt): edge chamfers and thread-entry countersinks
  (ZYLtech gives none), backlash, and the bore's real crest diameter.

Part frame. The axis is +Y and is published as ``ScrewAxis`` (Front ∩ Right).
y = 0 is the flange's bracket-side face, the one the spigot stands from, so
the spigot spans y -1.5 .. 0, the flange y 0 .. 3.5 and the long body
y 3.5 .. 13.5 (toward +Y). The flange holes sit at azimuth a about +Y,
measured from +X toward +Z, at (x, z) = (PCD/2 cos a, PCD/2 sin a). The set is
symmetric about both X and Z, so the round flange needs no angular datum.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as feed

SUPPLIER = "ZYLtech Engineering"
SKU = "HW-SC-T8x2-NUT"
KIT_SKU = "HW-SC-T8x2-600"  # the nut ships with this screw; not bought apart
INVENTORY_ID = feed.NUT_ID  # fixtures.trammel-tr8-flange-nut
QUANTITY = 1
MATERIAL = "Brass"

# --- FROM C4 (imported) ---------------------------------------------------------
FLANGE_DIA = feed.NUT_FLANGE_DIA  # 22
FLANGE_THICK = feed.NUT_FLANGE_THICK  # 3.5
HOLE_DIA = feed.NUT_HOLE_DIA  # 3.5, plain
HOLE_PCD = feed.NUT_HOLE_PCD  # 16
HOLE_ANGLES_DEG = feed.NUT_HOLE_ANGLES_DEG  # 45, 135, 225, 315
BODY_DIA = feed.NUT_BODY_DIA  # 10.2
LENGTH = feed.NUT_LENGTH  # 15
SPIGOT_LENGTH = feed.NUT_BODY_SHORT  # 1.5, into TL-32's counterbore
BODY_LONG = feed.NUT_BODY_LONG  # 10
LEAD = feed.SCREW_LEAD  # 2, single start

# --- SOURCED: contract / cross-reference ------------------------------------------
BORE_DIA = 6.0  # Tr8x2 thread minor (contract), as a plain bore
OOZNEST_CREST_DIA = 6.6  # cross-reference only: the superseded nut's crest bore


_BORE_R = BORE_DIA / 2.0
_BODY_R = BODY_DIA / 2.0
_FLANGE_R = FLANGE_DIA / 2.0
FAR_END_Y = FLANGE_THICK + BODY_LONG  # 13.5

# (radius, y), revolved 360° about the axis, round the bore.
PROFILE: tuple[tuple[float, float], ...] = (
    (_BORE_R, -SPIGOT_LENGTH),
    (_BODY_R, -SPIGOT_LENGTH),
    (_BODY_R, 0.0),
    (_FLANGE_R, 0.0),
    (_FLANGE_R, FLANGE_THICK),
    (_BODY_R, FLANGE_THICK),
    (_BODY_R, FAR_END_Y),
    (_BORE_R, FAR_END_Y),
)
# Flange-hole centres in model (x, z).
HOLE_CENTRES: tuple[tuple[float, float], ...] = tuple(
    (
        round(HOLE_PCD / 2.0 * math.cos(math.radians(a)), 9),
        round(HOLE_PCD / 2.0 * math.sin(math.radians(a)), 9),
    )
    for a in HOLE_ANGLES_DEG
)
# Exact current replacement identity was selected on the primary supplier's
# T8x2 variant on 2026-10-21. Its mixed-size gallery also contains unrelated
# R12 / inch-size nut drawings; those are not this nut's engineering evidence.
# The current T8x2 screw-kit page's dedicated front/side drawings supply these
# nominal sizes and agree with the unchanged installed envelope above.
SUPPLIER_PRODUCT_URL = (
    "https://www.zyltech.com/"
    "zyltech-brass-nut-only-various-diameters-and-pitches-available/"
)
SUPPLIER_KIT_URL = (
    "https://www.zyltech.com/"
    "8mm-t8x2-trapezoidal-acme-lead-screw-w-brass-nut-pre-cut-lengths-150mm-2000mm/"
)
SUPPLIER_DRAWING_URLS = (
    "https://cdn11.bigcommerce.com/s-eblil3q2nd/images/stencil/500x659/"
    "products/197/16129/"
    "s136714152818872222_p75_i6_w500__21913__97391.1698349316.jpg?c=2",
    "https://cdn11.bigcommerce.com/s-eblil3q2nd/images/stencil/500x659/"
    "products/197/16130/"
    "s136714152818872222_p75_i5_w1005__99935__02876.1698349316.jpg?c=2",
)
# Construction-only source chords are nominal size references, not measurements
# of the omitted internal thread. No source bore diameter or tolerance is given.
# Only what a drop-in substitute must match: the flange OD, the pilot (spigot)
# diameter TL-32's counterbore takes, the overall length (1.5 + 3.5 + 10),
# the flange thickness (the #4-40 screws' grip) and the bolt pattern.
# The sheet is 1:1 in the purchased layout's ``tall_top`` cells: Front
# 180 x 73 mm, Top (the end view) 180 x 96 mm. Every annotated view reserves
# 20 mm a side plus 6 mm for a lane, and the native outline is the model
# extent plus 11.176 mm. Each view is centred in its cell less these
# reserves, so Front must reserve the same above and below (Right's row) and
# left and right (Top's column), or it leaves third-angle projection. A
# horizontal Front size would need 26 mm both above and below: 73 - 52 = 21 <
# 26.176. So Front carries only the two vertical lengths (20 + 20 + 26.176 <=
# 73, lanes 26 left and right) and every diameter is read on the end view:
# the flange OD above it, the pilot (the long body's Ø10.2, the spigot's too)
# below, the bolt pattern to the sides (26 + 26 + 33.176 <= 96).
# The overall length runs on the axis; the two end-view diameters run along
# its horizontal centreline. Hidden construction chords print where an edge
# or a centreline already is, never across a face.
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", LENGTH, "vertical"),
    ("SupplierFlangeThickness", FLANGE_THICK, "vertical"),
    ("SupplierFlangeDiameter", FLANGE_DIA, "horizontal"),
    ("SupplierBodyDiameter", BODY_DIA, "horizontal"),
    ("SupplierMountingHoleDiameter", HOLE_DIA, "vertical"),
    ("SupplierHolePitchDiameter", HOLE_PCD, "vertical"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (0.0, -SPIGOT_LENGTH),
    "SupplierFlangeThickness": (-FLANGE_DIA / 2.0, 0.0),
    "SupplierFlangeDiameter": (-FLANGE_DIA / 2.0, 0.0),
    "SupplierBodyDiameter": (-BODY_DIA / 2.0, 0.0),
    "SupplierMountingHoleDiameter": (
        HOLE_CENTRES[0][0],
        -HOLE_CENTRES[0][1] - HOLE_DIA / 2.0,
    ),
    "SupplierHolePitchDiameter": (0.0, -HOLE_PCD / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierFlangeDiameter": "Top",
    "SupplierBodyDiameter": "Top",
    "SupplierMountingHoleDiameter": "Top",
    "SupplierHolePitchDiameter": "Top",
}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierFlangeDiameter": "top",
    "SupplierBodyDiameter": "bottom",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (0, "length", None, None),
    "SupplierFlangeThickness": (1, "length", None, None),
    "SupplierFlangeDiameter": (0, "diameter", None, None),
    "SupplierBodyDiameter": (1, "diameter", None, None),
    "SupplierMountingHoleDiameter": (1, "diameter", None, "4X"),
    "SupplierHolePitchDiameter": (0, "diameter", None, "PCD"),
}
SUPPLIER_REFERENCE_UNITS = {
    name: "mm" for name, _, _ in SUPPLIER_REFERENCE_DIMENSIONS
}


def revolved_volume(profile: tuple[tuple[float, float], ...]) -> float:
    """Volume (mm^3) of a closed (radius, y) polygon revolved about r = 0 (Pappus)."""
    area_moment = 0.0
    for (r1, y1), (r2, y2) in zip(profile, profile[1:] + profile[:1], strict=True):
        area_moment += (r1 + r2) * (r1 * y2 - r2 * y1)
    return abs(2.0 * math.pi * area_moment / 6.0)


BODY_VOLUME_MM3 = revolved_volume(PROFILE)
HOLE_VOLUME_MM3 = math.pi * (HOLE_DIA / 2.0) ** 2 * FLANGE_THICK
VOLUME_MM3 = BODY_VOLUME_MM3 - len(HOLE_ANGLES_DEG) * HOLE_VOLUME_MM3

DRAWING_NOTES = (
    "SPIGOT INTO THE NUT BRACKET'S COUNTERBORE; SCREW THE FLANGE TO THE BRACKET."
)

# --- Self-checks ----------------------------------------------------------------
if abs(SPIGOT_LENGTH + FLANGE_THICK + BODY_LONG - LENGTH) > 1e-9:
    raise AssertionError("the spigot, flange and body do not make C4's nut length")
if not HOLE_PCD / 2.0 - HOLE_DIA / 2.0 > _BODY_R:
    raise AssertionError("a flange hole breaks into the body")
if not HOLE_PCD / 2.0 + HOLE_DIA / 2.0 < _FLANGE_R:
    raise AssertionError("a flange hole breaks out of the flange rim")
if not _BORE_R < _BODY_R:
    raise AssertionError("the bore is wider than the body")
