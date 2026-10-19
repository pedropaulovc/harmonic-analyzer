"""EXPLODE refresh: re-author a saved assembly's named explodes in place.

``dodo.build_or_refresh`` takes this tier (``_refresh_tier.RefreshTier.EXPLODE``)
when the only inputs that changed since the saved ``.SLDASM`` are the
assembly's explode closure, which by construction cannot reach the inserted
components, mates or configuration. Reopening the saved model, deleting each
drawing configuration's exploded views and re-running the builder's own
authoring function therefore yields the presentation a FULL build would have
saved, without the insert/mate loop.

The tier proves rather than assumes that. The reopened model must open clean,
with its simplified configuration already in sync and its resolved geometry
fingerprint equal to the proof it was published with, so the saved bytes are
the ones the proof vouches for. No part changed (else the tier is not taken),
so only a component pose could move: every top-level component's
``Transform2`` must stay numerically equal to its reopened value after
re-authoring (checked before the in-place save) and again on the reconciled
re-saved model, and the model must be collapsed when saved. The proof is
retired before the save and republished from the re-saved model, fingerprinted
exactly where a FULL build takes it. That fingerprint hashes the ``repr`` of
rounded values, so a solver-noise sign flip of a zero rotation entry
(``-0.0`` -> ``0.0``, observed on the paper drive's knob drive pins) changes
it with nothing moved; the pose comparison is numeric and does not. If a
check fails the tier raises: the subprocess exits non-zero, a failure after
the proof is retired leaves no proof on disk, and ``dodo.build_or_refresh``
falls back to a FULL build in the same task, which replaces the bytes. A
failure before the save leaves the bytes, proof and input ledger as they
were, so without that fallback the next build would pick EXPLODE again and
repeat it. PNG renders, the free-DOF manifest and every other sidecar describe
the collapsed operational model, which is unchanged, so they are kept as saved.

Kept outside every builder's import closure (refresh_assembly.py is its only
importer), so editing it re-keys no artefact.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import _telemetry
from _assembly import (
    _activate_drawing_configuration,
    _invalidate_massprops_proof,
    _massprops_sidecar,
    _restore_default_configuration,
    assembly_geometry_digest,
    final_rebuild_before_save,
    reconcile_saved_rebuild_state,
    save_assembly_in_place,
    saved_rebuild_status,
    sync_simplified_configuration,
)
from _check import check
from _com import _early_bound
from _part_save import set_isometric_view
from _paths import OUT_SLDASM
from _rebuild import active_configuration_name
from _saved_display_data import assert_saved_display_data
from _simplified_names import simplified_name
from _visibility import assert_reference_geometry_hidden

SW_SEL_EXPLVIEWS = 43  # swSelectType_e.swSelEXPLVIEWS ("EXPLODEDVIEWS")


def _require_collapsed(model: Any, asm_name: str, when: str) -> None:
    """Never save or fingerprint an exploded presentation."""
    exploded = model.IsExploded()
    if exploded is None or bool(exploded):
        raise RuntimeError(
            f"{asm_name}: the working model must be collapsed {when}, "
            f"IsExploded() returned {exploded!r}"
        )


def _delete_exploded_views(model: Any, configuration: str) -> tuple[str, ...]:
    """Delete every exploded view ``configuration`` owns; return their names.

    Exploded views are configuration-tree ``AsmExploder`` features, reachable
    by ``SelectByID2(name, "EXPLODEDVIEWS")`` (the authoring helpers select
    them the same way to rename them), and deleted like any selected feature."""
    from solidworks_mcp.adapters.com_variant import null_callout

    assembly = _early_bound(model, "IAssemblyDoc")
    names = tuple(
        str(name) for name in assembly.GetExplodedViewNames2(configuration) or ()
    )
    for name in names:
        model.ClearSelection2(True)
        if not model.Extension.SelectByID2(
            name, "EXPLODEDVIEWS", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
        ):
            raise RuntimeError(f"{name}: cannot select exploded view for deletion")
        selection = _early_bound(model.SelectionManager, "ISelectionMgr")
        if int(selection.GetSelectedObjectType3(1, 0)) != SW_SEL_EXPLVIEWS:
            raise RuntimeError(f"{name}: selection is not an exploded-view feature")
        if not model.Extension.DeleteSelection2(0):
            raise RuntimeError(f"{name}: DeleteSelection2 refused the exploded view")
        model.ClearSelection2(True)
    if not model.EditRebuild3():
        raise RuntimeError(
            f"{configuration}: EditRebuild3 failed after explode deletion"
        )
    left = tuple(assembly.GetExplodedViewNames2(configuration) or ())
    if left:
        raise RuntimeError(
            f"{configuration}: exploded views {left!r} survived deletion"
        )
    return names


# Metres and direction cosines: far below the fingerprint's 0.1 mm rounding,
# far above the collapse readback the explode authoring already enforces.
POSE_TOLERANCE = 1e-9


def _component_poses(model: Any) -> dict[str, tuple[float, ...]]:
    """Every top-level component's ``Transform2`` in the active configuration."""
    assembly = _early_bound(model, "IAssemblyDoc")
    poses = {}
    for component in assembly.GetComponents(True) or ():
        component = _early_bound(component, "IComponent2")
        transform = _early_bound(component.Transform2, "IMathTransform")
        poses[str(component.Name2)] = tuple(float(v) for v in transform.ArrayData)
    return poses


