r"""Reproduction script: pivot shaft (book ch. 14 / ch. 17; 1 used).

Plain Ø6.35 (1/4") x 203.2 (8") steel shaft carrying the 20 rocker arms
at machine (x, y) = (-72.9, 253.8). Each end seats in a pivot-ball-mount's
Ø6.5 cross-bore (north mount seated on the rocker-support at z +81.5,
south mount on the A-frame clevis at z -111, M6.5); pivot-bushing spacers
set the 7.0565 channel pitch along it. The top levers' fulcrum is the
shorter build_fulcrum_shaft.py (182), which clears the west columns.

Dimensions: cad/DIMENSIONS.md "Channel & top-frame layout" (med; dia low).

Layout: shaft axis along Z. The PART is symmetric about its origin
(±101.6), but the assembly places it OFF-CENTRE (z -12.7) so the north end
lands at the rocker-support edge (z +88.9) while the south end (z -114.3)
still reaches the A-frame clevis mount (z -111).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pivot_shaft.py
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
from _part_pmi import author_part_pmi
from pivot_shaft_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    SHAFT_DIA,
    SHAFT_LENGTH,
)

PART_NAME = "pivot-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the shaft diameter and length. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 203.2 = 203.2 in).
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
    # GD&T lives on the MODEL as DimXpert PMI; the drawing imports it.
    author_part_pmi(adapter, datums=PART_DATUMS, controls=GEOMETRIC_CONTROLS)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
