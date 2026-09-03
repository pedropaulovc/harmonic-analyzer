---
name: solidworks-property-link-syntax
description: Sheet-format notes evaluate property links only in the double-quoted form ($PRPSHEET:"NAME" / $PRP:"NAME"); the brace form prints as literal text. $PRPSHEET reads the part, $PRP the drawing.
metadata:
  type: reference
---

2026-09-02, title-block rework of `harmonic-analyzer.DRWDOT`: two new notes
were typed as `$PRPSHEET:{COPYRIGHT_YEAR}` and `$PRPSHEET:{BUILD_ID}` (the
brace spelling I had written in review notes) and rendered VERBATIM on the
sheet while every neighbouring row resolved. The COM diagnostic showed the
working rows all use `$PRPSHEET:"TOL_LIN_X"` — double quotes. One render
round lost.

**Rules:**
- Link syntax is `$PRPSHEET:"NAME"` (custom property of the model the sheet's
  property view points at) or `$PRP:"NAME"` (custom property of the DRAWING
  document itself). Braces are not a link.
- Built-ins take the same quoting: `$PRPSHEET:"SW-Author(Author)"`,
  `$PRP:"SW-Sheet Scale"`.
- A value that must describe the SHEET (build id, sheet-level stamps) goes on
  the drawing via `apply_custom_properties(..., model=drawing_model)` and is
  read with `$PRP`; a value about the PART (tolerances, material, copyright
  year) is stamped in `part_properties` and read with `$PRPSHEET`.
- Verify a template edit by reading the notes back over COM
  (`INote.PropertyLinkedText` vs `GetText`): a link that did not resolve shows
  the raw `$PRP...` text in both.

Related: [[dimxpert-block-tolerance]] (which properties the block reads).
