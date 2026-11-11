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
0.9 examples; each header names its sources. Each plan's `adapter` is a prechips
adapter written against that part's manifest contents, so a drawing change that
alters the manifest's requirements needs a prechips adapter release before the
traveler passes again.

## Shop records

`shop.toml` is the prechips shop file: machines, gauges, limits, tools and
cutting settings, in prechips' schema and units. It holds only records an HA
plan or an HA spec/test reads (no example tooling from other projects); a fact
that schema can express lives here. Its records include the rocker DTI's range and
resolution (`gauges.dti`), read by `ch_rocker_arm_profile_check.py`; the
PM-30MV X DRO scale (`gauges.mill-x-dro`), whose resolution the paper-drive
tests read; and the rocker profile cutter (`tools.rocker-profile-cutter`) with
its HSS cutting setting (`settings.rocker-profile-hss-low-carbon-steel`).

Facts prechips has no field for, but which CAD specs and tests read, live in
[`cad/config/shop-equipment.toml`](../config/shop-equipment.toml):

- gauges: the DTI's kind and make, the pin-gauge note, the Mitutoyo gauge-block
  set (read by `ch_rocker_arm_tl_oblique_jig_assembly_spec.py`), the arm-outline
  template and the Vermont class X 2558-minus pin;
- the PM-30MV DRO's make and cited accuracy (read by the paper-drive tests);
- the LMS 6784 end-mill set and its sizes, the 8-32 plug hand tap's flute
  length, and the shop-made rocker trammel's R800/R816 lengths;
- the PM 6-in vise's make, SKU, source and opening;
- the base-bar plan's vise workholding (1-3/8 in parallels, HHIP 3901-0079
  screw jack), with the ownership status Pedro's 2026-11-05 hand sheet gives
  (PR #2218): neither owned on that date;
- three `[[stock]]` rows: OnlineMetals 4807 strap and 1173 bar, and McMaster
  8663K55 acetal.

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
`<stem>/diagrams/`). Under prechips 0.9 the base bar and end bracket pass both
on the v48 manifests.

The feed lever's plan (`ch_rocker_arm_tl_oblique_feed_lever/plan.toml`) is held
in the repository but not enrolled. prechips refuses it on `tool_sizing`: the
plan's 11/32 drill (8.73125 mm) is below the drawing's hole band
(8.7376–8.8392 mm). That is a finding for the owner (a different drill, or a
drawing change), not a check to opt out of; enroll the part once its plan passes.

```text
uv run doit prechips:<stem>
uv run python cad/scripts/prechips_traveler.py <stem>
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
under `cad/out/travelers/<stem>/`, resolves and prints the latest prechips
version, then runs
`uv tool run --from prechips==<version> prechips traveler cad/process/<stem>/plan.toml`
with `--profile pro` and then `--profile hobby`. Exit 0 from both is the only
pass. Exit 1 means `uv` or PyPI was unavailable and nothing was rendered. A
nonzero prechips exit from either is returned and removes both files; exit 2 is
a refusal, either bad input or a failed enforced check (`stock_fit`,
`turning_deflection`, `cutting_speeds`, `tool_sizing`, `indexing`,
`gauge_capability`, `lathe_holding`, `machine_capacity`, or `hobby`'s missing
setup picture). A missing plan fails only that part's task. A refusal is a
finding about the plan or shop data; correct the source, not the check.

A traveler that passes is not permission to machine: shop measurements,
physical setup verification and machining approval are still required. See the
[feature/traveler contract](../docs/pipeline/features-travelers.md).
