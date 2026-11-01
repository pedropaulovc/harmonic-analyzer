# Subsystem identities

Current part and assembly identities are frozen in [`cad/config/parts/`](../config/parts/) and [`cad/config/assemblies/`](../config/assemblies/). Those registry files own the Number and canonical stem. Build scripts own geometry. [`cad/config/current-identity-map.json`](../config/current-identity-map.json) records the 2026-10-19 cutover to two-digit Numbers and parent-scoped vendor identities, the 2026-10-20 consolidation of repeated supplier SKUs into shared `sh-vn-*` identities, and later dated allocations: `parts_and_assemblies` supplies the active web projection, while `retired_identities` preserves full prior/current identity pairs marked `retired` for historical lookup and permanent Number reservations, not current CAD or API aliases. [`cad/config/identity-migration-map.json`](../config/identity-migration-map.json) keeps the released v39 lookup used by the category cutover at `bfde892a5`. This guide explains all three cutovers and later additions; it does not replace either source of truth.

## Naming and numbering

Use `<prefix>-<descriptive-name>` for native model and exported asset basenames, and `<prefix>_<descriptive_name>` for Python module and doit task stems. Assembly builders and drawing artefacts retain their `_assembly` or `-assembly` suffix. For example, `dt-drive-train.SLDASM` is built by `build_dt_drive_train_assembly.py`; its drawing artefact stem is `dt-drive-train-assembly`.

Drawing Numbers use `MHA-<CATEGORY>-<NN>`, with two-digit sequences. `00` is the category's assembly drawing; fabricated parts start at `01`. HA, CH, DT, FR, MG, MS, PD, PN and SM have assemblies. SH contains fabricated parts and shared vendor parts; it has no assembly. Numbers are stored in the registries, not recalculated when the graph changes. Configuration variants retain their existing qualifiers on the family Number, such as `MHA-DT-03-T006` for a cone-gear configuration: `T006` is a tooth count, not an identity sequence, so it keeps its three digits. Installed channel spring stretch variants retain the unqualified base Number. Named member configurations of a shared vendor part (`InnerLink`, `LeverWire`, `TNut`) are selections within one Number, not qualifiers on it.

Vendor parts are purchased finished parts. Supplier, SKU and commercial-process evidence decides that a part is a vendor part. A vendor part that one assembly uses directly belongs to that assembly. Its stem is the parent assembly's prefix, then `vn`, then the descriptive name, such as `dt-vn-cone-lock-knob`; a name that already began with the parent prefix drops the repeat, so the measuring stick's stop-plate screw is `ms-vn-stop-plate-screw`. Its Number puts `VN` after the parent's category and counts from `50` within that parent: `dt-vn-cone-lock-knob` is `MHA-DT-VN-51`. Containment through a sub-assembly or the top assembly is not direct use.

