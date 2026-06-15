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
    assert_components_fully_defined,
    assert_model_healthy,
    check,
    check_no_interference,
    coincident_mate,
    log,
    named_ref,
    run_build,
)

ASM_NAME = "harmonic-analyzer"
DRIVE_TRAIN_COMP = "drive-train-1"  # 2nd subassembly inserted (frame is 1st)

REST = "Default"  # cone engaged -- the rest/render pose, drive-train @ Default
CONE_DISENGAGED = "cone_disengaged"  # drive-train @ its own cone_disengaged
CHILD_REST = "Default"  # the drive-train config referenced at rest

# operating: the full device with the crank FREE to turn. The drive-train is
# inserted rigid + FIXED, so its internal crank DOF cannot move at the top level.
# A sub must be FLOATED before it can go flexible -- but float/fix is GLOBAL in
# SOLIDWORKS, not config-scoped (proven live: floating in operating un-fixed
# Default too). So the durable fix is to replace the drive-train's fixed-flag
# grounding with three coincident principal-plane mates (its planes <-> the
# assembly planes, at identity -> SAME pose, renders unchanged; this is also the
# project's "replace fix anchoring with semantic relations" direction). Then:
#
#   Default / cone_disengaged  drive-train RIGID, grounding mates ACTIVE -> the
#                              mates fully define it at identity (bit-exact pose).
#   operating                  drive-train FLEXIBLE + grounding mates SUPPRESSED
#                              (config-scoped): the flexible sub self-grounds via
#                              its own internal fixed base (arbor/pedestals/posts),
#                              and the suppressed crank driver in the operating
#                              child frees the crank -> hand-drag / motor-drive.
#
# reset_pose.py returns the full model to Default (rigid, grounding mates live).
OPERATING = "operating"
CHILD_OPERATING = "operating"  # the drive-train child config: crank driver freed
# The drive-train's principal planes -> the assembly's, a non-drifting full
# grounding at identity (SW reports principal-plane-to-principal-plane as fully
# defined, not over-defined). Suppressed in operating, where the sub is flexible.
GROUNDING_PLANES = ("Front Plane", "Top Plane", "Right Plane")
_SOLVING_NAME = {0: "rigid", 1: "flexible"}


def _solving(adapter: Any, comp_name: str) -> str:
    """``"rigid"``/``"flexible"`` for ``comp_name`` (IComponent2::Solving)."""
    from solidworks_mcp.adapters.solidworks.assembly import _get_component

    comp = _get_component(adapter, comp_name)
    if comp is None:
        raise RuntimeError(f"{comp_name} not found in {ASM_NAME}")
    code = int(adapter._attempt(lambda: comp.Solving, default=-1))
    return _SOLVING_NAME.get(code, f"code{code}")


def _is_fixed(adapter: Any, comp_name: str) -> bool:
    """True when ``comp_name`` is fixed in the ACTIVE config (IComponent2::IsFixed)."""
    from solidworks_mcp.adapters.solidworks.assembly import _get_component

    comp = _get_component(adapter, comp_name)
    if comp is None:
        raise RuntimeError(f"{comp_name} not found in {ASM_NAME}")
    return bool(adapter._attempt(lambda: comp.IsFixed(), default=False))


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
    """rest is the bit-exact render pose: drive-train @ Default, RIGID, grounded.

    After the grounding conversion the sub is mate-grounded (not fixed-flag), so
    the leak gate is: references the Default child, solve mode RIGID, and the
    whole assembly is fully defined (0 DOF) and interference-free -- the same
    gates the render build uses. If operating's flex bled into Default (solve mode
    not config-scoped) or a grounding mate got wrongly suppressed here, this trips
    before save. The pose is identity either way, so renders are unchanged.
    """
    check(f"activate {REST}", await adapter.set_active_configuration(REST))
    ref = _referenced_config(adapter, DRIVE_TRAIN_COMP)
    if ref != CHILD_REST:
        raise RuntimeError(
            f"{REST}: {DRIVE_TRAIN_COMP} references {ref!r}, expected "
            f"{CHILD_REST!r} -- rest pose is not bit-exact")
    solving = _solving(adapter, DRIVE_TRAIN_COMP)
    if solving != "rigid":
        raise RuntimeError(
            f"{REST}: {DRIVE_TRAIN_COMP} is {solving}, expected rigid -- the "
            f"operating flex leaked into Default (solve mode not config-scoped)")
    log(f"{REST}: {DRIVE_TRAIN_COMP} -> {ref}, rigid -- verifying 0 DOF ...")
    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    log(f"{REST}: fully defined + interference-free (bit-exact render pose)")


