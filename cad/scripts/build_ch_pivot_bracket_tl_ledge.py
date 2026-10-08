r"""Build the pivot bracket's angle-plate ledge (MHA-CH-008-TL-01; shop fixture).

A 1018 block screwed to the reworked angle plate's upright: the bracket's
foot free end rests on its top in the bracket's S4 setup
(``ch_pivot_bracket_tl_ledge_spec``).

Layout: the face outline is a Front-plane rectangle from the origin corner
(left end, bottom face), extruded +Z by the thickness (the back face, which
seats on the upright, is Z0); two #5 through holes are drilled from the
front face.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_pivot_bracket_tl_ledge.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
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
)
from _holes import wizard_holes
from _saved_part_guard import require_saved_drawing_properties
from ch_pivot_bracket_tl_ledge_spec import (
    CLEARANCE_SPEC,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HOLE_DIA,
    HOLE_X,
    HOLE_Y,
    ISOMETRIC_VIEW_NOTE,
    LEDGE_HEIGHT,
    LEDGE_THICK,
    LEDGE_WIDTH,
)

PART_NAME = "ch-pivot-bracket-tl-ledge"
MATERIAL = "Plain Carbon Steel"  # the registry row names the 1018 bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

V_BLOCK = LEDGE_WIDTH * LEDGE_HEIGHT * LEDGE_THICK
V_TOTAL = V_BLOCK - len(HOLE_X) * math.pi * (HOLE_DIA / 2.0) ** 2 * LEDGE_THICK


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    await set_global(adapter, "LedgeWidth", f"{LEDGE_WIDTH}mm")
    await set_global(adapter, "LedgeHeight", f"{LEDGE_HEIGHT}mm")
    await set_global(adapter, "LedgeThick", f"{LEDGE_THICK}mm")
    await set_global(adapter, "LedgeHoleX1", f"{HOLE_X[0]}mm")
    await set_global(adapter, "LedgeHoleX2", f"{HOLE_X[1]}mm")
    await set_global(adapter, "LedgeHoleY", f"{HOLE_Y}mm")

    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    rect = [
        (0.0, 0.0),
        (LEDGE_WIDTH, 0.0),
        (LEDGE_WIDTH, LEDGE_HEIGHT),
        (0.0, LEDGE_HEIGHT),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter,
        lines,
        rect,
        label="ledge outline",
        dims=outline,
        names=["Width", "Height"],
        drives=['"LedgeWidth"', '"LedgeHeight"'],
    )
    await ensure_fully_defined(adapter, "ledge outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "LedgeProfile")
    drive_jobs = outline.apply(adapter, "LedgeProfile")
    check(
        "extrude ledge",
        await adapter.create_extrusion(ExtrusionParameters(depth=LEDGE_THICK)),
    )
    name_last_feature(adapter, "Ledge")
    drive_jobs.append((name_dimensions(adapter, "Ledge", ["Thick"])[0], '"LedgeThick"'))
    await volume_check(adapter, "ledge block", V_BLOCK, 0.005 * V_BLOCK)

    # ONE native #5 drill feature, two through instances from the front face;
    # the second hole's height repeats the first's and stays off the print.
    holes = wizard_holes(
        adapter,
        CLEARANCE_SPEC,
        [[x, HOLE_Y, LEDGE_THICK] for x in HOLE_X],
        (0.0, 0.0, 1.0),
        "ledge screw holes (#5 drill)",
        name="ScrewHoles",
        expect_dia_mm=HOLE_DIA,
        placement_dims=[
            (("Hole1X", '"LedgeHoleX1"'), ("Hole1Y", '"LedgeHoleY"')),
            (("Hole2X", '"LedgeHoleX2"'), ("Hole2Y", '"LedgeHoleY"')),
        ],
    )
    drive_jobs += holes.placement_drive_jobs
    await volume_check(adapter, "ledge with holes", V_TOTAL, 0.002 * V_BLOCK)

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven ledge (equations neutral)", V_TOTAL, 0.002 * V_BLOCK
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
