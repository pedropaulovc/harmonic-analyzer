r"""Reproduction script: cone pivot post (book ch. 12, p. 18 "pivot").

Black steel bearing post under the cone shaft's big-end journal, at the
machine front. The cone set swings horizontally out of mesh about this
point (ch. 12 notes; p. 18 top-down labels the black bracket "pivot"),
so the post carries the big-end journal at the drive height; the swing
function itself is not modeled -- the drive-train assembly places the
cone in its meshed position. Proportions estimated from the p. 18
top-down bracket silhouette (low confidence).

Dimensions: cad/DIMENSIONS.md ch. 13 "Drive supports" (estimated, low).

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
    IN,
    SketchDims,
    apply_material,
    name_bore_axis,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    name_ref_plane,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "cone-pivot-post"
MATERIAL = "Plain Carbon Steel"  # p.18: black steel bracket

BLOCK_WIDTH = 25.0  # X; p.18 bracket silhouette (scaled, low)
BLOCK_DEPTH = 20.0  # Z; p.18 bracket silhouette (scaled, low)
BLOCK_HEIGHT = 85.0  # journal at 76 + 9 of material above (low)
BORE_DIA = 0.375 * IN  # 9.525: cone shaft big-end diameter (ch. 12, legacy, med)
BORE_HEIGHT = 76.0  # ch13 layout: drive height above base top (med)
# Axial seat for the cone-gear-shaft pivot end (drive-train assembly mate). The
# shaft's pivot-end Front Plane seats coincident here instead of via a distance
# mate; the offset is the journal engagement -- the shaft origin sits this far
# toward the cone (local +Z, increasing cone station) from the post centre, and
# equals the drive-train assembly's |PIVOT_POST_STATION| (keep the two in sync).
CONE_SHAFT_SEAT_MM = 1.0

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
    await name_bore_axis(adapter, "Top Plane", 76.0, "Right Plane", 0.0, "journal axis")
    # Vertical swing pivot (Axis2): the local Y centreline through the plan
    # centre. The whole cone set swings HORIZONTALLY out of mesh about this post
    # (ch.12, p.18 "pivot"); the drive-train floats the post and rotates it about
    # this axis -- the p1 disengage DOF. The post is inserted with a pure Ry
    # incline, which leaves this axis vertical, so a rotation about it is the
    # horizontal swing the book describes.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "swing pivot")
    # Axial seat datum for the cone-gear-shaft pivot end (see CONE_SHAFT_SEAT_MM):
    # the assembly mates Front Plane@cone-gear-shaft coincident to this instead of
    # pinning a distance, so the drive train carries no distance mates.
    await name_ref_plane(
        adapter, "Front Plane", CONE_SHAFT_SEAT_MM, "cone_shaft_axial_seat"
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
