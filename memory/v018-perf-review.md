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
