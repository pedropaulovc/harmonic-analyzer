"""Post-build assembly operations, split out of _assembly.py so their churn no
longer re-keys the 8-assembly BUILD cache.

None of these run on the assembly BUILD path (no build_<stem>_assembly.py imports
them), so they are deliberately OUTSIDE the assembly recipe/helper closure:

  * INCREMENTAL REFRESH -- refresh_assembly + helpers (reopen, re-solve, repair
    dangling mates, save in place); the cheap alternative to a from-scratch
    re-insert, invoked by refresh_assembly.py.
  * RELEASE-PREFLIGHT DOF PROOF -- load/replay recorded park specs and
    assert_park_closure (author every deferred driver -> assert 0 DOF); invoked by
    preflight_release.py / verify.py and the motion/mobility diagnostics.

Dependencies point ONE way: this module imports helpers from _assembly; _assembly
never imports this module (no build-path function calls any of these -- verified).
"""
from __future__ import annotations

import json

import _telemetry
from collections.abc import Iterable
from typing import Any

from _common import (
    DEFAULT_VIEWS,
    OUT_SLDASM,
    _FEATURE_ERROR,
    _flag,
    check,
    log,
    set_isometric_view,
)
from _assembly import (
    _byref_variant,
    _export_assembly_images,
    _massprops_sidecar,
    _mate,
    _under_constrained_components,
    assembly_geometry_digest,
    assert_components_fully_defined,
    assert_model_healthy,
    check_no_interference,
    mark_park_driver,
    park_spec_path,
    whats_wrong,
)


def load_park_specs(name: str) -> list[dict[str, Any]]:
    """Read the deferred park specs for ``<name>.SLDASM`` (``[]`` if none)."""
    path = park_spec_path(name)
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("specs", [])

async def replay_park_specs(adapter: Any, specs: list[dict[str, Any]]) -> list[str]:
    """Author every recorded deferred park driver ENGAGED on the ACTIVE assembly
    and rename it ``PARK_<key>``; return the new names.

    Used by the release preflight (and the mobility/motion diagnostics) to
    reconstitute the freed operational DOF on a reopened default-``free`` model.
    Reconstructs each :class:`MateEntityRef` from the recorded fields, replays the
    exact mate on the RECORDED side (``spec["flip"]`` -- the build's sign-derived
    seat, #185), with the original flip-recovery ``verify`` target as the safety
    net, then re-solves."""
    from solidworks_mcp.adapters.base import MateEntityRef

    names: list[str] = []
    for spec in specs:
        entities = [MateEntityRef(**e) for e in spec["entities"]]
        verify = None
        if spec.get("verify"):
            verify = (spec["verify"][0], list(spec["verify"][1]))
        res = await _mate(
            adapter,
            f"replay PARK_{spec['key']}",
            spec["kind"],
            entities,
            verify=verify,
            flip=bool(spec.get("flip", False)),
            **spec.get("params", {}),
        )
        names.append(await mark_park_driver(adapter, res, spec["key"]))
    if names:
        adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    return names

async def assert_park_closure(
    adapter: Any, specs: list[dict[str, Any]], expected_count: int
) -> None:
    """Release-preflight SUFFICIENCY gate: on a reopened default-``free`` model,
    prove the deferred park drivers are the SOLE freedom.

    * NECESSITY: the spec count equals ``expected_count`` and, before authoring,
      at least ``expected_count`` top-level components read under-constrained (the
      freedom really is present in the shipped free model).
    * SUFFICIENCY: :func:`replay_park_specs` authors every recorded driver engaged
      and re-solves; the model must then be fully defined (0 under-constrained), so
      the true free-DOF count equals the number of drivers.

    The caller MUST discard the document WITHOUT saving -- this mutates the
    in-memory model (authoring real mates), and the shipped ``.SLDASM`` must stay
    the free kinematic model."""
    with _telemetry.span("gate.park_closure") as gsp:
        gsp.set_attribute("expected_free_dof", expected_count)
        gsp.set_attribute("specs", len(specs))
        if len(specs) != expected_count:
            raise RuntimeError(
                f"park spec count {len(specs)} != expected free DOF {expected_count} "
                "-- the recorded specs disagree with the configured free-DOF count "
                "(rebuild the assembly)"
            )
        under = _under_constrained_components(adapter)
        gsp.set_attribute("free_under_constrained", len(under))
        if len(under) < expected_count:
            raise RuntimeError(
                f"expected >= {expected_count} under-constrained component(s) in the "
                f"free pose but found {len(under)}: {sorted(under)} -- the shipped "
                "model is already frozen (the deferred park drivers freed nothing)"
            )
        names = await replay_park_specs(adapter, specs)
        gsp.set_attribute("authored", len(names))
        # SUFFICIENCY: with every driver engaged the model must be rigid.
        assert_components_fully_defined(adapter)
        _telemetry.success(
            f"park closure OK: {len(under)} free -> authored {len(names)} PARK_* "
            "driver(s) -> 0 under-constrained (sufficiency); model NOT saved"
        )

