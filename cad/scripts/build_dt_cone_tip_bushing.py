r"""Build MHA-DT-38, the cone tip bushing (owner decision C1 keyed, 2026-11-09).

A brass ring pressed on T006's pivot (MHA-DT-37) against T006's north face;
its north face bears on the MHA-DT-39 end screw.  Dimensions live in
``dt_cone_tip_bushing_spec`` (all of them ``cone_tip_cluster``'s).

Layout: one revolve about local +X (the MHA-DT-34 ferrule's pattern).  The
south face is the Right Plane (x = 0), the north face is ``NorthFace`` at
x = LENGTH, ``Axis1`` is the bore axis.  Both O.D. corners are broken by one
native 45 deg chamfer feature (#2697).  The bore's reamed band lives on its
model dimension; OD and length take the title block's .XXX.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_tip_bushing.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _visibility import blank_reference_geometry
from dt_cone_tip_bushing_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    END_CHAMFER,
    ISOMETRIC_VIEW_NOTE,
    LENGTH,
    OUTER_DIA,
)

PART_NAME = "dt-cone-tip-bushing"

MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)

OUTER_R = OUTER_DIA / 2.0
BORE_R = BORE_DIA / 2.0
V_RING = math.pi * (OUTER_R**2 - BORE_R**2) * LENGTH
# Each 45 deg O.D. break: a triangle of leg c revolved at centroid R - c/3.
V_CHAMFERS = 2.0 * math.pi * END_CHAMFER**2 * (OUTER_R - END_CHAMFER / 3.0)
V_BUSHING = V_RING - V_CHAMFERS
NORTH_FACE = "NorthFace"


def _profile(adapter) -> list[tuple[str, str]]:
    """Front-plane half section revolved about the X axis: south face -> OD ->
    north face -> bore.  Returns the deferred drive equations."""
    from solidworks_mcp.adapters.base import RevolveParameters

    profile = SketchDims()
    check("create_sketch bushing profile", adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "bushing axis centerline",
        adapter.add_centerline(0.0, 0.0, LENGTH, 0.0),
    )
    south_face, outer, north_face, bore = add_line_chain(
        adapter,
        [
            (0.0, BORE_R),
            (0.0, OUTER_R),
            (LENGTH, OUTER_R),
            (LENGTH, BORE_R),
        ],
    )
    set_sketch_direct_db(adapter, False)
    check(
        "axis horizontal", adapter.add_sketch_constraint(axis, None, "horizontal")
    )
    for label, entity, relation in (
        ("south face", south_face, "vertical"),
        ("OD", outer, "horizontal"),
        ("north face", north_face, "vertical"),
        ("bore", bore, "horizontal"),
    ):
        check(
            f"bushing {label} {relation}",
            adapter.add_sketch_constraint(entity, None, relation),
        )
    check(
        "axis starts at the origin",
        adapter.add_sketch_constraint(f"{axis}.start", "origin", "coincident"),
    )
    check(
        "south face on the origin plane",
        adapter.add_sketch_constraint(
            f"{south_face}.start", "origin", "vertical_points"
        ),
    )
    # Dimensions in creation order.
    check(
        "axis length", adapter.add_sketch_dimension(axis, None, "linear", LENGTH)
    )
    profile.record("AxisLength", '"Length"')
    check(
        "bushing length",
        adapter.add_sketch_dimension(outer, None, "linear", LENGTH),
    )
    profile.record("Length", '"Length"')
    add_diametric_linear_dimension(
        adapter, axis, outer, (LENGTH / 2.0, OUTER_R + 2.0), "OuterDia"
    )
    profile.record("OuterDia", '"OuterDia"')
    add_diametric_linear_dimension(
        adapter, axis, bore, (LENGTH / 2.0, BORE_R - 0.5), "BoreDia"
    )
    profile.record("BoreDia", '"BoreDia"')
    ensure_fully_defined(adapter, "bushing profile sketch")
    check("exit_sketch bushing profile", adapter.exit_sketch())
    name_last_feature(adapter, "BushingProfile")
    drive_jobs = profile.apply(adapter, "BushingProfile")
    check(
        "revolve bushing", adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "Bushing")
    return drive_jobs


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.  The mm
    # suffix is load-bearing: the equation manager reads bare numbers in
    # document units.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    for name, value in (
        ("OuterDia", OUTER_DIA),
        ("BoreDia", BORE_DIA),
        ("Length", LENGTH),
        ("EndChamferSize", END_CHAMFER),
    ):
        set_global(adapter, name, f"{value}mm")

    drive_jobs = _profile(adapter)
    volume_check(adapter, "brass ring", V_RING, 0.005 * V_RING)
    bbox_extent_check(adapter, "bushing length", "x", LENGTH)
    # Both O.D. corners in one native 45 deg chamfer (the
    # pd_transgear_front_bushing recipe; one pick on each face's O.D. edge).
    check(
        "chamfer both O.D. corners",
        adapter.add_chamfer(
            END_CHAMFER, [[0.0, OUTER_R, 0.0], [LENGTH, OUTER_R, 0.0]]
        ),
    )
    name_last_feature(adapter, "EndChamfer")
    chamfer_dim = name_dimensions(adapter, "EndChamfer", ["EndChamferSize"])
    drive_jobs.append((chamfer_dim[0], '"EndChamferSize"'))
    volume_check(
        adapter, "chamfered bushing", V_BUSHING, 0.02 * V_CHAMFERS + 0.05
    )
    bbox_extent_check(adapter, "chamfered bushing length", "x", LENGTH)

    # Mate datums: the bore axis first, so it is Axis1; then the north face,
    # driven by the length so it tracks a length edit.
    axis = name_bore_axis(
        adapter, "Front Plane", 0.0, "Top Plane", 0.0, "bushing bore axis"
    )
    if axis != "Axis1":
        raise RuntimeError(f"bushing bore axis came back {axis!r}, not Axis1")
    check(
        f"create_plane {NORTH_FACE} (Right Plane + Length)",
        adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=LENGTH
            )
        ),
    )
    name_last_feature(adapter, NORTH_FACE)
    blank_reference_geometry(adapter, ((NORTH_FACE, "PLANE"),))
    north_offset = name_dimensions(adapter, NORTH_FACE, ["NorthFaceOffset"])
    drive_jobs.append((north_offset[0], '"Length"'))

    force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        drive_dimension(adapter, dimension, expression)
    force_rebuild(adapter)
    volume_check(
        adapter,
        "driven brass bushing (equations neutral)",
        V_BUSHING,
        0.02 * V_CHAMFERS + 0.05,
    )

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    # The bore prints the .0625 reamer's size with no band: MHA-DT-37's pivot
    # is turned last to it (fit audit 2026-11-23, F10).  OD and length take
    # the title block's .XXX.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    return save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
