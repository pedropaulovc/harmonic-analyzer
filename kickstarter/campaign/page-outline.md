# Campaign page — section by section

Kickstarter pages are read in this order: **video → first image → tiers →
scroll**. Optimize in that order. Everything below is a draft skeleton, not
copy; write the copy last, once the logbook has real machining photographs.

---

## 0. Above the fold

| element | requirement | status |
|---|---|---|
| Project title | ≤ 60 chars, names the machine | draft: *Michelson's Harmonic Analyzer: A Project for Hobby Machinists* |
| Blurb | ≤ 135 chars, states the deliverable | TBD |
| Card image | 1024×576, readable as a thumbnail | needs a hero render — see [`../assets/README.md`](../assets/README.md) |
| Video | 2:00–2:30 | not shot |
| Funding goal | see [`budget.md`](budget.md) | TBD |
| Category | Publishing → Nonfiction (alt: Design → Product Design) | decide before launch |

## 1. The video (2:00–2:30)

The single highest-leverage asset. Rough beat sheet:

1. **0:00–0:15 — the hook.** The real machine drawing a square wave. Twenty
   sine waves added by gears. No narration yet.
2. **0:15–0:40 — what it is.** Michelson, 1898, springs instead of Kelvin's
   ropes. Why it matters: this is an FFT you can turn with your hand.
3. **0:40–1:10 — the problem.** It exists in a glass case in Altgeld Hall.
   There is no plan. Nobody has published how to build one.
4. **1:10–1:45 — what's already done.** Screen-record the CAD model rotating;
   the comparison slider between photograph and render; a drawing sheet.
5. **1:45–2:10 — what the money buys.** Machining the real thing, one part at a
   time, and writing down every operation. Show the shop.
6. **2:10–2:30 — the ask + tiers.**

Do not narrate over silence-worthy footage. The machine's own motion is the
pitch.

## 2. "What you get" — immediately below the video

A single table, before any prose:

- The book (PDF + EPUB, and a print edition at the higher tiers)
- Every CAD file, STEP export and drawing sheet — MIT-licensed, free to all,
  funded or not
- The interactive simulator — free to all
- Named in the acknowledgements at tier N+

## 3. What the machine does

Short. One diagram: crank → cone gears → cylinder gears + cams → rocker arms →
amplitude bars → springs → summing lever → magnifier → pen. The repo already
has renders of every one of those sub-assemblies (`cad/docs/images/`).

Link out rather than explain in full — the engineerguy series does this better
than any campaign page can, and pointing at it builds trust.

## 4. What the book actually contains

Pull the table of contents straight from [`../../book/outline.md`](../../book/outline.md).
Show a real spread, not a mock-up. Show the hardest page — the six-tooth gear
setup — not the prettiest.

## 5. The evidence (this is the section that converts)

The differentiator: the design work is done and inspectable *now*.

- Photo-vs-render comparison slider (from `cad/comparisons/`)
- The dimension-provenance table: every dimension tagged with its source and a
  confidence level
- A machining-DFM excerpt: the three parts that carry the risk, named with real
  numbers
- Link to the GitHub repo and the tagged releases

## 6. Who I am

Software engineer, no prior machining experience, learning it on camera. This
is a feature, not an apology: the book is written by someone who just learned
the skill, for someone about to learn it. Link the
[logbook](../../logbook/README.md).

## 7. Reward tiers

See [`../rewards/tiers.md`](../rewards/tiers.md).

## 8. Timeline

See [`timeline.md`](timeline.md). Kickstarter backers punish optimistic dates
harder than they punish long ones. Quote the honest date, then add slack.

## 9. Risks and challenges

Required by Kickstarter. See [`risks.md`](risks.md). Write it straight — this
section is read by exactly the people most likely to back at a high tier.

## 10. FAQ

See [`faq.md`](faq.md).

---

## Pre-launch checklist

- [ ] Landing page collecting emails, live ≥ 6 weeks before launch
- [ ] ≥ 500 email signups before launch day (rule of thumb: 10–30 % convert in
      the first 48 h, and the first 48 h decides the campaign)
- [ ] Video edited and captioned
- [ ] All page images at final resolution, original work only
- [ ] Tiers locked (they cannot be reduced after launch)
- [ ] Print quote in hand if any physical reward is offered
- [ ] Shipping cost per destination zone, per physical reward
- [ ] Project reviewed by Kickstarter (submit ≥ 1 week ahead)
- [ ] engineerguy notified as a courtesy before launch, not after
