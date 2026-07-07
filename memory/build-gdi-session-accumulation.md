---
name: build-gdi-session-accumulation
description: "Two distinct SW seat slowdowns: (1) GDI handle exhaustion (rm_gdi modal, hang) — act only on the actual error; (2) runaway TextInputHost starving SW's STA message pump (mates 4.7s→35s, GDI fine, SW restart does NOT help) — diagnose via release-log span diffs + per-process CPU rate, remedy = kill TextInputHost"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1f309627-0ce3-4562-b4bc-935d4f44247a
---

`build_output_assembly.py` (the 123-component output monolith, since SPLIT into 4 flat subassembly builders — summing/magnifier/pen/paper-drive — 2026-06-20) inserts ~123 component instances and pushes SolidWorks'
per-process GDI handle count up. The Windows default `GDIProcessHandleQuota` is **10000**
(HKLM\...\Windows NT\CurrentVersion\Windows). A **fresh** SW process baselines ~1780 and
the full build peaks **~8871** — comfortably under the ceiling, and it completes (123
components + interference check). But GDI handles **accumulate across operations in one SW
session and are NOT released between scripts**: running the part build + a probe + the full
assembly back-to-back in the same session started the full build already ~partly depleted,
so it hit 10000 around component ~50 (the fastener block) and SolidWorks popped the
recurring "Available GDI objects are critically low" (`rm_gdi`) modal, hanging the build's
STA thread indefinitely (68 min before I noticed).

**Rule (user-corrected 2026-06-17):** GDI exhaustion is a **once-in-a-blue-moon** event —
do NOT pre-emptively restart SW or raise the quota just because the idle baseline looks
high. Keep the restart/quota trick **in your back pocket** and only act on an **actual** GDI
error (the `rm_gdi` "critically low" modal / a build hang at it). If it becomes **recurring**,
tell the user. (Earlier I over-reacted: restarted SW because idle GDI was 8923 then ~3243,
but the full output build from a ~3243 baseline still peaked well under 10000 and completed
fine — placed 89 comps at GDI 4892.) When you DO need a fresh session: kill + 3DX-shortcut
relaunch — see [[solidworks-3dx-launch]], then clear the recovery dialog [[sw-recovery-dialog]].

Diagnostics: GDI is cheap per repeated INSTANCE (chain links, fasteners cost ~20/comp —
graphics reused) but ~140-180 per distinct new part doc. Measure live with
`GetGuiResources(proc.Handle, 0)` via a P/Invoke. The quota
*can* be raised to 65536 (HKLM, needs admin + SW restart) as a belt-and-suspenders fix, but
a fresh restart alone was sufficient — no registry change was needed. Confirmed 2026-06-17.

**Second failure mode (2026-07-06): progressive per-operation SLOWDOWN — a runaway
`TextInputHost`, NOT SW session age and NOT GDI.** Identical drive-train gear mates ran
**7.5× slower** than the v0.15.1 release logs (4.7 s → 35.5 s each), full `frame` build
2.5× slower (148 s → 372 s), worsening across the day (2.5× mid-afternoon → 7.5× by
evening). GDI was fine (~1500) and a CLEAN SW RESTART DID NOT FIX IT (fresh instance still
placed 5× slow). Culprit: Windows' `TextInputHost.exe` runaway (a known Windows bug) — 9.3
CPU-hours accumulated, burning 66% of a core continuously while SW got only 36%. Mechanism:
SW is an STA COM server — every call serializes on the UI thread's message pump, exactly
where a churning input host injects load, so op LATENCY inflates while CPU looks idle.
**Kill it** (`Stop-Process -Name TextInputHost -Force`; it respawns clean on demand) →
placement cadence back to baseline (8.3 s → 1.2–2.2 s) immediately, no SW restart needed.

**Diagnosis recipe:** (1) download the latest release's `-logs.zip` (per-task logs attached
to the GitHub release) and diff the SAME-labelled mate/placement spans — per-task totals
mislead (doit task lines include cache-store upload); (2) `GetGuiResources` for GDI; (3)
per-process CPU RATE (sample `Get-Process` CPU twice over 5 s — cumulative totals flag the
runaway: TextInputHost had 33,605 s); (4) only then consider an SW restart (clean exit:
attach → `CloseAllDocuments(True)` → `ExitApp()`, avoids the recovery dialog
[[sw-recovery-dialog]]; doit resumes from its ledger).
