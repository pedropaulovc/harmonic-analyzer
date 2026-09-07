"""Native parallel spacing for the two measured channel-lever BASIC pairs.

The native control datum-policy-xqvch22r passed full recipe/cold/crossing checks.
Its scale-0.5 model/type11 and drawing-reference/type2 pairs had native paper
pitch gains 1 and 0.5 respectively. These are explicit lever calibrations, NOT a
general SolidWorks scaling rule. Unknown classes/scales/geometry fail.

Only the supplied four annotations are measured, once before and once after two
native commands. Final whole-sheet manufacturing and crossing checks remain the
recipe's responsibility. No scene enumeration, feature pick, position setter,
retry, source write, or diagnostic dependency belongs here.

Primary API contracts: IModelDoc2.AlignParallelDimensions (void, selected linear
dimensions); DP_Dimensions, swDetailingDimToDimOffset (metres, document-local;
tolerance-bearing dimensions double spacing); IModelDocExtension preference
getters/setters. The measured BASIC geometry determines the requested clearance.
"""

from dataclasses import dataclass
import math
from typing import Any

from _common import _early_bound
from _drawing_annotation_bounds import (
    AnnotationBounds,
    Segment,
    _installed_swconst,
    annotation_box,
)
from _drawing_native_callouts import (
    DimensionSource,
    _Dimension,
    _dimension_witness,
    _same_dimension,
)
from _drawing_view_packing import Rect
from channel_lever_spec import BAR_PIN_X, LEVER_SPRING_X, TAB_START_X, TIP_ARC_CX
from solidworks_mcp.adapters.pywin32_adapter import null_callout
import _telemetry


PAIRS = {
    "front": (("BarLength", TAB_START_X / 1000), ("TipCentreX", TIP_ARC_CX / 1000)),
    "holes": (("RD1", BAR_PIN_X / 1000), ("RD2", LEVER_SPRING_X / 1000)),
}
NOMINAL_LINEAR_TOLERANCE_M = 1e-9  # Design recognition only; mutation checks exact.
PAPER_CLEARANCE_M = 0.001
GEOMETRY_EPS_M = 1e-10  # Axis/connectivity and final floating-point subtraction only.


@dataclass(frozen=True)
class BasicLinearInk:
    body: Rect
    strokes: tuple[Segment, ...]
    native_leaders: tuple[Segment, ...]
    decorations: tuple[Rect, ...]

    @classmethod
    def from_bounds(cls, measured: AnnotationBounds) -> "BasicLinearInk":
        return cls(
            measured.body,
            measured.native_strokes,
            measured.native_leader_segments,
            measured.leader_decorations,
        )


@dataclass(frozen=True)
class BasicLinearGeometry:
    line_y_m: float
    line_x_m: tuple[float, float]
    body: Rect
    upper_reach_m: float
    body_height_m: float
    decorations: tuple[Rect, ...]


def _near(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=0, abs_tol=GEOMETRY_EPS_M)


def basic_linear_geometry(ink: BasicLinearInk) -> BasicLinearGeometry:
    """Identify the captured closed BASIC frame/line/extensions, never indices."""
    body, strokes = ink.body, ink.strokes
    if len(strokes) != 7 or ink.native_leaders:
        raise RuntimeError(
            "parallel BASIC geometry requires frame, two extensions and one dimension line"
        )
    horizontal, vertical = [], []
    for index, stroke in enumerate(strokes):
        start, end = stroke.start, stroke.end
        if (
            len(start) != 2
            or len(end) != 2
            or not all(math.isfinite(value) for value in (*start, *end))
            or stroke.width_m != 0
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
        if strokes[index].start[1] < body.ymin - GEOMETRY_EPS_M
        and min(strokes[index].start[0], strokes[index].end[0]) < body.xmin
        and max(strokes[index].start[0], strokes[index].end[0]) > body.xmax
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            "parallel BASIC dimension line is not uniquely identified by geometry"
        )
    index = candidates[0]
    line = strokes[index]
    line_y = line.start[1]
    stations = tuple(sorted((line.start[0], line.end[0])))
    extensions = []
    for x in stations:
        matches = [
            item
            for item in vertical
            if _near(strokes[item].start[0], x)
            and min(strokes[item].start[1], strokes[item].end[1]) <= line_y
            and max(strokes[item].start[1], strokes[item].end[1]) > body.ymax
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
        for point in (stroke.start, stroke.end):
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
            body.xmin - GEOMETRY_EPS_M <= x <= body.xmax + GEOMETRY_EPS_M
            and body.ymin - GEOMETRY_EPS_M <= y <= body.ymax + GEOMETRY_EPS_M
        )
        for x, y in nodes
    ):
        raise RuntimeError("parallel BASIC frame is not contained by measured body")
    return BasicLinearGeometry(
        line_y,
        stations,
        body,
        body.ymax - line_y,
        body.ymax - body.ymin,
        ink.decorations,
    )


