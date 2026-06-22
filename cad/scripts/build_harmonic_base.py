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

    uv run python cad\scripts\build_harmonic_base.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    measure_check,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

import _telemetry

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


def _pos_drive(global_name: str, sketch_value: float) -> str:
    """Drive expression for an UNSIGNED centre-distance dim whose global holds the
    signed sketch coordinate. The dim displays the magnitude, so the equation must
    evaluate POSITIVE -- negate the global when the coordinate is negative (driving
    such a dim to a negative value fails loud at equation-add)."""
    return f'-"{global_name}"' if sketch_value < 0.0 else f'"{global_name}"'


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success and res.data else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the two plate footprints + thicknesses,
    # the hole/counterbore diameters, and each fastener-hole station. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 457.2 = 457 inches and
    # blows the part up 25.4x). The thicknesses / cbore depth are extrude/offset
    # feature parameters (not sketch dims), exposed here as editable constants even
    # though nothing in drive_jobs drives them.
    await set_global(adapter, "BottomLength", f"{BOTTOM_LENGTH}mm")
    await set_global(adapter, "BottomWidth", f"{BOTTOM_WIDTH}mm")
    await set_global(adapter, "BottomThickness", f"{BOTTOM_THICKNESS}mm")
    await set_global(adapter, "TopLength", f"{TOP_LENGTH}mm")
    await set_global(adapter, "TopWidth", f"{TOP_WIDTH}mm")
    await set_global(adapter, "TopThickness", f"{TOP_THICKNESS}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")
    await set_global(adapter, "CboreDia", f"{CBORE_DIA}mm")
    await set_global(adapter, "CboreDepth", f"{CBORE_DEPTH}mm")
    # One global per fastener-hole station, holding the SKETCH-space coordinate
    # (define_circle receives (x, -z), so the z global is the negated machine z).
    # The centre dims are unsigned distances -- _pos_drive negates a negative
    # global so the equation evaluates positive.
    for i, (x, z) in enumerate(HOLE_XZ):
        await set_global(adapter, f"Hole{i}X", f"{x}mm")
        await set_global(adapter, f"Hole{i}Z", f"{-z}mm")

    # Each sketch DECLARES its dim names + drive equations inline; a per-sketch
    # SketchDims records each dim in the helper's emission order. Drive equations
    # are collected here and applied in one deferred batch at the end (every
    # target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # Bottom plate, centered on the origin.
    bottom = SketchDims()
    check("create_sketch bottom", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, BOTTOM_LENGTH / 2.0, BOTTOM_WIDTH / 2.0, "bottom plate", dims=bottom,
        name_width="BottomLen", drive_width='"BottomLength"',
        name_depth="BottomWid", drive_depth='"BottomWidth"',
        name_corner=("BottomCornerX", "BottomCornerZ"),
        drive_corner=('"BottomLength" / 2', '"BottomWidth" / 2'),
    )
    await ensure_fully_defined(adapter, "bottom plate sketch")
    check("exit_sketch bottom", await adapter.exit_sketch())
    name_last_feature(adapter, "BottomProfile")
    drive_jobs += bottom.apply(adapter, "BottomProfile")
    check(
        "extrude bottom",
        await adapter.create_extrusion(ExtrusionParameters(depth=BOTTOM_THICKNESS)),
    )
    name_last_feature(adapter, "BottomPlate")
    _telemetry.info(f"volume after bottom plate: {await _volume(adapter):.1f} mm^3")
    # expected: 18 * 11 * 0.5 in^3 = 99 in^3 = 1,622,319 mm^3

    # Top plate, centered, starting at the bottom plate's upper face.
    top = SketchDims()
    check("create_sketch top", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, TOP_LENGTH / 2.0, TOP_WIDTH / 2.0, "top plate", dims=top,
        name_width="TopLen", drive_width='"TopLength"',
        name_depth="TopWid", drive_depth='"TopWidth"',
        name_corner=("TopCornerX", "TopCornerZ"),
        drive_corner=('"TopLength" / 2', '"TopWidth" / 2'),
    )
    await ensure_fully_defined(adapter, "top plate sketch")
    check("exit_sketch top", await adapter.exit_sketch())
    name_last_feature(adapter, "TopProfile")
    drive_jobs += top.apply(adapter, "TopProfile")
    extrude_at_offset(adapter, TOP_THICKNESS, BOTTOM_THICKNESS)
    name_last_feature(adapter, "TopPlate")
    _telemetry.info(f"volume after top plate: {await _volume(adapter):.1f} mm^3")
    # expected: 99 + 17.5 * 10.5 * 1.5 = 374.625 in^3 = 6,139,003 mm^3

    # M6.10 fastener holes: Top sketch (x, y) -> global (X, -Z), mid-plane
    # cuts so the direction never matters (below y 0 is outside the part).
    total = BOTTOM_THICKNESS + TOP_THICKNESS
    pre_holes = await _volume(adapter)
    holes = SketchDims()
    check("create_sketch fastener holes", await adapter.create_sketch("Top"))
    for i, (x, z) in enumerate(HOLE_XZ):
        await define_circle(
            adapter, x, -z, HOLE_DIA / 2.0, f"hole ({x:.2f}, {z:.1f})", dims=holes,
            names=(f"Hole{i}Cx", f"Hole{i}Cz", f"Hole{i}Dia"),
            drives=(
                _pos_drive(f"Hole{i}X", x),
                _pos_drive(f"Hole{i}Z", -z),
                '"HoleDia"',
            ),
        )
    await ensure_fully_defined(adapter, "fastener holes sketch")
    check("exit_sketch fastener holes", await adapter.exit_sketch())
    name_last_feature(adapter, "FastenerHoleProfile")
    drive_jobs += holes.apply(adapter, "FastenerHoleProfile")
    check(
        "cut fastener holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=3.0 * total, both_directions=True)
        ),
    )
    name_last_feature(adapter, "FastenerHoles")
    before = await _volume(adapter)
    v_holes = len(HOLE_XZ) * math.pi * (HOLE_DIA / 2.0) ** 2 * total
    _telemetry.info(f"volume after holes: {before:.1f} mm^3 (removed analytic {v_holes:.1f})")
    if abs((pre_holes - before) - v_holes) > 0.02 * v_holes:
        raise RuntimeError(
            f"holes removed {pre_holes - before:.1f}, expected {v_holes:.1f}"
        )

    # Lag-screw head counterbores up from the underside: a both-directions
    # cut of 2x depth about the bottom plane lands exactly 0..4.5 in
    # material (the lower half is air).
    cbores = SketchDims()
    check("create_sketch counterbores", await adapter.create_sketch("Top"))
    # CBORE_XZ is HOLE_XZ[2:], so each counterbore is concentric with a fastener
    # hole -- reuse the same Hole{2,3}{X,Z} station globals so a station edit moves
    # both. The index offset (2) keeps the global names aligned with the holes.
    cbore_offset = len(HOLE_XZ) - len(CBORE_XZ)
    for j, (x, z) in enumerate(CBORE_XZ):
        i = cbore_offset + j
        await define_circle(
            adapter, x, -z, CBORE_DIA / 2.0, f"cbore ({x:.2f})", dims=cbores,
            names=(f"Cbore{i}Cx", f"Cbore{i}Cz", f"Cbore{i}Dia"),
            drives=(
                _pos_drive(f"Hole{i}X", x),
                _pos_drive(f"Hole{i}Z", -z),
                '"CboreDia"',
            ),
        )
    await ensure_fully_defined(adapter, "counterbores sketch")
    check("exit_sketch counterbores", await adapter.exit_sketch())
    name_last_feature(adapter, "CounterboreProfile")
    drive_jobs += cbores.apply(adapter, "CounterboreProfile")
    check(
        "cut counterbores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * CBORE_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Counterbores")
    after = await _volume(adapter)
    v_cbore = (
        len(CBORE_XZ)
        * math.pi
        * ((CBORE_DIA / 2.0) ** 2 - (HOLE_DIA / 2.0) ** 2)
        * CBORE_DEPTH
    )
    _telemetry.info(f"volume after counterbores: {after:.1f} mm^3 (removed analytic {v_cbore:.1f})")
    if abs((before - after) - v_cbore) > 0.02 * v_cbore:
        raise RuntimeError(
            f"counterbores removed {before - after:.1f}, expected {v_cbore:.1f}"
        )

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves -- then re-check neutrality against the
    # as-built volume (each equation evaluates to the value just built, so the
    # geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven base (equations neutral)", after, 0.005 * after
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
