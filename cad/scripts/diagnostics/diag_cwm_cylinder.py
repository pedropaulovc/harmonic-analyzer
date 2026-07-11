r"""Gating experiment for the drive-train cylinder-gear CopyWithMates2 ladder.

The 20 cylinder gears measured 156.0 s of the 1076 s drive-train build
(memory/v018-perf-review.md). Unlike the cone ladder (all three mates
reference the shared shaft -- the pure Repeat path), a cylinder gear's
slice does NOT fit Repeat: its axial dim chains to the PREVIOUS gear's
Front Plane and its gear-mesh mate couples a DIFFERENT cone gear at a
DIFFERENT ratio per station. Probed here ON THE REAL BUILT ASSEMBLY
(the toy-vs-real lesson of the attractor minimization).

Measured findings from the first run (2026-07-10), which this script now
asserts as the contract:

* ``NewEntityToMateTo`` DOES re-point a copied GEAR mate's external axis
  (both copies meshed their new cone gear), and the chained axial
  re-point lands the translation exactly (pose-err 0.0000 mm).
* The copied gear mate's ratio is INHERITED from the seed and IS
  editable via ``IGearMateFeatureData`` GetDefinition -> ratio ->
  ModifyDefinition (typed VT_DISPATCH null third arg). The stored form
  is normalized -- setting 12:120 reads back 120:12 -- so the edit is
  judged against the stored form of an AUTHORED station mate, not the
  raw pair that was set.
* BUT a copy carrying the mesh mate parks SPUN 9.1229 deg off the seed
  (both copies, identical angle, stable across rebuild) -- the
  parked-pose wander family, living in the copied gear mate's stored
  phase. It breaks the tuned tooth-in-gap phase, and no post-copy spin
  correction is safe: through the mesh coupling a driver/drag would
  crank the whole free train, moving every already-landed gear
  differentially.

Production candidate this probe therefore gates on (variant 2): NEVER
copy the mesh mate. Replicate a 2-mate seed (radial + chained axial),
put the copy's spin at design (nothing stores spin state once no mesh
mate is copied), then author each station's gear mate FRESH -- a fresh
mate records phase from the current pose and carries its ratio
natively (no tree walk, no ratio edit). Variant 2 is emulated on the
real slice by stripping copy A's copied mesh mate, replicating copy C
from it, and running the land-and-mesh sequence.

Nothing is ever saved. Run (SolidWorks already open)::

    uv run python cad\scripts\diagnostics\diag_cwm_cylinder.py
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _assembly import (  # noqa: E402
    component_names,
    component_transform,
    gear_mate,
    named_ref,
)
from _assembly_postbuild import discard_open_documents  # noqa: E402
from _common import OUT_SLDASM, _flag_only, check, log, run_build  # noqa: E402
from _cwm import (  # noqa: E402
    component_constrained_status,
    component_mate_count,
    copy_with_mates,
    external_mate_rows,
    mates_with_owners,
    put_component_pose,
    resolve_entity,
)

PREFIXES = {"cylinder-gear", "cone-gear", "cylinder-gear-shaft"}
TOL_MM = 0.05
TOL_DEG = 1e-4


def _stem(name: str) -> str:
    return name.rsplit("-", 1)[0]


def _org_mm(a16: list[float]) -> list[float]:
    return [a16[9] * 1000.0, a16[10] * 1000.0, a16[11] * 1000.0]


def _rot_delta_deg(a: list[float], b: list[float]) -> float:
    """Rotation angle (deg) between two array16 rotation blocks -- the spin
    wander readout. trace(Ra^T Rb) = 1 + 2 cos(theta)."""
    ra = [a[0:3], a[3:6], a[6:9]]
    rb = [b[0:3], b[3:6], b[6:9]]
    tr = sum(ra[r][c] * rb[r][c] for r in range(3) for c in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


def _gear_data(adapter: Any, mate_name: str) -> tuple[Any, Any]:
    """(feature, IGearMateFeatureData) for a gear mate by feature name."""
    from solidworks_mcp.adapters.solidworks.assembly import _read_member

    model = adapter.currentModel
    _flag_only(model, "FeatureByName")
    feat = adapter._attempt(lambda: model.FeatureByName(mate_name), default=None)
    if feat is None:
        raise RuntimeError(f"no mate feature {mate_name!r}")
    data = _read_member(feat, "GetDefinition")
    if data is None:
        raise RuntimeError(f"no definition on {mate_name!r}")
    return feat, data


def _read_ratio(adapter: Any, mate_name: str) -> tuple[float, float, bool]:
    _, data = _gear_data(adapter, mate_name)
    return (float(data.GearRatioNumerator), float(data.GearRatioDenominator),
            bool(data.Reverse))


def _set_ratio(adapter: Any, mate_name: str, num: float, den: float) -> None:
    """GetDefinition -> ratio -> ModifyDefinition. Third arg must be a typed
    VT_DISPATCH null -- a bare ``None`` marshals VT_NULL and the call
    silently no-ops (the set_distance_flip trap)."""
    import pythoncom
    from win32com.client import VARIANT

    feat, data = _gear_data(adapter, mate_name)
    data.GearRatioNumerator = num
    data.GearRatioDenominator = den
    _flag_only(feat, "ModifyDefinition")
    ok = adapter._attempt(
        lambda: feat.ModifyDefinition(
            data, adapter.currentModel, VARIANT(pythoncom.VT_DISPATCH, None)),
        default=False)
    if not ok:
        raise RuntimeError(f"ModifyDefinition failed on {mate_name!r}")


def _delete_feature(adapter: Any, name: str) -> None:
    """Select2 + DeleteSelection2 (build_channel_assembly's recipe)."""
    model = adapter.currentModel
    feat = adapter._attempt(lambda: model.FeatureByName(name), default=None)
    if feat is None:
        raise RuntimeError(f"feature to delete not found: {name!r}")
    adapter._attempt(lambda: model.ClearSelection2(True), default=None)
    if not adapter._attempt(lambda: feat.Select2(False, 0), default=False):
        raise RuntimeError(f"failed to select feature for delete: {name!r}")
    if not adapter._attempt(
            lambda: model.Extension.DeleteSelection2(0), default=False):
        adapter._attempt(lambda: model.EditDelete(), default=None)
    if adapter._attempt(lambda: model.FeatureByName(name), default=None) is not None:
        raise RuntimeError(f"feature {name!r} still present after delete")


def _teeth(adapter: Any, cone: str) -> int:
    cfg = str(adapter.currentModel.GetComponentByName(cone)
              .ReferencedConfiguration)
    return int(cfg.lstrip("T"))


def _copy_one(adapter: Any, seed: str, n: int, dist_slot: int,
              pitch_mm: float, flip: bool, axial_ent: Any,
              gear_slot: int | None = None, mesh_ent: Any = None,
              gear_slot_value: float = 0.0) -> tuple[str, float]:
    """One chained-re-point copy; returns (new instance, seconds)."""
    values = [0.0] * n
    values[dist_slot] = pitch_mm / 1000.0
    repeat = [True] * n
    new_ents: list[Any] = [None] * n
    flips = [False] * n
    repeat[dist_slot] = False
    new_ents[dist_slot] = axial_ent
    flips[dist_slot] = flip
    if gear_slot is not None:
        values[gear_slot] = gear_slot_value
        repeat[gear_slot] = False
        new_ents[gear_slot] = mesh_ent
    before = set(component_names(adapter))
    t0 = time.monotonic()
    copy_with_mates(adapter, [seed], n, values, flips=flips,
                    repeat=repeat, new_entities=new_ents)
    dt = time.monotonic() - t0
    new = sorted(set(component_names(adapter)) - before)
    if len(new) != 1:
        raise RuntimeError(f"expected 1 new component, got {new}")
    return new[0], dt


async def build(adapter: Any) -> dict[str, str]:
    check("open drive-train",
          await adapter.open_model(str(OUT_SLDASM / "drive-train.SLDASM")))
    try:
        return await _probe(adapter)
    finally:
        # Discard the mutated model WITHOUT saving, even on a raise -- the
        # built artefact must stay byte-identical (verify reopens it).
        discard_open_documents(adapter)


async def _probe(adapter: Any) -> dict[str, str]:
    results: dict[str, str] = {}
    comps = component_names(adapter)
    cyls = sorted((c for c in comps if _stem(c) == "cylinder-gear"),
                  key=lambda c: component_transform(adapter, c)[11])
    if len(cyls) < 4:
        raise RuntimeError(f"need >= 4 cylinder gears, found {len(cyls)}")
    seed = cyls[-1]  # last station: its axial mate has the chained shape

    log("--- survey (one mate-tree walk) ---")
    t0 = time.monotonic()
    rows = mates_with_owners(adapter, PREFIXES)
    log(f"tree walk: {len(rows)} mates in {time.monotonic() - t0:.1f}s")
    seed_rows = [r for r in rows if seed in r["instances"]]
    ext = external_mate_rows(seed_rows, {seed})
    if len(ext) != 3:
        raise RuntimeError(f"seed {seed}: expected 3 external mates, got"
                           f" {[(r['name'], r['type']) for r in ext]}")
    dist_slots = [i for i, r in enumerate(ext) if r["type"] == "MateDistanceDim"]
    gear_slots = [i for i, r in enumerate(ext) if "Gear" in r["type"]]
    if len(dist_slots) != 1 or len(gear_slots) != 1:
        raise RuntimeError(f"slot shapes off: {[r['type'] for r in ext]}")
    dist_slot, gear_slot = dist_slots[0], gear_slots[0]
    dist_row, gear_row = ext[dist_slot], ext[gear_slot]
    flip = bool(dist_row["flip"])
    # The one-pitch step comes from ADJACENT-by-z station transforms, NOT
    # from the seed's own dim partner/value: under the production star
    # ladder every copy's axial dim references STATION 0 (value j * pitch),
    # so the dim partner is the far end of the drum and its value the whole
    # stack span (codex #240). The dim's FLIP side still transfers to the
    # one-pitch copies -- same plane pair, same +z side, any magnitude.
    prev = cyls[-2]
    seed_cone = next(i for i in gear_row["instances"] if i != seed)
    # cyl instance -> (its cone, its authored mesh-mate name), for every
    # station: the copies' targets AND the stored-form ground truth.
    mesh_of = {
        next(i for i in r["instances"] if _stem(i) == "cylinder-gear"):
            (next(i for i in r["instances"] if _stem(i) == "cone-gear"),
             r["name"])
        for r in rows
        if "Gear" in r["type"]
        and any(_stem(i) == "cylinder-gear" for i in r["instances"])
        and any(_stem(i) == "cone-gear" for i in r["instances"])
    }
    cone_a, cone_b, cone_c = (mesh_of[cyls[-2]][0], mesh_of[cyls[-3]][0],
                              mesh_of[cyls[-4]][0])
    seed_ratio = _read_ratio(adapter, gear_row["name"])
    seed_status = component_constrained_status(adapter, seed)
    seed_a16 = list(component_transform(adapter, seed))
    prev_a16 = list(component_transform(adapter, prev))
    seed_org, prev_org = _org_mm(seed_a16), _org_mm(prev_a16)
    step = [seed_org[k] - prev_org[k] for k in range(3)]
    pitch_mm = math.dist(seed_org, prev_org)
    prev2_org = _org_mm(list(component_transform(adapter, cyls[-3])))
    if abs(math.dist(prev_org, prev2_org) - pitch_mm) > TOL_MM:
        raise RuntimeError(
            f"stack pitch not uniform: {pitch_mm:.3f} vs"
            f" {math.dist(prev_org, prev2_org):.3f} between the last three"
            " stations -- adjacent-transform pitch derivation is invalid")
    log(f"seed {seed}: slots dist={dist_slot} gear={gear_slot}"
        f" pitch={pitch_mm:.3f} flip={flip} status={seed_status}")
    log(f"seed mesh '{gear_row['name']}' vs {seed_cone}"
        f" ({_teeth(adapter, seed_cone)}T):"
        f" stored ratio {seed_ratio[0]:g}:{seed_ratio[1]:g}"
        f" reverse={seed_ratio[2]}")
    # Authored stored-form ground truth per target cone: the neighbour
    # stations' own mesh mates (what a correct edit must read back as).
    authored_form = {}
    for cyl in (cyls[-2], cyls[-3]):
        cone, name = mesh_of[cyl]
        authored_form[cone] = _read_ratio(adapter, name)
        log(f"authored '{name}' vs {cone} ({_teeth(adapter, cone)}T):"
            f" stored ratio {authored_form[cone][0]:g}"
            f":{authored_form[cone][1]:g} reverse={authored_form[cone][2]}")

    log("--- phase 1: copies CARRYING the mesh mate (findings) ---")
    copies: list[tuple[str, str, list[float]]] = []  # (name, cone, target org)
    anchor, anchor_org = seed, seed_org
    for tag, cone in (("A", cone_a), ("B", cone_b)):
        axial_ent = resolve_entity(
            adapter, named_ref(f"Front Plane@{anchor}", "PLANE"))
        mesh_ent = resolve_entity(adapter, named_ref(f"Axis1@{cone}", "AXIS"))
        copy, dt = _copy_one(adapter, seed, 3, dist_slot, pitch_mm, flip,
                             axial_ent, gear_slot, mesh_ent, 0.0)
        a16 = list(component_transform(adapter, copy))
        org = _org_mm(a16)
        tgt = [anchor_org[k] + step[k] for k in range(3)]
        pose_mm = math.dist(org, tgt)
        spin_deg = _rot_delta_deg(seed_a16, a16)
        mates = component_mate_count(adapter, copy)
        status = component_constrained_status(adapter, copy)
        ok = pose_mm < TOL_MM and mates == 3 and status == seed_status
        log(f"  copy {tag} = {copy} (mesh -> {cone}): {dt:.2f}s"
            f" pose-err={pose_mm:.4f}mm mates={mates} status={status}"
            f" -> {'PASS' if ok else 'FAIL'};"
            f" WANDER={spin_deg:.4f}deg (the copied-mesh disqualifier)")
        results[f"copy-{tag}"] = "PASS" if ok else "FAIL"
        copies.append((copy, cone, tgt))
        anchor, anchor_org = copy, tgt

    log("--- phase 2: re-point + ratio-edit findings (one tree walk) ---")
    rows2 = mates_with_owners(adapter, PREFIXES)
    copy_mesh_name: dict[str, str] = {}
    for copy, cone, _tgt in copies:
        mesh = [r for r in rows2
                if copy in r["instances"] and "Gear" in r["type"]]
        if len(mesh) != 1:
            raise RuntimeError(f"{copy}: expected 1 gear mate, got"
                               f" {[r['name'] for r in mesh]}")
        row = mesh[0]
        copy_mesh_name[copy] = row["name"]
        repointed = cone in row["instances"]
        got = _read_ratio(adapter, row["name"])
        log(f"  {copy} mesh '{row['name']}': partners={sorted(row['instances'])}"
            f" inherited ratio {got[0]:g}:{got[1]:g}"
            f" -> re-point {'PASS' if repointed else 'FAIL'}")
        results[f"repoint-{copy}"] = "PASS" if repointed else "FAIL"
        _set_ratio(adapter, row["name"], float(_teeth(adapter, cone)), 120.0)
        got = _read_ratio(adapter, row["name"])
        want = authored_form[cone]
        edit_ok = (got[0], got[1]) == (want[0], want[1])
        log(f"  {copy} ratio edit -> stored {got[0]:g}:{got[1]:g}"
            f" (authored form {want[0]:g}:{want[1]:g})"
            f" -> {'PASS' if edit_ok else 'FAIL'}")
        results[f"ratio-{copy}"] = "PASS" if edit_ok else "FAIL"

    log("--- variant 2: fresh-mesh recipe (the production candidate) ---")
    # Strip copy A's copied mesh -> the 2-external-mate seed shape the
    # production ladder would replicate (radial Repeat + chained axial).
    copy_a = copies[0][0]
    copy_b, _cone_b, tgt_b = copies[1]
    _delete_feature(adapter, copy_mesh_name[copy_a])
    # Removing the gear row keeps the remaining slots' relative tree order.
    dist_slot2 = dist_slot - (1 if gear_slot < dist_slot else 0)
    axial_ent = resolve_entity(
        adapter, named_ref(f"Front Plane@{copy_b}", "PLANE"))
    copy_c, dt = _copy_one(adapter, copy_a, 2, dist_slot2, pitch_mm, flip,
                           axial_ent)
    tgt_c = [tgt_b[k] + step[k] for k in range(3)]
    a16 = list(component_transform(adapter, copy_c))
    pose_mm = math.dist(_org_mm(a16), tgt_c)
    spin_deg = _rot_delta_deg(seed_a16, a16)
    log(f"  copy C = {copy_c} (2-mate, from {copy_a}): {dt:.2f}s"
        f" pose-err={pose_mm:.4f}mm spin-off-design={spin_deg:.4f}deg")
    if pose_mm > TOL_MM:
        raise RuntimeError(f"copy C translation off by {pose_mm:.4f}mm --"
                           " the 2-mate chained copy does not land")
    if spin_deg > TOL_DEG:
        # Land the spin: design rotation = the seed's (every station is
        # inserted at the same rot). Nothing stores spin state on a 2-mate
        # copy, so a plain Transform2 put should hold -- measured below.
        t0 = time.monotonic()
        put = list(seed_a16)
        put[9:12] = [v / 1000.0 for v in tgt_c]
        put_component_pose(adapter, copy_c, put)
        a16 = list(component_transform(adapter, copy_c))
        spin_deg = _rot_delta_deg(seed_a16, a16)
        log(f"  copy C put -> spin {spin_deg:.4f}deg"
            f" ({time.monotonic() - t0:.2f}s)")
    t0 = time.monotonic()
    await gear_mate(
        adapter,
        named_ref(f"Axis1@{cone_c}", "AXIS"),
        named_ref(f"Axis2@{copy_c}", "AXIS"),
        [_teeth(adapter, cone_c), 120],
        label=f"probe fresh mesh {cone_c}:cyl120",
    )
    log(f"  fresh gear mate authored in {time.monotonic() - t0:.2f}s")
    model = adapter.currentModel
    if not adapter._attempt(lambda: model.EditRebuild3(), default=False):
        raise RuntimeError("EditRebuild3 returned False after fresh mesh")
    a16 = list(component_transform(adapter, copy_c))
    pose_mm = math.dist(_org_mm(a16), tgt_c)
    spin_deg = _rot_delta_deg(seed_a16, a16)
    mates = component_mate_count(adapter, copy_c)
    status = component_constrained_status(adapter, copy_c)
    ok = (pose_mm < TOL_MM and spin_deg < TOL_DEG and mates == 3
          and status == seed_status)
    log(f"  copy C post-rebuild: pose-err={pose_mm:.4f}mm"
        f" spin={spin_deg:.4f}deg mates={mates} status={status}"
        f" -> {'PASS' if ok else 'FAIL'}")
    results["variant2-land-and-mesh"] = "PASS" if ok else "FAIL"

    log("--- closing stability (put-reversion tripwire) ---")
    if not adapter._attempt(lambda: model.EditRebuild3(), default=False):
        raise RuntimeError("closing EditRebuild3 returned False")
    a16 = list(component_transform(adapter, copy_c))
    drift = math.dist(_org_mm(a16), tgt_c)
    spin = _rot_delta_deg(seed_a16, a16)
    ok = drift < TOL_MM and spin < TOL_DEG
    log(f"  {copy_c}: second-rebuild drift={drift:.4f}mm spin={spin:.4f}deg"
        f" -> {'PASS' if ok else 'FAIL'}")
    results["variant2-stable"] = "PASS" if ok else "FAIL"

    log("=== SUMMARY ===")
    for key, verdict in results.items():
        log(f"  {key}: {verdict}")
    failed = [k for k, v in results.items() if v != "PASS"]
    if failed:
        raise RuntimeError(f"cylinder-ladder probe FAILED: {failed}")
    return results


if __name__ == "__main__":
    sys.exit(run_build(build))
