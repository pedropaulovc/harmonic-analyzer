"""The summing assembly's builder-owned named explode (SM_EXPLODED).

``create_summing_explode`` authors ``sm_summing_explode_spec.EXPLODE_STEPS``
in the active configuration along the assembly's native world axes, proves
every instance's world translation after each step and leaves the
operational model collapsed (the ms-measuring-stick pattern). A step that
names a knife-mount station moves only the instances on that side of the
lever's centre plane, read from the collapsed pose.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import _telemetry
import sm_summing_assembly_spec as spec
import sm_summing_explode_spec as explode
from _assembly_patterns import ensure_global_pattern_axis
from _com import _early_bound
from _simplified_names import simplified_name
from _cone_axis_constants import SUMMING_Z

_SW_SEL_EXPLVIEWS = 43


def summing_exploded_view_name(configuration: str) -> str:
    """The named explode ``configuration`` owns: exploded-view names are unique
    per document, so ``Default Simplified``'s copy carries the suffix too."""
    if configuration == explode.SOURCE_CONFIGURATION:
        return explode.EXPLODED_VIEW_NAME
    if configuration == simplified_name(explode.SOURCE_CONFIGURATION):
        return simplified_name(explode.EXPLODED_VIEW_NAME)
    raise ValueError(
        f"{explode.EXPLODED_VIEW_NAME}: no explode is authored in {configuration!r}"
    )


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


def _global_axes(
    adapter: Any, assembly: Any, view_name: str
) -> dict[str, tuple[str, bool]]:
    """The native world axes (shared with component patterns) and whether each
    points along +key; geometry and signed sense are verified."""
    axes = {}
    for index, key in enumerate("xyz"):
        axis_name = ensure_global_pattern_axis(adapter, key)
        feature = _early_bound(assembly.FeatureByName(axis_name), "IFeature")
        if feature is None or str(feature.GetTypeName2()) != "RefAxis":
            raise RuntimeError(f"{view_name}: missing reference axis {axis_name}")
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
        axes[key] = (axis_name, vector[index] > 0.0)
    return axes


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


def station_of(z_mm: float) -> str:
    """The knife-mount station an instance at world ``z_mm`` belongs to."""
    if abs(z_mm - SUMMING_Z) < 1.0:
        raise ValueError(f"z {z_mm:.3f} sits on the lever centre plane, not a station")
    return explode.STATIONS[0] if z_mm > SUMMING_Z else explode.STATIONS[1]


