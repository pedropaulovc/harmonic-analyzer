r"""Build the cone gears' dividing-head index plate (MHA-DT-03-TL-01; shop tooling).

A BS-0 dividing-head plate with the 57-, 51- and 24-hole circles that index
the 114T, 102T and 96T cone gears (``dt_cone_gear_tl_index_plate_spec``).
Its sizes come from the owner's measurements of the stock plate and the head
(#2157; his words are in the spec).

Layout (the spec's model frame): the plate is a Front-plane annulus (OD and
bore circles about the origin) extruded +Z by the thickness, so the back face
seats on Z0 and the front face is Z = thickness. Each index circle is one
Front-plane sketch, a construction bolt circle carrying the printed diameter
and one seed hole on +Y, cut through and circular-patterned about the named
plate axis. The mounting hole is a cut seed at 150 degrees, its counterbore
a revolved cut on a plane through the seed's row (the Top plane offset by
its Y), sketched as build_ch_rocker_arm_tl_oblique_riser's countersink is;
the hole and its counterbore are patterned three times. Their helpers are
copied here as private functions, as that riser copied the pivot plate's.

Run only through the supervised farm launcher:
``part:dt_cone_gear_tl_index_plate``.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from typing import Any

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_dimension_insert import add_diametric_linear_dimension
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
from _sketch import (
    SketchDims,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from dt_cone_gear_tl_index_plate_spec import (
    BORE_DEVIATIONS,
    BORE_DIA,
    CBORE_DEPTH,
    CBORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    GLOBALS,
    INDEX_HOLE_DIA,
    ISOMETRIC_VIEW_NOTE,
    MOUNT_COUNT,
    MOUNT_HOLE_DIA,
    MOUNT_PCD,
    MOUNT_SEED,
    MOUNT_X_FACTOR,
    MOUNT_Y_FACTOR,
    PLATE_DIA,
    RING_COUNTS,
    RING_PCDS,
    THICKNESS,
    UNIT,
)

PART_NAME = "dt-cone-gear-tl-index-plate"
MATERIAL = "6061 Alloy"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

AXIS_OVERRUN = 2.0
# Mid-plane cuts from the back face: past both faces whatever the thickness.
THROUGH_CUT_DEPTH = 2.0 * THICKNESS
MOUNT_ROW_PLANE = "MountRowPlane"


V_PLATE = math.pi / 4.0 * (PLATE_DIA**2 - BORE_DIA**2) * THICKNESS
V_INDEX_HOLE = math.pi * (INDEX_HOLE_DIA / 2.0) ** 2 * THICKNESS
V_MOUNT_HOLE = math.pi * (MOUNT_HOLE_DIA / 2.0) ** 2 * THICKNESS
V_CBORE = (
    math.pi * ((CBORE_DIA / 2.0) ** 2 - (MOUNT_HOLE_DIA / 2.0) ** 2) * CBORE_DEPTH
)
V_FINISHED = (
    V_PLATE - sum(RING_COUNTS) * V_INDEX_HOLE - MOUNT_COUNT * (V_MOUNT_HOLE + V_CBORE)
)


def _as_construction(adapter: Any, entity_id: str) -> None:
    """Make a registered sketch segment construction-only and prove the flag."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _require_one_solid_body(adapter: Any, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


