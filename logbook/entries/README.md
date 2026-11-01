# Entries

One file per session at a machine: `YYYY-MM-DD-<slug>.md`, from
[`TEMPLATE.md`](TEMPLATE.md).

**Every observation comes from the person who did the work.** They write the
entry, or hand an agent their session notes; the agent interviews them and
writes it up (see [`../AGENTS.md`](../AGENTS.md#writing-an-entry)). Every feed,
speed, measurement and failure in the book traces back to an entry here, so a
fabricated observation would poison the whole book.

## What makes an entry useful later

- **The numbers you actually used**, not the ones you meant to use.
- **The failures, in full.** A scrapped part with the reason is worth more than
  three successes.
- **Time.** Real hours per part is the number the book publishes and the
  Kickstarter timeline is built on. Nobody else has it.
- **What surprised you.** You only get to be a beginner once, and that
  perspective is the book's whole edge.

## Conventions

- Frontmatter `outcome` is one of `success` · `partial` · `scrapped` ·
  `aborted`. Don't invent others — [`../progress.md`](../progress.md) counts
  them.
- Name the module in frontmatter so the module's session table can be updated.
- Raw photos and video go outside the repo (`logbook/media/` is gitignored);
  link them. Only frames destined for the book get committed, into
  `book/figures/hand/`.
- Explanatory sketches (setups, workholding, cutter paths) are drawings, not
  raw media: commit them as `figures/YYYY-MM-DD-<slug>.png` and embed them in
  the entry.
- Advice received after a session goes in an optional
  `## Advice afterwards (from <who>, not yet tried)` section after `## Open`,
  never in the observed sections. The next entry says what held up.
- A deliberate mistake on scrap (a module's controlled mistakes) is logged
  like any other session, with part `practice`. Say in "What happened" that it
  was deliberate, what you predicted, and what the wrong way and then the right
  way looked, sounded and measured like.

## Index

| date | entry | module | part | outcome | hours |
|---|---|---|---|---|---:|
| 2026-10-29 | [Install the 6 in vise and start the oblique-jig base bar](2026-10-29-vise-install-and-first-cuts.md) | M06 | `ch-rocker-arm-tl-oblique-base-bar` | partial | 6.5 |
| 2026-10-30 | [Get the pendant working, then rough the base bar to length](2026-10-30-pendant-and-roughing-base-bar-to-length.md) | M07 | `ch-rocker-arm-tl-oblique-base-bar` | scrapped | 5.0 |
