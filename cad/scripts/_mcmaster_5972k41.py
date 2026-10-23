r"""Pure 5972K41 (6200-2RS) catalogue bands and vendor-model dimensions.

The envelope is the calculator's: bore, OD and width are
``ch_rocker_arm_tl_oblique_trammel_spec.BEARING_BORE`` / ``BEARING_OD`` /
``BEARING_WIDTH`` (10 / 30 / 9), imported, so the faces the jig mates on are
exactly those nominals. Internal ring, seal and ball geometry is read off
McMaster's vendor model, downloaded 2026-10-17 from the
https://www.mcmaster.com/5972K41/ CAD links
(``5972K41_Steel Ball Bearing.STEP``, SHA-256
``617c061f9ee7b93425cf85cd29eb80eae1382ae82e6c66bfbf61f80f08754090``) and
measured with headless FreeCAD 1.1 on 2026-10-17
(dt-logs ``trammel-bought/vendor-cad/bd-freecad-harvest.json``): 11 solids,
3824.014343 mm^3, 5563.163779 mm^2.  The vendor model is read for dimensions
only; the part is not replica-gated against it (user ruling 2026-10-17).

Purchased size authority is the SKU-specific McMaster catalogue transcription
read live 2026-10-17 and rechecked live 2026-10-21
(cad/references/mcmaster/README.md): bore 10 -0.008/0,
OD 30 -0.009/0, width 9 -0.12/0, ABEC 1, C3, DIN 625-1. The bands below
are catalogue deviations, not a claim that an actual bearing has been received
or qualified. Trace the actual purchase to that dimensional authority and
inspect its intact full-circumference cylindrical OD land, including the axial
mid-plane, before pressing. Vendor CAD does not qualify that physical profile
or establish a maximum supplied chamfer.

* Outer ring (1427.660359 mm^3): Ø30 OD, 0.45 x 45 deg chamfers on both OD
  corners, Ø26 lands, a raceway groove of radius sqrt(13) centred on the
  Ø20 ball-pitch circle at mid-width, meeting each land 2.0 from mid-width.
* Inner ring (602.244065 mm^3): Ø10 bore, 0.45 x 45 deg chamfers on both
  bore corners, Ø14 lands, the same groove circle meeting each land 2.0
  from mid-width.  Neither ring's land corners are broken.
* Seven balls (196.337672 mm^3 each), Ø sqrt(52) = 7.2111 on the Ø20
  pitch circle at mid-width, each conforming to both grooves.
* Two seals (209.873107 mm^3 each), Ø14 to Ø26, inner face tangent to the
  balls; outer face recessed 0.225 at the Ø24.6-Ø26 lip, 0.392362 across the
  Ø18-Ø24.6 web, and crowned between Ø14 and Ø18 by an arc whose crest is
  back at the lip's 0.225 recess.

The vendor model is centred on its Z axis; ``diag_build_5972K41`` puts a side
face at y = 0.  ISO 15 gives the 6200 a chamfer dimension r_s min 0.6 (SKF
6200-2RSH, https://www.skf.com/products/rolling-bearings/ball-bearings/deep-groove-ball-bearings/productid-6200-2RSH,
read 2026-10-16: "r1,2 min. 0.6 mm", housing/shaft fillet "ra max. 0.6 mm");
the vendor model's 0.45 is less than that, and the model carries the vendor's
0.45.  ``CHAMFER_RS_MIN`` records the standard's
value as a note for mating-fillet checks; no geometry reads it.
"""

from __future__ import annotations

import math

from ch_rocker_arm_tl_oblique_trammel_spec import (
    BEARING_BORE as BORE,
    BEARING_OD as OD,
    BEARING_WIDTH as WIDTH,
)

__all__ = [
    "BALL_COUNT",
    "BALL_DIA",
    "BORE",
    "BORE_BAND",
    "CHAMFER_RS_MIN",
    "GROOVE_HALF_WIDTH",
    "INNER_LAND_DIA",
    "OD",
    "OD_BAND",
    "OUTER_LAND_DIA",
    "PITCH_DIA",
    "RING_CHAMFER",
    "SEAL_CROWN_DIA",
    "SEAL_LIP_DIA",
    "SEAL_LIP_RECESS",
    "SEAL_WEB_RECESS",
    "WIDTH",
    "WIDTH_BAND",
    "ball_volume",
    "inner_ring_volume",
    "outer_ring_volume",
    "seal_crown_radius",
    "seal_inner_recess",
    "seal_volume",
    "total_volume",
]

# --- Purchased catalogue deviations, (upper, lower), millimetres ------------
# SKU-specific supplier dimensions, not inferred from the CAD or ABEC label.
BORE_BAND = (0.0, -0.008)
OD_BAND = (0.0, -0.009)
WIDTH_BAND = (0.0, -0.12)

