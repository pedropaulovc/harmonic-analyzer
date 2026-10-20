# Subsystem identities

Current part and assembly identities are frozen in [`cad/config/parts/`](../config/parts/) and [`cad/config/assemblies/`](../config/assemblies/). Those registry files own the Number and canonical stem. Build scripts own geometry. [`cad/config/current-identity-map.json`](../config/current-identity-map.json) records the 2026-10-19 cutover to two-digit Numbers and parent-scoped vendor identities; [`cad/config/identity-migration-map.json`](../config/identity-migration-map.json) keeps the released v39 lookup used by the category cutover at `bfde892a5`. This guide explains both cutovers; it does not replace either source of truth.

## Naming and numbering

Use `<prefix>-<descriptive-name>` for native model and exported asset basenames, and `<prefix>_<descriptive_name>` for Python module and doit task stems. Assembly builders and drawing artefacts retain their `_assembly` or `-assembly` suffix. For example, `dt-drive-train.SLDASM` is built by `build_dt_drive_train_assembly.py`; its drawing artefact stem is `dt-drive-train-assembly`.

Drawing Numbers use `MHA-<CATEGORY>-<NN>`, with two-digit sequences. `00` is the category's assembly drawing; fabricated parts start at `01`. HA, CH, DT, FR, MG, MS, PD, PN and SM have assemblies. SH contains fabricated parts only. Numbers are stored in the registries, not recalculated when the graph changes. Configuration variants retain their existing qualifiers on the family Number, such as `MHA-DT-03-T006` for a cone-gear configuration: `T006` is a tooth count, not an identity sequence, so it keeps its three digits. Installed channel spring stretch variants retain the unqualified base Number.

Vendor parts are purchased finished parts. Supplier, SKU and commercial-process evidence decides that a part is a vendor part. Each vendor part belongs to the assembly that uses it directly. Its stem is the parent assembly's prefix, then `vn`, then the descriptive name, such as `dt-vn-cone-lock-knob`; a name that already began with the parent prefix drops the repeat, so the measuring stick's stop-plate screw is `ms-vn-stop-plate-screw`. Its Number puts `VN` after the parent's category and counts from `50` within that parent: `dt-vn-cone-lock-knob` is `MHA-DT-VN-51`. When several assemblies use one vendor family directly, each of those assemblies has its own vendor identity, registry row and native model. The identities may share one supplier and SKU geometry recipe; see [Vendor families used by several assemblies](#vendor-families-used-by-several-assemblies). Containment through a sub-assembly or the top assembly is not direct use.

Parent-scoped native parts keep separate identities even when they use the same purchased SKU. Shared physical dimensions live in pure-data `_mcmaster_<sku>.py` modules, not in a helper named after one consuming parent.

Shop fixtures, the shop-made tooling that holds or gauges one part while it is machined, carry their parent part's Number plus `-TL-<NN>`, sequenced per parent from `01`: `MHA-DT-05-TL-01` is the cone pivot post's bond cradle. The stem is the parent stem plus `-tl-<name>`, such as `dt-cone-pivot-post-tl-bond-cradle`. Fixture parts never enter a machine assembly or BOM, and the table's part counts exclude them. A fixture kit may have its own TL-numbered assembly, such as `ch-rocker-arm-tl-oblique-jig` (`MHA-CH-06-TL-00`, using the `00` assembly convention); it references only its fixture parts and never enters a machine assembly or BOM. Bought finished fixture hardware, such as dowels, screws and magnetic bases, is not modelled, except the oblique trammel jig's. Those bought parts are modelled as purchased parts (`process: purchased`) so the jig assembly can run native interference against them. Their direct parent assembly is the jig, `ch-rocker-arm-tl-oblique-jig` (`MHA-CH-06-TL-00`), but their stems and Numbers belong to the namespace of the fixture's parent part, the rocker arm `ch-rocker-arm` (`MHA-CH-06`): the stem is that part's stem plus `-tl-vn-<name>`, and the Number is its Number plus `-TL-VN-<NN>`, counted from `50`. `ch-rocker-arm-tl-vn-oblique-rail` is `MHA-CH-06-TL-VN-50`, and the set runs to `MHA-CH-06-TL-VN-72` (VN-72 retired, never reissued).

Components of a built-up part are the detail parts a finished part may be made from when its own drawing notes permit it (`BUILT_UP_PERMISSION_NOTE` in its notes module). They are ordinary machine parts: each takes the next free Number in its category and its own stem, such as `ch-rocker-hub` (MHA-CH-12) and `ch-rocker-strap` (MHA-CH-13) for the rocker arm MHA-CH-06, and the table's part counts include them. The finished part stays the assembly's part, so a component never enters an assembly or BOM. Its registry row instead names its parent's stem in `component_of`, and the coverage contract (`test_part_coverage.py`) counts it reachable through that parent and refuses a `component_of` parent whose notes do not permit the built-up route. A component's drawing gives it as supplied to the joint; sizes finished after joining print on the parent's drawing only.

