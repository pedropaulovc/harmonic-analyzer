# Assembly mass-read experiment: VM2

Batch B follows accepted Batch A, `aff115c4` (native candidate `840b0a42`),
on branch `perf/assembly-mass-read`. The adapter remains
`e77bfda4de1962625da8a9a859eb0bbaf1e6f10f`. Stationary comparison passed;
changed-part and production acceptance remain pending.
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

## Stationary native positive control

Frozen source: `2cbe2a50d777028fdf0d74463361802e99be33ad`; same adapter and
licensed process. After one checked deep rebuild and deep-health gate, the
unchanged complete production fingerprint ran three ABBA blocks on one reopened
drive-train. A calls the original adapter, with its hidden rebuild observed; B
reads the same legacy native mass object without that rebuild. Timings include
all fingerprint work and candidate guards, but exclude open, shared rebuild,
health and untimed state witnesses. All twelve trials passed without native
failure, retry, recovery or mate repair.

| Trial | Variant | Fingerprint s | Hidden rebuild s | SW session age s |
| ---: | :---: | ---: | ---: | ---: |
| 1 | A | 129.411317 | 113.723655 | 16080.185 |
| 2 | B | 4.657590 | none | 16214.781 |
| 3 | B | 4.968940 | none | 16224.530 |
| 4 | A | 111.747442 | 104.270892 | 16234.927 |
| 5 | A | 141.057070 | 132.999674 | 16351.796 |
| 6 | B | 4.643030 | none | 16497.993 |
| 7 | B | 4.658064 | none | 16507.598 |
| 8 | A | 116.659124 | 109.172598 | 16517.366 |
| 9 | A | 92.606578 | 85.015418 | 16639.300 |
| 10 | B | 5.270386 | none | 16737.091 |
| 11 | B | 4.620363 | none | 16747.583 |
| 12 | A | 132.380124 | 116.602496 | 16757.239 |

Median: **123.035221 s → 4.657827 s**, saving 118.377394 s (96.214% of this
stationary fingerprint phase). This is not a whole-build speed claim: native mass
calculation may reuse internally cached values on the stationary candidate.
Fresh construction and changed-part acceptance must cover nonstationary reads.

Every complete SHA-256 fingerprint was
`15e144ee08e61593d08c828237175bbd6d1f2932398720dd7d29efdf62e586ed`, also matching
the saved baseline sidecar. Raw mass/volume/area/COM/inertia and all component
poses/configurations passed the recorded relative `1e-10`, absolute `1e-9`
comparison; full rounded fingerprints must match exactly. Every trial retained
clean `NeedsRebuild2` and the same native document identities. This native model
has only `Default`; multi-configuration activation/resolve/rest behavior is
covered by behavioral offline tests, not claimed as a native multi-config trial.

Run: 2026-09-07 04:55:32.940688 UTC to 05:11:41.576194 UTC,
968.638566 s wall. Trace `0x04a87e9afc4f07834f6739169f4e75c1`:
70 spans, zero errors, 967.486092 s after seat acquisition. All 39 saved native
inputs (root plus 38 parts) retained their exact SHA-256 after owned documents
were closed without saving. Raw trials and state witnesses:
`cad/out/reports/assembly-mass-read-v_ga9jbv/measurements.json`, SHA-256
`9731f41b493e3fc81781612ba9f9846ea223b25b4a388d7fa66a92e4f9578ab5`.
Exclusive profile: `cad/out/reports/assembly-mass-read/paired-profile.json`,
SHA-256 `e8b679a713d59c0a327c1c7f5adb06c7db965a203f697b3a3c31a11a287d79b8`.

```powershell
$env:HARMONIC_SW_AUTOSTART='0'
$env:HARMONIC_REMOTE_CACHE_MODE='off'
$env:HARMONIC_DIAGNOSTIC_SW_PID='<inventoried licensed PID>'
uv run python cad/scripts/diagnostics/probe_assembly_mass_read.py --blocks 3
```

The enrolled `test_verify_auto_repair.py` module now passes 67 tests, including
legacy unit/tensor mapping, strict malformed/state rejection, golden fingerprint
rows, pose-only changes and configuration-switch failure/rest handling
(`run-spiaovl8`, 0.53 s). Ruff and whitespace checks pass. The production
fingerprint still calls the original adapter at this checkpoint.

## Copied dependent-part trial

`probe_assembly_part_change.py` is the next native acceptance diagnostic.
It copies all 39 native inputs, verifies byte equality, relinks closed references
and proves both saved and live dependency closure before any native write.
A relinked unchanged legacy control must reproduce the saved fingerprint, pass
DOF/health/interference and reopen clean. Independent A/B copies then change only
the existing copied crank-handle `PivotBoreDia` global from 6.125 to 6.225 mm.
The 58 mm through-bore must remove 56.258070444 mm³; named dimension readback,
an unchanged-value equation control and unchanged unrelated equations establish
that this is the intended change. This deliberately exceeds the production
drawing tolerance and is never written to a production part or configuration.

Both variants run the unchanged real refresh function, all three required gates
and independent cold-reopen checks. AutoMateRepair is refused before it can act.
The diagnostic redirects only its process-local assembly/PNG output directories;
its lifecycle wrapper closes only exact registered copies and latches ownership
failures even across the adapter's best-effort calls. Original native files and
hidden sidecars are hashed before/after, including their path membership.

Run both comparison diagnostics **at their recorded pre-integration source
revision**. They require the original production fingerprint's adapter-read seam
and reject an unobserved mass read; running against a later direct-read production
function must not produce a vacuous A/B success.

```powershell
uv run python cad/scripts/diagnostics/probe_assembly_part_change.py
```

The same cache-off/autostart-off/inventoried-PID environment applies. Source,
configuration and dependencies stay frozen throughout each native attempt.
Native results are pending. Before launch, the enrolled focused module passes
83 tests (including scoped-close, failed-open, latched-cleanup and same-handle
path-change contracts); Ruff and CLI import/help checks pass.
