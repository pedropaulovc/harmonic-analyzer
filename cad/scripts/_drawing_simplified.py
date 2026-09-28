r"""Derived ``<configuration> Simplified`` configurations for assembly drawing views.

Modeled gear teeth and helical thread grooves print black in a small-scale line
view of an assembly (the user's ruling, 2026-09-27). Every gear and threaded
part therefore carries, for EACH of its configurations ``P``, a DERIVED child
``P Simplified`` in which only the tooth/thread features are suppressed. The
parent is untouched: part drawings, renders, STL and every gate keep reading
``P``. Assemblies add ``Default Simplified`` and point each component at its
``<referenced> Simplified`` child (``_assembly``), and an assembly drawing's
small line views reference it (``_drawing_common``).

The ``<parent> Simplified`` naming is uniform across tiers so one component rule
serves parts and subassemblies alike. This module is part-tier: it imports no
assembly module (``check:partiso``/``check:graph``), so it joins only the
recipes of the builders that call it.

Mechanism (proven on SolidWorks 2026 against a scratch v37 drive train):
``IConfigurationManager.AddConfiguration2(child, …, ParentConfigName=P)`` makes
the derived child; ``IFeature.SetSuppression2(swSuppressFeature,
swSpecifyConfiguration, [child])`` suppresses in the child only; an activated
``ForceRebuild3`` regenerates it. The child reports its parent's BOM part number,
description and configuration-specific custom properties, so a BOM grouping a
derived configuration cannot fork a row.

Each derived configuration's comment names what it suppresses (a part: the
feature names; an assembly: a fingerprint of every component's referenced
configuration and that configuration's own comment). A child whose simplified
geometry changes therefore changes every ancestor's ``Default Simplified``
comment, which is how an in-place assembly refresh knows to re-save even when
Default's geometry is untouched.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from typing import Any

import _telemetry
from _common import (
    DEFAULT_VIEWS,
    _early_bound,
    _read_member,
    active_configuration_name,
    assert_saved_configurations_regenerate,
    check,
    save_part_and_images,
    whats_wrong,
)

SIMPLIFIED_SUFFIX = " Simplified"
SIMPLIFIED_COMMENT = "drawing views: modeled gear teeth and screw threads suppressed"

_SUPPRESS = 0  # swFeatureSuppressionAction_e.swSuppressFeature
_SPECIFY_CONFIGURATION = 3  # swInConfigurationOpts_e.swSpecifyConfiguration
_DOCUMENT_NAME = 1  # swBOMPartNumberSource_e.swBOMPartNumber_DocumentName
_CONFIGURATION_NAME = 2  # swBOMPartNumberSource_e.swBOMPartNumber_ConfigurationName
_PARENT_NAME = 4  # swBOMPartNumberSource_e.swBOMPartNumber_ParentName
_USER_SPECIFIED = 8  # swBOMPartNumberSource_e.swBOMPartNumber_UserSpecified
_REPLACE_VALUE = 2  # swCustomPropertyAddOption_e.swCustomPropertyReplaceValue

# (BOMPartNoSource, AlternateName, UseAlternateNameInBOM, Description,
#  UseDescriptionInBOM) of one configuration.
type BomIdentity = tuple[int, str, bool, str, bool]


def simplified_name(configuration: str) -> str:
    """The derived drawing configuration of ``configuration``."""
    if is_simplified(configuration):
        raise ValueError(f"{configuration!r} is already a simplified configuration")
    return configuration + SIMPLIFIED_SUFFIX


def is_simplified(configuration: str) -> bool:
    return configuration.endswith(SIMPLIFIED_SUFFIX)


def simplified_comment(identity: str) -> str:
    """A derived configuration's comment: the policy plus what it suppresses."""
    return f"{SIMPLIFIED_COMMENT} [{identity}]"


