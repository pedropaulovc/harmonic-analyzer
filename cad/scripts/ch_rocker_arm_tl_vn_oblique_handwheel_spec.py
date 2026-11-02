r"""Pure-data envelope of the bought feed handwheel, MISUMI HOK40-HC8 (MHA-CH-06-TL-VN-57).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_vn_oblique_handwheel`` revolves the profiles
below and cuts the two set-screw holes from here.

The item is the shop-inventory ``fixtures.trammel-handwheel``: a black-
anodised 5056 aluminium knurled handwheel, Ø40, with MISUMI's factory HC8
alteration (an Ø8 H8 THROUGH bore and two radial M5 set-screw taps 90° apart
in the hub, one set screw supplied). It carries a revolving Nylon 6 grip and
sits on the far end of the jig's Tr8 leadscrew.

Vendor-checked. The native model is checked against MISUMI's vendor STEP
``HOK40-HC8.step``, sha256
a9c2c04cdf53fefc978441149df3f69dab544915a3d229e4dcfd1fc6bf16a7af. It was
downloaded 2026-10-17 UTC through the user's own browser session, from the
product page's CAD download, and is kept locally in
``C:/src/dt-logs/trammel-bought/vendor-cad/``; it is never committed. The STEP
was measured headless in FreeCAD 1.1 (analytic face radii, axes and extents;
per-solid and fused volumes). It holds three solids: the wheel, the grip and
one M5 set screw.

Sources:

- FROM C4 (imported from ``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``, never
  retyped): hub Ø22 x 13, rim Ø40 x 12, the Ø8 through bore over the 25 body,
  the grip's 14.5 axis offset, the M5 set-screw thread and its 6.5 station
  from the hub end. The vendor STEP agrees with all of these. C4 also carries
  the catalogue grip (Ø13, 18.8 proud, 43.8 overall), and there the STEP
  disagrees: see the next item.
- SOURCED, vendor STEP: the detail C4 does not carry. The rim edges have
  1 x 45° chamfers, so both faces are flat to Ø38. R0.5 fillets round the hub
  end face's outer edge (convex) and the hub-to-rim corner (concave). The
  set-screw taps are drilled at the M5 minor diameter, Ø4.134, from the hub
  OD into the bore, one at 90° to the other; the supplied screw sits in the
  one opposite the grip. The grip, on its own axis, is a Ø10 x 5 collar (with
  8 AF wrench flats over 4 of it) on the rim face, a step out to Ø12, a taper
  to Ø14 over 16/3, then a Ø14 barrel to 21 proud of the rim face, with an R2
  round on its end. So the vendor grip is Ø14 max and 21 proud, 46 overall,
  sweeping radius 21.5, against C4's catalogue Ø13 / 18.8 / 43.8 / 21. This
  part models the vendor envelope, which encloses C4's catalogue one.
- SOURCED, https://us.misumi-ec.com/vona2/detail/110300515660/?HissuCode=HOK40-HC8,
  its drawing and HC alteration table, and catalogue page 3210
  (https://us.misumi-ec.com/pdf/fa/2019/2019_US_3210.pdf). All were read
  2026-10-17 UTC, and copies are kept in
  ``C:/src/dt-logs/trammel-leadscrew/handwheel/`` (``misumi_HOK40-HC8_2026-10-17.txt``,
  ``misumi_hok_drw_01.gif``, ``misumi_hok_alt_01.gif`` and
  ``misumi_2019_US_3210.pdf``). They give 5056 aluminium, black anodise and a
  Nylon 6 revolving grip. The D40 row reads H25, A12, S13, D1 22, h6.5, P14.5,
  B13, G18.8 and 50 g. The HC8 alteration gives an H8 through bore with two M5
  taps 90° apart, "Comes with one set screw".
- SOURCED, ISO 724: the M5x0.8 internal minor diameter, D1 = D - 1.082532 P.
  M5 is not in ``_hole_spec.TAP_DRILL_MM``, so by the bought-parts modelling
  rule the taps are plain bores at the minor diameter, which is the vendor
  model's own hole.
- UNVERIFIED (verify on receipt): the set screw's length and point (the
  vendor model shows an M5 x 5 cup point) and its holding torque.

Modelled as one solid. The grip is a separate turning piece, but it is fused
to the rim face here: it is not loose and needs no motion. The set screw is
not modelled (the modelling rule for grub screws); its tap is.

Omitted vendor detail (the native solid is the larger, so it stays
conservative for interference): the grip collar's wrench flats
(``GRIP_FLATS_MM3``), and the void the vendor model leaves in its grip
socket. That socket is a Ø4.917 blind hole under the grip's Ø6 shank, whose
chamfered end stops short of the socket's chamfered bottom
(``GRIP_SOCKET_VOID_MM3``). With those two added back, ``VOLUME_MM3`` equals
the vendor wheel-plus-grip volume, ``VENDOR_VOLUME_MM3``.

Part frame. The axis is +Y and is published as ``ScrewAxis`` (Front ∩ Right).
y = 0 is the hub end face, where the bore opens. The hub spans y 0 .. 13, the
rim y 13 .. 25 and the grip y 25 .. 46. The grip's axis is at x =
``GRIP_OFFSET``, z = 0. The set-screw taps are at y = 6.5: one along -X
(opposite the grip, the one with the supplied screw) and one along +Z. The
vendor frame maps to this one by x = -y_v, y = -x_v and z = -z_v; the vendor
axis is X, its hub end face is at x_v = 0 and its grip is on -Y_v.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as feed

SUPPLIER = "MISUMI"
SKU = "HOK40-HC8"
INVENTORY_ID = feed.HANDWHEEL_ID  # fixtures.trammel-handwheel
QUANTITY = 1
MATERIAL = "6061 Alloy"  # SOLIDWORKS library stand-in for the vendor's 5056

# --- FROM C4 (imported) ---------------------------------------------------------
HUB_DIA = feed.HANDWHEEL_HUB_DIA  # 22
HUB_LENGTH = feed.HANDWHEEL_HUB_LENGTH  # 13
WHEEL_DIA = feed.HANDWHEEL_WHEEL_DIA  # 40
WHEEL_LENGTH = feed.HANDWHEEL_WHEEL_LENGTH  # 12
BODY_LENGTH = feed.HANDWHEEL_BORE_LENGTH  # 25, the through bore's length
BORE_DIA = feed.SCREW_MAJOR_DIA  # 8 H8: the wheel bore takes the screw's crests
GRIP_OFFSET = feed.HANDWHEEL_GRIP_OFFSET  # 14.5
SET_SCREW_THREAD = feed.HANDWHEEL_GRUB  # "M5"
SET_SCREW_STATION = feed.HANDWHEEL_GRUB_FROM_HUB  # 6.5 from the hub end
CATALOGUE_GRIP_DIA = feed.HANDWHEEL_GRIP_DIA  # 13 (the vendor model: Ø14 max)
CATALOGUE_GRIP_LENGTH = feed.HANDWHEEL_GRIP_LENGTH  # 18.8 (the vendor model: 21)
CATALOGUE_LENGTH = feed.HANDWHEEL_LENGTH  # 43.8 (the vendor model: 46)

# --- SOURCED: catalogue / ISO 724 -------------------------------------------------
SET_SCREW_COUNT = 2  # taps; one screw supplied ("Comes with one set screw")
SET_SCREW_PITCH = 0.8  # M5 coarse
SET_SCREW_MAJOR = float(SET_SCREW_THREAD.removeprefix("M"))
SET_SCREW_MINOR_DIA = SET_SCREW_MAJOR - 1.082532 * SET_SCREW_PITCH  # 4.134
SUPPLIED_SET_SCREW = "M5 x 5 cup point"  # vendor model; not modelled
MASS_G = 50.0  # catalogue D40 row
# Handbook densities (g/cm^3) for the mass cross-check only: 5056 aluminium
# and Nylon 6 (the SOLIDWORKS material is one 6061 stand-in for the solid).
WHEEL_DENSITY = 2.64
GRIP_DENSITY = 1.14

# --- SOURCED: vendor STEP ---------------------------------------------------------
WHEEL_FACE_Y = HUB_LENGTH + WHEEL_LENGTH  # 25: the rim's grip-side face
RIM_CHAMFER = 1.0  # 45°, both rim edges
HUB_FILLET = 0.5  # the hub end face's outer edge and the hub-to-rim corner
# Set-screw tap directions in the part's (x, z): the screwed one opposite the
# grip, the other a quarter turn on.
SET_SCREW_DIRECTIONS: tuple[tuple[float, float], ...] = ((-1.0, 0.0), (0.0, 1.0))
GRIP_COLLAR_DIA = 10.0
GRIP_COLLAR_LENGTH = 5.0
GRIP_STEP_DIA = 12.0  # the taper's start, at the collar's end
GRIP_TAPER_LENGTH = 16.0 / 3.0  # 10.62° half-angle, to GRIP_DIA
GRIP_DIA = 14.0  # the barrel; the vendor envelope's grip diameter
GRIP_LENGTH = 21.0  # proud of the rim face
GRIP_END_ROUND = 2.0
GRIP_FLATS_AF = 8.0  # wrench flats on the collar (omitted)
GRIP_FLATS_LENGTH = 4.0  # from the rim face
LENGTH = WHEEL_FACE_Y + GRIP_LENGTH  # 46
SWEEP_R = GRIP_OFFSET + GRIP_DIA / 2.0  # 21.5, the grip's swept radius
# The vendor's grip socket (wheel) and shank (grip), for the void only.
GRIP_SOCKET_DIA = 4.917
GRIP_SOCKET_DEPTH = 9.0  # cylindrical, from the rim face
GRIP_SOCKET_CHAMFER = 0.5  # 45°, its bottom
GRIP_SHANK_END_DIA = 4.772  # the shank's chamfered tip, 9.0 in

# --- Vendor model comparison ----------------------------------------------------
VENDOR_STEP = "HOK40-HC8.step"
VENDOR_STEP_SHA256 = "a9c2c04cdf53fefc978441149df3f69dab544915a3d229e4dcfd1fc6bf16a7af"
VENDOR_VOLUME_MM3 = 21119.08  # FreeCAD 1.1: wheel fused with the grip
VENDOR_WHEEL_VOLUME_MM3 = 18272.275  # solid 0, with the empty grip socket
VENDOR_GRIP_VOLUME_MM3 = 2927.126  # solid 1, its shank inside the socket
VENDOR_SET_SCREW_VOLUME_MM3 = 77.596  # solid 2, not modelled

_BORE_R = BORE_DIA / 2.0
_HUB_R = HUB_DIA / 2.0
_WHEEL_R = WHEEL_DIA / 2.0

# (radius, y) about the wheel axis, revolved 360°: the hub and rim round the
# through bore (corners sharp; the fillets are separate features).
WHEEL_PROFILE: tuple[tuple[float, float], ...] = (
    (_BORE_R, 0.0),
    (_HUB_R, 0.0),
    (_HUB_R, HUB_LENGTH),
    (_WHEEL_R - RIM_CHAMFER, HUB_LENGTH),
    (_WHEEL_R, HUB_LENGTH + RIM_CHAMFER),
    (_WHEEL_R, WHEEL_FACE_Y - RIM_CHAMFER),
    (_WHEEL_R - RIM_CHAMFER, WHEEL_FACE_Y),
    (_BORE_R, WHEEL_FACE_Y),
)
# (radius from the grip's own axis, y), revolved 360° about that axis (its
# end corner sharp; the R2 round is a separate feature).
GRIP_PROFILE: tuple[tuple[float, float], ...] = (
    (0.0, WHEEL_FACE_Y),
    (GRIP_COLLAR_DIA / 2.0, WHEEL_FACE_Y),
    (GRIP_COLLAR_DIA / 2.0, WHEEL_FACE_Y + GRIP_COLLAR_LENGTH),
    (GRIP_STEP_DIA / 2.0, WHEEL_FACE_Y + GRIP_COLLAR_LENGTH),
    (GRIP_DIA / 2.0, WHEEL_FACE_Y + GRIP_COLLAR_LENGTH + GRIP_TAPER_LENGTH),
    (GRIP_DIA / 2.0, LENGTH),
    (0.0, LENGTH),
)
# The set-screw tap, in its own sketch (u, v) = (along the tap, station): a
# rectangle from the wheel axis out past the hub OD, revolved about its
# station edge, the chain's closing edge. Front plane: u = model x. Right
# plane: u = -model z.
TAP_REACH = _HUB_R + 1.0
TAP_PROFILE: tuple[tuple[float, float], ...] = (
    (-TAP_REACH, SET_SCREW_STATION),
    (-TAP_REACH, SET_SCREW_STATION + SET_SCREW_MINOR_DIA / 2.0),
    (0.0, SET_SCREW_STATION + SET_SCREW_MINOR_DIA / 2.0),
    (0.0, SET_SCREW_STATION),
)


def revolved_volume(profile: tuple[tuple[float, float], ...]) -> float:
    """Volume (mm^3) of a closed (radius, y) polygon revolved about r = 0 (Pappus)."""
    area_moment = 0.0
    for (r1, y1), (r2, y2) in zip(profile, profile[1:] + profile[:1], strict=True):
        area_moment += (r1 + r2) * (r1 * y2 - r2 * y1)
    return abs(2.0 * math.pi * area_moment / 6.0)


# A round of radius rho on a square corner: the spandrel's area, and its
# centroid's distance from each leg toward the corner, (10 - 3 pi) rho / (3 (4 - pi)).
def spandrel_area(rho: float) -> float:
    return rho * rho * (1.0 - math.pi / 4.0)


def spandrel_centroid(rho: float) -> float:
    return (10.0 - 3.0 * math.pi) * rho / (3.0 * (4.0 - math.pi))


def fillet_ring_volume(corner_r: float, rho: float, outward: bool) -> float:
    """The ring a round of radius rho on a revolved square corner at radius
    ``corner_r`` sweeps: its centroid sits inboard of the corner (an outer,
    convex corner) or outboard of it (an inner, concave corner)."""
    offset = spandrel_centroid(rho)
    radius = corner_r - offset if outward else corner_r + offset
    return 2.0 * math.pi * radius * spandrel_area(rho)


def _elliptic_k_e(m: float) -> tuple[float, float]:
    """Complete elliptic integrals K(m), E(m), parameter m = k^2 < 1 (AGM)."""
    a, b = 1.0, math.sqrt(1.0 - m)
    weight, total = 0.5, 0.5 * m
    while abs(a - b) > 1e-15 * a:
        a, b, c = 0.5 * (a + b), math.sqrt(a * b), 0.5 * (a - b)
        weight *= 2.0
        total += weight * c * c
    k = math.pi / (2.0 * a)
    return k, k * (1.0 - total)


def cross_hole_volume(hole_dia: float, shaft_dia: float) -> float:
    """Volume a diametral hole removes from a full cylinder (both walls):
    the two cylinders' intersection, (8/3) R [(R^2+r^2) E - (R^2-r^2) K]."""
    r, big_r = hole_dia / 2.0, shaft_dia / 2.0
    k, e = _elliptic_k_e((r / big_r) ** 2)
    return 8.0 / 3.0 * big_r * ((big_r**2 + r**2) * e - (big_r**2 - r**2) * k)


