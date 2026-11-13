r"""Reproduction script: ch-rocker-arm-tl-oblique-jig.SLDASM (MHA-CH-06-TL-00).

The rocker arm's oblique-trammel mill jig, a shop fixture (never in the
machine tree, ``_buildgraph.is_shop_fixture``): two of the one base bar (as
saved under rail 1 on -X, turned over under rail 2 on +X) held to the table
by hold-down studs in T-nuts under flange nuts, an HGR15 rail screwed on each
bar with an HGH15 carriage on it, a plain pivot block on rail 2 and an
integral nut-lug feed block on rail 1. Purchased shoulder screws, selected
shims and loose spacers support and capture the carrier. The strap is held
by three common #8-32 SHCS (CL and CR direct, HUB through the brass #8 SAE
flat washer) against two loose stock stop pins in the riser.
The raised leadscrew runs in two KP08 blocks on on-edge end brackets and
through the feed block's nut. Every bought item and screw is inserted.

Authored in the MACHINE frame of ``ch_rocker_arm_tl_oblique_jig_assembly_spec``
(origin on the spindle at the table top, +X along the table, +Y toward the
column, +Z up) at the symmetric inner pass. Every pose is the spec's
(``spec.PLACEMENTS``), derived from the calculator
``ch_rocker_arm_tl_oblique_trammel_spec``. The structure is fixed; the moving
occurrences (``spec.is_moving``: the families in ``spec.MOVING``, but only the
common screw's strap clamps of its family) are inserted free at that pose and
mated (``spec.LOCKED_TO``, ``spec.PIN_MATES``): each carriage on its rail, the
carrier on the two pins (a planar P-R-R-P loop), everything else lock-mated
to what carries it. Carriage 1's slide is the one free DOF: recorded in the
DOF manifest (``spec.SLIDE_KEY``), never authored, and the build writes the
sweep sidecar (``spec.sweep_sidecar``) that verify.py's
``pass-sweep-interference-free`` gate walks through both passes.

The build names the spec's machine-frame views on the assembly
(``spec.VIEW_AXES``: the plan, the operator's elevation and the front-right
isometric), each read back, and the fitter drawing places those; the
standard views stay SolidWorks' own.

The named explode JIG_EXPLODED (Default and Default Simplified) is the fitter
drawing's exploded view: the disassembly order along the machine axes, each
step read back in world space and the saved pose proven unchanged.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_jig_assembly.py
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import _telemetry
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
from _assembly import (
    activate_assembly_contract,
    allowed_free_stems,
    assembly_title_properties,
    assert_component_placed,
    assert_free_dof_necessity,
    author_in_drawing_configurations,
    check_no_interference,
    coincident_mate,
    distance_driver,
    dof_manifest_path,
    lock_mate,
    named_ref,
    place_component,
    place_components_batch,
    reset_dof_manifest,
    save_assembly_and_images,
    write_dof_manifest,
)
from _assembly_contract import assembly_contract
from _assembly_patterns import ensure_global_pattern_axis
from _check import check
from _com import _early_bound
from _component_references import component_identity, component_reference_names
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _drawing_marks import DRAWN_BY
from _ch_rocker_arm_tl_oblique_jig_interference import ALLOWED_PAIRS
from _named_views import octant_rotation
from _session import run_build
from _simplified_names import simplified_name
from _transforms import euler_from_rows
from _visibility import blank_reference_geometry

ASM_NAME = "ch-rocker-arm-tl-oblique-jig"
assert ASM_NAME == spec.ASM_NAME, (ASM_NAME, spec.ASM_NAME)
# Literal (physical filename, logical family) rows: the build graph reads the
# first field syntactically, never through a spec-derived or generated filename.
# A repeated configured file (a purchased kit or the TL-20 base bar) is one
# producer with one configured BOM row per member.
_PARTS = (
    ("ch-rocker-arm-tl-oblique-base-bar", "ch-rocker-arm-tl-oblique-base-bar--Bar1"),
    ("ch-rocker-arm-tl-oblique-base-bar", "ch-rocker-arm-tl-oblique-base-bar--Bar2"),
    ("ch-rocker-arm-tl-oblique-carrier", "ch-rocker-arm-tl-oblique-carrier"),
    ("ch-rocker-arm-tl-oblique-pivot-block", "ch-rocker-arm-tl-oblique-pivot-block"),
    ("ch-rocker-arm-tl-oblique-feed-block", "ch-rocker-arm-tl-oblique-feed-block"),
    ("ch-rocker-arm-tl-vn-oblique-pivot-screw", "ch-rocker-arm-tl-vn-oblique-pivot-screw"),
    ("ch-rocker-arm-tl-vn-oblique-pivot-spacer", "ch-rocker-arm-tl-vn-oblique-pivot-spacer"),
    ("ch-rocker-arm-tl-vn-oblique-pivot-shim", "ch-rocker-arm-tl-vn-oblique-pivot-shim"),
    ("ch-rocker-arm-tl-oblique-riser", "ch-rocker-arm-tl-oblique-riser"),
    ("ch-rocker-arm-tl-vn-oblique-hub-washer", "ch-rocker-arm-tl-vn-oblique-hub-washer"),
    ("ch-rocker-arm-tl-oblique-feed-lever", "ch-rocker-arm-tl-oblique-feed-lever"),
    ("ch-rocker-arm-tl-oblique-end-bracket", "ch-rocker-arm-tl-oblique-end-bracket"),
    ("ch-rocker-arm-tl-vn-oblique-rail-kit", "ch-rocker-arm-tl-vn-oblique-rail-kit--Rail"),
    ("ch-rocker-arm-tl-vn-oblique-rail-kit", "ch-rocker-arm-tl-vn-oblique-rail-kit--Carriage"),
    ("sm-vn-knife-mount-dowel", "sm-vn-knife-mount-dowel"),
    ("ch-rocker-arm-tl-vn-oblique-leadscrew-kit", "ch-rocker-arm-tl-vn-oblique-leadscrew-kit--LeadScrew"),
    ("ch-rocker-arm-tl-vn-oblique-leadscrew-kit", "ch-rocker-arm-tl-vn-oblique-leadscrew-kit--FeedNut"),
    ("ch-rocker-arm-tl-vn-oblique-pillow-block", "ch-rocker-arm-tl-vn-oblique-pillow-block"),
    ("ch-rocker-arm-tl-vn-oblique-handwheel", "ch-rocker-arm-tl-vn-oblique-handwheel"),
    ("sh-vn-clamping-kit-hardware", "sh-vn-clamping-kit-hardware--HoldDownStud"),
    ("sh-vn-clamping-kit-hardware", "sh-vn-clamping-kit-hardware--TNut"),
    ("sh-vn-clamping-kit-hardware", "sh-vn-clamping-kit-hardware--FlangeNut"),
    ("ch-rocker-arm-tl-vn-oblique-rail-screw", "ch-rocker-arm-tl-vn-oblique-rail-screw"),
    ("ch-rocker-arm-tl-vn-oblique-carriage-screw", "ch-rocker-arm-tl-vn-oblique-carriage-screw"),
    ("ch-rocker-arm-tl-vn-oblique-bracket-screw", "ch-rocker-arm-tl-vn-oblique-bracket-screw"),
    ("ch-rocker-arm-tl-vn-oblique-riser-screw", "ch-rocker-arm-tl-vn-oblique-riser-screw"),
    ("ch-rocker-arm-tl-vn-oblique-lever-screw", "ch-rocker-arm-tl-vn-oblique-lever-screw"),
    ("ch-rocker-arm-tl-vn-oblique-lever-washer", "ch-rocker-arm-tl-vn-oblique-lever-washer"),
)
assert tuple(family for _physical, family in _PARTS) == spec.BOM_ORDER
assert all(
    spec.COMPONENT_IDENTITIES[family][0] == physical for physical, family in _PARTS
)
# A family of this many instances or more goes in one AddComponents3 (one
# family per batch: the batch matches components by origin, and no two
# instances of one family share an origin).
_BATCH_MIN = 4


def _rows(rows: spec.Rows) -> list[list[float]]:
    return [list(row) for row in rows]


def sweep_sidecar_path() -> Path:
    """``.<asm>.sweep.json`` beside the DOF manifest (verify.py and dodo name
    the same path)."""
    return dof_manifest_path(ASM_NAME).with_name(f".{ASM_NAME}.sweep.json")


async def _place_family(adapter: Any, physical: str, family: str) -> dict[str, str]:
    """Insert a logical family in one batch where possible; retain actual names.

    Kit references are role-local ordinals. SOLIDWORKS allocates the native
    Name2 suffix across the shared file, so it is never inferred from that ordinal.
    """
    native_stem, configuration = spec.COMPONENT_IDENTITIES[family]
    if physical != native_stem:
        raise ValueError(f"{family}: manifest file {physical!r} != {native_stem!r}")
    placements = spec.PLACEMENTS[family]
    # Fixed occurrences are grounded; the moving ones are inserted free at
    # their pose (the common screw's strap clamps ride; its rail occurrences
    # and the bracket-family bar screws stay fixed).
    grounds = [not spec.is_moving(family, index) for index in range(len(placements))]
    selectors = [spec.instance_name(family, index) for index in range(len(placements))]
    if len(placements) >= _BATCH_MIN:
        # Keep the batch's source rows in the bounded append-loop form the
        # build graph enumerates; placement metadata is not a filename source.
        rows_spec = []
        for index, (origin, rows) in enumerate(placements):
            selector = selectors[index]
            rows_spec.append(
                {
                    "part": physical,
                    "position": list(origin),
                    "rows": _rows(rows),
                    "ground": grounds[index],
                    "configuration": configuration or "",
                    "component_reference": selector[1:] if configuration else "",
                }
            )
        names = await place_components_batch(adapter, rows_spec, label=family)
    else:
        names = []
        for index, (selector, (origin, rows)) in enumerate(
            zip(selectors, placements, strict=True)
        ):
            matrix = _rows(rows)
            names.append(
                await place_component(
                    adapter,
                    physical,
                    list(origin),
                    euler_from_rows(matrix),
                    matrix,
                    ground=grounds[index],
                    configuration=configuration or "",
                    component_reference=selector[1:] if configuration else "",
                    label=selector,
                )
            )
    if len(names) != len(selectors) or len(set(names)) != len(names):
        raise RuntimeError(f"{family}: incomplete or repeated inserted names {names!r}")
    observed = dict(zip(selectors, names, strict=True))
    if configuration:
        resolved = component_reference_names(
            adapter.currentModel,
            {selector: (physical, configuration) for selector in selectors},
        )
        if resolved != observed:
            raise RuntimeError(
                f"{family}: inserted references {observed!r} != {resolved!r}"
            )
    elif names != selectors:
        raise RuntimeError(f"{family}: inserted {names!r}, expected {selectors!r}")
    return observed


def _verify_member_references(adapter: Any, placed_names: dict[str, str]) -> None:
    """Read every configured member's role/file/member again after the final
    solve before save (purchased kits and the TL-20 base bars)."""
    actual = component_reference_names(
        adapter.currentModel, spec.MEMBER_COMPONENT_REFERENCES
    )
    expected = {selector: placed_names[selector] for selector in actual}
    if actual != expected:
        raise RuntimeError(
            f"jig final member references {actual!r} != inserted {expected!r}"
        )


async def _mate_carriages(adapter: Any, names: dict[str, str]) -> None:
    """Each carriage rides its rail (Front and Top planes coincident: the
    frames coincide by construction). Carriage 1's slide is the sweep's one
    DOF: recorded for verify's replays, never authored; carriage 2's is
    driven through the carrier. ``names`` maps each selector to the native
    name its placement returned (kit members are role references)."""
    for index, (origin, _carriage_rows) in enumerate(spec.CARRIAGE_PLACEMENTS):
        carriage = names[spec.instance_name(spec.CARRIAGE, index)]
        rail = names[spec.instance_name(spec.RAIL, index)]
        for plane in ("Front Plane", "Top Plane"):
            await coincident_mate(
                adapter,
                named_ref(f"{plane}@{carriage}", "PLANE"),
                named_ref(f"{plane}@{rail}", "PLANE"),
                label=f"{carriage} {plane} on {rail}",
                verify=(carriage, list(origin)),
            )
    index = spec.RAILS.index(spec.SLIDE_RAIL)
    carriage = names[spec.instance_name(spec.CARRIAGE, index)]
    await distance_driver(
        adapter,
        named_ref(f"Right Plane@{names[spec.instance_name(spec.RAIL, index)]}", "PLANE"),
        named_ref(f"Right Plane@{carriage}", "PLANE"),
        spec.slide_distance(spec.CARRIAGE_STATION),
        label=f"carriage {spec.SLIDE_RAIL} slide on rail {spec.SLIDE_RAIL}",
        verify=(carriage, list(spec.CARRIAGE_PLACEMENTS[index][0])),
        free_dof_key=spec.SLIDE_KEY,
    )


async def _lock_families(
    adapter: Any, families: list[str], names: dict[str, str]
) -> None:
    """Lock-mate every moving instance of ``families`` to what carries it."""
    for stem in families:
        for index in range(spec.QUANTITIES[stem]):
            if not spec.is_moving(stem, index):
                continue
            child = names[spec.instance_name(stem, index)]
            parent = names[spec.lock_parent(stem, index)]
            await lock_mate(
                adapter,
                named_ref(f"Front Plane@{child}", "PLANE"),
                named_ref(f"Front Plane@{parent}", "PLANE"),
                label=f"{child} locked to {parent}",
            )


async def _mate_carrier(adapter: Any) -> None:
    """The carrier rides the two pins: each pass hole's named axis coincident
    with its pin's (a coaxial; CreateMate takes no concentric on two axes),
    each mate renamed (``spec.PIN_MATES``) so verify's outer pass can suppress
    it, and its top face (its Top Plane) on a hidden assembly plane
    ``CARRIER_TOP_Z`` up the Front Plane. With the two slides a planar P-R-R-P
    loop: the sweep's one DOF.

    Every entity is picked by name: a face point pick depends on the seat's
    view (jig-bought-r2 missed the collar edge, r3 a hole wall). The pins
    ride the rails at a fixed height, so the datum is the same constraint as
    the collar top, and it stays valid through the outer pass's re-mate."""
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        RenameFeatureParameters,
    )

    carrier = spec.instance_name(spec.CARRIER, 0)
    (carrier_at,) = spec.PLACEMENTS[spec.CARRIER]
    for name, hole, pin in spec.PIN_MATES[spec.PASS]:
        mate = await coincident_mate(
            adapter,
            named_ref(spec.carrier_hole_axis(hole), "AXIS"),
            named_ref(spec.pin_axis(pin), "AXIS"),
            label=name,
            verify=(carrier, list(carrier_at[0])),
        )
        check(
            f"rename {mate['name']!r} -> {name!r}",
            await adapter.rename_feature(
                RenameFeatureParameters(old_name=mate["name"], new_name=name)
            ),
        )
    seat = check(
        "create_plane Front Plane at the carrier top",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Front Plane",
                offset=spec.trammel.CARRIER_TOP_Z,
            )
        ),
    )
    seat_name = getattr(seat, "name", seat)
    # Hidden at creation: the mate selects it by name, and a shown plane
    # prints in the assembly's renders.
    blank_reference_geometry(adapter, ((seat_name, "PLANE"),))
    await coincident_mate(
        adapter,
        named_ref(f"Top Plane@{carrier}", "PLANE"),
        named_ref(seat_name, "PLANE"),
        label="carrier top on the carrier-top plane",
        verify=(carrier, list(carrier_at[0])),
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


def explode_step_components(
    label: str,
    selectors: Sequence[str],
    groups: Mapping[str, Sequence[Any]],
    by_name: Mapping[str, Any],
    member_names: Mapping[str, str],
) -> list[Any]:
    """The native components one ``spec.EXPLODE_STEPS`` entry moves.

    A family selector moves its whole identity group. An instance selector
    (``spec.instance_name``; the riser and nut screws share a family but
    explode apart; so do the KP08 and TL-28 bar screws) moves the one
    occurrence it names: a configured member's occurrence by its persisted
    role reference (``member_names``), any other by the Name2
    ``_place_family`` proved equal to its selector.
    """
    moved: dict[str, Any] = {}
    for selector in selectors:
        if selector in groups:
            members = tuple(groups[selector])
        else:
            try:
                (occurrence,) = spec.explode_occurrences(selector)
            except ValueError as error:
                raise RuntimeError(
                    f"{label}: unknown explode selector {selector!r}"
                ) from error
            name = member_names.get(occurrence, occurrence)
            if name not in by_name:
                raise RuntimeError(
                    f"{label}: explode occurrence {selector!r} has no component {name!r}"
                )
            members = (by_name[name],)
        for component in members:
            moved.setdefault(str(component.Name2), component)
    return list(moved.values())


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
    member_names = component_reference_names(model, spec.MEMBER_COMPONENT_REFERENCES)
    groups: dict[str, list[Any]] = {family: [] for family in spec.QUANTITIES}
    for component in components:
        identity = component_identity(component)
        try:
            family = spec.component_family(*identity)
        except ValueError as error:
            raise RuntimeError(
                f"{view_name}: unexpected component {component.Name2}: {identity!r}"
            ) from error
        groups[family].append(component)
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
    by_name = {str(component.Name2): component for component in components}
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
        for step_index, (label, selectors, key, distance_mm) in enumerate(
            spec.EXPLODE_STEPS, 1
        ):
            moved = explode_step_components(label, selectors, groups, by_name, member_names)
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
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    # Clear the free-DOF manifest before carriage 1's slide is recorded.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())
    apply_package_model_units(adapter, assembly_contract(ASM_NAME).drawing_unit, label=ASM_NAME)

    # Every family in BOM order (SolidWorks numbers a top-level BOM in
    # FeatureManager order; the base bars come first and SolidWorks fixes the
    # first insert), each instance at its spec pose: the structure fixed, the
    # moving families free at the inner pass's symmetric pose.
    placed_names: dict[str, str] = {}
    for physical, family in _PARTS:
        placed_names.update(await _place_family(adapter, physical, family))
    # The carriages on their rails; what rides a carriage, a pivot block or
    # the nut bracket locked to it; the carrier on the pins; its riders
    # locked to it.
    await _mate_carriages(adapter, placed_names)
    def _rides_carrier(parents: tuple[tuple[str, int] | None, ...]) -> bool:
        return any(parent is not None and parent[0] == spec.CARRIER for parent in parents)

    carried = [stem for stem, parents in spec.LOCKED_TO.items() if not _rides_carrier(parents)]
    riders = [stem for stem, parents in spec.LOCKED_TO.items() if _rides_carrier(parents)]
    await _lock_families(adapter, carried, placed_names)
    await _mate_carrier(adapter)
    await _lock_families(adapter, riders, placed_names)
    # The mates solved in place: every moving instance is still at its pose.
    for moving in spec.MOVING:
        for index, (origin, rows) in enumerate(spec.PLACEMENTS[moving]):
            if not spec.is_moving(moving, index):
                continue
            assert_component_placed(
                adapter,
                placed_names[spec.instance_name(moving, index)],
                list(origin),
                _rows(rows),
            )
    _telemetry.info(
        f"jig at the {spec.PASS} pass, theta {spec.THETA:g}: pins at station "
        f"{spec.PIN_STATION:.3f}, carriages at {spec.CARRIAGE_STATION:.3f}; "
        f"carrier underside Z {spec.trammel.CARRIER_UNDERSIDE_Z:.1f}, "
        f"strap top Z {spec.PART_TOP_Z:.3f}"
    )

    # One free DOF, the sweep: every moving family reads under-constrained
    # (a rider a mate silently fixed fails) and nothing else does. A moving
    # kit member shares its file with a fixed one (Carriage with Rail, FeedNut
    # with LeadScrew), and the common screw's strap clamps share theirs with
    # its fixed rail and bar occurrences, so each such moving occurrence must
    # read free itself.
    assert_free_dof_necessity(
        adapter,
        1,
        required_stems=spec.MOVING_STEMS,
        required_instances=tuple(
            placed_names[spec.instance_name(family, index)]
            for family in spec.MOVING
            if family in spec.KIT_IDENTITIES
            or not all(spec.is_moving(family, i) for i in range(spec.QUANTITIES[family]))
            for index in range(spec.QUANTITIES[family])
            if spec.is_moving(family, index)
        ),
        allowed_stems=allowed_free_stems(ASM_NAME),
    )
    write_dof_manifest(ASM_NAME)
    sweep_sidecar_path().write_text(
        json.dumps(spec.sweep_sidecar(), indent=2), encoding="utf-8"
    )
    # This pose's check; verify.py's pass-sweep-interference-free walks both
    # passes. The allowed pairs are the jig's exact press fits and thread
    # envelopes (_ch_rocker_arm_tl_oblique_jig_interference).
    check_no_interference(
        adapter,
        allowed_pairs=ALLOWED_PAIRS,
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
    return await save_assembly_and_images(
        adapter,
        ASM_NAME,
        solved_gates=lambda current: _verify_member_references(current, placed_names),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
