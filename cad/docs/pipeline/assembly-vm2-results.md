# Independent assembly validation on vm-solidworks

Execution evidence for [the second-VM handoff](second-vm-assembly-handoff.md).
The initial saved-channel check and complete assembly fleet passed soundness and
kinematics; paired performance measurements are in progress. Portfolio status
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
2.646 seconds, including 1.174 seconds in the native call. These are observations
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
`bf7f92ad`) and the unchanged pinned adapter. Documentation commit `b503b7b9`
was made during the run; imported native sources did not change. The run ended
at 2026-09-07 02:18:27 UTC with exit 0, zero failed tasks and zero recoveries.
Every dependency was built locally after read-only cache misses. No experimental
artifacts were uploaded; remote-cache hits were not demonstrated.

All eight saved assemblies passed soundness, including saved-rebuild, health,
DOF, mate and interference checks. Channel's already-current stamp was retained;
the other seven ran in this invocation. Kinematics passed (102.23 seconds,
trace `0xa57c10feff6fe51fc3b9650c3c448be2`).

Times below are task spans **after seat acquisition**, not total scheduler wall
time. Seat waiting is a separate recorded attribute and is not construction cost.
Initial channel figures are included for completeness.

| assembly | native task s | seat wait s | saved soundness s | construction trace |
|---|---:|---:|---:|---|
| channel | 225.280 | 0 | 25.250 | `0x0319584c22350b5ca4463493f3368261` |
| frame | 123.650 | 22.99 | 35.470 | `0xf47827efc7397ed241ef6e9b89e4881e` |
| drive-train | 474.850 | 118.02 | 59.050 | `0x00f7ffa7b02aa2f46a3bab940e66c9f5` |
| paper-drive | 171.170 | 41.56 | 34.260 | `0xbcc20fc274566a24a11b7b7f67bc0450` |
| pen | 24.960 | 186.65 | 9.690 | `0x768b6a3a32dcf3d614410183c968957b` |
| magnifier | 37.840 | 192.05 | 11.750 | `0x4ed0a8cda3573c1e2c49c30e963b0c09` |
| summing | 34.660 | 753.48 | 14.210 | `0xee11e77d55d985e34f291acd710c1a7b` |
| harmonic-analyzer | 310.180 | 135.84 | 106.300 | `0x4917c16664abb49ce0384e428041e04a` |

All eight fresh isometric assembly PNGs were inspected. No obvious displaced
components were seen; dense edge shading limits fine gear/contact inspection.
Complete native dependencies, renders, cache log and telemetry are preserved in
`cad/out/reports/assembly-vm2/fleet-baseline/`.

### No-change behavior

With `HARMONIC_REMOTE_CACHE_MODE=off`, a subsequent
`uv run python -m doit -n 4 build_bare` skipped all 108 parts and eight assemblies:
10.4004653 seconds process wall time, exit 0, no COM work. This repeated a
preceding no-change invocation whose terminal timing was not retained; it is
not presented as a first-versus-second timing comparison.

### Profile and paired probe

Channel's initial spans put 104.57 seconds in pose driving, 27.25 seconds in
CopyWithMates and 9.35 seconds in geometry digest collection. The top assembly's
health target collection took 13.15 seconds during construction and 7.57 seconds
during saved soundness, despite producing only ten targets. Summing produced
nine targets in 1.48/0.26 seconds; channel produced 129 in 3.52/3.30 seconds.

The bounded candidate is native top-level component enumeration inside
`assert_model_healthy`, which already filters out all nested instance names.
It does not deduplicate repeated child documents or change rebuild/error rules.
The committed diagnostic `probe_assembly_health_targets.py` compares the exact
production gate with each enumeration flag, in ABBA order on one opened and
deep-rebuilt saved model. Witness and pose collection are outside timed trials.
It records exact dependency hashes, native target identities, null children,
What's Wrong results, configuration and transforms, and refuses foreign documents.

The baseline session retained 114 clone-owned documents after verification.
After preserving outputs and inspecting every path, these were closed without
saving (zero documents remained). No user document was present or discarded.

## Outstanding evidence

A measured bounded improvement with paired trials and regression tests;
input-identity checks; candidate assembly acceptance; final trace/hash manifests.
No failure-rate bound or full merge-gate result is claimed.
