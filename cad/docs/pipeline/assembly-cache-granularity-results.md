# Assembly recipe granularity: VM2 evidence

Historical VM2 record, retained from `dd5e5b2a`. The measurements below belong to
the stated VM2 inputs, not the VM1 integration onto `3c0c4a97` / adapter `25bc99b1`.
That integration requires its own full native build and visual checks. See the
[later VM2 record](https://github.com/pedropaulovc/harmonic-analyzer/blob/439f8dec448e540cf61e3153b74b216336fe3f7d/cad/docs/pipeline/assembly-granularity-integration-results.md)
for the completed baselines and failed candidate run; they are not new-tree acceptance.

This is the Batch A experiment record requested by
`second-vm-assembly-batch-2.md` on the drawing parent branch. Portfolio status
belongs on the [project](https://github.com/users/pedropaulovc/projects/1).
Native acceptance and post-extraction results are pending.

## Baseline and boundaries

- Accepted parent: `a6b5c900def3b8dc45f3475607f9de6aae4b4992`, PR #676.
- Adapter: `e77bfda4de1962625da8a9a859eb0bbaf1e6f10f`.
- Dedicated clone: `C:/src/harmonic-analyzer-assembly-vm2`.
- Host: `vm-solidworks`; SolidWorks 2026 SP3, RevisionNumber `34.3.0`.
- Closed native baseline: `cad/out/reports/assembly-vm2/identity-accepted/`.
  Its 116 artifact/identity pairs and six DOF manifests are recorded in
  [the preceding batch](https://github.com/pedropaulovc/harmonic-analyzer/blob/dd5e5b2a644bda03be3e7787eda03fdb2cb646b1/cad/docs/pipeline/assembly-vm2-results.md).

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
