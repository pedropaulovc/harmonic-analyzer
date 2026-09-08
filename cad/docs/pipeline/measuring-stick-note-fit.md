# Measuring-stick manufacturing-note fit

Issue [#712](https://github.com/pedropaulovc/harmonic-analyzer/issues/712)
records printed content loss on the measuring-stick and harmonic-base sheets.
This change addresses only the measuring-stick recipe. The corrected targeted
native run saved a readable sheet; cold reopening and full-stack acceptance
remain unproved here. The offline cases use synthetic native extents.

The retained measuring-stick PNG SHA-256 is
`a826ab15c5e955e81452bf39154040f8493e8c51a809453eced84b88a9d8d123`.
Its producing task ran at `3c0c4a97e69ead5f04fa760b8aa507c16143172d`,
2026-09-08 02:00:39.217692 to 02:00:48.351951 UTC, trace
`0x77395c518f1398e3d24809d67fc71f0f`. The lower manufacturing notes cross
the border and page edge. The [unaltered sheet and 51-sheet audit](https://github.com/pedropaulovc/harmonic-analyzer/blob/82ff30bde5a1beb1e35aec8813a3842cf0248d5d/cad/docs/evidence/2026-09-08-drawing-print/README.md)
preserve the full evidence. Whether this clipping was introduced by the retained
stack is unknown: the note anchor was unchanged, but a matching native baseline
was not run.

The recipe retains all note text, property links, fonts, dimensions, tolerances,
ruled-face orientation, 0..10 labels and explicit 1:1/1:2 view scales. Existing
tests deliberately cover these contracts; none asserts the old note anchor.

The recipe measures the manufacturing note and both view captions with the
existing native-note bounds helper. Its available rectangle is inside the live
sheet zone margins, below the ruled-face caption, and left of the isometric view,
its caption and the shared title-block keep-out. A 3 mm layout gap separates
these regions; containment itself has no tolerance. If the unchanged note is
too large, the recipe reports its extent and available region and stops before
finalization. Otherwise it translates the note once along each overflowing axis,
using the current native anchor, and requires a fresh native extent to fit.
An already contained note is not moved.

The bundled API references establish the call contract:

- `INote.GetExtent`: six doubles in drawing sheet coordinates; invalid for an
  invisible document. The recipe rejects invisibility and checks native
  current/active drawing and sheet identity around measurement and placement.
- `IAnnotation.GetPosition` and `SetPosition2`: a note's native anchor is the
  upper-left of its text box. A successful setter alone does not prove fit.
- `IView.GetOutline`: four sheet-coordinate view bounds.
- `ISheet.GetProperties2` and `GetZoneMargin`: live paper size and border margins.

The callback regression first failed against `86fda61b`: it reached finalization
without a native extent read or translation. Tests preserve the five original
assertion groups and cover oversized/missing/nonfinite extents, rejected/no-op
movement, changed margins, invisible/wrong documents and a document switch
during measurement. No test substitutes a shorter manufacturing note.

The targeted native result below supplies the measured bounds and saved-sheet
inspection. Offline bounds tests alone do not prove native font metrics, saved
printed content or cold-reopen persistence.

## First native attempt: property access rejected before measurement

The normal `doit drawing:measuring_stick` attempt at testing integration
`4013c480cbcd79c865a0cff59c02e3d2d548f3ae` failed before its first note extent
read. The guard passed `ISldWorks.ActiveDoc` through `_get_attr_or_call`, which
called the returned callable COM document. Native dispatch rejected that extra
call with `-2147352573`, "Member not found". This is a caller bug, not evidence
that the note cannot fit. No translation or finalization was reached.

The completed raw log was copied unchanged before any rerun from
`C:/src/ha-foundations-integration/cad/out/logs/drawing-measuring_stick.log` to
the owning worktree's ignored report
`cad/out/reports/measuring-stick-note-fit/native-4013-drawing-measuring_stick.log`.
Both SHA-256 reads were
`fb93c555b67075cfdc730b952a5099881f9dc79a5638dd687301ac92856ccfd4`.

The correction reads the documented early-bound `app.ActiveDoc` property
directly and retains the same native identity predicate. The callback fixture
now makes the returned document callable and raises if anything invokes it;
the new regression failed first with the same call chain (run-m_rpu1zc).
The related `Visible` property returns a Boolean, while `GetType`, `GetExtent`
and `GetSpecificAnnotation` are methods. Their existing reads do not perform
this extra document invocation.

## Corrected targeted native run

The normal `doit drawing:measuring_stick` run at
`f52cbde1acad6f877488d1ad85cb76f4eb9aba10`, adapter
`25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`, exited 0 in the genuine producer
checkout. Trace `0xee7bead1a5acf1bf430bdd8774ee9549` records the task from
2026-09-08 03:23:53.865208 to 03:24:04.479387 UTC (10.614179 seconds),
`drawing.build` at 9.366451 seconds and the note fit at 0.690573 seconds.
These are one targeted run's durations, not a paired performance comparison.

Native measured bounds, in sheet metres:

| Rectangle | xmin | ymin | xmax | ymax |
| --- | ---: | ---: | ---: | ---: |
| Before | 0.01567423887587821 | -0.0074659344262295035 | 0.15716711007025758 | 0.11033355503512882 |
| After | 0.060725035128805616 | 0.03725115222482439 | 0.20188419672131147 | 0.15505064168618268 |
| Available | 0.0157 | 0.0157 | 0.2469383793911007 | 0.17674515222482437 |

The single requested anchor was
`(0.06089851522248246, 0.15478876580796253, 0.0)`. The fresh after extent
passes strict containment. Both the owning agent and a separate read-only eye
pass inspected the complete saved PNG: notes 1 through 4 are contained and
readable; the ruler, 0..10 labels, dimensions and 1:1/1:2 captions remain visible.
The trace records native save, PDF export and PNG rendering as successful.
No cold reopen was performed for this targeted check.

| Saved output | SHA-256 |
| --- | --- |
| SLDDRW | ad4aafbe4fe5ab5af9e2e58b280e8d3e725f31373bfa984a97a8521efc9b7121 |
| PDF | d2e0a049487b001a6349fa263af594e8e15478d75699ac9b4eb5c7b5949f44f5 |
| PNG | 17594a793c1b547d62e12cab858cfe1796298f51bb4bf970246941ddff7737ea |

The source SLDPRT SHA-256 stayed
`c32c8af16c024e416fdb55d059ccc37b83b8da267f1e8c3c3641335936b94b4e`,
and the execution-token file SHA-256 stayed
`2441d7fb5cb6994130a2cb32f69727f91f40db2e590d00767c21108c839bfcbd`
across the failed and successful attempts. Separate read-only shared-file
hashes after the run matched these source/token hashes and the saved drawing.
The immediate repeat at exact `f52cbde1` skipped both part and drawing tasks,
exited 0 and added no telemetry: trace bytes stayed 9,125,695 and log bytes
20,359,196. This repeat did not reopen the drawing or provide cold evidence.

The [public raw receipts](../evidence/2026-09-08-measuring-stick-note-fit/README.md)
include the original failed command log and every raw record of the successful
trace. The old native/PDF/PNG outputs were backed up, not restored, under
`cad/out/reports/measuring-stick-before-1880-20260908` in the producer checkout.

Windows-local Codex reviewed the complete correction diff from `4013c480` to
`f52cbde1` with no actionable findings. The frozen correction passed 431
focused/adjacent tests, including graph and part isolation (run-smzbf8gg).
This closes the observed measuring-stick clipping on the targeted saved sheet;
it does not establish cold persistence or a successful full-stack build.
