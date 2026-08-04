# Positioning

## The one-liner

> **A 19th-century mechanical computer, reverse-engineered into a shop manual.**
> Michelson's harmonic analyzer adds twenty sine waves with gears and springs.
> It has been beautifully explained, but nobody has written down how to build
> one. This book is that: every part, every setup, every cut. The machine it
> produces goes to a university maths museum.

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

- **The machine is famous, thoroughly explained, and still unbuildable.** Do not
  claim it is undocumented; that is both false and unfair to the people who
  documented it. The 2014 book and the video series explain the mechanism about
  as well as it can be explained. What they are is a *visual tour*: gorgeous
  photographs, a handful of scattered dimensions, no drawings, no tolerances, no
  process. The gap is the shop floor, not the understanding.
- **It has a destination, and that destination is arranged.** The finished
  machine goes to [Matemateca](https://matemateca.ime.usp.br/index_ingles.html),
  the mathematics outreach collection at IME-USP, for use with middle and high
  school students. The professor who runs the collection is on board. Backers
  are not funding a hobby; they are funding a working Fourier machine for a
  public maths collection, and the builder does not keep it.

  This is the strongest single asset on the page. Lead with it.

  Three specifics make it land, and all three are checkable:
  1. It fills a real gap in their collection. They already have a harmonograph,
     Chladni plates, a harmonic-series piece, a sampling piece, gears, an adding
     machine and a slide rule. They do not have anything that decomposes a curve
     into its frequencies mechanically.
  2. Their own donations page says complex pieces are the ones they struggle to
     produce, because it is hard to find someone who can turn the theory into an
     object. A 102-part working analyzer is the far end of that scale.
  3. It makes the book's audience and the machine's audience different people,
     which is unusual and good: machinists fund it, schoolchildren use it.

  **Before their name goes on a public commercial page, get written
  confirmation.** An enthusiastic email from a professor is not the same as an
  institution agreeing to appear in a crowdfunding campaign. See
  [`risks.md`](risks.md).
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