def tap_volume(hole_dia: float) -> float:
    """One radial hole from the hub's OD into the bore (one wall)."""
    return (
        cross_hole_volume(hole_dia, HUB_DIA) - cross_hole_volume(hole_dia, BORE_DIA)
    ) / 2.0


def _frustum(r1: float, r2: float, height: float) -> float:
    return math.pi * height / 3.0 * (r1 * r1 + r1 * r2 + r2 * r2)


WHEEL_VOLUME_MM3 = revolved_volume(WHEEL_PROFILE)
HUB_END_FILLET_MM3 = fillet_ring_volume(_HUB_R, HUB_FILLET, outward=True)  # removed
HUB_CORNER_FILLET_MM3 = fillet_ring_volume(_HUB_R, HUB_FILLET, outward=False)  # added
GRIP_VOLUME_MM3 = revolved_volume(GRIP_PROFILE)
GRIP_END_ROUND_MM3 = fillet_ring_volume(GRIP_DIA / 2.0, GRIP_END_ROUND, outward=True)
TAP_VOLUME_MM3 = tap_volume(SET_SCREW_MINOR_DIA)
VOLUME_MM3 = (
    WHEEL_VOLUME_MM3
    - HUB_END_FILLET_MM3
    + HUB_CORNER_FILLET_MM3
    + GRIP_VOLUME_MM3
    - GRIP_END_ROUND_MM3
    - SET_SCREW_COUNT * TAP_VOLUME_MM3
)

