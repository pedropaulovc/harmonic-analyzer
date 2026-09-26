r"""Reproduction script: crank eccentric bushing, MHA-149 (#906 R1).

Bronze sleeve lining MHA-016's crank bore, with the crankshaft running in it.
Its bore is offset from its OD by the throw (``crank_eccentric_bushing_spec``),
so turning it in the post sets the 16T:64T centre distance at fit-up.

Plain sleeve: OD and bore extruded from the Top plane along +Y (the assembly
lays it along the crank axis, the Top-plane end south).  Both axes lie in the
Front plane, which is the clocking reference the assembly turns the throw by.
Two wrench flats on the south end, square to the throw, turn it.

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
    define_centered_rectangle,
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
import crank_hub_geometry
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
    FLATS_ACROSS,
    FLATS_LENGTH,
    FLATS_THROW_LEAN,
    GEOMETRIC_CONTROLS,
    LENGTH,
    OD_BAND,
    OUTER_DIA,
    PART_DATUMS,
    SURFACE_FINISHES,
    WALL_FLOOR_MM,
)

PART_NAME = "crank-eccentric-bushing"
MATERIAL = "Brass"  # nearest SolidWorks entry; the yaml names the bronze

# The bore is this part's running fit, so its band is DERIVED, as on
# cone-tip-bushing: from the named fit class (crank-eccentric-bushing.yaml:
# shaft_in_bushing) and the 3/8 in core's own limits.  bore_min = shaft_max +
# clearance_min, bore_max = shaft_min + clearance_max.
_CLEARANCE_MIN, _CLEARANCE_MAX = (
    float(value)
    for value in _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
)
_SHAFT_UPPER, _SHAFT_LOWER = crank_hub_geometry.SHAFT_DIA_BAND
BORE_DIA_BAND = (  # (upper, lower) deviations from BORE_DIA
    crank_hub_geometry.SHAFT_DIA + _SHAFT_LOWER + _CLEARANCE_MAX - BORE_DIA,
    crank_hub_geometry.SHAFT_DIA + _SHAFT_UPPER + _CLEARANCE_MIN - BORE_DIA,
)

# The g6 OD in the post's H7 bore (crank_eccentric_bushing_spec.OD_BAND).
OD_SEAT_CLEARANCE = (
    POST_BORE_BAND[1] - OD_BAND[0],
    POST_BORE_BAND[0] - OD_BAND[1],
)
if OD_SEAT_CLEARANCE[0] <= 0.0:
    raise AssertionError("the bushing's g6 OD can bind in the post's H7 bore")

# Rule 12 (drawing-simplicity-policy.md): the thin side of the wall at
# print-worst -- OD at its minimum, the throw at its maximum, the bore at its
# maximum -- and the wall under a flat, with the flats' clocking at its angular
# limit.  Both sit under the 2.0 target and over the 1.5 floor, and both are
# the policy's named MHA-149 row; the test holds the row to these numbers.
_BORE_MAX = BORE_DIA + BORE_DIA_BAND[0]
_THROW_MAX = ECCENTRICITY + ECCENTRICITY_BAND[0]
WALL_WORST = (OUTER_DIA + OD_BAND[1]) / 2.0 - _THROW_MAX - _BORE_MAX / 2.0
_FLATS_ROW = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
FLATS_WALL_WORST = (
    (FLATS_ACROSS - _FLATS_ROW) / 2.0 - _THROW_MAX * FLATS_THROW_LEAN - _BORE_MAX / 2.0
)
for _name, _wall in (("thin side", WALL_WORST), ("under a flat", FLATS_WALL_WORST)):
    if _wall < WALL_FLOOR_MM - 1e-9:
        raise AssertionError(
            f"the bushing's wall {_name} is {_wall:.4f} at print-worst, under the "
            f"{WALL_FLOOR_MM} floor"
        )
if FLATS_ACROSS + _FLATS_ROW >= OUTER_DIA + OD_BAND[1]:
    raise AssertionError("the wrench flats can print as wide as the OD they cut")


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

    # Wrench flats, square to the throw (the throw lies along model X, so the
    # flats face +/-Z): the ring between an oversize circle and a rectangle
    # FlatsAcross deep in Z is cut from the south (Top-plane) end, into the
    # body, so it is reversed explicitly.
    await set_global(adapter, "FlatsAcross", f"{FLATS_ACROSS}mm")
    await set_global(adapter, "FlatsLength", f"{FLATS_LENGTH}mm")
    flats = SketchDims()
    check("create_sketch flats", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, OUTER_DIA, "flats outer", dims=flats,
        names=("FlatsCx", "FlatsCz", "FlatsClear"), drives=(None, None, None),
    )
    await define_centered_rectangle(
        adapter, OUTER_DIA / 2.0 + 0.5, FLATS_ACROSS / 2.0, "flats", dims=flats,
        name_width="FlatsSpan", name_depth="FlatsAcross",
        drive_depth='"FlatsAcross"',
    )
    await ensure_fully_defined(adapter, "flats sketch")
    check("exit_sketch flats", await adapter.exit_sketch())
    name_last_feature(adapter, "FlatsProfile")
    drive_jobs += flats.apply(adapter, "FlatsProfile")
    check("cut flats", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=FLATS_LENGTH, reverse_direction=True)))
    name_last_feature(adapter, "Flats")
    flats_depth = name_dimensions(adapter, "Flats", ["FlatsDepth"])
    drive_jobs += [(flats_depth[0], '"FlatsLength"')]
    _r, _h = OUTER_DIA / 2.0, FLATS_ACROSS / 2.0
    v_flats = 2.0 * FLATS_LENGTH * (
        _r * _r * math.acos(_h / _r) - _h * math.sqrt(_r * _r - _h * _h)
    )
    volume = await volume_check(adapter, "flats", volume - v_flats, 0.02 * v_flats)
    for dim_name, expr in drive_jobs[-2:]:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
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
    author_part_pmi(
        adapter,
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        surface_finishes=SURFACE_FINISHES,
    )
    apply_drawing_properties(
        adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES}
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
