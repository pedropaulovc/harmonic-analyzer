"""Build the channel-spring lower anchor from McMaster 9489T111.

Twenty of these routing eyebolts replace the old formed-wire J-hook. Each one
threads DOWN through a #6-32 tap in the summing lever's coefficient plate
(``sm_summing_lever_spec.HOLE_SPEC``, sourced from this same anchor record) and
the channel spring's lower eye links onto its eye. The SUPPLIED HEX NUT IS
OMITTED: the anchor is locked by the separate MHA-CH-14 round jam nut
(``ch_anchor_jam_nut_spec``) on the plate underside, so the production
part is the bolt body alone.

Two supplier options this production part takes -- the nut above and LENGTH:
the vendor's 19.05 mm shank is cut to ``ch_vn_spring_hook_spec.SHANK_LENGTH_MM``
with the 45 deg deburr restored at the new end (its leg driven to the sheet's
.018 nominal), so the shank crosses the plate, carries the jam nut and still
shows two full threads below it after the calibration back-out -- and the
factory thread phase survives.

The tracked diagnostic recipe is an exact geometric replay of the supplied
vendor SLDPRT and stays in the vendor's own frame -- eye centre at the origin,
eye plane in XY, shank axis along -Y, threads starting at y -9.525.
``build_ch_channel_assembly`` positions it; nothing here moves it.

Run (SolidWorks already open)::

    uv run python cad\\scripts\\build_ch_vn_spring_hook.py
"""

from __future__ import annotations

from functools import wraps
import math
import sys

from solidworks_mcp.adapters.com_variant import null_variant
from solidworks_mcp.adapters.solidworks.sketch import _resolve_entity_ref
import _telemetry
from _check import check
from _appearance import PANEL_BLACK
from _com import _early_bound, _read_member
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _part_save import save_part_and_images
from _simplified_part import (
    assert_simplified_configurations,
    _hard_faults,
    derive_simplified_on_saved_part,
)
from _configuration_material import require_material_in_every_configuration
from _feature_tree import _feature_by_name, name_last_feature
from _rebuild import (
    active_configuration_name, assert_saved_configurations_regenerate, force_rebuild,
)
from _sketch import (
    SketchDims, add_line_chain, anchor_point_to_origin, blank_reference_sketches,
    dimension_between, ensure_fully_defined,
)
from _supplier_screw_reference import add_supplier_reference_sketch
from _drawing_precision import _named_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import (
    set_dimension_symmetric_tolerance,
    set_dimension_symmetric_angular_tolerance,
)
from diagnostics.diag_build_9489T111 import build_9489T111
from ch_vn_spring_hook_spec import (
    SHANK_LENGTH_MM,
    FINISHED_OVERALL_MM,
    FINISHED_OVERALL_TOLERANCE_MM,
    CHAMFER_WIDTH_MM,
    CHAMFER_WIDTH_TOLERANCE_MM,
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    DRAWING_DIMENSIONS,
    DIMENSION_PRECISION,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
    REFERENCE_SKETCHES,
    SUPPLIER_STOCK_AXIS_MM,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_DIMENSIONS,
    SUPPLIER_STOCK_FEATURE,
    SUPPLIER_STOCK_MM,
    SUPPLIER_THREAD_MAJOR_MM,
    SUPPLIER_THREAD_START_MM,
    UNIT,
)
from stock_anchor_geom import ANCHOR_9489T111

PART_NAME = "ch-vn-spring-hook"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
ANCHOR = ANCHOR_9489T111
FINISHED_FEATURES = (
    "Shank", "Wire", "TipFillet", "EndChamfer", "ThreadGroove", "StockTrim", "StockDeburr",
)

# The vendor ships 9489T111 with a captive hex nut; it is discarded (the
# MHA-CH-14 jam nut is its own part), so no nut geometry belongs in the
# SLDPRT -- and the trim below would cut through its seat.
NUT = "omitted"


