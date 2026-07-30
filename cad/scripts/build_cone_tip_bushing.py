r"""Reproduction script: cone tip bushing (item 5, v4_t00471 / 7:49).

Small brass bushing on the cone shaft's 1/32" tip stub, between the
smallest (6T) gear and the tip block: the axial spacer the adjuster
screw loads against, part of the end-play takeup stack (bushing ->
partially hollow adjuster screw -> pinch-locked block).

Plain sleeve: O6 x 4 long, 1/32" bore, extruded from the Top plane
(the assembly lays it along the shaft like the gears).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_tip_bushing.py
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
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from cone_tip_bushing_spec import (
    BORE_DIA,
    BORE_DIA_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    LENGTH,
    LENGTH_TOLERANCE_MM,
    OUTER_DIA,
    SURFACE_FINISHES,
)

PART_NAME = "cone-tip-bushing"
MATERIAL = "Brass"

OD = OUTER_DIA  # spec nominal; the assembly reads BORE_DIA/LENGTH from here too


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "OD", f"{OD}mm")
    await set_global(adapter, "Length", f"{LENGTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    drive_jobs: list[tuple[str, str]] = []

    body = SketchDims()
    check("create_sketch body", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, OD / 2.0, "body", dims=body,
        names=("BodyCx", "BodyCz", "ODDim"), drives=(None, None, '"OD"'),
    )
    await ensure_fully_defined(adapter, "body sketch")
    check("exit_sketch body", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    drive_jobs += body.apply(adapter, "BodyProfile")
    check("extrude body", await adapter.create_extrusion(
        ExtrusionParameters(depth=LENGTH)))
    name_last_feature(adapter, "Body")
    depth_dim = name_dimensions(adapter, "Body", ["Depth"])
    drive_jobs += [(depth_dim[0], '"Length"')]
    v = math.pi * (OD / 2.0) ** 2 * LENGTH
    volume = await volume_check(adapter, "body", v, 0.005 * v)

    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIA / 2.0, "bore", dims=bore,
        names=("BoreCx", "BoreCz", "BoreDiaDim"), drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check("cut bore", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=LENGTH + 4.0, both_directions=True)))
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * (BORE_DIA / 2.0) ** 2 * LENGTH
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.05 * v_bore)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bushing (equations neutral)", volume,
                       0.05 * v_bore)
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDiaDim", *deviations(BORE_DIA_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "Body", "Depth", LENGTH_TOLERANCE_MM
    )

    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "bore axis")
    await apply_material(adapter, MATERIAL)  # Brass appearance = the gears' gold
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES}
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
