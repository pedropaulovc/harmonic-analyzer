r"""Reproduction script: pen v-block (book ch. 24, pp. 64-65).

The chunky brass block that seats the marker: chamfered top corners, two
vertical bores, a stopped horizontal slit from one end (the flexing clamp
jaw -- it must NOT run the full length or the block would fall apart) and
a front #5-40 UNC tapped hole (a real Hole Wizard smart hole) for the set
screw. This is the modern replacement pen holder (Harland/Wilson)
documented by the book photos; the marker itself is a consumable, not
modelled.

Dimensions: cad/DIMENSIONS.md "Chapter 24" — all scaled from the p.65
close-up vs the ~5 mm square rod (low).

Layout: length along +X, height along +Y from the origin corner, depth
extruded +Z. Vertical bores cut from a Top-plane sketch (maps (x, y) ->
global (X, -Z)); slit and front hole from Front-plane sketches.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_v_block.py
"""

from __future__ import annotations

import sys

from _common import (
    CASTING_GREEN,
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
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
    set_sketch_direct_db,
    volume_check,
)

import _telemetry

PART_NAME = "pen-v-block"
MATERIAL = "Brass"  # see _common.apply_material docstring

BLOCK_LENGTH = 32.0  # X  DIMENSIONS.md ch24: p.65 vs 5 mm rod (low)
BLOCK_HEIGHT = 18.0  # Y
BLOCK_DEPTH = 16.0  # Z
CHAMFER = 6.0  # 45 deg top corners
BORE_DIA = 8.0  # two vertical bores
BORE_X = (11.0, 21.0)
SLIT_LENGTH = 26.0  # stopped cut from x=0; hinge remains 26..32
SLIT_Y = (4.0, 8.0)  # slit band
# Front-face set-screw hole: a Hole Wizard #5-40 UNC tapped THROUGH hole. Inch
# (Unified) per docs/tolerance-gdt-assessment.md §5.5 -- the machine is an inch
# machine, so NOT metric M3 ("don't force the M form onto an inch thread"). The
# tap-drill diameter comes from the #5-40 table, so there is no ScrewHoleDia knob.
SCREW_HOLE_SIZE = "#5-40"
SCREW_HOLE_XY = (29.0, 11.0)

