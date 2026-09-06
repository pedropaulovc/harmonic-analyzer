# Build performance and drawing attachment contracts

The September 2026 telemetry audit identified two recurring costs: channel pose
correction repeatedly resolves the same components and transforms, and drawing
recipes repeatedly locate geometry through sheet coordinates or whole-view scans.

The audit read 69,252 spans and 126,342 log records from ten checkouts. In nine
successful channel builds without presentation-pose configurations, pose
correction consumed 353 to 468 seconds, or 66 to 73 percent of the build body.
Nine of eleven failed drawing attempts concerned geometry selection or attachment.
These histories span changing code and do not estimate production failure rates.

## Channel construction

Component handles and target transforms are prepared once within the stable
post-copy document phase. Cached handles must not survive document replacement or
topology changes. The conservative experiment preserved the original solver
sequence; a second experiment changes that sequence explicitly: reset only the
current four-component copy, retain its three construction drivers while posing
the remaining copies, then remove the complete driver bank in one native call.

The deletion manifest must contain exactly three unique, newly created distance
mates per copy. Resolve and type-check the entire manifest before mutation,
select only those features, delete without absorbed/child-feature flags, and
verify every target disappeared. The closing pose, mate-count, solver status,
operational-DOF, interference and saved-rebuild checks remain in place.

Validation compares the resulting component poses, mate health, operational DOF
and saved/reopened assembly with the reference construction. Aggregate telemetry
must distinguish preparation, resetting poses and authoring drivers, and record
the operation counts without emitting a span for every component.

Changing the solver sequence requires a separate live experiment. Fewer COM calls
are useful evidence; a single faster wall-clock run is insufficient because seat
load and SolidWorks state vary.

### Measured channel experiments

These are individual full, uncached builds on the same seat and built inputs on
2026-09-06 UTC, not a statistical speedup or failure-rate estimate. Task time
excludes seat waiting (zero for these attempts) and cache transfer.

| construction | task seconds | pose writes | driver-release seconds |
|---|---:|---:|---:|
| reference | 509.550 | 3,888 | included in each pose operation |
| prepared handles, original sequence | 320.197 | 3,888 | included in each pose operation |
| retained drivers, individual deletion | 334.959 | 216 | 76.516 |
| retained drivers, one batch deletion | 247.125 | 216 | 2.695 |

The last deletion spent 1.143 seconds inside `DeleteSelection2(0)`; the remaining
1.552 seconds covers manifest resolution, selection and readback. All four builds
passed their construction gates. Reference and prepared-handle DOF manifests are
byte-identical. The individual-deletion experiment preserves all manifest keys,
component identities and state, with a maximum numeric difference of
1.055e-9 mm. These three builds have the same rounded mass-properties/pose
fingerprint; that fingerprint is not raw CAD-byte equality or a substitute for
independent saved-model verification.

The corresponding task trace IDs, in table order, are
`0x7f0525b4ba7b594486d3f433c3fad1c3`,
`0x2e09f191b7027c43f04c5d9d4d2ab893`,
`0x1adeed12c9431a9fbbbb1dffc73ba773`, and
`0xe96bc142669b5cd06495cf34a62b3d18` in
`cad/out/reports/telemetry/traces.jsonl`. Logs and preserved native artifacts for
the experiment are under `cad/out/reports/performance-audit-20260905/`.

## Drawing attachments

Model geometry owns attachment identity. Let SolidWorks choose annotation layout
where its native API supports it; fixed sheet coordinates are not a manufacturing
requirement. A drawing must not identify a bore, datum, controlled surface or
dimension endpoint by selecting the first nearby edge. Converting an already
identified entity's location into drawing coordinates is distinct from using
coordinates to discover that entity.

Entity resolution must specify the required geometric role, validate its model
context, and reject missing or ambiguous results. Resolve all requested entities
in one traversal while the view and model are stable. Discard live entity caches
after rebuilds, configuration changes or visibility changes. Persistent references
must travel with the exact model artifact to which they belong.

The opt-in `diagnostics/probe_drawing_attachments.py` changes view positions and
scales on a uniquely named drawing copy, rebuilds the drawing, and saves/reopens
that copy. It compares supported attachment geometry signatures and reports every
excluded annotation kind explicitly. It does not prove persistent-ID equality or
behavior after a source-part topology change. Changed source parts must also be
rebuilt and their drawing recipes rerun. Check annotation values and visual
placement: successful API calls alone do not make a sheet usable for machining.

The native dimension arrangement API has a positive control in
`probe_drawing_dimension_selection.py`: a saved screw drawing selected all seven
dimensions by their returned `GetNameForSelection()` identifiers and completed one
`AlignDimensions` call. The tested `IAnnotation.Select3` shapes rejected those
same visible dimensions; that is evidence about those call shapes, not evidence
that native arrangement is unavailable.

Treat historical API limitations as hypotheses with a recorded reproduction,
including a working control and the variants not tried. In particular, a failure
to force an imported annotation to a prescribed position does not establish that
native model-annotation import is unsuitable when layout is free to change.

## Measurement and release checks

Separate cache transfer, COM-seat waiting, process startup, construction and
verification. Correlate child spans with their task and attempt; exclude mocked
test telemetry from build statistics. Do not add inclusive parents to children or
sum overlapping workers' waits as elapsed pipeline time.

Save and PDF export need separate spans: together they consumed 87 to 116 seconds
of the top assembly drawing's 107 to 140 second task in the inspected histories.

Compare repeated A/B blocks with the same source/configuration and record the
range plus operation counts. Before merge, run the full doit graph on the proposed
head, inspect affected renders/drawing sheets, and obtain clean review of that head.
Any new strategy's retry/manual-repair rate is measured separately from geometry
correctness. Zero failures in 59 representative independent trials gives a
one-sided 95 percent binomial upper bound below five percent; repeated correlated
attempts do not establish that bound.

`diagnostics/benchmark_drawing_recipes.py` runs pinned part-drawing recipes in ABBA
order, redirects managed outputs before recipe import, and fingerprints actual
helpers, configuration, templates and source parts. Both variants use the current
helpers and built parts: it measures recipe changes, not two complete historical
pipeline versions. Each trial checkpoints its result and writes distinct native,
PDF and PNG artifacts for inspection.
