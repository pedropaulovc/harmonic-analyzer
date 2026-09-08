# Partial drawing visual receipt: batch 4

Frozen head: `64c3dab4875354a7d44d709539e001db920a0377`.
Initial batch pinned: `2026-09-08T05:12:06.138393+00:00`. The 38 names in batch 1, 2 and 3 manifests were excluded; 13 remaining completed PNGs were captured, below the cap of 20. No later arrivals were added.

All 13 title blocks visibly separate drawing number and revision. PART, MATERIAL and FINISH fields are readable and remain inside their cells in this batch. Complete-sheet review found body annotation/border collisions in six drawings, listed below. These are current-pixel observations, not claims that the frozen head introduced them. Existing followups #709 and #712 govern field/body layout disposition; no new formatting work was started.

Each complete PNG was opened with view_image, and all title fields were read on contact crops. Suspected collisions were inspected on original-resolution, unaltered pixel crops. Exact source PNG bytes are preserved in title-fields-batch4-images/. All sheets are 5100 x 3300; title crop bounds are (3060,2508,5100,3300). Coordinates use top-left origin, with exclusive right/bottom bounds.

This receipt covers only these 13 pinned images. It does not complete the full-fleet visual gate or establish native closure, cold-reopen/move/scale behavior, dimensional accuracy, source identity, or manufacturing release. The known rack cold-route gate is not waived by PNG review. No tracked source edits, tests, builds, or COM calls were made.

[Exact manifest](title-fields-batch4-manifest.json) includes source/pinned-copy paths, SHA-256, byte lengths, nanosecond and UTC mtimes, dimensions, crop boxes and hashes of the earlier three manifests.

| Source PNG | SHA-256 | Modified UTC | Title fields | Complete-sheet finding |
| --- | --- | --- | --- | --- |
| [cone-pivot-screw_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/cone-pivot-screw_drawing.png) | `f96c7af2227269c540ca0c758aff093130a286530482fc6ff2d81cc3086d9422` | 2026-09-08T05:10:53.522695+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | Body observation: HEAD BEARING FACE control and text cross the adjacent view outline; 1.20 +/-0.1 slot-depth text crosses the isometric outline. Original crop (2800,650,4150,1050). |
| [frame-side-screw_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/frame-side-screw_drawing.png) | `25668b0cad7f836581932a2d14761408d686bf6dd26552413613c6e761eba319` | 2026-09-08T05:09:55.361550+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | No text/border conflict observed in this review. |
| [gooseneck_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/gooseneck_drawing.png) | `41612692019b96d9210f3efebb2fc6ca2e07fe71edadb80077bb1f2c7f7eecc0` | 2026-09-08T05:09:41.130246+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | Body observation: isometric lower tube end crosses the 1:4 caption text. Original crop (3450,2050,4350,2320). |
| [guide-lock_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/guide-lock_drawing.png) | `1259192f93eff0ad72ca283d11862ac25c25d5e1524cac88d85837d147a63075` | 2026-09-08T05:09:28.272790+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | No text/border conflict observed in this review. |
| [lever-wire_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/lever-wire_drawing.png) | `ca3b9b1e6808d70752156bdf6345eefbe5af0d4904764258bcce0e82dab2245c` | 2026-09-08T05:09:02.665090+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | No field/border conflict observed. Existing printed manufacturing note explicitly says not to release until formed hook, hub wrap and cut-length details are specified; this visual review does not override it. |
| [output-fixture_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/output-fixture_drawing.png) | `f920a3c6f85e1e03e077a68173d4ed472290b7b926d39a384ede3c97f109bcbb` | 2026-09-08T05:11:08.054568+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | No text/border conflict observed in this review. |
| [pen-frame_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/pen-frame_drawing.png) | `6421d8d21a126c982f7e241eb24582505c42e4cd986f46735025848008b8180a` | 2026-09-08T05:11:21.317456+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | No text/border conflict observed in this review. |
| [pen-wire_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/pen-wire_drawing.png) | `3db4495b817b2bd40117ef80b92377317b458e926f6ada35b3c94fcb6be53bc6` | 2026-09-08T05:11:56.454889+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | No text/border conflict observed in this review. |
| [pinion-cam-pin_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/pinion-cam-pin_drawing.png) | `74e0fc5ab2282c14b41a0e0c54ea71d4fe7748f740a43c6845076b78e01748cc` | 2026-09-08T05:11:43.970829+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | Body observation: Ra 0.8 text crosses the side-view left outline. Original crop (1260,900,1930,1300). |
| [pinion-cam_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/pinion-cam_drawing.png) | `8475f12fb663817243700190a3ebb267aa57e0ce155a542408876f48d49b2bc0` | 2026-09-08T05:08:51.008521+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | Border observation: diameter 10.32 +/-0.05 text/leader crosses the left frame. Original crop (0,1780,600,1960). |
| [pinion-handle_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/pinion-handle_drawing.png) | `7c39f88471380104b197900806f2b0d22807f193a04ce636944cfb6b6ec8ce61` | 2026-09-08T05:08:00.356798+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | Body observation: BODY HOLE; REAM THRU text overlaps the cross-hole view outline and the dimension extension line. Original crop (3120,1830,4070,2200). |
| [pinion-lever_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/pinion-lever_drawing.png) | `ac807a98cb9ddc7d9e9aa8b41e79f459aa58d7ba38e3e10b6f63119e3ec0b150` | 2026-09-08T05:10:23.593544+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | Body observations: Ra 1.6 symbol/leader overlaps the 0.05 A control and view extension lines; isometric caption overlaps the view and title-block upper rule. Original crops (1670,1680,2330,2020) and (3750,2380,4950,2670). |
| [rocker-arm-support_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/rocker-arm-support_drawing.png) | `5209fc256ed183e2ec32f2460220407a6b64fc661a8d9f40eccfa5fa0944b5bf` | 2026-09-08T05:08:27.242304+00:00 | DWG/REV separated; PART/MATERIAL/FINISH contained. | No text/border conflict observed in this review. |

Preserved original-resolution collision crops:

- [Cone pivot screw control/depth](title-fields-batch4-images/cone-pivot-screw-body-callouts.png).
- [Gooseneck caption](title-fields-batch4-images/gooseneck-iso-caption.png).
- [Pinion cam pin finish](title-fields-batch4-images/pinion-cam-pin-finish-overlap.png).
- [Pinion cam left frame](title-fields-batch4-images/pinion-cam-left-frame.png).
- [Pinion handle hole caption](title-fields-batch4-images/pinion-handle-crosshole-label.png).
- [Pinion lever finish/control](title-fields-batch4-images/pinion-lever-finish-fcf.png) and [isometric caption/title-block rule](title-fields-batch4-images/pinion-lever-iso-titleblock.png).

All 13 pinned source hashes and mtimes still match at the closing recheck.

The title fields themselves pass this batch visual check; body/border acceptance remains open for the six named drawings. No causal comparison against predecessor builds was performed in batch 4.
