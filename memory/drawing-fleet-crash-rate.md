---
name: drawing-fleet-crash-rate
description: Measured SolidWorks crash rate across drawing fleet passes (~2 in ~750 builds), both auto-recovered — the bar for calling a red gate "flaky" vs a real regression
metadata:
  type: project
---

Across nine complete 93-drawing fleet passes run 2026-07-27/28 (PRs #435,
#436, #437, #440), SolidWorks crashed **twice** — 2 in 837 drawing builds:

| pass | drawing | wedged inside | seat age at crash |
|---|---|---|---|
| #437 pass 1 | `swing_stop_screw` | `span-start drawing.fastener_sheet` | 1541 s |
| #440 pass 1 | `magnifying_vertical_rod` | `span-start drawing.reopen` | 2804 s |

Different drawings, different operations. That is NOT evidence of independence
— both recipes reach the same `finalize_drawing`, so a shared-code regression
could surface under two different last-active span names. What the pair does
show is that no ONE drawing or operation is implicated. **Both recovered
automatically** and the pass completed: the watchdog detected the new
`sldexitapp.exe` (exit 86), the seat lock released cleanly from the parent, and
the reactive lifecycle recovery stopped SolidWorks, relaunched it via the
3DEXPERIENCE connector, and retried. `swing_stop_screw` finished at 693 s
including two backoffs.

Not GDI: no `rm_gdi` / "Available GDI objects are critically low" modal appears
in ANY of the nine logs, and GDI exhaustion presents as a modal + hang, not a
crash — see [[build-gdi-session-accumulation]]. Not the `TextInputHost` runaway
either (that mode is progressive slowdown with a healthy GDI count, and a
restart does not fix it). Also distinct from a **hung window**, which is log-only by design and is
COMMON, not rare: 37 episodes across the nine passes, 1410 s (24 min) total,
~4 per pass at 15–90 s each. They cluster hard — 18 last-active at
`span-end drawing.layout_audit`, 8 at `span-end drawing.curate_dimensions`,
7 at `span-start drawing.save_and_export_pdf`, so 68% sit on the audit →
save/PDF-export boundary, which reads as SolidWorks legitimately not pumping
messages through a heavy export. (An earlier version of this file said "appeared
once" — that was one pass mistaken for the fleet.)

**Why:** the standing instruction is to fix flakiness immediately, so a red
fleet gate needs a decision: repo bug or third-party crash? These numbers are
the baseline for that call. A crash that (a) hits a drawing no recent change
touched, (b) names a different operation than last time, and (c) auto-recovers,
is most likely SolidWorks instability the watchdog exists to absorb rather than
a regression to chase — but "most likely" is the honest strength, since shared
helpers like `finalize_drawing` sit under nearly every recipe. Two crashes on
the SAME drawing or the SAME operation would be a different signal and worth
investigating.

**How to apply:** read the crash line before judging — it names `reason`,
`exit_code`, `last_op` and the `sldexitapp` pids
(`rg "SolidWorks CRASHED|watchdog.abort" <pass>.log`). Then confirm recovery
actually completed rather than assuming it: look for the retry's
`task drawing:<stem> … OK`, since a pass can also fail recovery and burn all
three retries. Related: [[sw-crash-watchdog]], [[connector-lifecycle-lib]],
[[solidworks-3dx-launch]], [[drawing-fleet-cost-profile]].
