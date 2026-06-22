r"""Reproduction script: knife bearing support (book ch. 18, pp. 42-43).

The cast bearing block that suspends the summing lever's knife edge from the
top crossbar. The lever rocks as a FIRST-CLASS LEVER on the **top vertex line
of its hexagonal pivot trunnions** (build_summing_lever ``_hex_collar``); each
trunnion overhangs the lever body into one of these supports.

DESIGN (user direction, 2026-06-17, refs: ch30-p003, bore.png, ch18 p.43 photo):
a **circular bore much larger than the hex trunnion**, so that *only the top
knife edge of the trunnion* nears the bore -- the upper inner wall of the bore
comes down to the hex's top vertex line while every other facet clears by
millimetres. This is the true knife-edge suspension: line contact at the ridge,
free to rock, replacing the M6.4 "diamond knife-bar in the lever tube bore"
(which clashed with the lever's solid pivot cylinder once the bore was removed).

There are TWO supports, one per trunnion (placed front/back in the assembly at
|z| ~ 87). This single part is built once and placed twice.

Layout (part-local): origin = the **knife-edge contact line** = the hex top
vertex ridge (placed at machine (15, 995.13, +-87)); local Z = the bore/trunnion
axis, +Y up, +X across. The bore centre sits ``R_BORE`` below the origin so the
bore's upper inner wall lands on the ridge (with a TOP_CLEAR sliver margin). The
block rises from below the bore up to the top-crossbar lower face (held there).

The named "knife axis" is the contact ridge line itself (part origin); the
assembly mates the lever's knife ridge (``Axis3@summing-lever``) coincident to
it, so the lever rocks about the true knife edge (not the cylinder centre).

Dimensions: cad/DIMENSIONS.md ch. 18. Bore/clearance: low confidence (tune vs
ch30 parity); the only hard constraint is "only the top edge contacts".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_knife_mount.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    PANEL_BLACK,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from build_summing_lever import HEX_H, HEX_W

PART_NAME = "knife-mount"
MATERIAL = "Gray Cast Iron"  # cast bearing bracket, painted dark (ch18 p.43)

# --- knife-edge geometry (kept in sync with the lever's hex trunnion) -------
RIDGE_Y = HEX_H / 2.0  # hex top vertex above the pivot/cylinder centreline (5.134)

# --- bore: "much larger than the hex trunnion", top-edge contact only -------
R_BORE = 12.7  # Ø25.4 bore; hex is only ~Ø10.3 across-corners -> much larger
TOP_CLEAR = 0.25  # hex top vertex hangs this far below the bore upper inner wall
# Bore centre BELOW the origin so only the upper wall reaches the ridge:
BORE_CY = TOP_CLEAR - R_BORE  # -12.45 (bore top inner wall at local y +TOP_CLEAR)

# --- block (bearing body, held to the crossbar) ----------------------------
SUPPORT_Z_THICK = 14.0  # axial length straddling the trunnion mid (low)
BLK_HALF_X = 17.0  # bore wall + flank
WALL = 4.0  # material below the bore
BLK_BOT = BORE_CY - R_BORE - WALL  # -29.15

# Mount: the block top abuts the top-crossbar lower face (held to the top frame).
KNIFE_Y = 990.0  # machine y of the pivot centreline (build_summing_assembly KNIFE)
CROSSBAR_BOTTOM_Y = 1010.0  # top-crossbar lower face (build_summing_assembly)
MOUNT_GAP = 0.25  # design clearance to the crossbar (sliver-flag margin)
CONTACT_Y = KNIFE_Y + RIDGE_Y  # machine y of the knife-edge contact line (995.13)
BLK_TOP = CROSSBAR_BOTTOM_Y - CONTACT_Y - MOUNT_GAP  # local top (14.62)

THROUGH_CUT_DEPTH = SUPPORT_Z_THICK + 4.0  # > the block thickness, both directions


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the bore radius + its top clearance,
    # the block half-width / wall / axial thickness, and the local block top. The
    # derived globals (BoreCy / BlkBot) are equations of the primitives so the
    # bore centre and block bottom track when a primitive changes. The mm suffix
    # is load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 12.7 = 12.7 in, 25.4x too big).
    await set_global(adapter, "RBore", f"{R_BORE}mm")
    await set_global(adapter, "TopClear", f"{TOP_CLEAR}mm")
    await set_global(adapter, "SupportZThick", f"{SUPPORT_Z_THICK}mm")
    await set_global(adapter, "BlkHalfX", f"{BLK_HALF_X}mm")
    await set_global(adapter, "Wall", f"{WALL}mm")
    await set_global(adapter, "BlkTop", f"{BLK_TOP}mm")
    await set_global(adapter, "BoreCy", '"TopClear" - "RBore"')
    await set_global(adapter, "BlkBot", '"BoreCy" - "RBore" - "Wall"')

    # Each sketch records its dim names + drive equations as the define_* helper
    # emits them; the equations are collected here and applied in one deferred
    # batch at the end (every target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Bearing block: Front-plane rectangle, mid-plane extrude along Z (the
    #    bore/trunnion axis), straddling the trunnion mid. Asymmetric in Y (not
    #    origin-centred), so a generic rectilinear chain, not define_centered_*.
    #    Emission order (anchor vertex 0 at (-BlkHalfX, BlkBot)): the width dim
    #    (seg 0), the height dim (seg 1), then the anchor dims (x, then z).
    block_dims = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Front"))
    block_rect = [
        (-BLK_HALF_X, BLK_BOT),
        (BLK_HALF_X, BLK_BOT),
        (BLK_HALF_X, BLK_TOP),
        (-BLK_HALF_X, BLK_TOP),
    ]
    block = await add_line_chain(adapter, block_rect)
    await define_rectilinear_chain(
        adapter, block, block_rect, label="block", dims=block_dims,
        names=["BlockWidth", "BlockHeight", "BlockAnchorX", "BlockAnchorZ"],
        drives=[
            '2 * "BlkHalfX"',
            '"BlkTop" - "BlkBot"',
            '"BlkHalfX"',
            '-"BlkBot"',
        ],
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block_dims.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SUPPORT_Z_THICK, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Block")
    expected = 2.0 * BLK_HALF_X * (BLK_TOP - BLK_BOT) * SUPPORT_Z_THICK
    vol = await _volume(adapter)
    print(f"  volume after block: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"block volume {vol:.1f} != {expected:.1f}")

    # 2. Circular bore through the block (the trunnion rides inside; only the
    #    hex top vertex nears the upper inner wall). Centred TOP_CLEAR below the
    #    ridge so the rest of the hex clears. On the Y-axis (x 0): only the
    #    centre-Z + diameter are dims (the X is a relation).
    bore_dims = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_CY, R_BORE, "knife bore", dims=bore_dims,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, '-"BoreCy"', '2 * "RBore"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore_dims.apply(adapter, "BoreProfile")
    check(
        "cut knife bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "KnifeBore")
    expected -= math.pi * R_BORE**2 * SUPPORT_Z_THICK
    vol = await _volume(adapter)
    print(f"  volume after bore: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"bore volume {vol:.1f} != {expected:.1f}")

    # Sanity: hex must fit the bore with only the top vertex near the wall.
    hex_top = 0.0  # ridge = origin
    gap_top = (BORE_CY + R_BORE) - hex_top
    if not 0.0 < gap_top < 0.5:
        raise RuntimeError(f"top-edge gap {gap_top:.3f} mm out of (0, 0.5)")
    # widest hex point (shoulder at +-HEX_W/2, y = -RIDGE_Y +- HEX_H/4) must
    # clear the bore wall.
    for sy in (-RIDGE_Y + HEX_H / 4.0, -RIDGE_Y - HEX_H / 4.0):
        d = math.hypot(HEX_W / 2.0, sy - BORE_CY)
        if d > R_BORE - 0.5:
            raise RuntimeError(f"hex shoulder {d:.3f} mm too close to Ø{2*R_BORE} bore")

    # Named axis = the knife-edge contact ridge line (part origin, along Z). The
    # assembly mates Axis3@summing-lever (the hex ridge) coincident to it.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "knife axis")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check: each equation evaluates to the value just built, so
    # the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven knife mount (equations neutral)", expected, 0.01 * expected
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)  # ch30 plates: see _common palette
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
