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
    """Save drive-train.SLDASM in place with a silent ``ModelDoc2.Save3``.

    The doc was OPENED from this path, so the active doc IS the file. The correct
    save is therefore an in-place ``Save3(swSaveAsOptions_Silent | SaveReferenced,
    &err, &warn)`` -- NOT the adapter's ``save_file``, both of whose branches are
    wrong for an opened-in-place doc:

      * ``save_file(PATH)`` -> SaveAs branch does ``CloseDoc(PATH)`` +
        ``os.remove(PATH)`` before ``SaveAs3``; when the active doc IS that path
        this disconnects the doc and deletes the file -- it destroyed
        drive-train.SLDASM twice.
      * ``save_file()`` (no path) -> ``Save3(1, None, None)``; ``None`` for the two
        [out] byref params fails the COM call, so it falls through to the blocking
        parameterless ``Save()`` that raises the "Component documents must be
        saved" modal -- which is what spawned the (now-deleted) UIAutomation
        Save-All watchdog.

    Passing the two [out] params as real pywin32 BYREF VARIANTs makes ``Save3``
    write silently and return the error/warning codes. The referenced part docs
    are untouched here (only assembly-level config + mate-suppression changes), so
    there is nothing to prompt about; ``SaveReferenced`` is included so any dirty
    reference would still be written without a dialog. Proven end-to-end by
    ``repro_inplace_save.py`` (ret=True, err=0, warn=0, config persists on reopen).
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
