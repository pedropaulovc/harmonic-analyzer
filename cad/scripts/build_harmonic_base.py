r"""Reproduction script: harmonic analyzer base (book ch. 6 / legacy part).

Two-plate welded construction: bottom plate 18.0 x 11.0 x 0.5 in with a
17.5 x 10.5 x 1.5 in top plate centered on it. Re-authors the legacy
HarmonicBase.cs; the book's p.3 photo callouts (46 x 28 cm = 18.1 x 11.0 in)
confirm the legacy footprint, so the legacy inch dims are kept.

Deferred: the legacy 0.125"/0.0625" edge fillets are cosmetic and need
edge-selection tooling — re-added with the M4 finishing pass.

Dimensions: cad/DIMENSIONS.md "Chapter 6" — annotated (high) footprint,
legacy thicknesses (photo-verify note).

Layout: plates centered on the origin, Top-plane sketches (sketch x,y ->
global X,-Z), stacked along +Y. Top plate boss starts at the bottom plate's
upper face via extrude_at_offset (raw-COM stopgap until MCP Phase 3).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_harmonic_base.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    ensure_fully_defined,
    extrude_at_offset,
    measure_check,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "harmonic-base"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

IN = 25.4
BOTTOM_LENGTH = 18.0 * IN  # DIMENSIONS.md ch6: 46 cm callout = 18.1" (annotated)
BOTTOM_WIDTH = 11.0 * IN  # DIMENSIONS.md ch6: 28 cm callout = 11.0" (annotated)
BOTTOM_THICKNESS = 0.5 * IN  # legacy HarmonicBase.cs (photo-verify M2 note)
TOP_LENGTH = 17.5 * IN  # legacy: 0.25" reveal per side
TOP_WIDTH = 10.5 * IN
TOP_THICKNESS = 1.5 * IN

MM3_PER_IN3 = IN**3


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success and res.data else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Bottom plate, centered on the origin.
    check("create_sketch bottom", await adapter.create_sketch("Top"))
    lines = await add_line_chain(
        adapter,
        [
            (-BOTTOM_LENGTH / 2.0, -BOTTOM_WIDTH / 2.0),
            (BOTTOM_LENGTH / 2.0, -BOTTOM_WIDTH / 2.0),
            (BOTTOM_LENGTH / 2.0, BOTTOM_WIDTH / 2.0),
            (-BOTTOM_LENGTH / 2.0, BOTTOM_WIDTH / 2.0),
        ],
    )
    await ensure_fully_defined(adapter, "bottom plate sketch", fix_entities=lines)
    check("exit_sketch bottom", await adapter.exit_sketch())
    check(
        "extrude bottom",
        await adapter.create_extrusion(ExtrusionParameters(depth=BOTTOM_THICKNESS)),
    )
    print(f"  volume after bottom plate: {await _volume(adapter):.1f} mm^3")
    # expected: 18 * 11 * 0.5 in^3 = 99 in^3 = 1,622,319 mm^3

    # Top plate, centered, starting at the bottom plate's upper face.
    check("create_sketch top", await adapter.create_sketch("Top"))
    lines = await add_line_chain(
        adapter,
        [
            (-TOP_LENGTH / 2.0, -TOP_WIDTH / 2.0),
            (TOP_LENGTH / 2.0, -TOP_WIDTH / 2.0),
            (TOP_LENGTH / 2.0, TOP_WIDTH / 2.0),
            (-TOP_LENGTH / 2.0, TOP_WIDTH / 2.0),
        ],
    )
    await ensure_fully_defined(adapter, "top plate sketch", fix_entities=lines)
    check("exit_sketch top", await adapter.exit_sketch())
    extrude_at_offset(adapter, TOP_THICKNESS, BOTTOM_THICKNESS)
    print(f"  volume after top plate: {await _volume(adapter):.1f} mm^3")
    # expected: 99 + 17.5 * 10.5 * 1.5 = 374.625 in^3 = 6,139,003 mm^3

    await apply_material(adapter, MATERIAL)

    # Verify the annotated footprint (ch. 6: 46 x 28 cm callouts = 18.1 x
    # 11.0 in; legacy 18.0 x 11.0 kept). Side-face pairs fail to pick (the
    # far faces are hidden in the active view and point picking is
    # screen-projected) — measure the bottom plate's perimeter edges.
    await measure_check(
        adapter,
        "base length (annotated 46 cm / 18 in)",
        [{"entity_type": "EDGE", "point": [0.0, 0.0, BOTTOM_WIDTH / 2.0]}],
        "length",
        BOTTOM_LENGTH,
    )
    await measure_check(
        adapter,
        "base depth (annotated 28 cm / 11 in)",
        [{"entity_type": "EDGE", "point": [BOTTOM_LENGTH / 2.0, 0.0, 0.0]}],
        "length",
        BOTTOM_WIDTH,
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
