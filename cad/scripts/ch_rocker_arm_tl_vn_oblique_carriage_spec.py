r"""Pure-data envelope of the purchased HIWIN HGH15CA Z0 carriage (MHA-CH-06-TL-VN-51).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_vn_oblique_carriage`` extrudes ``CAP_OUTLINE``
over the length over the seals and ``BODY_OUTLINE`` over the steel body, cuts
the rail ``CHANNEL`` through, cuts the four M4 bores, and adds the grease
nipple and the opposite end's port plug.

Two carriages, one on each HGR15R rail (MHA-CH-06-TL-VN-50), each carrying a
pivot block (MHA-CH-06-TL-22) on its four M4 holes. Shop inventory
``fixtures.trammel-hgh15ca-carriages``: HIWIN HGH-15-CA-Z0-C, DigiKey
Marketplace / Midwest Machine Tool Supply 4433-HGH-15-CA-Z0-C.

VENDOR-CHECKED. The first pass was datasheet-built: no vendor CAD obtained
(HIWIN's CAD download needs a member login and CAPTCHA, 2026-10-17). The user
then downloaded HIWIN's own model through his logged-in session:
``HGH15CAZ0C_GW202610023079.stp`` (HIWIN configurator, HG Series > Block,
HGH15CAZ0C with the M4x0.7 grease nipple, downloaded 2026-10-17 ~04:10 UTC;
sha256 ``VENDOR_STEP_SHA256``; local only at
``C:/src/dt-logs/trammel-bought/vendor-cad/HGH15CA.step``, never committed).
FreeCAD 1.1.4 harvest: 7 solids (steel body, two end caps, two end seals,
grease nipple, port plug), 36856.0037 mm^3 (``vendor-cad/HGH15CA.dims.md``,
``HGH15CA.harvest.json`` ``per_solid``).

Source of each number:

- VENDOR STEP (read 2026-10-17): ``BODY_OUTLINE`` (34 wide; the 1 x 45 deg
  top and 1.3 x 45 deg bottom chamfers; the two 0.5 deep top grooves; the
  0.3 relief on the -Y reference side), ``CAP_OUTLINE`` (end caps and seals
  share it: 32.4 wide, offset 0.043 to +Y, top 24.174), ``CAP_LENGTH``
  (8 cap + 3 seal), the channel (HIWIN models it as the rail's own profile,
  raceway arcs on the rail's centres), the bores Ø3.242 x 5 with a 118 deg
  drill point (``DRILL_POINT_HALF_ANGLE``), the nipple (Ø6 ball head,
  ``NIPPLE_PROUD`` 6.66 beyond the seal on the axis 5.05 above the rail
  top) and the opposite port's plug (Ø7.51 head, ``PLUG_PROUD`` 1.7), and
  the per-solid ``VENDOR_*_VOLUME_MM3``.
- SOURCED: HIWIN "Linear Guideway Technical Information", catalogue
  G99TE23-2203, https://www.hiwin.com/wp-content/uploads/Linear_Guideway-E-1.pdf
  (read 2026-10-16; sha256 9ded6606...b800733103). Section 2-1-13 (1)
  "HGH-CA / HGH-HA", printed page 38, row HGH15CA: H 28, H1 4.3, N 9.5,
  W 34, B 26, C 26, L1 39.4 (``BODY_LENGTH``), L 61.4, K1 10, K2 4.85, G 5.3
  (``CATALOGUE_NIPPLE_PROUD``), M x l M4 x 5, T 6, H2 7.95
  (``NIPPLE_BELOW_TOP``), H3 7.7, C 14.7 kN, C0 23.47 kN, block 0.18 kg
  (``MASS_KG``). Section 2-1-7 (printed page 29): HG15 grease nipple
  M4x0.7P, part no. 34310002. Table 2-1-17 (printed page 34): HG15 end seal
  t1 3. The vendor STEP agrees with every catalogue value except G: its
  nipple stands 6.66 proud, not 5.3 (the vendor envelope governs).
- FROM THE CALCULATOR (imported, ``ch_rocker_arm_tl_oblique_trammel_spec``):
  ``CARRIAGE_HEIGHT`` 28 (H, the mounting face above the rail seat),
  ``CARRIAGE_UNDER`` 4.3 (H1, the underside), ``CARRIAGE_WIDTH`` 34 (W),
  ``CARRIAGE_LENGTH`` 61.4 (L), ``CARRIAGE_BOLT_SPAN`` (26, 26) (C, B),
  ``CARRIAGE_BOLT`` "M4". From ``ch_rocker_arm_tl_oblique_pivot_block_spec``:
  ``CARRIAGE_THREAD_DEPTH`` 5 (the l of M4 x 5). From
  ``ch_rocker_arm_tl_vn_oblique_rail_spec``: the rail ``SECTION``, its height
  and the polygon helpers. The vendor STEP agrees with every one of these.
  The registry quantity 2 is C4's
  ``ch_rocker_arm_tl_oblique_fasteners_spec.RAILS`` (asserted by the test).
- DERIVED: ``BORE_DIA`` 3.242, the ISO 68-1 basic minor diameter of M4x0.7
  (D1 = D - 1.082532 P), which is also the vendor's modelled bore. M4 is
  not in ``_hole_spec.TAP_DRILL_MM`` and the hole wizard here is ANSI-inch
  only, so each M4 x 5 hole is a plain flat-bottomed bore at the thread
  minor diameter (CONTRACT.md modelling rule), not a wizard tapped hole.
- MODELLING (not a product value): ``CHANNEL_CLEARANCE`` 0.1. HIWIN's model
  puts the block's channel exactly on the rail's faces (balls omitted);
  the channel here is the modelled rail section offset 0.1 outward, so the
  jig's native interference check sees a true gap instead of coincident
  faces. HIWIN publishes no running clearance.

Modelling departures from the vendor solids, each closed-form or bounded:

- Channel: the 0.1 offset of the rail's chord polygon, against HIWIN's exact
  rail profile; ``CHANNEL_EXCESS_MM2`` (closed form) over the length.
- Bores flat-bottomed: the four 118 deg drill points
  (``V_DRILL_POINTS``) stay solid.
- End caps and seals are solid prisms of ``CAP_OUTLINE``: their lube
  passages, ports, recirculation turnarounds and seal lips stay solid,
  ``CAP_INTERNAL_MM3`` (measured from the vendor per-solid volumes, about
  7 % of the cap and seal volume).
- Nipple and plug are cylinder envelopes of their outside parts (the
  vendor's hex, ball head and domed plug inside them); their shanks in
  the end ports are not separate.
- One body in "Alloy Steel": the native mass overstates the catalogue
  0.18 kg because the plastic caps count as steel; the steel body alone is
  26.0 cm^3, 200 g at 7.7 g/cm^3.

Part frame (CONTRACT.md, the jig assembly mates on the default planes):
origin at mid-length, on the rail centreline, at the rail seat level (the
carriage's z 0 is the rail's z 0); +X along the rail, +Z up, Y across.
Mounting face at z ``MOUNTING_FACE_Z`` 28, underside at ``UNDERSIDE_Z`` 4.3,
the four M4 bores at (+-13, +-13). Front (XY) is the rail seat level, Top
(XZ) the centre plane, Right (YZ) the mid-length plane, so the carriage's
Right to the rail's Right is the free slide. The vendor STEP's frame is
centred on the length with y 0 on the rail top: part z = vendor y + 15,
part Y = vendor Z. HIWIN fits the nipple on its -X end by default; the
port is the same at both ends, and here it sits on the +X end:
``ch_rocker_arm_tl_oblique_pivot_block_spec`` puts +X away from the
spindle and the pivot block overhangs the -X end (X -50), so +X is the
reachable end. Sections list (y, z) vertices, counter-clockwise seen from
+X.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_vn_oblique_rail_spec as rail
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from ch_rocker_arm_tl_oblique_pivot_block_spec import CARRIAGE_THREAD_DEPTH
from ch_rocker_arm_tl_vn_oblique_rail_spec import clip_above, polygon_area_centroid

SUPPLIER = "DigiKey Marketplace (Midwest Machine Tool Supply)"
SKU = "HGH-15-CA-Z0-C"  # Midwest part; DigiKey 4433-HGH-15-CA-Z0-C
MAKER_PART = "HGH15CAZ0C"  # HIWIN order code: HG, H square, 15, C heavy, A top, Z0
MATERIAL = "Alloy Steel"  # SOLIDWORKS library steel for the hardened block

# --- Calculator (imported) -------------------------------------------------------
MOUNTING_FACE_Z = trammel.CARRIAGE_HEIGHT  # H 28
UNDERSIDE_Z = trammel.CARRIAGE_UNDER  # H1 4.3
WIDTH = trammel.CARRIAGE_WIDTH  # W 34
LENGTH = trammel.CARRIAGE_LENGTH  # L 61.4, over the end seals
BOLT_X = trammel.CARRIAGE_BOLT_SPAN[0] / 2.0  # C/2 13, along
BOLT_Y = trammel.CARRIAGE_BOLT_SPAN[1] / 2.0  # B/2 13, across
BOLT_POINTS: tuple[tuple[float, float], ...] = tuple(
    (sx * BOLT_X, sy * BOLT_Y) for sx in (-1, 1) for sy in (-1, 1)
)
if trammel.CARRIAGE_BOLT != "M4":
    raise AssertionError("the carriage is no longer M4: revisit BORE_DIA")
BORE_DEPTH = CARRIAGE_THREAD_DEPTH  # l of M4 x 5

# --- Catalogue (SOURCED, G99TE23-2203) ----------------------------------------------
BODY_LENGTH = 39.4  # L1, steel body
CATALOGUE_NIPPLE_PROUD = 5.3  # G; the vendor model's nipple stands 6.66
NIPPLE_BELOW_TOP = 7.95  # H2, block top to the nipple axis
THREAD_MAJOR = 4.0  # M4
THREAD_PITCH = 0.7  # M4x0.7 (coarse), also the HG15 nipple thread
RAIL_SIDE_TO_BLOCK_SIDE = 9.5  # N
END_SEAL_THICK = 3.0  # t1, Table 2-1-17
LOAD_C_KN = 14.7
LOAD_C0_KN = 23.47
MASS_KG = 0.18

# --- Vendor STEP (HGH15CAZ0C_GW202610023079.stp, HGH15CA.dims.md) -------------------
VENDOR_STEP = "HGH15CAZ0C_GW202610023079.stp"
VENDOR_STEP_SHA256 = "ae98aba826779b0ed633593b809734ba738473c0786e78092a6ef3f5b7e448ea"
VENDOR_DOWNLOADED = "2026-10-17"
VENDOR_VOLUME_MM3 = 36856.0037  # all 7 solids
VENDOR_BODY_VOLUME_MM3 = 26020.9973
VENDOR_CAP_VOLUME_MM3 = 3826.3593  # each end
VENDOR_SEAL_VOLUME_MM3 = 1462.2354  # each end
VENDOR_NIPPLE_VOLUME_MM3 = 199.5971
VENDOR_PLUG_VOLUME_MM3 = 58.2201
# Vendor-frame bounding box (x along, y up from the rail top, z across), mm:
# nipple tip at -37.36, plug dome at +32.4.
VENDOR_BBOX_MIN = (-37.36, -10.7, -17.0)
VENDOR_BBOX_MAX = (32.4, 13.0, 17.0)
END_CAP_THICK = 8.0
CAP_LENGTH = (LENGTH - BODY_LENGTH) / 2.0  # 11 = 8 cap + 3 seal, each end
DRILL_POINT_HALF_ANGLE = 59.0  # deg, 118 deg point
NIPPLE_DIA = 6.0  # ball head Ø6 (hex across corners 5.77 inside it)
NIPPLE_PROUD = 6.66  # tip beyond the seal face
PLUG_DIA = 7.52  # domed head, Ø7.513 bbox, rounded up
PLUG_PROUD = 1.7

# Steel body outline (y, z), counter-clockwise from the underside's -Y corner.
BODY_OUTLINE: tuple[tuple[float, float], ...] = (
    (-15.7, UNDERSIDE_Z),
    (15.7, UNDERSIDE_Z),
    (17.0, 5.6),  # 1.3 x 45 deg bottom chamfer
    (17.0, 27.0),
    (16.0, MOUNTING_FACE_Z),  # 1 x 45 deg top chamfer
    (9.0, MOUNTING_FACE_Z),
    (8.5, 27.5),  # top groove, 0.5 deep, 45 deg sides
    (3.5, 27.5),
    (3.0, MOUNTING_FACE_Z),
    (-3.0, MOUNTING_FACE_Z),
    (-3.5, 27.5),
    (-8.5, 27.5),
    (-9.0, MOUNTING_FACE_Z),
    (-16.0, MOUNTING_FACE_Z),
    (-17.0, 27.0),
    (-17.0, 22.0),
    (-16.7, 21.7),  # 0.3 reference-side relief down to the bottom chamfer
    (-16.7, 5.3),
)
# End cap and seal outline, the same order.
END_CAP_TOP_Z = 24.174
CAP_OUTLINE: tuple[tuple[float, float], ...] = (
    (-15.131, UNDERSIDE_Z),
    (15.217, UNDERSIDE_Z),
    (16.243, 5.326),
    (16.243, END_CAP_TOP_Z - 1.0),
    (15.243, END_CAP_TOP_Z),
    (-15.157, END_CAP_TOP_Z),
    (-16.157, END_CAP_TOP_Z - 1.0),
    (-16.157, 5.326),
)

# --- Modelling ------------------------------------------------------------------
CHANNEL_CLEARANCE = 0.1
# The channel cut's floor, in the air under the underside, so its bottom
# edge never lies on a face.
CHANNEL_FLOOR_Z = 3.0


def offset_polygon(
    points: tuple[tuple[float, float], ...], distance: float
) -> tuple[tuple[float, float], ...]:
    """Mitred outward offset of a counter-clockwise polygon: each edge moves
    ``distance`` along its outward normal, each vertex to where its two moved
    edges meet."""

    def normal(p: tuple[float, float], q: tuple[float, float]) -> tuple[float, float]:
        length = math.dist(p, q)
        return (q[1] - p[1]) / length, (p[0] - q[0]) / length

    out = []
    for i, p in enumerate(points):
        a = normal(points[i - 1], p)
        b = normal(p, points[(i + 1) % len(points)])
        k = distance / (1.0 + a[0] * b[0] + a[1] * b[1])
        out.append(
            (round(p[0] + k * (a[0] + b[0]), 9), round(p[1] + k * (a[1] + b[1]), 9))
        )
    return tuple(out)


_RAIL_OFFSET = offset_polygon(rail.SECTION, CHANNEL_CLEARANCE)
# The cut profile, closed below the underside.
CHANNEL = clip_above(_RAIL_OFFSET, CHANNEL_FLOOR_Z)
# The part of it that removes material: above the underside.
CHANNEL_IN_BLOCK = clip_above(_RAIL_OFFSET, UNDERSIDE_Z)


def _material_section(
    outline: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
    """``outline`` (starting with its underside edge) less the channel, as one
    closed polygon: around the outline from the underside's +Y corner, then up
    the channel's -Y side, across its roof and down its +Y side."""
    return outline[1:] + outline[:1] + tuple(reversed(CHANNEL_IN_BLOCK))


