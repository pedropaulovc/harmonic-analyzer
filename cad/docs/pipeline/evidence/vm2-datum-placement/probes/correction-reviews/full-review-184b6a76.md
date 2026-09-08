# Independent full committed-diff review: 184b6a76

Verdict: **no outstanding actionable code or evidence-consistency findings in the reviewed diff**. Native validation and external review remain separate; this is not a full-build or manufacturing-acceptance verdict.

PR #702 baseline: `55056d4990d38ebb461f343d3002fc90731b9e73`.
Frozen reviewed head: `184b6a76dec231bba38dc7fe5d0e28a5fd236953`.

The reviewer authored none of the implementation. The review covers the complete baseline-to-head diff, using the prior full review at `1f948641ddb9418a43351d6051424fc18e3191b7`, explicit byte-identity verification of its unchanged coverage, and review of every subsequent change. It is not a delta-only verdict presented as a full review. All source inspection and lint input came from pinned Git blobs. No production files, Git heads, or COM state were changed. Only this report was written.

## Scope and verification

The full diff contains **368 files: 22 Python source/test files and 346 documentation/evidence files**. All 22 final-head Python blobs, totaling **5,872 lines**, were parsed without application imports and linted individually with Ruff on exact Git bytes via stdin. Both checks passed for every file. `git diff --check <baseline> <head> -- cad/scripts` also passed.

The full source review covers:

- Production: `_native_axis_datum.py`, `_rack_bore_finish.py`, and both drawing recipes.
- Diagnostics: attachment experiments, source/body correspondence, lifecycle and ink clearance, ownership/closure, rack finish insertion controls, source-save causation, and the two-drawing receipt wrapper.
- Tests: native datum behavior, both drawing contracts, the shared gear contract, geometry/clearance and lifecycle guards, CLI/ownership rejection, and recorded source-save causation.

The complete prior review examined all added runtime functions and changed production/test hunks, not just the finish fix. It covered source/view/body correspondence, adjacent cylinders, strict native equality, no-op/missing attachment rejection, finite readbacks, unchanged stability boundaries, imported manufacturing dimensions, source-write causation, owned closure, cold-reopen provenance, translated primitives, filled-triangle intersection, and partial-versus-production scope. The final extraction and its affected tests/wrapper were then reviewed in full.

Of the prior head's 363 changed files, **359 remain byte-identical**: all 342 evidence files and 17 source/test files. Four source/test files changed, and five files were added. This was checked by reading both versions with `git cat-file --batch` and comparing their bytes, not by assuming unchanged filenames imply unchanged content. The sorted UTF-8 `path + space + SHA256 + LF` list of those 359 unchanged members hashes to:

`25ebb69c319a25ba71b0d5e16813e48c95e81f55ca737786a7562de1512c5428`

## Findings resolved

### Drawing-purity failure at 1f948641

The prior full offline recipe run rejected two `f"Ra {control.roughness_ra}"` expressions in the drawing recipe. The new head moves their renderer, with its associated semantic attachment checks, into `_rack_bore_finish.py`. The drawing recipe retains `BORE_FINISH_POSITION` and passes that position explicitly. The renderer imports the existing part-owned `SURFACE_FINISHES`, bore diameter, and face width; it introduces no manufacturing values or alternative specifications.

An independent AST comparison confirms that the extracted function body is **identical** to the reviewed inline body after renaming only the layout reference `BORE_FINISH_POSITION` to the `symbol_xy` parameter. The signature/function name and module imports changed as expected. Selection, both rebuilds, roughness/production-method readbacks, inventory, strict attachment identity, dangling checks, and the actual endpoint check are therefore preserved, not approximated in the extraction.

The drawing-purity analyzer and its tests are unchanged. `_drawing_common.py` and `rack_pinion_spec.py` also retain their exact prior Git blobs. The rack tests now exercise the extracted implementation directly and verify that it consumes the actual specification objects. The shared gear contract follows the imported helper to verify explicit `Select4`; the other gear branches and manufacturing assertions remain intact. The old purity failure is preserved in a newly committed raw log, not hidden by changing the gate.

The receipt wrapper now hashes `_rack_bore_finish.py` before and after its normal drawing run, along with both recipes, the datum helper, and the general drawing helper. Moving the implementation therefore does not remove it from the wrapper's monitored runtime inputs.

### Earlier selector-count and closure failures

The stale expectation of two `entity=bore_edge` spellings remains corrected: the rack contract requires the one native-datum keyword occurrence plus the actual finish-renderer call and its explicit semantic selection. No manufacturing assertion was removed to fix that count.

The finish-control closure still uses names from the verified inventory and current document enumeration, avoiding dereferencing a source handle after its drawing implicitly unloads it. New evidence preserves the original disconnected-proxy failure and the subsequent independent empty-seat inventory. The failed close is not labeled successful.

### Earlier route, clearance, and provenance findings

