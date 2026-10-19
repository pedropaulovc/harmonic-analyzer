"""Source-authored nominal stock cross-section, separate from installed wire.

The installed 0.8 mm envelope is an accepted in-band representation.  The
supplier's 0.0310 in nominal belongs to this separate, sketch-only
configuration; it must never be stamped onto the installed 0.8 silhouette.
"""

from __future__ import annotations

from _check import check
from _com import _early_bound
from _feature_tree import _feature_by_name, name_last_feature
from _mcmaster_9666k56 import DIA
from _mcmaster_9666k56_reference import (
    SUPPLIER_REFERENCE_CONFIGURATION,
    SUPPLIER_REFERENCE_DIMENSION,
    SUPPLIER_REFERENCE_FEATURE,
)
from _rebuild import _hard_fault_names, active_configuration_name, force_rebuild
from _sketch import SketchDims, blank_reference_sketches, ensure_fully_defined
from _sketch_circle import define_circle
from solidworks_mcp.adapters.com_variant import null_variant


_SUPPRESS_FEATURE = 0  # swFeatureSuppressionAction_e.swSuppressFeature
_THIS_CONFIGURATION = 1  # swInConfigurationOpts_e.swThisConfiguration


async def author_nominal_stock_cross_section(
    adapter, *, installed_features: tuple[str, ...]
) -> None:
    """Add the actual nominal stock circle without changing installed solids.

    ``installed_features`` is the caller's complete inventory of installed
    solid and solid-dependent features (sketches, splits, datums), in feature
    tree order.  Each one is explicitly suppressed in the sketch-only stock
    configuration; none is assumed to follow its parent's suppression.
    """
    _require_inventory(installed_features)
    dims = SketchDims()
    check("create supplier stock cross-section", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        DIA / 2.0,
        "as-supplied nominal wire stock",
        dims=dims,
        names=(None, None, SUPPLIER_REFERENCE_DIMENSION),
    )
    sketch = _early_bound(adapter.currentModel.GetActiveSketch2(), "ISketch")
    segments = tuple(sketch.GetSketchSegments() or ())
    if len(segments) != 1:
        raise RuntimeError("supplier stock cross-section is not one native circle")
    segment = _early_bound(segments[0], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("supplier stock circle did not remain construction-only")
    await ensure_fully_defined(adapter, "supplier nominal stock cross-section")
    check("exit supplier stock cross-section", await adapter.exit_sketch())
    name_last_feature(adapter, SUPPLIER_REFERENCE_FEATURE)
    dims.apply(adapter, SUPPLIER_REFERENCE_FEATURE)
    blank_reference_sketches(adapter, (SUPPLIER_REFERENCE_FEATURE,))

    await _isolate_stock_configuration(adapter, installed_features)


def _require_inventory(installed_features: tuple[str, ...]) -> None:
    """Refuse an inventory that cannot name every installed feature once."""
    if (
        type(installed_features) is not tuple
        or not installed_features
        or any(type(name) is not str or not name for name in installed_features)
        or len(set(installed_features)) != len(installed_features)
        or SUPPLIER_REFERENCE_FEATURE in installed_features
    ):
        raise ValueError(
            "installed_features must be a non-empty tuple of distinct installed "
            f"feature names, excluding {SUPPLIER_REFERENCE_FEATURE!r}; "
            f"got {installed_features!r}"
        )


def _suppression(feature) -> tuple[bool, ...]:
    """``feature``'s suppression in the ACTIVE configuration, as read."""
    return tuple(feature.IsSuppressed2(_THIS_CONFIGURATION, null_variant()) or ())


def _suppressions(adapter, names) -> dict[str, tuple[bool, ...]]:
    return {name: _suppression(_feature_by_name(adapter, name)) for name in names}


async def _isolate_stock_configuration(
    adapter, installed_features: tuple[str, ...]
) -> None:
    """Derive the sketch-only stock configuration and return to the installed one.

    AddConfiguration2 with Options = 0 activates the new configuration, and
    SolidWorks 2026 refuses ShowConfiguration2 of the already-active one, so
    every switch compares the active name first and reads it back after.
    The try starts at creation: any failure from there on returns to the
    installed configuration and proves its feature states, faults and single
    solid unchanged; a restoration failure is noted on the primary failure,
    never raised in its place.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = _early_bound(model, "IPartDoc")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    original = active_configuration_name(adapter, model)
    if not original or original == SUPPLIER_REFERENCE_CONFIGURATION:
        raise RuntimeError("wire has no active installed configuration")
    original_states = _suppressions(
        adapter, (*installed_features, SUPPLIER_REFERENCE_FEATURE)
    )
    if any(state != (False,) for state in original_states.values()):
        raise RuntimeError(
            f"installed wire configuration has suppressed features: {original_states}"
        )
    primary: BaseException | None = None
    created = manager.AddConfiguration2(
        SUPPLIER_REFERENCE_CONFIGURATION,
        "As-supplied nominal McMaster 9666K56 stock cross-section only",
        "",
        0,
        original,
        "Supplier nominal stock; not the installed envelope",
        False,
    )
    if created is None:
        raise RuntimeError("cannot create supplier nominal stock configuration")
    try:
        parent = _early_bound(created, "IConfiguration").GetParent()
        if parent is None or str(_early_bound(parent, "IConfiguration").Name) != original:
            raise RuntimeError(
                "supplier nominal stock must derive from the installed configuration"
            )
        if active_configuration_name(adapter, model) != SUPPLIER_REFERENCE_CONFIGURATION:
            if model.ShowConfiguration2(SUPPLIER_REFERENCE_CONFIGURATION) is not True:
                raise RuntimeError("cannot activate supplier nominal stock configuration")
        if active_configuration_name(adapter, model) != SUPPLIER_REFERENCE_CONFIGURATION:
            raise RuntimeError("supplier nominal stock configuration is not active")
        # Dependents first, so no feature rebuilds against a suppressed parent;
        # one already suppressed through its parent is read, not re-suppressed.
        for name in reversed(installed_features):
            feature = _feature_by_name(adapter, name)
            if _suppression(feature) != (True,):
                if (
                    feature.SetSuppression2(
                        _SUPPRESS_FEATURE, _THIS_CONFIGURATION, null_variant()
                    )
                    is not True
                ):
                    raise RuntimeError(f"cannot suppress {name} in stock configuration")
        await force_rebuild(adapter)
        stock_states = _suppressions(adapter, original_states)
        retained = [
            name for name in installed_features if stock_states[name] != (True,)
        ]
        if retained:
            raise RuntimeError(
                f"supplier stock configuration retained installed features {retained}"
            )
        if stock_states[SUPPLIER_REFERENCE_FEATURE] != (False,):
            raise RuntimeError("supplier nominal stock circle is suppressed")
        faults = _hard_fault_names(adapter, model)
        if faults:
            raise RuntimeError(f"supplier stock configuration has hard faults: {faults}")
        if tuple(part.GetBodies2(0, False) or ()):
            raise RuntimeError(
                "nominal wire stock configuration contains an installed solid"
            )
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if active_configuration_name(adapter, model) != original:
                if model.ShowConfiguration2(original) is not True:
                    raise RuntimeError("cannot restore installed wire configuration")
            if active_configuration_name(adapter, model) != original:
                raise RuntimeError("installed wire configuration is not active")
            await force_rebuild(adapter)
            restored = _suppressions(adapter, original_states)
            if restored != original_states:
                raise RuntimeError(
                    "stock suppression leaked into the installed wire: "
                    f"{restored} != {original_states}"
                )
            faults = _hard_fault_names(adapter, model)
            if faults:
                raise RuntimeError(f"restored installed wire has hard faults: {faults}")
            if len(tuple(part.GetBodies2(0, False) or ())) != 1:
                raise RuntimeError(
                    "installed wire did not retain its one solid after stock authoring"
                )
        except Exception as error:
            if primary is None:
                raise
            primary.add_note(f"restoration also failed: {error}")
