---
name: sw-recovery-dialog
description: "After force-killing SolidWorks (GDI reset / hung build), the 3DX relaunch pops a Document Recovery dialog — how to detect it and clear it"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1f309627-0ce3-4562-b4bc-935d4f44247a
---

Whenever you force-kill SLDWORKS and relaunch via the 3DX shortcut (the standard
GDI-reset / hung-build recovery — see [[solidworks-3dx-launch]]), SolidWorks pops the
**"Welcome - SOLIDWORKS Design"** window on the **Alerts → Document Recovery** tab,
listing the auto-saved docs from the killed session (e.g. the junk `Assem8.SLDASM`
from a crashed build) with **Open All / Delete All**.

**Detection signal:** the SLDWORKS process is up with a fresh low GDI count (~1700) but
its `MainWindowTitle` stays **empty** — the frame title is blank until the recovery
dialog is handled. So "process alive + GDI low + MainWindowTitle='' for >30s after
launch" = the recovery dialog is waiting. Confirm by searching the desktop UI Automation
root for a button named `Delete All` (or a window `Welcome - SOLIDWORKS Design`).

**Detection caveat:** `EnumWindows` + GetWindowText title-match for "Welcome..." FAILS —
it's a hosted/WPF popup, not a top-level titled window. Use
`[System.Windows.Automation.AutomationElement]::RootElement.FindFirst(Descendants,
NameProperty=...)` instead. Likewise UIA `InvokePattern.Invoke()` on the button works
where Win32 `BM_CLICK`/SendKeys silently no-op'd (UIPI / owner-window issues). For a
plain MessageBox-style "SOLIDWORKS Design" warning (e.g. the GDI `rm_gdi` modal),
`SendMessage(dlg, WM_COMMAND=0x0111, IDOK=1, 0)` dismisses it.

**Action — always Delete All, never Open All:** the listed auto-saves ARE the junk you
just killed; the real parts are saved in `cad/out/sldprt`. Click `Delete All` → it pops a
second confirm **"Are you sure you want to delete all backup files?"** → click **Yes**.
The recovery list goes empty and SW reaches the ready/no-document state; the build's
`create_assembly` then proceeds normally.

**Why:** the recovery dialog is a modal that blocks COM readiness and leaves the main
title blank, so an automated build that just connects + creates an assembly will hang or
mis-read SW state until it's cleared. **How to apply:** after any SW force-kill+relaunch,
poll for process-up, then UIA-clear the recovery dialog (Delete All → Yes) BEFORE running
the build script. Take a screenshot to confirm the list is empty if unsure.
