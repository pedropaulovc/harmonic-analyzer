# Drawing requirements, STEP face sets and process travelers

## Scoped producers and full-export consumers

`package:features:<stem>` is one scoped COM leaf per part with its own drawing:
`export_features.SUPPORTED_PARTS` lists every `draw_<stem>.py` beside its part
builder `build_<stem>.py` (assembly drawings pair with `build_<x>_assembly.py`),
read from the directory without importing either; `test_part_coverage` holds
it equal to the drawing registry's part drawings. Tier-1 standard hardware
(delivered as its HARDWARE.md row) and the consumable recording paper have no
drawing and no bundle; purchased `*_vn_*` parts and shop tooling `*_tl_*` with
a drawing have one. `DECLARED_PARTS`, derived by an import-free AST scan of the
draw scripts, are the parts that declare requirement features; adding a
declaration enrolls the part's features without editing a central exporter
list. `package:features` is a seat-free
aggregator depending on every `package:features:<stem>` leaf, not a COM export action.
This namespace is interim until `solidworks-pool` admits top-level `features` targets; no pool change is included.
Each leaf's native dependency is its own part, not assemblies or drawing
artefacts, and it reads no drawing: it labels and exports geometry only.
`package:manifest:<stem>` (seat-free, `export_features.py <stem>`) then binds
the drawing's declarations to that geometry and writes `features.toml`;
`package:manifest` aggregates them. Parts with an enrolled (non-placeholder)
plan feed their manifest to a prechips traveler, and parts with a CAM recipe
feed it and its STEP to their NC programs (below). Fixture bundles expose
drawing requirements too. Each part's bundle is self-contained:

```text
cad/out/features/<underscore-stem>/
  <dashed-stem>.STEP          (COM leaf: every face labelled)
  <dashed-stem>.faces.json    (COM leaf: face inventory bound to that STEP)
  features.toml               (package:manifest:<stem>, no SolidWorks)
```

The COM leaf gives every native face a deterministic ASCII label with
`IPartDoc::SetEntityName` (`HAF_F0001`..., numbered by rounded box, then walk
position; a face SolidWorks already named, e.g. for a mate, keeps its name),
reads each back, exports the STEP with face/edge properties on so the labels
reach its `ADVANCED_FACE` entities (a split periodic face carries its label on
both halves), and closes the part unsaved. Beside each STEP,
`<stem>.faces.json` (`harmonic-analyzer/face-inventory@1`) records the STEP's
`step_sha256` and, per label, the native surface identity, parameters, outward
normal and box: exactly what the drawing's face selectors read. Its labels must
be exactly the STEP's face labels.

The manifest step runs each declared feature's selectors (`FaceSpec.matches`,
the matcher the native walk used to run) over the inventory's recorded
geometry, then lists every STEP face the claimed labels carry as
`#<entity>/ADVANCED_FACE[<ordinal>]/<label>`. A new or changed `requirement(...)`
declaration therefore binds to an already-exported (or fetched) STEP without
SolidWorks; only a geometry or exporter change needs the COM leaf. A selector
that matches no recorded face, or a face two features claim, fails the
manifest. The manifest's `step` is the adjacent STEP basename and `step_sha256`
binds its raw bytes. The STEP, inventory and `features.toml` are the consumer
artefact; there are no feature receipts or preservation certificates.
`export_features.py` is SolidWorks-free.

