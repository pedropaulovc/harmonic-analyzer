r"""Pure-data envelope of the purchased pen marker, a Sharpie Fine Point (MHA-VN-065).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_vn_pen_marker`` revolves ``PROFILE`` and the pen assembly
reads the seat, length, mass and CG from here.

The pen is a stock regular-size Sharpie permanent marker, fine point (item
30051), used with the cap taken off. The engineerguy 4/4 video (9:15-10:34)
used a Sharpie Mini; this build takes the regular Fine Point instead, so the
same-format markers sold in Brazil fit the v-block: Oval PY230200 and the
Brasfort "caneta marcador permanente ponta fina". Their dimensions are not
published; they are assumed to match the Sharpie Fine Point format.
Masterprint MP616 does not fit: it has a chisel tip and a 127 x 18 x 20 mm
body.

As in the video (frames t042/t046), the cap-seat section (the grip under
the cap) lies in the v-block groove, the body shoulder stands at the
block's paper-end section, and the nose and nib stand proud of the paper
end. The body runs back through the relief slot and out of the free end.

Evidence (all read 2026-10-13):

- jetpens.com, Sharpie Fine Point 30051: grip Ø10.6, barrel with ink 7 g,
  cap 2 g, uncapped 123 long.
- The Sharpie Mini (sharpie.com item 35111) product photograph
  ``s7d1.scene7.com/is/image/NewellBrands/35111-sharpie-permanent-mini-item-front``
  and the artsupplycritic.com review of the Mini (2016: "the same starting
  and ending diameters as the regular sized Sharpie"). Together they give
  the shared front end and the body's diameters.

Source of each number:

- SOURCED: ``OVERALL_LENGTH`` (123, uncapped), ``BARREL_DIA`` (the Ø10.6
  cap seat that lies in the V) and ``MASS_G`` (7 g, the barrel with its
  ink), all from jetpens.com.
- PHOTO-SCALED from the Mini, about ±0.5, through the review's "same
  diameters": the body's Ø12.3 at the shoulder and Ø11.0 where the back
  dome begins, and the dome's profile.
- ESTIMATED, not published by any source found: the cap-seat length (14.5),
  the nose cone (Ø3.2 to Ø7.2 over 8.0) and the nib (Ø2.0 standing 3.0
  proud), all kept from the Mini; the body's straight taper from the
  shoulder to the dome; and the dome's start station (``BODY_TAPER_END_Y``),
  which carries the Mini's photographed dome to the 123 overall length.
- MASS and CG: the carriage balance (``pn_pen_carriage_geom``) uses the
  published ``MASS_G`` at the envelope's centroid ``CG_Y``, which assumes
  uniform density (ESTIMATED: the ink reservoir and the hollow barrel are
  not modelled). The native part is the solid envelope in polypropylene
  ("PP Copolymer", the SOLIDWORKS library material, 0.89 g/cm^3). It weighs
  more than 7 g and is not used for the balance.

Part frame: the origin is at the nib tip on the marker axis, and +Y runs
along the axis toward the back end. ``PROFILE`` lists the (y, radius)
envelope stations from the nib to the back end.
"""

from __future__ import annotations

import math

SUPPLIER = "Newell Brands (Sharpie)"
SKU = "30051"  # Sharpie Permanent Marker, Fine Point (jetpens.com)
MATERIAL = "PP Copolymer"  # SOLIDWORKS library polypropylene (the native envelope)

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
# Body (silver barrel): photo-scaled diameters, estimated stations.
BODY_FRONT_DIA = 12.3  # at the shoulder
BODY_BACK_DIA = 11.0  # where the dome begins to roll over
BODY_TAPER_END_Y = 110.6
OVERALL_LENGTH = 123.0  # uncapped, as used: nib tip to the domed back end

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
    (117.0, 5.05),  # domed back end, photo-scaled from the Mini
    (119.6, 4.4),
    (122.2, 2.8),
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
# jetpens.com: the barrel with its ink, uncapped as used.
MASS_G = 7.0

DRAWING_NOTES = "USED UNCAPPED; THE GRIP UNDER THE CAP SEATS IN THE V-BLOCK GROOVE."
