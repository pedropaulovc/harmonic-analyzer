r"""Shared builder for the two column-clamp semi-arc shells (book ch. 21/22).

The ch30 p005 quarter view shows each platen-bar clamp as a BLACK two-piece
collar: a FRONT arc (bar side) and a BACK arc, each wrapping half the Ø25.4
column, with ears flanking the column closed by two screws. The screw stack
runs bar -> front-arc ear -> back-arc ear (threaded), heads on the bar's
front face (ch30 p002). Both shells are one rectangular block with the
column's half-cylinder relieved from the mating face and two ear holes along
the clamp axis -- only the block depth, which side the relief opens, and the
ear-hole diameter (clearance vs thread) differ, so one builder takes the
deltas.

Local frame (matches build_column_clamp.py): clamp axis (screw line) along
+X, column axis along Y through the origin, ears flanking at local z +-17.5;
the assembly rotates local +X to machine -Z. The FRONT arc spans local
x 0..DEPTH (relief opening -X, back face on the column-axis plane), the BACK
arc spans x -DEPTH..0 (relief opening +X).
"""

from __future__ import annotations

import math
from typing import Any

from _common import (
    PANEL_BLACK,
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
    name_last_feature,
    report_mass_properties,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

ARC_WIDTH = 48.0  # lateral (Z) span, ear tip to ear tip (old collar OD)
ARC_HALF_H = 8.0  # 16 tall along the column, like the old one-piece collar
COLUMN_BORE = 25.6  # half-cylinder relief: slides on the Ø25.4 column
EAR_HOLE_Z = 17.5  # ear screw line flanks the column (ch30 p002 heads)
MATERIAL = "Gray Cast Iron"  # black casting (ch30 p005)


async def build_arc(
    adapter: Any,
    *,
    part_name: str,
    depth: float,
    front: bool,
    hole_dia: float,
) -> dict[str, str]:
    """Build one semi-arc shell: ``front=True`` spans local x 0..depth (relief
    cut opening -X toward the column), ``front=False`` spans x -depth..0."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix is load-bearing -- INCH
    # document, the equation manager reads bare numbers in document units.
    await set_global(adapter, "ArcDepth", f"{depth}mm")
    await set_global(adapter, "ArcWidth", f"{ARC_WIDTH}mm")
    await set_global(adapter, "ArcHalfH", f"{ARC_HALF_H}mm")
    await set_global(adapter, "ColumnBore", f"{COLUMN_BORE}mm")
    await set_global(adapter, "HoleDia", f"{hole_dia}mm")

    drive_jobs: list[tuple[str, str]] = []

    x0, x1 = (0.0, depth) if front else (-depth, 0.0)

    # Block footprint on the Top plane (x depth, z lateral), extruded the
    # collar height about the bar's centre plane. Emission order (rectilinear
    # chain, anchor vertex 0 at (x0, -W/2)): seg0 depth, seg1 width, then the
    # non-zero anchor coords -- x only when the block starts off the column
    # plane (the back arc), z always.
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Top"))
    rect = [
        (x0, -ARC_WIDTH / 2.0),
        (x1, -ARC_WIDTH / 2.0),
        (x1, ARC_WIDTH / 2.0),
        (x0, ARC_WIDTH / 2.0),
    ]
    lines = await add_line_chain(adapter, rect)
    anchor_names = ["AnchorZ"] if front else ["AnchorX", "AnchorZ"]
    anchor_drives = ['"ArcWidth" / 2'] if front else ['"ArcDepth"', '"ArcWidth" / 2']
    await define_rectilinear_chain(
        adapter, lines, rect, label="block", dims=block,
        names=["Depth", "Width", *anchor_names],
        drives=['"ArcDepth"', '"ArcWidth"', *anchor_drives],
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * ARC_HALF_H, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Block")
    expected = depth * ARC_WIDTH * 2.0 * ARC_HALF_H
    await volume_check(adapter, "block", expected, 0.005 * expected)

    # Column relief: the Ø25.6 cylinder about the origin Y axis cut through.
    # The block sits on one side of the column-axis plane, so exactly the
    # half-disc leaves the mating face.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, COLUMN_BORE / 2.0, "column bore", dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"ColumnBore"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut column relief",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * ARC_HALF_H, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ColumnRelief")
    expected -= math.pi * (COLUMN_BORE / 2.0) ** 2 / 2.0 * 2.0 * ARC_HALF_H
    await volume_check(adapter, "column relief", expected, 0.01 * expected)

    # Ear screw holes: along the clamp axis (local X) at z +-EAR_HOLE_Z, bar
    # centre height. Right-plane sketch (x -> local Z, y -> local Y), cut
    # through both ways -- the ears are outside the bore, so each hole removes
    # a full-depth cylinder.
    ears = SketchDims()
    check("create_sketch ear holes", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    for label, z in (("Pos", EAR_HOLE_Z), ("Neg", -EAR_HOLE_Z)):
        await define_circle(
            adapter, z, 0.0, hole_dia / 2.0, f"ear hole {label}", dims=ears,
            names=(f"Ear{label}Z", f"Ear{label}Y", f"Ear{label}Dia"),
            drives=(None, None, '"HoleDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "ear holes sketch")
    check("exit_sketch ear holes", await adapter.exit_sketch())
    name_last_feature(adapter, "EarHoleProfile")
    drive_jobs += ears.apply(adapter, "EarHoleProfile")
    check(
        "cut ear holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.5 * depth, both_directions=True)
        ),
    )
    name_last_feature(adapter, "EarHoles")
    expected -= 2.0 * math.pi * (hole_dia / 2.0) ** 2 * depth
    await volume_check(adapter, "ear holes", expected, 0.01 * expected)

    # Deferred drive equations, then re-check neutrality (each evaluates to
    # the as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, f"driven {part_name} (equations neutral)", expected, 0.01 * expected
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, part_name)
