# Two fastener inputs for the existing cold pilot

This is an explicit diagnostic enrollment of `cone_tip_adjuster` and
`cone_pivot_screw`, based on root `0d208ea0`. It adds exactly two targets to the
previous fourteen; every previous pin and the default rocker/lever order remain
unchanged. There is no source authoring, automatic pinning, alternative accepted
hash, new runner, or production recipe/layout change.

Native cold acceptance of these two enrolled inputs is pending. Following the
initial enrollment, the tip was rebuilt through the real production task and
its pin explicitly migrated to `f3578ac2...8468` below. The historical builder
identity and the mismatching pre-rebuild output are both rejected; neither is
an alternative accepted input. The first owned tip replay then failed its
source-copy preservation gate; the screw target was not reached (receipt below).

## Source provenance and the pre-rebuild tip mismatch

The actual production builder evidence is retained in
[model_callout_fleet.md](model_callout_fleet.md). The tip builder at `2d5d4d4d`
authored the original `BodyProfile` above-text and `Cup` below-text callouts,
then saved the part with execution identity
`8e2ce51d8e7ca47f9ca5a8e5c743d1d6a0f0cd749e10195a54e2140117bf12f4`.
That historical identity was the initial enrollment pin, not a claim about the
file subsequently occupying the output path.

The screw builder at `c61655db`, adapter `25bc99b1`, PID 31860, produced
`515019088b41d329b45f0487b9241123751ecac7d6c116481930ae9c45e89c36`.
Trace `0x03b6ad66aeedd08030f5543c0e2da971` records the real part task and its
`ThreadTail` authoring. The subsequent production drawing at `0d208ea0`
passed the live final collision gate and visual inspection; that pipeline does
not cold-reopen the drawing. Its separate evidence is in
[the reference-ink report](../../docs/pipeline/gtol-reference-ink-obstacles.md).

A read-only audit on 2026-09-07 used `FileStream` with `FileAccess.Read` and
`FileShare.ReadWrite`, repeated the digest, and checked unchanged size/mtime:

| Root output | Observed bytes | Last-write UTC | Observed SHA-256 |
| --- | ---: | --- | --- |
| `cone-tip-adjuster.SLDPRT` | 87111 | `2026-09-07T11:21:11.2310177Z` | `55cc336009f1a837e5c9fb5afbea4cc06d6658c17dcb0aaef86294762f555194` |
| `cone-pivot-screw.SLDPRT` | 72863 | `2026-09-07T10:45:59.0649169Z` | `515019088b41d329b45f0487b9241123751ecac7d6c116481930ae9c45e89c36` |

At that audit, the screw's `.cone-pivot-screw.execution` equaled its observed
digest. The tip's `.cone-tip-adjuster.execution` contained the historical `8e2ce51d...12f4`
identity, not `55cc3360...5194`. Token equality alone would not prove builder
provenance; this mismatch does not establish harmless save-metadata churn.
Neither file nor token was changed by this audit. The following rebuild and
explicit migration resolve the input mismatch without reclassifying its cause.

## Explicit tip rebuild and pin migration, 2026-09-07

At frozen root `be38f5b5`, adapter `25bc99b1`, licensed PID 31860, the parent ran
`uv run python -m doit -a part:cone_tip_adjuster` with remote cache disabled.
The real task exited zero. No drawing ran between this rebuild and the identity
capture. The new output is 83669 bytes, last-write
`2026-09-07T11:59:23.3065459Z`, with SHA-256 and execution token both exactly
`f3578ac2b2ab95e478bc7bd72c316ebab057c125d5244af6fa2c3e12f4d48468`.
Two independent audit passes each made two read-only shared-file SHA reads;
the repeated digests and size/mtime agreed. This follow-up changes only the
tip pin; all other fifteen enrolled identities remain unchanged.

Retained trace `0x47af91b93f03813f7c22ced4e98083b1` records the task from
11:58:10.656888 to 11:59:24.152219 UTC (73.495331 seconds), with `part.build`
72.236573 seconds. Both actual `dim.model_callouts` spans passed: `Cup`
2.184715 seconds and `BodyProfile` 1.494968 seconds. The latter retains the
existing above-text lane. These are production authoring operations, not a
diagnostic rewrite of a source copy.

The pre-rebuild `55cc3360...5194` binary (87111 bytes) and its historical
`8e2ce51d...12f4` execution token are preserved under
`cad/out/reports/tip-source-before-rebuild-c68b086141824fbb94de75266d4bd65f/`.
The mismatch evidence and original builder provenance remain intact. There is
no manual token restamp, automatic pin update, or assertion that the old byte change
was harmless. This new native build is evidence for source enrollment, not yet
a successful cold drawing replay.

## Existing manufacturing contracts

The registry references each existing spec's `DRAWING_DIMENSIONS` directly:

| Target | Exact required `dimension@feature` names |
| --- | --- |
| Tip (5) | `BodyDiaDim@BodyProfile`, `BodyLenDim@Body`, `CupDiaDim@CupProfile`, `CupDepth@Cup`, `SlotWDim@SlotProfile` |
| Screw (7) | `HeadDiaDim@HeadProfile`, `ShoulderDiaDim@ShoulderProfile`, `HeadHt@Head`, `ShoulderLg@Shoulder`, `ThreadLg@ThreadTail`, `SlotWDim@SlotProfile`, `SlotDepth@DriverSlot` |

Neither builder declares source BASIC dimensions, so the enrollment adds no
invented BASIC constraint. The existing named-parameter reader retains its
exact part-owner/configuration/handle checks and its existing value/tolerance
representation; this is not a new full-part raw-property manifest.

The tip recipe verifies its authored `BodyProfile` and `Cup` text against the
explicit intended source and view. The screw's actual `FastenerSheet` recipe
retains `side_callout_feature='ThreadTail'` and the spec's unchanged side map;
the existing shared fastener verifier executes. Both retain their production
prepared-factory contract (4:1 sheet scale, two decimals). No optional
source-authoring, lower-text, source-save experiment, or layout variant is used.

The pilot still protects the original selected source plus the default rocker
and lever sources, opens only a unique owned source copy, runs the current
recipe through its normal owned saver, and compares fresh built/cold source and
drawing witnesses. All existing attachment/identity, emitted-text/layout,
copy-hash, failure-retention, and runtime-source guards remain intact. No new
explicit VIEW-role manifest is inferred for these recipes. Generic geometry
coverage is not an additional persistent-identity proof. Expected callout
storage verification and unchanged emitted text do not alone establish visual
readability; the fresh PDF/PNG must also be inspected.

## Serial native replay after review

Only the parent with the granted native seat should run this, from the reviewed
and frozen root checkout. Confirm the actual live PID first. The parent command
takes the existing machine-global lock; do not invoke `--worker` directly.

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '31860'
uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
  --candidate HEAD `
  --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --guard-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --target cone_pivot_screw --factory prepared
```

After integrating this separately reviewed pin migration, use the same command
with `--target cone_tip_adjuster` in a separate serial invocation. Only the
rebuilt `f3578ac2...8468` tip is accepted; both `55cc3360...5194` and the original
`8e2ce51d...12f4` are explicitly tested as rejections.

## Offline verification

New tests cover explicit pins, rejection without repinning, exact spec dimension
sets, named owner resolution, actual recipe AST redirection, the screw's shared
fastener call, prepared parent/worker forwarding, and the existing pilot engine's
copy/cold rejection paths. Their COM leaves are mocked; they do not establish
native fastener acceptance. The initial registry-dependent tests failed before
enrollment. The final eight-file adjacent suite passed 326 tests in 17.91 seconds
(`pytest-telemetry/run-mr2snw6w`). The new file follows the enrolled
`test_*_drawing.py` convention. The previous whole-map test was explicitly
extended from fourteen to sixteen entries after approval, retaining every
previous exact hash assertion.

For the separate tip pin migration, the updated pin/rejection tests failed six
cases against the old registry (`run-1q_9rgez`), including wrongly accepting the
historical input. After changing only that registry identity, the four-file
pin/spec/fleet suite passed 151 tests in 4.44 seconds (`run-8ui396og`); Ruff and
diff checks passed. The full sixteen-entry equality still pins every other
identity exactly.

## First owned tip replay: source-copy preservation failed

At frozen root `fb958fda`, the prepared full-recipe pilot selected tip then screw.
Receipt `cad/out/reports/datum-policy-sd8umcdz/pilot.json` has SHA-256
`100067e57314e7eeee8d9d848190d246868bebf2035cc1613f76e91d2078fce0`.
The complete failed pilot took 183.5877625 seconds; the tip recipe returned after
24.0260824 seconds. These include diagnostic work and are not a speed comparison.

The tip's owned source copy began with the enrolled
`f3578ac2b2ab95e478bc7bd72c316ebab057c125d5244af6fa2c3e12f4d48468`
identity. Immediately after the recipe, its SHA was
`9864a588cb934322d1a0fa58cff56aba1f8b40845663cdd2cd686f13551fe5e1`;
the final observation retained that same changed identity. The original error
was `after_recipe: owned source copy changed on disk; no source save is
authorized`. The independent final runtime guard also rejected the changed copy.

All four protected original files, including the freshly rebuilt tip, kept their
exact starting hashes. Failure capture completed with `errors=[]` and retained
native observations plus PDF/PNG evidence. Its before/after-export preservation
checks concern the already-failed scene; they do not establish unchanged source
semantics across the recipe. The normal post-recipe source witness and built/cold
drawing acceptance were not reached. There is only one trial in the receipt:
the second selected screw target never started.

This preserves the distinction between historical successful production tasks
and the stricter owned-copy/cold pilot: a returned recipe or successful native
save does not pass the latter gate. No source-pin update, source-write permission,
or checker exemption follows from this failure. The receipt locates the byte
change within the recipe, not at a particular operation; attributing it to
`set_reference_dimensions` or any individual setter still requires a separate
first-dirty boundary observation.
