"""Drawing edge-dimension authoring and measured-attachment verification.

Geometry-defined dimensions select edges and verify measured distances here
separately from imported model dimensions.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _early_bound
from _drawing_attachment import _is_same_attachment
import _telemetry


def add_edge_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float],
    p1: tuple[float, float],
    text_xy: tuple[float, float],
    label: str,
    orientation: str = "smart",
    entity_type: Literal["EDGE", "SILHOUETTE"] = "EDGE",
    entity_types: tuple[str, str] | None = None,
    entities: tuple[Any | None, Any | None] | None = None,
) -> Any:
    """Dimension across two view entities picked at explicit sheet points.

    The adapter's ``add_overall_dimension`` derives its picks from
    ``IView.GetOutline``, which pads the geometry with a whitespace margin, so
    its coordinate picks can miss.  Recipes know their layout exactly — the
    explicit sheet-meter points make the pick deterministic. Revolved outlines
    are drawing silhouettes rather than model edges, so callers must request
    ``SILHOUETTE`` for those flanks. Fails loud on either pick or dimension
    creation.

    ``orientation`` pins the measured direction: ``"smart"`` (default) lets
    SolidWorks infer from the picks and text position, while ``"horizontal"`` /
    ``"vertical"`` force the X/Y component — required when a hole is located by
    coordinate components off a datum rather than a slant centre distance (a
    slant reads ambiguous for holes not collinear with their datum).

    ``"angular"`` explicitly requests swAngularDimension through the documented
    AddSpecificDimension API. Exact mixed edge/owned-centreline selections keep
    their supplied selection points, so the caller can choose an on-sheet wedge.

    ``entities`` may identify either pick exactly; a ``None`` entry retains the
    corresponding coordinate pick. Explicit entities avoid ambiguous hit-test
    results when projected edges are close together.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    draw.ClearSelection2(True)
    for index, (x, y) in enumerate((p0, p1)):
        selected_type = entity_types[index] if entity_types else entity_type
        requested_entity = entities[index] if entities else None
        if requested_entity is None:
            selected = draw.Extension.SelectByID2(
                "", selected_type, x, y, 0.0, index > 0, 0, null_callout(), 0
            )
            location = f"at sheet ({x:g}, {y:g})"
        elif selected_type == "SILHOUETTE":
            manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
            selection_data = manager.CreateSelectData()
            selection_data.View = view
            selectable = _sw_type_info.early_bound_or_flag(
                requested_entity, "ISilhouetteEdge", "Select2"
            )
            selected = selectable.Select2(index > 0, selection_data)
            location = "by entity"
        elif selected_type == "SKETCHSEGMENT":
            # An owned view centreline (``ISketchSegment``, no ``IEntity``
            # face): a bore axis the print dimensions FROM, so a location
            # starts on the feature the shop indicates, not mid-air.
            manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
            selection_data = manager.CreateSelectData()
            selection_data.View = view
            selectable = _sw_type_info.early_bound_or_flag(
                requested_entity, "ISketchSegment", "Select4"
            )
            selected = selectable.Select4(index > 0, selection_data)
            location = "by centreline"
        else:
            manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
            selection_data = manager.CreateSelectData()
            selection_data.View = view
            selectable = _early_bound(requested_entity, "IEntity")
            selected = selectable.Select4(index > 0, selection_data)
            location = "by entity"
        if not selected:
            raise RuntimeError(
                f"failed to select {label} {selected_type.lower()} {index} {location}"
            )
        if requested_entity is not None:
            manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
            count = int(manager.GetSelectedObjectCount2(-1))
            if count != index + 1:
                raise RuntimeError(
                    f"{label} {selected_type.lower()} {index} changed the "
                    f"selection count to {count}"
                )
            if orientation == "angular" and manager.SetSelectionPoint2(
                index + 1, -1, x, y, 0.0
            ) is not True:
                raise RuntimeError(f"failed to set {label} angular selection point {index}")
    if orientation == "horizontal":
        dimension = draw.AddHorizontalDimension2(text_xy[0], text_xy[1], 0.0)
    elif orientation == "vertical":
        dimension = draw.AddVerticalDimension2(text_xy[0], text_xy[1], 0.0)
    elif orientation == "smart":
        dimension = draw.AddDimension2(text_xy[0], text_xy[1], 0.0)
    elif orientation == "angular":
        extension = _early_bound(draw.Extension, "IModelDocExtension")
        dimension, status = extension.AddSpecificDimension(
            text_xy[0], text_xy[1], 0.0, 3, 0  # swAngularDimension
        )
        if dimension is None or status != 0:
            raise RuntimeError(f"failed to add {label} angular dimension ({status})")
        model_dimension = _early_bound(
            _early_bound(dimension, "IDisplayDimension").GetDimension2(0), "IDimension"
        )
        if model_dimension is None:
            raise RuntimeError(f"failed to read {label} angular model dimension")
        model_dimension.DrivenState = 1  # swDimensionDriven
        if int(model_dimension.DrivenState) != 1:
            raise RuntimeError(f"{label} angular dimension did not become driven")
    else:
        raise ValueError(f"unknown dimension orientation {orientation!r}")
    draw.ClearSelection2(True)
    # No rebuild here: ``Add*Dimension2`` returns an evaluated display
    # dimension (its value, text and position read back at once -- every
    # ``_checked_dimension`` proves the value straight after this call), and
    # at ~0.45 s per ``EditRebuild3`` the per-dimension rebuild was 26 of
    # top-frame's 104 rebuilds. The finalizer rebuilds once before the
    # layout readbacks that do need settled text extents.
    if dimension is None:
        raise RuntimeError(f"failed to add the {label} {orientation} dimension")
    return dimension


