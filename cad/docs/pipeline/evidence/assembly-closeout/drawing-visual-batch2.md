# Shared title fields: pinned visual batch 2

Head: `64c3dab4875354a7d44d709539e001db920a0377`.
Checkout: `C:/src/ha-assembly-closeout-independent`.

Codex visually inspected all 13 pinned complete drawing sheets and all 13
readable title-field crops. **DWG and REV values remain separate on 13/13.
Title/material/finish containment passes 12/13: the
`channel-spring-installed` title wraps over the DWG label.** No material or
finish text overflow was observed in this batch.

The exact filename list was pinned once, excluding the 14 names in
`title-fields-batch1-manifest.json`, with a cap of 20. There were 13 remainder
files at that pin, and all 13 were included. No later outputs were added or
chased. The immutable source-byte copies, source SHA-256 values, timestamps,
dimensions, crop coordinates, and crop SHA-256 values are recorded in
[title-fields-batch2-manifest.json](title-fields-batch2-manifest.json).
The actual inspected files are under
[title-fields-batch2-images](title-fields-batch2-images).

Each full PNG is 5100 by 3300 pixels. Each title crop is the unscaled pixel
rectangle `[3060, 2508, 5100, 3300]` from its pinned full sheet, producing a
2040 by 792 crop. The crops are inspection derivatives; the full-sheet copies
retain the exact original PNG bytes.

| Sheet stem | Visible DWG no. | Visible REV | Title containment | Material / finish containment |
| --- | --- | --- | --- | --- |
| alignment-pinion | MHA-002 | v32 | Contained | Both contained |
| boss-hook | MHA-005 | v32 | Contained | Both contained |
| bracket-screw | MHA-108 | v32 | Contained | Both contained |
| channel-spring-installed | MHA-011 | v32 | **Overflows downward** | Both contained |
| cone-gear-shaft | MHA-014 | v32 | Contained | Both contained |
| cone-gear | MHA-013 | v32 | Contained | Both contained |
| cone-tip-block | MHA-092 | v32 | Contained | Both contained |
| connecting-rod | MHA-017 | v32 | Contained | Both contained |
| fillister-screw | MHA-030 | v32 | Contained | Both contained |
| magnifying-clamp | MHA-042 | v32 | Contained | Both contained |
| measuring-stick | MHA-046 | v32 | Contained | Both contained |
| spring-hook | MHA-090 | v32 | Contained | Both contained |
| transgear-pinion | MHA-080 | v32 | Contained | Both contained |

The DWG numbers and `v32` strings are readable within their separate cells in
every crop. On the channel spring sheet, the title's second line obscures the
`DWG. NO.` label above the number; it does not merge the number into the REV
cell. This distinction does not excuse the title containment failure.

## Observations to retain with deferred work

1. **Channel spring title wrapping:** In
   [the channel-spring-installed crop](title-fields-batch2-images/channel-spring-installed_drawing_title.png),
   `channel-spring-` occupies the first line and `installed` crosses the title
   cell's lower boundary into the `DWG. NO.` label. The same overflow is visible
   on the complete sheet. Retain with the existing title/material layout
   follow-up [#709](https://github.com/pedropaulovc/harmonic-analyzer/issues/709).
   No old-template comparison was performed, so the cause and introduction
   point are unknown; this receipt does not attribute the wrap to the template
   replacement.
2. **Measuring-stick body notes clip:** The complete
   [measuring-stick sheet](title-fields-batch2-images/measuring-stick_drawing.png)
   shows its lower-left general notes crossing the bottom drawing border,
   overlapping the Maker watermark, and continuing beyond the bottom PNG
   edge. Its title/material/finish fields are contained. This is an incidental
   whole-sheet layout observation, separate from the shared title-field check;
   retain with deferred drawing work
   [#712](https://github.com/pedropaulovc/harmonic-analyzer/issues/712).
   No old-sheet comparison was performed, so its cause and introduction point
   are unknown.

## Boundaries

This is a partial visual receipt, not a complete drawing acceptance or full
native gate. The complete sheets were viewed for context; dimension semantics,
datum/leader persistence, and tolerances were not re-certified here. In
particular, a hot PNG cannot waive the separately known rack cold-reopen leader
failure in #702; rack is excluded by the batch-1 name list in any case.

No COM was launched, no drawing/source/test/telemetry files were changed, and
no GitHub issue or PR was mutated by this reviewer. Only these untracked
inspection copies, crops, manifest, and report were written.
