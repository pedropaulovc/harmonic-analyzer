# Kickstarter — funding the book

**Status: pre-launch, nothing published.** Everything here is a draft.

The campaign funds one thing: the time and material to machine a Michelson
harmonic analyzer from scratch and write down every operation, so a hobby
machinist with a lathe and a mill can build one too.

| what | where |
|---|---|
| Who this is for, and the one-sentence pitch | [`campaign/positioning.md`](campaign/positioning.md) |
| The campaign page, section by section | [`campaign/page-outline.md`](campaign/page-outline.md) |
| Reward tiers and what each one costs to fulfil | [`rewards/tiers.md`](rewards/tiers.md) |
| Funding goal, built up from real line items | [`campaign/budget.md`](campaign/budget.md) |
| Risks & Challenges (Kickstarter requires this section) | [`campaign/risks.md`](campaign/risks.md) |
| Pre-launch → launch → fulfilment schedule | [`campaign/timeline.md`](campaign/timeline.md) |
| Every image, video and graphic the page needs | [`assets/README.md`](assets/README.md) |
| Questions backers will ask | [`campaign/faq.md`](campaign/faq.md) |

## The honest position

Kickstarter's own data says the campaigns that fund are the ones that look
finished before they launch. This project's advantage is that a large,
verifiable chunk of the work is *already done and public*:

- ~115 parts modelled in SolidWorks, generated from Python scripts, with a
  build pipeline that gates every assembly on DOF, interference and mass
  properties (see the root [README](../README.md)).
- A photo-vs-CAD comparison gallery scoring the model against Hammack, Kranz
  and Carpenter's photographs of the surviving University of Illinois machine.
- A per-part manufacturability pass ([`docs/machining-dfm.md`](../docs/machining-dfm.md))
  that already names the three parts carrying the whole risk.

The campaign should lead with that evidence, not with a promise.

## Hard rules for this directory

1. **No pricing, quote, or reward tier is real until it is sourced.** Anything
   speculative is marked `TBD` or `[EST]`. Do not let an estimate quietly
   become a commitment on the campaign page — Kickstarter tiers cannot be
   edited downward after launch.
2. **Do not promise a physical machine as a reward.** Building one analyzer is
   the project; building twenty is a manufacturing business. See
   [`rewards/tiers.md`](rewards/tiers.md) for what is and isn't shippable.
3. **Respect the source material's copyright.** *Albert Michelson's Harmonic
   Analyzer* (Hammack, Kranz & Carpenter, 2014) is free to view and share
   **for non-commercial purposes**. This book is commercial. It may cite,
   reference and build on that work; it may **not** reproduce its photographs
   or text. Original renders, original photographs, original prose only. See
   [`campaign/risks.md`](campaign/risks.md) §IP.
4. **The machine is not patented and never was** — Michelson's design is
   comfortably public domain. The constraint is the 2014 book, not the 1898
   machine.
