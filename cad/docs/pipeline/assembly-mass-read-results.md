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
