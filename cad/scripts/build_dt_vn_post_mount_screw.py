r"""Modified purchased cone pivot post mount screw: MSC 40923906, cut to length.

Head up, under-head junction at the origin: the head seats on the MHA-DT-05
counterbore floor and the shank runs down through the post into the
MHA-DT-20 tap.  Modelled at the cut-to-fit nominal (U37c;
dt_vn_post_mount_screw_spec.CUT_LENGTH_MM: flush less half the allowance).

The cut is the one modification, so the part owns its length: a hidden
construction sketch whose single driving dimension is the cut length
(under-head face to cut end), at its model-owned places, marked for the
drawing.  It carries no band: no one length suits every in-band post and
plate (``dt_vn_post_mount_screw_spec``'s U27 check), so the sheet prints it as a
reference and each screw is cut to its own hole at assembly.  The build
proves the dimension and the solid's cut end agree.

The cut end carries no modelled break: the title block's edge break governs
it, and the retained engagement stack spends that general maximum.

The solid carries the modification too (Main's ruling on the cut end):
cutting to fit removes the factory-chamfered tip.  The shared catalog-only
recipe builds the stock screw at its SUPPLIED 4 in length; this builder
then trims it at CutLength (``CutToLength``), the cutter driven by an
equation from that model dimension.  An analytic volume check proves the cut.
"""

from __future__ import annotations

from functools import wraps
import math
import sys

