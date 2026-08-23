# The book

**_Albert Michelson's Harmonic Analyzer: A Project for Hobby Machinists_**.
Step-by-step machining instructions for building a working 20-element harmonic
analyzer on a manual mill and lathe.

The book is the main machining and publication deliverable. The
[CAD model](../cad) supplies the geometry, the
[logbook](../logbook/README.md) supplies the process, the
[website](../web/README.md) shows readers what they are building, and the
[Kickstarter](../kickstarter/README.md) funds the work. The
[AI story](../ai-story/README.md) is a separate, first-class workstream.

## Work status

Current Book workstream status and sequencing live in the
[Harmonic Analyzer project](https://github.com/users/pedropaulovc/projects/1).
Each chapter's `status:` frontmatter is authoritative for its own maturity.
[`outline.md`](outline.md) owns scope and order, not status.

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
  outline.md           the plan: every chapter, scope and reading order
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

Chapters may be drafted from CAD and cited references before the corresponding
shop work. A draft must not present an unperformed feed, setup or measurement as
observed fact; it marks that gap `TODO(cut it first)`.

Real feeds, speeds, setups, measurements and mistakes come from
[`logbook/`](../logbook/README.md). A chapter becomes `verified` only after the
part has been made by following the text.
