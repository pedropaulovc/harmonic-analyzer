"""EXPLODE refresh: re-author a saved assembly's named explodes in place.

``dodo.build_or_refresh`` takes this tier (``_refresh_tier.RefreshTier.EXPLODE``)
when the only inputs that changed since the saved ``.SLDASM`` are the
assembly's explode closure, which by construction cannot reach the inserted
components, mates or configuration. Reopening the saved model, deleting each
drawing configuration's exploded views and re-running the builder's own
authoring function therefore yields the presentation a FULL build would have
saved, without the insert/mate loop.

The tier proves rather than assumes that: the reopened model must open clean
with its simplified configuration already in sync, the re-authored model must
be collapsed, and its resolved geometry fingerprint must equal the proof the
saved model was published with. Any difference raises before the in-place save.
PNG renders, the free-DOF manifest and every other sidecar describe the
collapsed operational model, which is unchanged, so they are kept as saved.

Kept outside every builder's import closure (refresh_assembly.py is its only
importer), so editing it re-keys no artefact.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import _telemetry
from _assembly import (
    _massprops_sidecar,
    assembly_geometry_digest,
    author_in_drawing_configurations,
    final_rebuild_before_save,
    reconcile_saved_rebuild_state,
    save_assembly_in_place,
    saved_rebuild_status,
    sync_simplified_configuration,
)
from _check import check, log
from _com import _early_bound
from _part_save import set_isometric_view
from _paths import OUT_SLDASM
from _saved_display_data import assert_saved_display_data
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
    drift = sync_simplified_configuration(adapter, asm_name, verify=False)
    if drift:
        raise RuntimeError(
            f"{asm_name}: Default Simplified needed {drift} change(s) on reopen; "
            "that is not an explode-only change"
        )
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    _require_collapsed(model, asm_name, "before re-authoring")

    def reauthor(configuration: str) -> None:
        with _telemetry.span(
            "explode_refresh.delete", configuration=configuration
        ) as sp:
            removed = _delete_exploded_views(model, configuration)
            sp.set_attribute("views", ",".join(removed))
        log(f"explode refresh {asm_name}: {configuration} deleted {removed!r}")
        author(configuration)

    author_in_drawing_configurations(adapter, asm_name, reauthor)
    final_rebuild_before_save(adapter, asm_name)
    _require_collapsed(model, asm_name, "after re-authoring")
    assert_reference_geometry_hidden(adapter, asm_name)
    digest = await assembly_geometry_digest(adapter, asm_name)
    if digest != proof:
        raise RuntimeError(
            f"{asm_name}: re-authoring the explode changed the resolved geometry "
            f"({proof[:12]} -> {digest[:12]}); rebuild it from scratch"
        )
    _require_collapsed(model, asm_name, "before save")
    with _telemetry.span("save", asm=asm_name, changed=True):
        set_isometric_view(adapter)
        save_assembly_in_place(adapter, asm_name, True)
    await reconcile_saved_rebuild_state(adapter, asm_name, asm_path)
    sidecar.write_text(digest + "\n", encoding="utf-8")
    return {"assembly": str(asm_path)}
