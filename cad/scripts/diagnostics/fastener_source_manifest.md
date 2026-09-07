# Two fastener inputs for the existing cold pilot

This is an explicit diagnostic enrollment of `cone_tip_adjuster` and
`cone_pivot_screw`, based on root `0d208ea0`. It adds exactly two targets to the
previous fourteen; every previous pin and the default rocker/lever order remain
unchanged. There is no source authoring, automatic pinning, alternative accepted
hash, new runner, or production recipe/layout change.

Native cold acceptance of these two enrolled inputs is pending. In particular,
the current tip bytes do **not** match the historical builder pin below. The
strict input gate must reject that file until a separately evidenced builder
run and explicit pin migration are reviewed.

## Source provenance and the pending tip mismatch

The actual production builder evidence is retained in
[model_callout_fleet.md](model_callout_fleet.md). The tip builder at `2d5d4d4d`
authored the original `BodyProfile` above-text and `Cup` below-text callouts,
then saved the part with execution identity
`8e2ce51d8e7ca47f9ca5a8e5c743d1d6a0f0cd749e10195a54e2140117bf12f4`.
That historical identity is the initial enrollment pin, not a claim about the
file currently occupying the output path.

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

The screw's `.cone-pivot-screw.execution` equals its observed digest. The tip's
`.cone-tip-adjuster.execution` still contains the historical `8e2ce51d...12f4`
identity, not `55cc3360...5194`. Token equality alone would not prove builder
provenance; this mismatch does not establish harmless save-metadata churn.
Neither file nor token was changed by this audit. The parent will rebuild the
tip through the real part task and capture its exact output/token before any
drawing save; accepting that new identity requires an explicit follow-up.

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

After the separately reviewed tip rebuild/pin migration, use the same command
with `--target cone_tip_adjuster` in a separate serial invocation. The currently
observed `55cc3360...5194` tip is deliberately rejected, not a runnable input
for the historical pin.

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
