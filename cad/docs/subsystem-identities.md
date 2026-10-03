# Subsystem identities

Current part and assembly identities are frozen in [`cad/config/parts/`](../config/parts/) and [`cad/config/assemblies/`](../config/assemblies/). Those registry files own the Number and canonical stem. Build scripts own geometry. This guide records the identity cutover from `bfde892a5`; it does not replace either source of truth.

## Naming and numbering

Use `<prefix>-<descriptive-name>` for native model and exported asset basenames, and `<prefix>_<descriptive_name>` for Python module and doit task stems. Assembly builders and drawing artefacts retain their `_assembly` or `-assembly` suffix. For example, `dt-drive-train.SLDASM` is built by `build_dt_drive_train_assembly.py`; its drawing artefact stem is `dt-drive-train-assembly`.

Drawing Numbers use `MHA-<CATEGORY>-<NNN>`. `000` is the category's assembly drawing; parts start at `001`. HA, CH, DT, FR, MG, PD, PN and SM have assemblies. VN and SH contain parts only. The cutover assigned part sequences by the old numeric identifier within each evidence-derived category. The numbers are stored in the registries, not recalculated when the graph changes. Configuration variants share their part family's Number; installed channel spring stretch variants retain the base Number.

| Prefix | Category | Parts |
|---|---|---:|
| `ha` / `HA` | Harmonic analyzer | 2 |
| `ch` / `CH` | Channel | 9 |
| `dt` / `DT` | Drive train | 36 |
| `fr` / `FR` | Frame | 5 |
| `mg` / `MG` | Magnifier | 9 |
| `pd` / `PD` | Paper drive | 25 |
| `pn` / `PN` | Pen | 6 |
| `sm` / `SM` | Summing | 3 |
| `vn` / `VN` | Vendor parts | 49 |
| `sh` / `SH` | Shared fabricated parts | 2 |

Supplier, SKU and commercial-process evidence determines VN classification before assembly sharing is considered. SH contains fabricated parts used directly by multiple assemblies, currently the front and back column clamps. Transitive containment by the top assembly does not make a part shared. The retained orphan chain sprocket belongs to PD by its translational-gearing and platen-chain evidence; the retained orphan hex bolt belongs to VN by catalog evidence. Wheel axle nut is VN by commercial-process evidence.

Purchased ANSI #25 inner and outer chain links and finished ISO 2338 m6 crank
hub dowel stock are VN, including cut-to-length modifications. Pins machined
from raw drill rod remain owned by their subsystem.

Doit selection uses the underscore stem:

```powershell
uv run python -m doit part:dt_cone_gear
uv run python -m doit assembly:pd_paper_drive
uv run python -m doit drawing:dt_drive_train_assembly
```

