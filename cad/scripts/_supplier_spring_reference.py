"""Source-authored stock states isolated from an installed purchased solid.

A ``kind="body"`` state's author runs in a transient native part, never a
downloaded vendor file; its complete bodies are copied without simplification
into the state's configuration. A ``kind="diagram"`` state has no author and
no body: its reference callback authors new, hidden, drawing-dimensioned
native sketches directly in the installed part, and the state must hold no
solid or sheet body. Either way a configuration-local Body-Delete removes the
installed bodies only in that state; no installed feature, dimension, or body
is edited.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
import math
from typing import Any, Literal

from solidworks_mcp.adapters.com_variant import bstr_array

from _check import check
from _com import _com_invoke, _early_bound
from _dimensions import _dim_owner_feature, _feature_display_dimensions
from _rebuild import active_configuration_name

SUPPLIER_FREE_CONFIGURATION = "Supplier-Free"
SUPPLIER_MAX_CONFIGURATION = "Supplier-Max"
SUPPLIER_DIAGRAM_CONFIGURATION = "Supplier-Dimensions"

# swBodyType_e: swSolidBody = 0, swSheetBody = 1.
_SOLID_BODY, _SHEET_BODY = 0, 1


@dataclass(frozen=True)
class ReferenceState:
    """One reference configuration, declared by ``kind``.

    ``kind="body"``: a callable ``author`` builds the bodies; ``body_count``
    is None (the installed count) or at least 1. ``kind="diagram"``: a
    nominal dimension diagram with ``author=None``, ``body_count=0`` and a
    ``references`` callback that authors hidden, dimensioned sketches.
    """

    name: str
    author: Callable[[Any], Awaitable[None]] | None
    # Return every new reference feature's name, so all are isolated too.
    references: Callable[[Any], Awaitable[Sequence[str]]] | None = None
    body_count: int | None = None
    kind: Literal["body", "diagram"] = "body"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("supplier reference state needs a configuration name")
        if self.kind == "diagram":
            if (
                self.author is not None
                or self.body_count != 0
                or not callable(self.references)
            ):
                raise ValueError(
                    f"{self.name}: a diagram state needs author=None, body_count=0 "
                    "and a references callback"
                )
        elif self.kind == "body":
            if not callable(self.author):
                raise ValueError(f"{self.name}: a body state needs a source author")
            if self.body_count is not None and self.body_count < 1:
                raise ValueError(
                    f"{self.name}: a body state needs at least one source body"
                )
            if self.references is not None and not callable(self.references):
                raise ValueError(f"{self.name}: references must be a callback")
        else:
            raise ValueError(f"{self.name}: unknown supplier state kind {self.kind!r}")


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
            raise RuntimeError(
                f"{label}: nominal dimension diagram holds {found} {noun} bodies"
            )


def _signature(bodies: Sequence[Any]) -> list[tuple[int, tuple[float, ...]]]:
    signatures = []
    for body in bodies:
        values = tuple(float(value) for value in (body.GetMassProperties(1.0) or ()))
        if len(values) != 12 or not all(map(math.isfinite, values)) or values[3] <= 0:
            raise RuntimeError(
                "supplier reference body has invalid native mass properties"
            )
        signatures.append((len(body.GetFaces() or ()), values))
    return sorted(signatures)


def _same_bodies(actual: Sequence[Any], expected: list, *, label: str) -> None:
    observed = _signature(actual)
    if len(observed) != len(expected) or any(
        faces != expected_faces
        or any(
            not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-13)
            for a, b in zip(values, expected_values, strict=True)
        )
        for (faces, values), (expected_faces, expected_values) in zip(
            observed, expected, strict=True
        )
    ):
        raise RuntimeError(
            f"{label}: native bodies/topology changed during reference insertion"
        )


def _show(adapter: Any, model: Any, name: str, *, action: str) -> None:
    """Make ``name`` active; ShowConfiguration2 refuses the already-active one."""
    if active_configuration_name(
        adapter, model
    ) != name and not model.ShowConfiguration2(name):
        raise RuntimeError(f"cannot {action} configuration {name}")
    active = active_configuration_name(adapter, model)
    if active != name:
        raise RuntimeError(
            f"cannot {action} configuration {name}: {active!r} is active"
        )


def _activate(adapter: Any, model: Any) -> None:
    # ISldWorks.ActivateDoc3 [out] Errors follows the adapter's exercised binding.
    activated, status = adapter.swApp.ActivateDoc3(str(model.GetTitle()), False, 1, 0)
    if activated is None or int(status) not in (0, 2):
        raise RuntimeError(f"cannot restore installed part document (status {status})")
    if int(adapter.swApp.IsSame(activated, model)) != 1:
        raise RuntimeError("restored document is not the installed part")
    adapter.currentModel = _early_bound(activated, "IModelDoc2")
    adapter.currentSketch = None
    adapter.currentSketchManager = None
    adapter._reset_sketch_entity_registry()


def _cleanup(primary: BaseException | None, step: Callable[[], None]) -> None:
    """Run a restoration step without hiding an earlier failure."""
    try:
        step()
    except Exception as error:
        if primary is None:
            raise
        primary.add_note(f"restoration also failed: {error}")


def _isolate(feature: Any, owner: str | None, configurations: Sequence[str]) -> None:
    """Unsuppress ``feature`` only in ``owner``; ``None`` suppresses it in all."""
    for name in configurations:
        suppressed = name != owner
        if not feature.SetSuppression2(0 if suppressed else 1, 3, bstr_array([name])):
            raise RuntimeError(
                f"{feature.Name}: cannot isolate supplier feature in {name}"
            )
        readback = tuple(feature.IsSuppressed2(3, bstr_array([name])) or ())
        if readback != (suppressed,):
            raise RuntimeError(
                f"{feature.Name}: wrong suppression in {name}: {readback!r}"
            )


def _features(model: Any, *, top_level: bool) -> dict[str, Any]:
    # IFeatureManager.GetFeatures: False adds every child feature to the top level.
    features = _early_bound(model.FeatureManager, "IFeatureManager").GetFeatures(
        top_level
    )
    return {
        str(_com_invoke(feature, "IFeature", "Name")): feature
        for feature in features or ()
    }


def _restore_originals(
    adapter: Any,
    model: Any,
    baseline: set[str],
    originals: dict[str, list],
    body_count: int,
) -> None:
    """After a failure, suppress every new top-level feature in each original
    configuration, then prove each still rebuilds to its original bodies."""
    problems = []
    for name, raw in _features(model, top_level=True).items():
        if name not in baseline:
            try:
                _isolate(_early_bound(raw, "IFeature"), None, tuple(originals))
            except Exception as error:
                problems.append(str(error))
    for name, signature in originals.items():
        try:
            _show(adapter, model, name, action="restore original")
            if not model.EditRebuild3():
                raise RuntimeError(f"cannot rebuild original configuration {name}")
            _same_bodies(
                _bodies(model, count=body_count, label=name), signature, label=name
            )
        except Exception as error:
            problems.append(str(error))
    if problems:
        raise RuntimeError(
            "original configurations not restored: " + "; ".join(problems)
        )


def _require_diagram_sketch(
    feature: Any, name: str, *, before: set[str], label: str
) -> None:
    """A diagram reference is a new, hidden sketch owning a drawing-marked dimension."""
    if name in before:
        raise RuntimeError(
            f"{label}: diagram reference {name} predates the diagram state"
        )
    if feature.GetTypeName2() not in ("ProfileFeature", "3DProfileFeature"):
        raise RuntimeError(f"{label}: diagram reference {name} is not a sketch")
    if int(feature.Visible) != 1:  # swVisibilityStateHide
        raise RuntimeError(f"{label}: source reference sketch {name} must be hidden")
    for display in _feature_display_dimensions(feature):
        dimension = _com_invoke(display, "IDisplayDimension", "GetDimension2", 0)
        if _dim_owner_feature(dimension) == name and bool(
            _com_invoke(display, "IDisplayDimension", "MarkedForDrawing")
        ):
            return
    raise RuntimeError(
        f"{label}: diagram sketch {name} has no drawing-marked dimension"
    )


async def add_supplier_reference_configurations(
    adapter: Any,
    states: Sequence[ReferenceState],
    *,
    body_count: int,
) -> None:
    """Add reference-only configurations; restore the existing active configuration.

    A body state's author takes only ``adapter`` and builds the complete
    source-grounded state into its empty current part. A diagram state has no
    author or scratch part. Reference callbacks run in the installed
    document's new state and return their feature names. A state need not be
    an extension spring or have a maximum-length companion. On failure every
    new top-level feature is suppressed in the original configurations, whose
    bodies are re-proven against their recorded signatures.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    installed = active_configuration_name(adapter, model)
    existing = tuple(str(name) for name in (model.GetConfigurationNames() or ()))
    names = tuple(state.name for state in states)
    if (
        body_count < 1
        or not states
        or not installed
        or len(set(names)) != len(names)
        or any(name in existing for name in names)
    ):
        raise ValueError(
            "supplier states must be distinct new configurations of an installed part"
        )
    original_by_configuration = {}
    primary: BaseException | None = None
    try:
        for name in existing:
            _show(adapter, model, name, action="read original")
            original_by_configuration[name] = _signature(
                _bodies(model, count=body_count, label=name)
            )
    except BaseException as error:
        primary = error
        raise
    finally:
        _cleanup(
            primary,
            lambda: _show(adapter, model, installed, action="restore installed"),
        )
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    configurations = (*existing, *names)
    features_by_state: dict[str, list[Any]] = {}
    # Everything added after this, including a failed callback's partial
    # features, is suppressed in the original configurations on failure.
    baseline = set(_features(model, top_level=True))
    try:
        # Make every state first so each new feature can be isolated immediately.
        # Options 4 (swConfigOption_SuppressByDefault) without DontActivate:
        # each new configuration becomes active.
        for state in states:
            configuration = manager.AddConfiguration2(
                state.name,
                "Supplier stock reference only; not an assembly state",
                "",
                4,
                "",
                state.name,
                False,
            )
            if configuration is None:
                raise RuntimeError(f"cannot create supplier configuration {state.name}")
        for state in states:
            diagram = state.kind == "diagram"
            copies: list[Any] = []
            expected: list = []
            if not diagram:
                check(f"create {state.name} source part", await adapter.create_part())
                scratch = _early_bound(adapter.currentModel, "IModelDoc2")
                authored: BaseException | None = None
                try:
                    await state.author(adapter)
                    source_bodies = _bodies(
                        scratch, count=state.body_count or body_count, label=state.name
                    )
                    expected = _signature(source_bodies)
                    copies = [body.Copy2(True) for body in source_bodies]
                    if any(body is None for body in copies):
                        raise RuntimeError(f"{state.name}: native body copy failed")
                except BaseException as error:
                    authored = error
                    raise
                finally:
                    _cleanup(
                        authored,
                        lambda: adapter.swApp.CloseDoc(str(scratch.GetTitle())),
                    )
                    _cleanup(authored, lambda: _activate(adapter, model))
            _show(adapter, model, state.name, action="activate supplier")
            model.ClearSelection2(True)
            selection = _early_bound(
                model.SelectionManager, "ISelectionMgr"
            ).CreateSelectData()
            for index, body in enumerate(
                _bodies(model, count=body_count, label="installed source")
            ):
                if not body.Select2(index > 0, selection):
                    raise RuntimeError(f"{state.name}: cannot select installed body")
            removed = _early_bound(
                model.FeatureManager, "IFeatureManager"
            ).InsertDeleteBody2(False)
            model.ClearSelection2(True)
            if removed is None:
                raise RuntimeError(f"{state.name}: cannot isolate installed bodies")
            removed = _early_bound(removed, "IFeature")
            removed.Name = f"{state.name}-RemoveInstalled"
            features = [removed]
            features_by_state[state.name] = features
            _isolate(removed, state.name, configurations)
            part = _early_bound(model, "IPartDoc")
            for index, body in enumerate(copies, 1):
                feature = part.CreateFeatureFromBody3(
                    body, False, 1
                )  # Check, never Simplify.
                if feature is None:
                    raise RuntimeError(
                        f"{state.name}: cannot insert source body {index}"
                    )
                feature = _early_bound(feature, "IFeature")
                feature.Name = f"{state.name}-Body{index}"
                features.append(feature)
                _isolate(feature, state.name, configurations)
            if state.references is not None:
                before = set(_features(model, top_level=False)) if diagram else set()
                referenced = tuple(await state.references(adapter))
                if diagram and (
                    not referenced or len(set(referenced)) != len(referenced)
                ):
                    raise RuntimeError(
                        f"{state.name}: nominal dimension diagram needs distinct reference sketches"
                    )
                for name in referenced:
                    raw = part.FeatureByName(name)
                    if raw is None:
                        raise RuntimeError(
                            f"{state.name}: missing reference feature {name}"
                        )
                    feature = _early_bound(raw, "IFeature")
                    if diagram:
                        _require_diagram_sketch(
                            feature, name, before=before, label=state.name
                        )
                    # IFeature.Visible 1 = swVisibilityStateHide.
                    elif (
                        feature.GetTypeName2() in ("ProfileFeature", "3DProfileFeature")
                        and int(feature.Visible) != 1
                    ):
                        raise RuntimeError(
                            f"{state.name}: source reference sketch {name} must be hidden"
                        )
                    features.append(feature)
                    _isolate(feature, state.name, configurations)
            if not model.EditRebuild3():
                raise RuntimeError(
                    f"{state.name}: supplier configuration rebuild failed"
                )
            if diagram:
                _require_bodiless(model, label=state.name)
            else:
                _same_bodies(
                    _bodies(
                        model, count=state.body_count or body_count, label=state.name
                    ),
                    expected,
                    label=state.name,
                )
            configuration = _early_bound(
                model.GetConfigurationByName(state.name), "IConfiguration"
            )
            configuration.AddRebuildSaveMark = True
            if not configuration.AddRebuildSaveMark:
                raise RuntimeError(f"{state.name}: rebuild-save mark did not persist")
        for name in existing:
            _show(adapter, model, name, action="restore original")
            for owner, features in features_by_state.items():
                for feature in features:
                    _isolate(feature, owner, (name,))
            if not model.EditRebuild3():
                raise RuntimeError(f"cannot rebuild original configuration {name}")
            _same_bodies(
                _bodies(model, count=body_count, label=name),
                original_by_configuration[name],
                label=name,
            )
    except BaseException as error:
        primary = error
        raise
    finally:
        _cleanup(primary, lambda: _activate(adapter, model))
        if primary is not None:
            _cleanup(
                primary,
                lambda: _restore_originals(
                    adapter,
                    model,
                    baseline,
                    original_by_configuration,
                    body_count,
                ),
            )
        _cleanup(
            primary,
            lambda: _show(adapter, model, installed, action="restore installed"),
        )
