# PR 717 Codex full-diff rereview

**Result: clean. No open actionable code findings in PR 717's own diff. Geometry equivalence is not claimed.**

| Item | Exact identity |
|---|---|
| Reviewed base | `748cf37c18bc8e1ffe65651769e42f0696f644f9` |
| Reviewed head | `2d8618ca17fdcae69c32a67b9aa0f2f23e1ecee2` |
| PR | `https://github.com/pedropaulovc/harmonic-analyzer/pull/717` |
| Full binary diff | 378,159 bytes; SHA-256 `4b58b0995a185f54e016694f7ac2215c732bdc9fbb9f0aef471c681b3690fb08` |
| Scope | 26 files; 3,491 insertions, 666 deletions; one binary drawing-template replacement |
| Adapter at base and head | `2269009ed56712867826516f4406afc98a0c2814` |
| Prior reviewed base/head | `372acd6eee51ce5950480e65c9a2c6c63ea076a2` / `64c3dab4875354a7d44d709539e001db920a0377` |
| Prior complete review | `codex-717-64c3dab4-review.md`; SHA-256 `81bfc26921917580072b3dfda256816ed9482442b580ea8ae9760cedd5f2cb0c` |

Reviewer: Codex, continuing its independent full-diff review. This rereview inspected the exact Git objects, complete changed-file set, every before/after blob identity, the new document change, the prior full source review and the retained fingerprint evidence. It ran no tests or native operations and changed no tracked files. The coordinating agent's latest-head native build was active during review.

## Exact transfer of the prior review

The old and new PR diffs contain exactly the same 26 paths. All 26 base blobs are identical to their prior reviewed base blobs, including absent files. Twenty-five head blobs are identical to their prior reviewed head blobs. The sole changed head blob is `cad/docs/pipeline/assembly-granularity-integration-results.md`, whose opening historical-provenance notice was read in full. Every code, test and binary template blob therefore remains exactly the code reviewed clean at `64c3dab4`; this conclusion does not rely on commit messages, patch similarity, or filenames alone.

The old full diff SHA-256 is `340537aa15ddfb9232052cc742e61c15d86f646db8a3708f42dbc92b3da87188`. Exact old/new Git blob IDs for all 26 files, both diff hashes, adapter pins and the entire notice change are retained in `codex-717-2d8618ca-diff-proof.json`, SHA-256 `447a7f12a31e4a1fd2d7a6173d837bf7d27ef079feb76b13d859c74fc81df63e`. The new complete binary patch is retained as `codex-717-2d8618ca-full.diff`. `git diff --check` is clean.

The new opening correctly identifies the document as historical, preserves its original run SHA and historical receipts, links current closeout evidence to PR 717, and points portfolio status to the project board. It removes the stale opening assertion that historical validation is currently in progress. This conforms to the repository's historical-plan guidance and does not promote old timings or artifacts into current acceptance evidence. No actionable documentation finding remains.

## Source review disposition

The prior P1 concerning unsupported mapping-owner and keyed-field binders remains fixed. The four existing correction commits, their runtime-backed negative controls and the supported keyed-mapping positive control were re-reviewed clean in the retained report. The corrected parser and regression-test blobs are unchanged at this head. No new test invocation was necessary to determine that identity, and none was run for this rereview.

The retained full review covers the bounded source interpreter's lexical/global ordering, mutation rejection, generated-row provenance, keyed owner/field handling and unresolved-source failure contract. It also covers the config-analysis memo's syntax-only cache and conservative fallback, actual producer-edge discovery, caller/import resolution after the helper split, dependency reporter, test-path isolation and component-pattern test enrollment in `dodo.py`.

The 82 extracted function/class ASTs and 13 caller non-import ASTs audited in that review remain the same because all involved before/after blobs match exactly. The six removed false source edges, the remaining 119 actual edges, the module ownership/import checks and the addressed P1 retain their prior review disposition. AST equality is one source invariant; it is not substituted for import/global binding review or native validation.

The unchanged binary template remains the previously reviewed 87,851-byte correction, SHA-256 `2b1bbe3dfff265e8bb35ea79f0f9690f808049f5cef764cab8959c1eaee5e849`. This own-diff review does not re-review PR 702's separately accepted datum and rack-finish changes beneath the current base.

## Fingerprint uncertainty and finding assessment

The frozen candidate64 comparison found all 108 leaf input maps and recorded cache keys equal to the preserved baseline550 records, and all six operational DOF manifests byte-for-byte equal. Three of eight stored assembly geometry fingerprints match; frame, drive-train, magnifier, paper-drive and the top assembly differ. The manifests contain authored driving/rest specifications, not fresh native DOF measurements. Cross-seat raw CAD identities and execution tokens were treated separately throughout.

The fingerprint function itself is AST-identical at the compared sources. It hashes rounded mass/COM/inertia and sorted named component transforms; stored full-build hashes precede saved-copy reconciliation. The bounded cold capture subsequently reproduced seven of eight candidate stored hashes, with paper-drive differing from its own stored value. A finite 1,622-attempt signed-zero probe did not explain the five cross-seat differences or paper-drive's own mismatch. This remains unresolved evidence, not proof of equality and not proof that a particular geometry value is wrong.

The uncertainty does **not currently establish an actionable finding in this source diff**. The changed helper bodies/caller computations retain their reviewed ASTs and bindings; the actual source-input and leaf-recipe invariants hold; no dropped producer, changed geometric calculation, weakened tolerance or identity check, or incorrect native pose has been demonstrated in this change. The coordinating agent also reports the candidate64 full native health gates and assembly visual inspection passed. Those checks support the source review but do not resolve the hash differences. The remaining fingerprint investigation can be tracked separately under the user's instruction to defer pending investigation and finish separable improvements; this review does not dismiss it or prescribe an unsupported code fix.

The comparison and finite probe remain in `closeout-verification/baseline550-candidate64-comparison.md` and `closeout-verification/signed-zero-64-summary.md`, with exact input/result hashes and limitations. No further diagnosis was launched for this review.

## Gate boundary

This is a clean review of the exact own diff `748cf37c..2d8618ca`. It satisfies the source-review gate only. The full pipeline and visual gates for the latest combined head are the coordinating agent's separate responsibility; an active build is not reported here as passed. No geometric-equivalence certification, token restamping, native mutation, test rerun, or review of unrelated deferred PRs is implied.
