r"""Reproduction script: top-lever fulcrum spacer bushing (book ch. 17; 19 used).

Small spacer between adjacent top levers on the common Ø6.35 fulcrum
shaft: Ø12 OD x 4.0565 long x Ø6.5 bore. Length sets the 7.0565 channel
pitch against the 3.0 lever thickness (7.0565 - 3.0 = 4.0565); 19 fill
the gaps between 20 levers - the lever-bank twin of the rocker bank's
pivot-bushing.

Dimensions: cad/DIMENSIONS.md "Chapter 17" lever rows (derived, med;
OD scaled, low).

Layout: bushing axis along Z, centred (annulus on the Front plane,
mid-plane extrude).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_lever_bushing.py
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
from lever_bushing_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    LENGTH,
    OUTER_DIA,
)

PART_NAME = "lever-bushing"
MATERIAL = "Brass"  # lever-bank twin of the brass pivot-bushing

async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): OD, bore, and length. The mm suffix is
    # load-bearing (INCH document; the equation manager reads bare numbers in
    # document units, so an unsuffixed value would blow the part up 25.4x).
    await set_global(adapter, "OuterDia", f"{OUTER_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "Length", f"{LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Concentric annulus on the Front plane, both circles on-axis (x=z=0): each
    # define_circle emits ONE dim (the diameter), so the centre name/drive slots
    # are ignored (recorded as None by the on-axis branch).
    annulus = SketchDims()
    check("create_sketch annulus", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, OUTER_DIA / 2.0, "outer", dims=annulus,
        names=(None, None, "OuterDia"), drives=(None, None, '"OuterDia"'),
    )
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIA / 2.0, "bore", dims=annulus,
        names=(None, None, "BoreDia"), drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "annulus sketch")
    check("exit_sketch annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "AnnulusProfile")
    drive_jobs += annulus.apply(adapter, "AnnulusProfile")
    check(
        "extrude bushing",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bushing")
    depth_dim = name_dimensions(adapter, "Bushing", ["Depth"])
    drive_jobs += [(depth_dim[0], '"Length"')]
    v = math.pi * ((OUTER_DIA / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2) * LENGTH
    await volume_check(adapter, "bushing annulus", v, 0.001 * v)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bushing (equations neutral)", v, 0.001 * v)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES}
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
