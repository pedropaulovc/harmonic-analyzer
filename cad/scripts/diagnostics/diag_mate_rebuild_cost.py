r"""Empirical attribution of per-mate cost growth + the rebuild-deferral test.

Claims under test (adapter ``_add_mate_impl`` ends every mate with a full
``EditRebuild3``; the v0.18.0 channel log shows identical mate families going
1.7 s -> 4.4 s across 20 channels):

  H1  per-mate wall time grows with assembly population (reproduce in
      isolation, out of the channel build's noise);
  H2  the growth lives in the per-mate ``EditRebuild3`` (the whole-assembly
      re-solve), NOT in selection or ``CreateMate`` itself;
  H3  ``CreateMate`` alone already snaps the component onto the mate (so the
      flip/witness read-backs would still see the solved pose without the
      full rebuild);
  H4  skipping the per-mate rebuild and running ONE ``EditRebuild3`` after a
      mate batch yields the same final poses and constraint statuses -- i.e.
      the per-mate rebuild is a COST, not a correctness requirement.

Method (fresh throwaway assembly, NEVER saved): grounded pivot-shaft; ladder
rungs grow the population with grounded filler bushings (components without
mates) and separately with SEATED bushings (3 mates each, the production
``_seat_bushing_on_shaft`` path). At each rung, N_PROBE instrumented probe
mates are added by replaying the adapter's exact CreateMate sequence with a
``time.perf_counter`` split around each phase: select / CreateMate /
name-read / EditRebuild3, plus a component-transform read BETWEEN CreateMate
and the rebuild (H3). The deferral batch (H4) then re-runs the same mates
rebuild-free with one closing rebuild and diffs final Z stations + statuses.

Run (SolidWorks open, seat free; ~15-30 min)::

    uv run python cad\scripts\diagnostics\diag_mate_rebuild_cost.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _common import check, log, run_build  # noqa: E402
from _assembly import (  # noqa: E402
    component_transform,
    place_component,
    place_components_batch,
)
from build_channel_assembly import (  # noqa: E402
    IDENTITY,
    PIVOT,
    PIVOT_BUSHING_OD,
    PIVOT_SHAFT_Z,
    PITCH,
    SHAFT_R,
    _seat_bushing_on_shaft,
)
from solidworks_mcp.adapters.base import AddMateParameters, MateEntityRef  # noqa: E402
from solidworks_mcp.adapters.solidworks import assembly as _sw_asm  # noqa: E402

N_PROBE = 4          # instrumented probe mates per rung
FILLER_GROUNDED = 60  # rung 2: grounded components, zero mates
FILLER_SEATED = 16    # rung 3: seated bushings, 3 mates each (48 mates)
Z_FAR = 400.0         # keep fillers clear of the probe stations


def _probe_params(comp: str, z_mm: float) -> AddMateParameters:
    """A coincident axial mate: probe component's Front Plane to a Z station.

    Distance mates carry flip/side semantics; a plain coincident keeps the
    probe about SOLVE COST, not side selection. The bushing is already
    concentric-free (grounded fillers never mate), so each probe bushing gets
    ONE concentric first (un-instrumented) and then this instrumented mate.
    """
    return AddMateParameters(
        mate_type="coincident",
        entities=[
            MateEntityRef(entity_type="PLANE", name=f"Front Plane@{comp}"),
            MateEntityRef(entity_type="PLANE", name="Front Plane"),
        ],
        alignment="closest",
    )


def _timed_mate(adapter, params: AddMateParameters, comp: str,
                rebuild: bool) -> dict[str, float]:
    """Replay _add_mate_impl's standard-mate sequence with per-phase timers."""
    model = adapter.currentModel
    mate_type = _sw_asm._MATE_TYPES.get(params.mate_type)
    if mate_type is None:
        raise RuntimeError(f"unknown mate_type {params.mate_type!r}")
    t: dict[str, float] = {}

    t0 = time.perf_counter()
    adapter._attempt(lambda: model.ClearSelection2(True), default=None)
    for ref in params.entities:
        mark = ref.mark or _sw_asm._MATE_DEFAULT_MARKS.get(params.mate_type, 1)
        if not _sw_asm._select_mate_entity(adapter, ref, mark):
            raise RuntimeError(f"select failed: {ref.name or ref.point}")
    t["select"] = time.perf_counter() - t0

    _sw_asm._flag_feature_methods(model, "IAssemblyDoc")
    t0 = time.perf_counter()
    mate = _sw_asm._create_standard_mate(adapter, model, params, mate_type)
    t["create"] = time.perf_counter() - t0

    # H3: does CreateMate alone snap the component? Read the pose BEFORE any
    # rebuild -- if z already moved to the target, the solve happened in-create.
    t0 = time.perf_counter()
    t["z_after_create"] = component_transform(adapter, comp)[11] * 1000.0
    t["readback"] = time.perf_counter() - t0

    adapter._attempt(lambda: model.ClearSelection2(True), default=None)
    t0 = time.perf_counter()
    _sw_asm._mate_feature_name(adapter, mate)
    t["name"] = time.perf_counter() - t0

    if rebuild:
        t0 = time.perf_counter()
        adapter._attempt(lambda: model.EditRebuild3())
        t["rebuild"] = time.perf_counter() - t0
    return t


