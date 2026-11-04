r"""Pure-data envelope of the bought feed handwheel, HARFINGTON 50 mm (Amazon B0DJ3DZT86) (MHA-CH-06-TL-VN-57).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_vn_oblique_handwheel`` revolves the profiles
below and cuts the two set-screw holes from here.

The item is the shop-inventory ``fixtures.trammel-handwheel``: a HARFINGTON
anodized aluminium-alloy handwheel, Ø50 with a knurled rim, an Ø8 bore in a
Ø26 hub, and a rotating handle on the rim's outer face. It sits on the far
end of the jig's Tr8 leadscrew.

Datasheet-built: no vendor CAD obtained (the listing offers no CAD download).

Sources:

- SOURCED, https://www.amazon.com/dp/B0DJ3DZT86 (read 2026-11-04): "HARFINGTON
  Aluminum Alloy Handwheel 50mm OD 8mm Bore Lathe Hand Wheel | with Rotate
  Handle ... with Wrench and 2pcs Screws"; "Outer Diameter: 50mm / 2", Bore:
  8mm / 0.31", Height: 27mm / 1.1", Step Overall Dimension: 26 x 14mm / 1" x
  0.6"(D*H). Comes with two screws to secure the shaft"; anodized aluminum
  alloy, knurled rim, movable (rotating) handle. The listing's dimension
  image shows the hub (the "step") on the rim, one set-screw socket at about
  mid-hub and the handle standing off the rim's other face.
- FROM C4 (imported from ``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``, never
  retyped): the listing's hub Ø26 x 14 and rim Ø50 x 13 (27 over both), the
  Ø8 bore, its guaranteed depth ``BORE_LENGTH`` (the hub's 14), the handle
  envelope (Ø14 x 25 proud of the rim face, its axis 17 off the screw axis,
  52 overall) and the set screws' thread and station (M5, 7 from the hub
  end).
- SOURCED, ISO 724: the M5x0.8 internal minor diameter, D1 = D - 1.082532 P.
  M5 is not in ``_hole_spec.TAP_DRILL_MM``, so by the bought-parts modelling
  rule the taps are plain bores at the minor diameter.
- UNVERIFIED (not on the listing; verify on receipt, each with its check):
  - the bore's depth past the hub: the photos of the rim's outer face show
    no through hole, so the model's bore is blind, ``BORE_LENGTH`` deep.
    Check: an Ø8 gauge pin enters at least 14 from the hub end.
  - the handle's diameter, length and offset (the model's handle is the
    conservative Ø14 x 25 cylinder at offset 17, not its shape). Check: the
    handle stands at most 25 proud of the rim face and within 24 (offset
    plus radius) of the bore axis.
  - the set screws' size, their station and their clock (the model taps two
    M5 holes 90° apart at 7 from the hub end, the one used opposite the
    handle). Check: the supplied screws are M5 and their axis stands 7 from
    the hub end within ``leadscrew_stock.HANDWHEEL_GRUB_COVER``, measured
    before the leadscrew's handwheel flat is milled (that flat is stationed
    from it).
  - edge chamfers, knurl depth, alloy grade, handle material and mass: none
    is modelled; the rim is a plain Ø50 cylinder.

Modelled as one solid. The listing's handle rotates, but it is fused to
the rim face here: it is not loose and needs no motion. The set screws are
not modelled (the modelling rule for grub screws); their taps are.

Part frame. The axis is +Y and is published as ``ScrewAxis`` (Front ∩ Right).
y = 0 is the hub end face, where the bore opens. The hub spans y 0 .. 14, the
rim y 14 .. 27 and the handle y 27 .. 52. The bore runs y 0 .. 14. The
handle's axis is at x = ``GRIP_OFFSET``, z = 0. The set-screw taps are at
y = 7: one along -X (opposite the handle, the one on the leadscrew's flat)
and one along +Z.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as feed

SUPPLIER = "Amazon (sold by HARFINGTON)"
SKU = "B0DJ3DZT86"
INVENTORY_ID = feed.HANDWHEEL_ID  # fixtures.trammel-handwheel
QUANTITY = 1
MATERIAL = "6061 Alloy"  # SOLIDWORKS library stand-in: the alloy grade is not stated

# --- FROM C4 (imported) ---------------------------------------------------------
HUB_DIA = feed.HANDWHEEL_HUB_DIA  # 26
HUB_LENGTH = feed.HANDWHEEL_HUB_LENGTH  # 14
WHEEL_DIA = feed.HANDWHEEL_WHEEL_DIA  # 50
WHEEL_LENGTH = feed.HANDWHEEL_WHEEL_LENGTH  # 13
BORE_LENGTH = feed.HANDWHEEL_BORE_LENGTH  # 14, blind: UNVERIFIED past the hub
BORE_DIA = feed.SCREW_MAJOR_DIA  # 8: the bore takes the screw's crests
GRIP_OFFSET = feed.HANDWHEEL_GRIP_OFFSET  # 17, UNVERIFIED envelope
GRIP_DIA = feed.HANDWHEEL_GRIP_DIA  # 14, UNVERIFIED envelope
GRIP_LENGTH = feed.HANDWHEEL_GRIP_LENGTH  # 25 proud of the rim face, UNVERIFIED
LENGTH = feed.HANDWHEEL_LENGTH  # 52 overall
SET_SCREW_THREAD = feed.HANDWHEEL_GRUB  # "M5", UNVERIFIED
SET_SCREW_STATION = feed.HANDWHEEL_GRUB_FROM_HUB  # 7 from the hub end, UNVERIFIED

# --- SOURCED: listing / ISO 724 ---------------------------------------------------
SET_SCREW_COUNT = 2  # "Comes with two screws to secure the shaft"
SET_SCREW_PITCH = 0.8  # M5 coarse
SET_SCREW_MAJOR = float(SET_SCREW_THREAD.removeprefix("M"))
SET_SCREW_MINOR_DIA = SET_SCREW_MAJOR - 1.082532 * SET_SCREW_PITCH  # 4.134

# --- UNVERIFIED: the taps' clock (one socket shows in the listing's image) ----------
# Set-screw tap directions in the part's (x, z): the one on the leadscrew's
# flat opposite the handle, the other a quarter turn on.
SET_SCREW_DIRECTIONS: tuple[tuple[float, float], ...] = ((-1.0, 0.0), (0.0, 1.0))

WHEEL_FACE_Y = HUB_LENGTH + WHEEL_LENGTH  # 27: the rim's outer (handle) face
# The swept radius: the rim's, unless the handle's envelope reaches past it.
SWEEP_R = max(WHEEL_DIA / 2.0, GRIP_OFFSET + GRIP_DIA / 2.0)  # 25

_BORE_R = BORE_DIA / 2.0
_HUB_R = HUB_DIA / 2.0
_WHEEL_R = WHEEL_DIA / 2.0
_GRIP_R = GRIP_DIA / 2.0

# (radius, y) about the wheel axis, revolved 360° about the chain's closing
# edge, which lies on the axis behind the blind bore (y BORE_LENGTH ..
# WHEEL_FACE_Y). Every corner is sharp: no edge break is published.
WHEEL_PROFILE: tuple[tuple[float, float], ...] = (
    (0.0, WHEEL_FACE_Y),
    (_WHEEL_R, WHEEL_FACE_Y),
    (_WHEEL_R, HUB_LENGTH),
    (_HUB_R, HUB_LENGTH),
    (_HUB_R, 0.0),
    (_BORE_R, 0.0),
    (_BORE_R, BORE_LENGTH),
    (0.0, BORE_LENGTH),
)
# (radius from the handle's own axis, y), revolved 360° about that axis (the
# closing edge): the handle's envelope cylinder on the rim face.
GRIP_PROFILE: tuple[tuple[float, float], ...] = (
    (0.0, WHEEL_FACE_Y),
    (_GRIP_R, WHEEL_FACE_Y),
    (_GRIP_R, LENGTH),
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


WHEEL_VOLUME_MM3 = revolved_volume(WHEEL_PROFILE)
GRIP_VOLUME_MM3 = revolved_volume(GRIP_PROFILE)
TAP_VOLUME_MM3 = tap_volume(SET_SCREW_MINOR_DIA)
VOLUME_MM3 = WHEEL_VOLUME_MM3 + GRIP_VOLUME_MM3 - SET_SCREW_COUNT * TAP_VOLUME_MM3

# The note names the leadscrew by its drawing number, read from the registry.
LEADSCREW_NUMBER = _config.parts("ch-rocker-arm-tl-vn-oblique-leadscrew")["number"]
DRAWING_NOTES = (
    f"SLIDE ONTO LEADSCREW {LEADSCREW_NUMBER} FAR END; LOCK A SET SCREW ON ITS FLAT."
)

# --- Self-checks ----------------------------------------------------------------
if not GRIP_OFFSET + _GRIP_R <= _WHEEL_R:
    raise AssertionError("the handle envelope overhangs the rim")
if abs(WHEEL_FACE_Y + GRIP_LENGTH - LENGTH) > 1e-9:
    raise AssertionError("the hub, rim and handle miss C4's overall length")
if not HUB_LENGTH <= BORE_LENGTH < WHEEL_FACE_Y:
    raise AssertionError("the blind bore is not through the hub and inside the rim")
# Each tap lies inside the hub and opens into the bore.
if not (
    0.0 < SET_SCREW_STATION - SET_SCREW_MINOR_DIA / 2.0
    and SET_SCREW_STATION + SET_SCREW_MINOR_DIA / 2.0 < min(HUB_LENGTH, BORE_LENGTH)
):
    raise AssertionError("a set-screw tap leaves the hub or misses the bore")
if not feed.HANDWHEEL_ENGAGEMENT < BORE_LENGTH:
    raise AssertionError("the leadscrew reaches the blind bore's bottom")
