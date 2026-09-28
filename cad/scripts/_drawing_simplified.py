r"""Derived ``<configuration> Simplified`` configurations for assembly drawing views.

Modeled gear teeth and helical thread grooves print black in a small-scale line
view of an assembly (the user's ruling, 2026-09-27). Every gear and threaded
part therefore carries, for each configuration ``P`` an assembly can place, a
DERIVED child ``P Simplified`` in which only the tooth/thread features are
suppressed. The parent keeps them, before and after: part drawings, renders,
STL and every gate keep reading ``P``. Assemblies add ``Default Simplified``
and point each component at its ``<referenced> Simplified`` child
(``_assembly``), and an assembly drawing's small line views reference it
(``_drawing_common``).

A part simplifies every configuration unless its builder names the placeable
ones. cone-gear names its twenty ``T<teeth>`` configurations: its ``Default`` is
never placed, and its teeth, authored while ``T120`` was active, read
suppressed there together with the ``Default Simplified`` child derived from it
(farm build 2 of #1102), while every ``T`` parent read them present.

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

The children are derived on the SAVED part reopened from disk, never on the
document that authored it (:func:`derive_simplified_on_saved_part`). The proof
above ran on files opened from disk; on cone-gear's authoring document, fresh
from its drawing-dimension, tolerance and property edits, the same calls raised
a modal dialog on all three farm attempts (c85a21ec4, exit 88 inside
``simplified.configs``). The reopened part is then finalized on disk the way
multi-configuration parts must be for an assembly to load their non-active
configurations: every configuration activated and force-rebuilt, its
rebuild-save mark set and read back, one silent ``Save3`` in place.

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
    stale_configurations,
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
_SAVE_SILENT = 1  # swSaveAsOptions_e.swSaveAsOptions_Silent

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
    """Suppression of ``feature`` in each of ``configurations``, in that order.

    One ``IsSuppressed2`` call per configuration: the API documents only "an
    array of Booleans" for a name array, not that it follows the input order,
    and on the farm a multi-name query came back aligned to the part's own
    configuration order (cone-gear read ``Default``'s state against ``T006``).
    """
    states: list[bool] = []
    for name in configurations:
        answer = tuple(feature.IsSuppressed2(_SPECIFY_CONFIGURATION, _bstr_array([name])) or ())
        if len(answer) != 1:
            raise RuntimeError(
                f"{feature.Name}: IsSuppressed2 for {name!r} returned {answer!r}, expected one state"
            )
        states.append(bool(answer[0]))
    return tuple(states)


def _simplified_parents(
    part_name: str, names: Sequence[str], parents: Sequence[str] | None
) -> list[str]:
    """The configurations that get a ``<P> Simplified`` child: ``parents`` when
    given, else every configuration of the part."""
    if parents is None:
        return [name for name in names if not is_simplified(name)]
    chosen = list(parents)
    if not chosen:
        raise ValueError(f"{part_name}: no configurations to simplify")
    if len(set(chosen)) != len(chosen):
        raise ValueError(f"{part_name}: duplicate simplified parents {chosen!r}")
    unknown = [name for name in chosen if name not in names or is_simplified(name)]
    if unknown:
        raise ValueError(
            f"{part_name}: simplified parents {unknown!r} are not among {list(names)}"
        )
    return chosen


def _assert_parents_keep_features(
    part_name: str, targets: Sequence[Any], parents: Sequence[str], names: Sequence[str]
) -> None:
    """Refuse to derive from a parent that already suppresses a target feature:
    a child can only be proven to suppress what its parent keeps.

    The configurations left without a child are logged, not judged, so a part
    whose unplaced configuration lacks the features says so on the record.
    """
    others = [name for name in names if name not in parents and not is_simplified(name)]
    order = [*parents, *others]
    lacking: list[str] = []
    report: list[str] = []
    for feature in targets:
        states = dict(zip(order, _suppression(feature, order), strict=True))
        lacking += [f"{feature.Name} in {parent}" for parent in parents if states[parent]]
        if others:
            report.append(f"{feature.Name} {({name: states[name] for name in others})!r}")
    if report:
        _telemetry.info(
            f"{part_name}: no simplified child for {others}; suppressed there: "
            + "; ".join(report)
        )
    if lacking:
        raise RuntimeError(
            f"{part_name}: a simplified parent must keep what its child suppresses, "
            f"but these are already suppressed: {lacking}"
        )


@_telemetry.traced("simplified.configs", label_param="part_name")
def add_simplified_configurations(
    adapter: Any,
    part_name: str,
    features: Sequence[str],
    parents: Sequence[str] | None = None,
) -> list[str]:
    """Derive ``<P> Simplified`` from each configuration ``P`` in ``parents``
    (default: every configuration of the open part), suppressing ``features``
    in the children only; return the children's names.

    Call on the saved part reopened from disk, after its configurations, BOM
    identity and configuration properties are final
    (:func:`derive_simplified_on_saved_part`). Every parent must keep
    ``features`` unsuppressed before anything is derived. Each child is
    activated and force-rebuilt and must read What's Wrong clean; the active
    configuration is restored. Nothing here saves.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    active = active_configuration_name(adapter, model)
    names = [str(name) for name in (model.GetConfigurationNames() or ())]
    already = [name for name in names if is_simplified(name)]
    if already:
        raise RuntimeError(f"{part_name}: simplified configurations already exist: {already}")
    if active not in names:
        raise RuntimeError(f"{part_name}: active configuration {active!r} not in {names}")
    parents = _simplified_parents(part_name, names, parents)
    targets = _features(model, part_name, features)
    _assert_parents_keep_features(part_name, targets, parents, names)
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
    assert_simplified_configurations(adapter, part_name, features, parents)
    _telemetry.annotate(
        configurations=len(parents), features=len(targets), feature_names=",".join(features)
    )
    _telemetry.success(
        f"{part_name}: {len(children)} simplified configuration(s) suppress {list(features)}"
    )
    return children


@_telemetry.traced("simplified.readback", label_param="part_name")
def assert_simplified_configurations(
    adapter: Any,
    part_name: str,
    features: Sequence[str],
    parents: Sequence[str] | None = None,
) -> None:
    """Prove, without switching, every ``P`` in ``parents`` (default: every
    configuration) has its derived ``P Simplified`` with exactly ``features``
    suppressed there (not in ``P``), a comment naming them and ``P``'s BOM part
    number, and that no other simplified configuration exists."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    names = [str(name) for name in (model.GetConfigurationNames() or ())]
    parents = _simplified_parents(part_name, names, parents)
    orphans = sorted(
        name
        for name in names
        if is_simplified(name) and name not in {simplified_name(p) for p in parents}
    )
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


def _close_part(adapter: Any) -> None:
    adapter.swApp.CloseDoc(str(_early_bound(adapter.currentModel, "IModelDoc2").GetTitle()))
    adapter.currentModel = None


def _save3_in_place(model: Any, *, label: str) -> None:
    """Silent in-place ``Save3``; its ``(ok, errors, warnings)`` tuple is consumed."""
    result = model.Save3(_SAVE_SILENT, 0, 0)
    if isinstance(result, (list, tuple)):
        ok, errors, warnings = bool(result[0]), int(result[1] or 0), int(result[2] or 0)
    else:
        ok, errors, warnings = bool(result), 0, 0
    _telemetry.info(f"{label}: Save3 ok={ok}, errors={errors}, warnings={warnings}")
    if not ok or errors:
        raise RuntimeError(f"{label}: Save3 failed: ok={ok}, errors={errors}, warnings={warnings}")


@_telemetry.traced("simplified.persist", label_param="part_name")
def persist_configurations_in_place(adapter: Any, part_name: str) -> None:
    """Finalize a reopened part on disk: activate and ``ForceRebuild3`` every
    configuration (the active one last, so the part stays on it), each reading
    What's Wrong clean, set and read back its rebuild-save mark, prove none
    stale, and save once in place.

    A mark set on a never-saved document, or re-applied without the rebuilds,
    did not make an assembly load the part's non-active configurations (the
    cone-gear persistence probes, 2026-09-03); this sequence did. ``Save3``
    rebuilds none of them itself, so none may be stale when it runs.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    active = active_configuration_name(adapter, model)
    names = [str(name) for name in (model.GetConfigurationNames() or ())]
    if active not in names:
        raise RuntimeError(f"{part_name}: active configuration {active!r} not in {names}")
    failures: list[str] = []
    for name in [name for name in names if name != active] + [active]:
        if active_configuration_name(adapter, model) != name and not bool(
            model.ShowConfiguration2(name)
        ):
            failures.append(f"{name}: ShowConfiguration2 refused")
            continue
        if not bool(model.ForceRebuild3(False)):
            failures.append(f"{name}: ForceRebuild3 returned False")
            continue
        faults = _hard_faults(adapter, model)
        if faults:
            failures.append(f"{name}: rebuilt with faults {faults}")
            continue
        configuration = _configuration(model, name)
        configuration.AddRebuildSaveMark = True
        if not bool(configuration.AddRebuildSaveMark):
            failures.append(f"{name}: rebuild-save mark did not set")
    if failures:
        raise RuntimeError(
            f"{part_name}: configurations did not finalize for the save: " + "; ".join(failures)
        )
    stale = stale_configurations(model, names)
    if stale:
        raise RuntimeError(f"{part_name}: configurations {stale} are stale at the final save")
    _save3_in_place(model, label=f"{part_name}: persist {len(names)} marked configuration(s)")
    _telemetry.annotate(config_count=len(names), active=active)


