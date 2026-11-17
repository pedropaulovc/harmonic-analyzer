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

The base bar, end bracket and feed lever have plans ported from the prechips
0.10 examples. The riser's plan is authored here, and prechips `examples/riser.toml`
copies it. Each header names its sources. Each plan's `adapter` is a prechips
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
  12 mm H7 reamer (`tools.reamer-12mm-h7`) and a 4140/4142 HT `[[stock]]` row;
- the MHA-SM-01 gooseneck tube to buy (owner rulings 2026-10-27 (Pedro), #1951,
  2026-11-08, #2315, and 2026-11-14, #2401): a 4130-N `[[stock]]` row of form
  `round_tube` (OnlineMetals 7322, one 36 in cut with about 11 in for a trial
  bend), read by `test_sm_gooseneck_drawing.py` against the bent tube's
  developed length plus its ~2 in arm-end tail and ~1 in at the foot, and the
  shop-made bend form it is
  bent on (`fixtures.sm-gooseneck-bend-form`, no toleranced size: the radius
  is a reference);
- the leadscrew kit's hacksaw (`tools.kit-hacksaw`) and 3/16 in-body 82°
  countersink (`tools.kit-countersink-82`), not owned (HA #2740);

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
`prechips:<stem>` task: the oblique-trammel base bar, end bracket, feed
lever, riser, pivot block, feed block, leadscrew kit and carrier. `build` runs
every one beside the drawing PDFs (`build_bare` runs none); `release` runs
every one and ships each hobby sheet as
`travelers/<slug>-traveler.pdf` (owner ruling 2026-11-14). Each run renders two
travelers from the same plan: `traveler.html` (`pro`, concise) and
`traveler-hobby.html` (`hobby`, with the setup pictures in `<stem>/diagrams/`),
then prints the hobby sheet to `<slug>-traveler.pdf` with a headless Edge or
Chrome. A plan that prechips refuses therefore blocks the release. Under prechips 0.10.1 the base bar and
end bracket pass both on the v49 manifests. The base-bar and feed-lever plans
need 0.10.1: they read its adapter bindings `cad.vise_centred_overhang_mm`
(centred overhang from the CAD length and `vise_jaw_width_mm`) and
`cad.overhang_mm` (from the lever's one `overhang_in`), and the base-bar adapter
refuses a Setup 3 jack centre off the bar or inside a rail-hole, counterbore or
slot outline. Since owner ruling 2026-11-16 the base-bar plan needs the first
prechips release after 0.11.2, which carries pedropaulovc/prechips#427: 0.11.2
refuses the manifest's banded rail stations, and the plan reads that release's
`cad.rail_station_tol_in`, `cad.rail_station_tol_mm`, `cad.rail_first_band_mm`
and `cad.rail_last_band_mm`. The feed-lever plan needs 0.11.0, which binds the lever's
grip-corner fillet (`cad.corner_radius_in` and its limits). All three plans
carry 0.11.0's `milling_deflection` data (a `beam` per non-lathe setup or
operation, `milling_cuts` per spindle operation) and pass that check enforced;
the end-bracket plan's tap flags and the dropped feed-lever grip-end setup
need the 0.11.0 jig pictures, so they pass under `@latest` from 0.11.0 (released). The riser plan needs 0.11.4
(its `harmonic_riser` adapter's Setup 2 stations and Setup 4 guards). Every plan (base bar, end bracket, feed
lever, riser, carrier, pivot and feed blocks, leadscrew kit) carries
`drill_pecking` data and so needs prechips 0.11.4 (pedropaulovc/prechips#403):
every operation with a tool declares `drilling` (`"twist_drill"`, or `"none"`
for spots, countersinks, reamers, end mills, taps, saws and files), and each
twist-drilled hole declares `peck` (`"none"` or `{ step_mm, retract }`) and
`hole_depth_mm`. Each step is one mm process parameter (`*_peck_mm`, one
drill Ø) bound into both `step_mm` and the instruction
(`{{process.<name>:in.3dot}}`), and the feed-block pilot depth is the process
parameter `lug_bore_depth_mm`, printed the same way; earlier releases refuse
those fields and bindings.

The riser plan (TL-24) needs prechips 0.11.4: 0.11.0 added its `harmonic_riser`
adapter and the `milling_deflection` check; 0.11.4 derives the Setup 2 strap
stations and faced spans from the authored strap layout (refusing a strap off
faced metal or in a cut), binds the .230 minimum thickness the Setup 3–5 beams
take, and refuses a stop hole over a jaw with the longest (14.05) blank or a Y0
touch the .200 edge finder cannot make clear of hold 1's jaws. It passes both
profiles, with every check enforced, on the v49 manifest. Setups 1–4 make the
bar and drill the stop-pin holes P1/P2 at their printed stations. Setup 1
calipers the bar: under .230 anywhere rejects it, and Setup 2 faces it only when
it is over the .25 thickness limit, from three straps then four, because a
single strap span along the bar's length bends the thin bar ~.23 mm under the
cutter. The 1/2 in end mill runs at the logbook's 1800 rpm, 7 in/min. The other
seven holes print X/Y LOC REF: Setup 5 runs after TL-00 step 11C has spotted
them from the carrier and drills each at its own mark, so its table gives the
REF X/Y only to find the marks. The 12 mm HUB drill and the 82° countersink are
recorded as not owned in `cad/config/shop-equipment.toml`.

prechips 0.10 adds the `vise_holding` check: every non-lathe setup declares
`vise_hold` (`"other"` for table clamps, saw or bench), and each milling-vise
hold is checked against `workholding.vise-pm-6` and the three vise limits
(opening, parallels below the jaw top, grip depth, centring or a declared
balance, and a rod against an unmachined moving-jaw face). Overhang rigidity
is not judged. All three plans pass it with HA's 5 3/4 in opening.

What the 0.10 port and the 2026-11-13 v49 reassessment changed on the sheets:

- Base bar: bar 2 is the opposite hand of bar 1 (rail and table faces
  swapped), so Setup 3 marks bar 1 C'BORE SIDE and bar 2 RAIL SIDE, and Setup
  4 pictures bar 1 turned over (C'BORE SIDE down on the table, rail up) and a
  bar 2 section. The edge setup uses three 1-2-3 blocks, one at mid-length,
  and two end straps; program BB01 cuts both edges, alternating pass by pass,
  and its setup names the work offsets and the full-depth plunges beside the
  blank ends. Setup 3 holds each bar in one vise clamping from the side-2
  face on (owner ruling 2026-11-16, "merge"): after facing side 1, flipping
  and facing side 2 it squares both ends, mills both slots and then spots,
  drills, taps and counterbores without unclamping, so the holes keep
  the ZERO END squared and the ZERO EDGE edge-found there (2026-11-14
  traveler review: the former table-strapped end squaring left the ends on a
  221 mm cantilever, 0.057 mm under `milling_deflection`, refused). The slots
  take .05 depth steps on the jaws' cantilever. Setup 3 prints the bar's
  stand-out above the jaws, keeps the 1-3/8 in parallels and two screw jacks
  (touch only, at the DRO positions it gives) as set, and splits its drill and
  counterbore operations by end, each over its jack. Facing runs full length
  at 850 rpm, 6.8 in/min (owner ruling 2026-11-11,
  `settings.basebar-face-6061-t6511`). The edges and ends use the dechatter
  v11 records (`settings.em-half-hss-6061-v11-wide`/`-narrow`, at most
  7.62 mm per depth level, 48.8 mm stickout), both at 2250 rpm: the narrow
  column was stable at every speed measured, and the ends no longer share the
  slots' 1250. Every speed is on the PM-30MV's low belt, 100–2800 rpm (owner
  ruling 2026-11-16, "2800 max with low belty"): no belt change. The rail
  holes are drilled at their printed stations, ±0.05 mm from ZERO END, on
  the CNC by programs BB05 (spot) and BB07 (#29 drill) of
  `cam:ch_rocker_arm_tl_oblique_base_bar` (owner rulings 2026-11-16,
  superseding the R4 transfer from the trimmed rail; "Rail holes CNC at
  ±0.05 mm OK" is the part yaml's RV-04): each bar's untrimmed rail is then
  fitted with its eight screws entering free and only then cut and ground
  flush with both bar ends per TL-00 steps 1D–1F (`tools.rail-trim-grinder`,
  not owned yet). The owner assumes the purchased rail's hole span within
  0.15 mm of nominal; the base-bar spec's `RAIL_FIT_STACK` closes that, with
  the CNC's hole-to-hole scatter (the converted PM-30MV's ±0.02 mm
  repeatability, `cad/config/shop-equipment.toml` `cnc.pm-30mv`), the
  spring tap guide's 0.05° squareness (`tools.spring-tap-guide`; owner ruling
  2026-11-16) and the rail holes' Ø4.50 receipt minimum (TL-VN-83 sheet 2,
  checked at TL-00 step 1J), under the screws' float. The
  1/2 in end mill alone cuts both slots, tracing a cutter-centre rectangle
  printed per slot, and `tool_sizing` checks it against the slot width band
  less the path offset (the 3/8 in slot
  drill and 17/32 in slot-finish cutter are gone). Position checks are added:
  X on the DRO before unclamping, rows from ZERO EDGE with calipers. The saw
  is the 14 in Evolution metal-cutting miter saw (`tools.saw-evolution-14`,
  both logbook entries; no blade is recorded, #2084).
- End bracket: both brackets share each vise clamping, one at each jaw end
  (`balance = "twin_part"`), Pedro's 2026-11-10 ruling. Each operation runs on
  both before the next tool; X0 is the left part's INNER END and XR the right
  part's. The two blanks are sawn adjacent from the same bar so their as-bought
  widths match in the jaws. This route differs from the 2026-11-02 hand sheet
  (`hand-travelers/`), which holds and re-zeroes one bracket at a time. The
  sheet's FRONT FACE is the plan's KP08 SIDE and its BACK FACE the BAR SIDE.
  The #29 drill runs to 1.06 below BAR SIDE so the KP08-side exit is full
  size; each face's plug and bottoming taps carry one flag (BAR .45, KP08 .51
  from the tip, in the low half of the drawing's tip windows) so the two
  bottoming taps never meet; Setup 4 lines up on the drilled holes instead of
  re-finding datums. The final screw check runs a flagged screw only to its
  own face's full-thread depth, never on into the opposite face's thread.
- Feed lever: the 2X bolt holes are the 11/32 drill, `2X Ø.3438 11/32 DRILL
  THRU ALL`, +.004/0 (owner ruling 2026-11-13, so the traveler follows the
  post-v49 drawing; the former 5/16 normal-fit clearance, Ø.344, put the
  plan's 11/32 drill under its minimum), inspected with pin gauges. The grip
  corners' R.2 and its R.1–R.3 band come from the manifest's `grip_corners`
  fillet, not an authored radius. The saw cut at 11.85 is the finished grip
  end (11.8 ±.1 after the ZERO END clean-up, checked on the DRO), so the plan
  has no second vise setup.

The carrier (`ch_rocker_arm_tl_oblique_carrier/plan.toml`, MHA-CH-06-TL-21)
is enrolled. It needs prechips 0.11.1 (the `harmonic_carrier` adapter with
its `block_tolerance_in` refusal, and the `jig-carrier-*` pictures), and passes
both profiles under `@latest` with every check enforced. The 20.5 in plate is made flat on the table, vise off,
on four 1-2-3 blocks under the LMS 1268 strap clamps (both owned, logbook
2026-11-05/06), placed between hole columns, as the registry note now says
(on edge in the vise the jaws grip at most 1.77 in of the 6 in-tall bar, under
the one-third rule). Strap toes land on the blocks. Holes run from
the lower-left corner as sheet 2 prints them, from one DRO zero; note 2's
relations (B1, A2, B2, CL, CR, R1-R4 from A1 and the A1-B1 line) are inspected
before tapping by centring the DTI on a pin in each hole. The .3760-.3770 bores
are checked .376 GO / .377 NO-GO with the owned pin-gauge set, and their
underside edges carry the title-block break only (owner rulings 2026-11-13).

The pivot block (`ch_rocker_arm_tl_oblique_pivot_block`, TL-22) and feed block
(`ch_rocker_arm_tl_oblique_feed_block`, TL-32) plans are written fresh against
the v50 sheets' manifests (no hand traveler): each saws its own blank from the
OnlineMetals 1187 1 x 3 in bar (`cad/config/shop-equipment.toml` `[[stock]]`;
TL-22 a 1.70 strip, then across to 1.70 x 1.70), faces SEAT and TOP with the
1/2 in end mill, mills the 1.64 length (TL-32: about 1.36 in off the 3 in
width in .10 layers, #2083) and the sawn ends on end, then cuts every top hole
in one hold: the 4X .180 holes and .31 counterbores to the .570 floor, and the
pivot seat (F tap drill, then the LMS 6784 3/8 end mill, miked at .3750 or
more, plunged to the flat .359 floor, .375–.379 under DRILLED HOLES, owner
ruling 2026-11-13; then the 5/16-18 tap through). TL-32 adds the lug notch,
standing on edge (OUTER END down, LUG END out past the jaw side; at the other
jaw end a spacer offcut faced with the block to its height within .001, not
the finished TL-22) so the owner's 1 in-flute 1/2 in end mill's end cuts the
lug face and leaves a square inside corner, and the Ø.375 leadscrew clearance,
piloted and plunged in .25 full-retract pecks with the same 3/8 end mill with
the block standing on SPINDLE END; the KP08 axis-height check moves to the TL-00 assembly (#2184),
and its four #4-40 nut taps stay with the TL-00 transfer. Their adapters
(`harmonic_pivot_block`, `harmonic_feed_block`) ship in prechips 0.11.0 (released). No
boring head is needed; the F drill and 5/16-18 plug tap share the carrier's
records (`jig-drill-f`, `jig-tap-5-16-18-plug`).

The leadscrew kit's plan (`ch_rocker_arm_tl_vn_oblique_leadscrew_kit/plan.toml`,
MHA-CH-06-TL-VN-84) is enrolled and needs prechips 0.11.4 (its saw lay binds the adapter's rounded-up 1/16 in step): its
`harmonic_leadscrew_kit` adapter binds the two-member manifest (the LeadScrew's
cut end and five flats, the FeedNut member's faced seat, countersinks and
receipt limits), and its `kit-*` setup pictures are prechips layouts. The route
is authored (no hand traveler): receive and check the kit, hacksaw the screw
long, mill the cut end to length from the NEAR END, mill the five set-screw
flats on the BS-0 dividing head (the handwheel flat in its own 16 mm re-grip:
at the cut-end KP08 flats' 42 mm stick-out `milling_deflection` estimates about
0.09 mm against the 0.025 mm finish limit), face the nut's spigot in the lathe
on the threaded offcut and countersink its four holes by hand. It declares its
milling beams and cuts, so it renders with `milling_deflection` enforced. The
hacksaw and the 3/16 in-body 82° countersink are not owned
(`shop-equipment.toml`, `present = false`).

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

A part listed in `cad/scripts/_cam_programs.py:CAM_STEMS` also has
`<stem>/cam.py`, a CAM recipe that turns the plan's machining setups into
G-code with FreeCAD's CAM workbench, run headless. `uv run --frozen python -m
doit cam:<stem>` (opt-in; not in `build` or `release`) needs FreeCAD 1.1 or
later: `$HARMONIC_FREECAD` names `freecadcmd`, otherwise the newest
`FreeCAD <version>` install under the Windows program directories is used, and
the task fails when there is none (or when it is older than 1.1). It writes
one `.nc` per recipe program, `cycle_times.json` and `manifest.json` (input,
post and output SHA-256s, FreeCAD version, the post file FreeCAD loaded) to
`cad/out/nc/<stem>/`, logs each program's cutting, air-at-feed and rapid
minutes, and leaves freecadcmd's console output in `freecadcmd.log` there.

A recipe has four parts:

- `PROGRAMS`: the file names, each listing its operations. Each program is one
  tool, because GRBL has no tool changer, and one FreeCAD Job per spindle
  speed. The PM-30MV's speed is set by hand on the knob, so a program whose
  operations are grouped runs each group after an operator comment and `M0`
  (the base bar's BB04: ends at 2250 rpm, then slots at 1250); `_gcode`
  checks each stop is retracted above the stock and commented, and each
  section's S word.
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
  below the stock top and no feed move above it. Each program's `air_feed`
  expectation also names the stock top its cycle time is split at.

CAM produced toolpaths that looked valid while the base-bar programs were
being written, yet these checks caught a spot depth measured from the
counterbore floor, a feed height below the stock top, a slot cut from the
outside and an oversized radial step. A failed check removes every output.
Fix the recipe, not the expectation.
The base-bar recipe refuses to post when the manifest's rail stations are REF
(no `station` requirement): such holes are transferred from each bar's own
rail, and posting at the nominal would drill off the real rail.

Milling speed rules (owner rulings 2026-11-16): "replace fusion with oss
cam" moved the task from Autodesk Fusion Personal, which posted rapids at
feed, to FreeCAD, whose posts use real G0 above the stock. The PM-30MV
conversion has ball screws, so faces zigzag (climb on alternate passes).
"Cut edge 1 in +X and edge 2 in −X": both edges stay conventional (the
dechatter edge settings were measured conventional) and BB01 alternates
between them, so no pass returns through the air. Ends, slots and holes keep
the plan's strategy. Edge and end passes plunge beside the stock, so they
plunge at their cutting feed; only the slot corners plunge into metal at the
plan's slow feed. With the rapid rate assumed at 100 in/min
(`_gcode.RAPID_MM_MIN`, until the controller's `$110`/`$111` are read), one
bar's programs fell from about 207 to 86 minutes.

FreeCAD's `grbl` post expands G81/G82/G83 into G0/G1 but not G73, so the
drilled holes peck with full retracts (G83), one drill diameter each, as the
traveler says; FreeCAD measures each peck from the R plane, which is why the
R plane sits just above the stock.

For the base bar, S3 after the side-2 face (S3c) puts X0 at ZERO END and Y0
at ZERO EDGE, against the back jaw. The bar lies at −Y, so drawing Y becomes
−Y, and Z0 is the top face. Bar 1's C'BORE SIDE and bar 2's RAIL SIDE are the
model's Z0 face, so one set of S3 programs serves both hands; `_bar1` programs
are bar 1 only. S2 is different: X0 is the blank's left end, Y0 the finished
front edge with the bar at +Y, and Z0 the blank's top. Posted NC is not
machining approval: prove each program in air and check the setup against the
traveler first.
