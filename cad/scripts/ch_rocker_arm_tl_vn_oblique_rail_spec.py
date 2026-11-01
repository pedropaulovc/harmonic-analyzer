r"""Pure-data envelope of the purchased HIWIN HGR15R rail, cut to 440 (MHA-CH-06-TL-VN-50).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_vn_oblique_rail`` extrudes ``SECTION`` and cuts
the seven counterbored holes, and the carriage spec reads ``SECTION`` for its
running clearance.

Two rails, one per base bar (MHA-CH-06-TL-20), each carrying one HGH15CA
carriage (MHA-CH-06-TL-VN-51). Shop inventory ``fixtures.trammel-hgr15-rails``:
Motion Constrained part 172270559990 (HIWIN HGR15R, any length; the 440 cut
and its hole pattern are a special order, confirmed on the vendor quote).

VENDOR-CHECKED. The first pass was datasheet-built: no vendor CAD obtained
(HIWIN's CAD download needs a member login and CAPTCHA, 2026-10-17). The user
then downloaded HIWIN's own model through his logged-in session:
``HGR15R440C_GW202610023056.stp`` (HIWIN configurator, HG Series > Rail,
HGR15R440C, downloaded 2026-10-17 ~03:55 UTC; sha256 ``VENDOR_STEP_SHA256``;
local only at ``C:/src/dt-logs/trammel-bought/vendor-cad/HGR15R.step``, never
committed). FreeCAD 1.1.4 harvest: volume 81085.4038 mm^3, one solid,
bbox 440 x 15 x 15; profile read from its analytic faces
(``vendor-cad/HGR15R.dims.md``).

Source of each number:

- VENDOR STEP (HGR15R.dims.md, read 2026-10-17): the end-face profile
  ``VENDOR_HALF_PROFILE`` (flats, 45 deg flanks and chamfers, the R1.62
  raceway grooves ``GROOVE_*``, the R1 lower blend), the hole Ø4.5, the
  counterbore Ø7.5 x 5.3, and ``VENDOR_VOLUME_MM3``. The vendor model is
  HIWIN's standard drilling for a 440 rail, 8 holes at E 10
  (``VENDOR_HOLE_COUNT``, ``VENDOR_HOLE_END``); ours is the calculator's
  special-order 7 holes at E 40 on the same 60 pitch and hole geometry.
- SOURCED: HIWIN "Linear Guideway Technical Information", catalogue
  G99TE23-2203, https://www.hiwin.com/wp-content/uploads/Linear_Guideway-E-1.pdf
  (read 2026-10-16; sha256 9ded6606...b800733103). Section 2-1-13 (1)
  "HGH-CA / HGH-HA", printed page 38, row HGH15CA, rail columns:
  WR 15, HR 15, D 7.5, h 5.3, d 4.5, P 60, E 20, rail bolt M4x16, rail
  weight 1.45 kg/m (``MASS_KG_PER_M``). Table 2-1-24 (printed page 37), row
  HG15: shoulder height beside the rail E1 3, shoulder fillet r1 0.5 max.
  The vendor STEP agrees with every catalogue rail dimension.
- FROM THE CALCULATOR (imported, ``ch_rocker_arm_tl_oblique_trammel_spec``):
  ``RAIL_LENGTH`` 440, ``RAIL_WIDTH`` 15, ``RAIL_HEIGHT`` 15,
  ``RAIL_HOLE_PITCH`` 60, ``RAIL_HOLE_COUNT`` 7, ``RAIL_HOLE_END`` 40, and
  ``RAIL_SCREW_SEAT_ABOVE_BASE`` 9.7 (the counterbore floor, so
  ``CBORE_DEPTH`` = 15 - 9.7 = the vendor's 5.3). The registry quantity 2
  is C4's ``ch_rocker_arm_tl_oblique_fasteners_spec.RAILS`` (asserted by
  the test, not imported here, so the fastener table may import this spec
  without a cycle).

Modelling departures from the vendor solid, each closed-form in
``GROOVE_FILL_MM2`` or bounded by ``VENDOR_VOLUME_ALLOWANCE_MM3``:

- Each R1.62 raceway groove (two per side) is spanned by its chord, which
  fills the groove's circular segment; the R1 lower blend is cut by its
  chord, which removes its segment. ``GROOVE_FILL_MM2`` is the net, 1.522
  mm^2 of section, 670 mm^3 over the length. The carriage channel never
  reaches into a groove, so the fill changes no clearance.
- Ten R0.4 edge blends are replaced by chords and the 0.1 deep HIWIN logo
  engraved on the top face is omitted; with the dims' 3-decimal rounding
  these stay inside ``VENDOR_VOLUME_ALLOWANCE_MM3`` (44 mm^3, ten segments
  under 0.01 mm^2 each; measured residual 5.4 mm^3).
- The holes follow the calculator's 7 / E 40, not the vendor model's
  8 / E 10: ``VENDOR_EQUIVALENT_VOLUME_MM3`` adds the eighth hole back.

Part frame (CONTRACT.md, the jig assembly mates on the default planes):
origin at one end face, on the bottom (seat) face, on the rail centreline;
+X along the 440 length, +Z up (height 15), Y across. Front (XY) is the seat
face, Top (XZ) the centre plane, Right (YZ) the end face. Holes at
``RAIL_HOLE_END + k * RAIL_HOLE_PITCH``. ``SECTION`` lists (y, z) vertices
of the end-face section, counter-clockwise seen from +X. The vendor STEP's
own frame is centred on the length with +Y up from the top face (y 0 top,
-15 seat) and Z across; ``_vendor_to_part`` maps it.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_oblique_trammel_spec as trammel

SUPPLIER = "Motion Constrained"
SKU = "172270559990"  # Motion Constrained part: HIWIN HGR15R rail, cut to length
MAKER_PART = "HGR15R440C"  # HIWIN order code: size 15, R (top mount), 440, C normal
MATERIAL = "Alloy Steel"  # SOLIDWORKS library steel for the hardened rail

# --- Calculator (imported) -------------------------------------------------------
LENGTH = trammel.RAIL_LENGTH  # 440
WIDTH = trammel.RAIL_WIDTH  # WR 15
HEIGHT = trammel.RAIL_HEIGHT  # HR 15
HOLE_PITCH = trammel.RAIL_HOLE_PITCH  # P 60
HOLE_COUNT = trammel.RAIL_HOLE_COUNT  # 7
HOLE_END = trammel.RAIL_HOLE_END  # 40, special order
HOLE_X: tuple[float, ...] = tuple(HOLE_END + k * HOLE_PITCH for k in range(HOLE_COUNT))
CBORE_DEPTH = HEIGHT - trammel.RAIL_SCREW_SEAT_ABOVE_BASE  # h 5.3

# --- Catalogue (SOURCED, G99TE23-2203) ----------------------------------------------
HOLE_DIA = 4.5  # d, through (vendor STEP R2.25)
CBORE_DIA = 7.5  # D (vendor STEP R3.75)
CATALOGUE_CBORE_DEPTH = 5.3  # h (vendor STEP floor 5.3 below the top)
MASS_KG_PER_M = 1.45
SHOULDER_BESIDE_RAIL = 3.0  # E1, Table 2-1-24
SHOULDER_FILLET_MAX = 0.5  # r1, Table 2-1-24

# --- Vendor STEP (HGR15R440C_GW202610023056.stp, HGR15R.dims.md) -------------------
VENDOR_STEP = "HGR15R440C_GW202610023056.stp"
VENDOR_STEP_SHA256 = "7c56abc87b2b76ec2e70b497ca0ed7b16542f92ef32f59b12f9e6583caa1af95"
VENDOR_DOWNLOADED = "2026-10-17"
VENDOR_VOLUME_MM3 = 81085.4038  # FreeCAD harvest, 8 holes, logo engraved
VENDOR_HOLE_COUNT = 8
VENDOR_HOLE_END = 10.0
# Raceway grooves: radius, and each centre as (across, from the top face).
GROOVE_RADIUS = 1.62
UPPER_GROOVE_CENTRE = (6.923, -0.064)
LOWER_GROOVE_CENTRE = (6.923, -6.365)
UPPER_GROOVE_SPAN = (-0.381, -1.671)  # its arc's end heights
LOWER_GROOVE_SPAN = (-6.059, -4.756)
LOWER_BLEND_RADIUS = 1.0  # flank into the lower side flat
# The upper chamfer under the neck: the plane across = 11.489 + height.
NECK_CHAMFER_OFFSET = 11.489


def _groove_across(centre: tuple[float, float], height: float) -> float:
    """Across-coordinate of a point at ``height`` on a groove arc (the arc's
    material side, toward the rail axis)."""
    cz, cy = centre
    return cz - math.sqrt(GROOVE_RADIUS**2 - (height - cy) ** 2)


# +side profile in the vendor frame, (across, height below the top face),
# from the seat corner up to the top face. Groove arcs and blends run between
# consecutive points as chords.
VENDOR_HALF_PROFILE: tuple[tuple[float, float], ...] = (
    (6.8, -15.0),  # seat flat end; 0.7 x 45 deg foot chamfer
    (7.5, -14.3),
    (7.5, -11.757),  # lower side flat top, R1 blend tangent
    (7.207, -11.05),  # R1 blend tangent on the 45 deg lower flank
    (4.887, -8.73),
    (4.77, -8.447),  # neck flat (R0.4 blends each end)
    (4.77, -6.885),
    (4.887, -6.602),  # 45 deg chamfer under the lower groove
    (NECK_CHAMFER_OFFSET - 6.267, -6.267),
    (_groove_across(LOWER_GROOVE_CENTRE, LOWER_GROOVE_SPAN[0]), LOWER_GROOVE_SPAN[0]),
    (_groove_across(LOWER_GROOVE_CENTRE, LOWER_GROOVE_SPAN[1]), LOWER_GROOVE_SPAN[1]),
    (7.5, -3.989),  # upper side flat
    (7.5, -2.451),
    (_groove_across(UPPER_GROOVE_CENTRE, UPPER_GROOVE_SPAN[1]), UPPER_GROOVE_SPAN[1]),
    (_groove_across(UPPER_GROOVE_CENTRE, UPPER_GROOVE_SPAN[0]), UPPER_GROOVE_SPAN[0]),
    (5.225, -0.176),  # top edge chamfer
    (5.049, 0.0),  # top flat, 10.10 wide
)


def _vendor_to_part(across: float, height: float) -> tuple[float, float]:
    """Vendor (across, y from the top face) to the part's (y, z)."""
    return round(across, 9), round(HEIGHT + height, 9)