# The omitted vendor detail, closed form (see the docstring).
_FLAT_D = GRIP_FLATS_AF / 2.0
_COLLAR_R = GRIP_COLLAR_DIA / 2.0
GRIP_FLATS_MM3 = (
    2.0
    * GRIP_FLATS_LENGTH
    * (
        _COLLAR_R**2 * math.acos(_FLAT_D / _COLLAR_R)
        - _FLAT_D * math.sqrt(_COLLAR_R**2 - _FLAT_D**2)
    )
)
_SOCKET_R = GRIP_SOCKET_DIA / 2.0
_SHANK_TIP_R = GRIP_SHANK_END_DIA / 2.0
_SLIVER = _SOCKET_R - _SHANK_TIP_R  # the 45° shank chamfer's length inside the socket
GRIP_SOCKET_VOID_MM3 = _frustum(
    _SOCKET_R, _SOCKET_R - GRIP_SOCKET_CHAMFER, GRIP_SOCKET_CHAMFER
) + math.pi * (
    _SOCKET_R**2 * _SLIVER - ((_SHANK_TIP_R + _SLIVER) ** 3 - _SHANK_TIP_R**3) / 3.0
)

# The note names the leadscrew by its drawing number, read from the registry.
LEADSCREW_NUMBER = _config.parts("ch-rocker-arm-tl-vn-oblique-leadscrew")["number"]
DRAWING_NOTES = (
    f"SLIDE ONTO LEADSCREW {LEADSCREW_NUMBER} FAR END; LOCK WITH THE HUB SET SCREW."
)

