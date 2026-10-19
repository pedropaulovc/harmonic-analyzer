"""The named ``PN_EXPLODED`` presentation of pn-pen.SLDASM (MHA-PN-000).

Follows ``_pd_paper_drive_explode``: the builder owns the presentation, the
drawing only consumes it. Ordered translations and a common-axis stirrup turn
are read back as complete rigid poses of exactly the intended instances (every
other instance reads unmoved). The operational model is left collapsed with
its transforms unchanged.

``build_pn_pen_assembly`` calls :func:`create_pn_explode` only through its
canonical ``author_in_drawing_configurations`` call, so an edit confined to
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
from _explode_transforms import RigidTransform
from _feature_tree import name_last_feature
from _simplified_names import simplified_name
from _visibility import blank_reference_geometry, blank_sketch_feature
from pn_pen_assembly_spec import QUANTITIES
from pn_pen_explode_spec import (
    EXPLODE_STEPS,
    SOURCE_CONFIGURATION,
    RotationStep,
    STIRRUP_TURN,
    TranslationStep,
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


def _ensure_turn_axis(adapter: Any, model: Any, assembly: Any) -> tuple[str, bool]:
    """Hidden, updateable reference axis through the detached stirrup window.

    Its construction line has no inferencing relations, so EXPLODE refresh can
    update the pivot without leaving stale or duplicate reference geometry.
    """
    sketch_name, axis_name = "PNStirrupTurnLine", "PNStirrupTurnAxis"
    pivot = tuple(value / 1000.0 for value in STIRRUP_TURN.pivot_mm)
    ends = (pivot, (pivot[0], pivot[1] + 0.02, pivot[2]))
    manager = _early_bound(model.SketchManager, "ISketchManager")
    feature = _early_bound(assembly.FeatureByName(sketch_name), "IFeature")
    model.ClearSelection2(True)
    if feature is None:
        manager.Insert3DSketch(True)
        try:
            if manager.ActiveSketch is None:
                raise RuntimeError(f"{axis_name}: no active 3D sketch")
            manager.AddToDB = True
            line = _early_bound(manager.CreateLine(*ends[0], *ends[1]), "ISketchSegment")
            if line is None:
                raise RuntimeError(f"{axis_name}: cannot create pivot construction line")
            line.ConstructionGeometry = True
            if not bool(line.ConstructionGeometry):
                raise RuntimeError(f"{axis_name}: pivot line is not construction")
        finally:
            manager.AddToDB = False
            if manager.ActiveSketch is not None:
                manager.Insert3DSketch(True)
        name_last_feature(adapter, sketch_name)
        feature = _early_bound(assembly.FeatureByName(sketch_name), "IFeature")
    else:
        if str(feature.GetTypeName2()) != "3DProfileFeature" or not feature.Select2(False, 0):
            raise RuntimeError(f"{axis_name}: cannot edit pivot line sketch")
        model.EditSketch()
        try:
            sketch = _early_bound(manager.ActiveSketch, "ISketch")
            if sketch is None:
                raise RuntimeError(f"{axis_name}: pivot sketch did not enter edit mode")
            segments = tuple(sketch.GetSketchSegments() or ())
            if len(segments) != 1:
                raise RuntimeError(f"{axis_name}: pivot sketch does not contain one line")
            line = _early_bound(segments[0], "ISketchLine")
            for point, target in zip((line.GetStartPoint2(), line.GetEndPoint2()), ends):
                if point is None or not _early_bound(point, "ISketchPoint").SetCoords(*target):
                    raise RuntimeError(f"{axis_name}: cannot update pivot line")
        finally:
            if manager.ActiveSketch is not None:
                manager.Insert3DSketch(True)
    if feature is None:
        raise RuntimeError(f"{axis_name}: missing pivot sketch feature")
    sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
    segments = tuple(sketch.GetSketchSegments() or ())
    if len(segments) != 1:
        raise RuntimeError(f"{axis_name}: pivot sketch does not contain one line")
    line = _early_bound(segments[0], "ISketchSegment")
    axis_feature = _early_bound(assembly.FeatureByName(axis_name), "IFeature")
    if axis_feature is None:
        selection = _early_bound(model.SelectionManager, "ISelectionMgr")
        data = _early_bound(selection.CreateSelectData(), "ISelectData")
        model.ClearSelection2(True)
        if data is None or not line.Select4(False, data) or not model.InsertAxis2(True):
            raise RuntimeError(f"{axis_name}: cannot create pivot reference axis")
        axis_feature = _early_bound(selection.GetSelectedObject6(1, -1), "IFeature")
        if axis_feature is None or str(axis_feature.GetTypeName2()) != "RefAxis":
            raise RuntimeError(f"{axis_name}: created object is not a reference axis")
        axis_feature.Name = axis_name
    if str(axis_feature.GetTypeName2()) != "RefAxis" or not model.EditRebuild3():
        raise RuntimeError(f"{axis_name}: pivot reference axis rebuild failed")
    axis = _early_bound(axis_feature.GetSpecificFeature2(), "IRefAxis")
    points = tuple(float(value) for value in axis.GetRefAxisParams())
    if len(points) != 6 or not all(math.isfinite(value) for value in points):
        raise RuntimeError(f"{axis_name}: invalid axis readback {points!r}")
    if abs(points[4] - points[1]) < 1e-9 or any(
        abs(points[index] - pivot[index % 3]) > 1e-8 for index in (0, 2, 3, 5)
    ):
        raise RuntimeError(f"{axis_name}: axis is not vertical through detached pivot: {points!r}")
    blank_sketch_feature(model, feature, axis_name)
    blank_reference_geometry(adapter, ((axis_name, "AXIS"),))
    if int(axis_feature.Visible) != 1:
        raise RuntimeError(f"{axis_name}: presentation axis remains visible")
    return axis_name, points[4] > points[1]


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


def _require_step_order(
    configuration: Any, names: list[str], *, label: str, when: str
) -> None:
    actual = tuple(
        str(_early_bound(configuration.GetExplodeStep(index), "IExplodeStep").Name)
        for index in range(int(configuration.GetNumberOfExplodeSteps()))
    )
    if actual != tuple(names):
        raise RuntimeError(
            f"{label}: {when} native step order {actual!r} != {tuple(names)!r}"
        )


@_telemetry.traced("assembly.pn_explode")
def create_pn_explode(adapter: Any, configuration_name: str) -> None:
    """Author ``pn_pen_explode_EXPLODE_STEPS`` in the active ``configuration_name`` and
    leave the operational model collapsed (the ms-measuring-stick recipe).

    Run in Default and in Default Simplified
    (``_assembly.author_in_drawing_configurations``): a drawing view shows the
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
    expected = {
        name: RigidTransform.from_sw(values, label=f"{view_name}: {name} baseline")
        for name, values in baseline.items()
    }
    axes = _global_axes(adapter, assembly, view_name)
    turn_axis = _ensure_turn_axis(adapter, model, assembly)

    _create_named_view(model, assembly, configuration_name, view_name)
    if not assembly.ShowExploded2(True, view_name):
        raise RuntimeError(f"{view_name}: cannot activate authored view")
    step_names: list[str] = []
    try:
        for index in range(int(configuration.GetNumberOfExplodeSteps()) - 1, -1, -1):
            seed = _early_bound(configuration.GetExplodeStep(index), "IExplodeStep")
            if seed is None or not configuration.DeleteExplodeStep(str(seed.Name)):
                raise RuntimeError(f"{view_name}: cannot remove auto step {index}")
        if int(configuration.GetNumberOfExplodeSteps()) != 0:
            raise RuntimeError(f"{view_name}: auto steps remain")
        for step_index, plan in enumerate(EXPLODE_STEPS, 1):
            label = plan.label
            moved = [component for stem in plan.stems for component in groups[stem]]
            distance = (
                plan.distance_mm / 1000.0 if isinstance(plan, TranslationStep) else 0.0
            )
            angle = plan.angle_rad if isinstance(plan, RotationStep) else 0.0
            planned = plan.transform
            operation = RigidTransform(
                (*planned.values[:9], *(value / 1000.0 for value in planned.values[9:12]))
            )
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
                rotating = isinstance(plan, RotationStep)
                axis_name, positive = turn_axis if rotating else axes[plan.axis]
                if not model.Extension.SelectByID2(
                    axis_name, "AXIS", 0.0, 0.0, 0.0, True,
                    32 if rotating else 2, null_callout(), 0,
                ):
                    raise RuntimeError(f"{label}: cannot select direction {axis_name}")
                # Mark 32 is a COMMON assembly axis; RotateAboutOrigin=False
                # prevents the stirrup and screw rotating about separate origins.
                result = configuration.AddExplodeStep2(
                    abs(distance),
                    -1,
                    (distance > 0.0) != positive,
                    abs(angle),
                    -1,
                    (angle > 0.0) != positive if rotating else False,
                    not rotating,
                    False,
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
                step_names.append(step_name)
                if int(configuration.GetNumberOfExplodeSteps()) != step_index:
                    raise RuntimeError(f"{label}: authored step count is not {step_index}")
                actual = {
                    str(_early_bound(component, "IComponent2").Name2)
                    for component in (step.GetComponents() or ())
                }
                intended = {str(component.Name2) for component in moved}
                if actual != intended or abs(float(step.ExplodeDistance) - abs(distance)) > 1e-9:
                    raise RuntimeError(f"{label}: step component/distance readback mismatch: {actual!r}")
                if abs(float(step.RotationAngle) - abs(angle)) > 1e-9 or (
                    rotating
                    and (
                        bool(step.RotateAboutEachComponentOrigin)
                        or bool(step.AutoSpaceComponentsOnDrag)
                    )
                ):
                    raise RuntimeError(f"{label}: step rotation/origin readback mismatch")
                native = RigidTransform.from_sw(
                    step.GetComponentXform() or (), label=f"{label}: native step"
                )
                if any(abs(a - b) > 1e-8 for a, b in zip(native.values, operation.values)):
                    opposite_matches = False
                    if isinstance(plan, RotationStep):
                        opposite = RigidTransform.rotation(
                            tuple(float(key == plan.axis) for key in "xyz"),
                            -plan.angle_rad,
                            tuple(value / 1000.0 for value in plan.pivot_mm),
                        )
                        opposite_matches = all(
                            abs(a - b) <= 1e-8
                            for a, b in zip(native.values, opposite.values)
                        )
                    raise RuntimeError(
                        f"{label}: native step is not the planned world-space operation; "
                        f"{native.values!r} != {operation.values!r}; "
                        f"opposite_rotation_matches={opposite_matches}"
                    )
                for name in intended:
                    expected[name] = expected[name].then(operation)
                # Full pose of EVERY instance, including unmoved ones. This also
                # proves GetComponentXform's incremental order against native
                # presentation readback, not merely against another Python sum.
                for component in components:
                    name = str(component.Name2)
                    current = _presentation_transform(component)
                    if any(
                        abs(current[i] - value) > (1e-9 if i < 9 else 1e-7)
                        for i, value in enumerate(expected[name].values)
                    ) or abs(current[12] - baseline[name][12]) > 1e-9:
                        raise RuntimeError(
                            f"{label}: {name} native rigid pose {current!r} != "
                            f"{expected[name].values!r}; direction={axis_name}"
                        )
        _require_step_order(configuration, step_names, label=view_name, when="shown")
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
    _require_step_order(configuration, step_names, label=view_name, when="collapsed")
    if tuple(assembly.GetExplodedViewNames2(configuration_name) or ()) != (view_name,):
        raise RuntimeError(f"{view_name}: collapsed presentation lost named view")
    if str(assembly.GetExplodedViewConfigurationName(view_name)) != configuration_name:
        raise RuntimeError(f"{view_name}: named presentation is not owned by {configuration_name}")
    _telemetry.success(
        f"{view_name}: {len(EXPLODE_STEPS)} native steps verified in world space; "
        f"all {len(components)} instances restored"
    )
