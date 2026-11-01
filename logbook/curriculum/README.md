# The curriculum

**Goal: learn hobby machining by building the Michelson harmonic analyzer.**
The course covers the lathe and mill skills that this machine needs, and stops
there.

Module maturity lives only in each linked module's `status:` frontmatter. This
index does not repeat it.

## How the lessons are chosen

**A part motivates every module.** Each module starts from a part the build
actually needs. That is either a part of the analyzer or a piece of shop
tooling, a jig or fixture (`*-tl-*`) made to build one. The part is what
justifies learning the skill: the module teaches only what that part demands,
and it ends with the part made. Nothing is made just for practice. Jigs count
because the build can't go on without them, and because they are forgiving:
they are aluminium or acetal, toleranced loosely enough for a first attempt,
and nobody photographs them for the book.

**The mill track opens on the oblique jig.** Rocker arms are cut on the
`ch-rocker-arm-tl-oblique-jig` (MHA-CH-06-TL-00), the trammel that swings each
arm under the cutter to generate its R800 top edge. Before any rocker arm can
be cut, the jig has to exist. Its parts cover the beginner mill skills in
order, from facing a bar to length up to shimming a running fit. So the mill
modules build the jig first, then move on to the analyzer parts that use the
same skills.

| jig part | Number | module that makes it |
|---|---|---|
| end bracket ×2, feed lever (saw and face to length) | TL-28, TL-26 | M06 |
| base bar ×2 (face to 440 long, both faces to 12.0) | TL-20 | M06 |
| pivot block, feed block (square six faces) | TL-22, TL-32 | M06 |
| carrier plate (rip, face, mill to 520 × 130) | TL-21 | M06 |
| tapped, counterbored and reamed holes in all of the above | — | M08 |
| base bar hold-down slots, riser blank (acetal) | TL-20, TL-24 | M07 |
| jig assembly and carrier running-gap shimming | TL-00 | M07 |

Part identities follow the
[subsystem identity guide](../../cad/docs/subsystem-identities.md); sizes and
processes are taken from each part's `cad/config/parts/*.yaml` row.

## The twist: break it on purpose first

**Every module has a controlled mistake to make before doing the job right.**
A beginner can't tell that a cut is going wrong because they have never seen
one go wrong. So for each common mistake a module covers, you make it once on
purpose, on scrap, with a small cut and the stop under your hand. You watch,
listen and measure what wrong looks like. Then you change that one thing back
and do the job right. The pair of results, wrong next to right, is the lesson.

It is the controlled version of what happened on
[2026-10-30](../entries/2026-10-30-pendant-and-roughing-base-bar-to-length.md):
climb milling without knowing it, ringing in a cut high above the jaws,
backing off the wrong way, and a part scrapped. That session showed what
wrong looks like with a real part at stake. A controlled mistake shows the same
thing at a cost of one offcut.

The rules:

1. **Scrap only.** Never on a part you need. Offcuts and failed parts are the
   stock for this. The base bar scrapped on 2026-10-30 is the first candidate,
   unless measuring it shows it can still make another jig part.
2. **Start from a setup known to cut well and change one thing.** Then the
   difference is caused by that one change.
3. **Small cut.** Use a shallow depth, a slow feed and a short stick-out. The
   mistake should be visible without the energy to throw anything.
4. **Predict first.** Write down what you expect to see, hear and measure.
   Then do it.
5. **Rehearse the escape dry.** On the mill: stop, wait for all motion to end,
   then retract Z. Never back off sideways while the cutter is in the cut. On
   the lathe: feed stop, then spindle stop.
6. **Record it like any session.** It gets an entry, with part `practice`. The
   entry describes what the mistake looked, sounded and measured like. Then it
   does the same for the right way.

**Never on purpose:** anything that could throw the work or the tool. That
includes work held loosely or by a burr, a chuck key left in the chuck,
gloves, loose sleeves or hands near anything rotating, and a deliberately
heavy cut. If a mistake can't be made safely at a small scale, the module
describes it instead of staging it.

## Module format

Each module has: objectives · prerequisites · references · practice ·
**controlled mistakes** · **the part that motivates it** ("now make") ·
competency check (with a number) · notes · sessions.

## The modules

