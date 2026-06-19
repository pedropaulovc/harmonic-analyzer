r"""Reproduction script: rocker arm support (book ch. 14 / ch. 30 views; 1 used).

Solid green-painted cast-iron tapered frustum carrying the BACK (north,
z +101.6) end of the rocker-pivot shaft: base 88.9 x 40 tapering to
20 x 20 at the apex over 177.8 (7") tall. A ball mount (separate part)
seats on the apex and holds the Ø6.35 pivot shaft at 25.2 above it,
putting the pivot axis at machine y = 228.6 + 25.2 = 253.8. An integral
boss on the west flank (Ø20 about local (-25.4, 76), axis Z; east before
the M6.8 machine mirror) carries a Ø9.7 through-bore that clamps the
north end of the stationary cylinder arbor
(machine (x, y) = (+47.5, 126.8)) - the back view (p5) shows the
drum running straight into this casting with no separate pedestal, and
the v3 side view shows the arbor end buried in the green flank.

M6.9 REINSTATES the windowed-frame reading that M6.3/M6.5 refuted: the
brightened ch. 30 p008 (+x side) view plainly shows the legacy windowed
portal frame (~184 wide, ~127 window) - this frustum is its NORTH
upright, the transgear A-frame its SOUTH upright (z -111, clevis grips
the south pivot ball - see build_a_frame.py, which also carries the
frame's top and foot rails). The earlier refutation came from the -x
side view, where the cone/drum hides the frame. What M6.5 did refute and
stays refuted: a second free-standing SOUTH frustum. The p008 uprights
read ~28-40 deep and near-uniform, so the legacy strong side taper
(63.5 -> 16.9) is replaced by 40 -> 20; the front-view X-taper
(88.9 -> 20) and 7" height are photo-confirmed and survive.

Dimensions: cad/DIMENSIONS.md ch. 14 "Rocker pivot & supports layout"
(photo + legacy height, med); mounting holes legacy 5/16" (low).

Built as the side-view trapezoid extruded across X, then two Front-plane
wedge cuts forming the X-taper - NOT a loft: the offset plane a loft's
top profile needs is side-ambiguous live, while the Front-plane sketch
mapping (x, y) -> global (X, Y) is exact. The Right-plane trapezoid is
symmetric in sketch x, so that plane's handedness does not matter.

Layout: origin at the base centre, height +Y, base 88.9 along X / 63.5
along Z. Mounting holes are Ø7.9 x 25 sockets up from the base underside
(the hold-down lag-screws come up through the base -- modeled in the
M6.10 fasteners pass, placed in frame.SLDASM), cut mid-plane so the cut
direction never matters. The arbor
boss extrudes from z -27.5 (machine z +74.1: 0.6 clear of the j=19
connecting-rod ring at z <= +73.5) back to the sketch plane z 0, merging
into the tapered flank; its added volume and the bore's removal are gated
by grid integration over the taper (no tidy closed form).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_rocker_arm_support.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    IN,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "rocker-arm-support"
MATERIAL = "Gray Cast Iron"  # green-painted frustum (ch30/photogrammetry)

TOTAL_HEIGHT = 7.00 * IN  # 177.8  DIMENSIONS.md ch14 layout: legacy height kept (med)
BASE_X = 3.50 * IN  # 88.9   ch14 layout: front-view triangle base (photo, med)
BASE_Z = 40.0  # ch14 layout: side-view depth at the base (ch30 p008, M6.9, med)
TOP_X = 20.0  # ch14 layout: apex width under the ball-mount foot (photo, med)
TOP_Z = 20.0  # ch14 layout: side-view depth at the apex (ch30 p008, M6.9, med)
MOUNTING_HOLE_DIA = 0.3125 * IN  # 7.94  legacy 5/16" hold-down (low)
MOUNTING_HOLE_SPACING = 2.5 * IN  # 63.5  legacy hole pitch across X (low)
MOUNTING_HOLE_DEPTH = 25.0  # socket depth up from the base underside (low)

WEDGE_CUT_DEPTH = BASE_Z * 2.5  # mid-plane total; > base depth
HOLE_CUT_DEPTH = 2.0 * MOUNTING_HOLE_DEPTH  # mid-plane total about y = 0

# Arbor clamp boss on the west flank (M6.5; east->west in the M6.8 machine
# mirror): the cylinder arbor at machine
# (x, y) = (+47.5, 126.8) = local (-25.4, 76.0) clamps into this casting
# (back view p5: the drum runs into the green flank; no north pedestal).
BOSS_X = -25.4  # local x of the arbor axis (= 47.5 - 72.9)
BOSS_Y = 76.0  # drive height above the base top
BOSS_DIA = 20.0  # boss OD around the bore (function-driven, low)
BOSS_Z_FRONT = -27.5  # boss face: machine z 74.1, 0.6 clear of the j=19 rod ring
BORE_DIA = 9.7  # arbor Ø9.525 + slip clearance
BORE_CUT_DEPTH = 70.0  # mid-plane total; > boss + body depth


def _taper_half_widths(y: float) -> tuple[float, float]:
    """Body half-width (X) and half-depth (Z) at height y (linear taper)."""
    s = y / TOTAL_HEIGHT
    half_w = BASE_X / 2.0 + (TOP_X / 2.0 - BASE_X / 2.0) * s
    half_d = BASE_Z / 2.0 + (TOP_Z / 2.0 - BASE_Z / 2.0) * s
    return half_w, half_d


def _grid_circle_volume(radius: float, boss_only: bool, step: float = 0.02) -> float:
    """Grid-integrate material length along Z over a circle at (BOSS_X, BOSS_Y).

    boss_only=True: volume the boss ADDS (z BOSS_Z_FRONT..0 outside the body).
    boss_only=False: material the bore REMOVES (boss span + body span).
    """
    n = int(2.0 * radius / step)
    total = 0.0
    for i in range(n):
        x = BOSS_X - radius + (i + 0.5) * step
        half_chord_sq = radius * radius - (x - BOSS_X) ** 2
        if half_chord_sq <= 0.0:
            continue
        dy = math.sqrt(half_chord_sq)
        m = int(2.0 * dy / step)
        for j in range(m):
            y = BOSS_Y - dy + (j + 0.5) * step
            half_w, half_d = _taper_half_widths(y)
            inside = abs(x) <= half_w
            if boss_only:
                length = -BOSS_Z_FRONT - half_d if inside else -BOSS_Z_FRONT
                total += max(0.0, length) * step * step
                continue
            length = (-BOSS_Z_FRONT + half_d) if inside else -BOSS_Z_FRONT
            total += length * step * step
    return total


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    # Side-view trapezoid (Z taper), extruded mid-plane across X.
    check("create_sketch trapezoid", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    trapezoid_pts = [
        (-BASE_Z / 2.0, 0.0),
        (BASE_Z / 2.0, 0.0),
        (TOP_Z / 2.0, TOTAL_HEIGHT),
        (-TOP_Z / 2.0, TOTAL_HEIGHT),
    ]
    lines = await add_line_chain(adapter, trapezoid_pts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(adapter, lines, trapezoid_pts, label="trapezoid")
    await ensure_fully_defined(adapter, "trapezoid sketch")
    check("exit_sketch trapezoid", await adapter.exit_sketch())
    check(
        "extrude trapezoid",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BASE_X, both_directions=True)
        ),
    )
    v_slab = (BASE_Z + TOP_Z) / 2.0 * TOTAL_HEIGHT * BASE_X
    volume = await volume_check(adapter, "trapezoid slab", v_slab, 0.005 * v_slab)

    # X taper: two wedge cuts on the Front plane (mapping (x, y) -> (X, Y)
    # is exact - no handedness probe needed).
    check("create_sketch wedges", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    margin = 15.0  # wedge outer edge clear of the base corner
    left_pts = [
        (-BASE_X / 2.0, 0.0),
        (-TOP_X / 2.0, TOTAL_HEIGHT),
        (-BASE_X / 2.0 - margin, TOTAL_HEIGHT),
        (-BASE_X / 2.0 - margin, 0.0),
    ]
    right_pts = [
        (BASE_X / 2.0, 0.0),
        (TOP_X / 2.0, TOTAL_HEIGHT),
        (BASE_X / 2.0 + margin, TOTAL_HEIGHT),
        (BASE_X / 2.0 + margin, 0.0),
    ]
    left = await add_line_chain(adapter, left_pts)
    right = await add_line_chain(adapter, right_pts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(adapter, left, left_pts, label="left wedge")
    await define_polygon_chain(adapter, right, right_pts, label="right wedge")
    await ensure_fully_defined(adapter, "wedges sketch")
    check("exit_sketch wedges", await adapter.exit_sketch())
    check(
        "cut wedges",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=WEDGE_CUT_DEPTH, both_directions=True)
        ),
    )
    # Frustum volume via the prismatoid integral: w(s) = BASE_X..TOP_X,
    # d(s) = BASE_Z..TOP_Z linear in s; V = H * integral(w * d).
    a0 = BASE_X * BASE_Z
    a1 = BASE_X * (TOP_Z - BASE_Z) + BASE_Z * (TOP_X - BASE_X)
    a2 = (TOP_X - BASE_X) * (TOP_Z - BASE_Z)
    v_frustum = TOTAL_HEIGHT * (a0 + a1 / 2.0 + a2 / 3.0)
    volume = await volume_check(adapter, "frustum", v_frustum, 0.005 * v_frustum)

    # Hold-down screw sockets up from the base underside; mid-plane cut
    # about y = 0 so only the +Y half removes material.
    check("create_sketch holes", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        -MOUNTING_HOLE_SPACING / 2.0,
        0.0,
        MOUNTING_HOLE_DIA / 2.0,
        "mounting hole left",
    )
    await define_circle(
        adapter,
        MOUNTING_HOLE_SPACING / 2.0,
        0.0,
        MOUNTING_HOLE_DIA / 2.0,
        "mounting hole right",
    )
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    check(
        "cut mounting holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=HOLE_CUT_DEPTH, both_directions=True)
        ),
    )
    v_holes = 2.0 * math.pi * (MOUNTING_HOLE_DIA / 2.0) ** 2 * MOUNTING_HOLE_DEPTH
    volume = await volume_check(
        adapter, "mounting holes", volume - v_holes, 0.01 * v_holes + 5.0
    )

    # Arbor clamp boss on the east flank (Front sketch (x, y) -> (X, Y),
    # extruded from z = BOSS_Z_FRONT back to the sketch plane).
    check("create_sketch boss", await adapter.create_sketch("Front"))
    await define_circle(adapter, BOSS_X, BOSS_Y, BOSS_DIA / 2.0, "arbor boss")
    await ensure_fully_defined(adapter, "boss sketch")
    check("exit_sketch boss", await adapter.exit_sketch())
    extrude_at_offset(adapter, -BOSS_Z_FRONT, BOSS_Z_FRONT)
    v_boss = _grid_circle_volume(BOSS_DIA / 2.0, boss_only=True)
    volume = await volume_check(adapter, "arbor boss", volume + v_boss, 0.02 * v_boss)

    # Arbor through-bore along Z (mid-plane cut: direction never matters).
    check("create_sketch arbor bore", await adapter.create_sketch("Front"))
    await define_circle(adapter, BOSS_X, BOSS_Y, BORE_DIA / 2.0, "arbor bore")
    await ensure_fully_defined(adapter, "arbor bore sketch")
    check("exit_sketch arbor bore", await adapter.exit_sketch())
    check(
        "cut arbor bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BORE_CUT_DEPTH, both_directions=True)
        ),
    )
    v_bore = _grid_circle_volume(BORE_DIA / 2.0, boss_only=False)
    await volume_check(adapter, "arbor bore", volume - v_bore, 0.02 * v_bore)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
