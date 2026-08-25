"""Build production stock fasteners from verified McMaster geometry recipes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import _telemetry
from _fastener_catalog import fastener
from _common import (
    _early_bound,
    apply_color,
    apply_custom_properties,
    apply_material,
    check,
    force_rebuild,
    report_mass_properties,
    save_part_and_images,
)


type RecipeAuthor = Callable[[Any, Any | None], Awaitable[None]]
type Vector3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class RecipeMetadata:
    """Static import metadata for one verified diagnostic recipe."""

    module: str
    callable_name: str


# Metadata only: production builders statically import the one recipe they use and
# pass its callable in StockComponent. Importing recipes here would make every stock
# fastener depend on every diagnostic geometry module in the build graph.
STOCK_RECIPES: Mapping[str, RecipeMetadata] = MappingProxyType(
    {
        "90280A194": RecipeMetadata(
            "diagnostics.diag_build_90280A194", "build_90280A194"
        ),
        "90280A201": RecipeMetadata(
            "diagnostics.diag_build_90280A201", "build_90280A201"
        ),
        "91882A412": RecipeMetadata(
            "diagnostics.diag_build_91882A412", "build_91882A412"
        ),
        "91829A560": RecipeMetadata(
            "diagnostics.diag_build_91829A560", "build_91829A560"
        ),
        "94025A150": RecipeMetadata(
            "diagnostics.diag_build_94025A150", "build_94025A150"
        ),
        "90280A108": RecipeMetadata(
            "diagnostics.diag_build_90280A108", "build_90280A108"
        ),
        "90114A511": RecipeMetadata(
            "diagnostics.diag_build_90114A511", "build_90114A511"
        ),
        "91410A538": RecipeMetadata(
            "diagnostics.diag_build_91410A538", "build_91410A538"
        ),
        "93075A194": RecipeMetadata(
            "diagnostics.diag_build_93075A194", "build_93075A194"
        ),
        "92865A585": RecipeMetadata(
            "diagnostics.diag_build_92865A585", "build_92865A585"
        ),
        "91247A720": RecipeMetadata(
            "diagnostics.diag_build_91247A720", "build_91247A720"
        ),
        "90126A211": RecipeMetadata(
            "diagnostics.diag_build_90126A211", "build_90126A211"
        ),
        "91783A722": RecipeMetadata(
            "diagnostics.diag_build_91783A722", "build_91783A722"
        ),
        "99607A213": RecipeMetadata(
            "diagnostics.diag_build_99607A213", "build_99607A213"
        ),
        "90280A199": RecipeMetadata(
            "diagnostics.diag_build_90280A199", "build_90280A199"
        ),
        "90280A196": RecipeMetadata(
            "diagnostics.diag_build_90280A196", "build_90280A196"
        ),
        "91882A221": RecipeMetadata(
            "diagnostics.diag_build_91882A221", "build_91882A221"
        ),
    }
)


@dataclass(frozen=True, slots=True)
class RigidTransform:
    """Rigid body transform: millimetre positions and radian Euler rotations."""

    translation_mm: Vector3 = (0.0, 0.0, 0.0)
    rotation_radians: Vector3 = (0.0, 0.0, 0.0)
    rotation_origin_mm: Vector3 = (0.0, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class StockComponent:
    """One stock SKU recipe and the transform applied only to its new bodies."""

    sku: str
    author: RecipeAuthor
    transform: RigidTransform = RigidTransform()


@dataclass(frozen=True, slots=True)
class _NamedBody:
    name: str
    body: Any


def _recipe_metadata(sku: str) -> RecipeMetadata:
    try:
        return STOCK_RECIPES[sku]
    except KeyError:
        raise KeyError(f"unknown stock fastener SKU {sku!r}") from None


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
            rx,
            ry,
            rz,
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
) -> None:
    transform = component.transform
    names = tuple(item.name for item in bodies)
    prefix = f"Stock{component_index}_{component.sku}"

    # InsertMoveCopyBody2 ignores translation whenever rotation is also supplied,
    # so a compound rigid transform must be represented by two separate features.
    if any(transform.rotation_radians):
        _insert_rotation(
            model,
            names,
            transform,
            f"{prefix}_Rotation",
            component.sku,
        )
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
) -> dict[str, str]:
    """Create, author, transform, finish, and save one production stock part."""

    check("create_part", await adapter.create_part())
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    component_count = 0
    try:
        for component_count, component in enumerate(components, 1):
            metadata = _recipe_metadata(component.sku)
            if not callable(component.author):
                raise TypeError(
                    f"stock fastener SKU {component.sku!r} recipe author is not callable"
                )
            if getattr(component.author, "__name__", None) != metadata.callable_name:
                raise ValueError(
                    f"stock fastener SKU {component.sku!r} requires recipe "
                    f"{metadata.callable_name!r}, got "
                    f"{getattr(component.author, '__name__', type(component.author).__name__)!r}"
                )

            model.ClearSelection2(True)
            before = _solid_bodies(model)
            with _telemetry.span(
                "fastener.stock.recipe",
                sku=component.sku,
                component=component_count,
            ):
                try:
                    await component.author(adapter, None)
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
                _transform_new_bodies(model, component_count, component, new_bodies)
                model.ClearSelection2(True)
    finally:
        if hasattr(adapter, "_mcm_com_map"):
            delattr(adapter, "_mcm_com_map")

    if component_count == 0:
        raise ValueError(f"stock fastener {part_name!r} has no components")

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
    return await save_part_and_images(adapter, part_name)
