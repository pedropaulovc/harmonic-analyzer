---
name: drawing-fleet-timings-drift
description: "Drawing-build wall clock varies wildly run to run (−30% to +21% fleet-wide, −98% to +61% per drawing) with no code change — single-run A/B fleet timings are unusable; compare span counts/durations instead"
metadata:
  node_type: memory
  type: project
---

Measured 2026-07-28 across six full cache-cold 93-drawing fleet builds (cache
off, parts/assemblies from cache, `doit drawing` serial, three branches).

Running the **same code** twice back-to-back gives fleet totals that differ by
tens of percent, **in both directions**:

| branch | pass 1 | pass 2 | delta | per-drawing direction |
|---|---|---|---|---|
| `main` @ 26f419a9 | 2995 s | 3227 s | +7.7% | — |
| PR #436 | 3830 s | 4629 s | **+20.9%** | 93 slower / 0 faster |
| PR #437 | 4573 s | 3186 s | **−30.3%** | 57 slower / 36 faster |

Per-drawing extremes on identical code: `swing_stop_screw` −97.7%,
`hanger_screw` −60.3%, `pen_assembly` +61.2%, `channel_assembly` +28.6%.

**Do not read a mechanism into this.** The #436 pair was perfectly monotonic
(every one of 93 drawings slower), which looks like session-age degradation —
but the #437 pair went the other way and was mixed, which falsifies that.
Whatever drives it (machine load, OS file cache, SolidWorks internal state), it
is not a clean function of session age, and the −97.7% outlier is extreme
enough that it probably is not a "speedup" at all. This memory records the
*variance*, not an explanation.

**Why it matters:** single-run A/B fleet comparisons are unusable below roughly
30%. Every perf claim in the abandoned #382-#391 stack was exactly that — one
"paired fleet measurement" — at 1.24% (#389), 5.7% (#384) and 12.84% (#388),
all far inside the noise. #436 removed one of two reopens per drawing and the
fleet total reported it as **slower**.

**How to apply:**
- Never claim a drawing perf win from one A/B fleet pair. Repeat the arms, or
  don't make the claim.
- Prefer **span-level** evidence, which survives this: a count (`reopen saved
  drawing` 186 -> 93) or one named span's own duration. With #437's spans in
  place `drawing.reopen` measures 393.9 s over 93 drawings (4.2 s mean, 10.4 s
  max), so #436's saving is ~394 s / ~13% of baseline — a number the fleet
  total could never have produced. See [[otel-trace-local-viewing]].
- Absolute costs from one run are still fine for finding **outliers**:
  drive_train at 583 s against a 32 s fleet mean is far outside any noise band
  (see [[drawing-recipe-com-pitfalls]] and issue #438).
- Distinct from [[build-gdi-session-accumulation]], which is GDI exhaustion
  inside one large *assembly* build; this is ~93 short drawing subprocesses
  against one long-lived `SLDWORKS.exe`.
