r"""Reproduction script: cone pivot post (book ch. 12, p. 18 "pivot").

Green bearing post under the cone shaft's big-end journal, at the
machine front. The cone set swings horizontally out of mesh about this
point (ch. 12 notes; p. 18 top-down labels the bracket "pivot"), so the
post carries the big-end journal at the drive height. The ch30 GT re-read
(2026-07-02) moved the drive plane down to 54 above the base top and slid
the post forward (station -12.25): it now sits between the 64T and the
crank-pedestal slab, the shaft's front stub running on through its bore
to the proud end boss the photos show (GT cone_front). The eight-views
show it green, part of one continuous casting complex with the pedestal
-- repainted CASTING_GREEN and grown to 32 x 26 to match that silhouette.

Dimensions: cad/DIMENSIONS.md ch. 13 "Drive supports" (estimated, low;
heights + colour re-read from the ch30 GT).

Layout: block standing on the Top plane, centred at the origin in plan
(X width x Z depth), journal bore along Z at y = BORE_HEIGHT (the
assembly rotates the post 19.8 deg about Y to align with the cone axis).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_pivot_post.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    IN,
    SketchDims,
    apply_color,
    apply_material,
    name_bore_axis,
    check,
    define_centered_rectangle,
    define_circle,
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

PART_NAME = "cone-pivot-post"
MATERIAL = "Gray Cast Iron"  # ch30 GT: green-painted casting, one complex with
# the crank pedestal (was black steel per the p.18 b/w read)

BLOCK_WIDTH = 32.0  # X; ch30 eight-views silhouette (scaled, low)
BLOCK_DEPTH = 26.0  # Z; ch30 eight-views silhouette (scaled, low)
BLOCK_HEIGHT = 63.0  # journal at 54 + 9 of material above (low)
BORE_DIA = 0.375 * IN  # 9.525: cone shaft big-end diameter (ch. 12, legacy, med)
BORE_HEIGHT = 54.0  # ch30 GT: drive height above base top (was 76)

BORE_RADIUS = BORE_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the block envelope and the journal
    # bore. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units (an unsuffixed 85 =
    # 85 in, blowing the part up 25.4x). BoreDia carries the legacy 0.375" value
    # already reduced to mm.
    await set_global(adapter, "BlockWidth", f"{BLOCK_WIDTH}mm")
    await set_global(adapter, "BlockDepth", f"{BLOCK_DEPTH}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHeight", f"{BORE_HEIGHT}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Origin-centred block footprint: width along X, depth along Z.
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, BLOCK_WIDTH / 2.0, BLOCK_DEPTH / 2.0, "block", dims=block,
        name_width="Width", drive_width='"BlockWidth"',
        name_depth="Depth", drive_depth='"BlockDepth"',
        name_corner=("CornerX", "CornerZ"),
        drive_corner=('"BlockWidth" / 2', '"BlockDepth" / 2'),
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    name_last_feature(adapter, "Block")
    v_block = BLOCK_WIDTH * BLOCK_DEPTH * BLOCK_HEIGHT
    volume = await volume_check(adapter, "block", v_block, 0.005 * v_block)

    # Big-end journal bore along Z at the drive height. On-axis in X (centre x 0,
    # a relation), so define_circle records only the centre-Z + diameter dims.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_HEIGHT, BORE_RADIUS, "bore", dims=bore,
        names=("BoreX", "BoreZ", "BoreDia"),
        drives=(None, '"BoreHeight"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BLOCK_DEPTH + 4.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "JournalBore")
    v_bore = math.pi * BORE_RADIUS**2 * BLOCK_DEPTH
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Apply the deferred drive equations after the model + a rebuild exist, then
    # re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven post (equations neutral)", volume, 0.01 * v_bore)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", BORE_HEIGHT, "Right Plane", 0.0, "journal axis")
    # Vertical swing pivot (Axis2): the local Y centreline through the plan
    # centre. The whole cone set swings HORIZONTALLY out of mesh about this post
    # (ch.12, p.18 "pivot"); the drive-train floats the post and rotates it about
    # this axis -- the p1 disengage DOF. The post is inserted with a pure Ry
    # incline, which leaves this axis vertical, so a rotation about it is the
    # horizontal swing the book describes.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "swing pivot")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
