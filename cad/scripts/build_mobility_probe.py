r"""Mobility probe (plan step 5 verification): prove each operational DOF's park
driver removes exactly the freedom it is meant to, expressed through SolidWorks'
per-component constraint status (the closest thing the API gives to a Kutzbach
mobility count -- there is no scalar DOF readout).

The argument, per subassembly:

  1. ``rest`` baseline -- with every park driver ACTIVE, no top-level component is
     under-defined (all status 3 / fixed / pattern). That is mobility 0: the saved
     pose is deterministic, which is what protects the render pipeline.
  2. suppress ONE park driver, ForceRebuild3, and read the status again: the
     component(s) that driver pins flip to under-defined (status 2). Mobility rose
     by the freedom that driver was holding.
  3. unsuppress -> back to all-defined. ``rest`` is restored (the doc is never
     saved, so the on-disk fully-defined state is untouched regardless).

So with all park drivers active the device is 0-DOF (deterministic exports); drop
the crank driver and the whole gear train is free to be turned (the 1 operating
DOF); drop a setup driver (p0 amplitude / p1 cone swing / p2 pinion swing) and
just that quasi-static freedom opens. The probe NEVER saves.

Park drivers live as TOP-LEVEL mates of each standalone subassembly (drive-train
carries crank + p1 + p2; channel carries the 20 p0 amplitude slides), so they are
suppressible by name without the flexible-sub indirection the motion study needs.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mobility_probe.py
"""

from __future__ import annotations

import sys
from typing import Any

from _common import (
    OUT_SLDASM,
    UNDER_CONSTRAINED,
    _flag_only,
    _read_member,
    check,
    log,
    run_build,
)
from build_motion_study import (
    ANGLE,
    DISTANCE,
    _family,
    _iter_mates,
    _real_parts,
)

import _telemetry

# Mate features are auto-named by SolidWorks ("Distance34"), NOT by the build
# script's label -- a park driver is identified the way the motion study does:
# a DISTANCE/ANGLE mate that references exactly ONE real moving part (its pose
# value, measured against a root plane). So the probe targets each operational
# DOF by the PART FAMILY its drivers pin, suppresses every single-real driver on
# that family, and checks the family goes free. (subassembly, family, label.)
PROBES = [
    ("drive-train", "crank-handle", "crank input (the 1 operating DOF)"),
    # p1: the swing park pins the PLATFORM (the post/tip block/shaft ride it by
    # seat mates, so no rider family carries a swing driver of its own).
    ("drive-train", "cone-swing-platform", "p1 cone swing-to-disengage"),
    # p2: the swing park pins the FRONT STRAP (the pinion itself is tied to the
    # strap by two-real mates, so its family carries no swing driver of its own).
    ("drive-train", "pinion-bracket", "p2 pinion swing-to-engage"),
    ("channel", "amplitude-bar", "p0 amplitude slides (all 20)"),
]


def _component_status(adapter: Any) -> dict[str, int]:
    """Map each non-fixed, non-pattern top-level component name -> constrained
    status (2 under, 3 fully). Fixed and pattern-instance components are omitted:
    their pose is held by IsFixed / the owning pattern feature, not by mates, so
    they carry no mobility."""
    asm = adapter.currentModel
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
    comps = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
    out: dict[str, int] = {}
    for comp in comps:
        # Flag ONLY the two zero-arg methods called below; Name2/IsFixed are
        # property reads (issue #87 -- not the 165-method IComponent2 flag).
        _flag_only(comp, "IsPatternInstance", "GetConstrainedStatus")
        name = str(_read_member(comp, "Name2"))
        if bool(_read_member(comp, "IsFixed")):
            continue
        if bool(adapter._attempt(lambda c=comp: c.IsPatternInstance(), default=False)):
            continue
        out[name] = int(
            adapter._attempt(lambda c=comp: c.GetConstrainedStatus(), default=-1)
        )
    return out


def _under(status: dict[str, int]) -> set[str]:
    return {n for n, s in status.items() if s == UNDER_CONSTRAINED}


def _drivers_by_family(adapter: Any, model: Any, root: str) -> dict[str, list[str]]:
    """Walk MODEL's mate group once and group the single-real-part DISTANCE/ANGLE
    driver mates by the family of the part they pin.

    ``root`` is the sub's doc-root pseudo-part name (``"drive-train"``); a driver
    dim references that root plane plus exactly one real part, so ``_real_parts``
    leaving one name marks a driver and names the part it controls."""
    out: dict[str, list[str]] = {}
    for _f, _m, name, mtype, parts, _v in _iter_mates(
            adapter, model, read_values=False, progress_every=40):
        if mtype not in (DISTANCE, ANGLE):
            continue
        reals = _real_parts(parts, root)
        if len(reals) == 1:
            out.setdefault(_family(reals[0]), []).append(name)
    return out


