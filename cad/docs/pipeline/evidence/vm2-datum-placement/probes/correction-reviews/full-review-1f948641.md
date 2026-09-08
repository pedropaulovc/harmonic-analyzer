# Independent full committed-diff review: 1f948641

Verdict: **one outstanding offline contract failure; not clean**. Evidence-byte checks found no mismatch. This is not native acceptance, a green full build, or an external CodeRabbit approval.

Reviewed PR #702 base `55056d4990d38ebb461f343d3002fc90731b9e73` against frozen head `1f948641ddb9418a43351d6051424fc18e3191b7`. The reviewer authored none of the implementation. Review used pinned Git blobs, not the working-tree source or the concurrently running native session. No COM calls, production edits, Git head changes, or merges were performed.

## Findings and disposition

### P2: The inline finish renderer violates the existing drawing-purity gate

Location: `cad/scripts/draw_rack_pinion.py:119` and line 145, the two `f"Ra {control.roughness_ra}"` expressions. The existing fleet test in `test_drawing_specification_purity.py` rejects drawing-owned manufacturing string rendering, including this f-string form. The parent's full offline recipe run exposed this failure at the reviewed head (one failure, 1,503 passes in 70.00 s); native production had not started. The complete local log is `cad/out/reports/datum-placement/correction-offline-gates.log`; this reviewer read its exact failing locations and result. Reading the pinned purity test independently confirms that this is an existing deliberate contract, not an assertion to relax.

Move the exact finish-rendering implementation into a narrowly imported renderer while the recipe retains placement and passes the existing part-owned control. Preserve the semantic selection, rebuild, attachment, endpoint, and manufacturing checks. Do not change the purity rule or source manufacturing specifications. A later implementation proposal is outside this frozen-head verdict until reviewed.

### Closed: Shared rack selector-count regression

One definite regression was found while reviewing the preceding frozen head `b4abb34fdd01a63d42f0c74c60a53da04e4245d6`: the rack branch of `test_bore_annotations_use_explicit_nonconflicting_selectors` still required two `entity=bore_edge` occurrences, although the new finish insertion helper left one. A pure Git-byte count reproduced the mismatch without importing the application or running tests. This would fail the shared offline drawing contract.

The final head fixes that rack-only assertion: it requires one datum keyword occurrence, the `_add_bore_finish(adapter, front, bore_edge)` call, and the explicit `IEntity.Select4(False, data)` call. All other gear branches and the rack manufacturing, radius, shoulder, and stability checks remain intact. The final source satisfies those three literal assertions. This finding is closed for the reviewed head.

The only other `b4abb34f..1f948641` change is in the diagnostic finish-control closure: it now uses names from the verified inventory and re-enumerates current paths before each close. A source document implicitly unloaded by closing its drawing is recorded as `already_unloaded`; its disconnected proxy is no longer dereferenced. This fixes the reported closure failure without changing either production drawing recipe, the datum helper, or the lifecycle runner. The change was statically reviewed; its implicit-unload behavior was not executed by this reviewer.

## Previous full-review findings

The three findings recorded at `66e5d88e` were rechecked against the complete final diff:

1. **Rack finish route:** the production recipe no longer repositions or reattaches an existing symbol. `_add_bore_finish` validates the part-owned finish face, activates the exact front view, creates view-scoped selection data, selects the already-resolved bore edge, and requires one selected object with strict native equality. It inserts a new machining-required symbol immediately after that selection. Both rebuild results are checked. It verifies roughness and optional production-method readbacks, exact finish inventory, one non-dangling edge attachment, strict equality, one finite leader, and the actual endpoint within `1e-8 m` of the projected right-rim XY. No endpoint, annotation-position, or reattachment setter remains in this function. The 20/100 micrometre datum limits and manufacturing values are unchanged.
2. **Production datum/diameter clearance:** every production `observe` call now checkpoints the raw primitive row and invokes `assert_production_diameter_clearance` before the rack finish comparison. The helper calls the existing `assert_clearance`, retaining the 1 mm separation and current-anchor checks. Cold open, moved, scaled, restored, and second cold open all use this path. The new regression cases include the recorded original overlap, all five recorded cold stages for both drawings, absent ink, stale moved ink, and explicit partial/production mode separation. The analyzer CLI still prints measurements only; it is not represented as the enforcing gate.
3. **Historical notices:** both `probe-results.md` and `finish-attachment-control.md` now explicitly identify their historical scope and link the later persistence failure. Their original observations remain unchanged. The later failure is not silently converted to a pass.

