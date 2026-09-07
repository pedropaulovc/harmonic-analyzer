# Independent assembly validation on vm-solidworks

Execution evidence for [the second-VM handoff](second-vm-assembly-handoff.md).
The initial saved-channel soundness check passed; fleet acceptance and paired
performance measurements are pending. Portfolio status
is tracked on the [project board](https://github.com/users/pedropaulovc/projects/1).

## Frozen starting environment

- Fresh recursive clone: `C:/src/harmonic-analyzer-assembly-vm2`.
- Branch: `perf/assembly-vm2`, stacked on `perf/cad-build-and-drawing-entities`.
- Root: `bf7f92ad70376e59be8b0ace6147d35f197b879d`.
- Adapter: `e77bfda4de1962625da8a9a859eb0bbaf1e6f10f`.
- References: `bee888222d62f232eac14ef8f7a8d1a4303a8710`.
- `git fetch origin main` followed by `git log --oneline HEAD..origin/main`
  returned no missing main commits before native work.
- Host: `vm-solidworks`; running SolidWorks PID: `18748`.
- Native `RevisionNumber()`: `34.3.0` (SolidWorks 2026 SP3).
- Executable: `C:/Program Files/Dassault Systemes/SOLIDWORKS 3DEXPERIENCE R2026x/SOLIDWORKS/sldworks.exe`.
- Python: clone-local `.venv/Scripts/python.exe`, CPython 3.14.5, created by
  `uv sync` from the pinned lockfile.
- Imported adapter: clone-local
  `SolidworksMCP-python/src/solidworks_mcp/adapters/pywin32_adapter.py`.
- Offline API reference: v3.12.1.

An attach-only inventory under `dodo._com_seat`, with
`HARMONIC_SW_AUTOSTART=0` and `HARMONIC_DIAGNOSTIC_SW_PID=18748`, returned an empty
`GetDocuments()` array at 2026-09-07 00:34 UTC. The inventory neither launched
SolidWorks nor changed document preferences.

## Initial channel run

Started from the root and adapter revisions above:

```powershell
$env:HARMONIC_REMOTE_CACHE_MODE = 'ro'
uv run python -m doit -n 4 assembly:channel verify_soundness:channel
```

Native sources and dependencies stay frozen during the run. Documentation-only
commits may record observations without changing its imported inputs.
All eleven dependency parts and channel construction completed locally after
cache misses. This run is not an uncached paired performance trial.
Cache provenance, task logs and spans are retained
under this clone's `cad/out/reports/cache.jsonl`, `cad/out/logs/` and
`cad/out/reports/telemetry/`.

The run finished successfully at 2026-09-07 00:44:13 UTC. There were zero failed
tasks and zero SolidWorks recoveries. Channel construction took 225.280 seconds
(223.903 seconds in the build body); independent saved soundness took 25.250
seconds. Both task spans recorded zero seat wait. Driver-bank deletion took
2.654 seconds, including 1.172 seconds in the native call. These are observations
on this VM, not comparisons against the first VM's wall times.

All six saved-model gates passed: saved-rebuild-clean, dof-free-necessity,
no-over-constrained, model-healthy, interference-free and channel-independence.
The exact-set DOF gate found 80 under-constrained components, covering the 60
expected free DOF with no stray component families. The final construction
ledger checked all 128 placed components. The manifest has 60 drive specs.

| evidence | identity |
|---|---|
| channel task trace | `0x0319584c22350b5ca4463493f3368261` |
| saved soundness trace | `0x5226a67d398e143435ee8e5c36c0ba06` |
| native assembly SHA-256 / execution token | `909e1a6630a0bbcaa0d9475d83e390f7210e99e807fd9a45d26b523779e97e26` |
| DOF manifest SHA-256 | `e5c09e65398839546c7147cc1b14724bc5b83fa4bdf7f8f2748fe86642338854` |
| isometric PNG SHA-256 | `3d9d5d28beef037b53499cc3cf19bc8c0e70026c80a5219ed35c15dbbbd6fc1b` |

The independently generated DOF manifest is byte-identical to the batch-deletion
manifest reported in `performance.md`. This does not establish equal CAD identity
or a population failure-rate bound.

The generated isometric PNG was inspected: channel stacks, shafts, vertical rods
and spring/lever banks are present without an obvious displaced instance. Dense
edge rendering limits fine contact inspection; the numerical gates provide that
run's placement and interference evidence.

The complete initial native part/assembly output set, render set, cache log and
telemetry are preserved locally under
`cad/out/reports/assembly-vm2/channel-initial/`. The preserved native assembly hash
matches the execution token. Direct PowerShell hashing of the live assembly was
blocked by SolidWorks' file lock; the copied baseline provided the hash above.

## Assembly fleet baseline

After fetching main again and confirming no missing commits, started:

```powershell
$env:HARMONIC_REMOTE_CACHE_MODE = 'ro'
uv run python -m doit -n 4 build_bare verify:soundness verify:kinematics
```

This run uses root `20ec8ee0` (only the initial evidence document added since
`bf7f92ad`) and the unchanged pinned adapter. Results are pending.

## Outstanding evidence

Complete assembly graph, soundness and kinematics; remaining fresh render
inspection; a measured bounded improvement with paired trials;
incremental no-change and input-identity checks; final trace and hash manifests.
No failure-rate bound or full merge-gate result is claimed.
