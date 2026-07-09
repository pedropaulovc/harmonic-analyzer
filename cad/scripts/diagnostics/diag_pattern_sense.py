r"""Empirical revalidation of the LocalLinearPattern retirement claims (#8 era).

History under test (build_channel_assembly.py:1030 comment + the #8 memory):

  H1  the pattern direction sense, taken from the pivot shaft's cylindrical
      face, resolves unreliably at 20 channels (clean at 3) -- flips are real
      and scale-dependent;
  H2  the sense is NONDETERMINISTIC (varies across identical trials);
  H3  "the API exposes no sense override" -- contradicted on paper by BOTH
      ``FeatureLinearPattern5``'s ``FlipDir1`` argument (the adapter hard-codes
      it ``False``) and ``ILocalLinearPatternFeatureData.D1ReverseDirection``.

Method: one fresh throwaway assembly per trial (NEVER saved): grounded
pivot-shaft, one pivot-bushing seed at the top inter-channel gap, then the
retired production call verbatim -- ``pattern_components_linear`` with
``direction_point`` on the shaft OD (the historic face pick). The judge is the
instances' origin Z read back via ``component_transform`` -- NEVER a property
read-back (belt/chain lesson: definition getters lie). Trials: R reps for each
N in {3, 20}; then the ``FlipDir1=True`` raw-COM variant; then the
``D1ReverseDirection`` definition rewrite on a live pattern.

Verdicts printed at the end:
  * flip rate per (N, variant) -> H1/H2 confirmed or refuted;
  * whether FlipDir1 / D1ReverseDirection actually MOVE instances -> H3.

Run (SolidWorks open, seat free; ~10-20 min)::

    uv run python cad\scripts\diagnostics\diag_pattern_sense.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _common import check, log, run_build  # noqa: E402
from _assembly import (  # noqa: E402
    component_names,
    component_transform,
    place_component,
)
from build_channel_assembly import (  # noqa: E402
    ARM_MID_DZ,
    CHANNELS,
    IDENTITY,
    PITCH,
    PIVOT,
    PIVOT_SHAFT_Z,
    SHAFT_R,
    z_station,
)
from solidworks_mcp.adapters.base import (  # noqa: E402
    AdapterResultStatus,
    ComponentLinearPatternParameters,
)
from solidworks_mcp.adapters.solidworks import assembly as _sw_asm  # noqa: E402
from solidworks_mcp.adapters.solidworks import features as _sw_feat  # noqa: E402

REPS = 5  # trials per (count, variant) cell
SEED_TOL = 0.5  # mm; Z classification slack

# Top inter-channel gap: where the retired code seeded the bank (old
# build_channel_assembly z_gap_top = z_mid(top) - PITCH/2).
Z_TOP_GAP = z_station(CHANNELS - 1) + ARM_MID_DZ - PITCH / 2.0
PIVOT_OD_PT = [PIVOT[0] + SHAFT_R, PIVOT[1], 0.0]  # historic face pick


def _bushing_zs(adapter) -> list[float]:
    return sorted(
        component_transform(adapter, n)[11] * 1000.0
        for n in component_names(adapter)
        if n.rsplit("-", 1)[0] == "pivot-bushing"
    )


def _classify(zs: list[float], n: int) -> str:
    """Classify the pattern sense from instance origins.

    'down' = copies filled toward channel 0 (-Z of the seed; the intended
    sense), 'up' = flipped (+Z), anything else = 'other' (count mismatch or
    off-plane instances).
    """
    if len(zs) != n:
        return f"other(count={len(zs)})"
    lo, hi = zs[0], zs[-1]
    span = PITCH * (n - 1)
    if abs(hi - Z_TOP_GAP) < SEED_TOL and abs((hi - lo) - span) < SEED_TOL:
        return "down"
    if abs(lo - Z_TOP_GAP) < SEED_TOL and abs((hi - lo) - span) < SEED_TOL:
        return "up"
    return f"other(z {lo:.1f}..{hi:.1f})"


async def _fresh_rig(adapter) -> str:
    """New throwaway assembly: grounded shaft + one bushing seed. Never saved."""
    check("create_assembly", await adapter.create_assembly())
    await place_component(
        adapter, "pivot-shaft", [PIVOT[0], PIVOT[1], PIVOT_SHAFT_Z],
        [0.0, 0.0, 0.0], IDENTITY, ground=True, label="pivot-shaft (grounded)",
    )
    return await place_component(
        adapter, "pivot-bushing", [PIVOT[0], PIVOT[1], Z_TOP_GAP],
        [0.0, 0.0, 0.0], IDENTITY, ground=True, label="pivot-bushing seed",
    )


async def _pattern_adapter(adapter, seed: str, n: int):
    """The retired production call, verbatim (FlipDir1 False inside)."""
    return await adapter.pattern_components_linear(
        ComponentLinearPatternParameters(
            components=[seed], count=n, spacing=PITCH,
            direction_point=PIVOT_OD_PT,
        )
    )


def _pattern_raw_flip(adapter, seed: str, n: int):
    """FeatureLinearPattern5 with FlipDir1=True -- the creation-time override
    the adapter never exposed. Mirrors _pattern_components_linear_impl."""
    model = adapter.currentModel
    _sw_asm._select_pattern_components(adapter, [seed])
    direction_type = _sw_feat._select_reference_point(
        adapter, PIVOT_OD_PT, 2, ("EDGE", "AXIS", "FACE"))
    if direction_type is None:
        raise RuntimeError(f"direction pick failed at {PIVOT_OD_PT}")
    fm = model.FeatureManager
    _sw_asm._flag_feature_methods(fm, "IFeatureManager")
    names_before = _sw_feat._feature_names(adapter)
    feature = fm.FeatureLinearPattern5(
        int(n), float(PITCH) / 1000.0, 1, 0.0,
        True,   # FlipDir1  <-- the ONLY change vs the adapter
        False, "", "", False, False, False, False, True, True,
        False, False, False, False, 0.0, 0.0, False, False,
    )
    return _sw_feat._resolve_feature(adapter, feature, names_before)


def _try_reverse_direction(adapter, pattern_name: str) -> str:
    """Attempt the post-create D1ReverseDirection rewrite; judge by TRANSFORMS.

    Returns 'moved', 'inert' or 'failed(<why>)'. Property read-backs are not
    trusted -- only a real instance-Z change counts (belt/chain lesson)."""
    model = adapter.currentModel
    before = _bushing_zs(adapter)
    feat = adapter._attempt(lambda: model.FeatureByName(pattern_name), default=None)
    if feat is None:
        return "failed(FeatureByName None)"
    defn = adapter._attempt(lambda: feat.GetDefinition(), default=None)
    if defn is None:
        return "failed(GetDefinition None -- late-binding, cf. chain pattern)"
    ok = adapter._attempt(lambda: defn.AccessSelections(model, None), default=None)
    log(f"    AccessSelections -> {ok!r}")
    try:
        defn.D1ReverseDirection = True
    except Exception as exc:  # noqa: BLE001 -- probe reports, never hides
        adapter._attempt(lambda: defn.ReleaseSelectionAccess(), default=None)
        return f"failed(set: {exc})"
    done = adapter._attempt(lambda: feat.ModifyDefinition(defn, model, None), default=None)
    log(f"    ModifyDefinition -> {done!r}")
    adapter._attempt(lambda: model.EditRebuild3())
    after = _bushing_zs(adapter)
    moved = max(abs(a - b) for a, b in zip(after, before)) if before and len(after) == len(before) else -1.0
    return "moved" if moved > SEED_TOL else f"inert(max dz {moved:.3f})"


async def build(adapter) -> dict[str, str]:
    results: list[tuple[str, int, int, str]] = []  # (variant, n, rep, sense)

    # --- H1/H2: historic adapter call, face-point direction ------------------
    for n in (3, CHANNELS):
        for rep in range(REPS):
            seed = await _fresh_rig(adapter)
            res = await _pattern_adapter(adapter, seed, n)
            if res.status != AdapterResultStatus.SUCCESS:
                results.append(("face", n, rep, f"error({res.error})"))
                continue
            sense = _classify(_bushing_zs(adapter), n)
            results.append(("face", n, rep, sense))
            log(f"face n={n} rep={rep}: {sense}")

    # --- H3a: creation-time FlipDir1=True ------------------------------------
    for rep in range(REPS):
        seed = await _fresh_rig(adapter)
        try:
            feat = _pattern_raw_flip(adapter, seed, CHANNELS)
            sense = _classify(_bushing_zs(adapter), CHANNELS)
            results.append(("flipdir1", CHANNELS, rep, sense))
            log(f"flipdir1 n={CHANNELS} rep={rep}: {sense} (feature={feat!r})")
        except Exception as exc:  # noqa: BLE001
            results.append(("flipdir1", CHANNELS, rep, f"error({exc})"))

    # --- H3b: post-create D1ReverseDirection on a live pattern ---------------
    seed = await _fresh_rig(adapter)
    res = await _pattern_adapter(adapter, seed, CHANNELS)
    if res.status == AdapterResultStatus.SUCCESS:
        pattern_name = getattr(res.data, "name", "") or "LocalLPattern1"
        verdict = _try_reverse_direction(adapter, pattern_name)
        results.append(("d1reverse", CHANNELS, 0, verdict))
        log(f"d1reverse: {verdict}")

    # --- summary --------------------------------------------------------------
    log("=" * 70)
    for variant, n in (("face", 3), ("face", CHANNELS), ("flipdir1", CHANNELS)):
        cell = [r[3] for r in results if r[0] == variant and r[1] == n]
        if not cell:
            continue
        down = sum(1 for s in cell if s == "down")
        up = sum(1 for s in cell if s == "up")
        log(f"{variant} n={n}: down={down} up={up} other={len(cell)-down-up} of {len(cell)}")
    d1 = [r[3] for r in results if r[0] == "d1reverse"]
    if d1:
        log(f"d1reverse override: {d1[0]}")
    log("H1 (flips at 20, clean at 3): "
        + ("CONFIRMED" if any(r[3] == "up" for r in results if r[0] == "face" and r[1] == CHANNELS)
           and all(r[3] == "down" for r in results if r[0] == "face" and r[1] == 3)
           else "NOT REPRODUCED -- history in doubt"))
    log("H2 (nondeterministic): "
        + ("CONFIRMED" if len({r[3] for r in results if r[0] == "face" and r[1] == CHANNELS}) > 1
           else "NOT REPRODUCED (sense was consistent across reps)"))
    return {"trials": str(len(results))}


if __name__ == "__main__":
    sys.exit(run_build(build))