async def derive_simplified_on_saved_part(
    adapter: Any,
    part_name: str,
    features: Sequence[str],
    part_path: str,
    parents: Sequence[str] | None = None,
) -> None:
    """Close the just-saved part, reopen it from ``part_path``, derive the
    simplified configurations of ``parents`` (default: every configuration),
    finalize every configuration in place and close.

    The caller then reopens the file and proves the saved caches
    (``assert_saved_configurations_regenerate``) before anything force-rebuilds
    it, then reads the children back (:func:`assert_simplified_configurations`).
    """
    _close_part(adapter)
    check(
        f"reopen saved {part_name} to derive simplified configurations",
        await adapter.open_model(part_path),
    )
    add_simplified_configurations(adapter, part_name, features, parents)
    persist_configurations_in_place(adapter, part_name)
    _close_part(adapter)


async def save_simplified_part(
    adapter: Any,
    part_name: str,
    features: Sequence[str],
    views: Iterable[str] = DEFAULT_VIEWS,
) -> dict[str, str]:
    """Save, derive the simplified configurations on the saved file, and prove
    the saved caches.

    An assembly's ``Default Simplified`` activates each child from its SAVED
    cache, never rebuilt by the part's own session (cg-fx1: faulted inactive
    caches), so the part is reopened and every configuration is regenerated
    the way a placing assembly loads it, then the readback runs on the file.
    """
    artefacts = await save_part_and_images(adapter, part_name, views)
    await derive_simplified_on_saved_part(adapter, part_name, features, artefacts["part"])
    check(f"reopen saved {part_name}", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, part_name)
    assert_simplified_configurations(adapter, part_name, features)
    return artefacts
