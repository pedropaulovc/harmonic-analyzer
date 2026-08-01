r"""Mobility probe (plan step 5 verification): prove each operational DOF's
drive spec removes exactly the freedom it is meant to, expressed through
SolidWorks' per-component constraint status (the closest thing the API gives
to a Kutzbach mobility count -- there is no scalar DOF readout).

The saved free model carries no driver mates at all: every operational DOF's
spec is recorded into the assembly's DOF manifest instead of authored (see
AGENTS.md "Default-free DOF"). This probe first replays that manifest
(``_assembly_postbuild.author_dof_drives``, authoring each spec TRANSIENTLY
and renaming it ``DRIVE_<key>``) to reconstitute a fully-defined baseline to
probe against. The argument, per subassembly:

  1. ``rest`` baseline -- with every replayed drive mate ACTIVE, no top-level
     component is under-defined (all status 3 / fixed / pattern). That is
     mobility 0: the saved pose is deterministic, which is what protects the
     render pipeline.
  2. suppress ONE drive mate, ForceRebuild3, and read the status again: the
     component(s) that mate pins flip to under-defined (status 2). Mobility rose
     by the freedom that mate was holding.
  3. unsuppress -> back to all-defined. ``rest`` is restored (the doc is never
     saved, so the on-disk free model is untouched regardless).

So with every replayed drive mate active the device is 0-DOF (deterministic);
drop the crank driver and the whole gear train is free to be turned (the 1
operating DOF); drop a setup driver (p0 amplitude / p1 cone swing / p2 pinion
swing) and just that quasi-static freedom opens. The probe NEVER saves.

Drive mates land as TOP-LEVEL mates of each standalone subassembly (drive-train
carries crank + p1 + p2; channel replays its rocker/rod drives, while the 20 p0
amplitude stations are the PRODUCTION J6 rocker<->bar angle mates -- driven, not
freed, PR #458), so they are suppressible by name without the flexible-sub
indirection the motion study needs.

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
# script's label -- a drive mate is identified the way the motion study does:
# a DISTANCE/ANGLE mate that references exactly ONE real moving part (its pose
# value, measured against a root plane). So the probe targets each operational
# DOF by the PART FAMILY its drivers pin, suppresses every single-real driver on
# that family, and checks the family goes free. (subassembly, family, label.)
PROBES = [
    ("drive-train", "crank-handle", "crank input (the 1 operating DOF)"),
    # p1: the swing driver pins the PLATFORM (the post/tip block/shaft ride it by
    # seat mates, so no rider family carries a swing driver of its own).
    ("drive-train", "cone-swing-platform", "p1 cone swing-to-disengage"),
    # p2: the swing driver pins the FRONT STRAP (the pinion itself is tied to the
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
            continue
        # The p0 amplitude station is DRIVEN part<->part (the J6 rocker<->bar
        # angle mate, PR #458), not a single-real root-plane dim -- classify
        # it under the bar family it pins.
        if (mtype == ANGLE
                and sorted(_family(r) for r in reals)
                == ["amplitude-bar", "rocker-arm"]):
            out.setdefault("amplitude-bar", []).append(name)
    return out


async def _probe_sub(adapter: Any, sub: str, probes: list[tuple]) -> list[str]:
    """Run every probe whose subassembly is ``sub`` against one open doc.

    Returns a list of human-readable result rows; raises on any broken invariant.
    """
    from solidworks_mcp.adapters.base import SuppressMateParameters

    path = str(OUT_SLDASM / f"{sub}.SLDASM")
    check(f"open {sub}", await adapter.open_model(path))

    # The saved free model carries no driver mates for its operational DOF --
    # each is recorded into the assembly's DOF manifest instead (see AGENTS.md
    # "Default-free DOF"). Replay the manifest (authors every spec TRANSIENTLY,
    # renamed DRIVE_<key>) so the baseline/suppress argument below has real
    # mates to work on. The doc is NEVER saved (this probe only reads status),
    # so the on-disk free model is untouched.
    from _assembly_postbuild import author_dof_drives, load_dof_manifest

    specs = load_dof_manifest(sub)
    if specs:
        log(f"{sub}: replaying {len(specs)} recorded free-DOF driver(s) for the probe")
        await author_dof_drives(adapter, specs)

    log(f"{sub}: classifying single-real DISTANCE/ANGLE drive mates ...")
    drivers = _drivers_by_family(adapter, adapter.currentModel, sub)
    log(f"{sub}: driver families {[(f, len(n)) for f, n in sorted(drivers.items())]}")

    # author_dof_drives authors every recorded spec ENGAGED (never suppressed),
    # so replaying the manifest already establishes the fully-defined baseline
    # directly -- no separate re-engage pass is needed.
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
                f"{sub}: no single-real drive mate references family {family!r} "
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

    _telemetry.info("MOBILITY PROBE -- drive mate -> freed DOF (rest = 0 DOF baseline):")
    _telemetry.info("\n".join(rows))
    _telemetry.success("rest is 0-DOF; each drive mate controls a real freedom; "
                       "every probe restored rest.")
    return {"probes": str(len(rows))}


if __name__ == "__main__":
    sys.exit(run_build(build))
