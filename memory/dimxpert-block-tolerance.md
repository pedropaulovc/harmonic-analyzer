---
name: dimxpert-block-tolerance
description: "Title-block general tolerances (.XX ±.02in / .XXX ±.005in / ±1°): TOL_* custom props + DimXpert doc props; decimals/angular prefs are GET-ONLY on R2026x — angular must be fixed in the seat's part template"
metadata:
  type: project
---

Title-block general tolerances (chosen 2026-07-13: `.XX ±.02 in`, `.XXX ±.005 in`, angles `±1°` — the loose/general-fab US trio, right for a manually machined replica).

- **Source of truth:** `cad/config/title_block.yaml` (display strings + numeric values — its OWN file, split from tolerances.yaml so a title-block edit never FULL-rebuilds the fit readers drive_train/paper_drive). Accessor `_config.title_block(kind)` → dynamic buildgraph token → every part deps `title_block.yaml`.
- **Drawing side:** every part carries custom properties `TOL_LIN_XX` / `TOL_LIN_XXX` / `TOL_ANG` / `TOL_SURFACE` (display strings — surface is `125 µin`, Ra machined finish; stamped by `_common.part_properties`); the `.drwdot` title block reads them via `$PRPSHEET:"TOL_LIN_XX"` etc. (Pedro maintains the template.) `$PRPSHEET` pastes verbatim — store machinist-formatted strings (`±.02`), not bare numbers.
- **Part side:** `_common.apply_block_tolerances` (called in `save_part_and_images`) stamps DimXpert block-tolerance doc props: method=Block (pref 637), Tol1/Tol2 values (prefs 123/124, **meters**). Raises if a settable write is rejected.
- **API limitation (probe-verified 2026-07-13, repro: `cad/scripts/diagnostics/probe_block_tolerance.py`):** on 3DEXPERIENCE R2026x the decimals prefs (405/406) and angular value (126, radians) **reject all writes** (False under both int encodings × options 0–3 × pre/post ForceRebuild3 × saved doc) despite help.solidworks.com/…/DP_DimXpert.htm documenting them settable. Positive control: 637/123/124 set fine with identical call shapes → not a marshaling issue. Untested deltas: other SW versions, VBA path.
- **Why it still works:** template defaults already carry decimals 2/3/4 for Tol1/2/3 — exactly the `.xx`/`.xxx` split. Only the angular value (default 0.01°) is wrong vs ±1° and can ONLY be fixed by hand in the seat's default part template (`.prtdot`). **The template is a hard seat prerequisite:** `apply_block_tolerances` RAISES on get-only-pref drift (Codex: a warn would let a drifted seat publish metadata-stale parts into the shared remote cache under the same key — template state is not a cache-key input). Every part build on a seat fails until that seat's default `.prtdot` carries angular ±1°.
- The DimXpert doc props are dormant MBD metadata here (no DimXpert annotations are authored); the machinist-facing truth is the title-block note fed by the TOL_* props. See [[fastener-policy-us-customary]], [[part-d-custom-properties]].
- **Units decision (2026-07-13, PR #289):** generated drawings migrate mm → **inch display** (issue #290) to match the inch title block + UNC policy; until then the mm drawings are unaffected (nothing reads TOL_* yet). `title_block` is a DYNAMIC buildgraph token narrowed like `parts/*` — non-stamping assemblies drop the tolerances.yaml dep (no FULL rebuild on a title-block edit).
