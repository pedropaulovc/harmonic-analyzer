r"""Reproduction script: pen square rod (book ch. 24, pp. 64-65).

The square brass rod that carries the v-block; the wire from the
magnifying wheel ties into the cross hole near its top, so the rod (and
pen) mirror the summed motion vertically.

Dimensions: cad/DIMENSIONS.md "Chapter 24" — ~5 mm square photo-scaled
(low); length ~120 from the p.64 inset (low).

Layout: length along +Y from the origin (assembly orientation), section
centred on the origin in X, extruded +Z; wire hole along Z near the top.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_rod.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "pen-rod"
MATERIAL = "Brass"  # see _common.apply_material docstring

ROD_SECTION = 5.0  # DIMENSIONS.md ch24: square section (low)
ROD_LENGTH = 120.0  # DIMENSIONS.md ch24: p.64 inset (low)
WIRE_HOLE_DIA = 2.0  # wire tie-off near the top
WIRE_HOLE_Y = 115.0
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > section


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the square section, the rod length and
    # the wire-hole geometry. The mm suffix is load-bearing -- this is an INCH
    # document and the equation manager reads BARE numbers in document units (an
    # unsuffixed 120 = 120 in, blowing the part up 25.4x).
    await set_global(adapter, "RodSection", f"{ROD_SECTION}mm")
    await set_global(adapter, "RodLength", f"{ROD_LENGTH}mm")
    await set_global(adapter, "WireHoleDia", f"{WIRE_HOLE_DIA}mm")
    await set_global(adapter, "WireHoleY", f"{WIRE_HOLE_Y}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Square section, anchored at the origin corner and spanning 0..ROD_LENGTH in
    # Y (not origin-centred, so keep the rectilinear chain). Emission order: the
    # kept per-segment distance dims (one horizontal width, one vertical length;
    # the closing horizontal/vertical are redundant), THEN the anchor dims at the
    # bottom-left corner (-RodSection/2, 0): only X is non-zero, so one anchor dim.
    section = SketchDims()
    check("create_sketch section", await adapter.create_sketch("Front"))
    section_rect = [
        (-ROD_SECTION / 2.0, 0.0),
        (ROD_SECTION / 2.0, 0.0),
        (ROD_SECTION / 2.0, ROD_LENGTH),
        (-ROD_SECTION / 2.0, ROD_LENGTH),
    ]
    lines = await add_line_chain(adapter, section_rect)
    await define_rectilinear_chain(
        adapter, lines, section_rect, label="rod", dims=section,
        names=["Section", "Length", "CornerX"],
        drives=['"RodSection"', '"RodLength"', '"RodSection" / 2'],
    )
    await ensure_fully_defined(adapter, "rod outline")
    check("exit_sketch section", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += section.apply(adapter, "RodProfile")
    check(
        "extrude rod",
        await adapter.create_extrusion(ExtrusionParameters(depth=ROD_SECTION)),
    )
    name_last_feature(adapter, "Rod")
    v_rod = ROD_SECTION * ROD_SECTION * ROD_LENGTH
    await volume_check(adapter, "rod", v_rod, 0.005 * v_rod)

    # Wire hole near the top (on-axis in X at y = WIRE_HOLE_Y): only the centre Z
    # and the diameter are dims (the X is a relation), so define_circle records
    # just those two -- the "X" slot is ignored.
    wire = SketchDims()
    check("create_sketch wire hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, WIRE_HOLE_Y, WIRE_HOLE_DIA / 2.0, "wire hole",
        dims=wire,
        names=("WireX", "WireZ", "WireDia"),
        drives=(None, '"WireHoleY"', '"WireHoleDia"'),
    )
    await ensure_fully_defined(adapter, "wire hole sketch")
    check("exit_sketch wire hole", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += wire.apply(adapter, "WireProfile")
    check(
        "cut wire hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "WireHole")
    v_wire = math.pi * (WIRE_HOLE_DIA / 2.0) ** 2 * ROD_SECTION
    v_final = v_rod - v_wire
    await volume_check(adapter, "wire hole", v_final, 0.005 * v_rod)

    # Apply the deferred drive equations after the whole model + a rebuild exists,
    # then re-check: every equation evaluates to the value just built, so the
    # geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pen rod (equations neutral)", v_final, 0.005 * v_rod)

    # Named slide axis (local Y through the origin = Front Plane ∩ Right Plane,
    # the square rod's long axis) so the pen rod runs as a prismatic joint along
    # the v-block guide in the M6 mated-DOF assembly (vertical pen travel).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "slide axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
