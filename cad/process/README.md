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
  and 2026-11-08, #2315): a 4130-N `[[stock]]` row of form `round_tube`
  (OnlineMetals 7322, one 24 in cut), read by `test_sm_gooseneck_drawing.py`
  against the bent tube's developed length plus its ~2 in tail.

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
`prechips:<stem>` task: the oblique-trammel base bar, end bracket, feed
lever and riser. `build` and `release` do not run it, and releases carry no travelers while
prechips stabilises. Each run renders two travelers from the same plan:
`traveler.html` (`pro`, concise) and `traveler-hobby.html` (`hobby`, with the
setup pictures in `<stem>/diagrams/`). Under prechips 0.10.1 the base bar and
end bracket pass both on the v49 manifests. The base-bar and feed-lever plans
need 0.10.1: they read its adapter bindings `cad.vise_centred_overhang_mm`
(centred overhang from the CAD length and `vise_jaw_width_mm`) and
`cad.overhang_mm` (from the lever's one `overhang_in`), and the base-bar adapter
refuses a Setup 4 jack centre off the bar or inside a rail-hole, counterbore or
slot outline. The feed-lever plan needs 0.11.0, which binds the lever's
grip-corner fillet (`cad.corner_radius_in` and its limits). All three plans
carry 0.11.0's `milling_deflection` data (a `beam` per non-lathe setup or
operation, `milling_cuts` per spindle operation) and pass that check enforced;
the end-bracket plan's tap flags and the dropped feed-lever grip-end setup
need the 0.11.0 jig pictures, so they pass under `@latest` from 0.11.0. The riser plan needs 0.11.0 too
(its `harmonic_riser` adapter).

The riser plan (TL-24) needs prechips 0.11.0, which adds its `harmonic_riser`
adapter and the `milling_deflection` check. It passes both profiles, with every
check enforced, on the v49 manifest. Setups 1–4 make the bar
and drill the stop-pin holes P1/P2 at their printed stations. Setup 1 calipers
the bar: Setup 2 faces it only when it is over the .25 thickness limit, from three
straps then four, because a single strap span along the bar's length bends the
thin bar ~.23 mm under the cutter. The other seven
holes print X/Y LOC REF: Setup 5 runs after TL-00 step 11C has spotted them
from the carrier and drills each at its own mark, so its table gives the REF
X/Y only to find the marks. The 12 mm HUB drill and the 82° countersink are
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
  5 pictures bar 1 turned over (C'BORE SIDE down on the table, rail up) and a
  bar 2 section. The edge setup uses three 1-2-3 blocks, one at mid-length,
  and two end straps. Setup 3 faces both sides, squares both ends and mills
  both slots in one vise clamping (2026-11-14 traveler review: the former
  table-strapped end squaring left the ends on a 221 mm cantilever, 0.057 mm
  under `milling_deflection`, refused); the slots take .05 depth steps on the
  jaws' cantilever. Vise setups print the bar's stand-out above the jaws, keep
  the 1-3/8 in parallels and two screw jacks (touch only; Setup 4 gives their
  DRO positions and its drill and counterbore operations split by end, each
  over its jack). Facing runs full length at 850 rpm, 6.8 in/min (owner ruling
  2026-11-11, `settings.basebar-face-6061-t6511`), one pass per side. Setups
  2–3 run in the low belt range and Setup 4 in the high range, so both bars
  take one belt change. The rail
  stations are REF only, never drill targets (spec; owner R4 ruling, restated
  2026-11-11): all eight hole centres are picked up on the bar's own rail,
  trimmed flush with the angle grinder per TL-00 steps 1D–1G
  (`tools.rail-trim-grinder`, not owned yet) and clamped on the rail face,
  with the edge finder on the X DRO (both sides of each counterbore, centre =
  midpoint; owner ruling 2026-11-13, #2546), the rail comes off, and each
  hole is drilled at its recorded X. The 1/2 in end mill alone cuts both
  slots, tracing a cutter-centre rectangle printed per slot, and `tool_sizing`
  checks it against the slot width band less the path offset (the 3/8 in slot
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

The pivot block (`ch_rocker_arm_tl_oblique_pivot_block`, TL-22) and feed block
(`ch_rocker_arm_tl_oblique_feed_block`, TL-32) plans are written fresh against
their v49 manifests (no hand traveler): each saws its own blank from the
OnlineMetals 1187 1 x 3 in bar (`cad/config/shop-equipment.toml` `[[stock]]`),
faces SEAT and TOP, mills the 1.64 length from the 3 in width on edge (#2083),
faces the sawn ends on end, then cuts every top hole in one hold: the 4X .180
holes and .31 counterbores to the .570 floor, and the pivot seat (F tap drill,
then the LMS 6784 3/8 end mill plunged to the flat .359 floor, .375–.379 under
DRILLED HOLES, owner ruling 2026-11-13; then the 5/16-18 tap through). TL-32
adds the lug notch, with LUG END out past the jaw side, a spacer at the other
jaw end and the owner's 1 in-flute 1/2 in end mill, and the Ø.375 leadscrew
clearance, piloted and plunged with the same 3/8 end mill with the block
standing on SPINDLE END, after an arrival check of both KP08 axis heights
(#2184); its four #4-40 nut taps stay with the TL-00 transfer. Their adapters
(`harmonic_pivot_block`, `harmonic_feed_block`) ship in prechips 0.11.0. No
boring head is needed; the F drill and 5/16-18 plug tap share the carrier's
records (`jig-drill-f`, `jig-tap-5-16-18-plug`).

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
`turning_deflection`, `milling_deflection`, `cutting_speeds`, `tool_sizing`,
`indexing`, `gauge_capability`, `lathe_holding`, `vise_holding`,
`machine_capacity`, or
`hobby`'s missing setup picture). A missing plan fails only that part's task.
A refusal is a finding about the plan or shop data; correct the source, not
the check.

A traveler that passes is not permission to machine: shop measurements,
physical setup verification and machining approval are still required. See the
[feature/traveler contract](../docs/pipeline/features-travelers.md).
