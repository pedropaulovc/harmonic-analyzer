# Drawing requirements, STEP face sets and process travelers

## Scoped producers and full-export consumers

`package:features:<stem>` is one scoped COM leaf per part whose `draw_<stem>.py`
declares requirement features. `export_features.SUPPORTED_PARTS` is derived by
an import-free AST scan of those draw scripts; adding a declaration enrolls the
part without editing a central exporter list. `package:features` is a seat-free
aggregator depending on every `package:features:<stem>` leaf, not a COM export action.
This namespace is interim until `solidworks-pool` admits top-level `features` targets; no pool change is included.
Each leaf's native dependency is its own part, not assemblies or drawing
artefacts. Parts in `_process_plans.TRAVELER_STEMS` feed their manifest to a
prechips traveler (below). Fixture bundles expose drawing requirements too.
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
symbol in the part's feature spec (normally `<stem>_spec`), while `(module, NAME)`
cites a symbol in another module.
Shared-helper sources name their defining module, such as
`("_drawing_hole_callout", "add_native_hole_callout")`; the lifecycle-only
`_drawing_common` module is not the authority for helpers extracted from it.

A configured shared producer may declare one literal `FEATURE_SPEC_MODULE` in
its drawing to name the actual saved/default member's spec instead. For example,
`sh_vn_clamping_kit_hardware` names `sh_vn_clamping_kit_hold_down_stud_spec`,
whose `CONFIGURATION` must match the registry's `default_configuration`
(`HoldDownStud`). Do not invent an aggregate spec or re-export member facts to
match the producer stem. The feature source closure includes the drawing, the
selected spec and both transitive Python dependency closures without importing
them; config reads from those sources remain feature-leaf inputs.

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
`cad/config/title_block.yaml:linear_2pl.band_mm`. Python spans are resolved from
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
It waits for scoped bundles and the full neutral inventory. Its checks are
HA-owned; no prechips schema is involved. It requires the manifest's `part` to
identify the bundle's part, its `step` to name the adjacent STEP and its
`step_sha256` to match that STEP's raw bytes, a non-empty `features` table of
tables, and every feature's recorded face set to equal the references parsed
from that STEP. A mismatch fails with the feature name
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

## Process plans

`cad/process/<stem>/plan.toml` is a plan in the restarted prechips format
(see the [prechips README](https://github.com/pedropaulovc/prechips)). Its
`[cad]` table names the part's scoped manifest,
`file = "../../out/features/<stem>/features.toml"`, and the prechips adapter
that reads it; root `shop = "../shop.toml"` names the shared shop file. Text
and numeric fields bind CAD values as `{{cad.<name>}}` and the plan's own
`[parameters]` as `{{process.<name>}}`; prechips refuses unknown names. A plan
directory may also hold `diagrams/*.svg` files that the plan names. HA does not
rewrite, bind or stamp plans: prechips reads the tracked plan and the exported
manifest directly, with no STEP reader, geometry kernel or hash check.

`cad/process/shop.toml` is the prechips shop file (machines, workholding,
gauges, limits, tools and settings) and holds every fact its schema can
express. Facts prechips has no field for, read directly by CAD specs and tests,
live in `cad/config/shop-equipment.toml`. An object may appear in both with
disjoint fields; no field is duplicated. See
[`cad/process/README.md`](../../process/README.md).

## Travelers

`_process_plans.TRAVELER_STEMS` lists the parts with a `prechips:<stem>` task:
`ch_rocker_arm_tl_oblique_base_bar`, `ch_rocker_arm_tl_oblique_end_bracket`
and `ch_rocker_arm_tl_oblique_feed_lever`. `build` and `release` require every
one.

```text
uv run --frozen python -m doit prechips:<stem>
```

The task runs `cad/scripts/prechips_traveler.py <stem>`, which removes any
previous `cad/out/travelers/<stem>/traveler.html` and then runs:

```text
python -m prechips traveler cad/process/<stem>/plan.toml --profile pro --out cad/out/travelers/<stem>/traveler.html
```

It returns prechips' exit code unchanged. The task is SolidWorks-free,
submitter-only (including under the farm executor) and not remote-cache-keyed.
Its only task dependency is its own `package:features:<stem>` leaf. Its file
dependencies are every file in the plan directory, `cad/process/shop.toml`, the
scoped `features.toml`, `pyproject.toml`, `uv.lock` and the wrapper's script
closure. Its targets are the stamp `cad/out/reports/prechips-<stem>.ok` and
`traveler.html`; the stamp is removed before each run so a refusal never leaves
an old stamp. If `cad/process/<stem>/plan.toml` is missing, the graph still
loads and only that task fails, naming the missing plan.

| prechips exit | build/release gate | meaning |
|---|---|---|
| 0 | pass | `traveler.html` written |
| 2 | fail, no stamp | refusal: bad input, or a failed enforced check (`stock_fit`, `turning_deflection`, `cutting_speeds`, `tool_sizing`, `indexing`, `gauge_capability`, `lathe_holding`, `machine_capacity`); nothing written |
| other nonzero | fail, no stamp | consumer failure |

The `pro` profile enforces every check listed above. A refusal names the check;
a pass prints no checker text on the sheet. The traveler is one standalone HTML
file. It carries no report, hash or certificate, and a pass is not permission to
machine: shop measurements, physical setup verification and machining approval
remain human responsibilities.

The `_run_stamped` → `_exec` path injects `TRACEPARENT` and service
`prechips-traveler`; the wrapper continues the task trace with a
`pipeline.prechips_traveler` span and a `prechips.traveler` span around the CLI.
A missing plan or nonzero exit marks the pipeline span as failed.

Current state: only the base-bar plan exists, ported from the prechips
`examples/base-bar.toml`. Under prechips 0.8.0 its `harmonic_base_bar` adapter
cannot read the v48 manifest (`rail_hole_1.station: missing drawing
requirement`), so it refuses; the fix is upstream in prechips 0.9. The end
bracket and feed lever have no plan yet. Until both are resolved the traveler
tasks fail `build` and `release`.

## Release travelers

After staging the verified `features/` bundles, `cut_release.py` calls
`_process_plans.stage_travelers(out, stage)` under `release.travelers_stage`.
It copies each enrolled `cad/out/travelers/<stem>/traveler.html` to
`travelers/<stem>/traveler.html` in the release ZIP, and fails naming every
traveler that was not generated. `facts["travelers"]` records the staged
paths and the release notes list them.

The publisher's only tracked-source update is `cad/config/release.yaml`
`next_revision`; it does not edit process plans. The generated-only follow-up
exemption covers that bump and generated README images; plan and shop edits
require the [ordinary PR requirements](../../../AGENTS.md#minimum-merge-gate-every-pr),
including focused source checks, appropriate native proof and applicable reviews.
An individual PR or stack does not require a full build before merge; the
release manager runs the full build on main and releases only green main.
