r"""Reproduction script: transgear rear bushing (MHA-PD-24; R9-68; 1 used).

The turned brass ring on the MHA-PD-23 pin between the MHA-PD-18 arm's front
face and the MHA-PD-10 sleeve's rear face (``pd_transgear_rear_bushing_spec``).
Its length prints at the title block: the MHA-PD-VN-68 shims under it set the
disc's end float (#2124).

Layout: Front-plane annulus at the origin (O.D., bore) extruded +Z by the
length, so the arm face is the Front Plane (z = 0) and the sleeve face is the
``SleeveFace`` plane at z = LENGTH.  ``Axis1`` is the bore axis (Top Plane ∩
Right Plane, the local Z axis).  #290: the part saves in inch units (the
row's ``drawing_unit``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_rear_bushing.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from pd_transgear_rear_bushing_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    LENGTH,
    OD,
    SURFACE_FINISHES,
)

PART_NAME = "pd-transgear-rear-bushing"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

V_RING = math.pi * ((OD / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2) * LENGTH


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    set_global(adapter, "RingOd", f"{OD}mm")
    set_global(adapter, "RingLength", f"{LENGTH}mm")
    set_global(adapter, "BoreDia", f"{BORE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: O.D. + bore in ONE Front-plane sketch (both on-axis circles ->
    # only the two diameter dims emit), extruded once along +Z.
    ring = SketchDims()
    check("create_sketch ring", adapter.create_sketch("Front"))
    define_circle(
        adapter,
        0.0,
        0.0,
        OD / 2.0,
        "bushing OD",
        dims=ring,
        names=("OdCx", "OdCy", "RingOd"),
        drives=(None, None, '"RingOd"'),
    )
    define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIA / 2.0,
        "bushing bore",
        dims=ring,
        names=("BoreCx", "BoreCy", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    ensure_fully_defined(adapter, "bushing sketch")
    check("exit_sketch ring", adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    drive_jobs += ring.apply(adapter, "RingProfile")
    check(
        "extrude ring",
        adapter.create_extrusion(ExtrusionParameters(depth=LENGTH)),
    )
    name_last_feature(adapter, "Ring")
    ring_depth = name_dimensions(adapter, "Ring", ["RingLength"])
    drive_jobs.append((ring_depth[0], '"RingLength"'))
    volume_check(adapter, "bushing", V_RING, 0.005 * V_RING)
    bbox_extent_check(adapter, "bushing length", "z", LENGTH)
    bbox_extent_check(adapter, "bushing O.D.", "x", OD)

    # The mate datums: the bore axis first, so it is Axis1; then the sleeve
    # face, driven by the length so it tracks a length edit.
    axis = name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "bushing bore axis"
    )
    if axis != "Axis1":
        raise RuntimeError(f"bushing bore axis came back {axis!r}, not Axis1")
    check(
        "create_plane SleeveFace (Front Plane + RingLength)",
        adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=LENGTH
            )
        ),
    )
    name_last_feature(adapter, "SleeveFace")
    blank_reference_geometry(adapter, (("SleeveFace", "PLANE"),))
    sleeve_offset = name_dimensions(adapter, "SleeveFace", ["SleeveFaceOffset"])
    drive_jobs.append((sleeve_offset[0], '"RingLength"'))

    # Deferred drive equations, then re-check neutrality.
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(
        adapter, "driven bushing (equations neutral)", V_RING, 0.005 * V_RING
    )

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    # The bore prints the reamer's size with no band (fit audit 2026-11-23):
    # the MHA-PD-23 pin is turned to it, and its callout carries the
    # acceptance.  The length prints at the title block; the shims take up
    # its band.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The sleeve's thrust face, resolved by outward normal and offset: a ring
    # extruded -Z would have no +Z face at z = LENGTH and refuse here.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
