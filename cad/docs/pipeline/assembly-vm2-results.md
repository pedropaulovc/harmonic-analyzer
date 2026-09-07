# Independent assembly validation on vm-solidworks

Execution evidence for [the second-VM handoff](second-vm-assembly-handoff.md).
Assembly acceptance and performance measurements are pending. Portfolio status
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
Cache misses are building dependencies locally; this run is not an uncached
paired performance trial. Cache provenance, task logs and spans are retained
under this clone's `cad/out/reports/cache.jsonl`, `cad/out/logs/` and
`cad/out/reports/telemetry/`.

## Outstanding evidence

Saved-channel soundness; complete assembly graph, soundness and kinematics;
fresh render inspection; a measured bounded improvement with paired trials;
incremental no-change and input-identity checks; final trace and hash manifests.
No failure-rate bound or full merge-gate result is claimed.