def _require_unmoved(
    asm_name: str,
    when: str,
    before: dict[str, tuple[float, ...]],
    after: dict[str, tuple[float, ...]],
) -> None:
    moved = sorted(
        name
        for name in before.keys() | after.keys()
        if name not in before
        or name not in after
        or any(abs(a - b) > POSE_TOLERANCE for a, b in zip(before[name], after[name]))
    )
    if moved:
        raise RuntimeError(
            f"{asm_name}: {len(moved)} component(s) moved {when}: "
            f"{', '.join(moved[:6])}; rebuild it from scratch"
        )


@_telemetry.traced("explode_refresh.drawing_configurations", label_param="asm_name")
def _reauthor_drawing_configurations(
    adapter: Any, asm_name: str, author: Callable[[str], None]
) -> None:
    """Preserve refresh's sync and two configuration-owned authoring passes.

    Unlike a new build, refresh already proved the saved child in sync before
    entering this authoring traversal. Keep the existing second synchronization
    and final-Default-solve contract; full-build consolidation does not change
    this tier's native work or substitute a new simplified verification gate.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    rest = "Default"
    if active_configuration_name(adapter, model) != rest:
        raise RuntimeError(
            f"{asm_name}: drawing configurations are authored from {rest!r}"
        )
    try:
        sync_simplified_configuration(adapter, asm_name)
        with _telemetry.span("simplified.author", asm=asm_name, configuration=rest):
            author(rest)
        child = simplified_name(rest)
        _activate_drawing_configuration(adapter, model, asm_name, child)
        with _telemetry.span("simplified.author", asm=asm_name, configuration=child):
            author(child)
    finally:
        _restore_default_configuration(adapter, model, asm_name)


async def refresh_explode(
    adapter: Any, asm_name: str, author: Callable[[str], None]
) -> dict[str, str]:
    """Replace ``asm_name``'s named explodes with ``author``'s, in place.

    ``author`` is the builder's own per-configuration explode function bound to
    ``adapter`` (``lambda configuration: fn(adapter, configuration)``); it runs
    in ``Default`` and ``Default Simplified`` exactly as the FULL build runs it."""
    asm_path = (OUT_SLDASM / f"{asm_name}.SLDASM").resolve()
    if not asm_path.exists():
        raise RuntimeError(f"missing assembly {asm_path}; build it from scratch first")
    assert_saved_display_data(asm_path)
    sidecar = _massprops_sidecar(asm_name)
    try:
        proof = sidecar.read_text(encoding="utf-8").strip()
    except OSError as missing:
        raise RuntimeError(
            f"{asm_name}: no geometry proof {sidecar.name} for the saved model; "
            "the explode tier reuses its gates and needs the proof to compare against"
        ) from missing

    with _telemetry.span("open", asm=asm_name):
        check(f"open {asm_name}", await adapter.open_model(str(asm_path)))
        opened_status = saved_rebuild_status(adapter)
    if opened_status != 0:
        raise RuntimeError(
            f"{asm_name}: saved model opened with NeedsRebuild2={opened_status}; "
            "the explode tier only re-authors a clean model"
        )
    drift = sync_simplified_configuration(adapter, asm_name)
    if drift:
        raise RuntimeError(
            f"{asm_name}: Default Simplified needed {drift} change(s) on reopen; "
            "that is not an explode-only change"
        )
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    _require_collapsed(model, asm_name, "before re-authoring")
    opened = await assembly_geometry_digest(adapter, asm_name)
    if opened != proof:
        raise RuntimeError(
            f"{asm_name}: the saved model fingerprints {opened[:12]}, not its proof "
            f"{proof[:12]}; rebuild it from scratch"
        )
    poses = _component_poses(model)

    def reauthor(configuration: str) -> None:
        with _telemetry.span(
            "explode_refresh.delete", configuration=configuration
        ) as sp:
            removed = _delete_exploded_views(model, configuration)
            sp.set_attribute("views", ",".join(removed))
        _telemetry.info(
            f"explode refresh {asm_name}: {configuration} deleted {removed!r}"
        )
        author(configuration)

    _reauthor_drawing_configurations(adapter, asm_name, reauthor)
    final_rebuild_before_save(adapter, asm_name)
    assert_reference_geometry_hidden(adapter, asm_name)
    _require_unmoved(
        asm_name, "re-authoring the explode", poses, _component_poses(model)
    )
    _require_collapsed(model, asm_name, "before save")
    # Retire the proof before the bytes it vouches for are replaced.
    _invalidate_massprops_proof(sidecar)
    with _telemetry.span("save", asm=asm_name, changed=True):
        set_isometric_view(adapter)
        save_assembly_in_place(adapter, asm_name, True)
    await reconcile_saved_rebuild_state(adapter, asm_name, asm_path)
    saved = _early_bound(adapter.currentModel, "IModelDoc2")
    _require_unmoved(asm_name, "in the re-saved model", poses, _component_poses(saved))
    persisted = await assembly_geometry_digest(adapter, asm_name)
    _telemetry.info(
        f"explode refresh {asm_name}: geometry proof {proof[:12]} -> "
        f"{persisted[:12]}, {len(poses)} component poses unchanged"
    )
    sidecar.write_text(persisted + "\n", encoding="utf-8")
    return {"assembly": str(asm_path)}
