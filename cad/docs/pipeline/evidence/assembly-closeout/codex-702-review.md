# Codex full-diff and native-evidence review of PR #702

- Base: `55056d4990d38ebb461f343d3002fc90731b9e73`
- Latest reviewed head: `748cf37c18bc8e1ffe65651769e42f0696f644f9`
- Runtime head: `f9c8bddff7c5f56d094f46723d5bd8151d541e9a`
- Adapter: `2269009ed56712867826516f4406afc98a0c2814`
- Reviewer: Codex / GPT-6, independent read-only review on VM1.

## Verdict

**Clean latest-head review: no actionable code or evidence findings.** The
published native receipts and independently inspected prints support the
scoped datum and rack-finish correction at runtime head `f9c8bddf`.

This closes the native-evidence uncertainty recorded in the preceding
`codex-702-f9c8bddf-review.md`. It does not replace VM1's final combined-head
full build, geometry/identity comparison, closed snapshot or zero-COM repeat.

## Complete diff coverage and preserved originals

The base-to-head diff contains 435 files. The complete prior review at
`f9c8bddf` covers the first 368 files. Its clean code result carries forward
through explicit tree identity: both heads have `cad/scripts` tree
`580a26ce90bb4c47dbc57792640960bce347f46a`.

The entire subsequent delta consists of 67 added evidence files under
`cad/docs/pipeline/evidence/vm2-datum-placement/`. No existing file changes,
including earlier failed evidence. All 67 exact Git blobs were extracted to
the ignored `codex-702-748cf37c-WORK` folder; their paths, blob IDs, SHA-256 and
lengths are retained in `codex-702-748cf37c-extraction.json`. No checkout or
image transformation occurred.

The publication narrative, current and intermediate-failure receipts,
production/lifecycle artifacts, test logs, and independent review reports were
checked against their stated scope. The prior `184b6a76` numeric passes remain
raw originals and are accurately described as a separate visual failure.
Their artifacts also match their receipts; they are not compared to later
overwritten production paths.

## Receipt and artifact audit

The repeatable audit passed 194 checks, including exact output/log hashes,
source preservation, native source/body/edge correspondence, datum attachment
and shoulder readbacks, intended bore-rim endpoints, stage inventories,
position errors and independently recalculated line/triangle clearances.
Both corrected and retained intermediate bundles were checked. Original
SLDDRW/PDF files were byte-verified, not opened in SolidWorks or a PDF viewer.

The corrected normal run reports exit 0 in 47.763881 seconds. Its actual log
records rack drawing rebuilt; rod drawing and both parts were current. All
five monitored runtime hashes and Git head are stable before/after. The
closure receipt is hash-linked to that run and reports
`production_closed_without_save_bytes_unchanged`.

Both corrected lifecycles contain exactly first cold open, moved, scaled,
restored and second cold open. Changed-view ink is refreshed through
save/close/reopen. The movement is +8/+5 mm and scale multiplier is 1.25.
The first cold open is the documented baseline; no pre-save insertion witness
is inferred. Both restore and second-reopen errors are zero. Their first and
second cold PNGs are byte-identical.

| Recomputed clearance | Rack ordinary stages | Rack scaled | Rod ordinary stages | Rod scaled |
| --- | ---: | ---: | ---: | ---: |
| Datum/diameter, mm | 1.947243456 | 2.521455400 | 5.902836736 | 7.628394517 |
| Finish/datum, mm | 4.457878257 | 5.597262226 | N/A | N/A |

The minimum clearance requirement remains 1 mm. The rack and rod native
position-stability limits remain 100 and 20 micrometres respectively; those
are distinct from the `1e-8 m` ink/rim consistency limit. The finish is one
non-dangling annotation on the intended semantic edge, reads `Ra 1.6`, and
terminates at the positive-X projected rim at every stage. The existing
manufacturing values are unchanged.

The published offline log contains `1504 passed in 62.11s`; graph and part
isolation are marked current. This is retained VM2 test evidence, not a suite
rerun by this reviewer.

## Independent visual inspection

Viewed both complete production PNGs and all six corrected lifecycle cold,
moved and scaled PNGs individually. Rack bore dimension, datum and finish
leaders remain readable and separate. `Ra 1.6` clears the adjacent side view
and lower notes in every inspected state. Rod datum and diameter remain clear;
the length, surface-finish, geometric-tolerance and crown notes remain readable.
Also viewed the retained `184b6a76` moved rack PNG: its side-view overlap is
visible and is resolved in the corrected image.

These are scoped correction findings. The disclosed shared Number/Revision
crowding and moved/scaled rack Gear Data heading touching the border remain
visible and tracked separately under #709/#712. The rod scaled stress print
retains its static 2:1 note while the tested view is 2.5:1; the restored
production view is 2:1. The publication accurately limits that stress print
to attachment evidence. None of these existing limits is presented as fixed
or as unrestricted manufacturing-sheet approval.

## Exact identities and verification limits

| Original | SHA-256 |
| --- | --- |
| Normal run receipt | `30376bd3d36bf8baa6010ac923f6b51e152d18fd805043e10a7843e9fe4ec23e` |
| Production closure receipt | `6b48aa20a01f522db12ef0915e230a76a507a444b82c14ad398a434edd181ceb` |
| Rack lifecycle receipt | `d7030f7dcc24b9c596d880b1a0b2666b3214cc9cc35489dc6c70103a90ece92a` |
| Rod lifecycle receipt | `d0ed67a0c33fa223c1f3038a8c1e17673e583c33288f26f88e5df1644ee813a5` |
| Rack production SLDDRW | `c71ea20ed14de4c9718f281a2003191aa3876960820673e8bdf4f7617a8d54ce` |
| Rod production SLDDRW | `981b4a065a07f0779caf1d20730e5d7170d2efcba955318471c820576600447b` |
| Rack source hash preserved in all receipts | `24eb4236303c758016d2340bd6cfbee63ffed63e2f5a73bfb99f889adbaac418` |
| Rod source hash preserved in all receipts | `59f635b07d5b1edb91ea828c0f9f8f8285cbcbbe17ce188cddeafef8ae08e8db` |

The original VM2 source-part files and working recipe files are unavailable
at their recorded paths on VM1. This reviewer independently verified their
recorded before/after consistency and available published output identities.
The two recipe runtime hashes cannot be reproduced by uniform LF/CRLF
conversion of their Git blobs. VM2's published independent native audit
reports that path-aware Git filtering matched all five runtime files; that
specific working-file check is attributed to that audit, not claimed as
independently reconstructed here. The other three monitored runtime files
match available Git/CRLF variants directly. The recipes' Git code is explicitly
identical between the reviewed and published heads.

Reproduce the pure receipt/hash audit:

```powershell
uv run --no-sync python cad/out/reports/closeout-verification/codex-702-748cf37c-audit.py
```

Audit JSON SHA-256:
`b2aca3213c9f812b98429aa4976766a2bda7e4e0a517ad485a639380de2f0455`.

No COM calls, checkout, tracked changes, native reruns, telemetry writers or
test-suite execution occurred. All extracted originals and review artifacts
remain in ignored reports. Tracked status was clean at the final check.