| Prefix | Category | Fabricated parts | Vendor parts |
|---|---|---:|---:|
| `ha` / `HA` | Harmonic analyzer | 0 | 0 |
| `ch` / `CH` | Channel | 13 | 8 |
| `dt` / `DT` | Drive train | 35 | 19 |
| `fr` / `FR` | Frame | 5 | 5 |
| `mg` / `MG` | Magnifier | 10 | 7 |
| `pd` / `PD` | Paper drive | 23 | 18 |
| `pn` / `PN` | Pen | 5 | 8 |
| `ms` / `MS` | Measuring stick | 3 | 2 |
| `sm` / `SM` | Summing | 4 | 6 |
| `sh` / `SH` | Shared fabricated parts | 2 | 0 |

SH contains fabricated parts used directly by several assemblies, currently the front and back column clamps, `sh-column-clamp-front` (MHA-SH-01) and `sh-column-clamp-back` (MHA-SH-02). Each keeps one shared identity. The wheel axle nut, `mg-vn-wheel-axle-nut`, is a vendor part by commercial-process evidence. HA holds the top assembly only: its two former parts, the measuring stick and its stop, moved into the MS category on 2026-10-09 when the stop was re-derived as a block, a plate and stock screws inside their own `ms-measuring-stick` sub-assembly.

Purchased ANSI #25 inner, outer and connecting chain links and finished ISO 2338 m6 crank
hub dowel stock are vendor parts, including cut-to-length modifications. Pins machined
from raw drill rod remain owned by their subsystem.

Doit selection uses the underscore stem:

```powershell
uv run python -m doit part:dt_cone_gear
uv run python -m doit part:dt_vn_cone_lock_knob
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
  retains sheets 1–5 and appends sheet 6 for the complete BOM. Its 48 mm Number
  column and 118 mm description column form two 190 mm pieces, split using
  rebuilt native row heights. Every instruction sheet has a reference model
  view for title-block property links.
- [`draw_ch_channel_assembly.py`](../scripts/draw_ch_channel_assembly.py)
  retains its four sheets and complete parent-scoped vendor Numbers. On sheet 2,
  the exploded-view caption follows the rebuilt native BOM bottom, including
  wrapped rows, rather than an estimated row pitch. Its actual native note
  extent must leave at least 4 mm below the table and remain clear of the border
  and title block, including after the final rebuild.

Earlier selected-image page indices remain unchanged. Native note extents,
table growth and view outlines still determine containment; offline wrapping
budgets do not replace the native audit or complete-package visual review.



## Historical evidence

Dated reports, released packages, raw logs, source quotations and user-authored bench entries retain the identifiers, snapshot URLs and checksums they recorded. Their identifiers come from one of three epochs:

- v39 release identifiers: unprefixed stems with `MHA-NNN` part and `MHA-ANN` assembly Numbers, recorded in `identity-migration-map.json`.
- Category identifiers, current from `bfde892a5` (2026-10-02) until 2026-10-19: prefixed stems, three-digit `MHA-<CATEGORY>-<NNN>` Numbers such as `MHA-DT-005` and `MHA-DT-005-TL-01`, assembly Numbers ending `000`, and one machine-wide vendor category with `vn-` stems and `MHA-VN-<NNN>` Numbers.
- Current identifiers, from 2026-10-19, as described above.

Read older identifiers through the table below when locating a current model. Current instructions, registry references, commands and asset links use current identities. A migration notice on a historical document does not change the evidence or certify it against the current model.

## Identity migration table

The table translates every v39 and category identity to its current identity, including retired families, shop fixtures and assemblies. The v39 and category columns are lookup keys for historical evidence, not supported aliases for current commands or files. A family created after the v39 release has no v39 stem or Number (—). A category vendor family that several assemblies use directly has one row per current identity, so its v39 and category cells repeat. Every other category Number maps to the same sequence written with two digits: MHA-DT-005 is now MHA-DT-05, MHA-DT-000 is MHA-DT-00 and MHA-CH-006-TL-000 is MHA-CH-06-TL-00.

Retired Numbers keep their rows here for historical lookup and are never reissued; a retired machine or fixture Number stays reserved in its two-digit form. MHA-PD-21 `pd-latch-hook-bracket` (category MHA-PD-021, v39 MHA-170) and the category vendor family `vn-latch-hook-rivet` (MHA-VN-045, v39 MHA-175) have no registry, builder or drawing: the one-piece formed spring-steel latch hook MHA-PD-14 `pd-latch-hook` replaces the bracket, its rivets and the old riveted strip, and screws to the support bar with the two MHA-PD-VN-59 screws. The old 1/2-inch `vn-knife-hanger-washer` (MHA-VN-026, v39 MHA-131) remains retired. The #10 18-8 washer that replaced it took the new category Number MHA-VN-060 under the same functional stem and is now `sm-vn-knife-hanger-washer`, MHA-SM-VN-54; it did not revive VN-026. `sm-vn-knife-hanger-stud` (MHA-SM-VN-52, category MHA-VN-024) keeps the drawing title **Bolt**; it is made by cutting #10-24 hex-head stock 92314A253 and is seated on the new washer on the MHA-FR-02 faced top. The former #6 socket-head/counterbore-floor route is obsolete. The category vendor family `vn-transgear-collar-cross-pin` (MHA-VN-037, v39 MHA-154) is retired: the true D-bore of the MHA-PD-22 drive collar carries the torque on the knob shaft's D-flat, so no front cross-pin remains. MHA-PN-03 `pn-pen-marker` (category MHA-PN-003, v39 MHA-050) is retired: the pen is a purchased Sharpie Fine Point, `pn-vn-pen-marker` MHA-PN-VN-56, not a turned brass barrel. Retired category vendor Numbers (MHA-VN-008, MHA-VN-026, MHA-VN-037 and MHA-VN-045) have no current form.

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
| retired part | `lever-wire` | MHA-115 | `mg-lever-wire` | MHA-MG-009 | — (replaced by `mg-vn-lever-wire`, MHA-MG-VN-56) | MHA-MG-09 (retired; never reissued) |
| part | — | — | `mg-wheel-drum` | MHA-MG-010 | `mg-wheel-drum` | MHA-MG-10 |
| part | — | — | `mg-wheel-axle-spacer` | MHA-MG-011 | `mg-wheel-axle-spacer` | MHA-MG-11 |
| part | `chain-inner-link` | MHA-006 | `vn-chain-inner-link` | MHA-VN-002 | `pd-vn-chain-inner-link` | MHA-PD-VN-50 |
| part | `chain-outer-link` | MHA-007 | `vn-chain-outer-link` | MHA-VN-003 | `pd-vn-chain-outer-link` | MHA-PD-VN-51 |
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
| retired part | `pen-wire` | MHA-100 | `pn-pen-wire` | MHA-PN-006 | — (replaced by `pn-vn-pen-wire`, MHA-PN-VN-57) | MHA-PN-06 (retired; never reissued) |
| part | — | — | `pn-pen-adjust-screw` | MHA-PN-007 | `pn-pen-adjust-screw` | MHA-PN-07 |
| part | `gooseneck` | MHA-032 | `sm-gooseneck` | MHA-SM-001 | `sm-gooseneck` | MHA-SM-01 |
| part | `knife-mount` | MHA-037 | `sm-knife-mount` | MHA-SM-002 | `sm-knife-mount` | MHA-SM-02 |
| part | `summing-lever` | MHA-073 | `sm-summing-lever` | MHA-SM-003 | `sm-summing-lever` | MHA-SM-03 |
| part | — | — | `sm-gooseneck-spring-screw` | MHA-SM-004 | `sm-gooseneck-spring-screw` | MHA-SM-04 |
| part | `boss-hook` | MHA-005 | `vn-boss-hook` | MHA-VN-001 | `sm-vn-boss-hook` | MHA-SM-VN-50 |
| part | `channel-spring-installed` | MHA-011 | `vn-channel-spring-installed` | MHA-VN-004 | `ch-vn-channel-spring-installed` | MHA-CH-VN-50 |
| part | `counter-spring` | MHA-019 | `vn-counter-spring` | MHA-VN-005 | `sm-vn-counter-spring` | MHA-SM-VN-51 |
| part | `fillister-screw` | MHA-030 | `vn-fillister-screw` | MHA-VN-006 | `dt-vn-fillister-screw` | MHA-DT-VN-50 |
| part | `fillister-screw` | MHA-030 | `vn-fillister-screw` | MHA-VN-006 | `fr-vn-fillister-screw` | MHA-FR-VN-50 |
| part | `fillister-screw` | MHA-030 | `vn-fillister-screw` | MHA-VN-006 | `pd-vn-fillister-screw` | MHA-PD-VN-52 |
| part | `hanger-screw` | MHA-034 | `vn-hanger-screw` | MHA-VN-007 | `pn-vn-hanger-screw` | MHA-PN-VN-50 |
| retired part | `hex-bolt` | MHA-036 | `vn-hex-bolt` | MHA-VN-008 | — | — (retired; MHA-VN-008 never reissued) |
| part | `lag-screw` | MHA-039 | `vn-lag-screw` | MHA-VN-009 | `fr-vn-lag-screw` | MHA-FR-VN-51 |
| part | `pen-set-screw` | MHA-052 | `vn-pen-set-screw` | MHA-VN-010 | `pn-vn-pen-set-screw` | MHA-PN-VN-51 |
| part | `thumb-screw` | MHA-075 | `vn-thumb-screw` | MHA-VN-011 | `mg-vn-thumb-screw` | MHA-MG-VN-50 |
| part | `thumb-screw` | MHA-075 | `vn-thumb-screw` | MHA-VN-011 | `ms-vn-thumb-screw` | MHA-MS-VN-50 |
| part | `spring-hook` | MHA-090 | `vn-spring-hook` | MHA-VN-012 | `ch-vn-spring-hook` | MHA-CH-VN-51 |
| part | `cone-lock-knob` | MHA-093 | `vn-cone-lock-knob` | MHA-VN-013 | `dt-vn-cone-lock-knob` | MHA-DT-VN-51 |
| part | `cone-pivot-screw` | MHA-094 | `vn-cone-pivot-screw` | MHA-VN-014 | `dt-vn-cone-pivot-screw` | MHA-DT-VN-52 |
| part | `swing-stop-screw` | MHA-095 | `vn-swing-stop-screw` | MHA-VN-015 | `dt-vn-swing-stop-screw` | MHA-DT-VN-53 |
| part | `cone-tip-collar` | MHA-096 | `vn-cone-tip-collar` | MHA-VN-016 | `dt-vn-cone-tip-collar` | MHA-DT-VN-54 |
| part | `cone-tip-adjuster` | MHA-097 | `vn-cone-tip-adjuster` | MHA-VN-017 | `dt-vn-cone-tip-adjuster` | MHA-DT-VN-55 |
| part | `cone-tip-pinch-screw` | MHA-098 | `vn-cone-tip-pinch-screw` | MHA-VN-018 | `dt-vn-cone-tip-pinch-screw` | MHA-DT-VN-56 |
| part | `slotted-screw` | MHA-101 | `vn-slotted-screw` | MHA-VN-019 | `dt-vn-slotted-screw` | MHA-DT-VN-57 |
| part | `foot-screw` | MHA-103 | `vn-foot-screw` | MHA-VN-020 | `dt-vn-foot-screw` | MHA-DT-VN-58 |
| part | `clamp-screw` | MHA-107 | `vn-clamp-screw` | MHA-VN-021 | `mg-vn-clamp-screw` | MHA-MG-VN-51 |
| part | `clamp-screw` | MHA-107 | `vn-clamp-screw` | MHA-VN-021 | `pd-vn-clamp-screw` | MHA-PD-VN-53 |
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
| part | `arbor-set-screw` | MHA-147 | `vn-arbor-set-screw` | MHA-VN-034 | `ch-vn-arbor-set-screw` | MHA-CH-VN-53 |
| part | `arbor-set-screw` | MHA-147 | `vn-arbor-set-screw` | MHA-VN-034 | `dt-vn-arbor-set-screw` | MHA-DT-VN-64 |
| part | `keeper-chain` | MHA-149 | `vn-keeper-chain` | MHA-VN-035 | `dt-vn-keeper-chain` | MHA-DT-VN-65 |
| part | `keeper-chain-link` | MHA-150 | `vn-keeper-chain-link` | MHA-VN-036 | `dt-vn-keeper-chain-link` | MHA-DT-VN-66 |
| retired part | `transgear-collar-cross-pin` | MHA-154 | `vn-transgear-collar-cross-pin` | MHA-VN-037 | — | — (retired; MHA-VN-037 never reissued) |
| part | `transgear-knob-drive-pin` | MHA-155 | `vn-transgear-knob-drive-pin` | MHA-VN-038 | `pd-vn-transgear-knob-drive-pin` | MHA-PD-VN-54 |
| part | `transgear-disc-screw` | MHA-161 | `vn-transgear-disc-screw` | MHA-VN-039 | `pd-vn-transgear-disc-screw` | MHA-PD-VN-55 |
| part | `transgear-arm-plate-screw` | MHA-166 | `vn-transgear-arm-plate-screw` | MHA-VN-040 | `pd-vn-transgear-arm-plate-screw` | MHA-PD-VN-56 |
| part | `transgear-pivot-screw` | MHA-168 | `vn-transgear-pivot-screw` | MHA-VN-041 | `pd-vn-transgear-pivot-screw` | MHA-PD-VN-57 |
| part | `transgear-latch-pin` | MHA-169 | `vn-transgear-latch-pin` | MHA-VN-042 | `pd-vn-transgear-latch-pin` | MHA-PD-VN-58 |
| part | `latch-hook-bracket-screw` | MHA-171 | `vn-latch-hook-bracket-screw` | MHA-VN-043 | `pd-vn-latch-hook-bracket-screw` | MHA-PD-VN-59 |
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
| part | — | — | `vn-lever-wire` | MHA-VN-066 | `mg-vn-lever-wire` | MHA-MG-VN-56 |
| part | — | — | `vn-pen-wire` | MHA-VN-067 | `pn-vn-pen-wire` | MHA-PN-VN-57 |
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
| tooling part | — | — | `ch-rocker-arm-tl-filing-button` | MHA-CH-006-TL-04 | `ch-rocker-arm-tl-filing-button` | MHA-CH-06-TL-04 |
| tooling part | — | — | `ch-rocker-arm-tl-filing-stud` | MHA-CH-006-TL-05 | `ch-rocker-arm-tl-filing-stud` | MHA-CH-06-TL-05 |
| retired tooling part | — | — | `ch-rocker-arm-tl-pivot-screw` | MHA-CH-006-TL-06 | — | MHA-CH-06-TL-06 (retired; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-pivot-washer` | MHA-CH-006-TL-07 | — | MHA-CH-06-TL-07 (retired; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-inspection-box` | MHA-CH-006-TL-08 | — | MHA-CH-06-TL-08 (retired; never reissued) |
| retired tooling part | — | — | `ch-rocker-arm-tl-c-stop-bar` | MHA-CH-006-TL-09 | — | MHA-CH-06-TL-09 (retired; never reissued) |
| tooling part | — | — | `ch-rocker-arm-tl-riser-block` | MHA-CH-006-TL-10 | `ch-rocker-arm-tl-riser-block` | MHA-CH-06-TL-10 |
| tooling part | — | — | `ch-rocker-arm-tl-strap-shim-stack` | MHA-CH-006-TL-11 | `ch-rocker-arm-tl-strap-shim-stack` | MHA-CH-06-TL-11 |
| tooling part | — | — | `ch-rocker-arm-tl-filing-stand` | MHA-CH-006-TL-12 | `ch-rocker-arm-tl-filing-stand` | MHA-CH-06-TL-12 |
| tooling part | — | — | `ch-rocker-arm-tl-outline-template` | MHA-CH-006-TL-13 | `ch-rocker-arm-tl-outline-template` | MHA-CH-06-TL-13 |
| tooling part | — | — | `ch-rocker-arm-tl-trammel-pivot-block` | MHA-CH-006-TL-14 | `ch-rocker-arm-tl-trammel-pivot-block` | MHA-CH-06-TL-14 |
| tooling part | — | — | `ch-rocker-arm-tl-trammel-scriber-block` | MHA-CH-006-TL-15 | `ch-rocker-arm-tl-trammel-scriber-block` | MHA-CH-06-TL-15 |
| tooling part | — | — | `ch-rocker-arm-tl-trammel-scriber-point` | MHA-CH-006-TL-16 | `ch-rocker-arm-tl-trammel-scriber-point` | MHA-CH-06-TL-16 |
| tooling part | — | — | `ch-rocker-arm-tl-trammel-setting-bar` | MHA-CH-006-TL-17 | `ch-rocker-arm-tl-trammel-setting-bar` | MHA-CH-06-TL-17 |
| tooling part | — | — | `ch-rocker-arm-tl-trammel-pivot-point` | MHA-CH-006-TL-18 | `ch-rocker-arm-tl-trammel-pivot-point` | MHA-CH-06-TL-18 |
| tooling part | — | — | `ch-rocker-arm-tl-trammel-pivot-plate` | MHA-CH-006-TL-19 | `ch-rocker-arm-tl-trammel-pivot-plate` | MHA-CH-06-TL-19 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-base-bar` | MHA-CH-006-TL-20 | `ch-rocker-arm-tl-oblique-base-bar` | MHA-CH-06-TL-20 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-carrier` | MHA-CH-006-TL-21 | `ch-rocker-arm-tl-oblique-carrier` | MHA-CH-06-TL-21 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-pivot-block` | MHA-CH-006-TL-22 | `ch-rocker-arm-tl-oblique-pivot-block` | MHA-CH-06-TL-22 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-pivot-pin` | MHA-CH-006-TL-23 | `ch-rocker-arm-tl-oblique-pivot-pin` | MHA-CH-06-TL-23 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-riser` | MHA-CH-006-TL-24 | `ch-rocker-arm-tl-oblique-riser` | MHA-CH-06-TL-24 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-hub-pin` | MHA-CH-006-TL-25 | `ch-rocker-arm-tl-oblique-hub-pin` | MHA-CH-06-TL-25 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-feed-lever` | MHA-CH-006-TL-26 | `ch-rocker-arm-tl-oblique-feed-lever` | MHA-CH-06-TL-26 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-end-bracket` | MHA-CH-006-TL-28 | `ch-rocker-arm-tl-oblique-end-bracket` | MHA-CH-06-TL-28 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-nut-bracket` | MHA-CH-006-TL-29 | `ch-rocker-arm-tl-oblique-nut-bracket` | MHA-CH-06-TL-29 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-rail` | MHA-CH-006-TL-30 | `ch-rocker-arm-tl-vn-oblique-rail` | MHA-CH-06-TL-VN-50 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-carriage` | MHA-CH-006-TL-31 | `ch-rocker-arm-tl-vn-oblique-carriage` | MHA-CH-06-TL-VN-51 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-bearing` | MHA-CH-006-TL-32 | `ch-rocker-arm-tl-vn-oblique-bearing` | MHA-CH-06-TL-VN-52 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-cl-dowel` | MHA-CH-006-TL-33 | `ch-rocker-arm-tl-vn-oblique-cl-dowel` | MHA-CH-06-TL-VN-53 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-leadscrew` | MHA-CH-006-TL-34 | `ch-rocker-arm-tl-vn-oblique-leadscrew` | MHA-CH-06-TL-VN-54 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-leadscrew-nut` | MHA-CH-006-TL-35 | `ch-rocker-arm-tl-vn-oblique-leadscrew-nut` | MHA-CH-06-TL-VN-55 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-pillow-block` | MHA-CH-006-TL-36 | `ch-rocker-arm-tl-vn-oblique-pillow-block` | MHA-CH-06-TL-VN-56 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-handwheel` | MHA-CH-006-TL-37 | `ch-rocker-arm-tl-vn-oblique-handwheel` | MHA-CH-06-TL-VN-57 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-hold-down-stud` | MHA-CH-006-TL-38 | `ch-rocker-arm-tl-vn-oblique-hold-down-stud` | MHA-CH-06-TL-VN-58 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-t-nut` | MHA-CH-006-TL-39 | `ch-rocker-arm-tl-vn-oblique-t-nut` | MHA-CH-06-TL-VN-59 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-flange-nut` | MHA-CH-006-TL-40 | `ch-rocker-arm-tl-vn-oblique-flange-nut` | MHA-CH-06-TL-VN-60 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-rail-screw` | MHA-CH-006-TL-41 | `ch-rocker-arm-tl-vn-oblique-rail-screw` | MHA-CH-06-TL-VN-61 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-bracket-screw` | MHA-CH-006-TL-42 | `ch-rocker-arm-tl-vn-oblique-bracket-screw` | MHA-CH-06-TL-VN-62 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-block-screw` | MHA-CH-006-TL-43 | `ch-rocker-arm-tl-vn-oblique-block-screw` | MHA-CH-06-TL-VN-63 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-carriage-screw` | MHA-CH-006-TL-44 | `ch-rocker-arm-tl-vn-oblique-carriage-screw` | MHA-CH-06-TL-VN-64 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-kp08-screw` | MHA-CH-006-TL-45 | `ch-rocker-arm-tl-vn-oblique-kp08-screw` | MHA-CH-06-TL-VN-65 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-nut-screw` | MHA-CH-006-TL-46 | `ch-rocker-arm-tl-vn-oblique-nut-screw` | MHA-CH-06-TL-VN-66 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-riser-screw` | MHA-CH-006-TL-47 | `ch-rocker-arm-tl-vn-oblique-riser-screw` | MHA-CH-06-TL-VN-67 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-clamp-screw` | MHA-CH-006-TL-48 | `ch-rocker-arm-tl-vn-oblique-clamp-screw` | MHA-CH-06-TL-VN-68 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-lever-screw` | MHA-CH-006-TL-49 | `ch-rocker-arm-tl-vn-oblique-lever-screw` | MHA-CH-06-TL-VN-69 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-block-washer` | MHA-CH-006-TL-50 | `ch-rocker-arm-tl-vn-oblique-block-washer` | MHA-CH-06-TL-VN-70 |
| tooling part | — | — | `ch-rocker-arm-tl-oblique-lever-washer` | MHA-CH-006-TL-51 | `ch-rocker-arm-tl-vn-oblique-lever-washer` | MHA-CH-06-TL-VN-71 |
| tooling part | — | — | `ch-pivot-bracket-tl-ledge` | MHA-CH-008-TL-01 | `ch-pivot-bracket-tl-ledge` | MHA-CH-08-TL-01 |
| tooling part | — | — | `ch-pivot-bracket-tl-angle-plate` | MHA-CH-008-TL-02 | `ch-pivot-bracket-tl-angle-plate` | MHA-CH-08-TL-02 |
| tooling part | — | — | `dt-cone-pivot-post-tl-bond-cradle` | MHA-DT-005-TL-01 | `dt-cone-pivot-post-tl-bond-cradle` | MHA-DT-05-TL-01 |
| tooling part | — | — | `dt-cone-pivot-post-tl-saw-cradle` | MHA-DT-005-TL-02 | `dt-cone-pivot-post-tl-saw-cradle` | MHA-DT-05-TL-02 |
| tooling part | — | — | `dt-cone-pivot-post-tl-cap-jaw-button` | MHA-DT-005-TL-03 | `dt-cone-pivot-post-tl-cap-jaw-button` | MHA-DT-05-TL-03 |
| tooling part | — | — | `dt-cone-pivot-post-tl-soft-jaw` | MHA-DT-005-TL-04 | `dt-cone-pivot-post-tl-soft-jaw` | MHA-DT-05-TL-04 |
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

### Vendor families used by several assemblies

At the 2026-10-19 cutover, four category vendor families were in direct use by more than one assembly. Each consuming assembly now has its own identity:

| Category stem | Category Number | Current identities |
|---|---|---|
| `vn-fillister-screw` | MHA-VN-006 | `dt-vn-fillister-screw` MHA-DT-VN-50 (in `dt-drive-train`); `fr-vn-fillister-screw` MHA-FR-VN-50 (in `fr-frame`); `pd-vn-fillister-screw` MHA-PD-VN-52 (in `pd-paper-drive`) |
| `vn-thumb-screw` | MHA-VN-011 | `mg-vn-thumb-screw` MHA-MG-VN-50 (in `mg-magnifier`); `ms-vn-thumb-screw` MHA-MS-VN-50 (in `ms-measuring-stick`) |
| `vn-clamp-screw` | MHA-VN-021 | `mg-vn-clamp-screw` MHA-MG-VN-51 (in `mg-magnifier`); `pd-vn-clamp-screw` MHA-PD-VN-53 (in `pd-paper-drive`) |
| `vn-arbor-set-screw` | MHA-VN-034 | `ch-vn-arbor-set-screw` MHA-CH-VN-53 (in `ch-channel`); `dt-vn-arbor-set-screw` MHA-DT-VN-64 (in `dt-drive-train`) |

## Changes after the category cutover

A retired Number is never reused. A family added after a cutover takes the next free Number in its namespace: the next fabricated Number in its category, the next vendor Number from `50` under its direct parent assembly, or the next TL Number under its fixture's parent part. It has no v39 stem or Number. This log uses current stems and Numbers. Retired machine and fixture Numbers appear in their reserved two-digit form; retired category vendor families keep their category stem and Number, which have no current form. The table above gives each family's earlier identities.

| Change | Stem | Number | Note |
|---|---|---|---|
| retired | `pd-chain-sprocket` | MHA-PD-01 | orphan removed from assemblies in `29025dd34`; superseded by the MHA-PD-09 `pd-transgear-removable` sprocket configurations (#68; delivery #507 retired) |
| retired | `vn-hex-bolt` | MHA-VN-008 | orphan removed from the frame in `2ab7dc109`; no assembly uses this family (delivery #543 retired) |
| retired | `pd-latch-hook-bracket` | MHA-PD-21 | replaced by the one-piece formed spring-steel MHA-PD-14 latch hook, screwed to the support bar by the two MHA-PD-VN-59 screws |
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
| added | `sm-gooseneck-spring-screw` | MHA-SM-04 | shop-turned slotted fillister screw clamps the counter spring's upper eye to MHA-SM-01's brazed, #6-32 through-tapped end plug |
| added | `pd-vn-platen-clip-screw` | MHA-PD-VN-65 | four brass #2-56 fillister screws hold the MHA-PD-03 platen clip to the MHA-PD-02 platen in place of the MHA-PD-VN-52 fillister screws |
| added | `sm-vn-knife-hanger-washer` (new #10 family) | MHA-SM-VN-54 | 18-8 SAE washer 96659A104 under the modified #10-24 hex-head MHA-SM-VN-52 Bolt on the MHA-FR-02 faced top; functional stem reused, retired Number never reused |
| retired | `pn-pen-marker` | MHA-PN-03 | replaced by the purchased MHA-PN-VN-56 Sharpie marker |
| added | `pn-vn-pen-marker` | MHA-PN-VN-56 | purchased Sharpie permanent marker, fine point (regular size), used uncapped; its cap-seat grip lies in the MHA-PN-05 v-block groove |
| added | `pn-vn-pen-rod-set-screw` | MHA-PN-VN-52 | #4-40 x 3/16 cup-point set screw in the MHA-PN-05 v-block, locking the MHA-PN-04 pen rod's pivot end |
| added | `pn-vn-pen-adjust-nut` | MHA-PN-VN-53 | brass #0-80 jam nut on the MHA-PN-07 adjuster stud in the MHA-PN-04 pen rod's top |
| added | `pn-pen-adjust-screw` | MHA-PN-07 | turned brass #0-80 eye stud in the MHA-PN-04 pen rod's top, locked by the MHA-PN-VN-53 jam nut; the MHA-PN-VN-57 pen wire ties through its eye |
| added | `pn-vn-pen-hanger-nut` | MHA-PN-VN-54 | zinc-plated steel #8-32 hex nut on the strap front; holds the MHA-PN-02 pen hanger on the MHA-PN-VN-50 hanger screw through the strap's clearance hole |
| added | `pn-vn-pen-hanger-jam-nut` | MHA-PN-VN-55 | thin zinc-plated steel #8-32 hex nut jammed against the MHA-PN-VN-54 nut, locking the MHA-PN-VN-50 hanger screw |
| retired | `mg-lever-wire` | MHA-MG-09 | replaced by the purchased MHA-MG-VN-56 lever wire |
| retired | `pn-pen-wire` | MHA-PN-06 | replaced by the purchased MHA-PN-VN-57 pen wire |
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
| added | `ch-rocker-arm-tl-vn-oblique-bearing` | MHA-CH-06-TL-VN-52 | McMaster 5972K41 6200-2RS bearings, a pair pressed into each oblique trammel jig pivot block; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-cl-dowel` | MHA-CH-06-TL-VN-53 | McMaster 91595A452 Ø6 x 20 m6 dowel, press-set above the actual riser in the oblique trammel jig carrier's CL hole; locates the rocker strap blank without standing above it; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-leadscrew` | MHA-CH-06-TL-VN-54 | ZYLtech HW-SC-T8x2-600 Tr8x2 304 stainless lead screw, cut to 410; the oblique trammel jig's feed screw in two KP08 pillow blocks; bought fixture hardware modelled datasheet-built for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-leadscrew-nut` | MHA-CH-06-TL-VN-55 | ZYLtech HW-SC-T8x2-NUT Tr8x2 brass flange nut (ships with HW-SC-T8x2-600), screwed to the TL-29 nut bracket; bought fixture hardware modelled datasheet-built for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-pillow-block` | MHA-CH-06-TL-VN-56 | AMPEC KP08 pillow blocks (Bearings Direct) x2, one on each TL-28 end bracket, carrying the TL-VN-54 leadscrew; bought fixture hardware modelled datasheet-built for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-handwheel` | MHA-CH-06-TL-VN-57 | MISUMI HOK40-HC8 Ø40 knurled handwheel, revolving grip, Ø8 H8 through bore, 2 x M5 taps (one set screw supplied), on the TL-VN-54 leadscrew; bought fixture hardware modelled vendor-checked for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-hold-down-stud` | MHA-CH-06-TL-VN-58 | Precision Matthews 52PCCK-9/16-14mm kit 1/2-13 x 3 in studs x4, holding the TL-20 base bars down to the mill table; bought fixture hardware modelled datasheet-built for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-t-nut` | MHA-CH-06-TL-VN-59 | Precision Matthews 52PCCK-9/16-14mm kit 14 mm T-nuts x4, tapped 1/2-13, one under each TL-VN-58 stud; bought fixture hardware modelled datasheet-built for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-flange-nut` | MHA-CH-06-TL-VN-60 | Precision Matthews 52PCCK-9/16-14mm kit 1/2-13 flange nuts x4, one on each TL-VN-58 stud on the TL-20 base bar's top face; bought fixture hardware modelled datasheet-built for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-rail-screw` | MHA-CH-06-TL-VN-61 | McMaster 91251A197 #8-32 X 3/4 SHCS x14: holds an HGR15R rail to its TL-20 base bar, tapped THRU; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-bracket-screw` | MHA-CH-06-TL-VN-62 | McMaster 91251A196 #8-32 X 5/8 SHCS x8: holds a TL-28 end bracket (4 each) to the TL-20 base bar, up from the bar's underside into the bracket, tapped THRU; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-block-screw` | MHA-CH-06-TL-VN-63 | McMaster 91251A188 #8-32 X 1-7/8 SHCS x2: holds the TL-29 nut bracket to TL-22 pivot block 1, into a blind tap, each head on a TL-VN-70 wedge-lock pair; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-carriage-screw` | MHA-CH-06-TL-VN-64 | McMaster 91290A168 M4 X 20 SHCS x8: holds a TL-22 pivot block to its HGH15CA carriage (the carriage's M4 x 5 holes); bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-kp08-screw` | MHA-CH-06-TL-VN-65 | McMaster 91251A150 #6-32 X 5/8 SHCS x4: holds a KP08 pillow block to its TL-28 end bracket, tapped THRU; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-nut-screw` | MHA-CH-06-TL-VN-66 | Olander 4C50BHCA #4-40 X 1/2 BHCS x4 (McMaster 91255A110 cross-reference): holds the Tr8 flanged leadscrew nut to the TL-29 nut bracket, into blind taps spotted from the nut's own flange holes, each button head directly on the flange; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-riser-screw` | MHA-CH-06-TL-VN-67 | McMaster 91771A112 #4-40 X 5/8 flat head x4: holds the TL-24 riser to the TL-21 carrier, tapped THRU; seat the head and keep the factory tip unless actual interference prevents assembly; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-clamp-screw` | MHA-CH-06-TL-VN-68 | McMaster 91251A541 1/4-20 X 7/8 SHCS x1: the CR clamp, clamping the rocker-arm strap and the riser down on the TL-21 carrier, tapped THRU; used full length, its tip standing below the carrier clear of the pivot blocks, over the rails; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-lever-screw` | MHA-CH-06-TL-VN-69 | McMaster 91251A583 5/16-18 X 1 SHCS x2: holds the TL-26 feed lever to the TL-21 carrier, tapped THRU, each head on a TL-VN-71 wedge-lock pair; bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-block-washer` | MHA-CH-06-TL-VN-70 | McMaster 91812A215 #8 wedge-lock washer pair x2: one under each TL-VN-63 block screw head on the floor of TL-22's counterbore, the mechanical lock for the screws that carry the leadscrew's reversing thrust (rule 23); bought fixture hardware modelled for the jig assembly |
| added | `ch-rocker-arm-tl-vn-oblique-lever-washer` | MHA-CH-06-TL-VN-71 | McMaster 91812A230 5/16 wedge-lock washer pair x2: one under each TL-VN-69 feed lever screw head on the TL-26 lever's top face, the mechanical lock for the screws that carry the operator's reversing push and pull on the lever (rule 23); bought fixture hardware modelled for the jig assembly |
| retired | `ch-rocker-arm-tl-vn-oblique-nut-washer` | MHA-CH-06-TL-VN-72 | the #4 flat washer under each MHA-CH-06-TL-VN-66 nut screw head; removed when the nut screws became button heads bearing directly on the nut's flange (owner ruling 2026-10-20); no registry, builder or drawing, and the Number is never reissued |
