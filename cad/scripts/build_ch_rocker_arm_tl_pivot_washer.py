r"""Build the rocker arm's pivot-screw washer (MHA-CH-006-TL-07; shop fixture).

An as-supplied O1 drill-rod washer the pivot screw's head clamps onto the upper hub
face (``ch_rocker_arm_tl_pivot_washer_spec``). Layout: two concentric Front
plane circles extruded +Z by the thickness, so the hub face is Z0 in the
inventory's fixture frame.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_pivot_washer.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
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
from ch_rocker_arm_tl_pivot_washer_spec import (
    BORE_BAND,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    OUTER_DIA,
    THICK,
)

PART_NAME = "ch-rocker-arm-tl-pivot-washer"
MATERIAL = "Alloy Steel"  # the registry row names the O1 drill rod
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

V_WASHER = math.pi / 4.0 * (OUTER_DIA**2 - BORE_DIA**2) * THICK


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "OuterDia", f"{OUTER_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "Thick", f"{THICK}mm")

    profile = SketchDims()
    check("create_sketch washer", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        OUTER_DIA / 2.0,
        "washer outside",
        dims=profile,
        names=("OuterCx", "OuterCy", "OuterDia"),
        drives=(None, None, '"OuterDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIA / 2.0,
        "washer bore",
        dims=profile,
        names=("BoreCx", "BoreCy", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "washer sketch")
    check("exit_sketch washer", await adapter.exit_sketch())
    name_last_feature(adapter, "WasherProfile")
    drive_jobs = profile.apply(adapter, "WasherProfile")
    check("extrude washer", await adapter.create_extrusion(ExtrusionParameters(depth=THICK)))
    name_last_feature(adapter, "Washer")
    drive_jobs.append((name_dimensions(adapter, "Washer", ["Thick"])[0], '"Thick"'))
    await volume_check(adapter, "washer", V_WASHER, 0.005 * V_WASHER)

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven washer (equations neutral)", V_WASHER, 0.005 * V_WASHER)
    bodies = tuple(_early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"pivot washer: expected one solid body, found {len(bodies)}")

    set_dimension_bilateral_tolerance(
        adapter, "WasherProfile", "BoreDia", *deviations(BORE_BAND)
    )
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
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