def _sketch_mapper(
    adapter: Any, *, u_axis: int, v_axis: int, label: str
) -> Callable[[tuple[float, float, float]], tuple[float, float]]:
    """Map model points (mm) into the ACTIVE sketch, requiring model axis
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign).

    A plane's sketch axes are SolidWorks' choice; the profile points go
    through ``ModelToSketchTransform`` so only the orientation (which
    relations read horizontal/vertical) is assumed, and it is checked here
    (build_ch_rocker_arm_tl_oblique_riser's mapper). Coordinates are rounded
    to the nanometre so axis-parallel segments compare equal.
    """
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError(f"{label}: no active sketch")
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def raw(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    base = raw((0.0, 0.0, 0.0))
    for axis, want in ((u_axis, 0), (v_axis, 1)):
        unit = [0.0, 0.0, 0.0]
        unit[axis] = 1.0
        moved = raw(tuple(unit))
        delta = [m - b for m, b in zip(moved, base, strict=True)]
        if abs(abs(delta[want]) - 1.0) > 1e-6:
            raise RuntimeError(
                f"{label}: model axis {axis} maps to sketch {delta!r}, not along "
                f"sketch {'uv'[want]}"
            )

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        u, v, w = raw(model_mm)
        if abs(w) > 1e-4:
            raise RuntimeError(f"{label}: {model_mm} is {w:g} mm off the sketch")
        u, v = round(u, 9), round(v, 9)
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch


@_telemetry.traced("part.index_plate_counterbore")
def _counterbore(
    adapter: Any, *, plane: str, x: float, y: float, x_drive: str
) -> list[tuple[str, str]]:
    """Revolve-cut the flat-bottomed counterbore on ``plane`` (model Y =
    ``y``): mouth on the front face at model X = ``x``, floor below it.

    Profile: axis-top P0 -> mouth P1 -> floor corner P2 -> floor on the axis
    P3 -> P0, a centerline up past the face as the revolve axis, the mouth
    diameter and the depth each driven from its global.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    label = "counterbore"
    dims = SketchDims()
    check(f"create_sketch {label}", adapter.create_sketch(plane))
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=2, label=label)
    origin = to_sketch((0.0, y, 0.0))
    if origin != (0.0, 0.0):
        raise RuntimeError(f"{label}: sketch origin maps to {origin}")
    mouth_r = CBORE_DIA / 2.0
    profile = [
        to_sketch((x, y, THICKNESS)),
        to_sketch((x + mouth_r, y, THICKNESS)),
        to_sketch((x + mouth_r, y, THICKNESS - CBORE_DEPTH)),
        to_sketch((x, y, THICKNESS - CBORE_DEPTH)),
    ]
    set_sketch_direct_db(adapter, True)
    axis = check(
        f"{label} axis",
        adapter.add_centerline(
            *profile[0], *to_sketch((x, y, THICKNESS + AXIS_OVERRUN))
        ),
    )
    lines = add_line_chain(adapter, profile)
    set_sketch_direct_db(adapter, False)
    face, wall, floor, axis_side = lines
    for i in range(len(lines)):
        check(
            f"{label} junction {i}",
            adapter.add_sketch_constraint(
                f"{lines[i]}.end", f"{lines[(i + 1) % len(lines)]}.start", "coincident"
            ),
        )
    for first, second, relation in (
        (face, None, "horizontal"),
        (wall, None, "vertical"),
        (floor, None, "horizontal"),
        (axis_side, None, "vertical"),
        (axis, None, "vertical"),
        (f"{axis}.start", f"{face}.start", "coincident"),
    ):
        check(
            f"{label} {relation} {first}",
            adapter.add_sketch_constraint(first, second, relation),
        )
    dimension_between(
        adapter,
        "origin",
        f"{face}.start",
        "horizontal_distance",
        abs(profile[0][0]),
        f"{label} station",
    )
    dims.record("CboreX", x_drive)
    dimension_between(
        adapter,
        "origin",
        f"{face}.start",
        "vertical_distance",
        abs(profile[0][1]),
        f"{label} on the front face",
    )
    dims.record("CboreFace", '"PlateThick"')
    add_diametric_linear_dimension(
        adapter,
        axis,
        f"{wall}.start",
        to_sketch((x + mouth_r, y, THICKNESS + 3.0)),
        f"{label} mouth diameter",
    )
    dims.record("CboreMouthDia", '"CboreDia"')
    dimension_between(
        adapter,
        f"{wall}.start",
        f"{wall}.end",
        "vertical_distance",
        CBORE_DEPTH,
        f"{label} depth",
    )
    dims.record("CboreSeatDepth", '"CboreDepth"')
    check(
        f"{label} axis length",
        adapter.add_sketch_dimension(axis, None, "linear", AXIS_OVERRUN),
    )
    dims.record("CboreAxisLength")
    ensure_fully_defined(adapter, f"{label} profile")
    check(f"exit_sketch {label}", adapter.exit_sketch())
    name_last_feature(adapter, "CounterboreProfile")
    jobs = dims.apply(adapter, "CounterboreProfile")
    check(
        f"revolve-cut {label}",
        adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Counterbore")
    return jobs


def _seed_hole_sketch(
    adapter: Any,
    *,
    sketch: str,
    pcd: float,
    pcd_name: str,
    seed: tuple[float, float],
    hole_dia: float,
    hole_names: tuple[str, str, str],
    hole_drives: tuple[str, str, str],
    label: str,
) -> list[tuple[str, str]]:
    """One Front-plane sketch: the construction bolt circle (its diameter the
    printed one) and one seed hole on it, centre-driven from the same global
    (build_pd_transgear_disc_hub's screw holes)."""
    dims = SketchDims()
    check(f"create_sketch {label}", adapter.create_sketch("Front"))
    bolt_circle = define_circle(
        adapter,
        0.0,
        0.0,
        pcd / 2.0,
        f"{label} bolt circle",
        dims=dims,
        names=(None, None, pcd_name),
        drives=(None, None, f'"{pcd_name}"'),
    )
    _as_construction(adapter, bolt_circle)
    define_circle(
        adapter,
        *seed,
        hole_dia / 2.0,
        f"{label} seed hole",
        dims=dims,
        names=hole_names,
        drives=hole_drives,
    )
    ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    return dims.apply(adapter, sketch)


def _cut_through(adapter: Any, feature: str, label: str) -> None:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check(
        f"cut {label}",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, feature)


def _pattern(
    adapter: Any, *, axis: str, features: list[str], count: int, name: str
) -> None:
    from solidworks_mcp.adapters.base import CircularPatternParameters

    check(
        f"circular pattern {name} x{count}",
        adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_name=axis, features=features, count=count, geometry_pattern=True
            )
        ),
    )
    name_last_feature(adapter, name)


