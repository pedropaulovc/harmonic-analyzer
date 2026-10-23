# Drawing requirements, STEP face sets and process travelers

## Scoped producers and full-export consumers

`package:features:<stem>` is one scoped COM leaf per part whose `draw_<stem>.py`
declares requirement features. `export_features.SUPPORTED_PARTS` is derived by
an import-free AST scan of those draw scripts; adding a declaration enrolls the
part without editing a central exporter list. `package:features` is a seat-free
aggregator depending on every `package:features:<stem>` leaf, not a COM export action.
This namespace is interim until `solidworks-pool` admits top-level `features` targets; no pool change is included.
Each leaf's native dependency is its own part, not assemblies or drawing
artefacts. The three machine parts have legacy committed process plans; they
are not enrolled travelers yet. Fixture bundles expose drawing requirements too.
Each leaf writes only its own self-contained bundle:

```text
cad/out/features/<underscore-stem>/
  <dashed-stem>.STEP
  features.toml
```

The manifest's `step` is the adjacent STEP basename and `step_sha256` binds its
raw bytes, verified when the manifest is generated directly from that STEP.
The STEP plus `features.toml` is the consumer artefact; there are no feature
receipts or preservation certificates. `export_features.py` is SolidWorks-free.

The ordinary full `export` owns `cad/out/step/`, the other existing neutral
outputs and `release-neutral.json`. For enrolled feature parts it validates and
consumes the scoped feature bundles, copying their exact STEP bytes into the
full neutral inventory instead of loading draw declarations or re-deriving
manifests. It waits for `package:features`; the scoped leaves never overwrite
full-export paths, STL/PNG outputs, colors or source-digest ledgers.

