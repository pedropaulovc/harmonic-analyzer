# AGENTS.md — logbook/

A machining curriculum and its practice log. Prose only.
**The `/developing-solidworks` skill is not required here.**

## What an agent may and may not do

**May:**
- Draft or restructure curriculum modules from the cited references.
- Look up speeds, feeds, tap drills, indexing plates and fits in
  `references/machinerys-handbook/` (there is a local search index) and
  `references/gears-and-gear-cutting/`, and write them into a module **with the
  citation attached**.
- Derive which parts a module unlocks from `cad/scripts/build_*.py`,
  `cad/config/parts/*.yaml` and `cad/docs/machining-dfm.md`. Shop tooling
  (`*-tl-*` jigs and fixtures) counts as a module's part when the build needs
  it.
- Propose controlled mistakes for a module, within the
  [rules](curriculum/README.md#the-twist-break-it-on-purpose-first): on scrap,
  low energy, one variable changed from a known-good setup. Never propose one
  that could throw the work or the tool, or that puts hands, gloves or sleeves
  near rotation; describe that mistake instead of staging it.
- Write log entries from the user's session notes, following the workflow
  below.
- Tidy, format and cross-link entries.
- Draw explanatory sketches (setups, workholding, cutter paths) for an entry
  and commit them under `entries/figures/YYYY-MM-DD-<slug>.png`. A sketch is a
  drawing, not a record: it may show a proposed setup, but any number on it
  that describes what happened must come from the entry.
- Add the advice the user asks for to an entry, in an
  `## Advice afterwards (from <who>, not yet tried)` section after `## Open`.
  It is attributed and marked untried so it is never read as an observation;
  a later entry records what held up. Mark anything not checked against the
  user's machine or config `unverified`.
- Update `progress.md` and `SKILLS.md` from what the entries actually say.

**May not:**
- **Invent a number or an observation.** Every speed, feed, DOC, measured
  value, duration and event in an entry comes from the user. If a value is
  unknown, the entry says so; it is never filled in from a reference or a
  calculation. In a *curriculum* module a starting value may be quoted from a
  reference — cite it, and mark it as a starting point, not a result.
- **Mark a module complete.** Competency is the user's call, made at the
  machine.
- Soften a failure. If the user says the part was scrapped, it stays scrapped.
- Put advice or a proposed setup anywhere but the advice section, or present
  it as something the user did.

## Writing an entry

The user hands over a session as bullet points or loosely organized notes.

1. **Interview.** Before drafting, ask the clarifying questions a curious
   novice hobby machinist would ask on hearing the story: why that approach,
   what went wrong and how they noticed, how they fixed it, what it felt like,
   what they'd do differently, and the numbers a reader would want (RPM, feed,
   DOC, sizes, readings, time spent). Settle the frontmatter too: module,
   machine, part (or `practice`), outcome (one of the four in
   `entries/README.md`) and hours. Batch questions by topic, then follow up
   only on what's still missing. Resolve shorthand, tool names and part names
   rather than guessing them.
2. **Draft** from [`entries/TEMPLATE.md`](entries/TEMPLATE.md) as
   `entries/YYYY-MM-DD-<slug>.md`, dated the day of the session. Write in the
   user's first person and keep their voice; the "What happened" narrative
   carries the story, including false starts. Leave a template section out
   or mark a value `not recorded` rather than padding it.
3. **Cross-check** part names, stock and equipment against the CAD registry
   and `cad/process/shop/inventory.toml`. Link the module, the part when the
   session made one (not for `practice`), and any PR or issue the session
   produced. Where the notes and the repository disagree, ask; don't silently
   correct either.
4. **Publish.** Update the entry index in `entries/README.md` and the
   `progress.md` roll-up, then commit and open a PR under the ordinary git
   workflow.

## Curriculum module format

Every module has, in this order: objectives · prerequisites · references ·
practice · controlled mistakes · **the part that motivates it** ("now make") ·
competency check (with a number) · notes · sessions, with estimated hours and
status in the frontmatter. Keep it. The book's Part III chapters are generated
from this structure, and a module missing its "now make" has no place in a
course built around a machine.

## Status vocabulary

`not started` → `in progress` → `competent` (check passed) → `applied` (a real
part made with it). Use exactly these.

The `status:` frontmatter in each curriculum module is authoritative. Index and
progress tables link to it rather than copying the value.
