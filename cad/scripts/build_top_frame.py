r"""Reproduction script: top frame (ch. 19 close-ups + ch. 30 eight-views; 1 used).

The green cast frame capping the four columns: ONE casting carrying the rail
ring, the cross member the summing lever hangs from, and the gooseneck socket.

* **Webbed rails.** The rails are not slabs -- they are a cast I-section: a
  ~10 top flange and a ~5 bottom flange joined by a web recessed ~9 per face
  (ch. 19 p.44 close-ups show the recessed panel between two proud flange
  bands; the ch30 p008 side view resolves the same two steps on the outer face
  at y 1063.7 and 1036.0 against a 1073.7 top and 1032.7 bottom).
* **Rounded corners, not protruding bosses.** Each corner is a R17 quadrant
  centred on its column bore, tangent to both rail outer faces -- the ch30
  p002 front view reads the front-left corner as Ø34.2 centred at x 206.0 with
  its outer face at x 223.1. The corner pads drop 6 BELOW the rail underside
  (p008: ends bottom out at y 1025 vs the rail's 1032).
* **The cross member is cast in.** The former separate ``top-crossbar`` part
  is this casting's cross rib: it spans the window along Z at the summing-lever
  knife line, its TOP face flush with the rail top (ch30 p002 shows the
  knife-mount nut bearing on the frame's top face, no proud bar), and the
  knife-mount block hangs from its underside.
* **The gooseneck socket is cast in.** The former separate ``gooseneck-clamp``
  block does not exist: the counter-spring post passes through a Ø17 bore in a
  local full-section boss on the east rail's mid-span (the boss is what keeps
  the web recess from breaking into the bore), pinched by a square-head set
  screw threaded radially through the rail's outer face -- ch. 19 p.45's "a
  square-head screw pinches the post in its socket", and the screw is visibly
  IN the casting in ch19 page001_img04.

Stations come from ``machine/frame.yaml`` (the ch30 bundle solve): columns
(±203.8, ±117.5), casting top face y 1074.6, rail band 41 tall. See that file
for the measurement and for what it supersedes.

Layout: plan profile in XZ centred on the origin, rail band extruded both ways
in Y (y -20.5..+20.5) -- the assembly lifts the origin to 1054.1. Build order:
the two slabs + corner discs make the rounded-corner ring, the window cut opens
it, the recess cut carves the web band, THEN the cross rib / gooseneck boss go
back in at full section (so they refill the recess where they land), then the
pads, then every bore. The ring is z-symmetric and its x-asymmetric features
(cross rib, gooseneck socket) are authored machine-handed, so the Top-plane
(x, y) -> (X, -Z) mapping needs no handedness care.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_top_frame.py
"""

from __future__ import annotations

import math
import sys

import _config
from _common import (
    CASTING_GREEN,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import TAP_DRILL_MM
from top_frame_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FRONT_VIEW_NOTE,
    INSPECTION_NOTES,
    TOP_VIEW_NOTE,
)

PART_NAME = "top-frame"
MATERIAL = "Gray Cast Iron"  # green-painted casting like the base

# --- machine anchors (machine/frame.yaml, ch30 bundle solve) ----------------
COLUMN_X = float(_config.machine("frame", "column_x_mm"))  # 203.8
COLUMN_Z = float(_config.machine("frame", "column_z_mm"))  # 117.5
RING_HEIGHT = float(_config.machine("frame", "top_frame_height_mm"))  # 41.0
HALF_H = RING_HEIGHT / 2.0

# --- rail section ----------------------------------------------------------
RAIL_HALF = 17.0  # rail half-width = corner radius (ch30 p002 corner Ø34.2)
WEB_HALF = 8.0  # web half-thickness -> 9 recessed per face
TOP_FLANGE = 10.0  # ch30 p008 outer-face step at y 1063.7 vs top 1073.7
BOT_FLANGE = 5.0  # step at 1036.0 vs bottom 1032.7 (ch19 p.44 proportions)
WEB_HEIGHT = RING_HEIGHT - TOP_FLANGE - BOT_FLANGE  # 26
CORNER_LAND = 8.0  # full-section land left beyond each corner quadrant, so the
# recess strips stay clear of the pads (and of each other at the inner corner)
PAD_DROP = 6.0  # corner pads stand proud BELOW the rail underside (p008)

