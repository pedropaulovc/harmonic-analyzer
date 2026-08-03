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
* Webbed faces (T-rail section): an 8-tall full-thickness top flange, then
  the web thins 3.5 per face and STAYS thin through the bottom edge (ch19
  img04/img05 + user read), with full-thickness lands at the bosses, hub
  rib and crossbar junctions.

Layout: plan profile in XZ, ring mid-plane extruded symmetrically in Y
(rails y -18.25..+18.25 local). Sketches on the Top plane use the
(x, y) -> (X, -Z) handedness; sketches on Right-plane offsets map
(x, y) -> (Z, Y) (build_rocker_arm_support precedent; NEGATIVE-offset
planes mirror sketch x -- see the gusset/pocket sites). Build order
(ADDITIVE T-section -- the web/flange rings are extruded, not pocketed):
web ring -> crossbar junction lands -> top-flange ring -> hub rib
restore -> crossbar+gussets -> corner bosses (up/down pair) -> hub boss
+ V-gussets -> set-screw pocket -> spot-faces -> column bores ->
gooseneck bore -> wizard holes (hanger-stud clearances, side-screw taps,
set-screw tap, keeper taps). Wizard holes come after the face cuts so
every seat face is final. Analytic volume checks after every feature;
the boss/hub/spot-face/tap expectations use small grid integrals (no
tidy closed form against the webbed solid).

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
    set_dimension_symmetric_tolerance,
)
from _visibility import blank_reference_geometry
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
# T-rail section (user-corrected vs ch19 img04): an 8-tall full-thickness top
# flange, below which the web thins by RECESS per face and STAYS thin through
# the bottom edge (no bottom flange). Built ADDITIVELY: a full-height thin web
# ring + an 8-tall full-width flange ring (two nested-rectangle sketches),
# plus full-thickness restore pads at the hub rib and the crossbar junctions.
# The corner bosses supply the corner lands.
FLANGE = 8.0  # top flange band (the only full-thickness band)
RECESS = 3.5  # web setback per face
FLANGE_BOT_Y = RING_HEIGHT / 2.0 - FLANGE  # +10.25 (flange underside)
WEB_OUT_X = OUTER_X - RECESS  # 210.6
WEB_IN_X = INNER_X + RECESS  # 183.4
WEB_OUT_Z = OUTER_Z - RECESS  # 127.5
WEB_IN_Z = INNER_Z + RECESS  # 96.5
LAND_X0 = BAR_X0 - GUSSET - 6.0  # -50; crossbar-junction land pads on the
LAND_X1 = BAR_X1 + GUSSET + 6.0  # +20; front/rear inner faces (6 margin)

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


def _in_web_plan(x: float, z: float) -> bool:
    """Full-height web-ring plan membership (NE-quadrant symmetric test)."""
    ax, az = abs(x), abs(z)
    return (WEB_IN_X <= ax <= WEB_OUT_X and az <= WEB_OUT_Z) or (
        WEB_IN_Z <= az <= WEB_OUT_Z and ax <= WEB_OUT_X
    )


def _in_flange_plan(x: float, z: float) -> bool:
    """Top-flange ring plan membership."""
    ax, az = abs(x), abs(z)
    return (INNER_X <= ax <= OUTER_X and az <= OUTER_Z) or (
        INNER_Z <= az <= OUTER_Z and ax <= OUTER_X
    )