import _telemetry
from _check import check
from _com import _early_bound
from solidworks_mcp.adapters.com_variant import null_variant
from solidworks_mcp.adapters.solidworks.sketch import _resolve_entity_ref
from _dimensions import drive_dimension, name_dimensions
from _feature_tree import _feature_by_name, name_last_feature
from _rebuild import (
    _hard_fault_names,
    active_configuration_name,
    assert_saved_configurations_regenerate,
    force_rebuild,
)
from _session import run_build
from _sketch import (
    anchor_point_to_origin,
    SketchDims,
    blank_reference_sketches,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_precision import apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _part_save import save_part_and_images
from _simplified_part import (
    assert_simplified_configurations,
    derive_simplified_on_saved_part,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from diagnostics.diag_build_40923906 import build_40923906
from _msc_40923906 import FILLISTER_SIZE
from diagnostics.diag_mcmaster_lib import no_sketch_inference
from dt_vn_post_mount_screw_spec import (
    CUT_LENGTH_DIMENSION,
    CUT_LENGTH_MM,
    CUT_LENGTH_SKETCH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FACTORY_THREAD_START_MM,
    MAJOR_RADIUS_MM,
    MANUFACTURING_NOTES,
    REFERENCE_SKETCHES,
    SKU,
    STOCK_LENGTH_MM,
    SUPPLIER_PRECISION,
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_PROFILE_MM,
    SUPPLIER_PROFILE_SECTIONS,
    SUPPLIER_SOURCE,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_DIMENSIONS,
    SUPPLIER_STOCK_FEATURE,
    SUPPLIER_STOCK_TITLE,
    TRIM_REMOVED_MM3,
)

PART_NAME = "dt-vn-post-mount-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# The shared row is the supplied screw; the part's shank is its cut length.
SHANK_DIA, _STOCK_LEN, HEAD_H, HEAD_DIA, THREAD_PITCH = FILLISTER_SIZE
if _STOCK_LEN != STOCK_LENGTH_MM:
    raise ValueError("the stock recipe length is not the supplied length")
SHANK_LEN = CUT_LENGTH_MM

PLAIN_SHANK_PROFILE = "PlainShankProfile"
PLAIN_SHANK_FEATURE = "PlainShank"
TRIM_PROFILE = "CutToLengthProfile"
TRIM_FEATURE = "CutToLength"
# Equation drive: the cutter follows the model dimension that owns it.
CUT_LENGTH_REF = f'"{CUT_LENGTH_DIMENSION}@{CUT_LENGTH_SKETCH}"'
TRIM_DRIVES = {"TrimAt": CUT_LENGTH_REF}
# The trim cutter reaches one diameter past the supplied tip.
TRIM_OVERRUN_MM = SHANK_DIA
# The sweep route under-removes ~0.4% of the groove
# (diag_mcmaster_lib.thread_sweep_cut_modern): inside 0.5% of the trim.
TRIM_VOLUME_TOL_MM3 = 0.005 * TRIM_REMOVED_MM3
# Actual CURRENT catalogue-family solid features, in dependency order.
# Do not substitute the paused corrected author's FactoryThreadSplit/BodyUnion:
# this port preserves HeadSplit, full-shank ThreadGroove and both runout bosses;
# PlainShank then restores the unthreaded shank above the factory thread.
SUPPLIER_SOLID_FEATURES = (
    "Body", "DriverSlot", "HeadSplit", "ThreadGroove", "RunoutFill",
    "RunoutTaper", "JunctionFillet", PLAIN_SHANK_FEATURE, TRIM_FEATURE,
)
# The groove PlainShank fills lies between the major and the thread's root
# radius (UNC basic: 5/8 of the fundamental triangle below the major).
_THREAD_ROOT_RADIUS_MM = MAJOR_RADIUS_MM - 0.75 * THREAD_PITCH * math.sqrt(3.0) / 2.0
PLAIN_SHANK_FILL_MAX_MM3 = (
    math.pi * (MAJOR_RADIUS_MM**2 - _THREAD_ROOT_RADIUS_MM**2) * FACTORY_THREAD_START_MM
)


def _as_construction(adapter, entity_id: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _cut_end_y_mm(adapter) -> float:
    """The solid's lowest point along the screw axis (IBody2.GetExtremePoint,
    exact -- see _part_checks.bbox_extent_check), in mm."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = part.GetBodies2(0, False) or ()  # swSolidBody
    if not bodies:
        raise RuntimeError("post-mount-screw has no solid body to measure")
    lowest = float("inf")
    for body in bodies:
        found = _early_bound(body, "IBody2").GetExtremePoint(0.0, -1.0, 0.0)
        if not found or len(found) < 4 or not found[0]:
            raise RuntimeError("post-mount-screw: GetExtremePoint failed")
        lowest = min(lowest, float(found[2]) * 1000.0)
    return lowest


async def _author_reference_dimension(
    adapter,
    *,
    sketch: str,
    dimension: str,
    start: tuple[float, float],
    end: tuple[float, float],
    orientation: str,
    value_mm: float,
) -> None:
    """One construction line on the Front plane carrying ONE driving,
    model-owned drawing dimension.  The line is dimensioned first, so
    name_dimensions' creation order finds it before the origin-anchor
    dimensions."""
    check(f"create_sketch {sketch}", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    line = check(f"{sketch} line", await adapter.add_line(*start, *end))
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, line)
    check(
        f"{sketch} {orientation}",
        await adapter.add_sketch_constraint(line, None, orientation),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        f"{orientation}_distance",
        value_mm,
        sketch,
    )
    await anchor_point_to_origin(adapter, f"{line}.start", *start, sketch)
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    name_dimensions(adapter, sketch, [dimension])


async def _author_cut_controls(adapter) -> None:
    """The cut length runs along the shank's left silhouette, under-head face
    to cut end: the print dimensions between faces the shop measures, not
    along the axis through the part."""
    x = -SHANK_DIA / 2.0
    await _author_reference_dimension(
        adapter,
        sketch=CUT_LENGTH_SKETCH,
        dimension=CUT_LENGTH_DIMENSION,
        start=(x, 0.0),
        end=(x, -CUT_LENGTH_MM),
        orientation="vertical",
        value_mm=CUT_LENGTH_MM,
    )


async def _volume_mm3(adapter) -> float:
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"get_mass_properties failed: {mass.error}")
    return float(mass.data.volume)


def _check_removed(label: str, before: float, after: float, expected: float) -> None:
    removed = before - after
    if abs(removed - expected) > TRIM_VOLUME_TOL_MM3:
        raise RuntimeError(
            f"{label}: removed {removed:.4f} mm^3, analytic {expected:.4f} "
            f"(+/- {TRIM_VOLUME_TOL_MM3:.4f})"
        )
    _telemetry.success(
        f"{label}: removed {removed:.4f} mm^3 (analytic {expected:.4f})"
    )


async def _trim_to_cut_length(adapter) -> None:
    """Remove the factory tip: everything below the cut plane."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    half = 2.0 * MAJOR_RADIUS_MM
    top, bottom = -CUT_LENGTH_MM, -(STOCK_LENGTH_MM + TRIM_OVERRUN_MM)
    dims = SketchDims()
    with no_sketch_inference(adapter):
        check(f"create_sketch {TRIM_PROFILE}", await adapter.create_sketch("Front"))
        lines = await add_line_chain(
            adapter, [(-half, top), (half, top), (half, bottom), (-half, bottom)]
        )
        for line, direction in zip(
            lines, ("horizontal", "vertical", "horizontal", "vertical"), strict=True
        ):
            check(
                f"{TRIM_PROFILE} {direction}",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        await anchor_point_to_origin(
            adapter, f"{lines[0]}.start", -half, top, TRIM_PROFILE
        )
        dims.record("CutterLeft")
        dims.record("TrimAt", TRIM_DRIVES["TrimAt"])
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            f"{lines[0]}.end",
            "horizontal_distance",
            2.0 * half,
            f"{TRIM_PROFILE} width",
        )
        dims.record("CutterWidth")
        await dimension_between(
            adapter,
            f"{lines[1]}.start",
            f"{lines[1]}.end",
            "vertical_distance",
            top - bottom,
            f"{TRIM_PROFILE} depth",
        )
        dims.record("CutterDepth")
        await ensure_fully_defined(adapter, f"{TRIM_PROFILE} sketch")
        check(f"exit_sketch {TRIM_PROFILE}", await adapter.exit_sketch())
    name_last_feature(adapter, TRIM_PROFILE)
    drives = dims.apply(adapter, TRIM_PROFILE)
    check(
        TRIM_FEATURE,
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * SHANK_DIA, both_directions=True)
        ),
    )
    name_last_feature(adapter, TRIM_FEATURE)
    for dimension, expression in drives:
        await drive_dimension(adapter, dimension, expression)


async def _modify_stock(adapter) -> None:
    """Trim the supplied screw at CutLength."""
    stock = await _volume_mm3(adapter)
    await _trim_to_cut_length(adapter)
    await force_rebuild(adapter)
    trimmed = await _volume_mm3(adapter)
    _check_removed("trim to cut length", stock, trimmed, TRIM_REMOVED_MM3)


def _manufacturing_controls(adapter) -> None:
    """Places and drawing marks; the sheet's note."""
    cut_end = _cut_end_y_mm(adapter)
    if abs(cut_end + CUT_LENGTH_MM) > 1e-4:
        raise RuntimeError(
            f"solid cut end at y={cut_end:.4f} is not the dimensioned "
            f"{CUT_LENGTH_MM} below the under-head face"
        )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # The cut length stays unbanded (reference): no fixed length suits every
    # post and plate.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The stock helper's reference pass hides the sketches with the recipe's.
    apply_drawing_properties(
        adapter, PART_NAME, {
            "Manufacturing Notes": MANUFACTURING_NOTES,
            "Supplier Reference Source": SUPPLIER_SOURCE,
            "Supplier Reference Title": SUPPLIER_STOCK_TITLE,
        }
    )


@_telemetry.traced("part.post_mount_screw.plain_shank")
async def _restore_plain_shank(adapter) -> None:
    """The shared recipe threads the whole shank, but MSC threads only the
    last 1.500 in: a major-diameter boss from the under-head face (the Top
    plane) down to the factory thread start fills the groove above it."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    before = await _volume_mm3(adapter)
    dims = SketchDims()
    check(f"create_sketch {PLAIN_SHANK_PROFILE}", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, MAJOR_RADIUS_MM, PLAIN_SHANK_PROFILE, dims=dims
    )
    await ensure_fully_defined(adapter, f"{PLAIN_SHANK_PROFILE} sketch")
    check(f"exit_sketch {PLAIN_SHANK_PROFILE}", await adapter.exit_sketch())
    name_last_feature(adapter, PLAIN_SHANK_PROFILE)
    dims.apply(adapter, PLAIN_SHANK_PROFILE)
    check(
        PLAIN_SHANK_FEATURE,
        await adapter.create_extrusion(
            ExtrusionParameters(depth=FACTORY_THREAD_START_MM, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, PLAIN_SHANK_FEATURE)
    await force_rebuild(adapter)
    filled = await _volume_mm3(adapter) - before
    # Only groove metal comes back: a boss run up through the head instead
    # would add a whole Ø.250 stub, over twice this bound.
    if not 0.0 < filled < PLAIN_SHANK_FILL_MAX_MM3:
        raise RuntimeError(
            f"{PLAIN_SHANK_FEATURE} added {filled:.3f} mm^3; the thread groove "
            f"above the factory thread holds under {PLAIN_SHANK_FILL_MAX_MM3:.3f}"
        )
    _telemetry.success(f"{PLAIN_SHANK_FEATURE}: filled {filled:.3f} mm^3 of groove")


@wraps(build_40923906)
async def _cut_to_length(adapter, truth=None, **parameters):
    # The shared recipe builds the supplied screw; the trim cuts it to fit.
    receipt = await build_40923906(adapter, truth, **parameters)
    await _restore_plain_shank(adapter)
    await _author_cut_controls(adapter)
    await _modify_stock(adapter)
    _manufacturing_controls(adapter)
    return receipt


def _supplier_profile_dimension(adapter, row, lines, dims) -> None:
    """Measure the source diagram's own vertices; never override numeric text."""
    model = adapter.currentModel
    model.ClearSelection2(True)
    for index in row.vertices:
        point = _resolve_entity_ref(adapter, f"{lines[index]}.start")
        if point.Select4(True, None) is not True:
            raise RuntimeError(f"{row.name}: cannot select source vertex {index}")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    display, status = extension.AddSpecificDimension(0.0, 0.015, 0.0, row.native_type, 0)
    model.ClearSelection2(True)
    if display is None or status != 0:
        raise RuntimeError(f"{row.name}: cannot dimension source profile ({status})")
    display = _early_bound(display, "IDisplayDimension")
    native = _early_bound(display.GetDimension2(0), "IDimension")
    native.DrivenState = 1
    if (
        int(native.DrivenState) != 1
        or int(display.Type2) != row.native_type
        or not math.isclose(
            abs(float(native.SystemValue)) * 1000.0,
            row.expected_mm, rel_tol=0.0, abs_tol=1e-5,
        )
    ):
        raise RuntimeError(f"{row.name}: source diagram extent or nominal major changed")
    # Source bands belong to the model dimension, never drawing-only text.
    tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
    band = row.deviations_mm
    tolerance.Type = 0 if band is None else 3  # swTolNONE / swTolLIMIT
    if band is not None and not tolerance.SetValues(band[0] / 1000.0, band[1] / 1000.0):
        raise RuntimeError(f"{row.name}: cannot retain supplier limits")
    status = display.SetPrecision3(SUPPLIER_PRECISION, -1, SUPPLIER_PRECISION, -1)
    if (
        status != 0
        or int(display.GetPrimaryPrecision2()) != SUPPLIER_PRECISION
        or int(display.GetPrimaryTolPrecision2()) != SUPPLIER_PRECISION
        or int(tolerance.Type) != (0 if band is None else 3)
        or (band is not None and (
            not math.isclose(float(tolerance.GetMinValue()), band[0] / 1000.0, abs_tol=1e-12)
            or not math.isclose(float(tolerance.GetMaxValue()), band[1] / 1000.0, abs_tol=1e-12)
        ))
    ):
        raise RuntimeError(f"{row.name}: supplier model limits/precision did not persist")
    dims.record(row.name)


async def _supplier_stock_envelope(adapter) -> None:
    """Construction-only source envelope, NOT a replacement for the current solid."""
    before_volume = await _volume_mm3(adapter)
    check("create supplier max-limit profile", await adapter.create_sketch("Front"))
    points = list(SUPPLIER_PROFILE_MM)
    lines = await add_line_chain(adapter, points)
    for entity in lines:
        _as_construction(adapter, entity)
    dims = SketchDims()
    await define_rectilinear_chain(
        adapter, lines, points, label=SUPPLIER_STOCK_FEATURE, dims=dims,
    )
    # Genuine skirt/crown and factory-thread boundaries join the same profile.
    for first, last in SUPPLIER_PROFILE_SECTIONS:
        section = (await add_line_chain(adapter, [points[first], points[last]], close=False))[0]
        _as_construction(adapter, section)
    for row in SUPPLIER_REFERENCE_DIMENSIONS:
        _supplier_profile_dimension(adapter, row, lines, dims)
    await ensure_fully_defined(adapter, SUPPLIER_STOCK_FEATURE)
    check("close supplier max-limit profile", await adapter.exit_sketch())
    name_last_feature(adapter, SUPPLIER_STOCK_FEATURE)
    dims.apply(adapter, SUPPLIER_STOCK_FEATURE)
    mark_dimensions_for_drawing(
        adapter, SUPPLIER_STOCK_FEATURE, SUPPLIER_STOCK_DIMENSIONS[SUPPLIER_STOCK_FEATURE]
    )
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    await _add_supplier_stock_configuration(adapter, before_volume)


async def _add_supplier_stock_configuration(adapter, before_volume) -> None:
    """Suppress the actual old recipe only in a zero-body source-diagram child."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    native_part = _early_bound(model, "IPartDoc")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    original = active_configuration_name(adapter, model)
    before = {
        name: tuple(_feature_by_name(adapter, name).IsSuppressed2(1, null_variant()) or ())
        for name in SUPPLIER_SOLID_FEATURES
    }
    if any(state != (False,) for state in before.values()):
        raise RuntimeError(f"installed catalogue solid has suppressed features: {before}")
    try:
        # AddConfiguration2 can activate the child even before returning.
        if manager.AddConfiguration2(
            SUPPLIER_STOCK_CONFIGURATION, SUPPLIER_STOCK_TITLE, "", 0, original,
            "Construction-only source limits; not the current purchased solid", False,
        ) is None:
            raise RuntimeError("cannot create separate supplier max-limit configuration")
        if active_configuration_name(adapter, model) != SUPPLIER_STOCK_CONFIGURATION:
            if model.ShowConfiguration2(SUPPLIER_STOCK_CONFIGURATION) is not True:
                raise RuntimeError("cannot activate supplier max-limit configuration")
        # Leaf-first suppression includes independent Front-plane cuts and both
        # old runout bosses; suppression of Body alone is not diagram isolation.
        for name in reversed(SUPPLIER_SOLID_FEATURES):
            feature = _feature_by_name(adapter, name)
            if tuple(feature.IsSuppressed2(1, null_variant()) or ()) != (True,):
                if feature.SetSuppression2(0, 1, null_variant()) is not True:
                    raise RuntimeError(f"cannot suppress {name} in supplier envelope")
        await force_rebuild(adapter)
        for name in SUPPLIER_SOLID_FEATURES:
            if tuple(_feature_by_name(adapter, name).IsSuppressed2(1, null_variant()) or ()) != (True,):
                raise RuntimeError(f"{name}: source-only suppression did not persist")
        faults = _hard_fault_names(adapter, model)
        if faults:
            raise RuntimeError(f"supplier max-limit configuration has hard faults: {faults}")
        if native_part.GetBodies2(0, False):
            raise RuntimeError("supplier max-limit configuration contains solids")
        if tuple(_feature_by_name(adapter, SUPPLIER_STOCK_FEATURE).IsSuppressed2(
            1, null_variant()
        ) or ()) != (False,):
            raise RuntimeError("supplier max-limit profile became suppressed")
    finally:
        primary = sys.exception()
        try:
            if active_configuration_name(adapter, model) != original:
                if model.ShowConfiguration2(original) is not True:
                    raise RuntimeError("cannot restore installed catalogue configuration")
            for name, state in before.items():
                feature = _feature_by_name(adapter, name)
                if tuple(feature.IsSuppressed2(1, null_variant()) or ()) != state:
                    if feature.SetSuppression2(0 if state[0] else 1, 1, null_variant()) is not True:
                        raise RuntimeError(f"{name}: cannot restore installed suppression")
            await force_rebuild(adapter)
            for name, state in before.items():
                if tuple(_feature_by_name(adapter, name).IsSuppressed2(1, null_variant()) or ()) != state:
                    raise RuntimeError(f"{name}: installed suppression changed")
            faults = _hard_fault_names(adapter, model)
            if faults:
                raise RuntimeError(f"restored catalogue solid has hard faults: {faults}")
            if len(tuple(native_part.GetBodies2(0, False) or ())) != 1:
                raise RuntimeError("installed catalogue part did not retain its one solid")
            if not math.isclose(await _volume_mm3(adapter), before_volume, rel_tol=0.0, abs_tol=1e-6):
                raise RuntimeError("supplier source configuration changed the installed volume")
        except Exception as restore_error:
            if primary is None:
                raise
            primary.add_note(f"also failed to restore installed catalogue solid: {restore_error}")


async def _save_screw(adapter, part_name, suppressed_features):
    """Create source references after material, then simplify only installed stock."""
    await _supplier_stock_envelope(adapter)
    installed = active_configuration_name(adapter, adapter.currentModel)
    if installed == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("cannot save post mount screw with source envelope active")
    parents = (installed,)
    artefacts = await save_part_and_images(adapter, part_name)
    await derive_simplified_on_saved_part(
        adapter, part_name, suppressed_features, artefacts["part"], parents=parents,
    )
    check(f"reopen saved {part_name}", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, part_name)
    assert_simplified_configurations(
        adapter, part_name, suppressed_features, parents=parents,
    )
    return artefacts


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=SKU,
                author=_cut_to_length,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=_save_screw,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