_HALF = tuple(_vendor_to_part(a, h) for a, h in VENDOR_HALF_PROFILE)
# (y, z) end-face section, counter-clockwise seen from +X: the +Y half up
# from the seat, then its mirror back down the -Y side.
SECTION: tuple[tuple[float, float], ...] = _HALF + tuple(
    (-y, z) for y, z in reversed(_HALF)
)


def polygon_area_centroid(
    points: tuple[tuple[float, float], ...],
) -> tuple[float, float, float]:
    """Shoelace area (mm^2, positive counter-clockwise) and centroid (y, z)
    (mm) of a closed (y, z) polygon."""
    area = moment_y = moment_z = 0.0
    for (y0, z0), (y1, z1) in zip(points, points[1:] + points[:1]):
        cross = y0 * z1 - y1 * z0
        area += cross
        moment_y += (y0 + y1) * cross
        moment_z += (z0 + z1) * cross
    area /= 2.0
    return area, moment_y / (6.0 * area), moment_z / (6.0 * area)


def clip_above(
    points: tuple[tuple[float, float], ...], z: float
) -> tuple[tuple[float, float], ...]:
    """The part of a closed (y, z) polygon at or above height ``z``
    (Sutherland-Hodgman against one half-plane; order is kept)."""
    out: list[tuple[float, float]] = []
    for a, b in zip(points, points[1:] + points[:1]):
        a_in, b_in = a[1] >= z, b[1] >= z
        if a_in:
            out.append(a)
        if a_in != b_in:
            t = (z - a[1]) / (b[1] - a[1])
            out.append((a[0] + t * (b[0] - a[0]), z))
    return tuple(out)


