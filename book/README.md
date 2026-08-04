# The book

**_Albert Michelson's Harmonic Analyzer: A Project for Hobby Machinists_** —
step-by-step machining instructions for building a working 20-element harmonic
analyzer on a manual mill and lathe.

This is the project's main deliverable. Everything else exists to support it:
the [CAD model](../cad) supplies the geometry, the
[logbook](../logbook/README.md) supplies the process (I learn each operation
before writing it up), the [simulator](../web/README.md) shows readers what
they're building, and the [Kickstarter](../kickstarter/README.md) funds it.

## Status

Outline drafted, chapters stubbed, **no finished prose**. See
[`outline.md`](outline.md) for the full plan and per-chapter status.

## Build it

Authored in [Quarto](https://quarto.org) — Markdown in, print PDF + HTML +
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
`book/figures/generated/` (gitignored) and writes a manifest, so a chapter
references a stable path and the render itself stays a build artefact. Run
`doit build` first if `cad/out/` is empty or stale.

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

**Nothing goes in this book that hasn't been done.** A chapter describing an
operation is written after that operation has been performed and logged in
[`logbook/`](../logbook/README.md), with the real feeds, speeds, setups,
measurements and mistakes. A plausible-sounding process that was never cut is
the one thing that would make this book worthless.

Chapters may be *drafted* ahead from the CAD model — see the `status:` field in
each chapter's frontmatter — but a chapter is not `verified` until the part
exists on the bench.
