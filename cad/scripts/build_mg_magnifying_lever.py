r"""Build the approved full-body quarter-inch brass lever, without a shoulder.

Only the free end is hemispherical. The opposite flat end carries a native
1/4-20 UNC-2A cosmetic thread. Its incomplete root runout lies outside the
engaged receiver; no below-root relief groove or press land is introduced.
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _part_checks import report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, add_line_chain, anchor_point_to_origin, blank_reference_sketches, dimension_between, ensure_fully_defined, set_sketch_direct_db
from mg_lever_thread_joint import INCOMPLETE_THREAD_MAX, ROD_DIA, ROD_DIA_BAND, ROD_LENGTH, THREAD, THREAD_LENGTH, THREAD_ROOT_X, TIP_CHAMFER, TIP_CHAMFER_BAND
from mg_magnifying_lever_geom import KNIFE_LOCAL_X, KNIFE_LOCAL_Y
from mg_magnifying_lever_spec import DRAWING_DIMENSIONS, DRAWING_PRECISION, ISO_VIEW_NOTE, SINGLE_LIMITS, SURFACE_FINISHES, THREAD_CALLOUT

PART_NAME = "mg-magnifying-lever"
MATERIAL = "Brass"
R = ROD_DIA / 2.0
V_PROFILE = math.pi * R**2 * (ROD_LENGTH - R) + 2.0 / 3.0 * math.pi * R**3 - math.pi * TIP_CHAMFER**2 * (R - TIP_CHAMFER / 3.0)


def _single_limits(adapter) -> None:
    for (feature, name), (limit, kind) in SINGLE_LIMITS.items():
        _, dimension = _named_dimension(adapter, feature, name)
        if not math.isclose(float(dimension.SystemValue) * 1000.0, limit, abs_tol=1e-6):
            raise RuntimeError(f"{name}@{feature}: single-limit nominal changed")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = kind
        if not tolerance.SetValues(0.0, 0.0) or int(tolerance.Type) != kind:
            raise RuntimeError(f"{name}@{feature}: single-limit tolerance did not persist")


async def _thread_extent(adapter):
    """Independent manufacturing witnesses, with creation-time inference off."""
    dims = SketchDims()
    check("thread extent requirement sketch", await adapter.create_sketch("Front"))
    for start, height, name, expression in ((THREAD_ROOT_X, R, "ThreadLength", '"ThreadLength"'), (ROD_LENGTH - INCOMPLETE_THREAD_MAX, -R, "IncompleteLength", None)):
        (line,) = await add_line_chain(adapter, [(start, height), (ROD_LENGTH, height)], close=False)
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError("thread witness is not construction geometry")
        await anchor_point_to_origin(adapter, f"{line}.end", ROD_LENGTH, height, "flat thread tip")
        dims.record(f"{name}Tip", '"RodLength"')
        dims.record(f"{name}Height")
        check("thread witness horizontal", await adapter.add_sketch_constraint(line, None, "horizontal"))
        await dimension_between(adapter, f"{line}.start", f"{line}.end", "horizontal_distance", ROD_LENGTH - start, name)
        dims.record(name, expression)
    await ensure_fully_defined(adapter, "thread extent requirements")
    check("exit thread extent sketch", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadExtent")
    return dims.apply(adapter, "ThreadExtent")


def _assert_thread_extent_driving(adapter) -> None:
    # Check BEFORE equations: equation-owned dimensions legitimately report a
    # different DrivenState afterward. SDK dimension creation can return success
    # even when native SetSystemValue3 refuses a redundant/reference dimension.
    for name, nominal in (
        ("ThreadLengthTip", ROD_LENGTH), ("ThreadLengthHeight", R),
        ("ThreadLength", THREAD_LENGTH), ("IncompleteLengthTip", ROD_LENGTH),
        ("IncompleteLengthHeight", R), ("IncompleteLength", INCOMPLETE_THREAD_MAX),
    ):
        _, dimension = _named_dimension(adapter, "ThreadExtent", name)
        if int(dimension.DrivenState) != 2:
            raise RuntimeError(f"{name}@ThreadExtent must be driving before equations")
        actual = float(dimension.SystemValue) * 1000.0
        if not math.isclose(actual, nominal, abs_tol=1e-6):
            raise RuntimeError(f"{name}@ThreadExtent: requested {nominal:g} mm, native value is {actual:g} mm")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import AddThreadParameters, RevolveParameters

    check("create part", await adapter.create_part())
    for name, value in (("RodDia", ROD_DIA), ("RodLength", ROD_LENGTH), ("ThreadLength", THREAD_LENGTH), ("TipChamfer", TIP_CHAMFER)):
        await set_global(adapter, name, f"{value}mm")
    jobs = []
    dims = SketchDims()
    check("rod profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check("rod axis", await adapter.add_centerline(0.0, 0.0, ROD_LENGTH, 0.0))
    lines = await add_line_chain(adapter, [(ROD_LENGTH, 0.0), (ROD_LENGTH, R - TIP_CHAMFER), (ROD_LENGTH - TIP_CHAMFER, R), (R, R)], close=False)
    dome = check("free end dome", await adapter.add_arc(R, 0.0, R, R, 0.0, 0.0))
    closure = check("profile closes on axis", await adapter.add_line(0.0, 0.0, ROD_LENGTH, 0.0))
    set_sketch_direct_db(adapter, False)
    for first, second in ((f"{lines[2]}.end", f"{dome}.start"), (f"{dome}.end", f"{closure}.start"), (f"{closure}.end", f"{lines[0]}.start"), (f"{axis}.start", f"{closure}.start"), (f"{axis}.end", f"{closure}.end")):
        check("rod profile coincidence", await adapter.add_sketch_constraint(first, second, "coincident"))
    check("free tip origin", await adapter.add_sketch_constraint(f"{closure}.start", "origin", "coincident"))
    check("dome centre on rod axis", await adapter.add_sketch_constraint(f"{dome}.center", "origin", "horizontal_points"))
    check("tangent free dome", await adapter.add_sketch_constraint(lines[2], dome, "tangent"))
    for line, relation in ((axis, "horizontal"), (closure, "horizontal"), (lines[0], "vertical"), (lines[2], "horizontal")):
        check("rod profile alignment", await adapter.add_sketch_constraint(line, None, relation))
    await dimension_between(adapter, f"{closure}.start", f"{closure}.end", "horizontal_distance", ROD_LENGTH, "overall lever length")
    dims.record("OverallLength", '"RodLength"')
    for kind, name in (("horizontal_distance", "TipChamfer"), ("vertical_distance", "TipChamferRise")):
        await dimension_between(adapter, f"{lines[1]}.start", f"{lines[1]}.end", kind, TIP_CHAMFER, "45 degree tip chamfer")
        dims.record(name, '"TipChamfer"')
    await add_diametric_linear_dimension(adapter, axis, lines[2], (70.0, R + 4.0), "RodDia")
    dims.record("RodDia", '"RodDia"')
    await ensure_fully_defined(adapter, "full-body threaded lever profile")
    check("exit rod profile", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    jobs.extend(dims.apply(adapter, "RodProfile"))
    check("revolve full-body lever", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Rod")

    # Native witnesses carry thread length/runout requirements, not body edges.
    jobs.extend(await _thread_extent(adapter))
    await force_rebuild(adapter)
    _assert_thread_extent_driving(adapter)
    for dimension, expression in jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    adapter._zoom_to_fit(adapter.currentModel)
    check("native quarter-inch external thread", await adapter.add_thread(AddThreadParameters(edge_point=[ROD_LENGTH - TIP_CHAMFER, R, 0.0], standard="ansi_inch", size=THREAD, end_type="blind", depth=THREAD_LENGTH - TIP_CHAMFER, note=THREAD_CALLOUT)))
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "rod axis")
    await name_bore_axis(adapter, "Right Plane", KNIFE_LOCAL_X, "Top Plane", KNIFE_LOCAL_Y, "knife axis")
    set_dimension_bilateral_tolerance(adapter, "RodProfile", "RodDia", *deviations(ROD_DIA_BAND))
    set_dimension_bilateral_tolerance(adapter, "RodProfile", "TipChamfer", *deviations(TIP_CHAMFER_BAND))
    _single_limits(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    blank_reference_sketches(adapter, ("ThreadExtent",))
    await apply_material(adapter, MATERIAL)
    apply_drawing_properties(adapter, PART_NAME, {"Iso View Note": ISO_VIEW_NOTE})
    await report_mass_properties(adapter)
    await force_rebuild(adapter)
    await volume_check(adapter, "full-body lever with one dome and a flat threaded tip", V_PROFILE, 0.005 * V_PROFILE)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
