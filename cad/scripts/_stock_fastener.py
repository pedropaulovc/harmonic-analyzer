"""Build production stock fasteners from vendor replays and catalog-only recipes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import _telemetry
from _fastener_catalog import fastener
from _appearance import apply_color, apply_material
from _check import check
from _com import _com_invoke, _early_bound
from _custom_properties import apply_custom_properties
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _stock_recipe import RecipeAuthor, recipe_declaration
from _visibility import FeatureWalk


type ThreadedPartSaver = Callable[[Any, str, Sequence[str]], Awaitable[dict[str, str]]]
type Vector3 = tuple[float, float, float]

# The helical groove every threaded stock recipe cuts
# (diag_mcmaster_lib.thread_sweep_cut*): the only feature the drawing-view
# configuration suppresses on a fastener.
THREAD_FEATURE = "ThreadGroove"


@dataclass(frozen=True, slots=True)
class RigidTransform:
    """Rigid body transform in model XYZ axes, independent of COM argument order."""

    translation_mm: Vector3 = (0.0, 0.0, 0.0)
    rotation_radians: Vector3 = (0.0, 0.0, 0.0)
    rotation_origin_mm: Vector3 = (0.0, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class StockComponent:
    """One stock SKU recipe and the transform applied only to its new bodies."""

    sku: str
    author: RecipeAuthor
    transform: RigidTransform = RigidTransform()
    parameters: Mapping[str, str | float] | None = None


@dataclass(frozen=True, slots=True)
class _NamedBody:
    name: str
    body: Any


def _solid_bodies(model: Any) -> tuple[_NamedBody, ...]:
    part = _early_bound(model, "IPartDoc")
    raw = part.GetBodies2(0, False)  # swSolidBody, include hidden bodies
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raw = (raw,)

    bodies: list[_NamedBody] = []
    names: set[str] = set()
    for value in raw:
        if value is None:
            raise RuntimeError("solid-body enumeration returned a missing body")
        body = _early_bound(value, "IBody2")
        name = str(body.Name)
        if not name:
            raise RuntimeError("solid-body enumeration returned an unnamed body")
        if name in names:
            raise RuntimeError(
                f"solid-body enumeration returned duplicate name {name!r}"
            )
        names.add(name)
        bodies.append(_NamedBody(name, body))
    return tuple(bodies)


def _new_bodies(
    sku: str,
    before: tuple[_NamedBody, ...],
    after: tuple[_NamedBody, ...],
) -> tuple[_NamedBody, ...]:
    before_names = {item.name for item in before}
    after_names = {item.name for item in after}
    missing = before_names - after_names
    if missing:
        raise RuntimeError(
            f"stock fastener SKU {sku!r} removed existing solid bodies: {sorted(missing)!r}"
        )

    expected_new_count = len(after) - len(before)
    new = tuple(item for item in after if item.name not in before_names)
    if expected_new_count <= 0 or len(new) != expected_new_count:
        raise RuntimeError(
            f"stock fastener SKU {sku!r} new solid-body count mismatch: "
            f"before={len(before)}, after={len(after)}, identified={len(new)}"
        )
    return new


def _current_named_bodies(
    model: Any, names: tuple[str, ...], sku: str
) -> tuple[Any, ...]:
    wanted = set(names)
    current = _solid_bodies(model)
    found = tuple(item.body for item in current if item.name in wanted)
    if len(found) != len(names):
        current_names = {item.name for item in current}
        missing = sorted(wanted - current_names)
        raise RuntimeError(
            f"stock fastener SKU {sku!r} transform bodies missing: {missing!r}; "
            f"expected={len(names)}, found={len(found)}"
        )
    return found


def _component_body_names(
    model: Any,
    existing_names: frozenset[str],
    expected_count: int,
    sku: str,
) -> tuple[str, ...]:
    names = tuple(
        item.name for item in _solid_bodies(model) if item.name not in existing_names
    )
    if len(names) != expected_count:
        raise RuntimeError(
            f"stock fastener SKU {sku!r} transformed body count mismatch: "
            f"expected={expected_count}, found={len(names)}, names={names!r}"
        )
    return names


def _blank_recipe_references(adapter: Any) -> None:
    """Hide every shown construction feature left by a diagnostic recipe."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    hide_types = {
        "ProfileFeature": "SKETCH",
        "3DProfileFeature": "SKETCH",
        "CompositeCurve": "REFERENCECURVES",
        "Helix": "REFERENCECURVES",
        "RefPlane": "PLANE",
        "RefAxis": "AXIS",
    }
    model = adapter.currentModel
    hidden: list[str] = []
    walk = FeatureWalk(model)
    for feature in walk:
        kind = str(_com_invoke(feature, "IFeature", "GetTypeName2"))
        select_type = hide_types.get(kind)
        if not select_type:
            continue
        name = str(_com_invoke(feature, "IFeature", "Name"))
        if name == "Origin" or _com_invoke(feature, "IFeature", "Visible") != 2:
            continue

        model.ClearSelection2(True)
        selected = model.Extension.SelectByID2(
            name,
            select_type,
            0,
            0,
            0,
            False,
            0,
            null_callout(),
            0,
        )
        if not selected:
            raise RuntimeError(
                f"cannot select shown stock reference {name!r} as {select_type}"
            )
        if kind in ("ProfileFeature", "3DProfileFeature"):
            model.BlankSketch()
        else:
            model.BlankRefGeom()
        model.ClearSelection2(True)
        if _com_invoke(feature, "IFeature", "Visible") == 2:
            raise RuntimeError(f"stock reference {name!r} [{kind}] remained visible")
        hidden.append(f"{name} [{kind}]")

    # Hiding a sketch does not hide dimensions that were explicitly shown by
    # its diagnostic recipe. Clear the document-level feature-dimension display
    # before capturing production renders.
    model.HideFeatureDimensions()
    model.ClearSelection2(True)

    _telemetry.event(
        "fastener.stock.references_hidden",
        count=len(hidden),
        features_visited=walk.visited,
        references=", ".join(hidden),
    )