def _boss_add_volumes() -> tuple[float, float]:
    """(up, down) volume ONE corner boss extrude pair adds to the T-section.

    Grid over the NE boss circle. Existing material per plan cell: web ring
    -> full band (-18.25..18.25); flange-only (the web setback crescents) ->
    10.25..18.25; else empty. BossUp fills y 0..22.75, BossDown 0..-24.55.
    All four corners match by symmetry (lands/rib/crossbar are far away).
    """
    r = BOSS_DIA / 2.0
    step = 0.05
    up = down = 0.0
    x = COLUMN_X - r
    while x < COLUMN_X + r:
        xx = x + 0.5 * step
        dx2 = (xx - COLUMN_X) ** 2
        if dx2 > r * r:
            x += step
            continue
        half = math.sqrt(r * r - dx2)
        z = abs(FRONT_COLUMN_Z) - half
        z_hi = abs(FRONT_COLUMN_Z) + half
        while z < z_hi:
            zz = z + 0.5 * step
            if zz < z_hi:
                da = step * step
                if _in_web_plan(xx, zz):
                    up += (BOSS_ABOVE) * da
                    down += (BOSS_BELOW) * da
                elif _in_flange_plan(xx, zz):
                    up += (HALF_H + BOSS_ABOVE - FLANGE) * da
                    down += (HALF_H + BOSS_BELOW) * da
                else:
                    up += (HALF_H + BOSS_ABOVE) * da
                    down += (HALF_H + BOSS_BELOW) * da
            z += step
        x += step
    return up, down


