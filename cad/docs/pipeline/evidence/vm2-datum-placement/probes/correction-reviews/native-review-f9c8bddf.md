# Independent native evidence and publication review

Runtime head: `f9c8bddff7c5f56d094f46723d5bd8151d541e9a`.
Publication head: `9ecef40d999ce6a2839f2f330418f40f2011fda0`.
Adapter: `2269009ed56712867826516f4406afc98a0c2814`.

## Verdict and scope

No actionable finding in the final correction's native receipts, six independently inspected lifecycle PNGs, or the 66-file evidence publication. The correction's scoped datum attachment, rack leader clearance, cold-reopen and move/scale evidence is supported. This is an addendum to `full-review-f9c8bddf.md`, not a replacement for that complete baseline-to-head code/evidence review.

This reviewer authored no implementation and made no COM calls, source changes, Git changes or native reruns. Native behavior was independently assessed from completed original receipts, their exact artifacts and the PNG prints; native files and PDFs were byte-verified, not independently opened in SolidWorks or a PDF viewer. This does not accept a combined retained stack, the expensive full build, its closed snapshot or its exact-head zero-COM repeat. Those remain VM1 integration gates. External CodeRabbit status and VM1's earlier integration run were not independently refreshed in this bounded addendum.

## Receipt and identity audit

The three completed original receipt directories are under `cad/out/reports/datum-placement/`: `production-f9c8bddf`, `rack-production-lifecycle-f9c8bddf` and `rod-production-lifecycle-f9c8bddf`. The batch audit passed 144 assertions covering head/adapter identity, runtime-script and source stability, artifact hashes, production closure, lifecycle stage identities and measured gates.

- Normal drawing run: passed in 47.76388079999015 seconds. Its log shows rack drawing rebuilt; rod drawing and both source parts were current. This is not a fresh rod rebuild claim.
- All five recorded runtime script SHA-256 values were identical before and after. Their current disk bytes match the receipts; Git's path-aware filtered hashes match the frozen head's blobs.
- Rack recipe runtime SHA-256 is `86a1ce874e9003f0781c6bd589cb5fffedcbf0447c6695dbf6fb0402d88ceec8`; committed Git-blob SHA-256 is `5735c2389ffbb5c26de2d247fbabfa9958e429120783630e2fe47c6335e816ce`. Git filtering proves these are the same source content under checkout line-ending conversion, not an unrecorded implementation change.
- Both source part hashes remained unchanged across normal production and both lifecycle runs, and match the actual source files. Rack: `24eb4236303c758016d2340bd6cfbee63ffed63e2f5a73bfb99f889adbaac418`. Rod: `59f635b07d5b1edb91ea828c0f9f8f8285cbcbbe17ce188cddeafef8ae08e8db`.
- All six production output hashes, both lifecycle working drawing hashes, and all 16 lifecycle PNG/PDF export hashes match their receipts and the files. Original production drawings remained unchanged by lifecycle testing.
- Each lifecycle contains exactly cold-open, moved, scaled, restored and second-cold-open stages. Each records the semantic source/body/edge identity checks, distinct adjacent-face ownership, native datum attachment and finite measured geometry. Rack stages additionally retain one attached non-dangling Ra 1.6 finish symbol and the actual expected bore-rim leader endpoint.
- The separate per-part native-position stability tolerances remain unchanged: rod 0.020 mm and rack 0.100 mm. Clearance threshold remains 1.000 mm; anchor-error limit remains 0.000010 mm (1e-8 m).
- Both lifecycle restoration errors and second-cold-open errors are zero. Second-cold-open PNGs are byte-identical to first-cold-open PNGs for both parts. Rod's ink translation residual is approximately 5.59e-17 m; rack's is zero.
- The production closure receipt reports `production_closed_without_save_bytes_unchanged`. This review checked that receipt and preserved bytes, not a fresh live document inventory.

| Measured quantity | Rack ordinary stages | Rack scaled | Rod ordinary stages | Rod scaled |
| --- | ---: | ---: | ---: | ---: |
| Datum/diameter clearance (mm) | 1.947243 | 2.521455 | 5.902837 | 7.628395 |
| Finish/datum clearance (mm) | 4.457878 | 5.597262 | not applicable | not applicable |

