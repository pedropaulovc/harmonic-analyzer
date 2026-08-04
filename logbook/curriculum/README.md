# The curriculum

A beginner's lathe and milling course, sized to exactly what building a
Michelson harmonic analyzer requires. Nothing more, nothing decorative.

**Every module ends by cutting a real part of the machine.** If a skill can't
be closed that way, it isn't in the course.

## The modules

| # | module | h `[EST]` | ends by making | status |
|---|---|---:|---|---|
| M00 | [Safety and shop setup](m00-safety-and-shop-setup.md) | 8 | — | not started |
| M01 | [Measurement and layout](m01-measurement-and-layout.md) | 12 | — | not started |
| M02 | [Lathe I — facing, turning, shoulders](m02-lathe-i-facing-turning-shoulders.md) | 20 | `crank-pin`, `pivot-shaft` blank | not started |
| M03 | [Lathe II — drilling, boring, reaming](m03-lathe-ii-drilling-boring-reaming.md) | 16 | one `pivot-bushing` | not started |
| M04 | [Lathe III — parting to length, batch work](m04-lathe-iii-parting-to-length-and-batch-work.md) | 20 | 19× `pivot-bushing` + 19× `lever-bushing` | not started |
| M05 | [Lathe IV — slender work, steadies, tapers](m05-lathe-iv-slender-work-steadies-tapers.md) | 16 | `pivot-shaft`, `fulcrum-shaft`, `cone-gear-shaft` | not started |
| M06 | [Mill I — tramming, squaring, edge finding](m06-mill-i-tramming-squaring-edge-finding.md) | 16 | `knife-mount` ×2 | not started |
| M07 | [Mill II — profiling, slots, workholding](m07-mill-ii-profiling-slots-workholding.md) | 20 | `rocker-arm` ×20, `connecting-rod` ×20 | not started |
| M08 | [Hole patterns, reaming and tapping](m08-hole-patterns-reaming-and-tapping.md) | 12 | `rocker-arm-support` feet, spring-hole pattern | not started |
| M09 | [The dividing head and indexing](m09-the-dividing-head-and-indexing.md) | 20 | `cylinder-gear` alignment notches | **blocked** |
| M10 | [Gear cutting](m10-gear-cutting-making-the-cutter-then-the-gear.md) | 60+ | form cutters, then `cone-gear` T120 → the whole train | not started |
| M11 | [Soldering, finishing, assembly craft](m11-soldering-finishing-and-assembly-craft.md) | 16 | cone gear set soldered to its shaft | not started |

Total `[EST]` ≈ **236 h**, and M10 is certainly underestimated.

## Dependency order

```
M00 ─ M01 ─┬─ M02 ─ M03 ─ M04 ─ M05 ─────────────┐
           │                                     ├─ M10 ─ M11
           └─ M06 ─ M07 ─ M09 ────────────────────┘
                 └─ M08
```

Two independent tracks (lathe and mill) that converge on gear cutting. The
lathe track is longer; start it first and slot mill modules in around it.

## Critical path

**M09 → M10.** The dividing head is not yet acquired and everything about the
gear train waits on it. Off-the-shelf involute cutters for this machine's
diametral pitch (DP 49.82) **do not exist** — that is a settled finding, not an
assumption (`docs/machining-dfm.md`) — so M10 includes generating your own
cutters by the Eureka method before a single tooth is cut.

Buy the dividing head early. It unblocks 40 gears and 20 notches.

## How this feeds the book

Each module maps onto a chapter of the book's Part III, and the parts it
unlocks map onto Part IV. See [`../SKILLS.md`](../SKILLS.md) for the full
matrix. **A book chapter cannot go past `drafted` until its module is
`applied`.**

## Reading list, in order

1. `references/machining-for-hobbyists-getting-started/` — front to back, once,
   before touching anything
2. `references/jet-bd-920n-operators-manual.pdf` and the mill's manual
3. `references/machinerys-handbook/` — as a lookup, never front to back
4. `references/gears-and-gear-cutting/` — before M09, not before M10; the
   indexing chapters come first
