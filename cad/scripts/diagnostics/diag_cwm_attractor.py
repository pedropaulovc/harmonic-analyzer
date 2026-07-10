r"""Minimal isolated repro: the CopyWithMates2 free-DOF solver-state attractor.

The 2026-07-09 channel rework found that a CopyWithMates2 copy of a slice
with FREED operational DOF does not stay where you put it: every solve
returns it to one deterministic wrong pose, from any start, even though the
copied mates are value-identical to the seed's and satisfied at the design
pose. This script reproduces that on the SMALLEST slice that shows it and
compares three landing strategies side by side, one fresh copy each (so no
strategy pollutes the next):

  copy A  put-only            Transform2 put to the design pose, then
                              EditRebuild3 -- the BUG demo (put lands
                              exactly, the rebuild reverts it).
  copy B  put + drivers       put, author transient drive mates pinning the
                              free DOF at the design pose, delete them, then
                              rebuild -- the fix build_channel_assembly
                              ships (a driven solve rewrites stored state).
  copy C  IDragOperator drag  absolute-transform Drag() to the design pose
                              (the UI's own Move Components solver path,
                              docs: "reuses the solver ... more efficient
                              than multiple SetTransformAndSolve"), then
                              rebuild -- the candidate cheaper fix.

Three phases, escalating topology (each a fresh throwaway assembly):

  single  rocker on the pivot shaft (concentric + axial dim; spin FREE) --
          2 mates, 1 free DOF, open chain.
  chain   + connecting-rod on the rocker pin (coax + axial dim; swing
          FREE) -- 4 mates, 2 free DOF, still an OPEN serial chain.
  loop    chain + a root-plane distance holding the rod's ring bore at
          fixed X (the production J3/J5 loop-closer idiom) -- 5 mates,
          CLOSED kinematic loop ground-rocker-rod-ground, 1 net free DOF.
          The production attractor lives in the closed-loop channel slice;
          this is its smallest analogue.

Measured 2026-07-09 (all three phases, three runs): the parked-pose wander
reproduces EVERYWHERE -- every copy of a free-DOF slice parks spun ~9 deg
off the seed, deterministically -- but the put-reversion attractor does
NOT: a bare Transform2 put survived EditRebuild3 in all nine cells,
including the closed loop. The attractor is an emergent property of the
production channel slice (mirrored/rotated seed transforms, coincident
PLANE axial mates, the 4-part rocker->rod->bar->lever multi-loop, ~100-
component assembly context) that this minimal scale cannot summon; the
production build keeps its put+driver landing on measured evidence
(build_channel_assembly, runs 3-4 of the 2026-07-09 hunt). Positive
finding: IDragOperator lands copies in ~0.2 s/part vs ~0.8 s per authored
driver mate, and survives the rebuild here -- the candidate cheap landing
for future ladders, pending validation on the real slice. Each stage
prints the pose readback and a HOLD/WANDER verdict; nothing is ever saved.

Run (SolidWorks already open)::

    uv run python cad\scripts\diagnostics\diag_cwm_attractor.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _assembly import (  # noqa: E402
    bore_axis_ref,
    coincident_mate,
    component_names,
    component_transform,
    concentric_mate,
    distance_driver,
    named_ref,
    place_component,
    spin_driver,
)
from _assembly_postbuild import discard_open_documents  # noqa: E402
from _common import _flag_only, check, log, run_build  # noqa: E402
from _cwm import (  # noqa: E402
    component_constrained_status,
    component_mate_count,
    copy_with_mates,
    external_mate_rows,
    mates_with_owners,
    put_component_pose,
)
from solidworks_mcp.adapters.solidworks.assembly import (  # noqa: E402
    _create_math_transform,
)
from build_rocker_arm import ROD_HOLE_X, ROD_HOLE_Y, _mid_y  # noqa: E402
from build_connecting_rod import CENTER_DISTANCE as ROD_C2C  # noqa: E402

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
SHAFT_R = 6.35 / 2.0
PIVOT_Y = _mid_y(0.0)  # 8.0 -- rocker pivot bore at local (0, 8)
# Dim VALUES stay positive; the flip rule's natural side for these distance
# refs is -Z (measured: seeding at +Z0 raised flip-seed MISS off by 2*Z0), so
# the design frame marches -Z. Don't touch _FLIP_INVERT for a diagnostic.
Z0 = 10.0  # seed station depth (shaft spans +/-101.6, stations stay inside)
PITCH = 7.0565
ROD_DZ = 2.5  # rod Front plane offset off the rocker's (production J2 axial)
PREFIXES = {"rocker-arm", "connecting-rod", "pivot-shaft"}
TOL_MM = 0.1


def _pose(adapter, name: str) -> list[float]:
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0, a[0], a[1]]


def _report(adapter, tag: str, name: str, target: list[float]) -> bool:
    """Print pose vs target; True when within TOL_MM (and spin unrotated)."""
    p = _pose(adapter, name)
    t = [target[9] * 1000.0, target[10] * 1000.0, target[11] * 1000.0,
         target[0], target[1]]
    hold = (max(abs(a - b) for a, b in zip(p[:3], t[:3])) < TOL_MM
            and abs(p[3] - t[3]) < 1e-3 and abs(p[4] - t[4]) < 1e-3)
    log(f"  {tag:34s} {name}: org=({p[0]:8.3f},{p[1]:8.3f},{p[2]:8.3f})"
        f" xrow=({p[3]:+.3f},{p[4]:+.3f})"
        f"  -> {'HOLD' if hold else 'WANDER'}")
    return hold


def _rebuild(adapter) -> None:
    """EditRebuild3, raising on a False return: the verdicts below are only
    meaningful against a rebuild that actually solved -- a silent failure
    would leave the pre-rebuild pose in place and fake a HOLD."""
    model = adapter.currentModel
    if not adapter._attempt(lambda: model.EditRebuild3(), default=False):
        raise RuntimeError(
            "EditRebuild3 returned False -- no-solution/over-defined state")


def _drag_to(adapter, name: str, array16: list[float]) -> bool:
    """Absolute-transform IDragOperator drag -- the UI Move Components path."""
    model = adapter.currentModel
    _flag_only(model, "GetDragOperator")
    op = adapter._attempt(lambda: model.GetDragOperator(), default=None)
    if op is None:
        raise RuntimeError("GetDragOperator returned None")
    _flag_only(op, "AddComponent", "BeginDrag", "Drag", "EndDrag")
    comp = model.GetComponentByName(name)
    if not adapter._attempt(lambda: op.AddComponent(comp, False), default=False):
        raise RuntimeError(f"DragOperator.AddComponent failed for {name!r}")
    op.CollisionDetectionEnabled = False
    op.DynamicClearanceEnabled = False
    op.TransformType = 2       # general (translation + rotation)
    op.DragMode = 0            # maximum move (rigid where possible)
    op.UseAbsoluteTransform = True
    if not adapter._attempt(lambda: op.BeginDrag(), default=False):
        raise RuntimeError("BeginDrag failed")
    xform = _create_math_transform(adapter, list(array16))
    moved = adapter._attempt(lambda: op.Drag(xform), default=False)
    adapter._attempt(lambda: op.EndDrag(), default=None)
    return bool(moved)


async def _seed_slice(adapter, mode: str) -> dict[str, str]:
    """Author the seed: rocker on the shaft (spin free); ``chain``/``loop``
    add the rod on the rocker pin (swing free); ``loop`` also closes the
    kinematic loop with a root-plane distance pinning the ring bore's X
    (the production J3 loop-closer idiom). Every part lands on-solution."""
    check("create_assembly", await adapter.create_assembly())
    await place_component(
        adapter, "pivot-shaft", [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, label="pivot-shaft (seed, auto-fixed)")
    rocker = await place_component(
        adapter, "rocker-arm", [0.0, -PIVOT_Y, -Z0], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, label="rocker-arm seed")
    tgt = [0.0, -PIVOT_Y, -Z0]
    await concentric_mate(
        adapter, bore_axis_ref([SHAFT_R, 0.0, 0.0]),
        named_ref(f"Axis1@{rocker}", "AXIS"),
        label="J1 rocker radial", verify=(rocker, tgt))
    await distance_driver(
        adapter, named_ref(f"Front Plane@{rocker}", "PLANE"),
        named_ref("Front Plane", "PLANE"), Z0,
        label=f"J1 rocker axial d={Z0:.2f}", verify=(rocker, tgt))
    comps = {"rocker-arm": rocker}
    if mode in ("chain", "loop"):
        # Rod hanging plumb below the rocker's rod pin (local (127.37, 15.30)
        # -> world (127.37, 7.30)); ring centre = rod origin, pin at local +Y.
        pin = [ROD_HOLE_X, ROD_HOLE_Y - PIVOT_Y]
        rod = await place_component(
            adapter, "connecting-rod",
            [pin[0], pin[1] - ROD_C2C, -Z0 - ROD_DZ],
            [0.0, 0.0, 0.0], IDENTITY,
            ground=False, label="connecting-rod seed")
        rod_tgt = [pin[0], pin[1] - ROD_C2C, -Z0 - ROD_DZ]
        await coincident_mate(
            adapter, named_ref(f"Axis2@{rocker}", "AXIS"),
            named_ref(f"Axis2@{rod}", "AXIS"),
            label="J2 rod coaxial pin", verify=(rod, rod_tgt))
        await distance_driver(
            adapter, named_ref(f"Front Plane@{rod}", "PLANE"),
            named_ref(f"Front Plane@{rocker}", "PLANE"), ROD_DZ,
            label=f"J2 rod axial d={ROD_DZ:.2f}", verify=(rod, rod_tgt))
        comps["connecting-rod"] = rod
        if mode == "loop":
            # Loop closer: the ring bore held at its as-solved X off the root
            # Right Plane (production J3 idiom) -- closes ground-rocker-rod-
            # ground, leaving 1 net free DOF.
            await distance_driver(
                adapter, named_ref(f"Axis1@{rod}", "AXIS"),
                named_ref("Right Plane", "PLANE"), pin[0],
                label=f"J6 ring X={pin[0]:.2f} (loop closer)",
                verify=(rod, rod_tgt))
    return comps


def _slice_slots(adapter, seed: dict[str, str]) -> tuple[int, list[float], int]:
    """(mate count, per-slot seed values in metres, the Z-ladder slot index).

    Live dim slots must carry their seed value -- a 0.0 there re-values the
    copy's dim to zero (the pinned contract). The ladder slot (the J1 axial,
    the one dim the copies re-value) is found by its seed value Z0."""
    instances = set(seed.values())
    rows = [r for r in mates_with_owners(adapter, PREFIXES)
            if r["instances"] & instances]
    ext = external_mate_rows(rows, instances)
    values = [(r["mm"] or 0.0) / 1000.0 if r["type"] == "MateDistanceDim"
              else 0.0 for r in ext]
    ladder = [i for i, r in enumerate(ext)
              if r["type"] == "MateDistanceDim" and abs(r["mm"] - Z0) < 1e-6]
    assert len(ladder) == 1, (ladder, [(r["name"], r["mm"]) for r in ext])
    return len(rows), values, ladder[0]


def _copy(adapter, seed: dict[str, str], n: int, values_m: list[float],
          dim_slot: int, station: int) -> dict[str, str]:
    # Values slots map onto the EXTERNAL mates in tree order (the phase-H
    # calibration); the array is padded to n like the sibling bool arrays.
    values = list(values_m) + [0.0] * (n - len(values_m))
    values[dim_slot] = (Z0 + station * PITCH) / 1000.0
    before = set(component_names(adapter))
    copy_with_mates(adapter, list(seed.values()), n, values)
    comps: dict[str, str] = {}
    for name in sorted(set(component_names(adapter)) - before):
        comps[name.rsplit("-", 1)[0]] = name
    assert set(comps) == set(seed), comps
    return comps


def _targets(seed_arrays: dict[str, list[float]],
             station: int) -> dict[str, list[float]]:
    """Station targets off the SNAPSHOT of the seed's as-authored transforms
    -- never a live read: the seed is under-constrained, so a prior copy or
    rebuild could drift it, and live-derived targets would normalize that
    drift away and fake a HOLD."""
    out = {}
    for part, a in seed_arrays.items():
        a = list(a)
        a[11] -= station * PITCH / 1000.0
        out[part] = a
    return out


async def _land_put(adapter, comps, targets) -> None:
    for part, name in comps.items():
        put_component_pose(adapter, name, targets[part])


async def _land_drivers(adapter, comps, targets) -> None:
    """The shipped fix: puts + transient drive mates + delete (see
    build_channel_assembly's copy dispatch)."""
    from build_channel_assembly import _delete_feature
    await _land_put(adapter, comps, targets)
    rocker = comps["rocker-arm"]
    drives = []
    mate = await spin_driver(
        adapter, named_ref(f"Axis2@{rocker}", "AXIS"), (0.0, 0.0),
        (ROD_HOLE_X, ROD_HOLE_Y - PIVOT_Y),
        label=f"repro rocker spin -> {ROD_HOLE_X:.1f},{ROD_HOLE_Y - PIVOT_Y:.1f}",
        verify=(rocker, [v * 1000.0 for v in targets["rocker-arm"][9:12]]))
    drives.append(mate["name"])
    if "connecting-rod" in comps:
        await _land_put(adapter, comps, targets)
        rod = comps["connecting-rod"]
        t = targets["connecting-rod"]
        pin = (ROD_HOLE_X, ROD_HOLE_Y - PIVOT_Y)
        ring = (t[9] * 1000.0, t[10] * 1000.0)
        mate = await spin_driver(
            adapter, named_ref(f"Axis1@{rod}", "AXIS"), pin, ring,
            label=f"repro rod swing -> ring {ring[0]:.1f},{ring[1]:.1f}",
            verify=(rod, [v * 1000.0 for v in t[9:12]]))
        drives.append(mate["name"])
    for name in reversed(drives):
        _delete_feature(adapter, name)


async def _land_drag(adapter, comps, targets) -> None:
    for part, name in comps.items():
        moved = _drag_to(adapter, name, targets[part])
        log(f"  drag {name}: moved={moved}")


_PHASE_LABELS = {
    "single": "single (rocker, 1 free DOF, open)",
    "chain": "chain (rocker+rod, 2 free DOF, open)",
    "loop": "loop (rocker+rod+ring-X closer, 1 net free DOF, CLOSED)",
}


async def _phase(adapter, mode: str) -> dict[str, bool]:
    log(f"=== phase: {_PHASE_LABELS[mode]} ===")
    # Repo idiom for dropping a dirty transient model -- CloseAllDocuments
    # on an unsaved assembly can raise the Save Modified Documents modal
    # and hang a headless run.
    discard_open_documents(adapter)
    seed = await _seed_slice(adapter, mode)
    n, slot_values, dim_slot = _slice_slots(adapter, seed)
    log(f"seed slice: {n} mates, ext dims {slot_values}, ladder slot {dim_slot}")
    # Snapshot the seed BEFORE any copy: as-authored transforms (the target
    # basis) and per-part mate count / constrained status (the copy-
    # completeness reference, mirroring the production validation).
    seed_arrays = {p: list(component_transform(adapter, c))
                   for p, c in seed.items()}
    seed_counts = {p: component_mate_count(adapter, c)
                   for p, c in seed.items()}
    seed_status = {p: component_constrained_status(adapter, c)
                   for p, c in seed.items()}
    verdicts: dict[str, bool] = {}
    strategies = (
        ("A put-only", _land_put),
        ("B put+drivers (shipped fix)", _land_drivers),
        ("C IDragOperator drag (UI path)", _land_drag),
    )
    for station, (tag, land) in enumerate(strategies, start=1):
        comps = _copy(adapter, seed, n, slot_values, dim_slot, station)
        targets = _targets(seed_arrays, station)
        log(f"--- copy {tag} at station {station} ---")
        for part, name in comps.items():
            _report(adapter, "post-copy (parked)", name, targets[part])
        await land(adapter, comps, targets)
        for part, name in comps.items():
            _report(adapter, "post-landing", name, targets[part])
        _rebuild(adapter)
        hold = all(
            _report(adapter, "post-EditRebuild3", name, targets[part])
            for part, name in comps.items())
        # The copy must also CARRY the seed's constraints -- a copy that
        # silently dropped mates could sit at target and fake a HOLD.
        for part, name in comps.items():
            mates = component_mate_count(adapter, name)
            status = component_constrained_status(adapter, name)
            if mates != seed_counts[part] or status != seed_status[part]:
                log(f"  !! {name}: mates={mates} (seed {seed_counts[part]}),"
                    f" status={status} (seed {seed_status[part]})"
                    " -- copy incomplete, verdict forced WANDER")
                hold = False
        # The seed itself must not have drifted, or the snapshot targets no
        # longer describe the design ladder.
        for part, name in seed.items():
            if not _report(adapter, "seed drift check", name,
                           _targets(seed_arrays, 0)[part]):
                raise RuntimeError(f"seed {name} drifted off its snapshot")
        verdicts[tag] = hold
        log(f"  VERDICT {tag}: {'HOLD' if hold else 'WANDER'}")
    return verdicts


async def build(adapter) -> dict[str, str]:
    try:
        out: dict[str, str] = {}
        for mode in ("single", "chain", "loop"):
            verdicts = await _phase(adapter, mode)
            out[mode] = ", ".join(
                f"{t}={'HOLD' if v else 'WANDER'}" for t, v in verdicts.items())
        log("=== SUMMARY ===")
        for k, v in out.items():
            log(f"  {k}: {v}")
        return out
    finally:
        discard_open_documents(adapter)


if __name__ == "__main__":
    sys.exit(run_build(build))