def _select_bodies(model: Any, bodies: tuple[Any, ...], sku: str) -> None:
    if not bodies:
        raise RuntimeError(
            f"stock fastener SKU {sku!r} has no solid bodies to transform"
        )
    model.ClearSelection2(True)
    manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    select_data = _early_bound(manager.CreateSelectData(), "ISelectData")
    if select_data is None:
        raise RuntimeError(f"stock fastener SKU {sku!r}: CreateSelectData failed")
    select_data.Mark = 1
    for index, value in enumerate(bodies):
        body = _early_bound(value, "IBody2")
        if not bool(body.Select2(index != 0, select_data)):
            model.ClearSelection2(True)
            raise RuntimeError(
                f"stock fastener SKU {sku!r}: failed to select new solid body "
                f"{index + 1}/{len(bodies)} at mark 1"
            )


def _name_feature(feature: Any, name: str, sku: str) -> None:
    feature = _early_bound(feature, "IFeature")
    feature.Name = name
    if str(feature.Name) != name:
        raise RuntimeError(
            f"stock fastener SKU {sku!r}: failed to name transform feature {name!r}"
        )


def _insert_rotation(
    model: Any,
    names: tuple[str, ...],
    transform: RigidTransform,
    feature_name: str,
    sku: str,
) -> None:
    bodies = _current_named_bodies(model, names, sku)
    _select_bodies(model, bodies, sku)
    ox, oy, oz = (value / 1000.0 for value in transform.rotation_origin_mm)
    rx, ry, rz = transform.rotation_radians
    # Despite the API parameter names, Move/Copy Body's generated feature maps
    # RotAngleX to a model-Z rotation and RotAngleZ to model X.  Preserve this
    # class's conventional model-XYZ contract by swapping those two arguments.
    # Live proof: a Y-axis fillister recipe rotated (-pi/2, 0, 0) must span Z;
    # passing rx as RotAngleX instead made it span X and drove both clamp screws
    # sideways through the magnifier wheel bar.
    manager = _early_bound(model.FeatureManager, "IFeatureManager")
    try:
        feature = manager.InsertMoveCopyBody2(
            0.0,
            0.0,
            0.0,
            0.0,
            ox,
            oy,
            oz,
            rz,
            ry,
            rx,
            False,
            1,
        )
    finally:
        model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError(
            f"stock fastener SKU {sku!r}: rotation feature creation failed"
        )
    _name_feature(feature, feature_name, sku)


def _insert_translation(
    model: Any,
    names: tuple[str, ...],
    transform: RigidTransform,
    feature_name: str,
    sku: str,
) -> None:
    bodies = _current_named_bodies(model, names, sku)
    _select_bodies(model, bodies, sku)
    tx, ty, tz = (value / 1000.0 for value in transform.translation_mm)
    manager = _early_bound(model.FeatureManager, "IFeatureManager")
    try:
        feature = manager.InsertMoveCopyBody2(
            tx,
            ty,
            tz,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            False,
            1,
        )
    finally:
        model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError(
            f"stock fastener SKU {sku!r}: translation feature creation failed"
        )
    _name_feature(feature, feature_name, sku)


def _transform_new_bodies(
    model: Any,
    component_index: int,
    component: StockComponent,
    bodies: tuple[_NamedBody, ...],
    existing_names: frozenset[str],
) -> None:
    transform = component.transform
    names = tuple(item.name for item in bodies)
    prefix = f"Stock{component_index}_{component.sku}"

    # InsertMoveCopyBody2 ignores translation whenever rotation is also supplied,
    # so a compound rigid transform must be represented by two separate features.
    # A move feature can rename its result body; refresh the component body names
    # before applying the second feature instead of trusting the consumed names.
    if any(transform.rotation_radians):
        _insert_rotation(
            model,
            names,
            transform,
            f"{prefix}_Rotation",
            component.sku,
        )
        names = _component_body_names(model, existing_names, len(bodies), component.sku)
    if any(transform.translation_mm):
        _insert_translation(
            model,
            names,
            transform,
            f"{prefix}_Translation",
            component.sku,
        )


