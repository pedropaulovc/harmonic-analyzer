r"""Build the cone tip gears' phasing comb (MHA-DT-03-TL-02; shop tooling).

One flat sheet (dt_cone_gear_tl_phasing_comb_spec), cut to a U: its near
arm's stepped edge carries one blade per gear, T030, T024, T018, T012 and
T006, each dropping into one tooth space of that gear while LOCTITE 638 grabs
(MHA-DT-00 step 1); its far arm, a spring, holds a second blade in T030's
mirror space; the bridge joins them over the tip. Model frame (spec
docstring): X north along the cone, Y radially outward through the near arm,
Z through the thickness; the origin is the near arm's south end on the seat
line (its T030 blade's edge).

Features:

* ``SheetProfile`` on the Front plane: the closed U outline, every length,
  width and depth driven from the spec's globals.
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
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    GLOBALS,
    GRIP_POINT,
    RETURN_POINT,
    ISOMETRIC_VIEW_NOTE,
    MATERIAL,
    ORIGIN,
    PROFILE_SKETCH,
    SHEET_FEATURE,
    SHEET_THICK,
    SHEET_VOLUME,
    SKETCH_DIMENSIONS,
    profile_points_mm,
)

PART_NAME = "dt-cone-gear-tl-phasing-comb"
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
    """The closed U (``profile_points_mm``): every segment horizontal or
    vertical, the near arm's seat corner on the origin, each driving
    dimension of ``SKETCH_DIMENSIONS`` between its two points.  The spring
    arm's end (from ``GRIP_POINT``) is collinear with the near arm's, so both
    arms' feet stand on T036 at the seat edge's station, and the near arm's
    edge past T006's level (from ``RETURN_POINT``) with the T030 blade's, on
    the seat line."""
    points = profile_points_mm()
    check("create_sketch sheet profile", await adapter.create_sketch("Front"))
    lines = await add_line_chain(adapter, points)
    collinear = {GRIP_POINT: 0, RETURN_POINT: 1}
    for index, other in collinear.items():
        check(
            f"sheet profile line {index} on line {other}",
            await adapter.add_sketch_constraint(
                lines[index], lines[other], "collinear"
            ),
        )
    for index, line in enumerate(lines):
        if index in collinear:
            continue
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

    def ref(point: str | int) -> str:
        return ORIGIN if point == ORIGIN else f"{lines[point]}.start"

    dims = SketchDims()
    for name, start, end, kind in SKETCH_DIMENSIONS:
        await dimension_between(
            adapter, ref(start), ref(end), kind, GLOBALS[name], name
        )
        dims.record(name, f'"{name}"')
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
