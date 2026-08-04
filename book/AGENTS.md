# AGENTS.md — book/

Quarto book source. Prose and figures; no CAD, no COM.
**The `/developing-solidworks` skill is not required to work here** — it gates
`cad/`, not writing. It *is* required if a task sends you into `cad/scripts/`
to change geometry.

## Non-negotiables

1. **Never invent a machining process.** Every setup, feed, speed, tool and
   depth of cut in this book comes from an actual operation recorded in
   `logbook/entries/`, or from a cited reference (`references/machinerys-handbook/`,
   `references/gears-and-gear-cutting/`,
   `references/machining-for-hobbyists-getting-started/`). If neither exists,
   write `TODO(cut it first)` — do not fill the gap with something plausible.
   A wrong feed rate in a machining book breaks tools and hurts people.
2. **Every dimension comes from the model, not from memory.** The source of
   truth is `cad/config/` and `cad/scripts/build_*.py`. Quote the number and
   name where it came from. `cad/config/dimensions.yaml` carries provenance and
   a confidence level per dimension — carry the caveat through when confidence
   is low.
3. **Every figure is generated or tracked, never pasted.** CAD figures come
   from `cad/out/` via `scripts/collect_figures.py`; hand-drawn diagrams live in
   `figures/hand/` and are tracked. Nothing from the 2014 Hammack/Kranz/
   Carpenter book goes in this commercial product — see
   `kickstarter/campaign/risks.md`.
4. **Chapter status is honest.** The `status:` field in each chapter's
   frontmatter is one of `stub` → `drafted` (written from CAD, not yet cut) →
   `verified` (the part has been made following exactly this text). Never
   promote a chapter's status because it reads well.
5. **Units: millimetres primary.** The model is metric; the original machine is
   a mix (the fastener policy is US customary — see
   `memory/fastener-policy-us-customary.md`, and drill/tap sizes are imperial).
   Give mm first with the inch equivalent in parentheses where a reader will
   buy an imperial tool: `Ø9.525 mm (3/8")`.
6. **Safety language is not decorative.** Where an operation can grab, throw or
   cut, say so specifically ("the 0.4 mm slitting saw will grab if the feed
   stalls"), not generically.

## Voice

Machinist-to-machinist, second person, imperative for operations. Short
sentences. Numbers over adjectives. Say what will go wrong before it does.
Model the tone on *Gears and Gear Cutting* and the Home Shop Machinist serials,
not on a textbook.

## Adding a chapter

1. Copy `_templates/part-chapter.qmd` (a part) or `_templates/operation.qmd`
   (a skill/operation).
2. Add it to `_quarto.yml` in reading order — chapter order lives there, not in
   filenames alone.
3. Add a row to `outline.md`.
4. Cross-reference with Quarto refs (`@sec-cone-gears`, `@fig-cone-tip`), never
   with page numbers.

## Rendering

`quarto render book`. If it fails on LaTeX, `quarto install tinytex` first.
Don't commit `_book/`, `.quarto/` or `figures/generated/` — all gitignored.
