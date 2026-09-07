"""One drawing-local parallel-spacing control, not a production layout policy.

Bundled primary SW2026 contracts:
types/IModelDoc2/AlignParallelDimensions.md (void, selected linear dimensions),
docs/swconst/DP_Dimensions.md (DimToDimOffset controls parallel/baseline spacing;
tolerance-bearing dimensions double the offset), and
types/IModelDocExtension/SetUserPreferenceDouble.md (document, not app defaults).
The retained native control measured pitch gains 1/0.5 for these exact model11/
reference2 pairs at view scale 0.5. That is a bounded calibration, not an API rule.
The revised request still needs fresh geometry and unchanged downstream gates.
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
PAPER_CLEARANCE_M = 0.001
_GEOMETRY_EPS_M = 1e-10  # Axis/connectivity classification only, never value drift.


def _near(a, b):
    return math.isclose(a, b, rel_tol=0, abs_tol=_GEOMETRY_EPS_M)


def basic_linear_geometry(measurement):
    """Recognize the captured axis-aligned BASIC frame/line/extensions, not indices."""
    body = measurement["body"]
    values = tuple(float(body[key]) for key in ("xmin", "ymin", "xmax", "ymax"))
    if (
        not all(math.isfinite(value) for value in values)
        or values[0] >= values[2]
        or values[1] >= values[3]
    ):
        raise RuntimeError("parallel BASIC body must have finite positive area")
    strokes = tuple(measurement["native_strokes"])
    if len(strokes) != 7 or measurement.get("native_leader_segments", ()):
        raise RuntimeError(
            "parallel BASIC geometry requires frame, two extensions and one dimension line"
        )
    horizontal, vertical = [], []
    for index, stroke in enumerate(strokes):
        start, end = tuple(stroke["start"]), tuple(stroke["end"])
        if (
            len(start) != 2
            or len(end) != 2
            or not all(math.isfinite(float(value)) for value in (*start, *end))
            or stroke["width_m"] != 0
        ):
            raise RuntimeError(
                "parallel BASIC strokes require finite observed zero-width native segments"
            )
        dx, dy = end[0] - start[0], end[1] - start[1]
        if _near(dy, 0) and not _near(dx, 0):
            horizontal.append(index)
            continue
        if _near(dx, 0) and not _near(dy, 0):
            vertical.append(index)
            continue
        raise RuntimeError("parallel BASIC geometry is not axis aligned")
    if len(horizontal) != 3 or len(vertical) != 4:
        raise RuntimeError(
            "parallel BASIC geometry lacks the rectangular frame/extension inventory"
        )
    candidates = [
        index
        for index in horizontal
        if strokes[index]["start"][1] < body["ymin"] - _GEOMETRY_EPS_M
        and min(strokes[index]["start"][0], strokes[index]["end"][0]) < body["xmin"]
        and max(strokes[index]["start"][0], strokes[index]["end"][0]) > body["xmax"]
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            "parallel BASIC dimension line is not uniquely identified by geometry"
        )
    index = candidates[0]
    line = strokes[index]
    line_y = line["start"][1]
    stations = sorted((line["start"][0], line["end"][0]))
    extensions = []
    for x in stations:
        matches = [
            item
            for item in vertical
            if _near(strokes[item]["start"][0], x)
            and min(strokes[item]["start"][1], strokes[item]["end"][1]) <= line_y
            and max(strokes[item]["start"][1], strokes[item]["end"][1]) > body["ymax"]
        ]
        if len(matches) != 1:
            raise RuntimeError(
                "parallel BASIC dimension line lacks exact two extension stations"
            )
        extensions.extend(matches)
    frame = [
        stroke
        for item, stroke in enumerate(strokes)
        if item not in (index, *extensions)
    ]
    nodes, edges = [], set()
    for stroke in frame:
        edge = []
        for point in (stroke["start"], stroke["end"]):
            matches = [
                i
                for i, old in enumerate(nodes)
                if all(_near(a, b) for a, b in zip(point, old, strict=True))
            ]
            if not matches:
                nodes.append(point)
                matches = [len(nodes) - 1]
            edge.append(matches[0])
        edges.add(tuple(sorted(edge)))
    if (
        len(frame) != 4
        or len(nodes) != 4
        or len(edges) != 4
        or any(sum(node in edge for edge in edges) != 2 for node in range(4))
    ):
        raise RuntimeError(
            "parallel BASIC remaining strokes do not form one closed rectangular frame"
        )
    if any(
        not (
            body["xmin"] - _GEOMETRY_EPS_M <= x <= body["xmax"] + _GEOMETRY_EPS_M
            and body["ymin"] - _GEOMETRY_EPS_M <= y <= body["ymax"] + _GEOMETRY_EPS_M
        )
        for x, y in nodes
    ):
        raise RuntimeError("parallel BASIC frame is not contained by measured body")
    decorations = tuple(measurement.get("leader_decorations", ()))
    for item in decorations:
        vals = tuple(float(item[key]) for key in ("xmin", "ymin", "xmax", "ymax"))
        if (
            not all(math.isfinite(value) for value in vals)
            or vals[0] >= vals[2]
            or vals[1] >= vals[3]
        ):
            raise RuntimeError(
                "parallel BASIC leader decoration is not a finite positive rectangle"
            )
    return {
        "line_y_m": line_y,
        "line_x_m": stations,
        "body": body,
        "upper_reach_m": body["ymax"] - line_y,
        "body_height_m": body["ymax"] - body["ymin"],
        "decorations": decorations,
    }


def pair_geometry(rows, keys):
    geometry = {key: basic_linear_geometry(rows[key]["measurement"]) for key in keys}
    first, second = (geometry[key] for key in keys)
    if first["line_y_m"] <= second["line_y_m"]:
        raise RuntimeError(
            "parallel BASIC pair does not have the observed shorter-above-longer order"
        )
    for own, other in ((first, second), (second, first)):
        body = other["body"]
        if not (
            own["line_x_m"][0] < body["xmin"] and own["line_x_m"][1] > body["xmax"]
        ):
            raise RuntimeError("parallel BASIC pair lacks the observed nested span")
        if any(
            not (item["xmax"] < body["xmin"] or item["xmin"] > body["xmax"])
            for item in own["decorations"]
        ):
            raise RuntimeError(
                "parallel BASIC leader decoration can intersect the other body"
            )
    return geometry


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
    result, plans = {}, {}
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
            selected.append(key)
        result[label] = tuple(selected)
        source, kind, gain = (
            (DimensionSource.MODEL, 11, 1.0)
            if label == "front"
            else (DimensionSource.DRAWING_REFERENCE, 2, 0.5)
        )
        scales = [
            row["scale"]
            for key, row in before.layout.items()
            if key.rpartition("/")[2] == str(views[label].GetName2())
        ]
        if scales != [0.5] or any(
            before.dimensions[key].source is not source
            or before.dimensions[key].display_type != kind
            for key in selected
        ):
            raise RuntimeError(
                "parallel gain calibration only covers the exact model11/reference2 pairs at scale0.5"
            )
        geometry = pair_geometry(before.rows, tuple(selected))
        paper_pitch = (
            max(row["upper_reach_m"] for row in geometry.values()) + PAPER_CLEARANCE_M
        )
        plans[label] = {
            "geometry": geometry,
            "paper_pitch_m": paper_pitch,
            "native_gain": gain,
            "document_offset_m": paper_pitch / gain,
            "view_scale": scales[0],
            "source": source.value,
            "display_type": kind,
        }
    return result, plans


def observed_pair_clearance(after, pairs):
    result = {}
    for label, keys in pairs.items():
        geometry = pair_geometry(after.rows, keys)
        first, second = (geometry[key] for key in keys)
        pitch = first["line_y_m"] - second["line_y_m"]
        clearance = pitch - max(row["upper_reach_m"] for row in geometry.values())
        result[label] = {
            "paper_pitch_m": pitch,
            "line_body_clearance_m": clearance,
            "geometry": geometry,
        }
        if clearance < PAPER_CLEARANCE_M - _GEOMETRY_EPS_M:
            raise RuntimeError(
                f"parallel native pair did not retain 1mm paper line/body clearance: {label}: {result[label]}"
            )
    return result


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
            "scope": "one calibrated document offset write per view and one native parallel call per pair; no retry/speedup claim",
            "gain_calibration": "k5mypm3x: exact model/type11 gain1 and reference/type2 gain0.5, both scale0.5; not a universal API rule",
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
                    pairs, plans = planned_pairs(before, views)
                    report["plans"] = plans
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
                    report["offset_before_m"] = old
                    checkpoint()
                    for label, keys in pairs.items():
                        requested = plans[label]["document_offset_m"]
                        row = report["pairs"][label] = {"requested_offset_m": requested}
                        adapter.ownership.assert_current_owned()
                        if not extension.SetUserPreferenceDouble(
                            preference, option, requested
                        ):
                            raise RuntimeError(
                                "parallel document spacing write rejected"
                            )
                        actual = float(
                            extension.GetUserPreferenceDouble(preference, option)
                        )
                        row["actual_offset_m"] = actual
                        if actual != requested:
                            raise RuntimeError(
                                "parallel document spacing did not retain requested value"
                            )
                        row.update(
                            select_and_align(adapter, views[label], keys, before)
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
                    report["observed_pair_clearance"] = observed_pair_clearance(
                        after, pairs
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