THROUGH_CUT_DEPTH = 80.0  # mid-plane total; > any extent crossed


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, TappedHoleParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the block envelope, the chamfer, the
    # two bores and the slit band. The mm suffix is load-bearing -- this is an
    # INCH document and the equation manager reads BARE numbers in document units
    # (an unsuffixed 32 = 32 in, blowing the part up 25.4x in-plane). Bore/slit
    # stations are independent globals so a GUI edit nudges one feature without
    # touching its neighbours. The set-screw hole is a Hole Wizard feature, but it
    # is placed on a DRIVEN sketch point (ScrewHoleX/ScrewHoleY), so its location
    # is equation-driven like every other feature -- not an un-dimensioned pick.
    await set_global(adapter, "BlockLength", f"{BLOCK_LENGTH}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BlockDepth", f"{BLOCK_DEPTH}mm")
    await set_global(adapter, "Chamfer", f"{CHAMFER}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreX0", f"{BORE_X[0]}mm")
    await set_global(adapter, "BoreX1", f"{BORE_X[1]}mm")
    await set_global(adapter, "SlitLength", f"{SLIT_LENGTH}mm")
    await set_global(adapter, "SlitY0", f"{SLIT_Y[0]}mm")
    await set_global(adapter, "SlitY1", f"{SLIT_Y[1]}mm")
    # Set-screw hole station: the Hole Wizard hole is placed ON a driven sketch
    # point (below), so its X/Y ARE equation-driven dims -- a machinist reads the
    # locators off the drawing, and a GUI edit moves the tapped hole.
    await set_global(adapter, "ScrewHoleX", f"{SCREW_HOLE_XY[0]}mm")
    await set_global(adapter, "ScrewHoleY", f"{SCREW_HOLE_XY[1]}mm")

    # Each sketch records its dim names + drive equations in the helper's
    # emission order; the equations are collected here and applied in one
    # deferred batch at the end (every target must resolve against the finished
    # model).
    drive_jobs: list[tuple[str, str]] = []

    # Outline with 45-degree chamfered top corners (sloped lines need
    # direct-to-DB so inference cannot snap them).
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    outline_pts = [
        (0.0, 0.0),
        (BLOCK_LENGTH, 0.0),
        (BLOCK_LENGTH, BLOCK_HEIGHT - CHAMFER),
        (BLOCK_LENGTH - CHAMFER, BLOCK_HEIGHT),
        (CHAMFER, BLOCK_HEIGHT),
        (0.0, BLOCK_HEIGHT - CHAMFER),
    ]
    lines = await add_line_chain(adapter, outline_pts)
    set_sketch_direct_db(adapter, False)
    # Anchor vertex 0 is the origin (no anchor dims); the closing segment 5
    # (back to vertex 0) is skipped. Emission in line order: seg0 horizontal
    # (length), seg1 vertical (height - chamfer), seg2 chamfer dx + dy, seg3
    # horizontal (length - 2*chamfer), seg4 chamfer dx + dy = 7 dims.
    await define_polygon_chain(
        adapter, lines, outline_pts, label="block outline", dims=outline,
        names=["Length", "RiseY", "Chamfer2dx", "Chamfer2dy", "TopRun",
               "Chamfer4dx", "Chamfer4dy"],
        drives=['"BlockLength"', '"BlockHeight" - "Chamfer"',
                '"Chamfer"', '"Chamfer"',
                '"BlockLength" - 2 * "Chamfer"',
                '"Chamfer"', '"Chamfer"'],
    )
    await ensure_fully_defined(adapter, "block outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "OutlineProfile")
    drive_jobs += outline.apply(adapter, "OutlineProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_DEPTH)),
    )
    name_last_feature(adapter, "Block")
    vol = await _volume(adapter)
    _telemetry.info(f"volume after extrude: {vol:.1f} mm^3")

    # Two vertical bores along Y. Each centre is off both axes (x = bore
    # station, z = -BlockDepth/2), so define_circle emits centre-X, centre-Z,
    # diameter = 3 dims per circle.
    bores = SketchDims()
    check("create_sketch bores", await adapter.create_sketch("Top"))
    for i, bx in enumerate(BORE_X):
        await define_circle(
            adapter, bx, -BLOCK_DEPTH / 2.0, BORE_DIA / 2.0, f"bore {i + 1}",
            dims=bores,
            names=(f"Bore{i}X", f"Bore{i}Z", f"Bore{i}Dia"),
            drives=(f'"BoreX{i}"', '"BlockDepth" / 2', '"BoreDia"'),
        )
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
    name_last_feature(adapter, "Bores")
    vol = await _volume(adapter)
    _telemetry.info(f"volume after bores: {vol:.1f} mm^3")

    # Stopped clamp slit through Z from the x=0 end. Rectilinear chain anchored
    # at vertex 0 (0, SlitY0): the last segment of each direction is supplied by
    # closure, so the distance dims are seg0 horizontal (SlitLength) and seg1
    # vertical (SlitY1 - SlitY0); then the anchor vertical_distance (SlitY0,
    # x is on the axis so no anchor-X dim) = 3 dims.
    slit_dims = SketchDims()
    check("create_sketch slit", await adapter.create_sketch("Front"))
    slit_rect = [
        (0.0, SLIT_Y[0]),
        (SLIT_LENGTH, SLIT_Y[0]),
        (SLIT_LENGTH, SLIT_Y[1]),
        (0.0, SLIT_Y[1]),
    ]
    slit = await add_line_chain(adapter, slit_rect)
    await define_rectilinear_chain(
        adapter, slit, slit_rect, label="slit", dims=slit_dims,
        names=["SlitLength", "SlitWidth", "SlitY0"],
        drives=['"SlitLength"', '"SlitY1" - "SlitY0"', '"SlitY0"'],
    )
    await ensure_fully_defined(adapter, "slit sketch")
    check("exit_sketch slit", await adapter.exit_sketch())
    name_last_feature(adapter, "SlitProfile")
    drive_jobs += slit_dims.apply(adapter, "SlitProfile")
    check(
        "cut slit",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Slit")
    vol = await _volume(adapter)
    _telemetry.info(f"volume after slit: {vol:.1f} mm^3")

    # Front-face set-screw hole: a real Hole Wizard #5-40 UNC tapped THROUGH hole
    # at (ScrewHoleX, ScrewHoleY) on the front face (z=0, a solid spot clear of the
    # bores and the slit). Modeling it as a smart hole rather than a plain drill
    # means the MODEL carries the thread designation, so the drawing reads a native
    # "#5-40 UNC-2B THRU" callout with no hard-coded map; the tap-drill diameter
    # comes from the #5-40 table.
    hole = check(
        "tapped set-screw hole (#5-40 UNC)",
        await adapter.insert_tapped_hole(
            TappedHoleParameters(
                face_point=[SCREW_HOLE_XY[0], SCREW_HOLE_XY[1], 0.0],
                size=SCREW_HOLE_SIZE,
            )
        ),
    )
    _telemetry.info(f"set-screw hole feature: {hole}")

    # The Hole Wizard drops its location point UN-dimensioned (an under-defined
    # pick), so the hole has no X/Y locator on a drawing and its position is not
    # parametric. Open the wizard's own positioning sketch and anchor that point to
    # the origin: a horizontal + vertical distance dim (D1/D2), driven by the
    # ScrewHoleX/ScrewHoleY globals. This fully defines the hole and gives the
    # drawing real locator dimensions telling a machinist WHERE to drill/tap.
    locator = check(
        "open set-screw hole positioning sketch",
        await adapter.edit_hole_position(hole["name"], "ScrewHoleLocator"),
    )
    await anchor_point_to_origin(
        adapter, locator, SCREW_HOLE_XY[0], SCREW_HOLE_XY[1], "set-screw locator"
    )
    await ensure_fully_defined(adapter, "set-screw locator sketch")
    check("exit_sketch set-screw locator", await adapter.exit_sketch())
    # anchor_point_to_origin emits horizontal (D1) then vertical (D2) for a general
    # off-axis point; drive each by its global (the positioning sketch is absorbed
    # under the wizard, so it is addressed by these raw dim names, not SketchDims).
    drive_jobs += [
        ("D1@ScrewHoleLocator", '"ScrewHoleX"'),
        ("D2@ScrewHoleLocator", '"ScrewHoleY"'),
    ]
    v_final = await _volume(adapter)
    _telemetry.info(f"volume after set-screw hole: {v_final:.1f} mm^3")

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pen v-block (equations neutral)", v_final, 0.001 * v_final
    )

    await apply_material(adapter, MATERIAL)
    # The ch24 macro shows the cradle painted the machine green (manifest note
    # "pen v-block authored brass vs green"); keep the brass mass model.
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