The fresh-insertion control supports the replacement call sequence, not final-head acceptance. Its new symbol retained endpoint `(0.222499999953, 0.175, 0.0015)` metres at insertion, both rebuilds, and cold reopen; each of those observations has one edge attachment, `IsSame == 1`, and no dangling state. The cold-reopened styled symbol reads `Ra 1.6`. Intermediate `read_rack_finish` roughness fields are empty in this raw control, so this review does not claim that those intermediate text readbacks proved the roughness. The production implementation separately requires its direct `GetText(8)` readback after the styled rebuild.

## Full source scope

The complete diff contains **363 files: 21 Python source/test files and 342 documentation/evidence files**. This was a full-diff review, not merely the final two-file delta. Every added runtime function and changed production/test hunk was reviewed in context. All 21 Python blobs, totaling **5,852 final-head lines**, were parsed without application imports and linted individually via exact Git bytes on Ruff stdin.

| Area | Reviewed files under `cad/scripts/` |
| --- | --- |
| Production | `_native_axis_datum.py`, `draw_pinion_lift_rod.py`, `draw_rack_pinion.py` |
| Diagnostic runtime | `diagnostics/analyze_vm2_datum_clearance.py`, `diagnostics/probe_vm2_datum_attachment.py`, `diagnostics/probe_vm2_datum_body_correspondence.py`, `diagnostics/probe_vm2_datum_lifecycle.py`, `diagnostics/probe_vm2_datum_ownership.py`, `diagnostics/probe_vm2_rack_finish_attachment.py`, `diagnostics/probe_vm2_rack_source_save.py`, `diagnostics/run_vm2_datum_drawings.py` |
| Diagnostic tests | `diagnostics/test_vm2_datum_clearance.py`, `diagnostics/test_vm2_datum_lifecycle.py`, `diagnostics/test_vm2_datum_ownership.py`, `diagnostics/test_vm2_datum_probe.py`, `diagnostics/test_vm2_rack_finish_attachment.py` |
| Drawing and source-save tests | `test_gear_drawing_batch_contract.py`, `test_pinion_lift_rod_drawing.py`, `test_rack_pinion_drawing.py`, `test_vm2_native_axis_drawing.py`, `test_vm2_rack_source_save.py` |

The review covered source/view/body correspondence, adjacent cylindrical geometry, strict native equality, no-op/missing attachment rejection, finite readbacks, unchanged stability boundaries, imported manufacturing dimension preservation, source-save causation, ownership and closure guards, cold-reopen provenance, translated ink, filled-triangle intersection, and explicit partial-versus-production acceptance scope.

No changes to the shared `_drawing_common.py`, adapter submodule, part geometry/configuration, templates, build graph, or protected parent integration branches are included. The narrow finish function consumes the existing part-owned control and preserves the existing face validation. SolidWorks method documentation was checked for insertion, surface-finish text assignment, leader styling, and leader-point readbacks.

## Evidence and byte audit

All **342 evidence blobs** were read as bytes from the pinned Git tree. All **13 Markdown summaries** were reviewed, including the historical review and new fresh-insertion report. Binary artifacts were checked for byte identity, not decoded through a lossy text representation.

The prior `66e5d88e` audit was not assumed to remain valid: SHA-256 was recomputed for every one of its 321 evidence paths. **319 are byte-identical**; the only two changes are the explicitly reviewed historical notices. No original raw receipt, native artifact, sidecar, or log from that set changed. The sorted UTF-8 list of `path + space + SHA256 + LF` for those 319 unchanged members hashes to:

