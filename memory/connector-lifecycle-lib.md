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

**Auto-wired into the build.** `_common.run_build` calls `_sw_lifecycle.ensure_ready()`
just before `adapter.connect()` (before the watchdog arms), so **any doit COM task —
`part:`/`assembly:`/`verify:*`/`export`/`release`/`drawing:` — starts SolidWorks when
down and recovers it from the .NET wedge, automatically.** It runs only in a real COM
subprocess, so a fully-cached build (which launches none) never starts SW. Fast no-op
when already `CONNECTED`. Opt out `HARMONIC_SW_AUTOSTART=0`; connect-wait
`HARMONIC_SW_CONNECT_TIMEOUT` (default 300s). Every action is a `build-infra` span
(`sw.ensure_ready` with `initial_state`/`action`/`final_state`; `sw.start`/`sw.stop`/
`sw.wait_connected`), so a trace answers "did this build have to start/recover SW?".

**Validation state (be honest):** the full stop→start→wait cycle is LIVE-VALIDATED on
this seat (stop ~1.5s, connector launch, ~135s to `CONNECTED_LOAD_STATUS=2`). The doit
`ensure_ready` hook is validated on the **no-op path** (already connected → 0.87s span);
the start-from-a-real-doit-build path is wired but NOT yet exercised end-to-end.

**Known gap:** the lib does NOT clear the post-kill **Document Recovery** dialog
([[sw-recovery-dialog]]) or the **crash** dialog ([[sw-crash-watchdog]]). If a real build
is force-killed with unsaved docs, the relaunch can stall on Document Recovery and
`wait_until_connected` will time out — those UIA dialog-clears are still separate. The
live recover test hit none because the killed session had no open documents.
