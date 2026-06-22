r"""Reproduction script: knife stay (book ch. 18, pp. 42-43).

The thin anchor rod + strap that steady the knife mount against the
spring pull: a O3 rod running along X above the top frame (from the west
column line past the machine centre) and a flat strap hooked over it,
descending diagonally to the knife block's face. Modeled as ONE part
(rod + strap merged where the strap's upper end overlaps the rod --
the p.43 hooked end collapsed; documented simplification).

Layout: origin on the rod axis at machine x 0 (machine (0, 1086, 0)),
rod along X (local -197..+20), strap from (x -10, rod) down to the
knife-mount stud's west flank at local (9.7, -33) = machine (9.7, 1053),
its end corner 0.44 short of the stud face and its low corner 1.5 above
the raised top crossbar (top 1051) (M6.4 reroute: the original drop to
the knife block at (5, 990) crossed the summing-lever plate band; M6.5
reroute: the lever spring tabs overhang to x -14.1 / y ~1070.1, so the
hook moved from -40 to -10 to keep the whole strap east of the tab tips).
Dimensions: cad/DIMENSIONS.md ch. 18 (M6.4, low).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_knife_stay.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "knife-stay"
MATERIAL = "Plain Carbon Steel"

ROD_DIA = 3.0  # DIMENSIONS.md ch18: thin anchor rod (low)
ROD_X = (-197.0, 20.0)  # west column line -> past centre (low)
STRAP_TOP = (-10.0, 0.0)  # strap hooks the rod here (M6.5: the levers'
# spring tabs OVERHANG 8 past the hole line to x -14.1 with tab tops at
# y ~1070.1 -- the former -40 hook sent the strap's lower edge through
# the two tab overhangs nearest z 0 (6.03/2.75 mm^3); the whole strap now
# stays east of x -10.9 > -14.1)
STRAP_BOT = (9.7, -33.0)  # knife-mount stud west flank at machine y 1053:
# the strap END CORNER (endpoint + half-thickness perpendicular, the
# steeper M6.5 run puts it at x 10.56) stays 0.44 clear of the stud's
# west tangent plane (x 11) and the strap's low corner (y 1052.5) stays
# 1.5 above the raised crossbar top 1051 (derived: a drop to the knife
# block itself would cross the summing-lever plate band x -45..+5 at
# y 987.46..992.54 -- the corrected coplanar .cs plate)
STRAP_HALF_W = 4.0  # strap 8 wide (z), 2 thick (low)
STRAP_HALF_T = 1.0


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 197 = 197 in). Only the rod diameter maps
    # to a single sketch dim (driven below); the rod's X extents are the rod
    # extrude's offset/depth (feature parameters, not sketch dims), and the
    # strap profile's dims are trig blends of the two strap endpoints + the
    # half-thickness (no single-global knob), so those globals are editable
    # knobs with nothing driven off them -- matching the exemplar note that a
    # declared-but-undriven global is fine.
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "RodX0", f"{ROD_X[0]}mm")
    await set_global(adapter, "RodX1", f"{ROD_X[1]}mm")
    await set_global(adapter, "StrapTopX", f"{STRAP_TOP[0]}mm")
    await set_global(adapter, "StrapTopY", f"{STRAP_TOP[1]}mm")
    await set_global(adapter, "StrapBotX", f"{STRAP_BOT[0]}mm")
    await set_global(adapter, "StrapBotY", f"{STRAP_BOT[1]}mm")
    await set_global(adapter, "StrapHalfW", f"{STRAP_HALF_W}mm")
    await set_global(adapter, "StrapHalfT", f"{STRAP_HALF_T}mm")

    drive_jobs: list[tuple[str, str]] = []

    # 1. Rod along X: an extruded circle, NOT a revolved rectangle -- a
    # 360-degree revolve of an on-axis profile leaves a degenerate axis
    # edge in the b-rep, and every boolean that crosses that axis (the
    # strap below) fails (probed live: extrude+merge and revolve-second
    # both refuse; the extruded rod merges fine). The circle sits on the
    # part origin, so the Right-plane axis-mapping ambiguity is moot.
    # On-axis circle: only the diameter is a dim (centre X/Z are origin
    # relations), so define_circle records just Dia.
    rod = SketchDims()
    check("create_sketch rod", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    await define_circle(
        adapter, 0.0, 0.0, ROD_DIA / 2.0, "rod circle", dims=rod,
        names=("RodCx", "RodCz", "RodDia"),
        drives=(None, None, '"RodDia"'),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "rod sketch")
    check("exit_sketch rod", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += rod.apply(adapter, "RodProfile")
    rod_len = ROD_X[1] - ROD_X[0]
    extrude_at_offset(adapter, rod_len, ROD_X[0])
    name_last_feature(adapter, "Rod")
    expected = math.pi * (ROD_DIA / 2.0) ** 2 * rod_len
    await volume_check(adapter, "rod", expected, 0.005 * expected)
    res = await adapter.get_mass_properties()
    com_x = float(res.data.center_of_mass[0])
    rod_mid = (ROD_X[0] + ROD_X[1]) / 2.0
    if abs(com_x - rod_mid) > 0.5:
        raise RuntimeError(
            f"rod extruded the wrong way: COM x {com_x:.1f}, expected {rod_mid:.1f}"
        )

    # 2. Diagonal strap (Front sketch quad, mid-plane along Z). A general
    # (non-axis-parallel) quad -> define_polygon_chain. Its dims are trig
    # blends of the two endpoints + the perpendicular half-thickness, with no
    # single-global equation, so every slot is left None (auto-named, static)
    # per the spec's "no meaningful global knob" rule. Emission order (anchor
    # vertex 0, both coords != 0 -> two anchor dims x,z; then each kept
    # segment's horizontal+vertical offsets in line order, the segment ending
    # at the anchor vertex skipped): 2 anchor + 3 segments x 2 = 8 dims.
    dx = STRAP_BOT[0] - STRAP_TOP[0]
    dy = STRAP_BOT[1] - STRAP_TOP[1]
    length = math.hypot(dx, dy)
    px, py = -dy / length * STRAP_HALF_T, dx / length * STRAP_HALF_T
    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    strap_pts = [
        (STRAP_TOP[0] - px, STRAP_TOP[1] - py),
        (STRAP_TOP[0] + px, STRAP_TOP[1] + py),
        (STRAP_BOT[0] + px, STRAP_BOT[1] + py),
        (STRAP_BOT[0] - px, STRAP_BOT[1] - py),
    ]
    strap_lines = await add_line_chain(adapter, strap_pts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(
        adapter, strap_lines, strap_pts, label="strap", dims=strap,
        names=[None] * 8,
        drives=[None] * 8,
    )
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapProfile")
    drive_jobs += strap.apply(adapter, "StrapProfile")
    # Raw-COM start-offset extrude: the adapter's mid-plane extrusion fails
    # on this direct-db quad ("Failed to create extrusion feature"), while
    # the offset path is the proven recipe for direct-db sketches.
    extrude_at_offset(adapter, 2.0 * STRAP_HALF_W, -STRAP_HALF_W)
    name_last_feature(adapter, "Strap")
    # The strap's upper end MERGES into the rod, so the solid adds slightly
    # LESS than the standalone strap box -- the original check accepted added
    # volume in [0.90, 1.01] * v_strap. Reproduce that asymmetric band exactly
    # as expected +/- tol: centre = rod + 0.955 * v_strap, tol = 0.055 * v_strap.
    v_strap = length * 2.0 * STRAP_HALF_T * 2.0 * STRAP_HALF_W
    strap_tol = 0.055 * v_strap
    expected += 0.955 * v_strap
    await volume_check(adapter, "strap", expected, strap_tol)

    # Apply the deferred drive equations after the model exists, then re-check:
    # every equation evaluates to the value just built, so geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven knife stay (equations neutral)", expected, strap_tol
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