async def _probe_sub(adapter: Any, sub: str, probes: list[tuple]) -> list[str]:
    """Run every probe whose subassembly is ``sub`` against one open doc.

    Returns a list of human-readable result rows; raises on any broken invariant.
    """
    from solidworks_mcp.adapters.base import SuppressMateParameters

    path = str(OUT_SLDASM / f"{sub}.SLDASM")
    check(f"open {sub}", await adapter.open_model(path))

    # Default-`free` builds DEFER the freed-DOF park drivers (they are recorded, not
    # authored -- see AGENTS.md "Default-free DOF"), so the saved model has none to
    # probe. Replay the recorded specs (author them engaged, renamed PARK_*) so the
    # baseline/suppress argument below has real drivers to work on. The doc is NEVER
    # saved (this probe only reads status), so the on-disk free model is untouched.
    from _assembly_postbuild import load_park_specs, replay_park_specs

    specs = load_park_specs(sub)
    if specs:
        log(f"{sub}: replaying {len(specs)} deferred park driver(s) for the probe")
        await replay_park_specs(adapter, specs)

    log(f"{sub}: classifying single-real DISTANCE/ANGLE park drivers ...")
    drivers = _drivers_by_family(adapter, adapter.currentModel, sub)
    log(f"{sub}: driver families {[(f, len(n)) for f, n in sorted(drivers.items())]}")

    # The default-free build leaves operational PARK_* drivers (e.g. the crank
    # angle) SUPPRESSED, so the saved rest pose is NOT 0-DOF. Re-engage every
    # PARK_* mate first to establish the fully-defined baseline; the per-driver
    # suppress/measure loop below then proves each one frees its own family.
    from _assembly import find_park_drivers

    re_engaged = 0
    for pname, suppressed in await find_park_drivers(adapter):
        if suppressed:
            check(f"re-engage park {pname}", await adapter.suppress_mate(
                SuppressMateParameters(name=pname, suppress=False)))
            re_engaged += 1
    if re_engaged:
        adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
        log(f"{sub}: re-engaged {re_engaged} suppressed PARK_* driver(s) for the baseline")

    base_under = _under(_component_status(adapter))
    log(f"{sub}: {len(base_under)} under-defined components at rest")
    if base_under:
        raise RuntimeError(
            f"{sub} rest pose is NOT 0-DOF -- under-defined: {sorted(base_under)}"
        )

    rows: list[str] = []
    for s, family, label in probes:
        if s != sub:
            continue
        names = drivers.get(family, [])
        if not names:
            raise RuntimeError(
                f"{sub}: no single-real park driver references family {family!r} "
                f"(have {sorted(drivers)})")

        for name in names:
            check(f"suppress {name}", await adapter.suppress_mate(
                SuppressMateParameters(name=name, suppress=True)))
        freed = sorted(_under(_component_status(adapter)) - base_under)
        for name in names:
            check(f"unsuppress {name}", await adapter.suppress_mate(
                SuppressMateParameters(name=name, suppress=False)))
        restored = _under(_component_status(adapter))

        if not freed:
            raise RuntimeError(
                f"{label}: suppressing {len(names)} {family} driver(s) freed NO "
                "component -- they pin nothing (redundant constraints, not a DOF)")
        if not any(_family(c) == family for c in freed):
            raise RuntimeError(
                f"{label}: freed {freed} but none are {family} components")
        if restored:
            raise RuntimeError(
                f"{label}: rest NOT restored after unsuppress -- still free: "
                f"{sorted(restored)}")

        head = ", ".join(freed[:6]) + (" ..." if len(freed) > 6 else "")
        rows.append(f"  {label:34s} {len(names)} driver(s) -> +{len(freed):2d} "
                    f"free: {head}")
        log(f"{label}: OK ({len(names)} drivers -> +{len(freed)} freed, rest restored)")
    return rows


async def build(adapter: Any) -> dict[str, str]:
    rows: list[str] = []
    for sub in ("drive-train", "channel"):
        rows += await _probe_sub(adapter, sub, PROBES)
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)

    _telemetry.info("MOBILITY PROBE -- park driver -> freed DOF (rest = 0 DOF baseline):")
    _telemetry.info("\n".join(rows))
    _telemetry.success("rest is 0-DOF; each park driver controls a real freedom; "
                       "every probe restored rest.")
    return {"probes": str(len(rows))}


if __name__ == "__main__":
    sys.exit(run_build(build))
