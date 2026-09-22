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
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    view_name,
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


def _cosmetic_thread_annotations(adapter: Any) -> list[tuple[str, Any]]:
    """Every swCThread in the drawing, named by sheet/view, skipping no view.

    SolidWorks attaches a feature's auto cosmetic 'Tapped Hole' annotation to
    whichever view imports that feature FIRST, and how many arrive is a lottery
    (7/8/5 across identical builds of one geometry -- draw_top_frame's measured
    case), so this walk inventories what THIS build produced and names it. It
    is evidence, never a gate on a count, and it never touches a native hole
    callout or note (``GetType()`` is ``swCThread`` only).
    """
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    found: list[tuple[str, Any]] = []
    for sheet_name in drawing.GetSheetNames() or ():
        sheet = _early_bound(drawing.Sheet(str(sheet_name)), "ISheet")
        for raw_view in sheet.GetViews() or ():
            view = _early_bound(raw_view, "IView")
            label = f"{sheet_name}/{view_name(adapter, view)}"
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                if int(annotation.GetType()) != 1:  # swCThread, not swNote/hole callout
                    continue
                if int(annotation.OwnerType) != 0:  # swAnnotationOwner_DrawingView
                    raise RuntimeError(
                        f"{label}: cosmetic thread is not owned by its drawing view"
                    )
                if annotation.GetSpecificAnnotation() is None:
                    raise RuntimeError(
                        f"{label}: cosmetic thread has no native ICThread object"
                    )
                found.append((label, annotation))
    return found


def _hide_cosmetic_thread_annotations(adapter: Any) -> None:
    """Hide every cosmetic thread; the HIDE is the gate, never a census size.

    A build whose import produced no cosmetic thread is legal and passes. What
    must hold after the rebuild is that zero swCThread annotations remain on a
    printing layer, anywhere on any sheet -- so the proof re-walks every sheet
    and view and names whatever still refuses the hidden layer.
    """
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

    for label, annotation in _cosmetic_thread_annotations(adapter):
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError(
                f"{label}: cosmetic-thread annotation refused hidden layer"
            )

    rebuild_drawing(adapter, label="hide redundant cosmetic threads")
    persisted_layer = _early_bound(
        manager.GetLayer(_COSMETIC_THREAD_LAYER), "ILayer"
    )
    if bool(persisted_layer.Visible) or bool(persisted_layer.Printable):
        raise RuntimeError("cosmetic-thread layer flags changed after rebuild")

    unhidden = [
        (label, annotation)
        for label, annotation in _cosmetic_thread_annotations(adapter)
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER
    ]
    if unhidden:
        for _label, annotation in unhidden:
            annotation.Layer = _COSMETIC_THREAD_LAYER
        refused = [
            (label, str(annotation.Layer or ""))
            for label, annotation in _cosmetic_thread_annotations(adapter)
            if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER
        ]
        if refused:
            raise RuntimeError(
                "cosmetic-thread annotations refused the hidden layer after a "
                "second hide: "
                + "; ".join(f"{label} on layer {name!r}" for label, name in refused)
            )


