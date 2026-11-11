# Process plans and travelers

This directory holds the inputs to the `prechips:<stem>` travelers:

```text
cad/process/
  shop.toml                 prechips shop file, shared by every plan
  <stem>/plan.toml          one prechips plan per part
  <stem>/diagrams/*.svg     optional setup diagrams the plan names
  hand-travelers/           interim handwritten sheets (see its README)
```

[prechips](https://github.com/pedropaulovc/prechips) is a stdlib-only PyPI
package. It is not an HA dependency while it stabilises (owner ruling
2026-11-11, [#2502](https://github.com/pedropaulovc/harmonic-analyzer/issues/2502)):
it stays out of `uv.lock`, and every traveler run uses the latest PyPI release
through uv's tool runner. It reads the plan, the shop file and the part's
exported `features.toml`, and writes standalone HTML travelers. It needs no
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

The base bar, end bracket and feed lever have plans, ported from the prechips
0.10 examples; each header names its sources. Each plan's `adapter` is a prechips
adapter written against that part's manifest contents, so a drawing change that
alters the manifest's requirements needs a prechips adapter release before the
traveler passes again.

Plan parameters that size envelopes and pictures (vise jaw width, jaw height
and bed height) repeat `shop.toml` `workholding.vise-pm-6`, because prechips
plan bindings cannot read shop records; each such parameter names the shop
field it repeats, and the two must be changed together.

## Shop records

`shop.toml` is the prechips shop file: machines, workholding, gauges, limits,
tools and cutting settings, in prechips' schema and units. It holds only records
an HA plan or an HA spec/test reads (no example tooling from other projects); a
fact that schema can express lives here. Its records include the rocker DTI's
range and resolution (`gauges.dti`), read by `ch_rocker_arm_profile_check.py`;
the PM-30MV X DRO scale (`gauges.mill-x-dro`), whose resolution the paper-drive
tests read; the rocker profile cutter (`tools.rocker-profile-cutter`) with its
HSS cutting setting (`settings.rocker-profile-hss-low-carbon-steel`); and the
PM 6-in vise (`workholding.vise-pm-6`: jaw width, opening, jaw height and bed
height), whose 5 3/4 in opening the trammel spec test reads. The opening is
the owner-reported fit with the stock hard jaws (2026-10-30), not the bare
6.135 in jaw-to-jaw reading.

The `[limits]` table carries the three `vise_holding` limits: grip at least
`vise_grip_min_mm` 6 mm (Pedro's house choice) and `vise_grip_fraction_min`
one-third of the part's height (a rule of thumb, not a standard), and a
`"centred"` hold's gripped-span midpoint within `vise_centre_fraction_max`
one-third of the half jaw width (Pedro's house rule). Each is cited beside it.

Facts prechips has no field for, but which CAD specs and tests read, live in
[`cad/config/shop-equipment.toml`](../config/shop-equipment.toml):

- gauges: the DTI's kind and make, the pin-gauge note, the Mitutoyo gauge-block
  set (read by `ch_rocker_arm_tl_oblique_jig_assembly_spec.py`), the arm-outline
  template and the Vermont class X 2558-minus pin;
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
- the base-bar plan's vise workholding (1-3/8 in parallels, HHIP 3901-0079
  screw jack), with the ownership status Pedro's 2026-11-05 hand sheet gives
  (PR #2218): neither owned on that date;
- three `[[stock]]` rows: OnlineMetals 4807 strap and 1173 bar, and McMaster
  8663K55 acetal;
- the MHA-FR-02 top-frame casting to buy (owner ruling 2026-11-10 (Pedro),
  #2333): a gray-iron ASTM A48 class 25B `[[stock]]` row of form `casting`,
  with its pattern, datum-target and as-cast mass notes; not quoted or ordered;
- the MHA-SM-02 knife mount's records to make or buy (owner ruling 2026-11-10
  (Pedro), #2334): the MHA-SM-00 gauge bar (`gauges.gauge-bar-0472x8`), the
  12 mm H7 reamer (`tools.reamer-12mm-h7`) and a 4140/4142 HT `[[stock]]` row.

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

`cad/scripts/_process_plans.py:TRAVELER_STEMS` lists the parts with an opt-in
`prechips:<stem>` task: the oblique-trammel base bar and end bracket. `build`
and `release` do not run it, and releases carry no travelers while prechips
stabilises. Each run renders two travelers from the same plan: `traveler.html`
(`pro`, concise) and `traveler-hobby.html` (`hobby`, with the setup pictures in
`<stem>/diagrams/`). Under prechips 0.10.1 the base bar and end bracket pass both
on the v48 manifests. The base-bar and feed-lever plans need 0.10.1: they read
its adapter bindings `cad.vise_centred_overhang_mm` (centred overhang from the
CAD length and `vise_jaw_width_mm`) and `cad.overhang_mm` (from the lever's one
`overhang_in`), and the base-bar adapter refuses a Setup 5 jack centre off the
bar or inside a rail-hole, counterbore or slot outline.

prechips 0.10 adds the `vise_holding` check: every non-lathe setup declares
`vise_hold` (`"other"` for table clamps, saw or bench), and each milling-vise
hold is checked against `workholding.vise-pm-6` and the three vise limits
(opening, parallels below the jaw top, grip depth, centring or a declared
balance, and a rod against an unmachined moving-jaw face). Overhang rigidity
is not judged. All three plans pass it with HA's 5 3/4 in opening.

What the 0.10 port changed on the sheets:

- Base bar: bar 2 is the opposite hand of bar 1 (rail and table faces
  swapped), so Setup 4 marks bar 1 C'BORE SIDE and bar 2 RAIL SIDE, and Setup
  6 pictures bar 1 turned over (C'BORE SIDE down on the table, rail up) and a
  bar 2 section. The table setups use three 1-2-3 blocks, one at mid-length
  under the long-edge straps. Vise setups print the bar's stand-out above the
  jaws, keep the 1-3/8 in parallels and two screw jacks (touch only; Setup 5
  gives their DRO positions). Facing runs full length at 850 rpm, 6.8 in/min
  (owner ruling 2026-11-11, `settings.basebar-face-6061-t6511`). The rail
  stations are REF only, never drill targets (spec; owner R4 ruling, restated
  2026-11-11): all eight hole centres are measured on the bar's own rail,
  trimmed flush, the rail comes off, and each hole is drilled at its measured X.
  The 1/2 in end mill alone cuts both slots, tracing a cutter-centre
  rectangle printed per slot, and `tool_sizing` checks it against the slot
  width band less the path offset (the 3/8 in slot drill and 17/32 in
  slot-finish cutter are gone). Position checks are added: X on the DRO before
  unclamping, rows from ZERO EDGE with calipers. The saw is the 14 in Evolution
  metal-cutting miter saw (`tools.saw-evolution-14`, both logbook entries; no
  blade is recorded, #2084).
- End bracket: both brackets share each vise clamping, one at each jaw end
  (`balance = "twin_part"`), Pedro's 2026-11-10 ruling. Each operation runs on
  both before the next tool; X0 is the left part's INNER END and XR the right
  part's. The two blanks are sawn adjacent from the same bar so their as-bought
  widths match in the jaws. This route differs from the 2026-11-02 hand sheet
  (`hand-travelers/`), which holds and re-zeroes one bracket at a time.

The feed lever's plan (`ch_rocker_arm_tl_oblique_feed_lever/plan.toml`) is held
in the repository but not enrolled. It declares its vise holds and passes
`vise_holding`; prechips refuses it only on `tool_sizing`: the plan's 11/32
drill (8.73125 mm) is below the drawing's hole band (8.7376–8.8392 mm). That is
a finding for the owner (a different drill, or a drawing change), not a check
to opt out of; enroll the part once its plan passes.

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

The wrapper removes any previous `traveler.html` and `traveler-hobby.html`
under `cad/out/travelers/<stem>/`, resolves and logs the latest prechips
version, then runs
`uv tool run --from prechips==<version> prechips traveler cad/process/<stem>/plan.toml`
with `--profile pro` and then `--profile hobby`. Exit 0 from both is the only
pass. Exit 1 means uv itself failed: no `uv`, no PyPI, or a render whose
`uv tool run` failed before prechips ran (uv's `error:` or `×` diagnostic on
stderr); it is never a finding about the plan. A nonzero prechips exit from
either is returned and removes both files; exit 2 is
a refusal, either bad input or a failed enforced check (`stock_fit`,
`turning_deflection`, `cutting_speeds`, `tool_sizing`, `indexing`,
`gauge_capability`, `lathe_holding`, `vise_holding`, `machine_capacity`, or
`hobby`'s missing setup picture). A missing plan fails only that part's task.
A refusal is a finding about the plan or shop data; correct the source, not
the check.

A traveler that passes is not permission to machine: shop measurements,
physical setup verification and machining approval are still required. See the
[feature/traveler contract](../docs/pipeline/features-travelers.md).
