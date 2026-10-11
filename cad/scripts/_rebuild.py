"""Rebuild diagnostics and configuration regeneration.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

# Recipe-inert (in no cache key; see its docstring and check:inert). Imported as a
# module and used by attribute: it reads these helpers the same way, so neither
# side needs the other fully initialised at import time.
import _seat_forensics
import _telemetry
from _check import check
from _com import _early_bound, _read_member


@_telemetry.traced("save.rebuild_configs", label_param="part_name")
def rebuild_stale_configurations(adapter: Any, part_name: str) -> None:
    """Leave no configuration stale in the saved part: read first, rebuild only
    when dirty, and prove it.

    An edit made after a configuration's last rebuild can leave that
    configuration stale.  Saved that way, an assembly placing it opens with
    NeedsRebuild2=1 and fails verify:soundness's saved-rebuild-clean, and the
    #267 reconcile re-saves only the assembly, never the child.  The pc-p1r
    probe (dt-logs/pc-p1r/probe-saved-rebuild.jsonl) read MHA-135's INSTALLED
    configuration stale in the saved part, and cone-gear's unplaced Default.

    Same shape as _assembly.rebuild_if_needed_before_save (1013334c3): every
    configuration's IConfiguration.NeedsRebuild is read first, and a clean part
    -- the common case -- gets no rebuild call and no switch at all.

    A stale INACTIVE configuration is activated and force-rebuilt
    (ShowConfiguration2 + ForceRebuild3), must then read What's Wrong clean,
    and the original active configuration is shown again.  efae8d795 rebuilt
    those with one EditRebuildAll and no switch (#271 measured the cost of
    switching), but cg-fx1 (9459428ec,
    dt-logs/farm-runs/leaf-logs/cg-fx1-task.log:305-345) found that it left
    every cone-gear T00x configuration saved with ToothGapCut and
    ToothGapPattern at error 1 and NeedsRebuild false: the drive train's
    configuration swap failed its EditRebuild3, and only an activated
    ForceRebuild3 cleared the faults.  What's Wrong reads the active
    configuration only, so the no-switch path could not see them.  The user
    ruled (2026-09-27, option (a)) that the fix lives here: one switch per
    stale inactive configuration, none otherwise.  #267's objection to
    ForceRebuild3 is about an assembly's children; a part has none.

    A stale ACTIVE configuration keeps ONE IModelDocExtension.EditRebuildAll.
    A refused rebuild, any non-warning What's Wrong entry (the fleet's fault
    convention), or a configuration still stale afterwards raises, naming the
    part.  :func:`assert_saved_configurations_regenerate` proves the saved
    result the way a placing assembly loads it.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    names = [str(name) for name in (model.GetConfigurationNames() or ())]
    stale_before = stale_configurations(model, names)
    _telemetry.annotate(
        config_count=len(names),
        stale_before=len(stale_before),
        stale_before_names=",".join(stale_before[:8]),
    )
    if not stale_before:
        _telemetry.annotate(rebuild_all="skipped", stale_after=0)
        _telemetry.success(
            f"{part_name}: {len(names)} configuration(s) clean before save"
        )
        return
    active = active_configuration_name(adapter, model)
    if not active:
        raise RuntimeError(f"{part_name}: the active configuration cannot be read")
    inactive = [name for name in stale_before if name != active]
    _telemetry.annotate(stale_inactive=len(inactive))
    if inactive:
        _rebuild_inactive_while_active(adapter, model, part_name, inactive, active)
    if active in stale_before:
        _telemetry.annotate(rebuild_all="ran")
        extension = _early_bound(_read_member(model, "Extension"), "IModelDocExtension")
        if not extension.EditRebuildAll():
            raise RuntimeError(
                f"{part_name}: EditRebuildAll refused rebuilding stale configurations "
                f"{stale_before}"
            )
    faults = _hard_fault_names(adapter, model)
    if faults:
        raise RuntimeError(
            f"{part_name}: rebuilding {stale_before} left faults {faults}"
        )
    stale_after = stale_configurations(model, names)
    _telemetry.annotate(stale_after=len(stale_after))
    if stale_after:
        raise RuntimeError(
            f"{part_name}: configurations {stale_after} still need a rebuild before "
            "the save; an assembly placing one would open NeedsRebuild2=1"
        )
    _telemetry.success(
        f"{part_name}: rebuilt stale configuration(s) {stale_before} before save"
    )


