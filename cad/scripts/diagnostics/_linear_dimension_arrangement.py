"""One drawing-local parallel-spacing control, not a production layout policy.

Bundled primary SW2026 contracts:
types/IModelDoc2/AlignParallelDimensions.md (void, selected linear dimensions),
docs/swconst/DP_Dimensions.md (DimToDimOffset controls parallel/baseline spacing;
tolerance-bearing dimensions double the offset), and
types/IModelDocExtension/SetUserPreferenceDouble.md (document, not app defaults).
Native ranking/BASIC doubling on these four dimensions remains unproven until
the recorded anchor/stroke readback and unchanged downstream gates pass.
"""

from dataclasses import dataclass
from enum import StrEnum
import math
import time

from _common import _early_bound
from _drawing_annotation_bounds import _installed_swconst
from _drawing_native_callouts import (
    _dimension_witness,
    _same_dimension,
    DimensionSource,
)
from channel_lever_spec import BAR_PIN_X, LEVER_SPRING_X, TAB_START_X, TIP_ARC_CX
from diagnostics import probe_datum_shoulder as shoulder
from diagnostics import probe_drawing_attachments as attachments
from solidworks_mcp.adapters.pywin32_adapter import null_callout
import _telemetry


class LinearArrangement(StrEnum):
    PARALLEL = "parallel"


PAIRS = {
    "front": (("BarLength", TAB_START_X / 1000), ("TipCentreX", TIP_ARC_CX / 1000)),
    "holes": (("RD1", BAR_PIN_X / 1000), ("RD2", LEVER_SPRING_X / 1000)),
}
# Nominal design matching only. The retained native model dimensions differ
# from nominal by +0.074/-0.094 nm; use a bounded 1 nm absolute comparison.
# _same_dimension and source before/after equality remain EXACT mutation gates.
NOMINAL_LINEAR_TOLERANCE_M = 1e-9


def require_targets(variant, targets):
    if variant is None:
        return
    if not isinstance(variant, LinearArrangement) or tuple(targets) != (
        "channel_lever",
    ):
        raise ValueError("parallel linear control requires exactly channel_lever")


@dataclass
class Capture:
    rows: dict
    handles: dict
    dimensions: dict
    tolerances: dict
    layout: dict
    source: dict
    source_handles: dict

    def receipt(self):
        return {
            "annotations": self.rows,
            "layout": self.layout,
            "source": self.source,
            "dimensions": {
                key: {
                    "source": row.source.value,
                    "type": row.display_type,
                    "configuration": row.configuration,
                    "parameters": row.parameters,
                    "tolerance_types": self.tolerances[key],
                }
                for key, row in self.dimensions.items()
            },
        }


def capture(adapter, views, source_reader, expected_source):
    adapter.ownership.assert_current_owned()
    rows, handles = shoulder.all_annotation_layout(adapter)
    source, source_handles = source_reader()
    dimensions, tolerances = {}, {}
    for view in views.values():
        view = _early_bound(view, "IView")
        if int(adapter.swApp.IsSame(view.ReferencedDocument, expected_source)) != 1:
            raise RuntimeError(
                "parallel control view references the wrong exact source"
            )
        for raw in view.GetAnnotationsByType(4) or ():
            annotation = _early_bound(raw, "IAnnotation")
            key = f"{view.GetName2()}/{annotation.GetName()}"
            if (
                key not in rows
                or key in dimensions
                or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1
            ):
                raise RuntimeError(
                    "parallel control dimension inventory/owner mismatch"
                )
            dimension = _dimension_witness(adapter, view, annotation)
            dimensions[key] = dimension
            tolerances[key] = tuple(
                int(_early_bound(item.Tolerance, "IDimensionTolerance").Type)
                for item in dimension.dimensions
            )
            if dimension.source is DimensionSource.MODEL and any(
                not any(
                    int(adapter.swApp.IsSame(item, original)) == 1
                    for original in source_handles.values()
                )
                for item in dimension.dimensions
            ):
                raise RuntimeError(
                    "imported dimension is not an exact declared source parameter"
                )
    return Capture(
        rows,
        handles,
        dimensions,
        tolerances,
        attachments.layout(adapter.currentModel),
        source,
        source_handles,
    )


