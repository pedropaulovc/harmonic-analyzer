r"""Create the curated machinist drawing for the knife-mount bearing block.

A machined, heat-treated steel block (24 wide x ~29.4 tall x 16 deep) with a
single Ø12 bore.  The bore is the knife-edge bearing: the summing-lever
trunnion's top vertex rides its upper inner wall in line contact (ch18 p.42:
unpainted hardened steel, close bore -- 2026-09-02 user re-read).  Every face
and the bore are real edges, so the block dimensions ride the auto-imported
profile marks while center section A-A shows the true tap-drill cone and
knife-bore crown.

Run with SolidWorks open::

    uv run python cad\scripts\draw_knife_mount.py knife-mount
"""

from __future__ import annotations

import argparse
from collections import Counter
import sys
from typing import Any, NamedTuple


from win32com.client.dynamic import Dispatch as dynamic_dispatch

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    add_native_hole_callout,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    rebuild_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hole_callout_precision,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from knife_mount_spec import (
    BLK_HALF_X,
    BORE_DIAMETER_TOLERANCE_MM,
    BORE_FROM_TOP_TOLERANCE_MM,
    BLK_BOT,
    BLK_TOP,
    BORE_CY,
    DRAWING_DIMENSIONS,
    DRAWING_NOMINALS_MM,
    DRAWING_PRECISION_BY_NAME,
    R_BORE,
    REFERENCE_DIMENSION_NOMINALS_MM,
    DRAWING_REFERENCE_PRECISION,
    STUD_TAP_DIA,
    STUD_TAP_SPEC,
    STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM,
    STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM,
    SUPPORT_Z_THICK,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["knife_mount"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (2.0, 1.0)
_BLOCK_CY = (BLK_TOP + BLK_BOT) / 2.0  # block centre height (model mm)

FRONT_CENTER = (0.145, 0.115)
SECTION_CENTER = (0.255, 0.115)
TOP_CENTER = (0.145, 0.205)
ISO_CENTER = (0.345, 0.195)


_COSMETIC_THREAD_LAYER = "COSMETIC-THREADS-HIDDEN"


def _hide_cosmetic_thread_annotations(
    adapter: Any, views: tuple[Any, ...]
) -> None:
    """Hide every view-owned cosmetic thread, never a native hole callout."""
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        status = manager.AddLayer(
            _COSMETIC_THREAD_LAYER,
            "redundant cosmetic thread annotations hidden",
            0,
            0,
            0,
        )
        if int(status) != 1:
            raise RuntimeError("failed to add hidden cosmetic-thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Printable):
        layer.Printable = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("cosmetic-thread layer is not hidden and non-printing")

    cosmetic_threads = []
    for view in views:
        for raw in _early_bound(view, "IView").GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.GetType()) != 1:  # swCThread, not swNote/hole callout
                continue
            if int(annotation.OwnerType) != 0:  # swAnnotationOwner_DrawingView
                raise RuntimeError("cosmetic thread is not owned by its drawing view")
            if annotation.GetSpecificAnnotation() is None:
                raise RuntimeError("cosmetic thread has no native ICThread object")
            cosmetic_threads.append(annotation)
    if not cosmetic_threads:
        raise RuntimeError("drawing has no cosmetic-thread annotations to hide")
    for annotation in cosmetic_threads:
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError("cosmetic-thread annotation refused hidden layer")

    rebuild_drawing(adapter, label="hide redundant cosmetic threads")
    persisted_layer = _early_bound(
        manager.GetLayer(_COSMETIC_THREAD_LAYER), "ILayer"
    )
    if bool(persisted_layer.Visible) or bool(persisted_layer.Printable):
        raise RuntimeError("cosmetic-thread layer flags changed after rebuild")
    persisted = []
    for view in views:
        persisted.extend(
            _early_bound(raw, "IAnnotation")
            for raw in (_early_bound(view, "IView").GetAnnotations() or ())
            if int(_early_bound(raw, "IAnnotation").GetType()) == 1
        )
    if len(persisted) != len(cosmetic_threads) or any(
        str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER
        for annotation in persisted
    ):
        raise RuntimeError("cosmetic-thread census changed after rebuild")


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


FRONT_KEEP = {
    "BlockWidth": (FRONT_CENTER[0], _front_y(BLK_BOT) - 0.016),
    "BlockHeight": (FRONT_CENTER[0] - 0.060, FRONT_CENTER[1]),
    "BoreDia": (FRONT_CENTER[0] - 0.048, _front_y(BORE_CY) + 0.026),
    "BoreFromTop": (FRONT_CENTER[0] + 0.043, FRONT_CENTER[1]),
    "BoreFromSide": (FRONT_CENTER[0], _front_y(BLK_TOP) + 0.014),
}
SECTION_KEEP = {
    "Depth": (SECTION_CENTER[0], _front_y(BLK_TOP) + 0.018),
}
TOP_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "BoreDia": "THRU",
}


def _assert_imported_nominals(adapter: Any, annotations: list[Any]) -> None:
    """Prove every imported model dimension still measures the spec nominal."""
    remaining = dict(DRAWING_NOMINALS_MM)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        expected_mm = remaining.pop(name, None)
        if expected_mm is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        actual_mm = abs(float(dimension.SystemValue)) * 1000.0
        if abs(actual_mm - expected_mm) > 1e-5:
            raise RuntimeError(
                f"imported {name} measured {actual_mm:g}, expected {expected_mm:g} mm"
            )
    if remaining:
        raise RuntimeError(f"model dimensions never reached sheet: {sorted(remaining)}")


def _finish_tap_reference_dimension(
    adapter: Any, display: Any, dimension_name: str, *, label: str
) -> Any:
    """Center-anchor, parenthesize, and read back one actual-geometry locator."""
    expected_mm = REFERENCE_DIMENSION_NOMINALS_MM[dimension_name]
    precision = DRAWING_REFERENCE_PRECISION[dimension_name]
    display = set_arc_endpoints_to_center(adapter, display, label=label)
    display = _early_bound(display, "IDisplayDimension")
    display.SetPrecision3(
        DRAWING_REFERENCE_PRECISION[dimension_name], -1, -1, -1
    )
    if int(display.GetPrimaryPrecision2()) != precision:
        raise RuntimeError(f"{label} did not retain {precision}-place precision")
    display = set_reference_dimension(
        adapter, display.GetAnnotation(), label=label
    )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    actual_mm = abs(float(dimension.SystemValue)) * 1000.0
    if abs(actual_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label} measured {actual_mm:g} mm, expected {expected_mm:g} mm"
        )
    return display