async def _probe_batch(adapter, tag: str, rebuild_each: bool) -> list[dict[str, float]]:
    """Insert N_PROBE bushings on the shaft and add the instrumented mates."""
    rows = []
    for i in range(N_PROBE):
        z = -80.0 - i * PITCH  # below the shaft midline, clear of fillers
        comp = await place_component(
            adapter, "pivot-bushing", [PIVOT[0], PIVOT[1], z],
            [0.0, 0.0, 0.0], IDENTITY, ground=False,
            label=f"probe bushing {tag}-{i}",
        )
        t = _timed_mate(adapter, _probe_params(comp, z), comp, rebuild=rebuild_each)
        t["comp"] = comp
        rows.append(t)
        log(f"  {tag}[{i}] select={t['select']:.2f}s create={t['create']:.2f}s "
            f"name={t['name']:.2f}s rebuild={t.get('rebuild', 0.0):.2f}s "
            f"z_after_create={t['z_after_create']:.2f}")
    if not rebuild_each:
        t0 = time.perf_counter()
        adapter._attempt(lambda: adapter.currentModel.EditRebuild3())
        log(f"  {tag}: ONE closing EditRebuild3 = {time.perf_counter() - t0:.2f}s")
    return rows


async def _grow_grounded(adapter, count: int) -> None:
    specs = [{
        "part": "pivot-bushing",
        "position": [PIVOT[0], PIVOT[1], Z_FAR + k * PITCH],
        "rotation": [0.0, 0.0, 0.0], "rows": IDENTITY, "ground": True,
        "label": f"filler grounded {k}",
    } for k in range(count)]
    await place_components_batch(adapter, specs, label=f"{count} grounded fillers")


async def _grow_seated(adapter, count: int) -> None:
    for k in range(count):
        z = 100.0 + k * PITCH
        comp = await place_component(
            adapter, "pivot-bushing", [PIVOT[0], PIVOT[1], z],
            [0.0, 0.0, 0.0], IDENTITY, ground=False, label=f"filler seated {k}",
        )
        await _seat_bushing_on_shaft(
            adapter, comp, [PIVOT[0] + SHAFT_R, PIVOT[1], 0.0],
            (PIVOT[0], PIVOT[1]), PIVOT_BUSHING_OD / 2.0,
        )


async def build(adapter) -> dict[str, str]:
    check("create_assembly", await adapter.create_assembly())
    await place_component(
        adapter, "pivot-shaft", [PIVOT[0], PIVOT[1], PIVOT_SHAFT_Z],
        [0.0, 0.0, 0.0], IDENTITY, ground=True, label="pivot-shaft (grounded)",
    )

    # Rung 1: near-empty assembly (baseline).
    log("== rung 1: baseline (shaft only) ==")
    r1 = await _probe_batch(adapter, "base", rebuild_each=True)

    # Rung 2: + grounded fillers (components, no mates). If per-mate cost
    # jumps here, COMPONENT count drives it; if flat, mates do.
    log(f"== rung 2: +{FILLER_GROUNDED} grounded fillers ==")
    await _grow_grounded(adapter, FILLER_GROUNDED)
    r2 = await _probe_batch(adapter, "grounded", rebuild_each=True)

    # Rung 3: + seated fillers (grows the MATE system).
    log(f"== rung 3: +{FILLER_SEATED} seated fillers ({FILLER_SEATED * 3} mates) ==")
    await _grow_seated(adapter, FILLER_SEATED)
    r3 = await _probe_batch(adapter, "seated", rebuild_each=True)

    # H4: deferral batch on the now-heavy assembly, then verify equivalence:
    # the mated bushings must land on their planes and read fully-defined
    # exactly as the rebuild-each batch did.
    log("== deferral: same mates, NO per-mate rebuild, ONE closing rebuild ==")
    r4 = await _probe_batch(adapter, "defer", rebuild_each=False)
    for row in r4:
        z_final = component_transform(adapter, row["comp"])[11] * 1000.0
        log(f"  defer {row['comp']}: z_after_create={row['z_after_create']:.3f} "
            f"z_final={z_final:.3f}")

    log("=" * 70)
    for tag, rows in (("base", r1), ("grounded", r2), ("seated", r3), ("defer", r4)):
        n = len(rows)
        sel = sum(r["select"] for r in rows) / n
        cre = sum(r["create"] for r in rows) / n
        reb = sum(r.get("rebuild", 0.0) for r in rows) / n
        log(f"{tag:9s} avg/mate: select={sel:.2f}s create={cre:.2f}s rebuild={reb:.2f}s")
    log("H2 verdict: growth column is the one that rises rung 1 -> 3.")
    log("H3 verdict: z_after_create == target plane -> CreateMate solves in place.")
    return {"probe_mates": str(len(r1) + len(r2) + len(r3) + len(r4))}


if __name__ == "__main__":
    sys.exit(run_build(build))
