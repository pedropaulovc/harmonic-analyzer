"""Build the counter-spring lower anchor from McMaster 9490T1.

The single open routing eyebolt that hangs the master (counter) spring from the
summing lever's summation-anchor boss. It threads DIRECTLY into the #10-24 tap
through that boss (``sm_summing_lever_spec.COUNTER_HOLE_SPEC``, sourced from this
same anchor record) and is locked by the MHA-SM-VN-55 jam nut on the boss top face
-- no separate link ring.

The one supplier option this production part takes is LENGTH: the vendor's
58.7375 mm shank is cut back to the boss height it engages (19.05 mm, the
lever's ``ANCHOR_H``) plus the jam nut's thread above the boss
(``sm_vn_boss_hook_spec.JAM_NUT_THREAD_MM``) with the 45 deg deburr restored at the
new end, so the factory thread phase is preserved.

The tracked diagnostic recipe is an exact geometric replay of the supplied
vendor SLDPRT and stays in the vendor's own frame -- eye centre at the origin,
eye plane in XY, shank axis along -Y, thread starting at y -8.79475.
``build_sm_summing_assembly`` positions it; nothing here moves it.

Run (SolidWorks already open)::

    uv run python cad\\scripts\\build_sm_vn_boss_hook.py
"""

from __future__ import annotations

from functools import wraps
import math
import sys

from solidworks_mcp.adapters.com_variant import null_variant
from solidworks_mcp.adapters.solidworks.sketch import _resolve_entity_ref
from _check import check
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
from _dimensions import drive_dimension
from _feature_tree import _feature_by_name, name_last_feature
from _rebuild import (
    active_configuration_name,
    assert_saved_configurations_regenerate,
    force_rebuild,
)
from _sketch import (
    SketchDims, add_line_chain, blank_reference_sketches,
    dimension_between, ensure_fully_defined,
)
from _sketch_circle import define_circle
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
from sm_vn_boss_hook_spec import (
    SHANK_LENGTH_MM,
    FINISHED_OVERALL_MM,
    FINISHED_OVERALL_DEVIATIONS,
    FINISHED_OVERALL_TOLERANCE_MM,
    CHAMFER_WIDTH_MM,
    CHAMFER_WIDTH_DEVIATIONS,
    CHAMFER_WIDTH_TOLERANCE_MM,
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    UNIT,
    DRAWING_DIMENSIONS,
    DIMENSION_PRECISION,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
    REFERENCE_SKETCHES,
    SUPPLIER_EYE_ID_MM,
    SUPPLIER_NOMINAL_EYE_OD_MM,
    SUPPLIER_NOMINAL_WIRE_MM,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_DIMENSIONS,
    SUPPLIER_STOCK_FEATURE,
    SUPPLIER_STOCK_WIRE_CENTER_MM,
    SUPPLIER_STOCK_AXIS_MM,
    SUPPLIER_STOCK_OVERALL_MM,
    SUPPLIER_STOCK_SHANK_OUTLINE_MM,
    SUPPLIER_STOCK_SHANK_MM,
    SUPPLIER_THREAD_MAJOR_MM,
    SUPPLIER_THREAD_START_MM,
)
from diagnostics.diag_build_9490T1 import build_9490T1
from stock_anchor_geom import ANCHOR_9490T1
import _telemetry

