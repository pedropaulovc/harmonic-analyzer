"""Release-preflight DOF-sufficiency proof, split out of _assembly.py so its churn
does not re-key the 8-assembly BUILD cache.

These functions run ONLY on the verify/preflight/diagnostics path -- NEVER on the
assembly BUILD path (no build_<stem>_assembly.py imports them), so they are
deliberately OUTSIDE the assembly recipe/helper closure: load/replay the recorded
park specs and assert_park_closure (author every deferred driver -> assert 0 DOF).
Consumed by preflight_release.py / verify.py and the motion/mobility diagnostics.

Because this module is on NO assembly build closure, a change to it does not bump
any .SLDASM digest -- so verify:/preflight tasks depend on it DIRECTLY (see
POSTBUILD_PY in dodo.py) to stay fresh. (The incremental-REFRESH helpers, which ARE
build-path, live in _assembly.py where they ride the assembly recipe -- codex #193.)

Dependencies point ONE way: this module imports helpers from _assembly; _assembly
never imports this module.
"""
from __future__ import annotations

import json

import _telemetry
from typing import Any

from _assembly import (
    _mate,
    _under_constrained_components,
    assert_components_fully_defined,
    mark_park_driver,
    park_spec_path,
)


def load_park_specs(name: str) -> list[dict[str, Any]]:
    """Read the deferred park specs for ``<name>.SLDASM`` (``[]`` if none)."""
    path = park_spec_path(name)
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("specs", [])
async def replay_park_specs(adapter: Any, specs: list[dict[str, Any]]) -> list[str]:
    """Author every recorded deferred park driver ENGAGED on the ACTIVE assembly
    and rename it ``PARK_<key>``; return the new names.

    Used by the release preflight (and the mobility/motion diagnostics) to
    reconstitute the freed operational DOF on a reopened default-``free`` model.
    Reconstructs each :class:`MateEntityRef` from the recorded fields, replays the
    exact mate on the RECORDED side (``spec["flip"]`` -- the build's sign-derived
    seat, #185), with the original flip-recovery ``verify`` target as the safety
    net, then re-solves."""
    from solidworks_mcp.adapters.base import MateEntityRef

    names: list[str] = []
    for spec in specs:
        entities = [MateEntityRef(**e) for e in spec["entities"]]
        verify = None
        if spec.get("verify"):
            verify = (spec["verify"][0], list(spec["verify"][1]))
        res = await _mate(
            adapter,
            f"replay PARK_{spec['key']}",
            spec["kind"],
            entities,
            verify=verify,
            flip=bool(spec.get("flip", False)),
            **spec.get("params", {}),
        )
        names.append(await mark_park_driver(adapter, res, spec["key"]))
    if names:
        adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    return names
async def assert_park_closure(
    adapter: Any, specs: list[dict[str, Any]], expected_count: int
) -> None:
    """Release-preflight SUFFICIENCY gate: on a reopened default-``free`` model,
    prove the deferred park drivers are the SOLE freedom.

    * NECESSITY: the spec count equals ``expected_count`` and, before authoring,
      at least ``expected_count`` top-level components read under-constrained (the
      freedom really is present in the shipped free model).
    * SUFFICIENCY: :func:`replay_park_specs` authors every recorded driver engaged
      and re-solves; the model must then be fully defined (0 under-constrained), so
      the true free-DOF count equals the number of drivers.

    The caller MUST discard the document WITHOUT saving -- this mutates the
    in-memory model (authoring real mates), and the shipped ``.SLDASM`` must stay
    the free kinematic model."""
    with _telemetry.span("gate.park_closure") as gsp:
        gsp.set_attribute("expected_free_dof", expected_count)
        gsp.set_attribute("specs", len(specs))
        if len(specs) != expected_count:
            raise RuntimeError(
                f"park spec count {len(specs)} != expected free DOF {expected_count} "
                "-- the recorded specs disagree with the configured free-DOF count "
                "(rebuild the assembly)"
            )
        under = _under_constrained_components(adapter)
        gsp.set_attribute("free_under_constrained", len(under))
        if len(under) < expected_count:
            raise RuntimeError(
                f"expected >= {expected_count} under-constrained component(s) in the "
                f"free pose but found {len(under)}: {sorted(under)} -- the shipped "
                "model is already frozen (the deferred park drivers freed nothing)"
            )
        names = await replay_park_specs(adapter, specs)
        gsp.set_attribute("authored", len(names))
        # SUFFICIENCY: with every driver engaged the model must be rigid.
        assert_components_fully_defined(adapter)
        _telemetry.success(
            f"park closure OK: {len(under)} free -> authored {len(names)} PARK_* "
            "driver(s) -> 0 under-constrained (sufficiency); model NOT saved"
        )
