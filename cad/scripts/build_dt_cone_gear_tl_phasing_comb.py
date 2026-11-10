r"""Build the cone tip gears' phasing comb (MHA-DT-03-TL-02; shop tooling).

One flat steel plate (dt_cone_gear_tl_phasing_comb_spec): its stepped edge
carries one blade per gear, T030, T024, T018, T012 and T006, each dropping
into one tooth space of that gear while LOCTITE 638 grabs (MHA-DT-00 step 1).
Model frame (spec docstring): X north along the plate, Y radially outward, Z
through the thickness; the origin is the north end of the T030 blade on the
seat line.

Features:

* ``PlateProfile`` on the Front plane: the closed rectilinear outline (each
  blade's stock full thickness down to its tip), every length driven from
  the spec's globals; ``Plate`` extrudes it +Z by the thickness, so the
  Front plane is the plate's back face.
* ``BladeRootTnnn``: a plane at the step south of T018's, T012's and T006's
  blades (T030's and T024's leave the plate at the seat, the Top plane).
* ``BladeProfileTnnn`` / ``BladeReliefTnnn`` per blade: one outline round
  the blade, its thickness and its near face's ``BladeFace`` from the back
  face, cut from the blade's root down past its tip.

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
from _visibility import blank_reference_geometry
from dt_cone_gear_tl_phasing_comb_spec import (
    BLADE_TIP_DEPTH_MM,
    BONDED_TEETH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FINISHED_VOLUME,
    GEARS,
    GLOBALS,
    ISOMETRIC_VIEW_NOTE,
    MODEL_BANDS_MM,
    PLATE_FEATURE,
    PLATE_VOLUME,
    PROFILE_SKETCH,
    RELIEF_RUNOUT,
    RELIEF_VOLUME_MM3,
    THICKNESS,
    UNIT,
    blade_face_name,
    blade_root_depth_mm,
    blade_sketch,
    blade_tip_name,
    blade_width_name,
    gear_tag,
    profile_points_mm,
    relief_feature,
    relief_outline_mm,
    root_plane,
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
    vertical, the T030 blade's north end on the origin, the lengths from the
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
    south_tip = start(1)  # the south end's lower corner (T030 blade tip)
    await dimension_between(
        adapter,
        start(1),
        start(2),
        "horizontal_distance",
        -points[1][0],
        "T030 blade length",
    )
    dims.record("BladeLength", '"BladeLength"')
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
    # Each blade's lower south corner: the chain runs four vertices a blade
    # (step, south corner, north corner, step), T030's south corner is P1.
    blades = {teeth: 1 + 4 * index for index, teeth in enumerate(GEARS)}
    if any(points[blades[t]][1] != -BLADE_TIP_DEPTH_MM[t] for t in GEARS):
        raise AssertionError("plate profile blade corners out of order")
    for teeth in BONDED_TEETH:
        south = blades[teeth]
        await dimension_between(
            adapter,
            south_tip,
            start(south),
            "horizontal_distance",
            points[south][0] - points[1][0],
            f"{gear_tag(teeth)} blade start",
        )
        dims.record(f"Start{gear_tag(teeth)}", f'"Start{gear_tag(teeth)}"')
    for teeth in BONDED_TEETH[:-1]:
        south = blades[teeth]
        await dimension_between(
            adapter,
            start(south),
            start(south + 1),
            "horizontal_distance",
            points[south + 1][0] - points[south][0],
            f"{gear_tag(teeth)} blade length",
        )
        dims.record(f"BladeLength{gear_tag(teeth)}", '"BladeLength"')
    await dimension_between(
        adapter, "origin", start(0), "vertical_distance", points[0][1], "plate height"
    )
    dims.record("PlateHeight", '"PlateHeight"')
    for teeth in GEARS:
        corner = blades[teeth]
        await dimension_between(
            adapter,
            "origin",
            start(corner),
            "vertical_distance",
            -points[corner][1],
            f"{gear_tag(teeth)} blade tip",
        )
        dims.record(blade_tip_name(teeth), f'"{blade_tip_name(teeth)}"')
    for teeth in BONDED_TEETH[:-1]:
        step = blades[teeth] + 2
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


def _relief_drives(teeth: int) -> tuple[list[str | None], list[str | None]]:
    """Names and drives of a relief outline's dims in define_rectilinear_chain's
    emission order (``relief_outline_mm``): the blade's span past its south
    end, its width, its far face's span, the plate past the far face, the
    outline's span, its depth through the plate; then the anchor (the blade's
    near face at its north end): its x (none for T030's, on the origin) and
    BladeFace from the back face."""
    tag = gear_tag(teeth)
    blade_span = '"BladeLength" + "ReliefRunout"'
    names: list[str | None] = [
        f"BladeSpan{tag}",
        blade_width_name(teeth),
        f"BladeFarSpan{tag}",
        f"ReliefFar{tag}",
        f"ReliefSpan{tag}",
        f"ReliefWidth{tag}",
    ]
    drives: list[str | None] = [
        blade_span,
        f'"{blade_width_name(teeth)}"',
        blade_span,
        f'"PlateThick" + "ReliefRunout" - "{blade_face_name(teeth)}"'
        f' - "{blade_width_name(teeth)}"',
        '"BladeLength" + 2 * "ReliefRunout"',
        '"PlateThick" + 2 * "ReliefRunout"',
    ]
    if teeth != GEARS[0]:
        names.append(f"BladeEnd{tag}")
        drives.append(
            '"PlateLength" - "BladeLength"' if teeth == GEARS[-1] else f'"Start{tag}"'
        )
    names.append(blade_face_name(teeth))
    drives.append(f'"{blade_face_name(teeth)}"')
    return names, drives


async def _relief(
    adapter: Any, teeth: int, volume: float
) -> tuple[list[tuple[str, str]], float]:
    """The plate cut away beside ``teeth``'s blade, from the blade's root
    (the Top plane, the seat, for T030 and T024; a ``BladeRootTnnn`` plane at
    the step south of it otherwise) down past its tip: one closed outline
    round the blade (sketch u = model X, v = model -Z)."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    tag = gear_tag(teeth)
    jobs: list[tuple[str, str]] = []
    root = blade_root_depth_mm(teeth)
    plane = root_plane(teeth)
    root_drive = ""
    if plane is None:
        plane = "Top"
    else:
        south = GEARS[GEARS.index(teeth) - 1]
        root_drive = f' - "Step{gear_tag(south)}"'
        check(
            f"create_plane {plane}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Top Plane", offset=-root
                )
            ),
        )
        name_last_feature(adapter, plane)
        jobs.append(
            (
                name_dimensions(adapter, plane, [f"RootOffset{tag}"])[0],
                f'"Step{gear_tag(south)}"',
            )
        )
        blank_reference_geometry(adapter, ((plane, "PLANE"),))
    points = [(x, -z) for x, z in relief_outline_mm(teeth)]
    check(f"create_sketch {tag} relief", await adapter.create_sketch(plane))
    lines = await add_line_chain(adapter, points)
    dims = SketchDims()
    names, drives = _relief_drives(teeth)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        anchor=0,
        label=f"{tag} relief",
        dims=dims,
        names=names,
        drives=drives,
    )
    await ensure_fully_defined(adapter, f"{tag} relief sketch")
    check(f"exit_sketch {tag} relief", await adapter.exit_sketch())
    name_last_feature(adapter, blade_sketch(teeth))
    jobs += dims.apply(adapter, blade_sketch(teeth))
    # A cut from a plane parallel to Top runs -Y by default
    # (build_dt_cone_tip_block's dowel reverses it to run +Y).
    check(
        f"cut {tag} relief",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BLADE_TIP_DEPTH_MM[teeth] - root + RELIEF_RUNOUT)
        ),
    )
    name_last_feature(adapter, relief_feature(teeth))
    depth = name_dimensions(adapter, relief_feature(teeth), [f"ReliefDepth{tag}"])[0]
    jobs.append((depth, f'"{blade_tip_name(teeth)}"{root_drive} + "ReliefRunout"'))
    removed = RELIEF_VOLUME_MM3[teeth]
    volume = await volume_check(
        adapter, f"{tag} relief", volume - removed, 0.01 * removed + 0.01
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
    # +Z from the Front plane: the plate's back face is Z0, the blades' datum.
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, PLATE_FEATURE)
    drive_jobs.append(
        (name_dimensions(adapter, PLATE_FEATURE, ["PlateThick"])[0], '"PlateThick"')
    )
    volume = await volume_check(adapter, "plate", PLATE_VOLUME, 0.002 * PLATE_VOLUME)

    for teeth in GEARS:
        jobs, volume = await _relief(adapter, teeth, volume)
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
    # The blade thicknesses, locations and tip depths carry their shop rows;
    # the gear named at each blade is their mate (sheet note 1).
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
