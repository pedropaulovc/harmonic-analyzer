# Positioning

## The one-liner

> **A 19th-century mechanical computer, reverse-engineered into a shop manual.**
> Michelson's harmonic analyzer adds twenty sine waves with gears and springs.
> Nobody has published how to build one. This book does — every part, every
> setup, every cut.

## The audience, in priority order

1. **Hobby machinists with a lathe and a mill** who want a project that is
   hard, beautiful, and finite. They buy books like *Gears and Gear Cutting*
   and read Machinery's Handbook for fun. They are the paying core.
2. **The engineerguy audience.** Bill Hammack's four-video series on this
   machine has millions of views and no follow-through — there is nowhere to go
   after watching it. This book is the place to go.
3. **Mathematicians, physicists and educators** who want a Fourier machine on a
   department bench. They may not machine it themselves, but they buy the book
   and they are the ones who share it.
4. **People who just like the object.** Coffee-table interest. They fund at the
   low tiers and drive the algorithm.

## Why this project and not another

- **The machine is famous and undocumented.** The 2014 book is a *visual tour* —
  gorgeous photographs, no dimensions, no drawings, no process. There is no
  build plan anywhere, in print or online.
- **The hard half is already done and public.** A complete parametric CAD model
  with 102 parts, verified assemblies, and a photo-comparison gallery scoring
  it against the surviving machine. Backers can look at it before they pledge.
- **It is a genuine skills ladder.** Facing a bar → turning bushings to a length
  tolerance → boring → indexed gear cutting with self-made form cutters. A
  reader finishes it a better machinist, not just an owner of a thing.
- **The failure mode is honest.** If the pen never draws a clean square wave,
  that is still a book — the machining chapters stand alone and the debugging
  is the interesting part.

## What we are NOT selling

- Not a kit. Not machined parts. Not a finished analyzer. (See
  [`../rewards/tiers.md`](../rewards/tiers.md).)
- Not a CNC project. The point is **manual mill and lathe**, period-appropriate
  methods, with CNC as an optional accelerator for the 20× repeat families.
- Not a reprint of the 2014 book, and not affiliated with it.

## Competitive / adjacent shelf

| work | what it gives | what it doesn't |
|---|---|---|
| Hammack, Kranz & Carpenter, *Albert Michelson's Harmonic Analyzer* (2014) | The definitive visual and conceptual tour | No dimensions, no drawings, no process |
| engineerguy video series (4 parts + bonuses) | How the machine works, on video | Nothing to build from |
| Michelson & Stratton, *A New Harmonic Analyzer* (1898) | The primary source, 80-element variant | 13 pages, no shop detail |
| Gingery, *Build Your Own Metal Working Shop From Scrap* | The genre template — sequenced shop instruction that assumes nothing | Different machine, different era |
| Model-engineering serials (*Model Engineer*, *Home Shop Machinist*) | The tone and pacing to imitate | Serialized, not a single project |

**The gap this fills:** the visual tour exists, the primary source exists, the
machining tradition exists. The bridge — *here is how you actually cut a
0.49 mm-wall six-tooth gear* — does not.

## Proof points to lead with (all verifiable today)

- 102 parts, 8 sub-assemblies, 95 curated manufacturing drawings. (Counted from
  the build graph: `uv run python -m doit list --all`, needs no SolidWorks seat.)
- Every dimension traced to a source (book page, photograph, or derivation) with
  a confidence level — `cad/config/dimensions.yaml`.
- Assemblies gated on degrees of freedom, interference and mass properties on
  every build; a kinematic model you can drag by the crank.
- A per-part manufacturability pass that already names the three parts carrying
  the risk: the six-tooth cone gear, the summing lever's knife edge, and the
  0.79 mm cone-gear shaft journal.

## Tone

Machinist-to-machinist. Specific numbers over adjectives. Show the 0.49 mm wall
and say "this is the part that will beat you", not "an exciting challenge
awaits". Admit what isn't solved.