def basic_pair_geometry(
    first: BasicLinearInk, second: BasicLinearInk
) -> tuple[BasicLinearGeometry, BasicLinearGeometry]:
    geometry = basic_linear_geometry(first), basic_linear_geometry(second)
    a, b = geometry
    if a.line_y_m <= b.line_y_m:
        raise RuntimeError(
            "parallel BASIC pair does not have the observed shorter-above-longer order"
        )
    for own, other in ((a, b), (b, a)):
        body = other.body
        if not (own.line_x_m[0] < body.xmin and own.line_x_m[1] > body.xmax):
            raise RuntimeError("parallel BASIC pair lacks the observed nested span")
        if any(
            not (item.xmax < body.xmin or item.xmin > body.xmax)
            for item in own.decorations
        ):
            raise RuntimeError(
                "parallel BASIC leader decoration can intersect the other body"
            )
    return geometry


def required_paper_pitch(
    geometry: tuple[BasicLinearGeometry, BasicLinearGeometry],
) -> float:
    return max(row.upper_reach_m for row in geometry) + PAPER_CLEARANCE_M


def observed_paper_clearance(
    geometry: tuple[BasicLinearGeometry, BasicLinearGeometry],
) -> float:
    first, second = geometry
    clearance = (
        first.line_y_m - second.line_y_m - max(row.upper_reach_m for row in geometry)
    )
    if clearance < PAPER_CLEARANCE_M - GEOMETRY_EPS_M:
        raise RuntimeError(
            f"parallel native pair did not retain 1mm paper line/body clearance: {clearance}"
        )
    return clearance


@dataclass(frozen=True)
class _ViewContext:
    view: Any
    source: Any
    name: str
    configuration: str
    position: tuple[float, ...]
    scale: float


def _view_context(view: Any) -> _ViewContext:
    row = _ViewContext(
        view,
        view.ReferencedDocument,
        str(view.GetName2()),
        str(view.ReferencedConfiguration),
        tuple(view.Position),
        float(view.ScaleDecimal),
    )
    if (
        row.source is None
        or not row.name
        or not row.configuration
        or row.scale != 0.5
        or len(row.position) != 2
        or not all(math.isfinite(value) for value in row.position)
    ):
        raise RuntimeError(
            "parallel calibration requires exact named scale0.5 views and finite positions"
        )
    return row


def _same_context(
    adapter: Any, model: Any, sheet: Any, contexts: tuple[_ViewContext, ...]
) -> None:
    app = adapter.swApp
    if (
        int(app.IsSame(model, adapter.currentModel)) != 1
        or int(app.IsSame(model, app.ActiveDoc)) != 1
        or int(app.IsSame(sheet, _early_bound(model, "IDrawingDoc").GetCurrentSheet()))
        != 1
    ):
        raise RuntimeError("parallel spacing changed the exact drawing/sheet context")
    for old in contexts:
        new = _view_context(old.view)
        if (old.name, old.configuration, old.position, old.scale) != (
            new.name,
            new.configuration,
            new.position,
            new.scale,
        ) or int(app.IsSame(old.source, new.source)) != 1:
            raise RuntimeError(f"parallel spacing changed view context: {old.name}")


@dataclass(frozen=True)
class _Annotation:
    annotation: Any
    owner: Any
    dimension: _Dimension
    tolerance_types: tuple[int, ...]
    entities: tuple[Any, ...]
    entity_types: tuple[int, ...]
    measured: AnnotationBounds