def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units, and this is an inch document.
    for name, value in GLOBALS.items():
        set_global(adapter, name, f"{value}mm")

    # --- Plate: OD and bore about the origin, extruded +Z ---------------------
    plate = SketchDims()
    check("create_sketch plate", adapter.create_sketch("Front"))
    for dia, name in ((PLATE_DIA, "PlateDia"), (BORE_DIA, "BoreDia")):
        define_circle(
            adapter,
            0.0,
            0.0,
            dia / 2.0,
            name,
            dims=plate,
            names=(None, None, name),
            drives=(None, None, f'"{name}"'),
        )
    ensure_fully_defined(adapter, "plate profile")
    check("exit_sketch plate", adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs = plate.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, "Plate")
    drive_jobs.append(
        (name_dimensions(adapter, "Plate", ["PlateThick"])[0], '"PlateThick"')
    )
    volume = volume_check(adapter, "plate", V_PLATE, 0.002 * V_PLATE)

    # Every pattern turns about the plate axis (model Z), selected by name.
    axis = name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "plate axis"
    )

    # --- Index circles: seed on +Y, cut through, patterned ---------------------
    for count in RING_COUNTS:
        pcd_name = f"Ring{count}Pcd"
        drive_jobs += _seed_hole_sketch(
            adapter,
            sketch=f"Ring{count}Profile",
            pcd=RING_PCDS[count],
            pcd_name=pcd_name,
            seed=(0.0, RING_PCDS[count] / 2.0),
            hole_dia=INDEX_HOLE_DIA,
            hole_names=(None, f"Ring{count}HoleY", f"Ring{count}HoleDia"),
            hole_drives=(None, f'"{pcd_name}" / 2', '"IndexHoleDia"'),
            label=f"{count}-hole circle",
        )
        _cut_through(adapter, f"Ring{count}Seed", f"{count}-hole circle seed")
        volume = volume_check(
            adapter,
            f"{count}-hole circle seed",
            volume - V_INDEX_HOLE,
            0.01 * V_INDEX_HOLE,
        )
        _pattern(
            adapter,
            axis=axis,
            features=[f"Ring{count}Seed"],
            count=count,
            name=f"Ring{count}Holes",
        )
        expected = volume - (count - 1) * V_INDEX_HOLE
        volume = volume_check(
            adapter, f"{count}-hole circle", expected, 0.01 * count * V_INDEX_HOLE
        )

    # --- Mounting holes: seed at 150 degrees with its counterbore, patterned ---
    drive_jobs += _seed_hole_sketch(
        adapter,
        sketch="MountHoleProfile",
        pcd=MOUNT_PCD,
        pcd_name="MountPcd",
        seed=MOUNT_SEED,
        hole_dia=MOUNT_HOLE_DIA,
        hole_names=("MountHoleX", "MountHoleY", "MountHoleDia"),
        hole_drives=(
            f'"MountPcd" * {MOUNT_X_FACTOR!r}',
            f'"MountPcd" * {MOUNT_Y_FACTOR!r}',
            '"MountHoleDia"',
        ),
        label="mounting hole",
    )
    _cut_through(adapter, "MountHole", "mounting hole seed")
    volume = volume_check(
        adapter, "mounting hole seed", volume - V_MOUNT_HOLE, 0.01 * V_MOUNT_HOLE
    )
    check(
        f"create_plane {MOUNT_ROW_PLANE}",
        adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=MOUNT_SEED[1]
            )
        ),
    )
    name_last_feature(adapter, MOUNT_ROW_PLANE)
    drive_jobs.append(
        (
            name_dimensions(adapter, MOUNT_ROW_PLANE, ["MountRowOffset"])[0],
            f'"MountPcd" * {MOUNT_Y_FACTOR!r}',
        )
    )
    blank_reference_geometry(adapter, (("MountRowPlane", "PLANE"),))
    drive_jobs += _counterbore(
        adapter,
        plane=MOUNT_ROW_PLANE,
        x=MOUNT_SEED[0],
        y=MOUNT_SEED[1],
        x_drive=f'"MountPcd" * {MOUNT_X_FACTOR!r}',
    )
    volume = volume_check(
        adapter, "counterbore seed", volume - V_CBORE, 0.03 * V_CBORE + 0.05
    )
    _pattern(
        adapter,
        axis=axis,
        features=["MountHole", "Counterbore"],
        count=MOUNT_COUNT,
        name="MountHoles",
    )
    volume = volume_check(
        adapter,
        "mounting holes",
        volume - (MOUNT_COUNT - 1) * (V_MOUNT_HOLE + V_CBORE),
        0.03 * MOUNT_COUNT * (V_MOUNT_HOLE + V_CBORE),
    )
    _require_one_solid_body(adapter, label="index plate")

    force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        drive_dimension(adapter, dimension_name, expression)
    force_rebuild(adapter)
    volume_check(
        adapter, "driven index plate (equations neutral)", V_FINISHED, 0.002 * V_PLATE
    )
    _require_one_solid_body(adapter, label="driven index plate")

    # The bore pilots on the head's hub: never under the stock plate's bore.
    set_dimension_bilateral_tolerance(
        adapter,
        "PlateProfile",
        "BoreDia",
        *BORE_DEVIATIONS,
        places=3,
        display_unit=UNIT,
    )
    # The drilled index holes take the title block's DRILLED HOLES band: the
    # model dimension carries none (owner ruling 2026-11-23, tool audit Q15).
    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