BODY_SECTION = _material_section(BODY_OUTLINE)
CAP_SECTION = _material_section(CAP_OUTLINE)

# --- Derived --------------------------------------------------------------------
BORE_DIA = round(THREAD_MAJOR - 1.082532 * THREAD_PITCH, 3)  # ISO 68-1 D1, 3.242
NIPPLE_Z = MOUNTING_FACE_Z - NIPPLE_BELOW_TOP  # 20.05, vendor 5.05 above the rail top
NIPPLE_END = 1  # +X end; the plug closes the -X port
NIPPLE_FACE_X = NIPPLE_END * LENGTH / 2.0
PLUG_FACE_X = -NIPPLE_FACE_X

# --- Volume and centroid (closed form) --------------------------------------------------
A_CAP_OUTLINE, Y_CAP_OUTLINE, Z_CAP_OUTLINE = polygon_area_centroid(CAP_OUTLINE)
A_BODY_OUTLINE, Y_BODY_OUTLINE, Z_BODY_OUTLINE = polygon_area_centroid(BODY_OUTLINE)
A_CHANNEL, _, Z_CHANNEL = polygon_area_centroid(CHANNEL_IN_BLOCK)
V_CAPS = A_CAP_OUTLINE * LENGTH  # the cap prism, mid-plane over L
V_BODY_EXTRA = (A_BODY_OUTLINE - A_CAP_OUTLINE) * BODY_LENGTH  # CAP_OUTLINE lies inside
V_CHANNEL = A_CHANNEL * LENGTH
V_ONE_BORE = math.pi * (BORE_DIA / 2.0) ** 2 * BORE_DEPTH
V_BORES = len(BOLT_POINTS) * V_ONE_BORE
V_NIPPLE = math.pi * (NIPPLE_DIA / 2.0) ** 2 * NIPPLE_PROUD
V_PLUG = math.pi * (PLUG_DIA / 2.0) ** 2 * PLUG_PROUD
VOLUME_MM3 = V_CAPS + V_BODY_EXTRA - V_CHANNEL - V_BORES + V_NIPPLE + V_PLUG
CENTROID = (
    (
        V_NIPPLE * (NIPPLE_FACE_X + NIPPLE_END * NIPPLE_PROUD / 2.0)
        + V_PLUG * (PLUG_FACE_X - NIPPLE_END * PLUG_PROUD / 2.0)
    )
    / VOLUME_MM3,
    (
        V_CAPS * Y_CAP_OUTLINE
        + (A_BODY_OUTLINE * Y_BODY_OUTLINE - A_CAP_OUTLINE * Y_CAP_OUTLINE)
        * BODY_LENGTH
    )
    / VOLUME_MM3,  # the channel and bores are symmetric in Y
    (
        V_CAPS * Z_CAP_OUTLINE
        + (A_BODY_OUTLINE * Z_BODY_OUTLINE - A_CAP_OUTLINE * Z_CAP_OUTLINE)
        * BODY_LENGTH
        - V_CHANNEL * Z_CHANNEL
        - V_BORES * (MOUNTING_FACE_Z - BORE_DEPTH / 2.0)
        + (V_NIPPLE + V_PLUG) * NIPPLE_Z
    )
    / VOLUME_MM3,
)
# Exact closed form; the tolerance only absorbs the mass-property evaluation
# (well under one M4 bore, 41 mm^3).
VOLUME_TOL_MM3 = 5e-4 * VOLUME_MM3

