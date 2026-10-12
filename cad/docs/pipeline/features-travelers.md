# Drawing requirements, STEP face sets and process travelers

## Independent producers

`package:features` is a scoped COM leaf for `ch_rocker_arm`, `ch_pivot_shaft`,
`dt_cone_pivot_post` and every spec-driven shop fixture in
`export_features.SPEC_DRIVEN_PARTS` (`export_features.SUPPORTED_PARTS` is the
whole list). Its native dependency closure is those parts, not assemblies or
drawings. The three machine parts have legacy committed process plans; they are
not enrolled travelers yet. Fixture bundles expose drawing requirements too.
It writes only self-contained bundles:

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
there. A process plan cannot approve its own assembled substitute. Offline
citation checks load YAML to resolve every emitted key path, including dynamic
part-registry and material-family citations. Python citations identify source
line ranges but are not anchor-checked.

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

## Plan and fixture binding

`cad/process/` holds HA-authored process plans and shared shop inputs. Tracked
plans use stable bare face labels (`HAF_<FEATURE>__P<nn>`), never STEP entity
numbers or exact `#…/ADVANCED_FACE[…]` refs. Before prechips runs,
`_process_plans.bind_plan(stem, out)` writes
`cad/out/travelers/<stem>/plan.toml`, replacing whole quoted label tokens with the
fresh manifest's exact refs and pointing `features` at that manifest. A label
with several patches expands inside a list; a multi-face scalar, unknown label
or label owned by another part fails with its source line. Prose containing a
label is not rewritten, and other bytes stay unchanged. Plans carry no
`[paths]`: the wrapper supplies the shop paths as CLI flags.
Binding requires the plan's drawing revision to equal the scoped manifest's
revision; release preflight also compares it with the configured next revision.

A shop-made fixture's inventory entry uses `cad = "<fixture-stem>"` and no
hand-authored `solids`. Its TL spec exports `PRECHIPS_SOLIDS`, derived from the
same constants as the SolidWorks fixture in the fixture frame.
`_process_plans.bind_shop(out)` writes the bound inventory under
`cad/out/travelers/_shop/`, inserting those primitives and removing the HA-only
`cad` key. Tracked shop files and plans are never rewritten by binding.

Task-graph loading validates that every inventory CAD fixture's
`<fixture-stem>_spec.py` exists as a file. Malformed inventory and missing fixture
specs are captured as bad-input diagnostics on the enrolled `prechips:<stem>`
tasks, rather than aborting graph construction; build, gallery, check and part
tasks remain available. Selecting an affected traveler fails with its task label,
inventory path and captured diagnostic (including the missing spec path), without
bundle dependencies, geometry export, kernel launch or a success stamp. Add the
missing spec file or correct the inventory's `cad` stem before retrying.

## Strict local travelers and enrollment

`_process_plans.TRAVELER_STEMS` is the enrollment authority for the
`prechips:<stem>` task family. It is **empty** in this infrastructure change.
The legacy rocker, shaft and cone plans remain tracked but are stale against
prechips 0.1; they are neither run nor shipped. A stem enrolls only after its
migrated plan reaches exit 0 on real exported geometry. See
[`cad/process/README.md`](../../process/README.md) for authoring and enrollment.

For an enrolled stem:

```text
uv run --frozen python -m doit prechips:<stem>
```

