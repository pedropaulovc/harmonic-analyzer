r"""Reproduction script: platen plate (book ch. 22, pp. 54-55).

The heavy darkened-brass plate that carries the recording paper. The
toothed rack bar screwed to its back bottom edge and the two paper-clip
strips are separate parts (build_platen_rack.py / build_platen_clip.py);
fastener holes are deferred to assembly (M6) when the mating hardware
positions are fixed.

Dimensions: cad/DIMENSIONS.md "Chapter 22" — 140 mm height annotated
(p.55 callout, high); width ~300 from the front-photo aspect (~2.15:1)
and the p.54 inset vs the 460 mm frame (low; supersedes an earlier ~200
estimate); thickness ~4 from the p.55 top edge-on photo (low).

Layout: width along +X, height along +Y from the origin corner, thickness
extruded +Z.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_platen.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    apply_material,
    apply_color,
    PANEL_BLACK,
    check,
    ensure_fully_defined,
    measure_check,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "platen"
MATERIAL = "Brass"  # see _common.apply_material docstring

PLATE_WIDTH = 300.0  # DIMENSIONS.md ch22: photo aspect vs 140 mm (low)
PLATE_HEIGHT = 140.0  # DIMENSIONS.md ch22: p.55 callout (high)
PLATE_THICKNESS = 4.0  # DIMENSIONS.md ch22: p.55 edge-on photo (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch outline", await adapter.create_sketch("Front"))
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (PLATE_WIDTH, 0.0),
            (PLATE_WIDTH, PLATE_HEIGHT),
            (0.0, PLATE_HEIGHT),
        ],
    )
    await ensure_fully_defined(adapter, "plate outline", fix_entities=lines)
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_THICKNESS)),
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)  # ch30 plates: see _common palette

    # Verify the annotated 140 mm front-face height (p.55 callout).
    mid_x, mid_z = PLATE_WIDTH / 2.0, PLATE_THICKNESS / 2.0
    await measure_check(
        adapter,
        "plate height (annotated 140)",
        [
            {"entity_type": "FACE", "point": [mid_x, 0.0, mid_z]},
            {"entity_type": "FACE", "point": [mid_x, PLATE_HEIGHT, mid_z]},
        ],
        "normal_distance",
        PLATE_HEIGHT,
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
