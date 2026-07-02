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

import sys
from typing import Any

from _common import OUT_SLDASM, check, log, run_build
from _assembly import assert_park_closure, load_park_specs
from verify import REST, _expected_free_dof

import _telemetry

# The default-free assemblies that carry deferred park drivers (dashed stems, the
# same set verify.py's `_expected_free_dof` gives a non-zero count). A `locked`
# build of either yields 0 expected free DOF and is skipped (nothing to close).
FREE_ASSEMBLIES = ["drive-train", "channel"]


async def _preflight_one(adapter: Any, name: str) -> str:
    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        raise RuntimeError(f"{name}: not built ({sldasm}) -- run the build first")

    expected = _expected_free_dof(name)
    specs = load_park_specs(name)
    if expected == 0:
        # `locked` build (or an assembly with no parked DOF): the saved model is
        # already fully defined, so there is no deferred closure to re-run.
        log(f"{name}: locked/0-free-DOF build -- no park closure to preflight")
        return "locked"
    if not specs:
        raise RuntimeError(
            f"{name}: config expects {expected} free DOF but no deferred park specs "
            f"were found ({name}.park.json missing beside the .SLDASM) -- the "
            "assembly was not built in `free` mode, or the sidecar was lost; rebuild"
        )

    # Fresh session per assembly (mirrors verify.py): stale open docs degrade COM.
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    async with _telemetry.aspan("preflight.open", name=name):
        check(f"open {name}", await adapter.open_model(str(sldasm)))
        configs = check("list configurations", await adapter.list_configurations())
        if REST in (configs or []):
            check(f"activate {REST}", await adapter.set_active_configuration(REST))
    log(f"--- preflight {name} ({REST} pose): {expected} deferred park driver(s) ---")

    # Authors the recorded drivers engaged and asserts 0 under-constrained. The doc
    # is mutated in memory only -- discarded below WITHOUT saving, so the shipped
    # .SLDASM stays the free model.
    await assert_park_closure(adapter, specs, expected)
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
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
