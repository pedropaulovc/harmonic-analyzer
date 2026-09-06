# Drawing layout handoff: bounded A/B observation

Observed 2026-09-06 on SW 2026, Python 3.14.0, source head `d8616ce5`.
This is a copied, already-built arbor drawing, not a from-scratch recipe benchmark.
Both variants run the same native layout policy and final checks. The diagnostic
declares free notes as movable groups and does not apply recipe-specific view links.

Run:

```powershell
uv run python cad/scripts/probe_callout_obstacle_handoff.py C:/src/harmonic-analyzer/cad/out/slddrw/arbor-pedestal.SLDDRW
```

The parent takes the normal COM seat. The worker rejects execution without its
seat environment. Inputs are hashed, only unique drawing copies are saved, and
both outputs are reopened. `handoff.json` includes complete checks, per-stage
measurements and profiles even when a native check fails.

## Actual result

Evidence directory: `cad/out/reports/callout-handoff-q0zqtsqn` in
`C:/src/ha-perf-callout-handoff`. Raw profiles and reports are generated artifacts,
not source files. Both variants passed geometry, dimension value/BASIC, stored
datum/SF fields and GTol XML, final fresh packing/leader clearance, and save/reopen
checks. The final view layouts matched. PDF rasterization at 1.6x had identical
pixels; the resulting arbor layout was visually inspected.

| Measurement | Fresh obstacle reads | Actual handoff |
|---|---:|---:|
| Layout wall time, with profiler | 54.476 s | 53.613 s |
| Callouts | 15.765 s | 16.274 s |
| GTols | 21.397 s | 19.405 s |
| Packing | 17.285 s | 17.906 s |
| Full annotation measurements | 93 | 80 |
| Full measurement wall time | 24.657 s | 21.660 s |

Exactly 13 full reads disappeared: three datums, nine dimensions and one SF.
The whole observed saving is only 0.864 s in this single ordered pair. The handoff
has its own owner, identity, position and context COM costs. This observation does
not establish a repeatable speedup, and does not resolve the layout regression.

Original SHA-256 remained exact:

- Drawing: `aa29e93f32fb2d3600031be52565561450e4668fe224870149d8b8e4aa5b7fa3`
- Part: `dbb991437aea105ca5352b8b76468874077aeed0a74906413a1cc56fb7ca769e`

## Profile scope and useful signals

The explicit phase/measurement counters above measure wall time around the actual
main-thread operations. Treat cProfile caller chains more cautiously: the installed
runtime also records worker threads. The COM-free companion
`diagnostics/probe_cprofile_thread_scope.py` captured all 1,000 worker-only calls.
The native profile consequently contains impossible nested counts, such as two
`_run_layout` calls for one invocation. Do not add cumulative rows or interpret
their caller relationship as a trustworthy per-thread tree.

The raw profile still identifies a bounded lead worth isolating: fresh/handoff
profiles report 1,986/2,012 `GetTypeInfo` calls, approximately 13.4/13.5 s, alongside
8,806/8,527 `InvokeTypes` calls. Pywin32 wraps many unknown-interface return values
through `Dispatch` and a second dynamic-dispatch path before the caller applies
the already-known strict interface. A main-thread-only dispatch timer is the next
positive control; these mixed-thread profile times are not a promised saving.
By contrast, GDI cell calculation was about 0.07 s in the first profile and native
symbol definitions about 0.37 s. Caching those does not address the main cost.

### Main-thread return-wrapping control

At `5e398d5b`, the existing annotation performance probe gained an explicit
invoking-thread timer around pywin32's returned-object wrapper. A copied arbor
measurement-only run passed with 25 annotations and exactly equal measured bounds
before/after instrumentation; it performed no layout controls or saves. Original
drawing and part hashes were unchanged. Evidence:
`C:/src/harmonic-analyzer/cad/out/reports/annotation-profile-x9mukkxz/profile.json`.

The uninstrumented pass took 7.897 seconds and the instrumented pass 7.146 seconds.
Those successive observations do not estimate profiler overhead or a speedup.
The latter contained 84 timed return wrappers totaling 0.990 seconds: 25
`GetDisplayData`, 22 `GetTextFormat`, 11 `GetEnvironment`, 25 `Extension` and one
`GetSpecificAnnotation`. This timer includes type discovery and Python wrapping,
not the native call that returned the object. Inventory construction happened
before the timed pass; this is not a complete layout profile. Its wrapping and
makepy dispatch categories can overlap and must not be added together.

Real worker-thread controls verify that both manual timers exclude background
calls while preserving returned objects and errors. These results narrow the
performance lead without establishing a faster production implementation.

## Smallest next measurement reuse and transaction proposal

No following design is implemented by this observation.

1. Move repeated global handoff context reads to explicit start/end boundaries
   around each single-STA consumer bank. Retain exact per-entry annotation/owner
   identity and position, and reject a changed view or active drawing at the end.
   The full final witness still rejects content or geometry changes. Benchmark the
   native A/B before keeping this smaller optimization.
2. Build one typed initial annotation inventory with exact owner/attachment,
   native parameters/value/BASIC, datum/SF fields, GTol XML, text/font and measured
   geometry. Carry this ORIGINAL baseline through all layout stages; a later stage
   must not establish a new semantic baseline after an earlier mutation.
3. After SF leader styling, measure the changed representation once. After datum/SF
   placement, retain their actual four bodies for GTol obstacles. Do not fully
   remeasure the unchanged nine dimensions and three centerlines at this boundary;
   keep their initial measurements and cheap actual position witnesses.
4. Reuse the eight original GTol bodies/semantic records for native commands.
   Candidate positions derive from immutable initial bodies; read current native
   leader segments/decorations for bounded trials. Hand actual leader geometry and
   derived body predictions to initial packing, explicitly marked as predictions,
   never as completed correctness witnesses.
5. Read the whole final native inventory once after all view/note moves. Compare
   against the ORIGINAL semantic baseline, exact objects and attachment identities;
   validate expected positions, actual dimensions/BASIC, XML/content/font, SF/datum
   semantics, centerline stroke translation, body/leader coverage, sheet fit and
   text clearance. No final comparison may use an intermediate baseline.

For this arbor inventory, the measured packing pass reads 26 annotations: 25
visible items plus one hidden SF. Preserving that existing hidden-content witness,
the design targets 57 full geometry reads: 26 initial + one styled SF + four actual
placed callouts + 26 final. The
current handoff still takes 80 because every phase keeps an independent witness.
The 57-read count is a design target, not a measured timing. Intermediate actual
callout geometry remains because native datum clamping/SF side changes have been
observed. Final strict checks remain mandatory, including unchanged layouts.

Fail-first tests would mutate attachment identity, values/BASIC, stored fields/XML,
font/text and native geometry in EACH intermediate stage, then require the single
final original-baseline witness to reject. Separate native copied controls must
confirm final rendering and saved semantics while phase timings/read counts prove
the actual benefit. This is a larger contract change than the delivered handoff.
