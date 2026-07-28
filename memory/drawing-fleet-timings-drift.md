---
name: drawing-fleet-timings-drift
description: "Drawing-build wall clock varied −30% to +21% fleet-wide (−98% to +61% per drawing) with no code change — single-run A/B fleet timings prove nothing, and span DURATIONS are not a safe fallback; only span COUNTS are"
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

**No mechanism.** The #436 pair was perfectly monotonic (all 93 slower), which
looks like session-age degradation; the #437 pair went the other way and was
mixed, which falsifies that. This memory records the *variance*, not a cause.

Candidates to rule out before blaming session age, per
[[build-gdi-session-accumulation]] — whose SECOND failure mode is precisely a
progressive per-operation slowdown, and explicitly is *not* session age and is
*not* fixed by restarting SolidWorks:
- **runaway `TextInputHost.exe`** — checked here and **ruled out**: 62 CPU-seconds
  accumulated over two days, against 33,605 s in the documented incident.
- GDI handle pressure, other machine load, OS file cache state. None were
  measured, so the cause remains **unidentified**.

**No bound.** Two consecutive passes establish neither a ceiling nor what a
third or fourth pass does. Do not read "±30%" as a threshold above which a
result is trustworthy — it is the spread that happened to be observed, nothing
more.

## How to apply

- **A single A/B fleet pair proves nothing**, at any effect size. Every perf
  claim in the abandoned #382-#391 stack was exactly that: 1.24% (#389), 5.7%
  (#384), 12.84% (#388). #436 removed one of two reopens per drawing and the
  fleet total reported it as *slower*.
- **Prefer span COUNTS, which are inherently drift-immune** — `reopen saved
  drawing` 186 -> 93 across the fleet is a fact no timing variance can touch.
- **Span DURATIONS are NOT a safe fallback.** They inflate with whatever causes
  the drift; [[build-gdi-session-accumulation]]'s own diagnosis recipe detects
  that slowdown by watching identical labelled mate spans go 4.7 s -> 35.5 s. So
  `drawing.reopen` measuring 4.2 s (393.9 s over 93 drawings) is *indicative* of
  #436's saving, not proof of it — it was measured in one session.
- **If you must benchmark**, match the initial session state across both arms and
  counterbalance the order (paired AB/BA runs, or randomize per-drawing order).
  Restarting SolidWorks only between arms makes arm A aged and arm B fresh, and a
  plain ABAB interleave still puts B later than A in every pair. Note also that a
  restart does not clear the TextInputHost mode at all.
- **Outlier detection still works** off a single run: drive_train at 583 s against
  a 32 s fleet mean is orders outside any observed drift (issue #438).