| # | module | h `[EST]` | ends by making |
|---|---|---:|---|
| M00 | [Safety and shop setup](m00-safety-and-shop-setup.md) | 8 | — |
| M01 | [Measurement and layout](m01-measurement-and-layout.md) | 12 | the measured allowance sheet for the oblique-jig stock |
| M02 | [Lathe I — facing, turning, shoulders](m02-lathe-i-facing-turning-shoulders.md) | 20 | `dt-crank-pin`, `ch-pivot-shaft` blank |
| M03 | [Lathe II — drilling, boring, reaming](m03-lathe-ii-drilling-boring-reaming.md) | 16 | one `pivot-bushing` |
| M04 | [Lathe III — parting to length, batch work](m04-lathe-iii-parting-to-length-and-batch-work.md) | 20 | 19× `pivot-bushing` + 19× `lever-bushing` |
| M05 | [Lathe IV — slender work, steadies, tapers](m05-lathe-iv-slender-work-steadies-tapers.md) | 16 | `ch-pivot-shaft`, `ch-fulcrum-shaft`, `dt-cone-gear-shaft` |
| M06 | [Mill I — tramming, squaring, edge finding](m06-mill-i-tramming-squaring-edge-finding.md) | 24 | oblique-jig bars, blocks and carrier; then `sm-knife-mount` ×2 |
| M08 | [Hole patterns, reaming and tapping](m08-hole-patterns-reaming-and-tapping.md) | 16 | oblique-jig holes; then `fr-rocker-arm-support` feet, spring-hole pattern |
| M07 | [Mill II — profiling, slots, workholding](m07-mill-ii-profiling-slots-workholding.md) | 28 | oblique jig assembled; then `ch-rocker-arm` ×20, `ch-connecting-rod` ×20 on it |
| M09 | [The dividing head and indexing](m09-the-dividing-head-and-indexing.md) | 20 | `dt-cylinder-gear` alignment notches |
| M10 | [Gear cutting](m10-gear-cutting-making-the-cutter-then-the-gear.md) | 60+ | form cutters, then `dt-cone-gear` T120 → the whole train |
| M11 | [Soldering, finishing, assembly craft](m11-soldering-finishing-and-assembly-craft.md) | 16 | cone gear stack on its D-flat shaft |

Total `[EST]` ≈ **256 h**, and M10 is certainly underestimated.

Module numbers are identifiers, not sequence. M08 now comes before M07,
because the jig needs its holes before it can cut a rocker arm. The numbers
stay as they are so entry and book links keep working.

## Dependency order

```
M00 ─ M01 ─┬─ M02 ─ M03 ─ M04 ─ M05 ─────────────┐
           │                                     ├─ M10 ─ M11
           └─ M06 ─ M08 ─ M07 ─ M09 ─────────────┘
```

Two independent tracks, lathe and mill, that converge on gear cutting. Either
can start first and modules from one can slot in around the other. The mill
track opens on the oblique jig.

## Critical path

**M09 → M10.** This remains the gear-work learning sequence. The dividing head
is delivered, installed and usable, so equipment availability no longer blocks
it. M09 follows M07. M10 still requires M09 and M05. Stock 20° inch cutters cover
every gear except the T006 cone, which needs one self-made cutter, DT6-FORM1
(`cad/docs/machining-dfm.md`, cutter plan).

## How this feeds the book

Each module maps onto a chapter of the book's Part III, and the parts it
unlocks map onto Part IV. See [`../SKILLS.md`](../SKILLS.md) for the full
matrix. **A book chapter cannot go past `drafted` until its module is
`applied`.** The controlled mistakes are material for the book. A photo of
the wrong result beside the right one is something a reader can't get from a
handbook.

## Reading list, in order

1. `references/machining-for-hobbyists-getting-started/` — front to back, once,
   before touching anything
2. The installed machines' manufacturer manuals. The PM-1127VF-LB lathe manual
   is unresolved pending build-year/nameplate verification and a matching
   manufacturer manual; see [M00](m00-safety-and-shop-setup.md#references).
   `references/jet-bd-920n-operators-manual.pdf` is historical reference for the
   former JET only.
3. `references/machinerys-handbook/` — as a lookup, never front to back
4. `references/gears-and-gear-cutting/` — before M09, not before M10; the
   indexing chapters come first
