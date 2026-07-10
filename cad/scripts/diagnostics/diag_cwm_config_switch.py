r"""Gating experiment for the drive-train cone-gear CopyWithMates2 ladder:
can a copy switch ReferencedConfiguration and stay healthy?

The 20 cone gears are the ideal CopyWithMates2 slice -- FULLY DEFINED
(coaxial + axial-seat distance + parallel anti-spin, all referencing the
shared shaft; the vendor-blessed copy case, no free-DOF attractor risk,
measured 174.5 s of the 1076 s drive-train build) -- EXCEPT that each
station is a different part configuration (T120..T006). CopyWithMates2
clones the seed's referenced configuration, so the ladder only works if
the copy can be re-pointed at its own configuration afterwards.

This script keys a seed cone-gear (T120) onto the cone-gear-shaft in a
throwaway assembly, makes one copy per target configuration with the
axial-seat slot re-valued one step over, switches each copy's
``ReferencedConfiguration``, rebuilds, and validates the production way:
pose on target, 3 mates carried, fully-defined status, the configuration
read back, and the body actually re-sized (bounding-box diameter shrinks
with the tooth count). Nothing is ever saved.

Run (SolidWorks already open)::

    uv run python cad\scripts\diagnostics\diag_cwm_config_switch.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _assembly import (  # noqa: E402
    coincident_mate,
    component_names,
    component_transform,
    distance_driver,
    named_ref,
    parallel_mate,
    place_component,
)
from _assembly_postbuild import discard_open_documents  # noqa: E402
from _common import _flag_only, check, log, run_build  # noqa: E402
from _cwm import (  # noqa: E402
    component_constrained_status,
    component_mate_count,
    copy_with_mates,
    external_mate_rows,
    mates_with_owners,
)

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
# Dim VALUES stay positive; the flip rule's natural side for this
# plane-plane distance is -Z (measured: +Z0 raised flip-seed MISS off by
# 2*Z0), so the design frame marches -Z (same as diag_cwm_attractor).
Z0 = 40.0  # seed axial seat depth off the shaft's Front plane (arbitrary)
STEP = 10.0  # ladder step (repro-arbitrary; the real ladder uses SEAT_PITCH)
SEED_CFG = "T120"
TARGET_CFGS = ("T114", "T108", "T102")
FULLY_CONSTRAINED = 3  # swConstrainedStatus_e.swFullyConstrained
TOL_MM = 0.05


def _org_mm(adapter, name: str) -> list[float]:
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


def _box_dia_mm(adapter, name: str) -> float:
    """XY extent of the component's bounding box -- tracks the tooth-ring
    diameter, so a real configuration switch must SHRINK it."""
    model = adapter.currentModel
    comp = model.GetComponentByName(name)
    _flag_only(comp, "GetBox")
    box = adapter._attempt(
        lambda: comp.GetBox(False, False), default=None)
    if not box:
        raise RuntimeError(f"GetBox failed for {name!r}")
    return max(box[3] - box[0], box[4] - box[1]) * 1000.0


def _referenced_configuration(adapter, name: str) -> str:
    comp = adapter.currentModel.GetComponentByName(name)
    return str(comp.ReferencedConfiguration)


def _switch_configuration(adapter, name: str, cfg: str) -> None:
    comp = adapter.currentModel.GetComponentByName(name)
    comp.ReferencedConfiguration = cfg


async def build(adapter) -> dict[str, str]:
    try:
        check("create_assembly", await adapter.create_assembly())
        shaft = await place_component(
            adapter, "cone-gear-shaft", [0.0, 0.0, 0.0], [0.0, 0.0, 0.0],
            IDENTITY, ground=False, label="cone-gear-shaft (seed, auto-fixed)")
        seed = await place_component(
            adapter, "cone-gear", [0.0, 0.0, -Z0], [0.0, 0.0, 0.0], IDENTITY,
            ground=False, configuration=SEED_CFG,
            label=f"cone-gear {SEED_CFG} seed")
        tgt = [0.0, 0.0, -Z0]
        await coincident_mate(
            adapter, named_ref(f"Axis1@{seed}", "AXIS"),
            named_ref(f"Axis1@{shaft}", "AXIS"),
            label="seed coaxial", verify=(seed, tgt))
        await distance_driver(
            adapter, named_ref(f"Front Plane@{seed}", "PLANE"),
            named_ref(f"Front Plane@{shaft}", "PLANE"), Z0,
            label=f"seed axial seat d={Z0:.2f}", verify=(seed, tgt))
        await parallel_mate(
            adapter, named_ref(f"Right Plane@{seed}", "PLANE"),
            named_ref(f"Right Plane@{shaft}", "PLANE"),
            label="seed anti-spin (keyed phase)", verify=(seed, tgt))

        rows = [r for r in mates_with_owners(
            adapter, {"cone-gear", "cone-gear-shaft"}) if seed in r["instances"]]
        ext = external_mate_rows(rows, {seed})
        dims = [i for i, r in enumerate(ext)
                if r["type"] == "MateDistanceDim"]
        assert len(rows) == 3 and len(dims) == 1, (rows, dims)
        dim_slot = dims[0]
        seed_status = component_constrained_status(adapter, seed)
        seed_dia = _box_dia_mm(adapter, seed)
        log(f"seed: 3 mates, dim slot {dim_slot}, status={seed_status},"
            f" box dia {seed_dia:.2f}")

        results: dict[str, str] = {}
        for k, cfg in enumerate(TARGET_CFGS, start=1):
            values = [0.0] * 3
            values[dim_slot] = (Z0 + k * STEP) / 1000.0
            before = set(component_names(adapter))
            copy_with_mates(adapter, [seed], 3, values)
            new = sorted(set(component_names(adapter)) - before)
            assert len(new) == 1, new
            copy = new[0]
            org = _org_mm(adapter, copy)
            log(f"--- copy {copy} -> {cfg} at z={-(Z0 + k * STEP):.1f} ---")
            log(f"  post-copy pose z={org[2]:.3f} cfg="
                f"{_referenced_configuration(adapter, copy)}")
            _switch_configuration(adapter, copy, cfg)
            model = adapter.currentModel
            if not adapter._attempt(lambda: model.EditRebuild3(), default=False):
                raise RuntimeError(f"EditRebuild3 False after {copy} -> {cfg}")
            got_cfg = _referenced_configuration(adapter, copy)
            org = _org_mm(adapter, copy)
            mates = component_mate_count(adapter, copy)
            status = component_constrained_status(adapter, copy)
            dia = _box_dia_mm(adapter, copy)
            pose_ok = (abs(org[0]) < TOL_MM and abs(org[1]) < TOL_MM
                       and abs(org[2] + (Z0 + k * STEP)) < TOL_MM)
            ok = (got_cfg == cfg and pose_ok and mates == 3
                  and status == seed_status and dia < seed_dia - 1.0)
            log(f"  cfg={got_cfg} pose=({org[0]:.3f},{org[1]:.3f},{org[2]:.3f})"
                f" mates={mates} status={status} dia={dia:.2f}"
                f" -> {'PASS' if ok else 'FAIL'}")
            results[cfg] = "PASS" if ok else "FAIL"
        log("=== SUMMARY ===")
        for cfg, verdict in results.items():
            log(f"  {cfg}: {verdict}")
        return results
    finally:
        discard_open_documents(adapter)


if __name__ == "__main__":
    sys.exit(run_build(build))