# --- Self-checks ----------------------------------------------------------------
if not GRIP_OFFSET - GRIP_DIA / 2.0 > _BORE_R:
    raise AssertionError("the grip crosses the bore")
if not GRIP_OFFSET + GRIP_COLLAR_DIA / 2.0 < _WHEEL_R:
    raise AssertionError("the grip collar overhangs the rim")
if not SET_SCREW_MINOR_DIA / 2.0 < SET_SCREW_STATION - HUB_FILLET:
    raise AssertionError("a set-screw tap breaks into the hub end's fillet")
if not SET_SCREW_STATION + SET_SCREW_MINOR_DIA / 2.0 < HUB_LENGTH - HUB_FILLET:
    raise AssertionError("a set-screw tap breaks into the hub-to-rim fillet")
if not (GRIP_STEP_DIA < GRIP_DIA and GRIP_DIA / 2.0 > GRIP_END_ROUND):
    raise AssertionError("the grip's taper or end round is inconsistent")
if not (GRIP_DIA >= CATALOGUE_GRIP_DIA and LENGTH >= CATALOGUE_LENGTH):
    raise AssertionError("the vendor grip no longer encloses C4's catalogue grip")
if abs(HUB_LENGTH + WHEEL_LENGTH - BODY_LENGTH) > 1e-9:
    raise AssertionError("the hub and rim do not make up C4's through-bore length")