Every enrolled traveler is required by both `build` and `release`. Its task
depends on `package:features`, its scoped bundle and tracked plan, the shop
files, CAD-tagged fixture spec modules, the locked consumer and executed wrapper
closure. It runs locally on the submitter without a SolidWorks seat, including
under the farm executor, and needs FreeCAD 1.1 (see
[`DEVELOPING.md`](../../../DEVELOPING.md#process-traveler-prerequisites)).
The consumer is pinned to PyPI `prechips==0.1`; no upstream examples are run by
this task family.

| prechips exit | build/release gate | interpretation |
|---|---|---|
| 0 | pass only after output verification | no blocking/required-unknown findings |
| 2 | fail, no stamp | machining blockers |
| 3 | fail, no stamp | bad input or broken binding |
| 4 | fail, no stamp | required unknowns, including unavailable geometry kernel |
| other nonzero | fail, no stamp | consumer failure |

Outputs live under `cad/out/travelers/<stem>/`: the bound plan, `report.json`,
printable `traveler.html`, setup PNGs and operation inspection PNGs. The full
wrapper deletes the old report and HTML before binding so a binding error or
consumer failure cannot retain a previous traveler generation.
Completeness is derived from the plan: one `setup-S<ordinal>.png` per setup plus
every name from `prechips.report.inspection_sketch_names(plan)`. The report must
record matching SHA-256 hashes for every render under `inputs["render:…"]`,
declare `expected_exit == 0`, and match the manifest's `step_sha256`.
Its `hash` must equal `prechips.report.report_hash(report)`, so editing report
metadata without regenerating its canonical content hash also invalidates it.
prechips 0.1 does not record an HTML digest itself. After a successful default
run, the wrapper adds `inputs["traveler:html"]` with the exact HTML path,
SHA-256 and original `source_report_hash`, then recomputes the report's canonical
hash. The HTML's `prechips-report` meta tag keeps that original upstream hash,
avoiding a circular HTML/report hash. Verification requires the recorded HTML
bytes and recomputes the original report hash without this HA-added record;
both identities must match. An existing HTML certificate cannot be resealed.
This is hashed report material, not a free-standing sidecar, and verification
does not regenerate HTML or invoke FreeCAD. Native artifact binding is tracked
in [prechips issue #183](https://github.com/pedropaulovc/prechips/issues/183).
Its input digests must also match the bound plan, scoped feature manifest and
STEP, inventory, shop policy and cutting data. Verification regenerates the
tracked plan and shop bindings in memory and requires byte equality with the
bound files; a report cannot certify a different tracked source generation.
`verify_traveler` is used after execution, by the task's `uptodate` check and
during release staging. Changed inputs or renders force a rerun rather than
allowing a stale `cad/out/reports/prechips-<stem>.ok` stamp to pass.

The authoring wrapper's `--check` mode writes a separate bound plan,
`.check/_shop/` inputs and consumer outputs under
`cad/out/travelers/<stem>/.check/`. It references the current scoped feature
bundle without modifying it. All check-mode output rewrites and render cleanup
stay in scratch: the full bound plan, shared shop and traveler outputs remain
untouched even after source edits. Check mode does not verify full completeness.

The `_run_stamped` → `_exec` path injects `TRACEPARENT` and service
`prechips-traveler`; the wrapper continues the task trace with
`pipeline.prechips_traveler`, `prechips.bind` and `prechips.verify` spans and
captures prechips telemetry unchanged. The pipeline helper accounts for process
startup. Binding, completeness and nonzero consumer failures mark the pipeline
span as failed. A strict pass is not permission to machine: shop measurements,
physical setup verification and machining approval remain human responsibilities.

## Release travelers and revisions

After staging the verified `features/` bundles, `cut_release.py` calls
`_process_plans.stage_travelers(out, stage)` under `release.travelers_stage`.
Each enrolled traveler is verified against the **staged** feature manifest,
then only the validated byte snapshots of its bound plan and required outputs
are written to `travelers/<stem>/` in the release ZIP. The validated shared shop
inputs are staged under `travelers/_shop/` too. Check scratch, lock files and
stray temporary files are excluded; staging does not re-read an entire directory
after verification. `facts["travelers"]` records the staged paths, release notes
list them, and the final provenance manifest hashes their files. Any incomplete
report, changed render/input, source binding drift or mismatched STEP digest
fails before the ZIP is sealed. Empty enrollment stages and lists no travelers.

Each enrolled plan's tracked `[drawing].revision` literal equals
`cad/config/release.yaml:next_revision`. The publisher prepares source/temporary
pairs for `release.yaml` and every enrolled plan before publication. It changes
only the single revision line in each plan's `[drawing]` section, preserving
other bytes. After publication, replacements install in order; a failed
replacement reports which sources were already installed and names manual
recovery for the remaining revisions. All temporary files are discarded.
`--no-publish` and failed publication leave the tracked images and revisions
byte-identical. The generated-only follow-up exemption covers only generated
README images, `next_revision`, and matching enrolled-plan revision lines;
other plan edits require the ordinary merge gates.
