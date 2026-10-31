"""Build MHA-SM-VN-52 from complete 92314A253 hex stock, then trim and deburr.

Finished frame: tip Y=0, nominal bearing face Y=46.70, screw axis +Y. The stock
recipe is positioned before cutting, so both the solid and its native
manufacturing/inspection sketches share that frame without a body-only move.
The catalogue's factory helix survives the actual trim; no socket is added.
The closed deburr cutter stays on the positive-radius side of the shank axis.
After its equations are solved, select the completed sketch with mark 0 and
its construction centreline with mark 4; create_revolve does not select them.
"""

from __future__ import annotations

from functools import wraps
import math
import sys

import _config
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _fastener_catalog import fastener
from _feature_tree import _feature_by_name, name_last_feature
from _rebuild import (
    active_configuration_name,
    assert_saved_configurations_regenerate,
    force_rebuild,
)
from _session import run_build
from _simplified_part import (
    _bstr_array,
    _close_part,
    _copy_bom_identity,
    _suppression,
    assert_simplified_configurations,
    persist_configurations_in_place,
)
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
)
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from diagnostics.diag_build_92314A253 import build_92314A253
from diagnostics.diag_mcmaster_lib import no_sketch_inference
from sm_vn_knife_hanger_stud_spec import (
    CATALOG_LENGTH,
    CHAMFER_ANGLE,
    CHAMFER_ANGLE_TOLERANCE,
    CHAMFER_WIDTH,
    CHAMFER_WIDTH_TOLERANCE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    LENGTH,
    SHANK_DIA,
    SKU,
    THREAD_LENGTH_MIN,
    SUPPLIER_REFERENCE_SKETCH,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_SUPPRESSED_FEATURES,
    SUPPLIER_STOCK_TITLE,
    UNIT,
)

