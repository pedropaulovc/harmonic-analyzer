r"""Empirical probe: can ONE ``CopyWithMates2`` call replicate a channel's
whole 4-part moving chain (rocker + connecting-rod + amplitude-bar +
channel-lever, 12 mates) to the next Z station?

Follow-up to ``diag_copy_with_mates.py`` (single-part ladder, PASS
2026-07-09: native-typed arrays, positional per-mate ``Values``, ~0.65s/copy
vs ~4.4s production seat) and the prior session's F2 slice probe on toy
geometry (2 parts / 4 mates: internal mates re-bound between the copies,
external mates repeated). This is the production-shaped question: the
channel build authors ~12 mates per channel x 20 channels one
CreateMate+EditRebuild3 at a time; if a slice copy carries the whole chain,
channels 2..19 collapse to one call each.

Contracts under test (all previously measured, see memory/v018-perf-review.md):
  C1  arrays are sized to the DISTINCT mates of the slice (F2: 2 comps /
      4 mates); here 4 comps / 12 mates. The per-slot ORDER for a
      multi-component slice is NOT plain tree order (measured 2026-07-09:
      5 of 6 dims followed it, but foot-X consumed the J2-spin slot) and
      no armchair rule fits all six -- so the probe DISCOVERS the mapping
      with a sentinel-valued calibration copy, then deletes it.
  C2  ``Values`` entries map positionally per slot; entries under
      dimension-less mates are dead; every dimension mate must carry its
      REAL value (a 0.0 re-values it to zero -- the Z=0 landing of the
      first ladder run and the rod-ring-on-Right-Plane landing of the
      first slice run).
  C3  the ONE substituted entry is the rocker's axial distance to the
      anchor bushing's Front plane: PITCH/2 + k*PITCH, always positive =
      always the seed's side (Q5: FlipDimension is a NO-OP under
      Repeat=True; a copy inherits the seed's side, so the anchor must
      keep every station on one side -- which the bushing anchor does,
      unlike the Front-datum anchor whose stations cross zero).

Judged from the model (transforms + mate count), never from the lying
return value. Fresh throwaway assembly, NEVER saved.

Run (SolidWorks open, seat free; ~2-4 min)::

    uv run python cad\scripts\diagnostics\diag_copy_with_mates_slice.py
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

import pythoncom  # noqa: E402
from win32com.client import VARIANT  # noqa: E402

from _common import check, log, run_build  # noqa: E402
from _assembly import (  # noqa: E402
    _mate_hard_error,
    coincident_mate,
    component_names,
    component_transform,
    distance_driver,
    named_ref,
    place_component,
    spin_driver,
    world_point,
)
from _transforms import ROT_Y_180, compose_rows, euler_from_rows, rows_from_euler  # noqa: E402
import _telemetry  # noqa: E402
from solidworks_mcp.adapters.base import (  # noqa: E402
    ComponentRefParameters,
    MateRefParameters,
)
from solidworks_mcp.adapters.solidworks.assembly import (  # noqa: E402
    _mate_group_subfeatures,
    _read_member,
)
from build_channel_assembly import (  # noqa: E402
    ARM_ARC_CENTER_LOCAL_Y,
    ARM_MID_DZ,
    ARM_PIVOT_LOCAL_Y,
    BAR_FOOT_LOCAL,
    BAR_WIDTH,
    CAM_DZ,
    FULCRUM,
    IDENTITY,
    LEVER_BAR_PIN_BORE_LOCAL,
    PITCH,
    PIVOT,
    PIVOT_BUSHING_OD,
    PIVOT_SHAFT_Z,
    RING_CENTER,
    ROCKER_ROD_BORE_LOCAL,
    ROD_PIN_BORE_LOCAL,
    ROD_STRAP_BORE_LOCAL,
    SHAFT_R,
    _org,
    _revolute,
    _seat_bushing_on_shaft,
    bore_axis_ref,
    rot_z_rows,
    solve_state,
    z_station,
)

SEED_J = 1  # seed channel: its rocker anchors to the gap-1 bushing at PITCH/2
N_COPY_STATIONS = 4  # copies land at channels SEED_J+1 .. SEED_J+N
SLICE_MATES = 12  # J1(3) + J2(3) + J4(2) + J3(3) + J5(1), creation order
PIVOT_OD_PT = [PIVOT[0] + SHAFT_R, PIVOT[1], 0.0]
FULC_OD_PT = [FULCRUM[0] + SHAFT_R, FULCRUM[1], 0.0]
CHAIN_PARTS = ("rocker-arm", "connecting-rod", "amplitude-bar", "channel-lever")


# Semantic identity of each dimension mate in the slice, classified by the
# part prefixes of its two mated components ("ROOT" = an assembly plane;
# measured: the ReferenceComponent of a root plane is the assembly document
# itself, e.g. "Assem50", so any prefix that is not a known part maps to
# ROOT). Unique for this chain, so a copied dim is identifiable no matter
# what order the copy created it in.
_SEM_BY_OWNERS = {
    frozenset({"rocker-arm", "pivot-bushing"}): "J1a",
    frozenset({"rocker-arm", "ROOT"}): "J1s",
    frozenset({"connecting-rod", "rocker-arm"}): "J2a",
    frozenset({"connecting-rod", "ROOT"}): "J2s",
    frozenset({"amplitude-bar", "ROOT"}): "footX",
    frozenset({"amplitude-bar", "rocker-arm"}): "J5",
}
_KNOWN_PART_PREFIXES = set(CHAIN_PARTS) | {
    "pivot-bushing", "pivot-shaft", "fulcrum-shaft"}
# Position of each semantic dim in _seed_chain's creation-order dims list.
_DIMS_IDX_BY_SEM = {"J1a": 1, "J1s": 2, "J2a": 4, "J2s": 5, "footX": 10, "J5": 11}
# The dims whose slots MUST calibrate: the EXTERNAL ones (referencing an
# entity outside the copied set). The 2026-07-09 calibration measured that
# ONLY external mates get Values slots (tree-ordered among themselves:
# J1c=0, J1a=1, J1s=2, J2s=3, J4c=4, footX=5) -- INTERNAL mates (J2a, J5)
# are re-bound between the copies and INHERIT their dims (sentinels never
# touched them), so they need no slot and no value.
_EXTERNAL_SEMS = {"J1a", "J1s", "J2s", "footX"}


def _mates_with_owners(adapter) -> list[dict]:
    """EVERY mate in tree order: name, type, owner prefixes, instance
    names; for distance dims also D1 (mm) and the mate's own FlipDimension
    state (its side of the reference)."""
    model = adapter.currentModel
    out: list[dict] = []
    for feat in _mate_group_subfeatures(adapter):
        tname = str(_read_member(feat, "GetTypeName2"))
        name = str(_read_member(feat, "Name"))
        mm = flip = None
        if tname == "MateDistanceDim":
            param = adapter._attempt(
                lambda n=name: model.Parameter(f"D1@{n}"), default=None)
            val = _read_member(param, "SystemValue") if param is not None else None
            mm = (val or 0.0) * 1000.0
            data = _read_member(feat, "GetDefinition")
            flip = bool(_read_member(data, "FlipDimension")) if data else None
        mate = _read_member(feat, "GetSpecificFeature2")
        owners = set()
        instances = set()
        for i in range(2):
            ent = adapter._attempt(
                lambda m=mate, k=i: m.MateEntity(k), default=None)
            owner = _read_member(ent, "ReferenceComponent") if ent else None
            nm = str(_read_member(owner, "Name2") or "") if owner else ""
            part = nm.rsplit("-", 1)[0] if nm else ""
            if part in _KNOWN_PART_PREFIXES:
                owners.add(part)
                instances.add(nm)
            else:
                owners.add("ROOT")
        out.append({"name": name, "type": tname, "mm": mm,
                    "owners": frozenset(owners), "instances": instances,
                    "flip": flip})
    return out


def _dim_mates_with_owners(adapter) -> list[dict]:
    """Every MateDistanceDim in tree order (see :func:`_mates_with_owners`)."""
    return [r for r in _mates_with_owners(adapter)
            if r["type"] == "MateDistanceDim"]


def _spin_dim_value(pivot_xy: tuple[float, float], target_xy: tuple[float, float]) -> float:
    """The dimension value spin_driver authors: the better-conditioned
    in-plane coordinate of the off-pivot bore (see _assembly.spin_driver)."""
    dx = target_xy[0] - pivot_xy[0]
    dy = target_xy[1] - pivot_xy[1]
    return abs(target_xy[1]) if abs(dx) >= abs(dy) else abs(target_xy[0])


async def _seed_chain(adapter, j: int, bushing: str) -> tuple[dict[str, str], list[float], float]:
    """Author channel ``j``'s 4-part chain the production way, HARD-PINNED
    (no park deferral: every spin/amplitude driver authored, so the slice is
    fully defined and the copies replicate the full 12-mate battery).

    Returns (component names by part, per-mate dimension values in creation
    order, wall seconds). The values list is the probe's ground truth for
    the ``Values`` array (C2): dimension-less mates carry 0.0 (dead entries).
    """
    t0 = time.perf_counter()
    st = solve_state(0.0)  # neutral amplitude for every station
    zj = z_station(j)
    z_mid = zj + ARM_MID_DZ
    arm_rows = compose_rows(rot_z_rows(st["arm_tilt"]), ROT_Y_180)
    rod_rows = compose_rows(rot_z_rows(st["rod_tilt"]), ROT_Y_180)
    t = math.radians(st["arm_tilt"])
    arm_origin_dx = ARM_PIVOT_LOCAL_Y * math.sin(t)
    arm_origin_dy = ARM_PIVOT_LOCAL_Y * math.cos(t)
    bar_rows = rows_from_euler([st["bar_tilt"], -90.0, 0.0])
    lever_rows = compose_rows(rot_z_rows(st["lever_tilt"]), ROT_Y_180)

    rocker = await place_component(
        adapter, "rocker-arm",
        [PIVOT[0] - arm_origin_dx, PIVOT[1] - arm_origin_dy, z_mid],
        euler_from_rows(arm_rows), arm_rows,
        ground=False, label=f"rocker-arm ch{j:02d} (slice seed)",
    )
    rod = await place_component(
        adapter, "connecting-rod",
        [RING_CENTER[0], RING_CENTER[1], zj + CAM_DZ],
        euler_from_rows(rod_rows), rod_rows,
        ground=False, label=f"connecting-rod ch{j:02d} (slice seed)",
    )
    bar = await place_component(
        adapter, "amplitude-bar",
        [st["bar_origin_x"], st["bar_origin_y"], z_mid - BAR_WIDTH / 2.0],
        [st["bar_tilt"], -90.0, 0.0], bar_rows,
        ground=False, label=f"amplitude-bar ch{j:02d} (slice seed)",
    )
    lever = await place_component(
        adapter, "channel-lever",
        [FULCRUM[0], FULCRUM[1], z_mid],
        euler_from_rows(lever_rows), lever_rows,
        ground=False, label=f"channel-lever ch{j:02d} (slice seed)",
    )

    pivot_w = (PIVOT[0], PIVOT[1])
    fulc_w = (FULCRUM[0], FULCRUM[1])
    dims: list[float] = []

    # J1 rocker revolute: concentric(dead) + axial distance(SUBSTITUTED) +
    # spin pin. Same call as production but park_spin=None -> hard pin.
    rocker_rod_pin = world_point(adapter, rocker, ROCKER_ROD_BORE_LOCAL)
    await _revolute(
        adapter, rocker,
        bore_axis_ref(PIVOT_OD_PT), named_ref(f"Axis1@{rocker}", "AXIS"),
        concentric=True, off_axis_name="Axis2",
        off_axis_local=ROCKER_ROD_BORE_LOCAL, pivot_xy=pivot_w,
        label=f"J1 rocker ch{j:02d}",
        axial=("distance", bushing, PITCH / 2.0),
        park_spin=None,
    )
    dims += [0.0, PITCH / 2.0,
             _spin_dim_value(pivot_w, (rocker_rod_pin[0], rocker_rod_pin[1]))]

    # J2 rod: coaxial(dead) + axial distance + spin pin (production body,
    # free_dof_key omitted -> hard).
    rod_tgt = _org(adapter, rod)
    rod_ring = world_point(adapter, rod, ROD_STRAP_BORE_LOCAL)
    rod_pin = world_point(adapter, rod, ROD_PIN_BORE_LOCAL)
    await coincident_mate(
        adapter, named_ref(f"Axis2@{rocker}", "AXIS"), named_ref(f"Axis2@{rod}", "AXIS"),
        label=f"J2 rod ch{j:02d} coaxial pin <- {rocker}", verify=(rod, rod_tgt),
    )
    await distance_driver(
        adapter, named_ref(f"Front Plane@{rod}", "PLANE"),
        named_ref(f"Front Plane@{rocker}", "PLANE"),
        rod_tgt[2] - z_mid,
        label=f"J2 rod ch{j:02d} axial d={abs(rod_tgt[2] - z_mid):.2f} <- {rocker}",
        verify=(rod, rod_tgt),
    )
    # The rod-swing pin is authored so the UPRIGHT branch is the FALSE
    # side: a copy RESETS a re-valued dim's FlipDimension to False (the
    # array is ignored on the Repeat path -- measured, module docstring),
    # so False-means-upright is the only way a copied rod lands upright
    # FROM THE START (Pedro 2026-07-09: the mirrored branch is the old
    # drive-train side and must never appear, even transiently). Which
    # flip state the upright solve stores depends on the mate's
    # formulation, so try candidates (entity order x reference plane) and
    # keep the first whose authored state reads False; distance_driver
    # verifies the POSE upright either way, so a True candidate is
    # deleted and the next tried.
    axis_ref = named_ref(f"Axis1@{rod}", "AXIS")
    spin_val = None
    for tag, ra, rb, target in (
        ("axis~Right", axis_ref, named_ref("Right Plane", "PLANE"), rod_ring[0]),
        ("Right~axis", named_ref("Right Plane", "PLANE"), axis_ref, rod_ring[0]),
        ("axis~Top", axis_ref, named_ref("Top Plane", "PLANE"), rod_ring[1]),
        ("Top~axis", named_ref("Top Plane", "PLANE"), axis_ref, rod_ring[1]),
    ):
        await distance_driver(
            adapter, ra, rb, target,
            label=f"J2 rod ch{j:02d} swing [{tag}] -> "
                  f"ring {rod_ring[0]:.1f},{rod_ring[1]:.1f}",
            verify=(rod, rod_tgt),
        )
        row = [d for d in _dim_mates_with_owners(adapter)
               if d["owners"] == frozenset({"connecting-rod", "ROOT"})][-1]
        log(f"rod spin [{tag}]: authored FlipDimension={row['flip']}")
        if row["flip"] is False:
            spin_val = abs(target)
            break
        check(f"delete rod spin [{tag}] (flip=True, try next formulation)",
              await adapter.delete_mate(MateRefParameters(name=row["name"])))
    if spin_val is None:
        # No False-side formulation exists -- re-author the production form
        # and let copies lean on the FlipDimension repair (the documented
        # fallback).
        await spin_driver(
            adapter, axis_ref,
            (rod_pin[0], rod_pin[1]), (rod_ring[0], rod_ring[1]),
            label=f"J2 rod ch{j:02d} swing -> ring {rod_ring[0]:.1f},{rod_ring[1]:.1f}",
            verify=(rod, rod_tgt),
        )
        spin_val = _spin_dim_value((rod_pin[0], rod_pin[1]),
                                   (rod_ring[0], rod_ring[1]))
        log("rod spin: NO False-side formulation found -- copies will lean "
            "on the FlipDimension repair")
    dims += [0.0, abs(rod_tgt[2] - z_mid), spin_val]

    # J4 lever revolute: concentric(dead) + coincident mid-plane(dead), no
    # spin (closed by J5).
    await _revolute(
        adapter, lever,
        bore_axis_ref(FULC_OD_PT), named_ref(f"Axis1@{lever}", "AXIS"),
        concentric=True, off_axis_name="Axis2",
        off_axis_local=LEVER_BAR_PIN_BORE_LOCAL, pivot_xy=fulc_w,
        label=f"J4 lever ch{j:02d}", axial=("coincident", rocker),
        pin_spin=False,
    )
    dims += [0.0, 0.0]

    # J3 bar: top-pin hinge(dead) + mid-plane(dead) + foot-X distance (the
    # amplitude driver, hard-pinned here).
    bar_tgt = _org(adapter, bar)
    foot = world_point(adapter, bar, BAR_FOOT_LOCAL)
    await coincident_mate(
        adapter,
        named_ref(f"Axis2@{lever}", "AXIS"), named_ref(f"Axis1@{bar}", "AXIS"),
        label=f"J3 bar ch{j:02d} radial (top-pin hinge)", verify=(bar, bar_tgt),
    )
    await coincident_mate(
        adapter,
        named_ref(f"MidWidth@{bar}", "PLANE"), named_ref(f"Front Plane@{rocker}", "PLANE"),
        label=f"J3 bar ch{j:02d} axial coincident mid-plane <- {rocker}",
        verify=(bar, bar_tgt),
    )
    await distance_driver(
        adapter,
        named_ref(f"Axis2@{bar}", "AXIS"), named_ref("Right Plane", "PLANE"),
        foot[0],
        label=f"J3 bar ch{j:02d} foot-X={foot[0]:.2f} (hard pin)",
        verify=(bar, bar_tgt),
    )
    dims += [0.0, 0.0, abs(foot[0])]

    # J5 foot-on-arc coupling: axis-axis distance at the as-solved radius.
    arc_c = world_point(adapter, rocker, [0.0, ARM_ARC_CENTER_LOCAL_Y, 0.0])
    foot_r = math.hypot(foot[0] - arc_c[0], foot[1] - arc_c[1])
    await distance_driver(
        adapter,
        named_ref(f"Axis2@{bar}", "AXIS"), named_ref(f"Axis3@{rocker}", "AXIS"),
        foot_r,
        label=f"J5 bar-foot on rocker arc ch{j:02d} r={foot_r:.2f}",
        verify=(bar, bar_tgt),
    )
    dims += [foot_r]

    comps = {"rocker-arm": rocker, "connecting-rod": rod,
             "amplitude-bar": bar, "channel-lever": lever}
    return comps, dims, time.perf_counter() - t0


async def _mate_count(adapter) -> int:
    res = await adapter.list_mates()
    return len(res.data or []) if res.is_success else -1


def _copy_slice(adapter, comps: dict[str, str], values_m: list[float],
                flip_dim: list[bool] | None = None) -> None:
    """One native-typed CopyWithMates2 of the whole 4-part slice.

    ``flip_dim`` carries the per-slot dimension SIDE. The UI doc ties the
    flip controls to the mate list and the API doc says FlipDimension
    "maps to the Values array" -- i.e. when a slot re-values a dim, the
    side must ride along; all-False hands every re-valued dim the False
    side regardless of what the seed authored (measured: the rod spin,
    authored flip=True, copied mirrored under all-False).
    """
    model = adapter.currentModel
    raw = []
    for part in CHAIN_PARTS:
        c = model.GetComponentByName(comps[part])
        if c is None:
            raise RuntimeError(f"slice component not found: {comps[part]!r}")
        raw.append(c._oleobj_)
    n = SLICE_MATES
    args = (
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, raw),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [True] * n),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [None] * n),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values_m),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL,
                list(flip_dim) if flip_dim is not None else [False] * n),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I4, [0] * n),
    )
    # Return value lies (False on success) -- caller judges from the model.
    # Span per the COM-operation invariant (AGENTS.md): the multi-second
    # copy+solve must not read as an unsegmented gap in the trace
    # (codex #220).
    with _telemetry.span("assembly.copy_with_mates",
                         components=len(raw), mates=n):
        adapter._attempt(lambda: model.CopyWithMates2(*args), default=None)


def _slice_transforms(
    adapter, exclude: set[str],
) -> dict[str, list[tuple[str, list[float]]]]:
    """(name, transform) of every chain-part instance NOT in ``exclude``."""
    out: dict[str, list[tuple[str, list[float]]]] = {p: [] for p in CHAIN_PARTS}
    for name in component_names(adapter):
        part = name.rsplit("-", 1)[0]
        if part in out and name not in exclude:
            out[part].append((name, component_transform(adapter, name)))
    return out


async def build(adapter) -> dict[str, str]:
    check("create_assembly", await adapter.create_assembly())
    await place_component(
        adapter, "pivot-shaft", [PIVOT[0], PIVOT[1], PIVOT_SHAFT_Z],
        [0.0, 0.0, 0.0], IDENTITY, ground=True, label="pivot-shaft (grounded)",
    )
    await place_component(
        adapter, "fulcrum-shaft", [FULCRUM[0], FULCRUM[1], 0.0],
        [0.0, 0.0, 0.0], IDENTITY, ground=True, label="fulcrum-shaft (grounded)",
    )
    # The anchor bushing in the gap below the seed channel, seated the
    # production way (concentric + Front-datum distance + anti-spin).
    z_gap = z_station(SEED_J) + ARM_MID_DZ - PITCH / 2.0
    bushing = await place_component(
        adapter, "pivot-bushing", [PIVOT[0], PIVOT[1], z_gap],
        [0.0, 0.0, 0.0], IDENTITY, ground=False,
        label=f"pivot-bushing gap {SEED_J - 1:02d}/{SEED_J:02d} (anchor)",
    )
    await _seat_bushing_on_shaft(
        adapter, bushing, PIVOT_OD_PT, (PIVOT[0], PIVOT[1]), PIVOT_BUSHING_OD / 2.0,
    )

    comps, dims, t_seed = await _seed_chain(adapter, SEED_J, bushing)
    log(f"seed chain ch{SEED_J:02d}: {SLICE_MATES} mates in {t_seed:.1f}s; "
        f"dims (mm) = {[round(d, 3) for d in dims]}")
    mates_before = await _mate_count(adapter)
    res = await adapter.list_mates()
    order = [(m["name"], m["type"]) for m in (res.data or [])]
    log(f"mate tree order ({len(order)}): {order}")

    seed_tf = {p: component_transform(adapter, comps[p]) for p in CHAIN_PARTS}
    seed_names = set(comps.values())

    seed_dim_rows = _dim_mates_with_owners(adapter)
    # The seed's authored FlipDimension per semantic dim. Documented as
    # IGNORED on the Repeat path (copies reset to False) -- still passed in
    # the arrays as evidence, and logged so a formulation that authored
    # True is visible.
    seed_flip_by_sem = {
        _SEM_BY_OWNERS[d["owners"]]: bool(d["flip"])
        for d in seed_dim_rows if d["owners"] in _SEM_BY_OWNERS
    }
    log(f"seed FlipDimension by dim: {seed_flip_by_sem}")

    # Values-slot mapping, RULE-BASED (the 2026-07-09 sentinel calibration
    # discovered the rule): slots enumerate the slice's EXTERNAL mates --
    # those referencing an entity outside the copied set -- in tree order
    # among themselves; internal mates are re-bound between the copies and
    # inherit their dims. Computed here from the seed's own mate list, so
    # the normal path needs NO calibration copy (the sentinel copy solves
    # at absurd 1000+mm dims -- a deliberate No-Solution flash in the UI,
    # Pedro flagged it -- so it is now the OPT-IN cross-check: pass
    # --calibrate to run it and assert it agrees with the rule).
    slice_instances = set(comps.values())
    external_rows = [
        r for r in _mates_with_owners(adapter)
        if (r["instances"] & slice_instances)
        and ("ROOT" in r["owners"] or (r["instances"] - slice_instances))
    ]
    slot_by_sem: dict[str, int] = {}
    for k, r in enumerate(external_rows):
        sem = _SEM_BY_OWNERS.get(r["owners"])
        if sem is not None:
            slot_by_sem[sem] = k
    log(f"rule-based slots: externals in tree order = "
        f"{[(r['name'], r['type']) for r in external_rows]} -> {slot_by_sem}")
    missing = _EXTERNAL_SEMS - set(slot_by_sem)
    if missing:
        # Raise (not return): run_build only maps exceptions to a non-zero
        # exit, and automation must not read a failed mapping as a passing
        # run (codex #220).
        raise RuntimeError(
            f"rule-based mapping missing external dims {sorted(missing)} -- "
            f"got {slot_by_sem}; cannot value the real copies")

    if "--calibrate" in sys.argv:
        # Empirical cross-check of the rule: one copy with a DISTINCT
        # sentinel per slot, each copied dim identified by its mated
        # components, the sentinel it holds -> its slot; then delete the
        # calibration copy and assert the discovered map equals the rule.
        sentinels = [1000.0 + 10.0 * k for k in range(SLICE_MATES)]
        dims_before = {d["name"] for d in seed_dim_rows}
        comps_before = set(component_names(adapter))
        _copy_slice(adapter, comps, [s / 1000.0 for s in sentinels])
        cal: dict[str, int] = {}
        for dm in _dim_mates_with_owners(adapter):
            if dm["name"] in dims_before:
                continue
            sem = _SEM_BY_OWNERS.get(dm["owners"])
            k = round((dm["mm"] - 1000.0) / 10.0)
            ok = 0 <= k < SLICE_MATES and abs(dm["mm"] - sentinels[k]) < 0.01
            log(f"calibration: {dm['name']} owners={sorted(dm['owners'])} "
                f"={dm['mm']:.2f}mm -> sem={sem} slot={k if ok else '??'}")
            if sem is not None and ok:
                cal[sem] = k
        for name in sorted(set(component_names(adapter)) - comps_before):
            check(f"remove calibration copy {name}",
                  await adapter.remove_component(
                      ComponentRefParameters(name=name)))
        if cal != slot_by_sem:
            raise RuntimeError(
                f"sentinel calibration disagrees with the rule-based "
                f"mapping: {cal} != {slot_by_sem}")
        log("sentinel calibration agrees with the rule-based mapping")

    pre_copy_mates = {r["name"] for r in _mates_with_owners(adapter)}

    # Real copies: station k = SEED_J + i; every dim gets its SEED value at
    # its DISCOVERED slot, with only the rocker axial substituted to
    # PITCH/2 + i*PITCH (always positive = the seed's side; C3). Each slot
    # also carries the seed's authored FlipDimension -- value and side ride
    # together (all-False mirrored the rod; if this lands clean, the
    # ModifyDefinition repair below becomes a no-op fallback).
    flips = [False] * SLICE_MATES
    for sem, k in slot_by_sem.items():
        flips[k] = seed_flip_by_sem.get(sem, False)
    log(f"per-slot FlipDimension for copies: "
        f"{ {k: flips[k] for _, k in slot_by_sem.items()} }")
    times = []
    for i in range(1, N_COPY_STATIONS + 1):
        values = [0.0] * SLICE_MATES
        for sem, k in slot_by_sem.items():
            values[k] = (PITCH / 2.0 + i * PITCH if sem == "J1a"
                         else dims[_DIMS_IDX_BY_SEM[sem]]) / 1000.0
        t0 = time.perf_counter()
        _copy_slice(adapter, comps, values, flip_dim=flips)
        times.append(time.perf_counter() - t0)
        log(f"slice copy -> ch{SEED_J + i:02d}: {times[-1]:.2f}s")

    want_mates = mates_before + SLICE_MATES * N_COPY_STATIONS

    # Evidence dump: every distance mate's ACTUAL dimension value + owners,
    # in tree order -- the direct record of what each copied dim holds.
    dist_dump = [
        f"{d['name']}[{'+'.join(sorted(d['owners']))}]={d['mm']:.3f}mm"
        for d in _dim_mates_with_owners(adapter)
    ]
    log(f"distance dims in tree order: {'; '.join(dist_dump)}")
    log(f"seed dims for reference (mm): {[round(d, 3) for d in dims]} "
        f"(per-copy axial -> {[round(PITCH / 2.0 + i * PITCH, 3) for i in range(1, N_COPY_STATIONS + 1)]})")

    def _measure(tag: str) -> tuple[list[str], set[str]]:
        """Judge poses: every copy must hold the seed's rotation + XY and
        sit at seed Z + i*PITCH, for ALL FOUR parts. Returns (failure
        descriptions, failing instance names)."""
        tfs = _slice_transforms(adapter, seed_names)
        fails: list[str] = []
        bad: set[str] = set()
        for part in CHAIN_PARTS:
            got = sorted(tfs[part], key=lambda nm: nm[1][11])
            want_zs = sorted(seed_tf[part][11] * 1000.0 + i * PITCH
                             for i in range(1, N_COPY_STATIONS + 1))
            if len(got) != N_COPY_STATIONS:
                fails.append(f"{part}: {len(got)} copies != {N_COPY_STATIONS}")
                continue
            worst_rot = worst_xy = worst_z = 0.0
            for (name, m), want_z in zip(got, want_zs):
                rot_d = max(abs(m[k] - seed_tf[part][k]) for k in range(9))
                xy_d = max(abs((m[9 + a] - seed_tf[part][9 + a]) * 1000.0)
                           for a in range(2))
                z_d = abs(m[11] * 1000.0 - want_z)
                worst_rot = max(worst_rot, rot_d)
                worst_xy = max(worst_xy, xy_d)
                worst_z = max(worst_z, z_d)
                # Copies re-run the mate SOLVE, so sub-visible solver
                # residual vs the seed pose is expected; only real drift (a
                # wrong branch, a mis-valued dim) fails. rot elements are
                # unitless direction cosines: 1e-4 ~ 0.006 deg.
                if rot_d > 1e-4 or xy_d > 0.05 or z_d > 0.05:
                    bad.add(name)
                    fails.append(
                        f"{name}@{m[11] * 1000.0:.3f}: rot_d={rot_d:.2e} "
                        f"xy_d={xy_d:.4f}mm z_d={z_d:.4f}mm (want z {want_z:.3f})"
                    )
            log(f"pose deltas {tag} {part}: rot {worst_rot:.2e}, "
                f"xy {worst_xy:.5f}mm, z {worst_z:.5f}mm")
        return fails, bad

    pose_fail, bad_instances = _measure("raw")

    # FLIP-REPAIR PASS. A copied distance dim can solve on the OTHER side
    # of its reference (measured: the rod's spin dim landed the ring at
    # +54.474 instead of -54.474 -- drift exactly 2x the dim, the same
    # 108.95 mm flip the deferred rod_swing replays hit). The mate carries
    # that side as ITS OWN FlipDimension state, which is why a
    # SetTransformAndSolve3 to the correct pose just snaps back (measured
    # twice). The fix edits the mate itself: IFeature::GetDefinition ->
    # IDistanceMateFeatureData.FlipDimension = not current ->
    # ModifyDefinition (the documented edit path). For each drifted copy,
    # toggle its external dims one at a time and keep what heals.
    t_fix = 0.0
    model = adapter.currentModel
    if pose_fail:
        log(f"raw poses off ({len(pose_fail)} checks; instances "
            f"{sorted(bad_instances)}) -- running the FlipDimension repair")
        t0 = time.perf_counter()
        for inst in sorted(bad_instances):
            cands = [
                d for d in _dim_mates_with_owners(adapter)
                if inst in d["instances"]
                and ("ROOT" in d["owners"]
                     or d["owners"] == frozenset({"rocker-arm", "pivot-bushing"}))
            ]
            for d in cands:
                feat = next(
                    (f for f in _mate_group_subfeatures(adapter)
                     if str(_read_member(f, "Name")) == d["name"]), None)
                if feat is None:
                    continue
                data = _read_member(feat, "GetDefinition")
                if data is None:
                    log(f"!! {d['name']}: GetDefinition returned None")
                    continue
                cur = bool(_read_member(data, "FlipDimension"))
                adapter._attempt(
                    lambda dd=data, c=cur: setattr(dd, "FlipDimension", not c))
                # The Component arg must be a typed dispatch-null: a bare
                # Python None marshals as VT_NULL and the call is rejected
                # (the documented OpenDoc6/CopyWithMates2 trap; measured
                # here as ModifyDefinition=False with no effect).
                null_comp = VARIANT(pythoncom.VT_DISPATCH, None)
                ok = adapter._attempt(
                    lambda f=feat, dd=data, nc=null_comp:
                        f.ModifyDefinition(dd, model, nc),
                    default=False)
                adapter._attempt(lambda: model.EditRebuild3(), default=None)
                m = component_transform(adapter, inst)
                p = inst.rsplit("-", 1)[0]
                # Healed = rotation + XY back at the seed's AND Z on one of
                # the expected stations: an axial-only drift keeps rot/XY
                # matching, so without the Z term the loop would accept the
                # first (wrong) candidate and never try the axial mate
                # (codex #220 round 3). Which station this instance owns is
                # settled by the aggregate re-measure after the loop.
                want_zs_inst = [seed_tf[p][11] * 1000.0 + i * PITCH
                                for i in range(1, N_COPY_STATIONS + 1)]
                healed = (
                    all(abs(m[k] - seed_tf[p][k]) < 1e-4 for k in range(9))
                    and all(abs((m[9 + a] - seed_tf[p][9 + a]) * 1000.0) < 0.05
                            for a in range(2))
                    and min(abs(m[11] * 1000.0 - w) for w in want_zs_inst) < 0.05
                )
                log(f"flip-repair {inst}: {d['name']} FlipDimension "
                    f"{cur} -> {not cur} (ModifyDefinition={ok}) -> "
                    f"{'HEALED' if healed else 'no change'}")
                if healed:
                    break
                # revert the unhelpful toggle
                adapter._attempt(
                    lambda dd=data, c=cur: setattr(dd, "FlipDimension", c))
                adapter._attempt(
                    lambda f=feat, dd=data, nc=null_comp:
                        f.ModifyDefinition(dd, model, nc),
                    default=False)
        t_fix = time.perf_counter() - t0
        pose_fail, bad_instances = _measure("repaired")

    # END-STATE VALIDATION (codex #220 rounds 2-5 converged here): every
    # mutation -- the copies and any flip repair -- is done, ONE closing
    # rebuild (asserted) solves the final assembly, and every invariant is
    # proven on that post-rebuild end state. The absolute pose measure
    # subsumes the earlier pre/post "stability" comparison (a snap-back or
    # dropped mate lands the copy off its seed pose or station), and
    # nothing mutates after these checks, so no invariant can be silently
    # invalidated by a later step.
    if not bool(adapter._attempt(lambda: model.EditRebuild3(), default=False)):
        raise RuntimeError(
            "closing EditRebuild3 failed -- end state unproven")
    # (1) Mate count, re-read POST-rebuild: a copied mate that the closing
    # solve dropped would keep the pre-rebuild count and evade the health
    # scan (which only sees mates that still exist).
    mates_final = await _mate_count(adapter)
    # (2) Absolute poses post-rebuild: seed rotation/XY + exact station Z
    # for every copy of all four parts.
    pose_fail, _ = _measure("final")
    # (3) Seed immutability: the production rework copies FROM a source
    # channel, so nothing in the copy/repair/rebuild workflow may perturb
    # the seed slice itself -- every other check excludes seed_names, so
    # drift of the SOURCE would otherwise pass silently.
    seed_drift = []
    for part, name in comps.items():
        m = component_transform(adapter, name)
        rot_d = max(abs(m[k] - seed_tf[part][k]) for k in range(9))
        xyz_d = max(abs((m[9 + a] - seed_tf[part][9 + a]) * 1000.0)
                    for a in range(3))
        if rot_d > 1e-6 or xyz_d > 1e-3:
            seed_drift.append(f"{name}: rot_d={rot_d:.2e} xyz_d={xyz_d:.4f}mm")
    log(f"seed slice: {'unmoved' if not seed_drift else 'MOVED -- ' + '; '.join(seed_drift)}")
    # (4) Copied-mate HEALTH: count and poses can hold while a copied mate
    # sits suppressed or in a hard error state (the park-replay corpse mode
    # _mate_hard_error documents). Scan every mate the real copies added.
    res = await adapter.list_mates()
    unhealthy = []
    for m in (res.data or []):
        if m["name"] in pre_copy_mates:
            continue
        code = _mate_hard_error(adapter, m["name"])
        if m.get("suppressed") or code:
            unhealthy.append(
                f"{m['name']} (suppressed={m.get('suppressed')}, err={code})")
    log(f"copied-mate health: "
        f"{'all clean' if not unhealthy else 'UNHEALTHY -- ' + '; '.join(unhealthy)}")

    log("=" * 70)
    log(f"mates (post-rebuild): {mates_before} -> {mates_final} (want "
        f"{want_mates}: +{SLICE_MATES}/copy x {N_COPY_STATIONS})")
    log(f"poses: {'ALL ON-STATION' if not pose_fail else 'FAIL -- ' + '; '.join(pose_fail)}")
    log(f"timing: seed chain {t_seed:.1f}s vs slice copy avg "
        f"{sum(times) / len(times):.2f}s (first {times[0]:.2f}s, last "
        f"{times[-1]:.2f}s) + repair pass {t_fix:.1f}s total")
    ok = ((mates_final == want_mates) and not pose_fail
          and not unhealthy and not seed_drift)
    if not ok:
        # Raise so the process exits non-zero -- a logged FAIL with exit 0
        # would let automation treat a failed validation as passing
        # (codex #220).
        raise RuntimeError(
            f"slice validation FAILED: mates {mates_final}/{want_mates}, "
            f"{len(pose_fail)} pose failures, "
            f"{len(unhealthy)} unhealthy copied mates, "
            f"{len(seed_drift)} seed drifts (see log)")
    log("VERDICT: PASS -- one call + flip repair replicates the whole chain")
    return {"verdict": "pass"}


if __name__ == "__main__":
    sys.exit(run_build(build))
