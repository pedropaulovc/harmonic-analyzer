"""Native component patterns, imported only by builders that author patterns."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Any

import _telemetry
from _assembly import _ledger_record, assert_component_placed, component_transform
from _common import _early_bound, _read_member


_LOCAL_LINEAR_PATTERN = 108  # swFeatureNameID_e.swFmLocalLPattern
_LOCAL_CIRCULAR_PATTERN = 109  # swFeatureNameID_e.swFmLocalCirPattern
_GLOBAL_PATTERN_AXIS_PLANES = {
    "x": ("Top Plane", "Front Plane"),
    "y": ("Front Plane", "Right Plane"),
    "z": ("Top Plane", "Right Plane"),
}


class PatternDirection(StrEnum):
    FORWARD = "forward"
    REVERSE = "reverse"


def _top_features(model: Any) -> list[Any]:
    model = _early_bound(model, "IModelDoc2")
    features = []
    feature = _read_member(model, "FirstFeature")
    while feature is not None:
        feature = _early_bound(feature, "IFeature")
        features.append(feature)
        feature = feature.GetNextFeature()
    return features


@_telemetry.traced("assembly.pattern_axis", label_param="axis")
def ensure_global_pattern_axis(adapter: Any, axis: str) -> str:
    """Create/reuse an assembly reference axis aligned to global X, Y, or Z."""
    key = axis.lower()
    try:
        planes = _GLOBAL_PATTERN_AXIS_PLANES[key]
    except KeyError as exc:
        raise ValueError(f"pattern axis must be x, y, or z; got {axis!r}") from exc

    from solidworks_mcp.adapters.com_variant import null_callout

    model = adapter.currentModel
    asm_h = _early_bound(
        model, "IAssemblyDoc"
    )  # IAssemblyDoc for FeatureByName; keep `model` for ClearSelection2/Extension/SelectionManager
    name = f"PatternAxis{key.upper()}"
    existing = adapter._attempt(lambda: asm_h.FeatureByName(name), default=None)
    if existing is not None:
        return name

    model.ClearSelection2(True)
    for index, plane in enumerate(planes):
        selected = model.Extension.SelectByID2(
            plane,
            "PLANE",
            0.0,
            0.0,
            0.0,
            index > 0,
            0,
            null_callout(),
            0,
        )
        if not selected:
            raise RuntimeError(f"cannot select {plane} for global {key}-axis")
    if not model.InsertAxis2(True):
        raise RuntimeError(f"SOLIDWORKS rejected global {key}-axis creation")
    # InsertAxis2 selects the feature it just created. Read that identity
    # directly: reference geometry is inserted near the front of an assembly's
    # feature tree, so searching backward from the tail took 39-78 seconds on
    # large mechanisms and any fixed scan bound eventually failed.
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    created = adapter._attempt(
        lambda: selection.GetSelectedObject6(1, -1), default=None
    )
    if created is None:
        raise RuntimeError(f"cannot read newly-created global {key}-axis")
    created = _early_bound(created, "IFeature")
    if str(created.GetTypeName2()) != "RefAxis":
        raise RuntimeError(
            f"new global {key}-axis selected {created.GetTypeName2()!r}, expected RefAxis"
        )
    created.Name = name
    model.ClearSelection2(True)
    _telemetry.success(f"created assembly pattern axis {name}")
    return name


def _select_pattern_inputs(
    adapter: Any,
    seed_components: tuple[str, ...],
    direction_name: str,
    direction_type: str,
    direction2_name: str | None = None,
    direction2_type: str = "AXIS",
) -> None:
    from solidworks_mcp.adapters.com_variant import null_callout

    model = adapter.currentModel
    asm_h = _early_bound(
        model, "IAssemblyDoc"
    )  # IAssemblyDoc for GetComponentByName; keep `model` for ClearSelection2/Extension
    model.ClearSelection2(True)
    selected = model.Extension.SelectByID2(
        direction_name,
        direction_type,
        0.0,
        0.0,
        0.0,
        False,
        2,
        null_callout(),
        0,
    )
    if not selected:
        raise RuntimeError(
            f"cannot select pattern direction {direction_type} {direction_name!r}"
        )
    if direction2_name is not None:
        selected = model.Extension.SelectByID2(
            direction2_name,
            direction2_type,
            0.0,
            0.0,
            0.0,
            True,
            4,
            null_callout(),
            0,
        )
        if not selected:
            raise RuntimeError(
                "cannot select pattern direction 2 "
                f"{direction2_type} {direction2_name!r}"
            )
    for seed_component in seed_components:
        component = adapter._attempt(
            lambda name=seed_component: asm_h.GetComponentByName(name), default=None
        )
        if component is None or not component.Select2(True, 1):
            raise RuntimeError(
                f"cannot select pattern seed component {seed_component!r}"
            )


def _new_pattern_components(model: Any, before: set[str]) -> list[Any]:
    components = _early_bound(model, "IAssemblyDoc").GetComponents(False) or []
    return [
        component
        for component in components
        if str(_read_member(component, "Name2")) not in before
    ]


def assert_pattern_targets(
    adapter: Any,
    instances: Iterable[str],
    targets: Iterable[list[float]],
    rows: list[list[float]],
    label: str,
) -> None:
    """Match unordered native-pattern instances to authored poses and gate each."""
    unmatched = set(instances)
    for target in targets:
        matching = [
            name
            for name in unmatched
            if all(
                abs(
                    component_transform(adapter, name)[9 + axis] * 1000.0 - target[axis]
                )
                < 0.05
                for axis in range(3)
            )
        ]
        if len(matching) != 1:
            raise RuntimeError(f"{label} has {len(matching)} instances at {target}")
        name = matching[0]
        assert_component_placed(adapter, name, target, rows)
        _ledger_record(name, target, rows)
        unmatched.remove(name)
    if unmatched:
        raise RuntimeError(f"{label} has unexpected instances: {sorted(unmatched)}")


async def linear_component_pattern(
    adapter: Any,
    seed_components: Iterable[str],
    *,
    axis: str,
    spacing_mm: float,
    instances: int,
    direction: PatternDirection = PatternDirection.FORWARD,
    label: str = "linear fastener pattern",
) -> list[str]:
    """Pattern one or more seed components along a global assembly axis."""
    if instances < 2:
        raise ValueError("linear component pattern requires at least two instances")
    if spacing_mm <= 0.0:
        raise ValueError("linear component pattern spacing must be positive")
    seeds = tuple(seed_components)
    if not seeds:
        raise ValueError("linear component pattern requires at least one seed")
    if len(set(seeds)) != len(seeds):
        raise ValueError("linear component pattern seeds must be unique")

    model = adapter.currentModel
    asm_h = _early_bound(
        model, "IAssemblyDoc"
    )  # IAssemblyDoc for GetComponents; keep `model` for FeatureManager/ClearSelection2
    direction_name = ensure_global_pattern_axis(adapter, axis)
    before = {
        str(_read_member(component, "Name2"))
        for component in (asm_h.GetComponents(False) or [])
    }
    async with _telemetry.aspan(
        f"pattern {label}",
        kind="linear",
        seeds=",".join(seeds),
        axis=axis.lower(),
        instances=instances,
        spacing_mm=spacing_mm,
    ):
        _select_pattern_inputs(adapter, seeds, direction_name, "AXIS")
        manager = _early_bound(model.FeatureManager, "IFeatureManager")
        definition = manager.CreateDefinition(_LOCAL_LINEAR_PATTERN)
        if definition is None:
            raise RuntimeError("cannot create local linear pattern definition")
        definition = _early_bound(definition, "ILocalLinearPatternFeatureData")
        definition.D1ReverseDirection = direction is PatternDirection.REVERSE
        definition.D1Spacing = spacing_mm / 1000.0
        definition.D1TotalInstances = instances
        definition.D2PatternSeedOnly = False
        definition.D2ReverseDirection = False
        definition.D2Spacing = 0.001
        definition.D2TotalInstances = 1
        definition.SynchronizeFlexibleComponents = False
        feature = manager.CreateFeature(definition)
        model.ClearSelection2(True)
        if feature is None:
            raise RuntimeError(f"SOLIDWORKS rejected {label}")
        feature = _early_bound(feature, "IFeature")
        feature.Name = label

        created = _new_pattern_components(model, before)
        expected = len(seeds) * (instances - 1)
        if len(created) != expected:
            raise RuntimeError(
                f"{label} created {len(created)} components, expected {expected}"
            )
        names = []
        for component in created:
            component = _early_bound(component, "IComponent2")
            name = str(_read_member(component, "Name2"))
            if not component.IsPatternInstance():
                raise RuntimeError(f"{name} is not owned by the component pattern")
            names.append(name)
        _telemetry.success(f"{label}: created {len(names)} pattern instances")
        return names


async def grid_component_pattern(
    adapter: Any,
    seed_components: Iterable[str],
    *,
    axis1: str,
    spacing1_mm: float,
    instances1: int,
    axis2: str,
    spacing2_mm: float,
    instances2: int,
    direction1: PatternDirection = PatternDirection.FORWARD,
    direction2: PatternDirection = PatternDirection.FORWARD,
    label: str = "rectangular component pattern",
) -> list[str]:
    """Pattern seeds as one native two-direction rectangular grid."""
    if instances1 < 2 or instances2 < 2:
        raise ValueError("grid component pattern requires two instances per axis")
    if spacing1_mm <= 0.0 or spacing2_mm <= 0.0:
        raise ValueError("grid component pattern spacing must be positive")
    if axis1.lower() == axis2.lower():
        raise ValueError("grid component pattern axes must differ")
    seeds = tuple(seed_components)
    if not seeds:
        raise ValueError("grid component pattern requires at least one seed")
    if len(set(seeds)) != len(seeds):
        raise ValueError("grid component pattern seeds must be unique")

    model = adapter.currentModel
    asm_h = _early_bound(
        model, "IAssemblyDoc"
    )  # IAssemblyDoc for GetComponents; keep `model` for FeatureManager/ClearSelection2
    direction1_name = ensure_global_pattern_axis(adapter, axis1)
    direction2_name = ensure_global_pattern_axis(adapter, axis2)
    before = {
        str(_read_member(component, "Name2"))
        for component in (asm_h.GetComponents(False) or [])
    }
    async with _telemetry.aspan(
        f"pattern {label}",
        kind="grid",
        seeds=",".join(seeds),
        axis1=axis1.lower(),
        instances1=instances1,
        spacing1_mm=spacing1_mm,
        axis2=axis2.lower(),
        instances2=instances2,
        spacing2_mm=spacing2_mm,
    ):
        _select_pattern_inputs(
            adapter, seeds, direction1_name, "AXIS", direction2_name, "AXIS"
        )
        manager = _early_bound(model.FeatureManager, "IFeatureManager")
        definition = manager.CreateDefinition(_LOCAL_LINEAR_PATTERN)
        if definition is None:
            raise RuntimeError("cannot create local grid pattern definition")
        definition = _early_bound(definition, "ILocalLinearPatternFeatureData")
        definition.D1ReverseDirection = direction1 is PatternDirection.REVERSE
        definition.D1Spacing = spacing1_mm / 1000.0
        definition.D1TotalInstances = instances1
        definition.D2PatternSeedOnly = False
        definition.D2ReverseDirection = direction2 is PatternDirection.REVERSE
        definition.D2Spacing = spacing2_mm / 1000.0
        definition.D2TotalInstances = instances2
        definition.SynchronizeFlexibleComponents = False
        feature = manager.CreateFeature(definition)
        model.ClearSelection2(True)
        if feature is None:
            raise RuntimeError(f"SOLIDWORKS rejected {label}")
        feature = _early_bound(feature, "IFeature")
        feature.Name = label

        created = _new_pattern_components(model, before)
        expected = len(seeds) * (instances1 * instances2 - 1)
        if len(created) != expected:
            raise RuntimeError(
                f"{label} created {len(created)} components, expected {expected}"
            )
        names = []
        for component in created:
            component = _early_bound(component, "IComponent2")
            name = str(_read_member(component, "Name2"))
            if not component.IsPatternInstance():
                raise RuntimeError(f"{name} is not owned by the component pattern")
            names.append(name)
        _telemetry.success(f"{label}: created {len(names)} pattern instances")
        return names


async def circular_component_pattern(
    adapter: Any,
    seed_components: Iterable[str],
    *,
    axis_name: str,
    instances: int,
    direction: PatternDirection = PatternDirection.FORWARD,
    label: str = "circular fastener pattern",
) -> list[str]:
    """Pattern seed components equally through 360 degrees around a named axis."""
    if instances < 2:
        raise ValueError("circular component pattern requires at least two instances")
    seeds = tuple(seed_components)
    if not seeds:
        raise ValueError("circular component pattern requires at least one seed")
    if len(set(seeds)) != len(seeds):
        raise ValueError("circular component pattern seeds must be unique")

    model = adapter.currentModel
    asm_h = _early_bound(
        model, "IAssemblyDoc"
    )  # IAssemblyDoc for GetComponents; keep `model` for FeatureManager/ClearSelection2
    before = {
        str(_read_member(component, "Name2"))
        for component in (asm_h.GetComponents(False) or [])
    }
    async with _telemetry.aspan(
        f"pattern {label}",
        kind="circular",
        seeds=",".join(seeds),
        axis=axis_name,
        instances=instances,
    ):
        _select_pattern_inputs(adapter, seeds, axis_name, "AXIS")
        manager = _early_bound(model.FeatureManager, "IFeatureManager")
        definition = manager.CreateDefinition(_LOCAL_CIRCULAR_PATTERN)
        if definition is None:
            raise RuntimeError("cannot create local circular pattern definition")
        definition = _early_bound(definition, "ILocalCircularPatternFeatureData")
        definition.TotalInstances = instances
        definition.EqualSpacing = True
        definition.ReverseDirection = direction is PatternDirection.REVERSE
        definition.SynchronizeFlexibleComponents = False
        feature = manager.CreateFeature(definition)
        model.ClearSelection2(True)
        if feature is None:
            raise RuntimeError(f"SOLIDWORKS rejected {label}")
        feature = _early_bound(feature, "IFeature")
        feature.Name = label

        created = _new_pattern_components(model, before)
        expected = len(seeds) * (instances - 1)
        if len(created) != expected:
            raise RuntimeError(
                f"{label} created {len(created)} components, expected {expected}"
            )
        names = []
        for component in created:
            component = _early_bound(component, "IComponent2")
            name = str(_read_member(component, "Name2"))
            if not component.IsPatternInstance():
                raise RuntimeError(f"{name} is not owned by the component pattern")
            names.append(name)
        _telemetry.success(f"{label}: created {len(names)} pattern instances")
        return names