def components_identity(rows: Iterable[tuple[str, str, str]]) -> str:
    """Order-free fingerprint of an assembly's simplified components.

    One row per top-level component: its name, the configuration it references
    in ``Default Simplified`` and that configuration's own comment.
    """
    digest = hashlib.sha256(repr(sorted(rows)).encode("utf-8")).hexdigest()
    return f"components {digest[:16]}"


def child_bom_identity(
    parent: BomIdentity, parent_name: str, grandparent_name: str | None
) -> BomIdentity:
    """The BOM identity that makes ``<parent> Simplified`` print ``parent``'s number.

    "Link to Parent Configuration" (``ParentName``) prints the parent
    configuration's NAME, not its part number (SOLIDWORKS help, Component
    Options). So a parent numbered by its own name hands the child a link, but a
    parent that is itself linked prints ITS parent's name, which the child must
    pin as a user-specified number: a link would print the parent's name. The
    document name and a user-specified number carry over unchanged.
    """
    source, alternate, use_alternate, description, use_description = parent
    if source == _DOCUMENT_NAME:
        return (source, "", use_alternate, description, use_description)
    if source == _CONFIGURATION_NAME:
        return (_PARENT_NAME, "", use_alternate, description, use_description)
    if source == _PARENT_NAME:
        if grandparent_name is None:
            raise ValueError(
                f"{parent_name!r} links its part number to a parent configuration "
                "it does not have"
            )
        return (_USER_SPECIFIED, grandparent_name, True, description, use_description)
    if source == _USER_SPECIFIED:
        return (source, alternate, use_alternate, description, use_description)
    raise ValueError(f"{parent_name!r}: unknown BOM part-number source {source}")


def _bstr_array(names: Sequence[str]) -> Any:
    from solidworks_mcp.adapters.com_variant import bstr_array

    return bstr_array(list(names))


def _configuration(model: Any, name: str) -> Any:
    raw = model.GetConfigurationByName(name)
    if raw is None:
        raise RuntimeError(f"configuration {name!r} not found")
    return _early_bound(raw, "IConfiguration")


def _bom_identity(configuration: Any) -> BomIdentity:
    return (
        int(configuration.BOMPartNoSource),
        str(configuration.AlternateName or ""),
        bool(configuration.UseAlternateNameInBOM),
        str(configuration.Description or ""),
        bool(configuration.UseDescriptionInBOM),
    )


def _expected_child_identity(model: Any, parent: str) -> BomIdentity:
    configuration = _configuration(model, parent)
    grandparent = configuration.GetParent()
    return child_bom_identity(
        _bom_identity(configuration),
        parent,
        None if grandparent is None else str(_early_bound(grandparent, "IConfiguration").Name),
    )


def _property_manager(model: Any, configuration: str) -> Any:
    # A raw Extension dispatch, as _common.apply_custom_properties: the
    # parameterised CustomPropertyManager property is not a method on the
    # early-bound IModelDocExtension wrapper.
    extension = _read_member(model, "Extension")
    manager = extension.CustomPropertyManager(configuration) if extension is not None else None
    if manager is None:
        raise RuntimeError(f"CustomPropertyManager unavailable for {configuration!r}")
    return _early_bound(manager, "ICustomPropertyManager")


def _configuration_properties(model: Any, name: str) -> dict[str, tuple[int, str]]:
    """``{property: (type, raw expression)}`` of one configuration's own properties."""
    manager = _property_manager(model, name)
    properties: dict[str, tuple[int, str]] = {}
    for field in manager.GetNames() or ():
        field = str(field)
        result = manager.Get6(field, False)
        properties[field] = (int(manager.GetType2(field)), str(result[1] or ""))
    return properties