# --- Vendor model (FreeCAD read of the STEP, 2026-10-17) --------------------
RING_CHAMFER = 0.45  # 45 deg legs: OD corners (cone Ø29.1-Ø30) and bore corners
PITCH_DIA = 20.0  # ball-centre circle; both groove circles are centred on it
INNER_LAND_DIA = 14.0
OUTER_LAND_DIA = 26.0
GROOVE_HALF_WIDTH = 2.0  # each groove meets its land 2.0 either side of mid-width
BALL_COUNT = 7
# The groove circle through the land edges: radius hypot(3, 2) = sqrt(13),
# which is also the ball radius (the STEP's spheres are 3.605551).
BALL_DIA = 2.0 * math.hypot((OUTER_LAND_DIA - PITCH_DIA) / 2.0, GROOVE_HALF_WIDTH)
SEAL_LIP_DIA = 24.6  # the lip step: the STEP's Ø24.6 cylinder
SEAL_CROWN_DIA = 18.0  # the crown arc runs from the Ø14 land to Ø18
SEAL_LIP_RECESS = 0.225  # lip face and crown crest below the side face (4.5 - 4.275)
SEAL_WEB_RECESS = 0.392362  # web face below the side face (4.5 - 4.107638)

# --- ISO 15 / SKF note only (see the docstring) ------------------------------
CHAMFER_RS_MIN = 0.6

# Each groove meets the vendor's land edge, so the derived ball must be the
# Ø20-centred circle through (land, +/-2): sqrt(13) in the STEP.
if abs(BALL_DIA / 2.0 - 3.605551) > 1e-6:
    raise AssertionError(
        f"5972K41 ball radius {BALL_DIA / 2.0} is not the STEP's 3.605551"
    )


def seal_inner_recess() -> float:
    """The seal's inner face below the side face: tangent to the balls."""
    return WIDTH / 2.0 - BALL_DIA / 2.0  # 0.894449


def seal_crown_radius() -> float:
    """The crown arc's radius: chord Ø14-Ø18, rise from the web to the lip
    recess (3.071214 in the STEP)."""
    half_chord = (SEAL_CROWN_DIA - INNER_LAND_DIA) / 4.0
    rise = SEAL_WEB_RECESS - SEAL_LIP_RECESS
    return (half_chord**2 + rise**2) / (2.0 * rise)


def _segment(radius: float, offset: float) -> tuple[float, float]:
    """(area, centroid distance from the circle's centre) of the circular
    segment a chord ``offset`` from the centre cuts off a circle of ``radius``."""
    half = math.sqrt(radius**2 - offset**2)
    area = radius**2 * math.acos(offset / radius) - offset * half
    return area, 2.0 * half**3 / (3.0 * area)


def _chamfer_ring(corner_r: float, inward: float) -> float:
    """Volume a 45 deg RING_CHAMFER removes at a corner of radius
    ``corner_r``; ``inward`` is +1 when the material lies at smaller radius."""
    return (
        2.0 * math.pi * (corner_r - inward * RING_CHAMFER / 3.0) * RING_CHAMFER**2 / 2.0
    )


def _groove_segment() -> tuple[float, float]:
    offset = (OUTER_LAND_DIA - PITCH_DIA) / 2.0
    return _segment(BALL_DIA / 2.0, offset)


def outer_ring_volume() -> float:
    area, centroid = _groove_segment()
    annulus = math.pi / 4.0 * (OD**2 - OUTER_LAND_DIA**2) * WIDTH
    groove = 2.0 * math.pi * (PITCH_DIA / 2.0 + centroid) * area
    return annulus - groove - 2.0 * _chamfer_ring(OD / 2.0, 1.0)


def inner_ring_volume() -> float:
    area, centroid = _groove_segment()
    annulus = math.pi / 4.0 * (INNER_LAND_DIA**2 - BORE**2) * WIDTH
    groove = 2.0 * math.pi * (PITCH_DIA / 2.0 - centroid) * area
    return annulus - groove - 2.0 * _chamfer_ring(BORE / 2.0, -1.0)


def seal_volume() -> float:
    r_in, r_out = INNER_LAND_DIA / 2.0, OUTER_LAND_DIA / 2.0
    r_crown, r_lip = SEAL_CROWN_DIA / 2.0, SEAL_LIP_DIA / 2.0
    rise = SEAL_WEB_RECESS - SEAL_LIP_RECESS
    block = math.pi * (r_out**2 - r_in**2) * (seal_inner_recess() - SEAL_LIP_RECESS)
    web_notch = math.pi * (r_lip**2 - r_crown**2) * rise
    crown_r = seal_crown_radius()
    bulge, _ = _segment(crown_r, crown_r - rise)
    crown_mid = (r_in + r_crown) / 2.0  # the notch and the bulge are symmetric about it
    crown_notch = 2.0 * math.pi * crown_mid * ((r_crown - r_in) * rise - bulge)
    return block - web_notch - crown_notch


def ball_volume() -> float:
    return math.pi * BALL_DIA**3 / 6.0


def total_volume() -> float:
    return (
        outer_ring_volume()
        + inner_ring_volume()
        + 2.0 * seal_volume()
        + BALL_COUNT * ball_volume()
    )