PART_NAME = "sm-vn-knife-hanger-stud"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def _trim_stock(adapter) -> None:
    """The native CutLength drives the actual cut plane from the bearing face."""
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    radius = SHANK_DIA / 2
    bottom = LENGTH - CATALOG_LENGTH - SHANK_DIA
    with no_sketch_inference(adapter):
        check("create trim sketch", await adapter.create_sketch("Front"))
        lines = await add_line_chain(
            adapter,
            [
                (-2 * radius, bottom),
                (2 * radius, bottom),
                (2 * radius, 0.0),
                (-2 * radius, 0.0),
            ],
        )
        dims = SketchDims()
        for line, direction in zip(
            lines, ("horizontal", "vertical", "horizontal", "vertical"), strict=True
        ):
            check(
                "trim profile relation",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        await anchor_point_to_origin(
            adapter, f"{lines[0]}.start", -2 * radius, bottom, "trim cutter margin"
        )
        dims.record("CutterLeft")
        dims.record("CutterBottom")
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            f"{lines[0]}.end",
            "horizontal_distance",
            4 * radius,
            "trim cutter width",
        )
        dims.record("CutterWidth")
        point = adapter.currentSketchManager.CreatePoint(0, LENGTH / 1000, 0)
        if point is None:
            raise RuntimeError("cannot create under-head bearing reference")
        bearing = adapter._register_sketch_entity("Point", point)
        await anchor_point_to_origin(adapter, bearing, 0.0, LENGTH, "bearing face")
        dims.record("BearingFaceY")
        await dimension_between(
            adapter,
            bearing,
            f"{lines[2]}.start",
            "vertical_distance",
            LENGTH,
            "finished under-head length",
        )
        dims.record("CutLength")
        await ensure_fully_defined(adapter, "stock trim profile")
        check("exit trim sketch", await adapter.exit_sketch())
        name_last_feature(adapter, "StockTrimProfile")
        dims.apply(adapter, "StockTrimProfile")
        check(
            "cut stock to length",
            await adapter.create_cut_extrude(
                ExtrusionParameters(depth=4 * SHANK_DIA, both_directions=True)
            ),
        )
        name_last_feature(adapter, "StockTrim")

        chamfer = CHAMFER_WIDTH
        check("create deburr sketch", await adapter.create_sketch("Front"))
        lines = await add_line_chain(
            adapter,
            [
                (radius - chamfer, 0.0),
                (radius + chamfer, 0.0),
                (radius + chamfer, chamfer),
                (radius, chamfer),
            ],
            close=True,
        )
        dims = SketchDims()
        for line, direction in zip(
            lines[:3], ("horizontal", "vertical", "horizontal"), strict=True
        ):
            check(
                "deburr profile relation",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        await dimension_between(
            adapter,
            f"{lines[1]}.start",
            "origin",
            "horizontal_distance",
            radius + chamfer,
            "cutter outer radius",
        )
        dims.record("CutterRadius")
        point = adapter.currentSketchManager.CreatePoint(0, LENGTH / 1000, 0)
        if point is None:
            raise RuntimeError("cannot create deburr bearing reference")
        bearing = adapter._register_sketch_entity("Point", point)
        await anchor_point_to_origin(adapter, bearing, 0.0, LENGTH, "bearing face")
        dims.record("BearingFaceY")
        # A nonzero length from the real bearing plane locates the cutter.
        # Its equation follows CutLength; a Y=0 alignment would pin it in place.
        await dimension_between(
            adapter,
            bearing,
            f"{lines[1]}.start",
            "vertical_distance",
            LENGTH,
            "cut end from bearing face",
        )
        dims.record("CutEndFromBearing")
        await dimension_between(
            adapter,
            f"{lines[3]}.start",
            "origin",
            "horizontal_distance",
            radius,
            "stock major radius",
        )
        dims.record("StockMajorRadius")
        await dimension_between(
            adapter,
            f"{lines[3]}.start",
            f"{lines[3]}.end",
            "horizontal_distance",
            chamfer,
            "end chamfer width",
        )
        dims.record("ChamferWidth")
        model = adapter.currentModel
        model.ClearSelection2(True)
        _select_sketch_entities(adapter, [lines[0], lines[3]], 0)
        display, status = _early_bound(
            model.Extension, "IModelDocExtension"
        ).AddSpecificDimension((radius + 2 * chamfer) / 1000, chamfer / 2000, 0, 3, 0)
        model.ClearSelection2(True)
        if display is None:
            raise RuntimeError(f"cannot create native end-chamfer angle: {status}")
        display = _early_bound(display, "IDisplayDimension")
        angle = _early_bound(display.GetDimension2(0), "IDimension")
        nominal = math.radians(CHAMFER_ANGLE)
        actual = abs(float(angle.SystemValue))
        if not math.isclose(actual, nominal, abs_tol=1e-8):
            if (
                not math.isclose(math.pi - actual, nominal, abs_tol=1e-8)
                or not display.SupplementaryAngle()
            ):
                raise RuntimeError("end-chamfer angle is not the specified 45 degrees")
        angle.DrivenState = 2  # swDimensionDriving
        if int(angle.DrivenState) != 2 or not math.isclose(
            abs(float(angle.SystemValue)), nominal, abs_tol=1e-8
        ):
            raise RuntimeError("end-chamfer angle is not a driving 45-degree control")
        dims.record("ChamferAngle")
        axis = adapter.currentSketchManager.CreateCenterLine(
            0, -chamfer / 1000, 0, 0, 2 * chamfer / 1000, 0
        )
        if axis is None:
            raise RuntimeError("cannot create stock deburr axis")
        axis_id = adapter._register_sketch_entity("Line", axis)
        # The construction axis only represents the fixed stock shank axis.
        check(
            "fix deburr axis", await adapter.add_sketch_constraint(axis_id, None, "fix")
        )
        await ensure_fully_defined(adapter, "stock deburr profile")
        check("exit deburr sketch", await adapter.exit_sketch())
        name_last_feature(adapter, "StockDeburrProfile")
        dims.apply(adapter, "StockDeburrProfile")
        await drive_dimension(
            adapter,
            "BearingFaceY@StockDeburrProfile",
            '"BearingFaceY@StockTrimProfile"',
        )
        await drive_dimension(
            adapter,
            "CutEndFromBearing@StockDeburrProfile",
            '"CutLength@StockTrimProfile"',
        )
        # FeatureRevolve2 consumes selections; the adapter does not recover a
        # profile/axis after equation solving. Do not rely on exit-sketch state.
        # exit_sketch also resets the registry, so select the captured native
        # centreline rather than its now-expired axis_id.
        model.ClearSelection2(True)
        if not _feature_by_name(adapter, "StockDeburrProfile").Select2(False, 0):
            raise RuntimeError("cannot select stock deburr profile")
        selection = _early_bound(model.SelectionManager, "ISelectionMgr")
        data = _early_bound(selection.CreateSelectData(), "ISelectData")
        if data is None:
            raise RuntimeError("cannot create stock deburr axis selection")
        data.Mark = 4  # FeatureRevolve2: axis of revolution.
        if not _early_bound(axis, "ISketchSegment").Select4(True, data):
            raise RuntimeError("cannot select stock deburr axis")
        check(
            "deburr trimmed stock",
            await adapter.create_revolve(RevolveParameters(angle=360, is_cut=True)),
        )
        name_last_feature(adapter, "StockDeburr")


async def _thread_tail_acceptance(adapter) -> None:
    """Retain the approved native thread-tail MIN, not a supplier tolerance."""
    check("create tail inspection", await adapter.create_sketch("Front"))
    lines = await add_line_chain(
        adapter,
        [(SHANK_DIA / 2, 0.0), (SHANK_DIA / 2, THREAD_LENGTH_MIN)],
        close=False,
    )
    dims = SketchDims()
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", SHANK_DIA / 2, 0.0, "finished tip plane"
    )
    dims.record("TailMajorRadius")
    check(
        "tail direction",
        await adapter.add_sketch_constraint(lines[0], None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{lines[0]}.start",
        f"{lines[0]}.end",
        "vertical_distance",
        THREAD_LENGTH_MIN,
        "continuous inspected thread tail",
    )
    dims.record("ThreadLengthMin")
    await ensure_fully_defined(adapter, "tail inspection length")
    check("exit tail inspection", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadTailAcceptance")
    dims.apply(adapter, "ThreadTailAcceptance")


def _manufacturing_controls(adapter) -> None:
    clear_dimensions_for_drawing(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # MHA-SM-00 cuts the length to the stack measured at each hole, so the
    # driving CutLength prints as a reference nominal through the native
    # prefix/suffix channel, not ShowParenthesis.
    display, dimension = _named_dimension(adapter, "StockTrimProfile", "CutLength")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 0  # swTolType_e.swTolNONE; property put, no success retval
    display.SetText(1, "(")
    display.SetText(2, ")")
    if (
        int(tolerance.Type) != 0
        or (str(display.GetText(1) or ""), str(display.GetText(2) or "")) != ("(", ")")
        or not bool(display.ShowDimensionValue)
    ):
        raise RuntimeError(
            "CutLength@StockTrimProfile: reference display did not persist"
        )
    # The leg's band holds the chamfer inside the charged incomplete pitch.
    set_dimension_symmetric_tolerance(
        adapter, "StockDeburrProfile", "ChamferWidth", CHAMFER_WIDTH_TOLERANCE,
        display_unit=UNIT,
    )
    # The driving 45-degree angle keeps its title-block band natively;
    # swTolGeneral prints no band and leaves the title block's row in force.
    feature, name = "StockDeburrProfile", "ChamferAngle"
    band = math.radians(CHAMFER_ANGLE_TOLERANCE)
    _, dimension = _named_dimension(adapter, feature, name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 11  # swTolType_e.swTolGeneral
    if (
        not tolerance.SetValues(-band, band)
        or int(tolerance.Type) != 11
        or not math.isclose(float(tolerance.GetMinValue()), -band, abs_tol=1e-9)
        or not math.isclose(float(tolerance.GetMaxValue()), band, abs_tol=1e-9)
    ):
        raise RuntimeError(f"{name}@{feature}: cannot retain general tolerance")
    feature, name = "ThreadTailAcceptance", "ThreadLengthMin"
    _, dimension = _named_dimension(adapter, feature, name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 5  # swTolMIN: nominal is the minimum acceptance size.
    if not tolerance.SetValues(0.0, 0.0) or int(tolerance.Type) != 5:
        raise RuntimeError(f"{name}@{feature}: cannot retain MIN acceptance")
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    row = _config.parts(PART_NAME)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Purchased Screw Note": str(row["purchased_note"]),
            "Supplier Reference Title": SUPPLIER_STOCK_TITLE,
        },
    )


@wraps(build_92314A253)
async def _cut_to_length(adapter, truth=None, **parameters):
    receipt = await build_92314A253(adapter, truth, bearing_y_mm=LENGTH, **parameters)
    await _trim_stock(adapter)
    await drive_dimension(
        adapter,
        "CutterRadius@StockDeburrProfile",
        '"StockMajorRadius@StockDeburrProfile" + "ChamferWidth@StockDeburrProfile"',
    )
    await _thread_tail_acceptance(adapter)
    _manufacturing_controls(adapter)
    await force_rebuild(adapter)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError("finished knife-hanger bolt must have one solid body")
    body = _early_bound(bodies[0], "IBody2")
    tip = body.GetExtremePoint(0, -1, 0)
    if not tip[0] or not math.isclose(float(tip[2]), 0.0, abs_tol=1e-9):
        raise RuntimeError("finished knife-hanger bolt tip is not at Y=0")
    return receipt


def _activate_configuration(adapter, model, name: str) -> None:
    """Avoid SW2026's False return for showing the already-active configuration."""
    if (
        active_configuration_name(adapter, model) != name
        and model.ShowConfiguration2(name) is not True
    ):
        raise RuntimeError(f"cannot activate configuration {name!r}")
    if active_configuration_name(adapter, model) != name:
        raise RuntimeError(f"configuration {name!r} did not become active")


def _add_stock_configuration(adapter) -> str:
    """Restore complete source stock in one child without touching finished solids."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    finished = active_configuration_name(adapter, model)
    names = tuple(str(name) for name in (model.GetConfigurationNames() or ()))
    if model.GetConfigurationByName(SUPPLIER_STOCK_CONFIGURATION) is not None:
        raise RuntimeError("source-stock configuration already exists")
    features = {
        name: _feature_by_name(adapter, name)
        for name in (*SUPPLIER_STOCK_SUPPRESSED_FEATURES, "ThreadGroove")
    }
    before = {name: _suppression(feature, names) for name, feature in features.items()}
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    # Options=0 can activate the child: protect every operation after creation.
    created = manager.AddConfiguration2(
        SUPPLIER_STOCK_CONFIGURATION,
        "Original McMaster stock; finished trim and deburr suppressed",
        "",
        0,
        finished,
        "",
        False,
    )
    if created is None:
        raise RuntimeError("cannot create source-stock configuration")
    try:
        parent = _early_bound(created, "IConfiguration").GetParent()
        if parent is None or str(_early_bound(parent, "IConfiguration").Name) != finished:
            raise RuntimeError("source-stock configuration is not derived from finished")
        _activate_configuration(adapter, model, SUPPLIER_STOCK_CONFIGURATION)
        for name in SUPPLIER_STOCK_SUPPRESSED_FEATURES:
            if not features[name].SetSuppression2(
                0, 3, _bstr_array((SUPPLIER_STOCK_CONFIGURATION,))
            ):
                raise RuntimeError(f"{name}: cannot suppress the finished cut in stock")
        if not model.ForceRebuild3(False):
            raise RuntimeError("source-stock configuration did not rebuild")
        _copy_bom_identity(model, finished, SUPPLIER_STOCK_CONFIGURATION)
        for name, feature in features.items():
            expected = name in SUPPLIER_STOCK_SUPPRESSED_FEATURES
            if _suppression(feature, (SUPPLIER_STOCK_CONFIGURATION,)) != (expected,):
                raise RuntimeError(f"{name}: source-stock suppression is incorrect")
    except BaseException as primary:
        try:
            _activate_configuration(adapter, model, finished)
        except Exception as restore:
            primary.add_note(f"restoring finished configuration also failed: {restore!r}")
        raise
    _activate_configuration(adapter, model, finished)
    for name, feature in features.items():
        if _suppression(feature, names) != before[name]:
            raise RuntimeError(f"{name}: source-stock authoring changed finished states")
    return finished


async def _save_supplier_references(adapter, part_name, suppressed_features):
    """Save the finished-only Simplified child before adding original stock."""
    artefacts = await save_supplier_reference_part(
        adapter,
        part_name,
        suppressed_features,
        dimensions=SUPPLIER_REFERENCE_SKETCH,
        starts=SUPPLIER_REFERENCE_STARTS,
    )
    finished = _add_stock_configuration(adapter)
    persist_configurations_in_place(adapter, part_name)
    _close_part(adapter)
    check("reopen source-stock knife-hanger bolt", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, part_name)
    assert_simplified_configurations(
        adapter, part_name, suppressed_features, parents=(finished,)
    )
    return artefacts


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(SKU, _cut_to_length),),
        material=MATERIAL,
        save_threaded_part=_save_supplier_references,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
