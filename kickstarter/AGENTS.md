# AGENTS.md — kickstarter/

Campaign planning for the book's Kickstarter. Text and asset specs only; no
code, no CAD.

**You do not need the `/developing-solidworks` skill to work in this
directory** — it is required before touching `cad/`, not for prose.

## Rules

- **Never invent a number.** Costs, print quotes, shipping rates, timelines and
  backer counts are either sourced (with the source named inline) or written
  `TBD` / `[EST]`. A plausible-looking fabricated price is worse than a blank.
- **Never claim work is finished that isn't.** The campaign's whole credibility
  rests on the already-public CAD work. Check the claim against the repo before
  writing it: `docs/`, `comparisons/`, the release tags, `cad/scripts/`.
- **Marketing voice, not spec-sheet voice** — but no hype. The audience is
  hobby machinists and people who liked the engineerguy videos; they can smell
  a padded claim. Run drafts through `/humanizer`.
- **Copyright**: cite the 2014 Hammack/Kranz/Carpenter book, never reproduce it.
  Every image on the campaign page must be an original render from this repo's
  CAD or an original photograph. See `campaign/risks.md`.
- Reward-tier changes after launch are effectively irreversible on Kickstarter.
  Treat `rewards/tiers.md` as a design doc that gets reviewed hard before it
  ships, not a scratch pad.

## Where the evidence lives

| claim you want to make | check it here |
|---|---|
| "N parts modelled" | `cad/scripts/build_*.py` |
| "the model matches the real machine" | `comparisons/manifest.json`, the gallery from `doit export` |
| "we know which parts are hard" | `docs/machining-dfm.md`, `docs/tolerance-gdt-assessment.md` |
| "the design is documented to source" | `cad/config/dimensions.yaml`, `cad/DIMENSIONS.md` (rendered) |
| "it's verified, not just drawn" | `verify:soundness` / `verify:kinematics` in `dodo.py` |
