r"""Reproduction script: cylinder-bank end thrust washer (#743; 2 used).

The turned steel washer at each end of the solid cylinder-gear stack, between
the end gear and its arbor-pedestal strap. The back-side photographs (ch13
page002_img01, ch25 page002_img03) show a grey annulus of about 2.6x the ~O10
arbor dome between the strap and gear 19 (inferred, photo-scaled); the front
side shows gear 0's cam and rod directly behind the strap with no large disc,
so the former O55 brass "end disc" is retired (user ruling on #743, Q2). The
back washer's thickness sits in the bank's axial datum chain
(cylinder_bank_layout), so it carries a held band. The dimensions live in
cylinder_end_disc_spec.

Layout: Front-plane annulus at the origin (OD WASHER_OD, bore WASHER_BORE)
extruded +Z by WASHER_THICK. The drive-train assembly seats one against each
end gear and locks it to the arbor.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cylinder_end_disc.py
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
    apply_drawing_precision,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from cylinder_end_disc_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    WASHER_BORE,
    WASHER_BORE_BAND,
    WASHER_OD,
    WASHER_THICK,
    WASHER_THICK_TOLERANCE_MM,
)

PART_NAME = "cylinder-end-disc"
MATERIAL = "Plain Carbon Steel"  # the photographed annulus reads grey steel

DISC_DIA = WASHER_OD
DISC_THICK = WASHER_THICK
BORE_DIA = WASHER_BORE

V_DISC = math.pi * ((DISC_DIA / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2) * DISC_THICK


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

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
    set_dimension_bilateral_tolerance(
        adapter, "RingProfile", "BoreDia", *deviations(WASHER_BORE_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "Disc", "DiscThick", WASHER_THICK_TOLERANCE_MM
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
