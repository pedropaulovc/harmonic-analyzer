r"""Reproduction script: cone tip bushing (item 5, v4_t00471 / 7:49).

Small brass bushing on the cone shaft's 1/16" tip journal, between the
smallest (6T) gear and the tip block: the axial spacer the adjuster
screw loads against, part of the end-play takeup stack (bushing ->
partially hollow adjuster screw -> pinch-locked block).

Plain sleeve: O6 x 4 long, 1/16" bore, extruded from the Top plane
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
import _config
import cone_gear_shaft_spec
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from cone_tip_bushing_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    LENGTH,
    OUTER_DIA,
    SURFACE_FINISHES,
)

PART_NAME = "cone-tip-bushing"
MATERIAL = "Brass"

OD = OUTER_DIA  # spec nominal; the assembly reads BORE_DIA/LENGTH from here too

# The bore over the shaft's tip journal is this part's ONE critical fit, and a
# running fit exists only if the size limits on BOTH mating features are
# narrower than the clearance band it claims (cad/docs/tolerance-policy.md
# step 6b). So the band is DERIVED -- never a per-part number -- from the
# named fit class (cone-tip-bushing.yaml: shaft_in_bushing) and the journal's
# own published limits: bore_min = journal_max + clearance_min, bore_max =
# journal_min + clearance_max. Move either input and this moves with it. It
# lives in the BUILD script, not in the shared spec: reading a fit class in
# cone_tip_bushing_spec would put tolerances.yaml in the import closure of
# the drawing, and only the part needs the limits.
_CLEARANCE_MIN, _CLEARANCE_MAX = (
    float(value)
    for value in _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
)
_JOURNAL_UPPER, _JOURNAL_LOWER = cone_gear_shaft_spec.SECTION_DIA_BANDS[-1]
BORE_DIA_BAND = (  # (upper, lower) deviations
    _JOURNAL_LOWER + _CLEARANCE_MAX,
    _JOURNAL_UPPER + _CLEARANCE_MIN,
)


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

    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "bore axis")
    await apply_material(adapter, MATERIAL)  # Brass appearance = the gears' gold
    await report_mass_properties(adapter)
    # Mark the three manufacturing dimensions and author the decimal places
    # they print with (policy rule 2: the model owns both the band and its
    # spelling -- the drawing only reads them back).
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES}
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
