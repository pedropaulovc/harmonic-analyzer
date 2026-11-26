# Process plans and travelers

This directory holds the inputs to the `prechips:<stem>` travelers and the
`cam:<stem>` NC programs:

```text
cad/process/
  shop/common.toml          prechips shop directory: records several families share
  shop/<prefix>.toml        records only one subsystem family's plans name
  shop/standing.toml        the shop standing instructions page and the page header's project
  <stem>/plan.toml          one prechips plan per part (enrolled or placeholder),
                            or one family plan for several parts (see Family plans)
  placeholder-profile.toml  no-check prechips profile for the placeholder plans
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
through uv's tool runner. It reads the plan, the shop directory and the part's
exported `features.toml`, and writes standalone HTML travelers; the traveler
task prints the hobby sheet to `<slug>-traveler.pdf`, which releases ship. It needs no
FreeCAD or geometry kernel and checks no hashes. HA does not rewrite, bind or
stamp the plan; prechips reads the tracked file directly.

## Plans

`<stem>/plan.toml` follows the restarted prechips plan format documented in the
prechips README. It points at the part's scoped feature manifest and the shop
directory with paths relative to the plan:

```toml
shop = "../shop"

[cad]
file = "../../out/features/<stem>/features.toml"
adapter = "<prechips adapter for this part>"
```

Text and numeric fields take CAD values as `{{cad.<name>}}` and the plan's own
`[parameters]` as `{{process.<name>}}`; unknown names are refused. Bind
dimensions, limits and the drawing revision from `{{cad.…}}` rather than typing
them, so a CAD change reaches the traveler through the exported manifest. Every
file in the plan directory is an input to the traveler task.

Parts are enrolled by the CNC migration. Each enrolled plan opens with a header
comment that summarises the part's route (blank, setups, holding, zeros, NC
files); from 2026-11-21 that comment is the route summary and this README gets
no paragraph per part. The paragraph below records the parts enrolled before
then. The rocker strap (`ch_rocker_strap`,
MHA-CH-13) is the first: faced and bored in edge clamps on a shop-made
sub-plate, then bonded to it on tape and screwed down at the hub for the
outline. The magnifying clamp (`mg_magnifying_clamp`, MHA-MG-02) stands
upright on parallels in the vise for both ends and lies corner up between them
for its cross bore; its holes are tapped by hand under the spring tap guide
in the spindle, one Idle-ending NC file per hole. The column clamp halves
(`sh_column_clamp_front`, MHA-SH-01, and `sh_column_clamp_back`, MHA-SH-02)
are each squared from a 3/4 in bar blank on parallels in the vise and drilled
from one zero at the near side; the back's traveler then bolts each back to
its front, interpolates the shared bore on the split line, and faces the
back's grip offset off after unbolting. The oblique trammel jig's eight parts,
enrolled before it was deleted (owner ruling 2026-11-17, #2885), left their
plans, diagrams and the base bar's CAM recipe at
`ebd3bf3b44:cad/process/ch_rocker_arm_tl_oblique_*/` and
`ebd3bf3b44:cad/process/ch_rocker_arm_tl_vn_oblique_leadscrew_kit/`. Each
plan's `adapter` is a prechips adapter written against that part's manifest
contents, so a drawing change that alters the manifest's requirements needs a
prechips adapter release before the traveler passes again.

Plan parameters that size envelopes and pictures (vise jaw width, jaw height
and bed height) repeat the shop's `workholding.vise-pm-6` (`shop/common.toml`), because prechips
plan bindings cannot read shop records; each such parameter names the shop
field it repeats, and the two must be changed together.

Setup pictures (owner 2026-11-25: "work stop does not appear in sketches;
cutter is a wide yellow rectangle even for 1/2 in end mills"): every
workholding element a setup's holding, datum or operation text names (vise
jaws, parallels or stacks, 1-2-3 block, work stop, screws) appears in its
picture, and none it does not name; cutters, drills, taps, the tap guide and
locators such as the work stop's rod are drawn to scale from the plan's
numbers (a tool's diameter, its stick-out, its point's depth), at the pass or
station the picture shows, and end in a break line where drawn short. A
round tool or rod seen from the side carries the cue that it is round (owner
2026-11-25: "adding a round bottom"): its square end drawn as the near half
of its end face, a shallow arc 12 % of its diameter deep, whose apex is the
tool's true end, so its length and the cut depth still measure to scale; a
drill keeps its point. A size with no record stays schematic and is said to
be. A tool size a picture
reads is a plan parameter restating its shop record, held to it by a test
(`test_shop_equipment.py` for the tap guide) or by `cam.py`'s `_agree` (the
face overhang). A picture shows one moment: every view in it shows the same
tool at the same place, over the part (the face pass least past its edges, not
the first pass, which hangs over the fixed jaw). The setup's picture shows its first
cutting operation on the part (the first cut on the part, not a test plunge
into waste); each later tool (a drill, a tap) is drawn in its own
operation's picture, and a centre drill that spots the stations the next
drill drills is not drawn (the drill's picture stands for it). The work stop
is drawn as what it is, a round rod reaching in from its post beside the
vise (its own key entry, not the supports' hatch), and named once, in the
first picture that draws it, with when it is set. A locator that would lie
across or behind the part in a view is left out of that view, which says so
in a short callout (owner 2026-11-25: "rod is confusing on side view, better
to replace with a callout saying its not shown"); it appears in at least one
view of the picture, and a picture with only that view says in the callout
which end the locator is on. Touch-off tools (the edge
finder, the feeler) are not drawn in a cutting picture. Colour follows what
moves (owner 2026-11-25: "shouldnt the tap t handle be yellow since it is
arguably part of the cutter"): the tool's yellow covers the tool and all
that turns or travels with it or is held in the spindle (cutter, drill, tap,
the tap wrench or T-handle, the tap guide, a drill chuck where drawn, the
edge finder); grey is the work's surroundings (the rest of the bar,
hardware, fixtures); the work stop keeps its own entry. Template pictures
(`data-cad-template`) are drawn by prechips; the column clamp's
`clamp-half` takes `data-stop="rod"` or `"rod-labelled"`, and its
`data-up="outside"` picture is `data-work="face"` for the setup, `"drill"` or
`"tap"` for those operations. Where a family's halves differ only in what a
picture shows of them, one picture draws both (`data-halves="both"`: the
mating skim's two views from above, the finished front and back) rather
than a box each; a picture that only repeats what the drill or tap
pictures and the text already say (the halves before the bore) is left out.

## Placeholder plans

Until its traveler is written, a made part without an enrolled plan has a
placeholder `<stem>/plan.toml` (owner 2026-11-19): `revision = "placeholder"`, the
registry number, title and material, `stock = "To be written"`, one
`[[tools]]` entry per tool the part needs, and one dummy setup ("Traveler to
come"). Its tools come from the owner's quote workbook
`quotes-2026-11-17-rev3.xlsx` (its Items, Where used detail, Drills and Tap
coverage sheets), from a cross-check of the plans against the drawings
(2026-11-19) and from owner rulings, each `ref` a shop `tools` record
whose header comment cites the workbook row, the drawing callout, the inventory
record or the ruling, with the
tool's ownership in the inventory under the same key. Its `stock_refs` names
the inventory `[stock.<key>]` rows it is cut from (the stock assignment audit,
owner 2026-11-19). A placeholder is not enrolled (`revision = "placeholder"`
keeps it out of `TRAVELER_STEMS`): it has no `prechips:<stem>`
task, is not rendered by `build` or `release` and ships nothing; it lists a
part's tools for the stock BOM. It has no `[cad]` binding, so the built-in
`pro` and `hobby` profiles refuse it (`stock_fit` needs one);
`placeholder-profile.toml` checks nothing and validates it by hand:

```text
uv tool run --from prechips==<version> prechips traveler cad/process/<stem>/plan.toml --profile cad/process/placeholder-profile.toml --out <file outside the repo>
```

prechips refuses a plan with no `[[tools]]`, so a made part neither source names
a tool for has no placeholder. Enrolling a part means writing its real plan
over the placeholder (the `[cad]` binding, stock and setups, and a `revision`
bound from `{{cad.revision}}`), and, for a milled part, adding its `cam.py`.
The files are the enrolment: `_process_plans.TRAVELER_STEMS` is every plan
whose `revision` is not `"placeholder"` and `_cam_programs.CAM_STEMS` every
part with a `cam.py` (each needs an enrolled plan); no list is edited. A
family plan enrols its family stem for every part it binds (below).

## Family plans: one traveler for near-twin parts

Owner rulings 2026-11-24, after the column clamp trial (2026-11-22: "theres
too much repetition bw front and back clamps"): "Adopt it: delete the two
single plans; one plan serves both parts."; "One shared CC01-04 set."; a
release ships "a placeholder pdf per part that points to shared one";
"Renumber, so T3 means one drill everywhere on the sheet."; "Rename the marks
(fronts F1-F3 stay; backs become K1-K3)."

A family plan is one `<family>/plan.toml` for parts that start as the same
blank (same stock, same sawn length; each part its own piece) and go through
shared setups on one route. `sh_column_clamp/` is the first: it
serves MHA-SH-01 (`sh_column_clamp_front`) and MHA-SH-02
(`sh_column_clamp_back`), and neither part has a directory of its own here.
The contract:

- **Plan.** prechips `[[parts]]` binds each part's feature manifest under an
  id (`front`, `back`). A setup or operation with `part = "<id>"` binds that
  part's drawing values; the rest bind only values every part gives alike
  (prechips refuses the others), so a shared setup cannot print a number true
  of one part only. Each tool the mill runs has a `number`, its T number in
  every program; each setup lists its `programs`; a setup that prints one
  part's values but holds several lists them in `serves`.
- **Enrolment.** The family's stem is the enrolled stem
  (`TRAVELER_STEMS`, `CAM_STEMS`, `prechips:sh_column_clamp`,
  `cam:sh_column_clamp`). `_process_plans.family_parts(stem)` gives its parts,
  `part_stems(stem)` the parts any plan serves, and `part_view(plan, id)` one
  part's reading of the plan (shared parameters under its own; the setups and
  operations that name it or none, and the setups that list it in `serves`). A part served by two enrolled plans fails task loading.
- **Travelers.** `prechips:<family>` writes the shared sheets
  (`traveler.html`, `traveler-hobby.html`, `<family slug>-traveler.pdf`) and,
  for each part, a one-page placeholder `<part slug>-traveler.pdf` beside
  them (prechips `--placeholder <id>`): the part's number and name, the shared
  traveler's title and file name, the revision, and the shared setups and
  programs that part goes through. It carries no instructions, so it cannot
  drift from the shared sheet. A release ships the shared PDF once and each
  placeholder under its part's name, so every enrolled part still has
  `travelers/<part slug>-traveler.pdf`.
- **NC: one recipe, one program set, one manifest.** `<family>/cam.py` posts
  every program of the family once into `cad/out/nc/<family>/` (a release:
  `nc/<family>/`): the programs every blank runs (`CC01`-`CC04`), then each
  part's own (`CF*`, `CB*`). Its `context` is given each part's features, plan
  view and STEP by id, derives the shared programs from every part and
  refuses to post unless they agree move for move and check for check. The
  one `manifest.json` records every part's bundle (`features/<part stem>`,
  `step/<part stem>`), so a change to either drawing re-posts the set and a
  stale set fails the cut. No part has an `nc/` directory or manifest of its
  own; its placeholder names the family's programs.
- **Stock list.** `stock_bom.py` still reads one line per registry part: a
  family's part lists the plan's stock and the tools and gauges of the setups
  and operations it goes through.
- **Review.** The shared sheet is reviewed once, with every part's drawing as
  a companion; a placeholder is checked against it by reading.

Write a family plan only for parts that pass through shared setups. Near-twin
text between parts that never share a setup (the enamel recipe, the touch-off
wording) is not a family.

## Shop records

`shop/` is the prechips shop directory: machines, workholding, gauges, limits,
tools and cutting settings, in prechips' schema and units. prechips (0.11.10 and
later) merges every `*.toml` directly in it by section and refuses a key
defined in two files; HA reads it the same way through
`_process_plans.load_shop()`. `common.toml` holds the machines, workholding,
limits and gauges, and every tool, setting and stock record that plans of more
than one subsystem family name; `<prefix>.toml` (`ch`, `dt`, `fr`, `mg`, `ms`,
`pd`, `pn`, `sm`; a family without one adds it) holds the records only that
family's plans or specs/tests read, each with its citation comments. A family's
change adds its records to its own file. A record a second family needs moves
to `common.toml` in that change (deleted from the family file: a key in two
files is refused). A set of new records several families need, added by one
change, may start its own topic file (for example `lathe.toml`) instead of
growing `common.toml`. The directory holds only records
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

`standing.toml` is the shop's **standing instructions** page (owner
2026-11-25): what is common sense on every traveler (units, speeds, homing
and the zero re-check, Feed Hold, tool changes, proving a file, burrs, the
work stop, picture colours, "stop and tell the owner", and that a traveler is
not approval to machine). `prechips:standing` renders it once and the release
ships it as `travelers/shop-standing-instructions.pdf`; every traveler review
receives its text (rule T18 in `cad/docs/traveler-guidelines.md`). A plan
with `standing = true` prints only its one pointer line at the head and does
not repeat or re-word anything on it; a step prints a caution only where it is
critical, uncommon or confusing for that part. Its `[sheet] project` is the
running page header every traveler page carries. Plans convert batch by batch
(owner 2026-11-25: reviews stay on hold until then).

Converting a plan to the standing page (owner 2026-11-25: "convert the other
plans in batches"; the column clamp is the worked example):

1. Set root `standing = true` and delete the top-level `note`. What only this
   job needs (parts and marks, which setups serve which part, program
   prefixes, where finished sizes are tabled) goes into a `[[notes]]` block
   titled `This job`, one `[label, text]` row per idea, 60 printed words at
   most each; nothing a setup's Holding, Datum or op already prints.
2. Delete every sentence anywhere in the plan (head, Holding, Datum, op
   text, detail, steps, inspection) that says again what a standing row says:
   - units and G21;
   - speeds and belt;
   - homing once, homing again, and the zero re-check;
   - Feed Hold / Reset, including "(the controller keeps G54...)";
   - "(the tool setter measures it)" and "tool lengths from the tool setter";
   - the prove-in-air ops: delete the op (the method is the standing row
     "A file's first part", and its "watch every move ... clear the work,
     the jaws, the parallels, any clamp and the stop" covers a list of what
     a move clears, screw heads included); keep only a proof that departs
     from the row (a partial file, another raise);
   - burrs off before a face seats;
   - the work stop's rod drawn back before a touch-off.
3. Keep, at its own step, every departure from a standing row that is true
   only for this part: "do not home from here to the end of MS04", "this file
   has no M6: console M6 T2 before running it again", "pick G54 up again after
   a vise move", a rod moved mid-setup, a part-specific Feed Hold caution.
   Rewrite old wording that contradicts the standing page ("home at the start
   of every mill setup") to the standing rule, or delete it.
4. Remove the stem from `cad/config/machinist-review/standing-unconverted.yaml`.
5. Proof, on the PR:
   - a text diff, each removed sentence named with the standing row or step
     that now carries it;
   - the NC byte-identical: the recipe context and every posted program,
     before and after (the clamp's recipe reads no op text; if a program
     changes, something besides wording moved, so stop);
   - both profiles rendered, exit 0, with the hobby page count before and
     after;
   - the plan's own tests.
   Deleting ops renumbers the route, so check that nothing (plan text,
   tests, `machinist_exceptions`, `demoted.yaml`) cites an op number.
   Traveler reviews stay held until the owner lifts the hold.

Every inventory stock key a plan's `stock_refs` names also has a
`[stock.<key>]` record here, `description` only, because prechips checks each
plan's `stock_refs` against its shop. The stock's ownership `status` stays in
the inventory (`cad/config/shop-equipment/stock-*.toml`), so an enrolled
traveler prints no stock mark.

The `[limits]` table carries the three `vise_holding` limits: grip at least
`vise_grip_min_mm` 6 mm (Pedro's house choice) and `vise_grip_fraction_min`
one-third of the part's height (a rule of thumb, not a standard), and a
`"centred"` hold's gripped-span midpoint within `vise_centre_fraction_max`
one-third of the half jaw width (Pedro's house rule). Each is cited beside it.

Facts prechips has no field for, but which CAD specs and tests read, live in
the TOML files under [`cad/config/shop-equipment/`](../config/shop-equipment/),
split by topic and read only through `cad/scripts/_shop_equipment.py`, whose
`load()` merges them by section and refuses a record key found in two files.
Ownership is one `status`: `on_hand`, `not_received` (bought, not in the
shop), `to_order` or `to_make`; a record without one reads `unrecorded` in
every reader, and a shop directory record holds no ownership. A record the shop
makes carries `supply = "shop_made"` (provenance only). A record with
`location = "makerspace"` is the makerspace's equipment, used there (owner
ruling 2026-11-20, #2288); readers label it by its `status` alone, so no plan
names one until a reader labels makerspace equipment as such. No record names
the parts it serves as data (that is prose in its `note`): parts point at what
they need from their process plans. They hold:

- `measured_cuts.<setting>`: the envelope a measured cutting setting (a
  `shop/` `settings.<setting>` record from a dechatter report under
  `dechatter/`) is valid inside: the tool assembly's stick-out (`stickout_mm`; a
  record may allow a band with `stickout_min_mm` and `stickout_max_mm`, the
  reason beside it: the three 1/2 in carbide records allow 27.94 to 28.45 mm,
  and the plans pin the 28.45 the owner ruled on 2026-11-24) and the
  plan parameter that pins it, the deepest and the widest cut found stable.
  prechips refuses any other key on a setting, so the limits are data here;
  `test_measured_cuts.py` checks each against its report and refuses a plan
  operation that names the setting with a stick-out the record does not
  allow, or a
  `milling_cuts` entry deeper or wider than measured. The spindle is set by
  hand and a report prints the speed it asked for; the speed the spindle ran
  is in the session's results file beside the report (`results`,
  `spindle_hz` × 60), and a record may carry the band of heard speeds its
  limit holds in (`speed_in_cut_rpm`, `speed_no_load_rpm`), which the test
  checks against that file. The cut direction the
  passes ran (`direction`) is recorded and NOT checked: a cut has no direction
  field, so a climb pass on a measured setting is not refused;
- the PM-30MV's spindle speed stops (`machines.pm-30mv`:
  `spindle_speed_step_rpm`, `spindle_speed_steps`, the resting speeds
  observed, and how the head's display reads against the heard speed): the
  spindle rests only every 107.7 rpm, so a measured face record names the
  stop to bring the display to (`measured_cuts.<setting>.display_rest_rpm`)
  and the plans print it beside the speed asked for;
- ownership-only records, under the shop key, for the PM-30MV mill, the
  PM-1127VF-LB lathe, the calipers, the DRO scales and the clamp bore's and
  stop plate's drill shanks read as gauges (`machines.*`, `gauges.calipers`,
  `gauges.mill-x-dro`, `gauges.mill-y-dro`, `gauges.clamp-bore-drill-shanks`,
  `gauges.ms-plate-hole-drill-shanks`);
- gauges: the DTI's kind, the pin-gauge note, the Mitutoyo gauge-block set
  and the indicators' ownership;
- the PM-30MV DRO's make and cited accuracy (read by the paper-drive tests);
- the LMS 6784 end-mill set and its sizes, the 8-32 plug hand tap's flute
  length, and the shop-made rocker trammel's R800/R816 lengths;
- the cylinder gear's alignment-notch saw (TTC 10-215-014, .014 in), not
  owned, read by `test_dt_cylinder_gear_drawing.py` against the printed
  .016 MAX (#2364);
- the measuring stick's engraving bit (ESAO 3.175*30*0.1, 30° V, 0.1 mm
  tip), on hand, which cuts every MHA-MS-01 graduation and numeral; its
  brass cutting setting is `shop/ms.toml` `settings.ms-stick-engrave-brass`, and
  `test_ms_stick_drawing.py` reads both against the printed groove limits
  (#2433);
- the PM 6-in vise's make, SKU and source;
- a `[stock.<key>]` row for every bought bar, tube, wire and ball, each quoting
  its order line and allocation: Online Metals orders 1021704672 and
  1021751700, Metal Supermarkets invoice EC234347, McMaster-Carr PO
  0803PCAMPOS and McMaster 8663K55 acetal (owner 2026-11-17: all on hand but
  the platen's C360 plate), and the stock still to order. Every row carries
  `status` (`on_hand`, `not_received` or `to_order`); a process plan names the
  rows it is cut from in `stock_refs`.
  `uv run --frozen python cad/scripts/stock_bom.py [--format md|csv|xlsx]` joins
  the part registry's made parts (every stem without `-vn-`: a vendor part is
  bought finished, bought hardware with added machining is made) to their plans (every `<stem>/plan.toml`,
  enrolled or placeholder), normalized to one row per part and requirement:
  `type` `stock` (each row the plan names, with its status;
  one `vendor_sku`, `no_stock_record` or `no_traveler` row when it names none),
  `tool` (each `[[tools]]` entry of the part's process plan; one `no_traveler`
  row for a part without a plan) or `gauge` (each gauge its setups' and
  operations' `gauge_checks` name, once), then the stock rows no plan names
  with the part columns empty. A tool's or gauge's ownership is the `status`
  of the inventory record under its shop key in whichever of `tools`,
  `fixtures`, `consumables`, `gauges` and `holders` holds it, or `unrecorded` with no
  record, no status or (a tool) no `ref`. The md summary line counts the parts
  `ready`, `missing` and `no_traveler`. `--format xlsx --out PATH` adds a
  Readiness sheet first: per part, its missing stock rows (`not_received`,
  `to_order`, `no_stock_record`), missing tools and missing gauges (every
  status but `on_hand`) and state (`ready` only with none missing, `missing`,
  `no_traveler`), as COUNTIFS formulas over the BOM sheet (xlsxwriter cannot
  write a native PivotTable). Tools and gauges point from the plan, never from
  this inventory. It exits 2 when a stock row or inventory record carries an
  unknown status, a key sits in two of those sections, a plan names an unknown
  or vendor (`-vn-`) stem or unknown stock, or a plan's tool `ref` or gauge is not
  in the shop directory, and `test_stock_bom.py` (`check:recipe`) runs that check on
  every change;
- the MHA-FR-02 top-frame casting to buy (owner ruling 2026-11-10 (Pedro),
  #2333): a gray-iron ASTM A48 class 25B `[stock.<key>]` row of form `casting`,
  with its pattern, datum-target and as-cast mass notes; not quoted or ordered;
- the MHA-SM-02 knife mount's records to make or buy (owner ruling 2026-11-10
  (Pedro), #2334): the MHA-SM-00 (Ø.49) gauge bar (`gauges.gauge-bar-0472x8`), the
  .4990 reamer (`tools.reamer-4990`; owner ruling 2026-11-23, tool audit Q13: "no
  12 mm reamer") and a 4140/4142 HT `[stock.<key>]` row;
- the MHA-SM-01 gooseneck tube to buy (owner rulings 2026-10-27 (Pedro), #1951,
  2026-11-08, #2315, 2026-11-14, #2401, and 2026-11-22, option A,
  `https://github.com/pedropaulovc/harmonic-analyzer/issues/2401#issuecomment-7085840331`, superseding #2401's 36 in):
  a 4130-N `[stock.<key>]` row of form `round_tube` (OnlineMetals 7322, one
  48 in cut with about 23 in for a trial bend to 90° on the form before the
  part), read by `test_sm_gooseneck_drawing.py` against the bent tube's
  developed length plus its ~2 in arm-end tail and ~1 in at the foot, and the
  shop-made bend form it is
  bent on (`fixtures.sm-gooseneck-bend-form`, no toleranced size: the radius
  is a reference);
