r"""Build the blackened brass stop block (approved ch16 sketch, 2026-10-09).

The block frame and envelope are owned by ms_stop_spec. The X-through rebate starts at Z=0;
ms-stop-plate closes it. All hardware is separate, stock catalogue geometry.

The split-common helper ownership from the retired
build_ha_measuring_stick_stop recipe is carried into this block, the separate
cover and ms_stop_geom. Its old steel cube and merged head are not restored:
the approved brass parts and stock fasteners remain separate.
Run only through the supervised farm launcher: part:ms_stop_block.
"""

from __future__ import annotations

import sys

import ms_stop_spec as spec
from _appearance import PANEL_BLACK, apply_color, apply_material
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, add_line_chain, ensure_fully_defined
from _sketch_chains import define_rectilinear_chain
from _drawing_marks import (
    apply_drawing_precision, apply_drawing_properties, clear_dimensions_for_drawing,
    mark_dimensions_for_drawing, set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _holes import wizard_holes
from ms_stop_geom import (
    author_hole_precision, hide_location_references, location_reference,
    roof_reference, window_width_reference,
)

PART_NAME = "ms-stop-block"
MATERIAL = "Brass"
DRAWING_DIMENSIONS = spec.BLOCK_DRAWING_DIMENSIONS
DRAWING_PRECISION = spec.BLOCK_DRAWING_PRECISION


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create stop block", await adapter.create_part())
    for name, value in (
        ("BlockLength", spec.BLOCK_LENGTH), ("BlockHeight", spec.BLOCK_HEIGHT),
        ("BlockDepth", spec.BLOCK_DEPTH), ("WindowHeight", spec.WINDOW_HEIGHT),
        ("WindowWidth", spec.WINDOW_WIDTH), ("RoofThickness", spec.ROOF_THICKNESS),
        ("RoofChamferSize", spec.ROOF_END_CHAMFER),
    ):
        await set_global(adapter, name, f"{value}mm")
    await set_global(adapter, "WindowFloor", '"BlockHeight" - "RoofThickness" - "WindowHeight"')
    jobs: list[tuple[str, str]] = []
    dims = SketchDims()
    check("block profile", await adapter.create_sketch("Front"))
    points = [(0.0, 0.0), (spec.BLOCK_LENGTH, 0.0),
              (spec.BLOCK_LENGTH, spec.BLOCK_HEIGHT), (0.0, spec.BLOCK_HEIGHT)]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter, lines, points, label="block", dims=dims,
        names=["BlockLength", "BlockHeight"],
        drives=['"BlockLength"', '"BlockHeight"'],
    )
    await ensure_fully_defined(adapter, "block profile")
    check("exit block profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    jobs += dims.apply(adapter, "BlockProfile")
    check("block extrusion", await adapter.create_extrusion(ExtrusionParameters(depth=spec.BLOCK_DEPTH)))
    name_last_feature(adapter, "Block")
    name_dimensions(adapter, "Block", ["BlockDepth"])
    jobs.append(("BlockDepth@Block", '"BlockDepth"'))
    await volume_check(adapter, "block stock", spec.BLOCK_VOLUME, 0.005 * spec.BLOCK_VOLUME)

    dims = SketchDims()
    check("open rebate profile", await adapter.create_sketch("Front"))
    points = [(-spec.CUT_OVERHANG, spec.WINDOW_Y_MIN),
              (spec.BLOCK_LENGTH + spec.CUT_OVERHANG, spec.WINDOW_Y_MIN),
              (spec.BLOCK_LENGTH + spec.CUT_OVERHANG, spec.WINDOW_Y_MAX),
              (-spec.CUT_OVERHANG, spec.WINDOW_Y_MAX)]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter, lines, points, label="open rebate", dims=dims,
        names=["WindowCutLength", "WindowHeight", "WindowOverhang", "WindowFloor"],
        drives=[f'"BlockLength" + {2.0 * spec.CUT_OVERHANG}', '"WindowHeight"',
                None, '"WindowFloor"'],
    )
    await ensure_fully_defined(adapter, "rebate profile")
    check("exit rebate profile", await adapter.exit_sketch())
    name_last_feature(adapter, "WindowProfile")
    jobs += dims.apply(adapter, "WindowProfile")
    check("open rebate", await adapter.create_cut_extrude(ExtrusionParameters(depth=spec.WINDOW_WIDTH)))
    name_last_feature(adapter, "Window")
    name_dimensions(adapter, "Window", ["WindowWidth"])
    jobs.append(("WindowWidth@Window", '"WindowWidth"'))
    await volume_check(adapter, "open rebate", spec.BLOCK_VOLUME - spec.WINDOW_VOLUME, 0.005 * spec.BLOCK_VOLUME)

    check("roof end chamfers", await adapter.add_chamfer(
        spec.ROOF_END_CHAMFER,
        [[0.0, spec.BLOCK_HEIGHT, spec.BLOCK_DEPTH / 2.0],
         [spec.BLOCK_LENGTH, spec.BLOCK_HEIGHT, spec.BLOCK_DEPTH / 2.0]],
    ))
    name_last_feature(adapter, "RoofChamfers")
    name_dimensions(adapter, "RoofChamfers", ["RoofChamferSize", "RoofChamferAngle"])
    jobs.append(("RoofChamferSize@RoofChamfers", '"RoofChamferSize"'))

    wizard_holes(adapter, spec.THUMB_TAP_SPEC, spec.THUMB_HOLE_POINTS,
                 spec.THUMB_HOLE_NORMAL, "thumbscrew through floor", name="ThumbTap",
                 expect_dia_mm=spec.THUMB_TAP_DRILL)
    wizard_holes(adapter, spec.PLATE_TAP_SPEC, spec.BLOCK_PLATE_HOLE_POINTS,
                 spec.PLATE_HOLE_NORMAL, "cover plate blind taps", name="PlateTaps",
                 expect_dia_mm=spec.PLATE_TAP_DRILL_DIA)
    author_hole_precision(adapter, "ThumbTap")
    author_hole_precision(adapter, "PlateTaps")
    await location_reference(
        adapter, feature="ThumbLocationReference", plane="Top",
        spans=(spec.THUMB_AXIS_X,), station=-spec.THUMB_AXIS_Z,
        names=("ThumbFromEnd", "ThumbFromPlate"),
    )
    await location_reference(
        adapter, feature="PlateLocationReference", plane="Front",
        spans=spec.PLATE_HOLE_XS, station=spec.PLATE_HOLE_Y,
        names=("PlateLeftFromEnd", "PlateFromHeadFace", "PlateRightFromEnd"),
    )
    jobs += await roof_reference(adapter)
    jobs += await window_width_reference(adapter)
    await force_rebuild(adapter)
    for name, expression in jobs:
        await drive_dimension(adapter, name, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "finished brass stop block", spec.BLOCK_FINISHED_VOLUME,
                       0.005 * spec.BLOCK_FINISHED_VOLUME)
    lower, upper = spec.WINDOW_SIZE_TOLERANCE_MM
    set_dimension_bilateral_tolerance(adapter, "WindowProfile", "WindowHeight", lower, upper)
    set_dimension_bilateral_tolerance(adapter, "Window", "WindowWidth", lower, upper)
    set_dimension_bilateral_tolerance(adapter, "ReferenceWindowWidth", "WindowWidth", lower, upper)
    for name in spec.PLATE_LOCATION_DIMENSIONS:
        set_dimension_symmetric_tolerance(
            adapter, "PlateLocationReference", name, spec.PLATE_HOLE_POSITION_TOLERANCE_MM,
        )
    clear_dimensions_for_drawing(adapter)
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(adapter, PART_NAME, {
        "Manufacturing Notes": spec.BLOCK_DRAWING_NOTES,
        "Mating Face Note": spec.BLOCK_MATING_FACE_NOTE,
        "Isometric View Note": spec.ISOMETRIC_VIEW_NOTE,
    })
    hide_location_references(adapter, (
        "ThumbLocationReference", "PlateLocationReference", "RoofThicknessReference",
        "ReferenceWindowWidth",
    ))
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
