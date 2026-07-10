---
name: v018-perf-review
description: 2026-07-09 holistic perf review of v0.18.0 release logs (~4h serial seat) — ranked findings, ~80 min reclaimable; flag-storm re-regression + non-incremental release export are the top levers
metadata:
  type: project
---

Profiled the v0.18.0 `-logs.zip` (126 task logs, ~14,367s serial COM seat) + 3-agent code inspection.
Extends [[checks-perf-value-audit]] + [[release-perf-incremental]]. NONE of these are implemented yet
(review only, SW seat was in use). Ranked by est. seconds saved per full release run:

1. **Release neutral export not incremental (~1,700s).** `cut_release.export_neutral` re-rendered
   99/108 docs with only 2 changed parts: (a) `_png_key` (`cut_release.py:661-676`) hashes RAW
   artefact bytes, which churn via the parent-md5 save cascade → 9/648 hits; fix = key on
   `export_models.src_digest` (recipe digest) + bump `PNG_RENDER_REV` (~700s). (b) STEP/STL are
   SaveAs3'd for all 108 docs with NO staleness branch (`cut_release.py:761-767`) — the half
   [[release-perf-incremental]] explicitly left undone (~1,000s; needs recursive child-digest
   propagation for assemblies).
2. **Flag-storm re-regression in cut/sweep profile selector (~800s, zero geometry risk).**
   `_profile_feature_names` (submodule `features.py:621`, called by cut `:1058` + sweep `:706`) and
   `_common.feature_name_by_type` (`_common.py:665-684`, backs `extrude_at_offset`) full-flag the
   IFeature interface (~100 `_FlagAsMethod` round trips) per feature per walk; the `id()`-keyed flag
   cache never hits on fresh CDispatch wrappers. Same bug class fixed in `c992057` for
   `_feature_objects`; cut/sweep path never got it. Measured cut+sweep+offset-extrude = 1,353.7s
   (21% of part-build time); counterbore cut 9.4s vs plain boss extrude 0.2s. Fix = flag only
   `GetTypeName2` + `GetNextFeature` — MUST keep `GetTypeName2` method-dispatched or cut profile
   selection silently falls back to stale `_last_sketch_name`.
3. **Ground the channel cosmetic bank (~700-800s; POLICY — reverses #110).** Springs + spring-hooks
   + bushings = 254 of channel's ~450 mates, all cosmetic (no operational DOF, positioned entirely
   by the AddComponents3 insert transform). Per-mate cost grows with assembly size (same primitive:
   0.85s early → 6.1s late; every mate ends in `EditRebuild3`, submodule `assembly.py:2392`).
   `place_components_batch` already supports `ground=True` (one FixComponent, one solve, no flips).
   Runs against [[fix-relations-last-resort]] — cosmetic/no-DOF/no-contact is the justified case,
   but Pedro decides.
4. **Build-refresh gate battery duplicates verify:soundness (~400-800s; policy).** `refresh_assembly`
   runs full health/DOF/interference unconditionally even on a proven "geometry unchanged" no-op
   (`_assembly.py:2255-2259` skips only the Save3), then soundness reopens and re-proves the same
   artefact. Same bug class as the retired `subsystems` dup. Preferred fix: skip build-refresh gates
   on a no-op refresh, keep verify's independent check.
5. **`activate Default` pays an unconditional ForceRebuild3 even when no switch happened
   (~300-400s).** `parametrics.py:402-438`; redundant with the shared `verify.rebuild` right after
   (`verify.py:672-698`); `refresh_assembly` also double-rebuilds (`_assembly.py:2328`).
6. **Feature naming is O(F²) per part (~200-300s).** `name_last_feature` re-walks the whole tree per
   rename (318s bin, 559 renames); `SketchDims.apply` double-walks. Best fix: name-at-creation — the
   adapter already holds the raw IFeature in `_resolve_feature` (`features.py:1347-1359`) and
   discards it.
7. **One shared ForceRebuild3 in the build save path (~180-200s).** DOF-necessity (resolve=True) +
   model-healthy-deep each rebuild back-to-back with nothing dirty between (`_assembly.py:1551`,
   `:1906`) — apply the same shared-resolve pattern soundness already uses.
8. **Free-DOF component walk runs 3× per open (~250s).** Identical GetComponents+GetConstrainedStatus
   walk in `assert_components_fully_defined` / `_under_constrained_components` /
   `assert_no_over_constrained`; collect `{component: status}` once. No batch-status API exists;
   proxies already cached — dedup, not multi-select, is the win.
