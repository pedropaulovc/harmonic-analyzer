r"""Build the rocker arm hub filing button (MHA-CH-006-TL-04; shop fixture).

A hardened, lapped O1 button that rides the filing stud and seats on one hub
face of the rocker arm; its rim is the filing line for the hub O.D.
(``ch_rocker_arm_tl_filing_button_spec``). Two are made.

Layout: Front-plane annulus at the origin (O.D., bore) extruded +Z by the
thickness, like the rocker thrust washer.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_filing_button.py
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
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_filing_button_spec import (
    BORE_BAND,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    OD,
    THICKNESS,
)

PART_NAME = "ch-rocker-arm-tl-filing-button"
MATERIAL = "Alloy Steel"  # the registry row names the O1 drill rod
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

V_DISC = math.pi * ((OD / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2) * THICKNESS


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    await set_global(adapter, "DiscDia", f"{OD}mm")
    await set_global(adapter, "DiscThick", f"{THICKNESS}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")

    ring = SketchDims()
    check("create_sketch ring", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        OD / 2.0,
        "button rim",
        dims=ring,
        names=("OdCx", "OdCy", "DiscDia"),
        drives=(None, None, '"DiscDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIA / 2.0,
        "stud bore",
        dims=ring,
        names=("BoreCx", "BoreCy", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "ring sketch")
    check("exit_sketch ring", await adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    drive_jobs = ring.apply(adapter, "RingProfile")
    check(
        "extrude ring",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, "Disc")
    drive_jobs.append((name_dimensions(adapter, "Disc", ["DiscThick"])[0], '"DiscThick"'))
    await volume_check(adapter, "button", V_DISC, 0.005 * V_DISC)

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven button (equations neutral)", V_DISC, 0.005 * V_DISC
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(adapter, "RingProfile", "BoreDia", *deviations(BORE_BAND))
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