def stale_configurations(model: Any, names: Iterable[str]) -> list[str]:
    """Names of the configurations whose IConfiguration.NeedsRebuild reads true."""
    return [
        name
        for name in names
        if bool(
            _early_bound(
                model.GetConfigurationByName(name), "IConfiguration"
            ).NeedsRebuild
        )
    ]


def _hard_fault_names(adapter: Any, model: Any) -> list[str]:
    """Non-warning What's Wrong entries of the ACTIVE configuration, named."""
    return [
        f"{name} ({_FEATURE_ERROR.get(code, code)})"
        for name, code, warning in whats_wrong(adapter, model)
        if not warning
    ]


def _rebuild_inactive_while_active(
    adapter: Any, model: Any, part_name: str, inactive: list[str], active: str
) -> None:
    """Activate and force-rebuild each stale inactive configuration, then show
    ``active`` again (see :func:`rebuild_stale_configurations`)."""
    failures: list[str] = []
    for name in inactive:
        if not bool(model.ShowConfiguration2(name)):
            failures.append(f"{name}: ShowConfiguration2 refused")
            continue
        if not bool(model.ForceRebuild3(False)):
            failures.append(f"{name}: ForceRebuild3 returned False")
            continue
        faults = _hard_fault_names(adapter, model)
        if faults:
            failures.append(f"{name}: {faults}")
    if not bool(model.ShowConfiguration2(active)):
        failures.append(f"restoring {active}: ShowConfiguration2 refused")
    if failures:
        raise RuntimeError(
            f"{part_name}: stale inactive configurations did not rebuild clean "
            "while active: " + "; ".join(failures)
        )


