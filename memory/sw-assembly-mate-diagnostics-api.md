---
name: sw-assembly-mate-diagnostics-api
description: How/when to fetch SolidWorks "What's Wrong", per-mate errors, and over-define/DOF info via the COM API (assembly mate debugging)
metadata:
  type: reference
---

When a SolidWorks assembly build hits an over-define / unsolved mate (e.g. an
`AddMate5` that returns an error, or a red-X in the tree), use these COM APIs to
get the same data the **What's Wrong** dialog and **View Mate Errors** flyout
show. Reference docs: the `developing-solidworks:developing-solidworks` skill
(`./types/`, `./enums/swFeatureError_e.md`, `learnings/detecting-broken-mates-getwhatswrong.md`).

**What's Wrong dialog →** `IModelDocExtension::GetWhatsWrong(out Features, out
ErrorCodes, out Warnings)` — three parallel arrays: feature objects, a
`swFeatureError_e` code each, and an `IsWarning` bool each. Treat `IsWarning ==
False` as a hard fault. The dialog's **Description column is NOT returned** — it's
the canonical string for each `swFeatureError_e` code. Key codes:
`46 = mate over-defining the assembly` (usually a warning), `47 = mate cannot be
solved` ("distance correct but dimension flipped" — hard error), `48 = mate
entities suppressed/broken`, `2 = rebuild error`, `5/6 = sketch over/no-solution`.

**pywin32 byref trap (critical):** the three `out` params raise on a bare
`ext.GetWhatsWrong()` call. Pass `VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT,
None)` for each and read `.value` back (parallel tuples). Same byref pattern as
`SaveAs` Errors/Warnings. A quietly-swallowed bare call that reports "no errors"
is the trap that hides corruption — verify the call actually returned data.

**Per-feature/per-mate →** `IFeature::GetErrorCode2(out IsWarning)` returns the
`swFeatureError_e` code + warning flag for ONE feature. Walk the `MateGroup`
features and call it per mate to localize the bad one.

**View Mate Errors flyout →** no dedicated API; it's `GetWhatsWrong` filtered to
mate features. The label text (`"Distance13 (crank-handle<1>, Right Plane)"`) =
`IFeature.Name`; the mated entities come from `IFeature → GetSpecificFeature2()
→ IMate2 → MateEntity(i) → IMateEntity2.ReferenceComponent/Reference`.

**DOF gotcha (gear/mechanical mates):** there is NO "remaining DOF count" API in
the bundle. `IComponent2::GetConstrainedStatus` (2=under, 3=fully, 4=over,
5=no-solution) is per-component AND is **blind to gear-mate coupling** — a
gear-coupled part reads `2` (under) even when its rotation is fully determined.
So GetConstrainedStatus cannot distinguish "1 free DOF" from an over-constrained
closed loop; you must add a probe mate and read its `AddMate5`/What's Wrong result
(an over-defining *warning* on the correct flip ⇒ that DOF is already pinned by
the mesh). Also: `AddMate5` may still CREATE the mate feature in an error/warning
state even when it returns a non-success ErrorStatus — re-`GetWhatsWrong` after.

Repo already has working probes for this exact pattern:
`cad/scripts/diagnostics/probe_drivetrain_error.py` and `probe_live_drivetrain.py`
(GetWhatsWrong + GetErrorCode2), and `_add_wire1_gear` / cam-perturb in the
motion-study scripts handle pose/alignment-dependent gear over-defines.

Related: [[temp-3channel-build-reduction]], [[build-gdi-session-accumulation]],
[[sw-document-recovery-dialog]], [[solidworks-modeling-pitfalls]],
[[fix-relations-are-a-last-resort]].
