# Complete production drawing checks

The normal two-drawing run at `2ef52374e7589f5e6aa9481c2d03df3881408520`
passed in 73.894 s. [Receipt and exact native/PDF/PNG outputs](probes/production-2ef52374/receipt.json)
are published together. Recipe, graph and part-isolation gates passed with
1444, 21 and 4 tests respectively; the complete offline log is adjacent.
This is a targeted drawing result, **not full-stack acceptance**.

The helper required drawing-to-source-to-drawing correspondence, source solid
body identity, intended circle/cylinder, exactly two adjacent faces, one
non-dangling semantic edge attachment, label/shoulder persistence and finite
position before/after rebuild. Native rebuild drift was zero for both datums.
The 20/100 um values now measure native-position stability, as VM1 explicitly
approved; they do not prove the old requested-XY positions.

## Complete-drawing lifecycle at 33696944

Both [rack](probes/rack-production-lifecycle-33696944/receipt.json) and
[rod](probes/rod-production-lifecycle-33696944/receipt.json) passed on copies
of those complete production drawings. Each changed view was saved and cold
reopened before reading ink. Every stage re-resolved the intended circle,
mapped its source body, checked the strict drawing-edge round trip and
attachment, and retained the label, shoulder state and intended cylinder.

| Measurement | Rod | Rack |
| --- | --- | --- |
| Runtime | 14.698 s | 73.771 s |
| Translation position error | 0 | 0 |
| Maximum primitive translation error | 5.6e-17 m | 0 |
| Restored position error | 0 | 0 |
| Second cold-reopen position error | 0 | 0 |
| Source bytes unchanged through lifecycle | yes | yes |

Rack datum-to-diameter line/filled-triangle clearance was 1.947243456304 mm
at cold open, moved, restored and second cold open, and 2.521455399822 mm at
1.25x view scale. These measurements use current ink; the historical stale
primitive results remain invalid. They are not a whole-sheet visual gate.

The rod source remained
`59f635b07d5b1edb91ea828c0f9f8f8285cbcbbe17ce188cddeafef8ae08e8db`.
The rack drawing build changed its source from `aa70ef6a...` to
`24eb4236303c758016d2340bd6cfbee63ffed63e2f5a73bfb99f889adbaac418`;
the lifecycle preserved that exact post-build identity. The separate
[same-input callout/save controls](source-hash-cause.md) establish why imported
`THRU - REAM` text dirties and saves the source dimension. This production
receipt itself brackets the complete build, not each source-write operation;
it is not a byte-identity waiver or ledger/token restamp.

## Visual findings still requiring correction/integration

The full production sheets show the required manufacturing content: rod
diameter/length bands, cylindricity, perpendicularity, finish and crown notes;
rack bore band/ream note, gear data, perpendicularity, finish and runout notes.
The rod datum is readable, and the relocated rack bore dimension no longer
crosses the native datum leader. Two other visible findings prevent a clean
complete-print verdict at this stage:

- Both unchanged title blocks crowd drawing Number and Revision together
  (`MHA-060v32` / `MHA-070v32`). VM1 owns the shared template; VM2 leaves it
  unchanged under the explicit file-ownership boundary.
- The rack finish leader crowds the datum triangle. In the enlarged lifecycle
  print, the finish symbol/text also crosses gear teeth. This is visible only
  on the complete sheet, not the earlier partial datum controls. A rack-only
  finish-layout correction and additional attachment/ink checks are underway.

No full-stack run, closed integration snapshot, exact-head zero-COM repeat,
or merge is claimed. Those gates wait for VM1's explicit combined acceptance
SHA, covering the retained stack including #686/#687.