An undeclared part's manifest binds no feature. It
reads no drawing module and holds what needs no declaration: `part`, `units`,
the release `drawing.revision` and `number`, `material`, `step` and
`step_sha256`, `general_tolerances`, `notes.process` and `edge_break`, the model
frame (cited to the builder's docstring) and, when the part's notes module (or,
without one, its spec) defines `DRAWING_NOTES`, those notes and `construction`
(otherwise both are `unknown`). `precision` is `unknown`, `datums` is empty and
`features` is an explicitly empty table: an empty `[features]` means the drawing
declares no requirement, whereas a missing or unparseable manifest is an error.

The ordinary full `export` owns `cad/out/step/`, the other existing neutral
outputs and `release-neutral.json`. For enrolled feature parts it validates and
consumes the labelled STEPs (each must agree with its inventory), copying their
exact bytes into the full neutral inventory instead of loading draw
declarations; it reads no manifest, so a declaration edit never re-keys it. It
waits for `package:features`; the scoped leaves never overwrite full-export
paths, STL/PNG outputs, colors or source-digest ledgers.

Run COM leaves through
[`farm_build.py`](../../../DEVELOPING.md#farm-builds-farm_buildpy),
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
symbol in the part's feature spec (normally `<stem>_spec`), while `(module, NAME)`
cites a symbol in another module.
Shared-helper sources name their defining module, such as
`("_drawing_hole_callout", "add_native_hole_callout")`; the lifecycle-only
`_drawing_common` module is not the authority for helpers extracted from it.

When a configured producer's rework spans members, a requirement for a
non-default member names it with `configuration="<Member>"` (no current part
declares one; the oblique jig's leadscrew kit `FeedNut` did until 2026-11-17).
`export_models --features` shows every non-default registry member after the
default export, labels its faces and saves `<part>--<mesh key>.STEP` and its
inventory beside the bundle STEP (the member's
`_part_configuration_exports.mesh_key`, lowercased: a `FeedNut` member saves
`<part>--feednut.STEP`), the same name as the full export's neutral member
STEP, which `features_bound` then requires to be that exact copy. Every member
is exported whether or not a declaration names it, so a later member
declaration binds offline too. The manifest records every member STEP and its
digest under `member_steps.<Member>`, marks each member feature with
`configuration`, and binds that feature's `faces` to its member's STEP.

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

Every sourced value carries `file.py#symbol` citations for Python and
`file:dotted.key.path` citations for YAML, for example
`cad/config/title_block.yaml:linear_2pl.band_mm`. A field cites its requirement
call (`draw_<stem>.py#requirement:<name>`; part metadata `#part_metadata:<n>`)
and every named spec/notes symbol it reads (`#__doc__` for a module docstring).
Citations carry no line numbers; missing symbols fail export. YAML paths resolve to
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
The manifest has no unequally disposed surface-profile fields: the sourced
profile control is retained in each arc feature's `note` and its acceptance
identity remains explicitly `unknown`, never silently omitted or replaced with
a size band.

Pivot-cap fitted-head acceptance uses the manifest's required, cited `note`
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
Authored note requirements are recorded as cited notes, not as numeric
tolerance bands. The manifest therefore records representation and
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
source remains `unknown`.
Datum face sets identify exactly the drawing's attachment surfaces, not every
face of their parent feature. Rocker datum B is the +Z broad face and C is only
the +X radial tip land; those domains are disjoint from the remaining faces.
`construction` reads the notes used by the actual drawing and cites their
declaration; `built_up_permitted` requires an explicit permission note included
there. A process plan cannot approve its own assembled substitute. Offline
citation checks resolve every emitted YAML key path, including dynamic
part-registry and material-family citations, and require Python symbols to name
current top-level declarations or registered requirement/metadata calls.

## Face identity and native hygiene

Scoped feature exports and full exports of other parts use the same AP214
preference/default-configuration path. `swStepExportFaceEdgeProps` exposes the
transient native entity names, so every exported face carries its label.
The manifest step resolves each feature to every matching recorded face with
the drawing's existing geometry selectors. Zero matches, cross-feature claims,
failed label read-back, an inventory label that labels no STEP face, or a STEP
face whose label the inventory lacks, fail loudly. A periodic native face can
yield multiple `ADVANCED_FACE` patches with the same label; all belong to its
feature set. References include STEP entity id, file-order ordinal and raw
label, valid only with that exact STEP digest. The STEP is never rewritten.

Labels are never saved into the native part. A before/after native SHA guard
runs after closing the export document. Offline tests cover split patches and
ambiguous/lost labels. The rocker pivot bore must bind two STEP patches
(`export_features.STEP_FACE_COUNTS`); one surviving half fails the manifest and
the release gate.

## Release binding gate

`check:features_bound` is SolidWorks-free and required by `release`, not `build`.
It waits for scoped bundles, their manifests and the full neutral inventory.
Its checks are HA-owned; no prechips schema is involved. Every STEP's inventory
must bind that STEP's bytes and name exactly its face labels. It requires the
manifest's `part` to identify the bundle's part, its `step` to name the
adjacent STEP and its `step_sha256` to match that STEP's raw bytes, its
`drawing.revision` to be the revision being released (an older one is a stale
bundle), a non-empty `features` table of tables for a declared part and an
empty one for any other, `member_steps` to bind every member STEP, and every
feature's recorded faces to be existing STEP faces (entity id, ordinal and
label) that cover every face their labels carry, with no label claimed by two
features. It does not reload declarations. A mismatch fails before any bundle
is staged. The gate requires byte-identical scoped and full STEPs, reports both
raw digests, and retains the split rocker pivot-bore patch check. Full export
copies the scoped STEP bytes: this checks authoritative bundle binding and
copied neutral inventory, not an independent-session COM re-export.

Release staging copies the verified scoped STEPs, inventories and manifest
under `features/`, separately from the existing full neutral inventory. Each
face reference remains bound only to the adjacent STEP whose digest the
manifest records.

Each part's `package:features:<stem>` cache key is the generic exporter's
source closure, the config that closure reads for that part (its registry row,
`title_block.yaml`, `release.yaml`; never another part's row) and the native
part artefact identity/execution token. It holds no drawing module, so no
declaration or drawing edit re-keys a COM leaf.

`package:manifest:<stem>` is not cached: it is a seat-free doit task whose file
dependencies are the **entire** closure of the part's draw module (declared
parts), symbol-citation module closures, registry/config dependencies, the
release revision and the labelled STEPs and inventories it binds. Declaration
discovery and source-path construction parse Python statically without
importing draw modules; declaration values are validated when the manifest is
written. A draw-only edit re-runs that part's manifest task, not any COM leaf
or native part/assembly build; edits to shared drawing helpers,
`_drawing_common`, layout-audit helpers or `_pdf_ink` re-run every declared
part's manifest task, each a fraction of a second. An undeclared part's
manifest holds no draw module: the exporter, the closure of its
`DRAWING_NOTES` owner, the notes/spec files read to find it, its builder file
(the frame citation), registry/config and the release revision.
Every native part carries the release revision (`_part_properties`
`Revision`), so a release-revision bump rebuilds every `part:<stem>` and,
through its artefact identity, re-runs all 131 `package:features:<stem>`
SolidWorks leaves (123 more than the eight declared parts): each opens the part,
labels its faces, saves the STEP and closes, about 10 s of seat time plus the
per-leaf farm overhead (roughly 2-2.5 worker-hours, 15-20 min wall at farm
parallelism 8 on an idle queue). The full export still opens each part again
for STL/PNG, so the STEP work moves rather than disappears; the added cost is
the per-leaf dispatch and the second open.
Full `export` consumes the labelled STEPs and inventories rather than any
manifest or draw closure; changed STEP bytes can therefore re-key it
downstream. Feature leaves use `uptodate: [False]`, like full export, so each
invocation reaches the cache probe even when local targets exist; target
existence alone does not certify a bundle. The seat-free `package:features`
and `package:manifest` aggregators have no all-parts COM source key.
YAML comment-only edits do not change parsed dependencies; key-path citations
remain valid without forcing a rebuild for shifted lines. There is no raw-YAML
feature-task override; conservative dependency fallbacks may over-rebuild,
including after an edit irrelevant to a requirement.

## Process plans

`cad/process/<stem>/plan.toml` is a plan in the restarted prechips format
(see the [prechips README](https://github.com/pedropaulovc/prechips)). Its
`[cad]` table names the part's scoped manifest,
`file = "../../out/features/<stem>/features.toml"`, and the prechips adapter
that reads it; root `shop = "../shop"` names the shared shop directory. Text
and numeric fields bind CAD values as `{{cad.<name>}}` and the plan's own
`[parameters]` as `{{process.<name>}}`; prechips refuses unknown names. A plan
directory may also hold `diagrams/*.svg` files that the plan names. HA does not
rewrite, bind or stamp plans: prechips reads the tracked plan and the exported
manifest directly, with no STEP reader, geometry kernel or hash check.

`cad/process/shop/` is the prechips shop directory (machines, workholding,
gauges, limits, tools and settings) and holds every fact its schema can
express: `common.toml` holds the machines, workholding, limits and gauges and
every record plans of more than one subsystem family name, and
`<prefix>.toml` the records only that family names. prechips (0.11.10 and
later) merges the files by section and refuses a key defined in two of them;
HA reads it the same way through `_process_plans.load_shop()`. Facts prechips
has no field for live in `cad/config/shop-equipment/*.toml`,
read through `cad/scripts/_shop_equipment.py`. An object may appear in both with disjoint
fields; no field is duplicated. No COM build closure reads either directory: neither
is in a leaf's cache key (AGENTS.md, "Fine-grained config deps"). See
[`cad/process/README.md`](../../process/README.md).

## Travelers

`_process_plans.TRAVELER_STEMS`, derived from the plan files, lists the parts
with a `prechips:<stem>` task: every `cad/process/<stem>/plan.toml` whose
`revision` is not `"placeholder"` (a plan that cannot be read fails task
loading, naming it). A stem is a part's, or a family's: a family plan binds
several parts' manifests under prechips `[[parts]]`
(`_process_plans.family_parts`; `sh_column_clamp` serves both column clamp
halves, owner rulings 2026-11-24), its task depends on every part's
`package:manifest:<part>` and writes, beside the shared sheets, a one-page
placeholder `<part slug>-traveler.pdf` per part that points to the shared
one (`cad/process/README.md`, Family plans). Parts are enrolled by the CNC migration (owner ruling
2026-11-17): the machine premise is a CNC mill, the CNC-converted PM-30MV, and
a manual lathe, the PM-1127VF-LB, so a milled part's hobby sheet is the CNC
setup sheet for its NC programs. The oblique trammel jig's eight parts, the
previously enrolled ones, were deleted (owner ruling 2026-11-17, #2885).

prechips is not an HA dependency while it stabilises
([#2502](https://github.com/pedropaulovc/harmonic-analyzer/issues/2502)): a
locked prechips made every prechips release change `uv.lock`, which until #2882
re-keyed every `check:machinist_review:*`, so prechips stays out of the lock. `build` runs every
enrolled traveler beside the drawing PDFs and `build_bare` runs none; `release`
runs every one and ships its hobby sheet as a PDF (owner rulings 2026-11-14,
superseding the 2026-11-11 ruling that travelers stay out of `build` and
releases; see [Releases](#releases)). The plans, the shop file and the setup
pictures stay in HA.

Run it for an enrolled part with:

```text
uv run --frozen python -m doit prechips:<stem>
```

or render one sheet by hand, without doit:

```text
uvx --from prechips@latest prechips traveler cad/process/<stem>/plan.toml --profile hobby --out <file>
```

Both need the part's feature manifest at `cad/out/features/<stem>/features.toml`:
from a build (the task's `package:manifest:<stem>` dependency produces it), or
fetched from a release with no SolidWorks and no farm run:

```text
uv run --frozen python cad/scripts/fetch_features.py <stem> [--release vNN]
```

A family plan needs each of its parts' bundles: fetch every part stem
(`sh_column_clamp_front`, `sh_column_clamp_back`), then run the wrapper or
`cam_nc.py` with the family's stem (`sh_column_clamp`).

Releases cut after v50 ship every drawn part's bundle under `features/<stem>/`
(v50 and earlier only the declared parts', so an older `--release` fails for
any other part with "the release carries no ... bundle"); the script
range-reads just those ZIP members and refuses a bundle that does not bind its
STEP. When the part's `geometry` inputs (`part:<stem>` and the labelled-STEP
export code) differ between the release's tag and the working tree it reports
the bundle STALE (exit 2, nothing written unless `--accept-stale`): only a farm
build of `package:features:<stem>` makes it current. Otherwise it rebinds
`features.toml` from this checkout's declarations over the fetched STEPs and
inventories, exactly as `package:manifest:<stem>` would, so a new or changed
`requirement(...)` needs no farm run. A release cut before face inventories
shipped can be neither rebound nor validated, so it is always STALE (use a
newer release or `--accept-stale`). With the
bundle in place run the wrapper or `uvx` form (and `cad/scripts/cam_nc.py
<stem>` for NC); the doit tasks would first run the feature leaf. Both always
use the latest prechips release from PyPI, so they need `uv` and network access
to PyPI. After editing declarations on top of a local bundle, rerun
`uv run --frozen python cad/scripts/export_features.py <stem>` to rebind it.

The task runs `cad/scripts/prechips_traveler.py <stem>`, which removes any
previous `traveler.html`, `traveler-hobby.html` and `<slug>-traveler.pdf` under
`cad/out/travelers/<stem>/`, finds the PDF browser, resolves the newest prechips
release, logs its version once (`_telemetry.info`, shown on the console at
`HARMONIC_VERBOSITY=info`), renders both sheets from the same plan with that
version, and prints the hobby sheet to PDF:

```text
uv tool run --from prechips@latest python -c "<print prechips version>"
uv tool run --from prechips==<version> prechips traveler cad/process/<stem>/plan.toml --profile pro --out cad/out/travelers/<stem>/traveler.html
uv tool run --from prechips==<version> prechips traveler cad/process/<stem>/plan.toml --profile hobby --out cad/out/travelers/<stem>/traveler-hobby.html
msedge --headless --no-pdf-header-footer --user-data-dir=<temp> --print-to-pdf=cad/out/travelers/<stem>/<slug>-traveler.pdf file:///…/traveler-hobby.html
```

`<slug>` is the dashed stem (`ch-rocker-arm`). The browser
is `HARMONIC_PDF_BROWSER` when set, else the first of `msedge`, `chrome`,
`chromium` or `google-chrome` on `PATH`, else Edge or Chrome at its default
Windows install location. The print keeps the sheet's own `@page` (Letter,
0.5 in margins) and drops the browser's header and footer; a throwaway profile
keeps it out of any running browser session.

`@latest` makes uv revalidate its cached PyPI index and ignore a
`uv tool install`-ed copy; a bare `--from prechips` may reuse either, so the
hand command uses `@latest` too. Pinning the two renders to the resolved
version keeps both sheets on the release that was logged. If `uv` or a browser
is missing, or the latest release cannot be resolved, the wrapper exits 1
before writing a sheet.

If either render exits nonzero, the wrapper removes every output. A render whose
stderr carries uv's own diagnostic (`error:` for fetch, parse or install
failures, exit 2; `×` for an unresolvable pin, exit 1) is a uv failure and the
wrapper exits 1; otherwise it returns prechips' exit code, so exit 2 is always a
prechips refusal. The hobby run starts only after the pro run passes, and the
print only after both pass; a print that fails or leaves no `%PDF-` file exits 1
and removes every output. The task is
SolidWorks-free, submitter-only (including under the farm executor) and not
remote-cache-keyed. Because its generator version floats, it always runs when
requested (`uptodate: [False]`). Its only task dependency is its own
`package:manifest:<stem>` task (which needs the `package:features:<stem>`
leaf). Its file dependencies are every file in the
plan directory (including the `diagrams/*.svg` setup pictures the hobby sheet
embeds), every shop directory file, the scoped `features.toml` and the wrapper's
script closure. Its targets are the stamp
`cad/out/reports/prechips-<stem>.ok`, `traveler.html`,
`traveler-hobby.html` and `<slug>-traveler.pdf`; the stamp is removed before each run so a refusal never
leaves an old stamp.

| exit (either profile) | task | meaning |
|---|---|---|
| 0 from both, PDF printed | pass | `traveler.html`, `traveler-hobby.html` and `<slug>-traveler.pdf` written |
| 1 (wrapper) | fail, no stamp | infrastructure failed: `uv` or a browser missing, the latest prechips could not be resolved, a render's `uv tool run` failed before prechips ran (stderr carries uv's `error:` or `×` diagnostic, not prechips' `prechips:` prefix), or the PDF print failed; not a refusal, so no file kept and the plan is not at fault |
| 2 | fail, no stamp | refusal: bad input, or a failed enforced check (`stock_fit`, `turning_deflection`, `cutting_speeds`, `tool_sizing`, `indexing`, `gauge_capability`, `lathe_holding`, `vise_holding`, `machine_capacity`); no file kept |
| other nonzero | fail, no stamp | consumer failure; no file kept |

The `pro` profile enforces every check listed above and prints a concise sheet.
The `hobby` profile prints the plan's setup pictures and requires one for every
setup. A refusal names the check; a pass prints no checker text on the sheet.
Each HTML traveler is one standalone file. It carries no report, hash or
certificate, and a pass is not permission to machine: shop measurements,
physical setup verification and machining approval remain human
responsibilities.

The `_run_stamped` → `_exec` path injects `TRACEPARENT` and service
`prechips-traveler`; the wrapper continues the task trace with a
`pipeline.prechips_traveler` span, a `prechips.resolve` span around the version
lookup, one `prechips.traveler` span per profile around the CLI and a
`prechips.pdf` span (with `browser`) around the print. The
pipeline and per-profile spans carry the resolved `prechips.version`.
A missing plan, an unresolved version, a nonzero exit or a failed print marks the pipeline span
as failed.

Each plan's `[cad]` table names a neutral prechips adapter and the manifest's
`part` id. prechips adapters are tied to the
manifest's contents: a drawing change that alters a part's manifest
requirements needs a prechips adapter release before its traveler passes again.

## NC programs

`_cam_programs.CAM_STEMS`, derived from the recipe files, lists the parts
milled on the CNC mill (each needs an enrolled plan; a family plan's one
recipe posts every part's programs, the shared ones once, into the family's
`cad/out/nc/<family stem>/` under one manifest binding each part's bundle as
`features/<part stem>` and `step/<part stem>`); each has a
`cad/process/<stem>/cam.py` CAM recipe and a `cam:<stem>` task that posts its
G-code with headless FreeCAD CAM (`cad/scripts/cam_nc.py`, FreeCAD 1.1 or
later). `build` and `release` run every enrolled one and `build_bare` runs
none (owner ruling 2026-11-17). Like a traveler, the task is SolidWorks-free,
submitter-only (including under the farm executor: no farm worker has
FreeCAD) and not remote-cache-keyed, and its only task dependency is its own
`package:manifest:<stem>` task. Its file dependencies are the recipe, its
plan, every shop directory file, the scoped `features.toml` and STEP, the
FreeCAD runtime script and the driver's script closure, so a CAD change
re-posts the programs. Its targets are the stamp
`cad/out/reports/cam-<stem>.ok` and, under `cad/out/nc/<stem>/`, one
`<program>.nc` per recipe program, `cycle_times.json` and `manifest.json`
(input, post and output SHA-256s and the FreeCAD version). A submitter
without FreeCAD fails the task. See
[`cad/process/README.md`](../../process/README.md#nc-programs-freecad-cam).

## Releases

Releases ship every enrolled part's hobby traveler as a PDF (owner ruling
2026-11-14) and its NC programs (owner ruling 2026-11-17). A full `doit release`
depends on every `prechips:<stem>` and `cam:<stem>` task, so it re-renders the
travelers with the then-latest prechips and re-posts any stale programs;
`doit -s release` clears those dependencies and renders nothing.
`cut_release.py` copies each `cad/out/travelers/<stem>/<slug>-traveler.pdf` (a
family's shared sheet and each of its parts' placeholders,
`_process_plans.traveler_pdf_paths`) to
the bundle's `travelers/<slug>-traveler.pdf` and every `cam:<stem>` output to
`nc/<stem>/`, where `SHA256SUMS.txt` hashes them like every other staged
file, and names both directories in the release notes. A missing or empty PDF,
or one older than its part's `features/<stem>/features.toml`, fails the cut
before anything is zipped; the HTML sheets do not ship. So does a missing or
empty NC output, a program or `cycle_times.json` whose SHA-256 differs from
the CAM manifest, or a CAM manifest recording any input other than the
current one (`features.toml`, the STEP, `plan.toml`, each shop file, the recipe
or the FreeCAD runtime; the refusal names the file), so programs posted from
an older plan never ship beside a traveler rendered from the newer one;
`freecadcmd.log` does not
ship. A prechips refusal, an unreachable PyPI, a missing browser or a failed
post therefore blocks the release, like any other release gate. The farm
release runs `doit -s prechips` on the submitter after restoring the farm
outputs, before `doit -s release`
([`DEVELOPING.md`](../../../DEVELOPING.md#farm-releases)); the farm run's
`build` already posted the NC programs on that submitter, so they arrive with
the restored outputs.
With any traveler staged the release also ships `prechips:standing`'s shop standing instructions page as `travelers/shop-standing-instructions.pdf`; a missing one, or one older than a `cad/process/shop/*.toml`, fails the cut too.

The publisher's only tracked-source update is `cad/config/release.yaml`
`next_revision`; it does not edit process plans. The generated-only follow-up
exemption covers that bump and generated README images; plan and shop edits
require the [ordinary PR requirements](../../../AGENTS.md#minimum-merge-gate-every-pr),
including focused source checks, appropriate native proof and applicable reviews.
An individual PR or stack does not require a full build before merge; the
release manager runs the full build on main and releases only green main.