def select_mates_folder(adapter: Any) -> bool:
    """Select the active assembly's Mates folder -- the precondition for
    ``IAssemblyDoc.AutoMateRepair``. The folder is a ``MateGroup`` feature that sits
    at/near the END of the top-level tree, so scan from the back (a couple of COM
    round-trips) instead of walking all ~150 component features forward (~50 s).
    Falls back to a full forward walk if an in-context feature pushed it off the
    tail."""
    model = adapter.currentModel
    count = int(adapter._attempt(lambda: model.GetFeatureCount(), default=0) or 0)
    for i in range(min(count, 8)):  # MateGroup is the last top-level feature (i=0)
        feat = adapter._attempt(lambda i=i: model.FeatureByPositionReverse(i), default=None)
        if feat is None:
            continue
        _flag(feat, "IFeature")
        if str(adapter._attempt(lambda f=feat: f.GetTypeName2(), default="")) == "MateGroup":
            return bool(adapter._attempt(lambda f=feat: f.Select2(False, 0), default=False))
    feat = adapter._attempt(lambda: model.FirstFeature(), default=None)
    while feat is not None:
        _flag(feat, "IFeature")
        if str(adapter._attempt(lambda f=feat: f.GetTypeName2(), default="")) == "MateGroup":
            return bool(adapter._attempt(lambda f=feat: f.Select2(False, 0), default=False))
        feat = adapter._attempt(lambda f=feat: f.GetNextFeature(), default=None)
    return False

def _rebuild_faults(adapter: Any) -> list[str]:
    """Non-warning What's Wrong entries for the active model, formatted for a log."""
    return [
        f"{name} [{_FEATURE_ERROR.get(code, code)}]"
        for name, code, warn in whats_wrong(adapter, adapter.currentModel)
        if not warn
    ]

def repair_dangling_mates(adapter: Any) -> int:
    """Auto-heal mates whose referenced topology was re-IDed by a from-scratch part
    rebuild (the "sharp edge"): ``IAssemblyDoc.AutoMateRepair`` re-binds the broken
    mates in place (~5 s) instead of a ~500 s full re-insert/re-mate.

    Returns the count AutoMateRepair reports as repaired. Its own return code is
    ADVISORY ONLY -- it returns PartialSuccess with a large FailedMates array (the
    assembly's already-valid mates, which it cannot "re-repair") even on a fully
    successful heal -- so the CALLER must judge success from a fresh ``whats_wrong``
    + the standard DOF/interference/health gates, never from this code.
    """
    asm = adapter.currentModel
    _flag(asm, "IAssemblyDoc")
    if not select_mates_folder(adapter):
        log("AutoMateRepair: could not select the Mates folder -- skipping repair")
        return 0
    processed, failed = _byref_variant(), _byref_variant()
    ret = adapter._attempt(lambda: asm.AutoMateRepair(processed, failed), default=-1)
    n_proc = len(list(processed.value or [])) if processed.value is not None else 0
    n_fail = len(list(failed.value or [])) if failed.value is not None else 0
    log(f"AutoMateRepair: ret={ret} (1=PartialSuccess is normal) "
        f"re-bound {n_proc} mate(s), {n_fail} already-valid skipped")
    return n_proc