9. **Preflight gear-mesh walk (~150s).** `_mate_group_subfeatures` walks ~150 features FORWARD with
   full IFeature flags; `_assembly.select_mates_folder` already documents the backward-from-tail
   fix. Plus gear-ratios runs on channel which has zero meshes at its level (160.7s for nothing).

Deferred/rejected: persistent COM worker (~430s connect churn, 3% of total, loses fail isolation —
[[parallel-sw-instances-investigation]] is the better throughput bet); alignment-pinion Hausdorff
52s (down-sample query points, off-seat); dropping top/iso export views (~156s, hurts the visual
merge gate); belt/chain 70s one-off (leave it).

**User-hypothesis verdicts:** "patterns instead of N features" — already done everywhere it applies
(gear teeth circular-patterned; their 7.8s/tooth-gap is finding-2 flag tax, not a missing pattern;
channel banks deliberately de-patterned after #8 flips; moving parts can't pattern — park drivers +
motion). "Multi-select then one operation" — already done where geometry permits (multi-hole
single-sketch cuts, multi-edge fillets/chamfers, AddComponents3, batch FixComponent); exhaustive
scan of all 103 build scripts found only 6 in-loop COM calls, each geometrically necessary. Mates
cannot batch (each CreateMate consumes its own selection); everything but the solve is <100ms.

Also corrected: drive-train's "export_image front 77.3s" log line is mislabeled — the cost is
`assembly_geometry_digest`'s `get_mass_properties` (exact-BREP fingerprint), render itself ~1s.