def _auto_tapped_hole_notes(adapter: Any) -> dict[str, int]:
    """Delete SolidWorks' own Hole Wizard notes, named per view, on every sheet.

    Importing model items brings SolidWorks' descriptive thread note ("1/2-13
    Tapped Hole") along with the geometry, and this recipe replaces every one of
    them with an associative feature callout that also carries the process. A
    bare count cannot say WHICH view changed, and the count is not one per
    sheet: a note arrives once per view that imported a tapped feature, so a
    view added, re-scaled or switched to hidden-lines-removed moves it (the
    top-frame package printed 7, then 8, then 5 across three builds of the same
    geometry). This names them, and deletes them here rather than handing the
    substring to ``finalize_drawing``'s sweep: that sweep re-walked every
    annotation of every view, sheet by sheet (13 s of a 270 s build), to find
    the notes this walk -- ``ISheet::GetViews`` off the sheet objects, no sheet
    activation -- already holds. Each deletion is proved by the view's note list
    read back. The inventory is evidence, never a gate.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    counts: dict[str, int] = {}
    for sheet_name in drawing.GetSheetNames() or ():
        sheet = _early_bound(drawing.Sheet(str(sheet_name)), "ISheet")
        for raw_view in sheet.GetViews() or ():
            view = _early_bound(raw_view, "IView")
            hits = [
                note for note in (
                    _early_bound(raw_note, "INote") for raw_note in (view.GetNotes() or ())
                )
                if "tapped hole" in str(note.GetText() or "").lower()
            ]
            if not hits:
                continue
            label = f"{sheet_name}/{view_name(adapter, view)}"
            for note in hits:
                draw.ClearSelection2(True)
                if not _early_bound(note.GetAnnotation(), "IAnnotation").Select2(False, 0):
                    raise RuntimeError(f"{label}: failed to select an automatic tapped-hole note")
                draw.EditDelete()  # VT_VOID: the re-read below is the proof
            draw.ClearSelection2(True)
            survivors = sum(
                1 for raw_note in (view.GetNotes() or ())
                if "tapped hole" in str(_early_bound(raw_note, "INote").GetText() or "").lower()
            )
            if survivors:
                raise RuntimeError(
                    f"{label}: {survivors} automatic tapped-hole note(s) survived deletion"
                )
            counts[label] = len(hits)
    return counts


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


FRONT_KEEP = {
    "BlockWidth": (FRONT_CENTER[0], _front_y(BLK_BOT) - 0.016),
    "BlockHeight": (FRONT_CENTER[0] - 0.060, FRONT_CENTER[1]),
    "BoreDia": (FRONT_CENTER[0] - 0.048, _front_y(BORE_CY) + 0.026),
    "BoreFromTop": (FRONT_CENTER[0] + 0.043, FRONT_CENTER[1]),
    # 12.00 at its own dimension-line midpoint (the bore centreline is only
    # 24 mm from the left edge), so it stops reading as '12.00 ->A' against
    # the section line's upper arrow.
    "BoreFromSide": (FRONT_CENTER[0] - 0.012, _front_y(BLK_TOP) + 0.014),
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


def _assert_bore_diameter_presentation(display: Any, label: str) -> None:
    """Pin the bore callout as the same Ø12.00 ±0.2 diametric dimension."""
    display = _early_bound(display, "IDisplayDimension")
    if not bool(display.Diametric) or bool(display.DisplayAsLinear):
        raise RuntimeError(f"{label}: lost its diametric presentation")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue)) * 1000.0
    nominal_mm = DRAWING_NOMINALS_MM["BoreDia"]
    if abs(measured_mm - nominal_mm) > 1e-5:
        raise RuntimeError(
            f"{label} measured {measured_mm:g}, expected {nominal_mm:g} mm"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    limit_m = BORE_DIAMETER_TOLERANCE_MM / 1000.0
    if (
        int(tolerance.Type) != 4
        or abs(float(tolerance.GetMinValue()) + limit_m) > 1e-9
        or abs(float(tolerance.GetMaxValue()) - limit_m) > 1e-9
    ):
        raise RuntimeError(f"{label}: lost its native symmetric tolerance")


_LEADER_LINE_NONE = 3  # swLeaderLineVisibility_e.swLeaderLineNone


def _suppress_dimension_line_pair(display: Any, label: str) -> None:
    """Leave only the broken-leader shoulder and its near-edge arrow.

    A leader-attached dimension (diametric dim, native hole callout) also draws
    its dimension LEADER-LINE pair from the feature straight past the text, on
    top of the broken leader's horizontal shoulder -- the two leaders crossing
    the Ø12 bore circle and the tap circle are that pair, not a mis-aimed
    attachment. ``OffsetText`` is unavailable on radial/diametric dimensions
    (``cad/docs/solidworks-drawing-layout-tuning.md`` refusal (a)), so the pair
    is hidden outright instead. ``swLeaderLineNone`` keeps the shoulder and its
    arrow (tube-frame's Ø5 cross-hole callout measured exactly one surviving
    arrowhead); the arrowhead count is read back here so a leader that vanished
    whole cannot pass for a cleaned one.
    """
    display = _sw_type_info.early_bound_or_flag(
        display,
        "IDisplayDimension",
        "GetAnnotation",
        "SetSecondArrow",
        "GetUseDocSecondArrow",
        "GetSecondArrow",
        "SetBrokenLeader2",
        "GetUseDocBrokenLeader",
        "GetBrokenLeader2",
    )
    display.ArrowSide = 1
    if int(display.ArrowSide) != 1:
        raise RuntimeError(f"{label}: outside arrow did not persist")
    display.SetSecondArrow(False, False)
    if bool(display.GetUseDocSecondArrow()) or bool(display.GetSecondArrow()):
        raise RuntimeError(f"{label}: kept its opposite-side arrow")
    display.SolidLeader = False
    if bool(display.SolidLeader):
        raise RuntimeError(f"{label}: solid leader did not clear")
    if display.SetBrokenLeader2(False, 2) != 0:
        raise RuntimeError(f"{label}: failed to apply broken horizontal leader")
    if bool(display.GetUseDocBrokenLeader()) or int(display.GetBrokenLeader2()) != 2:
        raise RuntimeError(f"{label}: broken leader style did not persist")
    display.LeaderVisibility = _LEADER_LINE_NONE
    if int(display.LeaderVisibility) != _LEADER_LINE_NONE:
        raise RuntimeError(f"{label}: kept its dimension leader-line pair")
    annotation = display.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label}: dimension has no annotation")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetDisplayData"
    )
    data = annotation.GetDisplayData()
    if data is None:
        raise RuntimeError(f"{label}: dimension has no rendered display data")
    data = _sw_type_info.early_bound_or_flag(
        data, "IDisplayData", "GetArrowHeadCount"
    )
    arrowheads = int(data.GetArrowHeadCount())
    if arrowheads < 1:
        raise RuntimeError(
            f"{label}: hiding the leader-line pair took the arrowhead with it "
            f"({arrowheads} rendered)"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knife-mount source", await adapter.open_model(str(SOURCE)))
    source_part = _early_bound(adapter.currentModel, "IPartDoc")
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

    # The Ø12.00 THRU callout is leader-attached, so SOLIDWORKS drew its
    # dimension leader-line pair straight across the bore circle. Suppress the
    # pair only after every writer (callout text, precision, tolerance checks)
    # has run, so nothing re-solves the dimension afterwards.
    bore_annotation = next(
        (
            annotation
            for annotation in front_annotations
            if dimension_name(adapter, annotation) == "BoreDia"
        ),
        None,
    )
    if bore_annotation is None:
        raise RuntimeError("front view lost its BoreDia dimension")
    bore_display = _early_bound(
        bore_annotation.GetSpecificAnnotation(), "IDisplayDimension"
    )
    _assert_bore_diameter_presentation(bore_display, "front bore diameter")
    _suppress_dimension_line_pair(bore_display, "front bore diameter")
    _assert_bore_diameter_presentation(bore_display, "front bore diameter")
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
        text_xy=(TOP_CENTER[0] - 0.035, 0.197),
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
        edge_xy=(TOP_CENTER[0] + tap_radius_sheet, TOP_CENTER[1]),
        # 0.200 leaves the callout's second line ~5 mm clear of the block's
        # right outline (sheet x 0.169), which dropping '- 2B' had exposed.
        callout_xy=(0.200, 0.218),
        label="hanger-stud blind tap",
    )
    _propagate_source_tap_depth_contracts(
        adapter, tap_callout, source_tap_contracts
    )
    _check_tap_callout(tap_callout, source_tap_contracts)
    # The title block already carries THREADS UNC/UNF CLASS 2A/2B, so the
    # callout's associative class token is over-spec. It can only be dropped
    # AFTER `_check_tap_callout`, which still reads the hw-threadclass
    # variable `_omit_default_thread_class` removes from the definition.
    _omit_default_thread_class(
        tap_callout,
        STUD_TAP_SPEC.thread_class,
        "hanger-stud blind tap",
    )
    _assert_model_thread_class(
        source_part,
        "StudTap",
        STUD_TAP_SPEC.thread_class,
        "hanger-stud blind tap",
    )
    _suppress_dimension_line_pair(tap_callout, "hanger-stud blind tap callout")

    # A surface-finish annotation's sheet position is its LOWER-LEFT corner,
    # which is also where its leader starts: hung left of the bore the leader
    # ran up-right through the symbol's own 'Ra 1.6' value text. Attach on the
    # bore's lower-right rim and hang the symbol below-right of it instead --
    # the leader then runs up-left, away from its text. Parked beside the block
    # rather than under it, the symbol clears the 24.00 width dimension's right
    # extension line; the leader crossing the block outline itself is normal.
    add_surface_finish(
        adapter,
        front,
        edge_xy=(
            FRONT_CENTER[0] + R_BORE * SHEET_SCALE[0] * 0.7071 / 1000.0,
            _front_y(BORE_CY) - R_BORE * SHEET_SCALE[0] * 0.7071 / 1000.0,
        ),
        symbol_xy=(FRONT_CENTER[0] + 0.032, _front_y(BORE_CY) - 0.014),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_bore"),
        label="knife bore finish",
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.160)
    # Cosmetic-thread imports can be regenerated by dimension/callout rebuilds,
    # and SolidWorks attaches each to whichever view imports its feature first,
    # so hide every one across all sheets only after all recipe annotations
    # exist -- the hide is the gate, not any census size.
    _hide_cosmetic_thread_annotations(adapter)
    # SolidWorks' own '1/2-13 Tapped Hole' is an INote, so the swCThread census
    # above can never see it: delete it per view here, after every recipe
    # annotation exists and immediately before finalize. The per-view counts
    # are evidence of which views imported the tapped feature this build, never
    # a gate -- the count is a lottery.
    auto_tapped_notes = _auto_tapped_hole_notes(adapter)
    _telemetry.info(f"knife-mount automatic tapped-hole notes: {auto_tapped_notes!r}")
    # The sweep deletes SolidWorks' notes, never our associative callout: prove
    # the tap callout still reads its thread description afterwards.
    tap_strings = {
        record[0]: record[2]
        for record in _hole_callout_variable_snapshot(
            tap_callout, "hanger-stud blind tap"
        )
        if record[1] == 3
    }
    if tap_strings.get("hw-threaddesc", "").strip(" -") != "1/2-13 UNC":
        raise RuntimeError(
            "hanger-stud blind tap lost its thread description to the "
            f"redundant-note sweep: {tap_strings!r}"
        )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Mount Bearing Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # The associative tap callout replaces SolidWorks' own descriptive
        # thread notes: the automatic "Tapped Hole" notes are already gone,
        # deleted and proved per view by ``_auto_tapped_hole_notes`` above.
        redundant_note_substrings=(),
        expected_redundant_notes=0,
    )




def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