PART_NAME = "sm-vn-boss-hook"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
ANCHOR = ANCHOR_9490T1
FINISHED_FEATURES = (
    "Shank", "Wire", "ThreadGroove", "Dome1", "EndChamfer", "StockTrim", "StockDeburr",
)


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
        adapter,
        "StockTrimProfile",
        "FinishedOverall",
        FINISHED_OVERALL_TOLERANCE_MM,
        display_unit=UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "StockDeburrProfile",
        "ChamferWidth",
        CHAMFER_WIDTH_TOLERANCE_MM,
        display_unit=UNIT,
    )
    set_dimension_symmetric_angular_tolerance(
        adapter, "StockDeburrProfile", "ChamferAngle", CHAMFER_ANGLE_TOLERANCE_DEG
    )
    # General dimensions retain their numerical acceptance bands natively:
    # the printed band about the model (#290: the mm trim prints rounded in
    # inches); swTolGeneral omits the redundant printed band in favour of the
    # title block.
    angle_band = math.radians(CHAMFER_ANGLE_TOLERANCE_DEG)
    for feature, name, (lower, upper) in (
        (
            "StockTrimProfile",
            "FinishedOverall",
            (FINISHED_OVERALL_DEVIATIONS[0] / 1000, FINISHED_OVERALL_DEVIATIONS[1] / 1000),
        ),
        (
            "StockDeburrProfile",
            "ChamferWidth",
            (CHAMFER_WIDTH_DEVIATIONS[0] / 1000, CHAMFER_WIDTH_DEVIATIONS[1] / 1000),
        ),
        ("StockDeburrProfile", "ChamferAngle", (-angle_band, angle_band)),
    ):
        _, dimension = _named_dimension(adapter, feature, name)
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = 11  # swTolType_e.swTolGeneral
        if not tolerance.SetValues(lower, upper):
            raise RuntimeError(
                f"{name}@{feature}: cannot retain general tolerance values"
            )
        if (
            int(tolerance.Type) != 11
            or not math.isclose(float(tolerance.GetMinValue()), lower, abs_tol=1e-9)
            or not math.isclose(float(tolerance.GetMaxValue()), upper, abs_tol=1e-9)
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


@_telemetry.traced("stock.shank.lead_in")
async def _size_lead_in(adapter) -> None:
    """Drive the restored factory deburr's leg to the tap-clearing lead-in.

    The shared trim recipe restores the vendor's 0.80 leg; the counter anchor's
    own driving ChamferWidth then takes the spec nominal, whose short title-block
    leg still brings the cut end under the mating tap drill.
    """
    _, dimension = _named_dimension(adapter, "StockDeburrProfile", "ChamferWidth")
    # swSetValue_InAllConfigurations (2); only the finished configuration exists yet.
    status = dimension.SetSystemValue3(CHAMFER_WIDTH_MM / 1000, 2, null_variant())
    if int(status) != 0:  # swSetValueReturnStatus_e.swSetValue_Successful
        raise RuntimeError(
            f"ChamferWidth@StockDeburrProfile: lead-in rejected ({status})"
        )
    await force_rebuild(adapter)
    faults = _hard_faults(adapter, adapter.currentModel)
    if faults:
        raise RuntimeError(f"lead-in deburr rebuilt with faults {faults}")


def _stock_construction(adapter, entity):
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("supplier stock outline must remain construction-only")


def _stock_overall_reference(adapter, first, last, dims):
    """Measure the coherent crown-to-end axis, without driving it twice."""
    model = adapter.currentModel
    model.ClearSelection2(True)
    try:
        for ref in (first, last):
            if _resolve_entity_ref(adapter, ref).Select4(True, None) is not True:
                raise RuntimeError(f"cannot select supplier stock endpoint {ref}")
        extension = _early_bound(model.Extension, "IModelDocExtension")
        display, status = extension.AddSpecificDimension(0.015, 0.0, 0.0, 12, 0)
    finally:
        model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"cannot dimension supplier stock overall ({status})")
    display = _early_bound(display, "IDisplayDimension")
    if int(display.Type2) != 12:
        raise RuntimeError("supplier stock overall must be a vertical dimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1
    if (
        int(dimension.DrivenState) != 1
        or abs(float(dimension.SystemValue) * 1000.0 - SUPPLIER_STOCK_OVERALL_MM) > 1e-5
    ):
        raise RuntimeError("supplier stock overall is not the native envelope span")
    dims.record("SupplierStockOverall")


async def _supplier_nominal_stock_profile(adapter) -> None:
    """One associative source eye, shank envelope and wire section."""
    dims = SketchDims()
    check("create nominal supplier stock diagram", await adapter.create_sketch("Front"))
    circles = {}
    for name, center, diameter in (
        ("SupplierNominalEyeOD", (0.0, 0.0), SUPPLIER_NOMINAL_EYE_OD_MM),
        ("SupplierNominalEyeID", (0.0, 0.0), SUPPLIER_EYE_ID_MM),
        ("SupplierNominalWire", SUPPLIER_STOCK_WIRE_CENTER_MM, SUPPLIER_NOMINAL_WIRE_MM),
    ):
        circle = await define_circle(
            adapter, *center, diameter / 2.0, name,
            dims=dims, names=(None, None, name),
        )
        _stock_construction(adapter, circle)
        circles[name] = circle
    outline = await add_line_chain(adapter, list(SUPPLIER_STOCK_SHANK_OUTLINE_MM))
    for entity in outline:
        _stock_construction(adapter, entity)
    for index, entity in enumerate(outline):
        check(
            "rectilinear source shank",
            await adapter.add_sketch_constraint(
                entity, None, "horizontal" if index % 2 == 0 else "vertical"
            ),
        )
    await dimension_between(
        adapter, f"{outline[0]}.start", f"{outline[0]}.end",
        "horizontal_distance", SUPPLIER_NOMINAL_WIRE_MM, "source shank width",
    )
    dims.record(
        "SupplierStockWireWidth",
        f'"SupplierNominalWire@{SUPPLIER_STOCK_FEATURE}"',
    )
    # Actual circle/edge relations make this a source envelope rather than
    # independent equal-valued witness lines. The lower axis is already
    # vertical through its two rectangle-edge midpoint relations.
    axis = await add_line_chain(adapter, list(SUPPLIER_STOCK_AXIS_MM), close=False)
    for entity in axis:
        _stock_construction(adapter, entity)
    check("vertical stock eye axis", await adapter.add_sketch_constraint(axis[0], None, "vertical"))
    for ref in (f"{axis[0]}.start", f"{axis[0]}.end"):
        check(
            "source axis endpoint on nominal eye",
            await adapter.add_sketch_constraint(ref, circles["SupplierNominalEyeOD"], "coincident"),
        )
    check(
        "source eye axis through origin",
        await adapter.add_sketch_constraint(f"{axis[0]}.start", "origin", "vertical_points"),
    )
    for ref, edge in (
        (f"{axis[0]}.end", outline[0]),
        (f"{axis[-1]}.end", outline[2]),
    ):
        check(
            "source axis endpoint on shank midpoint",
            await adapter.add_sketch_constraint(ref, edge, "midpoint"),
        )
    await dimension_between(
        adapter, f"{axis[1]}.start", f"{axis[1]}.end", "vertical_distance",
        SUPPLIER_STOCK_SHANK_MM, "as-supplied shank",
    )
    dims.record("SupplierStockShank")
    _stock_overall_reference(adapter, f"{axis[0]}.start", f"{axis[-1]}.end", dims)
    await ensure_fully_defined(adapter, SUPPLIER_STOCK_FEATURE)
    check("close nominal supplier stock diagram", await adapter.exit_sketch())
    name_last_feature(adapter, SUPPLIER_STOCK_FEATURE)
    drive_jobs = dims.apply(adapter, SUPPLIER_STOCK_FEATURE)
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    mark_dimensions_for_drawing(
        adapter, SUPPLIER_STOCK_FEATURE, SUPPLIER_STOCK_DIMENSIONS[SUPPLIER_STOCK_FEATURE]
    )
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)