def save_assembly_in_place(adapter: Any, asm_name: str, geometry_changed: bool) -> None:
    """Save ``<asm_name>.SLDASM`` in place with a silent ``ModelDoc2.Save3``.

    For an assembly OPENED from its own path (a refresh or a config-hook reopen)
    the active doc IS the file, so the correct save is an in-place
    ``Save3(swSaveAsOptions_Silent | AvoidRebuildOnSave, &err, &warn)`` -- NOT the
    adapter's ``save_file``, both of whose branches are wrong for an
    opened-in-place doc:

      * ``save_file(PATH)`` -> SaveAs branch does ``CloseDoc(PATH)`` +
        ``os.remove(PATH)`` before ``SaveAs3``; when the active doc IS that path
        this disconnects the doc and deletes the file -- it destroyed
        drive-train.SLDASM twice.
      * ``save_file()`` (no path) -> ``Save3(1, None, None)``; ``None`` for the
        two [out] byref params fails the COM call, so it falls through to the
        blocking parameterless ``Save()`` "Component documents must be saved"
        modal.

    Passing the two [out] params as real pywin32 BYREF VARIANTs makes ``Save3``
    write silently and return the error/warning codes. The option mask is
    ``swSaveAsOptions_Silent (1) | swSaveAsOptions_AvoidRebuildOnSave (8)`` -- the
    canonical bitmask, NOT ``SaveReferenced`` (which is **4**, long mislabeled as 8
    here and in the MCP adapter's ``io.py``): ``Silent`` suppresses the save
    dialogs; ``AvoidRebuildOnSave`` skips the redundant save-time rebuild (the
    health/DOF/interference gates already ``ForceRebuild3``'d the model, so the
    in-memory geometry is current) and thereby avoids a save-triggered rebuild
    re-dirtying the referenced parts. ``SaveReferenced`` (4) is DELIBERATELY
    omitted: the referenced ``.SLDPRT``/sub-``.SLDASM`` files are the authoritative
    outputs of their own ``part:``/``assembly:`` tasks, and an assembly save must
    never rewrite them -- that is the parent-md5 byte-churn the build-idempotency
    keying in ``dodo.ContentChecker`` exists to neutralise. The mtime assertion
    proves the file was rewritten (never deleted). Proven by
    ``repro_inplace_save.py`` (ret=True, err=0, warn=0, the active config persists
    on reopen).

    ``geometry_changed`` gates the bump. Every in-place ``Save3`` rewrites fresh
    save metadata -> a new md5, and the parent's doit dep is this file's md5, so an
    unconditional save of an UNCHANGED assembly spuriously invalidates the parent
    and cascades a no-op reconciliation refresh up the tree (see
    ``_massprops_sidecar``). When the resolved-geometry fingerprint is unchanged we
    therefore skip the save outright, leaving the ``.SLDASM`` byte-identical so the
    parent stays valid. When it changed we force the rewrite even if SolidWorks
    reports the doc clean (a reload of changed PART geometry leaves the assembly's
    own data -- component refs + mates + transforms -- untouched, so ``GetSaveFlag``
    can read false): ``SetSaveFlag`` + ``Save3`` push the new geometry's md5 to the
    parent (codex review #5).
    """
    import pythoncom
    from win32com.client import VARIANT

    asm = adapter.currentModel
    sldasm = OUT_SLDASM / f"{asm_name}.SLDASM"
    if not geometry_changed:
        # No-op refresh: resolved geometry identical to the last save. Do NOT
        # rewrite -- a fresh md5 here would invalidate the parent for nothing.
        log(f"{sldasm.name}: geometry unchanged -- .SLDASM left intact (no md5 bump)")
        return

    if not bool(adapter._attempt(lambda: asm.GetSaveFlag(), default=True)):
        log(f"{sldasm.name} reported clean -- forcing rewrite for md5 propagation")
        adapter._attempt(lambda: asm.SetSaveFlag(), default=None)

    before = sldasm.stat().st_mtime
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    options = 1 | 8  # swSaveAsOptions_Silent | swSaveAsOptions_AvoidRebuildOnSave
    ret = adapter._attempt(lambda: asm.Save3(options, err, warn), default=False)

    after = sldasm.stat().st_mtime
    if after <= before:
        raise RuntimeError(
            f"{sldasm.name} mtime unchanged after Save3(Silent) "
            f"(ret={ret}, err={err.value}, warn={warn.value})")
    log(f"saved {sldasm.name} via Save3(Silent) (ret={ret}, err={err.value}, "
        f"warn={warn.value})")

