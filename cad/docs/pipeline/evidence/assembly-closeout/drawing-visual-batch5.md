# Closeout title-field visual inspection — batch 5

Frozen source head: `64c3dab4875354a7d44d709539e001db920a0377`.

Pinned at `2026-09-08T05:18:16.562564+00:00`. The initial completed root `*_drawing.png` remainder contained 18 sheets after excluding the 51 names in batches 1–4. All 18 were copied and inspected; no later outputs were added. The full sheets are 5100 × 3300 pixels. Each title crop is the original pixels from `[3060, 2508, 5100, 3300]`, with no resizing or annotation. Exact source-byte copies, source timestamps, full-image SHA-256 values and crop SHA-256 values are retained in [the manifest](title-fields-batch5-manifest.json) and `title-fields-batch5-images/`.

Every complete sheet and its readable title crop were viewed. All 18 drawing-number values and revision values occupy distinct cells and remain readable; every revision reads `v32`. Three wrapped titles overlap the `DWG. NO.` label, even though its number and the adjacent revision remain separate. Four sheets have a title, material or finish containment problem. These are observations of the pinned renders, not proof of when the problems began or their cause. No old comparison was inspected for this batch.

| Sheet | DWG. NO. | TITLE | MATERIAL | FINISH | Complete-sheet observation |
|---|---|---|---|---|---|
| arbor-pedestal | MHA-004 | Contained | Contained | Two lines contained | `CROWN + 2 FLANKS + FOOT TOP + RIGHT SIDE` runs across the upper portion of the isometric geometry. |
| cone-lock-knob | MHA-093 | Contained | Contained | Contained | No notable body collision observed. |
| cone-pivot-post | MHA-016 | Contained | Contained | Third line, `and counterbores`, enters the material row | No additional body collision recorded. |
| cone-swing-platform | MHA-091 | `cone-swing-` / `platform`; second line overlaps the DWG label | Second line, `plate; 5/16 in minimum stock`, crosses the lower cell boundary into the geometric-interpretation area | Two lines contained | No additional body collision recorded. |
| cone-tip-bushing | MHA-096 | Contained | Contained | Contained | No notable body collision observed. |
| cone-tip-pinch-screw | MHA-098 | `Flat-End Pinch` / `Screw`; second line overlaps the DWG label | Contained | Contained | No additional body collision recorded. |
| crank-pin | MHA-024 | Contained | Contained | Contained | No notable body collision observed. |
| crank-pinion | MHA-025 | Contained | Contained | Contained | Boxed datum A overlaps the lower-left front gear outline/teeth; `2X AXIAL END FACES` runs across the top edge of the adjacent side view. |
| magnifying-lever | MHA-043 | Contained | Contained | Contained | No notable body collision observed. |
| magnifying-vertical-rod | MHA-044 | `magnifying-vertical-` / `rod`; second line overlaps the DWG label | Contained | Contained | No additional body collision recorded. |
| pen-marker | MHA-050 | Contained | Contained | Contained | The upper-left feature-control frame crosses the inner left sheet border, remaining inside the PNG. |
| pen-rod | MHA-051 | Contained | Contained | Contained | No notable body collision recorded; lower general note ends close to the title block. |
| pen-v-block | MHA-053 | Contained | Contained | Contained | Datum B overlaps the 8.50 dimension at upper left; a lower dimension extension line crosses the title block's tolerance heading. |
| pinion-arbor | MHA-102 | Contained | Contained | Contained | No notable body collision observed. |
| pinion-bracket | MHA-056 | Contained | Contained | Two lines contained | `UPPER R7.50 ARC` overlaps the upper surface-finish symbol's horizontal line; the pin-seat-axis note reaches across the front-view edge. |
| thumb-screw | MHA-075 | Contained | Contained | Contained | No notable body collision observed. |
| top-frame | MHA-077 | Contained | Contained | Two lines contained | Right-side inspection/general notes run beyond the inner border and are clipped at the PNG's right edge. The hanger-stud feature-control frame and its caption overlap the lower-right boss geometry. Lower-left notes reach the bottom border. |
| wheel-bar | MHA-085 | Contained | Contained | Contained | No notable body collision recorded; left 10.00 dimension is close to the inner border. |

The four title-field follow-ups belong with existing issue #709: cone-pivot-post finish spill, cone-swing-platform title/material spill, cone-tip-pinch-screw title wrap and magnifying-vertical-rod title wrap. The six sheets with recorded body collisions or border protrusions are arbor-pedestal, crank-pinion, pen-marker, pen-v-block, pinion-bracket and top-frame; preserve these in the existing deferred drawing-layout follow-up #712. The parent coordinates issue updates; this inspection made none.

