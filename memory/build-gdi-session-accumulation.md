---
name: build-gdi-session-accumulation
description: "The full output-assembly build exhausts SolidWorks GDI handles if SW isn't freshly restarted first; run it as the first heavy script in a session"
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
