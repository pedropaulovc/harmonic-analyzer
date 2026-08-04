# Campaign assets

Inventory and specs. **Binaries do not live here** — renders come from the
build (`cad/out/`, gitignored), photographs from the logbook, and finished
campaign exports are uploaded to Kickstarter, not committed. This file tracks
what exists, what's missing, and to what spec.

## Specs

| asset | dimensions | format | notes |
|---|---|---|---|
| Project card image | 1024×576 min (16:9) | JPG/PNG | must read at thumbnail size — one recognisable silhouette, no small text |
| Page images | ≥ 1024 wide | JPG/PNG | Kickstarter shows them full-width |
| Video | 1080p, 2:00–2:30 | MP4 | captions required |
| Video thumbnail | 1024×576 | JPG | |
| Update images | ≥ 1024 wide | JPG | one per update, every update |

## Inventory

| # | asset | source | status |
|---|---|---|---|
| A1 | Hero render, iso view | `cad/docs/images/hero.png` | **exists** — re-render at campaign resolution |
| A2 | Sub-assembly renders (frame, drive train, channel, summing, magnifier, pen, paper drive) | `cad/docs/images/*.png` | **exists** |
| A3 | Drawing sheets | `cad/docs/images/*-drawing.png`, `doit export` | **exists** — pick the two most legible |
| A4 | Photo-vs-render comparison slider stills | `cad/comparisons/` gallery (`doit export`) | regenerate; needs Blender seat |
| A5 | Exploded view of one channel | new render | **missing** |
| A6 | Cone gear set close-up, showing the T006 tip gear against a coin for scale | new render + later a photo | **missing** |
| A7 | The signal diagram: crank → cones → cylinders+cams → rockers → bars → springs → summing → magnifier → pen | new, vector | **missing** |
| A8 | Shop photographs: the mill, the lathe, the bench | photo | **missing** |
| A9 | Machining footage: first chips, a gear being indexed, a bushing parted off | video | **missing — gates the launch** |
| A10 | The book spread mock-up (real pages, not a template) | `book/` render | **missing** — blocked on two finished chapters |
| A11 | Portrait / talking-head for the video | photo | **missing** |
| A12 | Animated GIF of the simulator running | `web/` | **missing** |

## Rules

- **Original work only.** No photograph, diagram or page from the 2014 book, in
  any campaign asset. See [`../campaign/risks.md`](../campaign/risks.md).
- Renders are regenerated from the current model, never reused from an old
  release — a stale render on the campaign page is a claim about the current
  design.
- Every render used publicly should be reproducible: note the pair id or the
  `cad/comparisons/manifest.json` pose that produced it.
- Keep an `[EST]`-free asset list: an asset is either done or missing.
