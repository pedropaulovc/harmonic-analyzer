r"""Release preflight: re-run the gear-ratios gate on a freshly reopened copy of
each gear-carrying assembly, WITHOUT saving. A COM-spine task gating ``release``
(opt-in, never part of ``build``).

gear-ratios is verified HERE at release, DEMOTED from the every-build soundness
battery (it was ~50% of a soundness run and re-proves a property the tooth-count
config already fixes, which ``check:math`` validates analytically). There is no
DOF-closure proof here: every freed operational DOF is recorded into its
assembly's DOF manifest (never authored) and stays genuinely free in the shipped
model -- see ``verify.py`` / AGENTS.md "Default-free DOF"; ``verify:kinematics``
replays the manifest transiently for the sweeps that need a driven pose.

Run (SolidWorks already open)::

    uv run python cad\scripts\preflight_release.py
"""

from __future__ import annotations

import sys
from typing import Any

from _common import OUT_SLDASM, check, run_build
from _assembly_postbuild import discard_open_documents as _discard_open_documents
from verify import REST, assert_gear_ratios

import _telemetry

# Assemblies checked at release: the only ones carrying real gear meshes
# (AGENTS.md "Verify suites"). drive-train carries the crank 1:4 drive + the
# 20 cone<->cylinder channel meshes; channel is opened for its own MateGroup
# read (0 gear mates at its level -- the meshes live in the flexible
# drive-train sub -- so its pass doubles as a cheap sanity read). The other
# assemblies carry no gear mates; they were only opened here for the retired
# DOF-closure proof.
GEAR_ASSEMBLIES = ["drive-train", "channel"]


async def _preflight_one(adapter: Any, name: str) -> str:
    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        raise RuntimeError(f"{name}: not built ({sldasm}) -- run the build first")

    # Fresh session per assembly (mirrors verify.py): stale open docs degrade COM.
    # Use the discard-by-title path, not CloseAllDocuments(True): a dirty doc left
    # by a prior iteration (or an aborted run) would otherwise pop the save modal.
    _discard_open_documents(adapter)
    try:
        async with _telemetry.aspan("preflight.open", name=name):
            check(f"open {name}", await adapter.open_model(str(sldasm)))
            configs = check("list configurations", await adapter.list_configurations())
            if REST in (configs or []):
                check(f"activate {REST}", await adapter.set_active_configuration(REST))
        assert_gear_ratios(adapter, name)
    finally:
        _discard_open_documents(adapter)
    return "gear-ratios ok"


async def build(adapter: Any) -> dict[str, str]:
    results: dict[str, str] = {}
    for name in GEAR_ASSEMBLIES:
        results[name] = await _preflight_one(adapter, name)
    _telemetry.info("RELEASE PREFLIGHT -- gear-ratios (model NOT saved):")
    for name, outcome in results.items():
        _telemetry.info(f"  {name:14s} {outcome}")
    _telemetry.success("release preflight passed: gear ratios match config")
    return results


if __name__ == "__main__":
    sys.exit(run_build(build))
