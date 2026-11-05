r"""FeedNut member of the ReliaBot T8 kit: the brass flange nut, as fitted (MHA-CH-06-TL-VN-84).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_vn_oblique_leadscrew_kit`` revolves
``PROFILE``, cuts the flange holes and revolve-cuts the countersinks from here,
in the kit's ``FeedNut`` configuration.

Owner ruling 2026-11-04 (#2177, option B): the brass flange nut supplied with
the ReliaBot lead screw (Amazon B085DDHJTW) drives TL-32's integral lug. It
replaces the shop-made MHA-CH-06-TL-27 nut and its MHA-CH-06-TL-VN-81 dowel,
both retired and never reissued. Owner ruling 2026-11-04 (#2187): the screw
and the nut are one native model, MHA-CH-06-TL-VN-84, with ``LeadScrew`` and
``FeedNut`` configurations; the nut's own TL-VN-82 was never released and
stays reserved. Before the TL-00 feed fit-up (step F1A) the nut's 1.5 spigot
is faced off, so the flange seats flat on the lug's -X face with no recess,
and the four flange holes are countersunk 82° for four
#4-40 X 5/8 flat heads (MHA-CH-06-TL-VN-67, McMaster 91771A112; owner ruling
relayed by Main 2026-11-04: a screw the repo already uses). The lug's four
taps are transferred through the seated nut. The model is the nut as fitted.

Codjiflo P2 on #2187 (and 4475311251): every limit the nut is made and
accepted to is a native model tolerance in the FeedNut configuration, printed
on the kit's REWORK sheet (``REWORK_SHEET_REFERENCE``). Section F-F carries
``REWORK_CONTROLS``: ``FlangeThick`` (LIMIT ``FLANGE_THICK_MIN`` /
``FLANGE_THICK_MAX``), ``CskDia`` (LIMIT ``CSK_DIA_MIN`` / ``CSK_DIA_MAX``)
and ``FacedLength`` (``LENGTH_MAX`` MAX); the end view carries
``RECEIPT_CONTROLS``: the flange OD, body, hole and PCD limits. Values no
feature dimension holds are the driving dimensions of hidden reference
sketches (``REFERENCE_SKETCHES``). The 82° is held by the driving apex depth
``CskApexDepth``, as on build_pd_transgear_arm_plate (an angular sketch
dimension there read the 139° supplement and flipped the cone, run
20261001T011714683Z). The angle prints in the countersink's callout under the
title block's angular band. TL-00 cites that sheet and types none of these
limits.

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
  ``LENGTH`` is 13.5 as fitted, and four 82° countersinks within
  ``CSK_DIA_MIN`` .. ``CSK_DIA_MAX``, cut with an 82° countersink no larger
  than ``CSK_CUTTER_DIA_MAX`` (Ø3/16, a method; the band's maximum is its
  full diameter, rounded down). A Ø1/4 cutter's cone would reach the Ø10.2
  body about 0.6 above the flange face and gouge it.
- RECEIPT ACCEPTANCE (UNVERIFIED until the nut is measured in F1A, before the
  lug's taps are transferred): the ``*_MIN`` / ``*_MAX`` limits below. Each
  is the bound a check in this jig reads: the flange OD (the lug face and the
  countersinks' OD wall), the flange thickness (the screws' engagement and
  seat), the body diameter (the heads' clearance, TL-32's spec), the hole size
  (the transfer spot's residual) and the hole PCD (the lug walls), measured as
  received; and the faced length (the near-KP08 feed gap), measured after the
  facing pass, since the supplied nut is 1.5 longer. F2 calipers each nut
  screw's head against ``SCREW_HEAD_DIA_MAX``.

Part frame. The axis is +Y and is the kit's shared ``ScrewAxis`` (Front ∩
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

import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_leadscrew_spec as leadscrew_stock
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
from _hole_spec import THREAD_MAJOR_MM
import _mcmaster_91771a112 as _nut_screw
from _mcmaster_91771a112 import DIMS as SCREW_DIMS
from _mcmaster_91771a112 import THREAD as SCREW_THREAD

SCREW_LENGTH_TEXT = _nut_screw.LENGTH_TEXT  # read by the fastener table
SCREW_SKU = _nut_screw.PART_NO  # read by the kit drawing's callout

INCH = 25.4
PART_NAME = leadscrew_stock.PART_NAME  # the kit's one native model
NUMBER = leadscrew_stock.NUMBER  # MHA-CH-06-TL-VN-84
CONFIGURATION = "FeedNut"
SUPPLIER = leadscrew_stock.SUPPLIER  # Amazon (sold by ReliaBot)
SKU = leadscrew_stock.SKU  # the nut ships with the screw; not bought apart
SUPPLIER_PRODUCT_URL = leadscrew_stock.SUPPLIER_PRODUCT_URL
SUPPLIER_DRAWING_IMAGE = "31zvVr4yFvL"  # the listing's dimension image
QUANTITY = 1
MATERIAL = "Brass"
# The member's native BOM description under the kit's one Number.
BOM_DESCRIPTION = "TR8X2 BRASS FLANGE NUT, SPIGOT FACED"
LEAD = leadscrew_stock.LEAD  # 2, single start
# The kit package: sheet 1 the members' reference views, sheet 2 the
# LeadScrew's cut and flats, sheet 3 this member's REWORK. TL-00 cites it.
REWORK_SHEET = 3
REWORK_SHEET_REFERENCE = f"{NUMBER} SHEET {REWORK_SHEET}"
# The member's Manufacturing Notes: where its rework is drawn, no method.
DRAWING_NOTES = f"FACE AND COUNTERSINK PER SHEET {REWORK_SHEET}."

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

# --- RECEIPT ACCEPTANCE: UNVERIFIED nominals, measured in F1A -----------------
# Every limit below is a native dimension of the FeedNut configuration
# (Codjiflo 4475311251 on #2187), printed on the REWORK sheet: the flange OD,
# body Ø, hole size and PCD on its end view (``RECEIPT_CONTROLS``), the flange
# thickness and the faced length in its section (``REWORK_CONTROLS``). TL-00's
# F1A cites the sheet and types none of them.
# The flange OD takes the listing's Ø22 at the ±0.2 its 3.5 thickness takes
# (FLANGE_THICK_MIN/MAX): the maximum keeps the flange within TL-32's lug
# face, the minimum bounds the countersinks' OD wall (CSK_WALL_TO_OD).
FLANGE_DIA_BAND = 0.2
FLANGE_DIA_MIN = round(FLANGE_DIA - FLANGE_DIA_BAND, 6)  # 21.8
FLANGE_DIA_MAX = round(FLANGE_DIA + FLANGE_DIA_BAND, 6)  # 22.2
FLANGE_THICK_MIN = 3.3
FLANGE_THICK_MAX = 3.7
BODY_DIA_MAX = 10.3
HOLE_DIA_MIN = 3.46  # a #29 transfer drill (Ø3.454) still enters
HOLE_DIA_MAX = 3.60
HOLE_PCD_BAND = 0.1  # ± on the diameter, so ±0.05 on each hole's station
LENGTH_MAX = 13.8  # faced, seat face to body end
HOLE_R_MAX = HOLE_DIA_MAX / 2.0
HOLE_STATION_BAND = HOLE_PCD_BAND / 2.0
if not SUPPLIED_LENGTH > LENGTH_MAX > LENGTH:
    raise AssertionError("the faced-length limit does not reject an unfaced nut")

# --- FIT-UP: the 82° countersinks for the four TL-VN-67 flat heads ------------
SCREW_COUNT = len(HOLE_ANGLES_DEG)
SCREW_MAJOR = THREAD_MAJOR_MM[SCREW_THREAD]
CSK_ANGLE = SCREW_DIMS.head_angle_deg  # 82, the head's
CSK_DIA = 4.6  # the modelled mouth, inside the band
CSK_DIA_PLACES = 2
# The cutter: no larger than Ø3/16, so its cone stays off the body
# (CSK_CUTTER_TO_BODY). The band's maximum is its full diameter rounded down
# to the band's places, so a conforming countersink is one that cutter can
# cut. F2's remedy for a nut that binds opens the countersinks within this
# band (Codjiflo 4475311242 on #2187), so every check below runs at its
# limits and F2 types none of them.
CSK_CUTTER_TEXT = "3/16"
CSK_CUTTER_DIA_MAX = float(Fraction(CSK_CUTTER_TEXT)) * INCH  # 4.7625
CSK_DIA_MIN = 4.50
CSK_DIA_MAX = math.floor(CSK_CUTTER_DIA_MAX * 10**CSK_DIA_PLACES) / 10**CSK_DIA_PLACES  # 4.76
if not CSK_DIA_MIN < CSK_DIA < CSK_DIA_MAX <= CSK_CUTTER_DIA_MAX:
    raise AssertionError("the countersink band is not inside the cutter's reach")
# ASSUMPTION: each countersink runs on its hole's axis to within 0.02 (an 82°
# countersink centred in the drilled hole); TL-32's head-to-body stack-up
# charges it.
CSK_ECCENTRICITY_MAX = 0.02
# Owner ruling 2026-11-04 (#2177 option 3, relayed by Main): F2 calipers each
# nut screw's head and rejects one over the catalogue Ø.212, since B18.6.3's
# sharp-edge Ø.225 maximum reaches the nut body (TL-32 spec, HEAD_TO_BODY_*).
# Oversize heads stop the fit-up for a report; the nut body is never cut.
SCREW_HEAD_DIA_MAX = SCREW_DIMS.head_dia  # 5.3848, .212
# SOURCED: ASME B18.6.3 #4 82° flat head, edge rounded or flat, Ø.212 max and
# Ø.191 min (RC Fastener's B18.6.3-2002 flat-head table, read 2026-11-04:
# https://www.rcfastener.com/documents/RC_Specs/Machine_Screw_Flat_Head_Dimensions.pdf).
# McMaster's .212 is that maximum; any head F2 accepts lies between them.
SCREW_HEAD_DIA_MIN = 0.191 * INCH  # 4.8514
if not SCREW_HEAD_DIA_MIN < SCREW_HEAD_DIA_MAX:
    raise AssertionError("the flat head's band is inverted")
_TAN = math.tan(math.radians(CSK_ANGLE / 2.0))
CSK_DEPTH = (CSK_DIA - HOLE_DIA) / (2.0 * _TAN)  # below the head face, nominal
CSK_CUTTER_TO_BODY = (
    HOLE_PCD / 2.0 - HOLE_STATION_BAND - CSK_ECCENTRICITY_MAX
    - CSK_CUTTER_DIA_MAX / 2.0 - BODY_DIA_MAX / 2.0
)  # 0.40
if CSK_CUTTER_TO_BODY <= 0.0:
    raise AssertionError("the countersink cutter reaches the nut body")
# The flat head stands proud of every mouth the band allows: its top Ø exceeds
# the largest mouth even at B18.6.3's least head, so the cone seats and the
# head top never meets the countersink's rim. Most proud: the largest head in
# the least mouth; least proud: the least head in the largest mouth (at the
# catalogue head, HEAD_PROUD_AT_MOUTH_MAX).
HEAD_PROUD_NOMINAL = (SCREW_DIMS.head_dia - CSK_DIA) / (2.0 * _TAN)  # 0.45
HEAD_PROUD_MAX = (SCREW_HEAD_DIA_MAX - CSK_DIA_MIN) / (2.0 * _TAN)  # 0.51
HEAD_PROUD_AT_MOUTH_MAX = (SCREW_HEAD_DIA_MAX - CSK_DIA_MAX) / (2.0 * _TAN)  # 0.36
HEAD_PROUD_MIN = (SCREW_HEAD_DIA_MIN - CSK_DIA_MAX) / (2.0 * _TAN)  # 0.05
if HEAD_PROUD_MIN <= 0.0:
    raise AssertionError("a flat head sinks past the largest countersink's mouth")
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
SCREW_TIP_REACH_MAX = SCREW_LENGTH - FLANGE_THICK_MIN - HEAD_PROUD_MIN  # 12.5
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
if not HOLE_PCD / 2.0 + _CSK_SHIFT + CSK_DIA_MAX / 2.0 < FLANGE_DIA_MIN / 2.0:
    raise AssertionError("a countersink breaks out of the flange rim")
if not HOLE_PCD / 2.0 - _CSK_SHIFT - CSK_DIA_MAX / 2.0 > _BODY_R_MAX:
    raise AssertionError("a countersink breaks into the body")
if not BORE_DIA < BODY_DIA:
    raise AssertionError("the bore is wider than the body")

# --- The countersinks' walls: a stated rule-17 shortfall ----------------------
# Ruling relayed by Main 2026-11-04, option A (auto-selected after an owner
# timeout; the kit's machinist_exceptions RV-01, provisional): the Ø4.6
# countersinks stay. A printed MIN covers everything the package allows: each
# hole ±HOLE_STATION_BAND off its station on the Ø16 PCD (receipt), its
# countersink CSK_ECCENTRICITY_MAX off the hole, the mouth at the band's
# Ø4.76 maximum (CSK_DIA_MAX, where F2's opening stops), the body at its
# receipt Ø10.3 maximum and the flange at its receipt Ø21.8 minimum
# (FLANGE_DIA_MIN). Both are under the metric packages' 1.5 floor
# (drawing-guidelines rule 17). The supplied Ø3.5 holes alone already leave
# less than the floor, nominal and at the receipt limits, so no countersink on
# this bought nut meets it. CskDia's callout prints both countersink walls,
# rounded down.
WALL_FLOOR = 1.5
CSK_WALL_TO_BODY = HOLE_PCD / 2.0 - _CSK_SHIFT - CSK_DIA_MAX / 2.0 - _BODY_R_MAX  # 0.40
CSK_WALL_TO_OD = FLANGE_DIA_MIN / 2.0 - HOLE_PCD / 2.0 - _CSK_SHIFT - CSK_DIA_MAX / 2.0  # 0.45
HOLE_WALL_TO_BODY = HOLE_PCD / 2.0 - HOLE_DIA / 2.0 - BODY_DIA / 2.0  # 1.15, nominal
HOLE_WALL_TO_OD = FLANGE_DIA / 2.0 - HOLE_PCD / 2.0 - HOLE_DIA / 2.0  # 1.25, nominal
HOLE_WALL_TO_BODY_MIN = HOLE_PCD / 2.0 - HOLE_STATION_BAND - HOLE_R_MAX - _BODY_R_MAX  # 1.00
HOLE_WALL_TO_OD_MIN = FLANGE_DIA_MIN / 2.0 - HOLE_PCD / 2.0 - HOLE_STATION_BAND - HOLE_R_MAX  # 1.05
if not 0.0 < CSK_WALL_TO_BODY < CSK_WALL_TO_OD < WALL_FLOOR:
    raise AssertionError("the countersink walls are not the stated shortfall")
if not max(HOLE_WALL_TO_BODY, HOLE_WALL_TO_OD) < WALL_FLOOR:
    raise AssertionError("a supplied hole meets the wall floor; revisit RV-01")
if not (HOLE_WALL_TO_BODY_MIN < HOLE_WALL_TO_BODY and HOLE_WALL_TO_OD_MIN < HOLE_WALL_TO_OD):
    raise AssertionError("the receipt limits do not thin the supplied holes' walls")


def _wall_text(wall: float) -> str:
    """A wall in mm at two places, rounded down: a MIN never overstates."""
    return f"{math.floor(wall * 100.0 + 1e-9) / 100.0:.2f}"


CSK_WALL_TEXT = (
    f"MIN WALL {_wall_text(CSK_WALL_TO_BODY)} TO BODY, "
    f"{_wall_text(CSK_WALL_TO_OD)} TO OD"
)

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
# NutProfile's dimensions in creation order: the free revolve axis's length,
# then define_polygon_chain's for ``PROFILE`` anchored at its first vertex
# (the anchor's radius, then one per axis-parallel segment; the bore edge
# closing on the anchor is the closure's). The flange's rim edge, seat face to
# head face, is the REWORK sheet's FlangeThick.
NUT_PROFILE_DIMENSIONS = (
    "NutAxisLength",
    "BoreRadius",
    "SeatWidth",
    "FlangeThick",
    "HeadFaceWidth",
    "BodyLength",
    "BodyEndWidth",
)
# Flange-hole centres in model (x, z).
HOLE_CENTRES: tuple[tuple[float, float], ...] = tuple(
    (
        round(HOLE_PCD / 2.0 * math.cos(math.radians(a)), 9) + 0.0,
        round(HOLE_PCD / 2.0 * math.sin(math.radians(a)), 9) + 0.0,
    )
    for a in HOLE_ANGLES_DEG
)
# Each countersink is revolved about its hole's axis on the plane that holds
# it (build_pd_transgear_arm_plate's profile): the apex on the axis, the cone
# up to the mouth on the head face, a wall CSK_OVERRUN above the face so the
# cut leaves no sliver there, and back along the axis. On Front, sketch
# u = model x; on Right, u = -model z; v = model y on both. The overrun wall
# stands at the mouth's radius, clear of the body.
CSK_OVERRUN = 0.25
CSK_TOP_Y = FLANGE_THICK + CSK_OVERRUN
CSK_APEX_DEPTH = CSK_DIA / 2.0 / _TAN  # below the head face: fixes the 82°
CSK_APEX_Y = FLANGE_THICK - CSK_APEX_DEPTH
if not HOLE_PCD / 2.0 - CSK_DIA / 2.0 > _BODY_R:
    raise AssertionError("the countersink's overrun wall reaches the modelled body")
# (plane, sketch u of the hole axis), one per hole: Front's x = +8 and -8,
# Right's u = -z for z = +8 and -8. Countersink 1 (+X, on Front) carries the
# printed controls; section A-A on the REWORK sheet cuts Front through it.
COUNTERSINK_AXES: tuple[tuple[str, float], ...] = (
    ("Front", HOLE_PCD / 2.0),
    ("Front", -HOLE_PCD / 2.0),
    ("Right", -HOLE_PCD / 2.0),
    ("Right", HOLE_PCD / 2.0),
)


def countersink_points(u: float) -> list[tuple[float, float]]:
    """The countersink profile for the hole axis at sketch ``u``: the apex,
    the mouth on the head face, the overrun wall's top and the axis top. The
    closing edge, axis top to apex, lies on the hole axis: the revolve axis."""
    side = 1.0 if u > 0.0 else -1.0
    mouth = u + side * CSK_DIA / 2.0
    return [
        (u, CSK_APEX_Y),
        (mouth, FLANGE_THICK),
        (mouth, CSK_TOP_Y),
        (u, CSK_TOP_Y),
    ]


def countersink_dimensions(index: int) -> tuple[str, ...]:
    """A countersink sketch's dimensions in creation order. Countersink 1's
    diameter and apex depth carry the printed names; the others are the same
    sizes, numbered."""
    printed = index == 1
    return (
        f"Csk{index}AxisLength",
        f"Csk{index}Station",
        f"Csk{index}Seat",
        "CskDia" if printed else f"Csk{index}Dia",
        "CskApexDepth" if printed else f"Csk{index}ApexDepth",
        f"Csk{index}Overrun",
    )


def revolved_volume(profile: tuple[tuple[float, float], ...]) -> float:
    """Volume (mm^3) of a closed (radius, y) polygon revolved about r = 0 (Pappus)."""
    area_moment = 0.0
    for (r1, y1), (r2, y2) in zip(profile, profile[1:] + profile[:1], strict=True):
        area_moment += (r1 + r2) * (r1 * y2 - r2 * y1)
    return abs(2.0 * math.pi * area_moment / 6.0)


def countersink_volume(mouth_dia: float, hole_dia: float) -> float:
    """Brass one 82° countersink removes round its hole: the cone from the
    hole's edge up to the mouth, less the hole it surrounds. Above the head
    face its overrun wall cuts only air."""
    r_m, r_h = mouth_dia / 2.0, hole_dia / 2.0
    return math.pi / (3.0 * _TAN) * (r_m**3 - r_h**3) - math.pi * r_h**2 * (r_m - r_h) / _TAN


BODY_VOLUME_MM3 = revolved_volume(PROFILE)
HOLE_VOLUME_MM3 = math.pi * (HOLE_DIA / 2.0) ** 2 * FLANGE_THICK
CSK_VOLUME_MM3 = countersink_volume(CSK_DIA, HOLE_DIA)
VOLUME_MM3 = BODY_VOLUME_MM3 - SCREW_COUNT * (HOLE_VOLUME_MM3 + CSK_VOLUME_MM3)

# --- Native controls in the FeedNut configuration only (Codjiflo P2) ------------
# name -> (nominal, lower deviation, upper deviation, places), mm. A LIMIT
# prints its two limits; a MAX prints its nominal, which IS the limit, then
# MAX (``_single_limit_tolerance``), the deviation below it the model's record
# of the modelled size; a symmetric band prints ±. Each prints at its band's
# places. The 82° prints in CskDia's callout under the title block's angular
# band; CskApexDepth drives it and does not print.
TOL_LIMIT = 3  # swTolType_e.swTolLIMIT
TOL_SYMMETRIC = 4  # swTolType_e.swTolSYMMETRIC
TOL_MAX = 6  # swTolType_e.swTolMAX


def _deviation(value: float) -> float:
    return round(value, 6)


# REWORK, in section F-F: the flange after facing (3.7/3.3), the countersink
# mouth (4.76/4.50) and the faced length (13.8 MAX).
REWORK_CONTROLS = {
    "FlangeThick": (
        FLANGE_THICK,
        _deviation(FLANGE_THICK_MIN - FLANGE_THICK),
        _deviation(FLANGE_THICK_MAX - FLANGE_THICK),
        1,
    ),
    "CskDia": (
        CSK_DIA,
        _deviation(CSK_DIA_MIN - CSK_DIA),
        _deviation(CSK_DIA_MAX - CSK_DIA),
        CSK_DIA_PLACES,
    ),
    "FacedLength": (LENGTH_MAX, _deviation(LENGTH - LENGTH_MAX), 0.0, 1),
}
# RECEIPT, on the end view: the flange OD (22.2/21.8), the body (10.3 MAX),
# the holes (3.60/3.46) and their PCD (16.0 ±0.1), as F1A measures them.
RECEIPT_CONTROLS = {
    "ReceiptFlangeDia": (FLANGE_DIA, -FLANGE_DIA_BAND, FLANGE_DIA_BAND, 1),
    "ReceiptBodyDia": (BODY_DIA_MAX, _deviation(BODY_DIA - BODY_DIA_MAX), 0.0, 1),
    "ReceiptHoleDia": (
        HOLE_DIA, _deviation(HOLE_DIA_MIN - HOLE_DIA), _deviation(HOLE_DIA_MAX - HOLE_DIA), 2,
    ),
    "ReceiptHolePcd": (HOLE_PCD, -HOLE_PCD_BAND, HOLE_PCD_BAND, 1),
}
NATIVE_CONTROLS = {**REWORK_CONTROLS, **RECEIPT_CONTROLS}
DIMENSION_TOLERANCE_TYPES = {
    "FlangeThick": TOL_LIMIT,
    "CskDia": TOL_LIMIT,
    "FacedLength": TOL_MAX,
    "ReceiptFlangeDia": TOL_LIMIT,
    "ReceiptBodyDia": TOL_MAX,
    "ReceiptHoleDia": TOL_LIMIT,
    "ReceiptHolePcd": TOL_SYMMETRIC,
}
if set(DIMENSION_TOLERANCE_TYPES) != set(NATIVE_CONTROLS):
    raise AssertionError("a native control has no tolerance type")
for _name, (_nominal, _lower, _upper, _places) in NATIVE_CONTROLS.items():
    if DIMENSION_TOLERANCE_TYPES[_name] == TOL_MAX and _upper != 0.0:
        raise AssertionError(f"{_name}: a MAX's nominal is not its limit")

# --- The carriers no feature dimension holds: hidden reference sketches ---------
# The profile's dimensions are widths from the bore and the holes stand at
# stations from the axis, so neither the receipt diameters nor the faced
# length's limit is a feature dimension. Each is the driving dimension of its
# own hidden construction entity (drawing-simplicity-policy, model
# ownership); the entities' stations off the origin do not print.
# ``ReceiptReference`` on Top (sketch (x, -z), the end view's): the flange OD,
# the body at its maximum, the bolt circle and the +Z hole as construction
# circles, each driven by its diameter. The hole's centre stands
# ``ReceiptHoleStation`` off the origin, which does not print.
RECEIPT_SKETCH = "ReceiptReference"
# (diameter dimension, its value, centre in sketch (x, -z)), in creation order.
RECEIPT_CIRCLES = (
    ("ReceiptFlangeDia", FLANGE_DIA, (0.0, 0.0)),
    ("ReceiptBodyDia", BODY_DIA_MAX, (0.0, 0.0)),
    ("ReceiptHolePcd", HOLE_PCD, (0.0, 0.0)),
    ("ReceiptHoleDia", HOLE_DIA, (0.0, -HOLE_PCD / 2.0)),  # the +Z hole
)
RECEIPT_HOLE_STATION = "ReceiptHoleStation"
RECEIPT_DIMENSIONS = (
    "ReceiptFlangeDia",
    "ReceiptBodyDia",
    "ReceiptHolePcd",
    RECEIPT_HOLE_STATION,
    "ReceiptHoleDia",
)
if {name for name, _, _ in RECEIPT_CIRCLES} != set(RECEIPT_CONTROLS) or any(
    RECEIPT_CONTROLS[name][0] != value for name, value, _ in RECEIPT_CIRCLES
):
    raise AssertionError("the receipt circles are not the receipt controls")
# ``FacedLengthReference`` on Front (section F-F's): a line from the seat face
# along the body's -X silhouette, LENGTH_MAX long.
FACED_LENGTH_SKETCH = "FacedLengthReference"
FACED_LENGTH_START = (-BODY_DIA / 2.0, 0.0)
FACED_LENGTH_DIMENSIONS = ("FacedLength", "FacedLengthStart")
REFERENCE_SKETCHES = (RECEIPT_SKETCH, FACED_LENGTH_SKETCH)

DRAWING_DIMENSIONS = {
    "NutProfile": {"FlangeThick"},
    "Countersink1Profile": {"CskDia"},
    FACED_LENGTH_SKETCH: {"FacedLength"},
    RECEIPT_SKETCH: set(RECEIPT_CONTROLS),
}
DRAWING_PRECISION = {
    feature: {name: NATIVE_CONTROLS[name][3] for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
# One printed countersink stands for all four. The section shows the mouth
# as a linear size, so the Ø is the native <MOD-DIAM> token in the prefix,
# as build_sm_gooseneck / build_mg_magnifying_wheel print their diameters.
# A diameter's own Ø is its default prefix, which a set prefix replaces (run
# 20261105T023247678Z printed "4X 3.60/3.46"), so the hole's count carries
# the token too.
CSK_PREFIX = f"{SCREW_COUNT}X <MOD-DIAM>"
CSK_CALLOUT = f"{CSK_ANGLE:.0f}° CSK"
DIMENSION_PREFIXES = {
    ("Countersink1Profile", "CskDia"): CSK_PREFIX,
    (RECEIPT_SKETCH, "ReceiptHoleDia"): CSK_PREFIX,
}

# --- Supplier reference sizes (the dimension image's, mm) ---------------------------
# Drawn in the FeedNut panel of the kit's reference sheet: Front carries only
# the two vertical lengths (the flange on its silhouette, the body on the
# axis), and every diameter is read on the end view: the flange OD above it,
# the body's below, the hole and the bolt pattern to the sides. Hidden
# construction chords print where an edge or a centreline already is, never
# across a face.
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
