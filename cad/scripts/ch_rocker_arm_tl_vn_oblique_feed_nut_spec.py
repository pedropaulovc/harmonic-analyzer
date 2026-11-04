r"""Pure-data envelope of the bought Tr8x2 brass flange nut, as fitted (MHA-CH-06-TL-VN-82).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_vn_oblique_feed_nut`` revolves ``PROFILE``,
cuts the flange holes and revolve-cuts the countersinks from here.

Owner ruling 2026-11-04 (#2177, option B): the brass flange nut supplied with
the ReliaBot lead screw (MHA-CH-06-TL-VN-54, Amazon B085DDHJTW) drives
TL-32's integral lug. It replaces the shop-made MHA-CH-06-TL-27 nut and its
MHA-CH-06-TL-VN-81 dowel, both retired and never reissued. At TL-00 fit-up
(step F1) the fitter faces the nut's 1.5 spigot off in one lathe pass, so
the flange seats flat on the lug's -X face with no recess, and countersinks
the four flange holes 82° for four #4-40 X 5/8 flat heads
(MHA-CH-06-TL-VN-67, McMaster 91771A112; owner ruling relayed by Main
2026-11-04: a screw the repo already uses). The lug's four taps are
transferred through the seated nut. The model is the nut as fitted.

Datasheet-built: no vendor CAD obtained. Sources:

- SOURCED, the listing (https://www.amazon.com/dp/B085DDHJTW, read
  2026-11-04): "Brass nut, with 4 holes for fixing to the machine"; "Screw
  pitch: 2mm; Number of Thread/Start:1; Lead: 2mm"; material "brass". Its
  dimension image (31zvVr4yFvL) gives the flange Ø22 x 3.5, 4-Ø3.5 holes on
  a Ø16 PCD, the body Ø10.2 x 10 and a Ø10.2 x 1.5 spigot on the flange's
  other side, 15 overall. The listing states no tolerance, brass alloy,
  thread class or hand, edge chamfer or hole angular position.
- CONTRACT (the bought-parts convention): the Tr8x2 internal thread is a
  plain bore at the thread's minor diameter, Ø6.0
  (``leadscrew_stock.MINOR_DIA``). The screw enters it as a plain Ø8
  cylinder, so the assembly carries a volume-bounded thread-engagement
  contract.
- FIT-UP (this jig's work, not the vendor's): the spigot faced off, so
  ``LENGTH`` is 13.5 as fitted, and four 82° countersinks Ø``CSK_DIA``
  ±``CSK_DIA_BAND`` cut with an 82° countersink no larger than
  ``CSK_CUTTER_DIA_MAX`` (Ø3/16). A Ø1/4 cutter's cone would reach the
  Ø10.2 body about 0.6 above the flange face and gouge it.
- RECEIPT ACCEPTANCE (UNVERIFIED until the nut is measured in F1, before the
  lug's taps are transferred): the ``*_MIN`` / ``*_MAX`` limits below. Each
  is the bound a check in this jig reads: the flange thickness (the screws'
  engagement and seat), the body diameter (the heads' clearance, TL-32's
  spec), the hole size (the transfer spot's residual), the hole PCD (the lug
  walls) and the faced length (the near-KP08 feed gap). F2 calipers
  each nut screw's head against ``SCREW_HEAD_DIA_MAX``.

Part frame. The axis is +Y and is published as ``ScrewAxis`` (Front ∩
Right). y = 0 is the faced seat face (on the lug); the flange spans
y 0 .. FLANGE_THICK and the body FLANGE_THICK .. LENGTH. The holes sit at
azimuths 0°, 90°, 180° and 270° about +Y, measured from +X toward +Z, at
(x, z) = (PCD/2 cos a, PCD/2 sin a), so each hole's axis lies on the Front or
Right plane, where its countersink is revolved. The jig turns the nut 45°
about its axis, so the holes sit at 45° to the lug's faces (the owner's
option-B sketch). The pattern is symmetric about X and Z, so the round
flange needs no angular datum.
"""

from __future__ import annotations

import math
from fractions import Fraction

import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec as leadscrew_stock
from _hole_spec import THREAD_MAJOR_MM
from _mcmaster_91771a112 import DIMS as SCREW_DIMS
from _mcmaster_91771a112 import LENGTH_TEXT as SCREW_LENGTH_TEXT
from _mcmaster_91771a112 import PART_NO as SCREW_SKU
from _mcmaster_91771a112 import THREAD as SCREW_THREAD

