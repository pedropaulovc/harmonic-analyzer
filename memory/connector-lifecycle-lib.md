---
name: connector-lifecycle-lib
description: sw_recovery lib + _sw_lifecycle autostart — start/stop/recover 3DEXPERIENCE SolidWorks in code (connector launch, .NET-splash-wedge recovery), auto-run before every doit COM task, telemetry-wrapped
metadata:
  type: project
---

There is now a **library** for driving the Makers/3DEXPERIENCE SolidWorks lifecycle
in code, replacing the manual SW Rx / Platform-shortcut dance:
`solidworks_mcp.adapters.sw_recovery` (in the submodule, merged as fork PR #92) +
`cad/scripts/_sw_lifecycle.py` (parent-side telemetry wrapper + policy). Everything
was derived empirically from a **Sysmon** capture of a real SW Rx *"Restart connector
processes → Launch SOLIDWORKS"* run (`winget install Microsoft.Sysinternals.Sysmon`).

**What the lib gives you** (`python -m solidworks_mcp.adapters.sw_recovery {status|stop|restart-connectors|start|recover}`):
- `start_solidworks()` — the exact `CATSTART.exe -run SWXDesktopLauncher.exe -object "-Url=<SpaceURL> --AppName=SWXCSWK_AP -MyAppsURL=… -tenant=<TenantId> -3DRegistryURL=…"` connector launch, params read from `HKCU\…\SOLIDWORKSPDM\Servers\3DEXPERIENCE` (never hardcoded). This is the SAME licensed path the Platform `.lnk` invokes — so it does NOT hit the "must be launched from the 3DEXPERIENCE Platform" rejection that bare `sldworks.exe`/COM-CLSID start does. Supersedes the "Start-Process the .lnk / ask the user" step in [[solidworks-3dx-launch]].
- `stop_solidworks()` / `kill_connector_processes()` — `taskkill /F` the SW tree + session-scoped connector agents (`SWXDesktopLauncher, CATSTART, ENOUSWCStart2/3, ENOPLMCSAClient, SWConnectorTasksAgent, EdmServerV6`); leaves the persistent platform daemons (`3DEXPERIENCELauncher*`, `sldworks_fs`) that hold the login/CAS session. Waits for `sldworks.exe` to fully exit (a relaunch during teardown trips the "already running" guard and no-ops).
- `recover_solidworks()` — stop → start → wait-connected. The fix for the **".NET Framework" splash wedge**: SW launches, sits on the splash behind a `#32770` "SOLIDWORKS Design" modal reading "Failed to load Microsoft .NET Framework.", never becomes COM-attachable (the [[sw-crash-watchdog]] does NOT cover this — no crash, no op activity). Detector `find_dotnet_splash_dialog()` keys on that modal owned by the disabled `'splash'` window (structural Win32, no comtypes).
- Health = registry `HKCU\Software\SolidWorks\SOLIDWORKS 2026\General\Last Run SolidWorks`: connected when `CONNECTED_LOAD_STATUS==2` AND `SOLIDWORKS_ISCONNECTED==1`. These persist across a kill, so `start_solidworks` calls `reset_connector_status()` (zeroes them) before launch and `is_connector_loaded()` requires a live `sldworks.exe` — closing a stale-flag false positive a live test caught.

**Auto-wired into the build — ONCE at startup + REACTIVE retry, driven from
`dodo._exec_com`** (NOT per COM subprocess — that cost ~0.76s/task, measured).
`_exec_com` wraps every COM `_exec` call site (`_run(com=True)`, the cached part/
assembly actions, drawings):
- **Autostart, once per doit worker**: the first COM task calls
  `_sw_lifecycle.ensure_ready()` (module flag `_SW_ENSURED`), bringing SolidWorks up
  before any COM work; later tasks see `CONNECTED` and skip. SW-free tasks
  (`doit list`, `check:math`) never reach `_exec_com`, so they never start SW.
  Measured: `ensure_ready` fires exactly once across a multi-part build (~0.8s no-op
  when SW already up), vs ~0.76s × every task under the old per-`run_build` hook.
- **Retry on a SolidWorks failure**: if a COM subprocess exits with a watchdog
  crash/op-timeout code (86/87) or leaves SW not-`CONNECTED`, `_exec_com` retries up
  to 3× with **1/2/4-min backoff**, calling `_sw_lifecycle.force_recover()` (kill→
  relaunch) between attempts. An ordinary failure (gate assertion) with SW still
  healthy is NOT retried — it raises immediately. `force_recover` is unconditional
  (a crashed SW is a zombie that still reads `CONNECTED`, so it can't trust
  `detect_state`) and first `taskkill`s `sldexitapp.exe` (crash dialog).

Opt out `HARMONIC_SW_AUTOSTART=0`; connect-wait `HARMONIC_SW_CONNECT_TIMEOUT`
(default 300s). Every action is a `build-infra` span (`sw.ensure_ready`,
`sw.force_recover`, `sw.start`/`sw.stop`/`sw.wait_connected`), so a trace answers
"did this build have to start or recover SolidWorks?".

**Validation state (be honest):** the full stop→start→wait cycle is LIVE-VALIDATED on
this seat (stop ~1.5s, connector launch, ~135s to `CONNECTED_LOAD_STATUS=2`).
Start-from-a-doit-build validated: a `doit -n 4` with SW down logged
`ensure_ready: state=not_running → CATSTART launch → SLDWORKS UP`. Once-per-worker
validated: a 2-part serial build fired `ensure_ready` exactly once (0.79s no-op, SW
already up), not on the second part. **The reactive retry / `force_recover` path is
NOT live-tested** — inducing a real mid-build COM crash to prove the 86/87 →
backoff → recover → retry loop is still pending.

**Known gap:** the lib does NOT clear the post-kill **Document Recovery** dialog
([[sw-recovery-dialog]]) or the **crash** dialog ([[sw-crash-watchdog]]). If a real build
is force-killed with unsaved docs, the relaunch can stall on Document Recovery and
`wait_until_connected` will time out — those UIA dialog-clears are still separate. The
live recover test hit none because the killed session had no open documents.
