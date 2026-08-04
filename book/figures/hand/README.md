# Hand-made figures

Tracked figures that are **not** generated from the CAD build: signal-path
diagrams, setup sketches, exploded views drawn by hand, scanned notes.

Everything in `../generated/` is copied out of `cad/out/` by
[`../../scripts/collect_figures.py`](../../scripts/collect_figures.py) and is
gitignored. Everything here is committed.

## Rules

- **Original work only.** Nothing traced from or scanned out of the 2014
  Hammack/Kranz/Carpenter book — this is a commercial product. See
  `kickstarter/campaign/risks.md`.
- Prefer vector (SVG/PDF) for diagrams so they survive print scaling.
- Name a figure after what it shows, not after the chapter it appears in —
  chapters get renumbered.
- Keep the source file (`.svg`, `.drawio`) next to the export, not just the
  export.