@_telemetry.traced("stock.shank.deburr")
async def _size_deburr(adapter) -> None:
    """Drive the restored factory deburr's leg to the sheet's inch nominal.

    The shared trim recipe restores the vendor's 0.4557 leg; the anchor's own
    driving ChamferWidth then takes the spec's .018 (the boss hook's pattern).
    """
    _, dimension = _named_dimension(adapter, "StockDeburrProfile", "ChamferWidth")
    # swSetValue_InAllConfigurations (2); only the finished configuration exists yet.
    status = dimension.SetSystemValue3(CHAMFER_WIDTH_MM / 1000, 2, null_variant())
    if int(status) != 0:  # swSetValueReturnStatus_e.swSetValue_Successful
        raise RuntimeError(f"ChamferWidth@StockDeburrProfile: deburr rejected ({status})")
    await force_rebuild(adapter)
    faults = _hard_faults(adapter, adapter.currentModel)
    if faults:
        raise RuntimeError(f"sized deburr rebuilt with faults {faults}")


def _manufacturing_controls(adapter) -> None:
    """Tolerance and mark actual cutting dimensions before the stock helper saves."""
    clear_dimensions_for_drawing(adapter)
    for feature, name, nominal in (
        ("StockTrimProfile", "FinishedOverall", FINISHED_OVERALL_MM / 1000),
        ("StockDeburrProfile", "ChamferWidth", CHAMFER_WIDTH_MM / 1000),
        ("StockDeburrProfile", "ChamferAngle", math.radians(CHAMFER_ANGLE_DEG)),
    ):
        display, dimension = _named_dimension(adapter, feature, name)
        if int(dimension.DrivenState) != 2:
            raise RuntimeError(f"{name}@{feature} must control the cutting sketch")
        if not math.isclose(float(dimension.SystemValue), nominal, abs_tol=1e-9):
            raise RuntimeError(f"{name}@{feature}: modified stock nominal changed")
        display = _early_bound(display, "IDisplayDimension")
        digits = DIMENSION_PRECISION[name]
        result = display.SetPrecision3(digits, -1, -1, -1)
        if (
            result is None
            or int(_read_member(display, "GetPrimaryPrecision2")) != digits
        ):
            raise RuntimeError(f"{name}@{feature}: native precision did not persist")
    set_dimension_symmetric_tolerance(
        adapter, "StockTrimProfile", "FinishedOverall", FINISHED_OVERALL_TOLERANCE_MM,
        display_unit=UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter, "StockDeburrProfile", "ChamferWidth", CHAMFER_WIDTH_TOLERANCE_MM,
        display_unit=UNIT,
    )
    set_dimension_symmetric_angular_tolerance(
        adapter, "StockDeburrProfile", "ChamferAngle", CHAMFER_ANGLE_TOLERANCE_DEG
    )
    # General dimensions retain their numerical acceptance bands natively;
    # swTolGeneral omits the redundant printed band in favour of the title block.
    for feature, name, band in (
        ("StockTrimProfile", "FinishedOverall", FINISHED_OVERALL_TOLERANCE_MM / 1000),
        (
            "StockDeburrProfile",
            "ChamferAngle",
            math.radians(CHAMFER_ANGLE_TOLERANCE_DEG),
        ),
    ):
        _, dimension = _named_dimension(adapter, feature, name)
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = 11  # swTolType_e.swTolGeneral
        if not tolerance.SetValues(-band, band):
            raise RuntimeError(
                f"{name}@{feature}: cannot retain general tolerance values"
            )
        if (
            int(tolerance.Type) != 11
            or not math.isclose(float(tolerance.GetMinValue()), -band, abs_tol=1e-9)
            or not math.isclose(float(tolerance.GetMaxValue()), band, abs_tol=1e-9)
        ):
            raise RuntimeError(f"{name}@{feature}: general tolerance readback changed")
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )


