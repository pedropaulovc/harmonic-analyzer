r"""Reproduction script: transgear front bushing (MHA-PD-25; R9-68; 1 used).

The turned brass ring on the MHA-PD-23 pin between the MHA-PD-10 sleeve's nose
and the MHA-PD-VN-61 retaining ring (``pd_transgear_front_bushing_spec``).  Its
length is printed (+/-LENGTH_BAND, a term of the disc cluster stack).

Layout: Front-plane annulus at the origin (O.D., bore) extruded +Z by the
length, so the nose face is the Front Plane (z = 0) and the ring face is the
``RingFace`` plane at z = LENGTH; the 45 deg chamfer breaks the ring face's
O.D. edge.  ``Axis1`` is the bore axis (Top Plane ∩ Right Plane, the local Z
axis).  #290: the part saves in inch units (the row's ``drawing_unit``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_front_bushing.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
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
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from pd_transgear_front_bushing_spec import (
    BORE_DIA,
    BORE_DIA_BAND,
    CHAMFER_SUFFIX,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FRONT_CHAMFER,
    ISOMETRIC_VIEW_NOTE,
    LENGTH,
    LENGTH_BAND,
    OD,
    SURFACE_FINISHES,
    UNIT,
)

PART_NAME = "pd-transgear-front-bushing"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

OD_R = OD / 2.0
V_RING = math.pi * (OD_R**2 - (BORE_DIA / 2.0) ** 2) * LENGTH
# The 45 deg O.D. break: a triangle of leg c revolved at centroid R - c/3.
V_CHAMFER = math.pi * FRONT_CHAMFER**2 * (OD_R - FRONT_CHAMFER / 3.0)
V_TOTAL = V_RING - V_CHAMFER


def _chamfer_max_limit(adapter) -> None:
    """FrontChamferSize as the single limit ".02 MAX": the modelled size IS
    the max, and the part authors the MAX as the size's suffix (the drawing
    reads it back; a sheet-side SetText writes through to the part, #1942)."""
    display, dimension = _named_dimension(adapter, "FrontChamfer", "FrontChamferSize")
    label = "FrontChamferSize@FrontChamfer"
    value = float(dimension.SystemValue)
    if not math.isclose(value, FRONT_CHAMFER / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the limit {FRONT_CHAMFER}"
        )
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(2, CHAMFER_SUFFIX)  # swDimensionTextSuffix
    if str(display.GetText(2) or "") != CHAMFER_SUFFIX:
        raise RuntimeError(f"{label}: the MAX suffix did not persist")
    _telemetry.success(f"{label}: single limit {FRONT_CHAMFER:g}{CHAMFER_SUFFIX}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "RingOd", f"{OD}mm")
    await set_global(adapter, "RingLength", f"{LENGTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "FrontChamferSize", f"{FRONT_CHAMFER}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: O.D. + bore in ONE Front-plane sketch (both on-axis circles ->
    # only the two diameter dims emit), extruded once along +Z.
    ring = SketchDims()
    check("create_sketch ring", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        OD_R,
        "bushing OD",
        dims=ring,
        names=("OdCx", "OdCy", "RingOd"),
        drives=(None, None, '"RingOd"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIA / 2.0,
        "bushing bore",
        dims=ring,
        names=("BoreCx", "BoreCy", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bushing sketch")
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
    volume = await volume_check(adapter, "bushing", V_RING, 0.005 * V_RING)
    await bbox_extent_check(adapter, "bushing length", "z", LENGTH)
    await bbox_extent_check(adapter, "bushing O.D.", "x", OD)

    # The ring face's O.D. break: one native 45 deg chamfer on that edge.
    check(
        "chamfer ring-face O.D. edge",
        await adapter.add_chamfer(FRONT_CHAMFER, [[OD_R, 0.0, LENGTH]]),
    )
    name_last_feature(adapter, "FrontChamfer")
    chamfer_dim = name_dimensions(adapter, "FrontChamfer", ["FrontChamferSize"])
    drive_jobs.append((chamfer_dim[0], '"FrontChamferSize"'))
    await volume_check(
        adapter, "chamfered bushing", volume - V_CHAMFER, 0.02 * V_CHAMFER + 0.05
    )

    # The mate datums: the bore axis first, so it is Axis1; then the ring
    # face, driven by the length so it tracks a length edit.
    axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "bushing bore axis"
    )
    if axis != "Axis1":
        raise RuntimeError(f"bushing bore axis came back {axis!r}, not Axis1")
    check(
        "create_plane RingFace (Front Plane + RingLength)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=LENGTH
            )
        ),
    )
    name_last_feature(adapter, "RingFace")
    blank_reference_geometry(adapter, (("RingFace", "PLANE"),))
    ring_offset = name_dimensions(adapter, "RingFace", ["RingFaceOffset"])
    drive_jobs.append((ring_offset[0], '"RingLength"'))

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "driven bushing (equations neutral)",
        V_TOTAL,
        0.02 * V_CHAMFER + 0.05,
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The bore runs on the pin: its reamed band lives on the model dimension.
    # The length is printed to the disc cluster stack's band.  The chamfer
    # prints its MAX.
    set_dimension_bilateral_tolerance(
        adapter,
        "RingProfile",
        "BoreDia",
        *deviations(BORE_DIA_BAND),
        display_unit=UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter, "Ring", "RingLength", LENGTH_BAND, display_unit=UNIT
    )
    _chamfer_max_limit(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Both bearing faces, resolved by outward normal and offset: a ring
    # extruded -Z would have no +Z face at z = LENGTH and refuse here.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
