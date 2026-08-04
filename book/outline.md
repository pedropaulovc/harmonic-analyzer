# Book outline

**Working title:** *Albert Michelson's Harmonic Analyzer: A Project for Hobby
Machinists*

**Promise to the reader:** by the end of this book you will have built a
machine that adds twenty sine waves with gears and springs, and you will be a
better machinist than when you started.

**Reader assumed at page 1:** owns or has access to a bench mill and a lathe,
can read a drawing, has never cut a gear. Not assumed: CNC, a dividing head, a
surface grinder, or any prior gear work.

**Structure principle:** *skills before parts, parts before assemblies.* Every
skill chapter in Part III ends by cutting a real part from the machine, so the
reader is never practising on scrap for its own sake, and Part IV never asks
for an operation Part III didn't teach.

Status legend: `stub` (skeleton only) · `drafted` (written from CAD, not yet
cut) · `verified` (part made following exactly this text).

---

## Front matter

| # | chapter | contains | status |
|---|---|---|---|
| — | Preface | Why this machine, why now, what this book is not. Credit to Hammack/Kranz/Carpenter and the engineerguy series: the machine is thoroughly *documented*, it has just never been written down as something buildable. Where the machine ends up: donated to Matemateca at IME-USP for use with school students. | stub |
| — | How to use this book | The three routes through it: read it, build one sub-assembly, build the whole machine. Conventions, units, symbols. | stub |
| — | Safety | Machine-specific hazards, not a generic list: slitting saws, small-diameter work, indexing with the spindle live, spring tension at assembly. | stub |

## Part I — The machine

| # | chapter | contains | status |
|---|---|---|---|
| 1 | What the machine does | Fourier synthesis and analysis with the minimum maths to build intentionally. Crank → twenty frequencies → weighted sum → pen. | stub |
| 2 | A tour of the mechanism | Sub-assembly by sub-assembly, using the CAD renders: frame, drive train, channels, summing, magnifier, pen, paper drive. The signal path end to end. | stub |
| 3 | Design decisions and deviations | Where this reproduction departs from the surviving machine and why: dimension provenance and confidence, the parts derived from photographs, the pen mechanism (itself a 2013 reconstruction), fastener policy. | stub |
| 4 | The plan of attack | Build order, what gates what, roughly how long each stage takes, and where to stop if you only want part of it. | stub |

## Part II — The shop

| # | chapter | contains | status |
|---|---|---|---|
| 5 | Machines and tooling | Minimum viable shop for this project. Mill, lathe, dividing head, what size, what to skip. What the author used (PM-30MV, JET BD-920N) and what else works. | stub |
| 6 | Measuring | Micrometers, bore gauges, indicators, gauge blocks, DRO. **What each tolerance in this book actually means at the bench** and how to check it. | stub |
| 7 | Materials and stock | Brass, steel, cast iron; why the original used what it used; the full stock list with sizes and quantities, cut from the BOM. | stub |
| 8 | Workholding and fixturing | Collets, chucks, vices, mandrels, soft jaws; the fixturing problems this machine specifically creates (tiny gears, long slender shafts, thin discs). | stub |

## Part III — Skills

Each chapter ends with **"Now make:"** — a real part from the machine.

| # | chapter | ends by making | status |
|---|---|---|---|
| 9 | Turning: facing, OD, shoulders | `crank-pin`, `pivot-shaft` blanks | stub |
| 10 | Drilling, boring, reaming | `pivot-bushing` bore (Ø6.5 on Ø6.35, 0.15 mm clearance) | stub |
| 11 | Parting off to a length tolerance | the 19 `pivot-bushing` + 19 `lever-bushing` sets — **length sets the 7.0565 mm channel pitch** | stub |
| 12 | Slender work: steadies and followers | `cone-gear-shaft` (Ø0.79 × 34 mm tip journal in steel, 43:1) | stub |
| 13 | Milling: squaring, profiling, edges | `rocker-arm` (R800 concave top edge as a 2D profile, ×20) | stub |
| 14 | Hole patterns and tapping | `rocker-arm-support` (4× 9/16-12), the 20 Ø2.0 spring holes | stub |
| 15 | Indexing and the dividing head | `cylinder-gear` 0.4 mm alignment notches, co-phased | stub |
| 16 | **Making your own gear cutters** | Eureka-method form cutters for DP 49.82 — **off-the-shelf cutters for this pitch do not exist** | stub |
| 17 | **Cutting the gears** | first `cone-gear` (T120, the easy end) | stub |
| 18 | Soft soldering and silver soldering | cone gears onto the shaft (no keyways anywhere in this machine) | stub |
| 19 | Finishing | Draw filing, stoning, polishing, blacking; matching the original's finishes | stub |

## Part IV — Making the parts

