# Funding goal

> Every figure is `TBD` until sourced. Fill a row only with a real quote, a
> real invoice, or a linked supplier price — and name the source in the row.

## The rule

**Set the goal at the minimum that makes the book real, not at what the project
is worth.** Kickstarter is all-or-nothing: a goal 30 % too high returns every
pledge. Stretch goals capture the upside; the base goal only has to cover the
things without which there is no book.

## Base goal — must-fund line items

| item | why it's load-bearing | cost | source |
|---|---|---|---|
| Stock: brass bar (gears, bushings, platen) | 40 gears + 38 bushings | TBD | — |
| Stock: steel bar and plate (shafts, rocker arms, frame) | 20 rocker arms, long slender shafts | TBD | — |
| Cast iron / castings or fabrication for the 3 cast parts | summing lever, rocker-arm support, connecting rods | TBD | `docs/machining-dfm.md` |
| Gear-cutter blanks + tool steel for self-made Eureka form cutters | off-the-shelf DP-49.82 cutters **do not exist** | TBD | `docs/machining-dfm.md` |
| Dividing head + tailstock | non-negotiable for 40 indexed gears | TBD | — |
| Measuring: micrometers, bore gauges, indicators, gauge blocks | the book's tolerances are meaningless without inspection | TBD | `docs/tolerance-gdt-assessment.md` |
| Springs (20 + 1 counter spring), wound to spec | not off-the-shelf | TBD | — |
| Editing + proofreading | a self-edited technical book reads like one | TBD | — |
| Book design and layout | | TBD | — |
| Photography (lighting, macro lens or rental) | every operation needs a photograph | TBD | — |
| ISBN(s) | one per format | TBD | — |
| Kickstarter + processing fees (~8–10 % of raise) | | derived | — |
| Print run / POD setup | | TBD | `../rewards/fulfilment.md` |
| Shipping and packaging | | TBD | `../rewards/fulfilment.md` |
| Tax on the funded amount | **the raise is income** | derived | — |
| Contingency (+20 %) | first-article parts get scrapped; that is the method | derived | — |

**Already owned — do not put in the goal** (and say so on the page; it builds
credibility): mill, lathe, SolidWorks seat, the CAD work to date, the reference
library.

## Stretch goals — candidates

| multiple | goal | cost driver |
|---|---|---|
| 1.25× | Full-colour print interior | print unit cost |
| 1.5× | Professional video series documenting the build | edit time |
| 1.75× | Second machine built by an independent machinist as a **build validation** — the strongest possible proof the book works | their time + stock |
| 2× | Translated edition (pt-BR) | translation |
| 2.5× | Interactive simulator gets full motion + a settable amplitude-bar UI | dev time |

The 1.75× goal is the interesting one: an independent build is the only real
test of whether the instructions are sufficient, and it's a compelling public
promise.

## Sanity checks before publishing a goal

- [ ] Does the base goal survive 10 % fees + 6 % dropped pledges + tax?
- [ ] If exactly 100 backers fund at the median tier, does it clear the goal?
- [ ] Is there any line item whose absence stops the book? If so it belongs in
      the base, not a stretch goal.
- [ ] Is any physical reward's fulfilment cost larger than its tier price?
