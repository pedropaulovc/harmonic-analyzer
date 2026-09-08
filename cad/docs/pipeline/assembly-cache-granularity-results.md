# Assembly recipe granularity: VM2 evidence

> Historical #677 experiment on its drawing parent and adapter. These results
> are not current integration acceptance or schedule. See the
> [new integration evidence](assembly-granularity-integration-results.md) and
> [project board](https://github.com/users/pedropaulovc/projects/1).

This is the Batch A experiment record requested by
`second-vm-assembly-batch-2.md` on the drawing parent branch. Portfolio status
belongs on the [project](https://github.com/users/pedropaulovc/projects/1).
Batch A proved narrower invalidation and unchanged native results. Full-stack
merge gates remain with the primary integration agent.

## Baseline and boundaries

- Accepted parent: `a6b5c900def3b8dc45f3475607f9de6aae4b4992`, PR #676.
- Adapter: `e77bfda4de1962625da8a9a859eb0bbaf1e6f10f`.
- Dedicated clone: `C:/src/harmonic-analyzer-assembly-vm2`.
- Host: `vm-solidworks`; SolidWorks 2026 SP3, RevisionNumber `34.3.0`.
- Closed native baseline: `cad/out/reports/assembly-vm2/identity-accepted/`.
  Its 116 artifact/identity pairs and six DOF manifests are recorded in
  [the preceding batch](assembly-vm2-results.md).

The planned extraction moves pattern construction and specialized couplings
without changing function bodies. Canonical insertion/placement, pose ledger,
mate-flip state, DOF recording, shared health/save gates and refresh stay in
`_assembly.py`. New modules import the core; the core must not import them back.

Refresh implementation is intentionally part of every assembly build recipe.
Verification uses explicitly enrolled dependencies rather than the whole
`verify.py` import closure. Moving those helpers into an unregistered provider
would lose freshness coverage. This split leaves that contract unchanged.

## Reproducible dependency evidence

Run in this clone's uv environment, with no native job active:

```powershell
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run python cad/scripts/diagnostics/report_assembly_dependencies.py cad/out/reports/assembly-cache-granularity/before.json
```

The diagnostic reads actual `module_deps_of` closures, `_recipe_files` and
`_assembly_file_deps`, then computes keys with the production content checker.
It covers all eight assemblies, 108 leaf parts, refresh, verification and
postbuild entrypoints. It does not open the doit database, drive COM, or transfer
cache artifacts. Existing submodule digest sidecars may be refreshed by the
normal dependency enumeration.

Baseline report SHA-256:
`53eb090ceb61a97f21a2598aa2adc18a764569507f56ae8d70f0000e6fb621e3`.
The report was generated before extraction, with only its new diagnostic
untracked. The baseline native artifacts and execution identities were untouched.

Tests will compare direct full-rebuild recipes separately from complete task
keys. A child recipe change can legitimately change its parent's task key before
any native rebuild. A token-only change follows the separate exact-identity path.
Moving functions predicts reduced invalidation coverage, not faster native COM
execution. The first build after extraction pays a one-time recipe migration.

## Extraction and consumer matrix

The source and AST comparison against `a6b5c900` found identical definitions for
all eight pattern functions, their enum, four coupling functions and 69 functions
remaining in core. Thirteen production/diagnostic callers changed imports only.
Pattern tests passed (12 tests, 0.37 s, `pytest-telemetry/run-dkb67fei`).

| transitive consumer | pattern group before / after | coupling group before / after |
|---|---|---|
| frame | core / patterns | core / absent |
| drive-train | core / patterns | core / couplings |
| channel | core / absent | core / absent |
| summing | core / absent | core / absent |
| magnifier | core / patterns | core / absent |
| pen | core / absent | core / absent |
| paper-drive | core / patterns | core / couplings |
| harmonic-analyzer | core / absent | core / absent |
| refresh entrypoint | core / absent | core / absent |
| verify entrypoint | core / patterns | core / couplings |
| postbuild entrypoint | core / absent | core / absent |
| all 108 leaf parts | absent / absent | absent / absent |

These are static transitive imports, including local imports used for builder
constants. Verification reaches builders transitively; its actual task dependencies
are recorded separately. No verification-only provider was introduced.

The after report is `cad/out/reports/assembly-cache-granularity/after.json`,
SHA-256 `8a5e0d7b5f2d460d836c4b81e09b919f5190e0311a6ef1a2f4d5adfef7e47a64`.
It adds generated-task consistency assertions, verify task dependencies and
source SHA-256 values to the baseline schema. All eight direct recipes/task keys
change once during migration; all 108 leaf keys remain identical.

Five focused tests passed in 50.39 s (`pytest-telemetry/run-74l29t4z`): exact
transitive consumer sets and isolated mutations of both extracted providers plus
core. They use copied actual inputs with production recipe and cache-key code.
Pattern edits now full-rebuild four assemblies; coupling edits full-rebuild two.
Both also change the top assembly's task key through child recipes while leaving
its direct recipe alone. Core edits still change all eight. All leaf recipes and
keys remain unchanged in every case. Existing exact-child identity and canonical
placement discovery tests remain intact.

## Frozen native acceptance

Candidate: `840b0a421ec3bff27413ff7b68ae8098ddfa706c`; adapter unchanged.
All recorded source SHA-256 values matched after the run. SolidWorks PID 18748
remained the same licensed session throughout. An attach-only, locked preflight
at 03:44:49 UTC confirmed zero open documents (trace
`0x980d9a43484b8829299ceeb1a9184d02`).

```powershell
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_SW_AUTOSTART = '0'
uv run python -m doit -n 4 check:recipe check:graph check:config check:math check:partiso check:cache check:watchdog check:verify_telemetry
uv run python -m doit -n 4 build_bare verify:soundness verify:kinematics
uv run python -m doit -n 4 build_bare
```

The enrolled checks passed; unchanged config/cache checks retained current stamps.
Separate focused suites also passed: 161 tests in 93.97 s, telemetry
`pytest-telemetry/run-1gizjl6n`. The enrolled invocation included 2,965 passing
graph cases, 22 watchdog tests and 18 health-telemetry tests. Ruff and diff checks
passed. No shared scheduler, graph implementation, cache, config or adapter file
changed.

Native acceptance ran 2026-09-07 **03:45:47.1568879–04:27:59.3982461 UTC**,
exit 0, **2532.2338795 s** process wall time. Every one of the 108 parts remained
current. All eight assemblies performed full construction, all eight saved
soundness suites passed, and kinematics passed. This is the one-time migration
cost, not a steady-state speedup. There were zero failed native tasks, retries,
recoveries or mate auto-repairs. The watchdog emitted informational hung-window
warnings during native solves; none became an abort.

| native task | seconds after seat acquisition | trace |
|---|---:|---|
| frame construction | 122.706701 | `0x07dd7ff26e30772a1fda521918a7e394` |
| channel construction | 234.346865 | `0xf0c4eaa561d31115c543a297da5314f8` |
| magnifier construction | 38.631022 | `0x98e18e914775a267fdf9382ee2ca351d` |
| drive-train construction | 676.498587 | `0xb8a5231750ee8305a2a85acdb86b8a99` |
| summing construction | 34.390663 | `0x34cacebeaedc2b795630f0d69999e204` |
| paper-drive construction | 208.323902 | `0x367c93c68621711a341796e1b231142a` |
| pen construction | 25.701403 | `0xc582b4eeb12666e2144ba4c23d619539` |
| top construction | 580.438100 | `0x21cfe32dca53d082d87d19846f518827` |
| channel saved soundness | 30.443244 | `0x066253bd39ac1621a25459ddff52e2df` |
| magnifier saved soundness | 12.234626 | `0xfeaea50c1cb05732f1a4c95327fadd50` |
| paper-drive saved soundness | 52.354260 | `0xe217c2e438914e6addd85ba12781eb17` |
| drive-train saved soundness | 117.915353 | `0xd2eb8edce8a8157807b1f64662d2c107` |
| summing saved soundness | 14.143309 | `0x667961c111e750988a55ca407f6d2b73` |
| pen saved soundness | 10.260858 | `0x77dcc8f7363f30e8e14cf493bd0470f7` |
| top saved soundness | 192.251391 | `0xa1c8246b5d256dd9ef0a5a0d7be99381` |
| frame saved soundness | 37.960712 | `0xc7b714d2f64541218c6fe75b8edb3b2a` |
| kinematics | 126.163719 | `0x531f2940cdebf4c7fbb1af996fe7944a` |

The no-change run passed in **10.9878991 s**, skipping all 116 producers with
zero COM work. At 04:29:41 UTC an owned-document inventory closed the remaining
ten documents without saving and verified zero remaining (trace
`0x7f9fce182e9b4cf97713caebe283f4a1`).

### Native identity and visual evidence

Closed snapshot: `cad/out/reports/assembly-cache-granularity/accepted-840b0a42/`.
It contains all native parts/assemblies, sidecars, renders, telemetry, gate
stamps, cache events and the clone's `cad/out/.doit.db`. An initial copy attempted
the wrong root-level database filename; it failed without changing the database.
The correct database was subsequently preserved, SHA-256
`59c160855cdfbab66176a2d27eaae067c965eedde75d0fdd3eee41956e50869c`.

`artifact-manifest.json` beside the snapshot binds all 116 baseline/candidate
native hashes and execution tokens. SHA-256:
`981158070d8ffe0b24d67a4df8a0b1abf7eb7ca218f7e468cbce63a69306350b`.
All 108 part bytes and tokens are identical to the accepted #676 baseline.
All eight assembly tokens changed as expected after full reconstruction; every
candidate native byte hash equals its producer token. All six DOF manifests and
all eight geometry-fingerprint sidecars stayed byte-identical to baseline.

All eight fresh `cad/out/png/<assembly>/<assembly>_isometric.png` images were
inspected, including the rebuilt top. No obvious geometry/placement regression
was seen. Dense edges limit fine-contact inspection. Paper-drive's loose T18 is
the previously documented parked state, not a new placement discrepancy.

### Timing interpretation and next experiment

Drive-train took 199.625388 s longer than #676's candidate. Exclusive attribution
subtracting each span's union of direct-child intervals reconciled exactly to
both task totals. Three deep-rebuild-containing scopes account for 194.881700 s
(97.62%) of that increase:

| scope | #676 candidate s | Batch A s |
|---|---:|---:|
| free-DOF gate | 39.687331 | 107.005573 |
| final deep rebuild | 36.213131 | 99.850899 |
| mass-property read, including hidden deep rebuild | 39.461823 | 103.387513 |

Scalar mate authoring stayed near 142–143 s, the gear bank near 44.7 s and
replication near 75 s. This localizes the slowdown without establishing that
extraction caused it. Both traces contain 207 spans and zero ERROR spans.
Do not infer the fraction spent in native rebuild versus subsequent reads from
an unsplit parent span.

Batch B should freshly profile the mass-read rebuild before considering its
removal: both digest callers already establish a checked resolved state, but
native equality must cover fresh copy-save, refresh, exact-child identity,
real part changes and configuration switches. A second, smaller opportunity is
seven scalar static locks (16.836943 s here). CodeRabbit also noted repeated
transform reads in pattern matching; this PR leaves those function bodies intact.

## Delivery boundary

PR #677 is stacked above #676. CodeRabbit approved `840b0a42`; its performance
nitpick is retained above rather than mixed into this behavior-preserving split.
Codex's explicit review request returned the account/GitHub connection blocker
again, so there is no clean Codex review. The primary agent still owns that gate
and the full drawing-inclusive build at the integrated stack head. No PR was
merged or parent branch deleted.

The accepted sample is one frozen fleet run on one VM, not evidence of a
less-than-5% native solver, cache-identity or source-control conflict rate. Cache
transfers were disabled; no remote hit-rate improvement is claimed. Regenerate
the recipe reports before/after the split, run the isolated key tests and the
three commands above, and retain the complete referenced native set on the
measuring seat.
