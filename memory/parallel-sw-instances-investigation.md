---
name: parallel-sw-instances-investigation
description: Queued assignment — probe whether 2+ independent SolidWorks instances can run parallel builds on one seat
metadata:
  type: project
---

**Assignment (queued 2026-07-06, starts AFTER PR #193 merges):** investigate whether
it is possible to run **2 or more SolidWorks instances working independently on a
single seat**, so the COM build tasks can run in parallel instead of serialized.

Concretely, three questions to answer empirically:
1. Can 2+ `SLDWORKS.exe` processes run at once on one seat (licensing + stability)?
2. Can COM **reliably pick a SPECIFIC instance/window** to drive (not just attach to
   whatever singleton is in the ROT)? This is the crux — `Dispatch("SldWorks.Application")`
   binds to the first ROT entry; need to enumerate the Running Object Table for all
   `!SldWorks.Application` monikers and match by PID/window, or launch+bind deterministically.
3. Do **parallel builds cause flakiness** (mate-flip nondeterminism, save-churn races,
   cross-instance interference)?

**Acceptance bar (hard):** run a full **PARALLEL** cold build (the multi-instance mode
being tested, N instances driving COM tasks at once) **3×** and all three must pass before
claiming success. Cold = no remote-cache hits (bust the salt / `HARMONIC_CACHE_MODE=off`).

**Measure the speedup** — wall-clock of the parallel cold build vs **past releases**
(historical serial-spine release build times; pull from release logs / `cad/out/reports/`
telemetry / prior run timings). Quantify N× actual vs N-instance theoretical.

**Resource surveillance (leak watch) — a build can PASS but leak.** Track across the run
and especially across the 3 repeats:
- **Committed memory** (commit charge / per-process working set) — N SolidWorks instances
  multiply RAM pressure; watch for monotonic growth across repeats (a leak, not steady state).
- **GDI objects** — SW accumulates GDI handles per session (see [[build-gdi-session-accumulation]]);
  the per-process cap is 10k and multiple instances multiply the pressure. A GDI climb that
  doesn't reset between builds is a blocker even if geometry is correct.

**Why it matters:** `dodo.py` serializes every COM task on the single STA seat with a
cross-process file lock (`_com_seat`; see [[com-seat-lock]], which replaced the old
`_COM_TAIL`/`_spine_dep` spine 2026-07-11) precisely because of the invariant "one
SolidWorks STA seat ⇒ COM tasks must never run concurrently." If N independent instances
are viable, that invariant relaxes and the COM build parallelizes (N× speedup on the
slowest stage) — concretely, you would key the lock PER INSTANCE (or use N lock slots)
instead of one machine-global seat. See [[mate-flip-determinism]] for the flip
nondeterminism that parallel builds could re-expose, and [[per-seat-part-order]] for the
existing cross-SEAT (not cross-instance) parallelism the cache already exploits.

**Resource knobs to give breathing room (researched 2026-07-06)** — raise these BEFORE
running parallel instances, then watch whether they hold across the 3 repeats:

| knob | location | default | range | governs |
|------|----------|---------|-------|---------|
| `GDIProcessHandleQuota` | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows` (DWORD, **decimal**) | 10000 | 256–65536 (SW blog says max 16384; OS allows up to 65536) | per-process GDI handles |
| `USERProcessHandleQuota` | same key (DWORD, decimal) | 10000 | 200–18000 | per-process USER objects (windows/menus/cursors) |
| Pagefile custom size | Control Panel → System → Advanced → Performance → Virtual Memory | auto | — | commit-charge headroom; SW blog suggests 2× physical RAM initial+max |
| Desktop heap `SharedSection` | `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\SubSystems\Windows` (2nd value) | e.g. 3072/20480 | — | interactive-desktop USER heap; bounds total windows across processes |

**THE parallel-instance ceiling (crux caveat, Raymond Chen + SW forum):** there is a
**session-wide** GDI/USER pool (~65,536 handles) that bounds the SUM across ALL processes,
not just each one. Raising `GDIProcessHandleQuota` only lets ONE process grab a bigger
slice — it "starves out other processes." So N instances × per-process quota **cannot exceed
the session pool**: you can't crank every instance to 16k AND run 8 of them. SW forum 214732:
at the default 10k quota SolidWorks opens **~47 parts** before hitting the wall — so per-instance
GDI is consumed per open document (our build's `CloseAllDocuments` between parts is what keeps
it bounded; see [[build-gdi-session-accumulation]]). **Design implication:** pick N and the
per-process quota together so `N × quota ≲ 60k`, and treat a GDI climb that doesn't reset
between the 3 cold builds as a leak/blocker even if geometry passes.

**How to apply:** consult the `developing-solidworks` skill's `./learnings/` and `./docs/`
for ROT/multi-instance COM binding before writing code. Prototype the ROT-enumeration bind
in `SolidworksMCP-python` (the COM adapter). Do NOT relax the `_com_seat` serialization in
`dodo.py` (widen from one seat lock to N slots) until the 3× cold-build bar is met — a
false "it works" here silently corrupts every build.
