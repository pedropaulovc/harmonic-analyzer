# Process plans and travelers

This directory holds the inputs to the `prechips:<stem>` travelers and the
`cam:<stem>` NC programs:

```text
cad/process/
  shop.toml                 prechips shop file, shared by every plan
  <stem>/plan.toml          one prechips plan per part
  <stem>/diagrams/*.svg     optional setup diagrams the plan names
  <stem>/cam.py             CAM recipe of a part milled on the CNC mill
```

The machine premise is a CNC mill and a manual lathe (owner ruling
2026-11-17): milled work runs on the CNC-converted PM-30MV (FluidNC
controller, CNCjs sender, electronic tool setter and 3D touch probe) from the
part's posted NC programs, with speed of manufacture the priority, and turned
work runs on the manual PM-1127VF-LB lathe.

[prechips](https://github.com/pedropaulovc/prechips) is a stdlib-only PyPI
package. It is not an HA dependency while it stabilises (owner ruling
2026-11-11, [#2502](https://github.com/pedropaulovc/harmonic-analyzer/issues/2502)):
it stays out of `uv.lock`, and every traveler run uses the latest PyPI release
through uv's tool runner. It reads the plan, the shop file and the part's
exported `features.toml`, and writes standalone HTML travelers; the traveler
task prints the hobby sheet to `<slug>-traveler.pdf`, which releases ship. It needs no
FreeCAD or geometry kernel and checks no hashes. HA does not rewrite, bind or
stamp the plan; prechips reads the tracked file directly.

## Plans

`<stem>/plan.toml` follows the restarted prechips plan format documented in the
prechips README. It points at the part's scoped feature manifest and the shop
file with paths relative to the plan:

```toml
shop = "../shop.toml"

[cad]
file = "../../out/features/<stem>/features.toml"
adapter = "<prechips adapter for this part>"
```

Text and numeric fields take CAD values as `{{cad.<name>}}` and the plan's own
`[parameters]` as `{{process.<name>}}`; unknown names are refused. Bind
dimensions, limits and the drawing revision from `{{cad.…}}` rather than typing
them, so a CAD change reaches the traveler through the exported manifest. Every
file in the plan directory is an input to the traveler task.

Parts are enrolled by the CNC migration. The rocker strap (`ch_rocker_strap`,
MHA-CH-13) is the first: faced and bored in edge clamps on a shop-made
sub-plate, then bonded to it on tape and screwed down at the hub for the
outline. The magnifying clamp (`mg_magnifying_clamp`, MHA-MG-02) stands
upright on parallels in the vise for both ends and lies corner up between them
for its cross bore; its holes are tapped by hand on a dead centre in the
spindle, one Idle-ending NC file per hole. The oblique trammel jig's eight parts,
enrolled before it was deleted (owner ruling 2026-11-17, #2885), left their
plans, diagrams and the base bar's CAM recipe at
`ebd3bf3b44:cad/process/ch_rocker_arm_tl_oblique_*/` and
`ebd3bf3b44:cad/process/ch_rocker_arm_tl_vn_oblique_leadscrew_kit/`. Each
plan's `adapter` is a prechips adapter written against that part's manifest
contents, so a drawing change that alters the manifest's requirements needs a
prechips adapter release before the traveler passes again.

Plan parameters that size envelopes and pictures (vise jaw width, jaw height
and bed height) repeat `shop.toml` `workholding.vise-pm-6`, because prechips
plan bindings cannot read shop records; each such parameter names the shop
field it repeats, and the two must be changed together.

## Shop records

`shop.toml` is the prechips shop file: machines, workholding, gauges, limits,
tools and cutting settings, in prechips' schema and units. It holds only records
an HA plan or an HA spec/test reads (no example tooling from other projects); a
fact that schema can express lives here. Its records include the shop's
indicators' ranges and resolutions (`gauges.dti`, `gauges.dial-indicators`,
`gauges.digital-indicator`, owner inventory 2026-11-17), the DTI's read by the
channel and paper-drive drawing tests;
the PM-30MV X DRO scale (`gauges.mill-x-dro`), whose resolution the paper-drive
tests read; the rocker profile cutter (`tools.rocker-profile-cutter`) with its
HSS cutting setting (`settings.rocker-profile-hss-low-carbon-steel`); and the
PM 6-in vise (`workholding.vise-pm-6`: jaw width, opening, jaw height and bed
height). The opening is the owner-reported fit with the stock hard jaws
(2026-10-30), not the bare 6.135 in jaw-to-jaw reading. The owned 1/8, 1/4,
3/8 and 1/2 in 3-flute uncoated carbide end mills (`tools.endmill-carbide-3fl-*`)
carry cutting settings on 1018 within the PM-30MV's 2800 rpm ceiling
(`settings.endmill-carbide-3fl-*-1018-cf`), each number cited beside it.

The `[limits]` table carries the three `vise_holding` limits: grip at least
`vise_grip_min_mm` 6 mm (Pedro's house choice) and `vise_grip_fraction_min`
one-third of the part's height (a rule of thumb, not a standard), and a
`"centred"` hold's gripped-span midpoint within `vise_centre_fraction_max`
one-third of the half jaw width (Pedro's house rule). Each is cited beside it.

Facts prechips has no field for, but which CAD specs and tests read, live in
[`cad/config/shop-equipment.toml`](../config/shop-equipment.toml):

- gauges: the DTI's kind, the pin-gauge note, the Mitutoyo gauge-block set
  and the indicators' ownership;
- the PM-30MV DRO's make and cited accuracy (read by the paper-drive tests);
- the LMS 6784 end-mill set and its sizes, the 8-32 plug hand tap's flute
  length, and the shop-made rocker trammel's R800/R816 lengths;
- the cylinder gear's alignment-notch saw (TTC 10-215-014, .014 in), not
  owned, read by `test_dt_cylinder_gear_drawing.py` against the printed
  .016 MAX (#2364);
- the measuring stick's engraving bit (2L P-125x2.0-30-.005-S, 30° V, .005 in
  tip), not owned, which cuts every MHA-MS-01 graduation and numeral; its
  brass cutting setting is `shop.toml` `settings.ms-stick-engrave-brass`, and
  `test_ms_stick_drawing.py` reads both against the printed groove limits
  (#2433);
- the PM 6-in vise's make, SKU and source;
- a `[[stock]]` row for every bought bar, tube, wire and ball, each quoting
  its order line and allocation: Online Metals orders 1021704672 and
  1021751700, Metal Supermarkets invoice EC234347, McMaster-Carr PO
  0803PCAMPOS and McMaster 8663K55 acetal (owner 2026-11-17: all on hand but
  the platen's C360 plate). Every row carries `status` (`on_hand`,
  `not_received` or `to_order`) and `allocated_to`, the registry stems it is
  cut for now (empty when its part is retired or none was named).
  `uv run --frozen python cad/scripts/stock_bom.py [--format md|csv|xlsx]` joins
  these rows to the part registry, normalized to one row per part and
  requirement: `type` `stock` (each allocated row with its status; one
  `vendor_sku` or `no_stock_record` row when none serves the part) or `tool`
  (each `[[tools]]` entry of the part's process plan, ownership read from this
  file's `tools.<ref>` `present`: `on_hand`, `to_buy` or `unrecorded`; one
  `no_traveler` row for a part without a plan), then the unallocated rows with
  the part columns empty. `--format xlsx --out PATH` adds a Readiness sheet
  first: per part, its missing stock rows (`not_received`, `to_order`,
  `no_stock_record`), missing tools (`to_buy`, `unrecorded`) and state
  (`ready`, `missing`, `no_traveler`), as COUNTIFS formulas over the BOM sheet
  (xlsxwriter cannot write a native PivotTable). Tools point from the plan,
  never from this inventory. It exits 2 when a row or plan names an unknown or purchased
  stem, or a plan's tool `ref` is not in `shop.toml`, and
  `test_stock_bom.py` (`check:recipe`) runs that check on every change;
- the MHA-FR-02 top-frame casting to buy (owner ruling 2026-11-10 (Pedro),
  #2333): a gray-iron ASTM A48 class 25B `[[stock]]` row of form `casting`,
  with its pattern, datum-target and as-cast mass notes; not quoted or ordered;
- the MHA-SM-02 knife mount's records to make or buy (owner ruling 2026-11-10
  (Pedro), #2334): the MHA-SM-00 gauge bar (`gauges.gauge-bar-0472x8`), the
  12 mm H7 reamer (`tools.reamer-12mm-h7`) and a 4140/4142 HT `[[stock]]` row;
- the MHA-SM-01 gooseneck tube to buy (owner rulings 2026-10-27 (Pedro), #1951,
  2026-11-08, #2315, and 2026-11-14, #2401): a 4130-N `[[stock]]` row of form
  `round_tube` (OnlineMetals 7322, one 36 in cut with about 11 in for a trial
  bend), read by `test_sm_gooseneck_drawing.py` against the bent tube's
  developed length plus its ~2 in arm-end tail and ~1 in at the foot, and the
  shop-made bend form it is
  bent on (`fixtures.sm-gooseneck-bend-form`, no toleranced size: the radius
  is a reference);
- the owned tools, gauges, cutters, inserts, holders, saws and shop fluids of
  McMaster-Carr PO 0803PCAMPOS (packing list 1616317-01, 08/04/2025; owner
  2026-11-17), each with its SKU, quantity and packing-list line;

One fact lives in one file. The same object may appear in both files with
disjoint fields (the DTI, for example), but no field is duplicated. Together
the two files are the source of truth for installed shop equipment.

The former `cad/process/shop/inventory.toml` and `cutting-data.toml` are
deleted; records not carried into either file were dropped. Their last version
is at commit `45952b66bc`, for example
`git show 45952b66bc:cad/process/shop/inventory.toml`.

Shop values need a vendor/catalogue or measurement source. Keep a dated vendor
specification separate from an owner-selected cut length or layout decision,
and distinguish purchased stock length from installed length. prechips uses
values as written; do not change a value merely to make a check pass.

Owner rulings (Pedro), recorded for the cutover:

- The prechips cutover is a clean cutover. It deleted the legacy machinery,
  including the #1413 placeholder release refusal and the PROVISIONAL sheet
  stamp; no traveler or release gate distinguishes measured from placeholder
  values.
- For prechips shop data: "no pedantism of not measured value inferred; if it
  is in the inputs they will be considered" (2026-11-10). `shop.toml` and plan
  values are used as written, with no measured/placeholder provenance.
- `shop.toml` and the plans carry HA's own recorded values, not the prechips
  example ones: where the deleted inventory or shop policy (`45952b66bc`) held a
  different value for the same machine, holder or limit, HA's value is used
  and marked `HA:` in a comment beside it.
- Cutter and drill diameters stay at their nominal sizes. Sizing compares the
  named tool size with the drawing band; HA's per-tool readings in the deleted
  inventory (for example #29 3.451 mm, #12 4.798 mm, the 3/4 in end mill
  19.039 mm) were #1413 "realistic placeholder" values, not shop measurements,
  and under the ruling above values are used as written in `shop.toml`, which
  states the nominal size.

## Travelers

`cad/scripts/_process_plans.py:TRAVELER_STEMS` lists the parts with a
`prechips:<stem>` task, enrolled by the CNC migration. `build` runs
every one beside the drawing PDFs (`build_bare` runs none); `release` runs
every one and ships each hobby sheet as
`travelers/<slug>-traveler.pdf` (owner ruling 2026-11-14). Each run renders two
travelers from the same plan: `traveler.html` (`pro`, concise) and
`traveler-hobby.html` (`hobby`, with the setup pictures in `<stem>/diagrams/`),
then prints the hobby sheet to `<slug>-traveler.pdf` with a headless Edge or
Chrome. For a milled part the hobby sheet is the CNC setup sheet: the setups,
workholding and work zeros the part's NC programs run in. A plan that prechips
refuses therefore blocks the release. The
wrapper's `prechips@latest` runs the latest PyPI release.

```text
uv run --frozen python -m doit prechips:<stem>
uv run --frozen python cad/scripts/prechips_traveler.py <stem>
uvx --from prechips@latest prechips traveler cad/process/<stem>/plan.toml --profile hobby --out <file>
```

Each form needs the part's feature manifest at
`cad/out/features/<stem>/features.toml`. The doit task first runs its
`package:features:<stem>` leaf (SolidWorks, via the supervised farm); the
wrapper and the by-hand `uvx` command need an existing bundle, from a build or
copied from a release asset's `features/<stem>/`. All three use the latest
prechips release from PyPI (`@latest` makes uv revalidate its index and skip
any `uv tool install`-ed copy), so they need `uv` and network access. The doit
task always runs when requested.

The wrapper removes any previous `traveler.html`, `traveler-hobby.html` and
`<slug>-traveler.pdf` under `cad/out/travelers/<stem>/`, finds a headless Edge
or Chrome (`HARMONIC_PDF_BROWSER` overrides), resolves and logs the latest
prechips version, then runs
`uv tool run --from prechips==<version> prechips traveler cad/process/<stem>/plan.toml`
with `--profile pro` and then `--profile hobby`, and prints the hobby sheet to
`<slug>-traveler.pdf`. Exit 0 from both renders and a printed `%PDF-` file is
the only pass. Exit 1 is an infrastructure failure: no `uv`, no PyPI, a render
whose `uv tool run` failed before prechips ran (uv's `error:` or `×` diagnostic
on stderr), no browser, or a failed print; it is never a finding about the
plan. A nonzero prechips exit from either profile is returned and removes all
three files; exit 2 is
a refusal, either bad input or a failed enforced check (`stock_fit`,
`turning_deflection`, `milling_deflection`, `cutting_speeds`, `tool_sizing`,
`indexing`, `gauge_capability`, `lathe_holding`, `vise_holding`,
`machine_capacity`, `drill_pecking`, or
`hobby`'s missing setup picture). A missing plan fails only that part's task.
A refusal is a finding about the plan or shop data; correct the source, not
the check.

A traveler that passes is not permission to machine: shop measurements,
physical setup verification and machining approval are still required. See the
[feature/traveler contract](../docs/pipeline/features-travelers.md).

## NC programs (FreeCAD CAM)

A part listed in `cad/scripts/_cam_programs.py:CAM_STEMS`, enrolled by the CNC
migration, also has `<stem>/cam.py`, a CAM recipe that turns the plan's
machining setups into G-code with FreeCAD's CAM workbench, run headless.
`build` and `release` run every enrolled part's `cam:<stem>` task
(`build_bare` runs none); `uv run --frozen python -m doit cam:<stem>` runs
one. It runs on the submitter, like the travelers, even under the farm
executor (no farm worker has FreeCAD), and needs FreeCAD 1.1 or
later: `$HARMONIC_FREECAD` names `freecadcmd`, otherwise the newest
`FreeCAD <version>` install under the Windows program directories is used, and
the task fails when there is none (or when it is older than 1.1). It writes
one `.nc` per recipe program, `cycle_times.json` and `manifest.json` (input,
post and output SHA-256s, FreeCAD version, the post file FreeCAD loaded) to
`cad/out/nc/<stem>/`, logs each program's cutting, air-at-feed and rapid
minutes, and leaves freecadcmd's console output in `freecadcmd.log` there.
Its only task dependency is its own `package:features:<stem>` leaf. A release
ships the programs, `cycle_times.json` and `manifest.json` (not the log) under
the bundle's `nc/<stem>/`; a missing output, a program or `cycle_times.json`
that differs from the manifest, or a manifest recording any input other than
the current one (the feature bundle, `plan.toml`, `shop.toml`, the recipe or
the runtime: `_cam_programs.cam_inputs`) fails the cut.

A recipe has five parts:

- `PROGRAMS`: the file names, each listing its operations, flat (one FreeCAD
  Job, posted as it is) or in sections (one Job per tool and spindle speed,
  or a manual section: G-code the recipe writes itself, such as an operator
  stop or a probing cycle). Sections join into one file. A file may be one
  manual section alone, a hand-tap stop: it must load its tool first (`M6`,
  so the guide's length is set), retract with `G53 G0 Z` to the machine top,
  rapid over the hole and end `M30`, so the controller is Idle where FluidNC
  allows jogging; `_gcode.check_tap_stop` proves it. A new tool starts at
  `M5`, a `%msg` naming it and the speed to set, and `M6 T<n>`, which CNCjs
  (Manual Tool Change, Custom Probing) expands into its tool change and
  tool-setter probe; FluidNC 3.7.8 has no tool change of its own. The
  PM-30MV's speed is set by hand on the knob, so the same tool at a new speed
  starts at `%msg` and `M0`. CNCjs strips comments before sending and shows
  the pending `%msg` text at the next M0 or M6 pause. `_gcode` splits a file at its `M6`s into
  tool sections, named `FILE@k` in expectations, and checks the tools called,
  each stop and tool change (retracted above the stock, spindle stopped where
  hands go in, commented), each section's S words and the probe's single
  `G10 L20 P1` straight after its `G38.2`.
- `LOAD_FIRST_TOOL`: the programs that load their own first tool the same
  way (`M5`, `%msg`, `M6 T<n>` straight after the preamble's `G54`, before
  any move); any other program runs on the tool already in the spindle and
  the length last set. The rocker strap lists all four of its files: a
  carried-over tool is only right when the files run in order, and a re-run
  or restart breaks that. `check_tool_changes(..., loads_first=True)` refuses
  a move or S word before the first `M6`.
- `context(features, plan, shop, step)`: a pure function. It reads every part
  dimension from the part's `features.toml`. Blank size, cutter tip depths,
  radial steps and jack positions come from the part's `plan.toml`
  (`[parameters]`, `milling_cuts`), and cutter diameters, speeds and feeds from
  `shop.toml`. It also places the part in each setup's work frame and lays out
  the pass stations and depth levels. Values neither record carries are
  recipe constants with a stated source: the centre drill's geometry, the S2
  strap clearance, the approach clearance, the saw allowance past the blank
  end, the face overhang past the bar edges, the safe height above the stock
  and the facing plunge feed. A part dimension typed into the recipe would let
  the NC drift from the CAD.
- `build(ctx, rt)`: runs inside `freecadcmd` with the
  `_freecad_cam_runtime.py` helpers (Jobs, tool controllers, Profile, MillFace
  and Drilling operations, the `grbl` post).
- `expectations(ctx)`: the `_gcode` checks every posted file must pass, such
  as depths, hole centres, slot cutter-centre envelopes and plunge corners,
  pass positions and directions, zigzag face passes, spindle speeds, no rapid
  below the stock top and no feed move above it. Each file's `air_feed`
  expectation (or each tool section's) also names the stock top its cycle
  time is split at.

CAM can produce toolpaths that look valid yet are wrong; the expectations
caught a spot depth measured from the counterbore floor, a feed height below
the stock top, a slot cut from the outside and an oversized radial step in the
first recipe. A failed check removes every output. Fix the recipe, not the
expectation.

Milling speed rules (owner rulings 2026-11-16): "replace fusion with oss
cam" moved the task from Autodesk Fusion Personal, which posted rapids at
feed, to FreeCAD, whose posts use real G0 above the stock. The PM-30MV
conversion has ball screws, so faces zigzag (climb on alternate passes).
Passes that plunge beside the stock plunge at their cutting feed; only
plunges into metal take the plan's slow feed. The rapid rate is assumed at
100 in/min (`_gcode.RAPID_MM_MIN`, until the controller's `$110`/`$111` are
read). Probing moves and tool changes are not timed.

FreeCAD's `grbl` post expands G81/G82/G83 into G0/G1 but not G73, so the
drilled holes peck with full retracts (G83), one drill diameter each, as the
traveler says; FreeCAD measures each peck from the R plane, which is why the
R plane sits just above the stock.

Posted NC is not machining approval: prove each program in air and check the
setup against the traveler first.