# --- Against the vendor solids ------------------------------------------------------
# HIWIN's channel is the rail's true profile above the underside: the chord
# polygon less its groove segments (all four grooves lie above the underside).
VENDOR_CHANNEL_MM2 = (
    polygon_area_centroid(clip_above(rail.SECTION, UNDERSIDE_Z))[0]
    - rail.GROOVE_SEGMENTS_MM2
)
CHANNEL_EXCESS_MM2 = A_CHANNEL - VENDOR_CHANNEL_MM2
_R_BORE = BORE_DIA / 2.0
V_DRILL_POINTS = len(BOLT_POINTS) * (
    math.pi
    * _R_BORE**2
    * (_R_BORE / math.tan(math.radians(DRILL_POINT_HALF_ANGLE)))
    / 3.0
)
# The steel body as HIWIN models it, from this outline: the residual against
# VENDOR_BODY_VOLUME_MM3 is the channel's eight R0.4 blend chords (each
# segment under 0.01 mm^2).
VENDOR_BODY_MODEL_MM3 = (
    (A_BODY_OUTLINE - VENDOR_CHANNEL_MM2) * BODY_LENGTH - V_BORES - V_DRILL_POINTS
)
VENDOR_BODY_ALLOWANCE_MM3 = 0.1 * BODY_LENGTH
# Cap and seal internals (lube passages, ports, recirculation turnarounds,
# seal lips), solid in the model: the vendor caps' prism less their volume.
CAP_INTERNAL_MM3 = (A_CAP_OUTLINE - VENDOR_CHANNEL_MM2) * 2.0 * CAP_LENGTH - 2.0 * (
    VENDOR_CAP_VOLUME_MM3 + VENDOR_SEAL_VOLUME_MM3
)

# The note names the rail by its drawing number, read from the registry.
RAIL_NUMBER = _config.parts("ch-rocker-arm-tl-vn-oblique-rail")["number"]
DRAWING_NOTES = (
    f"MOUNT ON THE OBLIQUE TRAMMEL RAIL {RAIL_NUMBER}; GREASE THROUGH THE END NIPPLE."
)
