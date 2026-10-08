# Skills matrix

The join table between the three deliverables that depend on each other:
**a curriculum module teaches a skill → the skill unlocks parts → the parts and
the skill become book chapters.**

Rule: **a book chapter may not go past `drafted` until its module is
`applied`.** Prose about an operation that hasn't been performed is the one
failure mode that would make the book worthless.

| skill | module | parts it unlocks | book chapter |
|---|---|---|---|
| Shop safety, machine setup | M00 | — | `front/safety.qmd` |
| Measurement, layout, reading GD&T | M01 | — | ch. 6 Measuring |
| Facing, turning to diameter, shoulders | M02 | `dt-crank-pin`, `dt-crankshaft`, `dt-crank-handle`, `mg-wheel-axle`, screw blanks | ch. 9 Turning |
| Drilling, boring, reaming to a fit | M03 | `pivot-bushing`, `lever-bushing`, `dt-cylinder-gear` bore, `sm-knife-mount` bore, `mg-magnifying-wheel` | ch. 10 Drilling, boring, reaming |
| Parting to a length, batch repeatability | M04 | 19× `pivot-bushing`, 19× `lever-bushing`, spacers | ch. 11 Parting to a length tolerance |
| Slender turning, steadies, followers | M05 | `ch-pivot-shaft`, `ch-fulcrum-shaft`, `dt-cone-gear-shaft`, `dt-cylinder-gear-shaft`, `dt-pinion-arbor`, `ch-amplitude-bar` | ch. 12 Slender work |
| Tramming, squaring, edge finding | M06 | `sm-knife-mount` ×2, `dt-pinion-pivot-block`, `pd-transgear-arm`, `dt-arbor-pedestal` | ch. 13 Milling |
| Profile milling, slots, batch fixturing | M07 | `ch-rocker-arm` ×20, `ch-connecting-rod` ×20, `ch-channel-lever` ×20, `pd-platen-guide`, `mg-wheel-bar` | ch. 13 Milling |
| Hole patterns, reaming, tapping | M08 | `fr-rocker-arm-support` (4× 1/2-13 UNC-2B, `cad/scripts/build_fr_rocker_arm_support.py`), `sm-summing-lever` 20× Ø2.0 pattern, `fr-harmonic-base` | ch. 14 Hole patterns and tapping |
| Dividing head, indexing, co-phasing | M09 | `dt-cylinder-gear` notches ×20, every gear blank | ch. 15 Indexing |
| Form-cutter generation (Eureka) | M10 | the T006 cone gear's cutter, the one gear no stock cutter range covers | ch. 16 Making your own gear cutters |
| Gear cutting and inspection | M10 | `dt-cone-gear` ×20, `dt-cylinder-gear` ×20, `dt-crank-pinion`, `dt-alignment-pinion`, `pd-rack-pinion`, `pd-transgear-*`, `vn-transgear-*`, `pd-chain-sprocket`, `pd-platen-rack` | ch. 17 Cutting the gears |
| D-bore fitting, gear-stack assembly | M11 | 64T + cone gear set → D-flat shaft | ch. 18 Fitting D-bores and the cone gear stack |
| Silver soldering | M11 | `dt-crank-pin-ring` ends | — |
| Draw filing, polishing, blacking | M11 | every visible part | ch. 19 Finishing |
| Assembly, alignment, calibration | — (learned on the machine) | the whole analyzer | ch. 33–35 |

## Parts with no module yet

These need a decision before a module can be written for them:

| part | question |
|---|---|
| `sm-summing-lever` | Cast, fabricate, or hog from solid? Each answer is a different skill. `cad/docs/machining-dfm.md` recommends not hogging. |
| `sm-summing-lever` knife edge | Machine into the parent, or make a hardened tool-steel insert? |
| `fr-rocker-arm-support`, `ch-connecting-rod` | Cast or cut from bar? (Both benign as bar.) |
| `vn-counter-spring`, `vn-channel-spring-installed` ×20 | Wind your own (a module) or specify to a spring house (a procurement task)? |
| `vn-chain-inner-link` / `vn-chain-outer-link` / `pd-chain-sprocket` | Make the roller chain or buy it? |
| `ha-measuring-stick` | Hand stamping — a small module of its own, or a paragraph? |

## Coverage check

Run this occasionally: does every Tier-1 part in `cad/docs/machining-dfm.md` appear
in the "parts it unlocks" column above? A T1 part with no module is a hole in
the curriculum, and it will become a hole in the book.
