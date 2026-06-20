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

Related: [[temp-3channel-build-reduction]], [[build-gdi-session-accumulation]],
[[sw-document-recovery-dialog]], [[solidworks-modeling-pitfalls]],
[[fix-relations-last-resort]].
