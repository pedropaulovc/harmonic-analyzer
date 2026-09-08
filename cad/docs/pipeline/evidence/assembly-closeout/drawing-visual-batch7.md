# Partial drawing visual receipt: batch 7

Frozen head: `64c3dab4875354a7d44d709539e001db920a0377`.
Initial batch pinned: `2026-09-08T05:36:14.275836+00:00`. The 82 names in batch 1-6 manifests were excluded. Seven additional completed PNGs were captured, below the cap of 20; no later arrivals were added.

All seven drawing numbers remain visibly distinct from revision v32. The five assembly drawings all have resolved titles and three populated geometry views; none is a blank assembly sheet. Paper-drive assembly has a wrapped-title collision. Three other drawings have body/border collisions described below. These observations do not establish when or why the layouts arose. Existing followups #709 (fields) and #712 (body layout) govern disposition; no formatting work was started.

Each complete PNG was opened with view_image. Readable title contact crops and original-resolution pixel crops were inspected. All exact source bytes are retained under title-fields-batch7-images/. Sheets are 5100 x 3300; title crop bounds are (3060,2508,5100,3300). Coordinates use top-left origin and exclusive right/bottom bounds.

This receipt is partial visual evidence, not full-fleet visual acceptance, native closure, cold-reopen/move/scale validation, source-identity proof, or manufacturing release. Known native failures are not waived by PNG review. No tracked changes, COM, tests, builds, telemetry operations, or GitHub actions were performed.

[Exact manifest](title-fields-batch7-manifest.json) retains source/copy paths, SHA-256, sizes, mtimes, dimensions, crop bounds and the exact earlier manifest hashes.

| Source PNG | SHA-256 | Modified UTC | Title-field observation | Complete-sheet/assembly observation |
| --- | --- | --- | --- | --- |
| [channel-assembly_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/channel-assembly_drawing.png) | `2d9a424e87627b2e60f13554932484e3151d2deb77f863b057f1930b7b974662` | 2026-09-08T05:26:20.506086+00:00 | Title present; DWG/REV separate; PART/MATERIAL/FINISH contained. | Three populated assembly views; no missing title, blank geometry, or text/border collision observed. |
| [frame-assembly_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/frame-assembly_drawing.png) | `ee191d1d8754093cbc6de908b48e15ebab93bb187d81dd165c304784df74adae` | 2026-09-08T05:25:33.858749+00:00 | Title present; DWG/REV separate; PART/MATERIAL/FINISH contained. | Three populated assembly views. Isometric base intrudes into the title-block tolerance panel, crossing its upper rule and tolerance text. Crop (3020,2400,4100,2800). No missing title or blank geometry. |
| [fulcrum-keeper_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/fulcrum-keeper_drawing.png) | `9b322208841a32f45f5552cf9be5e5137cdfaf9c1c93398b956ae2da40a22029` | 2026-09-08T05:24:54.474858+00:00 | DWG/REV separate; PART/MATERIAL/FINISH contained. | Body/border observations: datum A box and 23.00 dimension overlap; note 5 falls below the bottom frame and overlaps the Maker watermark. Crops (950,2220,1330,2390) and (100,3090,2100,3300). |
| [magnifier-assembly_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/magnifier-assembly_drawing.png) | `fb7d8e9bc79d51b47419cf2fe98d1ee8f66e3019734cbbd787cb2d1ea0fa337f` | 2026-09-08T05:26:01.017850+00:00 | Title present; DWG/REV separate; PART/MATERIAL/FINISH contained. | Three populated assembly views; no missing title, blank geometry, or text/border collision observed. |
| [magnifying-wheel_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/magnifying-wheel_drawing.png) | `c8255bd8cf6b1859c8c532ef344a4d60279e21b45e91f3d3120cbb6e57d84b83` | 2026-09-08T05:25:14.436639+00:00 | DWG/REV separate; PART/MATERIAL/FINISH contained. | Body observations: 5.00/6X SPOKE caption, Ra symbol/leader and datum A intersect rim/spoke geometry; THRU - REAM text is crossed by rim/centerline. Crops (1650,1030,2310,1460) and (790,1390,1350,1570). Existing printed note says not to release until hub material, grooves and retention are specified; no waiver. |
| [paper-drive-assembly_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/paper-drive-assembly_drawing.png) | `9dd60212bbf65ceaa500b4490c51564cac8774ad659f66bcf3fd61f8e45d5e4a` | 2026-09-08T05:25:48.477319+00:00 | Title present but wraps paper-drive / assembly; second line crosses the PART lower rule and overlaps DWG. NO. label. Number MHA-A06 and v32 remain distinct. MATERIAL/FINISH contained. | Three populated assembly views; no missing title or blank geometry. Separate small gear is the intentional spare T18 per prior source review, not a defect. Title crop (3060,2508,5100,3300). |
| [summing-assembly_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/summing-assembly_drawing.png) | `8511f6b1c329af2a00adec5e7541a0ebd132ad972f46b14b6249e7b7f0ad6c1e` | 2026-09-08T05:26:58.489187+00:00 | Title present; DWG/REV separate; PART/MATERIAL/FINISH contained. | Three populated assembly views; no missing title, blank geometry, or text/border collision observed. |

Assembly geometry observation resolved by existing evidence:

Paper-drive shows a separate small gear below the principal mechanism in each view. The existing [first four assembly review](assembly-visual-first-four.md), read during this task, identifies it as the intentional spare T18 and records the actual source check: SPARE_GEAR_POS (160.0, BASE_DECK_Y, -75.0), transgear-removable configuration T18 with ROT_X_NEG90, label transgear-removable (spare T18). The supporting deck belongs to the separate frame assembly, so its absence in the isolated paper-drive view is expected. This is not classified as detached driven geometry. Seating on the deck belongs to the top-assembly inspection.

The existing review has SHA-256 `06579aa05fb39593de8eb5a61f35afb7e5d8bce1847d32f39ae72061eefb8305`. This batch did not re-run a native placement check.

Preserved original-resolution evidence:

- [Paper-drive title wrap](title-fields-batch7-images/paper-drive-assembly_drawing-title-crop.png).
- [Frame geometry/tolerance panel](title-fields-batch7-images/frame-assembly-geometry-titleblock.png).
- [Fulcrum keeper datum/dimension](title-fields-batch7-images/fulcrum-keeper-datum-dimension.png) and [bottom notes](title-fields-batch7-images/fulcrum-keeper-bottom-notes.png).
- [Magnifying wheel spoke/finish](title-fields-batch7-images/magnifying-wheel-spoke-finish.png) and [bore caption/rim](title-fields-batch7-images/magnifying-wheel-bore-outline.png).
- [Paper-drive intentional spare](title-fields-batch7-images/paper-drive-assembly-separated-gear.png), observational crop, not a defect.

All seven source hashes and mtimes still match the initial manifest at the closing recheck.

No predecessor-layout comparison was performed for this batch. One title-field observation and three body/border observations remain for existing followup disposition.