**2026-07-09 seat validation (PR #219) — measured results:**
- **Channel rebuild 1016s vs 1736s = 720s saved (41%)**, all gates green + soundness 5/5 +
  renders pixel-equivalent to v0.18.0. Bushing banks seed+pattern off the `BankZ` datum axis
  (Top∩Right) with `flip_direction=True` seeded from the probe (landed first-solve, no retry);
  springs+hooks grounded (40 comps, one AddComponents3 + one FixComponent, 16.2s vs ~679s of
  mates).
- **diag_pattern_sense**: the historic face-pick flip did NOT reproduce in isolation (10/10
  correct at n=3 AND n=20, deterministic); the axis pick is deterministic-but-+Z (5/5) and
  FlipDir1 reverses it 5/5; `D1ReverseDirection` dead late-bound (`GetDefinition` → None).
  Keep verify+retry in production — the historic flip happened in full-assembly context.
- **diag_mate_rebuild_cost**: per-mate growth attributed to **CreateMate itself** (0.43→1.32s
  across population rungs), NOT the per-mate `EditRebuild3` (0.11→0.44s); CreateMate solves
  in place (pose lands pre-rebuild, so flip read-backs don't need the rebuild); batch-defer +
  ONE closing rebuild (0.52s) is pose-identical. ⇒ mate-COUNT elimination is the lever;
  rebuild-deferral is a minor (~100-200s) follow-up.
- **CopyWithMates2 FULLY SOLVED from pywin32 (2026-07-09, 10 probe phases; Pedro pushed
  back three times on premature "dead" verdicts — see [[negative-result-positive-control]]).
  The contract: EVERY array must be its NATIVE-TYPED SAFEARRAY with raw pointers — VBA's
  exact wire shape.** The working call (scratchpad `cwm_phase_w.py` W1, session 8640c77b):
  `asm.CopyWithMates2(VARIANT(VT_ARRAY|VT_DISPATCH, [comp._oleobj_]),
  VARIANT(VT_ARRAY|VT_BOOL, repeat), VARIANT(VT_ARRAY|VT_DISPATCH, [None]*n),
  VARIANT(VT_ARRAY|VT_R8, values_m), VARIANT(VT_ARRAY|VT_BOOL, flip_align),
  VARIANT(VT_ARRAY|VT_BOOL, flip_dim), VARIANT(VT_ARRAY|VT_BOOL, lock_rot),
  VARIANT(VT_ARRAY|VT_I4, orient))` — full semantics: mates replicated as REAL features,
  per-mate `Values` re-values applied, pose solved (verified vs an in-process VBA control,
  byte-identical result). Failure ladder (all verified): `CDispatch` in the comps array →
  instant False, nothing; raw `_oleobj_` comps + plain lists elsewhere (pywin32 marshals
  lists as `VT_ARRAY|VT_VARIANT`) → component copied, mates SILENTLY DROPPED (multi-comp
  copies kept internal mates only); all-native-typed → everything works. **The return
  value LIES (False on success) — judge by mate dump + transforms.** Triangulation route:
  in-process VBA via `RunMacro2` on generated text `.swb` (module name `""` works) —
  `Dim x As Object` declarations fail EXACTLY like Python (so not a language/process gate);
  VBA bisect (asm typed/Object × comps typed/Object) fingered the typed call; comtypes
  (true `COMMETHOD` vtable call, gens sldworks TLB in ~4s) still failed with its default
  list→`VT_VARIANT`-array conversion — which pinned the gate to the ARRAY VTs, closed by
  Phase W. comtypes gotcha: cannot unpack `SAFEARRAY(VT_DISPATCH)` returns (GetComponents)
  — fetch via `GetComponentByName`. ⇒ REOPENS mate-count elimination for the moving
  channel parts AND drive-train's repeated stations (Pedro: consider both); next
  validation = pair/slice copy + throughput ladder in the native-typed shape, concentric
  mates, real channel parts. COM traps confirmed en route: bare `None` → VT_NULL 'Type
  mismatch' (`VARIANT(VT_DISPATCH, None)`); `OpenDoc6` byref outs = `VT_BYREF|VT_I4`
  VARIANTs; a part must be OPEN before `AddComponent5` inserts by path;
  `Extension.SaveAs3` Options: 1 = Silent, **2 = Copy** (doc stays unsaved — silent no-op
  trap); gen_py wrapper loads via `GetModuleForTypelib` (fast, no regen) —
  `sw_type_info.early_bound` safe, in-process `EnsureModule` still forbidden;
  `RunMacro2(path.swb, "", "main", 0, byref_i4())` = general in-process escape hatch.
- Environment note: one SW crash during the first soundness attempt (wedged at
  `channel.SLDASM [Viewing]`, Responding=False); Pedro disabled ENHANCED GRAPHICS and the
  re-run passed — suspect that setting, not the model.

**2026-07-09 round 2 (PR #220) — CopyWithMates2 validated on the REAL channel chain.**
`diag_copy_with_mates` (ladder, real pivot-bushing on pivot-shaft) and
`diag_copy_with_mates_slice` (whole 4-part rocker+rod+bar+lever chain, 12 hard-pinned
mates, one call per station) both PASS. The full multi-component contract, all measured:
1. **`Values`/flip slots enumerate EXTERNAL mates ONLY** (mates referencing an entity
   outside the copied set), tree-ordered among themselves (slice: J1c=0, J1a=1, J1s=2,
   J2s=3, J4c=4, footX=5). Extra array entries are ignored (arrays may be sized to all
   mates).
2. **Internal mates inherit** — mates between copied components are re-bound to the
   copies and KEEP their dims (sentinel calibration left J2a/J5 untouched). No slot, no
   value, no flip for them.
3. **Every external dim slot must carry its REAL value** — a 0.0 re-values the copied
   dim to zero (first ladder run: all copies at Z=0; first slice run: rod ring yanked
   onto the Right Plane, drift exactly the 54.474 dim).
4. **On the Repeat=True path a re-valued dim's FlipDimension RESETS to False — the seed's
   state is not inherited AND the FlipDimension array entry is IGNORED** (three encodings
   tried: all-False, tree-order bits, the seed's authored flip at the discovered slot —
   identical mirrored landing every time; ladder Q5: both bits land a +20 target at −20;
   positive control: editing the same property on the copied mate post-hoc works). The
   array's flip evidently serves only the Repeat=False/new-entity path — matches the UI
   doc, where "Flip Mate Alignment" belongs to "New Entity to Mate to". The rod spin
   (seed flip=True) therefore copies mirrored (drift exactly 2×54.474), and a
   SetTransformAndSolve3 to the right pose just snaps back (the mate pins the side).
   **Repair that works:** `IFeature.GetDefinition` → `IDistanceMateFeatureData
   .FlipDimension = not cur` → `ModifyDefinition(data, model, VARIANT(VT_DISPATCH,
   None))` → rebuild; heals to rot 1e-16. Bare `None` third arg = VT_NULL → the call
   returns False and silently does nothing (same trap family as OpenDoc6/CopyWithMates2
   arrays). **Avoidance (Pedro 2026-07-09: parts must land upright from the start, the
   mirrored branch is the OLD drive-train side):** (a) the production `free` build's
   slice has NO spin dims at all — they are deferred park drivers — and its only external
   dim (rocker axial, flip=False, always-positive ladder) copies right natively, so the
   flip problem evaporates there; (b) where a pinned dim must be copied (`locked`),
   formulate the seed dim so the WANTED side is the False side — **VALIDATED: the
   authored flip state follows the REFERENCE-PLANE choice, not entity order** (rod
   spin: axis↔Right and Right↔axis both author upright as flip=True; axis↔Top authors
   upright as flip=False → copies land upright natively, rod rot 2e-16, repair pass
   0.0s). The probe's formulation search (author → read FlipDimension → delete + try
   next candidate) finds the False-side form in one seed pass; (c)
   ModifyDefinition-set-after-copy stays as the ~1s/copy fallback. Also: the slot
   mapping needs NO calibration copy — it is computed rule-based from the seed's own
   mate list (external mates in tree order); the sentinel calibration (which flashes
   No-Solution states at 1000+mm dims — Pedro flagged the UI drama) is now the opt-in
   `--calibrate` cross-check only.
5. **Anchor one-sided** — a copy lands on the SEED's side of a re-valued distance, so
   stations must not cross the anchor (channel: anchor the rocker axial to the
   gap-1 bushing at PITCH/2 + k·PITCH, not the Front datum whose stations cross zero).
6. **Calibration-copy technique** (how the slot mapping was discovered, reusable):
   one copy with a distinct sentinel per slot, classify each copied dim by its mated
   components (`IMate2.MateEntity(i).ReferenceComponent`; a root plane's owner is the
   assembly DOC name, e.g. "Assem50" — not empty), read which sentinel it holds → slot;
   delete the calibration copy. Robust against any enumeration rule.
7. **Timing (throwaway assembly, population ~20 comps):** seed chain 12 mates =
   12–20s; slice copy = 0.92–1.47s/station; ladder copy 0.65s vs 4.4s production seat.
   ⇒ channel rework: 18 stations × ~12 mates of CreateMate (~400–700s) collapse to
   ~1.2s/station + flip-set + ONE closing rebuild. Next: production rework of
   build_channel_assembly's moving loop + drive-train's cone-gear ladder on this recipe.

**2026-07-09 round 3 — SHIPPED in build_channel_assembly (`_cwm.py`; channel 20ch
standalone 418s vs ~1016s baseline, soundness 5/5, pose ledger 128/128).** New facts
the FREE (no spin dims) slice forced, all measured on the seat:

1. **Free-DOF copies carry a solver-state ATTRACTOR.** A copied chain whose operational
   DOF are free lands parked at a solver-chosen pose, and EVERY later solve returns it
   to one deterministic wrong pose from ANY start — even though the copied mates are
   value/flip/alignment-identical to the seed's (IMate2 dump) and satisfied at the
   design pose. Raw `Transform2` puts land all 4 parts exactly and the next
   EditRebuild3 reverts them; `SetTransformAndSolve3` with the whole chain already
   consistent at target reverts identically (the yank is NOT sibling inconsistency).
   The solver re-solves copied chains from the mates' stored state, not from current
   positions. Authored chains never show this: inserted at pose, solved at pose.
2. **Driver-only landing picks the WRONG BRANCH.** Authoring the 3 transient drive
   mates from the attractor pose solves each to the NEAREST solution branch: the
   channel lever solved to the MIRROR intersection of its two J3 pin circles
   (fulcrum-R127 x foot-R806.45; verified numerically — observed pin = design pin
   reflected across the fulcrum->foot line), leaving ~1 mm residuals everywhere and a
   false 'flip-seed MISS (off by 0.98 mm)'. A spin driver pins ONE coordinate, so it
   cannot disambiguate the two branches by itself.
3. **The landing recipe that works (production `_cwm` + build_channel_assembly):**
   PUT the whole chain at the design pose (branch selection) -> author the 3 transient
   drivers rocker-spin/bar-foot-X/rod-swing, RE-PUTTING the chain before each add
   (every add re-seats the still-free siblings) -> delete the drivers -> ONE closing
   EditRebuild3. The driven solves rewrite the stored state, so the freed DOF then
   HOLD the design pose through ForceRebuild3/gates/save like an authored channel.
   ~5s/copy + ~1.2s CopyWithMates2 vs 13-17s authored.
4. **J3 amplitude flip: the sign rule is already correct** (flip=False for the
   positive foot-X) — do NOT add 'bar AMPLITUDE drive foot X= . (amp + . )' to
   `_FLIP_INVERT`; tried, lands the bar at -72.9 (146 mm off). The 0.98 mm 'MISS' was
   fact 2, not a side flip. (Sub-mm 'flip MISS' reports = unconverged solve, not flip.)
5. **The MateGroup tree walk is ~20 s per pass on the real channel assembly**
   (`_mate_group_subfeatures` walks EVERY top-level feature with per-feature flagging;
   per-copy snapshots are unaffordable). Cheap replacements: `IComponent2::GetMates`
   (one call per component — the API docs' own remedy; counts + `IMate2`
   Type/Flipped/DisplayDimension2 dims), `GetConstrainedStatus` (2=under, 4=over,
   5/6=no/invalid solution) as the per-copy mate-health read, and `component_names`
   (0.2 s). The tree walk survives ONLY in the once-per-seed slot audit.
6. **Validation that sticks** (CopyWithMates2's return LIES): per-copy component-name
   diff; post-rebuild `assert_component_placed` vs seed-pose-translated targets;
   per-part GetMates count == seed's; per-part constrained status == under;
   `reledger_to_solved` so the final pose-ledger sweep covers copies; DOF specs
   recorded on the copies via the same driver helpers (labels VERBATIM like the
   authored path so `_flip_sig` signatures match).

**2026-07-09 round-3 addendum — the attractor resists minimal reproduction
(`diagnostics/diag_cwm_attractor.py`, 3 seat runs):** a 3-phase isolated repro
(rocker-on-shaft single; +rod open chain; +ring-X root-plane closer = CLOSED
loop, the production J3 idiom) copied each slice 3x and landed one copy per
strategy. All NINE cells HOLD through EditRebuild3 — including bare
`Transform2` put-only on the closed loop. So fact 1's put-reversion is an
EMERGENT property of the production channel slice (mirrored/rotated seed
transforms, coincident-PLANE axial mates, the 4-part multi-loop, ~100-component
context), not of CopyWithMates2 + free DOF per se; the put+driver landing
stays justified by the production-scale measurements (runs 3-4), and any
future ladder must validate on its REAL slice, not a toy. What DOES reproduce
at every scale is the parked-pose wander: each copy parks spun ~9deg off the
seed, deterministically. Two positive findings: (a) **IDragOperator**
(`GetDragOperator` -> AddComponent/BeginDrag/Drag(absolute)/EndDrag,
TransformType=2, DragMode=0, UseAbsoluteTransform=True — the UI Move
Components solver path, "reuses the solver") lands copies in ~0.2s/part vs
~0.8s per authored driver mate and survives the rebuild in all repro phases —
the candidate cheap landing for the drive-train cone-gear ladder, pending
real-slice validation. (b) The UI-vs-API mystery is WORKFLOW, not solver
magic: every vendor demo (GoEngineer pT3GPqMmAWk, Visiativ ToiXLdm7ncs
transcripts; thecadcoder prerequisite "both components fully constraint")
copies a FULLY-DEFINED seed — the UI path never exercises under-constrained
copies at all.

**2026-07-09 minimal wander repro (`diagnostics/diag_cwm_min.py`, standalone
pywin32, vendor-ticket grade):** the CopyWithMates2 parked-pose wander needs
NOTHING: one part with ZERO features (default planes only), TWO root-plane
mates (coincident Top + distance Front; in-plane slide + spin free), one
Repeat copy with the dim slot re-valued -> the copy lands at the right
distance but parked 8.5 mm off along the free in-plane direction (seed sat
exact). The --visible one-extrude variant adds a SECOND divergence flavor:
the copied dim resolves on a DIFFERENT side than the seed's authored mate
(z -45 measured vs -50 seed-derived; the seed's dim carries a -5 body-side
offset the copy loses) -- the flip/side family at minimal scale. A raw
Transform2 put heals the free directions and HOLDS through EditRebuild3
(the put-reversion attractor stays exclusive to the big multi-loop
assembly). Standalone COM traps re-confirmed: SelectByID2's Callout and
ModifyDefinition's third arg need typed VT_DISPATCH nulls (bare None =
VT_NULL 'Type mismatch'); IModelDoc2::SaveAs3 returns 0 ON SUCCESS (gate on
file existence); a crashed run's open doc holds the .SLDPRT file lock
(CloseDoc by basename before deleting).
