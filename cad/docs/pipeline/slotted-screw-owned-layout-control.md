# Slotted-screw owned layout control

This diagnostic work extends the existing owned datum-policy pilot for the
[slotted-screw layout candidate](slotted-screw-native-layout.md). A capture-only
arm can collect imported drawing attachment slots from the genuinely built
source. The accepting target is not enrolled: source-model dimension kinds do
not establish the drawing's attachment arrays.

The witness requires the recipe's three model-dimension roles and three views at
6:1. It uses the existing native annotation measurement bank, including displayed
dimension strokes, to record signed clearances to the sheet's measured zone
border. A baseline overflow remains a recorded negative layout result. The
candidate must fit. Neither outcome replaces the pilot's source, attachment,
saved/cold drawing, or printed-content checks.

Enrollment requires a genuine local source build on the frozen producer branch,
its exact output SHA, execution token, producer trace, and native dimension-role
readback. The current 17 source pins and coverage contracts remain unchanged.
No synthetic test value is an enrollment value.

The existing pilot requires rocker, lever, and the selected target under both
source and guard roots. A declared diagnostic-only bundle may contain byte copies
of the pinned rocker/lever sources and the genuinely built slotted source, with
that same bundle supplied as both roots. The pilot protects the bundle and opens
only its uniquely named owned trial copies. Separate outer guards must retain the
upstream originals' paths, producer revisions, hashes, and provenance before and
after the trial. Staging is not a producer output restore or a token restamp.

The accepting observation readers retain uncropped full-sheet rendering and
literal printed text after the normal save and cold reopen. They are not yet
runnable against the unenrolled source. These checks run outside the recipe
timer. Correctness of the baseline/candidate pair comes first; one timing pair
cannot establish a performance benefit.

## Source provenance and the capture-only boundary

The source built by `part:slotted_screw` on
`3c0c4a97e69ead5f04fa760b8aa507c16143172d`, adapter `25bc99b1`, has SHA/token
`2033c1fe198e38eebd1c32aaecf38646ae3487569fb7848d718d083bb1736396`.
Producer trace `0xe73351e79208db7861d9b1e24b0923da` records a 44.506162-second
task. This is source-build timing, not drawing timing.

The subsequent read-and-close receipt is
`C:/src/ha-slotted-screw-native-layout/cad/out/reports/slotted-source-readback-_seyh1jg/closure.json`,
SHA `f6835f1d58bcabc55055adf5c904eaa3e12d9a889a88cae77dd59c4204a7a61e`.
Its two complete ten-dimension banks are exactly equal. The three marked roles
are `HeadDia@HeadProfile` (native kind 6, raw value
`0.008000000002000001` m), `HeadHt@Head` (kind 2, `0.0025` m), and
`ShankLg@Shank` (kind 2, `0.022` m). HeadDia retains `<MOD-DIAM>` in text
compartments 1 and 5. Source `Generator` identifies `3c0c4a97`, both linked-note
properties contain the full spec text, and closing the clean source without a
save leaves an empty document inventory and unchanged source hash. No imported
drawing attachment tuple is established by that receipt.

The capture-only arm requires that exact producer revision and source hash,
the prepared factory, and no other experimental factor. It runs the unchanged
recipe on a unique owned byte copy, with the existing owned save wrapper. The
recipe may save its diagnostic drawing/PDF/PNG; it never saves the source part.
After building, it records the complete native annotation bank before checking
the three imported parameter/view identities. Raw attachment arrays come from
that bank, not a second query or a guessed manifest. Source values, tolerances,
presentation, native handles, copied bytes and all protected originals must
remain exact. Partial observations survive errors, and cleanup/runtime/hash
errors cannot replace the primary error.

The copied part must report native Boolean `False` for its dirty flag on open
and immediately before cleanup, including after a recipe failure. An unchanged
file hash does not excuse an in-memory dirty source. The default BSURF grid and
tooth-observation modes are required through the parent CLI, worker CLI, direct
pilot call and direct capture callback.