def _stock_span(adapter, first, last, expected_mm, name, dims):
    """Read a source station span on the original bolt's coherent axis."""
    model = adapter.currentModel
    model.ClearSelection2(True)
    try:
        for ref in (first, last):
            if _resolve_entity_ref(adapter, ref).Select4(True, None) is not True:
                raise RuntimeError(f"cannot select original stock endpoint {ref}")
        display, status = _early_bound(model.Extension, "IModelDocExtension").AddSpecificDimension(
            0.015, 0.0, 0.0, 12, 0
        )
    finally:
        model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"cannot dimension original stock {name} ({status})")
    display = _early_bound(display, "IDisplayDimension")
    if int(display.Type2) != 12:
        raise RuntimeError(f"{name}: original stock span must be a vertical dimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1
    if (
        int(dimension.DrivenState) != 1
        or abs(float(dimension.SystemValue) * 1000.0 - expected_mm) > 1e-5
    ):
        raise RuntimeError(f"{name}: original stock native station span changed")
    dims.record(name)


async def _supplier_stock_profile(adapter):
    """Source station references, hidden outside the stock drawing view."""
    dims = SketchDims()
    check("create original stock axis", await adapter.create_sketch("Front"))
    axis = await add_line_chain(adapter, list(SUPPLIER_STOCK_AXIS_MM), close=False)
    await anchor_point_to_origin(
        adapter, f"{axis[0]}.start", *SUPPLIER_STOCK_AXIS_MM[0], "original eye crown"
    )
    dims.record(None)
    for index, entity in enumerate(axis):
        segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError("original stock axis must remain construction-only")
        check("vertical original stock axis", await adapter.add_sketch_constraint(entity, None, "vertical"))
        await dimension_between(
            adapter, f"{entity}.start", f"{entity}.end", "vertical_distance",
            SUPPLIER_STOCK_AXIS_MM[index][1] - SUPPLIER_STOCK_AXIS_MM[index + 1][1],
            "original stock axis segment",
        )
        dims.record("SupplierStockThread" if index == 2 else None)
    for name, first in (
        ("SupplierStockShank", f"{axis[1]}.start"),
        ("SupplierStockOverall", f"{axis[0]}.start"),
    ):
        _stock_span(adapter, first, f"{axis[-1]}.end", SUPPLIER_STOCK_MM[name], name, dims)
    await ensure_fully_defined(adapter, SUPPLIER_STOCK_FEATURE)
    check("close original stock axis", await adapter.exit_sketch())
    name_last_feature(adapter, SUPPLIER_STOCK_FEATURE)
    dims.apply(adapter, SUPPLIER_STOCK_FEATURE)
    mark_dimensions_for_drawing(
        adapter, SUPPLIER_STOCK_FEATURE, SUPPLIER_STOCK_DIMENSIONS[SUPPLIER_STOCK_FEATURE]
    )
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)


