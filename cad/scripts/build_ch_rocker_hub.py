r"""Reproduction script: rocker hub (MHA-CH-12; 20 used, one per rocker arm).

The turned 1018 hub of the built-up rocker arm MHA-CH-06
(``ch_rocker_arm_notes.BUILT_UP_PERMISSION_NOTE``), as SUPPLIED to the joint
(``ch_rocker_hub_spec``): the Ø.400 land at its finished size with its press
band on the MHA-CH-13 strap's reamed hole (``ch_rocker_hub_fit``), the bore
drilled under the finished ream and the length left long, both finished on the
joined part to the MHA-CH-06 print.

Layout: Front-plane annulus at the origin (land, bore) extruded mid-plane, so
the hub's own mid-plane is the Front plane, as the rocker's integral hub is.
Axis1 is the hub axis (Top Plane x Right Plane).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_hub.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from ch_rocker_hub_fit import HUB_LAND_BAND
from ch_rocker_hub_notes import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    SUPPLY_LENGTH_PREFIX,
)
from ch_rocker_hub_spec import (
    LAND_DIA,
    SUPPLY_BORE_DIA,
    SUPPLY_LENGTH_MIN,
    SUPPLY_LENGTH_TOL_TYPE,
    UNIT,
)

PART_NAME = "ch-rocker-hub"
MATERIAL = "Plain Carbon Steel"  # AISI 1018 cold-finish round
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
)

V_HUB = (
    math.pi * ((LAND_DIA / 2.0) ** 2 - (SUPPLY_BORE_DIA / 2.0) ** 2) * SUPPLY_LENGTH_MIN
)


def _supply_length_min_limit(adapter) -> None:
    """Print the supply length as a single MIN limit: SOLIDWORKS prints the
    nominal then "MIN", so the model value is the limit itself
    (build_ch_rod_pivot_pin._blank_min_limit's recipe)."""
    label = "SupplyLength@Hub"
    _, dimension = _named_dimension(adapter, "Hub", "SupplyLength")
    if not math.isclose(
        float(dimension.SystemValue), SUPPLY_LENGTH_MIN / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError(
            f"{label}: nominal {float(dimension.SystemValue) * 1000.0:.7f} is not "
            f"the limit {SUPPLY_LENGTH_MIN:.7f}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = SUPPLY_LENGTH_TOL_TYPE
    if (
        not tolerance.SetValues(0.0, 0.0)
        or int(tolerance.Type) != SUPPLY_LENGTH_TOL_TYPE
    ):
        raise RuntimeError(f"{label}: cannot retain the MIN limit")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "LandDia", f"{LAND_DIA}mm")
    await set_global(adapter, "SupplyBore", f"{SUPPLY_BORE_DIA}mm")
    await set_global(adapter, "SupplyLength", f"{SUPPLY_LENGTH_MIN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: land + supply bore in ONE sketch (both on-axis circles -> only
    # the two diameter dims emit), extruded once.
    ring = SketchDims()
    check("create_sketch hub", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        LAND_DIA / 2.0,
        "hub land",
        dims=ring,
        names=("LandCx", "LandCz", "LandDia"),
        drives=(None, None, '"LandDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        SUPPLY_BORE_DIA / 2.0,
        "hub supply bore",
        dims=ring,
        names=("BoreCx", "BoreCz", "SupplyBore"),
        drives=(None, None, '"SupplyBore"'),
    )
    await ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", await adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += ring.apply(adapter, "HubProfile")
    check(
        "extrude hub",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SUPPLY_LENGTH_MIN, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Hub")
    hub_depth = name_dimensions(adapter, "Hub", ["SupplyLength"])
    drive_jobs.append((hub_depth[0], '"SupplyLength"'))
    await volume_check(adapter, "hub", V_HUB, 0.005 * V_HUB)

    # Axis1: the hub axis, model Z (Top Plane x Right Plane).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "hub axis")

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven hub (equations neutral)", V_HUB, 0.005 * V_HUB)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The land carries its press band natively; the supply bore takes the
    # title block's DRILLED HOLES row; the supply length is a single MIN limit
    # (it only has to leave facing stock, ch_rocker_hub_spec.FACE_STOCK).
    set_dimension_bilateral_tolerance(
        adapter, "HubProfile", "LandDia", *deviations(HUB_LAND_BAND), display_unit=UNIT
    )
    _supply_length_min_limit(adapter)
    set_dimension_prefix(adapter, "Hub", "SupplyLength", SUPPLY_LENGTH_PREFIX)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
