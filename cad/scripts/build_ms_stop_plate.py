r"""Build the blackened brass cover of the measuring-stick stop.

The block and plate use one frame: the plate occupies Z=-1..0, with its
clearance holes along +Z. Roof-end chamfers match the approved block outline.
Run only through the supervised farm launcher: part:ms_stop_plate.
"""

from __future__ import annotations

import sys

import ms_stop_spec as spec
from _common import (
    PANEL_BLACK, SketchDims, add_line_chain, apply_color, apply_material, check,
    define_rectilinear_chain, drive_dimension, ensure_fully_defined, force_rebuild,
    name_dimensions, name_last_feature, report_mass_properties, run_build,
    save_part_and_images, set_global, volume_check,
)
from _drawing_marks import (
    apply_drawing_precision, apply_drawing_properties, clear_dimensions_for_drawing,
    mark_dimensions_for_drawing, set_dimension_symmetric_tolerance,
)
from _holes import wizard_holes
from ms_stop_geom import (
    author_hole_precision, hide_location_references, location_reference,
    pilot_drill_reference,
)

PART_NAME = "ms-stop-plate"
MATERIAL = "Brass"
DRAWING_DIMENSIONS = spec.PLATE_DRAWING_DIMENSIONS
DRAWING_PRECISION = spec.PLATE_DRAWING_PRECISION


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create stop cover", await adapter.create_part())
    for name, value in (
        ("PlateLength", spec.BLOCK_LENGTH), ("PlateHeight", spec.BLOCK_HEIGHT),
        ("PlateThickness", spec.PLATE_THICKNESS),
        ("RoofChamferSize", spec.ROOF_END_CHAMFER),
        ("PilotDrillDiameter", spec.PLATE_TAP_DRILL_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")
    dims = SketchDims()
    check("plate profile", await adapter.create_sketch("Front"))
    points = [(0.0, 0.0), (spec.BLOCK_LENGTH, 0.0),
              (spec.BLOCK_LENGTH, spec.BLOCK_HEIGHT), (0.0, spec.BLOCK_HEIGHT)]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter, lines, points, label="cover", dims=dims,
        names=["PlateLength", "PlateHeight"],
        drives=['"PlateLength"', '"PlateHeight"'],
    )
    await ensure_fully_defined(adapter, "plate profile")
    check("exit plate profile", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    jobs = dims.apply(adapter, "PlateProfile")
    check("cover extrusion", await adapter.create_extrusion(
        ExtrusionParameters(depth=spec.PLATE_THICKNESS, reverse_direction=True)))
    name_last_feature(adapter, "Plate")
    name_dimensions(adapter, "Plate", ["PlateThickness"])
    jobs.append(("PlateThickness@Plate", '"PlateThickness"'))
    check("cover roof end chamfers", await adapter.add_chamfer(
        spec.ROOF_END_CHAMFER,
        [[0.0, spec.BLOCK_HEIGHT, (spec.PLATE_Z_MIN + spec.PLATE_Z_MAX) / 2.0],
         [spec.BLOCK_LENGTH, spec.BLOCK_HEIGHT, (spec.PLATE_Z_MIN + spec.PLATE_Z_MAX) / 2.0]],
    ))
    name_last_feature(adapter, "RoofChamfers")
    name_dimensions(adapter, "RoofChamfers", ["RoofChamferSize", "RoofChamferAngle"])
    jobs.append(("RoofChamferSize@RoofChamfers", '"RoofChamferSize"'))
    wizard_holes(adapter, spec.PLATE_CLEARANCE_SPEC, spec.PLATE_HOLE_POINTS,
                 spec.PLATE_HOLE_NORMAL, "cover clearance holes", name="PlateClearances",
                 expect_dia_mm=spec.PLATE_CLEARANCE_DIA)
    author_hole_precision(adapter, "PlateClearances")
    await location_reference(
        adapter, feature="PlateLocationReference", plane="Front",
        spans=spec.PLATE_HOLE_XS, station=spec.PLATE_HOLE_Y,
        names=("PlateLeftFromEnd", "PlateFromHeadFace", "PlateRightFromEnd"),
    )
    jobs += await pilot_drill_reference(adapter)
    await force_rebuild(adapter)
    for name, expression in jobs:
        await drive_dimension(adapter, name, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "finished brass stop cover", spec.PLATE_FINISHED_VOLUME,
                       0.005 * spec.PLATE_FINISHED_VOLUME)
    set_dimension_symmetric_tolerance(
        adapter, "Plate", "PlateThickness", spec.PLATE_THICKNESS_TOLERANCE_MM,
    )
    for name in spec.PLATE_LOCATION_DIMENSIONS:
        set_dimension_symmetric_tolerance(
            adapter, "PlateLocationReference", name, spec.PLATE_HOLE_POSITION_TOLERANCE_MM,
        )
    clear_dimensions_for_drawing(adapter)
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(adapter, PART_NAME, {
        "Manufacturing Notes": spec.PLATE_DRAWING_NOTES,
        "Isometric View Note": spec.ISOMETRIC_VIEW_NOTE,
    })
    hide_location_references(adapter, ("PlateLocationReference", "PilotDrillReference"))
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
