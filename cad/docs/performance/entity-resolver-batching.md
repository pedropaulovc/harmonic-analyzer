# Entity resolver batching experiment

This child experiment follows
`cad/docs/pipeline/second-vm-entity-resolver-performance.md` at
`d67152990960eecb0703a3f9d2bc366d44ac4e8d`.

Batching saved 0.88 s (41.1%) in the hot resolver comparison and 1.47 s (9.1%)
per production drawing in the matched ABBA pass. Complete crank manufacturing,
identity, cold-reopen and print checks passed. Integration and merging remain
with VM1. Local CodeRabbit reviewed all six files with zero findings.

## Inputs and ownership

- Accepted parent: #682, `19431a0088519bd8755b941a3da73a699c0ed7e1`.
- Adapter: `25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`.
- Branch: `perf/entity-resolver-batching`.
- Child PR: [#685](https://github.com/pedropaulovc/harmonic-analyzer/pull/685),
  open and ready for review, not for merge.
- Isolated checkout: `C:/src/ha-entity-resolver-batching`, with its own
  `uv sync --frozen` environment and no borrowed build state or artifacts.
- Observed main: `c6ab57db`. It includes assembly-health work after the accepted
  parent. This experiment deliberately retains the handoff's pinned parent.

VM1 owns parent integration and merging. This branch does not alter #676-678,
the accepted crank recipe, manufacturing data, annotation placement, the adapter,
or shared build/template helpers.

## Experiment contract

Measure repeated native reads before changing production code. Compare fresh
resolver banks on one unchanged, genuinely built local source, using at least
three alternating ABBA blocks. Keep instrumented resolver timings separate from
uninstrumented production drawing timings. Warm each prepared-template entry
before production measurements.

The acceptance checks remain those of #682: all 14 explicit attachment roles,
13 raw dimensions, manufacturing metadata, native identity, both cold reopens,
move/scale and Save3 association, template guards, source/token hashes, and
production-scale full-sheet/crop inspection. The moved sheet is association
evidence only. No optimization is accepted without repeatable native benefit.

## Native inputs and first measurement

The cache-off `doit part:crank_arm` build produced a new 129127-byte source.
Its SHA-256 and genuine execution token are both
`cfde03558f6ca85ef096080d322f32621f62063d5994108fba54a5028a65b4d3`.
No token was restamped to accept an observation. The accepted #682 worktree and
artifacts remain untouched.

The locked inventory found only the two clean documents from the completed
#682 experiment before the new production build. Every run used PID 18748,
SolidWorks revision 34.3.0, the global seat and watchdog, with
`HARMONIC_SW_AUTOSTART=0` and `HARMONIC_REMOTE_CACHE_MODE=off`.
No instance was launched, restarted or recovered. Instrumented and uninstrumented
ABBA receipts include process memory, source/resolver/recipe hashes, selector
descriptions, adapter revision, interpreter path and native view/source witnesses.
The uninstrumented ABBA memory observation was 6.0565 to 6.0587 GB private bytes.

The pre-change profile (`entity-resolver-performance-bsztry6w`) took 4.143915 s
and confirmed 22 surface reads, 10 face-edge enumerations and 42 curve reads.
Feature lookup and face enumeration already occurred only four times. This
observation justified batching distinct face selectors per feature and boundary
selectors per face, rather than another feature-name cache.

## Resolver comparison

Code under validation: `4c99b9d6` (production implementation `b54af9ac`).
The baseline module comes directly from accepted `19431a00`. Both implementations
consume the exact immutable recipe selectors; each call constructs a fresh bank.
Only selector classes are shared between the loaded modules, not resolution code,
decoded geometry or handles. There is no cache across calls or native mutations.

Each run uses three ABBA blocks on the same stationary Default source. Native
`IsSame` checks compare all ten returned entities and all four production views'
referenced source/configuration, outside the timed resolver interval. Both the
instrumented and uninstrumented runs passed all 12 samples, with no failed role
or identity checks. Profiling is restricted to the invoking thread: binding,
member lookup/property reads and method invocation have disjoint intervals.
Their rows must not be added to the enclosing resolver duration.

| Native read per call | Accepted A | Batched B |
|---|---:|---:|
| Feature lookup | 4 | 4 |
| Feature face enumeration | 4 | 4 |
| Surface reads | 22 | 10 |
| Face edge enumeration | 10 | 6 |
| Curve reads | 42 | 24 |

Every instrumented sample has these counts. Full binding and parameter-read
counts and elapsed times are in the receipt; the table does not collapse
different native methods into one cumulative profile row.

Uninstrumented resolver seconds, in execution order:

| Block | A | B | B | A |
|---|---:|---:|---:|---:|
| 1 | 2.186753 | 1.281873 | 1.520520 | 2.564985 |
| 2 | 2.091196 | 1.256206 | 1.265919 | 2.077304 |
| 3 | 2.094509 | 1.229585 | 1.209113 | 2.394274 |

Median: 2.140631 s to 1.261062 s, saving 0.879569 s (41.1%).
Means: 2.234837 s and 1.293869 s. Ranges: 2.077304 to 2.564985 s
and 1.209113 to 1.520520 s. These are hot, stationary resolver timings, not a
five-second production-bank or fleet timing claim. The full offline recipe gate
was active during this alternating run; both variants shared that workload.

## Production and complete acceptance

Each variant's production prepared entry was warmed before timing; measured
drawings use `uv run python -m doit -a -s drawing:crank_arm`. The part dependency
was genuinely current and its identity stayed fixed. Initial chronological
production series A1-A3 took 16.784281, 16.452457 and 16.002675 s. B1-B3 took
16.320626, 15.904366 and 16.718998 s, with the offline gate active during B.
These overlapping total times are retained, not treated as a matched speedup.

After the offline gate completed, a matched production ABBA pass used the exact
accepted resolver file for A and the candidate for B. Swaps happened only between
native runs and were never committed as production changes. Each restored variant
had a separate warm drawing before measurement. The same prepared-template key
`274147637940d179cca2bfa08446c819ca8f8204f563b7306c117093d88f5092`
passed validation for both variants: the resolver change does not alter template
preparation inputs. Warm observations and their artifacts are retained as
`entity-resolver-production-warm-{A4,B4,A5}` and excluded below.

| Order / trial | Total build s | Resolver s | Factory setup s |
|---|---:|---:|---:|
| A4 | 16.169386 | 4.113309 | 0.917742 |
| B4 | 14.377182 | 2.375151 | 0.998053 |
| B5 | 15.017477 | 2.405482 | 0.903319 |
| A5 | 16.157221 | 4.129353 | 0.918033 |

Mean/median total: A 16.163304 s, B 14.697330 s, saving 1.465974 s (9.1%).
The baseline range is 16.157221 to 16.169386 s; candidate range is 14.377182
to 15.017477 s. Mean resolver saving is 1.731015 s. This is four production
samples, not a fleet estimate or a reliability bound.

| Trial | Native save s | PDF s | PNG s | Model-callout verification s | Finalize s |
|---|---:|---:|---:|---:|---:|
| A4 | 0.701322 | 0.638788 | 0.356417 | 0.937974 | 1.964877 |
| B4 | 0.659110 | 0.593194 | 0.355214 | 0.948326 | 1.870924 |
| B5 | 0.661322 | 0.606507 | 0.357733 | 1.205129 | 1.877051 |
| A5 | 0.664085 | 0.598869 | 0.361885 | 0.956221 | 1.871711 |

Timing boundaries follow existing production telemetry. Total build is the
`drawing.build` span, including prepared access and recipe execution, not a
new instrumented recipe measurement. The prepared-hit spans took 0.002855,
0.002848, 0.002971 and 0.002969 s. Finalize includes sheet checks and native
save/export/render; it overlaps those columns and must not be summed with them.
Model-callout verification is the sum of the two non-overlapping
`drawing.verify_model_callouts` spans, not every inline attachment check's cost.
All production checks ran. The separately instrumented complete-acceptance
recipe took 24.975177 s and is not part of this production comparison.

Raw production spans and artifacts are in `entity-resolver-production-{A4,B4,B5,A5}`.
Trace IDs, in that order: `0x73d478edffac4c09a289837e569646d9`,
`0x5b80409a4c76c945695f7314fbc75df2`, `0x2ae330976af8d6ade7662c43bc6a9b4e`,
`0xc2014a1c127efaeddbdf4996d396a134`. The candidate was restored after A5,
and another successful production output is retained as `B6-final`.

The complete unchanged crank acceptance passed in `crank-arm-entities-s2878g3y`:
14 explicit roles, 13 raw drawing dimensions, source and manufacturing values,
tolerance/text/BASIC/arc conditions, both cold reopens, movement/scaling,
in-place Save3, fresh native entity banks and factory guards. Original source,
owned copy and original execution token all retained the SHA above. Only the
diagnostic's genuine local source and baseline receipt pins changed.

The baseline, candidate B3 and first-cold full-sheet PNGs are byte-identical:
`65f92a8d28ffcb60cdb68b5ea90174f55342f11182daef674fee04a873884bb8`.
Visual inspection covered the full sheet and six 600 dpi detail windows.
All six production/cold crop hashes match. The overlapping shaft and front
windows show the complete shaft callout, datum B and Ra 1.6 text; stock, cross-hole,
notes and title windows retain the accepted layout and readable manufacturing
content. The moved/scaled scratch sheet remains association evidence only.
The same 21 geometry exclusions and zero dimension-semantic exclusions remain.
Moved-cold comparison accepted 181 coordinate-roundoff entries and zero zero-Z
serialization entries under the unchanged rules; no tolerance was widened.

Final replay `crank-arm-entities-3s1mtuq2` passed the same complete acceptance
after restoring the candidate. Whole-file A/B replay normalized checkout line
endings; the restored resolver matches committed Git content, with file SHA
`c4d85f2deb77cacf8c0d9cbc0bdbb385e7b4894a5fb7bdc0f2d2db4c3fc02ce3`.
The second replay validates those exact restored bytes. It retains all source,
copy and token hashes, the same 21/0 exclusions and 181/0 roundoff/zero-Z counts.
Its instrumented recipe took 22.913174 s. Its cold full sheet also matches the
production PNG hash above.

## Tests and limitations

Fail-first baseline: three expected batching failures and 13 passes in
`pytest-telemetry/run-3ucuzchd`. Candidate focused tests: 56 passed
(`run-14ghe8fg`). Ruff passed after removing one unused diagnostic import.
Graph: 83 passed (`run-hvruxzeb`); part isolation: four passed (`run-sikro6jk`).
Full recipe gate: 6199 passed, one failed in 285.11 s (`run-h7xiejm5`).
After all native work, the gate rerun retained the same sole failure and 6199
passes in 259.15 s (`run-tqw_00va`); graph and isolation remained current.
The final raw-string-only test change passed all 22 new tests in 0.61 s
(`run-tzr_jn0s`) and the explicit Ruff `RUF043` check.
The sole failure is the unchanged
`test_fillister_is_not_silently_enrolled_in_full_owned_pilot` registration/test
contradiction at the frozen baseline. Neither its assertion nor registry changed.

This small sample does not establish a fleet speedup or a below-5% failure rate.
The full integrated COM graph and post-rebase render inspection remain VM1's
merge gate. The child PR is not merge-ready from isolated crank validation.
GitHub's rewritten parent makes the hosted PR diff appear to contain 509 files;
CodeRabbit declined it above its 300-file limit (run
`e969a660-cc7d-4eb0-adc7-166ba5dd1ef2`). The real bounded diff from `19431a00`
contains six files. GitHub GraphQL also returned `graphql_rate_limit`, causing
the watch-pr comment formatter to pause after three retries. REST readback
confirmed the review skip; missing formatter output was not treated as approval.
The authorized Windows CodeRabbit CLI review uses both the parent branch and
exact accepted baseline, with pinned helper sources as context. The first local
pass found only a documentation inconsistency between
the committed scaffold and the live results note supplied as review context;
this complete committed report replaces that scaffold before re-review.
No production-code finding was raised. No parent branch, merge or billing
setting changed.

The second local pass requested only an explicit raw-regex test literal; it is
fixed without changing the pattern or assertion. The third pass completed with
zero findings on all six files at
`4c13ed91036ec8478cd97e3a9c9d9a86ac9f70f1` (CLI exit 0). This subsequent
documentation-only commit records the completed review and gate receipts;
production, diagnostic and test code are unchanged from that reviewed commit.
A separate receipt audit
corrected two swapped A-sample table rows; aggregate calculations were unchanged.
Native observations total 16 successful production builds (including five warm
builds and the final restored output), 24 successful ABBA resolver samples and
two successful complete crank callbacks. A post-build archive command initially
used the wrong PNG path; it was corrected before the next sample without rerunning
or changing that successful native result. No native failure is hidden by that
bookkeeping correction.

The exact local review invocation was:

```powershell
cr review --agent --committed --base perf/crank-arm-semantic-entities --base-commit 19431a0088519bd8755b941a3da73a699c0ed7e1 --config cad/docs/performance/entity-resolver-batching.md cad/scripts/_part_pmi.py cad/scripts/_drawing_common.py cad/scripts/diagnostics/_owned_native_session.py
```

GitHub REST also returned HTTP 403 rate limiting during final readback; a later
REST update succeeded and recorded this result in the PR description. The
persistent watcher remains attached. Its parent-conflict notice is deferred to
VM1 under the frozen-base handoff, not resolved by altering parent integration.

The complete bounded ownership list is:

- `cad/scripts/_drawing_entities.py`
- `cad/scripts/diagnostics/probe_entity_resolver_performance.py`
- `cad/scripts/diagnostics/probe_crank_arm_entities.py` (local evidence pins only)
- `cad/scripts/test_entity_batching_drawing.py`
- `cad/scripts/test_entity_resolver_performance_drawing.py`
- `cad/docs/performance/entity-resolver-batching.md`

## Receipt index

Paths are relative to this checkout's `cad/out/reports/`. Full native drawings,
PDFs, PNGs, detail crops, ownership receipts and telemetry remain beside them.

| Receipt | SHA-256 |
|---|---|
| `entity-resolver-performance-q8jd4qaa/measurements.json` (instrumented ABBA) | `40de3621d4d29409fb33528bcfcaafa5a87688e58856ba020f8984842b16501a` |
| `entity-resolver-performance-0yuuw78q/measurements.json` (uninstrumented ABBA) | `45fea0e36f4934636f24d431593ca70ba3be4a154749698e0cae2f2edaa7f3a8` |
| `crank-arm-entities-uc6rpju9/measurements.json` (new baseline) | `6e00b42ca53fe0d4557ee7ae98044f016683c6ad1a4cb5ea8568b36fa529815d` |
| `crank-arm-entities-s2878g3y/measurements.json` (complete acceptance) | `34795a9715b7de76416ce11cf2becbc7612942fd178735f0d371d04ab275708e` |
| `crank-arm-entities-s2878g3y/ownership.json` | `5e77be2b67318bc25d542bc35a5ebd75c89ffa4abe837cdf3b9c79c832f05bba` |
| `crank-arm-entities-3s1mtuq2/measurements.json` (final replay) | `813bd226c92d2cfcbd29f99596964ae6025e0741c6669876817aa9d6df1cab14` |
| `crank-arm-entities-3s1mtuq2/ownership.json` | `329019ff16a2ded8fc0eb87803553f39f592c17e34988957cb8660c46088e75f` |
| `entity-resolver-production-B6-final/crank-arm.SLDDRW` | `05f962e1eb37a8dc3b38f1c6bea6bf26d97ede5120869bc9bacf2d24c2cc1df3` |
| `entity-resolver-production-B6-final/crank-arm.pdf` | `887768ac92b056c9669a6f9c04ee9de82f0d2bb39474f699e8fce8a94e685ab9` |
| `entity-resolver-local-review-4c99b9d6.log` (first local review) | `506372dcd1a5b0ef494119884616c1c48ec61c6e8bc9cb767816c4d8ab2fd5a2` |
| `entity-resolver-local-review-ec2cdfb8.log` (second local review) | `74db7fac7cf93936bae4822d1cb819d64065d32c38a3a75a05701fa7b8d4e2f9` |
| `entity-resolver-local-review-4c13ed91.log` (clean latest-code review) | `f66afd14aad8197a90645730f489bac45d5f1058d2a5df2d006134357207e4e3` |
