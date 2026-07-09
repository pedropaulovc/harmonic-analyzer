r"""Empirical probe: can ``IAssemblyDoc::CopyWithMates2`` replicate a mated
component per channel station -- and is it faster than authoring the mates?

Motivation (user pointer, 2026-07-09): SolidWorks supports component copies
that CARRY their mates (the fastener "pattern-driven mates" workflow). The
channel assembly authors ~450 mates one CreateMate+EditRebuild3 at a time,
and at the neutral preset channel j's chain differs from channel 0's ONLY in
its Front-plane Z-station distance -- exactly what ``CopyWithMates2``'s
``Repeat``/``Values`` arrays substitute per copy. If one call replicates a
component + its 3 mates (with real, independent copies of the mates), the
20-channel fan-out could collapse from ~9 authored mates/channel to one
CopyWithMates2 call per channel.

Questions this probe answers (transform-judged, never read-backs):
  Q1  does CopyWithMates2 work at all under pywin32 late binding (array
      marshaling: components as VT_DISPATCH array, per-mate bool/double
      arrays)?
  Q2  do the copies land at the substituted Z station, with REAL new mates
      (mate count grows by the seed's mate count per copy)?
  Q3  wall time per copy vs the production 3-mate ``_seat_bushing_on_shaft``
      path; does per-copy cost also grow with population?
  Q4  does the copy read the same constraint status as its hand-mated twin?

Method (fresh throwaway assembly, NEVER saved): grounded pivot-shaft; seat
bushing #0 at gap 0 via the production path (timed baseline); seat bushing #1
at gap 1 the same way (second baseline, population-matched); then
CopyWithMates2 bushing #0 -> gaps 2..9, Repeat=[True]*3 with the distance
mate's ``Values`` entry set per gap, timing each call. pywin32 marshaling is
attempted with plain lists first, then explicit VARIANT arrays -- both
outcomes are logged (the GetWhatsWrong byref lesson).

Run (SolidWorks open, seat free; ~5-10 min)::

    uv run python cad\scripts\diagnostics\diag_copy_with_mates.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

import pythoncom  # noqa: E402
from win32com.client import VARIANT  # noqa: E402

from _common import check, log, run_build  # noqa: E402
from _assembly import (  # noqa: E402
    component_names,
    component_transform,
    place_component,
)
from build_channel_assembly import (  # noqa: E402
    ARM_MID_DZ,
    IDENTITY,
    PITCH,
    PIVOT,
    PIVOT_BUSHING_OD,
    PIVOT_SHAFT_Z,
    SHAFT_R,
    _seat_bushing_on_shaft,
    z_station,
)

N_COPIES = 8
GAP_Z = [z_station(j) + ARM_MID_DZ - PITCH / 2.0 for j in range(1, 12)]
PIVOT_OD_PT = [PIVOT[0] + SHAFT_R, PIVOT[1], 0.0]
SEED_MATES = 3  # concentric + Front-plane distance + Top-plane parallel


async def _mate_count(adapter) -> int:
    res = await adapter.list_mates()
    return len(res.data or []) if res.success else -1


async def _seat_baseline(adapter, gap: int) -> tuple[str, float]:
    """Production path: place + 3 mates. Returns (name, seconds)."""
    z = GAP_Z[gap]
    t0 = time.perf_counter()
    comp = await place_component(
        adapter, "pivot-bushing", [PIVOT[0], PIVOT[1], z],
        [0.0, 0.0, 0.0], IDENTITY, ground=False, label=f"baseline bushing gap{gap}",
    )
    await _seat_bushing_on_shaft(
        adapter, comp, PIVOT_OD_PT, (PIVOT[0], PIVOT[1]), PIVOT_BUSHING_OD / 2.0,
    )
    return comp, time.perf_counter() - t0


def _copy_with_mates(adapter, comp_name: str, new_z_mm: float,
                     variant: str) -> bool:
    """One CopyWithMates2 call: repeat every mate, substitute the distance.

    ``Values`` maps to the seed's distance/angle mates; the seat triple has
    exactly ONE (the Front-plane Z distance), so a single entry re-stations
    the copy. ``variant`` picks the marshaling: 'list' = plain Python lists
    (pywin32 auto-marshal), 'variant' = explicit VARIANT arrays.
    """
    model = adapter.currentModel
    comp = model.GetComponentByName(comp_name)
    if comp is None:
        raise RuntimeError(f"seed component not found: {comp_name!r}")
    repeat = [True] * SEED_MATES
    new_refs = [None] * SEED_MATES
    values = [new_z_mm / 1000.0]  # metres; maps to the ONE distance mate
    flip_align = [False] * SEED_MATES
    flip_dim = [True]  # positive dimension, matches the seat's abs(z) authoring
    lock_rot = [False] * SEED_MATES
    orient = [0]

    if variant == "list":
        args = ([comp], repeat, new_refs, values, flip_align, flip_dim,
                lock_rot, orient)
    else:
        args = (
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [comp]),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, repeat),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, new_refs),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, flip_align),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, flip_dim),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, lock_rot),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I4, orient),
        )
    ok = adapter._attempt(lambda: model.CopyWithMates2(*args), default=None)
    return bool(ok)


def _bushing_zs(adapter) -> list[float]:
    return sorted(
        component_transform(adapter, n)[11] * 1000.0
        for n in component_names(adapter)
        if n.rsplit("-", 1)[0] == "pivot-bushing"
    )


async def build(adapter) -> dict[str, str]:
    check("create_assembly", await adapter.create_assembly())
    await place_component(
        adapter, "pivot-shaft", [PIVOT[0], PIVOT[1], PIVOT_SHAFT_Z],
        [0.0, 0.0, 0.0], IDENTITY, ground=True, label="pivot-shaft (grounded)",
    )

    seed, t_seed = await _seat_baseline(adapter, 0)
    _, t_base2 = await _seat_baseline(adapter, 1)
    log(f"baseline production seat: {t_seed:.2f}s / {t_base2:.2f}s per bushing")
    mates_before = await _mate_count(adapter)

    # Q1: marshaling. Try plain lists once; on failure retry VARIANT arrays.
    variant = "list"
    ok = False
    try:
        ok = _copy_with_mates(adapter, seed, GAP_Z[2], variant)
    except Exception as exc:  # noqa: BLE001 -- probe reports, never hides
        log(f"!! list marshaling raised: {exc}")
    if not ok:
        variant = "variant"
        ok = _copy_with_mates(adapter, seed, GAP_Z[2], variant)
    log(f"CopyWithMates2 first call: ok={ok} (marshaling={variant})")
    if not ok:
        log("Q1 verdict: CopyWithMates2 UNUSABLE under pywin32 -- both "
            "marshaling variants failed; history's manual path stands")
        return {"verdict": "unusable"}

    # Q3: timed copies across gaps 3..N -- population grows each call.
    times = []
    for k in range(3, 3 + N_COPIES - 1):
        t0 = time.perf_counter()
        okk = _copy_with_mates(adapter, seed, GAP_Z[k], variant)
        dt = time.perf_counter() - t0
        times.append(dt)
        log(f"copy -> gap {k}: ok={okk} {dt:.2f}s")

    # Q2: real mates + correct stations, judged from the model.
    mates_after = await _mate_count(adapter)
    zs = _bushing_zs(adapter)
    expected = sorted(GAP_Z[k] for k in range(2 + N_COPIES))
    on_plane = (
        len(zs) == len(expected)
        and all(abs(g - w) < 0.05 for g, w in zip(zs, expected))
    )
    log("=" * 70)
    log(f"mate count: {mates_before} -> {mates_after} "
        f"(expected +{SEED_MATES * N_COPIES} if copies carry REAL mates)")
    log(f"stations: {'ON-PLANE' if on_plane else 'OFF -- ' + str(zs)}")
    log(f"timing: production seat ~{(t_seed + t_base2) / 2:.2f}s vs "
        f"CopyWithMates2 avg {sum(times) / len(times):.2f}s "
        f"(first {times[0]:.2f}s, last {times[-1]:.2f}s -- growth says "
        f"whether the copy also pays the population tax)")
    return {"verdict": "ran", "on_plane": str(on_plane)}


if __name__ == "__main__":
    sys.exit(run_build(build))
