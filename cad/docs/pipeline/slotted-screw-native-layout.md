# Slotted-screw dimension border overflow

This is an unvalidated native-layout candidate. The current production print
shows the upper tail of the 2.50 head-height dimension crossing the top zone
border, although `drawing:slotted_screw` completed successfully. Portfolio status
belongs on the project board; this file records the defect and its validation.

## Reproduction evidence

- Checkout: `C:/src/ha-foundations-integration`.
- Frozen source: `eb39accdfb18d4c81b45dbc76439111c4658c0fb`.
- Adapter: `e77bfda4de1962625da8a9a859eb0bbaf1e6f10f`.
- Full command: `uv run --no-sync python -m doit -n 4`, cache disabled.
- Successful drawing task: trace `0x6e6f10e2acf665a695a035d75d90a73a`,
  completed `2026-09-07T21:04:24.844747Z`.
- Output: `cad/out/png/slotted-screw_drawing.png`, SHA-256
  `0c31dd530689da79e5c6800b013870134fed34852f29b5c6cd56da457981637b`.
- Both the main agent and an independent read-only agent inspected the image.
  The dimension text is readable; its upper line tail intrudes into the zone band.

The integration parent `a89a27b0` has the same view positions, dimensions and
scale. Its recipe changes only the drawing-factory wiring, so that change does
not establish a fix for this layout defect. The observed image is a foundation
baseline, not a matched candidate performance comparison.

## Candidate

The recipe now opts into the existing dimension auto-arrange and measured
whole-sheet layout helpers. The bank includes side, head-end and isometric
views, the manufacturing note, and the head-end caption. The caption follows
its view; the manufacturing note is independently packed. Horizontal ordering
preserves head-end, side, then isometric without inventing projection alignment.

Named source dimensions, manufacturing text, the 6:1 scale and initial placement
seeds remain unchanged. Full decorated-view measurement determines the final
positions. Failure propagates before export; there is no coordinate retry,
font shrink, content removal or relaxed border. Shared layout helpers are not
changed. The dependency test explicitly enrolls this eighth layout recipe and
continues to exclude the helper closure from all other unlisted drawings.

The local API bundle documents `IModelDocExtension.AlignDimensions` and
`IView.SetViewPosition`; the existing helpers check their native results and
remeasure the final drawing. Those contracts and other recipes' positive
controls do not prove success for this print.

## Offline checks

The first test attempt used an incorrect mock adapter result and failed before
the recipe reached annotation creation. That fixture error is not a regression
witness. After correcting it to the adapter's success/data interface, all four
new cases failed for the intended reason: the actual recipe exported without
calling either layout stage. Retained run: `run-z3mjf2lu`.

After implementation, the four composed-recipe tests, unchanged slotted-screw
contracts and full per-recipe layout-dependency tests passed: 105 tests in
1.58 seconds, `run-32ypfcob`. Changed-file Ruff and `git diff --check` passed.
These tests cover integration order, all declared views/notes, preserved
dimension sets and rejection before export. They mock COM and do not establish
native fit or source immutability.

## Required native closure

After the active foundation run drains, establish a genuine local source and
token through doit in the isolated candidate checkout. Compare the unchanged
parent recipe and candidate on the same saved source with guarded, owned
documents. Retain their source hashes, dimension identities/raw values,
tolerances/presentation, linked text, view scales and complete final native
envelopes. Prove that the upper tail clears the zone border without hiding or
changing the head-height dimension.

Measure matched uninstrumented recipe/total times, including arrangement and
packing. Inspect production and fresh cold-reopened full sheets/detail views;
verify source immutability and fresh-handle attachments. The existing full
recipe/graph/isolation checks and exact-head full-stack build remain required.
No native acceptance, performance improvement or merge readiness is claimed.
