r"""Reproduction script: pen frame / stirrup (book ch. 24, pp. 64-65).

The rectangular brass yoke that wraps the v-block and marker; the set
screw threads up through its bottom rail to set the pen angle. Nested
sketch contours (outer + inner rectangle) extrude directly into the ring.

Dimensions: cad/DIMENSIONS.md "Chapter 24" — scaled from the p.64-65
photos vs the ~5 mm square rod (low). Side rails 4, end rails 5 (the
window must span the marker + pen rod when the frame lies flat on the
v-block, long axis along machine X -- see build_output_assembly.py).

Layout: width along +X, height along +Y from the origin corner, depth
extruded +Z; set-screw hole cut along Y from a Top-plane sketch with a
mid-plane depth short enough to spare the top rail.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pen_frame.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "pen-frame"
MATERIAL = "Brass"  # see _common.apply_material docstring

OUTER_WIDTH = 22.0  # X  DIMENSIONS.md ch24: p.64/65 vs 5 mm rod (low)
OUTER_HEIGHT = 40.0  # Y
RAIL_SIDE = 4.0  # long-side rails (local X): read thinner in the photo; the
# extra 1 mm of window also clears the marker barrel at the platen side in
# the M6.4 flat-on-the-v-block layout
RAIL_END = 5.0  # end rails (local Y); the screw rail keeps thread depth
TRIM_NEAR = 0.75  # local x = 0 edge pulled back: that rail faces the platen
# (machine z = -143 - local x) and must clear the recording paper's front
# face at -143.4 by the 0.25+ margin (M6.8 platen-paper)
FRAME_DEPTH = 10.0  # Z
SCREW_HOLE_DIA = 3.0  # set screw, bottom rail only

# Mid-plane cut from the Top plane spans +-depth/2 in Y: deep enough for
# the bottom rail, short of the top rail.
SCREW_CUT_DEPTH = 30.0


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Outer + inner rectangles in one sketch -> ring on extrude.
    check("create_sketch ring", await adapter.create_sketch("Front"))
    outer = await add_line_chain(
        adapter,
        [
            (TRIM_NEAR, 0.0),
            (OUTER_WIDTH, 0.0),
            (OUTER_WIDTH, OUTER_HEIGHT),
            (TRIM_NEAR, OUTER_HEIGHT),
        ],
    )
    inner = await add_line_chain(
        adapter,
        [
            (RAIL_SIDE, RAIL_END),
            (OUTER_WIDTH - RAIL_SIDE, RAIL_END),
            (OUTER_WIDTH - RAIL_SIDE, OUTER_HEIGHT - RAIL_END),
            (RAIL_SIDE, OUTER_HEIGHT - RAIL_END),
        ],
    )
    await ensure_fully_defined(adapter, "ring sketch", fix_entities=[*outer, *inner])
    check("exit_sketch ring", await adapter.exit_sketch())
    check(
        "extrude ring",
        await adapter.create_extrusion(ExtrusionParameters(depth=FRAME_DEPTH)),
    )
    vol = await _volume(adapter)
    print(f"  volume after extrude: {vol:.1f} mm^3")

    # Set-screw hole up through the bottom rail.
    check("create_sketch screw hole", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, OUTER_WIDTH / 2.0, -FRAME_DEPTH / 2.0, SCREW_HOLE_DIA / 2.0, "screw hole"
    )
    await ensure_fully_defined(adapter, "screw hole sketch")
    check("exit_sketch screw hole", await adapter.exit_sketch())
    check(
        "cut screw hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SCREW_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after screw hole: {vol:.1f} mm^3")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
