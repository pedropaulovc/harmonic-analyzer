r"""Release preflight: reconstitute the DEFERRED operational-DOF park drivers on
each default-``free`` assembly and re-run the exact-DOF closure gate, WITHOUT
saving. A COM-spine task gating ``release`` (opt-in, never part of ``build``).

Why this exists: the default ``free`` build no longer authors the freed-DOF park
drivers (each is an expensive mate solve only suppressed away again). It records
them as specs beside the ``.SLDASM`` (``_assembly.write_park_specs``) and leaves
the operational DOF genuinely free. This preflight replays those specs on a
reopened free model and PROVES the drivers are the sole freedom (author every
driver engaged -> the model goes fully defined). It NEVER saves, so the shipped
``.SLDASM`` stays the free kinematic model -- "gates re-evaluated as preflight,
then release continues as before".

The strict park-driver closure thus runs at RELEASE time (infrequent, opt-in)
rather than on every ``doit build``; the per-build soundness gate proves only
NECESSITY (the DOF are free) -- see ``verify.py`` / AGENTS.md "Default-free DOF".

Run (SolidWorks already open)::

    uv run python cad\scripts\preflight_release.py
"""

from __future__ import annotations

import os
import sys
from typing import Any

from _common import OUT_SLDASM, check, log, run_build
from _assembly_postbuild import (
    assert_park_closure,
    discard_open_documents as _discard_open_documents,
    load_park_specs,
)
from verify import REST, _expected_free_dof, assert_gear_ratios

import _telemetry

# The default-free assemblies that carry deferred park drivers (dashed stems, the
# same set verify.py's `_expected_free_dof` gives a non-zero count). A `locked`
# build of either yields 0 expected free DOF and is skipped (nothing to close).
FREE_ASSEMBLIES = ["drive-train", "channel", "magnifier", "paper-drive", "summing", "pen"]

# Off-by-default operator escape hatch: skip a named assembly's park-closure
# SUFFICIENCY proof (gear-ratios still runs) when a KNOWN, tracked gate
# limitation blocks it -- never a silent bypass. Set
# ``HARMONIC_PREFLIGHT_SKIP_PARK=<dashed-stem>[,<stem>...]``. Currently the only
# intended use is ``paper-drive`` per issue #205: its gear-mate/belt-chain-coupled
# transgear pair reads under-defined in SolidWorks' mate-DOF accounting even though
# the train is kinematically driven, so ``assert_park_closure``'s "every component
# fully defined" can't be satisfied. Remove the need for this when #205 lands.
_PARK_SKIP = {
    s for s in os.environ.get("HARMONIC_PREFLIGHT_SKIP_PARK", "").replace(",", " ").split()
}


async def _preflight_one(adapter: Any, name: str) -> str:
    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        raise RuntimeError(f"{name}: not built ({sldasm}) -- run the build first")

    expected = _expected_free_dof(name)
    specs = load_park_specs(name)
    if expected != 0 and not specs:
        raise RuntimeError(
            f"{name}: config expects {expected} free DOF but no deferred park specs "
            f"were found ({name}.park.json missing beside the .SLDASM) -- the "
            "assembly was not built in `free` mode, or the sidecar was lost; rebuild"
        )

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
        # gear-ratios is verified HERE at release, DEMOTED from the every-build
        # soundness battery (it was 50% of a soundness run and re-proved a property
        # fixed by the tooth-count config that check:math already validates). Run it
        # on the clean reopened model BEFORE park_closure authors any mates, for BOTH
        # `free` AND `locked` builds -- a locked release skips the park closure below,
        # so this is the ONLY live gear-mate ratio validation it gets now that
        # soundness no longer runs the gate. drive-train carries ALL 21 real meshes
        # (the crank 1:4 drive + the 20 cone<->cylinder channel meshes of its gear
        # stack); channel reads 0 gear mates at its own level (they live in the
        # flexible drive-train sub, verified there), so its check is a cheap no-op --
        # running it on both is harmless and keeps the shipped-artefact guarantee.
        assert_gear_ratios(adapter, name)
        if expected == 0:
            # `locked` build (or an assembly with no parked DOF): the saved model is
            # already fully defined, so there is no deferred closure to re-run --
            # gear-ratios above is the whole preflight for it.
            log(f"{name}: locked/0-free-DOF build -- gear-ratios checked, no park closure")
            return "locked (gear-ratios ok)"
        if name in _PARK_SKIP:
            _telemetry.warn(
                f"{name}: park-closure SUFFICIENCY SKIPPED via "
                "HARMONIC_PREFLIGHT_SKIP_PARK (known gate limitation, issue #205 -- "
                "gear/belt-chain-coupled DOF read under-defined); gear-ratios "
                "checked, sufficiency NOT proven this release"
            )
            return f"{expected} DOF -- park closure SKIPPED (issue #205)"
        log(f"--- preflight {name} ({REST} pose): {expected} deferred park driver(s) ---")
        # Authors the recorded drivers engaged and asserts 0 under-constrained. The
        # doc is mutated in memory only -- discarded in `finally` WITHOUT saving
        # (whether the closure passes or raises), so the shipped .SLDASM stays free.
        await assert_park_closure(adapter, specs, expected)
    finally:
        _discard_open_documents(adapter)
    return f"{expected} DOF closed"


async def build(adapter: Any) -> dict[str, str]:
    results: dict[str, str] = {}
    for name in FREE_ASSEMBLIES:
        results[name] = await _preflight_one(adapter, name)
    _telemetry.info("RELEASE PREFLIGHT -- deferred park-driver closure (model NOT saved):")
    for name, outcome in results.items():
        _telemetry.info(f"  {name:14s} {outcome}")
    _telemetry.success(
        "release preflight passed: every deferred operational DOF is the sole "
        "freedom of its assembly; shipped models untouched"
    )
    return results


if __name__ == "__main__":
    sys.exit(run_build(build))