def _assert_imported_tolerances(adapter: Any, annotations: list[Any]) -> None:
    expected = {
        "BoreDia": BORE_DIAMETER_TOLERANCE_MM,
        "BoreFromTop": BORE_FROM_TOP_TOLERANCE_MM,
    }
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        limit_mm = expected.pop(name, None)
        if limit_mm is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        limit_m = limit_mm / 1000.0
        if (
            int(tolerance.Type) != 4
            or abs(float(tolerance.GetMinValue()) + limit_m) > 1e-9
            or abs(float(tolerance.GetMaxValue()) - limit_m) > 1e-9
        ):
            raise RuntimeError(
                f"imported {name} lost its native symmetric tolerance"
            )
    if expected:
        raise RuntimeError(
            f"native tolerances never reached sheet: {sorted(expected)}"
        )


class _TapDepthContract(NamedTuple):
    precision: int
    tolerance_precision: int
    tolerance_type: int
    tolerance_lower_m: float
    tolerance_upper_m: float


def _read_source_tap_depth_contracts(
    adapter: Any,
) -> dict[str, _TapDepthContract]:
    """Read model-owned depth precision and tolerance before opening the drawing."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    feature = model.FeatureByName("StudTap")
    if feature is None:
        raise RuntimeError("source part has no StudTap Hole Wizard feature")
    feature = _early_bound(feature, "IFeature")
    targets = {
        "tapdrilldepth": "hw-tapdrldepth",
        "fullthreaddepth": "hw-threaddepth",
    }
    found: dict[str, list[_TapDepthContract]] = {
        variable: [] for variable in targets.values()
    }
    display = feature.GetFirstDisplayDimension()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        dimension = display.GetDimension()
        if dimension is not None:
            dimension = _early_bound(dimension, "IDimension")
            normalized = "".join(
                character
                for character in str(dimension.FullName).lower()
                if character.isalnum()
            )
            for token, variable in targets.items():
                if token in normalized:
                    tolerance = _early_bound(
                        dimension.Tolerance, "IDimensionTolerance"
                    )
                    found[variable].append(
                        _TapDepthContract(
                            precision=int(display.GetPrimaryPrecision2()),
                            tolerance_precision=int(
                                display.GetPrimaryTolPrecision2()
                            ),
                            tolerance_type=int(tolerance.Type),
                            tolerance_lower_m=float(tolerance.GetMinValue()),
                            tolerance_upper_m=float(tolerance.GetMaxValue()),
                        )
                    )
        display = feature.GetNextDisplayDimension(display)
    result: dict[str, _TapDepthContract] = {}
    expected_tolerances = {
        "hw-tapdrldepth": STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM,
        "hw-threaddepth": STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM,
    }
    for variable, values in found.items():
        if len(values) != 1:
            raise RuntimeError(
                f"source StudTap has {len(values)} native {variable} dimensions"
            )
        contract = values[0]
        expected_lower_mm, expected_upper_mm = expected_tolerances[variable]
        if (
            (contract.precision, contract.tolerance_precision) != (2, 2)
            or contract.tolerance_type != 2
            or abs(contract.tolerance_lower_m * 1000.0 - expected_lower_mm)
            > 1e-6
            or abs(contract.tolerance_upper_m * 1000.0 - expected_upper_mm)
            > 1e-6
        ):
            raise RuntimeError(
                f"source StudTap {variable} contract is not the approved native "
                f"precision/tolerance: {contract!r}"
            )
        result[variable] = contract
    return result


def _propagate_source_tap_depth_contracts(
    adapter: Any,
    display: Any,
    source_contracts: dict[str, _TapDepthContract],
) -> None:
    """Apply only model-read depth precision and tolerance to callout variables."""
    set_hole_callout_precision(
        display,
        {
            variable: contract.precision
            for variable, contract in source_contracts.items()
        },
        label="knife-mount tap source precision",
    )
    remaining = dict(source_contracts)
    for raw in display.GetHoleCalloutVariables() or ():
        late = dynamic_dispatch(raw._oleobj_)
        name = str(late.VariableName)
        expected = remaining.pop(name, None)
        if expected is None:
            continue
        length = _early_bound(raw, "ICalloutLengthVariable")
        length.TolerancePrecision = expected.tolerance_precision
        late.ToleranceType = expected.tolerance_type
        late.ToleranceMin = expected.tolerance_lower_m
        late.ToleranceMax = expected.tolerance_upper_m
        actual = _TapDepthContract(
            precision=int(length.Precision),
            tolerance_precision=int(length.TolerancePrecision),
            tolerance_type=int(late.ToleranceType),
            tolerance_lower_m=float(late.ToleranceMin),
            tolerance_upper_m=float(late.ToleranceMax),
        )
        if (
            actual.precision != expected.precision
            or actual.tolerance_precision != expected.tolerance_precision
            or actual.tolerance_type != expected.tolerance_type
            or abs(actual.tolerance_lower_m - expected.tolerance_lower_m) > 1e-9
            or abs(actual.tolerance_upper_m - expected.tolerance_upper_m) > 1e-9
        ):
            raise RuntimeError(
                f"knife-mount tap {name}: source contract did not persist; "
                f"expected={expected!r}, actual={actual!r}"
            )
    if remaining:
        raise RuntimeError(
            "knife-mount tap lacks native depth contract variables: "
            f"{sorted(remaining)}"
        )
    rebuild_drawing(adapter, label="knife-mount tap source contract")


@_telemetry.traced("drawing.knife_mount_tap_readback")
def _check_tap_callout(
    display: Any, source_contracts: dict[str, _TapDepthContract]
) -> None:
    """Prove the native callout carries both drill and usable-thread depths."""
    expected_lengths = {
        "hw-tapdrldia": STUD_TAP_DIA,
        "hw-tapdrldepth": STUD_TAP_SPEC.depth_mm,
        "hw-threaddepth": STUD_TAP_SPEC.overrides_mm["ThreadDepth"],
    }
    expected_tolerances = {
        "hw-tapdrldepth": STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM,
        "hw-threaddepth": STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM,
    }
    expected_strings = {
        "hw-threaddesc": "1/2-13 UNC",
        "hw-threadclass": STUD_TAP_SPEC.thread_class,
    }
    variables = tuple(display.GetHoleCalloutVariables() or ())
    found: set[str] = set()
    for raw in variables:
        late = dynamic_dispatch(raw._oleobj_)
        name = str(late.VariableName)
        if name in expected_strings:
            if int(late.Type) != 3:
                raise RuntimeError(f"knife-mount tap {name} is not a string")
            actual = str(_early_bound(raw, "ICalloutStringVariable").String or "")
            if actual.strip(" -") != expected_strings[name]:
                raise RuntimeError(
                    f"knife-mount tap {name}: {actual!r} != {expected_strings[name]!r}"
                )
            found.add(name)
            continue
        if name not in expected_lengths:
            raise RuntimeError(f"unexpected knife-mount tap variable {name!r}")
        if int(late.Type) != 1:
            raise RuntimeError(f"knife-mount tap {name} is not a length")
        length = _early_bound(raw, "ICalloutLengthVariable")
        actual_mm = float(length.Length) * 1000.0
        if abs(actual_mm - expected_lengths[name]) > 1e-5:
            raise RuntimeError(
                f"knife-mount tap {name}: {actual_mm} != "
                f"{expected_lengths[name]} mm"
            )
        if name in expected_tolerances:
            expected_lower_mm, expected_upper_mm = expected_tolerances[name]
            actual_lower_mm = float(late.ToleranceMin) * 1000.0
            actual_upper_mm = float(late.ToleranceMax) * 1000.0
            if (
                int(late.ToleranceType) != 2
                or abs(actual_lower_mm - expected_lower_mm) > 1e-6
                or abs(actual_upper_mm - expected_upper_mm) > 1e-6
                or (
                    int(length.Precision),
                    int(length.TolerancePrecision),
                )
                != (
                    source_contracts[name].precision,
                    source_contracts[name].tolerance_precision,
                )
            ):
                raise RuntimeError(
                    f"knife-mount tap {name}: native tolerance readback "
                    f"type={int(late.ToleranceType)}, "
                    f"lower_mm={actual_lower_mm!r}, "
                    f"upper_mm={actual_upper_mm!r}, "
                    f"nominal_precision={int(length.Precision)}, "
                    f"tolerance_precision={int(length.TolerancePrecision)}"
                )
        found.add(name)
    required = set(expected_lengths) | set(expected_strings)
    if found != required:
        raise RuntimeError(
            f"knife-mount tap callout is missing native variables: {required - found}"
        )


def _hole_callout_variable_snapshot(
    display: Any, label: str
) -> Counter[tuple[Any, ...]]:
    """Read a multiset of every native variable in a hole-callout definition."""
    display = _early_bound(display, "IDisplayDimension")
    variables: Counter[tuple[Any, ...]] = Counter()
    for raw in display.GetHoleCalloutVariables() or ():
        variable = dynamic_dispatch(raw._oleobj_)
        name = str(variable.VariableName)
        kind = int(variable.Type)
        if kind == 1:
            value = _early_bound(raw, "ICalloutLengthVariable")
            record = (
                name,
                kind,
                float(value.Length),
                int(value.Precision),
                int(value.TolerancePrecision),
            )
        elif kind == 2:
            value = _early_bound(raw, "ICalloutAngleVariable")
            record = (name, kind, float(value.Angle), int(value.Precision))
        elif kind == 3:
            value = _early_bound(raw, "ICalloutStringVariable")
            record = (name, kind, str(value.String or ""))
        else:
            raise RuntimeError(
                f"{label}: unsupported native variable type {kind} for {name!r}"
            )
        variables[record] += 1
    return variables


def _omit_default_thread_class(display: Any, expected_class: str, label: str) -> None:
    """Hide only the associative class token already covered by the title block."""
    display = _early_bound(display, "IDisplayDimension")
    variables_before = _hole_callout_variable_snapshot(display, label)
    class_records = [
        (record, count)
        for record, count in variables_before.items()
        if record[0] == "hw-threadclass"
    ]
    if sum(count for _record, count in class_records) != 1:
        raise RuntimeError(
            f"{label}: expected one thread-class occurrence, found {class_records!r}"
        )
    class_record = class_records[0][0]
    if class_record[1] != 3 or str(class_record[2]).strip(" -") != expected_class:
        raise RuntimeError(
            f"{label}: native thread class {class_record!r} != {expected_class!r}"
        )

    definitions = {
        part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)
    }
    matches = [
        part
        for part, definition in definitions.items()
        if "<hw-threadclass>" in definition
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: expected one associative class token: {definitions!r}"
        )
    definition_part = matches[0]
    updated = definitions[definition_part]
    for fragment in (
        " - <hw-threadclass>",
        "- <hw-threadclass>",
        "-<hw-threadclass>",
        " <hw-threadclass>",
        "<hw-threadclass>",
    ):
        if fragment in updated:
            updated = updated.replace(fragment, "", 1)
            break
    if "<hw-threadclass>" in updated or updated == definitions[definition_part]:
        raise RuntimeError(f"{label}: failed to remove only the class token")
    display.SetText(definition_part - 4, updated)
    if str(display.GetText(definition_part) or "") != updated:
        raise RuntimeError(f"{label}: associative definition did not persist")
    if any(
        expected_class in str(display.GetText(part) or "")
        for part in (1, 2, 3, 4)
    ):
        raise RuntimeError(f"{label}: default thread class still prints")
    if any(
        str(display.GetText(part) or "") != definition
        for part, definition in definitions.items()
        if part != definition_part
    ):
        raise RuntimeError(f"{label}: unrelated callout definition changed")

    expected_variables = variables_before.copy()
    expected_variables[class_record] -= 1
    if not expected_variables[class_record]:
        del expected_variables[class_record]
    variables_after = _hole_callout_variable_snapshot(display, label)
    if variables_after != expected_variables:
        raise RuntimeError(
            f"{label}: associations changed beyond thread class: "
            f"before={variables_before!r}, after={variables_after!r}"
        )


def _assert_model_thread_class(
    source_part: Any, feature_name: str, expected_class: str, label: str
) -> None:
    """Verify drawing formatting did not alter Hole Wizard source metadata."""
    feature = _early_bound(source_part.FeatureByName(feature_name), "IFeature")
    definition = _early_bound(feature.GetDefinition(), "IWizardHoleFeatureData2")
    actual = str(definition.ThreadClass or "")
    if actual != expected_class:
        raise RuntimeError(
            f"{label}: model thread class {actual!r} != {expected_class!r}"
        )

async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knife-mount source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    source_tap_contracts = _read_source_tap_depth_contracts(adapter)
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Knife-Mount Bearing Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "knife mount; hardened steel bearing block; knife-edge bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    section = create_section_view(
        adapter,
        front,
        line_start=(FRONT_CENTER[0], FRONT_CENTER[1] - 0.040),
        line_end=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.040),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="tap and knife-bore center section",
    )
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # The manufacturing section and orthographic views use HLR; the shared
    # finalizer promotes the standard isometric to precise Shaded With Edges.
    for view in (front, section, top, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="section A-A",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    dimensions = [*front_annotations, *section_annotations, *top_annotations]
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    _assert_imported_nominals(adapter, dimensions)
    _assert_imported_tolerances(adapter, dimensions)
    assert_imported_precision(adapter, dimensions, DRAWING_PRECISION_BY_NAME)
    for view, label in ((front, "knife bore"), (top, "hanger tap")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center mark to {label}")

    # Parenthesized locators are derived from the actual finished edges and
    # actual Hole Wizard circle. They expose the model's common-axis/mid-plane
    # construction without creating a second driving acceptance requirement.
    tap_radius_sheet = STUD_TAP_DIA * SHEET_SCALE[0] / 2000.0
    tap_from_side = add_edge_dimension(
        adapter,
        top,
        p0=(
            TOP_CENTER[0] - BLK_HALF_X * SHEET_SCALE[0] / 1000.0,
            TOP_CENTER[1],
        ),
        p1=(TOP_CENTER[0] - tap_radius_sheet, TOP_CENTER[1]),
        text_xy=(TOP_CENTER[0], TOP_CENTER[1] + 0.027),
        label="hanger tap from finished side",
        orientation="horizontal",
    )
    _finish_tap_reference_dimension(
        adapter,
        tap_from_side,
        "TapFromSide",
        label="hanger tap from finished side",
    )
    tap_from_end = add_edge_dimension(
        adapter,
        top,
        p0=(
            TOP_CENTER[0],
            TOP_CENTER[1] - SUPPORT_Z_THICK * SHEET_SCALE[0] / 2000.0,
        ),
        p1=(TOP_CENTER[0], TOP_CENTER[1] - tap_radius_sheet),
        text_xy=(TOP_CENTER[0] + 0.035, TOP_CENTER[1]),
        label="hanger tap from finished end",
        orientation="vertical",
    )
    _finish_tap_reference_dimension(
        adapter,
        tap_from_end,
        "TapFromEnd",
        label="hanger tap from finished end",
    )

    # Native Hole Wizard callout owns the thread size/class and blind depth.
    tap_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] - tap_radius_sheet, TOP_CENTER[1]),
        callout_xy=(0.078, 0.218),
        label="hanger-stud blind tap",
    )
    _propagate_source_tap_depth_contracts(
        adapter, tap_callout, source_tap_contracts
    )
    _check_tap_callout(tap_callout, source_tap_contracts)

    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] - R_BORE * SHEET_SCALE[0] / 1000.0, _front_y(BORE_CY)),
        symbol_xy=(FRONT_CENTER[0] - 0.037, _front_y(BORE_CY) - 0.018),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_bore"),
        label="knife bore finish",
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.160)
    # Cosmetic-thread imports can be regenerated by dimension/callout rebuilds.
    # Census every authored view only after all recipe annotations exist.
    _hide_cosmetic_thread_annotations(adapter, (front, section, top, iso))

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Mount Bearing Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )




def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
