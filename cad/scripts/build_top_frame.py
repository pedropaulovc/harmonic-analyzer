r"""Reproduction script: top frame casting (2026-08-02 rederive; 1 used).

ONE green cast iron piece that absorbed the old separate top-crossbar
(full-height integral bar) and gooseneck-clamp (square-head set screw in
the east-rail hub, -X crank side). Derived from the ch30 eight views (px
measurement anchored on the 394 x 224 column pitch), the GT bundle solve
rescaled onto the model column grid, and ch19 close-ups (webbing, hub, screw):

* Rail band y 999.7..1036.2 (H 36.5; the old 41-tall band top 1040.7 was
  the BOSS top -- the rail top face is 4.5 lower). Assembly inserts the
  part at ring mid-plane TOP_FRAME_MID_Y = 1017.95.
* Side rails (along Z at x +/-197) 34.2 wide -> outer faces x +/-214.1,
  window x +/-179.9. Front/rear rails (along X at z -/+112) 38.0 wide ->
  outer faces z -/+131, window z -/+93.
* Corner bosses O52.2 spanning y 993.4..1040.7 (proud 4.5 above the rail
  top, hanging 6.3 below the underside -- ch19 img04 / p002+p006 corner
  crops), bored O25.5 around the O25.4 columns, each with a #10-24 side
  screw tapped into its z face (front pair from the front, rear pair from
  the rear; O9 x 0.9 spot-face on the boss cylinder) pressing the column:
  the screws that hold the frame to the tube-frame.
* Integral crossbar 22 wide at x -26..-4 spanning the window along Z,
  flush with BOTH faces (its underside 999.7 is the knife-mount seat
  plane), with 18 x 18 plan gussets at all four rail junctions and two
  O13.49 (1/2 close) hanger-stud holes at z 3.088 -/+ 87.06 -- the
  knife-mount studs with their big hex nuts (top.png stud crops).
* Gooseneck hub on the east rail (-X) at z +3.088: full-height rib 27 wide,
  O17 clearance bore for the O16 counter-spring post, underside boss
  O30 x 8 with twin V-gussets (ch30 p004), a 16 x 16 x 2 cast pocket and
  a 1/4-20 tap through the rib to the bore for the square-head set screw
  (book p.45: "a square-head screw pinches the post in its socket").
* Webbed faces: panels recessed 3.5 into every inner and outer rail face
  between 8-tall top/bottom flanges (ch19 img04/img05), with full-
  thickness lands at the bosses, hub rib and crossbar junctions.

Layout: plan profile in XZ, ring mid-plane extruded symmetrically in Y
(rails y -18.25..+18.25 local). Sketches on the Top plane use the
(x, y) -> (X, -Z) handedness; sketches on Right-plane offsets map
(x, y) -> (Z, Y) (build_rocker_arm_support precedent). Build order:
outer slab -> window cut -> crossbar+gussets boss -> corner bosses
(up/down pair) -> hub boss + V-gussets -> face panels -> set-screw
pocket -> spot-faces -> column bores -> gooseneck bore -> wizard holes
(hanger-stud clearances, side-screw taps, set-screw tap). Wizard holes
come after the face cuts so every seat face is final. Analytic volume
checks after every feature; the boss/hub/spot-face/tap expectations use
small grid integrals (no tidy closed form against the webbed solid).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_top_frame.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    define_polygon_chain,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
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
    set_dimension_symmetric_tolerance,
)
from _holes import (
    CLEARANCE_MM,
    HoleSpec,
    TAP_DRILL_MM,
    blind_hole_volume_mm3,
    wizard_holes,
)
from top_frame_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FRONT_VIEW_NOTE,
    INSPECTION_NOTES,
    OUTER_PROFILE_TOLERANCE_MM,
    TOP_VIEW_NOTE,
)
from cone_pivot_post_installation import (
    FRAME_COLUMN_Z_CENTER,
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
    SUMMING_Z,
)

PART_NAME = "top-frame"
MATERIAL = "Gray Cast Iron"  # green-painted casting like the base

# --- Plan geometry (machine == part-local x/z; part y = machine y - 1017.95) --
COLUMN_X = 197.0  # column stations (frame.SLDASM)
FRONT_COLUMN_Z = FRAME_FRONT_COLUMN_Z  # -112
REAR_COLUMN_Z = FRAME_REAR_COLUMN_Z  # +112
FRAME_CENTER_Z = FRAME_COLUMN_Z_CENTER  # 0.0

RAIL_W_SIDE = 34.2  # side rails, along Z (GT corner rescale 221.5 -> 214.1)
RAIL_W_FR = 38.0  # front/rear rails, along X (GT z-corner rescale 137.4 -> 131)
RING_HEIGHT = 36.5  # rail band (ch30 p002 36.7 / p006 37.0 / ch19 img03 35.6)
HALF_H = RING_HEIGHT / 2.0  # 18.25; band local y -18.25..+18.25

BOSS_DIA = 52.2  # silhouette extremes +/-223.1 in p002/p006
BOSS_ABOVE = 4.5  # boss proud of the rail top (corner-crop step)
BOSS_BELOW = 6.3  # boss hang below the underside (p006 read 5.7-7)
BORE_DIA = 25.5  # clamps the O25.4 column (0.1 slip)

OUTER_X = COLUMN_X + RAIL_W_SIDE / 2.0  # 214.1
INNER_X = COLUMN_X - RAIL_W_SIDE / 2.0  # 179.9
OUTER_Z = abs(FRONT_COLUMN_Z) + RAIL_W_FR / 2.0  # 131.0
INNER_Z = abs(FRONT_COLUMN_Z) - RAIL_W_FR / 2.0  # 93.0

# --- Integral crossbar (old top-crossbar, merged) ---------------------------
BAR_X0, BAR_X1 = -26.0, -4.0  # 22 wide, centred on KNIFE x = -15
GUSSET = 18.0  # plan gusset legs at the four rail junctions
HEX_Z_MID = 87.06  # knife-mount trunnion mid offset (build_summing_assembly)
STUD_Z_FRONT = SUMMING_Z - HEX_Z_MID  # -83.972
STUD_Z_REAR = SUMMING_Z + HEX_Z_MID  # +90.148
STUD_HOLE_SPEC = HoleSpec("clearance", "1/2", fit="close")  # O13.492
STUD_HOLE_DIA = CLEARANCE_MM[("1/2", "close")]

# --- Gooseneck hub (old gooseneck-clamp function, merged) -------------------
GOOSENECK_X = -COLUMN_X  # east rail, -X crank side (summing's post station)
GOOSENECK_Z = SUMMING_Z
GOOSENECK_BORE_DIA = 17.0  # O16 post slides through
HUB_RIB_W = 27.0  # full-height rib band across the east rail
HUB_BOSS_DIA = 30.0  # underside boss around the bore exit
HUB_BOSS_DROP = 8.0  # boss bottom local -26.25
HUB_GUSSET_T = 7.0  # V-gusset thickness along X (x -200.5..-193.5)
HUB_GUSSET_HALF_IN = 8.0  # full-depth span |z - 3.088| <= 8
HUB_GUSSET_HALF_OUT = 30.0  # feathers to the underside at |z - 3.088| = 30
SET_POCKET = 16.0  # cast pocket (square) around the set-screw tap
SET_POCKET_DEPTH = 2.0
SET_TAP_SPEC = HoleSpec("tapped", "1/4-20", end="blind", depth_mm=8.0)

# --- Side screws (frame -> tube-frame columns) ------------------------------
SPOTFACE_DIA = 9.0
SPOTFACE_PLANE = abs(FRAME_FRONT_COLUMN_Z) + BOSS_DIA / 2.0 + 0.4  # z -/+138.5
SPOTFACE_FLOOR = SPOTFACE_PLANE - 0.9  # planar seat z -/+137.6
SIDE_TAP_SPEC = HoleSpec("tapped", "#10-24", end="blind", depth_mm=14.0)

# --- Fulcrum keepers (west rail top face; shaft-end brackets, ch17 p.40) ----
KEEPER_TAP_SPEC = HoleSpec("tapped", "#10-24", end="blind", depth_mm=10.0)
KEEPER_TAP_X = 199.9  # fulcrum line (build_channel_assembly FULCRUM[0])
KEEPER_TAP_Z_FRONT = SUMMING_Z - 74.0  # -70.912
KEEPER_TAP_Z_REAR = SUMMING_Z + 74.0  # +77.088

# --- Webbing ----------------------------------------------------------------
FLANGE = 8.0  # top/bottom flange bands
RECESS = 3.5  # panel recess into each face
PANEL_HALF_H = (RING_HEIGHT - 2.0 * FLANGE) / 2.0  # 10.25
# Panel spans (part z or x). Lands survive at bosses, hub rib and the
# crossbar junction; margins keep the recesses off the boss face
# intersections (|z| 92.3 on the side-face planes, |x| 179.1 on the
# front/rear planes) and off the hub rib / gusset toes.
PANEL_W_SIDE_HUB = ((-86.0, -14.0), (20.0, 86.0))  # east faces (hub rib gap)
PANEL_W_SIDE_FULL = ((-86.0, 86.0),)  # west faces
PANEL_FR_OUTER = ((-174.0, 174.0),)  # front/rear outer faces
PANEL_FR_INNER = ((-174.0, -50.0), (20.0, 174.0))  # inner faces (bar junction gap)

THROUGH_CUT_DEPTH = 110.0  # mid-plane total; > boss stack (47.3)

if abs(FRONT_COLUMN_Z + REAR_COLUMN_Z) > 1e-12 or abs(FRAME_CENTER_Z) > 1e-12:
    raise AssertionError("top-frame assumes a symmetric column span about z 0")
if STUD_Z_REAR + STUD_HOLE_DIA / 2.0 >= INNER_Z + GUSSET:
    raise AssertionError("rear hanger-stud hole escapes the junction material")


# --------------------------------------------------------------------------
# Analytic expectations. The webbed casting has no tidy closed form at the
# bosses/hub/tap break-ins, so those pieces integrate on fine grids (0.02 mm
# cells) exactly like the old _boss_extra_area did.
# --------------------------------------------------------------------------


def _boss_extra_in_band_area() -> float:
    """Plan area ONE corner boss adds beyond the ring solid, in the rail band.

    Grid-integrated over the NE corner: circle O52.2 at (197, 112) minus the
    ring plan solid (side rail x 179.9..214.1 union rear rail z 93..131,
    clipped to the slab x <= 214.1, z <= 131). All four corners match by
    symmetry (the crossbar is far away).
    """
    r = BOSS_DIA / 2.0
    step = 0.05
    n = int(2.0 * r / step) + 2
    x0, z0 = COLUMN_X - r, abs(FRONT_COLUMN_Z) - r
    extra = 0.0
    for i in range(n):
        x = x0 + (i + 0.5) * step
        dx2 = (x - COLUMN_X) ** 2
        if dx2 > r * r:
            continue
        half = math.sqrt(r * r - dx2)
        z_lo, z_hi = abs(FRONT_COLUMN_Z) - half, abs(FRONT_COLUMN_Z) + half
        z = z_lo
        while z < z_hi:
            zz = z + 0.5 * step
            if zz < z_hi:
                in_slab = zz <= OUTER_Z and x <= OUTER_X
                in_ring = in_slab and (x >= INNER_X or zz >= INNER_Z)
                if not in_ring:
                    extra += step * step
            z += step
    return extra


def _hub_underhang_volume() -> float:
    """Volume of the hub boss + V-gussets union hanging below the underside."""
    step = 0.05
    r = HUB_BOSS_DIA / 2.0
    vol = 0.0
    x = -212.6
    while x < -181.4:
        xx = x + 0.5 * step
        z = GOOSENECK_Z - HUB_GUSSET_HALF_OUT - 0.6
        z_end = GOOSENECK_Z + HUB_GUSSET_HALF_OUT + 0.6
        while z < z_end:
            zz = z + 0.5 * step
            h = 0.0
            if (xx - GOOSENECK_X) ** 2 + (zz - GOOSENECK_Z) ** 2 <= r * r:
                h = HUB_BOSS_DROP
            elif -200.5 <= xx <= -193.5:
                t = abs(zz - GOOSENECK_Z)
                if t <= HUB_GUSSET_HALF_IN:
                    h = HUB_BOSS_DROP
                elif t <= HUB_GUSSET_HALF_OUT:
                    h = (
                        HUB_BOSS_DROP
                        * (HUB_GUSSET_HALF_OUT - t)
                        / (HUB_GUSSET_HALF_OUT - HUB_GUSSET_HALF_IN)
                    )
            vol += h * step * step
            z += step
        x += step
    return vol


def _spotface_removal() -> float:
    """Material one O9 x 0.9 spot-face removes from the boss cylinder."""
    r_d = SPOTFACE_DIA / 2.0
    r_b = BOSS_DIA / 2.0
    step = 0.01
    vol = 0.0
    d = -r_d
    while d < r_d:
        dd = d + 0.5 * step
        chord = 2.0 * math.sqrt(max(0.0, r_d * r_d - dd * dd))
        surf = abs(FRONT_COLUMN_Z) + math.sqrt(max(0.0, r_b * r_b - dd * dd))
        length = max(0.0, min(surf, SPOTFACE_PLANE) - SPOTFACE_FLOOR)
        vol += chord * length * step
        d += step
    return vol


def _side_tap_removal() -> float:
    """Material one #10-24 x 14 tap removes (break-in to the curved bore)."""
    r_h = TAP_DRILL_MM["#10-24"] / 2.0
    r_v = BORE_DIA / 2.0
    step = 0.005
    vol = 0.0
    d = -r_h
    while d < r_h:
        dd = d + 0.5 * step
        chord = 2.0 * math.sqrt(max(0.0, r_h * r_h - dd * dd))
        void = abs(FRONT_COLUMN_Z) + math.sqrt(max(0.0, r_v * r_v - dd * dd))
        length = max(0.0, SPOTFACE_FLOOR - void)
        vol += chord * length * step
        d += step
    return vol


