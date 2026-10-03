r"""Reproduction script: transgear knob thrust ring (MHA-PD-015; ch. 23; 1 used).

The loose brass ring on the knob shaft's journal between the 12T's rear face
and the arm plate's front hub (``transgear_knob_thrust_ring_spec``): the
forward stop of the knob's end float.

Layout: Top-plane annulus at the origin (O.D., bore) extruded +Y by the
length, so the front face (on the 12T) is the Top Plane (y = 0) and the rear
face (on the plate hub) is y = LENGTH.  ``Axis1`` is the ring axis (Front
Plane ∩ Right Plane); the paper-drive assembly mates it to the knob shaft's
axis and the Top Plane to the 12T's rear face.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_knob_thrust_ring.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    bbox_extent_check,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
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
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from pd_transgear_knob_thrust_ring_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ID,
    ID_BAND,
    LENGTH,
    LENGTH_TOL,
    OD,
    SURFACE_FINISHES,
)

PART_NAME = "pd-transgear-knob-thrust-ring"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)

V_RING = math.pi * ((OD / 2.0) ** 2 - (ID / 2.0) ** 2) * LENGTH


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "RingOd", f"{OD}mm")
    await set_global(adapter, "RingLength", f"{LENGTH}mm")
    await set_global(adapter, "BoreDia", f"{ID}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: O.D. + bore in ONE Top-plane sketch (both on-axis circles ->
    # only the two diameter dims emit), extruded once along the plane's +Y.
    ring = SketchDims()
    check("create_sketch ring", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        OD / 2.0,
        "ring OD",
        dims=ring,
        names=("OdCx", "OdCz", "RingOd"),
        drives=(None, None, '"RingOd"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        ID / 2.0,
        "journal bore",
        dims=ring,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "ring sketch")
    check("exit_sketch ring", await adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    drive_jobs += ring.apply(adapter, "RingProfile")
    check(
        "extrude ring",
        await adapter.create_extrusion(ExtrusionParameters(depth=LENGTH)),
    )
    name_last_feature(adapter, "Ring")
    ring_depth = name_dimensions(adapter, "Ring", ["RingLength"])
    drive_jobs.append((ring_depth[0], '"RingLength"'))
    await volume_check(adapter, "ring", V_RING, 0.005 * V_RING)
    await bbox_extent_check(adapter, "ring length", "y", LENGTH)
    await bbox_extent_check(adapter, "ring O.D.", "x", OD)

    # The mate axis: the first reference axis, so it is Axis1.
    axis = await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "ring axis"
    )
    if axis != "Axis1":
        raise RuntimeError(f"ring axis came back {axis!r}, not Axis1")

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven ring (equations neutral)", V_RING, 0.005 * V_RING
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "RingProfile", "BoreDia", *deviations(ID_BAND)
    )
    # The forward stop of the knob's end float: its explicit band.
    set_dimension_symmetric_tolerance(adapter, "Ring", "RingLength", LENGTH_TOL)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Both thrust faces, resolved by outward normal and offset: a ring
    # extruded -Y would have no +Y face at y = LENGTH and refuse here.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
