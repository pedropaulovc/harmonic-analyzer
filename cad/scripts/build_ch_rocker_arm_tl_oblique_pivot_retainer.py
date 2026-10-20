"""Build MHA-CH-06-TL-31 as a real annular steel fitted retainer.

Installed nominal thickness comes from the UPPER-edge-loaded clevis stack.
The separate hidden supply-allowance sketch prints SUPPLY 7 MIN without
misrepresenting that supply blank as the installed washer geometry.
"""

from __future__ import annotations

import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _part_checks import report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import SketchDims, anchor_point_to_origin, blank_reference_sketches, dimension_between, ensure_fully_defined, set_sketch_direct_db
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
import ch_rocker_arm_tl_oblique_pivot_retainer_spec as spec

PART_NAME = "ch-rocker-arm-tl-oblique-pivot-retainer"
MATERIAL = "Plain Carbon Steel"
_SAVED_DRAWING_PROPERTIES = ("Number", "Material Specification", "Finish", "Quantity", "Isometric View Note", "Retainer Setup")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create retainer part", await adapter.create_part())
    for name, value in (
        ("WasherDia", spec.OUTER_DIA), ("WasherBore", spec.BORE_DIA),
        ("FinishedThickness", spec.THICKNESS), ("SupplyThickness", spec.SUPPLY_MIN_THICKNESS),
    ):
        await set_global(adapter, name, f"{value}mm")
    dims = SketchDims()
    check("washer profile", await adapter.create_sketch("Front"))
    for name, value in (("WasherDia", spec.OUTER_DIA), ("WasherBore", spec.BORE_DIA)):
        await define_circle(adapter, 0.0, 0.0, value / 2.0, name, dims=dims, names=(None, None, name), drives=(None, None, f'"{name}"'))
    await ensure_fully_defined(adapter, "retainer annulus")
    check("exit annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "WasherProfile")
    jobs = dims.apply(adapter, "WasherProfile")
    check("extrude retainer", await adapter.create_extrusion(ExtrusionParameters(depth=spec.THICKNESS)))
    name_last_feature(adapter, "Washer")
    jobs.append((name_dimensions(adapter, "Washer", ["FinishedThickness"])[0], '"FinishedThickness"'))

    # Right-plane coordinates (-Z,Y): one construction line carries the
    # supplied MIN allowance, independent of the installed thickness.
    dims = SketchDims()
    check("supply allowance sketch", await adapter.create_sketch("Right"))
    radius = spec.OUTER_DIA / 2.0
    set_sketch_direct_db(adapter, True)
    line = check("supply allowance line", await adapter.add_line(0.0, radius, -spec.SUPPLY_MIN_THICKNESS, radius))
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("supply allowance is not construction geometry")
    check("horizontal supply line", await adapter.add_sketch_constraint(line, None, "horizontal"))
    await anchor_point_to_origin(adapter, f"{line}.start", 0.0, radius, "supply line")
    dims.record("SupplyRadius", '"WasherDia"/2')
    await dimension_between(adapter, f"{line}.start", f"{line}.end", "horizontal_distance", spec.SUPPLY_MIN_THICKNESS, "supply minimum")
    dims.record("SupplyThickness", '"SupplyThickness"')
    await ensure_fully_defined(adapter, "supply reference")
    check("exit supply reference", await adapter.exit_sketch())
    name_last_feature(adapter, spec.SUPPLY_REFERENCE)
    jobs += dims.apply(adapter, spec.SUPPLY_REFERENCE)
    blank_reference_sketches(adapter, spec.REFERENCE_SKETCHES)
    check("retainer top plane", await adapter.create_plane(CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=spec.THICKNESS)))
    name_last_feature(adapter, spec.TOP_PLANE)
    jobs.append((name_dimensions(adapter, spec.TOP_PLANE, ["RetainerTopOffset"])[0], '"FinishedThickness"'))
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "retainer axis")
    name_last_feature(adapter, spec.AXIS_NAME)
    blank_reference_geometry(adapter, ((spec.TOP_PLANE, "PLANE"),))
    await force_rebuild(adapter)
    for name, expression in jobs:
        await drive_dimension(adapter, name, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "finished retainer, not supply blank", spec.VOLUME_MM3, 0.001 * spec.VOLUME_MM3)
    bodies = tuple(_early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"retainer: expected one solid, found {len(bodies)}")
    set_dimension_bilateral_tolerance(adapter, "WasherProfile", "WasherBore", *deviations(spec.DRILLED_BAND))
    display, dimension = _named_dimension(adapter, "Washer", "FinishedThickness")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 0  # swTolNONE: actual fitted gap controls this REF nominal
    display.SetText(1, "(")
    display.SetText(2, ")")
    if str(display.GetText(1)) != "(" or str(display.GetText(2)) != ")" or int(tolerance.Type) != 0:
        raise RuntimeError("finished-thickness reference notation did not persist")
    _, dimension = _named_dimension(adapter, spec.SUPPLY_REFERENCE, "SupplyThickness")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 5  # swTolMIN; model value IS the supply limit
    if not tolerance.SetValues(0.0, 0.0) or int(tolerance.Type) != 5:
        raise RuntimeError("SUPPLY MIN tolerance did not persist")
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    author_part_pmi(adapter, surface_finishes=spec.SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME, {"Isometric View Note": spec.ISOMETRIC_VIEW_NOTE, "Retainer Setup": spec.SETUP_NOTE})
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
