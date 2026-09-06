"""Create an explicitly dimension-attached datum at its native sheet location.

The positive control is ``probe_datum_dimension_attachment.py --mode
stationary_attachment``: named DIMENSION selection alone did not bind the new
datum, while SetAttachedEntities with a typed dispatch array did. No coordinate
selection, alternate selector, symbol-position write or nominal frame is used.
This module belongs only in recipes that deliberately identify a datum feature
by its exact source size dimension, not an arbitrary nearby dimension.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from _common import _early_bound
from _drawing_annotation_bounds import annotation_box
from _drawing_common import null_callout
from _drawing_marks import _named_dimension
from _drawing_native_callouts import _final_symbol, _read_symbol
import _telemetry
from solidworks_mcp.adapters.com_variant import dispatch_array


@dataclass(frozen=True)
class _Source:
    model: Any
    display: Any
    dimension: Any
    annotation: Any
    context: tuple[Any, ...]


def _source(adapter, view, annotation, feature, name):
    app = adapter.swApp
    if (
        int(annotation.GetType()) != 4
        or int(annotation.OwnerType) != 0
        or int(annotation.Visible) != 1
        or annotation.IsDangling()
        or int(app.IsSame(annotation.Owner, view)) != 1
    ):
        raise RuntimeError("datum size dimension must belong to the exact visible view")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if display is None or display.IsReferenceDim():
        raise RuntimeError("datum feature requires an imported source size dimension")
    if int(app.IsSame(display.GetAnnotation(), annotation)) != 1:
        raise RuntimeError("datum source display does not round-trip to its annotation")
    raw_model = view.ReferencedDocument
    if raw_model is None:
        raise RuntimeError("datum source view has no resolved native part")
    model = _early_bound(raw_model, "IModelDoc2")
    if int(model.GetType()) != 1 or not model.GetPathName():
        raise RuntimeError("datum source must be a saved native part")
    _, expected = _named_dimension(SimpleNamespace(currentModel=model), feature, name)
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if dimension is None or int(app.IsSame(dimension, expected)) != 1:
        raise RuntimeError(
            "datum display does not represent the exact source feature dimension"
        )
    configuration = str(view.ReferencedConfiguration)
    values = tuple(dimension.GetSystemValue3(3, configuration) or ())
    if not configuration or len(values) != 1 or not math.isfinite(float(values[0])):
        raise RuntimeError(
            "datum source dimension has no exact configured system value"
        )
    if str(dimension.Name) != name or not str(dimension.FullName):
        raise RuntimeError("datum source dimension name differs from its manifest")
    context = (
        str(Path(model.GetPathName()).resolve()),
        configuration,
        str(dimension.Name),
        str(dimension.FullName),
        float(values[0]),
    )
    return _Source(model, display, dimension, annotation, context)


def _same_source(app, before, after):
    if before.context != after.context:
        raise RuntimeError("datum source dimension configuration/value changed")
    if any(
        int(app.IsSame(getattr(before, field), getattr(after, field))) != 1
        for field in ("model", "display", "dimension", "annotation")
    ):
        raise RuntimeError("datum exact source dimension identity changed")


def _datum_inventory(view):
    inventory = {}
    for raw in view.GetAnnotationsByType(2) or ():
        annotation = _early_bound(raw, "IAnnotation")
        tag = _early_bound(annotation.GetSpecificAnnotation(), "IDatumTag")
        label = str(tag.GetLabel())
        if not label or label in inventory:
            raise RuntimeError("datum view needs unique nonempty labels")
        inventory[label] = annotation
    return inventory


@_telemetry.traced("drawing.dimension_datum", label_param="label")
def add_dimension_datum(
    adapter: Any,
    view: Any,
    *,
    dimension_annotation: Any,
    source_feature: str,
    source_dimension: str,
    datum: str,
    label: str,
) -> Any:
    """Bind a datum to the manifest's exact native size dimension, then witness it."""
    if not datum or len(datum) > 2 or not source_feature or not source_dimension:
        raise ValueError("dimension datum needs a valid label and source manifest")
    model, app = adapter.currentModel, adapter.swApp
    if int(model.GetType()) != 3:
        raise RuntimeError("dimension datum creation requires an active drawing")
    drawing = _early_bound(model, "IDrawingDoc")
    registered = tuple(raw for sheet in drawing.GetViews() or () for raw in sheet[1:])
    if not any(int(app.IsSame(raw, view)) == 1 for raw in registered):
        raise RuntimeError("datum target view does not belong to the active drawing")
    annotation = _early_bound(dimension_annotation, "IAnnotation")
    source = _source(adapter, view, annotation, source_feature, source_dimension)
    before = _datum_inventory(view)
    if datum in before:
        raise RuntimeError(f"datum {datum} already exists in the target view")
    if not drawing.ActivateView(str(view.GetName2())):
        raise RuntimeError("datum source dimension view activation failed")
    model.ClearSelection2(True)
    selection_name = str(source.display.GetNameForSelection() or "")
    if not selection_name or not model.Extension.SelectByID2(
        selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("exact named source dimension selection failed")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    if (
        int(selection.GetSelectedObjectCount2(-1)) != 1
        or int(selection.GetSelectedObjectType3(1, -1)) != 14
        or int(app.IsSame(selection.GetSelectedObject6(1, -1), source.display)) != 1
    ):
        raise RuntimeError("datum selection is not the exact source display dimension")
    raw_tag = model.InsertDatumTag2()
    if raw_tag is None:
        raise RuntimeError("native dimension datum insertion failed")
    tag = _early_bound(raw_tag, "IDatumTag")
    if not tag.SetLabel(datum) or str(tag.GetLabel()) != datum:
        raise RuntimeError("native dimension datum label did not persist")
    native = _early_bound(tag.GetAnnotation(), "IAnnotation")
    model.ClearSelection2(True)
    if not model.EditRebuild3():
        raise RuntimeError("native datum insertion finalization failed")
    payload = dispatch_array([source.display])
    if getattr(payload, "varianttype", None) != 8201:  # VT_ARRAY | VT_DISPATCH
        raise RuntimeError("dimension datum needs a typed dispatch attachment array")
    if not native.SetAttachedEntities(payload):
        raise RuntimeError("explicit native dimension datum attachment failed")
    initial = None
    for phase in ("immediate", "rebuilt"):
        if phase == "rebuilt" and not model.EditRebuild3():
            raise RuntimeError("dimension datum attachment rebuild failed")
        fresh_source = _source(
            adapter, view, annotation, source_feature, source_dimension
        )
        _same_source(app, source, fresh_source)
        actual = _read_symbol(adapter, view, native, annotation_box)
        if (
            actual.entity_types != (14,)
            or int(app.IsSame(actual.entities[0], source.display)) != 1
        ):
            raise RuntimeError(
                "datum is not attached to the exact source size dimension"
            )
        inventory = _datum_inventory(view)
        if (
            inventory.keys() != before.keys() | {datum}
            or any(
                int(app.IsSame(old, inventory[key])) != 1 for key, old in before.items()
            )
            or int(app.IsSame(inventory[datum], native)) != 1
        ):
            raise RuntimeError("dimension datum creation changed another native datum")
        if initial is not None:
            _final_symbol(app, initial, initial, actual)
        initial = actual
        _telemetry.info(
            "native dimension datum witnessed",
            label=label,
            phase=phase,
            datum=datum,
            source_dimension=fresh_source.context,
            position=actual.position,
            frame=actual.frame.bounds,
            body=actual.body.bounds,
            specific_text_diagnostic=actual.specific_text,
        )
    return tag


def measured_gdt_envelope(adapter: Any, annotation: Any, _kind: int):
    """Callback for the explicit legacy audit; never a nominal anchor-based box."""
    return annotation_box(adapter, annotation).envelope.bounds