INCH = 25.4
PART_NAME = "ch-rocker-arm-tl-vn-oblique-feed-nut"
NUMBER = "MHA-CH-06-TL-VN-82"
SUPPLIER = leadscrew_stock.SUPPLIER  # Amazon (sold by ReliaBot)
SKU = leadscrew_stock.SKU  # the nut ships with the screw; not bought apart
SUPPLIER_PRODUCT_URL = leadscrew_stock.SUPPLIER_PRODUCT_URL
SUPPLIER_DRAWING_IMAGE = "31zvVr4yFvL"  # the listing's dimension image
QUANTITY = 1
MATERIAL = "Brass"
LEAD = leadscrew_stock.LEAD  # 2, single start

# --- SOURCED: the listing's dimension image -----------------------------------
FLANGE_DIA = 22.0
FLANGE_THICK = 3.5
HOLE_DIA = 3.5
HOLE_PCD = 16.0
HOLE_ANGLES_DEG = (0.0, 90.0, 180.0, 270.0)
BODY_DIA = 10.2
BODY_LENGTH = 10.0
SPIGOT_LENGTH = 1.5  # faced off at fit-up
SUPPLIED_LENGTH = 15.0
if abs(SPIGOT_LENGTH + FLANGE_THICK + BODY_LENGTH - SUPPLIED_LENGTH) > 1e-9:
    raise AssertionError("the spigot, flange and body do not make the image's 15")

# --- CONTRACT: the thread as a plain minor-diameter bore -----------------------
BORE_DIA = leadscrew_stock.MINOR_DIA  # 6.0

# --- FIT-UP: the spigot faced off ----------------------------------------------
LENGTH = FLANGE_THICK + BODY_LENGTH  # 13.5, seat face to body end
# Five Tr8 turns at least, as the retired TL-27 was sized (ruling A1).
if LENGTH < 5.0 * LEAD:
    raise AssertionError("the fitted nut is shorter than five Tr8 turns")

# --- RECEIPT ACCEPTANCE: UNVERIFIED nominals, measured in F1 ------------------
FLANGE_DIA_MAX = 22.2
FLANGE_THICK_MIN = 3.3
FLANGE_THICK_MAX = 3.7
BODY_DIA_MAX = 10.3
HOLE_DIA_MIN = 3.46  # a #29 transfer drill (Ø3.454) still enters
HOLE_DIA_MAX = 3.60
HOLE_PCD_BAND = 0.1  # ± on the diameter, so ±0.05 on each hole's station
LENGTH_MAX = 13.8  # faced, seat face to body end
HOLE_R_MAX = HOLE_DIA_MAX / 2.0
HOLE_STATION_BAND = HOLE_PCD_BAND / 2.0
# F1 prints the limits in the nut's own millimetres (owner ruling 4, 2026-11-01).
RECEIPT_TEXT = (
    f"FLANGE {FLANGE_THICK_MIN:.1f}-{FLANGE_THICK_MAX:.1f} MM THICK, BODY "
    f"Ø{BODY_DIA_MAX:.1f} MM MAX, {len(HOLE_ANGLES_DEG)} HOLES "
    f"Ø{HOLE_DIA_MIN:.2f}-{HOLE_DIA_MAX:.2f} MM ON A Ø{HOLE_PCD:.0f} "
    f"±{HOLE_PCD_BAND:.1f} MM PCD, FACED LENGTH {LENGTH_MAX:.1f} MM MAX"
)