def _set_tap_removal() -> float:
    """Material the 1/4-20 x 8 set-screw tap removes (break-in to the bore)."""
    r_h = TAP_DRILL_MM["1/4-20"] / 2.0
    r_v = GOOSENECK_BORE_DIA / 2.0
    floor_x = OUTER_X - SET_POCKET_DEPTH  # 212.1 (magnitudes, east side)
    step = 0.005
    vol = 0.0
    d = -r_h
    while d < r_h:
        dd = d + 0.5 * step
        chord = 2.0 * math.sqrt(max(0.0, r_h * r_h - dd * dd))
        void = COLUMN_X + math.sqrt(max(0.0, r_v * r_v - dd * dd))
        length = max(0.0, floor_x - void)
        vol += chord * length * step
        d += step
    return vol


async def _panel_cut(
    adapter,
    label: str,
    base_plane: str,
    plane_offset: float,
    spans: tuple[tuple[float, float], ...],
    reverse: bool,
    feature: str,
) -> float:
    """Cut RECESS-deep webbing panels into one rail face.

    ``base_plane`` "Front Plane" sketches map (x, y) -> (X, Y); "Right
    Plane" offsets map (x, y) -> (Z, Y) (build_rocker_arm_support). Each
    span becomes one rectangle between the flanges (y -/+10.25); returns
    the exact removed volume.
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    plane = check(
        f"create_plane {label}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane=base_plane, offset=plane_offset
            )
        ),
    )
    plane_name = getattr(plane, "name", plane)
    panel = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(plane_name))
    for k, (a, b) in enumerate(spans):
        pts = [
            (a, -PANEL_HALF_H),
            (b, -PANEL_HALF_H),
            (b, PANEL_HALF_H),
            (a, PANEL_HALF_H),
        ]
        lines = await add_line_chain(adapter, pts)
        await define_rectilinear_chain(
            adapter,
            lines,
            pts,
            label=f"{label} panel {k}",
            dims=panel,
            names=[f"P{k}Run", f"P{k}Rise", f"P{k}Off", f"P{k}Drop"],
        )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{feature}Profile")
    panel.apply(adapter, f"{feature}Profile")  # named, undriven (cast cosmetics)
    check(
        f"cut {label}",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=RECESS, reverse_direction=reverse)
        ),
    )
    name_last_feature(adapter, feature)
    return sum((b - a) for a, b in spans) * 2.0 * PANEL_HALF_H * RECESS


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs: named equation-manager globals (mm) drive the primary
    # envelope sketches. A GUI fine-tune edits THESE -- e.g. RailWSide or
    # BossDia -- never an auto "D7@Sketch3". Explicit `mm`: inch document,
    # bare equation numbers evaluate in document units.
    await set_global(adapter, "ColumnX", f"{COLUMN_X}mm")
    await set_global(adapter, "ColumnZ", f"{abs(FRONT_COLUMN_Z)}mm")
    await set_global(adapter, "RailWSide", f"{RAIL_W_SIDE}mm")
    await set_global(adapter, "RailWFR", f"{RAIL_W_FR}mm")
    await set_global(adapter, "BossDia", f"{BOSS_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "GooseneckZ", f"{GOOSENECK_Z}mm")
    await set_global(adapter, "GooseneckBoreDia", f"{GOOSENECK_BORE_DIA}mm")
    await set_global(adapter, "HubBossDia", f"{HUB_BOSS_DIA}mm")
    await set_global(adapter, "OuterX", '"ColumnX" + "RailWSide" / 2')
    await set_global(adapter, "OuterZ", '"ColumnZ" + "RailWFR" / 2')
    await set_global(adapter, "InnerX", '"ColumnX" - "RailWSide" / 2')
    await set_global(adapter, "InnerZ", '"ColumnZ" - "RailWFR" / 2')

    drive_jobs: list[tuple[str, str]] = []

    # 1. Outer slab (origin-centred plan rectangle, mid-plane band).
    outer = SketchDims()
    check("create_sketch outer", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter,
        OUTER_X,
        OUTER_Z,
        "outer rectangle",
        dims=outer,
        name_width="Width",
        name_depth="Depth",
        drive_width='2 * "OuterX"',
        drive_depth='2 * "OuterZ"',
    )
    await ensure_fully_defined(adapter, "outer rectangle")
    check("exit_sketch outer", await adapter.exit_sketch())
    name_last_feature(adapter, "OuterProfile")
    drive_jobs += outer.apply(adapter, "OuterProfile")
    check(
        "extrude slab",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "OuterSlab")
    v_slab = 4.0 * OUTER_X * OUTER_Z * RING_HEIGHT
    volume = await volume_check(adapter, "slab", v_slab, 0.001 * v_slab)

    # 2. Window cut (full rectangle; the crossbar comes back as a boss).
    window = SketchDims()
    check("create_sketch window", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter,
        INNER_X,
        INNER_Z,
        "window rectangle",
        dims=window,
        name_width="Width",
        name_depth="Depth",
        drive_width='2 * "InnerX"',
        drive_depth='2 * "InnerZ"',
    )
    await ensure_fully_defined(adapter, "window rectangle")
    check("exit_sketch window", await adapter.exit_sketch())
    name_last_feature(adapter, "WindowProfile")
    drive_jobs += window.apply(adapter, "WindowProfile")
    check(
        "cut window",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "WindowCut")
    v_window = 4.0 * INNER_X * INNER_Z * RING_HEIGHT
    volume = await volume_check(adapter, "rail band", volume - v_window, 500.0)

    # 3. Integral crossbar + plan gussets (one 8-vertex polygon, sketch z
    #    flipped: (x, y) -> (X, -Z)).
    bar_pts_part = [
        (BAR_X0 - GUSSET, -INNER_Z),
        (BAR_X1 + GUSSET, -INNER_Z),
        (BAR_X1, -INNER_Z + GUSSET),
        (BAR_X1, INNER_Z - GUSSET),
        (BAR_X1 + GUSSET, INNER_Z),
        (BAR_X0 - GUSSET, INNER_Z),
        (BAR_X0, INNER_Z - GUSSET),
        (BAR_X0, -INNER_Z + GUSSET),
    ]
    bar_pts = [(x, -z) for x, z in bar_pts_part]
    bar = SketchDims()
    check("create_sketch crossbar", await adapter.create_sketch("Top"))
    bar_lines = await add_line_chain(adapter, bar_pts)
    await define_polygon_chain(
        adapter,
        bar_lines,
        bar_pts,
        anchor=0,
        label="crossbar",
        dims=bar,
        names=[
            "BarAnchorX",
            "BarAnchorZ",
            "BarFootSpan",
            "GussetRunE",
            "GussetRiseE",
            "BarSideE",
            "GussetRunE2",
            "GussetRiseE2",
            "BarHeadSpan",
            "GussetRunW",
            "GussetRiseW",
            "BarSideW",
        ],
    )
    await ensure_fully_defined(adapter, "crossbar sketch")
    check("exit_sketch crossbar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude crossbar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Crossbar")
    bar_area = (BAR_X1 - BAR_X0) * 2.0 * INNER_Z + 4.0 * GUSSET * GUSSET / 2.0
    v_bar = bar_area * RING_HEIGHT
    volume = await volume_check(adapter, "crossbar", volume + v_bar, 500.0)

    # 4. Corner bosses: one circle set extruded UP to the boss top, a second
    #    identical set extruded DOWN to the boss bottom (one-direction pair;
    #    a mid-plane extrude cannot land the asymmetric 22.75/24.55 split).
    boss_extra_band = _boss_extra_in_band_area()
    r_boss = BOSS_DIA / 2.0
    for updown, depth, feat in (
        ("up", HALF_H + BOSS_ABOVE, "BossesUpper"),
        ("down", HALF_H + BOSS_BELOW, "BossesLower"),
    ):
        bosses = SketchDims()
        check(f"create_sketch bosses {updown}", await adapter.create_sketch("Top"))
        n = 0
        for sx in (-1.0, 1.0):
            for z_world in (FRONT_COLUMN_Z, REAR_COLUMN_Z):
                await define_circle(
                    adapter,
                    sx * COLUMN_X,
                    -z_world,
                    r_boss,
                    f"boss {updown} ({sx:+.0f}, z={z_world:+.0f})",
                    dims=bosses,
                    names=(f"C{n}X", f"C{n}Z", f"C{n}Dia"),
                    drives=('"ColumnX"', '"ColumnZ"', '"BossDia"'),
                )
                n += 1
        await ensure_fully_defined(adapter, f"bosses {updown} sketch")
        check(f"exit_sketch bosses {updown}", await adapter.exit_sketch())
        name_last_feature(adapter, f"Boss{updown.capitalize()}Profile")
        drive_jobs += bosses.apply(adapter, f"Boss{updown.capitalize()}Profile")
        check(
            f"extrude bosses {updown}",
            await adapter.create_extrusion(
                ExtrusionParameters(depth=depth, reverse_direction=(updown == "down"))
            ),
        )
        name_last_feature(adapter, feat)
        proud = BOSS_ABOVE if updown == "up" else BOSS_BELOW
        v_add = 4.0 * (boss_extra_band * HALF_H + math.pi * r_boss**2 * proud)
        volume = await volume_check(
            adapter,
            f"bosses {updown}",
            volume + v_add,
            0.005 * v_add + 50.0,
        )

    # 5. Gooseneck hub: underside boss (extruded down 26.25 from the Top
    #    plane; only the 8 below the underside is new material) ...
    hub = SketchDims()
    check("create_sketch hub boss", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        GOOSENECK_X,
        -GOOSENECK_Z,
        HUB_BOSS_DIA / 2.0,
        "hub boss",
        dims=hub,
        names=("HubX", "HubZ", "HubDia"),
        drives=('"ColumnX"', '"GooseneckZ"', '"HubBossDia"'),
    )
    await ensure_fully_defined(adapter, "hub boss sketch")
    check("exit_sketch hub boss", await adapter.exit_sketch())
    name_last_feature(adapter, "HubBossProfile")
    drive_jobs += hub.apply(adapter, "HubBossProfile")
    check(
        "extrude hub boss",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HALF_H + HUB_BOSS_DROP, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "HubBoss")
    v_hub_boss = math.pi * (HUB_BOSS_DIA / 2.0) ** 2 * HUB_BOSS_DROP
    volume = await volume_check(
        adapter, "hub boss", volume + v_hub_boss, 0.001 * v_hub_boss + 20.0
    )

    # ... and the twin V-gussets: one trapezoid on a Right-plane offset at
    # x -200.5 ((x, y) -> (Z, Y)), extruded 7 toward +X, feathering from
    # full drop at |z-3.088| <= 8 to the underside at |z-3.088| = 30. The
    # expected volume is the grid union with the boss minus the boss.
    v_hub_union = _hub_underhang_volume()
    gusset_plane = check(
        "create_plane hub gussets",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Right Plane",
                offset=GOOSENECK_X - HUB_GUSSET_T / 2.0,
            )
        ),
    )
    gus_pts = [
        (GOOSENECK_Z - HUB_GUSSET_HALF_OUT, -HALF_H),
        (GOOSENECK_Z - HUB_GUSSET_HALF_IN, -HALF_H - HUB_BOSS_DROP),
        (GOOSENECK_Z + HUB_GUSSET_HALF_IN, -HALF_H - HUB_BOSS_DROP),
        (GOOSENECK_Z + HUB_GUSSET_HALF_OUT, -HALF_H),
    ]
    gus = SketchDims()
    check(
        "create_sketch hub gussets",
        await adapter.create_sketch(getattr(gusset_plane, "name", gusset_plane)),
    )
    gus_lines = await add_line_chain(adapter, gus_pts)
    await define_polygon_chain(
        adapter,
        gus_lines,
        gus_pts,
        anchor=0,
        label="hub gussets",
        dims=gus,
        names=[
            "GusAnchorZ",
            "GusAnchorY",
            "GusDropRun",
            "GusDrop",
            "GusFlat",
            "GusRiseRun",
            "GusRise",
        ],
    )
    await ensure_fully_defined(adapter, "hub gussets sketch")
    check("exit_sketch hub gussets", await adapter.exit_sketch())
    name_last_feature(adapter, "HubGussetProfile")
    drive_jobs += gus.apply(adapter, "HubGussetProfile")
    check(
        "extrude hub gussets",
        await adapter.create_extrusion(ExtrusionParameters(depth=HUB_GUSSET_T)),
    )
    name_last_feature(adapter, "HubGussets")
    v_gus_extra = v_hub_union - v_hub_boss
    volume = await volume_check(
        adapter, "hub gussets", volume + v_gus_extra, 0.01 * v_gus_extra + 30.0
    )

    # 6. Webbed faces: 8 recessed panels. reverse_direction puts each cut
    #    INTO the body (the blind face-cut default runs against the base
    #    plane normal -- build_gooseneck_clamp's proven idiom, so planes on
    #    the -X/-Z faces reverse and the +X/+Z faces do not... the OUTER
    #    faces sit past the body on their axis sign, the INNER faces face
    #    the window).
    for label, base, off, spans, reverse, feat in (
        (
            "panel east outer",
            "Right Plane",
            -OUTER_X,
            PANEL_W_SIDE_HUB,
            True,
            "PanelEastOuter",
        ),
        (
            "panel east inner",
            "Right Plane",
            -INNER_X,
            PANEL_W_SIDE_HUB,
            False,
            "PanelEastInner",
        ),
        (
            "panel west outer",
            "Right Plane",
            OUTER_X,
            PANEL_W_SIDE_FULL,
            False,
            "PanelWestOuter",
        ),
        (
            "panel west inner",
            "Right Plane",
            INNER_X,
            PANEL_W_SIDE_FULL,
            True,
            "PanelWestInner",
        ),
        (
            "panel front outer",
            "Front Plane",
            -OUTER_Z,
            PANEL_FR_OUTER,
            True,
            "PanelFrontOuter",
        ),
        (
            "panel front inner",
            "Front Plane",
            -INNER_Z,
            PANEL_FR_INNER,
            False,
            "PanelFrontInner",
        ),
        (
            "panel rear outer",
            "Front Plane",
            OUTER_Z,
            PANEL_FR_OUTER,
            False,
            "PanelRearOuter",
        ),
        (
            "panel rear inner",
            "Front Plane",
            INNER_Z,
            PANEL_FR_INNER,
            True,
            "PanelRearInner",
        ),
    ):
        removed = await _panel_cut(adapter, label, base, off, spans, reverse, feat)
        volume = await volume_check(adapter, label, volume - removed, 60.0)

    # 7. Set-screw cast pocket on the hub rib (east outer face, -X).
    pocket_plane = check(
        "create_plane set pocket",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=-OUTER_X
            )
        ),
    )
    pocket = SketchDims()
    check(
        "create_sketch set pocket",
        await adapter.create_sketch(getattr(pocket_plane, "name", pocket_plane)),
    )
    half_p = SET_POCKET / 2.0
    pk_pts = [
        (GOOSENECK_Z - half_p, -half_p),
        (GOOSENECK_Z + half_p, -half_p),
        (GOOSENECK_Z + half_p, half_p),
        (GOOSENECK_Z - half_p, half_p),
    ]
    pk_lines = await add_line_chain(adapter, pk_pts)
    await define_rectilinear_chain(
        adapter,
        pk_lines,
        pk_pts,
        label="set pocket",
        dims=pocket,
        names=["PocketRun", "PocketRise", "PocketOffZ", "PocketOffY"],
    )
    await ensure_fully_defined(adapter, "set pocket sketch")
    check("exit_sketch set pocket", await adapter.exit_sketch())
    name_last_feature(adapter, "SetPocketProfile")
    pocket.apply(adapter, "SetPocketProfile")
    check(
        "cut set pocket",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SET_POCKET_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "SetScrewPocket")
    v_pocket = SET_POCKET * SET_POCKET * SET_POCKET_DEPTH
    volume = await volume_check(adapter, "set pocket", volume - v_pocket, 20.0)

    # 8. Side-screw spot-faces: O9 x 0.9 flats on the curved boss z-faces
    #    (planar seats the tapped holes need).
    v_spot = _spotface_removal()
    for side, sign, reverse in (("front", -1.0, True), ("rear", 1.0, False)):
        spot_plane = check(
            f"create_plane spotface {side}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset",
                    base_plane="Front Plane",
                    offset=sign * SPOTFACE_PLANE,
                )
            ),
        )
        spot = SketchDims()
        check(
            f"create_sketch spotface {side}",
            await adapter.create_sketch(getattr(spot_plane, "name", spot_plane)),
        )
        for k, sx in enumerate((-1.0, 1.0)):
            await define_circle(
                adapter,
                sx * COLUMN_X,
                0.0,
                SPOTFACE_DIA / 2.0,
                f"spotface {side} ({sx:+.0f})",
                dims=spot,
                names=(f"S{k}X", None, f"S{k}Dia"),
            )
        await ensure_fully_defined(adapter, f"spotface {side} sketch")
        check(f"exit_sketch spotface {side}", await adapter.exit_sketch())
        name_last_feature(adapter, f"SpotFace{side.capitalize()}Profile")
        spot.apply(adapter, f"SpotFace{side.capitalize()}Profile")
        check(
            f"cut spotface {side}",
            await adapter.create_cut_extrude(
                ExtrusionParameters(
                    depth=SPOTFACE_PLANE - SPOTFACE_FLOOR, reverse_direction=reverse
                )
            ),
        )
        name_last_feature(adapter, f"SpotFace{side.capitalize()}")
        volume = await volume_check(
            adapter, f"spotface {side}", volume - 2.0 * v_spot, 0.2 * v_spot + 15.0
        )

    # 9. Column bores (through the boss stacks).
    bores = SketchDims()
    check("create_sketch bores", await adapter.create_sketch("Top"))
    n = 0
    for sx in (-1.0, 1.0):
        for z_world in (FRONT_COLUMN_Z, REAR_COLUMN_Z):
            await define_circle(
                adapter,
                sx * COLUMN_X,
                -z_world,
                BORE_DIA / 2.0,
                f"bore ({sx:+.0f}, z={z_world:+.0f})",
                dims=bores,
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
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ColumnBores")
    boss_h = RING_HEIGHT + BOSS_ABOVE + BOSS_BELOW
    v_bores = 4.0 * math.pi * (BORE_DIA / 2.0) ** 2 * boss_h
    volume = await volume_check(adapter, "column bores", volume - v_bores, 100.0)

    # 10. Gooseneck clearance bore (through the rail band + hub boss).
    gneck = SketchDims()
    check("create_sketch gooseneck bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        GOOSENECK_X,
        -GOOSENECK_Z,
        GOOSENECK_BORE_DIA / 2.0,
        "gooseneck bore",
        dims=gneck,
        names=("GnX", "GnZ", "GnDia"),
        drives=('"ColumnX"', '"GooseneckZ"', '"GooseneckBoreDia"'),
    )
    await ensure_fully_defined(adapter, "gooseneck bore sketch")
    check("exit_sketch gooseneck bore", await adapter.exit_sketch())
    name_last_feature(adapter, "GooseneckProfile")
    drive_jobs += gneck.apply(adapter, "GooseneckProfile")
    check(
        "cut gooseneck bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "GooseneckBore")
    v_gn = math.pi * (GOOSENECK_BORE_DIA / 2.0) ** 2 * (RING_HEIGHT + HUB_BOSS_DROP)
    volume = await volume_check(adapter, "gooseneck bore", volume - v_gn, 60.0)

    # 11. Hanger-stud clearance holes (1/2 close) through the crossbar,
    #     drilled from the underside seat plane (one wizard feature, both
    #     stations; the rear hole nicks the junction gusset -- material
    #     continues, the removal is a full cylinder either way).
    stud = await wizard_holes(
        adapter,
        STUD_HOLE_SPEC,
        [[BAR_X0 + 11.0, -HALF_H, STUD_Z_FRONT], [BAR_X0 + 11.0, -HALF_H, STUD_Z_REAR]],
        (0.0, -1.0, 0.0),
        "hanger stud holes",
        name="StudHoles",
        expect_dia_mm=STUD_HOLE_DIA,
    )
    v_studs = 2.0 * math.pi * (STUD_HOLE_DIA / 2.0) ** 2 * RING_HEIGHT
    volume = await volume_check(adapter, "hanger stud holes", volume - v_studs, 60.0)

    # 12. Side-screw taps (#10-24 x 14 blind): one per boss, on the
    #     spot-face seats, breaking into the column bores.
    v_side_tap = _side_tap_removal()
    for feat, x_pt, z_face in (
        ("SideTapFrontEast", -COLUMN_X, -SPOTFACE_FLOOR),
        ("SideTapFrontWest", COLUMN_X, -SPOTFACE_FLOOR),
        ("SideTapRearEast", -COLUMN_X, SPOTFACE_FLOOR),
        ("SideTapRearWest", COLUMN_X, SPOTFACE_FLOOR),
    ):
        normal = (0.0, 0.0, -1.0 if z_face < 0 else 1.0)
        await wizard_holes(
            adapter,
            SIDE_TAP_SPEC,
            [[x_pt, 0.0, z_face]],
            normal,
            f"side screw tap {feat}",
            name=feat,
            expect_dia_mm=TAP_DRILL_MM["#10-24"],
        )
        volume = await volume_check(
            adapter, f"side tap {feat}", volume - v_side_tap, 0.1 * v_side_tap + 10.0
        )

    # 13. Gooseneck set-screw tap (1/4-20 blind) on the pocket floor,
    #     through the rib into the bore.
    v_set_tap = _set_tap_removal()
    await wizard_holes(
        adapter,
        SET_TAP_SPEC,
        [[-(OUTER_X - SET_POCKET_DEPTH), 0.0, GOOSENECK_Z]],
        (-1.0, 0.0, 0.0),
        "gooseneck set-screw tap",
        name="GooseneckTap",
        expect_dia_mm=TAP_DRILL_MM["1/4-20"],
    )
    volume = await volume_check(
        adapter, "gooseneck set tap", volume - v_set_tap, 0.1 * v_set_tap + 10.0
    )

    # 14. Fulcrum-keeper taps (#10-24 x 10 blind) into the west rail TOP
    #     face: the two shaft-end keeper brackets' feet (ch17 p.40; the
    #     lever-pair ball mounts are replaced by keepers in channel.SLDASM).
    #     Solid flange + 27.1-thick web under both points -- exact blind
    #     volumes, no break-in.
    await wizard_holes(
        adapter,
        KEEPER_TAP_SPEC,
        [
            [KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_FRONT],
            [KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_REAR],
        ],
        (0.0, 1.0, 0.0),
        "fulcrum keeper taps",
        name="KeeperTaps",
        expect_dia_mm=TAP_DRILL_MM["#10-24"],
    )
    v_keeper = 2.0 * blind_hole_volume_mm3(TAP_DRILL_MM["#10-24"], 10.0)
    volume = await volume_check(adapter, "keeper taps", volume - v_keeper, 10.0)

    # Deferred drive equations: after the whole model + a rebuild exist so
    # every target resolves; the re-check proves the equations are neutral.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    set_dimension_symmetric_tolerance(
        adapter, "OuterProfile", "Width", OUTER_PROFILE_TOLERANCE_MM
    )
    set_dimension_symmetric_tolerance(
        adapter, "OuterProfile", "Depth", OUTER_PROFILE_TOLERANCE_MM
    )
    await volume_check(adapter, "driven casting (equations neutral)", volume, 200.0)

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
