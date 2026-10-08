"""Build production stock fasteners from vendor replays and catalog-only recipes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import _telemetry
from _fastener_catalog import fastener
from _common import (
    _com_invoke,
    _early_bound,
    apply_color,
    apply_custom_properties,
    apply_material,
    check,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    save_part_and_images,
)
from _drawing_simplified import save_simplified_part
from _visibility import FeatureWalk


type RecipeAuthor = Callable[..., Awaitable[None]]
type Vector3 = tuple[float, float, float]

# The helical groove every threaded stock recipe cuts
# (diag_mcmaster_lib.thread_sweep_cut*): the only feature the drawing-view
# configuration suppresses on a fastener.
THREAD_FEATURE = "ThreadGroove"


@dataclass(frozen=True, slots=True)
class RecipeMetadata:
    """Static import metadata for one native stock recipe.

    ``threaded`` declares that the recipe cuts a modeled helical thread named
    ``THREAD_FEATURE``; the stock build requires the feature to match, so a
    renamed groove cannot silently save a part without its simplified views.
    """

    module: str
    callable_name: str
    threaded: bool


# Metadata only: production builders statically import the one recipe they use and
# pass its callable in StockComponent. Importing recipes here would make every stock
# fastener depend on every diagnostic geometry module in the build graph.
STOCK_RECIPES: Mapping[str, RecipeMetadata] = MappingProxyType(
    {
        "90280A194": RecipeMetadata(
            "diagnostics.diag_build_90280A194", "build_90280A194", threaded=True
        ),
        "90280A197": RecipeMetadata(
            "diagnostics.diag_build_90280A197", "build_90280A197", threaded=True
        ),
        "90280A837": RecipeMetadata(
            "diagnostics.diag_build_90280A837", "build_90280A837", threaded=True
        ),
        "40923906": RecipeMetadata(
            "diagnostics.diag_build_40923906", "build_40923906", threaded=True
        ),
        "90280A201": RecipeMetadata(
            "diagnostics.diag_build_90280A201", "build_90280A201", threaded=True
        ),
        "91255A148": RecipeMetadata(
            "diagnostics.diag_build_91255A148", "build_91255A148", threaded=True
        ),
        "91255A106": RecipeMetadata(
            "diagnostics.diag_build_91255A106", "build_91255A106", threaded=True
        ),
        "91255A108": RecipeMetadata(
            "diagnostics.diag_build_91255A108", "build_91255A108", threaded=True
        ),
        "91882A425": RecipeMetadata(
            "diagnostics.diag_build_91882A425", "build_91882A425", threaded=True
        ),
        "93585A190": RecipeMetadata(
            "diagnostics.diag_build_93585A190", "build_93585A190", threaded=True
        ),
        "91829A560": RecipeMetadata(
            "diagnostics.diag_build_91829A560", "build_91829A560", threaded=True
        ),
        "91829A205": RecipeMetadata(
            "diagnostics.diag_build_91829A205", "build_91829A205", threaded=True
        ),
        "94025A164": RecipeMetadata(
            "diagnostics.diag_build_94025A164", "build_94025A164", threaded=True
        ),
        "91375A106": RecipeMetadata(
            "diagnostics.diag_build_91375A106", "build_91375A106", threaded=True
        ),
        "90280A108": RecipeMetadata(
            "diagnostics.diag_build_90280A108", "build_90280A108", threaded=True
        ),
        "91794A077": RecipeMetadata(
            "diagnostics.diag_build_91794A077", "build_91794A077", threaded=True
        ),
        "91794A112": RecipeMetadata(
            "diagnostics.diag_build_91794A112", "build_91794A112", threaded=True
        ),
        "90114A511": RecipeMetadata(
            "diagnostics.diag_build_90114A511", "build_90114A511", threaded=True
        ),
        "91410A538": RecipeMetadata(
            "diagnostics.diag_build_91410A538", "build_91410A538", threaded=True
        ),
        "91251A108": RecipeMetadata(
            "diagnostics.diag_build_91251A108", "build_91251A108", threaded=True
        ),
        "93075A194": RecipeMetadata(
            "diagnostics.diag_build_93075A194", "build_93075A194", threaded=True
        ),
        "92865A585": RecipeMetadata(
            "diagnostics.diag_build_92865A585", "build_92865A585", threaded=True
        ),
        "91247A720": RecipeMetadata(
            "diagnostics.diag_build_91247A720", "build_91247A720", threaded=True
        ),
        "90126A211": RecipeMetadata(
            "diagnostics.diag_build_90126A211", "build_90126A211", threaded=False
        ),
        "92240A540": RecipeMetadata(
            "diagnostics.diag_build_92240A540", "build_92240A540", threaded=True
        ),
        "99607A213": RecipeMetadata(
            "diagnostics.diag_build_99607A213", "build_99607A213", threaded=True
        ),
        "90280A199": RecipeMetadata(
            "diagnostics.diag_build_90280A199", "build_90280A199", threaded=True
        ),
        "91882A221": RecipeMetadata(
            "diagnostics.diag_build_91882A221", "build_91882A221", threaded=True
        ),
        "98296A026": RecipeMetadata(
            "diagnostics.diag_build_98296A026", "build_98296A026", threaded=False
        ),
        "98296A027": RecipeMetadata(
            "diagnostics.diag_build_98296A027", "build_98296A027", threaded=False
        ),
        "98296A031": RecipeMetadata(
            "diagnostics.diag_build_98296A031", "build_98296A031", threaded=False
        ),
        "9489T111": RecipeMetadata(
            "diagnostics.diag_build_9489T111", "build_9489T111", threaded=True
        ),
        "9490T1": RecipeMetadata(
            "diagnostics.diag_build_9490T1", "build_9490T1", threaded=True
        ),
        "9275K141": RecipeMetadata(
            "diagnostics.diag_build_9275K141", "build_9275K141", threaded=False
        ),
        "9414T1": RecipeMetadata(
            "diagnostics.diag_build_9414T1", "build_9414T1", threaded=False
        ),
        "98381A433": RecipeMetadata(
            "diagnostics.diag_build_98381A433", "build_98381A433", threaded=False
        ),
        "98381A434": RecipeMetadata(
            "diagnostics.diag_build_98381A434", "build_98381A434", threaded=False
        ),
        "98381A474": RecipeMetadata(
            "diagnostics.diag_build_98381A474", "build_98381A474", threaded=False
        ),
        "91794A055": RecipeMetadata(
            "diagnostics.diag_build_91794A055", "build_91794A055", threaded=True
        ),
        "91790A196": RecipeMetadata(
            "diagnostics.diag_build_91790A196", "build_91790A196", threaded=True
        ),
        "97431A260": RecipeMetadata(
            "diagnostics.diag_build_97431A260", "build_97431A260", threaded=False
        ),
        "9715K43": RecipeMetadata(
            "diagnostics.diag_build_9715K43", "build_9715K43", threaded=False
        ),
    }
)


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
) -> dict[str, str]:
    """Create, normalize, finish, and save one production stock part.

    ``screw_axis_planes`` restores the stable ``ScrewAxis`` mate contract for
    assemblies whose normalized stock body axis is not represented by a
    transformed recipe reference.
    """

    check("create_part", await adapter.create_part())
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    component_count = 0
    threaded = False
    try:
        for component_count, component in enumerate(components, 1):
            metadata = _recipe_metadata(component.sku)
            threaded = threaded or metadata.threaded
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
                # Sketch inference / automatic relations are APPLICATION-level
                # preferences, so a seat carries whatever the last leaf left
                # behind -- including a suppression block that never unwound
                # (SolidWorks crash, COM disconnect, watchdog exit, killed
                # process).  Every recipe asserts the state it requires instead
                # of inheriting it, which also repairs a seat an earlier leaf
                # poisoned.  Imported here, not at module scope, to keep the
                # build-graph note at the top of this file true.
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
    return await _save_stock_part(adapter, part_name, threaded=threaded)


async def _save_stock_part(
    adapter: Any, part_name: str, *, threaded: bool
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
        # "<cfg> Simplified" suppresses the helical cut for assembly views.
        return await save_simplified_part(adapter, part_name, (THREAD_FEATURE,))
    return await save_part_and_images(adapter, part_name)
