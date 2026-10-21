"""Isolate nominal supplier construction diagrams from every installed state.

Only explicitly named SUPPLIER_REFERENCE configurations are added. A native
configuration-local Body-Delete removes installed bodies there; callbacks add
hidden construction sketches, never copied bodies or substitute part shapes.
Every original configuration's solid/sheet signatures and feature suppression
are read before insertion and proved unchanged afterwards. The active original
configuration is restored even when authoring fails.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
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
            raise RuntimeError(f"installed body has invalid native mass properties: {values!r}")
        signatures.append((len(body.GetFaces() or ()), values))
    # GetBodies2 explicitly permits arbitrary enumeration order. In particular,
    # tiny COM noise must not sort two symmetric plates into opposite Z slots.
    return signatures


def _same_signature(actual: tuple, expected: tuple) -> bool:
    return actual[0] == expected[0] and all(
        math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-13)
        for a, b in zip(actual[1], expected[1], strict=True)
    )


def _body_bijection(
    candidates: Sequence[Sequence[int]], *, fixed: tuple[int, int] | None = None,
) -> tuple[int, ...] | None:
    """Find one complete correspondence, reserving an optional observed edge."""
    owners: list[int | None] = [None] * len(candidates)
    if fixed is not None:
        owners[fixed[1]] = fixed[0]

    def assign(observed: int, visited: set[int]) -> bool:
        for expected in candidates[observed]:
            if expected in visited:
                continue
            visited.add(expected)
            previous = owners[expected]
            if previous is None or (
                (fixed is None or previous != fixed[0]) and assign(previous, visited)
            ):
                owners[expected] = observed
                return True
        return False

    for observed in sorted(range(len(candidates)), key=lambda index: len(candidates[index])):
        if fixed is not None and observed == fixed[0]:
            continue
        if not assign(observed, set()):
            return None
    correspondence = [0] * len(candidates)
    for expected, observed in enumerate(owners):
        if observed is None:
            return None
        correspondence[observed] = expected
    return tuple(correspondence)


def _same_bodies(actual: Sequence[Any], expected: list, *, label: str, sheets: bool = False) -> None:
    observed = _signature(actual, sheets=sheets)
    candidates = [
        tuple(index for index, before in enumerate(expected) if _same_signature(after, before))
        for after in observed
    ]
    reason = None
    if len(observed) != len(expected):
        reason = f"body count {len(observed)} != {len(expected)}"
    else:
        correspondence = _body_bijection(candidates)
        if correspondence is None:
            reason = "no tolerance-preserving body bijection"
        else:
            for index, matched in enumerate(correspondence):
                feasible = [matched]
                for alternative in candidates[index]:
                    if alternative == matched or _body_bijection(
                        candidates, fixed=(index, alternative),
                    ) is None:
                        continue
                    # Floating tolerances are not transitive: two alternatives
                    # can each fit the chosen record without fitting each other.
                    if any(
                        not _same_signature(expected[previous], expected[alternative])
                        for previous in feasible
                    ):
                        reason = f"ambiguous non-equivalent body correspondence at observed {index}"
                        break
                    feasible.append(alternative)
                if reason is not None:
                    break
    if reason is not None:
        # Full native records survive in task.log even when a subsequent COM
        # disconnection prevents restoration or the forensic document harvest.
        raise RuntimeError(
            f"{label}: native bodies/topology changed during reference insertion: {reason}; "
            f"expected_records={expected!r}; observed_records={observed!r}; "
            f"candidate_expected_indices={candidates!r}"
        )


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


def _isolate(
    model: Any, name: str, kind: str, owner: str | None, configurations: Sequence[str],
) -> None:
    for configuration in configurations:
        suppressed = configuration != owner
        feature = _resolve_features(model, {name: kind}, configuration)[name]
        current = tuple(feature.IsSuppressed2(3, bstr_array([configuration])) or ())
        if current == (suppressed,):
            continue
        if not feature.SetSuppression2(
            0 if suppressed else 1, 3, bstr_array([configuration]),
        ):
            raise RuntimeError(f"{name}: cannot isolate supplier feature in {configuration}")
        # Suppression changes can replace native feature objects too.
        feature = _resolve_features(model, {name: kind}, configuration)[name]
        if tuple(feature.IsSuppressed2(3, bstr_array([configuration])) or ()) != (suppressed,):
            raise RuntimeError(f"{name}: wrong suppression in {configuration}")


def _features(model: Any, *, top_level: bool) -> dict[str, Any]:
    raw_features = _early_bound(model.FeatureManager, "IFeatureManager").GetFeatures(top_level)
    features = {}
    for raw in raw_features or ():
        feature = _early_bound(raw, "IFeature")
        name = str(_com_invoke(feature, "IFeature", "Name"))
        if not name or name in features:
            raise RuntimeError(f"native feature identity changed: duplicate/empty name {name!r}")
        features[name] = feature
    return features


def _resolve_features(
    model: Any, identities: Mapping[str, str], configuration: str,
) -> dict[str, Any]:
    """Resolve immutable name/type identities; never retain proxies across rebuilds."""
    try:
        current = _features(model, top_level=False)
    except Exception as error:
        raise RuntimeError(f"{configuration}: cannot reacquire native feature inventory") from error
    resolved = {}
    for name, expected_type in identities.items():
        feature = current.get(name)
        try:
            observed_type = None if feature is None else str(feature.GetTypeName2())
        except Exception as error:
            raise RuntimeError(
                f"{configuration}: {name!r} ({expected_type}) feature identity read failed"
            ) from error
        if observed_type != expected_type:
            raise RuntimeError(
                f"{configuration}: feature identity changed for {name!r}: "
                f"expected_type={expected_type!r}, observed_type={observed_type!r}"
            )
        resolved[name] = feature
    return resolved


def _suppression(
    model: Any, identities: Mapping[str, str], configuration: str,
) -> dict[str, tuple]:
    states = {}
    for name, feature in _resolve_features(model, identities, configuration).items():
        try:
            states[name] = tuple(feature.IsSuppressed2(3, bstr_array([configuration])) or ())
        except Exception as error:
            raise RuntimeError(
                f"{configuration}: {name!r} ({identities[name]}) suppression read failed"
            ) from error
    return states


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
    # Feature proxies are invalidatable across configuration switches/rebuilds.
    # Keep value identities only; every configuration proof reacquires its tree.
    originals = {
        name: str(feature.GetTypeName2())
        for name, feature in _features(model, top_level=False).items()
    }
    owned: dict[str, str] = {}
    pending_rename: tuple[str, str, str] | None = None
    snapshots = {}
    primary: BaseException | None = None

    def prove_originals() -> None:
        for name, (solids, sheets, suppression) in snapshots.items():
            _show(adapter, model, name, action="restore original")
            if not model.EditRebuild3():
                raise RuntimeError(f"cannot rebuild original configuration {name}")
            _same_bodies(_early_bound(model, "IPartDoc").GetBodies2(_SOLID_BODY, False) or (),
                         solids, label=name)
            _same_bodies(_early_bound(model, "IPartDoc").GetBodies2(_SHEET_BODY, False) or (),
                         sheets, label=f"{name} sheet bodies", sheets=True)
            observed_suppression = _suppression(model, originals, name)
            if observed_suppression != suppression:
                raise RuntimeError(
                    f"{name}: original feature suppression changed: "
                    f"expected={suppression!r}; observed={observed_suppression!r}"
                )

    try:
        for name in existing:
            _show(adapter, model, name, action="read original")
            # ShowConfiguration2 does not rebuild configurations dirtied by
            # newly authored member features. Compare settled state to settled
            # state, rather than a stale baseline against a rebuilt original.
            if not model.EditRebuild3():
                raise RuntimeError(f"cannot rebuild original baseline configuration {name}")
            snapshots[name] = (
                _signature(_bodies(model, count=body_count, label=name)),
                _signature(_early_bound(model, "IPartDoc").GetBodies2(_SHEET_BODY, False) or (),
                           sheets=True),
                _suppression(model, originals, name),
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
            if not model.EditRebuild3():
                raise RuntimeError(f"{state.name}: supplier source configuration rebuild failed")
            model.ClearSelection2(True)
            selection = _early_bound(model.SelectionManager, "ISelectionMgr").CreateSelectData()
            for index, body in enumerate(_bodies(model, count=body_count, label=state.name)):
                if not body.Select2(index > 0, selection):
                    raise RuntimeError(f"{state.name}: cannot select installed body")
            removed = _early_bound(model.FeatureManager, "IFeatureManager").InsertDeleteBody2(False)
            if removed is None:
                raise RuntimeError(f"{state.name}: cannot isolate installed bodies")
            removed = _early_bound(removed, "IFeature")
            removed_name = str(_com_invoke(removed, "IFeature", "Name"))
            removed_type = str(removed.GetTypeName2())
            owned[removed_name] = removed_type
            requested_name = f"{state.name}-RemoveInstalled"
            # A native setter can commit before its readback (or the setter
            # itself) raises. Retain both known aliases until readback succeeds.
            pending_rename = (removed_name, requested_name, removed_type)
            removed.Name = requested_name
            renamed = str(_com_invoke(removed, "IFeature", "Name"))
            del owned[removed_name]
            owned[renamed] = removed_type
            pending_rename = None
            if renamed != requested_name:
                raise RuntimeError(f"{state.name}: installed-body removal rename failed")
            model.ClearSelection2(True)
            _isolate(model, renamed, removed_type, state.name, configurations)
            # Configuration creation can add metadata folders. Only returned
            # Body-Delete features and features actually added by the callback
            # belong to this operation; a whole-tree entry delta is not ownership.
            before = set(_features(model, top_level=True))
            callback_failure: BaseException | None = None
            try:
                referenced = tuple(await state.references(adapter))
            except BaseException as error:
                callback_failure = error
                raise
            finally:
                try:
                    added = _features(model, top_level=True)
                    for name in set(added) - before:
                        owned[name] = str(added[name].GetTypeName2())
                except Exception as error:
                    if callback_failure is None:
                        raise
                    callback_failure.add_note(f"diagram ownership census also failed: {error}")
            if not referenced or len(set(referenced)) != len(referenced):
                raise RuntimeError(f"{state.name}: diagram needs distinct reference sketches")
            if set(added) - before != set(referenced):
                raise RuntimeError(f"{state.name}: callback added undeclared diagram features")
            for name in referenced:
                kind = owned[name]
                feature = _resolve_features(model, {name: kind}, state.name)[name]
                _require_diagram_sketch(feature, name, before=before, label=state.name)
                _isolate(model, name, kind, state.name, configurations)
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
        if pending_rename is not None:
            previous_name, requested_name, removed_type = pending_rename

            def recover_rename() -> None:
                current = _features(model, top_level=False)
                matches = [
                    name for name in dict.fromkeys((previous_name, requested_name))
                    if name in current
                ]
                if len(matches) != 1:
                    raise RuntimeError(
                        "cannot recover unique owned Body-Delete rename: "
                        f"aliases={(previous_name, requested_name)!r}, observed={matches!r}"
                    )
                recovered_name = matches[0]
                _resolve_features(
                    model, {recovered_name: removed_type}, "owned Body-Delete rename recovery",
                )
                del owned[previous_name]
                owned[recovered_name] = removed_type

            _cleanup(primary, recover_rename)
        for name, kind in reversed(tuple(owned.items())):
            _cleanup(
                primary,
                lambda name=name, kind=kind: _isolate(model, name, kind, None, existing),
            )
        _cleanup(primary, prove_originals)
        raise
    finally:
        _cleanup(primary, lambda: _show(adapter, model, installed, action="restore installed"))