# --- FIT-UP: the 82° countersinks for the four TL-VN-67 flat heads ------------
SCREW_COUNT = len(HOLE_ANGLES_DEG)
SCREW_MAJOR = THREAD_MAJOR_MM[SCREW_THREAD]
CSK_ANGLE = SCREW_DIMS.head_angle_deg  # 82, the head's
CSK_DIA = 4.6
CSK_DIA_BAND = 0.1
CSK_DIA_MIN = CSK_DIA - CSK_DIA_BAND
# The cutter: no larger than Ø3/16, so its cone stays off the body. F2's
# remedy for a nut that binds opens the countersinks (Main, 2026-11-04), never
# past this cutter's full diameter.
CSK_CUTTER_TEXT = "3/16"
CSK_CUTTER_DIA_MAX = float(Fraction(CSK_CUTTER_TEXT)) * INCH  # 4.7625
CSK_DIA_OPEN_MAX = CSK_CUTTER_DIA_MAX
# ASSUMPTION: each countersink runs on its hole's axis to within 0.02 (an 82°
# countersink centred in the drilled hole); TL-32's head-to-body stack-up
# charges it.
CSK_ECCENTRICITY_MAX = 0.02
# Owner ruling 2026-11-04 (#2177 option 3, relayed by Main): F2 calipers each
# nut screw's head and rejects one over the catalogue Ø.212, since B18.6.3's
# sharp-edge Ø.225 maximum reaches the nut body (TL-32 spec, HEAD_TO_BODY_*).
# Oversize heads stop the fit-up for a report; the nut body is never cut.
SCREW_HEAD_DIA_MAX = SCREW_DIMS.head_dia  # 5.3848, .212
_TAN = math.tan(math.radians(CSK_ANGLE / 2.0))
CSK_DEPTH = (CSK_DIA - HOLE_DIA) / (2.0 * _TAN)  # below the head face, nominal
CSK_CUTTER_TO_BODY = (
    HOLE_PCD / 2.0 - HOLE_STATION_BAND - CSK_ECCENTRICITY_MAX
    - CSK_CUTTER_DIA_MAX / 2.0 - BODY_DIA_MAX / 2.0
)  # 0.40
if CSK_CUTTER_TO_BODY <= 0.0:
    raise AssertionError("the countersink cutter reaches the nut body")
# The flat head stands proud of every mouth: its top Ø (the catalogue .212)
# exceeds the largest mouth, so the cone seats and the head top never meets
# the countersink's rim.
HEAD_PROUD_NOMINAL = (SCREW_DIMS.head_dia - CSK_DIA) / (2.0 * _TAN)  # 0.45
HEAD_PROUD_MAX = (SCREW_DIMS.head_dia - CSK_DIA_MIN) / (2.0 * _TAN)  # 0.51
HEAD_PROUD_MIN = (SCREW_DIMS.head_dia - CSK_DIA_OPEN_MAX) / (2.0 * _TAN)  # 0.36
if HEAD_PROUD_MIN <= 0.0:
    raise AssertionError("a flat head sinks past an opened countersink's mouth")
if CSK_DEPTH >= FLANGE_THICK_MIN:
    raise AssertionError("the countersink runs through the thinnest flange")
# The head's cone bears on the countersink from the screw's underhead
# transition to the least mouth. ASSUMPTION: the B18.6.3 underhead fillet
# bound of its other heads (Ø.1456, D + 0.3D), which exceeds the largest hole.
SCREW_FILLET_DIA_MAX = 1.3 * 0.112 * INCH
CSK_BEARING_INNER_DIA = max(HOLE_DIA_MAX, SCREW_FILLET_DIA_MAX)
CSK_BEARING_AREA_MIN = math.pi / 4.0 * (CSK_DIA_MIN**2 - CSK_BEARING_INNER_DIA**2)
if CSK_BEARING_AREA_MIN <= 0.0:
    raise AssertionError("the least countersink leaves the head no cone to bear on")

# --- The screws: 4 X #4-40 X 5/8 FLAT HEAD through the nut into the lug --------
# McMaster's flat head length is overall, from the head top. The grip is the
# head top to the lug face: the flange plus the head's stand-proud.
SCREW_LENGTH = SCREW_DIMS.length  # 15.875
SCREW_LENGTH_MIN = SCREW_LENGTH - 0.03 * INCH  # ASME B18.6.3, to 1 in
SCREW_POINT_MAX = 2.0 * SCREW_DIMS.pitch  # ASME B18.6.3's 2P maximum point
SCREW_GRIP = FLANGE_THICK + HEAD_PROUD_NOMINAL  # nominal
SCREW_ENGAGEMENT = SCREW_LENGTH - SCREW_GRIP  # 11.92 nominal, into the lug
# Rule 18 at the worst case: the shortest screw, the thickest flange, the
# head at its most proud, less the lug tap's mouth break and the point.
SCREW_FULL_THREAD_MIN = (
    SCREW_LENGTH_MIN
    - (FLANGE_THICK_MAX + HEAD_PROUD_MAX)
    - leadscrew.TAP_MOUTH_BREAK
    - SCREW_POINT_MAX
)  # 9.4, 3.3 D
if SCREW_FULL_THREAD_MIN < leadscrew.ENGAGEMENT_TARGET_D * SCREW_MAJOR:
    raise AssertionError("the feed nut screws engage the lug under 2 D")
