"""Named native members of one purchased SKU, without duplicate native files.

Member selection, suppression and metadata are checked against native state.
Saved-cache finalization reuses the existing multi-configuration part path;
there are no Default aliases or synthetic Simplified members.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

import _config
from _check import check
from _com import _early_bound, _read_member
from _configuration_material import require_material_in_every_configuration
from _part_configuration_exports import export_member_configurations, member_configurations
from _part_save import save_part_and_images
from _rebuild import active_configuration_name, assert_saved_configurations_regenerate
from _simplified_part import _bom_identity, _close_part, persist_configurations_in_place


async def activate_member(adapter: Any, configuration: str) -> None:
    """Select an existing member and reject a refused or misdirected switch."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if model.GetConfigurationByName(configuration) is None:
        raise RuntimeError(f"native member {configuration!r} does not exist")
    if active_configuration_name(adapter, model) != configuration:
        check(
            f"activate native member {configuration}",
            await adapter.set_active_configuration(configuration),
        )
    require_active_member(adapter, configuration)


def require_active_member(adapter: Any, configuration: str) -> None:
    active = active_configuration_name(adapter)
    if active != configuration:
        raise RuntimeError(f"native member {configuration!r} requested, active member is {active!r}")


def require_member_configurations(
    part_name: str, configurations: Sequence[str]
) -> tuple[str, ...]:
    """Refuse registry/member order drift before authoring or saving a native."""
    names = tuple(configurations)
    expected = member_configurations(part_name)
    if not expected or names != expected:
        raise ValueError(
            f"{part_name}: native members {names!r} differ from registry order {expected!r}"
        )
    return expected


async def create_member_configurations(
    adapter: Any, part_name: str, configurations: Sequence[str]
) -> None:
    """Replace the fresh part's Default with the registry's real named members."""
    from solidworks_mcp.adapters.base import CreateConfigurationParameters

    names = require_member_configurations(part_name, configurations)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    initial = tuple(str(name) for name in (model.GetConfigurationNames() or ()))
    if len(initial) != 1:
        raise RuntimeError(f"member authoring requires a fresh single-configuration part, got {initial!r}")
    original = _early_bound(model.GetConfigurationByName(initial[0]), "IConfiguration")
    original.Name = names[0]
    if model.GetConfigurationByName(names[0]) is None:
        raise RuntimeError(f"initial configuration did not rename to {names[0]!r}")
    for name in names[1:]:
        check(
            f"create native member {name}",
            await adapter.create_configuration(CreateConfigurationParameters(name=name, comment=name)),
        )
    actual = tuple(str(name) for name in (model.GetConfigurationNames() or ()))
    if set(actual) != set(names) or len(actual) != len(names):
        raise RuntimeError(f"native members {actual!r} differ from requested {names!r}")
    await activate_member(adapter, names[0])


def _feature(adapter: Any, name: str) -> Any:
    part = _early_bound(adapter.currentModel, "IPartDoc")
    raw = part.FeatureByName(name)
    if raw is None:
        raise RuntimeError(f"native member feature {name!r} not found")
    return _early_bound(raw, "IFeature")


def _suppressed(feature: Any) -> bool:
    from solidworks_mcp.adapters.com_variant import null_variant

    states = feature.IsSuppressed2(1, null_variant())  # swThisConfiguration
    if (
        not isinstance(states, (tuple, list))
        or len(states) != 1
        or not isinstance(states[0], bool)
    ):
        raise RuntimeError(f"{feature.Name}: invalid native suppression state {states!r}")
    return states[0]


def set_member_suppression(adapter: Any, names: Sequence[str], *, suppressed: bool) -> None:
    """Change only the active configuration, dependents before parents when hiding."""
    from solidworks_mcp.adapters.com_variant import null_variant

    for name in reversed(names) if suppressed else names:
        feature = _feature(adapter, name)
        if _suppressed(feature) == suppressed:
            continue
        if not bool(feature.SetSuppression2(0 if suppressed else 1, 1, null_variant())):
            raise RuntimeError(f"{name}: native suppression change refused")
        if _suppressed(feature) != suppressed:
            raise RuntimeError(f"{name}: native suppression change did not persist")


def assert_member_suppression(
    adapter: Any, configuration: str, members: Mapping[str, Sequence[str]]
) -> None:
    """Reject missing/foreign features even when the selected body looks plausible."""
    require_active_member(adapter, configuration)
    if configuration not in members:
        raise ValueError(f"unknown native member {configuration!r}")
    all_names = [name for names in members.values() for name in names]
    if len(all_names) != len(set(all_names)):
        raise ValueError("native member feature ownership overlaps")
    for member, names in members.items():
        expected = member != configuration
        for name in names:
            if _suppressed(_feature(adapter, name)) != expected:
                raise RuntimeError(f"{configuration}: feature {name!r} has wrong member suppression ({member})")


async def select_member_features(
    adapter: Any, configuration: str, members: Mapping[str, Sequence[str]]
) -> None:
    await activate_member(adapter, configuration)
    if configuration not in members:
        raise ValueError(f"unknown native member {configuration!r}")
    for member, names in reversed(tuple(members.items())):
        if member != configuration:
            set_member_suppression(adapter, names, suppressed=True)
    set_member_suppression(adapter, members[configuration], suppressed=False)
    assert_member_suppression(adapter, configuration, members)


