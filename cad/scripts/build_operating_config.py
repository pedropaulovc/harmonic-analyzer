r"""The ``operating`` configuration of the drive train (plan step 5, cont.).

``build_engagement_configs.py`` added ``cone_disengaged`` (gear meshes cut, cone
train decoupled). This adds the third engagement state, ``operating``: the SAME
mated model with the single CRANK PARK DRIVER suppressed, so the one machine DOF
-- the crank angle -- is FREE while every gear mesh stays LIVE.

    Default (= rest)   crank driver active, every mesh live -> 0 DOF, fully
                       defined, bit-exact: the saved/rendered/photo-gated pose.
                       UNTOUCHED here.
    operating          crank driver suppressed, every mesh live -> exactly ONE
                       free DOF (the crank). Hand-drag the crank and the whole
                       gear train turns through the live meshes; OR let the Basic
                       Motion crank motor (build_motion_study.py) drive it. This
                       is the kinematically-live state for demos + motion studies.

Why this is the clean place for it: drive-train.SLDASM grounds ONE base (arbor,
pedestals, posts) internally, so suppressing the crank driver frees ONLY the
crank's rotational DOF -- nothing drifts. (In the full harmonic-analyzer.SLDASM
the drive-train is inserted rigid + fixed, so its internals cannot move at the
top level regardless of config; the durable free-DOF state must live in the sub.
build_top_engagement_configs.py can then point the parent at this child config.)

The crank driver is the single-real-part DISTANCE mate on ``crank-handle`` that
``spin_driver`` created ("crank angle driver (#1)" -- but SW auto-named the mate,
so it is found by its entities, not its label, exactly as build_motion_study's
crank-driver suppressor does). It is suppressed CONFIG-SCOPED (swSpecifyConfig),
so Default keeps it live and renders exactly as before.

Idempotent: a re-run (or a build_all that opens an already-configured doc) skips
the create + suppress and just re-verifies both states.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_operating_config.py
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
from build_engagement_configs import _save_assembly_in_place
from build_mobility_probe import _component_status, _under
from build_motion_study import ANGLE, DISTANCE, _family, _iter_mates, _lone_real

ASM_NAME = "drive-train"
REST = "Default"  # the model's default config IS the rest/engaged 0-DOF pose
OPERATING = "operating"  # crank driver freed -> the one machine DOF is live

# The crank park driver: the single-real-part DISTANCE mate whose lone real part
# is the crank handle (spin_driver pins handle Axis1's in-plane coord to a root
# plane). Found by entities -- the mate carries SW's auto name, not the label.
CRANK_DRIVER_FAMILY = "crank-handle"

# Suppressing the crank driver while every mesh stays live frees the ONE
# rotational DOF shared by the whole coupled train. EXACTLY these rotating
# families may go under-defined; anything structural leaking in is a bug. (Built
# from _part_family, so each entry matches a part name with its instance suffix
# stripped: "cone-gear-shaft-1" -> "cone-gear-shaft", distinct from "cone-gear".)
ROTATING_FAMILIES = frozenset({
    "crankshaft", "crank-arm", "crank-handle", "crank-pinion",
    "transgear-removable", "crank-drive-gear", "cone-gear-shaft",
    "cone-gear", "cylinder-gear",
})


def _find_crank_driver(adapter: Any) -> str:
    """Name of the lone single-``crank-handle`` DISTANCE/ANGLE mate (the driver).

    Walks the open drive-train.SLDASM mate group (NOT flexible here -> fast) and
    matches the same signature build_motion_study uses for the crank driver: a
    DISTANCE or ANGLE mate referencing exactly one real part whose family is the
    crank handle. There must be exactly one -- the keyed-chain lock mates are LOCK
    (two real parts) and the axial drivers are lone-``crankshaft``, so neither
    collides.
    """
    hits = []
    for _f, _m, name, mtype, parts, _v in _iter_mates(
            adapter, adapter.currentModel, read_values=False):
        if mtype not in (DISTANCE, ANGLE):
            continue
        lone = _lone_real(parts, ASM_NAME)
        if lone is not None and _family(lone) == CRANK_DRIVER_FAMILY:
            hits.append(name)
    if len(hits) != 1:
        raise RuntimeError(
            f"expected exactly 1 crank driver (single-{CRANK_DRIVER_FAMILY} "
            f"DISTANCE/ANGLE mate), found {hits}")
    log(f"crank park driver mate = {hits[0]!r}")
    return hits[0]


async def _verify_rest(adapter: Any) -> None:
    """rest is the deterministic export pose: every component fully defined."""
    check(f"activate {REST}", await adapter.set_active_configuration(REST))
    log(f"--- verifying configuration {REST} (strict: 0 DOF) ---")
    assert_components_fully_defined(adapter)
    check_no_interference(adapter)


async def _verify_operating(adapter: Any) -> None:
    """operating: the freed set is EXACTLY the rotating train (one shared DOF).

    Suppressing the crank driver with the meshes LIVE frees the single coupled
    rotational DOF, so every rotating member goes under-defined together. The
    invariant: ONLY rotating families go free (no structural leak) and the pose is
    still interference-free. (This is a free DOF on purpose -- the config exists to
    be hand-dragged / motor-driven -- so it is NOT a 0-DOF pose, by design.)
    """
    check(f"activate {OPERATING}", await adapter.set_active_configuration(OPERATING))
    log(f"--- verifying configuration {OPERATING} (crank DOF live) ---")
    freed = sorted(_under(_component_status(adapter)))
    log(f"{OPERATING}: {len(freed)} under-defined (rotating) components")

    leaked = [n for n in freed if _family(n) not in ROTATING_FAMILIES]
    if leaked:
        raise RuntimeError(
            f"{OPERATING}: structural components leaked into the freed set "
            f"(only the rotating train may go free): {leaked}")
    if not any(_family(n) == "crankshaft" for n in freed):
        raise RuntimeError(
            f"{OPERATING}: the crankshaft is not free -- the crank driver was "
            f"not actually suppressed in this config: {freed}")
    log(f"{OPERATING}: freed set is the rotating train only (no structural leak) "
        f"-- the crank is hand-draggable / motor-drivable here")
    check_no_interference(adapter)


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        SuppressMateParameters,
    )

    path = str(OUT_SLDASM / f"{ASM_NAME}.SLDASM")
    check(f"open {ASM_NAME}", await adapter.open_model(path))

    # rest stays the Default config; assert it is the clean 0-DOF baseline first
    # (also leaves Default active so the driver lookup sees the live mate).
    await _verify_rest(adapter)
    driver = _find_crank_driver(adapter)

    # Idempotent: skip create + suppress if operating already exists.
    configs = check("list configurations", await adapter.list_configurations())
    if OPERATING in configs:
        log(f"{OPERATING} already present ({configs}) -- re-verifying only")
    else:
        # operating: derived from rest, then config-scoped-suppress the crank
        # driver so the one machine DOF is free. AddConfiguration2 activates the
        # new config, so the suppress readback sees it active with no switch.
        check(f"create {OPERATING}", await adapter.create_configuration(
            CreateConfigurationParameters(
                name=OPERATING, parent=REST,
                comment="crank park driver suppressed: the single crank DOF is "
                "free (hand-drag / Basic Motion motor), meshes stay live",
                description="Kinematically-live device: crank free, gear train "
                "turns through the live meshes.")))
        check(f"suppress {driver}@{OPERATING}", await adapter.suppress_mate(
            SuppressMateParameters(
                name=driver, suppress=True, configuration=OPERATING)))

    await _verify_operating(adapter)

    # Back to rest and re-verify: the crank driver must be LIVE again here (the
    # suppression was scoped to operating only) and the pose unchanged.
    await _verify_rest(adapter)
    live = check("list mates (rest)", await adapter.list_mates())
    if any(m["name"] == driver and m.get("suppressed") for m in live):
        raise RuntimeError(
            f"rest leaked suppression from {OPERATING}: {driver} is suppressed "
            f"in Default -- the rest pose is no longer deterministic")
    log(f"rest: crank driver {driver!r} live (suppression stayed scoped)")

    assert_model_healthy(adapter, label=ASM_NAME, deep=True)
    _save_assembly_in_place(adapter)
    return {"assembly": str(OUT_SLDASM / f"{ASM_NAME}.SLDASM"),
            "configs": f"{REST},{OPERATING}"}


if __name__ == "__main__":
    sys.exit(run_build(build))