Organized by sub-assembly, in build order. Each part gets a spread: drawing,
stock, setups, operations, inspection, and what went wrong the first time.

| # | chapter | parts | status |
|---|---|---|---|
| 20 | Frame and base | `harmonic-base`, `tube-frame`, `top-frame`, `support-bar`, `rocker-arm-support`, feet | stub |
| 21 | The crank and drive train | `crank-arm`, `crank-handle`, `crank-pin`, `crankshaft`, `crank-drive-gear`, `crank-pinion` | stub |
| 22 | **The cone gear set** | `cone-gear` ×20 (T006–T120), `cone-gear-shaft`, the swing platform and its pivot, tip block and adjuster. **The hardest chapter in the book** — the T006 gear has a 0.49 mm wall on a Ø0.79 mm bore. | stub |
| 23 | The cylinder gear set | `cylinder-gear` ×20 with integral eccentric cam and 0.4 mm index notch; `cylinder-gear-shaft`, `arbor-pedestal` | stub |
| 24 | The alignment pinion | `alignment-pinion`, `pinion-arbor`, bracket, lever, cam and lift rod — the sine/cosine setup mechanism | stub |
| 25 | A channel, twenty times | `connecting-rod`, `rocker-arm`, `amplitude-bar`, `channel-lever`, `pivot-bushing`, `lever-bushing`, springs. Batch strategy: how to make twenty identical things by hand without drift. | stub |
| 26 | The measuring stick | `measuring-stick` — hand-stamped divisions, and why the original's are uneven | stub |
| 27 | The summing lever and knife edge | `summing-lever`, `knife-mount`, `knife-hanger-stud`, `boss-hook`, `counter-spring`. The fabrication decision: cast, fabricate, or hog from solid. | stub |
| 28 | The magnifier | `magnifying-lever`, `magnifying-wheel` (100 mm/20 mm coaxial, ×5), bracket, clamp, vertical rod, `lever-wire` | stub |
| 29 | The pen mechanism | `pen-frame`, `pen-v-block`, `pen-rod`, `pen-marker`, `pen-wire`, `output-fixture`. Note: the original was lost; this follows the 2013 reconstruction. | stub |
| 30 | The paper drive | `platen`, `platen-rack`, `platen-guide`, `platen-clip`, transgear train, `chain-sprocket` + roller chain, `transgear-latch` | stub |
| 31 | Springs | 20 channel springs + the counter spring: winding your own, or specifying them for a spring house | stub |
| 32 | Fasteners and small parts | The screw families, period-appropriate heads, and what to substitute | stub |

## Part V — Assembly, calibration, operation

| # | chapter | contains | status |
|---|---|---|---|
| 33 | Assembly | Order of operations, what must be aligned before what, the mates that matter. Mirrors the CAD assembly order. | stub |
| 34 | Alignment and calibration | Squaring the frame, phasing the twenty cams to a common datum, setting spring tension, zeroing the summing lever, setting the magnification. | stub |
| 35 | Operating it | Setting the amplitude bars with the measuring stick, sine vs cosine setup via the alignment pinion, choosing translational gearing, reading the output. | stub |
| 36 | When it doesn't work | Symptom → cause → fix. Written from the real calibration, not imagined. | stub |

## Appendices

| # | appendix | contains | status |
|---|---|---|---|
| A | Bill of materials | Every part, quantity, material, stock size. Generated from `cad/config/parts/`. | stub |
| B | Drawing index | Every drawing sheet, cross-referenced to its chapter. Generated from the CAD build. | stub |
| C | Gear tables | Tooth counts, DP, PA, pitch/outside diameters, centre distances, cutter numbers, dividing-head plates and hole counts for every gear in the machine. | stub |
| D | Fits and tolerances | Every fit in the machine with the shop check that verifies it. From `docs/tolerance-gdt-assessment.md`. | stub |
| E | Suppliers and sources | Stock, tooling, springs, chain. | stub |
| F | The mathematics | The full Fourier treatment for readers who want it, kept out of the build chapters deliberately. | stub |
| G | Further reading | Michelson & Stratton 1898; Hammack, Kranz & Carpenter 2014; the engineerguy series; the machining literature. | stub |

---

## Open questions

- **Page count and format** — drives every print quote in
  [`../kickstarter/rewards/tiers.md`](../kickstarter/rewards/tiers.md). Blocked
  until three chapters are finished at real length.
- **Do drawing sheets ship inside the book, or as a separate pack?** Full-size
  drawings want a larger sheet than a book page. Current thinking: legible
  reduced drawings inline, full-size pack as a free PDF download.
- **How much Fourier maths belongs in Part I** vs Appendix F. Current split:
  Part I gives only what changes a build decision.
- **Chapter 22 ordering** — the cone gears are the hardest part and also the
  most motivating. Early (readers quit) or late (readers are ready)? Currently
  late, gated by Part III.
