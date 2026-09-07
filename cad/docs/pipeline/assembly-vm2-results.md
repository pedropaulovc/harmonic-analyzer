# Independent assembly validation on vm-solidworks

Execution evidence for [the second-VM handoff](second-vm-assembly-handoff.md).
The initial saved-channel check and complete assembly fleet passed soundness and
kinematics. Paired measurements support the implemented top-level health target
enumeration; the candidate fleet and incremental identity checks passed.
Portfolio status
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
| frame | 123.647 | 22.99 | 35.467 | `0xf47827efc7397ed241ef6e9b89e4881e` |
| drive-train | 474.848 | 118.02 | 59.054 | `0x00f7ffa7b02aa2f46a3bab940e66c9f5` |
| paper-drive | 171.174 | 41.56 | 34.258 | `0xbcc20fc274566a24a11b7b7f67bc0450` |
| pen | 24.962 | 186.65 | 9.685 | `0x768b6a3a32dcf3d614410183c968957b` |
| magnifier | 37.844 | 192.05 | 11.753 | `0x4ed0a8cda3573c1e2c49c30e963b0c09` |
| summing | 34.665 | 753.48 | 14.211 | `0xee11e77d55d985e34f291acd710c1a7b` |
| harmonic-analyzer | 310.179 | 135.84 | 106.296 | `0x4917c16664abb49ce0384e428041e04a` |

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

