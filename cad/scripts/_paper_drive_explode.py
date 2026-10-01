"""Author the paper drive's named exploded presentation (PAPER_DRIVE_EXPLODED).

Follows ``_drive_train_explode``: the builder owns the presentation, the
drawing only consumes it. Each step of ``paper_drive_explode_spec.EXPLODE_STEPS``
is authored along a global axis, read back as a world translation of exactly
the intended instances (every other instance, the chain links included, reads
unmoved), and the assembly is collapsed again before save -- the saved
operational pose is proven unchanged, transform for transform. The same steps
are authored in Default and in Default Simplified (as
``PAPER_DRIVE_EXPLODED Simplified``): a drawing view shows the explode of the
configuration it references, and the exploded sheet's view at 1:3 references
the teeth/thread-free one.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Mapping, NamedTuple

import _telemetry
from _assembly_patterns import ensure_global_pattern_axis
from _common import _early_bound
from _drawing_simplified import simplified_name
from paper_drive_explode_spec import (
    EXPLODED_VIEW_NAME,
    SOURCE_CONFIGURATION,
    Instance,
    Role,
    plan_explode,
)


class _Direction(NamedTuple):
    """A selectable global axis and whether its own sense runs along +key."""

    select_name: str
    positive: bool
    unit: tuple[float, float, float]


def _presentation_transform(component: Any) -> tuple[float, ...]:
    transform = _early_bound(component.GetTotalTransform(True), "IMathTransform")
    if transform is None:
        raise RuntimeError(f"{component.Name2}: missing total presentation transform")
    values = tuple(float(value) for value in transform.ArrayData)
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise RuntimeError(
            f"{component.Name2}: invalid presentation transform {values!r}"
        )
    return values


def exploded_view_name(configuration: str) -> str:
    """The named explode ``configuration`` owns: exploded-view names are unique
    per document, so ``Default Simplified``'s copy carries the suffix too."""
    if configuration == SOURCE_CONFIGURATION:
        return EXPLODED_VIEW_NAME
    if configuration == simplified_name(SOURCE_CONFIGURATION):
        return simplified_name(EXPLODED_VIEW_NAME)
    raise ValueError(
        f"{EXPLODED_VIEW_NAME}: no explode is authored in {configuration!r}"
    )


def _global_directions(adapter: Any, assembly: Any) -> dict[str, _Direction]:
    """World axis per key, and whether it points along +key."""
    directions = {}
    for index, key in enumerate("xyz"):
        axis_name = ensure_global_pattern_axis(adapter, key)
        feature = _early_bound(assembly.FeatureByName(axis_name), "IFeature")
        if feature is None or str(feature.GetTypeName2()) != "RefAxis":
            raise RuntimeError(
                f"{EXPLODED_VIEW_NAME}: missing reference axis {axis_name}"
            )
        axis = _early_bound(feature.GetSpecificFeature2(), "IRefAxis")
        points = tuple(float(value) for value in axis.GetRefAxisParams())
        if len(points) != 6 or not all(math.isfinite(value) for value in points):
            raise RuntimeError(f"{axis_name}: invalid axis endpoints {points!r}")
        vector = tuple(points[i + 3] - points[i] for i in range(3))
        length = math.sqrt(sum(value * value for value in vector))
        if length <= 1e-12 or any(
            abs(vector[i] / length) > 1e-9 for i in range(3) if i != index
        ):
            raise RuntimeError(
                f"{axis_name}: not aligned with world {key.upper()}: {vector!r}"
            )
        unit = tuple(1.0 if i == index else 0.0 for i in range(3))
        directions[key] = _Direction(axis_name, vector[index] > 0.0, unit)
    return directions


def _create_named_view(
    model: Any, assembly: Any, configuration_name: str, view_name: str
) -> None:
    from solidworks_mcp.adapters.com_variant import null_callout

    if not assembly.CreateExplodedView():
        raise RuntimeError(f"{view_name}: CreateExplodedView failed")
    names = tuple(assembly.GetExplodedViewNames2(configuration_name) or ())
    if len(names) != 1:
        raise RuntimeError(f"{view_name}: unexpected created views {names!r}")
    # Exploded views are configuration-tree AsmExploder features, not ordinary
    # assembly features discoverable through FeatureByName.
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        str(names[0]), "EXPLODEDVIEWS", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"{view_name}: cannot select created exploded view {names[0]!r}"
        )
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    if int(selection.GetSelectedObjectType3(1, 0)) != 43:  # swSelEXPLVIEWS
        raise RuntimeError(f"{view_name}: selection is not an exploded-view feature")
    feature = _early_bound(selection.GetSelectedObject6(1, 0), "IFeature")
    if feature is None or str(feature.GetTypeName2()) != "AsmExploder":
        raise RuntimeError(f"{view_name}: selected object is not an AsmExploder")
    feature.Name = view_name
    model.ClearSelection2(True)
    if not model.EditRebuild3() or tuple(
        assembly.GetExplodedViewNames2(configuration_name) or ()
    ) != (view_name,):
        raise RuntimeError(f"{view_name}: exploded-view feature rename did not persist")


