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
False` as a hard fault. The dialog's **Description column is NOT returned** by
this call. Key codes: `46 = mate over-defining the assembly` (usually a warning),
`47 = mate cannot be solved` (hard error), `48 = mate entities suppressed/broken`,
`2 = rebuild error`, `5/6 = sketch over/no-solution`.

**GetWhatsWrong is BLIND mid-build — do not gate a build on it (measured
2026-07-25).** Inside a live drive-train build, with a copied mate sitting at
code 47, `GetWhatsWrong` returned ZERO entries — and still zero after an
explicit 22 s `ForceRebuild3`. It only populates once the UI settles: attaching
to the same seat AFTER the build process detached showed all five entries. So
it is fine for post-hoc autopsy on a saved/settled document (and for
`verify:soundness`, which reopens), but a build that must fail at the operation
which CAUSED the fault has to use `IFeature::GetErrorCode2` on the mate feature
— that IS live immediately, which is why `_mate_hard_error` works for authored
mates. Cost is all TRAVERSAL: walking MateGroup's 104 subfeatures measured
5.62 s (~54 ms per `GetNextSubFeature`) vs 0.45 s for all 104 `GetErrorCode2`
reads (4.4 ms each), so scan incrementally from a remembered cursor
(`_cwm.new_mate_errors`), never per-copy from the top. Cheap per-component
signals do NOT substitute: `GetConstrainedStatus` (2–5 ms) read 4 for BOTH the
healthy seed and the broken copy, and `GetMates` counts were as expected.

**The per-mate error PROSE *is* reachable (verified 2026-07-25)** — the tree
tooltip's own wording, which is FINER-GRAINED than the code: 47's enum blurb is
the generic "This mate cannot be solved. Consider: deleting…", while the live
text distinguishes causes ("Planes are parallel but their **alignment is
reversed**. …edit this mate and change the alignment setting." vs the
dimension-flipped wording). No per-feature description API exists; instead
SolidWorks writes the prose into the SESSION MESSAGE STACK on a rebuild, and
`ISldWorks::GetErrorMessages(out Msgs, out MsgIDs, out MsgTypes)` returns it:

```python
error_messages(sw)            # DRAIN first -- the stack is read-and-clear
model.ForceRebuild3(False)    # regenerates the messages (~21 s on drive-train)
msgs = error_messages(sw)     # -> ['<Doc> - Rebuild Errors', 'Mates: …']
```

Same byref trap as `GetWhatsWrong` (three `VT_BYREF|VT_VARIANT` VARIANTs). Traps
specific to it: the stack keeps only the last **20** messages and is cleared by
the read (drain before the rebuild or you parse stale text); **every** mate
problem arrives concatenated into ONE string with no separator
(`…red error icons.Coincident37: This mate is over…Distance32: The components…`),
so split on the mate NAMES from `GetWhatsWrong`, never on punctuation; and the
text is UI-localized while the code is not — **decide on the code, explain with
the text**. Pair it with `IMate2.Alignment` (`swMateAlign_e`: 0 ALIGNED /
1 ANTI_ALIGNED / 2 CLOSEST) + `.Flipped` / `.CanBeFlipped` to know which knob the
message is pointing at. Working script:
`cad/scripts/diagnostics/probe_mate_error_text.py`.

**Early-vs-late binding trap (bit this THREE times in one session):** every one
of these calls has `out` params, so binding decides where the data lands. Under
an `_early_bound(...)` wrapper InvokeTypes returns the outs in the RETURN TUPLE
and leaves the byref VARIANTs empty — which silently reads as "no errors found"
/ "no messages". Either call on the RAW late-bound dispatch, or read the tuple:

- `GetWhatsWrong` → raw dispatch (`adapter.currentModel`, NOT `_early_bound`).
- `GetErrorCode2` → early-bound is fine, but consume the `(code, is_warning)`
  tuple; `int(result)` crashes on it.
- `GetErrorMessages` → **`adapter.swApp` IS early-bound** (`_do_connect` wraps it
  as `ISldWorks`), so the byrefs stay empty and the data is in the return tuple
  `(count, Msgs, MsgIDs, MsgTypes)` — read `ret[1]`. Confirmed by printing the
  shape live. Standalone `GetObject(...)` probes are late-bound and DO fill the
  byrefs, so a probe that works standalone can still come back empty in-build.

Also `FeatureByName` is declared on `IAssemblyDoc`, not `IModelDoc2` (same
dispatch), and `IMate2` has no feature/error accessor at all — you cannot get an
error code from `IComponent2::GetMates`, only from the mate FEATURE.

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

**Bottom-dead-centre distance-driver singularity (crank driver, 2026-06-19):**
when a revolute is pinned by a single in-plane *coordinate* of an off-axis bore
(`spin_driver`: a distance from the bore to Top/Right plane), the pin is a
KINEMATIC SINGULARITY at the arm's dead-centre poses. There the two distance
solutions merge, so the constraint's Jacobian row goes rank-deficient against the
existing lock/axial mates and SW reports it as *over-defining* — even though a
genuine free spin DOF still exists (proven: a probe build that SKIPS the driver
leaves the train 1-DOF under-defined). Real case: `a45a5ea` rederived the crank
to hang straight DOWN (bottom-dead-centre), so the down-pose `spin_driver`
over-defined and drive_train hard-failed. Ground truth via `GetWhatsWrong`:
`flip=False` → the driver mate gets code **47** ("dimension flipped", hard
error); `flip=True` → code **46** over-define *warning*, co-flagging the
pre-existing `Lock2`/`Lock4` (arm/handle keyed) + `Distance1` (crank axial) as
the redundant set. So it is NOT a flip/far-side reachability issue — BOTH flips
fail, which a far-side miss never does. **Fix:** pin the spin with an `angle_driver`
instead — an angle mate's Jacobian is constant and non-degenerate at every pose,
so it pins dead-centre cleanly (the same formulation the cone-post swing-park
uses). The dihedral is read live from the arm's rest transform (`acos` of the
assembly-x component of its local +X = its Right-plane normal → 90°); `_mate`'s
flip-recovery resolves the sign and the OFFSET handle (the arm origin sits on the
spin axis) verifies the rest pose. A distance driver only works ~90° off
dead-centre (the old horizontal arm); never pin a revolute at its dead-centre
with one. See [[tube-column-od-rederive]] for that build session.

Repo already has working probes for this exact pattern:
`cad/scripts/diagnostics/probe_drivetrain_error.py` and `probe_live_drivetrain.py`
(GetWhatsWrong + GetErrorCode2), and `_add_wire1_gear` / cam-perturb in the
motion-study scripts handle pose/alignment-dependent gear over-defines.

Related: [[channel-amplitude-state]], [[build-gdi-session-accumulation]],
[[sw-recovery-dialog]], [[solidworks-modeling-pitfalls]],
[[fix-relations-last-resort]].
