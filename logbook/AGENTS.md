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
  `cad/config/parts/*.yaml` and `cad/docs/machining-dfm.md`.
- Tidy, format and cross-link entries the user has written.
- Update `progress.md` and `SKILLS.md` from what the entries actually say.

**May not:**
- **Write a log entry.** `entries/` records what the user did at a real
  machine. An agent-written entry is a fabricated observation, and the book is
  built on these. Create the file from the template, leave it empty.
- **Invent a number.** Any speed, feed, DOC or measured value in an entry comes
  from the bench. In a *curriculum* module a starting value may be quoted from
  a reference — cite it, and mark it as a starting point, not a result.
- **Mark a module complete.** Competency is the user's call, made at the
  machine.
- Soften a failure. If an entry says the part was scrapped, it stays scrapped.

## Curriculum module format

Every module has, in this order: objectives · prerequisites · references ·
practice · **the real part it unlocks** · competency check (with a number) ·
estimated hours · status. Keep it. The book's Part III chapters are generated
from this structure, and a module missing its "now make" has no place in a
course built around a machine.

## Status vocabulary

`not started` → `in progress` → `competent` (check passed) → `applied` (a real
part made with it). Use exactly these.

The `status:` frontmatter in each curriculum module is authoritative. Index and
progress tables link to it rather than copying the value.
