# Drawing requirements, STEP face sets and process travelers

## Independent producers

`package:features` is a scoped COM leaf for `rocker_arm`, `pivot_shaft` and
`cone_pivot_post`. Its native dependency closure is those parts, not assemblies
or drawings. It writes only self-contained bundles:

```text
cad/out/features/<underscore-stem>/
  <dashed-stem>.STEP
  features.toml
```

The manifest's `step` is the adjacent STEP basename and `step_sha256` binds its
raw bytes, verified when the manifest is generated directly from that STEP.
The STEP plus `features.toml` is the consumer artefact; there are no feature
receipts or preservation certificates. `export_features.py` is SolidWorks-free.

The ordinary full `export` remains independent: it owns `cad/out/step/`, the
other existing neutral outputs and `release-neutral.json`. The scoped leaf does
not touch those paths, STL/PNG outputs, colors or source-digest ledgers. There is
no ordering or preservation relationship between the producers.

Run COM leaves through the
[supervised farm launcher](../../../DEVELOPING.md#supervised-farm-launches),
never through a local SolidWorks session or finite build timer.

## Drawing authority

Every sourced value carries `file:line` citations for Python and
`file:dotted.key.path` citations for YAML, for example
`cad/config/title_block.yaml:linear_2pl.display`. YAML paths resolve to scalar
values in the named file, not a synthetic merged registry; material-family
citations name both the part's family selection and the family's actual values.
Printed general-tolerance and note-only bands are acceptance limits, not the
underlying inch grade. Exact
model nominal coordinates are separate; BASIC and REF dimensions do not acquire
invented general-tolerance bands. Explicit native tolerance bands retain the
exact authored nominal where native display rounding has not been proved.
Precision alone does not justify a private rounding convention.

Turned-feature `z_mm` intervals describe nominal geometry along the feature's
source-frame Z axis, not an acceptance band. Shaft grooves overlay the journal
and body envelopes; the bank-derived south endpoint remains nominal cut-to-fit
geometry, not a new end-past-scribe requirement. Cone `body_axis`, `crank_axis`
and `cone_axis` are geometry-owned coordinate transforms for the model-Y
body/head, offset model-Z crank boss and inclined boss; they are not setup
frames, manufactured datums or physical bindings. Dome `base_radius` comes
from the shaft diameter; cone `volume_mm3`/`volume_cite` cite the spec's analytic volume
contract. `crank_bore.angle_tol_deg` is the cited maximum angular landing
allowance derived from the diametral angularity zone and boss length; it does
not replace the angularity FCF or give a BASIC dimension a general angle band.
Mounting `station` bands and `station_nominal` both use signed model X.

Required geometry, tolerance, precision, datum or setup information without a
source remains `unknown`. Pivot bracket is not supported until it has a drawing.
Datum face sets identify exactly the drawing's attachment surfaces, not every
face of their parent feature. Rocker datum B is the +Z broad face and C is only
the +X radial tip land; those domains are disjoint from the remaining faces.
`construction` reads the notes used by the actual drawing and cites their
declaration; `built_up_permitted` requires an explicit permission note included
there. A process plan cannot approve its own assembled substitute. The offline
source-map tripwire anchors each hand-authored Python range against its symbol
or number and loads YAML to resolve every emitted key path, including dynamic
part-registry and material-family citations.

## Face identity and native hygiene

Both export paths use the same AP214 preference/default-configuration/naming
path. `swStepExportFaceEdgeProps` exposes deterministic transient native entity
names. Existing `_part_pmi` geometry matchers resolve each feature to every
matching native patch. Zero matches, cross-feature claims, failed name/read-back
or missing/unknown exported labels fail loudly. A periodic native face can yield
multiple `ADVANCED_FACE` patches with the same label; all belong to its feature
set. References include STEP entity id, file-order ordinal and raw label, valid
only with that exact STEP digest. The STEP is never rewritten.

Names are never saved into the native part. A before/after native SHA guard runs
after closing the export document. Offline parser tests cover split patches and
ambiguous/lost labels. The rocker pivot bore must carry two labelled STEP patches;
one surviving half is a failure even if both producers make the same mistake.

## Release binding gate

`check:features_bound` is SolidWorks-free and required by `release`, not `build`.
It waits for both producers, validates the manifest with the pinned prechips
`Features` schema, verifies its adjacent scoped STEP digest, and requires every
feature's recorded face set to equal the references parsed from that STEP.
A mismatch fails with the feature name before any bundle is staged. It then
compares each feature's face labels and patch count per label between scoped and
full STEPs. Both raw digests are reported. Headers, entity
numbers and file order are not semantic identity: SolidWorks timestamps headers
and renumbers entities on re-export. This is the independent-session re-export
regression, not a byte-equality certificate.

Release staging copies the verified scoped STEP and manifest under `features/`,
separately from the existing full neutral inventory. Each face reference remains
bound only to the adjacent STEP whose digest the manifest records.

Both export leaves use the existing exporter/import-closure and `_config_deps`
cache keying. Exporter source changes therefore re-key both `package:features`
and `export` as expected. YAML comment-only edits do not change parsed dependencies;
key-path citations remain valid without forcing a rebuild for shifted lines.
There is no raw-YAML feature-task override; conservative dependency fallbacks
may over-rebuild, including after an edit irrelevant to a requirement.

## Local traveler gate

The committed plans under `cad/process/{rocker_arm,pivot_shaft,cone_pivot_post}/`
use the three shared inputs under `cad/process/shop/`. The rocker plan, policy
and cutting data came from prechips `0dd7614`; the shaft and cone plans came
from `55cae71`, with provenance headers. `shop/inventory.toml` mirrors prechips
`55cae71`'s `examples/inventory/pedro-shop.toml` verbatim. Bundle paths are adapted
and local YAML citations use key paths; external provenance, author-choice
proposals and inventory verification flags are preserved. They do not assert
purchased tools, measured geometry or approved cutting data.

```text
uv run python -m doit check:traveler_rocker_arm
uv run python -m doit check:traveler_pivot_shaft
uv run python -m doit check:traveler_cone_pivot_post
```

Each build/release gate depends on `package:features`, its own bundle and plan,
the shared shop inputs and locked consumer. It needs no full export/assembly
closure. For `<stem>` in `rocker_arm`, `pivot_shaft`, `cone_pivot_post`, its stamp
is `cad/out/reports/check-traveler_<stem>.ok`; it retains the consumer's
`report.json`, printable `traveler.html` and setup images under
`cad/out/reports/traveler_<stem>/`.

| prechips exit | CAD gate | interpretation |
|---|---|---|
| 3 | fail, no stamp | bad input or broken producer/consumer contract |
| 2 | pass | machining blockers; every `✗` finding logs at warn severity |
| 4 | pass | required unknowns remain unresolved |
| 0 | pass | no blocking/required-unknown findings |

The report retains original verdicts. Passing is **not machining approval**;
a missing reamer is not a CAD regression. Unexpected consumer exits are fatal.
The existing `_run_stamped` → `_exec` path injects `TRACEPARENT` and service
`check-traveler`; `prechips.traveler` continues the task span and appends to the
pipeline's atomic telemetry capture using separately owned provider handles.

The consumer is pinned to prechips `55cae713860a491b8925aed1ad8a24fb30502fe0`
(M3/M4/M5 merged), including telemetry compatibility without downgrading
existing OTel/pydantic-ai/logfire dependencies. Geometry rules run through
FreeCAD, not SolidWorks. prechips discovers `freecadcmd` via `FREECAD_CMD`, the
Windows FreeCAD 1.1 installation or `PATH`; an unavailable kernel produces
required-unknown findings (exit 4), not a fabricated geometry pass.
It accepts cone `angularity_dia`/`angularity_datums` without recasting the FCF as
position. The cone journal rim-break note and cited maximum remain preserved;
there is no typed per-feature edge-break field, so its inspection identity stays
explicitly `unknown` rather than implying an approved general edge break.

The shaft's T1/T2/T3 and cone's T1/M2/J3/C4 frames remain **plan-authored setup
proposals**. Their bindings and citations are preserved from the upstream plans;
the manifests' `frames.setup` remains `unknown`. A plan frame is not drawing
authority or evidence of a physically established setup. Issue #1210 item 2
therefore still needs design input. Item 6 also remains unresolved: no approved
shaft cut-to-fit owning feature or end-past-scribe acceptance band exists, so
historical `cut_past_scribe`/`end_past_scribe` numbers are not imported.
