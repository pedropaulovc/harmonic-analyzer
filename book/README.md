# The book

**_Albert Michelson's Harmonic Analyzer: A Project for Hobby Machinists_**.
Step-by-step machining instructions for building a working 20-element harmonic
analyzer on a manual mill and lathe.

This is the project's main deliverable, and everything else exists to support
it. The [CAD model](../cad) supplies the geometry. The
[logbook](../logbook/README.md) supplies the process, since I learn each
operation before writing it up. The [simulator](../web/README.md) shows readers
what they are building, and the [Kickstarter](../kickstarter/README.md) pays for
it.

## Status

Outline drafted, chapters stubbed, no finished prose yet. The plan and the
per-chapter status live in [`outline.md`](outline.md).

## Build it

Authored in [Quarto](https://quarto.org): Markdown in, print PDF plus HTML plus
EPUB out.

```powershell
# one-off: install Quarto (https://quarto.org/docs/get-started/) and a LaTeX engine
quarto install tinytex

# refresh figures from the CAD build, then render
uv run python book/scripts/collect_figures.py
quarto render book                 # all formats -> book/_book/
quarto render book --to pdf        # just the print PDF
quarto preview book                # live-reload HTML while writing
```

`collect_figures.py` copies renders and drawing sheets out of `cad/out/` into
`book/figures/generated/` (gitignored) and writes a manifest. A chapter can then
reference a stable path while the render itself stays a build artefact. It also
deletes figures the build no longer produces, so a renamed render cannot leave a
stale copy behind for a chapter to keep pointing at. Run `doit build` first if
`cad/out/` is empty or stale.

## Layout

```
book/
  _quarto.yml          project + book config (chapter order lives here)
  index.qmd            title page / front matter
  outline.md           the plan: every chapter, what's in it, status
  front/               preface, how to use this book, safety
  chapters/            the book, in reading order
  appendices/          BOM, drawing index, cutter tables, fits, suppliers
  _templates/          skeletons for a new part chapter / operation
  figures/
    generated/         copied from cad/out by scripts/collect_figures.py (gitignored)
    hand/              hand-made diagrams, tracked
  scripts/             figure collection and other build helpers
  references.bib       citations
```

## The rule that matters

Nothing goes in this book that hasn't been done. A chapter describing an
operation gets written after that operation has been performed and logged in
[`logbook/`](../logbook/README.md), with the real feeds, speeds, setups,
measurements and mistakes. A plausible-sounding process that was never actually
cut is the one thing that would make the whole book worthless.

Chapters can be *drafted* ahead from the CAD model, which is what the `status:`
field in each chapter's frontmatter tracks. But a chapter is not `verified`
until the part exists on the bench.
