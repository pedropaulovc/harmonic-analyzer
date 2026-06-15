r"""Top-level engagement configurations for harmonic-analyzer.SLDASM.

The drive-train subassembly already carries the engagement enum as its own
configurations (``build_engagement_configs.py``: ``Default`` = cone engaged,
``cone_disengaged`` = the cone train decoupled). But the renders and the
operator-facing demos drive the TOP assembly, and a child config is invisible
from the parent until the parent chooses it. So the top assembly needs matching
configurations that point the drive-train component at the right child config:

    Default (= rest)   drive-train-1 -> drive-train/Default   (cone engaged) --
                       the saved, rendered, photo-gated pose. Bit-exact: the
                       component keeps its default referenced configuration.
    cone_disengaged    drive-train-1 -> drive-train/cone_disengaged -- selecting
                       this top config now decouples the cone train through the
                       whole device, so set_active_configuration on the FULL
                       assembly demonstrates the disengage (ch.12).

The mechanism is the new ``set_component_configuration`` adapter call
(IAssemblyDoc::CompConfigProperties5 RefConfigName), scoped to the active
assembly configuration -- so the reference is changed ONLY in cone_disengaged;
Default keeps drive-train-1 at the drive-train's Default config and renders
exactly as before. No geometry is added at the top level.

Idempotent: a re-run (or a build_all that re-opens an already-configured doc)
skips the create + reference and just re-verifies both states.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_top_engagement_configs.py
"""

from __future__ import annotations

import sys
from typing import Any

from _common import (
    OUT_SLDASM,
    assert_model_healthy,
    check,
    log,
    run_build,
)

ASM_NAME = "harmonic-analyzer"
DRIVE_TRAIN_COMP = "drive-train-1"  # 2nd subassembly inserted (frame is 1st)

REST = "Default"  # cone engaged -- the rest/render pose, drive-train @ Default
CONE_DISENGAGED = "cone_disengaged"  # drive-train @ its own cone_disengaged
CHILD_REST = "Default"  # the drive-train config referenced at rest


def _referenced_config(adapter: Any, comp_name: str) -> str:
    """Child configuration ``comp_name`` references in the ACTIVE assembly config.

    Reads ``IComponent2::ReferencedConfiguration`` off the resolved component
    via the adapter's own ``_get_component`` (same lookup the setter uses), so
    the verification sees exactly what the setter wrote.
    """
    from solidworks_mcp.adapters.solidworks.assembly import _get_component

    comp = _get_component(adapter, comp_name)
    if comp is None:
        raise RuntimeError(f"{comp_name} not found in {ASM_NAME}")
    return str(adapter._attempt(lambda: comp.ReferencedConfiguration, default=""))


def _save_assembly_in_place(adapter: Any) -> None:
    """Save harmonic-analyzer.SLDASM in place with a silent ``Save3``.

    The doc was OPENED from this path, so the active doc IS the file; the right
    save is an in-place ``Save3(swSaveAsOptions_Silent | SaveReferenced, &err,
    &warn)`` with real pywin32 BYREF VARIANTs (a bare ``None`` for the [out]
    params fails the COM call and forces the blocking ``Save()`` modal). Only
    the top assembly's config + a component reference change here; the child
    docs are untouched.
    """
    import pythoncom
    from win32com.client import VARIANT

    asm = adapter.currentModel
    sldasm = OUT_SLDASM / f"{ASM_NAME}.SLDASM"
    if not bool(adapter._attempt(lambda: asm.GetSaveFlag(), default=True)):
        log(f"{sldasm.name} already clean -- nothing to save")
        return

    before = sldasm.stat().st_mtime
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    options = 1 | 8  # swSaveAsOptions_Silent | swSaveAsOptions_SaveReferenced
    ret = adapter._attempt(lambda: asm.Save3(options, err, warn), default=False)

    after = sldasm.stat().st_mtime
    if after <= before:
        raise RuntimeError(
            f"{sldasm.name} mtime unchanged after Save3(Silent) "
            f"(ret={ret}, err={err.value}, warn={warn.value})")
    log(f"saved {sldasm.name} via Save3(Silent) (ret={ret}, err={err.value}, "
        f"warn={warn.value})")


async def _verify_rest(adapter: Any) -> None:
    """rest is the bit-exact render pose: drive-train references its Default."""
    check(f"activate {REST}", await adapter.set_active_configuration(REST))
    ref = _referenced_config(adapter, DRIVE_TRAIN_COMP)
    if ref != CHILD_REST:
        raise RuntimeError(
            f"{REST}: {DRIVE_TRAIN_COMP} references {ref!r}, expected "
            f"{CHILD_REST!r} -- rest pose is not bit-exact")
    log(f"{REST}: {DRIVE_TRAIN_COMP} -> {ref} (cone engaged, bit-exact)")


async def _verify_cone_disengaged(adapter: Any) -> None:
    """cone_disengaged: drive-train references its own cone_disengaged config."""
    check(f"activate {CONE_DISENGAGED}", await adapter.set_active_configuration(
        CONE_DISENGAGED))
    ref = _referenced_config(adapter, DRIVE_TRAIN_COMP)
    if ref != CONE_DISENGAGED:
        raise RuntimeError(
            f"{CONE_DISENGAGED}: {DRIVE_TRAIN_COMP} references {ref!r}, expected "
            f"{CONE_DISENGAGED!r} -- the child config reference did not take")
    log(f"{CONE_DISENGAGED}: {DRIVE_TRAIN_COMP} -> {ref} (cone train decoupled)")


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        SetComponentConfigurationParameters,
    )

    path = str(OUT_SLDASM / f"{ASM_NAME}.SLDASM")
    check(f"open {ASM_NAME}", await adapter.open_model(path))

    # rest stays the Default config; assert the drive-train is cone-engaged.
    await _verify_rest(adapter)

    configs = check("list configurations", await adapter.list_configurations())
    if CONE_DISENGAGED in configs:
        log(f"{CONE_DISENGAGED} already present ({configs}) -- re-verifying only")
    else:
        # cone_disengaged: derived from rest, then point the drive-train at its
        # own cone_disengaged child config -- scoped to this config only.
        check(f"create {CONE_DISENGAGED}", await adapter.create_configuration(
            CreateConfigurationParameters(
                name=CONE_DISENGAGED, parent=REST,
                comment="cone set swung out of mesh (ch.12): drive-train "
                "references its cone_disengaged config",
                description="Cone train decoupled through the full device.")))
        # create_configuration activates the new config, so the reference is
        # written into cone_disengaged with no extra switch.
        res = check(
            f"reference {DRIVE_TRAIN_COMP} -> {CONE_DISENGAGED}",
            await adapter.set_component_configuration(
                SetComponentConfigurationParameters(
                    name=DRIVE_TRAIN_COMP, configuration=CONE_DISENGAGED)))
        log(f"  set_component_configuration -> {res}")

    await _verify_cone_disengaged(adapter)

    # Back to rest: the reference must still be Default (the change was scoped
    # to cone_disengaged only) so the rendered pose is untouched.
    await _verify_rest(adapter)

    assert_model_healthy(adapter, label=ASM_NAME, deep=True)
    _save_assembly_in_place(adapter)
    return {"assembly": str(OUT_SLDASM / f"{ASM_NAME}.SLDASM"),
            "configs": f"{REST},{CONE_DISENGAGED}"}


if __name__ == "__main__":
    sys.exit(run_build(build))
