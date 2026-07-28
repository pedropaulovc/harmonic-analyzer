---
name: drawing-fleet-timings-drift
description: "Drawing builds get monotonically slower as a SolidWorks session ages — +7.7% to +20.9% over one 93-drawing fleet pass, up to +61% on a single drawing — so single-run A/B fleet timings are worthless below ~20%"
metadata:
  node_type: memory
  type: project
---

Measured 2026-07-28 on four full cache-cold 93-drawing fleet builds (cache off,
parts/assemblies from cache, `doit drawing` serial).

Running the **same code** twice back-to-back in one SolidWorks session, *every
single drawing got slower in the second pass*:

| branch | pass 1 | pass 2 | drift |
|---|---|---|---|
| `main` @ 26f419a9 | 2995 s | 3227 s | **+7.7%** |
| PR #436 | 3830 s | 4629 s | **+20.9%** |

Per-drawing on the #436 pair: min **+3.0%**, max **+61.2%** (`pen_assembly`),
`paper_drive_assembly` +52.9%, `measuring_stick` +48.8%. Monotonic — not noise
scattered around zero, a systematic degradation with session age. Distinct from
[[build-gdi-session-accumulation]], which is about GDI exhaustion in one big
*assembly* build; this is ~93 short drawing subprocesses against one long-lived
`SLDWORKS.exe`.

**Why it matters:** it makes single-run A/B fleet comparisons meaningless below
roughly 20%. Every perf claim in the abandoned #382-#391 stack was a single-run
"paired fleet measurement" inside that band — 1.24% (#389), 5.7% (#384), 12.84%
(#388). #436 removed a whole reopen per drawing (186 -> 93 across the fleet,
verified twice) and the fleet still measured *slower*, because the arms ran in
different sessions.

**How to apply:**
- Never claim a drawing perf win from one A/B pair. Either restart SolidWorks
  between arms, or interleave/repeat the arms and report a spread.
- Prefer the **span-level** signal over wall clock: a count (reopens 186 -> 93)
  or a named span's own duration survives session drift far better than a fleet
  total. Measured with #437's spans in place, `drawing.reopen` is 393.9 s over
  93 drawings (4.2 s mean, 10.4 s max) -- so #436 removing one of the two
  reopens takes ~394 s off the fleet, about 13% of the 2995 s baseline, which
  the fleet total could never have shown. See [[otel-trace-local-viewing]] for
  reading `traces.jsonl`.
- Absolute per-drawing costs from one run are still usable for finding
  *outliers* (drive_train at 583 s vs a 32 s fleet mean is far outside the drift
  band) — just not for comparing two similar numbers.
- Worth investigating separately whether recycling the SolidWorks session
  partway through the fleet recovers the lost time.