SECTION_AREA, _, SECTION_CENTROID_Z = polygon_area_centroid(SECTION)


def circular_segment_area(
    p: tuple[float, float], q: tuple[float, float], radius: float
) -> float:
    """Area between chord ``pq`` and its minor arc of ``radius``."""
    theta = 2.0 * math.asin(math.dist(p, q) / (2.0 * radius))
    return radius**2 / 2.0 * (theta - math.sin(theta))


_P = VENDOR_HALF_PROFILE
# Both sides: the four groove chords fill their segments (all above the
# carriage underside), the two R1 blend chords cut theirs away (below it).
GROOVE_SEGMENTS_MM2 = 2.0 * (
    circular_segment_area(_P[9], _P[10], GROOVE_RADIUS)
    + circular_segment_area(_P[13], _P[14], GROOVE_RADIUS)
)
LOWER_BLEND_SEGMENTS_MM2 = 2.0 * circular_segment_area(_P[2], _P[3], LOWER_BLEND_RADIUS)
GROOVE_FILL_MM2 = GROOVE_SEGMENTS_MM2 - LOWER_BLEND_SEGMENTS_MM2

# The through hole runs from the seat to the counterbore floor, the
# counterbore from there to the top.
V_ONE_HOLE = math.pi * (HOLE_DIA / 2.0) ** 2 * (HEIGHT - CBORE_DEPTH)
V_ONE_CBORE = math.pi * (CBORE_DIA / 2.0) ** 2 * CBORE_DEPTH
V_PRISM = SECTION_AREA * LENGTH
V_HOLES = HOLE_COUNT * V_ONE_HOLE
V_CBORES = HOLE_COUNT * V_ONE_CBORE
VOLUME_MM3 = V_PRISM - V_HOLES - V_CBORES
# The vendor solid re-drilled to our 7 holes, and what the chords add to it.
VENDOR_EQUIVALENT_VOLUME_MM3 = VENDOR_VOLUME_MM3 + (VENDOR_HOLE_COUNT - HOLE_COUNT) * (
    V_ONE_HOLE + V_ONE_CBORE
)
# Ten R0.4 blend chords (each segment under 0.01 mm^2 at these spans), the
# 0.1 deep top-face logo, and the dims' 3-decimal rounding.
VENDOR_VOLUME_ALLOWANCE_MM3 = 0.1 * LENGTH
# The holes sit symmetric about mid-length, so the centroid stays at x = L/2.
CENTROID = (
    LENGTH / 2.0,
    0.0,
    (
        V_PRISM * SECTION_CENTROID_Z
        - V_HOLES * (HEIGHT - CBORE_DEPTH) / 2.0
        - V_CBORES * (HEIGHT - CBORE_DEPTH / 2.0)
    )
    / VOLUME_MM3,
)
# The native volume is exact closed form; the tolerance only absorbs the
# mass-property evaluation (well under one through hole, 154 mm^3).
VOLUME_TOL_MM3 = 5e-4 * VOLUME_MM3

