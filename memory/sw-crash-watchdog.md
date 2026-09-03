---
name: sw-crash-watchdog
description: How to DETECT a SolidWorks crash/wedge — sldexitapp.exe is the only timely signal (event log useless); per-op timeout 15 min (max healthy op ~230s); Responding==False is log-only
metadata:
  type: project
---

Findings from the 2026-07-17 crash (SW crashed 22:29:50, stuck "Generating
crash report" 8.5 h+), now implemented as `cad/scripts/_watchdog.py` +
`check:watchdog` (PR ops/com-watchdog):

- **The timely crash signal is the process `sldexitapp.exe`** (SolidWorks'
  crash-report handler, `C:\Program Files\Dassault Systemes\SOLIDWORKS
  3DEXPERIENCE R2026x\SOLIDWORKS\sldexitapp.exe`). It only runs after
  SLDWORKS.exe crashed and owns the `#32770` dialog titled exactly
  "SOLIDWORKS Design" ("…has encountered a problem… Generating crash
  report"). The dialog's inner text is NOT exposed to UI Automation — key on
  the process name / window title, not the static text.
- **The Windows event log is useless for this**: sldexitapp intercepts WER, so
  no Application-log 1000/1001/1002 event fires at crash time and the
  `%ProgramData%\Microsoft\Windows\WER\ReportQueue\AppCrash_sldworks.exe_*`
  folder appears only after the report completes — which can be *never* (the
  stuck report). Past crashes (7/12, 7/14) do have WER folders; a stuck one
  has nothing.
- **Zombie behavior**: SLDWORKS.exe stays alive, `Responding == False`,
  burning CPU (~33k s observed), sometimes with a phantom doc window
  (`[Assem6 *]`). A stale crash dialog can linger while a healthy NEW
  SolidWorks runs beside it — so crash detection must baseline pre-existing
  sldexitapp pids and only treat a NEW pid as fatal.
- **Timeout calibration** (~3 weeks of traces.jsonl, n≈3061 save_as): longest
  single healthy COM op ~230 s (`verify.rebuild`; `gate.dof` 218 s,
  `assembly.final_rebuild` 217 s, `mass_properties` 215 s, `export.save_as`
  193 s) → per-op idle timeout 900 s = ~4× headroom. Whole COM tasks
  legitimately run ~27 min (`assembly:summing` 1598 s) → any task-level
  timeout must be ≥ 40 min. Key on telemetry activity
  (`_telemetry.last_activity()`), never process lifetime.
- **Pedro's call**: `Responding == False` (IsHungAppWindow) is a NOISY
  criterion — SW legitimately hangs its message pump while resolving complex
  geometry — good to LOG (throttled warn), never to kill on.

**Why:** COM calls block forever on a crashed/wedged SW; only a process exit
frees the seat (lock is held by the doit PARENT, so a child `os._exit`
releases it cleanly).

**How to apply:** don't hand-roll crash polling — the watchdog is on by
default in every `run_build` COM session (exit 86 crash / 87 op-timeout;
`HARMONIC_COM_WATCHDOG=0` kill switch, `HARMONIC_COM_OP_TIMEOUT` override).
Recovery stays [[solidworks-3dx-launch]]: clear the dialog, Platform desktop
shortcut, never COM-start. See also [[sw-recovery-dialog]].

**Distinct failure this watchdog does NOT catch:** the ".NET Framework" splash
wedge — SW launches, sits on the splash behind a `#32770` "SOLIDWORKS Design"
modal ("Failed to load Microsoft .NET Framework."), and never becomes
COM-attachable. No crash (no NEW `sldexitapp.exe`) and no op activity, so
neither watchdog signal fires; a build just blocks on `sw.connect`. That case
is detected + recovered by [[connector-lifecycle-lib]]
(`sw_recovery.find_dotnet_splash_dialog` / `recover_solidworks`), now auto-run
before connect in every COM task.

2026-09-02 addendum -- the LOW-MEMORY MODAL (now watchdog signal 4, exit 88):
after ~10 h of builds on one session (sldworks.exe at 66 GB committed / 11 GB
working set, 127 GB box, 67 GB free), SolidWorks popped a `#32770`
"SOLIDWORKS Design" MessageBox mid top-assembly build: "Warning! Your system is
running critically low on committed memory. Executing this command might
cause SOLIDWORKS to fail... SOLIDWORKS strongly recommends that you do not
continue. [Yes] [No]". Facts: (1) it is owned by sldworks.exe (no sldexitapp,
so the crash signal is blind to it) and disables the main frame -- the hung
probe warned every poll but nothing was fatal until the 900 s op timeout;
(2) while it is up, COM queries return EMPTY rather than blocking:
`GetComponentByName` came back None ("Component not found: 'channel-1'") for a
component that a probe on a fresh session found at once -- so a "not found"
right after hung warns is the dialog, not the model; (3) Win32 BM_CLICK,
WM_COMMAND IDYES and SendKeys Alt+Y all no-op'd on it (same UIPI/owner issue as
the Document Recovery popup); the user's ruling is that killing SolidWorks is
the safe answer, never clicking Yes. Hence `_watchdog._seat_modal_dialog`
(fatal after 2 polls, dodo retries after force_recover) plus the preventive
`dodo._sw_preflight` (restart past `HARMONIC_SW_MAX_COMMIT_GB`, default 40).

