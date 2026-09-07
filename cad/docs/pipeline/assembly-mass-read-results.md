# Assembly mass-read experiment: VM2

Batch B follows accepted Batch A, `aff115c4` (native candidate `840b0a42`),
on branch `perf/assembly-mass-read`. The adapter remains
`e77bfda4de1962625da8a9a859eb0bbaf1e6f10f`. Experiment results are pending.
Portfolio status belongs on the [project](https://github.com/users/pedropaulovc/projects/1).

## Hypothesis and scope

The accepted drive-train trace spent 103.387513 s in geometry-fingerprint mass
collection. The adapter unconditionally calls `ForceRebuild3(False)` before
creating the native mass-property object. Both assembly-fingerprint callers
already establish a checked resolved state. Test whether reading the same native
object without that additional rebuild preserves the complete fingerprint and
native acceptance while reducing measured work.

This is a hypothesis. The official local `IModelDocExtension.CreateMassProperty`
reference says the method recalculates current values, including all assembly
component bodies when no subset is added. That does not prove solved component
poses or fresh-save/refresh equivalence. Keep all explicit rebuilds, configuration
switches, health, DOF, interference, identity and save gates intact.

Use the same legacy `CreateMassProperty` API, units, centre-of-mass inertia mode,
field ordering, rounding and component-pose rows. Do not change API versions,
adapter behavior, body inclusion, geometry or solver policy. A missing or malformed
native result must fail rather than produce a plausible zero fingerprint.

## Starting evidence

Clone: `C:/src/harmonic-analyzer-assembly-vm2`; host `vm-solidworks`; SolidWorks
2026 SP3 / `34.3.0`, licensed process 18748. Its document table was empty after
the accepted Batch A snapshot at 2026-09-07 04:29:41 UTC.

Baseline native set:
`cad/out/reports/assembly-cache-granularity/accepted-840b0a42/`.
Its paired artifact manifest is SHA-256
`981158070d8ffe0b24d67a4df8a0b1abf7eb7ca218f7e468cbce63a69306350b`.
All 116 artifacts and identities are retained together. See
[Batch A results](assembly-cache-granularity-results.md) for source hashes,
unchanged fingerprints, timings and full assembly acceptance.

First measure a fresh drive-train construction through `doit assembly:drive_train`,
after validating/preserving and cleaning only its generated assembly, execution
token, recipe sidecar and render directory. Cache off alone does not force a
build. No part is cleaned. Keep sources/configuration fixed during every run,
retain all attempts, and separate native task time from seat wait.

Required comparisons include alternating stationary controls, the fresh
copy-save boundary, a real dependent-part change in isolated fixtures, a
same-recipe child identity change, configuration switching and the subsequent
zero-COM no-op. A production change will be retained only after measured benefit
and native acceptance; a negative result will retain its reproducible diagnostic.

## Fresh construction baseline

Frozen source: `f681b566b8038a2e762a273c8718a61083cba8a5`.
`doit -n 4 assembly:drive_train` ran cache-off from
2026-09-07 04:37:01.286783 UTC to 04:49:20.218778 UTC: 738.930890 s wall,
723.499224 s traced task time after zero seat wait. All required part tasks
were up to date; drive-train was constructed from scratch. No retry, recovery or
error span occurred. The licensed process remained 18748.

The exact trace `0x6afcf97a583f16839fd9283e8175b51a` contains 207 spans.
`report_assembly_profile.py` retains their original records and attributes each
nanosecond once. Fingerprint collection took 128.552266 s, of which mass-property
collection was 123.119657 s; DOF validation and final rebuild remain separate.
This does not yet split the adapter's hidden rebuild from native mass calculation.

Run the reporter to reproduce the complete category table:

```powershell
uv run python cad/scripts/diagnostics/report_assembly_profile.py cad/out/reports/telemetry/traces.jsonl 0x6afcf97a583f16839fd9283e8175b51a cad/out/reports/assembly-mass-read/fresh-baseline-profile.json
```

Report SHA-256:
`b677b281b69ae7b8b23bd3c99ceeda1a51f88aeff03053ba7bd9f5b3539bd4ff`.
Closed native outputs, sidecars, renders, telemetry and database are preserved in
`cad/out/reports/assembly-mass-read/fresh-baseline-f681b566/`.
`fresh-baseline-manifest.json` beside that directory records all 116 native hashes
and execution tokens. Every hash matches its token. All 108 parts and the other
seven assemblies are byte-identical to accepted Batch A; only drive-train changed.
Owned documents were closed without saving and the inventory verified empty.
Manifest SHA-256: `7764a4ccb29a40e074e665ed410ed2231a2ec45d2df3580dfe67f58a98c180d0`.

The initial candidate is diagnostic-only: `probe_assembly_mass_read.py` invokes
the unchanged complete production fingerprint through an adapter observer.
Baseline forwards to the pinned adapter and records its hidden deep rebuild;
candidate substitutes the strict legacy native mass read. Three ABBA blocks
retain six observations per variant, complete raw properties and component poses,
session age, failures and input-preservation evidence. No production call site
has changed at this stage.

The first probe launch at 2026-09-07 04:54:44.633813 UTC stopped during Python
import (`ModuleNotFoundError: psutil`, 0.227641 s wall), before COM attachment or
any native trial. Process-age collection now uses the existing pywin32 bindings
(`GetProcessTimes`), verified against PID 18748; dependencies remain unchanged.
