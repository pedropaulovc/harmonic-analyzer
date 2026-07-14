---
name: sw-zombie-doc-lock
description: "A SolidWorks document can become un-closable (CloseDoc/CloseAllDocuments return True but it survives) while holding an OS lock on its file — SaveAs to that path fails with a bare 'Failed to save as'; remedy is kill + shortcut relaunch"
metadata:
  type: project
---

New seat failure mode (2026-07-14, during the #289 merge-gate build): a long-lived
SolidWorks session can carry a **zombie document** — `GetFirstDocument` lists it,
but `CloseDoc(title)` and `CloseAllDocuments(True)` both **return True without
closing it** — which keeps an OS-level handle on its `.SLDPRT`. Everything else
works: ~90 parts built and saved through the same seat around it; only the one
task whose `SaveAs` targeted the zombie's own path failed, with the generic
`Failed to save as: …top-crossbar.SLDPRT` (no error code pointing at a lock).

**Diagnosis recipe (~2 min):**
1. Confirm an OS lock, not a data problem: `mv <file> <file>.locktest` → `Device
   or resource busy` = locked. (A stale `~$<name>.SLDPRT` sidecar alone is NOT
   the signal — one existed for crankshaft too, which built fine.)
2. No zombie python processes → the holder is `sldworks` itself. Attach COM
   (`win32com.client.GetObject(Class='SldWorks.Application')`), walk
   `GetFirstDocument` → the zombie is listed with the locked path.
3. Try `CloseDoc` / `CloseAllDocuments(True)`: if the doc survives a True
   return, it is un-closable via COM — no dialog was up (EnumWindows showed
   only the main frame), so this is distinct from the modal-block cases in
   [[release-refresh-modal-dialog-block]] and [[sw-recovery-dialog]].

**Remedy:** `Stop-Process -Force sldworks`, relaunch via the 3DEXPERIENCE
Platform shortcut ([[solidworks-3dx-launch]]; ~30 s splash, then a real
MainWindowTitle = ready; UIA-check for the recovery dialog anyway), verify the
lock released with the `mv` round-trip, re-run `doit` — it resumes from the
failed task (already-built parts stay up-to-date/cached).

**Likely origin:** a doit build killed mid-run (TaskStop) leaves the
in-progress subprocess's documents open with no teardown; most get swept by the
next build's `CloseAllDocuments(True)`, but a doc can wedge into this
un-closable state and then only bites when ITS path is next written. After
killing a build mid-COM-task, consider proactively checking
`GetFirstDocument` and restarting the seat if a survivor ignores CloseDoc.