OUTER_X = COLUMN_X + RAIL_HALF  # 220.8
OUTER_Z = COLUMN_Z + RAIL_HALF  # 134.5
INNER_X = COLUMN_X - RAIL_HALF  # 186.8
INNER_Z = COLUMN_Z - RAIL_HALF  # 100.5
WEB_OUTER_X = COLUMN_X + WEB_HALF  # 211.8
WEB_INNER_X = COLUMN_X - WEB_HALF  # 195.8
WEB_OUTER_Z = COLUMN_Z + WEB_HALF  # 125.5
WEB_INNER_Z = COLUMN_Z - WEB_HALF  # 109.5
RECESS = RAIL_HALF - WEB_HALF  # 9: depth of the web recess, per face
RUN_X = COLUMN_X - RAIL_HALF - CORNER_LAND  # 178.8: recess run along the X rails
RUN_Z = COLUMN_Z - RAIL_HALF - CORNER_LAND  # 92.5: ... along the Z rails

# --- bores + cast-in features ----------------------------------------------
BORE_DIA = 25.5  # clamps the Ø25.4 column (0.1 slip; OD from the 8-views M6.11)
PAD_DIA = 2.0 * RAIL_HALF  # 34: corner pad = the corner quadrant, extended down

CROSSBAR_X = -15.0  # cross-rib centreline = the summing-lever knife line
# (build_summing_assembly.KNIFE[0]); the rib spans the window along Z and its
# ends run into the north/south rails.
CROSSBAR_HALF = 11.0  # 22 wide -- the ch30 p002 knife-mount stirrup straddles
# it with ~30 outside the legs.

GOOSENECK_X = -COLUMN_X  # counter-spring post on the east rail (summing places
# the gooseneck at -COLUMN_X); the bore is cut at part x -COLUMN_X so post and
# bore coincide. At +COLUMN_X the post would drill solid casting (M6.12).
GOOSENECK_Z = 0.0  # rail mid-span: the gooseneck is a planar bend in z 0
GOOSENECK_BORE_DIA = 17.0  # clearance for the Ø16 post sliding through
BOSS_HALF_Z = 17.0  # the socket boss keeps the FULL rail section over
# z ±17, so the Ø17 bore never breaks into the web recess (web is only 16 thick)
PASSAGE_DIA = TAP_DRILL_MM["1/4-20"]  # 5.105: square-head set screw, tapped
# radially through the outer face into the bore ("pinches the post in its
# socket", ch. 19 p.45). Cut at the tap drill so the native CAD carries the
# drawing's DRILL + TAP requirement, exactly as the retired clamp block did.
PASSAGE_Y = 0.0  # screw axis on the rail's mid-height plane

THROUGH = 2.0 * (RING_HEIGHT + PAD_DROP)  # mid-plane total for through cuts


def _ring_area(half_width: float) -> float:
    """Plan area of a uniform-width ring on the column stations with its outer
    corners rounded at the same radius.

    Outer = a 2(a+h) x 2(b+h) rectangle with R=h corners; inner = the plain
    2(a-h) x 2(b-h) rectangle, so the rounding is the only non-rectangular term.
    """
    h = half_width
    return 8.0 * h * (COLUMN_X + COLUMN_Z) - (4.0 - math.pi) * h * h


def _recess_area() -> float:
    """Plan area the web recess removes: two strips per rail, four rails."""
    return 4.0 * RECESS * (2.0 * RUN_X) + 4.0 * RECESS * (2.0 * RUN_Z)


