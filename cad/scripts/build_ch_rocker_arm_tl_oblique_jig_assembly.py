r"""Reproduction script: ch-rocker-arm-tl-oblique-jig.SLDASM (MHA-CH-006-TL-000).

The rocker arm's oblique-trammel mill jig, a shop fixture (never in the
machine tree, ``_buildgraph.is_shop_fixture``): two of the one base bar (as
saved under rail 1 on -X, turned over under rail 2 on +X), a pivot block with
its pressed pivot pin on each rail's carriage, and the carrier riding the two
pins with its riser, its pressed HUB locator pin and its feed lever.

Authored in the MACHINE frame of ``ch_rocker_arm_tl_oblique_jig_assembly_spec``
(origin on the spindle at the table top, +X along the table, +Y toward the
column, +Z up) at the symmetric inner pass. Every pose is the spec's, derived
from the calculator ``ch_rocker_arm_tl_oblique_trammel_spec``. The bought
rails, carriages, bearings and dowel are not modelled; the drawing's BOM lists
them. The modelled pose is one position of the sweep, so every component is
fixed (the fix-all strategy of the other sub-assemblies): 0 DOF, fully defined.

The build names the spec's machine-frame views on the assembly
(``spec.VIEW_AXES``: the plan, the operator's elevation and the front-right
isometric), each read back, and the fitter drawing places those; the
standard views stay SolidWorks' own.

The named explode JIG_EXPLODED (Default and Default Simplified) is the fitter
drawing's exploded view: the disassembly order along global Z, each step
read back in world space and the saved pose proven unchanged.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_jig_assembly.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import _telemetry
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
from _assembly import (
    activate_assembly_contract,
    assembly_title_properties,
    assert_components_fully_defined,
    author_in_drawing_configurations,
    check_no_interference,
    place_component,
    save_assembly_and_images,
)
from _assembly_patterns import ensure_global_pattern_axis
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _drawing_marks import DRAWN_BY
from _interference_contracts import allowed_interference_pairs
from _named_views import octant_rotation
from _session import run_build
from _simplified_names import simplified_name
from _transforms import euler_from_rows

ASM_NAME = "ch-rocker-arm-tl-oblique-jig"
assert ASM_NAME == spec.ASM_NAME, (ASM_NAME, spec.ASM_NAME)


def _rows(rows: spec.Rows) -> list[list[float]]:
    return [list(row) for row in rows]


async def _place_fixed(
    adapter: Any,
    part: str,
    origin: tuple[float, float, float],
    rows: spec.Rows,
    *,
    label: str = "",
) -> str:
    """One fixed component at its exact machine-frame transform."""
    matrix = _rows(rows)
    return await place_component(
        adapter,
        part,
        list(origin),
        euler_from_rows(matrix),
        matrix,
        label=label,
    )


def jig_exploded_view_name(configuration: str) -> str:
    """The named explode ``configuration`` owns: exploded-view names are unique
    per document, so ``Default Simplified``'s copy carries the suffix too."""
    if configuration == spec.SOURCE_CONFIGURATION:
        return spec.EXPLODED_VIEW_NAME
    if configuration == simplified_name(spec.SOURCE_CONFIGURATION):
        return simplified_name(spec.EXPLODED_VIEW_NAME)
    raise ValueError(
        f"{spec.EXPLODED_VIEW_NAME}: no explode is authored in {configuration!r}"
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


@_telemetry.traced("assembly.jig_explode")
def _create_jig_explode(adapter: Any, configuration_name: str) -> None:
    """Author ``spec.EXPLODE_STEPS`` in the active ``configuration_name`` and
    leave the operational model collapsed.

    Run in Default and in Default Simplified
    (``_assembly.author_in_drawing_configurations``): a drawing view shows the
    explode of the configuration it references."""
    from solidworks_mcp.adapters.com_variant import null_callout

    view_name = jig_exploded_view_name(configuration_name)
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
        for step_index, (label, stems, key, distance_mm) in enumerate(
            spec.EXPLODE_STEPS, 1
        ):
            moved = [component for stem in stems for component in groups[stem]]
            distance = distance_mm / 1000.0
            with _telemetry.span(
                "assembly.jig_explode.step", label=label, moved=len(moved)
            ):
                model.ClearSelection2(True)
                selection = _early_bound(model.SelectionManager, "ISelectionMgr")
                data = _early_bound(selection.CreateSelectData(), "ISelectData")
                if data is None:
                    raise RuntimeError(
                        f"{label}: cannot create component selection data"
                    )
                data.Mark = 1
                for component in moved:
                    if not component.Select4(True, data, False):
                        raise RuntimeError(f"{label}: cannot select {component.Name2}")
                axis_name, positive = axes[key]
                if not model.Extension.SelectByID2(
                    axis_name, "AXIS", 0.0, 0.0, 0.0, True, 2, null_callout(), 0
                ):
                    raise RuntimeError(
                        f"{label}: cannot select global direction {axis_name} with mark 2"
                    )
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
                if int(error) != 0 or raw_step is None:
                    raise RuntimeError(f"{label}: AddExplodeStep2 error {error!r}")
                step = _early_bound(raw_step, "IExplodeStep")
                # Distinct per explode: Default Simplified's copy carries the suffix.
                step_name = f"JIG {label.upper()}"
                if configuration_name != spec.SOURCE_CONFIGURATION:
                    step_name = simplified_name(step_name)
                step.Name = step_name
                if str(step.Name) != step_name or not model.EditRebuild3():
                    raise RuntimeError(f"{label}: step name/rebuild failed")
                if int(configuration.GetNumberOfExplodeSteps()) != step_index:
                    raise RuntimeError(
                        f"{label}: authored step count is not {step_index}"
                    )
                actual = {
                    str(_early_bound(component, "IComponent2").Name2)
                    for component in (step.GetComponents() or ())
                }
                intended = {str(component.Name2) for component in moved}
                if (
                    actual != intended
                    or abs(float(step.ExplodeDistance) - abs(distance)) > 1e-9
                ):
                    raise RuntimeError(
                        f"{label}: step component/distance readback mismatch: {actual!r}"
                    )
                for name in intended:
                    expected[name]["xyz".index(key)] += distance
                # Read every instance, the unmoved ones too.
                for component in components:
                    name = str(component.Name2)
                    current = _presentation_transform(component)
                    delta = tuple(
                        current[i + 9] - baseline[name][i + 9] for i in range(3)
                    )
                    if any(abs(delta[i] - expected[name][i]) > 1e-7 for i in range(3)):
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
    if int(configuration.GetNumberOfExplodeSteps()) != len(spec.EXPLODE_STEPS):
        raise RuntimeError(f"{view_name}: collapsed presentation lost authored steps")
    if tuple(assembly.GetExplodedViewNames2(configuration_name) or ()) != (view_name,):
        raise RuntimeError(f"{view_name}: collapsed presentation lost named view")
    if str(assembly.GetExplodedViewConfigurationName(view_name)) != configuration_name:
        raise RuntimeError(
            f"{view_name}: named presentation is not owned by {configuration_name}"
        )
    _telemetry.success(
        f"{view_name}: {len(spec.EXPLODE_STEPS)} native steps verified in world space; "
        f"all {len(components)} instances restored"
    )


# swStandardViews_e.swIsometricView: SolidWorks' native *Isometric, the
# positive control for the matrix convention.
_SW_ISOMETRIC_VIEW = 7
_CONVENTION_TOLERANCE = 1e-3  # SolidWorks' own *Isometric reads 0.57738
_ROTATION_TOLERANCE = 1e-6


def _close(a: tuple[float, ...], b: tuple[float, ...], tolerance: float) -> bool:
    return len(a) == len(b) and max(abs(x - y) for x, y in zip(a, b)) <= tolerance


def _transposed(rotation: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(rotation[column + 3 * row] for column in range(3) for row in range(3))


@_telemetry.traced("assembly.jig_named_views")
def name_machine_views(adapter: Any) -> None:
    """Name ``spec.VIEW_AXES`` on the assembly, each read back.

    ``_named_views.name_octant_views``' recipe: the matrix convention is read
    off the native ``*Isometric`` (octant +X+Y+Z, model +Y up), each
    orientation composed through ``IModelView.Orientation3``, named, and its
    nine values read back through ``GetNamedViewRotation``."""
    from solidworks_mcp.adapters.com_variant import double_array

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    isometric = tuple(
        float(value) for value in model.GetStandardViewRotation(_SW_ISOMETRIC_VIEW)
    )
    row_form = octant_rotation(1, 1, 1)
    if _close(isometric, row_form, _CONVENTION_TOLERANCE):
        stored = lambda rotation: rotation  # noqa: E731
    elif _close(isometric, _transposed(row_form), _CONVENTION_TOLERANCE):
        stored = _transposed
    else:
        raise RuntimeError(
            f"jig views: *Isometric rotation {isometric} matches neither the "
            f"view-axes-as-rows form {row_form} nor its transpose"
        )
    view = _early_bound(model.ActiveView, "IModelView")
    for name, rows in spec.VIEW_AXES.items():
        rotation = stored(tuple(value for row in rows for value in row))
        transform = utility.CreateTransform(
            double_array([*rotation, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        )
        if transform is None:
            raise RuntimeError(f"jig views: CreateTransform refused {name!r}")
        view.Orientation3 = transform
        model.NameView(name)
        readback = tuple(
            float(value) for value in (extension.GetNamedViewRotation(name) or ())
        )
        if not _close(readback, rotation, _ROTATION_TOLERANCE):
            raise RuntimeError(
                f"jig views: {name!r} read back {readback}, expected {rotation}"
            )
        _telemetry.event("assembly.named_view", view=name)
    model.ShowNamedView2("*Isometric", _SW_ISOMETRIC_VIEW)


async def build(adapter) -> dict[str, str]:
    # Free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    check("create_assembly", await adapter.create_assembly())

    # The base bars first (SolidWorks fixes the first insert): the one bar
    # part, as saved under rail 1 on -X and turned over (180° about its long
    # axis) under rail 2 on +X, each from RAIL_NEAR_S along its rail.
    for rail, (origin, rows) in zip(spec.RAILS, spec.BASE_BAR_PLACEMENTS):
        turned = " turned over" if spec.TURNED_OVER[rail] else ""
        await _place_fixed(
            adapter,
            "ch-rocker-arm-tl-oblique-base-bar",
            origin,
            rows,
            label=f"base bar rail {rail}{turned}",
        )
    # Each pivot block on its (unmodelled) carriage's top plane, the carriage
    # at the symmetric inner-pass station; each pivot pin pressed through the
    # block's two bearings, collar on the upper inner race.
    for origin, rows in spec.PIVOT_BLOCK_PLACEMENTS:
        await _place_fixed(
            adapter, "ch-rocker-arm-tl-oblique-pivot-block", origin, rows
        )
    for origin in spec.PIVOT_PIN_ORIGINS:
        await _place_fixed(
            adapter, "ch-rocker-arm-tl-oblique-pivot-pin", origin, spec.PIN_ROWS
        )
    # The carrier on the two pin collars, A1/B1 on the pins; the riser on its
    # top; the HUB pin pressed up from under it; the lever bolted on top.
    await _place_fixed(
        adapter,
        "ch-rocker-arm-tl-oblique-carrier",
        spec.CARRIER_ORIGIN,
        spec.CARRIER_ROWS,
    )
    await _place_fixed(
        adapter, "ch-rocker-arm-tl-oblique-riser", spec.RISER_ORIGIN, spec.RISER_ROWS
    )
    await _place_fixed(
        adapter,
        "ch-rocker-arm-tl-oblique-hub-pin",
        spec.HUB_PIN_ORIGIN,
        spec.HUB_PIN_ROWS,
    )
    await _place_fixed(
        adapter,
        "ch-rocker-arm-tl-oblique-feed-lever",
        spec.FEED_LEVER_ORIGIN,
        spec.FEED_LEVER_ROWS,
    )
    _telemetry.info(
        f"jig at the {spec.PASS} pass, theta {spec.THETA:g}: pins at station "
        f"{spec.PIN_STATION:.3f}, carriages at {spec.CARRIAGE_STATION:.3f}; "
        f"carrier underside Z {spec.trammel.CARRIER_UNDERSIDE_Z:.1f}, "
        f"HUB pin Z {spec.HUB_HEAD_BOTTOM_Z:.1f}..{spec.HUB_PIN_TOP_Z:.1f}"
    )

    assert_components_fully_defined(adapter)
    # Only the HUB pin's seat may overlap: the carrier's HUB is a centre-drill
    # spot reamed in place on the running jig, so the model carries no hole
    # for the pressed seat. The pivot pins' carrier sections sit coincident in
    # the Ø10 pin holes.
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
    )

    # Title-block identity for the fitter drawing
    # (draw_ch_rocker_arm_tl_oblique_jig_assembly.py); material and finish are
    # per component.
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The fitter drawing's exploded view references Default Simplified, so
    # the explode is authored in both drawing configurations.
    author_in_drawing_configurations(
        adapter,
        ASM_NAME,
        lambda configuration: _create_jig_explode(adapter, configuration),
    )
    name_machine_views(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