- the owned tools, gauges, cutters, inserts, holders, saws and shop fluids of
  McMaster-Carr PO 0803PCAMPOS (packing list 1616317-01, 08/04/2025; owner
  2026-11-17), each with its SKU, quantity and packing-list line;

One fact lives in one file. The same object may appear in both directories with
disjoint fields (the DTI, for example), but no field is duplicated. Together
the two directories are the source of truth for installed shop equipment.

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
  is in the inputs they will be considered" (2026-11-10). Shop and plan
  values are used as written, with no measured/placeholder provenance.
- The shop directory and the plans carry HA's own recorded values, not the prechips
  example ones: where the deleted inventory or shop policy (`45952b66bc`) held a
  different value for the same machine, holder or limit, HA's value is used
  and marked `HA:` in a comment beside it.
- Cutter and drill diameters stay at their nominal sizes. Sizing compares the
  named tool size with the drawing band; HA's per-tool readings in the deleted
  inventory (for example #29 3.451 mm, #12 4.798 mm, the 3/4 in end mill
  19.039 mm) were #1413 "realistic placeholder" values, not shop measurements,
  and under the ruling above values are used as written in the shop, which
  states the nominal size.

## Travelers

`cad/scripts/_process_plans.py:TRAVELER_STEMS`, derived from the plan files,
lists the parts with a `prechips:<stem>` task: every `<stem>/plan.toml` that is
not a placeholder (a plan TOML cannot read fails task loading, naming it). `build` runs
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
`package:manifest:<stem>` task, which needs the part's labelled STEP from its
`package:features:<stem>` leaf (SolidWorks, via the supervised farm); the
wrapper and the by-hand `uvx` command need an existing bundle, from a build or,
with no SolidWorks and no farm run, from a release:
`uv run --frozen python cad/scripts/fetch_features.py <stem>` (for a family
plan, once per part it binds: `fetch_features.py sh_column_clamp_front` and
`sh_column_clamp_back`, then the family stem `sh_column_clamp` in the commands
above; it rebinds the
manifest to this checkout's declarations, and reports a bundle whose geometry
has moved past the release, or any bundle from a release cut before face
inventories shipped (#3232), as STALE and writes nothing; see
[features and travelers](../docs/pipeline/features-travelers.md)). All three use the latest
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
`hobby`'s missing setup picture).
A refusal is a finding about the plan or shop data; correct the source, not
the check.

A traveler that passes is not permission to machine: shop measurements,
physical setup verification and machining approval are still required. See the
[feature/traveler contract](../docs/pipeline/features-travelers.md).

## NC programs (FreeCAD CAM)

A part with `<stem>/cam.py` (`cad/scripts/_cam_programs.py:CAM_STEMS`, derived
from the recipe files; each needs an enrolled plan) has a CAM recipe that turns the plan's
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
Its only task dependency is its own `package:manifest:<stem>` task. A release
ships the programs, `cycle_times.json` and `manifest.json` (not the log) under
the bundle's `nc/<stem>/`; a missing output, a program or `cycle_times.json`
that differs from the manifest, or a manifest recording any input other than
the current one (the feature bundle, `plan.toml`, each shop file, the recipe or
the runtime: `_cam_programs.cam_inputs`) fails the cut.

A recipe has five parts:

- `PROGRAMS`: the file names, each listing its operations, flat (one FreeCAD
  Job, posted as it is) or in sections (one Job per tool and spindle speed,
  or a manual section: G-code the recipe writes itself, such as an operator
  stop or a probing cycle). Sections join into one file. A file may be one
  manual section alone, a hand-tap stop: it must load its tool first (`M6`,
  so the guide's length is set: the Fisher spring tap guide in the 1/2 in R8
  collet, shop `tools.tap-guide-fisher`, owner ruling 2026-11-21), retract
  with `G53 G0 Z` to the machine top (machine Z0, the top of travel after
  homing, owner 2026-11-21; `cnc.pm-30mv-controller`), rapid over the hole
  and end `M30`, so the controller is Idle where FluidNC allows jogging;
  `_gcode.check_tap_stop` proves it. A new tool starts at
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
  the shop directory. It also places the part in each setup's work frame and lays out
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
  time is split at. A tabbed outline declares its tabs to
  `check_outline(..., tabs=...)`: each tab's box, top, floor and the
  recipe's thickness. The check proves each tab stands (every pass cut below
  its top hops it level at that top, no feed move, plunges included, enters
  its box below that top, and a level reaches its floor elsewhere) and that
  every level still covers the outline outside the boxes, so an undeclared
  gap, a moved or short box, a plunge inside a tab or a thinner tab fails.

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
