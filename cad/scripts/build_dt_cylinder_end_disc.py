r"""Reproduction script: south cylinder-bank end disc (MHA-DT-26; one used).

The C36000 brass disc has a reduced OD to clear the unchanged drive.
Its drilled bore clears the arbor; the ordinary thickness band meets the web target.
The south face seats directly on the south arbor-pedestal strap; the north
face closes gear 0's cam slot. The north spring holds the bank south onto
this datum. Dimensions live in dt_cylinder_end_disc_spec.

Layout: Front-plane annulus at the origin (OD WASHER_OD, bore WASHER_BORE)
extruded +Z by WASHER_THICK, stationary on the arbor.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cylinder_end_disc.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _document_units import apply_package_model_units
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from _drawing_precision import apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from dt_cylinder_end_disc_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    WASHER_BORE,
    WASHER_OD,
    WASHER_THICK,
)

PART_NAME = "dt-cylinder-end-disc"
MATERIAL = "Brass"

DISC_DIA = WASHER_OD
DISC_THICK = WASHER_THICK
BORE_DIA = WASHER_BORE

V_DISC = math.pi * ((DISC_DIA / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2) * DISC_THICK


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "DiscDia", f"{DISC_DIA}mm")
    await set_global(adapter, "DiscThick", f"{DISC_THICK}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: OD + bore in ONE sketch (both on-axis circles -> only the two
    # diameter dims emit), extruded once.
    ring = SketchDims()
    check("create_sketch ring", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        DISC_DIA / 2.0,
        "disc OD",
        dims=ring,
        names=("OdCx", "OdCz", "DiscDia"),
        drives=(None, None, '"DiscDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIA / 2.0,
        "arbor bore",
        dims=ring,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "ring sketch")
    check("exit_sketch ring", await adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    drive_jobs += ring.apply(adapter, "RingProfile")
    check(
        "extrude ring",
        await adapter.create_extrusion(ExtrusionParameters(depth=DISC_THICK)),
    )
    name_last_feature(adapter, "Disc")
    disc_depth = name_dimensions(adapter, "Disc", ["DiscThick"])
    drive_jobs.append((disc_depth[0], '"DiscThick"'))
    await volume_check(adapter, "disc", V_DISC, 0.005 * V_DISC)

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven disc (equations neutral)", V_DISC, 0.005 * V_DISC)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # MHA-DT-26's title block reads Material Specification / Finish / Quantity
    # from its registry row (test_source_properties_drawing).
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
