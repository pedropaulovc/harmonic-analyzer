# Measuring-stick manufacturing-note fit

Issue [#712](https://github.com/pedropaulovc/harmonic-analyzer/issues/712)
records printed content loss on the measuring-stick and harmonic-base sheets.
This change addresses only the measuring-stick recipe. Native acceptance of
the correction is pending; the offline cases use synthetic native extents.

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

The owning native validation must still rebuild this drawing from its genuine
source, retain the measured before/after bounds and source guards, and inspect
the complete saved PDF/PNG. Offline bounds tests do not prove native font metrics,
saved printed content or cold-reopen persistence.
