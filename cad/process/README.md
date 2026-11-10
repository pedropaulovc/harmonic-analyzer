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
dependency, declared as `prechips>=0.8,<10`. The lock resolves the latest
release; bump it with `uv lock --upgrade-package prechips`. It reads the plan,
the shop file and the part's exported `features.toml`, and writes one standalone
HTML traveler. It needs no FreeCAD or geometry kernel and checks no hashes. HA
does not rewrite, bind or stamp the plan; prechips reads the tracked file
directly.

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

Only `ch_rocker_arm_tl_oblique_base_bar/plan.toml` exists today. It is ported
from the prechips `examples/base-bar.toml`, and its header names its sources.
Under prechips 0.8.0 it refuses: the `harmonic_base_bar` adapter cannot read
the v48 manifest (`rail_hole_1.station: missing drawing requirement`). The fix
is upstream in prechips 0.9. The end bracket and feed lever still need plans.

## Shop records

`shop.toml` is the prechips shop file: machines, workholding, gauges, limits,
tools and cutting settings, in prechips' schema and units. Any fact that schema
can express lives here. Its records include the rocker DTI's range and
resolution (`gauges.dti`), read by `ch_rocker_arm_profile_check.py`, and the
rocker profile cutter (`tools.rocker-profile-cutter`) with its HSS cutting
setting (`settings.rocker-profile-hss-low-carbon-steel`).

Facts prechips has no field for, but which CAD specs and tests read, live in
[`cad/config/shop-equipment.toml`](../config/shop-equipment.toml):

- gauges: the DTI's kind and make, the pin-gauge note, the Mitutoyo gauge-block
  set (read by `ch_rocker_arm_tl_oblique_jig_assembly_spec.py`), the arm-outline
  template and the Vermont class X 2558-minus pin;
- the PM-30MV DRO's make, scale resolution and cited accuracy (read by the
  paper-drive tests);
- the LMS 6784 end-mill set and its sizes, the 8-32 plug hand tap's flute
  length, and the shop-made rocker trammel's R800/R816 lengths;
- the PM 6-in vise's make, SKU, source and opening;
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

## Travelers

`cad/scripts/_process_plans.py:TRAVELER_STEMS` lists the parts with a
`prechips:<stem>` task: the oblique-trammel base bar, end bracket and feed
lever. `build` and `release` require every one.

```text
uv run --frozen python -m doit prechips:<stem>
uv run --frozen python cad/scripts/prechips_traveler.py <stem>
```

The doit task first runs its `package:features:<stem>` leaf (SolidWorks, via the
supervised farm). The wrapper alone needs an existing scoped bundle. It removes
any previous `cad/out/travelers/<stem>/traveler.html`, then runs
`python -m prechips traveler cad/process/<stem>/plan.toml --profile pro` and
returns its exit code. Exit 0 is the only pass. Exit 2 is a refusal, either bad
input or a failed enforced check (`stock_fit`, `turning_deflection`,
`cutting_speeds`, `tool_sizing`, `indexing`, `gauge_capability`,
`lathe_holding`, `machine_capacity`), and nothing is written. A missing plan
fails only that part's task. A refusal is a finding about the plan or shop
data; correct the source, not the check.

Releases copy each `traveler.html` to `travelers/<stem>/` in the bundle and list
them in the notes. A traveler that passes is not permission to machine: shop
measurements, physical setup verification and machining approval are still
required. See the [feature/traveler contract](../docs/pipeline/features-travelers.md).
