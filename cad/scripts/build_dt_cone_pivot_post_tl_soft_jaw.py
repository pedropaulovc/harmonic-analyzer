r"""Build the cone pivot post's tall vise soft jaw (MHA-DT-005-TL-04; shop fixture).

A 6061 plate that replaces one of the PM 6 in vise's hardened jaw plates on
the vise's own M10 jaw screws, tall enough to close over the cone post's
buttoned cone-boss caps (``dt_cone_pivot_post_tl_soft_jaw_spec``). Two are
made, identical.

Layout: the plate outline is a Front-plane rectangle from the origin corner
(length +X, height +Y) extruded +Z by the thickness, so the back face seats
on the vise jaw at Z0 and the gripping face is +Z. The two counterbored bolt
holes are ONE native Hole Wizard feature drilled from the gripping face,
placed from the plate's bottom-left corner.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_pivot_post_tl_soft_jaw.py
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
    set_dimension_prefix,
)
from _holes import wizard_holes
from _saved_part_guard import require_saved_drawing_properties
from dt_cone_pivot_post_tl_soft_jaw_spec import (
    BOLT_HEIGHT,
    BOLT_HOLE_DIA,
    BOLT_HOLE_SPEC,
    BOLT_LEFT_X,
    BOLT_RIGHT_X,
    DIMENSION_PREFIXES,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    PLATE_HEIGHT,
    PLATE_LENGTH,
    PLATE_THICK,
)

PART_NAME = "dt-cone-pivot-post-tl-soft-jaw"
MATERIAL = "6061 Alloy"  # the registry row names the 6061-T6 flat bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

V_PLATE = PLATE_LENGTH * PLATE_HEIGHT * PLATE_THICK


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
    await set_global(adapter, "PlateLength", f"{PLATE_LENGTH}mm")
    await set_global(adapter, "PlateHeight", f"{PLATE_HEIGHT}mm")
    await set_global(adapter, "PlateThick", f"{PLATE_THICK}mm")
    await set_global(adapter, "BoltLeftX", f"{BOLT_LEFT_X}mm")
    await set_global(adapter, "BoltRightX", f"{BOLT_RIGHT_X}mm")
    await set_global(adapter, "BoltY", f"{BOLT_HEIGHT}mm")

    drive_jobs: list[tuple[str, str]] = []

    outline = SketchDims()
    check("create_sketch plate", await adapter.create_sketch("Front"))
    rect = [
        (0.0, 0.0),
        (PLATE_LENGTH, 0.0),
        (PLATE_LENGTH, PLATE_HEIGHT),
        (0.0, PLATE_HEIGHT),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter,
        lines,
        rect,
        label="soft-jaw outline",
        dims=outline,
        names=["PlateLength", "PlateHeight"],
        drives=['"PlateLength"', '"PlateHeight"'],
    )
    await ensure_fully_defined(adapter, "soft-jaw outline")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += outline.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_THICK)),
    )
    name_last_feature(adapter, "Plate")
    drive_jobs.append((name_dimensions(adapter, "Plate", ["PlateThick"])[0], '"PlateThick"'))
    await volume_check(adapter, "soft-jaw plate", V_PLATE, 0.005 * V_PLATE)

    # The vise's two jaw-screw holes: ONE native Hole Wizard counterbore
    # feature drilled from the gripping face, each station from the plate's
    # bottom-left corner (the outline's origin); the right hole's height
    # repeats the left's and stays off the print.
    holes = wizard_holes(
        adapter,
        BOLT_HOLE_SPEC,
        [[x, BOLT_HEIGHT, PLATE_THICK] for x in (BOLT_LEFT_X, BOLT_RIGHT_X)],
        (0.0, 0.0, 1.0),
        "soft-jaw bolt holes (M10 clearance cbore)",
        name="BoltHoles",
        expect_dia_mm=BOLT_HOLE_DIA,
        placement_dims=[
            (("BoltLeftX", '"BoltLeftX"'), ("BoltY", '"BoltY"')),
            (("BoltRightX", '"BoltRightX"'), ("BoltRightY", '"BoltY"')),
        ],
    )
    drive_jobs += holes.placement_drive_jobs
    v_hole = math.pi * (holes.cbore_dia_mm / 2.0) ** 2 * holes.cbore_depth_mm + math.pi * (
        holes.hole_dia_mm / 2.0
    ) ** 2 * (PLATE_THICK - holes.cbore_depth_mm)
    v_final = V_PLATE - 2.0 * v_hole
    await volume_check(adapter, "soft jaw with bolt holes", v_final, 0.005 * V_PLATE)
    _require_one_solid_body(adapter, label="soft jaw")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven soft jaw (equations neutral)", v_final, 0.005 * V_PLATE
    )
    _require_one_solid_body(adapter, label="driven soft jaw")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for (feature_name, dimension_name), prefix in DIMENSION_PREFIXES.items():
        set_dimension_prefix(adapter, feature_name, dimension_name, prefix)
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
