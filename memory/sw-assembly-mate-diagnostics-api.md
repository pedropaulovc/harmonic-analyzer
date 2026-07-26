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

**GetWhatsWrong works FINE mid-build — an earlier "it is BLIND mid-build"
entry here was WRONG and has been deleted (2026-07-25).** That verdict came
from calling it with byref VARIANTs on an early-bound extension, where the outs
ride the return tuple and the byrefs stay empty — it reported zero entries
because the data went somewhere else, not because SolidWorks had none. An A/B
against the walk proved equivalence in-build. Call it as the makepy wrapper
declares it (no args, consume the tuple) and it is live immediately, like
`IFeature::GetErrorCode2`. Cost is all TRAVERSAL: walking MateGroup's 104
subfeatures measured
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

Same `[out]`-param trap as `GetWhatsWrong` (see the rule below). Traps
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

**The `[out]`-param trap — ONE rule: go through makepy, read the tuple.** This
bit five times in one session, so state the rule positively rather than
cataloguing victims. 542 SolidWorks methods have at least one `[out]` param
(derivable from the generated wrapper: an `_ApplyTypes_` argspec entry whose
flags have bit 2, `PARAMFLAG_FOUT`). **makepy already handles all of them
uniformly** — the generated method defaults every out to `pythoncom.Missing`
and returns them in the RETURN TUPLE:

```python
def GetWhatsWrong(self, Features=pythoncom.Missing, ErrorCodes=..., Warnings=...):
    return self._ApplyTypes_(186, 1, (11,0), ((16396,2),(16396,2),(16396,2)), ...)
```

Call with no out args, unpack the tuple — `GetWhatsWrong` → `(ok, feats, codes,
warns)`, `GetErrorMessages` → `(count, msgs, ids, types)`, `OpenDoc6` →
`(doc, errors, warnings)`, `GetErrorCode2` → `(code, is_warning)`
(`int(result)` crashes on it). Never pass byref VARIANTs to a generated
wrapper: they defeat the `Missing` defaults, stay unwritten, and `.value is
None` then reads as "no errors" — a SILENT wrong answer, which is what makes
this trap expensive.

The trap only exists where code LEAVES the makepy path, and every such place is
ours, not SolidWorks': `_common._early_bound` swallows failure and returns the
raw dispatch (`except Exception: return obj`); `sw_type_info.early_bound_or_flag`
returns the object unwrapped-but-flagged when no typed class resolves; and the
standalone probes in `cad/scripts/diagnostics/` use `GetObject`/`Dispatch`
directly, so they are dynamic and genuinely DO need byrefs — which is exactly why
a probe that works standalone can come back empty in-build. Root-cause fix
(analysed 2026-07-25, IMPLEMENTED on `fix/out-param-trap`): `_early_bound` now
RAISES instead of falling back, its `*method_names` param is gone, and
`test_out_param_binding.py` (in `recipe_tests`) bans `VT_BYREF` on the build
path and forces every late-bound diagnostic to carry a `LATE-BOUND PROBE`
marker. Do NOT write a dual-mode `call_outs()` helper — that makes the broken
mode permanent. See [[no-untested-failure-assumptions]].

**The typelib is the OFFLINE authority on any method's out-param shape.** When
you need to know what a call returns without booting SolidWorks or guessing,
read the registered type library — `pythoncom.LoadRegTypeLib(SW_TLB_IID, 34, 0, 0)`
(major 34 = SW 2026), find the interface via `GetDocumentation(i)[0]`, then
`GetFuncDesc` → `fd.rettype[0]` for the return VT and `fd.args[n][1]` for each
param's PARAMFLAG bits (1 FIN / **2 FOUT** / 8 FRETVAL); `ti.GetNames(fd.memid)`
gives `(method, *param_names)` in declaration order. makepy's return tuple is
then just `(retval, *outs_in_declaration_order)`. Worked example —
`GetErrorMessages` reads `rettype=3 (VT_I4)` with `Msgs`/`MsgIDs`/`MsgTypes` all
`vt=(26,12)` (VT_PTR→VT_VARIANT) flagged pure `FOUT`, hence
`(count, Msgs, MsgIDs, MsgTypes)` and a call taking ZERO args. Confirmed live on
the seat (`shape=tuple len=4`) — cheap enough that "typelib says X" should
always be closed out with an observation. Beats both memory and a full-build
repro: it took seconds where an assembly-level repro could not even reach the
code path.

**Not every wrong-mate state reaches the error-prose path.** Trying to
manufacture a `swFeatureError_e 47` by inverting a mate's dimension flip
(`build_channel_assembly` J1a) does NOT work: the mate still SOLVES, just on the
wrong side, so the deterministic flip-seed guard raises first
(`flip-seed MISS … off by 7.06 mm, error=0`) and `_cwm.mate_error_prose` never
runs. An unsolved-mate repro needs a geometrically IMPOSSIBLE mate, not a
mirrored one.

Also `FeatureByName` is declared on `IAssemblyDoc`, not `IModelDoc2` (same
dispatch), and `IMate2` has no feature/error accessor at all — you cannot get an
error code from `IComponent2::GetMates`, only from the mate FEATURE.

**"A bare `ext.GetWhatsWrong()` raises — you must pass byrefs" was FOLKLORE,
now deleted (2026-07-25).** It holds ONLY on a late-bound dispatch (a
`GetObject`/`Dispatch` probe). Through the makepy wrapper the bare call is the
CORRECT form and the byrefs are the bug — see the `[out]`-param rule above. This
entry survived untested for months and is what sent a whole session chasing a
non-existent "GetWhatsWrong is blind mid-build" defect: a specific, confident,
un-repro'd claim is a hypothesis wearing a fact's clothes.

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