Run COM leaves through the
[supervised farm launcher](../../../DEVELOPING.md#supervised-farm-launches),
never through a local SolidWorks session or finite build timer.

## Drawing authority

Each part owns module-level `requirement(name, *, kind, faces, requirements,
fields, precision=...)` calls in its draw script, next to the code that prints
the corresponding callout, dimension, FCF or note. The shared API in
`_feature_requirements.py` registers each declaration and returns a `Requirement`
descriptor for registry inspection or explicit drawing-code consumption, not
automatic print-path wiring. The rocker explicitly reads its Pivot/Strap datum
and rod FCF tolerance/datum fields and checks four imported native precisions
against descriptor values. Its local `PivotDia` guard accepts explicit primary
precision or resolves `swPrecisionFollowsDocumentSetting` (`-2`) through the
drawing's `IModelDocExtension.GetUserPreferenceInteger(swDetailingLinearDimPrecision,
swDetailingDiameterDimension)`. The effective value must match
`PIVOT_BORE.precision["dia"]`; missing or unreadable values fail closed.
The guard does not change the sheet-wide units-decimal setting. The other
three dimensions (`TopAbovePivot`, `HubLength`, `StrapThickness`) retain the
strict explicit part-owned precision assertion. The front annotations are returned
by the outline helper that imports them and combined with the detail and right
annotations; they are not re-imported for these checks. None of these guards
rewrites the imported dimension. Other return values may remain inspection-only;
colocation alone is not a printed-callout drift check.
`faces` contains the existing geometry selectors;
`requirements` preserves the ordered acceptance-field names, including explicit
unknowns. Each `fields` entry is `(value, sources)`: a string source names a
symbol in `<stem>_spec`, while `(module, NAME)` cites a symbol in another module.
Shared-helper sources name their defining module, such as
`("_drawing_hole_callout", "add_native_hole_callout")`; the lifecycle-only
`_drawing_common` module is not the authority for helpers extracted from it.
Part-level fields, geometry frames and drawing datums use colocated
`part_metadata` declarations with the same `(value, sources)` pairs; explicit
`model_sources` and `precision_sources` cite the shared frame and displayed
precision facts. Multiple metadata declarations merge without replacing prior
facts.
Feature-level `precision` remains a raw value map, but requires nonempty
`part_metadata.precision_sources` naming the actual printed precision authority;
export fails if it is absent. A spec module docstring is not a precision source.
Literal process, through-hole and note requirements cite `DRAWING_NOTES` when
the notes are the printed authority; datum and callout literals cite the drawing
function that prints them. Citing a nearby numeric spec symbol does not establish
authority for an unrelated literal. Meaningful drift checks compare against the
printed authority, not registry/manifest/selector equality.
Inherited process values such as lap/face retain their route-docstring or
native-facing authority where no printed instruction exists; such citations
do not claim that the sheet prints those process requirements.
There is one declaration convention for machine parts and shop fixtures;
specs remain the source of geometry and native dimension values. Importing a
draw module to load its declarations neither connects to SolidWorks nor runs
its guarded `__main__` entrypoint.

Drawing-owned numeric acceptance bands belong to `_printed_limits.py`, not the
declaration API: draw scripts import `limits` and `drilled_limits` directly from
it. Native geometry safeguards instead derive their bounds directly from the
unchanged `_printed_tolerance.printed_deviations` helper, retaining the same
12-place rounding. Keeping the drawing numeric API separate avoids re-keying
native recipes when only feature requirements change. `_feature_requirements.py`
neither reads title-block configuration nor belongs in native part or assembly
source closures; `_printed_limits.py` also stays out of every native closure.

Every sourced value carries `file:start-end` citations for Python and
`file:dotted.key.path` citations for YAML, for example
`cad/config/title_block.yaml:linear_2pl.display`. Python spans are resolved from
the current AST: a field cites its requirement call site and every named
spec/notes symbol it reads. Cross-script citations use symbol names, never
hand-maintained line ranges; missing symbols fail export. YAML paths resolve to
scalar values in the named file, not a synthetic merged registry;
material-family citations name both the part's family selection and the
family's actual values.
Printed general-tolerance and note-only bands are acceptance limits, not the
underlying inch grade. Exact
model nominal coordinates are separate; BASIC and REF dimensions do not acquire
invented general-tolerance bands. Explicit native tolerance bands retain the
exact authored nominal where native display rounding has not been proved.
Precision alone does not justify a private rounding convention.
The rocker's `land_angle_deg` is the two-place BASIC mirror-plane clock angle
from `_ALPHA_TOP`, printed in Manufacturing Note 1, not the retired zero-place
land-perpendicularity band. BASIC radii and height remain nominal scalars;
arc lengths remain geometry-only metadata, not separate acceptance bands.
The consumer schema does not expose unequally disposed surface-profile fields:
the sourced profile control is retained in each arc feature's `note` and its
acceptance identity remains explicitly `unknown`, never silently omitted or
replaced with a size band.

Pivot-cap fitted-head acceptance uses the consumer's required, cited `note`
field, not private schema keys. The unchanged printed counterbore callouts
retain the actual seated highest-head recess of 0.50–0.60 normal to the actual
cap top and the 2.00 minimum whole-floor thickness, including full-width edge
openings. Their citations include `fitted_counterbore_acceptance` as well as
the printed limits. The 8.40 model cut remains `depth_ref`, not a toleranced
machining depth. The wire-channel note retains normal-to-actual-top,
whole-groove-floor applicability alongside the numeric width/depth bands. Each
register note carries the boss root-radius maximum, cited to
`REGISTER_ROOT_RADIUS_MAX`, the value charged to the register assembly and
engagement proof; the native root stays sharp.
Installed `prechips==0.2.0` accepts these authored note requirements but does
not select text notes for automated tolerance inspection or its traveler
tolerance table. Schema validation therefore proves representation and
provenance, not fitted-head or every-point floor acceptance; the part's
native/spec geometry and actual-fit guards remain separate and unchanged.

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
citation checks resolve every emitted YAML key path, including dynamic
part-registry and material-family citations, and require Python spans to match
current AST declarations or call sites in existing source files.

## Face identity and native hygiene

Scoped feature exports and full exports of other parts use the same AP214
preference/default-configuration/naming path. `swStepExportFaceEdgeProps`
exposes deterministic transient native entity names.
Existing `_part_pmi` geometry matchers resolve each feature to every
matching native patch. Zero matches, cross-feature claims, failed name/read-back
or missing/unknown exported labels fail loudly. A periodic native face can yield
multiple `ADVANCED_FACE` patches with the same label; all belong to its feature
set. References include STEP entity id, file-order ordinal and raw label, valid
only with that exact STEP digest. The STEP is never rewritten.

Names are never saved into the native part. A before/after native SHA guard runs
after closing the export document. Offline parser tests cover split patches and
ambiguous/lost labels. The rocker pivot bore must carry two labelled STEP patches;
one surviving half is a failure even if the full inventory copies that mistake.

## Release binding gate

`check:features_bound` is SolidWorks-free and required by `release`, not `build`.
It waits for scoped bundles and the full neutral inventory, validates the
manifest with the pinned prechips `Features` schema, verifies its adjacent
scoped STEP digest, and requires every feature's recorded face set to equal
the references parsed from that STEP. A mismatch fails with the feature name
before any bundle is staged. The gate requires byte-identical scoped and full
STEPs, reports both raw digests, and retains the split rocker pivot-bore patch
check. Full export now copies the scoped STEP bytes: this checks authoritative
bundle binding and copied neutral inventory, not an independent-session COM
re-export.

Release staging copies the verified scoped STEP and manifest under `features/`,
separately from the existing full neutral inventory. Each face reference remains
bound only to the adjacent STEP whose digest the manifest records.

Each `package:features:<stem>` cache key includes the **entire** closure of its own
draw module, symbol-citation module closures, registry/config dependencies,
release revision and native part artefact identity/execution token, plus shared
exporter/helper sources. Declaration discovery and source-path construction
parse Python statically without importing draw modules; declaration values are
validated when exporting.
Feature subprocesses restrict `fit(...)` reads to the tolerance groups folded
into their own cache keys via `HARMONIC_FIT_GROUPS`. Undeclared group reads raise
`KeyError` rather than producing cacheable success; when no groups are declared,
the empty guard refuses every group. The action-free `package:features`
aggregator remains unrestricted.
A draw-only edit re-keys that part's features leaf, not the other features
leaves or its native part/assembly builds. This is file-granular coupling, not
declaration-only coupling: edits to shared drawing helpers, `_drawing_common`,
layout-audit helpers or `_pdf_ink` re-key all 18 enrolled feature leaves.
Full `export` consumes bundle outputs rather than the draw closures directly;
changed bundle bytes can therefore re-key it downstream. Feature leaves use
`uptodate: [False]`, like full export, so each invocation reaches the cache probe
even when local targets exist; target existence alone does not certify a bundle.
The seat-free `package:features` aggregator has no all-parts COM source key.
YAML comment-only edits do not change parsed dependencies; key-path citations
remain valid without forcing a rebuild for shifted lines. There is no raw-YAML
feature-task override; conservative dependency fallbacks may over-rebuild,
including after an edit irrelevant to a requirement.

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
Binding refuses a spec solid without an explicit `measured.status` (#1462),
since prechips would otherwise trust it as installed nominal geometry.

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
`prechips:<stem>` task family. It is currently **empty**. The rocker plan is
migrated but held until its traveler reaches exit 0; the legacy shaft and cone
plans remain tracked but are stale against the pinned prechips; they are neither
run nor shipped. A stem enrolls only after its
migrated plan reaches exit 0 on real exported geometry. See
[`cad/process/README.md`](../../process/README.md) for authoring and enrollment.

For an enrolled stem:

```text
uv run --frozen python -m doit prechips:<stem>
```

Every enrolled traveler is required by both `build` and `release`. Its task
depends only on its own `package:features:<stem>` leaf, its scoped bundle and tracked plan, the shop
files, CAD-tagged fixture spec modules, the locked consumer and executed wrapper
closure. It runs locally on the submitter without a SolidWorks seat, including
under the farm executor, and needs FreeCAD 1.1 (see
[`DEVELOPING.md`](../../../DEVELOPING.md#process-traveler-prerequisites)).
The consumer is pinned to PyPI `prechips==0.2.0`; no upstream examples are run by
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
prechips 0.2.0 does not record an HTML digest itself. After a successful default
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

Each migrated or enrolled plan's tracked `[drawing].revision` literal equals
`cad/config/release.yaml:next_revision`. `_process_plans.revision_stems()` owns
this deduplicated union, independently of traveler enrollment. Publisher
preflight checks held migrated plans' authored freshness without requiring
an exported manifest; enrolled plans retain strict authored/configured/manifest
agreement, even if also migrated. Revision participation does not enroll a held
plan or imply machining qualification. Historical unmigrated plans stay unchanged.
The publisher prepares source/temporary pairs for `release.yaml` and every
revision participant before publication. It changes only the single revision
line in each plan's `[drawing]` section, preserving
other bytes. After publication, replacements install in order; a failed
replacement reports which sources were already installed and names manual
recovery for the remaining revisions. All temporary files are discarded.
`--no-publish` and failed publication leave the tracked images and revisions
byte-identical. The generated-only follow-up exemption covers only generated
README images, `next_revision`, and matching migrated/enrolled-plan revision lines;
other plan edits require the [ordinary PR requirements](../../../AGENTS.md#minimum-merge-gate-every-pr),
including focused source checks, appropriate native proof and applicable reviews.
An individual PR or stack does not require a full build before merge; the
release manager runs the full build on main and releases only green main.
