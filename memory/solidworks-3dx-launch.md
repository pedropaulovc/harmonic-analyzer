---
name: solidworks-3dx-launch
description: "SolidWorks 2026 (3DEXPERIENCE \"for Makers\" edition) cannot be launched by running sldworks.exe directly — recovery procedure after a crash"
metadata: 
  node_type: memory
  type: project
  originSessionId: 5e824fa0-7bda-4055-8655-aa59ed6f0ef9
---

SolidWorks on this machine is **SOLIDWORKS Design Professional for Makers 2026** (3DEXPERIENCE edition, `C:\Program Files\Dassault Systemes\SOLIDWORKS 3DEXPERIENCE R2026x\SOLIDWORKS\sldworks.exe`). Launching that exe directly pops "SOLIDWORKS Design must be launched from the 3DEXPERIENCE Platform or from the desktop shortcut created from the Platform" and the process exits — COM (`SldWorks.Application`) never comes up, and `New-Object -ComObject` attempts spawn extra doomed instances.

**Why:** the Makers licence is validated through the 3DEXPERIENCE launcher; bare exe launches are rejected.

**How to apply:** if SolidWorks crashes mid-automation (symptom: scripts fail with "No part template configured", then COM gives "Operation unavailable"/"Server execution failed"; only `sldworks_fs` remains in the process list):
1. Dismiss the platform prompt(s) with **No** on any stuck instances.
2. On the "SOLIDWORKS Design Error Report" dialog (process `SLDEXITAPP`), click **Restart SOLIDWORKS Design** — it relaunches through the proper licensed path.
3. If no crash dialog is available, use the 3DEXPERIENCE Platform desktop shortcut (or ask the user) — do NOT start sldworks.exe directly.
4. ~30 consecutive `create_part` builds without closing documents preceded the crash — consider closing documents periodically in long batch runs ([[harmonic-analyzer-project]]).

**2026-06-14 — CORRECTION: COM relaunch does NOT produce a valid session. Always use the desktop shortcut.** An earlier note here claimed plain COM activation (`win32com Dispatch SldWorks.Application`) relaunches SW fine as long as `3DEXPERIENCELauncherBackbone` is running. That is WRONG and was retracted after testing: the SW instance COM brings up reports it was **not started up via 3DEXPERIENCE** (unlicensed/unvalidated — the Makers licence is only granted through the launcher's own shortcut handoff, not via bare COM CLSID activation, even with the backbone running). Builds against that instance fail the licence check.
   The dismiss-the-CEIP-popup step is still correct for clearing the crash dialog, but recovery is NOT "then call connect()". Recovery is ALWAYS:
   1. Clear/close any crash dialog (`SLDEXITAPP` + its stacked CEIP "OK" popup) — dismiss via UI Automation if needed, or `Stop-Process` the dead `SLDEXITAPP`.
   2. Launch the Platform shortcut: `Start-Process "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Dassault Systemes SOLIDWORKS 3DEXPERIENCE R2026x\SOLIDWORKS Design.lnk"`. Splash clears in ~25-30 s with the cached session (no interactive re-login here).
   3. THEN `adapter.connect()` attaches to that properly-licensed instance.
   This applies to BOTH crash recovery and manual-kill recovery — the desktop shortcut is the single supported launch path; COM is only for *attaching* to an already-shortcut-launched SW, never for *starting* it.
   The crash that triggered this followed a heavy Basic Motion dynamic solve (21 springs + full gear train), not a build batch — the dynamic solve can take SW down (it died mid-`set_motion_time` sampling, surfacing as `Transform2`/`ArrayData` returning None). See [[motion-study-pipeline]].

**2026-07-04 — killing SW is FINE; the only rule is how you RESTART it (corrects the 2026-06-14 "leave the running SW alone" note, retracted by Pedro).** `Stop-Process -Force SLDWORKS` is an acceptable way to get rid of a wedged/slow instance. What does NOT work after the kill is letting COM `connect()` cold-start `sldworks.exe` — the Makers licence rejects that with the "must be launched from the 3DEXPERIENCE Platform or from the desktop shortcut" Yes/No dialog and connect fails with `Server execution failed`. Recovery after ANY kill (or crash) is the same single path: launch the Platform shortcut — `Start-Process "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Dassault Systemes SOLIDWORKS 3DEXPERIENCE R2026x\SOLIDWORKS Design.lnk"` — splash clears in ~25 s with the cached session (no interactive re-login), THEN `adapter.connect()` attaches to the licensed instance.

**2026-07-03 — "critically low on committed memory" modal mid-build.** After a
day of repeated full-spine builds (~6 FULL drive-train rebuilds + verifies in
one SW session) SolidWorks popped "Warning! Your system is running critically
low on committed memory... Do you want to continue?" — a MODAL that blocks all
COM, hanging the doit task. Remedy that worked: answer **No** (never Yes —
"executing this command might cause SOLIDWORKS to fail"), stop the doit run,
then a graceful COM `CloseAllDocuments(True)` + `ExitApp()` — which itself HUNG
(process alive, Responding False, several minutes) — so `Stop-Process -Force`
the hung instance and relaunch via the Platform shortcut (above), ~30 s splash,
COM attaches, `doit` resumes from staleness. Proactive detection (poll
committed memory / SW Resource Monitor between COM tasks, preemptively
restart) is tracked in the repo issue "preemptive SW restart on resource
exhaustion" (#164).
   Post-restart wrinkle (same day): the relaunched session showed 3DEXPERIENCE
licence errors that affected INTERACTIVE usage only -- COM builds kept
passing (full part build green). One earlier relaunch attempt died outright
(process exited, only `sldworks_fs` left, COM connect timeout after 60 s), so
the auth failure can be either fatal-at-launch or interactive-only. If COM
work starts failing after such a relaunch, suspect the licence state first,
not the geometry.