The replacement finish insertion is still performed immediately after view-scoped selection of the resolved bore edge. It requires exact selection identity, one inserted finish annotation, one non-dangling semantic edge attachment, unchanged manufacturing readbacks, and an actual post-rebuild right-rim endpoint within `1e-8 m`. It contains no endpoint, symbol-position, or reattachment setter. Its native diagnostic positive control retained the right-rim endpoint through both rebuilds and cold reopen.

The native-axis helper still validates the exact source part and sole solid body, drawing-to-source-to-drawing correspondence, intended circular/cylindrical axis, two distinct adjacent faces, native insertion inventory, label/shoulder, and stable finite XY. The original 20/100 micrometre limits remain native-position stability bounds under the explicitly approved contract; no old requested-XY accuracy claim is made.

Production lifecycle observation still enforces datum-versus-diameter clearance at every cold stage, before the rack finish-versus-datum gate. Recorded original-overlap, current cold-stage, missing-ink, and stale-ink regression cases remain intact. The analyzer CLI is observational; the lifecycle helper is the threshold-enforcing path.

The two historical report notices remain intact and point to the later persistence failure. Superseded stale-ink receipts and failed native trials are not counted as acceptance.

## Evidence audit

All 346 final evidence blobs were read as bytes. The prior 13 Markdown summaries and all prior binary/hash coverage carry forward through the exact byte comparison above. The four new evidence files were inspected: the previous offline failure log, pre-close ownership, failed closure, and subsequent empty-seat inventory.

The prior **457 explicitly mapped SHA-256 comparisons** remain valid because all 342 associated evidence blobs are byte-identical. Their coverage is 132 manifest source hashes, 132 copy hashes, 130 semantic sidecar hashes/payloads, 57 receipt/output/supersession links, three raw Markdown links, and three fresh-control artifact links. All 132 manifest sizes were checked in that audit. A further comparison verified the new failed-closure receipt's `ownership_sha256` against the committed ownership receipt, giving **458 covered comparisons, zero mismatches**. This count is not a claim that every historical absolute-path reference has a published counterpart.

The updated-main baseline remains 108 parts/eight assemblies with 130 identity inputs plus two closure receipts. It is not candidate geometry or full-stack acceptance. The earlier 319 original evidence blobs unchanged from `66e5d88e` remain unchanged here as well; only the two explicitly reviewed historical notices changed in that transition.

New evidence SHA-256 values, relative to `cad/docs/pipeline/evidence/vm2-datum-placement/probes/`:

| File | SHA-256 |
| --- | --- |
| `offline-1f948641-failure.log` | `7d94f91ac5e9058ec04f3287123c5eaa6ccbb409d25b7e1458707df6431ea9a0` |
| `production-b4abb34f-closure/ownership.json` | `22b866080f41cfcb29c4efd37b582540642aff4e89a258bd2196bde024e85841` |
| `production-b4abb34f-closure/closed.json` | `c441c734c50a401105dc1fbf91daaf5adbd4d22017d17914e93a33ac217684b9` |
| `production-b4abb34f-closure/after-failure.json` | `3a6fc31a79ee012053a06c416290b89431c1e10d6e83c7973150f7d65cbfe4d4` |

Final changed runtime byte hashes:

| File under `cad/scripts/` | SHA-256 |
| --- | --- |
| `_rack_bore_finish.py` | `16de2a0623c6f5100d50f018b0f64a7be98b07beb20b68b36356ecd76e106950` |
| `draw_rack_pinion.py` | `f06f71c7db6fe7a9f1cb500ba5aa2accc3d53c2703e0025b035d080d572b0b37` |
| `diagnostics/run_vm2_datum_drawings.py` | `1529cb6b36b582c8cbaa88792275f721de0af3c913d844b0eeb423064be6a05e` |

## Limits and acceptance handoff

No pytest suite or application import was executed by this reviewer while the parent ran offline/native validation. The parent's reported focused-test success is not represented as an independently executed result. This review independently performed Git-byte comparisons, AST equivalence/parsing, Ruff, and source diff checks.

No native document was opened and no PDF/PNG visual pass was performed here. Fresh insertion on a diagnostic copy is positive-control evidence, not final-head production acceptance. In that control, the cold-reopened styled symbol reads `Ra 1.6`; intermediate roughness fields from its separate display-data reader are empty and are not counted as successful text readbacks. The production renderer directly requires `GetText(8)` after the styled rebuild; the actual final-head run must prove that requirement succeeds.

The parent must supply final-head normal drawing, cold-reopen/move/scale/restore/reopen, source-byte, and readable-print results. Text-glyph/gear overlap is still a visual gate, not something the line/triangle calculation proves. First production cold open remains the stated lifecycle baseline, with no invented pre-save witness. Native binaries were byte-checked only; unavailable historical artifacts and unpublished ZIP members were not independently verified.

This is an independent agent full-diff code/evidence review, not a CodeRabbit approval or a successful CLI review after its payload-size failure. External review remains separate. Full retained-stack build, exact identity comparison, closed snapshot, and exact-head zero-COM repeat require VM1's designated combined integration head, including the retained assembly stack. No merge is authorized by this report.