@_telemetry.traced("assembly.sm_explode")
def create_summing_explode(adapter: Any, configuration_name: str) -> None:
    """Author ``explode.EXPLODE_STEPS`` in the active ``configuration_name`` and
    leave the operational model collapsed.

    Run in Default and in Default Simplified
    (``_assembly.author_in_drawing_configurations``): a drawing view shows the
    explode of the configuration it references."""
    from solidworks_mcp.adapters.com_variant import null_callout

    view_name = summing_exploded_view_name(configuration_name)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    assembly = _early_bound(model, "IAssemblyDoc")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != configuration_name:
        raise RuntimeError(
            f"{view_name} requires the active {configuration_name} configuration, "
            f"not {configuration.Name!r}"
        )
    if int(assembly.GetExplodedViewCount2(configuration_name)):
        raise RuntimeError(
            f"{view_name}: {configuration_name} unexpectedly contains exploded views"
        )

    components = tuple(
        _early_bound(component, "IComponent2")
        for component in (assembly.GetComponents(True) or ())
    )
    groups: dict[str, list[Any]] = {stem: [] for stem in spec.QUANTITIES}
    for component in components:
        stem = Path(str(component.GetPathName() or "")).stem.casefold()
        if stem not in groups:
            raise RuntimeError(
                f"{view_name}: unexpected component {component.Name2}: {stem}"
            )
        groups[stem].append(component)
    counts = {stem: len(group) for stem, group in groups.items()}
    if counts != spec.QUANTITIES:
        raise RuntimeError(
            f"{view_name} component counts: {counts!r} != {spec.QUANTITIES!r}"
        )
    baseline = {
        str(component.Name2): _presentation_transform(component)
        for component in components
    }
    if len(baseline) != sum(spec.QUANTITIES.values()):
        raise RuntimeError(f"{view_name}: duplicate component identities")
    station_stems = {
        stem
        for _, stems, station, _, _ in explode.EXPLODE_STEPS
        if station
        for stem in stems
    }
    stations = {
        str(component.Name2): station_of(baseline[str(component.Name2)][11] * 1000.0)
        for stem in station_stems
        for component in groups[stem]
    }
    expected = {name: [0.0, 0.0, 0.0] for name in baseline}
    axes = _global_axes(adapter, assembly, view_name)

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
        for step_index, (label, stems, station, key, distance_mm) in enumerate(
            explode.EXPLODE_STEPS, 1
        ):
            moved = [
                component
                for stem in stems
                for component in groups[stem]
                if station is None or stations[str(component.Name2)] == station
            ]
            if station is not None and len(moved) != sum(
                spec.QUANTITIES[stem] // len(explode.STATIONS) for stem in stems
            ):
                raise RuntimeError(
                    f"{label}: {station} station holds {len(moved)} instances"
                )
            distance = distance_mm / 1000.0
            with _telemetry.span(
                "assembly.sm_explode.step",
                label=label,
                moved=len(moved),
                configuration=configuration_name,
                step_index=step_index,
            ):
                with _telemetry.span(
                    "assembly.sm_explode.step.selection", selected_expected=len(moved)
                ):
                    selected_attempted = selected_completed = 0
                    axis_attempted = axis_selected = False
                    try:
                        model.ClearSelection2(True)
                        selection = _early_bound(
                            model.SelectionManager, "ISelectionMgr"
                        )
                        data = _early_bound(selection.CreateSelectData(), "ISelectData")
                        if data is None:
                            raise RuntimeError(
                                f"{label}: cannot create component selection data"
                            )
                        data.Mark = 1
                        for component in moved:
                            selected_attempted += 1
                            if not component.Select4(True, data, False):
                                raise RuntimeError(
                                    f"{label}: cannot select {component.Name2}"
                                )
                            selected_completed += 1
                        axis_name, positive = axes[key]
                        axis_attempted = True
                        if not model.Extension.SelectByID2(
                            axis_name, "AXIS", 0.0, 0.0, 0.0, True, 2, null_callout(), 0
                        ):
                            raise RuntimeError(
                                f"{label}: cannot select global direction {axis_name} with mark 2"
                            )
                        axis_selected = True
                    finally:
                        _telemetry.annotate(
                            selected_attempted=selected_attempted,
                            selected_completed=selected_completed,
                            axis_attempted=int(axis_attempted),
                            axis_completed=int(axis_selected),
                        )
                with _telemetry.span(
                    "assembly.sm_explode.step.create",
                    create_calls=1,
                    step_name_state="unverified",
                ):
                    # Explicit entity only; -1 omits the component-local manipulator.
                    # Early-bound wrapper returns (IExplodeStep, error); omit [out].
                    result = configuration.AddExplodeStep2(
                        abs(distance),
                        -1,
                        (distance > 0.0) != positive,
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
                    _telemetry.annotate(add_explode_error=error)
                    if int(error) != 0 or raw_step is None:
                        raise RuntimeError(f"{label}: AddExplodeStep2 error {error!r}")
                    step = _early_bound(raw_step, "IExplodeStep")
                    # Distinct per explode: Default Simplified's copy carries the suffix.
                    step_name = f"SM {label.upper()}"
                    if configuration_name != explode.SOURCE_CONFIGURATION:
                        step_name = simplified_name(step_name)
                    step.Name = step_name
                    if str(step.Name) != step_name:
                        raise RuntimeError(f"{label}: step name/rebuild failed")
                    _telemetry.annotate(step_name_state="verified")
                # This phase includes the status observation and required rebuild.
                # An unreadable observation is not clean and must not prevent rebuilding.
                with _telemetry.span(
                    "assembly.sm_explode.step.rebuild",
                    rebuild_calls=0,
                    rebuild_state="not_completed",
                ):
                    try:
                        needs_rebuild_before = int(model.Extension.NeedsRebuild2)
                    except Exception as observation_error:
                        rebuild_attributes = {
                            "needs_rebuild_before_state": "unreadable",
                            "needs_rebuild_before_error_type": type(
                                observation_error
                            ).__name__,
                            "needs_rebuild_before_error_message": str(
                                observation_error
                            ),
                        }
                    else:
                        rebuild_attributes = {
                            "needs_rebuild_before_state": "measured",
                            "needs_rebuild_before": needs_rebuild_before,
                        }
                    _telemetry.annotate(rebuild_calls=1, **rebuild_attributes)
                    rebuilt = model.EditRebuild3()
                    _telemetry.annotate(
                        rebuild_state="succeeded" if rebuilt else "failed"
                    )
                    if not rebuilt:
                        raise RuntimeError(f"{label}: step name/rebuild failed")
                with _telemetry.span(
                    "assembly.sm_explode.step.metadata", membership_expected=len(moved)
                ):
                    actual_step_count = int(configuration.GetNumberOfExplodeSteps())
                    _telemetry.annotate(step_count_actual=actual_step_count)
                    if actual_step_count != step_index:
                        raise RuntimeError(
                            f"{label}: authored step count is not {step_index}"
                        )
                    actual = {
                        str(_early_bound(component, "IComponent2").Name2)
                        for component in (step.GetComponents() or ())
                    }
                    _telemetry.annotate(membership_count=len(actual))
                    intended = {str(component.Name2) for component in moved}
                    if (
                        actual != intended
                        or abs(float(step.ExplodeDistance) - abs(distance)) > 1e-9
                    ):
                        raise RuntimeError(
                            f"{label}: step component/distance readback mismatch: {actual!r}"
                        )
                with _telemetry.span(
                    "assembly.sm_explode.step.readback",
                    instances_expected=len(components),
                ):
                    transform_reads_attempted = transform_reads_completed = 0
                    readback_completed = False
                    try:
                        for name in intended:
                            expected[name]["xyz".index(key)] += distance
                        # Read every instance, the unmoved ones too.
                        for component in components:
                            name = str(component.Name2)
                            transform_reads_attempted += 1
                            current = _presentation_transform(component)
                            transform_reads_completed += 1
                            delta = tuple(
                                current[i + 9] - baseline[name][i + 9] for i in range(3)
                            )
                            if any(
                                abs(delta[i] - expected[name][i]) > 1e-7
                                for i in range(3)
                            ):
                                raise RuntimeError(
                                    f"{label}: {name} world translation mm "
                                    f"{tuple(value * 1000.0 for value in delta)!r} != "
                                    f"{tuple(value * 1000.0 for value in expected[name])!r}; "
                                    f"direction={axis_name}, signed distance={distance_mm:g} mm"
                                )
                            if any(
                                abs(current[i] - baseline[name][i]) > 1e-9
                                for i in (*range(9), 12)
                            ):
                                raise RuntimeError(
                                    f"{label}: {name} presentation rotated or scaled"
                                )
                        readback_completed = True
                    finally:
                        _telemetry.annotate(
                            transform_reads_attempted=transform_reads_attempted,
                            transform_reads_completed=transform_reads_completed,
                            proof_state=(
                                "completed" if readback_completed else "incomplete"
                            ),
                        )
    finally:
        primary_error = sys.exception()
        try:
            model.ClearSelection2(True)
            if not assembly.ShowExploded2(False, view_name) or not model.EditRebuild3():
                raise RuntimeError(
                    f"{view_name}: failed to restore collapsed operational assembly"
                )
            for component in components:
                name = str(component.Name2)
                current = _presentation_transform(component)
                transform = _early_bound(component.Transform2, "IMathTransform")
                operational = tuple(float(value) for value in transform.ArrayData)
                if len(operational) != 16 or any(
                    abs(values[i] - baseline[name][i]) > 1e-9
                    for values in (current, operational)
                    for i in range(16)
                ):
                    raise RuntimeError(
                        f"{view_name}: collapse changed operational transform of {name}"
                    )
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(
                f"{view_name}: cleanup after authoring failure: {cleanup_error}"
            )
    if int(configuration.GetNumberOfExplodeSteps()) != len(explode.EXPLODE_STEPS):
        raise RuntimeError(f"{view_name}: collapsed presentation lost authored steps")
    if tuple(assembly.GetExplodedViewNames2(configuration_name) or ()) != (view_name,):
        raise RuntimeError(f"{view_name}: collapsed presentation lost named view")
    if str(assembly.GetExplodedViewConfigurationName(view_name)) != configuration_name:
        raise RuntimeError(
            f"{view_name}: named presentation is not owned by {configuration_name}"
        )
    _telemetry.success(
        f"{view_name}: {len(explode.EXPLODE_STEPS)} native steps verified in world space; "
        f"all {len(components)} instances restored"
    )
