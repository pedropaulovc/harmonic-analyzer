r"""Pure-data envelope of the purchased pen marker, a Sharpie Mini (MHA-VN-060).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_vn_pen_marker`` revolves ``PROFILE`` and the pen assembly
reads the seat, length and mass from here.

The pen is a stock Sharpie Mini permanent marker, fine point (engineerguy
4/4 video 9:15-10:34: "insert the mini-sharpie pen and secure it"). It is
used with the cap taken off: frame t042 shows the bare barrel with its domed
back end going into the stirrup, and t046 shows the coloured cap-seat
section lying in the v-block groove, with the barrel shoulder at the back
face of the block and the nose and nib standing just proud of the front
face. The model is the uncapped marker.

Evidence (all read 2026-10-13):

- sharpie.com, item 35111 (Sharpie Consumer Care): "The Sharpie Mini Markers
  are 3-1/2"-long"; fine tip; plastic barrel; cap with a key-ring clip.
- artsupplycritic.com review of the Sharpie Mini (2016): "the same starting
  and ending diameters as the regular sized Sharpie"; the snap-on key ring
  sits on the cap's tip.
- jetpens.com, Sharpie Fine Point 30051 (the regular marker): grip Ø10.6,
  barrel with ink 7 g, cap 2 g, uncapped 123 long.
- The Sharpie product photograph
  ``s7d1.scene7.com/is/image/NewellBrands/35111-sharpie-permanent-mini-item-front``
  (2000 px), scaled by the 3-1/2" overall length taken over the key ring
  (1367 px). Taken without the ring, the barrel would come out Ø13.0, above
  the regular Sharpie's 13.1 maximum (which includes its clip), so the ring
  is counted.

Source of each number:

- SOURCED: ``CAPPED_LENGTH`` from sharpie.com; ``BARREL_DIA``, the
  Ø10.6 cap seat, from the regular grip Ø10.6 on jetpens.com together with
  the review's "same diameters".
- PHOTO-SCALED, about ±0.5: the body (silver barrel) length 45.8, its taper
  from Ø12.3 at the shoulder to Ø11.0, the domed back end, and the
  cap-shell length that bounds the seat and nose.
- ESTIMATED, not published by any source found: the cap-seat length
  (14.5), the nose cone (Ø3.2 to Ø7.2 over 8.0) and the nib (Ø2.0 standing
  3.0 proud). These are sized to fit inside the photographed cap shell
  (28.6 long, behind the 9.5 key-ring tip piece) with about 2 of clearance
  ahead of the nib.
- MASS: no vendor mass is published. The native model is a solid envelope
  of polypropylene ("PP Copolymer", 0.89 g/cm^3, the SOLIDWORKS library
  material), which gives ``MASS_G``, about 5.2 g. For comparison, the
  regular Sharpie's 7 g barrel scaled by length (71.4/123) gives 4.1 g, so
  the model is about 1 g heavy.

Part frame: the origin is at the nib tip on the marker axis, and +Y runs
along the axis toward the back end. ``PROFILE`` lists the (y, radius)
envelope stations from the nib to the back end.
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4

SUPPLIER = "Newell Brands (Sharpie)"
SKU = "35111"  # Sharpie Mini Permanent Marker, Fine Point (sharpie.com)
MATERIAL = "PP Copolymer"  # SOLIDWORKS library polypropylene
DENSITY_G_PER_MM3 = 0.89e-3  # PP Copolymer, 890 kg/m^3

CAPPED_LENGTH = 3.5 * MM_PER_IN  # 88.9, sharpie.com, including the key ring

# Nib: felt bullet, estimated.
NIB_DIA = 2.0
NIB_LENGTH = 3.0  # proud of the nose
# Nose: tapered plastic cone carrying the nib, estimated.
NOSE_TIP_DIA = 3.2
NOSE_BASE_DIA = 7.2
# Cap seat (the coloured grip under the cap): the Ø that lies in the V.
BARREL_DIA = 10.6
BARREL_START_Y = 11.0  # nose base
BARREL_END_Y = 25.5  # shoulder up to the silver body
# Body (silver barrel), photo-scaled.
BODY_FRONT_DIA = 12.3  # at the shoulder
BODY_BACK_DIA = 11.0  # where the dome begins to roll over
BODY_TAPER_END_Y = 59.0
OVERALL_LENGTH = 71.4  # uncapped, as used: nib tip to the domed back end

MAX_DIA = BODY_FRONT_DIA  # uncapped: the body at the shoulder

# (y, radius) envelope stations, nib tip to back end; revolved about +Y.
PROFILE: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),  # nib tip
    (0.3, 0.7),
    (1.0, NIB_DIA / 2.0),
    (NIB_LENGTH, NIB_DIA / 2.0),  # nib enters the nose
    (NIB_LENGTH, NOSE_TIP_DIA / 2.0),
    (BARREL_START_Y, NOSE_BASE_DIA / 2.0),
    (BARREL_START_Y, BARREL_DIA / 2.0),
    (BARREL_END_Y, BARREL_DIA / 2.0),
    (BARREL_END_Y, BODY_FRONT_DIA / 2.0),  # shoulder
    (BODY_TAPER_END_Y, BODY_BACK_DIA / 2.0),
    (65.4, 5.05),  # domed back end, photo-scaled
    (68.0, 4.4),
    (70.6, 2.8),
    (OVERALL_LENGTH, 0.0),
)


def volume_and_cg_y() -> tuple[float, float]:
    """Revolved volume (mm^3) and its axial centroid station (mm from the nib)."""
    volume = 0.0
    moment = 0.0
    for (y0, r0), (y1, r1) in zip(PROFILE, PROFILE[1:]):
        h = y1 - y0
        if h == 0.0:
            continue
        sq = r0 * r0 + r0 * r1 + r1 * r1
        v = math.pi * h / 3.0 * sq
        volume += v
        moment += v * (y0 + h * (r0 * r0 + 2.0 * r0 * r1 + 3.0 * r1 * r1) / (4.0 * sq))
    return volume, moment / volume


VOLUME_MM3, CG_Y = volume_and_cg_y()
MASS_G = VOLUME_MM3 * DENSITY_G_PER_MM3

DRAWING_NOTES = "USED UNCAPPED; THE GRIP UNDER THE CAP SEATS IN THE V-BLOCK GROOVE."
