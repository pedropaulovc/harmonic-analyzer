r"""Build the rocker inspection box's C stop bar (MHA-CH-006-TL-09; shop fixture).

A hardened, lapped O1 bar screwed to the inspection box's front wall, seated
on the granite with the box: its top is the datum-C stop for the rocker arm's
off-machine position check (``ch_rocker_arm_tl_c_stop_bar_spec``).

Layout (the box's model frame): the bar profile is a Front-plane rectangle
from the origin, extruded +Z (away from the box) by the stock width; the two
#8 socket-head counterbores enter from the +Z face.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_c_stop_bar.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
    apply_material,
    check,
    define_rectilinear_chain,
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
from _holes import wizard_holes
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_c_stop_bar_spec import (
    BAR_HEIGHT,
    BAR_LENGTH,
    BAR_WIDTH,
    CLEARANCE_DIA,
    DRAWING_BANDS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    SCREW_HOLE_SPEC,
    SCREW_X,
    SCREW_Y,
)

PART_NAME = "ch-rocker-arm-tl-c-stop-bar"
MATERIAL = "Plain Carbon Steel"  # the registry row names the O1 ground flat stock
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

V_BAR = BAR_LENGTH * BAR_HEIGHT * BAR_WIDTH


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"{label}: expected exactly one solid body, found {len(bodies)}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")
    await set_global(adapter, "BarHeight", f"{BAR_HEIGHT}mm")
    await set_global(adapter, "BarWidth", f"{BAR_WIDTH}mm")

    profile = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    points = [(0.0, 0.0), (BAR_LENGTH, 0.0), (BAR_LENGTH, BAR_HEIGHT), (0.0, BAR_HEIGHT)]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="bar profile",
        dims=profile,
        names=["BarLength", "BarHeight"],
        drives=['"BarLength"', '"BarHeight"'],
    )
    await ensure_fully_defined(adapter, "bar profile")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs = profile.apply(adapter, "BarProfile")
    check("extrude bar", await adapter.create_extrusion(ExtrusionParameters(depth=BAR_WIDTH)))
    name_last_feature(adapter, "Bar")
    drive_jobs.append((name_dimensions(adapter, "Bar", ["BarWidth"])[0], '"BarWidth"'))
    volume = await volume_check(adapter, "bar", V_BAR, 0.002 * V_BAR)

    holes = wizard_holes(
        adapter,
        SCREW_HOLE_SPEC,
        [[x, SCREW_Y, BAR_WIDTH] for x in SCREW_X],
        (0.0, 0.0, 1.0),
        "C stop bar screw holes (#8 socket counterbore)",
        name="ScrewHoles",
        expect_dia_mm=CLEARANCE_DIA,
        placement_dims=[
            (("HoleLeftX", None), ("HoleY", None)),
            (("HoleRightX", None), ("HoleRightY", None)),
        ],
    )
    drive_jobs += holes.placement_drive_jobs
    v_hole = math.pi * (holes.hole_dia_mm / 2.0) ** 2 * (
        BAR_WIDTH - holes.cbore_depth_mm
    ) + math.pi * (holes.cbore_dia_mm / 2.0) ** 2 * holes.cbore_depth_mm
    volume = await volume_check(
        adapter, "screw holes", volume - 2.0 * v_hole, 0.01 * 2.0 * v_hole
    )
    _require_one_solid_body(adapter, label="bar")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bar (equations neutral)", volume, 0.002 * V_BAR)
    _require_one_solid_body(adapter, label="driven bar")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    for (feature_name, dimension_name), band in DRAWING_BANDS.items():
        set_dimension_bilateral_tolerance(
            adapter, feature_name, dimension_name, *deviations(band)
        )
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