`7a3d9dff4318336cb08b5db05a6df40a4287e16141f1b74c180a86a0bcdf1540`

The rerun completed **457 explicitly mapped SHA-256 comparisons with zero mismatches**:

- 132 manifest source hashes and 132 manifest copy hashes; all 132 recorded sizes also match.
- 130 semantic identity-sidecar hashes and their stored payloads.
- 57 unique receipt/output/supersession links.
- Three original-raw Markdown table links.
- Three fresh-control links: its exact probe source, saved diagnostic drawing, and ownership receipt.

The updated-main manifest accounts for 108 parts and eight assemblies. Its 130 published identity inputs plus two closure receipts match the publication. The manifest still declares the two absent non-operational DOF sidecars as missing, not passing native zero-DOF evidence.

Selected exact witnesses:

| Artifact, relative to `cad/docs/pipeline/evidence/vm2-datum-placement/` | SHA-256 |
| --- | --- |
| `raw/candidate-2d-datum-retry-full.log` | `a7ec86f9a83f2ff9bc7717f940e19c238a494f0352e0c613ddab89853184061f` |
| `probes/rack-production-lifecycle-372acd6e/receipt.json` | `94de73f21928ad2f707a5bbcf994037bb6fff759a95d22d3f59c888b18e56490` |
| `probes/rack-production-lifecycle-372acd6e/finish-persistent-trial.json` | `c25160bf30d218d77691c48606b84c831244f857343e77b4bd3ef627a49e0fe3` |
| `probes/rack-fresh-finish-specific-null/receipt.json` | `a73902daf9355615cef0a70d8520dd2bac73687db2b2b8281b3628d488f0550e` |
| `probes/rack-fresh-finish-specific-null/probe_vm2_rack_finish_attachment.py` | `83c67ad011d0686d92aba8e9f403aa0bbec243a45385a4b1f21fce6ea2d9bfe3` |
| `probes/rack-fresh-finish-specific-null/rack-pinion-fresh-finish.SLDDRW` | `37a4af9530885aa4c322a4e1eb3789b301950e97c76245dbd3151f6dbc6ecce8` |
| `probes/updated-main-550/manifest.json` | `2bbab87b02b55141689d0b96fae047154651ebc4a1725067d8626684fabec9b7` |

The evidence tree is byte-identical between `b4abb34f` and the final reviewed head; only the two source/test files listed above changed. Thus the independently repeated evidence audit applies to `1f948641` without treating a newer native run as already accepted.

## Verification performed and limits

- Exact-head Python AST parsing: **21/21 passed**.
- Exact-head Ruff, `--no-cache --stdin-filename <path> -`: **21/21 passed**.
- `git diff --check <base> <head> -- cad/scripts`: passed.
- The rack-specific literal contract that failed at `b4abb34f` now matches the final production source.
- No pytest suite was executed by this reviewer: the parent owns the running offline/native validation, and application imports could alter telemetry during that work. Parent-reported test results are not presented here as independently executed results.

This review does not replace CodeRabbit's requested GitHub full review. It does not label the CLI size rejection as a clean review. It does not independently validate unpublished ZIP members, unavailable historical artifacts, or every historical reference to code/COM identities; the explicit hash counts above describe only mapped, available artifacts. Archived failed and superseded receipts remain diagnostic provenance.

No SolidWorks document was opened here, and no PDF/PNG visual pass was performed during this review. Native semantics, final-head cold reopen/move/scale, readable complete prints, and source-byte preservation require the parent's actual final-head run. Text-glyph/gear overlap remains a visual gate; the line/triangle clearance functions explicitly do not prove it. First production cold open is the lifecycle baseline, not an invented pre-save witness.

Full retained-stack build, closed native snapshot, identity comparison, and exact-head zero-COM repeat remain separate integration gates on VM1's designated combined head, including the retained assembly stack. This report authorizes no merge and makes no claim that those gates have completed.