SH means Shared: one native model per supplier-qualified SKU (supplier plus SKU). A SKU qualifies as Shared when more than one assembly uses it directly, or when its installed members take more than one modelled form, even inside one assembly: the chain's inner and outer links are one SKU used by `pd-paper-drive` alone, and the clamping kit's stud, T-nut and flange nut are one SKU used by the oblique jig alone, and both are Shared. A shared vendor identity is stem `sh-vn-<descriptive-name>`, Number `MHA-SH-VN-<NN>` from `50`, one registry row, one native model and one drawing package. Every consuming assembly references that identity; a parent-scoped copy of a shared SKU is never created, and no compatibility alias or module stands in for a retired parent-scoped identity. A SKU with one installed form used by one assembly stays parent-scoped (`pd-vn-chain-connecting-link`, 6261K108, is the chain's one-form, one-consumer companion). Members of one SKU that differ in form are explicit named configurations of the one shared model; a consumer selects its member configuration explicitly and never relies on the default. Members that share one form use the `Default` configuration. The registry `quantity` of a shared vendor part counts installed member occurrences across the machine, and `configuration_quantities` splits that count per member; neither counts purchase units such as chains, coils or kits, which the drawing package and the supplier evidence disclose separately. Members share one purchase Number; their BOM rows differ by Description. A shared vendor part used only by shop fixtures carries `usage_scope: tooling`, never enters a machine assembly or BOM and is excluded from the machine part counts. See [Shared vendor families](#shared-vendor-families).

Shared physical dimensions live in pure-data `_mcmaster_<sku>.py` modules and in the shared part's own `sh_vn_<name>_spec.py` (or per-member `sh_vn_<name>_<member>_spec.py`) modules, not in a helper named after one consuming parent.

Shop fixtures, the shop-made tooling that holds or gauges one part while it is machined, carry their parent part's Number plus `-TL-<NN>`, sequenced per parent from `01`: `MHA-CH-06-TL-20` is the rocker arm's oblique base bar. The stem is the parent stem plus `-tl-<name>`, such as `ch-rocker-arm-tl-oblique-base-bar`. Fixture parts never enter a machine assembly or BOM, and the table's part counts exclude them. A fixture kit may have its own TL-numbered assembly, such as `ch-rocker-arm-tl-oblique-jig` (`MHA-CH-06-TL-00`, using the `00` assembly convention); it references only its fixture parts and never enters a machine assembly or BOM. Every registered fixture part must belong to a registered assembly, which for a fixture is its kit's TL assembly: the coverage contract (`test_part_coverage.py`) no longer exempts tooling from orphan detection, it only exempts tooling from the machine tree. Tooling that no registered assembly references is retired, not kept as a standalone model; the only current fixture kit is the oblique trammel jig, whose 37 logical families use the 35 current tooling part identities below, including three configurations of shared SH-VN-57. The 18 standalone rocker-arm, pivot-bracket and cone-pivot-post fixtures retired on 2026-10-21 (MHA-CH-06-TL-04, TL-05 and TL-10 through TL-19; MHA-CH-08-TL-01 and TL-02; MHA-DT-05-TL-01 through TL-04) keep their rows below and their Numbers are never reissued; where a shop route still describes one, its geometry lives in `cad/process/shop/inventory.toml` without a CAD owner. Bought finished fixture hardware, such as dowels, screws and magnetic bases, is not modelled, except the oblique trammel jig's. Those bought parts are modelled as purchased parts (`process: purchased`) so the jig assembly can run native interference against them. Their direct parent assembly is the jig, `ch-rocker-arm-tl-oblique-jig` (`MHA-CH-06-TL-00`), but apart from shared supplier SKUs their stems and Numbers belong to the namespace of the fixture's parent part, the rocker arm `ch-rocker-arm` (`MHA-CH-06`): the stem is that part's stem plus `-tl-vn-<name>`, and the Number is its Number plus `-TL-VN-<NN>`, counted from `50`. `ch-rocker-arm-tl-vn-oblique-rail` is `MHA-CH-06-TL-VN-50`, and the set runs to `MHA-CH-06-TL-VN-76` (VN-58 through VN-60 and VN-72 retired, never reissued).

The 2026-10-21 standalone-tooling retirement removes CAD ownership, while retaining analytic shop-process checks for the held reference route; those checks do not qualify a physical fixture or machining route. `test_process_shop.py` checks the inline rocker risers, shim stacks, filing stand and hub filing kit against `cad/process/ch_rocker_arm/plan.toml` and the current rocker geometry, retaining the former acceptance bands. The plan remains unenrolled, and its S5/S7 physical outline-template dependency must be requalified before machining; an inventory collision envelope is not replacement tooling CAD. Their historical source is revision `fcfc947c4`, under `cad/scripts/ch_rocker_arm_tl_{riser_block,strap_shim_stack,filing_stand,filing_button,filing_stud}_spec.py` and the corresponding drawing/tests; those are provenance references, not current imports.

Surviving native builders, drawings and specs also cite retired implementations as examples: the outline-template reference sketches and slot marks, the trammel-pivot-plate coordinate mapper and dimension text, `_trammel_block_drawing` edge selector, the trammel-pivot-point angle placement, the filing-stud single-limit setter, the filing-button center-mark audit, the trammel-setting-bar angle orientation, and the cone-post bond-cradle mapper/captions and soft-jaw hole callout. Read each such reference as `fcfc947c4:cad/scripts/<cited module>.py`, not as a live module or dependency. Keeping these historical example comments does not require re-keying every native recipe.

TL-VN-58 to TL-VN-60 are reserved; their Precision Matthews clamping-kit members are now configurations of the shared tooling-only `sh-vn-clamping-kit-hardware` (MHA-SH-VN-57).

Components of a built-up part are the detail parts a finished part may be made from when its own drawing notes permit it (`BUILT_UP_PERMISSION_NOTE` in its notes module). They are ordinary machine parts: each takes the next free Number in its category and its own stem, such as `ch-rocker-hub` (MHA-CH-12) and `ch-rocker-strap` (MHA-CH-13) for the rocker arm MHA-CH-06, and the table's part counts include them. The finished part stays the assembly's part, so a component never enters an assembly or BOM. Its registry row instead names its parent's stem in `component_of`, and the coverage contract (`test_part_coverage.py`) counts it reachable through that parent and refuses a `component_of` parent whose notes do not permit the built-up route. A component's drawing gives it as supplied to the joint; sizes finished after joining print on the parent's drawing only.

| Prefix | Category | Fabricated parts | Vendor parts |
|---|---|---:|---:|
| `ha` / `HA` | Harmonic analyzer | 0 | 0 |
| `ch` / `CH` | Channel | 13 | 7 |
| `dt` / `DT` | Drive train | 35 | 15 |
| `fr` / `FR` | Frame | 5 | 4 |
| `mg` / `MG` | Magnifier | 10 | 4 |
| `pd` / `PD` | Paper drive | 23 | 13 |
| `pn` / `PN` | Pen | 5 | 7 |
| `ms` / `MS` | Measuring stick | 3 | 1 |
| `sm` / `SM` | Summing | 4 | 6 |
| `sh` / `SH` | Shared parts | 2 | 7 (+1 tooling-only kit family) |

The vendor column counts machine vendor families. The 2026-10-20 shared-vendor consolidation moved nineteen parent-scoped vendor identities into eight shared ones: CH lost 1 (8 to 7), DT lost 4 (19 to 15), FR lost 1 (5 to 4), MG lost 3 (7 to 4), PD lost 5 (18 to 13), PN lost 1 (8 to 7) and MS lost 1 (2 to 1); SM is unchanged. SH gained seven machine vendor families (MHA-SH-VN-50 to MHA-SH-VN-56) plus one tooling-only family, `sh-vn-clamping-kit-hardware` (MHA-SH-VN-57, `usage_scope: tooling`), which replaced three oblique-jig fixture identities and is listed separately because fixture hardware is excluded from machine counts. Count it neither as a machine vendor family nor twice.

SH contains fabricated parts used directly by several assemblies, currently the front and back column clamps, `sh-column-clamp-front` (MHA-SH-01) and `sh-column-clamp-back` (MHA-SH-02), and the shared vendor parts listed under [Shared vendor families](#shared-vendor-families). Each keeps one shared identity. The wheel axle nut, `mg-vn-wheel-axle-nut`, is a vendor part by commercial-process evidence. HA holds the top assembly only: its two former parts, the measuring stick and its stop, moved into the MS category on 2026-10-09 when the stop was re-derived as a block, a plate and stock screws inside their own `ms-measuring-stick` sub-assembly.

Purchased ANSI #25 inner and outer chain links (configurations of `sh-vn-chain-link`), the connecting link `pd-vn-chain-connecting-link` and finished ISO 2338 m6 crank
hub dowel stock are vendor parts, including cut-to-length modifications. Pins machined
from raw drill rod remain owned by their subsystem.

Doit selection uses the underscore stem:

```powershell
uv run python -m doit part:dt_cone_gear
uv run python -m doit part:dt_vn_cone_lock_knob
uv run python -m doit part:sh_vn_chain_link
uv run python -m doit assembly:pd_paper_drive
uv run python -m doit drawing:dt_drive_train_assembly
```
Drawing registry lookups use the underscore task name, for example
`DRAWINGS_BY_NAME["dt_crankshaft"]`. The dashed `artifact_stem`
(`dt-crankshaft`) names exported files; it is not a registry key or alias.


Follow [BUILDING.md](BUILDING.md) and [the supervised farm-launch contract](../../DEVELOPING.md#supervised-farm-launches) for executor and launch requirements. Geometric API names, features, sketches, dimensions, mate labels and machine-configuration concepts are unchanged by this naming policy.

Assembly saves and refreshes stamp the Number from the assembly's own YAML
contract. Each part's frozen registry row, selected by canonical `part_name`,
owns its Number; a consumer depends only on its own row.
Configuration variants retain their qualified drawing Numbers; family grouping
does not replace them.
Assembly `00` Numbers are assembly references, not part Numbers.

Assembly `allowed_free_stems` and `required_free_stems` lists use canonical
registered part stems, including vendor families coupled to moving components.
The material palette's `casting_green_parts` list uses those same canonical
part identities; the domain grouping and operational DOF counts are unchanged.
The current top-level assembly BOM path is
`cad/out/ha-harmonic-analyzer-bom.csv`; older BOM paths in dated evidence are
historical provenance, not current output aliases.

Drawing callouts retain complete category-qualified Numbers and process
information; do not abbreviate Numbers in cross-part callouts.
Per-configuration Gear Data and linked Manufacturing or Installation Notes
retain their complete mate identifiers.

### Oblique jig plain-pivot tooling

The owner-approved 2026-10-23 simplification replaces the captured bearing
cartridges with purchased shoulder screws, spacers and selected shims; the
2026-10-30 inch ruling (issue #290) swaps the metric shoulder screw for a 3/8
extended-thread 5/16-18 one whose thread the shop cuts to length. The carrier
sits on loose spacers over the shim packs on the TL-20 base bars (owner
rulings 2026-10-27: the .359 shoulder seat leaves the unshimmed gap open at
every loose band, and a nominal five .008 shims a support close it;
2026-10-30: face both large faces of each bar). Positive lift capture runs
carrier → shoulder-screw head → 5/16-18 thread → block → carriage, not through
a bearing or press fit. Fit the measured head-to-carrier running gap to
.002–.010 in using the purchased shim stock. The assembly owns the full
fit-up, torque, lubrication, travel and actual tool/holder clearance checks.

The plain rail-2 pivot block retains MHA-CH-06-TL-22. Rail 1 uses the new
integral feed block `ch-rocker-arm-tl-oblique-feed-block`, MHA-CH-06-TL-32,
whose spec owns the nut layout, and the shop-made brass feed nut
`ch-rocker-arm-tl-oblique-feed-nut`, MHA-CH-06-TL-27 (owner ruling
2026-11-01, replacing the bought TL-VN-55 flange nut). Drill the lug's nut
taps to print, not by transfer spotting. Both blocks use new 6061 1 × 3-1/2 in bar; TL-28 end brackets use
owned OnlineMetals 1165 1/2 × 1 in bar on edge, raising the screw axis to
Z52.4. The owned 1164 1/2 × 3/4 in stock is spare.

New purchases are TL-VN-77 shoulder screws (Huyett BLTS40-0375-1500188P,
thread shop-cut), TL-VN-78 spacers (AluminumSpacers.com AS62-18-40), TL-VN-79
shims (Huyett SHIM-0375-008 nominal; SHIM-0375-004/-020 fitting stock),
and TL-VN-80 HUB gauge pin (McMaster 23065A855-23065A4 .4000 Class Z NO-GO
plug gauge, abrasive-cut to .79, factory end up, bonded with Loctite 638);
the TL-VN-53 CL dowel is McMaster 98381A542 (1/4 x 1). These parts belong
only to the jig, never a machine assembly. New identity-map rows use their
canonical stem as source key, `old_number: null`, and the introduction date.

Retirement records below reserve TL-23, TL-25, TL-29, TL-30, TL-31,
TL-VN-52, TL-VN-55, TL-VN-63, TL-VN-70 and TL-VN-73 through TL-VN-76 permanently.
TL-VN-72 also stays retired. Owned 6200 bearings remain shop stock without
a jig identity. For a pass change, isolate the machine, support the carrier,
unscrew both shoulder screws, lift the carrier, move the carriages and refit
the same carrier on the other hole pair before repeating assembly acceptance.

The `HoldDownStud` configuration of **MHA-SH-VN-57** retains Precision Matthews
52PCCK-9/16-14mm procurement: **four 1/2-13 × 3 in STOCK studs**, not a
57.2 mm vendor SKU. Rework only each unused upper free end to **57.2 mm
finished length, ordinary .X ±0.8 mm**, and restore the cut-end chamfer
(1.0 mm maximum). Its native configuration and the shared drawing's **REWORK**
sheet describe the finished reworked stud, not a purchased-identification-only envelope.
The lower factory end, loaded lower thread interval and insertion remain
unchanged, as do all anchors, stations, slots, footprints, clamp spans,
T-nut/flange-nut positions and both full pass sweeps.

Accept the actual installed stud/nut stack only with **G ≥3 mm** to the moving
block throughout **both complete hand sweeps**, and at least **one
complete 1/2-13 pitch (25.4/13 mm)** beyond every fully seated flange nut,
while retaining that nut's **entire actual complete internal thread span**.
Do not cut an engaged thread, insert a stud deeper to rescue the cut, add a
hold-down washer or force the assembly; reject an incompatible setup.
Measure the actual complete-thread setback separately: the cut-end chamfer
limit alone does not bound incomplete threads or establish nut engagement.
The complete installed authority is **TL-00, HD1–HD4, sheet 9**. The stud's
single REWORK sheet cites that authority rather than duplicating it. HD1/HD2
retain actual B/D/H/N/W/U intervals and finished L limits; HD3 is the stud
rework and realignment; HD4 repeats the installed checks after final
clamping. Missing readings reject the setup.

These are actual fit-up requirements, not invented PM kit tolerance bands.
The 22 mm insertion stack (assumed 14 mm throat + 8 mm foot), 28 mm nominal
carriage height and 13 mm estimated nut height remain unverified kit inputs.
TECO 41605's approximately 17.5 mm nut is comparison data, not a PM maximum.
Explicit measured ranges and their uncertainty are needed to accept the
installed setup; nominal dimensions alone cannot mark it VERIFIED. Neither
the free-end trim nor these geometric checks certify preload, mechanical
strength, bump-force capacity or deflection.


## Drawing package layout

Wrap complete category-qualified Numbers and sheet references as indivisible
units; restore ordinary spaces in printed text. A continuation must not look
like a new numbered assembly step.

Compact part-note fields retain complete Numbers, fit limits, setup conditions
and operation counts when instructions are rewrapped or shortened. Include the
full mating Number in a dimension callout's clearance envelope; reposition
the callout within its existing field when wrapping alone is insufficient.

The package recipes own sheet counts and locations:

- [`draw_dt_drive_train_assembly.py`](../scripts/draw_dt_drive_train_assembly.py)
  retains sheets 1–10 and appends sheet 11 for assembly continuations. Its
  local BOM uses a 48 mm Number column and a 118 mm description column in two
  190 mm pieces. The reference isometric and scale metadata occupy separate
  fields below the first piece.
- [`draw_pd_paper_drive_assembly.py`](../scripts/draw_pd_paper_drive_assembly.py)
  retains sheets 1–7 and appends sheet 8 for the complete BOM. Its 48 mm Number
  column and 118 mm description column form two 190 mm pieces, split using
  rebuilt native row heights. Every instruction sheet has a reference model
  view for title-block property links.
- [`draw_ch_channel_assembly.py`](../scripts/draw_ch_channel_assembly.py)
  retains its four sheets and complete parent-scoped vendor Numbers. On sheet 2,
  the exploded-view caption follows the rebuilt native BOM bottom, including
  wrapped rows, rather than an estimated row pitch. Its actual native note
  extent must leave at least 4 mm below the table and remain clear of the border
  and title block, including after the final rebuild.
- [`ha_harmonic_analyzer_assembly_sheet.py`](../scripts/ha_harmonic_analyzer_assembly_sheet.py)
  identifies MHA-MG-00 as the clamp hardware supplier and MHA-PN-00 as the
  pen-wire supplier, not MG's same-stock lever wire. Their subassembly BOMs
  remain the parts/quantity authority; HA adds no duplicate rows or balloons.

Earlier selected-image page indices remain unchanged. Native note extents,
table growth and view outlines still determine containment; offline wrapping
budgets do not replace the native audit or complete-package visual review.



## Historical evidence

Dated reports, released packages, raw logs, source quotations and user-authored bench entries retain the identifiers, snapshot URLs and checksums they recorded. Their identifiers come from one of four epochs:

- v39 release identifiers: unprefixed stems with `MHA-NNN` part and `MHA-ANN` assembly Numbers, recorded in `identity-migration-map.json`.
- Category identifiers, current from `bfde892a5` (2026-10-02) until 2026-10-19: prefixed stems, three-digit `MHA-<CATEGORY>-<NNN>` Numbers such as `MHA-DT-005` and `MHA-DT-005-TL-01`, assembly Numbers ending `000`, and one machine-wide vendor category with `vn-` stems and `MHA-VN-<NNN>` Numbers.
- Two-digit parent-scoped identifiers, current from 2026-10-19 until 2026-10-20: as described above, but with every vendor family parent-scoped, so one repeated SKU had one `<parent>-vn-` identity per consuming assembly (`dt-vn-fillister-screw` MHA-DT-VN-50, `fr-vn-fillister-screw` MHA-FR-VN-50, `pd-vn-fillister-screw` MHA-PD-VN-52) and the chain, wire and clamping-kit members were separate identities. Only the nineteen identities in the [shared vendor transition table](#shared-vendor-families) belong to this epoch; every other two-digit identity is unchanged and current.
- Current identifiers, from 2026-10-20, as described above, with repeated SKUs shared under SH.

Read older identifiers through the table below when locating a current model. Current instructions, registry references, commands and asset links use current identities. A migration notice on a historical document does not change the evidence or certify it against the current model.

## Identity migration table

The table translates every v39 and category identity to its current identity or reserved Number, including retired families, shop fixtures and assemblies; a reserved Number does not make a retired family current. The v39 and category columns are lookup keys for historical evidence, not supported aliases for current commands or files. The 18 standalone tooling families retired on 2026-10-21 live only in the current map's `retired_identities`, outside the active `parts_and_assemblies` and web projection. Historical release comparisons deliberately consume both collections, rejecting undeclared duplicate stems or Numbers across their union; current projection validation rejects active/reserved collisions and reappearing retired registries. A family created after the v39 release has no v39 stem or Number (—). A category vendor family that several assemblies used directly now has one row, resolving to the shared `sh-vn-` identity; its earlier parent-scoped two-digit identities are in the [shared vendor transition table](#shared-vendor-families). Where several category families converged on one shared identity (the chain links, the wire forms, the three 90280A108 screws, the kit members), the current cells name the member configuration. Every other category Number maps to the same sequence written with two digits: MHA-DT-005 is now MHA-DT-05, MHA-DT-000 is MHA-DT-00 and MHA-CH-006-TL-000 is MHA-CH-06-TL-00.

Retired Numbers keep their rows here for historical lookup and are never reissued; a retired machine or fixture Number stays reserved in its two-digit form. MHA-PD-21 `pd-latch-hook-bracket` (category MHA-PD-021, v39 MHA-170) and the category vendor family `vn-latch-hook-rivet` (MHA-VN-045, v39 MHA-175) have no registry, builder or drawing: the one-piece formed spring-steel latch hook MHA-PD-14 `pd-latch-hook` replaces the bracket, its rivets and the old riveted strip, and screws to the support bar with two MHA-SH-VN-52 `sh-vn-fillister-screw-90280a108` screws (formerly MHA-PD-VN-59). The old 1/2-inch `vn-knife-hanger-washer` (MHA-VN-026, v39 MHA-131) remains retired. The #10 18-8 washer that replaced it took the new category Number MHA-VN-060 under the same functional stem and is now `sm-vn-knife-hanger-washer`, MHA-SM-VN-54; it did not revive VN-026. `sm-vn-knife-hanger-stud` (MHA-SM-VN-52, category MHA-VN-024) keeps the drawing title **Bolt**; it is made by cutting #10-24 hex-head stock 92314A253 and is seated on the new washer on the MHA-FR-02 faced top. The former #6 socket-head/counterbore-floor route is obsolete. The category vendor family `vn-transgear-collar-cross-pin` (MHA-VN-037, v39 MHA-154) is retired: the true D-bore of the MHA-PD-22 drive collar carries the torque on the knob shaft's D-flat, so no front cross-pin remains. MHA-PN-03 `pn-pen-marker` (category MHA-PN-003, v39 MHA-050) is retired: the pen is a purchased Sharpie Fine Point, `pn-vn-pen-marker` MHA-PN-VN-56, not a turned brass barrel. Retired category vendor Numbers (MHA-VN-008, MHA-VN-026, MHA-VN-037 and MHA-VN-045) have no current form.

The measuring-stick cutover is recorded here and in the current registries, not in the sealed release identity map: `ha-measuring-stick` MHA-HA-001 became `ms-stick` MHA-MS-001 and `ha-measuring-stick-stop` MHA-HA-002 became `ms-stop-block` MHA-MS-002 on 2026-10-09, so the `measuring-stick` rows below carry their MS category Numbers, and the HA part Numbers (MHA-HA-01 and MHA-HA-02 in two-digit form) are never reissued. `cad/config/identity-migration-map.json` retains its released v39 bytes for provenance and release pairing; the v39 web model keeps its release-pinned identities until the next model release.

| Kind | v39 stem | v39 Number | Category stem | Category Number | Current stem | Current Number |
|---|---|---|---|---|---|---|
| part | `measuring-stick` | MHA-046 | `ms-stick` | MHA-MS-001 | `ms-stick` | MHA-MS-01 |
| part | `measuring-stick-stop` | MHA-122 | `ms-stop-block` | MHA-MS-002 | `ms-stop-block` | MHA-MS-02 |
| part | — | — | `ms-stop-plate` | MHA-MS-003 | `ms-stop-plate` | MHA-MS-03 |
| part | `amplitude-bar` | MHA-003 | `ch-amplitude-bar` | MHA-CH-001 | `ch-amplitude-bar` | MHA-CH-01 |
| part | `channel-lever` | MHA-009 | `ch-channel-lever` | MHA-CH-002 | `ch-channel-lever` | MHA-CH-02 |
| part | `connecting-rod` | MHA-017 | `ch-connecting-rod` | MHA-CH-003 | `ch-connecting-rod` | MHA-CH-03 |
| part | `fulcrum-shaft` | MHA-031 | `ch-fulcrum-shaft` | MHA-CH-004 | `ch-fulcrum-shaft` | MHA-CH-04 |
| part | `pivot-shaft` | MHA-065 | `ch-pivot-shaft` | MHA-CH-005 | `ch-pivot-shaft` | MHA-CH-05 |
| part | `rocker-arm` | MHA-071 | `ch-rocker-arm` | MHA-CH-006 | `ch-rocker-arm` | MHA-CH-06 |
| part | `fulcrum-keeper` | MHA-120 | `ch-fulcrum-keeper` | MHA-CH-007 | `ch-fulcrum-keeper` | MHA-CH-07 |
| part | `pivot-bracket` | MHA-123 | `ch-pivot-bracket` | MHA-CH-008 | `ch-pivot-bracket` | MHA-CH-08 |
| retired part | `rocker-thrust-washer` | MHA-148 | `ch-rocker-thrust-washer` | MHA-CH-009 | — | MHA-CH-09 (retired; never reissued) |
| part | — | — | `ch-rod-pivot-pin` | MHA-CH-010 | `ch-rod-pivot-pin` | MHA-CH-10 |
| part | — | — | `ch-bar-pivot-pin` | MHA-CH-011 | `ch-bar-pivot-pin` | MHA-CH-11 |
| part | — | — | `ch-anchor-jam-nut` | MHA-CH-014 | `ch-anchor-jam-nut` | MHA-CH-14 |
| part | — | — | `ch-rocker-hub` | MHA-CH-012 | `ch-rocker-hub` | MHA-CH-12 |
| part | — | — | `ch-rocker-strap` | MHA-CH-013 | `ch-rocker-strap` | MHA-CH-13 |
| part | `alignment-pinion` | MHA-002 | `dt-alignment-pinion` | MHA-DT-001 | `dt-alignment-pinion` | MHA-DT-01 |
| part | `arbor-pedestal` | MHA-004 | `dt-arbor-pedestal` | MHA-DT-002 | `dt-arbor-pedestal` | MHA-DT-02 |
| part | `cone-gear` | MHA-013 | `dt-cone-gear` | MHA-DT-003 | `dt-cone-gear` | MHA-DT-03 |
| part | `cone-gear-shaft` | MHA-014 | `dt-cone-gear-shaft` | MHA-DT-004 | `dt-cone-gear-shaft` | MHA-DT-04 |
| part | `cone-pivot-post` | MHA-016 | `dt-cone-pivot-post` | MHA-DT-005 | `dt-cone-pivot-post` | MHA-DT-05 |
| part | `crank-arm` | MHA-020 | `dt-crank-arm` | MHA-DT-006 | `dt-crank-arm` | MHA-DT-06 |
| part | `crank-drive-gear` | MHA-021 | `dt-crank-drive-gear` | MHA-DT-007 | `dt-crank-drive-gear` | MHA-DT-07 |
| part | `crank-handle` | MHA-022 | `dt-crank-handle` | MHA-DT-008 | `dt-crank-handle` | MHA-DT-08 |
| part | `crank-pin` | MHA-024 | `dt-crank-pin` | MHA-DT-009 | `dt-crank-pin` | MHA-DT-09 |
| part | `crank-pinion` | MHA-025 | `dt-crank-pinion` | MHA-DT-010 | `dt-crank-pinion` | MHA-DT-10 |
| part | `crankshaft` | MHA-026 | `dt-crankshaft` | MHA-DT-011 | `dt-crankshaft` | MHA-DT-11 |
| part | `cylinder-gear` | MHA-027 | `dt-cylinder-gear` | MHA-DT-012 | `dt-cylinder-gear` | MHA-DT-12 |
| part | `cylinder-gear-shaft` | MHA-028 | `dt-cylinder-gear-shaft` | MHA-DT-013 | `dt-cylinder-gear-shaft` | MHA-DT-13 |
| part | `pinion-bracket` | MHA-056 | `dt-pinion-bracket` | MHA-DT-014 | `dt-pinion-bracket` | MHA-DT-14 |
| part | `pinion-handle` | MHA-058 | `dt-pinion-handle` | MHA-DT-015 | `dt-pinion-handle` | MHA-DT-15 |
| part | `pinion-lever` | MHA-059 | `dt-pinion-lever` | MHA-DT-016 | `dt-pinion-lever` | MHA-DT-16 |
| part | `pinion-lift-rod` | MHA-060 | `dt-pinion-lift-rod` | MHA-DT-017 | `dt-pinion-lift-rod` | MHA-DT-17 |
| part | `pinion-pivot-block` | MHA-061 | `dt-pinion-pivot-block` | MHA-DT-018 | `dt-pinion-pivot-block` | MHA-DT-18 |
| part | `pinion-pivot-shaft` | MHA-062 | `dt-pinion-pivot-shaft` | MHA-DT-019 | `dt-pinion-pivot-shaft` | MHA-DT-19 |
| part | `cone-swing-platform` | MHA-091 | `dt-cone-swing-platform` | MHA-DT-020 | `dt-cone-swing-platform` | MHA-DT-20 |
| part | `cone-tip-block` | MHA-092 | `dt-cone-tip-block` | MHA-DT-021 | `dt-cone-tip-block` | MHA-DT-21 |
| part | `pinion-arbor` | MHA-102 | `dt-pinion-arbor` | MHA-DT-022 | `dt-pinion-arbor` | MHA-DT-22 |
| part | `pinion-cam` | MHA-104 | `dt-pinion-cam` | MHA-DT-023 | `dt-pinion-cam` | MHA-DT-23 |
| part | `pinion-spring` | MHA-114 | `dt-pinion-spring` | MHA-DT-024 | `dt-pinion-spring` | MHA-DT-24 |
| part | `pinion-cam-pin` | MHA-116 | `dt-pinion-cam-pin` | MHA-DT-025 | `dt-pinion-cam-pin` | MHA-DT-25 |
| part | `cylinder-end-disc` | MHA-121 | `dt-cylinder-end-disc` | MHA-DT-026 | `dt-cylinder-end-disc` | MHA-DT-26 |
| part | `crank-pin-ring` | MHA-128 | `dt-crank-pin-ring` | MHA-DT-027 | `dt-crank-pin-ring` | MHA-DT-27 |
| part | `crank-pin-eye` | MHA-130 | `dt-crank-pin-eye` | MHA-DT-028 | `dt-crank-pin-eye` | MHA-DT-28 |
| part | `crank-pinion-pin` | MHA-134 | `dt-crank-pinion-pin` | MHA-DT-029 | `dt-crank-pinion-pin` | MHA-DT-29 |
| part | `pinion-lever-pin` | MHA-135 | `dt-pinion-lever-pin` | MHA-DT-030 | `dt-pinion-lever-pin` | MHA-DT-30 |
| part | `crank-hub` | MHA-137 | `dt-crank-hub` | MHA-DT-031 | `dt-crank-hub` | MHA-DT-31 |
| part | `crank-hub-pin` | MHA-138 | `vn-crank-hub-pin` | MHA-VN-029 | `dt-vn-crank-hub-pin` | MHA-DT-VN-59 |
| part | `crank-handle-pivot-screw` | MHA-139 | `dt-crank-handle-pivot-screw` | MHA-DT-032 | `dt-crank-handle-pivot-screw` | MHA-DT-32 |
| part | `pinion-arbor-collar` | MHA-144 | `dt-pinion-arbor-collar` | MHA-DT-033 | `dt-pinion-arbor-collar` | MHA-DT-33 |
| part | `crank-handle-ferrule` | MHA-152 | `dt-crank-handle-ferrule` | MHA-DT-034 | `dt-crank-handle-ferrule` | MHA-DT-34 |
| part | `crank-handle-butt-cup` | MHA-153 | `dt-crank-handle-butt-cup` | MHA-DT-035 | `dt-crank-handle-butt-cup` | MHA-DT-35 |
| retired part | `crank-seat-washer` | MHA-172 | `dt-crank-seat-washer` | MHA-DT-036 | — | MHA-DT-36 (retired; never reissued) |
| part | `harmonic-base` | MHA-035 | `fr-harmonic-base` | MHA-FR-001 | `fr-harmonic-base` | MHA-FR-01 |
| part | `top-frame` | MHA-077 | `fr-top-frame` | MHA-FR-002 | `fr-top-frame` | MHA-FR-02 |
| part | `tube-frame` | MHA-083 | `fr-tube-frame` | MHA-FR-003 | `fr-tube-frame` | MHA-FR-03 |
| part | `nameplate` | MHA-086 | `fr-nameplate` | MHA-FR-004 | `fr-nameplate` | MHA-FR-04 |
| part | `rocker-arm-support` | MHA-089 | `fr-rocker-arm-support` | MHA-FR-005 | `fr-rocker-arm-support` | MHA-FR-05 |
| part | `magnifying-bracket` | MHA-041 | `mg-magnifying-bracket` | MHA-MG-001 | `mg-magnifying-bracket` | MHA-MG-01 |
| part | `magnifying-clamp` | MHA-042 | `mg-magnifying-clamp` | MHA-MG-002 | `mg-magnifying-clamp` | MHA-MG-02 |
| part | `magnifying-lever` | MHA-043 | `mg-magnifying-lever` | MHA-MG-003 | `mg-magnifying-lever` | MHA-MG-03 |
| part | `magnifying-vertical-rod` | MHA-044 | `mg-magnifying-vertical-rod` | MHA-MG-004 | `mg-magnifying-vertical-rod` | MHA-MG-04 |
| part | `magnifying-wheel` | MHA-045 | `mg-magnifying-wheel` | MHA-MG-005 | `mg-magnifying-wheel` | MHA-MG-05 |
| part | `output-fixture` | MHA-047 | `mg-output-fixture` | MHA-MG-006 | `mg-output-fixture` | MHA-MG-06 |
| part | `wheel-axle` | MHA-084 | `mg-wheel-axle` | MHA-MG-007 | `mg-wheel-axle` | MHA-MG-07 |
| part | `wheel-bar` | MHA-085 | `mg-wheel-bar` | MHA-MG-008 | `mg-wheel-bar` | MHA-MG-08 |
| retired part | `lever-wire` | MHA-115 | `mg-lever-wire` | MHA-MG-009 | — (replaced by the purchased wire, now `sh-vn-music-wire` `LeverWire`, MHA-SH-VN-56) | MHA-MG-09 (retired; never reissued) |
| part | — | — | `mg-wheel-drum` | MHA-MG-010 | `mg-wheel-drum` | MHA-MG-10 |
| part | — | — | `mg-wheel-axle-spacer` | MHA-MG-011 | `mg-wheel-axle-spacer` | MHA-MG-11 |
| part | `chain-inner-link` | MHA-006 | `vn-chain-inner-link` | MHA-VN-002 | `sh-vn-chain-link` (`InnerLink`) | MHA-SH-VN-50 |
| part | `chain-outer-link` | MHA-007 | `vn-chain-outer-link` | MHA-VN-003 | `sh-vn-chain-link` (`OuterLink`) | MHA-SH-VN-50 |
| retired part | `chain-sprocket` | MHA-008 | `pd-chain-sprocket` | MHA-PD-001 | — | MHA-PD-01 (retired; never reissued) |
| part | `platen` | MHA-066 | `pd-platen` | MHA-PD-002 | `pd-platen` | MHA-PD-02 |
| part | `platen-clip` | MHA-067 | `pd-platen-clip` | MHA-PD-003 | `pd-platen-clip` | MHA-PD-03 |
| part | `platen-paper` | MHA-068 | `pd-platen-paper` | MHA-PD-004 | `pd-platen-paper` | MHA-PD-04 |
| part | `platen-rack` | MHA-069 | `pd-platen-rack` | MHA-PD-005 | `pd-platen-rack` | MHA-PD-05 |
| part | `rack-pinion` | MHA-070 | `pd-rack-pinion` | MHA-PD-006 | `pd-rack-pinion` | MHA-PD-06 |
| part | `support-bar` | MHA-074 | `pd-support-bar` | MHA-PD-007 | `pd-support-bar` | MHA-PD-07 |
| part | `transgear-knob-shaft` | MHA-078 | `pd-transgear-knob-shaft` | MHA-PD-008 | `pd-transgear-knob-shaft` | MHA-PD-08 |
| part | `transgear-removable` | MHA-081 | `pd-transgear-removable` | MHA-PD-009 | `pd-transgear-removable` | MHA-PD-09 |
| part | `transgear-feed-pinion` | MHA-110 | `pd-transgear-feed-pinion` | MHA-PD-010 | `pd-transgear-feed-pinion` | MHA-PD-10 |
| part | `platen-guide` | MHA-111 | `pd-platen-guide` | MHA-PD-011 | `pd-platen-guide` | MHA-PD-11 |
| part | `guide-lock` | MHA-112 | `pd-guide-lock` | MHA-PD-012 | `pd-guide-lock` | MHA-PD-12 |
| part | `transgear-thumbnut` | MHA-126 | `pd-transgear-thumbnut` | MHA-PD-013 | `pd-transgear-thumbnut` | MHA-PD-13 |
| part | `latch-hook` | MHA-127 | `pd-latch-hook` | MHA-PD-014 | `pd-latch-hook` | MHA-PD-14 |
| part | `transgear-knob-thrust-ring` | MHA-156 | `pd-transgear-knob-thrust-ring` | MHA-PD-015 | `pd-transgear-knob-thrust-ring` | MHA-PD-15 |
| part | `transgear-knob-cup` | MHA-157 | `pd-transgear-knob-cup` | MHA-PD-016 | `pd-transgear-knob-cup` | MHA-PD-16 |
| part | `transgear-disc-hub` | MHA-159 | `pd-transgear-disc-hub` | MHA-PD-017 | `pd-transgear-disc-hub` | MHA-PD-17 |
| part | `transgear-arm` | MHA-164 | `pd-transgear-arm` | MHA-PD-018 | `pd-transgear-arm` | MHA-PD-18 |
| part | `transgear-arm-plate` | MHA-165 | `pd-transgear-arm-plate` | MHA-PD-019 | `pd-transgear-arm-plate` | MHA-PD-19 |
| part | `transgear-pivot-spacer` | MHA-167 | `pd-transgear-pivot-spacer` | MHA-PD-020 | `pd-transgear-pivot-spacer` | MHA-PD-20 |
| retired part | `latch-hook-bracket` | MHA-170 | `pd-latch-hook-bracket` | MHA-PD-021 | — | MHA-PD-21 (retired; never reissued) |
| part | `transgear-drive-collar` | MHA-177 | `pd-transgear-drive-collar` | MHA-PD-022 | `pd-transgear-drive-collar` | MHA-PD-22 |
| part | `transgear-pin` | MHA-179 | `pd-transgear-pin` | MHA-PD-023 | `pd-transgear-pin` | MHA-PD-23 |
| part | `transgear-rear-bushing` | MHA-180 | `pd-transgear-rear-bushing` | MHA-PD-024 | `pd-transgear-rear-bushing` | MHA-PD-24 |
| part | `transgear-front-bushing` | MHA-181 | `pd-transgear-front-bushing` | MHA-PD-025 | `pd-transgear-front-bushing` | MHA-PD-25 |
| part | `pen-frame` | MHA-048 | `pn-pen-frame` | MHA-PN-001 | `pn-pen-frame` | MHA-PN-01 |
| part | `pen-hanger` | MHA-049 | `pn-pen-hanger` | MHA-PN-002 | `pn-pen-hanger` | MHA-PN-02 |
| retired part | `pen-marker` | MHA-050 | `pn-pen-marker` | MHA-PN-003 | — (replaced by `pn-vn-pen-marker`, MHA-PN-VN-56) | MHA-PN-03 (retired; never reissued) |
| part | `pen-rod` | MHA-051 | `pn-pen-rod` | MHA-PN-004 | `pn-pen-rod` | MHA-PN-04 |
| part | `pen-v-block` | MHA-053 | `pn-pen-v-block` | MHA-PN-005 | `pn-pen-v-block` | MHA-PN-05 |
| retired part | `pen-wire` | MHA-100 | `pn-pen-wire` | MHA-PN-006 | — (replaced by the purchased wire, now `sh-vn-music-wire` `PenWire`, MHA-SH-VN-56) | MHA-PN-06 (retired; never reissued) |
| part | — | — | `pn-pen-adjust-screw` | MHA-PN-007 | `pn-pen-adjust-screw` | MHA-PN-07 |
| part | `gooseneck` | MHA-032 | `sm-gooseneck` | MHA-SM-001 | `sm-gooseneck` | MHA-SM-01 |
| part | `knife-mount` | MHA-037 | `sm-knife-mount` | MHA-SM-002 | `sm-knife-mount` | MHA-SM-02 |
| part | `summing-lever` | MHA-073 | `sm-summing-lever` | MHA-SM-003 | `sm-summing-lever` | MHA-SM-03 |
| part | — | — | `sm-gooseneck-spring-screw` | MHA-SM-004 | `sm-gooseneck-spring-screw` | MHA-SM-04 |
| part | `boss-hook` | MHA-005 | `vn-boss-hook` | MHA-VN-001 | `sm-vn-boss-hook` | MHA-SM-VN-50 |
| part | `channel-spring-installed` | MHA-011 | `vn-channel-spring-installed` | MHA-VN-004 | `ch-vn-channel-spring-installed` | MHA-CH-VN-50 |
| part | `counter-spring` | MHA-019 | `vn-counter-spring` | MHA-VN-005 | `sm-vn-counter-spring` | MHA-SM-VN-51 |
| part | `fillister-screw` | MHA-030 | `vn-fillister-screw` | MHA-VN-006 | `sh-vn-brass-fillister-screw` | MHA-SH-VN-51 |
| part | `hanger-screw` | MHA-034 | `vn-hanger-screw` | MHA-VN-007 | `pn-vn-hanger-screw` | MHA-PN-VN-50 |
| retired part | `hex-bolt` | MHA-036 | `vn-hex-bolt` | MHA-VN-008 | — | — (retired; MHA-VN-008 never reissued) |
| part | `lag-screw` | MHA-039 | `vn-lag-screw` | MHA-VN-009 | `fr-vn-lag-screw` | MHA-FR-VN-51 |
| part | `pen-set-screw` | MHA-052 | `vn-pen-set-screw` | MHA-VN-010 | `pn-vn-pen-set-screw` | MHA-PN-VN-51 |
| part | `thumb-screw` | MHA-075 | `vn-thumb-screw` | MHA-VN-011 | `sh-vn-thumb-screw` | MHA-SH-VN-55 |
| part | `spring-hook` | MHA-090 | `vn-spring-hook` | MHA-VN-012 | `ch-vn-spring-hook` | MHA-CH-VN-51 |
| part | `cone-lock-knob` | MHA-093 | `vn-cone-lock-knob` | MHA-VN-013 | `dt-vn-cone-lock-knob` | MHA-DT-VN-51 |
| part | `cone-pivot-screw` | MHA-094 | `vn-cone-pivot-screw` | MHA-VN-014 | `dt-vn-cone-pivot-screw` | MHA-DT-VN-52 |
| part | `swing-stop-screw` | MHA-095 | `vn-swing-stop-screw` | MHA-VN-015 | `sh-vn-fillister-screw-90280a108` (`Default`) | MHA-SH-VN-52 |
| part | `cone-tip-collar` | MHA-096 | `vn-cone-tip-collar` | MHA-VN-016 | `dt-vn-cone-tip-collar` | MHA-DT-VN-54 |
| part | `cone-tip-adjuster` | MHA-097 | `vn-cone-tip-adjuster` | MHA-VN-017 | `dt-vn-cone-tip-adjuster` | MHA-DT-VN-55 |
| part | `cone-tip-pinch-screw` | MHA-098 | `vn-cone-tip-pinch-screw` | MHA-VN-018 | `dt-vn-cone-tip-pinch-screw` | MHA-DT-VN-56 |
| part | `slotted-screw` | MHA-101 | `vn-slotted-screw` | MHA-VN-019 | `dt-vn-slotted-screw` | MHA-DT-VN-57 |
| part | `foot-screw` | MHA-103 | `vn-foot-screw` | MHA-VN-020 | `sh-vn-fillister-screw-90280a108` (`Default`) | MHA-SH-VN-52 |
| part | `clamp-screw` | MHA-107 | `vn-clamp-screw` | MHA-VN-021 | `sh-vn-clamp-screw` | MHA-SH-VN-53 |
| part | `frame-side-screw` | MHA-117 | `vn-frame-side-screw` | MHA-VN-022 | `ch-vn-frame-side-screw` | MHA-CH-VN-52 |
| part | `gooseneck-set-screw` | MHA-118 | `vn-gooseneck-set-screw` | MHA-VN-023 | `fr-vn-gooseneck-set-screw` | MHA-FR-VN-52 |
| part | `knife-hanger-stud` | MHA-119 | `vn-knife-hanger-stud` | MHA-VN-024 | `sm-vn-knife-hanger-stud` | MHA-SM-VN-52 |
| part | `wheel-axle-nut` | MHA-129 | `vn-wheel-axle-nut` | MHA-VN-025 | `mg-vn-wheel-axle-nut` | MHA-MG-VN-52 |
| retired part | `knife-hanger-washer` | MHA-131 | `vn-knife-hanger-washer` (old 1/2-inch family) | MHA-VN-026 | — | — (retired; MHA-VN-026 never reissued) |
| part | `frame-cross-screw` | MHA-132 | `vn-frame-cross-screw` | MHA-VN-027 | `fr-vn-frame-cross-screw` | MHA-FR-VN-53 |
| part | `tube-frame-cap` | MHA-133 | `vn-tube-frame-cap` | MHA-VN-028 | `fr-vn-tube-frame-cap` | MHA-FR-VN-54 |
| part | `cone-tip-block-screw` | MHA-140 | `vn-cone-tip-block-screw` | MHA-VN-030 | `dt-vn-cone-tip-block-screw` | MHA-DT-VN-60 |
| part | `post-mount-screw` | MHA-142 | `vn-post-mount-screw` | MHA-VN-031 | `dt-vn-post-mount-screw` | MHA-DT-VN-61 |
| part | `pedestal-hold-down-screw` | MHA-143 | `vn-pedestal-hold-down-screw` | MHA-VN-032 | `dt-vn-pedestal-hold-down-screw` | MHA-DT-VN-62 |
| part | `pinion-strap-pin` | MHA-145 | `vn-pinion-strap-pin` | MHA-VN-033 | `dt-vn-pinion-strap-pin` | MHA-DT-VN-63 |
| part | `arbor-set-screw` | MHA-147 | `vn-arbor-set-screw` | MHA-VN-034 | `sh-vn-arbor-set-screw` | MHA-SH-VN-54 |
| part | `keeper-chain` | MHA-149 | `vn-keeper-chain` | MHA-VN-035 | `dt-vn-keeper-chain` | MHA-DT-VN-65 |
| part | `keeper-chain-link` | MHA-150 | `vn-keeper-chain-link` | MHA-VN-036 | `dt-vn-keeper-chain-link` | MHA-DT-VN-66 |
| retired part | `transgear-collar-cross-pin` | MHA-154 | `vn-transgear-collar-cross-pin` | MHA-VN-037 | — | — (retired; MHA-VN-037 never reissued) |
| part | `transgear-knob-drive-pin` | MHA-155 | `vn-transgear-knob-drive-pin` | MHA-VN-038 | `pd-vn-transgear-knob-drive-pin` | MHA-PD-VN-54 |
| part | `transgear-disc-screw` | MHA-161 | `vn-transgear-disc-screw` | MHA-VN-039 | `pd-vn-transgear-disc-screw` | MHA-PD-VN-55 |
| part | `transgear-arm-plate-screw` | MHA-166 | `vn-transgear-arm-plate-screw` | MHA-VN-040 | `pd-vn-transgear-arm-plate-screw` | MHA-PD-VN-56 |
| part | `transgear-pivot-screw` | MHA-168 | `vn-transgear-pivot-screw` | MHA-VN-041 | `pd-vn-transgear-pivot-screw` | MHA-PD-VN-57 |
| part | `transgear-latch-pin` | MHA-169 | `vn-transgear-latch-pin` | MHA-VN-042 | `pd-vn-transgear-latch-pin` | MHA-PD-VN-58 |
| part | `latch-hook-bracket-screw` | MHA-171 | `vn-latch-hook-bracket-screw` | MHA-VN-043 | `sh-vn-fillister-screw-90280a108` (`Default`) | MHA-SH-VN-52 |
| part | `crank-seat-drive-pin` | MHA-173 | `vn-crank-seat-drive-pin` | MHA-VN-044 | `dt-vn-crank-seat-drive-pin` | MHA-DT-VN-67 |
| retired part | `latch-hook-rivet` | MHA-175 | `vn-latch-hook-rivet` | MHA-VN-045 | — | — (retired; MHA-VN-045 never reissued) |
| part | `guide-lock-screw` | MHA-176 | `vn-guide-lock-screw` | MHA-VN-046 | `pd-vn-guide-lock-screw` | MHA-PD-VN-60 |
| part | `transgear-retaining-ring` | MHA-182 | `vn-transgear-retaining-ring` | MHA-VN-047 | `pd-vn-transgear-retaining-ring` | MHA-PD-VN-61 |
| part | `transgear-knob-cup-pin` | MHA-183 | `vn-transgear-knob-cup-pin` | MHA-VN-048 | `pd-vn-transgear-knob-cup-pin` | MHA-PD-VN-62 |
| part | `transgear-pivot-spring` | MHA-184 | `vn-transgear-pivot-spring` | MHA-VN-049 | `pd-vn-transgear-pivot-spring` | MHA-PD-VN-63 |
| part | — | — | `vn-magnifying-bracket-screw` | MHA-VN-050 | `mg-vn-magnifying-bracket-screw` | MHA-MG-VN-53 |
| part | — | — | `vn-knife-mount-dowel` | MHA-VN-051 | `sm-vn-knife-mount-dowel` | MHA-SM-VN-53 |
| part | — | — | `vn-cylinder-bank-spring` | MHA-VN-052 | `dt-vn-cylinder-bank-spring` | MHA-DT-VN-68 |
| part | — | — | `vn-rocker-bank-spring` | MHA-VN-053 | `ch-vn-rocker-bank-spring` | MHA-CH-VN-54 |
| part | — | — | `vn-ms-stop-plate-screw` | MHA-VN-054 | `ms-vn-stop-plate-screw` | MHA-MS-VN-51 |
| part | — | — | `vn-fulcrum-set-screw` | MHA-VN-055 | `ch-vn-fulcrum-set-screw` | MHA-CH-VN-55 |
| part | — | — | `vn-transgear-arm-plate-locating-pin` | MHA-VN-056 | `pd-vn-transgear-arm-plate-locating-pin` | MHA-PD-VN-64 |
| part | — | — | `vn-wheel-axle-back-washer` | MHA-VN-057 | `mg-vn-wheel-axle-back-washer` | MHA-MG-VN-54 |
| part | — | — | `vn-wheel-axle-front-washer` | MHA-VN-058 | `mg-vn-wheel-axle-front-washer` | MHA-MG-VN-55 |
| part | — | — | `vn-platen-clip-screw` | MHA-VN-059 | `pd-vn-platen-clip-screw` | MHA-PD-VN-65 |
| part | — | — | `vn-pen-marker` | MHA-VN-065 | `pn-vn-pen-marker` | MHA-PN-VN-56 |
| part | — | — | `vn-pen-rod-set-screw` | MHA-VN-061 | `pn-vn-pen-rod-set-screw` | MHA-PN-VN-52 |
| part | — | — | `vn-pen-adjust-nut` | MHA-VN-062 | `pn-vn-pen-adjust-nut` | MHA-PN-VN-53 |
| part | — | — | `vn-pen-hanger-nut` | MHA-VN-063 | `pn-vn-pen-hanger-nut` | MHA-PN-VN-54 |
| part | — | — | `vn-pen-hanger-jam-nut` | MHA-VN-064 | `pn-vn-pen-hanger-jam-nut` | MHA-PN-VN-55 |
| part | — | — | `vn-lever-wire` | MHA-VN-066 | `sh-vn-music-wire` (`LeverWire`) | MHA-SH-VN-56 |
| part | — | — | `vn-pen-wire` | MHA-VN-067 | `sh-vn-music-wire` (`PenWire`) | MHA-SH-VN-56 |
| part | — | — | `vn-transgear-pivot-shim` | MHA-VN-069 | `pd-vn-transgear-pivot-shim` | MHA-PD-VN-67 |
| part | — | — | `vn-rocker-thrust-washer` | MHA-VN-070 | `ch-vn-rocker-thrust-washer` | MHA-CH-VN-56 |
| part | — | — | `vn-bracket-hold-down-screw` | MHA-VN-071 | `ch-vn-bracket-hold-down-screw` | MHA-CH-VN-57 |
| part | — | — | `vn-boss-hook-jam-nut` | MHA-VN-072 | `sm-vn-boss-hook-jam-nut` | MHA-SM-VN-55 |
| part | — | — | `vn-knife-hanger-washer` (new #10 family) | MHA-VN-060 | `sm-vn-knife-hanger-washer` | MHA-SM-VN-54 |
| part | — | — | `vn-chain-connecting-link` | MHA-VN-068 | `pd-vn-chain-connecting-link` | MHA-PD-VN-66 |
| part | `column-clamp-front` | MHA-105 | `sh-column-clamp-front` | MHA-SH-001 | `sh-column-clamp-front` | MHA-SH-01 |
| part | `column-clamp-back` | MHA-106 | `sh-column-clamp-back` | MHA-SH-002 | `sh-column-clamp-back` | MHA-SH-02 |
| retired tooling part | — | — | `ch-rocker-arm-tl-vise-stop` | MHA-CH-006-TL-01 | — | MHA-CH-06-TL-01 (retired; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-profile-fixture` | MHA-CH-006-TL-02 | — | MHA-CH-06-TL-02 (retired; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-diamond-pin` | MHA-CH-006-TL-03 | — | MHA-CH-06-TL-03 (retired; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-filing-button` | MHA-CH-006-TL-04 | — | MHA-CH-06-TL-04 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-filing-stud` | MHA-CH-006-TL-05 | — | MHA-CH-06-TL-05 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-pivot-screw` | MHA-CH-006-TL-06 | — | MHA-CH-06-TL-06 (retired; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-pivot-washer` | MHA-CH-006-TL-07 | — | MHA-CH-06-TL-07 (retired; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-inspection-box` | MHA-CH-006-TL-08 | — | MHA-CH-06-TL-08 (retired; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-c-stop-bar` | MHA-CH-006-TL-09 | — | MHA-CH-06-TL-09 (retired; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-riser-block` | MHA-CH-006-TL-10 | — | MHA-CH-06-TL-10 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-strap-shim-stack` | MHA-CH-006-TL-11 | — | MHA-CH-06-TL-11 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-filing-stand` | MHA-CH-006-TL-12 | — | MHA-CH-06-TL-12 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-outline-template` | MHA-CH-006-TL-13 | — | MHA-CH-06-TL-13 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-trammel-pivot-block` | MHA-CH-006-TL-14 | — | MHA-CH-06-TL-14 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-trammel-scriber-block` | MHA-CH-006-TL-15 | — | MHA-CH-06-TL-15 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-trammel-scriber-point` | MHA-CH-006-TL-16 | — | MHA-CH-06-TL-16 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-trammel-setting-bar` | MHA-CH-006-TL-17 | — | MHA-CH-06-TL-17 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-trammel-pivot-point` | MHA-CH-006-TL-18 | — | MHA-CH-06-TL-18 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-trammel-pivot-plate` | MHA-CH-006-TL-19 | — | MHA-CH-06-TL-19 (retired 2026-10-21; never reissued) |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-base-bar` | MHA-CH-006-TL-20 | `ch-rocker-arm-tl-oblique-base-bar` | MHA-CH-06-TL-20 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-carrier` | MHA-CH-006-TL-21 | `ch-rocker-arm-tl-oblique-carrier` | MHA-CH-06-TL-21 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-pivot-block` | MHA-CH-006-TL-22 | `ch-rocker-arm-tl-oblique-pivot-block` | MHA-CH-06-TL-22 |
| retired tooling part | — | — | `ch-rocker-arm-tl-oblique-pivot-pin` | MHA-CH-006-TL-23 | — | MHA-CH-06-TL-23 (retired 2026-10-23; never reissued) |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-riser` | MHA-CH-006-TL-24 | `ch-rocker-arm-tl-oblique-riser` | MHA-CH-06-TL-24 |
| retired tooling part | — | — | `ch-rocker-arm-tl-oblique-hub-pin` | MHA-CH-006-TL-25 | — | MHA-CH-06-TL-25 (retired 2026-10-23; never reissued) |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-feed-lever` | MHA-CH-006-TL-26 | `ch-rocker-arm-tl-oblique-feed-lever` | MHA-CH-06-TL-26 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-end-bracket` | MHA-CH-006-TL-28 | `ch-rocker-arm-tl-oblique-end-bracket` | MHA-CH-06-TL-28 |
| retired tooling part | — | — | `ch-rocker-arm-tl-oblique-nut-bracket` | MHA-CH-006-TL-29 | — | MHA-CH-06-TL-29 (retired 2026-10-23; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-oblique-pivot-cap` | MHA-CH-06-TL-30 | — | MHA-CH-06-TL-30 (retired 2026-10-23; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-oblique-pivot-retainer` | MHA-CH-06-TL-31 | — | MHA-CH-06-TL-31 (retired 2026-10-23; never reissued) |
| new tooling part (2026-10-23) | — | — | — | — | `ch-rocker-arm-tl-oblique-feed-block` | MHA-CH-06-TL-32 |
| new tooling part (2026-11-01) | — | — | — | — | `ch-rocker-arm-tl-oblique-feed-nut` | MHA-CH-06-TL-27 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-rail` | MHA-CH-006-TL-30 | `ch-rocker-arm-tl-vn-oblique-rail` | MHA-CH-06-TL-VN-50 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-carriage` | MHA-CH-006-TL-31 | `ch-rocker-arm-tl-vn-oblique-carriage` | MHA-CH-06-TL-VN-51 |
| retired tooling vendor part | — | — | `ch-rocker-arm-tl-oblique-bearing` | MHA-CH-006-TL-32 | — | MHA-CH-06-TL-VN-52 (retired 2026-10-23; never reissued) |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-cl-dowel` | MHA-CH-006-TL-33 | `ch-rocker-arm-tl-vn-oblique-cl-dowel` | MHA-CH-06-TL-VN-53 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-leadscrew` | MHA-CH-006-TL-34 | `ch-rocker-arm-tl-vn-oblique-leadscrew` | MHA-CH-06-TL-VN-54 |
| retired tooling vendor part | — | — | `ch-rocker-arm-tl-oblique-leadscrew-nut` | MHA-CH-006-TL-35 | — | MHA-CH-06-TL-VN-55 (retired 2026-11-01; never reissued) |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-pillow-block` | MHA-CH-006-TL-36 | `ch-rocker-arm-tl-vn-oblique-pillow-block` | MHA-CH-06-TL-VN-56 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-handwheel` | MHA-CH-006-TL-37 | `ch-rocker-arm-tl-vn-oblique-handwheel` | MHA-CH-06-TL-VN-57 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-hold-down-stud` | MHA-CH-006-TL-38 | `sh-vn-clamping-kit-hardware` (`HoldDownStud`) | MHA-SH-VN-57 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-t-nut` | MHA-CH-006-TL-39 | `sh-vn-clamping-kit-hardware` (`TNut`) | MHA-SH-VN-57 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-flange-nut` | MHA-CH-006-TL-40 | `sh-vn-clamping-kit-hardware` (`FlangeNut`) | MHA-SH-VN-57 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-rail-screw` | MHA-CH-006-TL-41 | `ch-rocker-arm-tl-vn-oblique-rail-screw` | MHA-CH-06-TL-VN-61 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-bracket-screw` | MHA-CH-006-TL-42 | `ch-rocker-arm-tl-vn-oblique-bracket-screw` | MHA-CH-06-TL-VN-62 |
| retired tooling vendor part | — | — | `ch-rocker-arm-tl-oblique-block-screw` | MHA-CH-006-TL-43 | — | MHA-CH-06-TL-VN-63 (retired 2026-10-23; never reissued) |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-carriage-screw` | MHA-CH-006-TL-44 | `ch-rocker-arm-tl-vn-oblique-carriage-screw` | MHA-CH-06-TL-VN-64 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-kp08-screw` | MHA-CH-006-TL-45 | `ch-rocker-arm-tl-vn-oblique-kp08-screw` | MHA-CH-06-TL-VN-65 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-nut-screw` | MHA-CH-006-TL-46 | `ch-rocker-arm-tl-vn-oblique-nut-screw` | MHA-CH-06-TL-VN-66 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-riser-screw` | MHA-CH-006-TL-47 | `ch-rocker-arm-tl-vn-oblique-riser-screw` | MHA-CH-06-TL-VN-67 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-clamp-screw` | MHA-CH-006-TL-48 | `ch-rocker-arm-tl-vn-oblique-clamp-screw` | MHA-CH-06-TL-VN-68 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-lever-screw` | MHA-CH-006-TL-49 | `ch-rocker-arm-tl-vn-oblique-lever-screw` | MHA-CH-06-TL-VN-69 |
| retired tooling vendor part | — | — | `ch-rocker-arm-tl-oblique-block-washer` | MHA-CH-006-TL-50 | — | MHA-CH-06-TL-VN-70 (retired 2026-10-23; never reissued) |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-lever-washer` | MHA-CH-006-TL-51 | `ch-rocker-arm-tl-vn-oblique-lever-washer` | MHA-CH-06-TL-VN-71 |
| retired tooling vendor part | — | — | `ch-rocker-arm-tl-vn-oblique-pivot-cap-screw` | MHA-CH-06-TL-VN-73 | — | MHA-CH-06-TL-VN-73 (retired 2026-10-23; never reissued) |
| retired tooling vendor part | — | — | `ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin` | MHA-CH-06-TL-VN-74 | — | MHA-CH-06-TL-VN-74 (retired 2026-10-23; never reissued) |
| retired tooling vendor part | — | — | `ch-rocker-arm-tl-vn-oblique-pivot-cotter` | MHA-CH-06-TL-VN-75 | — | MHA-CH-06-TL-VN-75 (retired 2026-10-23; never reissued) |
| retired tooling vendor part | — | — | `ch-rocker-arm-tl-vn-oblique-pivot-lock-wire` | MHA-CH-06-TL-VN-76 | — | MHA-CH-06-TL-VN-76 (retired 2026-10-23; never reissued) |
| new tooling vendor part (2026-10-23) | — | — | — | — | `ch-rocker-arm-tl-vn-oblique-pivot-screw` | MHA-CH-06-TL-VN-77 |
| new tooling vendor part (2026-10-23) | — | — | — | — | `ch-rocker-arm-tl-vn-oblique-pivot-spacer` | MHA-CH-06-TL-VN-78 |
| new tooling vendor part (2026-10-23) | — | — | — | — | `ch-rocker-arm-tl-vn-oblique-pivot-shim` | MHA-CH-06-TL-VN-79 |
| new tooling vendor part (2026-10-23) | — | — | — | — | `ch-rocker-arm-tl-vn-oblique-hub-pin` | MHA-CH-06-TL-VN-80 |
| retired tooling part | — | — | `ch-pivot-bracket-tl-ledge` | MHA-CH-008-TL-01 | — | MHA-CH-08-TL-01 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `ch-pivot-bracket-tl-angle-plate` | MHA-CH-008-TL-02 | — | MHA-CH-08-TL-02 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `dt-cone-pivot-post-tl-bond-cradle` | MHA-DT-005-TL-01 | — | MHA-DT-05-TL-01 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `dt-cone-pivot-post-tl-saw-cradle` | MHA-DT-005-TL-02 | — | MHA-DT-05-TL-02 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `dt-cone-pivot-post-tl-cap-jaw-button` | MHA-DT-005-TL-03 | — | MHA-DT-05-TL-03 (retired 2026-10-21; never reissued) |
| retired tooling part | — | — | `dt-cone-pivot-post-tl-soft-jaw` | MHA-DT-005-TL-04 | — | MHA-DT-05-TL-04 (retired 2026-10-21; never reissued) |
| assembly | `frame` | MHA-A04 | `fr-frame` | MHA-FR-000 | `fr-frame` | MHA-FR-00 |
| assembly | `drive-train` | MHA-A03 | `dt-drive-train` | MHA-DT-000 | `dt-drive-train` | MHA-DT-00 |
| assembly | `channel` | MHA-A02 | `ch-channel` | MHA-CH-000 | `ch-channel` | MHA-CH-00 |
| assembly | `summing` | MHA-A07 | `sm-summing` | MHA-SM-000 | `sm-summing` | MHA-SM-00 |
| assembly | `magnifier` | MHA-A05 | `mg-magnifier` | MHA-MG-000 | `mg-magnifier` | MHA-MG-00 |
| assembly | `pen` | MHA-A01 | `pn-pen` | MHA-PN-000 | `pn-pen` | MHA-PN-00 |
| assembly | `paper-drive` | MHA-A06 | `pd-paper-drive` | MHA-PD-000 | `pd-paper-drive` | MHA-PD-00 |
| assembly | — | — | `ms-measuring-stick` | MHA-MS-000 | `ms-measuring-stick` | MHA-MS-00 |
| assembly | `harmonic-analyzer` | MHA-A08 | `ha-harmonic-analyzer` | MHA-HA-000 | `ha-harmonic-analyzer` | MHA-HA-00 |
| tooling assembly | — | — | `ch-rocker-arm-tl-oblique-jig` | MHA-CH-006-TL-000 | `ch-rocker-arm-tl-oblique-jig` | MHA-CH-06-TL-00 |

### Shared vendor families

At the 2026-10-19 cutover, four category vendor families were in direct use by more than one assembly, and each consuming assembly received its own parent-scoped identity. On 2026-10-20 that duplication was reversed: every supplier-qualified SKU in repeated use became one shared SH vendor identity, and heterogeneous members of one SKU became named configurations of it. The eight current shared families are, in stable allocation order (sorted by supplier and SKU):

| Current stem | Current Number | Supplier and SKU | Configurations (installed members) | Direct consumers |
|---|---|---|---|---|
| `sh-vn-chain-link` | MHA-SH-VN-50 | McMaster-Carr 6261K171, sold by the foot | `InnerLink` 33; `OuterLink` 32 | `pd-paper-drive` (one cut 66-pitch loop closed by `pd-vn-chain-connecting-link` MHA-PD-VN-66, which stays parent-scoped: 6261K108 has one consumer; #2034 shortened it from 68 pitches) |
| `sh-vn-brass-fillister-screw` | MHA-SH-VN-51 | McMaster-Carr 90114A511 | `Default` | `dt-drive-train`, `fr-frame`, `pd-paper-drive` |
| `sh-vn-fillister-screw-90280a108` | MHA-SH-VN-52 | McMaster-Carr 90280A108 | `Default` (foot's unshifted stock frame; the swing-stop's PROUD_LEN placement and application colours live in the consuming occurrences) | `dt-drive-train` (foot and swing-stop roles), `pd-paper-drive` (latch-hook screws) |
| `sh-vn-clamp-screw` | MHA-SH-VN-53 | McMaster-Carr 90280A201 | `Default` | `mg-magnifier`, `pd-paper-drive` |
| `sh-vn-arbor-set-screw` | MHA-SH-VN-54 | McMaster-Carr 91375A106 | `Default` (alloy steel, Rockwell C45, black oxide, unchanged) | `ch-channel`, `dt-drive-train` |
| `sh-vn-thumb-screw` | MHA-SH-VN-55 | McMaster-Carr 91882A221 | `Default` | `mg-magnifier`, `ms-measuring-stick` |
| `sh-vn-music-wire` | MHA-SH-VN-56 | McMaster-Carr 9666K56, one 1/4 lb coil | `LeverWire` 1; `PenWire` 1 (one-sheet purchase drawing: supplier wire Ø and SKU only; terminations, wraps and cut lengths are not modelled) | `mg-magnifier` (lever wire), `pn-pen` (pen wire) |
| `sh-vn-clamping-kit-hardware` | MHA-SH-VN-57 | Precision Matthews 52PCCK-9/16-14mm, one kit | `HoldDownStud` 4; `TNut` 4; `FlangeNut` 4 | `ch-rocker-arm-tl-oblique-jig` only; `usage_scope: tooling`, no machine assembly or BOM, excluded from machine counts |

The registry `quantity` is the sum of the installed member counts (65 links, 2 wire forms, 12 kit members), never the purchase units (one chain cut from 2 ft, one coil, one kit). Members share one purchase Number; where their bodies differ, their BOM rows differ by Description and are not summed into one row. The SKU suffix in `sh-vn-fillister-screw-90280a108` separates that steel fillister product from the brass 90114A511 one. No supplier dimension changed in the consolidation; the shared models carry the geometry the parent-scoped models had.

Configured chain and clamping-kit reference sheets place each member caption from its measured native text extent and annotation position, centering the text box within its reserved panel-header band. After the final rebuild, strict containment checks require the actual note extent to remain inside both that band and the drawable sheet border. An insertion coordinate or a successful positioning call alone is not proof of fit. This placement contract does not change supplier dimensions, member geometry or installed quantities.

The wire's one-sheet purchase drawing prints only what replacement needs. A 20:1 end view of the zero-body `SUPPLIER_REFERENCE` circle carries the native supplier Ø as its one dimension; the circle's centre mark is deleted and its construction curves print as a solid outline. An undimensioned `PenWire` isometric, Shaded With Edges, is labelled reference only, not to length. One property-linked note gives the SKU. A second note says each member is cut to length and formed at assembly and cites the magnifier and pen assembly drawing sheets and steps that do it; neither note carries a dimension. The source part is opened read-only, must be clean, and its file bytes are proven unchanged through export and drawing close. Final readback re-checks the Ø identity and value, both views' configuration, scale and fields, and every note's text and clearance.

The clamping-kit sheet identifies its installed stud with an associative overall reference between the existing model's end rims; its measured reference text must stay at least 2 mm left of the FRONT view outline. Each nut retains one bore-owned native `ICThread.ThreadCallout` in its isometric view, inserting that callout once if absent. Bore-owned native callouts in other views are deliberately retired by selected-note identity, with fresh readback proving removal and unchanged cosmetic-thread/model geometry; they are not transferred by changing annotation ownership or replaced with free text. The returned `INote` can have zero direct geometry attachments: hole association and strict edge/face identity are proved on the owning cosmetic-thread annotation. Each leader targets the projected native top bore rim, identified by its center, axis, height, owning feature identity and the Hole Wizard's actual through-tap drill diameter, not a rounded nominal. A visible rim edge must map into the referenced source part and back to the exact original view edge; its adjacent features are compared with the bore feature only within that source context, never by matching names or comparing source and drawing feature wrappers directly. Source queries use fresh inventories in one explicitly activated view configuration, then strictly restore the prior configuration in `finally` without saving or forcing a rebuild. Initial mismatched/matched mapping observations test configuration dependence; the SDK does not state it as a precondition. Source SHA before/after the initial control, unsaved state, all view configurations and drawing activation must remain unchanged, and a fresh inventory after restoration must identify exactly the same visible edge. Across scopes, bore identity uses the source path, persistent `IFeature.GetID()` and exact diameter; mapped source-edge wrappers never escape the active scope. Native edge-parameter and closest-point readbacks require that target to lie on exactly one visible physical rim edge; an underlying circle alone does not establish its trim. After relocation and the final rebuild, checks require the same native note, cosmetic thread, bore feature/diameter, attachments and visible rim edge, unchanged note content, a live leader at that rim, and rendered text plus complete native extent inside the member's reserved panel. A successful leader setter alone is not evidence that the native parent relationship survived. The reference sheet prints sourcing facts only; the per-member installation legend and its `[1]`/`[2]`/`[3]` view flags were retired because installation belongs to the jig assembly's steps (MHA-CH-06-TL-00).

The stud-only REWORK sheet prints the finished-length model dimension and one native side-view chamfer leader attached to the upper bevel/barrel boundary. The leader uses the saved source angle and the model's validated maximum size and precision; the unprinted chamfer dimension must remain a driving MAX control with its original tolerance band and decimal places. Settled readback verifies that source control and the leader's front-view ownership, text, native attachment and landing. The end view retains no duplicate chamfer dimension. The reference-sheet footer retains the reference-view limitation, scopes “as supplied” to the two nuts and directs the stud rework explicitly to sheet 2.

SOLIDWORKS owns occurrence names and native instance indices. Shared components are identified by physical file, selected configuration and scoped `Role:N` component reference, not a custom `Name2` spelling. Logical BOM keys such as `sh-vn-chain-link--InnerLink` identify file/configuration rows; they are not native occurrence aliases. The pipeline never renames these occurrences or changes the application naming preference.

Drawing traversal calls `GetPathName` through `IDrawingComponent.Component` bound as `IComponent2` and propagates path-read failures. Shared-reference selectors (`@Role:N`) and configured member keys (`stem--member`) require native file/configuration identity rather than a display-name substitute. A recognized reference also requires readable, non-empty native `Name2` before deriving its parent scope; an unavailable name must not turn a nested occurrence into an unscoped selector. Ordinary unreferenced bare-stem matching is unchanged.

Reference writes are idempotent and read back independently. After an explicit rebuild, bind semantic references to current native names again and verify parent scope, native instance index, configuration and pose. Move any existing pose-ledger entry unchanged to its current name, refusing collisions; never accept a stale name through a compatibility alias.

The paper-drive chain assigns references after the pattern exists. At that late rebuild, match pre- and post-rebuild occurrences by checked loop station and apply the same name/index/scope/ledger checks to every station, including the unreferenced connecting link. Preserve the four existing seed/closing-link ledger entries exactly; do not replace them with newly observed poses.

Native drawing BOMs display the released `Number` through a separate associative custom-property column while retaining the original native Part Number column hidden and physically last. Converting the original column was observed to remove paper drive's entire T12/T24/T18 row immediately, despite unchanged eligibility and BOM names. Bind `Number` with every real column visible, using only `IBomTableAnnotation.SetColumnCustomProperty` on an already-native custom-property type 204 column; require boolean `True`, dedicated getter agreement and unchanged all-visible physical types before hiding. No retyping or fallback binding API is used. `ColumnHidden`/`SetColumnHidden` use a separate zero-based visibility domain: a top-level BOM keeps one Quantity column per configuration in `IBomFeature.GetConfigurations` order, and each deselected configuration's Quantity is latent, counted by `TotalColumnCount` and that domain but absent from typed/text APIs with `IncludeHidden=True`. Latent columns of configurations ordered before the selected one sit immediately before its typed Quantity, later ones after the last typed column, so a typed column maps to its physical index plus the number of earlier latent columns when at or after the typed Quantity. Native2507 (Default Simplified selected) observed that offset as plus one: PROPERTY4 hid physical Qty3, whereas PROPERTY5 hid physical native2014 and retained visible QTY, grouped quantity 3 and InnerLink/OuterLink quantities 34/33. With Default selected (v45 run 20261023T163903809Z) the latent Quantity follows the native column and the offset is zero; writing plus one materialized that latent as a hidden typed QTY. The mapping requires exactly one selected configuration, one typed Quantity and configurations-minus-one latent columns, and mutations refuse any index beyond the typed prefix. All six observed native membership snapshots retained 43 rows and 145 occurrences, and source disk hashes/live save flags were unchanged. The earlier visible native Part Number in the Qty slot was an actual mistaken Qty hide, not a projection of a supposedly hidden201 column. Central visibility helpers translate only those visibility accessors; widths, moves, inserts, custom-property binding and row indexing are not shifted. Readback rediscovers the unique trailing201 after SKU insertion, requires the contiguous visible prefix and proves the Number column's dedicated property binding. `TotalColumnCount` is a bounded scan limit, not a mutation destination: discover the complete valid physical typed prefix before evaluating visibility and any empty unsupported tail against two independent beyond-count controls. The first typed-invalid physical index can equal the valid hidden201 visibility index; its own visibility control is mapped through the same configuration-dependent offset. Zero-width hidden typed columns remain valid. Interior gaps, nonempty unsupported entries, malformed metadata, accessor errors, visibility-count mismatches and unsupported bounds fail closed. Physical row/header reads and description/SKU writes retain `IncludeHidden=True`. `SetText2` on a property-bound cell writes into each component model's active configuration (native PD runs 20261023T190254133Z/192129678Z dirtied `sh-vn-clamp-screw`), so the template DESCRIPTION column is unlinked in place with `SetColumnCustomProperty(column, "")` while every column is visible, read back as `(204, '', 0)` after the rebuild and again before and after authoring, and every row needs nonblank drawing text; independently compare actual `IncludeHidden=False` type/title/header ordering and visible Number/Qty cells with the nonhidden physical columns. Unsplit readback requires equal visible/total row counts, and the header plus every validated global row must read `RowHidden=False`. Immutable snapshots retain global row, native file/configuration occurrence counts, canonical Number and quantity; settled tables and split pieces must preserve them, catching same-Number InnerLink/OuterLink reassignment, omitted rows and quantity drift. Split pieces retain their native global ranges rather than local renumbering. Paper drive must retain distinct InnerLink/OuterLink rows and one T12/T24/T18 row with quantity 3, including the parked spare. No retries, fake rows or Number-based substitutes for native identity are permitted. Temporary native visibility controls and bulk diagnostic payloads are removed; split and saved/reopened associativity still require native qualification.

Paper drive authors BOM widths only while every real column is visible. Native2507 disproved the earlier claim that hidden201 caused the row-height explosion: PROPERTY4 had actually hidden Qty while leaving native201 visible. The unversioned width API has no `IncludeHidden` argument and does not inherit the visibility PROPERTY offset. Width setup rediscovers the unique trailing native column through the strict typed census, reads/exposes/restores it through the mapped visibility helpers, proves all-visible physical/visible type and header agreement, and checks each setter's actual return and every column's independent width readback. The retained native column keeps the existing 118 mm Description width solely to avoid changing another native dimension in this production canary; it is not a qualified hidden-row-minimum requirement. Its exact original hidden state is restored even on failure, and a restoration failure cannot mask the primary error. This window never rebinds Number, changes grouping or font, or adds a rebuild. Native2507 observed a 190 mm visible grid after hiding native201 correctly, but that unsplit control is not a production split/save/reopen qualification. Permanent split checks read each annotation's actual display-line grid: bounded ten-value native records must establish all five vertical boundaries and every repeated-header/data-row boundary with complete segment coverage. Missing, nonfinite, nonplanar, diagonal, extra or ambiguous geometry fails closed. Measured column intervals, top-to-bottom row intervals and the grid's top-left must independently agree with intended widths, native global-row heights and native annotation anchor before the measured rectangle is checked against its assigned field. Configured widths never supply missing geometry or normalize an ambiguous aggregate. Bounded raw grid, derived geometry and error evidence remain; temporary rendered-text/width observation bulk is removed. The SDK documents line encoding but not this table's display-coordinate or split-piece scope; production split geometry and saved/reopened readback still require native qualification.

Paper drive selects canonical `Default` native BOM membership at initial insertion, independently of its simplified rendered reference. The shared insertion helper's optional configuration override binds that one configuration before Number binding and normal width/height/split authoring; omitted overrides retain view-derived behavior. Top-level selection reads all available native configuration names, supplies the complete one-hot visibility array to `SetConfigurations(False, ...)`, and strictly reads that selection back before grouping or column authoring. Native2537 changed only the BOM configuration and observed the same attached pivot-screw balloon `* → 16 → *` across Simplified/Default/Simplified, with arm item 15 stable. All 43 source-document SHA-256/save-flag/active-configuration maps remained identical across those phases; 42 documents were already dirty, not clean. The late Default switch widened Qty from 12 to 21.427203109 mm: first-piece membership passed before its grid refused, so the second piece was not validated in that phase. This is why configuration selection precedes formatting rather than repairing a completed table.

Native2537 read both transgear isometric and inner views as `Default` after view operations; simplified creation policy does not establish their final configuration or identify which operation changed it. PD reads actual configuration against its selected BOM configuration immediately before each native balloon route, including the collar and the exploded platen view, which takes the full-detail role so it references `Default` at every ladder scale (native run 20261023T205501918Z: a `Default Simplified` occurrence resolved item `*` against the Default BOM); it never forces a view to pass. After the last rebuild, settled checks re-read native item text for every retained native balloon occurrence, including repeated stems, alongside attachment/leader and full split Number/Qty/membership/grid proofs. Circular item-text pivot notes are not native BOM balloons. Production all-43-row quantities 3/34/33, complete grids and saved/reopened associativity remain qualification gates, not results inferred from the controlled association experiment.

Installation checks remain with their subsystem rather than the purchased identity. The platform's `dt_cone_swing_platform_checks` reads the retained `dt_swing_stop_screw_spec` application contract, which consumes the shared stock dimensions; extracting those checks must not restore the retired `dt_vn_swing_stop_screw_spec` import.

A configured part that loses a create-only cache publication adopts the winner's complete native/member archive, stamps the adopted execution identity, then validates its STEP/PNG certificate before succeeding. Pre-publication validation of the losing outputs is not evidence for the adopted winner. Missing or mismatched winner members fail closed; never regenerate them or rewrite their certificate from the losing build.

Longer shared identities are checked against native drawing geometry. Support-bar slot counterbores retain their proven screw-head clearance minimum with native asymmetric model limits; Detail C's text and leader must clear Section B-B. The measuring-stick section-A marker must clear the setting dimension without changing its value or section plane. Frame sheet 2 places the set-screw balloon below the measured BOM extent and verifies its ring and leader remain clear of the cap balloon after rebuilding.

#### Shared vendor transition table

The two-digit parent-scoped identities below were current from 2026-10-19 to 2026-10-20 and appear in evidence dated in that window. They are lookup keys, not aliases: no registry row, builder, drawing, module or current map entry carries them, and their Numbers stay reserved in their parents and are never reissued. Read a historical reference through this table to the current shared identity and, where the shared part is configured, to the member configuration.

| Former stem (2026-10-19) | Former Number | Former parent | Current stem | Configuration | Current Number |
|---|---|---|---|---|---|
| `pd-vn-chain-inner-link` | MHA-PD-VN-50 | `pd-paper-drive` | `sh-vn-chain-link` | `InnerLink` | MHA-SH-VN-50 |
| `pd-vn-chain-outer-link` | MHA-PD-VN-51 | `pd-paper-drive` | `sh-vn-chain-link` | `OuterLink` | MHA-SH-VN-50 |
| `dt-vn-fillister-screw` | MHA-DT-VN-50 | `dt-drive-train` | `sh-vn-brass-fillister-screw` | `Default` | MHA-SH-VN-51 |
| `fr-vn-fillister-screw` | MHA-FR-VN-50 | `fr-frame` | `sh-vn-brass-fillister-screw` | `Default` | MHA-SH-VN-51 |
| `pd-vn-fillister-screw` | MHA-PD-VN-52 | `pd-paper-drive` | `sh-vn-brass-fillister-screw` | `Default` | MHA-SH-VN-51 |
| `dt-vn-foot-screw` | MHA-DT-VN-58 | `dt-drive-train` | `sh-vn-fillister-screw-90280a108` | `Default` | MHA-SH-VN-52 |
| `dt-vn-swing-stop-screw` | MHA-DT-VN-53 | `dt-drive-train` | `sh-vn-fillister-screw-90280a108` | `Default` | MHA-SH-VN-52 |
| `pd-vn-latch-hook-bracket-screw` | MHA-PD-VN-59 | `pd-paper-drive` | `sh-vn-fillister-screw-90280a108` | `Default` | MHA-SH-VN-52 |
| `mg-vn-clamp-screw` | MHA-MG-VN-51 | `mg-magnifier` | `sh-vn-clamp-screw` | `Default` | MHA-SH-VN-53 |
| `pd-vn-clamp-screw` | MHA-PD-VN-53 | `pd-paper-drive` | `sh-vn-clamp-screw` | `Default` | MHA-SH-VN-53 |
| `ch-vn-arbor-set-screw` | MHA-CH-VN-53 | `ch-channel` | `sh-vn-arbor-set-screw` | `Default` | MHA-SH-VN-54 |
| `dt-vn-arbor-set-screw` | MHA-DT-VN-64 | `dt-drive-train` | `sh-vn-arbor-set-screw` | `Default` | MHA-SH-VN-54 |
| `mg-vn-thumb-screw` | MHA-MG-VN-50 | `mg-magnifier` | `sh-vn-thumb-screw` | `Default` | MHA-SH-VN-55 |
| `ms-vn-thumb-screw` | MHA-MS-VN-50 | `ms-measuring-stick` | `sh-vn-thumb-screw` | `Default` | MHA-SH-VN-55 |
| `mg-vn-lever-wire` | MHA-MG-VN-56 | `mg-magnifier` | `sh-vn-music-wire` | `LeverWire` | MHA-SH-VN-56 |
| `pn-vn-pen-wire` | MHA-PN-VN-57 | `pn-pen` | `sh-vn-music-wire` | `PenWire` | MHA-SH-VN-56 |
| `ch-rocker-arm-tl-vn-oblique-hold-down-stud` | MHA-CH-06-TL-VN-58 | `ch-rocker-arm-tl-oblique-jig` | `sh-vn-clamping-kit-hardware` | `HoldDownStud` | MHA-SH-VN-57 |
| `ch-rocker-arm-tl-vn-oblique-t-nut` | MHA-CH-06-TL-VN-59 | `ch-rocker-arm-tl-oblique-jig` | `sh-vn-clamping-kit-hardware` | `TNut` | MHA-SH-VN-57 |
| `ch-rocker-arm-tl-vn-oblique-flange-nut` | MHA-CH-06-TL-VN-60 | `ch-rocker-arm-tl-oblique-jig` | `sh-vn-clamping-kit-hardware` | `FlangeNut` | MHA-SH-VN-57 |

## Changes after the category cutover

A retired Number is never reused. A family added after a cutover takes the next free Number in its namespace: the next fabricated Number in its category, the next vendor Number from `50` under its direct parent assembly, the next shared vendor Number from `50` under SH, or the next TL Number under its fixture's parent part. It has no v39 stem or Number. This log is chronological: each entry uses the stem and Number current when it was written, so the `added` entries for the nineteen parent-scoped vendor identities of 2026-10-19 stand as written, and the `shared` entries at the end record their 2026-10-20 consolidation. Retired machine and fixture Numbers appear in their reserved two-digit form; retired category vendor families keep their category stem and Number, which have no current form. The tables above give each family's earlier identities, and the shared vendor transition table resolves a superseded parent-scoped identity to its shared identity and configuration.

| Change | Stem | Number | Note |
|---|---|---|---|
| retired | `pd-chain-sprocket` | MHA-PD-01 | orphan removed from assemblies in `29025dd34`; superseded by the MHA-PD-09 `pd-transgear-removable` sprocket configurations (#68; delivery #507 retired) |
| retired | `vn-hex-bolt` | MHA-VN-008 | orphan removed from the frame in `2ab7dc109`; no assembly uses this family (delivery #543 retired) |
| retired | `pd-latch-hook-bracket` | MHA-PD-21 | replaced by the one-piece formed spring-steel MHA-PD-14 latch hook, screwed to the support bar by two MHA-SH-VN-52 screws (MHA-PD-VN-59 when this entry was written) |
| retired | `vn-latch-hook-rivet` | MHA-VN-045 | no replacement: the one-piece MHA-PD-14 latch hook has no riveted joint |
| retired | `vn-knife-hanger-washer` (old 1/2-inch family) | MHA-VN-026 | retired with the former 90126A211 washer; the new #10 washer took category Number MHA-VN-060 (now MHA-SM-VN-54), not a revived VN-026 |
| retired | `vn-transgear-collar-cross-pin` | MHA-VN-037 | no replacement: the MHA-PD-22 drive collar's true D-bore carries the torque on the knob shaft's D-flat |
| retired | `ch-rocker-arm-tl-vise-stop` | MHA-CH-06-TL-01 | rocker shop fixture the rocker manufacturing route no longer uses; no registry, builder or drawing |
| retired | `ch-rocker-arm-tl-profile-fixture` | MHA-CH-06-TL-02 | rocker shop fixture the rocker manufacturing route no longer uses; no registry, builder or drawing |
| retired | `ch-rocker-arm-tl-diamond-pin` | MHA-CH-06-TL-03 | rocker shop fixture the rocker manufacturing route no longer uses; no registry, builder or drawing |
| retired | `ch-rocker-arm-tl-pivot-screw` | MHA-CH-06-TL-06 | rocker shop fixture the rocker manufacturing route no longer uses; no registry, builder or drawing |
| retired | `ch-rocker-arm-tl-pivot-washer` | MHA-CH-06-TL-07 | rocker shop fixture the rocker manufacturing route no longer uses; no registry, builder or drawing |
| retired | `ch-rocker-arm-tl-inspection-box` | MHA-CH-06-TL-08 | rocker shop fixture the rocker manufacturing route no longer uses; no registry, builder or drawing |
| retired | `ch-rocker-arm-tl-c-stop-bar` | MHA-CH-06-TL-09 | rocker shop fixture the rocker manufacturing route no longer uses; no registry, builder or drawing |
| added | `mg-vn-magnifying-bracket-screw` | MHA-MG-VN-53 | screws the MHA-MG-01 magnifying bracket to the MHA-SM-03 summing lever |
| added | `sm-vn-knife-mount-dowel` | MHA-SM-VN-53 | keys each MHA-SM-02 knife mount to the MHA-FR-02 crossbar |
| added | `mg-wheel-drum` | MHA-MG-10 | brass drum pressed on the MHA-MG-05 wheel spigot; carries the lever wire |
| added | `mg-vn-wheel-axle-back-washer` | MHA-MG-VN-54 | brass #10 washer between the MHA-MG-11 axle spacer and the MHA-MG-05 wheel hub |
| added | `mg-vn-wheel-axle-front-washer` | MHA-MG-VN-55 | brass #4 washer between the MHA-MG-05 wheel spigot face and the first MHA-MG-VN-52 nut; its Ø7.1 OD bears inside the Ø14.0 spigot end, clear of the MHA-MG-10 drum |
| added | `mg-wheel-axle-spacer` | MHA-MG-11 | brass sleeve on the MHA-MG-07 axle between the MHA-MG-08 wheel bar and the MHA-MG-VN-54 back washer; its length puts the MHA-MG-05 wheel's rim on the pen-rod line |
| added | `sm-gooseneck-spring-screw` | MHA-SM-04 | shop-turned 1/4-28 UNF slotted cheese-head screw clamps the counter spring's upper eye, seated on its plain Ø6.35 body, to the face of MHA-SM-01's solid end piece, in its blind 1/4-28 tap (owner rulings 2026-10-27 (#1951)), whose arm-end counterbore clears the screw's die run-out |
| added | `pd-vn-platen-clip-screw` | MHA-PD-VN-65 | four brass #2-56 fillister screws hold the MHA-PD-03 platen clip to the MHA-PD-02 platen in place of the MHA-PD-VN-52 fillister screws |
| added | `sm-vn-knife-hanger-washer` (new #10 family) | MHA-SM-VN-54 | 18-8 SAE washer 96659A104 under the modified #10-24 hex-head MHA-SM-VN-52 Bolt on the MHA-FR-02 faced top; functional stem reused, retired Number never reused |
| retired | `pn-pen-marker` | MHA-PN-03 | replaced by the purchased MHA-PN-VN-56 Sharpie marker |
| added | `pn-vn-pen-marker` | MHA-PN-VN-56 | purchased Sharpie permanent marker, fine point (regular size), used uncapped; its cap-seat grip lies in the MHA-PN-05 v-block groove |
| added | `pn-vn-pen-rod-set-screw` | MHA-PN-VN-52 | #4-40 x 3/16 cup-point set screw in the MHA-PN-05 v-block, locking the MHA-PN-04 pen rod's pivot end |
| added | `pn-vn-pen-adjust-nut` | MHA-PN-VN-53 | brass #0-80 jam nut on the MHA-PN-07 adjuster stud in the MHA-PN-04 pen rod's top |
| added | `pn-pen-adjust-screw` | MHA-PN-07 | turned brass #0-80 eye stud in the MHA-PN-04 pen rod's top, locked by the MHA-PN-VN-53 jam nut; the pen wire (now MHA-SH-VN-56 `PenWire`, then MHA-PN-VN-57) ties through its eye |
| added | `pn-vn-pen-hanger-nut` | MHA-PN-VN-54 | zinc-plated steel #8-32 hex nut on the strap front; holds the MHA-PN-02 pen hanger on the MHA-PN-VN-50 hanger screw through the strap's clearance hole |
| added | `pn-vn-pen-hanger-jam-nut` | MHA-PN-VN-55 | thin zinc-plated steel #8-32 hex nut jammed against the MHA-PN-VN-54 nut, locking the MHA-PN-VN-50 hanger screw |
| retired | `mg-lever-wire` | MHA-MG-09 | replaced by the purchased lever wire, MHA-MG-VN-56 when written and now MHA-SH-VN-56 `LeverWire` |
| retired | `pn-pen-wire` | MHA-PN-06 | replaced by the purchased pen wire, MHA-PN-VN-57 when written and now MHA-SH-VN-56 `PenWire` |
| added | `mg-vn-lever-wire` | MHA-MG-VN-56 | ASTM A228 music wire, 0.031 in, cut from McMaster-Carr 9666K56 coil; hooks on the MHA-MG-06 output fixture and wraps the MHA-MG-10 drum |
| added | `pn-vn-pen-wire` | MHA-PN-VN-57 | ASTM A228 music wire, 0.031 in, cut from the same McMaster-Carr 9666K56 coil; runs from the MHA-MG-05 wheel rim groove to the MHA-PN-07 adjuster stud's eye |
| added | `pd-vn-chain-connecting-link` | MHA-PD-VN-66 | McMaster 6261K108 clip-retained connecting link that joins the cut 6261K171 chain's two inner-link ends; MHA-PD-VN-51 keeps only the cut chain's 33 outer links |
| added | `pd-vn-transgear-pivot-shim` | MHA-PD-VN-67 | DIN 988 spring-steel shim 98055A098 (5 x 10 x 0.5) on the MHA-PD-VN-57 shoulder under its head, on the MHA-PD-VN-63 spring; restores the spring room the 9.5 MHA-PD-07 bar took when it grew rearward |
| retired | `ch-rocker-thrust-washer` | MHA-CH-09 | replaced by the purchased MHA-CH-VN-56 rocker thrust washer (owner, 2026-10-15: every washer is a purchased part) |
| added | `ch-vn-rocker-thrust-washer` | MHA-CH-VN-56 | carbon-steel ring shim, 1/4 ID x 3/8 OD x 0.031 in, McMaster-Carr 3088A429; one each end of the rocker bank on the MHA-CH-05 pivot shaft, the north one against the datum MHA-CH-08 ear |
| retired | `dt-crank-seat-washer` | MHA-DT-36 | deleted, owner ruling D1 2026-10-15: collar bears on the post boss |
| added | `ch-vn-bracket-hold-down-screw` | MHA-CH-VN-57 | McMaster 90280A196 #8-32 x 5/8 slotted narrow fillister, zinc-plated steel; one per MHA-CH-08 foot into MHA-FR-05's top-face seat (owner Q13c), so the transferred seat stays 11.5 thread / 14.7 drill; MHA-DT-VN-62 keeps the arbor pedestals |
| added | `ch-rocker-hub` | MHA-CH-12 | turned 1018 hub of the built-up MHA-CH-06 rocker arm (`component_of: ch-rocker-arm`); its Ø10.20 r6 land is pressed into the MHA-CH-13 strap's H7 hole, then the bore and length are finished on MHA-CH-06 |
| added | `ch-rocker-strap` | MHA-CH-13 | 1018 flat strap of the built-up MHA-CH-06 rocker arm (`component_of: ch-rocker-arm`); finished outline and 2.5 thickness with the Ø10.20 H7 hole for the MHA-CH-12 hub |
| added | `sm-vn-boss-hook-jam-nut` | MHA-SM-VN-55 | thin zinc-plated steel #10-24 narrow-profile hex nut jammed against the MHA-SM-03 boss top face, locking the MHA-SM-VN-50 counter anchor |
| added | `ch-anchor-jam-nut` | MHA-CH-14 | turned brass round #6-32 jam nut, notched across its driven face for a forked driver, jammed against the MHA-SM-03 plate underside on each MHA-CH-VN-51 channel anchor; round because a hex overruns the 7.06 anchor pitch |
| added | `ch-rocker-arm-tl-vn-oblique-rail` | MHA-CH-06-TL-VN-50 | HIWIN HGR15R linear rail cut to 440 (Motion Constrained 172270559990, special-order 7 holes at E 40), one under each oblique trammel jig carriage; bought fixture hardware modelled vendor-checked for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-carriage` | MHA-CH-06-TL-VN-51 | HIWIN HGH15CAZ0C linear guideway block (DigiKey/Midwest HGH-15-CA-Z0-C), one on each oblique trammel jig rail under a pivot block; bought fixture hardware modelled vendor-checked for the jig assembly |
| retired | `ch-rocker-arm-tl-vn-oblique-bearing` | MHA-CH-06-TL-VN-52 | 2026-10-23 plain-pivot simplification; owned 6200-2RS bearings remain shop stock without a jig identity; Number never reissued |
| added | `ch-rocker-arm-tl-vn-oblique-cl-dowel` | MHA-CH-06-TL-VN-53 | McMaster 98381A542 1/4 x 1 alloy-steel dowel (ASME B18.8.2, +.0001/+.0003), press-set above the actual riser in the oblique trammel jig carrier's CL hole; locates the rocker strap blank without standing above it; bought fixture hardware modelled for the jig assembly (was McMaster 91595A452 Ø6 x 20 m6 until 2026-10-31) |
| added | `ch-rocker-arm-tl-vn-oblique-leadscrew` | MHA-CH-06-TL-VN-54 | ZYLtech HW-SC-T8x2-600 Tr8x2 304 stainless lead screw, cut to 410; the oblique trammel jig's feed screw in two KP08 pillow blocks; bought fixture hardware modelled datasheet-built for the jig assembly |
| changed | `ch-rocker-arm-tl-vn-oblique-leadscrew-nut` | MHA-CH-06-TL-VN-55 | ZYLtech HW-SC-T8x2-NUT brass nut (included with screw); mounts to the integral TL-32 feed-block lug (retired 2026-11-01, below) |
| added | `ch-rocker-arm-tl-vn-oblique-pillow-block` | MHA-CH-06-TL-VN-56 | AMPEC KP08 pillow blocks (Bearings Direct) x2, one on each TL-28 end bracket, carrying the TL-VN-54 leadscrew; bought fixture hardware modelled datasheet-built for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-handwheel` | MHA-CH-06-TL-VN-57 | MISUMI HOK40-HC8 Ø40 knurled handwheel, revolving grip, Ø8 H8 through bore, 2 x M5 taps (one set screw supplied), on the TL-VN-54 leadscrew; bought fixture hardware modelled vendor-checked for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-hold-down-stud` | MHA-CH-06-TL-VN-58 | Precision Matthews 52PCCK-9/16-14mm kit 1/2-13 x 3 in STOCK studs x4, reworked at the unused upper free ends to 57.2 ±0.8 mm finished length; unchanged lower ends, loaded intervals, insertion and TL-20 table anchors; actual G ≥3 mm through both full hand sweeps and ≥one complete pitch beyond each seated nut with its full actual complete internal span engaged are required |
| added | `ch-rocker-arm-tl-vn-oblique-t-nut` | MHA-CH-06-TL-VN-59 | Precision Matthews 52PCCK-9/16-14mm kit 14 mm T-nuts x4, tapped 1/2-13, one under each TL-VN-58 stud; bought fixture hardware modelled datasheet-built for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-flange-nut` | MHA-CH-06-TL-VN-60 | Precision Matthews 52PCCK-9/16-14mm kit 1/2-13 flange nuts x4, one on each TL-VN-58 stud on the TL-20 base bar's top face; bought fixture hardware modelled datasheet-built for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-rail-screw` | MHA-CH-06-TL-VN-61 | McMaster 91251A197 #8-32 X 3/4 SHCS x14: holds an HGR15R rail to its TL-20 base bar, tapped THRU; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-bracket-screw` | MHA-CH-06-TL-VN-62 | McMaster 91251A196 #8-32 X 5/8 SHCS x8: holds a TL-28 end bracket (4 each) to the TL-20 base bar, up from the bar's underside into the bracket, tapped THRU; bought fixture hardware modelled for the jig assembly |
| retired | `ch-rocker-arm-tl-vn-oblique-block-screw` | MHA-CH-06-TL-VN-63 | 2026-10-23 integral feed block removes the separate bracket joint; Number never reissued |
| changed | `ch-rocker-arm-tl-vn-oblique-carriage-screw` | MHA-CH-06-TL-VN-64 | McMaster 91290A168 M4 X 20 SHCS x8, each cut to fit its counterbore floor at assembly: four each for TL-22 and TL-32 onto their HGH15CA carriages |
| changed | `ch-rocker-arm-tl-vn-oblique-kp08-screw` | MHA-CH-06-TL-VN-65 | McMaster 91251A150 #6-32 X 5/8 SHCS x4: holds KP08 blocks to the raised TL-28 end brackets |
| changed | `ch-rocker-arm-tl-vn-oblique-nut-screw` | MHA-CH-06-TL-VN-66 | McMaster 91251A113 #4-40 X 3/4 SHCS x2: holds the TL-27 feed nut to TL-32's lug through its loose holes, tapped THRU, heads directly on the brass (was Olander 4C50BHCA #4-40 X 1/2 BHCS x4 on the bought TL-VN-55 flange until 2026-11-01) |
| added | `ch-rocker-arm-tl-vn-oblique-riser-screw` | MHA-CH-06-TL-VN-67 | McMaster 91771A112 #4-40 X 5/8 flat head x4: holds the TL-24 riser to the TL-21 carrier, tapped THRU; seat the head and keep the factory tip unless actual interference prevents assembly; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-clamp-screw` | MHA-CH-06-TL-VN-68 | McMaster 91251A541 1/4-20 X 7/8 SHCS x1: the CR clamp, clamping the rocker-arm strap and the riser down on the TL-21 carrier, tapped THRU; used full length, its tip standing below the carrier clear of the pivot blocks, over the rails; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-lever-screw` | MHA-CH-06-TL-VN-69 | McMaster 91251A583 5/16-18 X 1 SHCS x2: holds the TL-26 feed lever to the TL-21 carrier, tapped THRU, each head on a TL-VN-71 wedge-lock pair; bought fixture hardware modelled for the jig assembly |
| retired | `ch-rocker-arm-tl-vn-oblique-block-washer` | MHA-CH-06-TL-VN-70 | 2026-10-23 integral feed block removes its only joint; Number never reissued |
| added | `ch-rocker-arm-tl-vn-oblique-lever-washer` | MHA-CH-06-TL-VN-71 | McMaster 91812A230 5/16 wedge-lock washer pair x2: one under each TL-VN-69 feed lever screw head on the TL-26 lever's top face, the mechanical lock for the screws that carry the operator's reversing push and pull on the lever (rule 23); bought fixture hardware modelled for the jig assembly |
| retired | `ch-rocker-arm-tl-vn-oblique-nut-washer` | MHA-CH-06-TL-VN-72 | the #4 flat washer under each MHA-CH-06-TL-VN-66 nut screw head; removed when the nut screws became button heads bearing directly on the nut's flange (owner ruling 2026-10-20); no registry, builder or drawing, and the Number is never reissued |
| retired | `ch-rocker-arm-tl-filing-button` | MHA-CH-06-TL-04 | standalone rocker shop fixture no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing |
| retired | `ch-rocker-arm-tl-filing-stud` | MHA-CH-06-TL-05 | standalone rocker shop fixture no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; any surviving hub-filing-button inventory geometry lives in `cad/process/shop/inventory.toml` without a CAD owner |
| retired | `ch-rocker-arm-tl-riser-block` | MHA-CH-06-TL-10 | standalone rocker shop fixture no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; any surviving riser-block inventory geometry lives in `cad/process/shop/inventory.toml` without a CAD owner |
| retired | `ch-rocker-arm-tl-strap-shim-stack` | MHA-CH-06-TL-11 | standalone rocker shop fixture no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; any surviving shim-stack inventory geometry lives in `cad/process/shop/inventory.toml` without a CAD owner |
| retired | `ch-rocker-arm-tl-filing-stand` | MHA-CH-06-TL-12 | standalone rocker shop fixture no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; any surviving filing-stand inventory geometry lives in `cad/process/shop/inventory.toml` without a CAD owner |
| retired | `ch-rocker-arm-tl-outline-template` | MHA-CH-06-TL-13 | standalone rocker gauge no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; the rocker profile clocking-error check it supplied stays with the rocker-arm profile check (`ch_rocker_arm_profile_check.py`), not with a template spec, and any surviving arm-outline-template inventory geometry lives in `cad/process/shop/inventory.toml` without a CAD owner |
| retired | `ch-rocker-arm-tl-trammel-pivot-block` | MHA-CH-06-TL-14 | standalone rocker trammel kit part no registered assembly references (tooling retirement 2026-10-21); the oblique trammel jig MHA-CH-06-TL-00 is the current rocker trammel; no registry, builder or drawing |
| retired | `ch-rocker-arm-tl-trammel-scriber-block` | MHA-CH-06-TL-15 | standalone rocker trammel kit part no registered assembly references (tooling retirement 2026-10-21); the oblique trammel jig MHA-CH-06-TL-00 is the current rocker trammel; no registry, builder or drawing |
| retired | `ch-rocker-arm-tl-trammel-scriber-point` | MHA-CH-06-TL-16 | standalone rocker trammel kit part no registered assembly references (tooling retirement 2026-10-21); the oblique trammel jig MHA-CH-06-TL-00 is the current rocker trammel; no registry, builder or drawing |
| retired | `ch-rocker-arm-tl-trammel-setting-bar` | MHA-CH-06-TL-17 | standalone rocker trammel gauge no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; any surviving setting-bar inventory geometry lives in `cad/process/shop/inventory.toml` without a CAD owner |
| retired | `ch-rocker-arm-tl-trammel-pivot-point` | MHA-CH-06-TL-18 | standalone rocker trammel kit part no registered assembly references (tooling retirement 2026-10-21); the oblique trammel jig MHA-CH-06-TL-00 is the current rocker trammel; no registry, builder or drawing |
| retired | `ch-rocker-arm-tl-trammel-pivot-plate` | MHA-CH-06-TL-19 | standalone rocker trammel kit part no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; any surviving pivot-plate inventory geometry lives in `cad/process/shop/inventory.toml` without a CAD owner |
| retired | `ch-pivot-bracket-tl-ledge` | MHA-CH-08-TL-01 | standalone pivot-bracket shop fixture no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; its print references and geometry in `cad/process/shop/inventory.toml` are historical provenance, not a CAD owner |
| retired | `ch-pivot-bracket-tl-angle-plate` | MHA-CH-08-TL-02 | standalone pivot-bracket shop fixture no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; its print references and geometry in `cad/process/shop/inventory.toml` are historical provenance, not a CAD owner |
| retired | `dt-cone-pivot-post-tl-bond-cradle` | MHA-DT-05-TL-01 | standalone cone-pivot-post S6 bond fixture no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; `cad/config/dimensions.yaml` and `cad/process/shop/inventory.toml` retain descriptive geometry only, not matched-seat/pin-top limits; those former limits remain historical at `fcfc947c4:cad/scripts/dt_cone_pivot_post_tl_bond_cradle_spec.py` and its drawing |
| retired | `dt-cone-pivot-post-tl-saw-cradle` | MHA-DT-05-TL-02 | standalone cone-pivot-post S10 saw fixture no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; its print references and geometry in `cad/process/shop/inventory.toml` are historical provenance, not a CAD owner |
| retired | `dt-cone-pivot-post-tl-cap-jaw-button` | MHA-DT-05-TL-03 | standalone cone-pivot-post S11 vise-hold fixture no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing; its print references and geometry in `cad/process/shop/inventory.toml` are historical provenance, not a CAD owner |
| retired | `dt-cone-pivot-post-tl-soft-jaw` | MHA-DT-05-TL-04 | standalone cone-pivot-post S11 vise-hold fixture no registered assembly references (tooling retirement 2026-10-21); no registry, builder or drawing |
| shared | `sh-vn-chain-link` | MHA-SH-VN-50 | 2026-10-20: McMaster 6261K171 chain members consolidated from `pd-vn-chain-inner-link` MHA-PD-VN-50 (`InnerLink`, 34 installed) and `pd-vn-chain-outer-link` MHA-PD-VN-51 (`OuterLink`, 33 installed); one cut 2 ft chain, closed by the parent-scoped MHA-PD-VN-66 connecting link; PD-VN-50 and PD-VN-51 reserved |
| shared | `sh-vn-brass-fillister-screw` | MHA-SH-VN-51 | 2026-10-20: McMaster 90114A511 consolidated from `dt-vn-fillister-screw` MHA-DT-VN-50, `fr-vn-fillister-screw` MHA-FR-VN-50 and `pd-vn-fillister-screw` MHA-PD-VN-52 (`Default`); those Numbers reserved |
| shared | `sh-vn-fillister-screw-90280a108` | MHA-SH-VN-52 | 2026-10-20: McMaster 90280A108 consolidated from `dt-vn-foot-screw` MHA-DT-VN-58, `dt-vn-swing-stop-screw` MHA-DT-VN-53 and `pd-vn-latch-hook-bracket-screw` MHA-PD-VN-59 (`Default`, the foot's unshifted stock frame; the swing-stop placement and application colours stay in its occurrences); those Numbers reserved |
| shared | `sh-vn-clamp-screw` | MHA-SH-VN-53 | 2026-10-20: McMaster 90280A201 consolidated from `mg-vn-clamp-screw` MHA-MG-VN-51 and `pd-vn-clamp-screw` MHA-PD-VN-53 (`Default`); those Numbers reserved |
| shared | `sh-vn-arbor-set-screw` | MHA-SH-VN-54 | 2026-10-20: McMaster 91375A106 consolidated from `ch-vn-arbor-set-screw` MHA-CH-VN-53 and `dt-vn-arbor-set-screw` MHA-DT-VN-64 (`Default`; alloy steel, Rockwell C45, black oxide unchanged); those Numbers reserved |
| shared | `sh-vn-thumb-screw` | MHA-SH-VN-55 | 2026-10-20: McMaster 91882A221 consolidated from `mg-vn-thumb-screw` MHA-MG-VN-50 and `ms-vn-thumb-screw` MHA-MS-VN-50 (`Default`); those Numbers reserved |
| shared | `sh-vn-music-wire` | MHA-SH-VN-56 | 2026-10-20: McMaster 9666K56 wire forms consolidated from `mg-vn-lever-wire` MHA-MG-VN-56 (`LeverWire`) and `pn-vn-pen-wire` MHA-PN-VN-57 (`PenWire`); one two-sheet reference package, still DO NOT RELEASE with developed cut lengths unmodelled; those Numbers reserved |
| shared | `sh-vn-clamping-kit-hardware` | MHA-SH-VN-57 | 2026-10-20: Precision Matthews 52PCCK-9/16-14mm kit members consolidated from `ch-rocker-arm-tl-vn-oblique-hold-down-stud` MHA-CH-06-TL-VN-58 (`HoldDownStud` x4), `ch-rocker-arm-tl-vn-oblique-t-nut` MHA-CH-06-TL-VN-59 (`TNut` x4) and `ch-rocker-arm-tl-vn-oblique-flange-nut` MHA-CH-06-TL-VN-60 (`FlangeNut` x4); `usage_scope: tooling`, jig only, never a machine BOM row; TL-VN-58 to TL-VN-60 reserved |
| retired | `ch-rocker-arm-tl-oblique-pivot-pin` | MHA-CH-06-TL-23 | 2026-10-23 purchased shoulder-screw pivot replaces the bearing cartridge; Number never reissued |
| retired | `ch-rocker-arm-tl-oblique-hub-pin` | MHA-CH-06-TL-25 | 2026-10-23 purchased gauge pin replaces the turned locator; Number never reissued |
| retired | `ch-rocker-arm-tl-oblique-nut-bracket` | MHA-CH-06-TL-29 | 2026-10-23 merged into TL-32; Number never reissued |
| retired | `ch-rocker-arm-tl-oblique-pivot-cap` | MHA-CH-06-TL-30 | 2026-10-23 shoulder-screw head provides lift capture; Number never reissued |
| retired | `ch-rocker-arm-tl-oblique-pivot-retainer` | MHA-CH-06-TL-31 | 2026-10-23 shoulder-screw head provides lift capture; Number never reissued |
| retired | `ch-rocker-arm-tl-vn-oblique-pivot-cap-screw` | MHA-CH-06-TL-VN-73 | 2026-10-23 cartridge removed; Number never reissued |
| retired | `ch-rocker-arm-tl-vn-oblique-pivot-clevis-pin` | MHA-CH-06-TL-VN-74 | 2026-10-23 cartridge removed; Number never reissued |
| retired | `ch-rocker-arm-tl-vn-oblique-pivot-cotter` | MHA-CH-06-TL-VN-75 | 2026-10-23 cartridge removed; Number never reissued |
| retired | `ch-rocker-arm-tl-vn-oblique-pivot-lock-wire` | MHA-CH-06-TL-VN-76 | 2026-10-23 cartridge removed; Number never reissued |
| added | `ch-rocker-arm-tl-oblique-feed-block` | MHA-CH-06-TL-32 | 2026-10-23 integral rail-1 block and nut lug from 6061 1 × 3-1/2 in bar |
| added | `ch-rocker-arm-tl-vn-oblique-pivot-screw` | MHA-CH-06-TL-VN-77 | Huyett BLTS40-0375-1500188P extended-thread shoulder screw x2, 3/8 × 1-1/2, 5/16-18, thread shop-cut to .570 (was McMaster 90323A492 until 2026-10-31) |
| added | `ch-rocker-arm-tl-vn-oblique-pivot-spacer` | MHA-CH-06-TL-VN-78 | AluminumSpacers.com AS62-18-40 6061 spacer x2, .382 ID × .625 OD × .625 (was McMaster 92871A359 until 2026-10-31) |
| added | `ch-rocker-arm-tl-vn-oblique-pivot-shim` | MHA-CH-06-TL-VN-79 | Huyett SHIM-0375-008 steel shim x10 nominal (five a support), 3/8 × 5/8 × .008; select fitting stock SHIM-0375-004/-008/-020 for measured running gap (was McMaster DIN 988 98055A118 until 2026-10-31) |
| added | `ch-rocker-arm-tl-vn-oblique-hub-pin` | MHA-CH-06-TL-VN-80 | McMaster 23065A855-23065A4 Class Z NO-GO .4000 plug gauge x1, 2 in supply, abrasive-cut to .79 and bonded (was McMaster 2281A11-6410N695 Ø10.2000 until 2026-10-31) |
| retired | `ch-rocker-arm-tl-vn-oblique-leadscrew-nut` | MHA-CH-06-TL-VN-55 | 2026-11-01 owner ruling (item 4): the shop-made TL-27 feed nut replaces the bought flange nut, so TL-32's lug needs no spigot recess; no registry, builder or drawing; Number never reissued |
| added | `ch-rocker-arm-tl-oblique-feed-nut` | MHA-CH-06-TL-27 | 2026-11-01 shop-made Tr8x2 RH nut from brass 360-H02 3/4 × 1-1/4 in bar, faced to .40, on two TL-VN-66 screws into TL-32's lug |