The receipt says `acceptance: not_accepted`, even when `status: capture_only`.
It does not run cold acceptance, bless its own observed tuples, migrate pins or
prove the candidate's printed layout. A separately reviewed enrollment must add
the exact observed roles before baseline/candidate acceptance can run.

After the main agent stages the declared bundle and explicitly grants the seat,
the existing parent entrypoint can run this command from the reviewed diagnostic
checkout. The PID and bundle path must name that session's actual inputs:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<licensed existing PID>'
uv run --frozen python cad/scripts/diagnostics/probe_datum_policy_recipes.py --candidate 3c0c4a97e69ead5f04fa760b8aa507c16143172d --target slotted_screw --layout-observation capture_only --factory prepared --source-root '<declared bundle>' --guard-root '<same declared bundle>' --report-root cad/out/reports
```

The parent acquires the existing machine-wide seat lock and starts the owned
worker. Do not invoke `--worker` directly or set the seat marker manually. Outer
source/token guards remain the caller's responsibility as described above.

The accepting print contract requires each literal native text run within its
own measured annotation body, plus exact cold PDF glyphs and uncropped full-page
pixels. It does not infer CAD identities from PDF objects or guess a font-symbol
translation. Unsupported/ambiguous literal text fails explicitly. A rendered
visual inspection is still required; raster equality does not establish that
the initial drawing is correct.

## Offline reproduction

```powershell
$env:PYTHONPATH = 'cad/scripts;cad/comparisons/tools;SolidworksMCP-python/src'
uv run --frozen python -m pytest -q --tb=short cad/scripts/test_slotted_screw_layout_pilot_drawing.py
```

The initial synthetic suite passed 12 tests. It covers missing, hidden,
dangling, excluded and extra dimension data; numeric visibility, view and scale
changes; non-finite coordinates; absent strokes; and candidate border overflow.
Native dimension identities and printed output remain untested.

The capture-only implementation subsequently passed 68 focused cases, including
the actual existing pilot callback, both CLI routes, source-pin/context failures,
cleanup/primary-error preservation, interrupted reads, native-role identity
controls and a real PDFium full-page raster fixture. Those are COM-free tests,
not evidence that the new native capture has run.

Pre-native review exposed the missing initial/final source-dirty guard and the
direct-callback factor bypass. The added regressions failed in 15 cases against
`ce8d7236` (`run-bnwwg4ck`); three existing rejection controls already passed.
After correction, 256 focused/adjacent tests passed (`run-tm_5ds8b`), retaining
the original error object when a failing recipe also dirties its copied source.

## First native capture: property serialization, before recipe execution

The `197cb571` run stopped before the recipe. Its retained receipt is
`slotted-attachment-capture-06no8kxz/capture.json`, SHA
`c9d955abaf0e5e4bf6e46fe974028e6405fce7b1f0cfea23ea22c173eec1d254`.
Compared with the producer readback above, Generator and End View Note are exact.
Manufacturing Notes changes only from 954 to 970 characters: its 16 LF separators
are serialized as CRLF after reopening the owned copy. All 17 lines are otherwise
exact. The source is clean before and after, final guard errors are empty, and
the receipt remains failed / not accepted. No drawing attachment slots were read.

The diagnostic now compares native source-property and linked-note strings with
the spec after replacing CRLF with LF only. Raw strings remain in the receipt;
built/cold comparisons remain exact. Lone CRs, other controls, spaces, changed
lines and truncation are not normalized. Source pins, specs and drawing bodies
are unchanged. Four actual callback/linked-note regressions failed before this
correction (`run-0ohpgb2z`); 275 focused/adjacent tests then passed
(`run-8sx01hls`). A native rerun is still required.

The full-base Windows Codex review of `119ebdd7` found a separate diagnostic
failure-path bug: a report-write failure in the recipe-timing `finally` block
could replace the original recipe exception. Four combined-failure regressions
reproduced it (`run-_6726qqt`), including cancellation, keyboard interruption and
an additional cleanup failure. The checkpoint failure is now retained separately
and attached to the original exception. A checkpoint-only failure still fails the
capture. All 281 focused/adjacent tests pass (`run-at1bbxns`); this correction
changes neither native operations nor acceptance predicates.

## Native recipe saved; capture stopped on hidden sheet background

The `119ebdd7` recipe completed in 15.527312599937432 seconds and saved its
owned drawing/PDF/PNG. The capture then failed before parameter/view roundtrips
on hidden sheet surface-finish symbol `Sheet1/DetailItem324`. Receipt
`slotted-attachment-capture-uwahsqs8/capture.json` has SHA
`49ea2049b7b9db54ad8a19c7ccd33b48c2119e1f38f514660a683f533e4f3817`.
Source/copy hashes and native dirty flags remain unchanged; final guard errors
are empty. This is neither complete capture nor cold acceptance.

The prepared receipt, SHA
`cee1c2b0d50f5a9d7dd873d9293ebff5ae214c951358da5c1ed6338787e884b7`,
contains exactly one hidden surface-finish row, unchanged before/after. Its
position `[0,0,0]`, three raw lines, and empty arc/text/leader banks match the
captured symbol exactly. Owner type 1 denotes DrawingSheet; visibility 3 means
hidden. The complete drawing bank has three visible view dimensions, two view
notes, 43 template notes, one visible template finish and this hidden sheet finish.

The capture-only classifier reads that hash-guarded preparation evidence and
requires one exact matching hidden sheet finish with no attachments or dangling
state, plus native identity with the current sheet owner. It retains the raw row
as a background observation. Missing, duplicated, changed and unknown rows fail.
This comparison is not native identity across documents, nor approval of hidden
background in the accepting layout/print contract. It adds no full annotation scan.

The raw dimension tuples are HeadHt `[]/[]`, ShankLg `[]/[]`, and HeadDia
`[10]/[false]` (attachment types/null slots). They are observations only: none of
the required parameter/view roundtrips ran, so the accepting 18th target remains
unenrolled. The retained hidden-row fixture reproduced the capture failure before
the classifier (`run-ys870xon`); exact source/view/parameter checks still follow it.

## Full-base review and retained-receipt corrections

The complete Windows Codex review of `6f25cfb5` found three P2 issues. The capture
now records a recipe exception before the real ownership scope exits, retaining
any scope-checkpoint error separately. The staged PDF witness requires the entire
literal native text sequence inside each body, so `12.50`, `2.501`, or extra text
cannot pass for `2.50`. The retained JSON fixture is an explicit `check:recipe`
dependency. Neither the source pins nor the production layout was changed.

An independent replay of the actual raw capture and preparation receipt also
reproduced a status mismatch: preparation records `validated`, while its accessor
records `passed`. The classifier now checks the preparation contract. The fixture
also preserves native integral floats (`0.0` and `-1.0`) as floats instead of
reserializing them as integers. Its complete annotation, both prepared rows and
both receipt hashes were rechecked against the retained files. The classifier
then passed those actual files offline with only current-sheet owner handles
mocked; this is not a native call or acceptance result.

Eight fail-first cases (`run-tng4ta5j`) reproduced the status, dependency, numeric
PDF and real ownership-scope failures. The scope tests include the original
RuntimeError, cancellation and keyboard interruption; no assertion was weakened.
Fresh native dimension/source/view roundtrips and reviewed enrollment remain next.

The next full-base review (`732b23af`) found one further print false-pass: an
extra prefix could be discarded when it lay partly or entirely outside the
annotation body. Two fail-first cases reproduced it (`run-26c50vod`), with an
unrelated separate word elsewhere on the page retained as a positive control.
The witness now groups complete PDF words before applying containment; any word
that intersects the native body must fit there in full. It then compares the
complete literal sequence. All390 focused/adjacent cases pass (`run-zph4_zyj`).
This is a correction to the staged print checker, not an observed native export
defect or a new acceptance result.