async def _verify_operating(adapter: Any) -> None:
    """operating: drive-train floated + flexible + referencing its operating child.

    The crank is free here (the operating child suppressed its park driver, and
    flexible lets that DOF solve at the top), so this is NOT a 0-DOF pose -- by
    design. The gate is that the three enabling changes actually took.
    """
    check(f"activate {OPERATING}", await adapter.set_active_configuration(OPERATING))
    ref = _referenced_config(adapter, DRIVE_TRAIN_COMP)
    solving = _solving(adapter, DRIVE_TRAIN_COMP)
    fixed = _is_fixed(adapter, DRIVE_TRAIN_COMP)
    if ref != CHILD_OPERATING:
        raise RuntimeError(
            f"{OPERATING}: {DRIVE_TRAIN_COMP} references {ref!r}, expected "
            f"{CHILD_OPERATING!r} -- the operating child reference did not take")
    if solving != "flexible":
        raise RuntimeError(
            f"{OPERATING}: {DRIVE_TRAIN_COMP} is {solving}, expected flexible -- "
            f"the sub's internal crank DOF cannot solve at the top while rigid")
    if fixed:
        raise RuntimeError(
            f"{OPERATING}: {DRIVE_TRAIN_COMP} is still fixed -- a fixed sub "
            f"silently refuses to go flexible; it must be floated first")
    log(f"{OPERATING}: {DRIVE_TRAIN_COMP} -> {ref}, flexible + floated "
        f"(crank free to turn in the full model)")


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


async def _ground_drive_train(adapter: Any) -> list[str]:
    """Replace the drive-train's fixed-flag grounding with 3 principal-plane mates.

    Float the sub (so it can later go flexible -- a fixed sub refuses) then mate
    its Front/Top/Right planes coincident to the assembly's. Floating a component
    fixed AT IDENTITY leaves it exactly in place, so each mate is already satisfied
    when added (no movement, no flip side to recover). Added to the model, the
    mates are live in every config; operating suppresses them. Returns their names
    so the caller can config-scope-suppress them in operating.
    """
    from solidworks_mcp.adapters.base import ComponentRefParameters

    check(f"float {DRIVE_TRAIN_COMP}", await adapter.float_component(
        ComponentRefParameters(name=DRIVE_TRAIN_COMP)))
    names = []
    for plane in GROUNDING_PLANES:
        res = await coincident_mate(
            adapter,
            named_ref(f"{plane}@{DRIVE_TRAIN_COMP}", "PLANE"),
            named_ref(plane, "PLANE"),
            label=f"ground {DRIVE_TRAIN_COMP} {plane}")
        names.append(res["name"])
    log(f"  grounded {DRIVE_TRAIN_COMP} with plane mates {names}")
    return names


async def _build_cone_disengaged(adapter: Any, configs: list[str]) -> None:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        SetComponentConfigurationParameters,
    )

    if CONE_DISENGAGED in configs:
        log(f"{CONE_DISENGAGED} already present -- skipping create")
        return
    # cone_disengaged: derived from rest, then point the drive-train at its own
    # cone_disengaged child config -- scoped to this config only.
    check(f"create {CONE_DISENGAGED}", await adapter.create_configuration(
        CreateConfigurationParameters(
            name=CONE_DISENGAGED, parent=REST,
            comment="cone set swung out of mesh (ch.12): drive-train "
            "references its cone_disengaged config",
            description="Cone train decoupled through the full device.")))
    res = check(
        f"reference {DRIVE_TRAIN_COMP} -> {CONE_DISENGAGED}",
        await adapter.set_component_configuration(
            SetComponentConfigurationParameters(
                name=DRIVE_TRAIN_COMP, configuration=CONE_DISENGAGED)))
    log(f"  set_component_configuration -> {res}")


