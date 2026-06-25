---
name: release-refresh-modal-dialog-block
description: A modal SW dialog blocking the COM seat makes OpenDoc6 fail silently (null, error=0), which breaks the release/refresh REOPEN path but NOT the from-scratch build — diagnosis + dismiss recipe
metadata:
  type: project
---

`doit release` (and any incremental `refresh_assembly`) failed at the FIRST COM
step with `open <asm> failed: Failed to open model: …\frame.SLDASM`, while a
full `doit` build of the same model was green minutes earlier. Root cause was
**environmental, not data**: a leftover **modal "Open" file dialog** owned by
the SOLIDWORKS process was occupying the single STA COM seat.

**Why it presents as a silent open failure.** With a modal dialog up,
`ISldWorks::OpenDoc6` can't service the request and returns **null with
`error_code=0, warning_code=0` and `GetDocumentCount()==0`** (a documented SW
"S_OK with null return" mode). `adapters/solidworks/io.py` open_model treats
null as `raise "Failed to open model"`, so `refresh_assembly.py` fails the task
and the release aborts. The generic message hides that the real blocker is a
dialog, not the file.

**Why the build was green but the release wasn't (the key asymmetry).** The
build creates each assembly **FULL** (`create_assembly` + insert + mate from
scratch) and **never opens an existing `.SLDASM`**. The release path is
incremental — it **REFRESHES**, i.e. **reopens** the saved `.SLDASM` via
`OpenDoc6`. The reopen is the *only* pipeline step that calls OpenDoc6 on an
existing assembly, so it's the only step a seat-blocking dialog can break — even
when "nothing changed" since the green build. (The cache MISS that triggered the
refresh was benign drift: building the top assembly re-saves component parts
*after* the subs are built, shifting their dep digests — see
[[incremental-builds-validation]].)

**Diagnosis recipe (scratchpad probes, ~1 min):**
1. Rule out a real missing reference: `app.GetDocumentDependencies2(asm, True,
   False, False)` (TraverseFlag=True, **SearchFlag=False** = raw stored paths) →
   check each path exists. Here all 7 frame deps existed → not a data problem.
2. Confirm the seat is blocked: direct `OpenDoc6(path, swDocASSEMBLY, 1, "",
   VARIANT(VT_BYREF|VT_I4,0)×2)` → if it returns null with err=0/warn=0 and
   `GetDocumentCount()==0`, the seat is jammed (vs a real error code).
3. Find the dialog: `EnumWindows` filtered to the SLDWORKS pid; the culprit was
   a `WindowsForms10.Window…` titled **"Open"** (a file browser), NOT a `#32770`.

**Fix = dismiss the dialog, then re-run.** `SendMessage(hwnd, WM_CLOSE=0x0010)`
to the "Open" window cancels it. After that, the *same* silent open returned
real docs (frame=8, magnifier=12, top=79) and all 7 release refreshes passed.
v0.9.1 then published clean (0 geometry changes vs v0.9.0 — pure OTel release).

**Likely trigger** (not provable post-dismiss): the **Makers-edition silent-open
UI leak** (adapter runbook #7: `swOpenDocOptions_Silent` still pops UI on some SP
levels; this seat is *3DEXPERIENCE for Makers 2026 SP2.0*) went modal and jammed
the seat. Distinct from the post-kill Document-Recovery modal in
[[sw-recovery-dialog]] — same class of "modal blocks the seat", different dialog.

**Durable hardening (not yet done):** in `open_model`/`refresh_assembly`, treat
"null open with error=0 AND GetDocumentCount unchanged" as a distinct
`seat blocked by modal dialog` condition — enumerate+dismiss SW-owned modal
windows and retry once, instead of raising the generic "Failed to open model".

Relates to [[incremental-builds-validation]], [[sw-recovery-dialog]],
[[otel-trace-local-viewing]].
