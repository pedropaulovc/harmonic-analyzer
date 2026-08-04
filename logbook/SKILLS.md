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
| Facing, turning to diameter, shoulders | M02 | `crank-pin`, `crankshaft`, `crank-handle`, `wheel-axle`, screw blanks | ch. 9 Turning |
| Drilling, boring, reaming to a fit | M03 | `pivot-bushing`, `lever-bushing`, `cylinder-gear` bore, `knife-mount` bore, `magnifying-wheel` | ch. 10 Drilling, boring, reaming |
| Parting to a length, batch repeatability | M04 | 19× `pivot-bushing`, 19× `lever-bushing`, spacers | ch. 11 Parting to a length tolerance |
| Slender turning, steadies, followers | M05 | `pivot-shaft`, `fulcrum-shaft`, `cone-gear-shaft`, `cylinder-gear-shaft`, `pinion-arbor`, `amplitude-bar` | ch. 12 Slender work |
| Tramming, squaring, edge finding | M06 | `knife-mount` ×2, `pinion-pivot-block`, `transgear-bracket`, `arbor-pedestal` | ch. 13 Milling |
| Profile milling, slots, batch fixturing | M07 | `rocker-arm` ×20, `connecting-rod` ×20, `channel-lever` ×20, `platen-guide`, `wheel-bar` | ch. 13 Milling |
| Hole patterns, reaming, tapping | M08 | `rocker-arm-support` (4× 9/16-12), `summing-lever` 20× Ø2.0 pattern, `harmonic-base` | ch. 14 Hole patterns and tapping |
| Dividing head, indexing, co-phasing | M09 | `cylinder-gear` notches ×20, every gear blank | ch. 15 Indexing |
| Form-cutter generation (Eureka) | M10 | the cutters themselves — **nothing in the gear train without them** | ch. 16 Making your own gear cutters |
| Gear cutting and inspection | M10 | `cone-gear` ×20, `cylinder-gear` ×20, `crank-pinion`, `alignment-pinion`, `rack-pinion`, `transgear-*`, `chain-sprocket`, `platen-rack` | ch. 17 Cutting the gears |
| Soft and silver soldering | M11 | cone gear set → shaft; wire terminations | ch. 18 Soldering |
| Draw filing, polishing, blacking | M11 | every visible part | ch. 19 Finishing |
| Assembly, alignment, calibration | — (learned on the machine) | the whole analyzer | ch. 33–35 |

## Parts with no module yet

These need a decision before a module can be written for them:

| part | question |
|---|---|
| `summing-lever` | Cast, fabricate, or hog from solid? Each answer is a different skill. `cad/docs/machining-dfm.md` recommends not hogging. |
| `summing-lever` knife edge | Machine into the parent, or make a hardened tool-steel insert? |
| `rocker-arm-support`, `connecting-rod` | Cast or cut from bar? (Both benign as bar.) |
| `counter-spring`, `channel-spring-installed` ×20 | Wind your own (a module) or specify to a spring house (a procurement task)? |
| `chain-inner-link` / `chain-outer-link` / `chain-sprocket` | Make the roller chain or buy it? |
| `measuring-stick` | Hand stamping — a small module of its own, or a paragraph? |

## Coverage check

Run this occasionally: does every Tier-1 part in `cad/docs/machining-dfm.md` appear
in the "parts it unlocks" column above? A T1 part with no module is a hole in
the curriculum, and it will become a hole in the book.