async def _supplier_stock(adapter):
    """Recover the original body after material assignment, then restore the cut."""
    await add_supplier_reference_sketch(
        adapter,
        (("SupplierThreadMajor", SUPPLIER_THREAD_MAJOR_MM, "horizontal"),),
        starts={"SupplierThreadMajor": SUPPLIER_THREAD_START_MM},
    )
    await _supplier_stock_profile(adapter)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    original = active_configuration_name(adapter, model)
    if not original or original == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("spring anchor has no finished configuration")
    original_states = {
        name: tuple(_feature_by_name(adapter, name).IsSuppressed2(1, null_variant()) or ())
        for name in FINISHED_FEATURES
    }
    if any(state != (False,) for state in original_states.values()):
        raise RuntimeError("finished spring anchor has a suppressed solid feature")
    primary: BaseException | None = None
    created = manager.AddConfiguration2(
        SUPPLIER_STOCK_CONFIGURATION,
        "McMaster 9489T111 original as-supplied bolt body; supplied nut omitted",
        "", 0, original, "Source stock only; not the finished anchor", False,
    )
    if created is None:
        raise RuntimeError("cannot create original supplier stock configuration")
    try:
        parent = _early_bound(created, "IConfiguration").GetParent()
        if parent is None or str(_early_bound(parent, "IConfiguration").Name) != original:
            raise RuntimeError("original supplier stock must derive from the finished configuration")
        if active_configuration_name(adapter, model) != SUPPLIER_STOCK_CONFIGURATION:
            if model.ShowConfiguration2(SUPPLIER_STOCK_CONFIGURATION) is not True:
                raise RuntimeError("cannot activate original supplier stock configuration")
        if active_configuration_name(adapter, model) != SUPPLIER_STOCK_CONFIGURATION:
            raise RuntimeError("original supplier stock configuration is not active")
        for name in ("StockDeburr", "StockTrim"):
            feature = _feature_by_name(adapter, name)
            if feature.SetSuppression2(0, 1, null_variant()) is not True:
                raise RuntimeError(f"cannot suppress finished {name} in original stock")
        await force_rebuild(adapter)
        for name in FINISHED_FEATURES:
            expected = (name in ("StockDeburr", "StockTrim"),)
            if tuple(_feature_by_name(adapter, name).IsSuppressed2(1, null_variant()) or ()) != expected:
                raise RuntimeError(f"{name}: original stock has the wrong solid-feature state")
        if len(tuple(_early_bound(model, "IPartDoc").GetBodies2(0, False) or ())) != 1:
            raise RuntimeError("original supplier stock must retain one bolt solid")
        if tuple(_feature_by_name(adapter, SUPPLIER_STOCK_FEATURE).IsSuppressed2(1, null_variant()) or ()) != (False,):
            raise RuntimeError("original stock source axis became suppressed")
        faults = _hard_faults(adapter, model)
        if faults:
            raise RuntimeError(f"original supplier stock rebuilt with faults {faults}")
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if active_configuration_name(adapter, model) != original:
                if model.ShowConfiguration2(original) is not True:
                    raise RuntimeError("cannot restore finished spring anchor configuration")
            if active_configuration_name(adapter, model) != original:
                raise RuntimeError("finished spring anchor configuration is not active")
            for name, expected in original_states.items():
                feature = _feature_by_name(adapter, name)
                if tuple(feature.IsSuppressed2(1, null_variant()) or ()) != expected:
                    if feature.SetSuppression2(1, 1, null_variant()) is not True:
                        raise RuntimeError(f"cannot restore finished {name}")
            await force_rebuild(adapter)
            for name, expected in original_states.items():
                state = _feature_by_name(adapter, name).IsSuppressed2(1, null_variant())
                if tuple(state or ()) != expected:
                    raise RuntimeError(f"{name}: original stock suppression leaked into finished configuration")
            if len(tuple(_early_bound(model, "IPartDoc").GetBodies2(0, False) or ())) != 1:
                raise RuntimeError("finished spring anchor lost its single solid")
        except Exception as error:
            if primary is None:
                raise
            primary.add_note(f"restoration also failed: {error}")
    require_material_in_every_configuration(
        adapter, PART_NAME, MATERIAL, (original, SUPPLIER_STOCK_CONFIGURATION)
    )


async def _save_anchor(adapter, part_name, suppressed_features):
    """Keep the finished simplified derivative separate from original stock."""
    # The stock saver runs after normalized geometry and material assignment.
    await _supplier_stock(adapter)
    finished = active_configuration_name(adapter, adapter.currentModel)
    if not finished or finished == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("cannot save spring anchor without its finished configuration")
    parents = (finished,)
    artefacts = await save_part_and_images(adapter, part_name)
    await derive_simplified_on_saved_part(
        adapter, part_name, suppressed_features, artefacts["part"], parents=parents
    )
    check(f"reopen saved {part_name}", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, part_name)
    assert_simplified_configurations(
        adapter, part_name, suppressed_features, parents=parents
    )
    if active_configuration_name(adapter, adapter.currentModel) != finished:
        raise RuntimeError("saved spring anchor did not restore its finished configuration")
    return artefacts


@wraps(build_9489T111)
async def _modified_anchor(adapter, truth=None, **parameters):
    receipt = await build_9489T111(adapter, truth, **parameters)
    await _size_deburr(adapter)
    _manufacturing_controls(adapter)
    return receipt


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                ANCHOR.sku,
                _modified_anchor,
                parameters={"nut": NUT, "shank_length_mm": SHANK_LENGTH_MM},
            ),
        ),
        material=MATERIAL,
        save_threaded_part=_save_anchor,
        color=PANEL_BLACK,  # black-oxide hardware
        # Shank axis = the vendor -Y axis through the eye centre (Front n Right),
        # the stable mate reference the old sketched part named "shank axis".
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
