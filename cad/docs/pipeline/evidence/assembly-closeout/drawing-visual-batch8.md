# Final drawing visual batch 8

All three drawing-number/revision value pairs remain distinct and inside their cells. Each assembly sheet has a resolved title and three populated views. The harmonic-analyzer assembly title has a field-containment defect already within issue #709 scope; no additional body-layout observation for #712 was found in this batch.

Frozen source head: `64c3dab4875354a7d44d709539e001db920a0377`. Initial filename list pinned at `2026-09-08T05:53:24.250788+00:00`; excludes the 89 names in batches 1-7. The three exact source PNG copies complete 92 pinned drawing PNGs across those manifests. Prior batches retain their recorded limitations; this count is inspection coverage, not a statement that every sheet is clean.

Inspection used actual full-sheet view_image calls for all three 5100 x 3300 PNGs, a readable title contact sheet, and the original-resolution harmonic-analyzer title crop. Pixel coordinates below refer to the original full-sheet PNG. Crops are derived review aids; pinned full sheets preserve exact source bytes.

| Drawing | Title fields | Complete-sheet observation |
| --- | --- | --- |
| [drive-train-assembly_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/reports/closeout-verification/title-fields-batch8-images/drive-train-assembly_drawing.png) | MHA-A03 / v32 distinct; title, material, finish, scale and unit fit their fields. | All three views populated. No additional visible title, geometry, text or border obstruction observed. |
| [harmonic-analyzer-assembly_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/reports/closeout-verification/title-fields-batch8-images/harmonic-analyzer-assembly_drawing.png) | MHA-A08 / v32 distinct. Title wraps to a second line; assembly crosses the PART lower rule and overlaps DWG. NO. Material, finish, scale and unit fit. | All three views populated. No additional body or border obstruction observed. Field containment belongs to existing #709; causality is unestablished without an exact predecessor print. |
| [pen-assembly_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/reports/closeout-verification/title-fields-batch8-images/pen-assembly_drawing.png) | MHA-A01 / v32 distinct; title, material, finish, scale and unit fit their fields. | All three views populated. No additional visible title, geometry, text or border obstruction observed. |

On harmonic-analyzer-assembly_drawing.png, the second title line crosses the cell rule around original pixels x=4010-4420, y=2850-2950. The exact title crop is [harmonic-analyzer title crop](title-fields-batch8-images/harmonic-analyzer-assembly_drawing-title-crop.png), from box (3060, 2508, 5100, 3300). The drawing number MHA-A08 remains below the crowded label and separate from v32. This is an observed defect, not a claim that commit 64c3dab4 introduced wrapping. No predecessor comparison was made for this final assembly print.

No assembly drawing in this batch has a missing title or blank view geometry. This pixel review does not certify native document closure, cold reopen, dimensional ownership, the build result or zero-COM reuse; those remain the separate root-owned gates. No source edits, native calls, tests, build invocations or issue mutations were made.

| Source PNG | SHA-256 | UTC source modification time | Bytes |
| --- | --- | --- | ---: |
| [drive-train-assembly_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/drive-train-assembly_drawing.png) | `1d998ed4fc7eca38336cc07b1d3a225d9cb202ae37369a0c3410d0ddb9404d7c` | `2026-09-08T05:41:54.240496+00:00` | 683393 |
| [harmonic-analyzer-assembly_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/harmonic-analyzer-assembly_drawing.png) | `b7bc21d6ac9137e77c183f6ddbfa1b1a0ec8d592743fc4e544c4768065c24cdb` | `2026-09-08T05:49:55.576612+00:00` | 892708 |
| [pen-assembly_drawing.png](C:/src/ha-assembly-closeout-independent/cad/out/png/pen-assembly_drawing.png) | `14ec4901caf43b645d1cafdf12cffeb4863f4e71ac0d732450a6a4b56200df98` | `2026-09-08T05:40:04.445628+00:00` | 340280 |

Final source/copy recheck at `2026-09-08T05:57:03.753038+00:00` matched all three pinned SHA-256 values, lengths and source mtime_ns values. See [manifest](title-fields-batch8-manifest.json) and [recheck](title-fields-batch8-source-recheck.json).