# The longest reach past the lug face: the thinnest flange, the head least proud.
SCREW_TIP_REACH_MAX = SCREW_LENGTH - FLANGE_THICK_MIN - HEAD_PROUD_MIN  # 12.2
# The nut's reach toward the near KP08 from the lug face: the body end. The
# heads stand at most HEAD_PROUD_MAX above the flange, well short of it.
REACH = LENGTH_MAX
if FLANGE_THICK_MAX + HEAD_PROUD_MAX >= LENGTH:
    raise AssertionError("a screw head stands past the nut body's end")

# --- Self-checks on the envelope -------------------------------------------------
_BODY_R_MAX = BODY_DIA_MAX / 2.0
if not HOLE_PCD / 2.0 - HOLE_STATION_BAND - HOLE_R_MAX > _BODY_R_MAX:
    raise AssertionError("a flange hole breaks into the body")
_CSK_SHIFT = HOLE_STATION_BAND + CSK_ECCENTRICITY_MAX
if not HOLE_PCD / 2.0 + _CSK_SHIFT + CSK_DIA_OPEN_MAX / 2.0 < FLANGE_DIA / 2.0:
    raise AssertionError("a countersink breaks out of the flange rim")
if not HOLE_PCD / 2.0 - _CSK_SHIFT - CSK_DIA_OPEN_MAX / 2.0 > _BODY_R_MAX:
    raise AssertionError("a countersink breaks into the body")
if not BORE_DIA < BODY_DIA:
    raise AssertionError("the bore is wider than the body")

# --- Model --------------------------------------------------------------------------
_BORE_R = BORE_DIA / 2.0
_BODY_R = BODY_DIA / 2.0
_FLANGE_R = FLANGE_DIA / 2.0

# (radius, y), revolved 360° about the axis, round the bore.
PROFILE: tuple[tuple[float, float], ...] = (
    (_BORE_R, 0.0),
    (_FLANGE_R, 0.0),
    (_FLANGE_R, FLANGE_THICK),
    (_BODY_R, FLANGE_THICK),
    (_BODY_R, LENGTH),
    (_BORE_R, LENGTH),
)
# Flange-hole centres in model (x, z).
HOLE_CENTRES: tuple[tuple[float, float], ...] = tuple(
    (
        round(HOLE_PCD / 2.0 * math.cos(math.radians(a)), 9) + 0.0,
        round(HOLE_PCD / 2.0 * math.sin(math.radians(a)), 9) + 0.0,
    )
    for a in HOLE_ANGLES_DEG
)
# Each countersink is a triangle revolved about its hole's axis, on the plane
# that holds that axis: on Front, sketch u = model x; on Right, u = -model z;
# v = model y on both. Its top edge stands CSK_OVERRUN above the head face so
# the cut leaves no sliver there; that overrun cone still clears the body.
CSK_OVERRUN = 0.25
CSK_TOP_Y = FLANGE_THICK + CSK_OVERRUN
CSK_APEX_Y = FLANGE_THICK - CSK_DIA / 2.0 / _TAN
_CSK_TOP_R = CSK_DIA / 2.0 + CSK_OVERRUN * _TAN
if not HOLE_PCD / 2.0 - _CSK_TOP_R > _BODY_R:
    raise AssertionError("the countersink's overrun cone reaches the modelled body")
# (plane, sketch u of the hole axis), one per hole: Front's x = +8 and -8,
# Right's u = -z for z = +8 and -8.
COUNTERSINK_AXES: tuple[tuple[str, float], ...] = (
    ("Front", HOLE_PCD / 2.0),
    ("Front", -HOLE_PCD / 2.0),
    ("Right", -HOLE_PCD / 2.0),
    ("Right", HOLE_PCD / 2.0),
)


def countersink_points(u: float) -> list[tuple[float, float]]:
    """The countersink triangle for the hole axis at sketch ``u``: the axis
    top, the outer top corner (away from the nut axis) and the apex. The
    closing edge, apex to axis top, lies on the hole axis: the revolve axis."""
    side = 1.0 if u > 0.0 else -1.0
    return [(u, CSK_TOP_Y), (u + side * _CSK_TOP_R, CSK_TOP_Y), (u, CSK_APEX_Y)]