def planned_pairs(before, views):
    """Only named, visible BASIC linear dimensions; no nearest-coordinate pick."""
    result, heights = {}, []
    if not PAIRS.keys() <= views.keys():
        raise RuntimeError("parallel control needs distinct profile and hole views")
    if str(views["front"].GetName2()) == str(views["holes"].GetName2()):
        raise RuntimeError("parallel control needs distinct native views")
    for label, expected in PAIRS.items():
        selected = []
        for name, value in expected:
            key = f"{views[label].GetName2()}/{name}"
            row = before.rows.get(key)
            dimension = before.dimensions.get(key)
            if row is None or dimension is None or "measurement" not in row:
                raise RuntimeError(f"parallel control has no measured dimension {key}")
            if (
                row["semantic"]["kind"] != 4
                or row["semantic"]["visible"] != 1
                or row["semantic"]["owner_type"] != 0
                or dimension.display_type not in (2, 11)
                or before.tolerances[key] != (1,)
                or len(dimension.parameters) != 1
                or not math.isclose(
                    dimension.parameters[0][3],
                    value,
                    rel_tol=0,
                    abs_tol=NOMINAL_LINEAR_TOLERANCE_M,
                )
            ):
                raise RuntimeError(
                    f"parallel control named linear/BASIC/value contract failed: {key}"
                )
            body = row["measurement"]["body"]
            height = float(body["ymax"]) - float(body["ymin"])
            if not math.isfinite(height) or height <= 0:
                raise RuntimeError(
                    "parallel control has invalid measured BASIC-body height"
                )
            heights.append(height)
            selected.append(key)
        result[label] = tuple(selected)
    # This is a document spacing request, not a predicted native line pitch.
    # Native tolerance doubling/ranking is measured rather than assumed.
    return result, max(heights) + 0.001


def select_and_align(adapter, view, keys, before):
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    model.ClearSelection2(True)
    selected = []
    try:
        if not drawing.ActivateView(str(view.GetName2())):
            raise RuntimeError("parallel control could not activate its exact view")
        if len(keys) != 2 or len(set(keys)) != 2:
            raise RuntimeError(
                "parallel control requires exactly two distinct dimensions"
            )
        for key in keys:
            dimension = before.dimensions[key]
            display = dimension.display
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            if (
                int(adapter.swApp.IsSame(annotation, before.handles[key][0])) != 1
                or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1
            ):
                raise RuntimeError(
                    "parallel dimension identity changed before selection"
                )
            name = str(display.GetNameForSelection() or "")
            if not name or not extension.SelectByID2(
                name, "DIMENSION", 0.0, 0.0, 0.0, True, 0, null_callout(), 0
            ):
                raise RuntimeError("parallel named dimension selection rejected")
            selected.append(name)
            if (
                int(selection.GetSelectedObjectCount2(-1)) != len(selected)
                or int(
                    adapter.swApp.IsSame(
                        selection.GetSelectedObject6(len(selected), -1), display
                    )
                )
                != 1
            ):
                raise RuntimeError(
                    "parallel selection did not resolve to the exact display dimension"
                )
        started = time.perf_counter()
        model.AlignParallelDimensions()  # documented void; movement below is the proof
        return {"selection_names": selected, "seconds": time.perf_counter() - started}
    finally:
        model.ClearSelection2(True)


def compare_control(adapter, before, after, selected):
    if (
        before.source != after.source
        or before.source_handles.keys() != after.source_handles.keys()
    ):
        raise RuntimeError(
            "parallel control changed source parameters/tolerances/BASIC"
        )
    if any(
        int(adapter.swApp.IsSame(item, after.source_handles[key])) != 1
        for key, item in before.source_handles.items()
    ):
        raise RuntimeError("parallel control replaced source parameter identity")
    attachments.check_layout(before.layout, after.layout, "parallel control")
    shoulder.compare_all_annotation_layout(
        adapter.swApp, before.rows, after.rows, before.handles, after.handles
    )
    if (
        before.dimensions.keys() != after.dimensions.keys()
        or before.tolerances != after.tolerances
    ):
        raise RuntimeError("parallel control changed dimension inventory/BASIC")
    for key, dimension in before.dimensions.items():
        _same_dimension(adapter.swApp, key, dimension, after.dimensions[key])
    moved = {}
    for key, row in before.rows.items():
        actual = after.rows[key]
        if key not in selected:
            if row != actual:
                raise RuntimeError(
                    f"parallel control changed unselected native ink: {key}"
                )
            continue
        for field in ("name", "kind", "format_signature"):
            if row["measurement"][field] != actual["measurement"][field]:
                raise RuntimeError(
                    f"parallel control changed selected dimension format: {key}"
                )
        if (
            row["position"] != actual["position"]
            or row["measurement"]["native_strokes"]
            != actual["measurement"]["native_strokes"]
        ):
            moved[key] = {
                "anchor_before": row["position"],
                "anchor_after": actual["position"],
                "strokes_before": row["measurement"]["native_strokes"],
                "strokes_after": actual["measurement"]["native_strokes"],
                "body_before": row["measurement"]["body"],
                "body_after": actual["measurement"]["body"],
            }
    return moved


