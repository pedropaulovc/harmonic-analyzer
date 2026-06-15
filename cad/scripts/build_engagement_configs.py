r"""Engagement configurations for the drive train (plan step 5, the state enum).

The operator's engagement state is not a scattered set of booleans -- it is a
small enum, so it maps to assembly CONFIGURATIONS of drive-train.SLDASM (where
the cone/pinion meshes live). Each is a named pose of the SAME mated model; the
difference between them is which gear meshes are live, expressed with the new
config-scoped suppress_mate (swSpecifyConfiguration).

    rest (= the Default config)   cone engaged, pinion parked out -- the saved,
                                  rendered, photo-gated pose. Stays fully defined
                                  (0 DOF) and bit-exact: untouched here.
    cone_disengaged               the 20 cone:cyl meshes + the 16T:64T crank
                                  drive suppressed -> the cone train is kinematic-
                                  ally decoupled (book ch.12: the cone set swings
                                  out so "the cylinders read zero").

TOPOLOGY (proven by the mobility probe): the whole gear train's ROTATION is
pinned by the single crank park driver flowing THROUGH the gear meshes -- not by
a per-gear spin driver. So suppressing the 21 gear meshes in cone_disengaged
necessarily frees the train's rotational DOF: exactly the 20 cone gears, the 20
cylinder gears, the cone-gear-shaft and the crank-drive-gear go under-defined.
That is the physically-honest meaning of "disengaged": the decoupled members are
free to be turned. Their geometry stays put at the last solved pose (SW does not
move under-defined bodies on rebuild), so the config is stable; it is just not a
deterministic 0-DOF pose, which is correct for a demonstration of decoupling.
Nothing STRUCTURAL (brackets, posts, shafts, the crank input side) may leak into
that freed set -- that is what _verify_config asserts.

`rest` is the model's Default configuration and is left untouched, so the
top-level harmonic-analyzer (which references the Default config) renders exactly
as before. The derived config adds no geometry; it only suppresses gear mates in
its own configuration.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_engagement_configs.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from _common import (
    OUT_SLDASM,
    assert_components_fully_defined,
    assert_model_healthy,
    check,
    check_no_interference,
    log,
    run_build,
)
from build_mobility_probe import _component_status, _under

ASM_NAME = "drive-train"
REST = "Default"  # the model's default config IS the rest/engaged pose

# Derived (parent = REST) config and the gear-mate selection it suppresses.
# Suppressing every gear mesh decouples the cone train from the cylinders and the
# crank; because the train is pinned by the single crank driver through those
# meshes, the decoupled members go under-defined (see module docstring).
CONE_DISENGAGED = "cone_disengaged"

EXPECTED_GEAR_MATES = 21  # 20 cone Tk:cyl120 + 16T:64T (drive-train build)

# The members that MUST go free when the meshes are cut, and no others: the
# rotating gear train. cone-gear-shaft starts with "cone-gear" so the prefix
# tuple covers it; crank-drive-gear is the 16T input gear.
DECOUPLED_PREFIXES = ("cone-gear", "cylinder-gear", "crank-drive-gear")
EXPECTED_DECOUPLED = 42  # 20 cone-gear + 20 cylinder-gear + cone-gear-shaft + crank-drive-gear


def _gear_mate_names(mates: list[dict[str, Any]]) -> list[str]:
    return [m["name"] for m in mates if "gear" in str(m.get("type", "")).lower()]


def _save_assembly_in_place(adapter: Any) -> None:
    """Save drive-train.SLDASM in place via the blocking ModelDoc2.Save(), with a
    watchdog that auto-clicks the "Component documents must be saved -> Save All"
    dialog.

    Why this and not the obvious silent calls (all PROVEN to fail on this
    3DEXPERIENCE Makers seat):
      * ``adapter.save_file(PATH)`` -> SaveAs branch CloseDoc(PATH)+os.remove(PATH)
        before SaveAs3; the active doc IS that path, so CloseDoc disconnects the
        doc and SaveAs3 crashes ("disconnected from its clients") AFTER the file
        is deleted -- it destroyed drive-train.SLDASM twice.
      * ``ModelDoc2.Save3(Silent[, ...])`` silently writes NOTHING for a dirty
        assembly (mtime unchanged, no dialog), with or without SaveReferenced.
      * ``ModelDocExtension.SaveAs(..., Silent, ...)`` raises a COM error.

    The ONLY save that persists the modified component references is the
    interactive one: ``Save()`` raises the "Save All" dialog and BLOCKS until it
    is answered. So launch ``_click_save_all.ps1`` (a UIAutomation watchdog) first
    -- it polls for the "Save All" button and physically clicks it -- then call
    ``Save()``; the watchdog answers the modal and the save completes headlessly.
    The on-disk mtime advancing confirms the write. A clean idempotent re-run is
    skipped up front (Save() would not prompt and there is nothing to write).
    """
    import subprocess
    import time

    asm = adapter.currentModel
    sldasm = OUT_SLDASM / f"{ASM_NAME}.SLDASM"
    asm_dirty = bool(adapter._attempt(lambda: asm.GetSaveFlag(), default=True))
    if not asm_dirty:
        log(f"{sldasm.name} already clean -- nothing to save")
        return

    before = sldasm.stat().st_mtime
    ps_script = Path(__file__).resolve().parent / "_click_save_all.ps1"
    watchdog = subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(ps_script), "-ButtonName", "Save All",
         "-TimeoutSeconds", "180"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(1.0)  # let the watchdog start polling before Save() blocks

    # Save() (parameterless) is the one call that drives the full save-all and
    # raises the modal; it blocks until the watchdog clicks Save All.
    adapter._attempt(lambda: asm.Save())

    try:
        out, _ = watchdog.communicate(timeout=15)
        log(f"save-all watchdog: {out.strip()}")
    except subprocess.TimeoutExpired:
        watchdog.kill()
        log("save-all watchdog did not exit -- killed")

    after = sldasm.stat().st_mtime
    if after <= before:
        raise RuntimeError(
            f"{sldasm.name} mtime unchanged after Save() (asm_dirty=True) -- the "
            "Save All dialog was not answered / save did not write")
    log(f"saved {sldasm.name} (Save() + Save-All watchdog)")


async def _verify_rest(adapter: Any) -> None:
    """rest is the deterministic export pose: every component fully defined."""
    check(f"activate {REST}", await adapter.set_active_configuration(REST))
    log(f"--- verifying configuration {REST} (strict: 0 DOF) ---")
    assert_components_fully_defined(adapter)
    check_no_interference(adapter)


async def _verify_cone_disengaged(adapter: Any) -> None:
    """cone_disengaged: assert the freed set is EXACTLY the decoupled gear train.

    The meshes are cut, so the gear train loses its rotational pin and goes
    under-defined -- that is the point. The invariant is that ONLY the gear-train
    members go free (nothing structural leaks) and the pose is still
    interference-free.
    """
    check(f"activate {CONE_DISENGAGED}", await adapter.set_active_configuration(
        CONE_DISENGAGED))
    log(f"--- verifying configuration {CONE_DISENGAGED} (decoupled train) ---")
    freed = sorted(_under(_component_status(adapter)))
    log(f"{CONE_DISENGAGED}: {len(freed)} under-defined (decoupled) components")

    leaked = [n for n in freed if not n.startswith(DECOUPLED_PREFIXES)]
    if leaked:
        raise RuntimeError(
            f"{CONE_DISENGAGED}: structural components leaked into the freed set "
            f"(only the gear train may decouple): {leaked}")
    if len(freed) != EXPECTED_DECOUPLED:
        raise RuntimeError(
            f"{CONE_DISENGAGED}: expected exactly {EXPECTED_DECOUPLED} decoupled "
            f"gear-train members, got {len(freed)}: {freed}")
    log(f"{CONE_DISENGAGED}: freed set is exactly the {EXPECTED_DECOUPLED}-member "
        "gear train (no structural leak)")
    check_no_interference(adapter)


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        SuppressMateParameters,
    )

    path = str(OUT_SLDASM / f"{ASM_NAME}.SLDASM")
    check(f"open {ASM_NAME}", await adapter.open_model(path))

    mates = check("list mates", await adapter.list_mates())
    gear_mates = _gear_mate_names(mates)
    log(f"gear mates ({len(gear_mates)}): {gear_mates}")
    if len(gear_mates) != EXPECTED_GEAR_MATES:
        raise RuntimeError(
            f"expected {EXPECTED_GEAR_MATES} gear mates, found {len(gear_mates)} "
            f"-- mate types present: {sorted({m['type'] for m in mates})}")

    # rest stays the Default config; assert it is the clean engaged 0-DOF baseline.
    await _verify_rest(adapter)

    # Idempotent: a re-run (or a build_all that opens an already-configured doc)
    # must not fail on a duplicate AddConfiguration2 -- if cone_disengaged is
    # already present, skip create + suppress and just re-verify both states.
    configs = check("list configurations", await adapter.list_configurations())
    if CONE_DISENGAGED in configs:
        log(f"{CONE_DISENGAGED} already present ({configs}) -- re-verifying only")
    else:
        # cone_disengaged: derived from rest, then config-scoped-suppress every
        # gear mesh so the cone train is decoupled. AddConfiguration2 activates
        # the new config, so the suppress readback sees it active with no switch.
        check(f"create {CONE_DISENGAGED}", await adapter.create_configuration(
            CreateConfigurationParameters(
                name=CONE_DISENGAGED, parent=REST,
                comment="cone set swung out of mesh (ch.12): gear meshes suppressed",
                description="Cone train decoupled from the cylinders + crank.")))
        for gm in gear_mates:
            check(f"suppress {gm}@{CONE_DISENGAGED}", await adapter.suppress_mate(
                SuppressMateParameters(
                    name=gm, suppress=True, configuration=CONE_DISENGAGED)))
    await _verify_cone_disengaged(adapter)

    # Back to rest and re-verify: the gear meshes must be LIVE again here (the
    # suppression was scoped to cone_disengaged only) and the pose unchanged.
    await _verify_rest(adapter)
    live = check("list mates (rest)", await adapter.list_mates())
    still_suppressed = [m["name"] for m in live
                        if m["name"] in gear_mates and m.get("suppressed")]
    if still_suppressed:
        raise RuntimeError(
            f"rest leaked suppression from {CONE_DISENGAGED}: {still_suppressed}")
    log(f"rest: all {len(gear_mates)} gear meshes live (suppression stayed scoped)")

    # Save in place via Save3 (see _save_in_place for why not save_file/SaveAs).
    # The rest/Default PNG views were written by the drive-train build and are
    # unchanged (cone_disengaged does not alter the Default-config render), so no
    # image re-export is needed here.
    assert_model_healthy(adapter, label=ASM_NAME, deep=True)
    _save_assembly_in_place(adapter)
    return {"assembly": str(OUT_SLDASM / f"{ASM_NAME}.SLDASM"),
            "configs": f"{REST},{CONE_DISENGAGED}"}


if __name__ == "__main__":
    sys.exit(run_build(build))
