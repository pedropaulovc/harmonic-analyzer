---
name: drawing-fleet-timings-drift
description: "Drawing-build wall clock varied −30% to +21% fleet-wide (−98% to +61% per drawing) with no code change — single-run A/B fleet timings prove nothing; span counts are the best evidence but only after excluding _exec_com retries"
metadata:
  node_type: memory
  type: project
---

Measured 2026-07-28 across six full cache-cold 93-drawing fleet builds (cache
off, parts/assemblies from cache, `doit drawing` serial, three branches).

Running the **same code** twice back-to-back gave fleet totals differing by tens
of percent, **in both directions**:

| branch | pass 1 | pass 2 | delta | per-drawing |
|---|---|---|---|---|
| `main` @ 26f419a9 | 2995 s | 3227 s | +7.7% | — |
| PR #436 | 3830 s | 4629 s | **+20.9%** | 93 slower / 0 faster |
| PR #437 | 4573 s | 3186 s | **−30.3%** | 57 slower / 36 faster |

Per-drawing extremes on identical code: `swing_stop_screw` −97.7%,
`hanger_screw` −60.3%, `pen_assembly` +61.2%, `channel_assembly` +28.6%.

## What this does NOT establish

**The cause is unidentified.** The #436 pair was monotonic (all 93 slower),
which looks like session age; the #437 pair was faster and mixed. That rules out
**session age as a monotonic sole explanation** — no more than that. Machine
load, GDI pressure and OS cache state differed between passes and were not
measured, so a session-age *contribution* is still entirely possible. Do not use
this note to justify ignoring session state.

Rule out first, per [[build-gdi-session-accumulation]] — whose SECOND failure
mode is precisely a progressive per-operation slowdown that is explicitly *not*
session age and is *not* fixed by restarting SolidWorks:
- **runaway `TextInputHost.exe`** — checked here and **ruled out**: 62 CPU-seconds
  over two days, against 33,605 s in the documented incident.
- GDI handle count, per-process CPU rate, other machine load. Not measured here.

**No bound.** Two consecutive passes establish neither a ceiling nor what a
third or fourth pass does. "±30%" is what happened to be observed, not a
threshold above which a result becomes trustworthy.

## How to apply

- **A single A/B fleet pair proves nothing**, at any effect size. Every perf
  claim in the abandoned #382-#391 stack was exactly that: 1.24% (#389), 5.7%
  (#384), 12.84% (#388). #436 removed one of two reopens per drawing and the
  fleet total reported it as *slower*.
- **Span COUNTS are the strongest evidence — with one caveat.** `reopen saved
  drawing` 186 -> 93 is a fact no timing variance touches. But `dodo._exec_com`
  **retries the whole COM subprocess** (up to `len(_COM_RETRY_BACKOFF_S)`, with
  SolidWorks recovery between attempts) and telemetry from the failed attempt is
  preserved, so a retried task double-counts spans. Verify no retries occurred,
  or group by attempt and count only the successful one.
- **Span DURATIONS are NOT drift-resistant.** They inflate with whatever causes
  the drift; [[build-gdi-session-accumulation]]'s own recipe detects that
  slowdown by watching identical labelled mate spans go 4.7 s -> 35.5 s. So
  `drawing.reopen` at 4.2 s is *indicative* of #436's saving, not proof.
- **If you must benchmark:** multiple independently-reset, counterbalanced
  (AB/BA) blocks, and report the spread across blocks. One AB/BA block removes
  order bias but gives only two observations per arm, which cannot show the
  effect exceeds an unbounded variance. Restarting only between arms makes arm A
  aged and arm B fresh; plain ABAB leaves B later than A in every pair.
- **Outlier detection needs a like-for-like baseline, not the fleet mean.** The
  fleet is heterogeneous: `drive_train_assembly` builds seven sheets while most
  assembly drawings build one or two, so a large total can be entirely
  legitimate work. Compare **the same drawing and the same span labels across
  runs**, or normalize by expected work. drive_train was worth investigating
  because its own `drawing.isolate_balloon_components` span was 317 s of its
  583 s — a within-drawing breakdown — not because 583 s exceeded a 32 s mean.
