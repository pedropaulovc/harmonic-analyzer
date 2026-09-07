# Main-based assembly health extraction

This branch isolates the accepted native top-level health traversal change from
the drawing stack. Its **new-tree full native build and visual gate are pending**.
The historical VM2 acceptance is supporting evidence, not a transferred gate.

## Exact scope

Base: `9e746e1513479290565e6d920e74dadb3c7062a2` (main).
Adapter remains main's `2269009ed56712867826516f4406afc98a0c2814`.
The five source commits from PR #676 are replayed with `cherry-pick -x`:

```text
20ec8ee05d6585094110b45e22bc60cc466d79ba
b503b7b9292ef6bd013bd7d0f3f07fc9ba1b1989
cd4fbda739d80d501125b58dcd423b09c03e431e
60178f31d384eb45f540774faf9948b0a4bc0813
a6b5c900def3b8dc45f3475607f9de6aae4b4992
```

The only normal-build production change is `_assembly.assert_model_healthy`:
request `GetComponents(True)` instead of enumerating descendants and discarding
slash-qualified names. Instance multiplicity, null/self filtering, What's Wrong
checks, failure handling and the shared/owned rebuild contract stay unchanged.
Main's original `_assembly.py` is identical to the VM2 baseline at `bf7f92ad`.

The paired health probe is unchanged. Its missing standalone dependency,
`diagnostics/_owned_native_session.py`, is copied exactly from `4147d8d8`
(introduced by `aacd6df4`, corrected to true attach-only by `4147d8d8`). This
does not import drawing probes, clear documents, launch SolidWorks or write its
global preferences. Its caller retains ownership and must hold the machine seat.
Standalone offline tests cover the attach-only boundary. The health test module
also needs an explicit `pytest` import absent on old main; its predicates remain.

No drawing, part geometry, config, scheduler, cache-key or adapter changes are
included. PR #677's pattern/coupling split is deferred: its exact key-isolation
test exposes a spurious channel dependency in main's older string-based source
graph. The accepted source-manifest parser/guards must be assessed before that
separate extraction; its test must not simply accept the extra invalidation.

No PR #678 mass-read code is included. Its broad optimization was withdrawn at
[37cd3488](https://github.com/pedropaulovc/harmonic-analyzer/commit/37cd348864816fb7a5ca2ece31799ebef5cfd5b3)
after the paper-drive pose/fingerprint counterexample. The final `fac565cb`
production assembly/refresh code is identical to accepted #677, not a retained
mass-read optimization.

## Evidence and remaining gate

[VM2's retained report](assembly-vm2-results.md) records 24/24 stationary paired
trials, the candidate assembly fleet, saved soundness, kinematics, exact child
identity propagation and subsequent no-op. It used root `60178f31` and adapter
`e77bfda4`, not this main-based tree. The graph, channel construction, four part
builders and adapter differ between those trees. Native equivalence and a full
build on this extraction cannot be inferred from the earlier green fleet.

Main's actual `task_build()` includes **108 parts, eight assemblies, 92 drawings,
12 checks and soundness/kinematics**. No gate or drawing is omitted:

```powershell
uv sync --frozen
uv run --no-sync python -m pytest -q cad/scripts/test_verify_telemetry.py cad/scripts/test_owned_assembly_health_session.py
# With confirmed exclusive native seat coordination and healthy SolidWorks:
uv run --no-sync python -m doit -n 4
```

Inspect the freshly produced affected assembly renders before merging. Keep the
normal cache/recipe/execution-identity decisions; do not transplant old gate
stamps or force current outputs to appear valid. Reusing a seat's existing output
tree avoids an unnecessary parallel native fleet, but only matching producer
inputs and identities may stay current. The shared assembly edit intentionally
invalidates all eight assembly recipes.

For a new paired health repro, use the same probe with explicit model arguments,
an inventoried PID and the full saved dependency set in this checkout:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<confirmed-current-PID>'
uv run --no-sync python cad/scripts/diagnostics/probe_assembly_health_targets.py channel summing harmonic-analyzer
```

No COM was invoked during extraction. No remote PR or VM2 worktree was modified.