async def build_stock_fastener(
    adapter: Any,
    *,
    part_name: str,
    components: Iterable[StockComponent],
    material: str,
    color: tuple[float, float, float] | None = None,
    screw_axis_planes: tuple[str, str] | None = None,
    save_threaded_part: ThreadedPartSaver | None = None,
) -> dict[str, str]:
    """Create, normalize, finish, and save one production stock part.

    ``screw_axis_planes`` restores the stable ``ScrewAxis`` mate contract for
    assemblies whose normalized stock body axis is not represented by a
    transformed recipe reference.

    Threaded callers supply their statically imported simplified saver through
    ``save_threaded_part``. Unthreaded leaves never import that part machinery.
    """

    check("create_part", await adapter.create_part())
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    component_count = 0
    threaded = False
    try:
        for component_count, component in enumerate(components, 1):
            metadata = recipe_declaration(component.sku, component.author)
            threaded = threaded or metadata.threaded

            model.ClearSelection2(True)
            before = _solid_bodies(model)
            with _telemetry.span(
                "fastener.stock.recipe",
                sku=component.sku,
                component=component_count,
            ):
                # Sketch inference / automatic relations are APPLICATION-level
                # preferences, so a seat carries whatever the last leaf left
                # behind -- including a suppression block that never unwound
                # (SolidWorks crash, COM disconnect, watchdog exit, killed
                # process).  Every recipe asserts the state it requires instead
                # of inheriting it, which also repairs a seat an earlier leaf
                # poisoned.  Imported here, not at module scope, to keep the
                # recipe-import build-graph note in _stock_recipe true.
                from diagnostics.diag_mcmaster_lib import (
                    assert_seat_sketch_baseline,
                )

                assert_seat_sketch_baseline(adapter, component.sku)
                try:
                    if component.parameters is None:
                        await component.author(adapter, None)
                    else:
                        await component.author(adapter, None, **component.parameters)
                finally:
                    model.ClearSelection2(True)
            after = _solid_bodies(model)
            new_bodies = _new_bodies(component.sku, before, after)

            with _telemetry.span(
                "fastener.stock.transform",
                sku=component.sku,
                component=component_count,
                bodies=len(new_bodies),
            ):
                # ~27 s per build in one opaque span: split the body move from
                # the construction-feature walk so the cost can be attributed.
                with _telemetry.span("fastener.stock.move_features", sku=component.sku):
                    _transform_new_bodies(
                        model,
                        component_count,
                        component,
                        new_bodies,
                        frozenset(item.name for item in before),
                    )
                with _telemetry.span(
                    "fastener.stock.blank_references", sku=component.sku
                ):
                    _blank_recipe_references(adapter)
                model.ClearSelection2(True)
    finally:
        if hasattr(adapter, "_mcm_com_map"):
            delattr(adapter, "_mcm_com_map")

    if component_count == 0:
        raise ValueError(f"stock fastener {part_name!r} has no components")
    if screw_axis_planes is not None:
        from solidworks_mcp.adapters.base import CreateAxisParameters

        check(
            f"create_axis ScrewAxis ({' ∩ '.join(screw_axis_planes)})",
            await adapter.create_axis(
                CreateAxisParameters(
                    mode="two_planes",
                    planes=list(screw_axis_planes),
                )
            ),
        )
        name_last_feature(adapter, "ScrewAxis")
        _blank_recipe_references(adapter)

    await force_rebuild(adapter)
    await apply_material(adapter, material)
    if color is not None:
        await apply_color(adapter, color)
    stock = fastener(part_name)
    apply_custom_properties(
        adapter,
        {
            "Stock Name": stock.stock_name,
            "Supplier": stock.supplier,
            "Supplier SKUs": ", ".join(stock.skus),
        },
    )
    await report_mass_properties(adapter)
    return await _save_stock_part(
        adapter, part_name, threaded=threaded, save_threaded_part=save_threaded_part
    )


async def _save_stock_part(
    adapter: Any,
    part_name: str,
    *,
    threaded: bool,
    save_threaded_part: ThreadedPartSaver | None = None,
) -> dict[str, str]:
    """Save a finished stock part; a threaded one with its simplified views.

    Threaded-ness is the recipes' declaration, never inferred from the tree:
    a threaded part whose groove is missing (renamed, or never cut) and an
    unthreaded one that grew a groove both fail loud instead of saving a part
    whose assembly line views print the thread black.
    """
    part = _early_bound(adapter.currentModel, "IPartDoc")
    cut = part.FeatureByName(THREAD_FEATURE) is not None
    if cut != threaded:
        state = "has" if cut else "has no"
        declared = "threaded" if threaded else "unthreaded"
        raise RuntimeError(
            f"{part_name}: recipes declare it {declared} but it {state} "
            f"{THREAD_FEATURE!r} feature"
        )
    if threaded:
        if not callable(save_threaded_part):
            raise TypeError(
                f"{part_name}: threaded stock part requires a callable simplified saver"
            )
        # "<cfg> Simplified" suppresses the helical cut for assembly views.
        return await save_threaded_part(adapter, part_name, (THREAD_FEATURE,))
    return await save_part_and_images(adapter, part_name)