# The special order's receipt check: the received rail must land on the
# TL-20 base bar's tapped holes. The print states it as native model
# dimensions on the hole face, parenthesised as reference (the rail is used
# as supplied): the cut length is the Rail extrusion's depth, and the hole
# sketch places the first hole from the -X end face and each next one a
# pitch on from the one before, so one pitch prints for all of them.
DRAWING_DIMENSIONS = {
    "Rail": {"Length"},
    "BoltHoleProfile": {"HoleEnd", "HolePitch"},
}
# Whole millimetres: the order's own values.
DRAWING_PRECISION = {
    feature: dict.fromkeys(names, 0) for feature, names in DRAWING_DIMENSIONS.items()
}
# The one printed pitch stands for every gap between the holes.
HOLE_PITCH_CALLOUT = f"{HOLE_COUNT - 1}X"
# The pattern suits the base bar's rail taps: its drawing number and name
# (machinist review mr1: a bare "TL-20" named no drawing).
DRAWING_NOTES = (
    "SPECIAL ORDER CUT LENGTH AND HOLE PATTERN, TO SUIT MHA-CH-06-TL-20 BASE BAR."
)
if abs(LENGTH - (2.0 * HOLE_END + (HOLE_COUNT - 1) * HOLE_PITCH)) > 1e-9:
    raise AssertionError("the rail's hole pattern is not symmetric on its length")
