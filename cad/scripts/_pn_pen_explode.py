"""The named ``PN_EXPLODED`` presentation of pn-pen.SLDASM (MHA-PN-00).

Follows ``_pd_paper_drive_explode``: the builder owns the presentation, the
drawing only consumes it. Each step of ``pn_pen_explode_spec.EXPLODE_STEPS``
is authored along a global axis, read back as a world translation of exactly
the intended instances (every other instance reads unmoved), and the
operational model is left collapsed with its transforms unchanged.

``build_pn_pen_assembly`` calls :func:`create_pn_explode` only through its
canonical ``save_assembly_and_images(author=...)`` call, so an edit confined to
this module and ``pn_pen_explode_spec`` takes the EXPLODE refresh tier
(``_refresh_tier.explode_plan``): the saved model is reopened and its named
explodes are re-authored, with no insert/mate loop.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import _telemetry
from _assembly_patterns import ensure_global_pattern_axis
from _com import _early_bound
from _simplified_names import simplified_name
from pn_pen_assembly_spec import QUANTITIES
from pn_pen_explode_spec import (
    EXPLODE_STEPS,
    SOURCE_CONFIGURATION,
    exploded_view_name,
)


def _presentation_transform(component: Any) -> tuple[float, ...]:
    transform = _early_bound(component.GetTotalTransform(True), "IMathTransform")
    if transform is None:
        raise RuntimeError(f"{component.Name2}: missing total presentation transform")
    values = tuple(float(value) for value in transform.ArrayData)
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"{component.Name2}: invalid presentation transform {values!r}")
    return values


def _global_axes(adapter: Any, assembly: Any, view_name: str) -> dict[str, tuple[str, bool]]:
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
            raise RuntimeError(f"{axis_name}: not aligned with world {key.upper()}: {vector!r}")
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
        raise RuntimeError(f"{view_name}: cannot select created exploded view {names[0]!r}")
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


@_telemetry.traced("assembly.pn_explode")
def create_pn_explode(adapter: Any, configuration_name: str) -> None:
    """Author ``pn_pen_explode_EXPLODE_STEPS`` in the active ``configuration_name`` and
    leave the operational model collapsed (the ms-measuring-stick recipe).

    Run in Default and in Default Simplified
    (``_assembly.save_assembly_and_images``): a drawing view shows the
    explode of the configuration it references."""
    from solidworks_mcp.adapters.com_variant import null_callout

    view_name = exploded_view_name(configuration_name)
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
        raise RuntimeError(f"{view_name}: {configuration_name} unexpectedly contains exploded views")

    components = tuple(
        _early_bound(component, "IComponent2")
        for component in (assembly.GetComponents(True) or ())
    )
    groups: dict[str, list[Any]] = {stem: [] for stem in QUANTITIES}
    for component in components:
        stem = Path(str(component.GetPathName() or "")).stem.casefold()
        if stem not in groups:
            raise RuntimeError(f"{view_name}: unexpected component {component.Name2}: {stem}")
        groups[stem].append(component)
    counts = {stem: len(group) for stem, group in groups.items()}
    if counts != QUANTITIES:
        raise RuntimeError(f"{view_name} component counts: {counts!r} != {QUANTITIES!r}")
    baseline = {str(component.Name2): _presentation_transform(component) for component in components}
    if len(baseline) != sum(QUANTITIES.values()):
        raise RuntimeError(f"{view_name}: duplicate component identities")
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
        for step_index, (label, stems, key, distance_mm) in enumerate(EXPLODE_STEPS, 1):
            moved = [component for stem in stems for component in groups[stem]]
            distance = distance_mm / 1000.0
            with _telemetry.span("assembly.pn_explode.step", label=label, moved=len(moved)):
                model.ClearSelection2(True)
                selection = _early_bound(model.SelectionManager, "ISelectionMgr")
                data = _early_bound(selection.CreateSelectData(), "ISelectData")
                if data is None:
                    raise RuntimeError(f"{label}: cannot create component selection data")
                data.Mark = 1
                for component in moved:
                    if not component.Select4(True, data, False):
                        raise RuntimeError(f"{label}: cannot select {component.Name2}")
                axis_name, positive = axes[key]
                if not model.Extension.SelectByID2(
                    axis_name, "AXIS", 0.0, 0.0, 0.0, True, 2, null_callout(), 0
                ):
                    raise RuntimeError(f"{label}: cannot select global direction {axis_name} with mark 2")
                # Explicit entity only; -1 omits the component-local manipulator.
                # Early-bound wrapper returns (IExplodeStep, error); omit [out].
                result = configuration.AddExplodeStep2(
                    abs(distance), -1, (distance > 0.0) != positive,
                    0.0, -1, False, True, False,
                )
                model.ClearSelection2(True)
                if not isinstance(result, tuple) or len(result) != 2:
                    raise RuntimeError(f"{label}: incomplete AddExplodeStep2 result {result!r}")
                raw_step, error = result
                if int(error) != 0 or raw_step is None:
                    raise RuntimeError(f"{label}: AddExplodeStep2 error {error!r}")
                step = _early_bound(raw_step, "IExplodeStep")
                # Distinct per explode: Default Simplified's copy carries the suffix.
                step_name = f"PN {label.upper()}"
                if configuration_name != SOURCE_CONFIGURATION:
                    step_name = simplified_name(step_name)
                step.Name = step_name
                if str(step.Name) != step_name or not model.EditRebuild3():
                    raise RuntimeError(f"{label}: step name/rebuild failed")
                if int(configuration.GetNumberOfExplodeSteps()) != step_index:
                    raise RuntimeError(f"{label}: authored step count is not {step_index}")
                actual = {
                    str(_early_bound(component, "IComponent2").Name2)
                    for component in (step.GetComponents() or ())
                }
                intended = {str(component.Name2) for component in moved}
                if actual != intended or abs(float(step.ExplodeDistance) - abs(distance)) > 1e-9:
                    raise RuntimeError(f"{label}: step component/distance readback mismatch: {actual!r}")
                for name in intended:
                    expected[name]["xyz".index(key)] += distance
                # Read every instance, the unmoved ones too.
                for component in components:
                    name = str(component.Name2)
                    current = _presentation_transform(component)
                    delta = tuple(current[i + 9] - baseline[name][i + 9] for i in range(3))
                    if any(abs(delta[i] - expected[name][i]) > 1e-7 for i in range(3)):
                        raise RuntimeError(
                            f"{label}: {name} world translation mm "
                            f"{tuple(value * 1000.0 for value in delta)!r} != "
                            f"{tuple(value * 1000.0 for value in expected[name])!r}; "
                            f"direction={axis_name}, signed distance={distance_mm:g} mm"
                        )
                    if any(abs(current[i] - baseline[name][i]) > 1e-9 for i in (*range(9), 12)):
                        raise RuntimeError(f"{label}: {name} presentation rotated or scaled")
    finally:
        primary_error = sys.exception()
        try:
            model.ClearSelection2(True)
            if not assembly.ShowExploded2(False, view_name) or not model.EditRebuild3():
                raise RuntimeError(f"{view_name}: failed to restore collapsed operational assembly")
            for component in components:
                name = str(component.Name2)
                current = _presentation_transform(component)
                transform = _early_bound(component.Transform2, "IMathTransform")
                operational = tuple(float(value) for value in transform.ArrayData)
                if len(operational) != 16 or any(
                    abs(values[i] - baseline[name][i]) > 1e-9
                    for values in (current, operational) for i in range(16)
                ):
                    raise RuntimeError(f"{view_name}: collapse changed operational transform of {name}")
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(f"{view_name}: cleanup after authoring failure: {cleanup_error}")
    if int(configuration.GetNumberOfExplodeSteps()) != len(EXPLODE_STEPS):
        raise RuntimeError(f"{view_name}: collapsed presentation lost authored steps")
    if tuple(assembly.GetExplodedViewNames2(configuration_name) or ()) != (view_name,):
        raise RuntimeError(f"{view_name}: collapsed presentation lost named view")
    if str(assembly.GetExplodedViewConfigurationName(view_name)) != configuration_name:
        raise RuntimeError(f"{view_name}: named presentation is not owned by {configuration_name}")
    _telemetry.success(
        f"{view_name}: {len(EXPLODE_STEPS)} native steps verified in world space; "
        f"all {len(components)} instances restored"
    )