### Paired native result

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '18748'
uv run python cad/scripts/diagnostics/probe_assembly_health_targets.py
```

Two ABBA blocks per model completed with **24 passed / 0 failed trials**, no
retries or recoveries, at 2026-09-07 02:34:54 UTC. The seat was held for 614.4
seconds with zero waiting; that includes open, shared rebuild, untimed witness
and state checks, and cleanup. Production sources remained at the baseline;
the diagnostic records root `b503b7b9` plus its own exact source hash. Commit
`cd4fbda7` published the already-running diagnostic without changing its bytes.

All timings below measure the whole production health gate, excluding rebuild,
open, target-identity witnesses and transform snapshots. A uses descendant
enumeration; B uses top-level enumeration. Values are in execution order within
each variant (the actual schedule was ABBA, ABBA).

| assembly | A seconds (four trials) | B seconds (four trials) | enumerated A / B | health targets |
|---|---|---|---:|---:|
| channel | 9.586, 8.692, 8.987, 9.274 | 9.838, 8.683, 9.170, 9.318 | 128 / 128 | 129 |
| summing | 0.590, 0.578, 0.583, 0.576 | 0.569, 0.565, 0.561, 0.543 | 8 / 8 | 9 |
| harmonic-analyzer | 9.052, 9.267, 7.431, 4.580 | 0.669, 0.632, 0.906, 0.433 | 400 / 9 | 10 |

The top assembly's median health-gate time fell from 8.242 to 0.651 seconds
(92.1%). Channel's median was 9.130 / 9.244 seconds; summing's was 0.580 / 0.563.
The leaf controls show no material benefit; this is a traversal optimization for
nested assemblies, not an end-to-end build-speed claim. Within-run timing drift
is visible in the full retained sample, including the fastest baseline trial.

Every block preserved target-instance names and multiplicity, native document
identities and What's Wrong results. No null child documents were observed in
the live models; null-child handling is covered by the regression tests. Configuration, rebuild
state and all component transforms were unchanged after each trial. SHA-256
readbacks after closing established unchanged native inputs: 12 channel files,
7 summing files and all 114 top-assembly files (sets overlap). The full baseline
contains 116 native artifacts and 116 execution sidecars; the two unreferenced
parts (`chain-sprocket` and `hex-bolt`) and execution sidecars are outside the
paired probe's hash scope. Copied `~$` lockfiles are not native artifacts.

| paired native root | SHA-256 before and after |
|---|---|
| channel | `909e1a6630a0bbcaa0d9475d83e390f7210e99e807fd9a45d26b523779e97e26` |
| summing | `8455fa3d09aa3c4cf4e03254acca1faf4b89123f07a1212459b3521fa65da320` |
| harmonic-analyzer | `2a79eaf0ba16372b06dbc10173cd060b657d6ee4d2edff88e02c8b84a4890d4e` |

Trace: `0x54647cf29a724f7dac99198f97c19a0b`. Exact per-trial span IDs, timings,
all dependency hashes and witnesses are retained in
`cad/out/reports/assembly-health-targets-zd_3kf2m/measurements.json`
(SHA-256 `bfa6c9d0e7104704a32b5d474a769a21ba94d980200f6e1bf6b89d79ab5ea90c`).

Production now changes only this `GetComponents` argument and explanatory
comments. Regression cases exercise repeated child instances, null/self/nested
exclusion, explicit models, shallow inspection, named child errors, and shared
versus gate-owned rebuilds. Before the change, the focused test run produced
six expected failures on `[False] != [True]`, one pass and eleven deselections
(`cad/out/reports/pytest-telemetry/run-8rz3sib_/`). Existing assertions were not
weakened. This small sample does not establish a population failure rate below 5%.

## Candidate acceptance

Frozen implementation: `60178f31d384eb45f540774faf9948b0a4bc0813`; adapter remains
`e77bfda4de1962625da8a9a859eb0bbaf1e6f10f`. Fetching main before the run found no
missing commits. Only evidence-document edits occurred during native execution.
`_assembly.py` SHA-256:
`6b5117bc557467ba4872b293644134c11be5ce84eda2318cf0c06ef938581b04`.
Diagnostic SHA-256:
`796290b81b462944b26b55b83c087e47b9df089b667458d2b9af54aad4915fd9`.

After marking #676 ready, Ruff passed on all three changed Python files, and
these enrolled COM-free gates passed:

```powershell
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run python -m doit -n 4 check:verify_telemetry check:recipe check:graph check:partiso check:cache check:math check:config
uv run python -m doit -n 4 build_bare verify:soundness verify:kinematics
uv run python -m doit -n 4 build_bare
```

The health/telemetry suite passed all 18 tests, including the seven added cases.
The candidate native invocation finished at 2026-09-07 03:12:19 UTC, exit 0,
1,919.4491751 seconds process wall time. All 108 parts stayed current; all eight
assemblies were rebuilt, all eight saved soundness checks ran and passed, and
kinematics passed. There were zero failed native tasks and zero recoveries.
Transient hung-window warnings cleared without intervention; no crash, modal
abort or operation timeout occurred.

| assembly | build task s | seat wait s | saved soundness s | build trace |
|---|---:|---:|---:|---|
| frame | 113.400 | 0 | 37.073 | `0x74f8dab0b836aa18e5becf60558c1abe` |
| channel | 268.220 | 112.75 | 30.156 | `0xe46da003b3ef04a572d67d5f5997f24c` |
| summing | 33.811 | 382.36 | 14.087 | `0xd92017ceb84c5e2c4e51c9cfd0700b78` |
| magnifier | 36.902 | 304.07 | 12.031 | `0x1b864f6eb8ee1fb72ee4ee43c4048e7f` |
| drive-train | 476.873 | 453.70 | 65.430 | `0xe096f93e16207dfd096724ff65c346ec` |
| pen | 24.674 | 606.23 | 10.037 | `0x3b6dd7b888bc6f9a0646c8841f6ac656` |
| paper-drive | 173.685 | 641.87 | 35.570 | `0xe287aee336eed9ca8e3a4a254964b099` |
| harmonic-analyzer | 329.178 | 96.93 | 129.102 | `0x3cfe6a9b0e43ace26e0f3d2fee20a30f` |

Kinematics: 107.155 seconds after the seat, trace
`0x8184ad709f36caec551cb031d13d872f`. Top saved soundness trace:
`0x30f9a8196fbdf7a20f0251b6b8580070`. Its health target collection took 0.22 seconds
for ten targets; cold construction collection took 6.86 seconds. These unpaired
fleet observations include session/solver variation and do not establish an
overall speedup. The controlled stationary-gate comparison above is the
performance evidence.

All eight freshly regenerated isometric assembly renders were inspected with
no obvious placement regressions. Native outputs, their execution/recipe
sidecars, renders, verification stamps, cache log and telemetry are preserved
under `cad/out/reports/assembly-vm2/fleet-candidate/`.

The subsequent cache-off no-change run took **10.7310658 seconds**, exit 0,
skipping all 108 parts and eight assemblies with zero COM work. Parent-save byte
churn did not produce a phantom rebuild cascade.

## Same-recipe child identity and final no-op

After the candidate no-op, an attach-only inventory found 114 clone-owned
documents. They were closed without saving, with zero remaining. Under the
machine-global seat lock, the existing `dodo._clean_assembly('pen')` removed only
these resolved targets, already preserved in `fleet-candidate/`:

- `cad/out/sldasm/pen.SLDASM`
- `cad/out/sldasm/.pen.execution`
- `cad/out/sldasm/.pen.recipe.md5`
- `cad/out/png/pen/`

The eight pen parts were not cleaned. The supported build path was then:

```powershell
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run python -m doit -n 4 assembly:pen
uv run python -m doit -n 4 build_bare verify:soundness verify:kinematics
uv run python -m doit -n 4 build_bare
```

Pen rebuilt successfully in 33.4975561 seconds process wall time (18.394 seconds
in the native task, trace `0x093da8f55ec0be6f50d6f066ecdca94a`). Its recipe digest
stayed `af1eff2a95969dcd5127325891a02e77`, while its execution token changed:

- Before: `60e1ccc07b956c46039f57fec92fd6757395b63b58212ebea1a51b0248d7c14c`
- After: `826b6d9d973c97b41ddb07e197c45396f5e6a1aa9acd7f245c685953900925aa`

At that boundary all 108 part tokens and the other seven assembly tokens were
unchanged. The next invocation correctly refreshed only the top assembly,
skipping all 108 parts and all seven child assemblies. It reran pen/top saved
soundness and kinematics; unchanged saved gates stayed current. All passed,
exit 0, 720.8852676 seconds process wall time, ending 2026-09-07 03:27:38 UTC.

| operation | task s after seat | trace |
|---|---:|---|
| pen saved soundness | 9.399 | `0x5c49b61cfebfd51c260bbb957e1d6690` |
| kinematics | 98.641 | `0xdfe54cde527086a7019dfa0a7d0d33e6` |
| top refresh | 427.551 | `0x33e83b4e7b1352e3ef3be1513ad7a6c0` |
| top saved soundness | 167.629 | `0xdc8cd8aeac809449ef8a54bb5f81aaa2` |

The refresh recorded `mode=refresh`, 102.82 seconds seat wait, and the expected
dirty saved rebuild flag after child replacement (`NeedsRebuild2=1`). It forced
the gates and clean re-save; `Save3` returned true with error/warning codes 0.
No mate auto-repair, retry or recovery was used. This slow refresh is retained,
not treated as a speedup. The top execution token changed from
`974118083e44c02a0d8f0a40ce27841f0e8aa73cebd0ab1cc4112ef875f3c7c8` to
`156076487a3cee973a7626decafdde61552f35b6d37dba58924c89c7d7bcb8cf`.

The final no-change invocation skipped every producer, exit 0, **10.89929
seconds**, zero COM work. Fresh pen and refreshed top renders were inspected
again without an obvious placement regression. All six DOF manifests remained
byte-identical to the fleet baseline.

At 03:29 UTC the 114 owned documents were inventoried and closed without saving;
an empty document table was verified before preserving the next-batch baseline
in `cad/out/reports/assembly-vm2/identity-accepted/`.

### Complete artifact identity manifest

`cad/out/reports/assembly-vm2/artifact-manifest.json` binds all 116 native files
and execution tokens across `fleet-baseline`, `fleet-candidate` and
`identity-accepted`. SHA-256:
`e49aa7e075bf0a7afbe421cb9fa5c0a7426d8a6b33a27b771012ffb5f8fd330c`.
It records source/adapter revisions, host/SW provenance and each native byte
hash separately from its producer token. No file was missing or unreadable.

All 108 part bytes and tokens stayed unchanged across both comparisons. All
eight assembly tokens changed during the source-driven candidate rebuild; only
pen and top changed in the subsequent identity trial. No unexpected producer
identity changed. Every final native byte hash equals its execution token.
The final no-op proves this run did not manufacture a metadata-driven cascade;
it is not a claim that parent saves always change child bytes (none did here).

The snapshots retain referenced native dependencies together. Regenerate the
paired evidence using the committed probe in a dedicated empty session; its
JSON contains every dependency hash, trial span and stationary witness. Keep
these large snapshots/raw logs local; include the whole referenced set if an
evidence attachment is needed on another seat.

## Acceptance boundary and integration

Implemented and natively proven: top-level health enumeration, stationary paired
target equivalence, complete saved assembly acceptance, kinematics, same-recipe
child identity propagation, and no-change behavior. Offline-only edge cases:
null/self/nested target filtering, explicit-model selection and injected child
errors/rebuild failures. No geometry, solver, tolerance, drawing, cache-key,
scheduler or adapter behavior was changed.

CodeRabbit approved implementation `60178f31` with no actionable findings.
Codex review remains blocked: the GitHub bot's response to the explicit review
request says to connect the Codex account to GitHub. This is not a clean Codex
review. The primary integrator still owns that gate and the complete drawing-
inclusive `uv run python -m doit -n 4` build/visual inspection on the integrated
stack. Neither #675 nor #676 was merged by this VM.

The native sample contains zero failed construction/verification invocations
and 24/24 passing stationary health trials, on one VM/session and one pinned
configuration. This does not establish a less-than-5% solver, cache, or
source-control conflict rate. Remote cache hits were not demonstrated.