class ParallelLinearControl:
    def __init__(self, variant):
        require_targets(variant, ("channel_lever",))
        self.variant, self.calls = variant, 0

    def bind(self, adapter, module, trial, checkpoint, source_reader, expected_source):
        require_targets(self.variant, (trial["target"],))
        defaults = module.build.__kwdefaults__ or {}
        original = defaults.get("layout")
        if not callable(original) or self.calls:
            raise RuntimeError(
                "parallel control requires the recipe's explicit unused layout callback"
            )
        report = {
            "variant": self.variant.value,
            "nominal_linear_tolerance_m": NOMINAL_LINEAR_TOLERANCE_M,
            "pairs": {},
            "scope": "one document offset write plus two native parallel calls; no speedup claim",
        }
        trial["linear_dimension_control"] = report

        def controlled(actual_adapter, *, views, **kwargs):
            self.calls += 1
            if actual_adapter is not adapter or self.calls != 1:
                raise RuntimeError(
                    "parallel layout callback must run exactly once on its owned adapter"
                )
            try:
                with _telemetry.span("diagnostic.linear_dimensions.control"):
                    before = capture(adapter, views, source_reader, expected_source)
                    report["before"] = before.receipt()
                    pairs, requested = planned_pairs(before, views)
                    constants = _installed_swconst()
                    preference, option = (
                        int(constants.swDetailingDimToDimOffset),
                        int(constants.swDetailingNoOptionSpecified),
                    )
                    extension = _early_bound(
                        adapter.currentModel.Extension, "IModelDocExtension"
                    )
                    old = float(extension.GetUserPreferenceDouble(preference, option))
                    if not math.isfinite(old) or old <= 0:
                        raise RuntimeError("parallel document spacing is invalid")
                    report["offset"] = {
                        "before_m": old,
                        "requested_m": requested,
                        "basis": "maximum actual selected BASIC-body height plus 1 mm; native tolerance multiplier unassumed",
                    }
                    checkpoint()
                    adapter.ownership.assert_current_owned()
                    if not extension.SetUserPreferenceDouble(
                        preference, option, requested
                    ):
                        raise RuntimeError("parallel document spacing write rejected")
                    actual = float(
                        extension.GetUserPreferenceDouble(preference, option)
                    )
                    report["offset"]["actual_m"] = actual
                    if actual != requested:
                        raise RuntimeError(
                            "parallel document spacing did not retain requested value"
                        )
                    for label, keys in pairs.items():
                        report["pairs"][label] = select_and_align(
                            adapter, views[label], keys, before
                        )
                        checkpoint()
                    after = capture(adapter, views, source_reader, expected_source)
                    report["after"] = after.receipt()
                    selected = {key for keys in pairs.values() for key in keys}
                    report["moved"] = compare_control(adapter, before, after, selected)
                    if any(
                        not set(keys).intersection(report["moved"])
                        for keys in pairs.values()
                    ):
                        raise RuntimeError(
                            "native parallel control did not move both named linear pairs"
                        )
                    checkpoint()
                # All original manufacturing/packing/crossing gates remain mandatory.
                return original(adapter, views=views, **kwargs)
            except Exception as error:
                report["error"] = repr(error)
                try:
                    checkpoint()
                except Exception as checkpoint_error:
                    report["checkpoint_error"] = repr(checkpoint_error)
                raise

        return {"layout": controlled}

    def require_used(self):
        if self.calls != 1:
            raise RuntimeError("parallel control was not invoked exactly once")
