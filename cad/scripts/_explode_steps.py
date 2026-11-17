"""Author an assembly's named exploded presentation from declarative steps.

The builder owns the presentation; the drawing only consumes it. An assembly
supplies a plan -- ordered :class:`Step` rows, each naming the instances it
moves, a direction and a signed distance -- and :func:`author_explode_steps`
authors it with ``AddExplodeStep2`` in the active drawing configuration.
Every step is read back as a world translation of exactly the intended
instances (every other instance, native pattern followers and mated chains
included, must read unmoved), and the assembly is collapsed again before save:
the saved operational pose is proven unchanged, transform for transform.

Builders author in Default and in Default Simplified
(``_assembly.author_in_drawing_configurations``): a drawing view shows the
explode of the configuration it references, and the Simplified copy carries
the `` Simplified`` suffix on its view and step names (both are unique per
document).
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

import _component_order
import _telemetry
from _assembly_patterns import ensure_global_pattern_axis
from _com import _early_bound
from _simplified_names import simplified_name

_SW_SEL_EXPLVIEWS = 43

Transform = tuple[float, ...]


class Direction(NamedTuple):
    """A selectable explode direction: its entity name, whether the entity's
    own sense runs along the step's positive direction, and that direction as a
    world unit vector."""

    select_name: str
    positive: bool
    unit: tuple[float, float, float]


class Step(NamedTuple):
    """One native explode step: ``names`` move ``distance_mm`` (signed) along
    ``axis``, a world key (``"x"``, ``"y"``, ``"z"``) or a measured
    :class:`Direction`."""

    label: str
    names: tuple[str, ...]
    axis: str | Direction
    distance_mm: float


# (model, components in name order, their collapsed presentation transforms)
# -> the steps to author. A ValueError is reported against the view.
Plan = Callable[
    [Any, Sequence[tuple[str, Any]], Mapping[str, Transform]], Sequence[Step]
]


def exploded_view_name(view: str, source: str, configuration: str) -> str:
    """The named explode ``configuration`` owns: ``view`` in ``source``, its
    suffixed copy in ``source``'s simplified configuration."""
    if configuration == source:
        return view
    if configuration == simplified_name(source):
        return simplified_name(view)
    raise ValueError(f"{view}: no explode is authored in {configuration!r}")


def presentation_transform(component: Any) -> Transform:
    """The component's total presentation transform (the exploded pose while
    an explode is shown), as 16 finite values."""
    transform = _early_bound(component.GetTotalTransform(True), "IMathTransform")
    if transform is None:
        raise RuntimeError(f"{component.Name2}: missing total presentation transform")
    values = tuple(float(value) for value in transform.ArrayData)
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise RuntimeError(
            f"{component.Name2}: invalid presentation transform {values!r}"
        )
    return values


def axis_vector(feature: Any, label: str) -> tuple[float, float, float]:
    """The unit vector of reference-axis ``feature`` (named ``label``)."""
    if feature is None or str(feature.GetTypeName2()) != "RefAxis":
        raise RuntimeError(f"{label}: missing reference axis")
    axis = _early_bound(feature.GetSpecificFeature2(), "IRefAxis")
    points = tuple(float(value) for value in axis.GetRefAxisParams())
    if len(points) != 6 or not all(math.isfinite(value) for value in points):
        raise RuntimeError(f"{label}: invalid axis endpoints {points!r}")
    vector = (points[3] - points[0], points[4] - points[1], points[5] - points[2])
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-12:
        raise RuntimeError(f"{label}: degenerate axis endpoints {points!r}")
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def global_directions(adapter: Any, assembly: Any) -> dict[str, Direction]:
    """The native world axes (shared with component patterns) per key, each
    verified world-aligned, and whether it points along +key. Unlike
    manipulator indices, Mark=2 direction entities are independent of each
    selected component's local frame."""
    directions = {}
    for index, key in enumerate("xyz"):
        axis_name = ensure_global_pattern_axis(adapter, key)
        vector = axis_vector(
            _early_bound(assembly.FeatureByName(axis_name), "IFeature"), axis_name
        )
        if any(abs(vector[i]) > 1e-9 for i in range(3) if i != index):
            raise RuntimeError(
                f"{axis_name}: not aligned with world {key.upper()}: {vector!r}"
            )
        unit = tuple(1.0 if i == index else 0.0 for i in range(3))
        directions[key] = Direction(axis_name, vector[index] > 0.0, unit)
    return directions


def stem_groups(
    components: Sequence[tuple[str, Any]], quantities: Mapping[str, int]
) -> dict[str, list[str]]:
    """Instance names per part-file stem, refusing any stem or count off the
    ``quantities`` contract."""
    groups: dict[str, list[str]] = {stem: [] for stem in quantities}
    for name, component in components:
        stem = Path(str(component.GetPathName() or "")).stem.casefold()
        if stem not in groups:
            raise ValueError(f"unexpected component {name}: {stem}")
        groups[stem].append(name)
    counts = {stem: len(group) for stem, group in groups.items()}
    if counts != quantities:
        raise ValueError(f"component counts: {counts!r} != {dict(quantities)!r}")
    return groups


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
    if int(selection.GetSelectedObjectType3(1, 0)) != _SW_SEL_EXPLVIEWS:
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


