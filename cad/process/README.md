# Process plans and strict travelers

This directory holds HA-authored process plans (`<stem>/plan.toml`) and shared
shop data (`shop/inventory.toml`, `shop/shop-policy.toml`,
`shop/cutting-data.toml`). prechips is pinned to PyPI `prechips==0.3.0`.
`cad/scripts/_process_plans.py:TRAVELER_STEMS` is the enrollment authority; it is
currently empty. The rocker plan is a **HELD REFERENCE ROUTE**, not enrolled or
qualified for machining. Its current built-up strap/hub route and oblique-trammel
jig replace the retired one-piece outline-template sequence; historical inline
inventory envelopes do not qualify the current jig or restore retired tooling.
Before enrollment, qualify physical tooling and revalidate the route against
current geometry and the pinned prechips, then obtain traveler exit 0 (step 6
below). The oblique-trammel base bar plan (MHA-CH-06-TL-20) is a
held preview route from the owned 1/2 x 6 bar (#2083), migrated but not enrolled:
the v47 drawing still prints the width as stock (#2083 open) and its travelers stay
provisional. The shaft and cone are **HELD / UNENROLLED** source proposals:
allocated 3/8-inch 1018 shaft stock departs from the advisory 5/16-inch drawing
note without changing finished geometry; the cone remains integral one-piece
with **FINISH UNRESOLVED**. Stock receipt, support, pickups, physical bindings,
tooling and inspection availability remain unproved. These are not first-article
records or machining approval. Do not enroll a plan merely because it parses.
`_process_plans.MIGRATED_PLANS` includes all four held plans; `revision_stems()`
is the deduplicated union of migrated and enrolled plans for revision tracking only.

The current rocker and base-bar plans retain latest-main jig authority. The
rocker's `bandsaw_preform` is source-authored and analytically referenced by
`ch_rocker_arm_tl_oblique_blank_spec.py`, but **not PC-modeled or consumable**.
Its cutting prose under `deburr` is not seven modeled saw cuts. The binder must
not strip that table to obtain schema acceptance or claim the resulting stock
state is proved. PC consumption and material-changing saw semantics are deferred;
the obsolete full rocker rewrite is not the source for this route.

The shaft/cone reconciliation takes contracts from the held proposal at
[`e53b0641a6`](https://github.com/pedropaulovc/harmonic-analyzer/commit/e53b0641a6),
not its demonstration shop values. The cone's common crank boss/bore/caps
placement is a native placement contract, not an aim-only note: separation
43.2735 mm gives model Y 81.3735, delta Y +0.177856497104 mm from CAD nominal.
CAD, exported geometry and nominal setup frames are unchanged; native placement
must preserve concentricity and head support before it earns geometry credit.
The signed-station inspection offset and citation remain `unknown`, not copied
calibrations. The paint/mask split is unresolved despite the one-piece decision.

Prechips 0.3.0 adds three bounded contracts: explicitly qualified tailstock tool
mounting, relative-coordinate inspection readings, and shared-axis native
placement.
The release and dependency upgrade are separate from traveler activation:
all four plans remain **HELD / UNENROLLED**, and enrollment stays empty.
Installed schema/API admission is not full-plan consumption, native route replay
or machining qualification. The strict revision guard still refuses authored
v48 plans against v47 exports before invoking the consumer or geometry kernel;
do not relabel or rewrite the exported geometry to bypass it.

Full consumer migration, general traveler rendering and native retained-stock/
motion replay remain deferred. The relative-reading contract does not yet supply
printed physical reading bands or an executable inspection procedure. The cone's
rotary, manual-root and honing operations have no completed native proof; neither
prose, ideal feature sweeps nor bounding-box removal may substitute for actual
material-changing semantics. Its inspection qualification and finish holds
remain unresolved. The shaft's cradle, support engagement, dome compensation,
flat-face labels and apex pickup remain unqualified. Existing demonstration/
placeholder shop records are not actual availability, installed geometry or
commissioning measurements. Schema acceptance and the narrow PC contracts cannot
turn these holds into a manufacturing or first-article pass.

## Bind stable labels, not STEP entity numbers

Use the part's scoped `cad/out/features/<stem>/features.toml` and adjacent STEP
as the drawing/geometry authority. Migrated and enrolled plans carry a literal
`[drawing].revision` equal to `cad/config/release.yaml:next_revision`. Held migrated
plans advance with that reservation, but revision freshness does not revalidate
their geometry, enroll them, or imply machining qualification. Unmigrated
historical plans retain their authored revisions. Before enrollment, revalidate
the plan against current geometry and its drawing revision. Migrated plans use
bare stable labels matching
`HAF_[A-Z0-9_]+__P\d{2}` wherever prechips expects a face reference. Do not commit
exact `#<entity>/ADVANCED_FACE[<ordinal>]/<label>` references: export can renumber
entities without changing geometry.

The wrapper writes a bound copy to `cad/out/travelers/<stem>/plan.toml`. It
rewrites `features` to the fresh scoped manifest and replaces whole quoted label
tokens with that manifest's exact refs. A label covering multiple patches
expands inside a list; it cannot be used as a single-face scalar. Unknown labels,
wrong-part labels and ambiguous scalar bindings fail with a source line. A label
mentioned inside longer prose is not replaced. Other tracked bytes are preserved.
Binding also rejects a plan drawing revision that differs from the scoped
manifest. Release preflight requires enrolled plans' authored and manifest
revisions to match the configured next revision. It checks held migrated plans'
authored freshness without requiring or qualifying an exported manifest.
The authored v48 plans must refuse delivered v47 feature/STEP pairs **before**
the PC consumer or geometry kernel runs. Never relabel those exports or weaken
the revision guard to demonstrate a held proposal. Source/schema acceptance is
not native stock, placement, clearance, traveler or machining qualification.
Do not add `[paths]` to a tracked plan: the wrapper supplies the three shared
shop inputs as CLI flags. Binding never edits the tracked plan.

## Fixture geometry comes from the CAD spec

For a shop-made HA fixture, the inventory entry carries
`cad = "<fixture-stem>"` instead of hand-authored `solids`. The stem must be a
registered spec-driven fixture whose TL spec exports `PRECHIPS_SOLIDS` in the
fixture frame, derived from the same constants used to build its SolidWorks
part. Never supply both `cad` and `solids`, and do not maintain a second set of
fixture dimensions in the inventory.

The rocker's retired standalone-tooling inventory is a historical exception,
not registered current jig CAD: its inline solids support historical
process/clearance checks only. They do not restore deleted builders, drawings
or physical-gauge qualification and must not replace the current oblique-trammel
jig authority. Qualify that current route's actual tooling before enrollment.

`bind_shop` writes the generated inventory under
`cad/out/travelers/_shop/inventory.toml`, inserts the spec's primitives and
removes the HA-only `cad` key before prechips reads it. Policy and cutting data
remain shared inputs. Shop values need a vendor/catalogue or measurement source;
unverified measurements must remain explicitly unverified. Do not change a
value merely to make a rule pass. The shop data seeded from the rocker trial
marks each unmeasured fact as a realistic placeholder,
`measured = { status = "measured", by = "placeholder (realistic, remeasure: #1413)", … }`;
these are test inputs, not shop metrology, and must be remeasured before shop use.
Spell the `by` exactly as `_process_plans.PLACEHOLDER_BY`, in the inventory and in
TL specs' `PRECHIPS_SOLIDS`: it keeps `status = "measured"` so travelers exercise
every check, and it is the one marker binding counts. Every `PRECHIPS_SOLIDS`
entry carries `measured` with an explicit `status`, and `bind_shop` refuses one
without it, naming the spec and solid (#1462): prechips trusts a solid with no
record as installed nominal geometry, and an omitted status reads as `assumed`.
Binding counts every bound
occurrence: `measured.by` values (spliced spec solids included), prose, and the
comment-declared placeholders that schema-limited facts carry in the tracked
files; `bind_shop` warns with the count. A traveler built on any placeholder is
PROVISIONAL: `report.json` carries `ha_provisional = { provisional, placeholders,
remeasure = "#1413" }`, and every sheet banner of `traveler.html` opens with
`PROVISIONAL — <n> placeholder values, remeasure: #1413`. Builds and farm runs
still produce and verify it. Release preflight and traveler staging refuse while
any placeholder is bound to an enrolled stem, naming every one.
`cad/scripts/test_process_shop.py` (in `check:recipe`) validates the three
files under the pinned prechips models and through `bind_shop`, requires a `by`
on every `measured` record, an explicit `measured.status` on every bound solid
and the shared placeholder spelling (spec solids included), enumerates every
`shop_made` record, and rejects any other inventory table whose id or name names
a registered part (stem or drawing number from `cad/config/parts`).

Catalogue sourcing belongs in `shop/inventory.toml`: keep the dated vendor
specification separate from any owner-selected cut length or jig-layout
decision. Distinguish purchased stock length from the installed length: record
cutting and deburring as shop steps, not as a vendor-guaranteed tolerance.
An included kit member must not trigger a duplicate purchase. Keep unpurchased
hardware at `verify = true`; catalogue dimensions do not establish possession,
receipt metrology or assembled mechanical fit.
Record unpublished fields and rejected substitutes beside the affected item,
rather than duplicating their changing verification status here. CAD remains
the authority for installed geometry and any shop-made adapter.

## Add or migrate a part

1. Ensure the part is supported by `export_features.SUPPORTED_PARTS` and obtain
   its fresh scoped manifest/STEP through `package:features` on the supervised
   SolidWorks farm. Do not launch SolidWorks locally for this workflow.
2. Author or migrate `<stem>/plan.toml` against the pinned prechips schema using
   the actual drawing, requirements, geometry and sourced shop data. Use bare
   labels, the current tracked drawing revision and no `[paths]`. A setup frame
   authored in a plan is a process proposal, not drawing authority or evidence
   of a physically verified setup.
   Register a migrated plan in `_process_plans.MIGRATED_PLANS` even while held
   from enrollment so revision tracking and source contracts include it.
3. Register any needed fixture CAD spec and its `PRECHIPS_SOLIDS` contract;
   inventory `cad` tags must resolve to those specs. Cover the analytic volume
   and binding contract in tests instead of copying fixture geometry by hand.
4. Install FreeCAD 1.1 on the submitter, or set `FREECAD_CMD` to its command
   executable. The Python wheel does not install FreeCAD; see
   [local prerequisites](../../DEVELOPING.md#process-traveler-prerequisites).
5. With a migrated plan and fresh real exports, iterate the check loop below.
   Correct the source plan/shop data based on evidence; generated bound files
   under `cad/out/` are disposable, not authoring inputs.
6. Run the full wrapper and obtain exit 0 with complete output verification on
   real exported geometry **before** adding the stem to `TRAVELER_STEMS`. Add
   regression coverage for plan identity/revision, label binding and absence of
   tracked exact refs or `[paths]`, then use the enrolled `prechips:<stem>` task.

For a migrated part, substitute its underscore stem for `<stem>`:

```text
uv run --frozen python cad/scripts/prechips_traveler.py "<stem>" --check
uv run --frozen python cad/scripts/prechips_traveler.py "<stem>"
uv run --frozen python -m doit "prechips:<stem>"
```

`--check` binds the plan to `cad/out/travelers/<stem>/.check/plan.toml`, binds
shop inputs under `.check/_shop/`, and sends all check output to `.check/`.
It reads the current scoped feature bundle but never rewrites the full bound
plan, shared bound shop, report, HTML or PNGs, even when authoring inputs change.
Check mode does not produce or validate HTML/PNG traveler completeness.
The default wrapper removes the previous `report.json` **before binding**, then
invokes the full traveler command and verifies its outputs after exit 0; a failed
bind or consumer run cannot retain an old success certificate. Both modes
preserve nonzero consumer exits: 2 (machining blockers), 3 (bad input), 4 (required
unknowns) and unexpected failures are failures, not advisory passes. Do not run
this loop on a revision-mismatched bundle or the unconsumable rocker preform.

## Build and release contract

Every enrolled stem is required by both `build` and `release`. Its outputs are
`cad/out/travelers/<stem>/plan.toml`, `report.json`, `traveler.html`, setup images
and operation inspection images, with the task stamp at
`cad/out/reports/prechips-<stem>.ok`. Completeness is derived from the plan and
checked against render hashes, `expected_exit == 0` and report input digests for
the bound plan, scoped manifest and STEP, inventory, shop policy and cutting data.
Verification also regenerates the tracked plan and shop bindings in memory and
requires byte equality with the bound files. A changed source plan, feature
manifest, shop input or render invalidates the traveler even if its stamp remains.

Releases verify against the staged feature manifest and stage only the validated
byte snapshots of the bound plan and required report/HTML/PNGs to
`travelers/<stem>/`, plus the shared bound inputs under `travelers/_shop/`.
Scratch outputs, lock files and stray temporary files are not shipped.
The staged `features/<stem>/` bundle and the bound plan's relative feature path
continue to resolve together. Release notes list the travelers.
After successful publication the publisher advances `release.yaml` and each
migrated or enrolled plan's single `[drawing].revision` line, once per stem,
together with the generated README images. This does not change traveler
enrollment or machining qualification. The generated-only follow-up exemption
covers only those revision lines and image files, not other plan/shop edits.
Dry runs and failed publication
leave tracked revisions and images byte-identical; post-publication partial
installation reports explicit recovery paths.

A strict traveler pass is not permission to machine. Human measurement, physical
setup verification and machining approval are still required. See the full
[feature/traveler contract](../docs/pipeline/features-travelers.md).
