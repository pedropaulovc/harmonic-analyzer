# Assembly granularity integration evidence

This run follows `second-vm-assembly-granularity-integration.md` at
`29c6ec1eea9456cc7403cab8e5e6c3fb4df02979`. Validation is in progress;
no historical #677 timing or native artifact is used as new acceptance.
VM1 owns integration and merging. Portfolio status belongs on the
[project board](https://github.com/users/pedropaulovc/projects/1).

## Inputs and extraction

- Initial main: `c6ab57dbdf73a733b32fb580bada81dab7fd758c`.
- Integrated main: `55056d4990d38ebb461f343d3002fc90731b9e73` (#684), fetched
  while the initial native baseline was running. Both PRs were rebased in the
  code-only checkout; the active native checkout remained frozen on initial main.
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
`ec09e2d29351d47cc2e3121a2d29b89be7739fdf5578f369e73f2a73b61c2e2c`;
earlier receipts are retained as `extraction-audit-076e936f.json` and
`extraction-audit-e7d2d5f3.json` and `extraction-audit-d887117a.json`.

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

The next parent review reproduced same-line batch appends being dropped. A
bounded runtime audit then reproduced loop-carried scalar, keyed and list sources,
plus different key expressions that can address the same dictionary field.
Fail-first runs recorded six and nine failures, respectively, with sixteen
passing controls. Fix `56601349` shares lexical/global/prior-iteration ordering
and rejects potentially aliasing key expressions unless literal keys are provably
distinct. This is conservative source discovery, not general Python execution.
The native baseline and all assembly helper bodies remain unchanged.

All 126 parent graph tests passed (14.28 s). After child rebase, the full offline
run passed 1155 recipe tests (87.58 s), 128 graph tests (14.31 s) and four isolation
tests (9.31 s), with the cache gate current. Log
`offline-gates-loop-order-fixed.log` has SHA-256
`1cb0c235e8e7bada1488c5a2bf426b0ddf64725c863cd52d95a56a4e437425ed`.
The actual-parser/source-contract audit retained the same graph, 82 definition
ASTs, 13 import-only callers and 108 leaf-key invariants.

Complete parent review caches and their actual diff/source verification receipts
are retained for `d25cceb7` and `34ef4e83`. A second full child review at `aa89a0f4`
found nothing; its 23-file content-verification receipt has SHA-256
`ea223d04ae8eb5a53d155e49dc1ae7afb430034d384ed7a45a11d354070430ed`.
Reviews against the latest parent `56601349` remain pending after another CLI
rate limit. No old review is relabeled as coverage of the new code.

## Owner provenance fix and main advancement

The next parent review found whole-dictionary augmented assignments missing from
keyed reads. Runtime-backed regressions also covered owner initialization and
rebinding. Fix `5d9dcfdf` rejects unknown owners and mutations while preserving the
existing channel's prepared-row protocol. The first broad fix failed two existing
channel tests; their assertions were retained. Collection and selected-row escape
regressions then pinned the narrower provenance rule. All 144 parent graph tests
passed (12.99 s), followed by 1155 recipe tests (83.89 s), 146 child graph tests
(14.12 s), four isolation tests (8.89 s), and the current cache gate.

`offline-gates-owner-provenance-fixed.log` has SHA-256
`5d6d61fdcf68be546f87fa508058661f73f8f7f5f4e7a3c5e0f183e7d7684a9a`.
The full Windows CodeRabbit review at `5d9dcfdf` found nothing across all three
parent files. Its complete cache is retained as `cr-686-5d9dcfdf-full-cache`;
actual stored diffs and source match the exact initial-main base and reviewed
head. Receipt `cr-686-5d9dcfdf-cache-verification.json` has SHA-256
`dcc77d43a532a93246ba81e7ffd4df32ad87d0e481fbeb8ac81613d4c518e97c`.

Main subsequently merged #684. The rebased parser head is `cf8b3f80`; the child
retains main's corrected spare-sprocket position and `harmonic_base_spec` import.
Its paper-drive builder diff against integrated main contains imports only.
The initial-main reports above remain historical receipts, not evidence against
the newer main. After the frozen initial run ends, its closed artifacts will be
preserved before an updated-main baseline is built in the same native checkout.
Fresh same-main reports, full native validation, zero-COM repeat, visual checks,
and reviews of the rebased stack remain pending.

The integrated-main source audit passed at child `19a370ca`: 125/119 edges,
108 parts, 137/139-module closures, 82 equal definitions and 13 import-only callers.
Reproducer `audit_source_55056d49.py` has SHA-256
`6c3e6f91790fbc14d0dd9a767233c8e812662612730082464e3bd3e9a718d551`;
`source-audit-55056d49-19a370ca/source-audit.json` has SHA-256
`bec7290c3dcbd8bec01424ac10971f8c72564fdd8f628d0d81e3c03725f9b025`.
This audit materializes Git source only and does not inspect native/cache state.

The rebased parent `cf8b3f80` received a clean full CodeRabbit review. Its complete
cache and exact three-file diff/source verification are retained;
`cr-686-cf8b3f80-cache-verification.json` has SHA-256
`70544c165017a8c7de3a096b3a0e16cdb6c12bb851d851fbe7da3992c599a58f`.
The child review at `19a370ca` claimed the mutation fixture reused discovery-time
assembly dependencies. Inspection showed each snapshot already called the real
task generator afresh. Explicit guards now check every regenerated task against
`_assembly_file_deps` and require every path beneath the fixture. All three helper
mutation cases passed (56.44 s), retaining the exact key-change assertions.
`helper-snapshot-path-provenance.log` has SHA-256
`a190aa80b6ff70d6631ee0e29c19f8dfc0bdc3d7c5c933610913139d99fbe4ab`.
The reported review and its full 23-file content verification remain preserved,
not relabeled as clean. Another full child review is required.

The first integrated-main offline invocation passed 1266 recipe tests (91.37 s)
and four isolation tests (9.77 s); graph and cache gates were current from their
successful prior runs. Log `offline-gates-main550.log` has SHA-256
`7104f56504b921ce64208888a4d1c472f7d87d87aedf953303ad1c868a8edee1`.

## Initial native baseline preserved

The initial-main `build_bare` process exited zero at
2026-09-07 20:55:26.9240104 UTC, after 9360.3890202 seconds. Its 108 part tasks
and eight FULL assembly tasks all passed. There were no ERROR spans, retries,
recoveries, fatal watchdog signals or malformed telemetry records. Cache probes
and post-seat probes missed; all 116 stores were disabled. Log-only unresponsive
window episodes resolved without intervention. This is baseline construction,
not candidate full-pipeline acceptance.

The attach-only, seat-locked post-build inventory found the licensed PID 18748
with no open documents. The closed snapshot preserves 1848 files, including all
native artifacts, exact execution tokens, recipe/fingerprint/DOF sidecars, the
genuine ledger, runtime sources, logs and the disclosed baseline reporter.
Seven subassembly previews and the completed top render were inspected; their
hashes and visibility limits are retained. These are initial-main previews,
not a substitute for updated-main/candidate inspection.

| Receipt | SHA-256 |
|---|---|
| `initial-main-after-build.json` in native checkout | `c2489af28b59fffa7961cd2bf408614760ce0aae44c18a0b2531d7d5fc3ce1fd` |
| `initial-main-build-history-summary.json` in code checkout | `9b1bfff91f580e04eca947b3aef42ce1020cc513ee9ec1f1690cba848b7ceeaa` |
| `D:/harmonic-assembly-granularity-evidence/native-initial-main-c6/manifest.json` | `a530ae6a79e995e3df80f56d85fcb0e7222bcb61665dca074ec97a5ed13bee55` |
| Code checkout `cad/out/reports/assembly-granularity-delivery/native-initial-main-c6.zip` | `9676a0759e4eafba4e2c37c4dfb64064fa08dd2a72134bc3b916a9bf8a4d6515` |

Every compressed archive member was re-read and matched against the manifest;
the archive is 98484897 bytes on C:. D: temporary storage is not the only copy.
The history summary also includes two pre-build inventory tasks; its process
interval and the separately observed exit receipt distinguish baseline work.

Main was re-fetched and remains `55056d49`, with adapter `2269009e`. Only after
preservation, the native checkout moved there and completed `uv sync --frozen`.
Its normal `build_bare` update started at 20:59:20 UTC with cache transfers off,
using its existing genuine artifacts and ledger. Source/config/template/adapter
hashes and Git state are captured before/after by the wrapper. No other
worktree's artifacts or execution tokens were copied into it.

The latest-code child review at `95be2a5a` is clean across all 23 files. Complete
cache `cr-687-95be2a5a-full-cache` and actual diff/source verification are retained;
receipt `cr-687-95be2a5a-cache-verification.json` has SHA-256
`9a6f888573941f3ed49a8f85f04f1a1cfe8b4fc84ccdd85695099c6f9c66662e`.
Post-guard offline validation passed 1266 recipe tests (92.35 s), with graph,
isolation and cache gates current. Log `offline-gates-snapshot-guard.log` has
SHA-256 `1ceb3781f3835dcab7b1fd1d1e48fd05ae9bbb5528b392687da0654817b1fc52`.
GitHub later returned `graphql_rate_limit`; the exact error is retained and
missing watcher output is not counted as approval. Candidate native full-build,
zero-COM repeat, same-main comparison and final visual acceptance remain pending.

## Native validation blocker and unchanged reproduction

The stack is not merge-ready. Parent #686 is `cf8b3f8063ff14258a59aa97c0e59de87136e2a0`;
the candidate tested here is child #687 at `2d10203b0d554e1d53fb5f13d84951412afb4a82`.
Main was fetched again before the reproduction and remains
`55056d4990d38ebb461f343d3002fc90731b9e73`; adapter remains
`2269009ed56712867826516f4406afc98a0c2814`. VM1 owns correction coordination,
integration and merging. No protected PR or drawing source was changed.

The updated-main `build_bare` baseline passed in 1252.578826 seconds. It rebuilt
paper-drive FULL and refreshed the top assembly; its other six assemblies and
108 parts were current from this checkout's initial baseline construction.
The closed snapshot preserves 1856 files. Its manifest SHA-256 is
`2bbab87b02b55141689d0b96fae047154651ebc4a1725067d8626684fabec9b7`.
The verified 98735049-byte archive is at code checkout
`cad/out/reports/assembly-granularity-delivery/native-main-550.zip`, SHA-256
`eb2b31272d95e6a87e1478605612f1ca123805df45dc3ce1832c0c4d46dbf9a0`.
The original close guard refused the dirty top assembly. A separately recorded,
bounded no-save closure discarded its post-save CSV-export BOM table and proved
all 114 owned saved model hashes unchanged. Both receipts remain preserved.

The candidate's cache-disabled `uv run python -m doit -n 4` ran from
2026-09-07 21:36:48.993767 UTC to 22:24:30.759186 UTC, 2861.758145 seconds,
and exited **2**. All 12 offline checks passed, including 1266 recipe tests,
146 graph tests and four isolation tests. Seven FULL assembly tasks and
37 production drawings passed. Two production drawing tasks failed below.
The top assembly, saved soundness/kinematics and the remaining drawing fleet
were not reached. Seven fresh assembly isometric PNGs were inspected with no
obvious gross defect; the top candidate image and assembly print checks remain
unaccepted. The raw telemetry also contains mocked test tasks/errors; the raw
receipt is retained unchanged and is rejected, not presented as acceptance.

An unchanged, cache-disabled retry of just the two failed tasks ran from
2026-09-08 00:19:47.832855 UTC to 00:20:25.855035 UTC, 38.020772 seconds,
and exited **2**. Both part dependencies were current. Both drawing failures
reproduced with exactly the same requested and returned positions:

| Drawing / datum A | Requested sheet position, m | Returned sheet position, m | Error / limit |
|---|---|---|---|
| `pinion_lift_rod`, lift rod axis | `(0.055, 0.22899999999999998)` | `(0.05499999999999966, 0.22897646401719635)` | 23.536 / 20 micrometres |
| `rack_pinion`, bore axis | `(0.22, 0.20099999999999998)` | `(0.21999999999999942, 0.20083662770023045)` | 163.372 / 100 micrometres |

These errors compare datum-symbol sheet positions after `SetPosition2` and
`GetPosition` in `_drawing_common.add_datum_feature`. They are not measurements
of manufacturing geometry. The two drawing scripts, the common drawing helper,
both part builders, configuration and templates have no diff against main.
The retry's before/after source hashes, head and adapter remain unchanged.
This proves reproduction on the candidate using unchanged main drawing code;
it does not claim that a full main drawing build was run.

Reproduce through the native checkout's own uv environment and the normal
seat-locked doit tasks, with the licensed SolidWorks session already attached:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run python -m doit -n 4 drawing:pinion_lift_rod drawing:rack_pinion
```

The post-retry no-save close guard refused an unsaved document with empty path,
title `Draw109 - Sheet1`, and dirty state. It closed nothing. That document is
left intact because the guard cannot establish ownership from its path. Do not
restart or close the session indiscriminately. No native build remains active.

Receipts under native checkout
`cad/out/reports/assembly-granularity-integration/`:

| Receipt | SHA-256 |
|---|---|
| `candidate-2d-full.log` | `79183f3588264ae6df306ac73cb81447d6231650dc30db0486d58957f42f3ed0` |
| `candidate-2d-datum-retry-process.json` | `395b96c33637782495b1eec7506975887bf8231db6b93ba59635a7199469fda6` |
| `candidate-2d-datum-retry-full.log` | `a7ec86f9a83f2ff9bc7717f940e19c238a494f0352e0c613ddab89853184061f` |

The code checkout retains `candidate-2d-datum-retry-summary.json`, SHA-256
`78a32ddbe768e59150b419ba0d4931b77dc44c7c9b9c1c4f08c7d891e23e86cf`,
with exactly two ERROR drawing tasks and the recorded telemetry boundaries.
The first-failure per-task logs remain separately preserved before retry.

Completion requires a coordinated correction for these unchanged drawing checks,
then a successful full candidate build, complete same-main geometry/DOF and
native identity comparison, all required renders/prints, a closed candidate
snapshot and an exact-head zero-COM full repeat. No tolerance was loosened, token
restamped, freshness ledger rewritten or output tree deleted. Both PRs remain
open; the existing clean local CodeRabbit reviews cover the latest code, while
this subsequent evidence-only update is outside their exact reviewed diffs.