def _readback(
    by_name: Mapping[str, Any],
    baseline: Mapping[str, Transform],
    expected: Mapping[str, Sequence[float]],
) -> tuple[dict[str, tuple[float, float, float]], list[str]]:
    """Every instance's world translation from the collapsed pose, and each
    one that moved off ``expected`` or rotated/scaled."""
    offsets = {}
    mismatches = []
    for name, component in by_name.items():
        current = presentation_transform(component)
        delta = tuple(current[i + 9] - baseline[name][i + 9] for i in range(3))
        offsets[name] = delta
        if any(abs(delta[i] - expected[name][i]) > 1e-7 for i in range(3)):
            mismatches.append(
                f"{name} moved {tuple(v * 1000.0 for v in delta)!r} mm, "
                f"expected {tuple(v * 1000.0 for v in expected[name])!r}"
            )
        elif any(abs(current[i] - baseline[name][i]) > 1e-9 for i in (*range(9), 12)):
            mismatches.append(f"{name} presentation rotated or scaled")
    return offsets, mismatches


def author_explode_steps(
    adapter: Any,
    configuration_name: str,
    *,
    view: str,
    source: str,
    step_prefix: str,
    plan: Plan,
) -> dict[str, tuple[float, float, float]]:
    """Author ``plan``'s steps as the named explode ``view`` of the active
    ``configuration_name`` (``source`` or its simplified copy), then restore the
    collapsed working model. Step ``label`` is named ``<step_prefix> <LABEL>``.

    Returns every instance's verified world translation (metres) at the last
    step: the aggregate exploded offsets."""
    from solidworks_mcp.adapters.com_variant import null_callout

    view_name = exploded_view_name(view, source, configuration_name)
    with _telemetry.span("assembly.explode", label=view_name):
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

        components = _component_order.by_name(assembly.GetComponents(True))
        by_name = dict(components)
        if len(by_name) != len(components):
            raise RuntimeError(f"{view_name}: duplicate component identities")
        baseline = {name: presentation_transform(c) for name, c in by_name.items()}
        try:
            steps = tuple(plan(model, components, baseline))
        except ValueError as exc:
            raise RuntimeError(f"{view_name}: {exc}") from exc
        expected = {name: [0.0, 0.0, 0.0] for name in by_name}
        offsets = {name: (0.0, 0.0, 0.0) for name in by_name}
        directions = global_directions(adapter, assembly)

        _create_named_view(model, assembly, configuration_name, view_name)
        if not assembly.ShowExploded2(True, view_name):
            raise RuntimeError(f"{view_name}: cannot activate authored view")

        try:
            for index in range(
                int(configuration.GetNumberOfExplodeSteps()) - 1, -1, -1
            ):
                seed = _early_bound(configuration.GetExplodeStep(index), "IExplodeStep")
                if seed is None or not configuration.DeleteExplodeStep(str(seed.Name)):
                    raise RuntimeError(f"{view_name}: cannot remove auto step {index}")
            if int(configuration.GetNumberOfExplodeSteps()) != 0:
                raise RuntimeError(f"{view_name}: auto steps remain")

            for step_index, step in enumerate(steps, 1):
                label = step.label
                distance = step.distance_mm / 1000.0
                with _telemetry.span(
                    "assembly.explode.step", label=label, moved=len(step.names)
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
                    for name in step.names:
                        if not by_name[name].Select4(True, data, False):
                            raise RuntimeError(f"{label}: cannot select {name}")
                    direction = (
                        step.axis
                        if isinstance(step.axis, Direction)
                        else directions[step.axis]
                    )
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
                    step_name = f"{step_prefix} {label.upper()}"
                    if configuration_name != source:
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
                        actual != set(step.names)
                        or abs(float(native.ExplodeDistance) - abs(distance)) > 1e-9
                    ):
                        raise RuntimeError(
                            f"{label}: step component/distance readback mismatch: {actual!r}"
                        )
                    for name in step.names:
                        for i in range(3):
                            expected[name][i] += distance * direction.unit[i]
                    # Read every instance, the unmoved ones too.
                    offsets, mismatches = _readback(by_name, baseline, expected)
                    _telemetry.event(
                        "assembly.explode.readback",
                        view=view_name,
                        step=label,
                        moved=step.names,
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
                if (
                    not assembly.ShowExploded2(False, view_name)
                    or not model.EditRebuild3()
                ):
                    raise RuntimeError(
                        f"{view_name}: failed to restore the collapsed working model"
                    )
                for name, component in by_name.items():
                    current = presentation_transform(component)
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

        if int(configuration.GetNumberOfExplodeSteps()) != len(steps):
            raise RuntimeError(
                f"{view_name}: collapsed presentation lost authored steps"
            )
        if tuple(assembly.GetExplodedViewNames2(configuration_name) or ()) != (
            view_name,
        ):
            raise RuntimeError(
                f"{view_name}: collapsed presentation lost the named view"
            )
        if (
            str(assembly.GetExplodedViewConfigurationName(view_name))
            != configuration_name
        ):
            raise RuntimeError(
                f"{view_name}: named presentation is not owned by {configuration_name}"
            )
        _telemetry.success(
            f"{view_name}: {len(steps)} native steps verified in world space; "
            f"all {len(by_name)} instances restored to the saved pose"
        )
        return offsets
