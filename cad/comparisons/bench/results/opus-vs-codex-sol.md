# Opus-high vs codex-sol — T1 pose read (PARTIAL)

> [!WARNING]
> **INCOMPLETE RESULTS.** The Opus run was stopped by quota exhaustion partway
> through the T1 screening pass. Only **912 / 1782** T1 cells completed (~51%),
> at **N = 1**, and **T3 and T2 never ran for Opus**. This is a directional
> T1-only snapshot, not a decision-rule verdict. codex-sol (gpt-5.6-sol) ran the
> full grid (5346 cells, N = 3); it is down-sampled here to match Opus.

## Method (fair, apples-to-apples)

Both models scored on the **identical 912 (case_id, arm) cells** Opus completed,
with codex-sol restricted to `repeat == 0` so both are N = 1 on the same cells,
run through the same deterministic scorer (`report.macro_sign_accuracy`, macro
over {−, 0, +} per parameter class). The per-cell comparison is exact;
generalization to the full 1782-cell grid is unproven.

## T1 macro sign accuracy (matched cells)

| arm | Opus % | codex-sol % | Δ (opus − csol) |
|---|--:|--:|--:|
| P5 blend-subtle | 84.6 | 83.7 | **+0.8** |
| P3 sbs + grid | 83.5 | 86.7 | −3.2 |
| P10 flicker | 83.1 | 86.1 | −3.0 |
| P8 diff-heatmap | 82.6 | 84.8 | −2.2 |
| P9 edge-overlay | 80.8 | 85.4 | −4.5 |
| P1 blend-red (incumbent) | 80.2 | 84.8 | −4.6 |
| P4 onion | 80.0 | 84.2 | −4.2 |
| P11 dashboard | 79.9 | 88.0 | −8.1 |
| P2 side-by-side | 79.5 | 92.0 | −12.4 |
| P7 green-magenta | 79.5 | 82.9 | −3.4 |
| P6 checkerboard | 77.5 | 84.4 | −6.8 |
| **pooled** | **81.0** | **85.7** | **−4.7** |

## Per-parameter macro sign % (pooled, matched cells)

| param | Opus | codex-sol | diff |
|---|--:|--:|--:|
| az | 80 | 83 | −2 |
| el | 82 | 84 | −2 |
| roll | 83 | 88 | −5 |
| target_x | 80 | 89 | **−9** |
| target_y | 80 | 83 | −3 |
| zoom | 80 | 87 | **−7** |

## Takeaways (provisional)

- **codex-sol leads overall (85.7 vs 81.0) and on 10 of 11 arms.** Opus only
  edges P5 (+0.8, within noise). Consistent gap, not marginal.
- **Opus's weakness is concentrated in translation-x, zoom, and roll direction**
  (−9 / −7 / −5). It reads camera rotation (az/el) nearly as well as codex-sol
  (−2 each) — the classic target-shift-vs-orbit degeneracy hurts it more.
- **Cost trade, not a strict loss.** codex-sol spent ~12,300 median tokens/cell;
  Opus-high spent ~800–2,600 — roughly 5–10× cheaper per decision for ~5 points
  less accuracy.
- **The winning arm flips between subjects** (Opus → P5; codex-sol → P2, which is
  Opus's *worst* arm). The benchmark mandates reporting this rather than
  averaging it away — and it is unresolved here because Opus's grid is partial
  and CIs overlap.

## To complete

Re-run the Opus driver when quota resets (resumable — skips the 912 done cells,
retries the rest, then runs T3 → T2). A full-grid, N = 3, T1+T3+T2 Opus pass is
required before the decision rule can be applied.