def _member_properties(
    part_name: str, configuration: str, description: str, properties: Mapping[str, str]
) -> dict[str, str]:
    row = _config.parts(part_name)
    quantities = row["configuration_quantities"]
    if configuration not in quantities:
        raise ValueError(f"{part_name}: no quantity for native member {configuration!r}")
    return {
        **properties,
        "Number": str(row["number"]),
        "Description": description,
        "Quantity": str(quantities[configuration]),
    }


def _property_manager(adapter: Any, configuration: str) -> Any:
    extension = _read_member(adapter.currentModel, "Extension")
    raw = extension.CustomPropertyManager(configuration) if extension is not None else None
    if raw is None:
        raise RuntimeError(f"CustomPropertyManager unavailable for member {configuration!r}")
    return _early_bound(raw, "ICustomPropertyManager")


def apply_member_properties(
    adapter: Any,
    part_name: str,
    configuration: str,
    description: str,
    properties: Mapping[str, str],
) -> None:
    """Give heterogeneous rows distinct grouping keys but one purchase Number."""
    require_active_member(adapter, configuration)
    manager = _property_manager(adapter, configuration)
    for name, value in _member_properties(part_name, configuration, description, properties).items():
        manager.Add3(name, 30, str(value), 2)
    native = _early_bound(adapter.currentModel.GetConfigurationByName(configuration), "IConfiguration")
    native.BOMPartNoSource = 8  # swBOMPartNumber_UserSpecified
    native.AlternateName = f"{part_name}--{configuration}"
    native.UseAlternateNameInBOM = True
    native.Description = description
    native.UseDescriptionInBOM = True
    assert_member_properties(adapter, part_name, configuration, description, properties)


def assert_member_properties(
    adapter: Any,
    part_name: str,
    configuration: str,
    description: str,
    properties: Mapping[str, str],
) -> None:
    require_active_member(adapter, configuration)
    model = adapter.currentModel
    for name, value in _member_properties(part_name, configuration, description, properties).items():
        observed = str(model.GetCustomInfoValue(configuration, name) or "").replace("\r\n", "\n")
        if observed != str(value).replace("\r\n", "\n"):
            raise RuntimeError(f"{configuration}: property {name!r} reads {observed!r}, expected {value!r}")
    native = _early_bound(model.GetConfigurationByName(configuration), "IConfiguration")
    observed_bom = _bom_identity(native)
    expected_bom = (8, f"{part_name}--{configuration}", True, description, True)
    if observed_bom != expected_bom:
        raise RuntimeError(f"{configuration}: native BOM identity {observed_bom!r} != {expected_bom!r}")


def require_member_bodies(
    adapter: Any, configuration: str, count: int, references: Sequence[str]
) -> None:
    require_active_member(adapter, configuration)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())
    if len(bodies) != count:
        raise RuntimeError(f"{configuration}: {len(bodies)} native solid bodies, expected {count}")
    for name in references:
        if _suppressed(_feature(adapter, name)):
            raise RuntimeError(f"{configuration}: required reference {name!r} is suppressed")


def require_member_colour(
    adapter: Any, configuration: str, rgb: tuple[float, float, float]
) -> None:
    """Read the selected member's persisted native appearance, without repair."""
    require_active_member(adapter, configuration)
    observed = tuple(float(value) for value in (adapter.currentModel.MaterialPropertyValues or ())[:3])
    if len(observed) != 3 or any(
        not abs(got - expected) <= 1.0 / 255.0
        for got, expected in zip(observed, rgb, strict=True)
    ):
        raise RuntimeError(
            f"{configuration}: native colour {observed!r} differs from {rgb!r}"
        )


async def save_member_part(
    adapter: Any,
    part_name: str,
    configurations: Sequence[str],
    *,
    material: str,
    readback: Callable[[Any, str], Awaitable[None]],
) -> dict[str, str]:
    """Publish only a saved part whose actual member caches and metadata read clean."""
    names = require_member_configurations(part_name, configurations)
    for name in names:
        await activate_member(adapter, name)
        await readback(adapter, name)
    require_material_in_every_configuration(adapter, part_name, material, names)
    await activate_member(adapter, names[0])
    artefacts = await save_part_and_images(adapter, part_name)
    _close_part(adapter)
    check(f"reopen {part_name} to persist members", await adapter.open_model(artefacts["part"]))
    require_active_member(adapter, names[0])
    persist_configurations_in_place(adapter, part_name)
    _close_part(adapter)
    check(f"reopen saved {part_name} members", await adapter.open_model(artefacts["part"]))
    require_active_member(adapter, names[0])
    assert_saved_configurations_regenerate(adapter, part_name)
    for name in names:
        await activate_member(adapter, name)
        await readback(adapter, name)
    require_material_in_every_configuration(adapter, part_name, material, names)
    await activate_member(adapter, names[0])
    await export_member_configurations(adapter, part_name, names)
    return artefacts