async def _supplier_nominal_stock(adapter) -> None:
    """Isolate nominal source geometry without changing the installed solid."""
    await add_supplier_reference_sketch(
        adapter,
        (("SupplierThreadMajor", SUPPLIER_THREAD_MAJOR_MM, "horizontal"),),
        starts={"SupplierThreadMajor": SUPPLIER_THREAD_START_MM},
    )
    await _supplier_nominal_stock_profile(adapter)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = _early_bound(model, "IPartDoc")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    original = active_configuration_name(adapter, model)
    if not original or original == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("counter anchor has no finished configuration")
    original_states = {
        name: tuple(_feature_by_name(adapter, name).IsSuppressed2(1, null_variant()) or ())
        for name in FINISHED_FEATURES
    }
    if any(state != (False,) for state in original_states.values()):
        raise RuntimeError("finished counter anchor has a suppressed solid feature")
    primary: BaseException | None = None
    created = manager.AddConfiguration2(
        SUPPLIER_STOCK_CONFIGURATION,
        "McMaster 9490T1 supplier nominal full stock envelope and wire section",
        "", 0, original, "Supplier nominal stock diagram only; not finished geometry", False,
    )
    if created is None:
        raise RuntimeError("cannot create nominal supplier stock configuration")
    try:
        parent = _early_bound(created, "IConfiguration").GetParent()
        if parent is None or str(_early_bound(parent, "IConfiguration").Name) != original:
            raise RuntimeError("nominal supplier stock must derive from the finished configuration")
        if active_configuration_name(adapter, model) != SUPPLIER_STOCK_CONFIGURATION:
            if model.ShowConfiguration2(SUPPLIER_STOCK_CONFIGURATION) is not True:
                raise RuntimeError("cannot activate nominal supplier stock configuration")
        if active_configuration_name(adapter, model) != SUPPLIER_STOCK_CONFIGURATION:
            raise RuntimeError("nominal supplier stock configuration is not active")
        for feature_name in reversed(FINISHED_FEATURES):
            feature = _feature_by_name(adapter, feature_name)
            if feature.SetSuppression2(0, 1, null_variant()) is not True:
                raise RuntimeError(f"cannot suppress {feature_name} in stock diagram")
        await force_rebuild(adapter)
        for feature_name in FINISHED_FEATURES:
            state = _feature_by_name(adapter, feature_name).IsSuppressed2(1, null_variant())
            if tuple(state or ()) != (True,):
                raise RuntimeError(f"{feature_name}: source diagram retained a solid feature")
        if part.GetBodies2(0, False):
            raise RuntimeError("nominal stock diagram still contains finished solids")
        states = _feature_by_name(adapter, SUPPLIER_STOCK_FEATURE).IsSuppressed2(1, null_variant())
        if tuple(states or ()) != (False,):
            raise RuntimeError("nominal stock diagram sketch became suppressed")
        faults = _hard_faults(adapter, model)
        if faults:
            raise RuntimeError(f"nominal supplier stock rebuilt with faults {faults}")
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if active_configuration_name(adapter, model) != original:
                if model.ShowConfiguration2(original) is not True:
                    raise RuntimeError("cannot restore finished counter anchor configuration")
            if active_configuration_name(adapter, model) != original:
                raise RuntimeError("finished counter anchor configuration is not active")
            for name, expected in original_states.items():
                feature = _feature_by_name(adapter, name)
                if tuple(feature.IsSuppressed2(1, null_variant()) or ()) != expected:
                    if feature.SetSuppression2(1, 1, null_variant()) is not True:
                        raise RuntimeError(f"cannot restore finished {name}")
            await force_rebuild(adapter)
            for name, expected in original_states.items():
                state = _feature_by_name(adapter, name).IsSuppressed2(1, null_variant())
                if tuple(state or ()) != expected:
                    raise RuntimeError(f"{name}: stock suppression leaked into finished configuration")
            if len(tuple(part.GetBodies2(0, False) or ())) != 1:
                raise RuntimeError("finished counter anchor did not retain its one solid")
        except Exception as error:
            if primary is None:
                raise
            primary.add_note(f"restoration also failed: {error}")
    require_material_in_every_configuration(
        adapter, PART_NAME, MATERIAL, (original, SUPPLIER_STOCK_CONFIGURATION)
    )


async def _save_anchor(adapter, part_name, suppressed_features):
    """Simplify only the finished parent, never the zero-body source diagram."""
    # The stock saver runs after normalized geometry and material assignment.
    await _supplier_nominal_stock(adapter)
    finished = active_configuration_name(adapter, adapter.currentModel)
    if not finished or finished == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("cannot save counter anchor without its finished configuration")
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
        raise RuntimeError("saved counter anchor did not restore its finished configuration")
    return artefacts


@wraps(build_9490T1)
async def _modified_anchor(adapter, truth=None, **parameters):
    receipt = await build_9490T1(adapter, truth, **parameters)
    await _size_lead_in(adapter)
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
                parameters={"shank_length_mm": SHANK_LENGTH_MM},
            ),
        ),
        material=MATERIAL,
        save_threaded_part=_save_anchor,
        # Shank axis = the vendor -Y axis through the eye centre (Front n Right),
        # the stable mate reference the old sketched part named "shank axis".
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
