r"""Build the cone tip gears' phasing comb (MHA-DT-03-TL-02; shop tooling).

One flat brass sheet (dt_cone_gear_tl_phasing_comb_spec), cut to shape: its
stepped edge carries one blade per gear, T030, T024, T018, T012 and T006,
each dropping into one tooth space of that gear while LOCTITE 638 grabs
(MHA-DT-00 step 1). Model frame (spec docstring): X north along the sheet,
Y radially outward, Z through the thickness; the origin is the sheet's south
end on the seat line (its T030 blade's edge).

Features:

* ``SheetProfile`` on the Front plane: the closed staircase outline, every
  length and depth driven from the spec's globals.
* ``Sheet``: the outline extruded +Z by the stock's thickness.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_gear_tl_phasing_comb.py
"""

from __future__ import annotations

import sys
from typing import Any

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import SketchDims, add_line_chain, dimension_between, ensure_fully_defined
from dt_cone_gear_tl_phasing_comb_spec import (
    BONDED_TEETH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    GLOBALS,
    ISOMETRIC_VIEW_NOTE,
    PROFILE_SKETCH,
    SHEET_FEATURE,
    SHEET_THICK,
    SHEET_VOLUME,
    blade_depth_name,
    blade_start_name,
    gear_tag,
    profile_points_mm,
    step_corner_index,
)

PART_NAME = "dt-cone-gear-tl-phasing-comb"
MATERIAL = "Brass"  # see _appearance.apply_material docstring
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)


def _require_one_solid_body(adapter: Any, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


async def _sheet_profile(adapter: Any) -> list[tuple[str, str]]:
    """The closed staircase (``profile_points_mm``): every segment horizontal
    or vertical, the south end's seat corner on the origin, every step's
    start from the south end and every depth from the seat line (the
    origin's), both at the step's lower corner."""
    points = profile_points_mm()
    check("create_sketch sheet profile", await adapter.create_sketch("Front"))
    lines = await add_line_chain(adapter, points)
    for index, line in enumerate(lines):
        (x0, y0), (x1, y1) = points[index], points[(index + 1) % len(points)]
        direction = "horizontal" if y0 == y1 else "vertical"
        if direction == "vertical" and x0 != x1:
            raise ValueError(f"sheet profile segment {index} is not axis-parallel")
        check(
            f"sheet profile {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    check(
        "sheet profile seat corner -> origin",
        await adapter.add_sketch_constraint(
            f"{lines[1]}.start", "origin", "coincident"
        ),
    )

    def start(index: int) -> str:
        return f"{lines[index]}.start"

    dims = SketchDims()
    top = len(points) - 1
    await dimension_between(
        adapter,
        start(0),
        start(top),
        "horizontal_distance",
        points[top][0] - points[0][0],
        "sheet length",
    )
    dims.record("SheetLength", '"SheetLength"')
    await dimension_between(
        adapter, "origin", start(0), "vertical_distance", points[0][1], "sheet height"
    )
    dims.record("SheetHeight", '"SheetHeight"')
    for teeth in BONDED_TEETH:
        corner = step_corner_index(teeth)
        await dimension_between(
            adapter,
            "origin",
            start(corner),
            "horizontal_distance",
            points[corner][0],
            f"{gear_tag(teeth)} blade start",
        )
        dims.record(blade_start_name(teeth), f'"{blade_start_name(teeth)}"')
        await dimension_between(
            adapter,
            "origin",
            start(corner),
            "vertical_distance",
            -points[corner][1],
            f"{gear_tag(teeth)} blade depth",
        )
        dims.record(blade_depth_name(teeth), f'"{blade_depth_name(teeth)}"')
    await ensure_fully_defined(adapter, "sheet profile")
    check("exit_sketch sheet profile", await adapter.exit_sketch())
    name_last_feature(adapter, PROFILE_SKETCH)
    return dims.apply(adapter, PROFILE_SKETCH)


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units, and this is an inch document.
    for name, value in GLOBALS.items():
        await set_global(adapter, name, f"{value}mm")

    drive_jobs = await _sheet_profile(adapter)
    check(
        "extrude sheet",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHEET_THICK)),
    )
    name_last_feature(adapter, SHEET_FEATURE)
    drive_jobs.append(
        (name_dimensions(adapter, SHEET_FEATURE, ["SheetThick"])[0], '"SheetThick"')
    )
    await volume_check(adapter, "sheet", SHEET_VOLUME, 0.002 * SHEET_VOLUME)
    _require_one_solid_body(adapter, label="phasing comb")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "driven phasing comb (equations neutral)",
        SHEET_VOLUME,
        0.002 * SHEET_VOLUME,
    )
    _require_one_solid_body(adapter, label="driven phasing comb")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
