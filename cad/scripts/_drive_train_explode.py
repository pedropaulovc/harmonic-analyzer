"""Author the drive-train's named exploded presentation (DRIVE_TRAIN_EXPLODED).

Mirrors ``build_summing_assembly._create_summing_explode``: the builder owns
the presentation, the drawing only consumes it. Each step of
``drive_train_assembly_spec.EXPLODE_STEPS`` is authored along a global axis,
read back as a world translation of exactly the intended instances, and the
assembly is collapsed again before save -- the saved operational pose (the
free kinematic model) is proven unchanged, transform for transform.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import _telemetry
from _assembly_patterns import ensure_global_pattern_axis
from _common import _early_bound
from drive_train_assembly_spec import (
    EXPLODED_VIEW_NAME,
    SOURCE_CONFIGURATION,
    Instance,
    plan_explode,
)


def _presentation_transform(component: Any) -> tuple[float, ...]:
    transform = _early_bound(component.GetTotalTransform(True), "IMathTransform")
    if transform is None:
        raise RuntimeError(f"{component.Name2}: missing total presentation transform")
    values = tuple(float(value) for value in transform.ArrayData)
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"{component.Name2}: invalid presentation transform {values!r}")
    return values


def _global_axes(adapter: Any, assembly: Any) -> dict[str, tuple[str, bool]]:
    """World axis name per key, and whether it points along +key."""
    axes = {}
    for index, key in enumerate("xyz"):
        axis_name = ensure_global_pattern_axis(adapter, key)
        feature = _early_bound(assembly.FeatureByName(axis_name), "IFeature")
        if feature is None or str(feature.GetTypeName2()) != "RefAxis":
            raise RuntimeError(f"{EXPLODED_VIEW_NAME}: missing reference axis {axis_name}")
        axis = _early_bound(feature.GetSpecificFeature2(), "IRefAxis")
        points = tuple(float(value) for value in axis.GetRefAxisParams())
        if len(points) != 6 or not all(math.isfinite(value) for value in points):
            raise RuntimeError(f"{axis_name}: invalid axis endpoints {points!r}")
        vector = tuple(points[i + 3] - points[i] for i in range(3))
        length = math.sqrt(sum(value * value for value in vector))
        if length <= 1e-12 or any(
            abs(vector[i] / length) > 1e-9 for i in range(3) if i != index
        ):
            raise RuntimeError(f"{axis_name}: not aligned with world {key.upper()}: {vector!r}")
        axes[key] = (axis_name, vector[index] > 0.0)
    return axes


def _create_named_view(model: Any, assembly: Any) -> None:
    from solidworks_mcp.adapters.com_variant import null_callout

    if not assembly.CreateExplodedView():
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: CreateExplodedView failed")
    names = tuple(assembly.GetExplodedViewNames2(SOURCE_CONFIGURATION) or ())
    if len(names) != 1:
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: unexpected created views {names!r}")
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        str(names[0]), "EXPLODEDVIEWS", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: cannot select created exploded view {names[0]!r}"
        )
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    if int(selection.GetSelectedObjectType3(1, 0)) != 43:  # swSelEXPLVIEWS
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: selection is not an exploded-view feature")
    feature = _early_bound(selection.GetSelectedObject6(1, 0), "IFeature")
    if feature is None or str(feature.GetTypeName2()) != "AsmExploder":
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: selected object is not an AsmExploder")
    feature.Name = EXPLODED_VIEW_NAME
    model.ClearSelection2(True)
    if not model.EditRebuild3() or tuple(
        assembly.GetExplodedViewNames2(SOURCE_CONFIGURATION) or ()
    ) != (EXPLODED_VIEW_NAME,):
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: exploded-view feature rename did not persist")


@_telemetry.traced("assembly.drive_train_explode")
def create_drive_train_explode(adapter: Any) -> None:
    """Author the released presentation and restore the free working model."""
    from solidworks_mcp.adapters.com_variant import null_callout

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    assembly = _early_bound(model, "IAssemblyDoc")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != SOURCE_CONFIGURATION:
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME} requires the builder's {SOURCE_CONFIGURATION} "
            f"configuration, not {configuration.Name!r}"
        )
    if int(assembly.GetExplodedViewCount2(SOURCE_CONFIGURATION)):
        raise RuntimeError("new drive-train assembly unexpectedly contains exploded views")

    components = tuple(
        _early_bound(component, "IComponent2")
        for component in (assembly.GetComponents(True) or ())
    )
    by_name = {str(component.Name2): component for component in components}
    if len(by_name) != len(components):
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: duplicate component identities")
    baseline = {name: _presentation_transform(c) for name, c in by_name.items()}
    instances = [
        Instance(
            name=name,
            stem=Path(str(component.GetPathName() or "")).stem.casefold(),
            origin_mm=tuple(value * 1000.0 for value in baseline[name][9:12]),
        )
        for name, component in by_name.items()
    ]
    try:
        plan = plan_explode(instances)
    except ValueError as exc:
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: {exc}") from exc
    expected = {name: [0.0, 0.0, 0.0] for name in by_name}
    axes = _global_axes(adapter, assembly)

    _create_named_view(model, assembly)
    if not assembly.ShowExploded2(True, EXPLODED_VIEW_NAME):
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: cannot activate authored view")

    try:
        for index in range(int(configuration.GetNumberOfExplodeSteps()) - 1, -1, -1):
            seed = _early_bound(configuration.GetExplodeStep(index), "IExplodeStep")
            if seed is None or not configuration.DeleteExplodeStep(str(seed.Name)):
                raise RuntimeError(f"{EXPLODED_VIEW_NAME}: cannot remove auto step {index}")
        if int(configuration.GetNumberOfExplodeSteps()) != 0:
            raise RuntimeError(f"{EXPLODED_VIEW_NAME}: auto steps remain")

        for step_index, (step, names) in enumerate(plan, 1):
            label = step.label
            distance = step.distance_mm / 1000.0
            with _telemetry.span(
                "assembly.drive_train_explode.step", label=label, moved=len(names)
            ):
                model.ClearSelection2(True)
                selection = _early_bound(model.SelectionManager, "ISelectionMgr")
                data = _early_bound(selection.CreateSelectData(), "ISelectData")
                if data is None:
                    raise RuntimeError(f"{label}: cannot create component selection data")
                data.Mark = 1
                if int(data.Mark) != 1:
                    raise RuntimeError(f"{label}: component selection mark did not persist")
                for name in names:
                    if not by_name[name].Select4(True, data, False):
                        raise RuntimeError(f"{label}: cannot select {name}")
                axis_name, positive = axes[step.axis]
                if not model.Extension.SelectByID2(
                    axis_name, "AXIS", 0.0, 0.0, 0.0, True, 2, null_callout(), 0
                ):
                    raise RuntimeError(
                        f"{label}: cannot select global direction {axis_name} with mark 2"
                    )
                result = configuration.AddExplodeStep2(
                    abs(distance), -1, (distance > 0.0) != positive, 0.0, -1, False, True, False
                )
                model.ClearSelection2(True)
                if not isinstance(result, tuple) or len(result) != 2:
                    raise RuntimeError(f"{label}: incomplete AddExplodeStep2 result {result!r}")
                raw_step, error = result
                if int(error) != 0 or raw_step is None:
                    raise RuntimeError(f"{label}: AddExplodeStep2 error {error!r}")
                native = _early_bound(raw_step, "IExplodeStep")
                step_name = f"DRIVE TRAIN {label.upper()}"
                native.Name = step_name
                if str(native.Name) != step_name or not model.EditRebuild3():
                    raise RuntimeError(f"{label}: step name/rebuild failed")
                if int(configuration.GetNumberOfExplodeSteps()) != step_index:
                    raise RuntimeError(f"{label}: authored step count is not {step_index}")
                actual = {
                    str(_early_bound(component, "IComponent2").Name2)
                    for component in (native.GetComponents() or ())
                }
                if actual != set(names) or abs(
                    float(native.ExplodeDistance) - abs(distance)
                ) > 1e-9:
                    raise RuntimeError(
                        f"{label}: step component/distance readback mismatch: {actual!r}"
                    )
                for name in names:
                    expected[name]["xyz".index(step.axis)] += distance
                mismatches = []
                for name, component in by_name.items():
                    current = _presentation_transform(component)
                    delta = tuple(current[i + 9] - baseline[name][i + 9] for i in range(3))
                    if any(abs(delta[i] - expected[name][i]) > 1e-7 for i in range(3)):
                        mismatches.append(
                            f"{name} moved {tuple(v * 1000.0 for v in delta)!r} mm, "
                            f"expected {tuple(v * 1000.0 for v in expected[name])!r}"
                        )
                    elif any(
                        abs(current[i] - baseline[name][i]) > 1e-9 for i in (*range(9), 12)
                    ):
                        mismatches.append(f"{name} presentation rotated or scaled")
                _telemetry.event(
                    "assembly.drive_train_explode.readback",
                    step=label,
                    moved=names,
                    axis=axis_name,
                    signed_distance_mm=step.distance_mm,
                    mismatches=tuple(mismatches),
                )
                if mismatches:
                    raise RuntimeError(f"{label}: " + "; ".join(mismatches))
    finally:
        primary_error = sys.exception()
        try:
            model.ClearSelection2(True)
            if not assembly.ShowExploded2(False, EXPLODED_VIEW_NAME) or not model.EditRebuild3():
                raise RuntimeError(
                    f"{EXPLODED_VIEW_NAME}: failed to restore the collapsed working model"
                )
            for name, component in by_name.items():
                current = _presentation_transform(component)
                operational = tuple(
                    float(value)
                    for value in _early_bound(component.Transform2, "IMathTransform").ArrayData
                )
                if len(operational) != 16 or any(
                    abs(values[i] - baseline[name][i]) > 1e-9
                    for values in (current, operational)
                    for i in range(16)
                ):
                    raise RuntimeError(
                        f"{EXPLODED_VIEW_NAME}: collapse changed the saved pose of {name}"
                    )
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(f"{EXPLODED_VIEW_NAME}: cleanup after authoring failure: {cleanup_error}")

    if int(configuration.GetNumberOfExplodeSteps()) != len(plan):
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: collapsed presentation lost authored steps")
    if tuple(assembly.GetExplodedViewNames2(SOURCE_CONFIGURATION) or ()) != (EXPLODED_VIEW_NAME,):
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: collapsed presentation lost the named view")
    if str(assembly.GetExplodedViewConfigurationName(EXPLODED_VIEW_NAME)) != SOURCE_CONFIGURATION:
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: named presentation is not owned by {SOURCE_CONFIGURATION}"
        )
    _telemetry.success(
        f"{EXPLODED_VIEW_NAME}: {len(plan)} native steps verified in world space; "
        f"all {len(by_name)} instances restored to the saved pose"
    )