async def refresh_assembly(
    adapter: Any, asm_name: str, views: Iterable[str] = DEFAULT_VIEWS
) -> dict[str, str]:
    """Reload an assembly's parts in place -- the cheap incremental rebuild.

    A ``.SLDASM`` is a thin reference layer over its part files (component refs +
    mates + transforms, not baked geometry), so when only a referenced
    ``.SLDPRT``/sub-``.SLDASM`` changed, reopening the assembly + per-config
    ``ForceRebuild3`` loads the new geometry WITHOUT re-inserting/re-mating the
    ~122 components a from-scratch ``create_assembly`` costs (~500 s). This is the
    cheap path of the incremental build graph (see ``dodo.py``).

    Self-healing, then fail loud. Every configuration is force-rebuilt. A
    non-warning What's Wrong fault -- typically a mate dangled because a
    from-scratch part rebuild re-IDed the face it selected -- first triggers an
    in-place ``AutoMateRepair`` (the broken mates re-bind in ~5 s instead of a
    ~500 s full re-insert/re-mate); only if the re-read is STILL faulted does the
    refresh raise, naming the config + the broken feature/mate. Then the
    rest/export pose is re-activated and the
    standard gates run: ``assert_components_fully_defined`` (free DOF),
    ``check_no_interference`` (overlaps), ``assert_model_healthy`` (deep mate
    health). Any gate raises a ``RuntimeError`` naming the culprit and the
    ``.SLDASM`` is left untouched (the in-place save never runs) -- so an
    UNHEALABLE dangling mate (AutoMateRepair could not re-bind it) or a geometry
    change that grows into a neighbour (interference) HALTS the build rather than
    saving a stale/broken artefact. The caller escalates to a full from-scratch
    rebuild via the ``full`` escape (delete the target + ``doit assembly:<stem>``).
    """
    asm_path = (OUT_SLDASM / f"{asm_name}.SLDASM").resolve()
    if not asm_path.exists():
        raise RuntimeError(
            f"missing assembly {asm_path}; build it from scratch first")
    with _telemetry.span("open", asm=asm_name):
        check(f"open {asm_name}", await adapter.open_model(str(asm_path)))
        configs = check("list configurations", await adapter.list_configurations())
    log(f"refresh {asm_name}: {len(configs)} configuration(s): {configs}")
    # The deterministic export/rest pose: Default is the saved, rendered pose the
    # top-level assembly references, and the DOF gate runs on it.
    rest = "Default" if "Default" in configs else (configs[0] if configs else None)

    # Per-config rebuild: load the new part geometry into EVERY configuration so a
    # config-specific break (a config whose mesh entity moved) is caught here, not
    # silently saved. Any under-defined-by-design config is NOT a fault --
    # whats_wrong reports feature/mate rebuild errors, not free DOF.
    repaired_any = False
    with _telemetry.span("rebuild_configs", count=len(configs)):
        for cfg in configs:
            with _telemetry.span("rebuild_config", config=cfg):
                check(f"activate {cfg}", await adapter.set_active_configuration(cfg))
                adapter._attempt(
                    lambda: adapter.currentModel.ForceRebuild3(False), default=None)
                faults = _rebuild_faults(adapter)
                if faults:
                    # The sharp edge: a from-scratch part rebuild re-IDs the faces
                    # its mates selected, dangling them. Auto-heal in place with
                    # AutoMateRepair before failing, then rebuild + re-read. Success
                    # is judged by the CLEAN re-read below + the standard gates --
                    # not by AutoMateRepair's own return code.
                    log(f"refresh {asm_name}: configuration {cfg!r} has {len(faults)} "
                        f"rebuild fault(s) (dangling mate / re-IDed face?); auto-healing ...")
                    repaired_any = repair_dangling_mates(adapter) > 0 or repaired_any
                    adapter._attempt(
                        lambda: adapter.currentModel.ForceRebuild3(False), default=None)
                    faults = _rebuild_faults(adapter)
                if faults:
                    raise RuntimeError(
                        f"refresh {asm_name}: configuration {cfg!r} STILL has rebuild faults "
                        f"after AutoMateRepair (unhealable -- escalate to a full rebuild: "
                        f"delete the .SLDASM target + `doit assembly:{asm_name}`): "
                        + ", ".join(faults))
                log(f"refresh {asm_name}: configuration {cfg} rebuilt clean")

    # Back to the rest pose for the gates + save: the saved active config and the
    # exported PNGs must match the from-scratch build's deterministic pose.
    if rest is not None:
        with _telemetry.span("reactivate", config=rest):
            check(f"re-activate {rest}", await adapter.set_active_configuration(rest))

    # Gates -- each already raises a RuntimeError naming the culprit. No fallback.
    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    assert_model_healthy(adapter, label=asm_name, deep=True)

    # Decide whether this refresh actually changed the resolved geometry before
    # saving: an in-place Save3 always rewrites a fresh md5, which would invalidate
    # the parent even for a no-op reload of unchanged parts. Gate the bump on the
    # mass-properties fingerprint so a true no-op leaves the .SLDASM byte-stable.
    # A successful AutoMateRepair ALSO forces the save even when the fingerprint is
    # unchanged (a PID-churn-only rebuild): the re-bound mate PIDs MUST persist, or
    # every later refresh re-dangles and re-heals the same mates forever.
    digest = await assembly_geometry_digest(adapter, asm_name)
    sidecar = _massprops_sidecar(asm_name)
    try:
        prev = sidecar.read_text(encoding="utf-8").strip()
    except OSError:
        prev = None
    geometry_changed = prev != digest or repaired_any

    with _telemetry.span("save", asm=asm_name, changed=geometry_changed):
        if geometry_changed:
            set_isometric_view(adapter)  # opens isometric; only when we actually re-save
        save_assembly_in_place(adapter, asm_name, geometry_changed)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(digest + "\n", encoding="utf-8")

    artefacts = {"assembly": str(asm_path)}
    artefacts.update(await _export_assembly_images(adapter, asm_name, views))
    return artefacts
