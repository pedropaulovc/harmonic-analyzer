r"""Reproduction script: lever fulcrum shaft (book ch. 17; 1 used).

Plain Ø6.35 (1/4") x 182 steel shaft: the top levers' common fulcrum at
machine (x, y) = (-199.9, 1065.9). M6.5 split this off the 228.6
pivot-shaft: the fulcrum line sits on the west column line, and a 228.6
shaft's tips (z +-114.3) still clip the Ø25.4 columns (tip 3.7 from the
column axis vs the 12.7 surface; OD rederived from the 8-views, M6.11).
182 ends the shaft at z +-91, ~5.3 clear of the column surface (was 0.6
at the old Ø34.925), still 6 past each lever ball-mount's cross-bore
centre at z +-85.

Dimensions: cad/DIMENSIONS.md "Channel & top-frame layout" (med; dia low).

Layout: shaft axis along Z, centred (z -91..+91).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fulcrum_shaft.py
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
from fulcrum_shaft_spec import DRAWING_DIMENSIONS, SHAFT_DIA, SHAFT_LENGTH

PART_NAME = "fulcrum-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the shaft diameter and length. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 182 = 182 in).
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLength", f"{SHAFT_LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Shaft section: an on-axis (origin) circle, so define_circle emits only the
    # diameter dim -- the centre X/Z slots are relations, recorded but ignored.
    section = SketchDims()
    check("create_sketch section", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, SHAFT_DIA / 2.0, "shaft section", dims=section,
        names=("SectionCx", "SectionCz", "ShaftDia"),
        drives=(None, None, '"ShaftDia"'),
    )
    await ensure_fully_defined(adapter, "section sketch")
    check("exit_sketch section", await adapter.exit_sketch())
    name_last_feature(adapter, "SectionProfile")
    drive_jobs += section.apply(adapter, "SectionProfile")
    check(
        "extrude shaft",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SHAFT_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Shaft")
    depth_dim = name_dimensions(adapter, "Shaft", ["Depth"])
    drive_jobs += [(depth_dim[0], '"ShaftLength"')]
    v = math.pi * (SHAFT_DIA / 2.0) ** 2 * SHAFT_LENGTH
    await volume_check(adapter, "shaft", v, 0.001 * v)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven shaft (equations neutral)", v, 0.001 * v)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
