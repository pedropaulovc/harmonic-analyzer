r"""Reproduction script: cylinder gear arbor (book ch. 13, pp. 22-25).

Plain Ø3/8 in steel STATIONARY arbor carrying the 20 identical cylinder
gears with their integral eccentric cams (~134 mm stack at 7.06 mm
Z-pitch, alternating with the black connecting rods that ride the cams).
No keyseat: gear k turns k/80 rev per crank turn (ch. 29 gear law), so
the 20 gears all spin at DIFFERENT speeds and cannot be keyed to a
common shaft -- they run free on this fixed arbor (DIMENSIONS.md ch. 13,
"M6.2 keyway refutation"; the legacy keyseat was fiction, removed in
M6.2). The arbor is clamped in the pedestal supports at both ends.

Dimensions: cad/DIMENSIONS.md "Chapter 13" - dia legacy (med), length
derived from the stack + eight-views 8/8 pedestals (low).

Layout: arbor axis along +Y from the origin, plain cylinder y 0..200.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cylinder_gear_shaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
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
from _part_pmi import author_part_pmi
from cylinder_gear_shaft_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    GEOMETRIC_CONTROLS,
    ISO_VIEW_NOTE,
    PART_DATUMS,
    SHAFT_DIA,
    SHAFT_LENGTH,
)

PART_NAME = "cylinder-gear-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

SHAFT_RADIUS = SHAFT_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the arbor diameter and length. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 176 would be 176 in).
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLength", f"{SHAFT_LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # On-axis circle (centre at the origin): define_circle records ONLY the
    # diameter dim (the X/Z centre slots are relations, not display dims).
    shaft = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, SHAFT_RADIUS, "shaft circle", dims=shaft,
        names=("ShaftCx", "ShaftCz", "ShaftDia"),
        drives=(None, None, '"ShaftDia"'),
    )
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs += shaft.apply(adapter, "ShaftProfile")
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LENGTH)),
    )
    name_last_feature(adapter, "Shaft")
    depth_dim = name_dimensions(adapter, "Shaft", ["Depth"])
    drive_jobs += [(depth_dim[0], '"ShaftLength"')]
    v_shaft = math.pi * SHAFT_RADIUS**2 * SHAFT_LENGTH
    # expected: pi * 4.7625^2 * 176 = ~12,541 mm^3
    await volume_check(adapter, "shaft", v_shaft, 0.005 * v_shaft)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven shaft (equations neutral)", v_shaft, 0.005 * v_shaft)

    # Named central axis (arbor axis along +Y through the origin) so the
    # cylinder gears ride it coincident axis-to-axis in the assembly.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # GD&T lives on the MODEL as DimXpert PMI; the drawing imports it.
    author_part_pmi(adapter, datums=PART_DATUMS, controls=GEOMETRIC_CONTROLS)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
            "Iso View Note": ISO_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
