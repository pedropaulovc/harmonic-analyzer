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
DIST_IDX = 1  # the distance mate's position in the seed's mate order


async def _mate_count(adapter) -> int:
    res = await adapter.list_mates()
    return len(res.data or []) if res.is_success else -1


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
                     variant: str, flip_override: bool | None = None) -> bool:
    """One CopyWithMates2 call: repeat every mate, substitute the distance.

    Every array maps POSITIONALLY per seed mate, in the seed's mate order
    (measured 2026-07-09: the value placed at index 0 -- the concentric --
    was IGNORED and the distance mate copied with its index-1 entry 0.0,
    landing every copy at Z=0 exactly; the API doc says ``Values`` is
    "valid for distance, angle, and profile center mates only", i.e. the
    entry under a dimension-less mate is dead). The seat triple is
    concentric(0) / Front-plane distance(1) / Top-plane parallel(2), so the
    Z substitution rides index ``DIST_IDX = 1``. ``variant`` picks the
    marshaling: 'native' = every array in its native VT with raw
    ``_oleobj_`` component pointers (the PROVEN contract), 'list' /
    'variant' = the two known-broken encodings kept as regression probes.
    Returns the post-call bushing count -- the caller judges success from
    growth, never from CopyWithMates2's return value (it lies).
    """
    model = adapter.currentModel
    comp = model.GetComponentByName(comp_name)
    if comp is None:
        raise RuntimeError(f"seed component not found: {comp_name!r}")
    repeat = [True] * SEED_MATES
    # Values carry the POSITIVE magnitude (the seat authored abs(z), the
    # production distance_driver idiom). The SIDE is INHERITED from the
    # seed: Q5 measured FlipDimension as a NO-OP under Repeat=True (both
    # bits land a +20 target at -20, the seed's side), so the bit below is
    # kept only as the knob Q5 exercises -- never rely on it for side
    # selection.
    values = [0.0] * SEED_MATES
    values[DIST_IDX] = abs(new_z_mm) / 1000.0
    flip_align = [False] * SEED_MATES
    flip_dim = [False] * SEED_MATES
    flip_dim[DIST_IDX] = (new_z_mm >= 0.0 if flip_override is None
                          else flip_override)
    lock_rot = [False] * SEED_MATES
    orient = [0] * SEED_MATES

    if variant == "native":
        # The PROVEN contract (session 8640c77b, phase W): EVERY array in its
        # native VT with RAW `_oleobj_` component pointers -- VBA's exact wire
        # shape. pywin32's plain lists marshal as VT_VARIANT arrays, which SW
        # half-accepts: component copied, mates SILENTLY dropped.
        args = (
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH,
                    [comp._oleobj_]),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, repeat),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH,
                    [None] * SEED_MATES),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, flip_align),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, flip_dim),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, lock_rot),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I4, orient),
        )
    elif variant == "list":
        args = ([comp], repeat, [None] * SEED_MATES, values, flip_align,
                flip_dim, lock_rot, orient)
    else:
        args = (
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [comp]),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, repeat),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT,
                    [None] * SEED_MATES),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, values),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, flip_align),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, flip_dim),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, lock_rot),
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I4, orient),
        )
    # The return value LIES (False even when the copy lands mated -- measured
    # both ways on this seat), so success is judged by the caller from the
    # component count/transforms, never from this bool.
    adapter._attempt(lambda: model.CopyWithMates2(*args), default=None)
    n_bushings = sum(
        1 for n in component_names(adapter)
        if n.rsplit("-", 1)[0] == "pivot-bushing"
    )
    return n_bushings


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

    # Q1: marshaling. The 'native' shape is the proven contract; 'list' and
    # 'variant' stay as regression probes for the two known-broken encodings.
    # Success = the bushing count GREW (the returned bool lies), and a failed
    # shape only condemns THAT shape -- never the API (a working positive
    # control exists: the UI command and the in-process VBA twin both copy;
    # see memory/negative-result-positive-control.md).
    n_before = len(_bushing_zs(adapter))
    variant = None
    for shape in ("native", "list", "variant"):
        try:
            n_now = _copy_with_mates(adapter, seed, GAP_Z[2], shape)
        except Exception as exc:  # noqa: BLE001 -- probe reports, never hides
            log(f"!! {shape} marshaling raised: {exc}")
            continue
        copied = n_now > n_before
        log(f"CopyWithMates2 ({shape}): bushings {n_before} -> {n_now} "
            f"({'copy created' if copied else 'no copy'})")
        if copied:
            variant = shape
            break
    if variant is None:
        log("Q1 verdict: no copy under the shapes tried (native/list/"
            "variant) -- a marshaling regression, NOT proof the API is "
            "unusable; re-derive the wire shape against the VBA positive "
            "control before concluding anything")
        return {"verdict": "no-copy-under-tried-shapes"}

    # Q3: timed copies across gaps 3..N -- population grows each call.
    times = []
    for k in range(3, 3 + N_COPIES - 1):
        t0 = time.perf_counter()
        n_now = _copy_with_mates(adapter, seed, GAP_Z[k], variant)
        dt = time.perf_counter() - t0
        times.append(dt)
        log(f"copy -> gap {k}: bushings={n_now} {dt:.2f}s")

    # Q2: real mates + correct stations, judged from the model. A copy
    # inherits the SEED'S SIDE of the anchor plane (Q5: FlipDimension is a
    # no-op under Repeat=True), so the expected station for a copy is
    # -abs(target): the seed sits on the negative side, and the one ladder
    # target crossing zero (+0.737) legitimately lands mirrored. Production
    # must therefore anchor re-valued distances so every station shares the
    # seed's side (e.g. the neighbour-bushing anchor, PITCH/2 + k*PITCH).
    mates_after = await _mate_count(adapter)
    zs = _bushing_zs(adapter)
    expected = sorted([GAP_Z[0], GAP_Z[1]]
                      + [-abs(GAP_Z[k]) for k in range(2, 2 + N_COPIES)])
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

    # Q5: FlipDimension semantics. The 2026-07-09 ladder landed 9/10 stations
    # exactly; the one target CROSSING ZERO (+0.737) landed mirrored (-0.737)
    # despite flip_dim=True -- so "true for a positive distance dimension"
    # (the doc's wording) is NOT world-side-absolute. Pin it: copy the seed
    # (at Z=-62.77) to an unambiguous +20 mm target under both flip bits and
    # read where each lands. (Runs AFTER Q2 so the +/-20 landings don't
    # pollute the station comparison.)
    for flip in (False, True):
        before = set(component_names(adapter))
        _copy_with_mates(adapter, seed, 20.0, variant, flip_override=flip)
        new = [n for n in component_names(adapter) if n not in before]
        landed = [round(component_transform(adapter, n)[11] * 1000.0, 3)
                  for n in new]
        log(f"Q5 flip={flip}: target +20.0 -> landed {landed}")
    return {"verdict": "ran", "on_plane": str(on_plane)}


if __name__ == "__main__":
    sys.exit(run_build(build))
