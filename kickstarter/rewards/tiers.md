# Reward tiers — draft

> **Nothing here is committed.** Every price is `[EST]` until a quote backs it.
> Kickstarter tiers cannot be lowered or removed after launch, and a physical
> reward whose fulfilment cost was underestimated turns a funded campaign into a
> personal debt. Read [`fulfilment.md`](fulfilment.md) before touching a price.

## Design principles

1. **The digital book is the product.** Everything else is packaging.
2. **Every physical reward must have a quoted unit cost, a quoted shipping cost
   per zone, and a supplier that has confirmed the quantity** before it appears
   on the page.
3. **No reward may require machining by me at scale.** One analyzer is the
   project. Twenty is a factory. This rules out machined parts as rewards —
   with one deliberate exception below, capped hard. Note that the machine
   itself is already spoken for: it is being donated to Matemateca at IME-USP,
   so "the analyzer" was never available as a reward at any price.
4. **The CAD files, drawings and simulator stay free and MIT-licensed
   regardless of funding.** They are already public; making them a reward would
   be dishonest and would kill the goodwill the campaign runs on.

## Draft ladder

| # | tier | price `[EST]` | contents | unit cost | fulfilment risk |
|---|---|---|---|---|---|
| 1 | **Supporter** | $10 | Digital book (PDF + EPUB) on release; name in the backers list | ~$0 | none |
| 2 | **Machinist's Edition** | $35 | Tier 1 + the full drawing pack as print-ready PDFs, sized for the shop wall; build-log access as it's written | ~$0 | none |
| 3 | **Print** | $75 `[EST]` | Tier 2 + softcover print edition, shipped | print `TBD` + ship `TBD` | **high — needs a real print quote** |
| 4 | **Hardcover** | $120 `[EST]` | Tier 3 but hardcover, numbered | print `TBD` + ship `TBD` | **high** |
| 5 | **Acknowledged** | $250 `[EST]` | Tier 4 + name printed in the acknowledgements (must close before print deadline) | as tier 4 | medium — hard deadline |
| 6 | **Cone Gear** | $500 `[EST]`, **limit 20** | Tier 4 + one spare cone gear from the actual build run, mounted, with its inspection sheet | material ≈ $0, **time = the real cost** | **highest — see below** |
| 7 | **Workshop** | $1500 `[EST]`, **limit 5** | Tier 4 + a live video walkthrough of the build and a Q&A on your own build | time | medium |

## Tier 6 is the one to argue about

The cone gears are cut 20-at-a-time on a dividing head from a self-made form
cutter (`cad/docs/machining-dfm.md`). Cutting a few spares during that same session
is genuinely marginal work — *if* the setup succeeds and *if* the run happens
before the fulfilment deadline. Both are real ifs.

Options, in order of safety:

- **Cut it.** Safest. No physical reward above the print tiers.
- **Cap at 10, and only unlock the tier after the first successful gear run.**
  Kickstarter allows adding tiers mid-campaign; it does not allow removing one.
  This is the recommended path.
- **Offer it as a stretch goal**, contingent on the run succeeding.

Do **not** offer a full gear set, a kit, or an assembled analyzer at any price.

## Open questions

- [ ] Print-on-demand (Lulu / Blurb / IngramSpark) vs a short offset run — the
      answer changes tiers 3–5 entirely, and offset requires a minimum order
      that a modest campaign can't absorb.
- [ ] Is the print edition full-colour? The CAD renders and the photography
      argue yes; full-colour offset roughly doubles unit cost.
- [ ] Page count estimate — drives every print quote. Blocked on
      [`../../book/outline.md`](../../book/outline.md) reaching stable chapter
      lengths.
- [ ] Shipping zones offered. Shipping from Brazil vs a US/EU fulfilment
      partner is the single biggest cost swing on this page.
- [ ] VAT/customs handling for EU backers on physical rewards.
