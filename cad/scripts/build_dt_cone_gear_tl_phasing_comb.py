r"""Build the cone tip gears' phasing comb (MHA-DT-03-TL-02; shop tooling).

One flat steel plate (dt_cone_gear_tl_phasing_comb_spec): its stepped edge
carries a fork per gear, T030, T024, T018, T012 and T006, each split by a slot
that straddles that gear's phase-0 tooth while LOCTITE 638 grabs (MHA-DT-00
step 1). Model frame (spec docstring): X north along the plate, Y radially
outward, Z through the thickness; the origin is the north end of the T030 fork
on the seat line.

Features:

* ``PlateProfile`` on the Front plane: the closed rectilinear outline, every
  length driven from the spec's globals; ``Plate`` extrudes it mid-plane.
* ``SlotProfileTnnn`` / ``SlotTnnn`` per fork: a Front-plane rectangle over
  the fork's length, from under its tip up to its slot bottom, cut mid-plane
  to the slot's width.

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
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import SketchDims, add_line_chain, dimension_between, ensure_fully_defined
from _sketch_chains import define_rectilinear_chain
from dt_cone_gear_tl_phasing_comb_spec import (
    BONDED_TEETH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FINISHED_VOLUME,
    FORK_TIP_DEPTH_MM,
    GEARS,
    GLOBALS,
    ISOMETRIC_VIEW_NOTE,
    MODEL_BANDS_MM,
    PLATE_FEATURE,
    PLATE_VOLUME,
    PROFILE_SKETCH,
    SLOT_VOLUME_MM3,
    SLOT_WIDTH_MM,
    THICKNESS,
    UNIT,
    gear_tag,
    profile_points_mm,
    slot_feature,
    slot_rectangle_mm,
    slot_sketch,
    slot_width_name,
)

PART_NAME = "dt-cone-gear-tl-phasing-comb"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring
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


async def _plate_profile(adapter: Any) -> list[tuple[str, str]]:
    """The closed outline (``profile_points_mm``): every segment horizontal or
    vertical, the T030 fork's north end on the origin, the lengths from the
    plate's south end and the heights from the seat line (the origin's)."""
    points = profile_points_mm()
    check("create_sketch plate profile", await adapter.create_sketch("Front"))
    lines = await add_line_chain(adapter, points)
    for index, line in enumerate(lines):
        (x0, y0), (x1, y1) = points[index], points[(index + 1) % len(points)]
        direction = "horizontal" if y0 == y1 else "vertical"
        if direction == "vertical" and x0 != x1:
            raise ValueError(f"plate profile segment {index} is not axis-parallel")
        check(
            f"plate profile {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    check(
        "plate profile seat corner -> origin",
        await adapter.add_sketch_constraint(
            f"{lines[3]}.start", "origin", "coincident"
        ),
    )

    def start(index: int) -> str:
        return f"{lines[index]}.start"

    dims = SketchDims()
    south_tip = start(1)  # the south end's lower corner (T030 fork tip)
    await dimension_between(
        adapter,
        start(1),
        start(2),
        "horizontal_distance",
        -points[1][0],
        "T030 fork length",
    )
    dims.record("FingerLength", '"FingerLength"')
    top = len(points) - 1
    await dimension_between(
        adapter,
        start(0),
        start(top),
        "horizontal_distance",
        points[top][0] - points[0][0],
        "plate length",
    )
    dims.record("PlateLength", '"PlateLength"')
    # Each fork's lower south corner: the chain runs four vertices a fork
    # (step, south corner, north corner, step), T030's south corner is P1.
    forks = {teeth: 1 + 4 * index for index, teeth in enumerate(GEARS)}
    if any(points[forks[t]][1] != -FORK_TIP_DEPTH_MM[t] for t in GEARS):
        raise AssertionError("plate profile fork corners out of order")
    for teeth in BONDED_TEETH:
        south = forks[teeth]
        await dimension_between(
            adapter,
            south_tip,
            start(south),
            "horizontal_distance",
            points[south][0] - points[1][0],
            f"{gear_tag(teeth)} fork start",
        )
        dims.record(f"Start{gear_tag(teeth)}", f'"Start{gear_tag(teeth)}"')
    for teeth in BONDED_TEETH[:-1]:
        south = forks[teeth]
        await dimension_between(
            adapter,
            start(south),
            start(south + 1),
            "horizontal_distance",
            points[south + 1][0] - points[south][0],
            f"{gear_tag(teeth)} fork length",
        )
        dims.record(f"FingerLength{gear_tag(teeth)}", '"FingerLength"')
    await dimension_between(
        adapter, "origin", start(0), "vertical_distance", points[0][1], "plate height"
    )
    dims.record("PlateHeight", '"PlateHeight"')
    for teeth in GEARS:
        fork = forks[teeth]
        await dimension_between(
            adapter,
            "origin",
            start(fork),
            "vertical_distance",
            -points[fork][1],
            f"{gear_tag(teeth)} fork tip",
        )
        dims.record(f"Fork{gear_tag(teeth)}", f'"Fork{gear_tag(teeth)}"')
    for teeth in BONDED_TEETH[:-1]:
        step = forks[teeth] + 2
        await dimension_between(
            adapter,
            "origin",
            start(step),
            "vertical_distance",
            -points[step][1],
            f"{gear_tag(teeth)} step",
        )
        dims.record(f"Step{gear_tag(teeth)}", f'"Step{gear_tag(teeth)}"')
    await ensure_fully_defined(adapter, "plate profile")
    check("exit_sketch plate profile", await adapter.exit_sketch())
    name_last_feature(adapter, PROFILE_SKETCH)
    return dims.apply(adapter, PROFILE_SKETCH)


def _slot_drives(teeth: int) -> tuple[list[str], list[str]]:
    """Names and drives of a slot rectangle's dims in define_rectilinear_chain's
    emission order: its length, its depth, then its top-left corner's x (and
    y below the seat, but for T030 whose slot bottom IS the seat)."""
    tag = gear_tag(teeth)
    if teeth == GEARS[-1]:
        span = f'"PlateLength" - "Start{tag}"'
        bottom_name, bottom = "SlotBottomT006", '"SlotBottomT006"'
    else:
        span = '"FingerLength"'
        bottom_name, bottom = f"SlotBottom{tag}", f'"Step{tag}"'
    corner_x = (
        '"FingerLength"' if teeth == GEARS[0] else f'"Start{tag}" - "FingerLength"'
    )
    if teeth == GEARS[0]:
        depth = f'"Fork{tag}" + "SlotRunout"'
        return (
            [f"SlotSpan{tag}", f"SlotDepth{tag}", f"SlotX{tag}"],
            [span, depth, corner_x],
        )
    depth = f'"Fork{tag}" + "SlotRunout" - {bottom}'
    return (
        [f"SlotSpan{tag}", f"SlotDepth{tag}", f"SlotX{tag}", bottom_name],
        [span, depth, corner_x, bottom],
    )


async def _slot(
    adapter: Any, teeth: int, volume: float
) -> tuple[list[tuple[str, str]], float]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    tag = gear_tag(teeth)
    x0, y0, x1, y1 = slot_rectangle_mm(teeth)
    # Top-left first: the chain's anchor is the slot bottom's south corner.
    points = [(x0, y1), (x1, y1), (x1, y0), (x0, y0)]
    check(f"create_sketch {tag} slot", await adapter.create_sketch("Front"))
    lines = await add_line_chain(adapter, points)
    dims = SketchDims()
    names, drives = _slot_drives(teeth)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        anchor=0,
        label=f"{tag} slot",
        dims=dims,
        names=names,
        drives=drives,
    )
    await ensure_fully_defined(adapter, f"{tag} slot sketch")
    check(f"exit_sketch {tag} slot", await adapter.exit_sketch())
    name_last_feature(adapter, slot_sketch(teeth))
    jobs = dims.apply(adapter, slot_sketch(teeth))
    check(
        f"cut {tag} slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SLOT_WIDTH_MM[teeth], both_directions=True)
        ),
    )
    name_last_feature(adapter, slot_feature(teeth))
    width = name_dimensions(adapter, slot_feature(teeth), [slot_width_name(teeth)])[0]
    jobs.append((width, f'"{slot_width_name(teeth)}"'))
    removed = SLOT_VOLUME_MM3[teeth]
    volume = await volume_check(
        adapter, f"{tag} slot", volume - removed, 0.01 * removed + 0.01
    )
    return jobs, volume


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units, and this is an inch document.
    for name, value in GLOBALS.items():
        await set_global(adapter, name, f"{value}mm")

    drive_jobs = await _plate_profile(adapter)
    check(
        "extrude plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, PLATE_FEATURE)
    drive_jobs.append(
        (name_dimensions(adapter, PLATE_FEATURE, ["PlateThick"])[0], '"PlateThick"')
    )
    volume = await volume_check(adapter, "plate", PLATE_VOLUME, 0.002 * PLATE_VOLUME)

    for teeth in GEARS:
        jobs, volume = await _slot(adapter, teeth, volume)
        drive_jobs += jobs
    _require_one_solid_body(adapter, label="phasing comb")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "driven phasing comb (equations neutral)",
        FINISHED_VOLUME,
        0.002 * PLATE_VOLUME,
    )
    _require_one_solid_body(adapter, label="driven phasing comb")
    # The slot widths, fork-tip depths and plate thickness carry their shop
    # rows; the gear named at each slot is their mate (sheet note 1).
    for (feature_name, dimension_name), deviations in MODEL_BANDS_MM.items():
        set_dimension_bilateral_tolerance(
            adapter,
            feature_name,
            dimension_name,
            *deviations,
            places=DRAWING_PRECISION[feature_name][dimension_name],
            display_unit=UNIT,
        )

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