def _capture(
    adapter: Any, view: Any, annotation: Any, *, label: str, name: str, nominal: float
) -> _Annotation:
    annotation = _early_bound(annotation, "IAnnotation")
    owner = annotation.Owner
    if (
        str(annotation.GetName()) != name
        or int(annotation.GetType()) != 4
        or int(annotation.OwnerType) != 0
        or int(annotation.Visible) != 1
        or annotation.IsDangling()
        or int(adapter.swApp.IsSame(owner, view)) != 1
    ):
        raise RuntimeError(
            f"parallel named dimension owner/visibility/identity contract failed: {name}"
        )
    dimension = _dimension_witness(adapter, view, annotation)
    tolerance_types = tuple(
        int(_early_bound(item.Tolerance, "IDimensionTolerance").Type)
        for item in dimension.dimensions
    )
    expected_source, expected_type = (
        (DimensionSource.MODEL, 11)
        if label == "front"
        else (DimensionSource.DRAWING_REFERENCE, 2)
    )
    if (
        dimension.source is not expected_source
        or dimension.display_type != expected_type
        or tolerance_types != (1,)
        or len(dimension.parameters) != 1
        or dimension.parameters[0][0] != name
        or not math.isclose(
            dimension.parameters[0][3],
            nominal,
            rel_tol=0,
            abs_tol=NOMINAL_LINEAR_TOLERANCE_M,
        )
    ):
        raise RuntimeError(f"parallel named linear/BASIC/value contract failed: {name}")
    entities = tuple(annotation.GetAttachedEntities3() or ())
    kinds = tuple(int(value) for value in annotation.GetAttachedEntityTypes() or ())
    count = annotation.GetAttachedEntityCount3()
    if (
        count != 2
        or len(entities) != count
        or len(kinds) != count
        or any(entity is None for entity in entities)
        or kinds != ((11, 11) if label == "front" else (1, 1))
    ):
        raise RuntimeError(
            f"parallel dimension has an incomplete/unrecognized attachment inventory: {name}"
        )
    measured = annotation_box(adapter, annotation)
    if measured.name != name or measured.kind != 4:
        raise RuntimeError(f"parallel dimension measurement identity changed: {name}")
    return _Annotation(
        annotation, owner, dimension, tolerance_types, entities, kinds, measured
    )


def _ink_content(measured: AnnotationBounds) -> tuple:
    return tuple(
        (run.value, run.height_m, run.font, run.angle_rad, run.reference, run.inverted)
        for run in measured.text_runs
    )


def _same_annotation(
    app: Any, name: str, before: _Annotation, after: _Annotation
) -> None:
    _same_dimension(app, name, before.dimension, after.dimension)
    if (
        before.tolerance_types != after.tolerance_types
        or before.entity_types != after.entity_types
        or before.measured.format_signature != after.measured.format_signature
        or _ink_content(before.measured) != _ink_content(after.measured)
    ):
        raise RuntimeError(
            f"parallel dimension BASIC/attachment type/text/format changed: {name}"
        )
    for a, b in (
        (before.annotation, after.annotation),
        (before.owner, after.owner),
        *zip(before.entities, after.entities, strict=True),
    ):
        if int(app.IsSame(a, b)) != 1:
            raise RuntimeError(
                f"parallel dimension exact native identity changed: {name}"
            )


