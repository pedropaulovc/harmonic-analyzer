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
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import NUMBER_DRILL_MM, HoleSpec, wizard_holes
from pen_rod_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ROD_LENGTH,
    ROD_SECTION,
    TOP_VIEW_NOTE,
    WIRE_HOLE_Y,
)

PART_NAME = "pen-rod"
MATERIAL = "Brass"  # see _common.apply_material docstring


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the square section, the rod length and
    # the wire-hole geometry. The mm suffix is load-bearing -- this is an INCH
    # document and the equation manager reads BARE numbers in document units (an
    # unsuffixed 120 = 120 in, blowing the part up 25.4x).
    await set_global(adapter, "RodSection", f"{ROD_SECTION}mm")
    await set_global(adapter, "RodLength", f"{ROD_LENGTH}mm")
    await set_global(adapter, "WireHoleY", f"{WIRE_HOLE_Y}mm")
    # (The old WireHoleDia/WireHoleY knobs are gone: the wire hole is now a native
    # Hole Wizard feature whose diameter comes from the #47 drill standard, not an
    # equation-driven sketch dim.)

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
    depth_dim = name_dimensions(adapter, "Rod", ["Depth"])
    drive_jobs += [(depth_dim[0], '"RodSection"')]
    v_rod = ROD_SECTION * ROD_SECTION * ROD_LENGTH
    await volume_check(adapter, "rod", v_rod, 0.005 * v_rod)

    # Wire tie-off hole near the top: was a plain Ø2.0 cut, now a native Hole
    # Wizard #47 number drill (Ø1.994) so the model carries the real drill
    # (memory/fastener-policy-us-customary). Drilled +Z through the 5 mm square
    # section (Z 0..ROD_SECTION) at (0, WIRE_HOLE_Y); through-all is geometrically
    # identical to the old mid-plane both-directions cut.
    wire_cut = wizard_holes(
        adapter,
        HoleSpec("drilled_number", "#47"),
        [[0.0, WIRE_HOLE_Y, ROD_SECTION]],
        (0.0, 0.0, 1.0),
        "wire tie-off hole (#47)",
        name="WireHole",
        placement_dims=[((None, None), ("WireZ", '"WireHoleY"'))],
    )
    drive_jobs += wire_cut.placement_drive_jobs
    wire_dia = NUMBER_DRILL_MM["#47"]
    v_wire = math.pi * (wire_dia / 2.0) ** 2 * ROD_SECTION
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
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Top View Note": TOP_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