async def _build_operating(adapter: Any, configs: list[str]) -> None:
    """Add the operating config: re-ground, then flex + reference + suppress mates.

    Float/fix is GLOBAL, so the durable path re-grounds the drive-train with plane
    mates (live in Default/cone_disengaged), then in operating: flex the sub,
    reference its operating child, and config-scope-suppress the grounding mates
    (the flexible sub self-grounds via its internal fixed base). ORDER IS
    LOAD-BEARING: set_component_solving writes an EMPTY RefConfigName (resetting the
    child to Default), so flex MUST precede the reference; set_component_configuration
    carries the now-flexible solve mode through unchanged and writes the operating
    child last.
    """
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        SetComponentConfigurationParameters,
        SetComponentSolvingParameters,
        SuppressMateParameters,
    )

    if OPERATING in configs:
        log(f"{OPERATING} already present ({configs}) -- skipping build")
        return

    if not _is_fixed(adapter, DRIVE_TRAIN_COMP):
        raise RuntimeError(
            f"{DRIVE_TRAIN_COMP} is already floated but {OPERATING} is absent -- "
            f"inconsistent grounding state; rebuild the assembly from scratch")
    # Re-ground in Default (active here) so Default + cone_disengaged inherit the
    # float + the plane mates; Default must stay 0 DOF afterwards.
    ground_mates = await _ground_drive_train(adapter)
    await _verify_rest(adapter)

    check(f"create {OPERATING}", await adapter.create_configuration(
        CreateConfigurationParameters(
            name=OPERATING, parent=REST,
            comment="full device, crank FREE: drive-train flexible + grounding "
            "mates suppressed, references its operating child (crank driver freed)",
            description="Crank hand-draggable / motor-drivable in the full model; "
            "the flexible sub self-grounds via its internal fixed base.")))
    # create_configuration activates operating, so all changes land here.
    check(f"flexible {DRIVE_TRAIN_COMP}", await adapter.set_component_solving(
        SetComponentSolvingParameters(name=DRIVE_TRAIN_COMP, solving="flexible")))
    res = check(
        f"reference {DRIVE_TRAIN_COMP} -> {CHILD_OPERATING}",
        await adapter.set_component_configuration(
            SetComponentConfigurationParameters(
                name=DRIVE_TRAIN_COMP, configuration=CHILD_OPERATING)))
    log(f"  set_component_configuration -> {res}")
    for mate in ground_mates:
        check(f"suppress {mate}@{OPERATING}", await adapter.suppress_mate(
            SuppressMateParameters(
                name=mate, suppress=True, configuration=OPERATING)))


async def build(adapter: Any) -> dict[str, str]:
    path = str(OUT_SLDASM / f"{ASM_NAME}.SLDASM")
    check(f"open {ASM_NAME}", await adapter.open_model(path))

    # Initial sanity: rest is the engaged 0-DOF pose (works whether the drive-train
    # is still fixed-flag grounded (fresh) or already mate-grounded (re-run)).
    await _verify_rest(adapter)

    configs = check("list configurations", await adapter.list_configurations())
    await _build_cone_disengaged(adapter, configs)
    await _build_operating(adapter, configs)

    # Final verification of all three states after every change. rest LAST so the
    # doc is left on the deterministic render pose.
    await _verify_operating(adapter)
    await _verify_cone_disengaged(adapter)
    await _verify_rest(adapter)

    assert_model_healthy(adapter, label=ASM_NAME, deep=True)
    _save_assembly_in_place(adapter)
    return {"assembly": str(OUT_SLDASM / f"{ASM_NAME}.SLDASM"),
            "configs": f"{REST},{CONE_DISENGAGED},{OPERATING}"}


if __name__ == "__main__":
    sys.exit(run_build(build))
