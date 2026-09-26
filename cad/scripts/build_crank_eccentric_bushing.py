r"""Reproduction script: crank eccentric bushing, MHA-149 (#906 A2).

Bronze sleeve lining MHA-016's crank bore, with the crankshaft running in it.
Its bore is offset from its OD by the throw (``crank_eccentric_bushing_spec``),
so turning it in the post sets the 16T:64T centre distance at fit-up.

Plain sleeve: OD and bore extruded from the Top plane along +Y (the assembly
lays it along the crank axis).  Both axes lie in the Front plane, which is the
clocking reference the assembly turns the throw by.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_eccentric_bushing.py
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
import crankshaft_spec
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from cone_pivot_post_spec import CRANK_BORE_BAND as POST_BORE_BAND
from crank_eccentric_bushing_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ECCENTRICITY,
    ECCENTRICITY_BAND,
    LENGTH,
    OUTER_DIA,
    SURFACE_FINISHES,
    WALL_FLOOR_MM,
)

PART_NAME = "crank-eccentric-bushing"
MATERIAL = "Brass"  # nearest SolidWorks entry; the yaml names the bronze

# The bore is this part's running fit, so its band is DERIVED, as on
# cone-tip-bushing: from the named fit class (crank-eccentric-bushing.yaml:
# shaft_in_bushing) and the journal's own limits.  bore_min = journal_max +
# clearance_min, bore_max = journal_min + clearance_max.
_CLEARANCE_MIN, _CLEARANCE_MAX = (
    float(value)
    for value in _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
)
_JOURNAL_UPPER, _JOURNAL_LOWER = crankshaft_spec.JOURNAL_DIA_BAND
BORE_DIA_BAND = (  # (upper, lower) deviations from BORE_DIA
    crankshaft_spec.JOURNAL_DIA + _JOURNAL_LOWER + _CLEARANCE_MAX - BORE_DIA,
    crankshaft_spec.JOURNAL_DIA + _JOURNAL_UPPER + _CLEARANCE_MIN - BORE_DIA,
)

# The OD is a slip fit in the post's H7 bore on the same fit class (Main,
# 2026-09-26): the bushing turns in the bore at fit-up and is then bonded, so
# OD_max = post_bore_min - clearance_min and OD_min = post_bore_max -
# clearance_max.  Its lower limit is what the thin side of the wall is taken at.
_POST_UPPER, _POST_LOWER = POST_BORE_BAND
OD_BAND = (  # (upper, lower) deviations from OUTER_DIA
    _POST_LOWER - _CLEARANCE_MIN,
    _POST_UPPER - _CLEARANCE_MAX,
)

# Rule 12, the named exception (drawing-simplicity-policy.md): the thin side
# of the wall at print-worst -- OD at its minimum, the throw at its maximum,
# the bore at its maximum -- sits ON the floor.  The throw's band is what holds
# it there; loosen it and this fails.
WALL_WORST = (
    (OUTER_DIA + OD_BAND[1]) / 2.0
    - (ECCENTRICITY + ECCENTRICITY_BAND[0])
    - (BORE_DIA + BORE_DIA_BAND[0]) / 2.0
)
if WALL_WORST < WALL_FLOOR_MM - 1e-9:
    raise AssertionError(
        f"the bushing's thin wall is {WALL_WORST:.4f} at print-worst (OD "
        f"{OUTER_DIA + OD_BAND[1]:.3f} min, throw "
        f"{ECCENTRICITY + ECCENTRICITY_BAND[0]:.3f} max, bore "
        f"{BORE_DIA + BORE_DIA_BAND[0]:.3f} max), under the {WALL_FLOOR_MM} floor"
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "OD", f"{OUTER_DIA}mm")
    await set_global(adapter, "Length", f"{LENGTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "Eccentricity", f"{ECCENTRICITY}mm")
    drive_jobs: list[tuple[str, str]] = []

    body = SketchDims()
    check("create_sketch body", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, OUTER_DIA / 2.0, "body", dims=body,
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
    v = math.pi * (OUTER_DIA / 2.0) ** 2 * LENGTH
    volume = await volume_check(adapter, "body", v, 0.005 * v)

    # The throw is the bore centre's X offset in the Top sketch (model +X).
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, ECCENTRICITY, 0.0, BORE_DIA / 2.0, "bore", dims=bore,
        names=("BoreOffsetDim", "BoreCz", "BoreDiaDim"),
        drives=('"Eccentricity"', None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check("cut bore", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=LENGTH + 4.0, both_directions=True)))
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * (BORE_DIA / 2.0) ** 2 * LENGTH
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.005 * v_bore)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bushing (equations neutral)", volume,
                       0.005 * v_bore)
    set_dimension_bilateral_tolerance(
        adapter, "BodyProfile", "ODDim", *deviations(OD_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDiaDim", *deviations(BORE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreOffsetDim", *deviations(ECCENTRICITY_BAND)
    )

    # The OD axis seats in the post; the bore axis carries the crankshaft.  The
    # Front plane holds both, so it is the throw's clocking reference.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "od axis")
    name_last_feature(adapter, "OdAxis")
    await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", ECCENTRICITY, "bore axis",
        drive_b='"Eccentricity"', drive_jobs=drive_jobs,
    )
    name_last_feature(adapter, "BoreAxis")
    for dim_name, expr in drive_jobs[-1:]:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
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
