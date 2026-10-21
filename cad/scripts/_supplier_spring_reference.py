"""Isolate nominal supplier construction diagrams from every installed state.

Only explicitly named SUPPLIER_REFERENCE configurations are added. A native
configuration-local Body-Delete removes installed bodies there; callbacks add
hidden construction sketches, never copied bodies or substitute part shapes.
Every original configuration's solid/sheet signatures and feature suppression
are read before insertion and proved unchanged afterwards. The active original
configuration is restored even when authoring fails.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
import math
from typing import Any, Literal

from solidworks_mcp.adapters.com_variant import bstr_array

from _com import _com_invoke, _early_bound
from _dimensions import _dim_owner_feature, _feature_display_dimensions
from _rebuild import active_configuration_name

SUPPLIER_FREE_CONFIGURATION = "SUPPLIER_REFERENCE_FREE"
SUPPLIER_MAX_CONFIGURATION = "SUPPLIER_REFERENCE_MAX"
SUPPLIER_DIAGRAM_CONFIGURATION = "SUPPLIER_REFERENCE"
_SOLID_BODY, _SHEET_BODY = 0, 1  # swBodyType_e


@dataclass(frozen=True)
class ReferenceState:
    """Paused call signature retained; only zero-body diagram states are legal."""

    name: str
    author: Callable[[Any], Awaitable[None]] | None
    references: Callable[[Any], Awaitable[Sequence[str]]] | None = None
    body_count: int | None = None
    kind: Literal["diagram"] = "diagram"

    def __post_init__(self) -> None:
        if not self.name or not (
            self.name == "SUPPLIER_REFERENCE" or self.name.startswith("SUPPLIER_REFERENCE_")
        ):
            raise ValueError("supplier diagrams need an explicit SUPPLIER_REFERENCE configuration")
        if (self.kind != "diagram" or self.author is not None or self.body_count != 0
                or not callable(self.references)):
            raise ValueError(
                f"{self.name}: only kind='diagram', author=None, body_count=0 "
                "and a references callback are supported"
            )


def _bodies(model: Any, *, count: int, label: str) -> list[Any]:
    bodies = list(_early_bound(model, "IPartDoc").GetBodies2(_SOLID_BODY, False) or ())
    if len(bodies) != count:
        raise RuntimeError(f"{label}: {len(bodies)} solid bodies, expected {count}")
    return [_early_bound(body, "IBody2") for body in bodies]


def _require_bodiless(model: Any, *, label: str) -> None:
    part = _early_bound(model, "IPartDoc")
    for kind, noun in ((_SOLID_BODY, "solid"), (_SHEET_BODY, "sheet")):
        found = len(tuple(part.GetBodies2(kind, False) or ()))
        if found:
            raise RuntimeError(f"{label}: nominal dimension diagram holds {found} {noun} bodies")


def _signature(bodies: Sequence[Any], *, sheets: bool = False) -> list:
    signatures = []
    for raw in bodies:
        body = _early_bound(raw, "IBody2")
        values = tuple(float(value) for value in (body.GetMassProperties(1.0) or ()))
        if (len(values) != 12 or not all(map(math.isfinite, values))
                or values[3] < 0 or (not sheets and values[3] == 0)):
            raise RuntimeError("installed body has invalid native mass properties")
        signatures.append((len(body.GetFaces() or ()), values))
    return sorted(signatures)


def _same_bodies(actual: Sequence[Any], expected: list, *, label: str, sheets: bool = False) -> None:
    observed = _signature(actual, sheets=sheets)
    if len(observed) != len(expected) or any(
        faces != expected_faces
        or any(not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-13)
               for a, b in zip(values, expected_values, strict=True))
        for (faces, values), (expected_faces, expected_values)
        in zip(observed, expected, strict=True)
    ):
        raise RuntimeError(f"{label}: native bodies/topology changed during reference insertion")


def _show(adapter: Any, model: Any, name: str, *, action: str) -> None:
    if active_configuration_name(adapter, model) != name and not model.ShowConfiguration2(name):
        raise RuntimeError(f"cannot {action} configuration {name}")
    active = active_configuration_name(adapter, model)
    if active != name:
        raise RuntimeError(f"cannot {action} configuration {name}: {active!r} is active")


def _cleanup(primary: BaseException | None, step: Callable[[], None]) -> None:
    try:
        step()
    except Exception as error:
        if primary is None:
            raise
        primary.add_note(f"restoration also failed: {error}")


def _isolate(feature: Any, owner: str | None, configurations: Sequence[str]) -> None:
    for name in configurations:
        suppressed = name != owner
        if not feature.SetSuppression2(0 if suppressed else 1, 3, bstr_array([name])):
            raise RuntimeError(f"{feature.Name}: cannot isolate supplier feature in {name}")
        if tuple(feature.IsSuppressed2(3, bstr_array([name])) or ()) != (suppressed,):
            raise RuntimeError(f"{feature.Name}: wrong suppression in {name}")


def _features(model: Any, *, top_level: bool) -> dict[str, Any]:
    features = _early_bound(model.FeatureManager, "IFeatureManager").GetFeatures(top_level)
    return {str(_com_invoke(feature, "IFeature", "Name")): _early_bound(feature, "IFeature")
            for feature in features or ()}


def _suppression(features: dict[str, Any], configuration: str) -> dict[str, tuple]:
    return {name: tuple(feature.IsSuppressed2(3, bstr_array([configuration])) or ())
            for name, feature in features.items()}


def _require_diagram_sketch(feature: Any, name: str, *, before: set[str], label: str) -> None:
    if name in before or feature.GetTypeName2() not in ("ProfileFeature", "3DProfileFeature"):
        raise RuntimeError(f"{label}: diagram reference {name} is not a new sketch")
    if int(feature.Visible) != 1:  # swVisibilityStateHide
        raise RuntimeError(f"{label}: source reference sketch {name} must be hidden")
    sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
    segments = tuple(sketch.GetSketchSegments() or ())
    if not segments or any(not _early_bound(raw, "ISketchSegment").ConstructionGeometry
                           for raw in segments):
        raise RuntimeError(f"{label}: {name} must contain only construction geometry")
    for display in _feature_display_dimensions(feature):
        dimension = _com_invoke(display, "IDisplayDimension", "GetDimension2", 0)
        if _dim_owner_feature(dimension) == name and bool(
            _com_invoke(display, "IDisplayDimension", "MarkedForDrawing")
        ):
            return
    raise RuntimeError(f"{label}: diagram sketch {name} has no drawing-marked dimension")


async def add_supplier_reference_configurations(
    adapter: Any, states: Sequence[ReferenceState], *, body_count: int,
) -> None:
    """Add zero-solid/zero-sheet diagrams; never change original member identities."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    installed = active_configuration_name(adapter, model)
    existing = tuple(str(name) for name in (model.GetConfigurationNames() or ()))
    names = tuple(state.name for state in states)
    if (body_count < 1 or not states or installed not in existing
            or len(set(names)) != len(names) or any(name in existing for name in names)):
        raise ValueError("supplier states must be distinct new configurations of an installed part")
    originals = _features(model, top_level=False)
    baseline = set(_features(model, top_level=True))
    snapshots = {}
    primary: BaseException | None = None

    def prove_originals() -> None:
        for name, (solids, sheets, suppression) in snapshots.items():
            _show(adapter, model, name, action="restore original")
            if not model.EditRebuild3():
                raise RuntimeError(f"cannot rebuild original configuration {name}")
            _same_bodies(_bodies(model, count=body_count, label=name), solids, label=name)
            _same_bodies(_early_bound(model, "IPartDoc").GetBodies2(_SHEET_BODY, False) or (),
                         sheets, label=name, sheets=True)
            if _suppression(originals, name) != suppression:
                raise RuntimeError(f"{name}: original feature suppression changed")

    try:
        for name in existing:
            _show(adapter, model, name, action="read original")
            snapshots[name] = (
                _signature(_bodies(model, count=body_count, label=name)),
                _signature(_early_bound(model, "IPartDoc").GetBodies2(_SHEET_BODY, False) or (),
                           sheets=True),
                _suppression(originals, name),
            )
        _show(adapter, model, installed, action="restore installed")
        manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
        configurations = (*existing, *names)
        for state in states:
            configuration = manager.AddConfiguration2(
                state.name, "Nominal supplier diagram only; not a solid or assembly state", "",
                4, "", state.name, False,  # swConfigOption_SuppressByDefault
            )
            if configuration is None:
                raise RuntimeError(f"cannot create supplier configuration {state.name}")
        for state in states:
            _show(adapter, model, state.name, action="activate supplier")
            model.ClearSelection2(True)
            selection = _early_bound(model.SelectionManager, "ISelectionMgr").CreateSelectData()
            for index, body in enumerate(_bodies(model, count=body_count, label=state.name)):
                if not body.Select2(index > 0, selection):
                    raise RuntimeError(f"{state.name}: cannot select installed body")
            removed = _early_bound(model.FeatureManager, "IFeatureManager").InsertDeleteBody2(False)
            model.ClearSelection2(True)
            if removed is None:
                raise RuntimeError(f"{state.name}: cannot isolate installed bodies")
            removed = _early_bound(removed, "IFeature")
            removed.Name = f"{state.name}-RemoveInstalled"
            _isolate(removed, state.name, configurations)
            before = set(_features(model, top_level=False))
            referenced = tuple(await state.references(adapter))
            if not referenced or len(set(referenced)) != len(referenced):
                raise RuntimeError(f"{state.name}: diagram needs distinct reference sketches")
            added = _features(model, top_level=True)
            if set(added) - before != set(referenced):
                raise RuntimeError(f"{state.name}: callback added undeclared diagram features")
            for name in referenced:
                feature = added.get(name)
                if feature is None:
                    raise RuntimeError(f"{state.name}: missing reference feature {name}")
                _require_diagram_sketch(feature, name, before=before, label=state.name)
                _isolate(feature, state.name, configurations)
            if not model.EditRebuild3():
                raise RuntimeError(f"{state.name}: supplier configuration rebuild failed")
            _require_bodiless(model, label=state.name)
            configuration = _early_bound(model.GetConfigurationByName(state.name), "IConfiguration")
            configuration.AddRebuildSaveMark = True
            if not configuration.AddRebuildSaveMark:
                raise RuntimeError(f"{state.name}: rebuild-save mark did not persist")
        for state in states:
            _show(adapter, model, state.name, action="prove final supplier")
            if not model.EditRebuild3():
                raise RuntimeError(f"{state.name}: final supplier diagram rebuild failed")
            _require_bodiless(model, label=state.name)
        prove_originals()
    except BaseException as error:
        primary = error
        for name, feature in _features(model, top_level=True).items():
            if name not in baseline:
                _cleanup(primary, lambda feature=feature: _isolate(feature, None, existing))
        _cleanup(primary, prove_originals)
        raise
    finally:
        _cleanup(primary, lambda: _show(adapter, model, installed, action="restore installed"))
