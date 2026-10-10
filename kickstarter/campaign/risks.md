# Risks and challenges

Kickstarter requires this section. Written straight — the people who read it
carefully are the ones who back at the top tiers.

## Technical

**The six-tooth cone gear may not be machinable in my shop.** It is a gear 4.31 mm
across on a 1/32 in (0.79 mm) bore, leaving about 0.64 mm of metal between
tooth root and bore. `cad/docs/machining-dfm.md` calls it the single hardest part in the machine.
*Mitigation:* the original used a harder yellow metal for the tip gears; if my
first articles fail, the book documents the failure and the fallback (outsourced
wire-EDM), which is itself useful to a reader. **The book ships either way.**

**Two gears need tooling I don't have yet.** The gear train uses standard 20°
inch pitches, so stock cutters cover almost every gear
(`cad/docs/gear-standard.md`). The six-tooth cone gear falls outside every
stock cutter range, so it needs a form tool I grind myself
(DT6-FORM1), a skill I have not learned yet. The 64-tooth
crank gear is helical and needs a dividing head that can cut spirals; the head
in the shop is sold as semi-universal. *Mitigation:* cutter-making is scheduled
early in the curriculum, and the spiral head is a budget line (cost TBD) with
outsourcing that one gear as the fallback.

**The summing lever's knife edge is a casting-shaped organic part with a
delicate precision ridge.** Current thinking is a hardened tool-steel insert
rather than machining it into the parent. Unresolved.

**The model may be wrong somewhere.** Every dimension is traced to a source with
a confidence level, but the surviving machine has not been measured directly —
the model is derived from photographs, the 1898 paper, and the 2014 book.
Where the model and reality disagree, reality wins and the book says so.

**The machine may not produce clean output.** Twenty spring-loaded channels
summing onto a knife-edge lever is an error-stacking nightmare. Calibration
could take longer than machining.

## Schedule

**I am learning machining from scratch for this project.** That is the point of
the [logbook](../../logbook/README.md), and it is the largest schedule risk.
A skill takes as long as it takes. *Mitigation:* the curriculum is sequenced so
each module ends by cutting a real part from the machine — progress is never
purely practice.

**Single point of failure.** One person, one shop, one seat. Illness or a
machine breakdown moves everything.

*Mitigation for both:* the dates on the campaign page carry deliberate slack,
and the manuscript is written continuously as parts are cut rather than in one
block at the end.

## Fulfilment

Print and shipping quotes are not yet in hand; see
[`../rewards/fulfilment.md`](../rewards/fulfilment.md). No physical reward goes
on the page without a confirmed unit cost and per-zone shipping.

## The donation

The finished machine is going to [Matemateca](https://matemateca.ime.usp.br/index_ingles.html)
at IME-USP, and the professor who runs the collection is enthusiastic about it.

Two things follow, and neither is optional.

**Get it in writing before their name appears on a commercial page.** A warm
email from an academic is not an institution consenting to appear in a
crowdfunding campaign, and a university's name on a page that takes money
carries an implication of endorsement that nobody has agreed to. Ask for
explicit written confirmation covering: that they accept the donation, that
their name and a link may appear on the campaign page, and how they want to be
described. If they would rather not appear until the machine is delivered,
that is a completely reasonable answer and the campaign works without it.

**The donation is a public promise, so it constrains the build.** A museum piece
operated by school groups has to tolerate handling that a builder's shelf model
never would: the amplitude bars get slid by teenagers, the crank gets turned
hard, and the wires that drive the pen can fly off the magnifying wheel if the
setup is done carelessly. That is a real design input, not a sentiment. Where it
conflicts with period fidelity, say which one won and why.

## Intellectual property {#ip}

**The machine is public domain.** Michelson and Stratton published in 1898;
Wm. Gaertner & Co. built them between 1896 and 1923. No live patent, no live
design right.

**The 2014 book is not.** *Albert Michelson's Harmonic Analyzer: A Visual Tour
of a Nineteenth Century Machine that Performs Fourier Analysis* by Bill Hammack,
Steve Kranz and Bruce Carpenter is © 2014 and distributed free **for
non-commercial purposes**. This project is commercial. Therefore:

- Every photograph and drawing in the commercial book must be original.
- No text from the 2014 book is reproduced.
- Dimensions derived by measuring published photographs are facts about a
  public-domain object, not expression — but the photographs themselves stay
  out of the commercial product.
- The 2014 book is cited generously as the source that made this possible, and
  readers are pointed to it.
- The reference material in `references/` (submodule) and the comparison
  gallery are **research inputs and open-source artefacts**, not campaign or
  book assets. Keep that boundary sharp: `cad/comparisons/ATTRIBUTION.md` covers
  the CC BY imagery in the open repo, not in a product for sale.

**Unresolved: which licence actually covers the book's photographs.**
`cad/comparisons/ATTRIBUTION.md` states that both the 2014 book and the video
series are published under **CC BY**, which would permit commercial reuse with
attribution. The book PDF's own front matter says something different: "© 2014
... All rights reserved" and "free for you to view and share for
**non-commercial** purposes". Those cannot both be right, and the difference
decides whether a single book photograph may appear anywhere near this campaign.

The engineerguy *videos* are CC BY with high confidence; the *book* is the
doubtful one, and the ch30 plates are book plates.

The README no longer depends on the answer. It used to pair a ch30 plate with
the CAD render; it now pairs a first-party photograph of the machine in its
display case with a render posed to match
(`cad/docs/images/real-machine-display-case.jpg`, and see that folder's README).
That closes the only place a book plate was doing load-bearing work in public.

*Action:* resolve it before launch anyway, because the book and the campaign
page still need to know.
1. Ask Bill Hammack directly. One email settles it, and it pairs naturally with
   the courtesy note below.
2. Until it is settled, keep book imagery out of anything that is itself for
   sale (the book interior, the campaign page, reward material).
3. If the answer is "non-commercial only", nothing has to be pulled, but every
   future figure has to be first-party. The photogrammetry set
   (`references/photogrammetry/raw/`, 90 captures from 2025-08-28) is close-ups
   through glass with a scale bar in frame, so it does not double as
   illustration; budget for a proper photo session, or use CAD renders.

*Action before launch:* a courtesy note to Bill Hammack. Not legally required;
obviously right, and he may well be a supporter. Fold question 1 above into it.

**This project is not affiliated with or endorsed by the authors of the 2014
book, engineerguy, or the University of Illinois.** Say so on the page.
