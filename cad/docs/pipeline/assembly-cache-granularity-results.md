# Assembly recipe granularity: VM2 evidence

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