@_telemetry.traced("save.saved_configs_regenerate", label_param="part_name")
def assert_saved_configurations_regenerate(adapter: Any, part_name: str) -> None:
    """Load each configuration of a reopened part the way a placing assembly
    does, and prove it regenerates.

    An assembly that places a configuration other than the part's saved
    active one reads that configuration's saved cache and runs a plain
    ``EditRebuild3`` (the drive train's cone-gear ladder swaps 19 copies).
    cg-fx1 (9459428ec, dt-logs/farm-runs/leaf-logs/cg-fx1-task.log:305-345)
    found cone-gear's T00x caches faulted as loaded, ``EditRebuild3``
    returning False over them, and NeedsRebuild false throughout, so no
    NeedsRebuild read or forced-rebuild check can stand in for this one.

    Call it on the reopened part, before anything force-rebuilds it: each
    configuration (the saved active one last, so the part ends on it) is
    shown, What's Wrong is read as loaded, and ``EditRebuild3`` must return
    True with What's Wrong still clean.  Nothing may save afterwards.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    active = active_configuration_name(adapter, model)
    names = [str(name) for name in (model.GetConfigurationNames() or ())]
    if active not in names:
        raise RuntimeError(
            f"{part_name}: active configuration {active!r} is not among {names}"
        )
    failures: list[str] = []
    for name in [name for name in names if name != active] + [active]:
        shown = active_configuration_name(adapter, model) == name or bool(
            model.ShowConfiguration2(name)
        )
        if not shown:
            failures.append(f"{name}: ShowConfiguration2 refused")
            continue
        loaded = _hard_fault_names(adapter, model)
        rebuilt = bool(model.EditRebuild3())
        after = _hard_fault_names(adapter, model)
        _telemetry.info(
            f"{part_name} saved {name}: loaded={loaded or 'clean'}, "
            f"EditRebuild3={rebuilt}, after={after or 'clean'}"
        )
        if loaded or not rebuilt or after:
            failures.append(
                f"{name}: loaded {loaded or 'clean'}, EditRebuild3={rebuilt}, "
                f"after {after or 'clean'}"
            )
    if failures:
        raise RuntimeError(
            f"saved {part_name} configurations do not regenerate the way a "
            "placing assembly loads them (activate, then a plain EditRebuild3): "
            + "; ".join(failures)
        )
    _telemetry.success(
        f"{part_name}: {len(names)} saved configuration(s) regenerate clean as "
        "an assembly loads them"
    )


def whats_wrong(adapter: Any, model: Any) -> list[tuple[str, int, bool]]:
    """Return ``[(feature_name, error_code, is_warning), ...]`` for a model.

    Reads the What's Wrong dialog via ``GetWhatsWrong``. Early-bound
    ``IModelDocExtension::GetWhatsWrong`` collects its three ``out object`` arrays
    into the return tuple ``(retval, features, codes, warnings)`` -- pass nothing
    and consume the tuple. The old byref-VARIANT idiom leaves those VARIANTs
    UNWRITTEN under InvokeTypes, so it silently reported every model clean (a
    broken assembly would slip the deep-health gate). Empty when the model is
    clean or the call is unavailable.
    """
    ext = _read_member(model, "Extension")
    if ext is None:
        return []
    ext = _early_bound(ext, "IModelDocExtension")
    res = adapter._attempt(lambda: ext.GetWhatsWrong(), default=None)
    if not res:
        return []
    _retval, feats, codes, warns = res
    feats = list(feats or [])
    codes = list(codes or [])
    warns = list(warns or [])
    out: list[tuple[str, int, bool]] = []
    for i, feat in enumerate(feats):
        name = "?"
        if feat is not None:
            feat = _early_bound(feat, "IFeature")
            name = str(_read_member(feat, "Name"))
        code = int(codes[i]) if i < len(codes) else -1
        warn = bool(warns[i]) if i < len(warns) else False
        out.append((name, code, warn))
    return out


def active_configuration_name(adapter: Any, model: Any = None) -> str:
    """Return the active configuration name without switching or rebuilding."""
    model = model or adapter.currentModel
    manager = _read_member(model, "ConfigurationManager")
    active = (
        _read_member(manager, "ActiveConfiguration") if manager is not None else None
    )
    return str(_read_member(active, "Name") or "") if active is not None else ""


@_telemetry.traced("feature.rebuild")
async def force_rebuild(adapter: Any) -> None:
    """Force a full rebuild of the active doc, failing loud on error.

    Renamed features/dimensions register for the API immediately, but a rebuild
    makes the new names resolvable as equation targets and refreshes the tree
    labels. Delegates to the adapter's ``rebuild_model`` (``ForceRebuild3``) so
    the COM call runs on the adapter's executor thread and a failed rebuild
    raises through :func:`check` rather than passing silently.  A refused
    rebuild first names its What's Wrong features and captures the seat
    (:func:`_seat_forensics.capture_rebuild_failure`), raising the same message."""
    result = await adapter.rebuild_model()
    if not result.is_success:
        _seat_forensics.capture_rebuild_failure(
            adapter, f"rebuild failed: {result.error}"
        )
    check("rebuild", result)


# swFeatureError_e: the codes GetWhatsWrong returns. Whether an entry is a
# warning comes from GetWhatsWrong's separate is_warning array, never from
# the code: every non-warning entry is a fault, code 1 (swFeatureErrorUnknown)
# included, as verify.py and _assembly's health gates treat them.
_FEATURE_ERROR = {
    0: "none",
    1: "unknown-error",
    2: "rebuild-error",
    3: "dangling-no-members",
    4: "dangling-has-members",
    5: "sketch-overdefined",
    6: "sketch-nosolution",
    7: "sketch-overdefined-dangling",
}