def revolved_volume(profile: tuple[tuple[float, float], ...]) -> float:
    """Volume (mm^3) of a closed (radius, y) polygon revolved about r = 0 (Pappus)."""
    area_moment = 0.0
    for (r1, y1), (r2, y2) in zip(profile, profile[1:] + profile[:1], strict=True):
        area_moment += (r1 + r2) * (r1 * y2 - r2 * y1)
    return abs(2.0 * math.pi * area_moment / 6.0)


def countersink_volume(mouth_dia: float, hole_dia: float) -> float:
    """Brass one 82° countersink removes round its hole: the cone from the
    hole's edge up to the mouth, less the hole it surrounds."""
    r_m, r_h = mouth_dia / 2.0, hole_dia / 2.0
    return math.pi / (3.0 * _TAN) * (r_m**3 - r_h**3) - math.pi * r_h**2 * (r_m - r_h) / _TAN


BODY_VOLUME_MM3 = revolved_volume(PROFILE)
HOLE_VOLUME_MM3 = math.pi * (HOLE_DIA / 2.0) ** 2 * FLANGE_THICK
CSK_VOLUME_MM3 = countersink_volume(CSK_DIA, HOLE_DIA)
VOLUME_MM3 = BODY_VOLUME_MM3 - SCREW_COUNT * (HOLE_VOLUME_MM3 + CSK_VOLUME_MM3)

# The sheet's footer note: the fit-up work on the bought nut, one line that
# fits the purchased footer row (_NOTE_X to _FOOTER_RIGHT in
# _purchased_fastener_drawing). The general line says the part is cut at
# assembly per this note.
DRAWING_NOTES = (
    f"FACE ITS SPIGOT OFF AND COUNTERSINK ITS {SCREW_COUNT} HOLES PER "
    "MHA-CH-06-TL-00 STEP F1."
)

# --- Supplier reference sizes (the dimension image's, mm) ---------------------------
# The sheet is 1:1 in the purchased layout's ``tall_top`` cells (Front
# 180 x 73 mm, Top, the end view, 180 x 96 mm), the retired TL-VN-55 sheet's
# lane budget for the same nut: Front carries only the two vertical lengths
# (the flange on its silhouette, the body on the axis), and every diameter is
# read on the end view: the flange OD above it, the body's below, the hole
# and the bolt pattern to the sides. Hidden construction chords print where
# an edge or a centreline already is, never across a face.
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierBodyLength", BODY_LENGTH, "vertical"),
    ("SupplierFlangeThickness", FLANGE_THICK, "vertical"),
    ("SupplierFlangeDiameter", FLANGE_DIA, "horizontal"),
    ("SupplierBodyDiameter", BODY_DIA, "horizontal"),
    ("SupplierMountingHoleDiameter", HOLE_DIA, "vertical"),
    ("SupplierHolePitchDiameter", HOLE_PCD, "vertical"),
)
# The Top sketch reads model (x, -z): the +X hole's chord crosses it; the
# PCD's runs on the end view's vertical centreline through the ±Z holes.
SUPPLIER_REFERENCE_STARTS = {
    "SupplierBodyLength": (0.0, FLANGE_THICK),
    "SupplierFlangeThickness": (-FLANGE_DIA / 2.0, 0.0),
    "SupplierFlangeDiameter": (-FLANGE_DIA / 2.0, 0.0),
    "SupplierBodyDiameter": (-BODY_DIA / 2.0, 0.0),
    "SupplierMountingHoleDiameter": (HOLE_CENTRES[0][0], -HOLE_DIA / 2.0),
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
    "SupplierBodyLength": (0, "length", None, None),
    "SupplierFlangeThickness": (1, "length", None, None),
    "SupplierFlangeDiameter": (0, "diameter", None, None),
    "SupplierBodyDiameter": (1, "diameter", None, None),
    "SupplierMountingHoleDiameter": (1, "diameter", None, "4X"),
    "SupplierHolePitchDiameter": (0, "diameter", None, "PCD"),
}
SUPPLIER_REFERENCE_UNITS = {
    name: "mm" for name, _, _ in SUPPLIER_REFERENCE_DIMENSIONS
}