Rack lifecycle passed in 70.73783450003248 seconds; rod in 14.856386000057682 seconds. Rack was moved by (8, 5) mm and scaled from 1:1 to 1.25:1, then restored. Rod received the same translation and changed from 2:1 to 2.5:1, then restored. Recorded leader endpoint errors are below the unchanged limit at every stage.

| Original receipt | SHA-256 |
| --- | --- |
| `production-f9c8bddf/receipt.json` | `30376bd3d36bf8baa6010ac923f6b51e152d18fd805043e10a7843e9fe4ec23e` |
| `production-f9c8bddf/closed.json` | `6b48aa20a01f522db12ef0915e230a76a507a444b82c14ad398a434edd181ceb` |
| `rack-production-lifecycle-f9c8bddf/receipt.json` | `d7030f7dcc24b9c596d880b1a0b2666b3214cc9cc35489dc6c70103a90ece92a` |
| `rod-production-lifecycle-f9c8bddf/receipt.json` | `d0ed67a0c33fa223c1f3038a8c1e17673e583c33288f26f88e5df1644ee813a5` |

## Independent print inspection

Individually viewed `cold_open.png`, `moved.png` and `scaled.png` for both final lifecycle runs: six complete sheets, not only cropped details. Rack Ra 1.6 is now visibly clear of the adjacent side view and lower notes at all three states. Its leader remains separate from the datum and diameter annotation. Datum A, bore band and ream note are readable. The rod datum and diameter are readable and separate throughout; length band, cylindricity, perpendicularity, finish and crown notes remain visible.

These are scoped visual findings, not unrestricted manufacturing-sheet acceptance. Existing Number/Rev title-block crowding remains on both sheets; the rack moved/scaled Gear Data heading touches its border. The publication explicitly leaves those with VM1 under #709/#712. The rod's scaled stress image shows an actual 2.5:1 view while its static note still reads `END VIEW SCALE 2:1`; that image proves attachment under scaling, not a releasable sheet with correct scale text. Restoring 2:1 restores agreement. The publication accurately states this limitation.

The earlier `184b6a76` rack moved/scaled prints failed visual clearance despite passing numeric receipt gates. That failure is explicitly retained and superseded, not silently converted into acceptance. Numeric clearance alone does not certify text glyph clearance.

## Publication byte audit and summary consistency

Pinned publication commit `9ecef40d` changes exactly 66 files from runtime head `f9c8bddf`, all under `cad/docs/pipeline/evidence/vm2-datum-placement/`. There are no script, config, template, adapter or pipeline runtime changes in that delta. Every one of the 66 committed Git blobs equals the corresponding reviewed working-file bytes.

- `probes/correction-f9c8bddf`: all 30 files accounted for. All match the retained originals byte-for-byte, including the six current production artifacts; those six also match their receipt hashes.
- `probes/production-184b6a76-visual-failure`: all 30 files accounted for. Its 24 receipt/log/lifecycle files match their retained original files byte-for-byte. Its six historical production artifacts match the exact SHA-256 values in the retained original `production-correction/receipt.json`. Those historical artifacts were not compared to now-overwritten current production paths.
- `probes/correction-reviews`: all five files match the original local review/log files byte-for-byte.
- Total: 59 direct original-file byte comparisons and 12 production-artifact receipt-hash comparisons, with six current artifacts covered by both methods. Zero mismatches. The remaining publication file is the reviewed narrative `correction-f9c8bddf.md`.

The complete narrative's final native measurements, hashes, runtime identity, line-ending explanation, visual limits and retained failure provenance agree with the inspected evidence. The published offline log supports `1504 passed in 62.11s`; graph and part-isolation tasks are marked current rather than rerun, as the narrative says. Its full-review reference preserves the distinction between the earlier complete code/evidence review and subsequent native proof. No reviewed statement promotes VM2's scoped run into VM1 combined-stack acceptance.

The developing-solidworks skill informed the review's distinction between native attachment identity, actual leader endpoint readbacks and visual print acceptance; a passing COM return or numeric clearance alone was not treated as proof of all three.
