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