def _select_and_align(
    adapter: Any, view: Any, rows: tuple[_Annotation, _Annotation]
) -> None:
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    model.ClearSelection2(True)
    try:
        if not drawing.ActivateView(str(view.GetName2())):
            raise RuntimeError("parallel spacing could not activate its exact view")
        for index, row in enumerate(rows, 1):
            display = row.dimension.display
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            if (
                int(adapter.swApp.IsSame(annotation, row.annotation)) != 1
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
            if (
                int(selection.GetSelectedObjectCount2(-1)) != index
                or int(
                    adapter.swApp.IsSame(
                        selection.GetSelectedObject6(index, -1), display
                    )
                )
                != 1
            ):
                raise RuntimeError(
                    "parallel selection did not resolve to the exact display dimension"
                )
        model.AlignParallelDimensions()  # Void; actual final movement/clearance is checked.
    finally:
        model.ClearSelection2(True)


@_telemetry.traced("drawing.parallel_basic_spacing")
def align_channel_lever_basic_pairs(
    adapter: Any,
    *,
    front: Any,
    bar_length: Any,
    tip_centre_x: Any,
    holes: Any,
    bar_pin_c2c: Any,
    spring_c2c: Any,
) -> None:
    """One calibrated command per exact pair, with independent fresh readback."""
    model = adapter.currentModel
    if (
        int(model.GetType()) != 3
        or int(adapter.swApp.IsSame(model, adapter.swApp.ActiveDoc)) != 1
    ):
        raise RuntimeError("parallel spacing requires the exact active drawing")
    drawing = _early_bound(model, "IDrawingDoc")
    sheet = drawing.GetCurrentSheet()
    contexts = tuple(
        _view_context(_early_bound(view, "IView")) for view in (front, holes)
    )
    if (
        contexts[0].name == contexts[1].name
        or int(adapter.swApp.IsSame(contexts[0].view, contexts[1].view)) != 0
        or int(adapter.swApp.IsSame(contexts[0].source, contexts[1].source)) != 1
    ):
        raise RuntimeError(
            "parallel spacing requires distinct views of the exact same source"
        )
    views = dict(zip(PAIRS, (row.view for row in contexts), strict=True))
    annotations = {
        "front": (bar_length, tip_centre_x),
        "holes": (bar_pin_c2c, spring_c2c),
    }

    def capture():
        return {
            label: tuple(
                _capture(
                    adapter,
                    views[label],
                    annotation,
                    label=label,
                    name=name,
                    nominal=value,
                )
                for annotation, (name, value) in zip(
                    annotations[label], definitions, strict=True
                )
            )
            for label, definitions in PAIRS.items()
        }

    with _telemetry.span("drawing.parallel_basic_spacing.initial", annotations=4):
        before = capture()
        plans = {
            label: required_paper_pitch(
                basic_pair_geometry(
                    *(BasicLinearInk.from_bounds(row.measured) for row in rows)
                )
            )
            for label, rows in before.items()
        }
    constants = _installed_swconst()
    preference, option = (
        int(constants.swDetailingDimToDimOffset),
        int(constants.swDetailingNoOptionSpecified),
    )
    extension = _early_bound(model.Extension, "IModelDocExtension")
    old_offset = float(extension.GetUserPreferenceDouble(preference, option))
    if not math.isfinite(old_offset) or old_offset <= 0:
        raise RuntimeError("parallel document spacing is invalid")
    for label, rows in before.items():
        _same_context(adapter, model, sheet, contexts)
        gain = 1.0 if label == "front" else 0.5
        requested = plans[label] / gain
        with _telemetry.span(
            "drawing.parallel_basic_spacing.align",
            view=label,
            native_gain=gain,
            requested_offset_m=requested,
        ):
            if not extension.SetUserPreferenceDouble(preference, option, requested):
                raise RuntimeError("parallel document spacing write rejected")
            if (
                float(extension.GetUserPreferenceDouble(preference, option))
                != requested
            ):
                raise RuntimeError(
                    "parallel document spacing did not retain requested value"
                )
            _select_and_align(adapter, views[label], rows)
    with _telemetry.span("drawing.parallel_basic_spacing.final", annotations=4):
        after = capture()
        clearances = {}
        for label, old_rows in before.items():
            new_rows = after[label]
            for (name, _), old, new in zip(
                PAIRS[label], old_rows, new_rows, strict=True
            ):
                _same_annotation(adapter.swApp, name, old, new)
            if not any(
                old.measured.anchor != new.measured.anchor
                or old.measured.native_strokes != new.measured.native_strokes
                for old, new in zip(old_rows, new_rows, strict=True)
            ):
                raise RuntimeError(
                    f"parallel native command did not move its named pair: {label}"
                )
            clearances[label] = observed_paper_clearance(
                basic_pair_geometry(
                    *(BasicLinearInk.from_bounds(row.measured) for row in new_rows)
                )
            )
        _same_context(adapter, model, sheet, contexts)
    for label, clearance in clearances.items():
        _telemetry.info(
            "Native BASIC pair spacing verified",
            view=label,
            paper_pitch_m=plans[label],
            line_body_clearance_m=clearance,
            native_gain=1.0 if label == "front" else 0.5,
            annotations=tuple(name for name, _ in PAIRS[label]),
        )