def _hub_boss_add_volume() -> float:
    """Volume the hub under-boss extrude (circle, y 0..-26.25) adds.

    Covered cells (hub rib plan or web ring) already hold -18.25..0, so the
    boss adds only the 8 below; the web-setback slivers (circle past the web
    faces, under the flange) are empty below +10.25 and gain the full 26.25.
    """
    r = HUB_BOSS_DIA / 2.0
    rib_lo = GOOSENECK_Z - HUB_RIB_W / 2.0
    rib_hi = GOOSENECK_Z + HUB_RIB_W / 2.0
    step = 0.02
    vol = 0.0
    x = GOOSENECK_X - r
    while x < GOOSENECK_X + r:
        xx = x + 0.5 * step
        dx2 = (xx - GOOSENECK_X) ** 2
        if dx2 > r * r:
            x += step
            continue
        half = math.sqrt(r * r - dx2)
        z = GOOSENECK_Z - half
        z_hi = GOOSENECK_Z + half
        while z < z_hi:
            zz = z + 0.5 * step
            if zz < z_hi:
                in_rib = rib_lo <= zz <= rib_hi and INNER_X <= abs(xx) <= OUTER_X
                covered = in_rib or _in_web_plan(xx, zz)
                vol += (
                    (HUB_BOSS_DROP if covered else HALF_H + HUB_BOSS_DROP) * step * step
                )
            z += step
        x += step
    return vol


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
    await set_global(adapter, "Recess", f"{RECESS}mm")
    await set_global(adapter, "Flange", f"{FLANGE}mm")
    await set_global(adapter, "OuterX", '"ColumnX" + "RailWSide" / 2')
    await set_global(adapter, "OuterZ", '"ColumnZ" + "RailWFR" / 2')
    await set_global(adapter, "InnerX", '"ColumnX" - "RailWSide" / 2')
    await set_global(adapter, "InnerZ", '"ColumnZ" - "RailWFR" / 2')

    drive_jobs: list[tuple[str, str]] = []
    ref_planes: list[str] = []  # created offset planes, blanked before save

    # 1. Web ring: the full-height THIN section (T-rail web) as one annular
    #    extrude -- two nested origin-centred rectangles, web faces RECESS
    #    inside the rail faces on every side.
    web = SketchDims()
    check("create_sketch web ring", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter,
        WEB_OUT_X,
        WEB_OUT_Z,
        "web outer rectangle",
        dims=web,
        name_width="Width",
        name_depth="Depth",
        drive_width='2 * ("OuterX" - "Recess")',
        drive_depth='2 * ("OuterZ" - "Recess")',
    )
    await define_centered_rectangle(
        adapter,
        WEB_IN_X,
        WEB_IN_Z,
        "web inner rectangle",
        dims=web,
        name_width="WinWidth",
        name_depth="WinDepth",
        drive_width='2 * ("InnerX" + "Recess")',
        drive_depth='2 * ("InnerZ" + "Recess")',
    )
    await ensure_fully_defined(adapter, "web ring sketch")
    check("exit_sketch web ring", await adapter.exit_sketch())
    name_last_feature(adapter, "WebProfile")
    drive_jobs += web.apply(adapter, "WebProfile")
    check(
        "extrude web ring",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "WebRing")
    v_web = 4.0 * (WEB_OUT_X * WEB_OUT_Z - WEB_IN_X * WEB_IN_Z) * RING_HEIGHT
    volume = await volume_check(adapter, "web ring", v_web, 0.001 * v_web)

    # 2. Crossbar junction lands: full-thickness pads on the front/rear
    #    inner faces where the crossbar + gussets butt in (x -50..20,
    #    z +/-(93..96.5)), full height. Sketch z flipped: (x, y) -> (X, -Z).
    lands = SketchDims()
    check("create_sketch junction lands", await adapter.create_sketch("Top"))
    for k, (z_lo, z_hi) in enumerate(((-WEB_IN_Z, -INNER_Z), (INNER_Z, WEB_IN_Z))):
        pts = [
            (LAND_X0, -z_hi),
            (LAND_X1, -z_hi),
            (LAND_X1, -z_lo),
            (LAND_X0, -z_lo),
        ]
        land_lines = await add_line_chain(adapter, pts)
        await define_rectilinear_chain(
            adapter,
            land_lines,
            pts,
            label=f"junction land {k}",
            dims=lands,
            names=[f"L{k}Run", f"L{k}Rise", f"L{k}OffX", f"L{k}OffZ"],
        )
    await ensure_fully_defined(adapter, "junction lands sketch")
    check("exit_sketch junction lands", await adapter.exit_sketch())
    name_last_feature(adapter, "LandProfile")
    drive_jobs += lands.apply(adapter, "LandProfile")
    check(
        "extrude junction lands",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "JunctionLands")
    v_lands = 2.0 * (LAND_X1 - LAND_X0) * RECESS * RING_HEIGHT
    volume = await volume_check(adapter, "junction lands", volume + v_lands, 50.0)

    # 3. Top flange ring: the full-width 8-tall band, extruded from the
    #    flange underside plane up to the rail top (extrude_at_offset,
    #    positive offset -- proven helper). The OUTER rectangle carries the
    #    print's marked Width/Depth dims (OuterProfile contract).
    outer = SketchDims()
    check("create_sketch flange ring", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter,
        OUTER_X,
        OUTER_Z,
        "flange outer rectangle",
        dims=outer,
        name_width="Width",
        name_depth="Depth",
        drive_width='2 * "OuterX"',
        drive_depth='2 * "OuterZ"',
    )
    await define_centered_rectangle(
        adapter,
        INNER_X,
        INNER_Z,
        "flange window rectangle",
        dims=outer,
        name_width="WinWidth",
        name_depth="WinDepth",
        drive_width='2 * "InnerX"',
        drive_depth='2 * "InnerZ"',
    )
    await ensure_fully_defined(adapter, "flange ring sketch")
    check("exit_sketch flange ring", await adapter.exit_sketch())
    name_last_feature(adapter, "OuterProfile")
    drive_jobs += outer.apply(adapter, "OuterProfile")
    extrude_at_offset(adapter, FLANGE, FLANGE_BOT_Y)
    name_last_feature(adapter, "TopFlange")
    # New material only where the flange band is not already web/land solid.
    v_flange = (
        4.0 * (OUTER_X * OUTER_Z - INNER_X * INNER_Z)
        - 4.0 * (WEB_OUT_X * WEB_OUT_Z - WEB_IN_X * WEB_IN_Z)
        - 2.0 * (LAND_X1 - LAND_X0) * RECESS
    ) * FLANGE
    volume = await volume_check(adapter, "top flange", volume + v_flange, 100.0)

    # 4. Hub rib restore: full rail thickness across the east rail at the
    #    gooseneck station, full height (the web setback comes back).
    rib = SketchDims()
    check("create_sketch hub rib", await adapter.create_sketch("Top"))
    rib_pts = [
        (-OUTER_X, -(GOOSENECK_Z + HUB_RIB_W / 2.0)),
        (-INNER_X, -(GOOSENECK_Z + HUB_RIB_W / 2.0)),
        (-INNER_X, -(GOOSENECK_Z - HUB_RIB_W / 2.0)),
        (-OUTER_X, -(GOOSENECK_Z - HUB_RIB_W / 2.0)),
    ]
    rib_lines = await add_line_chain(adapter, rib_pts)
    await define_rectilinear_chain(
        adapter,
        rib_lines,
        rib_pts,
        label="hub rib",
        dims=rib,
        names=["RibRun", "RibWidth", "RibOffX", "RibOffZ"],
    )
    await ensure_fully_defined(adapter, "hub rib sketch")
    check("exit_sketch hub rib", await adapter.exit_sketch())
    name_last_feature(adapter, "RibProfile")
    drive_jobs += rib.apply(adapter, "RibProfile")
    check(
        "extrude hub rib",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "HubRib")
    v_rib = 2.0 * RECESS * HUB_RIB_W * (RING_HEIGHT - FLANGE)
    volume = await volume_check(adapter, "hub rib", volume + v_rib, 30.0)

    # 5. Integral crossbar + plan gussets (one 8-vertex polygon, sketch z
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

    # 6. Corner bosses: one circle set extruded UP to the boss top, a second
    #    identical set extruded DOWN to the boss bottom (one-direction pair;
    #    a mid-plane extrude cannot land the asymmetric 22.75/24.55 split).
    #    Expected adds come from the T-section grid (web/flange/empty cells).
    v_boss_up, v_boss_down = _boss_add_volumes()
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
        v_add = 4.0 * (v_boss_up if updown == "up" else v_boss_down)
        volume = await volume_check(
            adapter,
            f"bosses {updown}",
            volume + v_add,
            0.005 * v_add + 50.0,
        )

    # 7. Gooseneck hub: underside boss (extruded down 26.25 from the Top
    #    plane; the covered plan adds the 8 below the underside, the web
    #    setback slivers fill their full 26.25) ...
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
    v_hub_boss_add = _hub_boss_add_volume()
    volume = await volume_check(
        adapter, "hub boss", volume + v_hub_boss_add, 0.01 * v_hub_boss_add + 20.0
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
    # Negative-offset plane: sketch x = -(model Z) (negative-offset plane mirror -- see the module docstring). The
    # trapezoid is authored mirrored so it lands centred on GOOSENECK_Z.
    gus_pts = [
        (-(GOOSENECK_Z - HUB_GUSSET_HALF_OUT), -HALF_H),
        (-(GOOSENECK_Z - HUB_GUSSET_HALF_IN), -HALF_H - HUB_BOSS_DROP),
        (-(GOOSENECK_Z + HUB_GUSSET_HALF_IN), -HALF_H - HUB_BOSS_DROP),
        (-(GOOSENECK_Z + HUB_GUSSET_HALF_OUT), -HALF_H),
    ]
    gus = SketchDims()
    check(
        "create_sketch hub gussets",
        await adapter.create_sketch(getattr(gusset_plane, "name", gusset_plane)),
    )
    ref_planes.append(str(getattr(gusset_plane, "name", gusset_plane)))
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
    v_gus_extra = v_hub_union - math.pi * (HUB_BOSS_DIA / 2.0) ** 2 * HUB_BOSS_DROP
    volume = await volume_check(
        adapter, "hub gussets", volume + v_gus_extra, 0.01 * v_gus_extra + 30.0
    )

    # 8. Set-screw cast pocket on the hub rib (east outer face, -X).
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
    ref_planes.append(str(getattr(pocket_plane, "name", pocket_plane)))
    half_p = SET_POCKET / 2.0
    # Negative-offset plane: sketch x = -(model Z) (negative-offset plane mirror -- see the module docstring).
    pk_pts = [
        (-(GOOSENECK_Z - half_p), -half_p),
        (-(GOOSENECK_Z + half_p), -half_p),
        (-(GOOSENECK_Z + half_p), half_p),
        (-(GOOSENECK_Z - half_p), half_p),
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

    # 9. Side-screw spot-faces: O9 x 0.9 flats on the curved boss z-faces
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
        ref_planes.append(str(getattr(spot_plane, "name", spot_plane)))
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

    # 10. Column bores (through the boss stacks).
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

    # 11. Gooseneck clearance bore (through the rib + hub boss).
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

    # 12. Hanger-stud clearance holes (1/2 close) through the crossbar,
    #     drilled from the underside seat plane (one wizard feature, both
    #     stations; the rear hole nicks the junction gusset -- material
    #     continues, the removal is a full cylinder either way).
    wizard_holes(
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

    # 13. Side-screw taps (#10-24 x 14 blind): one per boss, on the
    #     spot-face seats, breaking into the column bores.
    v_side_tap = _side_tap_removal()
    for feat, x_pt, z_face in (
        ("SideTapFrontEast", -COLUMN_X, -SPOTFACE_FLOOR),
        ("SideTapFrontWest", COLUMN_X, -SPOTFACE_FLOOR),
        ("SideTapRearEast", -COLUMN_X, SPOTFACE_FLOOR),
        ("SideTapRearWest", COLUMN_X, SPOTFACE_FLOOR),
    ):
        normal = (0.0, 0.0, -1.0 if z_face < 0 else 1.0)
        wizard_holes(
            adapter,
            SIDE_TAP_SPEC,
            [[x_pt, 0.0, z_face]],
            normal,
            f"side screw tap {feat}",
            name=feat,
            # blind tap: no expect_dia_mm (definition reads 0.0 on blinds)
        )
        volume = await volume_check(
            adapter, f"side tap {feat}", volume - v_side_tap, 0.1 * v_side_tap + 10.0
        )

    # 14. Gooseneck set-screw tap (1/4-20 blind) on the pocket floor,
    #     through the rib into the bore.
    v_set_tap = _set_tap_removal()
    wizard_holes(
        adapter,
        SET_TAP_SPEC,
        [[-(OUTER_X - SET_POCKET_DEPTH), 0.0, GOOSENECK_Z]],
        (-1.0, 0.0, 0.0),
        "gooseneck set-screw tap",
        name="GooseneckTap",
        # blind tap: no expect_dia_mm (definition reads 0.0 on blinds)
    )
    volume = await volume_check(
        adapter, "gooseneck set tap", volume - v_set_tap, 0.1 * v_set_tap + 10.0
    )

    # 15. Fulcrum-keeper taps (#10-24 x 10 blind) into the west rail TOP
    #     face: the two shaft-end keeper brackets' feet (ch17 p.40; the
    #     lever-pair ball mounts are replaced by keepers in channel.SLDASM).
    #     Solid flange + 27.1-thick web under both points -- exact blind
    #     volumes, no break-in.
    wizard_holes(
        adapter,
        KEEPER_TAP_SPEC,
        [
            [KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_FRONT],
            [KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_REAR],
        ],
        (0.0, 1.0, 0.0),
        "fulcrum keeper taps",
        name="KeeperTaps",
        # blind tap: no expect_dia_mm (definition reads 0.0 on blinds)
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

    # Hide the construction offset planes -- shown reference geometry renders
    # in the part PNG and every assembly instance (fix_shown_sketches idiom).
    blank_reference_geometry(adapter, tuple((name, "PLANE") for name in ref_planes))

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