@_telemetry.traced("assembly.paper_drive_explode")
def create_paper_drive_explode(
    adapter: Any, roles: Mapping[str, Role], configuration_name: str
) -> None:
    """Author the released presentation in the active ``configuration_name``
    and restore the working model.

    ``roles`` maps each fillister-screw instance to the joint the builder
    placed it in (guide or clip screw). The builder runs this in Default and
    in Default Simplified (``_assembly.author_in_drawing_configurations``):
    each owns its explode."""
    from solidworks_mcp.adapters.com_variant import null_callout

    view_name = exploded_view_name(configuration_name)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    assembly = _early_bound(model, "IAssemblyDoc")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != configuration_name:
        raise RuntimeError(
            f"{view_name} requires the active {configuration_name} "
            f"configuration, not {configuration.Name!r}"
        )
    if int(assembly.GetExplodedViewCount2(configuration_name)):
        raise RuntimeError(
            f"{view_name}: {configuration_name} unexpectedly contains exploded views"
        )

    components = tuple(
        _early_bound(component, "IComponent2")
        for component in (assembly.GetComponents(True) or ())
    )
    by_name = {str(component.Name2): component for component in components}
    if len(by_name) != len(components):
        raise RuntimeError(f"{view_name}: duplicate component identities")
    unknown_roles = sorted(set(roles) - set(by_name))
    if unknown_roles:
        raise RuntimeError(
            f"{view_name}: roles name absent components {unknown_roles!r}"
        )
    baseline = {name: _presentation_transform(c) for name, c in by_name.items()}
    instances = [
        Instance(
            name=name,
            stem=Path(str(component.GetPathName() or "")).stem.casefold(),
            role=roles.get(name),
        )
        for name, component in by_name.items()
    ]
    try:
        plan = plan_explode(instances)
    except ValueError as exc:
        raise RuntimeError(f"{view_name}: {exc}") from exc
    expected = {name: [0.0, 0.0, 0.0] for name in by_name}
    directions = _global_directions(adapter, assembly)

    _create_named_view(model, assembly, configuration_name, view_name)
    if not assembly.ShowExploded2(True, view_name):
        raise RuntimeError(f"{view_name}: cannot activate authored view")

    try:
        for index in range(int(configuration.GetNumberOfExplodeSteps()) - 1, -1, -1):
            seed = _early_bound(configuration.GetExplodeStep(index), "IExplodeStep")
            if seed is None or not configuration.DeleteExplodeStep(str(seed.Name)):
                raise RuntimeError(f"{view_name}: cannot remove auto step {index}")
        if int(configuration.GetNumberOfExplodeSteps()) != 0:
            raise RuntimeError(f"{view_name}: auto steps remain")

        for step_index, (step, names) in enumerate(plan, 1):
            label = step.label
            distance = step.distance_mm / 1000.0
            with _telemetry.span(
                "assembly.paper_drive_explode.step", label=label, moved=len(names)
            ):
                model.ClearSelection2(True)
                selection = _early_bound(model.SelectionManager, "ISelectionMgr")
                data = _early_bound(selection.CreateSelectData(), "ISelectData")
                if data is None:
                    raise RuntimeError(
                        f"{label}: cannot create component selection data"
                    )
                data.Mark = 1
                if int(data.Mark) != 1:
                    raise RuntimeError(
                        f"{label}: component selection mark did not persist"
                    )
                for name in names:
                    if not by_name[name].Select4(True, data, False):
                        raise RuntimeError(f"{label}: cannot select {name}")
                direction = directions[step.axis]
                if not model.Extension.SelectByID2(
                    direction.select_name,
                    "AXIS",
                    0.0,
                    0.0,
                    0.0,
                    True,
                    2,
                    null_callout(),
                    0,
                ):
                    raise RuntimeError(
                        f"{label}: cannot select direction {direction.select_name} with mark 2"
                    )
                # Explicit entity only; -1 omits the component-local manipulator.
                # Early-bound wrapper returns (IExplodeStep, error); omit [out].
                result = configuration.AddExplodeStep2(
                    abs(distance),
                    -1,
                    (distance > 0.0) != direction.positive,
                    0.0,
                    -1,
                    False,
                    True,
                    False,
                )
                model.ClearSelection2(True)
                if not isinstance(result, tuple) or len(result) != 2:
                    raise RuntimeError(
                        f"{label}: incomplete AddExplodeStep2 result {result!r}"
                    )
                raw_step, error = result
                if int(error) != 0 or raw_step is None:
                    raise RuntimeError(f"{label}: AddExplodeStep2 error {error!r}")
                native = _early_bound(raw_step, "IExplodeStep")
                # Distinct per explode: Default Simplified's copy carries the suffix.
                step_name = f"PAPER DRIVE {label.upper()}"
                if configuration_name != SOURCE_CONFIGURATION:
                    step_name = simplified_name(step_name)
                native.Name = step_name
                if str(native.Name) != step_name or not model.EditRebuild3():
                    raise RuntimeError(f"{label}: step name/rebuild failed")
                if int(configuration.GetNumberOfExplodeSteps()) != step_index:
                    raise RuntimeError(
                        f"{label}: authored step count is not {step_index}"
                    )
                actual = {
                    str(_early_bound(component, "IComponent2").Name2)
                    for component in (native.GetComponents() or ())
                }
                if (
                    actual != set(names)
                    or abs(float(native.ExplodeDistance) - abs(distance)) > 1e-9
                ):
                    raise RuntimeError(
                        f"{label}: step component/distance readback mismatch: {actual!r}"
                    )
                for name in names:
                    for i in range(3):
                        expected[name][i] += distance * direction.unit[i]
                # Read every instance, the unmoved ones too: native pattern
                # followers (the screws, the chain) must never move unasked.
                mismatches = []
                for name, component in by_name.items():
                    current = _presentation_transform(component)
                    delta = tuple(
                        current[i + 9] - baseline[name][i + 9] for i in range(3)
                    )
                    if any(abs(delta[i] - expected[name][i]) > 1e-7 for i in range(3)):
                        mismatches.append(
                            f"{name} moved {tuple(v * 1000.0 for v in delta)!r} mm, "
                            f"expected {tuple(v * 1000.0 for v in expected[name])!r}"
                        )
                    elif any(
                        abs(current[i] - baseline[name][i]) > 1e-9
                        for i in (*range(9), 12)
                    ):
                        mismatches.append(f"{name} presentation rotated or scaled")
                _telemetry.event(
                    "assembly.paper_drive_explode.readback",
                    step=label,
                    moved=names,
                    axis=direction.select_name,
                    signed_distance_mm=step.distance_mm,
                    mismatches=tuple(mismatches),
                )
                if mismatches:
                    raise RuntimeError(f"{label}: " + "; ".join(mismatches))
    finally:
        primary_error = sys.exception()
        try:
            model.ClearSelection2(True)
            if not assembly.ShowExploded2(False, view_name) or not model.EditRebuild3():
                raise RuntimeError(
                    f"{view_name}: failed to restore the collapsed working model"
                )
            for name, component in by_name.items():
                current = _presentation_transform(component)
                operational = tuple(
                    float(value)
                    for value in _early_bound(
                        component.Transform2, "IMathTransform"
                    ).ArrayData
                )
                if len(operational) != 16 or any(
                    abs(values[i] - baseline[name][i]) > 1e-9
                    for values in (current, operational)
                    for i in range(16)
                ):
                    raise RuntimeError(
                        f"{view_name}: collapse changed the saved pose of {name}"
                    )
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(
                f"{view_name}: cleanup after authoring failure: {cleanup_error}"
            )

    if int(configuration.GetNumberOfExplodeSteps()) != len(plan):
        raise RuntimeError(f"{view_name}: collapsed presentation lost authored steps")
    if tuple(assembly.GetExplodedViewNames2(configuration_name) or ()) != (view_name,):
        raise RuntimeError(f"{view_name}: collapsed presentation lost the named view")
    if str(assembly.GetExplodedViewConfigurationName(view_name)) != configuration_name:
        raise RuntimeError(
            f"{view_name}: named presentation is not owned by {configuration_name}"
        )
    _telemetry.success(
        f"{view_name}: {len(plan)} native steps verified in world space; "
        f"all {len(by_name)} instances restored to the saved pose"
    )