This completes only the fixed batch of 18 sheets. It does not declare the overall visual or native gate complete, establish annotation attachment after cold reopen/move/scale, or waive the independently known rack leader failure. No COM, production edits, tests, telemetry changes or later-output inspection were performed.

Manifest SHA-256: `ce949606641a64b6415568d67208e994a5d2206cd0c103228116464c1dae195d`. All 18 retained full copies and all 18 crops match the manifest hashes; crop pixels match the corresponding full-image rectangles.

| Pinned full PNG | SHA-256 |
|---|---|
| [arbor-pedestal_drawing.png](title-fields-batch5-images/arbor-pedestal_drawing.png) | `57554988e20f88f09f4505244e2b9e77d8851d48206b3fdbdd5a38ec46cce6db` |
| [cone-lock-knob_drawing.png](title-fields-batch5-images/cone-lock-knob_drawing.png) | `4a5267a3f3525866b89678a2f28dbd4742a41348063bee5ec56dc0b9087b1ed0` |
| [cone-pivot-post_drawing.png](title-fields-batch5-images/cone-pivot-post_drawing.png) | `5e54e4f674a3a619b00ff00ed1ed8b3daba0f18a0ed538874cb8d8356f5f673b` |
| [cone-swing-platform_drawing.png](title-fields-batch5-images/cone-swing-platform_drawing.png) | `28bc61aeb9e57c6099f3d6e0e9305660fac92bbecc5d66d13c62671087f26a79` |
| [cone-tip-bushing_drawing.png](title-fields-batch5-images/cone-tip-bushing_drawing.png) | `e70c324f9c03685e524e2e83ac4268d2d77fde29e2c794e0c7431a27fb350bfe` |
| [cone-tip-pinch-screw_drawing.png](title-fields-batch5-images/cone-tip-pinch-screw_drawing.png) | `db29e2bbd9eadeb5c2d2b1829e58c99c91ca20b0a38d96994d44b7715349bbe2` |
| [crank-pin_drawing.png](title-fields-batch5-images/crank-pin_drawing.png) | `c66f60fcfe2ce052eda43be3e94cfd13e724c1ee11a4cfed3472d95aa7dd160e` |
| [crank-pinion_drawing.png](title-fields-batch5-images/crank-pinion_drawing.png) | `4b40ad163097dd5da958b3c57b4c34a873f317a899d5be2d2f62c4b7ad7491b4` |
| [magnifying-lever_drawing.png](title-fields-batch5-images/magnifying-lever_drawing.png) | `fcb549b70452f0260c8a8a7355de7cbf2d3a9401bdf00ffc4619dc795e4f70a7` |
| [magnifying-vertical-rod_drawing.png](title-fields-batch5-images/magnifying-vertical-rod_drawing.png) | `a8d3ab16e5cd70b8ce29fafed55fad1bb404c89f39b5cc79f2e3ace1215b3e0d` |
| [pen-marker_drawing.png](title-fields-batch5-images/pen-marker_drawing.png) | `754dbe024e4d2c0167248328d70647cd47f6393747c2857c5f1ee36709c3c0c6` |
| [pen-rod_drawing.png](title-fields-batch5-images/pen-rod_drawing.png) | `84d9fd5c29e7ebd7cc58bdb0eb49e5e4e47e3114873cf18751f398b28b917480` |
| [pen-v-block_drawing.png](title-fields-batch5-images/pen-v-block_drawing.png) | `fd128c0333ad2789fdbf0d1405a2cb58f0b72a23d8f84e9be445ac976e4450b4` |
| [pinion-arbor_drawing.png](title-fields-batch5-images/pinion-arbor_drawing.png) | `7ff989be14043c09729358120cdb1715953905ed82375e878675268932c91f2f` |
| [pinion-bracket_drawing.png](title-fields-batch5-images/pinion-bracket_drawing.png) | `81cf423904212230f271b7f60a0f568135717c6743f99080baf2daa8c787fe5c` |
| [thumb-screw_drawing.png](title-fields-batch5-images/thumb-screw_drawing.png) | `ea5a87bda741ddbec685d9deb5ed311e9e4608dd482aa373c7bf02e932d0dc6f` |
| [top-frame_drawing.png](title-fields-batch5-images/top-frame_drawing.png) | `f95eccaf690a613884d2f3e8295732b3f2508cd9565a3fdfdc0080b57888e08c` |
| [wheel-bar_drawing.png](title-fields-batch5-images/wheel-bar_drawing.png) | `fea671e812326a9cf7db6b864e44fb29ffee34488291510a0915c651f5749b27` |