def _copy_bom_identity(model: Any, parent: str, child: str) -> None:
    target = _configuration(model, child)
    expected = _expected_child_identity(model, parent)
    # The source must be set first: any non-user-specified source clears the
    # alternate name (IConfiguration.BOMPartNoSource remarks).
    target.BOMPartNoSource = expected[0]
    if expected[0] == _USER_SPECIFIED:
        target.AlternateName = expected[1]
    target.UseAlternateNameInBOM = expected[2]
    target.Description = expected[3]
    target.UseDescriptionInBOM = expected[4]
    applied = _bom_identity(target)
    if applied != expected:
        raise RuntimeError(
            f"{child}: BOM identity did not persist: {applied!r} != {expected!r}"
        )
    properties = _configuration_properties(model, parent)
    if properties:
        manager = _property_manager(model, child)
        for field, (kind, value) in properties.items():
            manager.Add3(field, kind, value, _REPLACE_VALUE)
    copied = _configuration_properties(model, child)
    missing = {
        field: value for field, value in properties.items() if copied.get(field) != value
    }
    if missing:
        raise RuntimeError(
            f"{child}: configuration properties did not copy from {parent}: {missing!r}"
        )


def _hard_faults(adapter: Any, model: Any) -> list[str]:
    return [
        f"{name} ({code})" for name, code, warning in whats_wrong(adapter, model) if not warning
    ]


def _features(model: Any, part_name: str, names: Sequence[str]) -> list[Any]:
    if not names:
        raise ValueError(f"{part_name}: no tooth/thread features to simplify")
    if len(set(names)) != len(names):
        raise ValueError(f"{part_name}: duplicate simplified features {list(names)!r}")
    part = _early_bound(model, "IPartDoc")
    found = []
    missing = []
    for name in names:
        feature = part.FeatureByName(name)
        if feature is None:
            missing.append(name)
        else:
            found.append(_early_bound(feature, "IFeature"))
    if missing:
        raise RuntimeError(f"{part_name}: simplified features {missing!r} not found")
    return found


def _suppression(feature: Any, configurations: Sequence[str]) -> tuple[bool, ...]:
    states = feature.IsSuppressed2(_SPECIFY_CONFIGURATION, _bstr_array(configurations))
    return tuple(bool(state) for state in (states or ()))


