# Assembly granularity integration evidence

This run follows `second-vm-assembly-granularity-integration.md` at
`29c6ec1eea9456cc7403cab8e5e6c3fb4df02979`. Validation is in progress;
no historical #677 timing or native artifact is used as new acceptance.
VM1 owns integration and merging. Portfolio status belongs on the
[project board](https://github.com/users/pedropaulovc/projects/1).

## Inputs and extraction

- Main: `c6ab57dbdf73a733b32fb580bada81dab7fd758c`, re-fetched before baseline.
- Adapter: `2269009ed56712867826516f4406afc98a0c2814`, unchanged from main.
- Parser branch: `perf/assembly-source-dependencies-isolated`, PR #686.
- Child branch: `perf/assembly-granularity-isolated`.
- Child PR: #687, targeting #686. Both were marked ready before tests.
- Native checkout: `C:/src/ha-assembly-granularity-integration`.
- Code-only checkout: `C:/src/ha-assembly-granularity-staging`.

Both checkouts have their own `uv sync --frozen` environment and initialized
submodules. The native checkout builds a same-main baseline while code extraction
runs in the other checkout; its Python, configuration and adapter inputs stay
frozen. No native outputs, freshness ledger, token, gate stamp or environment
were borrowed from another experiment.

Parser commits were extracted in order: `ac8d9035`, `592629bb`, `e2d3af8b`,
`d35c50ef`. The helper split follows `62cc4d79`, `840b0a42`, `aff115c4`.
The recipe-test conflict was resolved by importing only the helper fixture and
mutation cases, excluding the drawing parent's `_channel_pose` regression.
No `_channel_pose.py` or `_cwm.py` change is part of this stack.

The read-only comparison found 82 unchanged definition ASTs and 13
import-only callers. Fresh source-contract and key-mutation checks passed as
recorded below. Neither helper body changes nor the withdrawn #678
mass-read optimization are part of this extraction.

## Receipts so far

The reporter was copied locally from `aff115c4` before its introducing commit.
Its SHA-256 is
`9cbab71ad608397b57bdc2a5f47d389d9e0e5d33be67ab9be6050607bda8035a`.
Each report records production recipes/task keys for eight assemblies and 108
leaf parts without COM or cache transfers. Its untracked presence is disclosed.

| Report | SHA-256 |
|---|---|
| Native checkout `cad/out/reports/assembly-granularity-integration/main.json` | `77369ea71ba99d4edd436cc9f493715b36ce744967720a03d216925c7f9514aa` |
| Code checkout `cad/out/reports/assembly-granularity-integration/parser-only.json` | `77b3e6c0b531637455d36a163201d1f7a2514da878ab40b2316435034aff598b` |
| Code checkout `cad/out/reports/assembly-granularity-integration/parser-plus-split.json` | `f661652b805086f7e63db22e9d12ae6ec25776f8757c3ff8622e7cf5c13f9a88` |

All three reports preceded tests/native construction; each contains 113 missing
execution-token inputs. They prove structural differences, not native identity
acceptance. All 108 leaf input maps and keys are identical across the reports,
with matching adapter digest sidecars and relative input paths. Main to parser
changes frame, drive-train, channel and top task keys; only channel's direct
recipe changes. The split changes all eight assembly recipes/keys once.

Fresh actual-parser comparison against the same main builders reproduced
125 to 119 artifact edges, with unchanged 108 part names. The removed edges are
frame to gooseneck/rocker-arm, drive-train to channel/harmonic-base, and channel
to cylinder-gear/frame. The current source-import contract passed the actual
137-module main and 139-module split closures. All 82 definition ASTs and 13
callers' non-import ASTs remained equal after the review fix.

Reproducer in the code checkout:
`cad/out/reports/assembly-granularity-integration/audit_extraction.py`, SHA-256
`84fcbf2e89b5b5efba4761ee082363295657af6c3b968aab049bb58d1e3c439e`.
Run with `uv run python` while the native checkout still holds the pinned main
sources. The post-fix `extraction-audit.json` receipt is
`d2b86542dcfc75d2b216f350a806f98a56c2ecc866949b1670da0ac89342c9c2`;
earlier receipts are retained as `extraction-audit-076e936f.json` and
`extraction-audit-e7d2d5f3.json`.

The attach-only, seat-locked inventory found PID 18748, revision 34.3.0, and
only the two clean documents from our completed #685 run. Those exact documents
were closed without saving, with their accepted SHA-256 values checked before
and after. The original #682/#685 worktrees, outputs and receipts remain intact.
Inventory evidence is retained beside the native baseline report.

The cache-disabled same-main `uv run python -m doit -n 4 build_bare` run is in
progress. Candidate full-build, zero-COM repeat, native fingerprint/DOF comparison,
visual inspection and latest-code reviews are still required. This is not a
merge-ready result.

## Offline tests and review finding

The first full COM-free invocation passed 1155 recipe tests (100.65 s), 91 graph
tests (18.66 s), four isolation tests (9.48 s) and 13 cache tests (5.50 s).
CodeRabbit then found that the imported parser identity test redirected only
`dodo.CAD_OUT`, while artifact factories use `_buildgraph.CAD_OUT`. The test
wrote 14-byte placeholders into the code-only checkout. No native job or genuine
artifact existed there; the active native checkout was separate and untouched.
The earlier structural reports predate those placeholder writes.

The fail-first containment assertion reproduced the escaped path before any new
write (one expected failure, 1.72 s). Fix `d25cceb7` redirects both roots and
asserts artifact/token containment beneath `tmp_path` before writing. It also
makes the reviewed AST zip strict and regex literals raw. The focused identity
and graph run passed 90 tests in 16.39 s. The full post-fix invocation passed
1155 recipe tests (87.37 s), 91 graph tests (15.07 s), four isolation tests
(9.34 s), with the 13-test cache gate current. Ruff and diff checks passed.
The helper mutation cases prove exact 4/2/all-eight direct recipe consumers,
ancestor task-key propagation and unchanged leaf recipes/keys. Exact identity,
verify/drawing token and byte-churn regressions remain enrolled.

| Code-checkout report, under `cad/out/reports/assembly-granularity-integration/` | SHA-256 |
|---|---|
| `offline-gates.log` | `22e0cd91ab33fb02d85afed8f35f4c20e2c3c9435390761aa2d25eca5f995deb` |
| `offline-gates-fixed.log` | `56aecc53610eb8ce14124715c154f482d58f316dac20a460c16a30f3298685f6` |
| `fixture-isolation-fail-first.log` | `3f5e4584cac7bd4b69d972277e158e2f3e82e4460a030cfffb2ef1dde49a4e32` |
| `fixture-isolation-fixed.log` | `1def65a09e9559226d475354a3827fde6fd145019e645dc31d1cd703d0360588` |

Hosted CodeRabbit review #686 (`581303d8-8fa2-4980-a6ca-051b7b6442f1`)
found that fixture defect and two lint nits. It resolved the defect after the
fix; latest-code full review is still required. Hosted #687 review was rate
limited after an explicit request. Windows CLI attempts also returned
`rate_limit`: all ten included reviews used and organization spending cap
reached, with advertised retry windows retained in the complete logs. No billing
setting changed. The Codex bot again requested an account/GitHub connection.
Missing watcher output or a resolved thread is not counted as a clean review.

The Windows CLI later completed a full child review at `79804d94`, with zero
findings across all 23 changed files. Its complete local cache is preserved as
`cr-687-79804d94-full-cache`; actual diffs and source contents match
`d25cceb7..79804d94`, allowing only terminal LF and Windows CRLF differences.
The verification receipt `cr-687-cache-verification-crlf.json` has SHA-256
`c145c7c6aecc8513195cb6886eddfe93b0b5ec30577e86224d080f1be0a77fcd`.

The corresponding parent review at `d25cceb7` found that keyed dictionary writes
below a consuming function were incorrectly excluded. Fail-first tests reproduced
that dropped edge, an unknown-value escape, and a same-line earlier-write case;
three ordering controls passed. Fix `34ef4e83` applies the existing late-global
rule and statement-column ordering. All 95 parser tests then passed. The child
was rebased onto this parent; no native source was changed during the baseline.

The new full offline invocation passed 1155 recipe tests (83.87 s), 97 graph tests
(14.17 s), and four isolation tests (8.95 s); the 13-test cache gate stayed current.
Its log `offline-gates-keyed-source-fixed.log` has SHA-256
`43578887bc32db5d48e3e470e45cc905807441597f77ab8231681d7ae4648890`.
`keyed-source-fail-first.log` and `keyed-source-fixed.log` retain the regression
receipts. The refreshed source audit still proves 125/119 edges, 137/139 modules,
82 unchanged definitions, 13 import-only callers and unchanged 108 leaf keys.

Both original CLI cache entries were moved into this run's evidence directory,
after verified complete copies were retained, so subsequent review requests can
cover full PR diffs. No authentication, billing or other experiment cache changed.
Clean reviews of the corrected parent and rebased child remain pending.