@_telemetry.traced("drawing.find_edge_near", label_param="label")
def find_edge_near(
    adapter: Any,
    view: Any,
    xy: tuple[float, float],
    *,
    axis: Literal["x", "y"],
    label: str,
    span_m: float = 0.0015,
    step_m: float = 0.00025,
    entity_type: str = "EDGE",
) -> tuple[float, float]:
    """Refine an approximate sheet point to a selectable drawing edge."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate {label} drawing view")
    steps = int(round(span_m / step_m))
    offsets = sorted((index * step_m for index in range(-steps, steps + 1)), key=abs)
    for offset in offsets:
        x = xy[0] + (offset if axis == "x" else 0.0)
        y = xy[1] + (offset if axis == "y" else 0.0)
        draw.ClearSelection2(True)
        if not draw.Extension.SelectByID2(
            "", entity_type, x, y, 0.0, False, 0, null_callout(), 0
        ):
            continue
        draw.ClearSelection2(True)
        if offset:
            _telemetry.debug(f"{label}: edge found {offset * 1000:+.2f} mm off nominal")
        return x, y
    raise RuntimeError(f"{label}: no edge within {span_m * 1000:.1f} mm")


def assert_dimension_measures(
    adapter: Any,
    dimension: Any,
    *,
    expected_mm: float,
    label: str,
    entities: tuple[Any, Any] | None = None,
    entity_types: tuple[str, str] = ("EDGE", "EDGE"),
    tolerance_mm: float = 1e-5,
) -> float:
    """Fail unless a native ``Add*Dimension2`` result spans ``entities`` and
    measures ``expected_mm``.

    A drawing dimension reads whatever its two picks resolved to; when a
    coordinate hit-test lands on the neighbouring line the sheet prints a
    wrong locating number with no error (summing-lever's spring-hole start
    read 3.35 off the rib flange instead of 8.43 off the plate end, #1105).
    The value alone is a weak proof -- a 20-hole row has nineteen pairs at
    the same pitch and twenty rims at the same row X -- so the dimension's
    attached entities (``IAnnotation::GetAttachedEntities3``) must be the
    two the recipe named, each by ``_is_same_attachment``, and only then is
    ``IDimension.SystemValue`` checked against the spec constant. Returns the
    measured millimetres.

    ``entities=None`` is value-only: for a dimension the recipe cannot name
    by entity. The call site says why.
    """
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "GetDimension2", "GetAnnotation"
    )
    if entities is not None:
        annotation = _sw_type_info.early_bound_or_flag(
            display.GetAnnotation(),
            "IAnnotation",
            "GetAttachedEntities3",
            "GetAttachedEntityTypes",
            "IsDangling",
        )
        attached = list(annotation.GetAttachedEntities3() or ())
        types = tuple(int(t) for t in (annotation.GetAttachedEntityTypes() or ()))
        dangling = bool(annotation.IsDangling())
        unmatched = []
        for index, (expected, kind) in enumerate(zip(entities, entity_types)):
            match = next(
                (
                    item
                    for item in attached
                    if item is not None
                    and _is_same_attachment(adapter, item, expected, kind.upper())
                ),
                None,
            )
            if match is None:
                unmatched.append(index)
            else:
                attached.remove(match)
        if unmatched or attached or dangling:
            raise RuntimeError(
                f"{label} is not the dimension between its named entities: "
                f"unmatched picks={unmatched}, extra attachments={len(attached)}, "
                f"types={types}, dangling={dangling}"
            )
    native_dimension = display.GetDimension2(0)
    if native_dimension is None:
        raise RuntimeError(f"{label} has no native model dimension")
    model_dimension = _early_bound(native_dimension, "IDimension")
    value = model_dimension.SystemValue
    if value is None:
        raise RuntimeError(f"{label} has no measured native value")
    measured_mm = abs(float(value)) * 1000.0
    if not math.isfinite(measured_mm) or abs(measured_mm - expected_mm) > tolerance_mm:
        raise RuntimeError(
            f"{label} measures {measured_mm:g} mm, expected {expected_mm:g} mm: "
            "a pick resolved to the wrong entity"
        )
    return measured_mm
