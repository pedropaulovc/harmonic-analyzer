r"""Reproduction script: transgear pivot spacer (MHA-PD-020; ch. 23; 1 used).

The turned brass ring on the MHA-VN-041 pivot screw's shoulder between the
MHA-PD-007 support bar's back face and the MHA-PD-018 arm's front face
(``pd_transgear_pivot_spacer_spec``; contract §3.4).  Its length sets the pivot
head play, so it carries an explicit band; it is fitted as made, never faced
(R9-6).  Its reamed bore is a light press on the shoulder, under its own
one-sided band.

Layout: Front-plane annulus at the origin (O.D., bore) extruded +Z by the
length, so the bar-side (front) face is the Front Plane (z = 0) and the rear
face (on the arm) is the ``RearFace`` plane at z = LENGTH.  ``Axis1`` is the
bore axis (Top Plane ∩ Right Plane, the local Z axis); the paper-drive
assembly mates it to the pivot screw's axis, the Front Plane to the bar's
back face and ``RearFace`` to the arm's front face.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_pivot_spacer.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from pd_transgear_pivot_spacer_spec import (
    BORE_DIA,
    BORE_DIA_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    LENGTH,
    LENGTH_BAND,
    OD,
    SURFACE_FINISHES,
)

PART_NAME = "pd-transgear-pivot-spacer"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

V_RING = math.pi * ((OD / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2) * LENGTH


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "RingOd", f"{OD}mm")
    await set_global(adapter, "RingLength", f"{LENGTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: O.D. + bore in ONE Front-plane sketch (both on-axis circles ->
    # only the two diameter dims emit), extruded once along +Z.
    ring = SketchDims()
    check("create_sketch ring", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        OD / 2.0,
        "spacer OD",
        dims=ring,
        names=("OdCx", "OdCy", "RingOd"),
        drives=(None, None, '"RingOd"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIA / 2.0,
        "spacer bore",
        dims=ring,
        names=("BoreCx", "BoreCy", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "spacer sketch")
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
    await volume_check(adapter, "spacer", V_RING, 0.005 * V_RING)
    await bbox_extent_check(adapter, "spacer length", "z", LENGTH)
    await bbox_extent_check(adapter, "spacer O.D.", "x", OD)

    # The mate datums: the bore axis first, so it is Axis1; then the rear face
    # (on the arm), driven by the length so it tracks a length edit.
    axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "spacer bore axis"
    )
    if axis != "Axis1":
        raise RuntimeError(f"spacer bore axis came back {axis!r}, not Axis1")
    check(
        "create_plane RearFace (Front Plane + RingLength)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=LENGTH
            )
        ),
    )
    name_last_feature(adapter, "RearFace")
    blank_reference_geometry(adapter, (("RearFace", "PLANE"),))
    rear_offset = name_dimensions(adapter, "RearFace", ["RearFaceOffset"])
    drive_jobs.append((rear_offset[0], '"RingLength"'))

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven spacer (equations neutral)", V_RING, 0.005 * V_RING
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The pivot head play rides the length: its explicit band.  The bore is
    # a press on the shoulder: its reamed one-sided band.  The O.D. is
    # governed by its places alone (the title block's row).
    set_dimension_symmetric_tolerance(adapter, "Ring", "RingLength", LENGTH_BAND)
    set_dimension_bilateral_tolerance(
        adapter, "RingProfile", "BoreDia", *deviations(BORE_DIA_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Both end faces, resolved by outward normal and offset: a ring extruded
    # -Z would have no +Z face at z = LENGTH and refuse here.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
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