@_telemetry.traced("simplified.configs", label_param="part_name")
def add_simplified_configurations(
    adapter: Any, part_name: str, features: Sequence[str]
) -> list[str]:
    """Derive ``<P> Simplified`` from every configuration ``P`` of the open part,
    suppressing ``features`` in the children only; return the children's names.

    Call after the part's configurations, BOM identity and configuration
    properties are final and before its save (``save_part_and_images`` then
    proves no configuration stale). Each child is activated and force-rebuilt
    and must read What's Wrong clean; the active configuration is restored.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    active = active_configuration_name(adapter, model)
    parents = [str(name) for name in (model.GetConfigurationNames() or ())]
    already = [name for name in parents if is_simplified(name)]
    if already:
        raise RuntimeError(f"{part_name}: simplified configurations already exist: {already}")
    if active not in parents:
        raise RuntimeError(f"{part_name}: active configuration {active!r} not in {parents}")
    targets = _features(model, part_name, features)
    comment = simplified_comment(", ".join(features))
    children: list[str] = []
    failures: list[str] = []
    for parent in parents:
        child = simplified_name(parent)
        if active_configuration_name(adapter, model) != parent and not bool(
            model.ShowConfiguration2(parent)
        ):
            failures.append(f"{parent}: ShowConfiguration2 refused")
            continue
        created = manager.AddConfiguration2(child, comment, "", 0, parent, "", False)
        if created is None:
            failures.append(f"{child}: AddConfiguration2 returned None")
            continue
        derived_from = _early_bound(created, "IConfiguration").GetParent()
        if derived_from is None or str(_early_bound(derived_from, "IConfiguration").Name) != parent:
            failures.append(f"{child}: not derived from {parent}")
            continue
        if active_configuration_name(adapter, model) != child and not bool(
            model.ShowConfiguration2(child)
        ):
            failures.append(f"{child}: ShowConfiguration2 refused")
            continue
        refused = [
            str(feature.Name)
            for feature in targets
            if not bool(feature.SetSuppression2(_SUPPRESS, _SPECIFY_CONFIGURATION, _bstr_array([child])))
        ]
        if refused:
            failures.append(f"{child}: SetSuppression2 refused {refused}")
            continue
        if not bool(model.ForceRebuild3(False)):
            failures.append(f"{child}: ForceRebuild3 returned False")
            continue
        faults = _hard_faults(adapter, model)
        if faults:
            failures.append(f"{child}: rebuilt with faults {faults}")
            continue
        _copy_bom_identity(model, parent, child)
        children.append(child)
    if active_configuration_name(adapter, model) != active and not bool(
        model.ShowConfiguration2(active)
    ):
        failures.append(f"restoring {active}: ShowConfiguration2 refused")
    if failures:
        raise RuntimeError(
            f"{part_name}: simplified configurations failed: " + "; ".join(failures)
        )
    assert_simplified_configurations(adapter, part_name, features)
    _telemetry.annotate(
        configurations=len(parents), features=len(targets), feature_names=",".join(features)
    )
    _telemetry.success(
        f"{part_name}: {len(children)} simplified configuration(s) suppress {list(features)}"
    )
    return children


@_telemetry.traced("simplified.readback", label_param="part_name")
def assert_simplified_configurations(
    adapter: Any, part_name: str, features: Sequence[str]
) -> None:
    """Prove, without switching, every ``P`` has its derived ``P Simplified``
    with exactly ``features`` suppressed there (not in ``P``), a comment naming
    them and ``P``'s BOM part number."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    names = [str(name) for name in (model.GetConfigurationNames() or ())]
    parents = [name for name in names if not is_simplified(name)]
    orphans = sorted(set(names) - set(parents) - {simplified_name(p) for p in parents})
    targets = _features(model, part_name, features)
    comment = simplified_comment(", ".join(features))
    failures: list[str] = [f"orphan simplified configurations {orphans}"] if orphans else []
    for parent in parents:
        child = simplified_name(parent)
        if child not in names:
            failures.append(f"{parent}: no {child!r}")
            continue
        configuration = _configuration(model, child)
        derived_from = configuration.GetParent()
        if derived_from is None or str(_early_bound(derived_from, "IConfiguration").Name) != parent:
            failures.append(f"{child}: not derived from {parent}")
        if str(configuration.Comment or "") != comment:
            failures.append(f"{child}: comment {configuration.Comment!r} != {comment!r}")
        for feature in targets:
            states = _suppression(feature, [parent, child])
            if states != (False, True):
                failures.append(
                    f"{feature.Name}: suppressed in ({parent}, {child}) reads {states}"
                )
        identity = _bom_identity(configuration)
        expected = _expected_child_identity(model, parent)
        if identity != expected:
            failures.append(f"{child}: BOM identity {identity!r} != {expected!r}")
    if failures:
        raise RuntimeError(
            f"{part_name}: simplified configuration readback failed: " + "; ".join(failures)
        )
    _telemetry.annotate(parents=len(parents), features=len(targets))


async def save_simplified_part(
    adapter: Any,
    part_name: str,
    features: Sequence[str],
    views: Iterable[str] = DEFAULT_VIEWS,
) -> dict[str, str]:
    """Add the simplified configurations, save, and prove the saved caches.

    An assembly's ``Default Simplified`` activates each child from its SAVED
    cache, never rebuilt by the part's own session (cg-fx1: faulted inactive
    caches), so the part is reopened and every configuration is regenerated
    the way a placing assembly loads it, then the readback runs on the file.
    """
    add_simplified_configurations(adapter, part_name, features)
    artefacts = await save_part_and_images(adapter, part_name, views)
    part_title = str(_early_bound(adapter.currentModel, "IModelDoc2").GetTitle())
    adapter.swApp.CloseDoc(part_title)
    adapter.currentModel = None
    check(f"reopen saved {part_name}", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, part_name)
    assert_simplified_configurations(adapter, part_name, features)
    return artefacts
