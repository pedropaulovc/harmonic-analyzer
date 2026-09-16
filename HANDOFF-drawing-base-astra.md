# Handoff — PR #754 `drawing-base-astra` (base + frame drawing package)

State as of 2026-09-15, head `985e2bcb` (pushed, draft PR
<https://github.com/pedropaulovc/harmonic-analyzer/pull/754>).

## What is done and proven native

| artefact | PDF sha256 | evidence |
|---|---|---|
| `harmonic-base` (MHA-035, 2 sheets) | `831d864f` | `part:`+`drawing:` green, both sheets inspected (`cad/out/reports/main-visual/base-{1,2}.png`) |
| `top-frame` (MHA-077, 3 sheets) | `51f25bd4` | `part:`+`drawing:` green — **first green top export since `79dde2be`** — 3 sheets inspected (`top-{1,2,3}.png`) |
| `tube-frame` (MHA-083, 1 sheet) | `d4f026fe` | green, inspected; one defect open (below) |

Offline: 34 base tests, 109 drawing-layout tests, `ruff check cad/scripts` clean.
`check:*` gate run was in flight at handoff — re-run
`uv run python -m doit -n 4 --continue check:math check:config check:graph check:recipe check:partiso check:numerals check:nameplate check:budget check:cache`.

### Decisions the user made (do not relitigate)

1. **Finished-land acceptance.** Socket-to-rim land is an *acceptance* requirement:
   `1.0 MIN CONTINUOUS FINISHED DECK LAND … AFTER MATCHING AND EDGE BREAK`,
   authored once in `harmonic_base_spec.DRAWING_NOTES`, published through the part's
   Manufacturing Notes property.
2. **All four flange perimeter faces finished** (Ra 3.2, `FLANGE EDGES, 4 SIDES`)
   because they are the hole-table origin. Reviewer calls this over-specification
   twice; it stays.
3. **Base widened, columns stay.** `TOP_WIDTH` 266.7 → **274.5**, `BOTTOM_WIDTH`
   279.4 → **287.2**, so the land is **5.5 mm on both axes**. Column stations stay at
   the photographed ±112. Departure from the ch6 "28 cm" callout is recorded in
   `cad/config/dimensions.yaml` (ch6 cross-validation prose + Appendix B row).
4. **`R0.5 ROOT` deleted** from the print (not hobby-shop measurable; deck cutter's
   corner defines it). Model keeps the fillet.

### Consequence to keep in mind

`BASE_SPOTFACE_DEPTH` went 0.35 → **4.25** because `TOP_WIDTH/2` moved while the
shared `frame_attachment_spec.BASE_SCREW_SEAT_Z` (133.0) did not. The cross-screw
spotface is a real counterbore now and the callout says `4.25 DEEP`. Alternative
(not taken): move `BASE_SCREW_SEAT_Z` to 136.9, which shifts both cross-screw head
planes and is shared with tube/top frame.

## Open work, in priority order

### 1. Base envelope cascade (REQUIRED before trusting any interference gate)

The base *part envelope* changed, so downstream assemblies must rebuild:

```
uv run python -m doit -n 4        # full pipeline; frame, drive-train, verify all consume base geometry
```

Everything derives (no hard-coded base width in an assembly), but the gates have not
run since the widening. Files that intentionally keep the old photographed numbers:

- `cad/scripts/diagnostics/triangulate_ch30_gt.py:20-21,55` — `BASE_X, BASE_Z = 228.6, 139.7`
  are the **photo-triangulation anchors**; they must stay at 457.2 × 279.4.
- `cad/scripts/test_holes_face_selection.py:54,86` — synthetic −133.35/−133.0 fixtures,
  still a valid hard case.
- `cad/scripts/build_frame_assembly.py:11` — docstring says "Z = 28 cm depth" (stale text only).
- `cad/docs/pipeline/paper-drive-spare-deck-seating.md:29` — deck interior now ±130.25.

### 2. Tube-frame Ø5.00 leader tail (diagnosed, fix not written)

`tube-1.png`: the lower cross-hole callout draws a ~150 mm diagonal run from the hole
past the text, *plus* a correct horizontal shoulder — two leader renderings of one
annotation.

Root cause (evidence in `cad/out/reports/tube-dimension-geometry/report.json`, 85
segments / 4 views, produced by `cad/scripts/diagnostics/probe_tube_dimension_geometry.py`):
the cross-hole text is moved with **raw `SetPosition`/`SetPosition2` and no
`OffsetText`**, so the text is formally still on the dimension line and SolidWorks
draws the dimension run along the anchor→text vector for the full text width, while
the document-level broken-leader/horizontal-text pin draws the shoulder. The OD
callout on the same sheet is the **positive control**: identical setter block, but its
position comes from `AddDiameterDimension2` at creation and is never moved.

Prepared fix (not applied): replace the raw `annotation.SetPosition2(...)` at
`draw_tube_frame.py:306` with the repo's existing helper
`_drawing_common.offset_dimension_text` (sets `OffsetText = True` then `SetPosition2`;
only current user is `draw_pinion_handle.py:432`), hoisting the `hole_text =
model_point_in_view(...)` call above the style loop, and assert `display.OffsetText`.
Fallback if the report shows the run belongs to a witness line instead:
`display.ArcExtensionLineOrOppositeSide = False` with the readback used at
`draw_harmonic_base.py:835-837`.

`TubeLeaderProbe2` holds the full context (`hub send`; it was stopped on a request
budget, not an error — its transcript is `history://TubeLeaderProbe2`). Also delete
the scratch probe when done.

### 3. Third-round review findings (both packages FAIL / FIX, 0 → new blockers)

`cad/out/reports/machinist-review/{harmonic_base,top_frame}.md`.

**base, blocker:** the 4× 10-32 cross-screw axis has no unambiguous vertical
location — `38.10` reads either as deck-above-flange (40.6 − 2.5) or as axis height.
Dimension the axis from the flange underside (the Ra 3.2 seating face) with extension
lines landing on the hole centreline and that face.

**base, other:** reviewer now says the 1.0 MIN land note "cannot bind" at 5.5 nominal
(it is deliberate acceptance — answer, do not delete without the user); drill depth
`48.00` → `48 MIN` one-place; `ORIGIN:` note collides with the E1/F3 tags and the axis
`0` labels; sheet-1 `7.0` text sits on the `287.2` extension line; Section A-A is
labelled twice (keep the rotation note in the single under-view label); `(Ø25.50)`
parentheses in the hole table are **not possible natively** (`ITableAnnotation::IsCellTextEditable`
— only header/custom columns editable), which is why the note now says
`A1-A4 BORE DIAMETERS (HOLE TABLE): REFERENCE ONLY`.

**top-frame, blockers:** (a) nothing fixes the Ø52.2 boss vertically against the rail
(boss 47.3 vs rail 36.5, 10.8 unsplit) — add one rail-top-to-boss-top dimension in
Section A-A; (b) side rails (34.2 flange) and the 22.0 central web have no
web/flange thickness, root radius or rim chamfer anywhere, yet the keeper tap and the
Ø13.49 hangers depend on them — extend the B-B note or add a side-rail section.

**top-frame, clarity:** the new `275.2 / 2 PAIRS SPOTFACES / CENTRED ON FRAME MIDPLANE`
note collides with `22.75`, the `SECTION A-A` label and `4X: 2 FRONT + 2 REAR` — move
it and say what `22.75` is measured from. Several text-on-extension-line collisions
(`224.00`, `90.15`, `16.0`, `8.0`), labels not under their views, D-D lacks section
hatching and prints in an olive colour, and two-place decimals on hanger/keeper
positions should drop to one place.

### 4. Display-quality readback (done, but know the mechanism)

`set_high_quality_shaded_with_edges` no longer reads `GetFacettedHlrDisplay`; the new
`assert_precise_isometric_views` re-reads it **after** `save_drawing`. Reason, measured
by `_frame_shading_idempotence_probe.py --settled-modes` / `--fresh-view-compute`
(report `cad/out/reports/frame-shading-idempotence/report.json`): on a fresh view the
flag is False for ~10 ms, True from ~50 ms, and only settles False after the view's
first full compute. `ForceRebuild3`, `EditRebuild3`,
`IModelDocExtension.Rebuild(swRebuildAll)`, `GraphicsRedraw2`,
`UpdateViewDisplayGeometry`, `ActivateView`+`ViewZoomtofit2`/`ViewZoomToSheet` all
leave it True (122 s PDF export is the only thing that clears it).

## Operational notes (bought with real time)

- **Never hold a PDF handle.** `save_drawing` does `os.remove(pdf)` before export; a
  lingering `pypdfium2.PdfDocument` in the eval kernel fails `drawing:<stem>` with
  `WinError 32` *after* the whole COM build. Always `doc.close()`.
- **Do not use the `edit` tool on `cad/scripts/draw_*.py`.** Format-on-save reformats
  the whole file (this repo is not ruff-formatted); a one-line change came back as
  665 insertions. Use `open().write()` / a string-replacement script, and check with
  `git diff --no-index <ruff-formatted copy> <file>` to confirm only the intended hunks.
- **Session hygiene.** A failed drawing export leaves documents open; owned-session
  probes refuse a non-empty session by design. `uv run python _frame_residency_probe.py`
  inspects, `--close-clean-frame-build` closes the clean closure; it refuses saved
  drawings, and `_top_pocket_section_probe.py --discard-owned-unsaved` clears a
  leftover unsaved probe drawing.
- **`part:top_frame` shows `U` (run) every time** in `doit list --status` while
  `doit info` says up-to-date — worth a look; it costs ~9 min per top-frame run.
- Codex agents hit a usage limit mid-session (`usage_limit_reached`); the Claude
  agents (`BaseReviewFix2`, `TopPocketProbe`) carry the context for their slices.

## Scratch files to delete before merge

Repo-root `HANDOFF-drawing-base-astra.md`, `_frame_*_probe.py`, `_hole_callout_association_regression.py`,
`_top_failed608_recovery_probe.py`, `_top_pocket_apply.py`, and
`cad/scripts/diagnostics/{_base_finish_visual_probe,_base_socket_land_visual,_top_pocket_section_probe,probe_tube_dimension_geometry,diag_*_temp,repro_balloon_rendered_geometry}.py`
— all untracked, none committed.
