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

import math
import sys

from _common import (
    define_circle,
    CASTING_GREEN,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_rectilinear_chain,
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

# M6.10 fastener holes (machine = part-local: frame.SLDASM places the
# base unrotated at the origin). All through-drilled O8.2 (documented
# simplification -- the rail-bolt holes need only 12.5-deep sockets):
# 2x portal south foot-rail hex-bolts at (74.75, z -54/+36) and 2x
# portal north lag-screws at (72.9 +/- 31.75, z 101.6), the latter with
# O15 x 4.5 head counterbores up from the underside.
HOLE_DIA = 8.2
HOLE_XZ = (
    (74.75, -54.0),  # portal south foot-rail bolt
    (74.75, 36.0),  # portal south foot-rail bolt
    (41.15, 101.6),  # portal north lag screw (west)
    (104.65, 101.6),  # portal north lag screw (east)
)
CBORE_DIA = 15.0
CBORE_DEPTH = 4.5  # lag head 14 x 4 recessed 0.5
CBORE_XZ = HOLE_XZ[2:]

MM3_PER_IN3 = IN**3


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success and res.data else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Bottom plate, centered on the origin.
    check("create_sketch bottom", await adapter.create_sketch("Top"))
    bottom_rect = [
        (-BOTTOM_LENGTH / 2.0, -BOTTOM_WIDTH / 2.0),
        (BOTTOM_LENGTH / 2.0, -BOTTOM_WIDTH / 2.0),
        (BOTTOM_LENGTH / 2.0, BOTTOM_WIDTH / 2.0),
        (-BOTTOM_LENGTH / 2.0, BOTTOM_WIDTH / 2.0),
    ]
    lines = await add_line_chain(adapter, bottom_rect)
    await define_rectilinear_chain(adapter, lines, bottom_rect, label="bottom plate")
    await ensure_fully_defined(adapter, "bottom plate sketch")
    check("exit_sketch bottom", await adapter.exit_sketch())
    check(
        "extrude bottom",
        await adapter.create_extrusion(ExtrusionParameters(depth=BOTTOM_THICKNESS)),
    )
    print(f"  volume after bottom plate: {await _volume(adapter):.1f} mm^3")
    # expected: 18 * 11 * 0.5 in^3 = 99 in^3 = 1,622,319 mm^3

    # Top plate, centered, starting at the bottom plate's upper face.
    check("create_sketch top", await adapter.create_sketch("Top"))
    top_rect = [
        (-TOP_LENGTH / 2.0, -TOP_WIDTH / 2.0),
        (TOP_LENGTH / 2.0, -TOP_WIDTH / 2.0),
        (TOP_LENGTH / 2.0, TOP_WIDTH / 2.0),
        (-TOP_LENGTH / 2.0, TOP_WIDTH / 2.0),
    ]
    lines = await add_line_chain(adapter, top_rect)
    await define_rectilinear_chain(adapter, lines, top_rect, label="top plate")
    await ensure_fully_defined(adapter, "top plate sketch")
    check("exit_sketch top", await adapter.exit_sketch())
    extrude_at_offset(adapter, TOP_THICKNESS, BOTTOM_THICKNESS)
    print(f"  volume after top plate: {await _volume(adapter):.1f} mm^3")
    # expected: 99 + 17.5 * 10.5 * 1.5 = 374.625 in^3 = 6,139,003 mm^3

    # M6.10 fastener holes: Top sketch (x, y) -> global (X, -Z), mid-plane
    # cuts so the direction never matters (below y 0 is outside the part).
    total = BOTTOM_THICKNESS + TOP_THICKNESS
    pre_holes = await _volume(adapter)
    check("create_sketch fastener holes", await adapter.create_sketch("Top"))
    for x, z in HOLE_XZ:
        await define_circle(adapter, x, -z, HOLE_DIA / 2.0, f"hole ({x:.2f}, {z:.1f})")
    await ensure_fully_defined(adapter, "fastener holes sketch")
    check("exit_sketch fastener holes", await adapter.exit_sketch())
    check(
        "cut fastener holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=3.0 * total, both_directions=True)
        ),
    )
    before = await _volume(adapter)
    v_holes = len(HOLE_XZ) * math.pi * (HOLE_DIA / 2.0) ** 2 * total
    print(f"  volume after holes: {before:.1f} mm^3 (removed analytic {v_holes:.1f})")
    if abs((pre_holes - before) - v_holes) > 0.02 * v_holes:
        raise RuntimeError(
            f"holes removed {pre_holes - before:.1f}, expected {v_holes:.1f}"
        )

    # Lag-screw head counterbores up from the underside: a both-directions
    # cut of 2x depth about the bottom plane lands exactly 0..4.5 in
    # material (the lower half is air).
    check("create_sketch counterbores", await adapter.create_sketch("Top"))
    for x, z in CBORE_XZ:
        await define_circle(adapter, x, -z, CBORE_DIA / 2.0, f"cbore ({x:.2f})")
    await ensure_fully_defined(adapter, "counterbores sketch")
    check("exit_sketch counterbores", await adapter.exit_sketch())
    check(
        "cut counterbores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * CBORE_DEPTH, both_directions=True)
        ),
    )
    after = await _volume(adapter)
    v_cbore = (
        len(CBORE_XZ)
        * math.pi
        * ((CBORE_DIA / 2.0) ** 2 - (HOLE_DIA / 2.0) ** 2)
        * CBORE_DEPTH
    )
    print(f"  volume after counterbores: {after:.1f} mm^3 (removed analytic {v_cbore:.1f})")
    if abs((before - after) - v_cbore) > 0.02 * v_cbore:
        raise RuntimeError(
            f"counterbores removed {before - after:.1f}, expected {v_cbore:.1f}"
        )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)

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