# The eight recess strips (two faces x four rails) as
# (label, vertices, segment drives, anchor-x drive, anchor-z drive) in sketch
# coords. Vertex 0 is each strip's -x/-z corner, which is the one
# define_rectilinear_chain anchors; an anchor dim is a DISTANCE, so its
# expression is the absolute coordinate.
def _recess_strips() -> list[
    tuple[str, list[tuple[float, float]], list[str], str, str]
]:
    strips = []
    # rails running along X: strips span |x| <= RUN_X, RECESS deep in z
    for sz, rail in ((1.0, "N"), (-1.0, "S")):
        for lo_z, hi_z, face, near, far in (
            (WEB_OUTER_Z, OUTER_Z, "Out", "WebOuterZ", "OuterZ"),
            (INNER_Z, WEB_INNER_Z, "In", "InnerZ", "WebInnerZ"),
        ):
            lo, hi = sorted((sz * lo_z, sz * hi_z))
            strips.append((
                f"{rail}{face}",
                [(-RUN_X, lo), (RUN_X, lo), (RUN_X, hi), (-RUN_X, hi)],
                ['2 * "RunX"', '"Recess"'],
                '"RunX"',
                f'"{near if sz > 0 else far}"',
            ))
    # rails running along Z: strips span |z| <= RUN_Z, RECESS deep in x
    for sx, rail in ((1.0, "W"), (-1.0, "E")):
        for lo_x, hi_x, face, near, far in (
            (WEB_OUTER_X, OUTER_X, "Out", "WebOuterX", "OuterX"),
            (INNER_X, WEB_INNER_X, "In", "InnerX", "WebInnerX"),
        ):
            lo, hi = sorted((sx * lo_x, sx * hi_x))
            strips.append((
                f"{rail}{face}",
                [(lo, -RUN_Z), (hi, -RUN_Z), (hi, RUN_Z), (lo, RUN_Z)],
                ['"Recess"', '2 * "RunZ"'],
                f'"{near if sx > 0 else far}"',
                '"RunZ"',
            ))
    return strips


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs: named globals in the equation manager that drive every
    # dimension below. A GUI fine-tune edits THESE (Tools > Equations) -- e.g.
    # RailHalf or WebHalf -- never an auto "D7@Sketch3". The derived spans are
    # equations of the primitives, so the rail band, the web and the corner
    # pads stay concentric on the column stations when a primitive changes.
    # Primitives carry an explicit ``mm`` unit: this is an INCH document and the
    # equation manager evaluates BARE numbers in document units, so an
    # unsuffixed "203.8" would be read as inches and blow the part up 25.4x.
    await set_global(adapter, "ColumnX", f"{COLUMN_X}mm")
    await set_global(adapter, "ColumnZ", f"{COLUMN_Z}mm")
    await set_global(adapter, "RailHalf", f"{RAIL_HALF}mm")
    await set_global(adapter, "WebHalf", f"{WEB_HALF}mm")
    await set_global(adapter, "CornerLand", f"{CORNER_LAND}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "PadDia", '2 * "RailHalf"')
    await set_global(adapter, "CrossbarX", f"{CROSSBAR_X}mm")
    await set_global(adapter, "CrossbarHalf", f"{CROSSBAR_HALF}mm")
    await set_global(adapter, "BossHalfZ", f"{BOSS_HALF_Z}mm")
    await set_global(adapter, "GooseneckBoreDia", f"{GOOSENECK_BORE_DIA}mm")
    await set_global(adapter, "PassageDia", f"{PASSAGE_DIA}mm")
    await set_global(adapter, "OuterX", '"ColumnX" + "RailHalf"')
    await set_global(adapter, "OuterZ", '"ColumnZ" + "RailHalf"')
    await set_global(adapter, "InnerX", '"ColumnX" - "RailHalf"')
    await set_global(adapter, "InnerZ", '"ColumnZ" - "RailHalf"')
    await set_global(adapter, "WebOuterX", '"ColumnX" + "WebHalf"')
    await set_global(adapter, "WebInnerX", '"ColumnX" - "WebHalf"')
    await set_global(adapter, "WebOuterZ", '"ColumnZ" + "WebHalf"')
    await set_global(adapter, "WebInnerZ", '"ColumnZ" - "WebHalf"')
    await set_global(adapter, "Recess", '"RailHalf" - "WebHalf"')
    await set_global(adapter, "RunX", '"ColumnX" - "RailHalf" - "CornerLand"')
    await set_global(adapter, "RunZ", '"ColumnZ" - "RailHalf" - "CornerLand"')

    # Each sketch DECLARES its dim names + drive equations inline at the
    # define_* call; a per-sketch SketchDims records each dim in the exact order
    # the helper emits it, so naming lands structurally. The drive equations are
    # collected here and applied in one deferred batch at the end (every
    # equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # --- the rounded-corner ring ------------------------------------------
    # Two crossed slabs plus four corner discs. Their union IS the ring with
    # R = RailHalf outer corners centred on the bores: slab A carries the two
    # Z rails full length, slab B the two X rails, and each disc fills the
    # quadrant beyond both. This avoids sketching arcs entirely -- every
    # profile below is a plain rectangle or circle.
    slab_a = SketchDims()
    check("create_sketch slab A", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, OUTER_X, COLUMN_Z, "slab A (Z rails)", dims=slab_a,
        name_width="Width", drive_width='2 * "OuterX"',
        name_depth="Depth", drive_depth='2 * "ColumnZ"',
    )
    await ensure_fully_defined(adapter, "slab A")
    check("exit_sketch slab A", await adapter.exit_sketch())
    name_last_feature(adapter, "SlabAProfile")
    drive_jobs += slab_a.apply(adapter, "SlabAProfile")
    check(
        "extrude slab A",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SlabA")
    v = 4.0 * OUTER_X * COLUMN_Z * RING_HEIGHT
    await volume_check(adapter, "slab A", v, 0.001 * v)

    slab_b = SketchDims()
    check("create_sketch slab B", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, COLUMN_X, OUTER_Z, "slab B (X rails)", dims=slab_b,
        name_width="Width", drive_width='2 * "ColumnX"',
        name_depth="Depth", drive_depth='2 * "OuterZ"',
    )
    await ensure_fully_defined(adapter, "slab B")
    check("exit_sketch slab B", await adapter.exit_sketch())
    name_last_feature(adapter, "SlabBProfile")
    drive_jobs += slab_b.apply(adapter, "SlabBProfile")
    check(
        "extrude slab B",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SlabB")
    cross_area = 4.0 * (
        OUTER_X * COLUMN_Z + COLUMN_X * OUTER_Z - COLUMN_X * COLUMN_Z
    )
    v = cross_area * RING_HEIGHT
    await volume_check(adapter, "slab A+B", v, 0.001 * v)

    # Window: leaves the rail band standing on the column stations.
    window = SketchDims()
    check("create_sketch window", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, INNER_X, INNER_Z, "window rectangle", dims=window,
        name_width="Width", drive_width='2 * "InnerX"',
        name_depth="Depth", drive_depth='2 * "InnerZ"',
    )
    await ensure_fully_defined(adapter, "window rectangle")
    check("exit_sketch window", await adapter.exit_sketch())
    name_last_feature(adapter, "WindowProfile")
    drive_jobs += window.apply(adapter, "WindowProfile")
    check(
        "cut window",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "WindowCut")
    band_area = cross_area - 4.0 * INNER_X * INNER_Z
    v = band_area * RING_HEIGHT
    await volume_check(adapter, "rail band", v, 0.001 * v)

    # Corner quadrants: full Ø34 discs on the bores. Only the quadrant beyond
    # both slabs is new material, which is exactly the rounded outer corner.
    corners = SketchDims()
    check("create_sketch corners", await adapter.create_sketch("Top"))
    n = 0
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            await define_circle(
                adapter, sx * COLUMN_X, sz * COLUMN_Z, RAIL_HALF,
                f"corner ({sx:+.0f}, {sz:+.0f})", dims=corners,
                names=(f"C{n}X", f"C{n}Z", f"C{n}Dia"),
                drives=('"ColumnX"', '"ColumnZ"', '"PadDia"'),
            )
            n += 1
    await ensure_fully_defined(adapter, "corners sketch")
    check("exit_sketch corners", await adapter.exit_sketch())
    name_last_feature(adapter, "CornerProfile")
    drive_jobs += corners.apply(adapter, "CornerProfile")
    check(
        "extrude corners",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CornerQuadrants")
    ring_area = _ring_area(RAIL_HALF)
    v = ring_area * RING_HEIGHT
    await volume_check(adapter, "rounded ring", v, 0.001 * v)

    # --- web recess --------------------------------------------------------
    # One cut over the web band carves both faces of all four rails. The sketch
    # plane sits at the web's TOP (y +10.5) and the cut runs DOWN the web height
    # -- a face cut takes the direction opposite the sketch normal, so no
    # reverse flag (the proven blind face-cut idiom).
    web_plane = check(
        "create_plane web top",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=HALF_H - TOP_FLANGE
            )
        ),
    )
    recess = SketchDims()
    check(
        "create_sketch recess",
        await adapter.create_sketch(getattr(web_plane, "name", web_plane)),
    )
    for label, points, seg_drives, anchor_x, anchor_z in _recess_strips():
        lines = await add_line_chain(adapter, points)
        names = [f"{label}W", f"{label}H", f"{label}AX", f"{label}AZ"]
        await define_rectilinear_chain(
            adapter, lines, points, label=f"recess {label}", dims=recess,
            names=names, drives=[*seg_drives, anchor_x, anchor_z],
        )
    await ensure_fully_defined(adapter, "recess sketch")
    check("exit_sketch recess", await adapter.exit_sketch())
    name_last_feature(adapter, "RecessProfile")
    drive_jobs += recess.apply(adapter, "RecessProfile")
    check(
        "cut recess",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=WEB_HEIGHT)),
    )
    name_last_feature(adapter, "WebRecess")
    v_ring = ring_area * RING_HEIGHT - _recess_area() * WEB_HEIGHT
    await volume_check(adapter, "webbed ring", v_ring, 0.002 * v_ring)

    # --- cast-in cross rib -------------------------------------------------
    # Full section, so it refills the recess where it lands on the X rails; its
    # ends run to the rails' OUTER faces so it merges at every level.
    rib = SketchDims()
    check("create_sketch cross rib", await adapter.create_sketch("Top"))
    rib_rect = [
        (CROSSBAR_X - CROSSBAR_HALF, -OUTER_Z),
        (CROSSBAR_X + CROSSBAR_HALF, -OUTER_Z),
        (CROSSBAR_X + CROSSBAR_HALF, OUTER_Z),
        (CROSSBAR_X - CROSSBAR_HALF, OUTER_Z),
    ]
    rib_lines = await add_line_chain(adapter, rib_rect)
    await define_rectilinear_chain(
        adapter, rib_lines, rib_rect, label="cross rib", dims=rib,
        names=["Width", "Depth", "AnchorX", "AnchorZ"],
        drives=['2 * "CrossbarHalf"', '2 * "OuterZ"',
                '-"CrossbarX" + "CrossbarHalf"', '"OuterZ"'],
    )
    await ensure_fully_defined(adapter, "cross rib sketch")
    check("exit_sketch cross rib", await adapter.exit_sketch())
    name_last_feature(adapter, "CrossRibProfile")
    drive_jobs += rib.apply(adapter, "CrossRibProfile")
    check(
        "extrude cross rib",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CrossRib")
    rib_w = 2.0 * CROSSBAR_HALF
    rib_flange_add = rib_w * (2.0 * OUTER_Z) - rib_w * (2.0 * 2.0 * RAIL_HALF)
    rib_web_add = rib_w * (2.0 * OUTER_Z) - rib_w * (2.0 * 2.0 * WEB_HALF)
    v_rib = v_ring + rib_flange_add * (TOP_FLANGE + BOT_FLANGE) + rib_web_add * WEB_HEIGHT
    await volume_check(adapter, "cross rib", v_rib, 0.002 * v_rib)

    # --- gooseneck socket boss ---------------------------------------------
    # A full-section pad on the east rail's mid-span: without it the Ø17 bore
    # would break out of the 16-thick web into both recesses.
    boss = SketchDims()
    check("create_sketch socket boss", await adapter.create_sketch("Top"))
    boss_rect = [
        (-OUTER_X, -BOSS_HALF_Z),
        (-INNER_X, -BOSS_HALF_Z),
        (-INNER_X, BOSS_HALF_Z),
        (-OUTER_X, BOSS_HALF_Z),
    ]
    boss_lines = await add_line_chain(adapter, boss_rect)
    await define_rectilinear_chain(
        adapter, boss_lines, boss_rect, label="socket boss", dims=boss,
        names=["Width", "Depth", "AnchorX", "AnchorZ"],
        drives=['2 * "RailHalf"', '2 * "BossHalfZ"', '"OuterX"', '"BossHalfZ"'],
    )
    await ensure_fully_defined(adapter, "socket boss sketch")
    check("exit_sketch socket boss", await adapter.exit_sketch())
    name_last_feature(adapter, "SocketBossProfile")
    drive_jobs += boss.apply(adapter, "SocketBossProfile")
    check(
        "extrude socket boss",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SocketBoss")
    boss_web_add = (2.0 * RAIL_HALF - 2.0 * WEB_HALF) * (2.0 * BOSS_HALF_Z)
    v_boss = v_rib + boss_web_add * WEB_HEIGHT
    await volume_check(adapter, "socket boss", v_boss, 0.002 * v_boss)

    # --- corner pads -------------------------------------------------------
    # The corner quadrants continue PAD_DROP below the rail underside (ch30
    # p008 reads the ends 6-7 lower than mid-span). flip=True mirrors both the
    # start offset and the extrude direction, so this grows DOWN from -HALF_H.
    pads = SketchDims()
    check("create_sketch pads", await adapter.create_sketch("Top"))
    n = 0
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            await define_circle(
                adapter, sx * COLUMN_X, sz * COLUMN_Z, RAIL_HALF,
                f"pad ({sx:+.0f}, {sz:+.0f})", dims=pads,
                names=(f"P{n}X", f"P{n}Z", f"P{n}Dia"),
                drives=('"ColumnX"', '"ColumnZ"', '"PadDia"'),
            )
            n += 1
    await ensure_fully_defined(adapter, "pads sketch")
    check("exit_sketch pads", await adapter.exit_sketch())
    name_last_feature(adapter, "PadProfile")
    drive_jobs += pads.apply(adapter, "PadProfile")
    extrude_at_offset(adapter, PAD_DROP, HALF_H, flip=True)
    name_last_feature(adapter, "CornerPads")
    v_pads = v_boss + 4.0 * math.pi * RAIL_HALF**2 * PAD_DROP
    await volume_check(adapter, "corner pads", v_pads, 0.002 * v_pads)

    # --- bores -------------------------------------------------------------
    bores = SketchDims()
    check("create_sketch bores", await adapter.create_sketch("Top"))
    n = 0
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            await define_circle(
                adapter, sx * COLUMN_X, sz * COLUMN_Z, BORE_DIA / 2.0,
                f"bore ({sx:+.0f}, {sz:+.0f})", dims=bores,
                names=(f"B{n}X", f"B{n}Z", f"B{n}Dia"),
                drives=('"ColumnX"', '"ColumnZ"', '"BoreDia"'),
            )
            n += 1
    await ensure_fully_defined(adapter, "bores sketch")
    check("exit_sketch bores", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bores.apply(adapter, "BoreProfile")
    check(
        "cut bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ColumnBores")
    v_bored = v_pads - 4.0 * math.pi * (BORE_DIA / 2.0) ** 2 * (RING_HEIGHT + PAD_DROP)
    await volume_check(adapter, "column bores", v_bored, 0.002 * v_bored)

    # Counter-spring (gooseneck) socket bore through the boss: the post slides
    # through here and drops below the plate (build_gooseneck). On-axis in z
    # (z 0 is a relation, not a dim), so define_circle records X + diameter.
    socket = SketchDims()
    check("create_sketch socket bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, GOOSENECK_X, GOOSENECK_Z, GOOSENECK_BORE_DIA / 2.0,
        "gooseneck socket bore", dims=socket,
        names=("X", "Z", "Dia"),
        drives=('"ColumnX"', None, '"GooseneckBoreDia"'),
    )
    await ensure_fully_defined(adapter, "socket bore sketch")
    check("exit_sketch socket bore", await adapter.exit_sketch())
    name_last_feature(adapter, "SocketBoreProfile")
    drive_jobs += socket.apply(adapter, "SocketBoreProfile")
    check(
        "cut socket bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "GooseneckSocket")
    v_socket = v_bored - math.pi * (GOOSENECK_BORE_DIA / 2.0) ** 2 * RING_HEIGHT
    await volume_check(adapter, "gooseneck socket", v_socket, 0.002 * v_socket)

    # Set-screw passage: blind cut INTO the rail's outer face (offset plane at
    # x -OuterX), deep enough to pierce the curved socket wall everywhere across
    # the passage circle. Cut, not a Hole Wizard feature: the passage EXIT is a
    # curved bore wall and the entry face carries the screw head -- the
    # output-fixture cross-hole precedent, as the retired clamp block used.
    passage_plane = check(
        "create_plane passage face",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=-OUTER_X
            )
        ),
    )
    passage = SketchDims()
    check(
        "create_sketch passage",
        await adapter.create_sketch(getattr(passage_plane, "name", passage_plane)),
    )
    await define_circle(
        adapter, GOOSENECK_Z, PASSAGE_Y, PASSAGE_DIA / 2.0, "set-screw passage",
        dims=passage,
        names=("PassageCz", "PassageCy", "PassageDiaDim"),
        drives=(None, None, '"PassageDia"'),
    )
    await ensure_fully_defined(adapter, "passage sketch")
    check("exit_sketch passage", await adapter.exit_sketch())
    name_last_feature(adapter, "PassageProfile")
    drive_jobs += passage.apply(adapter, "PassageProfile")
    passage_depth = RAIL_HALF - math.sqrt(
        (GOOSENECK_BORE_DIA / 2.0) ** 2 - (PASSAGE_DIA / 2.0) ** 2
    ) + 1.0
    check(
        "cut passage",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=passage_depth)),
    )
    name_last_feature(adapter, "SetScrewPassage")
    # Removed volume: the wall band between the curved socket wall and the outer
    # face, over the passage circle (midpoint quadrature; the blind floor sits
    # inside the bore everywhere, so it never truncates the integrand).
    rc, bore_r = PASSAGE_DIA / 2.0, GOOSENECK_BORE_DIA / 2.0
    steps = 400
    v_passage = 0.0
    for i in range(steps):
        t = -rc + (i + 0.5) * (2.0 * rc / steps)
        chord = 2.0 * math.sqrt(max(rc * rc - t * t, 0.0))
        v_passage += chord * (RAIL_HALF - math.sqrt(bore_r**2 - t * t))
    v_passage *= 2.0 * rc / steps
    v_final = v_socket - v_passage
    await volume_check(adapter, "set-screw passage", v_final, 0.002 * v_final)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven frame (equations neutral)", v_final, 0.002 * v_final
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Inspection Notes": INSPECTION_NOTES,
            "Top View Note": TOP_VIEW_NOTE,
            "Front View Note": FRONT_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