Follow [BUILDING.md](BUILDING.md) and [the supervised farm-launch contract](../../DEVELOPING.md#supervised-farm-launches) for executor and launch requirements. Geometric API names, features, sketches, dimensions, mate labels and machine-configuration concepts are unchanged by this naming policy.

The offline configuration gate (`verify.py --suite config`, selected through
`check:config`) validates category and Number agreement, assembly `000` and
part sequences starting at `001`, unique Numbers across both kinds, and closure
between registries, producers, drawings and dependency references. Assembly
saves and refreshes stamp the Number from the assembly's own YAML contract.
Grouped BOM part properties accept category-qualified part Numbers with a
nonzero sequence only when they identify an exact frozen parts-registry entry.
Assembly `000` Numbers are assembly references, not part Numbers.

## Historical evidence

Dated reports, released packages, raw logs, source quotations and user-authored bench entries retain the identifiers, snapshot URLs and checksums they recorded. Read their identifiers through the table below when locating a current model. Current instructions, registry references, commands and asset links use canonical identities. A migration notice on a historical document does not change the evidence or certify it against the current model.

## Identity migration table

The table covers 146 part families and eight assemblies. Old names and Numbers are lookup keys for historical evidence, not supported aliases for current commands or files.

| Kind | Old stem | Canonical stem | Old Number | Current Number |
|---|---|---|---|---|
| part | `measuring-stick` | `ha-measuring-stick` | MHA-046 | MHA-HA-001 |
| part | `measuring-stick-stop` | `ha-measuring-stick-stop` | MHA-122 | MHA-HA-002 |
| part | `amplitude-bar` | `ch-amplitude-bar` | MHA-003 | MHA-CH-001 |
| part | `channel-lever` | `ch-channel-lever` | MHA-009 | MHA-CH-002 |
| part | `connecting-rod` | `ch-connecting-rod` | MHA-017 | MHA-CH-003 |
| part | `fulcrum-shaft` | `ch-fulcrum-shaft` | MHA-031 | MHA-CH-004 |
| part | `pivot-shaft` | `ch-pivot-shaft` | MHA-065 | MHA-CH-005 |
| part | `rocker-arm` | `ch-rocker-arm` | MHA-071 | MHA-CH-006 |
| part | `fulcrum-keeper` | `ch-fulcrum-keeper` | MHA-120 | MHA-CH-007 |
| part | `pivot-bracket` | `ch-pivot-bracket` | MHA-123 | MHA-CH-008 |
| part | `rocker-thrust-washer` | `ch-rocker-thrust-washer` | MHA-148 | MHA-CH-009 |
| part | `alignment-pinion` | `dt-alignment-pinion` | MHA-002 | MHA-DT-001 |
| part | `arbor-pedestal` | `dt-arbor-pedestal` | MHA-004 | MHA-DT-002 |
| part | `cone-gear` | `dt-cone-gear` | MHA-013 | MHA-DT-003 |
| part | `cone-gear-shaft` | `dt-cone-gear-shaft` | MHA-014 | MHA-DT-004 |
| part | `cone-pivot-post` | `dt-cone-pivot-post` | MHA-016 | MHA-DT-005 |
| part | `crank-arm` | `dt-crank-arm` | MHA-020 | MHA-DT-006 |
| part | `crank-drive-gear` | `dt-crank-drive-gear` | MHA-021 | MHA-DT-007 |
| part | `crank-handle` | `dt-crank-handle` | MHA-022 | MHA-DT-008 |
| part | `crank-pin` | `dt-crank-pin` | MHA-024 | MHA-DT-009 |
| part | `crank-pinion` | `dt-crank-pinion` | MHA-025 | MHA-DT-010 |
| part | `crankshaft` | `dt-crankshaft` | MHA-026 | MHA-DT-011 |
| part | `cylinder-gear` | `dt-cylinder-gear` | MHA-027 | MHA-DT-012 |
| part | `cylinder-gear-shaft` | `dt-cylinder-gear-shaft` | MHA-028 | MHA-DT-013 |
| part | `pinion-bracket` | `dt-pinion-bracket` | MHA-056 | MHA-DT-014 |
| part | `pinion-handle` | `dt-pinion-handle` | MHA-058 | MHA-DT-015 |
| part | `pinion-lever` | `dt-pinion-lever` | MHA-059 | MHA-DT-016 |
| part | `pinion-lift-rod` | `dt-pinion-lift-rod` | MHA-060 | MHA-DT-017 |
| part | `pinion-pivot-block` | `dt-pinion-pivot-block` | MHA-061 | MHA-DT-018 |
| part | `pinion-pivot-shaft` | `dt-pinion-pivot-shaft` | MHA-062 | MHA-DT-019 |
| part | `cone-swing-platform` | `dt-cone-swing-platform` | MHA-091 | MHA-DT-020 |
| part | `cone-tip-block` | `dt-cone-tip-block` | MHA-092 | MHA-DT-021 |
| part | `pinion-arbor` | `dt-pinion-arbor` | MHA-102 | MHA-DT-022 |
| part | `pinion-cam` | `dt-pinion-cam` | MHA-104 | MHA-DT-023 |
| part | `pinion-spring` | `dt-pinion-spring` | MHA-114 | MHA-DT-024 |
| part | `pinion-cam-pin` | `dt-pinion-cam-pin` | MHA-116 | MHA-DT-025 |
| part | `cylinder-end-disc` | `dt-cylinder-end-disc` | MHA-121 | MHA-DT-026 |
| part | `crank-pin-ring` | `dt-crank-pin-ring` | MHA-128 | MHA-DT-027 |
| part | `crank-pin-eye` | `dt-crank-pin-eye` | MHA-130 | MHA-DT-028 |
| part | `crank-pinion-pin` | `dt-crank-pinion-pin` | MHA-134 | MHA-DT-029 |
| part | `pinion-lever-pin` | `dt-pinion-lever-pin` | MHA-135 | MHA-DT-030 |
| part | `crank-hub` | `dt-crank-hub` | MHA-137 | MHA-DT-031 |
| part | `crank-hub-pin` | `vn-crank-hub-pin` | MHA-138 | MHA-VN-029 |
| part | `crank-handle-pivot-screw` | `dt-crank-handle-pivot-screw` | MHA-139 | MHA-DT-032 |
| part | `pinion-arbor-collar` | `dt-pinion-arbor-collar` | MHA-144 | MHA-DT-033 |
| part | `crank-handle-ferrule` | `dt-crank-handle-ferrule` | MHA-152 | MHA-DT-034 |
| part | `crank-handle-butt-cup` | `dt-crank-handle-butt-cup` | MHA-153 | MHA-DT-035 |
| part | `crank-seat-washer` | `dt-crank-seat-washer` | MHA-172 | MHA-DT-036 |
| part | `harmonic-base` | `fr-harmonic-base` | MHA-035 | MHA-FR-001 |
| part | `top-frame` | `fr-top-frame` | MHA-077 | MHA-FR-002 |
| part | `tube-frame` | `fr-tube-frame` | MHA-083 | MHA-FR-003 |
| part | `nameplate` | `fr-nameplate` | MHA-086 | MHA-FR-004 |
| part | `rocker-arm-support` | `fr-rocker-arm-support` | MHA-089 | MHA-FR-005 |
| part | `magnifying-bracket` | `mg-magnifying-bracket` | MHA-041 | MHA-MG-001 |
| part | `magnifying-clamp` | `mg-magnifying-clamp` | MHA-042 | MHA-MG-002 |
| part | `magnifying-lever` | `mg-magnifying-lever` | MHA-043 | MHA-MG-003 |
| part | `magnifying-vertical-rod` | `mg-magnifying-vertical-rod` | MHA-044 | MHA-MG-004 |
| part | `magnifying-wheel` | `mg-magnifying-wheel` | MHA-045 | MHA-MG-005 |
| part | `output-fixture` | `mg-output-fixture` | MHA-047 | MHA-MG-006 |
| part | `wheel-axle` | `mg-wheel-axle` | MHA-084 | MHA-MG-007 |
| part | `wheel-bar` | `mg-wheel-bar` | MHA-085 | MHA-MG-008 |
| part | `lever-wire` | `mg-lever-wire` | MHA-115 | MHA-MG-009 |
| part | `chain-inner-link` | `vn-chain-inner-link` | MHA-006 | MHA-VN-002 |
| part | `chain-outer-link` | `vn-chain-outer-link` | MHA-007 | MHA-VN-003 |
| part | `chain-sprocket` | `pd-chain-sprocket` | MHA-008 | MHA-PD-001 |
| part | `platen` | `pd-platen` | MHA-066 | MHA-PD-002 |
| part | `platen-clip` | `pd-platen-clip` | MHA-067 | MHA-PD-003 |
| part | `platen-paper` | `pd-platen-paper` | MHA-068 | MHA-PD-004 |
| part | `platen-rack` | `pd-platen-rack` | MHA-069 | MHA-PD-005 |
| part | `rack-pinion` | `pd-rack-pinion` | MHA-070 | MHA-PD-006 |
| part | `support-bar` | `pd-support-bar` | MHA-074 | MHA-PD-007 |
| part | `transgear-knob-shaft` | `pd-transgear-knob-shaft` | MHA-078 | MHA-PD-008 |
| part | `transgear-removable` | `pd-transgear-removable` | MHA-081 | MHA-PD-009 |
| part | `transgear-feed-pinion` | `pd-transgear-feed-pinion` | MHA-110 | MHA-PD-010 |
| part | `platen-guide` | `pd-platen-guide` | MHA-111 | MHA-PD-011 |
| part | `guide-lock` | `pd-guide-lock` | MHA-112 | MHA-PD-012 |
| part | `transgear-thumbnut` | `pd-transgear-thumbnut` | MHA-126 | MHA-PD-013 |
| part | `latch-hook` | `pd-latch-hook` | MHA-127 | MHA-PD-014 |
| part | `transgear-knob-thrust-ring` | `pd-transgear-knob-thrust-ring` | MHA-156 | MHA-PD-015 |
| part | `transgear-knob-cup` | `pd-transgear-knob-cup` | MHA-157 | MHA-PD-016 |
| part | `transgear-disc-hub` | `pd-transgear-disc-hub` | MHA-159 | MHA-PD-017 |
| part | `transgear-arm` | `pd-transgear-arm` | MHA-164 | MHA-PD-018 |
| part | `transgear-arm-plate` | `pd-transgear-arm-plate` | MHA-165 | MHA-PD-019 |
| part | `transgear-pivot-spacer` | `pd-transgear-pivot-spacer` | MHA-167 | MHA-PD-020 |
| part | `latch-hook-bracket` | `pd-latch-hook-bracket` | MHA-170 | MHA-PD-021 |
| part | `transgear-drive-collar` | `pd-transgear-drive-collar` | MHA-177 | MHA-PD-022 |
| part | `transgear-pin` | `pd-transgear-pin` | MHA-179 | MHA-PD-023 |
| part | `transgear-rear-bushing` | `pd-transgear-rear-bushing` | MHA-180 | MHA-PD-024 |
| part | `transgear-front-bushing` | `pd-transgear-front-bushing` | MHA-181 | MHA-PD-025 |
| part | `pen-frame` | `pn-pen-frame` | MHA-048 | MHA-PN-001 |
| part | `pen-hanger` | `pn-pen-hanger` | MHA-049 | MHA-PN-002 |
| part | `pen-marker` | `pn-pen-marker` | MHA-050 | MHA-PN-003 |
| part | `pen-rod` | `pn-pen-rod` | MHA-051 | MHA-PN-004 |
| part | `pen-v-block` | `pn-pen-v-block` | MHA-053 | MHA-PN-005 |
| part | `pen-wire` | `pn-pen-wire` | MHA-100 | MHA-PN-006 |
| part | `gooseneck` | `sm-gooseneck` | MHA-032 | MHA-SM-001 |
| part | `knife-mount` | `sm-knife-mount` | MHA-037 | MHA-SM-002 |
| part | `summing-lever` | `sm-summing-lever` | MHA-073 | MHA-SM-003 |
| part | `boss-hook` | `vn-boss-hook` | MHA-005 | MHA-VN-001 |
| part | `channel-spring-installed` | `vn-channel-spring-installed` | MHA-011 | MHA-VN-004 |
| part | `counter-spring` | `vn-counter-spring` | MHA-019 | MHA-VN-005 |
| part | `fillister-screw` | `vn-fillister-screw` | MHA-030 | MHA-VN-006 |
| part | `hanger-screw` | `vn-hanger-screw` | MHA-034 | MHA-VN-007 |
| part | `hex-bolt` | `vn-hex-bolt` | MHA-036 | MHA-VN-008 |
| part | `lag-screw` | `vn-lag-screw` | MHA-039 | MHA-VN-009 |
| part | `pen-set-screw` | `vn-pen-set-screw` | MHA-052 | MHA-VN-010 |
| part | `thumb-screw` | `vn-thumb-screw` | MHA-075 | MHA-VN-011 |
| part | `spring-hook` | `vn-spring-hook` | MHA-090 | MHA-VN-012 |
| part | `cone-lock-knob` | `vn-cone-lock-knob` | MHA-093 | MHA-VN-013 |
| part | `cone-pivot-screw` | `vn-cone-pivot-screw` | MHA-094 | MHA-VN-014 |
| part | `swing-stop-screw` | `vn-swing-stop-screw` | MHA-095 | MHA-VN-015 |
| part | `cone-tip-collar` | `vn-cone-tip-collar` | MHA-096 | MHA-VN-016 |
| part | `cone-tip-adjuster` | `vn-cone-tip-adjuster` | MHA-097 | MHA-VN-017 |
| part | `cone-tip-pinch-screw` | `vn-cone-tip-pinch-screw` | MHA-098 | MHA-VN-018 |
| part | `slotted-screw` | `vn-slotted-screw` | MHA-101 | MHA-VN-019 |
| part | `foot-screw` | `vn-foot-screw` | MHA-103 | MHA-VN-020 |
| part | `clamp-screw` | `vn-clamp-screw` | MHA-107 | MHA-VN-021 |
| part | `frame-side-screw` | `vn-frame-side-screw` | MHA-117 | MHA-VN-022 |
| part | `gooseneck-set-screw` | `vn-gooseneck-set-screw` | MHA-118 | MHA-VN-023 |
| part | `knife-hanger-stud` | `vn-knife-hanger-stud` | MHA-119 | MHA-VN-024 |
| part | `wheel-axle-nut` | `vn-wheel-axle-nut` | MHA-129 | MHA-VN-025 |
| part | `knife-hanger-washer` | `vn-knife-hanger-washer` | MHA-131 | MHA-VN-026 |
| part | `frame-cross-screw` | `vn-frame-cross-screw` | MHA-132 | MHA-VN-027 |
| part | `tube-frame-cap` | `vn-tube-frame-cap` | MHA-133 | MHA-VN-028 |
| part | `cone-tip-block-screw` | `vn-cone-tip-block-screw` | MHA-140 | MHA-VN-030 |
| part | `post-mount-screw` | `vn-post-mount-screw` | MHA-142 | MHA-VN-031 |
| part | `pedestal-hold-down-screw` | `vn-pedestal-hold-down-screw` | MHA-143 | MHA-VN-032 |
| part | `pinion-strap-pin` | `vn-pinion-strap-pin` | MHA-145 | MHA-VN-033 |
| part | `arbor-set-screw` | `vn-arbor-set-screw` | MHA-147 | MHA-VN-034 |
| part | `keeper-chain` | `vn-keeper-chain` | MHA-149 | MHA-VN-035 |
| part | `keeper-chain-link` | `vn-keeper-chain-link` | MHA-150 | MHA-VN-036 |
| part | `transgear-collar-cross-pin` | `vn-transgear-collar-cross-pin` | MHA-154 | MHA-VN-037 |
| part | `transgear-knob-drive-pin` | `vn-transgear-knob-drive-pin` | MHA-155 | MHA-VN-038 |
| part | `transgear-disc-screw` | `vn-transgear-disc-screw` | MHA-161 | MHA-VN-039 |
| part | `transgear-arm-plate-screw` | `vn-transgear-arm-plate-screw` | MHA-166 | MHA-VN-040 |
| part | `transgear-pivot-screw` | `vn-transgear-pivot-screw` | MHA-168 | MHA-VN-041 |
| part | `transgear-latch-pin` | `vn-transgear-latch-pin` | MHA-169 | MHA-VN-042 |
| part | `latch-hook-bracket-screw` | `vn-latch-hook-bracket-screw` | MHA-171 | MHA-VN-043 |
| part | `crank-seat-drive-pin` | `vn-crank-seat-drive-pin` | MHA-173 | MHA-VN-044 |
| part | `latch-hook-rivet` | `vn-latch-hook-rivet` | MHA-175 | MHA-VN-045 |
| part | `guide-lock-screw` | `vn-guide-lock-screw` | MHA-176 | MHA-VN-046 |
| part | `transgear-retaining-ring` | `vn-transgear-retaining-ring` | MHA-182 | MHA-VN-047 |
| part | `transgear-knob-cup-pin` | `vn-transgear-knob-cup-pin` | MHA-183 | MHA-VN-048 |
| part | `transgear-pivot-spring` | `vn-transgear-pivot-spring` | MHA-184 | MHA-VN-049 |
| part | `column-clamp-front` | `sh-column-clamp-front` | MHA-105 | MHA-SH-001 |
| part | `column-clamp-back` | `sh-column-clamp-back` | MHA-106 | MHA-SH-002 |
| assembly | `frame` | `fr-frame` | MHA-A04 | MHA-FR-000 |
| assembly | `drive-train` | `dt-drive-train` | MHA-A03 | MHA-DT-000 |
| assembly | `channel` | `ch-channel` | MHA-A02 | MHA-CH-000 |
| assembly | `summing` | `sm-summing` | MHA-A07 | MHA-SM-000 |
| assembly | `magnifier` | `mg-magnifier` | MHA-A05 | MHA-MG-000 |
| assembly | `pen` | `pn-pen` | MHA-A01 | MHA-PN-000 |
| assembly | `paper-drive` | `pd-paper-drive` | MHA-A06 | MHA-PD-000 |
| assembly | `harmonic-analyzer` | `ha-harmonic-analyzer` | MHA-A08 | MHA-HA-000 |
