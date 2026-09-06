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

Component handles and target transforms should be prepared once within the stable
post-copy document phase. Reusing them must preserve the order of pose writes,
driver creation, driver deletion and all solver-branch witnesses. Cached handles
must not survive document replacement or topology changes.

Validation compares the resulting component poses, mate health, operational DOF
and saved/reopened assembly with the reference construction. Aggregate telemetry
must distinguish preparation, resetting poses and authoring drivers, and record
the operation counts without emitting a span for every component.

Changing the solver sequence requires a separate live experiment. Fewer COM calls
are useful evidence; a single faster wall-clock run is insufficient because seat
load and SolidWorks state vary.

## Drawing attachments

Model geometry owns attachment identity. Sheet coordinates own view positions,
annotation positions and leader layout. A drawing must not identify a bore, datum,
controlled surface or dimension endpoint by selecting the first nearby edge.

Entity resolution must specify the required geometric role, validate its model
context, and reject missing or ambiguous results. Resolve all requested entities
in one traversal while the view and model are stable. Discard live entity caches
after rebuilds, configuration changes or visibility changes. Persistent references
must travel with the exact model artifact to which they belong.

Pilot validation changes sheet positions and scales, rebuilds the source model,
and saves/reopens the drawing. Assertions must check which model entities the
annotations reference, in addition to checking their values and visual placement.
The resulting sheets must remain complete and readable for machining.

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
