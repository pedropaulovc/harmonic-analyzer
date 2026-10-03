# Drawing requirements, STEP face sets and process travelers

`export_features` is the scoped COM leaf for `rocker_arm`, `pivot_shaft`,
`pivot_bracket` and `cone_pivot_post`. It depends on those four native part
identities only, not on the assembly/kinematics closure. The all-model `export`
leaf orders after it because both own the same neutral STEP bytes and
`cad/out/reports/release-neutral.json` certificate. Run COM leaves through the
[supervised farm launcher](../../../DEVELOPING.md#supervised-farm-launches),
never by starting a local SolidWorks session or finite build timer.

The SolidWorks-free `cad/scripts/export_features.py` reads the spec and drawing
notes/configuration and writes `cad/out/features/<underscore-stem>.features.toml`.
Dimensions carry per-value file:line citations. The printed drawing's nominal
and tolerance bands are acceptance limits; exact model nominal coordinates are
separate. BASIC and REF dimensions do not acquire general-tolerance bands.
Unresolved requirements, precision, datums or geometry are explicitly `unknown`.
Pivot bracket currently has no registered drawing, so its model geometry is not
silently promoted into known drawing tolerances.

`construction` is `one_piece` unless the part's notes module declares an explicit
built-up permission note that is included in its drawing notes. A manufacturing
plan cannot grant itself permission to use an assembled substitute.

## Face identity and native-file hygiene

AP214 export enables `swStepExportFaceEdgeProps`. Before `SaveAs3`, the exporter
resolves every supported spec feature to all matching native patches using the
existing `_part_pmi` geometry matcher and gives them deterministic entity names.
Zero matches, a face claimed by different features, failed naming/read-back,
and missing or duplicate exported labels fail loudly. Split cylindrical patches
belong to one feature set: the rocker pivot bore is not assumed to be one face.
No ordinal STEP face number is treated as persistent identity.

Names exist only in the open export document. It is closed without saving the
native part. A before/after hash guard rejects any change to the `.SLDPRT` bytes.
The manifest reads the STEP's actual `ADVANCED_FACE` labels and is bound to the
certificate's SHA-256, checked against the referenced STEP bytes. A later export
must regenerate that binding; an old face set cannot certify a new STEP digest.
The exporter source/dependency digest and export cache inventory include the
manifest generator, face matcher and supported requirement sources.

## Local traveler gate

The committed `cad/process/rocker_arm/plan.toml` and three `cad/process/shop/`
inputs are copied from prechips `0dd7614`, with provenance headers. Only bundle
paths are changed. Author-choice process proposals and inventory `verify` flags
are retained; the copy does not assert purchased tools, measured geometry or
approved cutting data. The generated manifest refers to `../step/rocker-arm.STEP`.

```text
uv run python -m doit check:traveler_rocker_arm
```

This SolidWorks-free, opt-in gate has a file dependency on the exported manifest
and actual STEP, plus its plan, shop inputs and locked consumer dependency. Its
stamp is `cad/out/reports/check-traveler_rocker_arm.ok`; outputs are
`cad/out/reports/traveler_rocker_arm/{report.json,traveler.html}`.

| prechips exit | CAD gate | interpretation |
|---|---|---|
| 3 | fail, no stamp | bad input or broken producer/consumer contract |
| 2 | pass | machining blockers; every `✗` finding is logged at warn severity |
| 4 | pass | required unknowns remain unresolved |
| 0 | pass | no blocking/required-unknown findings |

Reports and the printable traveler keep prechips' original verdicts. Passing
this CAD gate is **not machining approval**. In particular a missing reamer is
not a CAD regression. Unexpected consumer exits remain fatal.

The existing `_run_stamped` → `_exec` path injects `TRACEPARENT` and stage
`OTEL_SERVICE_NAME=check-traveler`. The real consumer `prechips.traveler` span
continues `task check:traveler_rocker_arm`; its library-owned provider also
appends to the pipeline's atomic `cad/out/reports/telemetry/traces.jsonl` capture.

## Consumer schema boundary

The dependency is pinned to prechips `0dd7614`. Rocker-arm is the only committed
traveler gate. Cone-pivot-post emits its drawing's sourced `angularity_dia` and
`angularity_datums` requirements, which that pin does not yet accept. Bump the pin
to the prechips M2 merge before validating cone bundles; do not disguise the FCF
as a position tolerance or drop it. This does not affect the rocker-arm gate.
