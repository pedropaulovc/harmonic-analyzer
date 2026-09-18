# Harmonic-analyzer SolidWorks templates

The project-owned SolidWorks templates, all **created manually in SolidWorks**
(not generated — the old `create_drawing_standards.py` generator and the
`asme-b-book.*` assets it produced are gone). Edit them only in SolidWorks,
then rebuild/re-render and visually inspect before committing the changed
binary.

## harmonic-analyzer.PRTDOT — part template

The default part template every `part:*` build instantiates.
`_common._pin_default_part_template` points the seat's default-part-template
preference at it on every build connect (read-back verified, raises on
failure), so a build never silently runs on a drifted seat template. It must
carry the DimXpert block-tolerance document properties that are GET-ONLY over
COM on R2026x — notably the **angular tolerance ±1°** and the 2/3-decimal
linear precisions (`cad/config/title_block.yaml` is the source of truth;
`_common.apply_block_tolerances` stamps the settable ones and RAISES if the
get-only ones drift from the config). The template is a `file_dep` of every
part task (`dodo.PART_TEMPLATE`), so editing it rebuilds all parts and busts
their cache keys.

## Drawing templates

Manufacturing drawings select one of two ASME B templates:

- `harmonic-analyzer-landscape.DRWDOT`: 431.8 × 279.4 mm
- `harmonic-analyzer-portrait.DRWDOT`: 279.4 × 431.8 mm

Both templates contain their border and zone geometry, title block, tolerance
block, and third-angle projection symbol. The sheet formats are embedded, so
there is no separate `.slddrt`. `_drawing_registry.DRAWING_TEMPLATES` owns each
template's path, physical dimensions, raster dimensions, and title-block
keep-out. Every `DrawingSpec` selects a `DrawingLayout` explicitly. The current
production fleet uses landscape; changing a row to portrait switches that
drawing's template and cache dependency together.

Per-drawing setup sets the sheet scale
(`_drawing_common.new_project_drawing`). `_drawing_common.finalize_drawing`
links each sheet's custom-property view to its first drawing view and enforces
the standard isometric projection as high-quality Shaded With Edges.

`third-angle-projection.SLDBLK` is the projection-symbol block embedded in both
templates and remains the editable source for future template work.

The layout audit reads the title-block keep-out from `DRAWING_TEMPLATES`. Its
measured `(left, top)` bounds are `(0.216, 0.066)` m for landscape and
`(0.0636, 0.066)` m for portrait. Re-measure and update the matching registry
entry if either block moves or grows.

### Title block

Left side, top to bottom: the general-tolerance block (**UNLESS OTHERWISE
SPECIFIED**; `.XX` / `.XXX` / angular / surface finish, linked to the source
part's `TOL_LIN_XX` / `TOL_LIN_XXX` / `TOL_ANG` / `TOL_SURFACE` custom
properties from `cad/config/title_block.yaml`); the edge-break note; FINISH;
MATERIAL; the ASME Y14.5-2018 interpretation note; DO NOT SCALE DRAWING; and
the third-angle projection symbol. Right side: project title; PART name; DWG.
NO. (`Number`, the MHA-### registry id); REV (the release tag); scale; UNIT;
copyright + CC BY-SA mark. The source part supplies the linked `$PRPSHEET`
fields. `_common.part_properties` stamps `Number`, `Revision`, `Title`, and
the `TOL_*` set. `_drawing_marks.apply_drawing_properties` stamps `Drawn By`
and `Revision Description`. Consolidating these stamping paths is tracked in
issue #249.

`finalize_drawing` requires the `TOL_*` set on the linked model, so a stale
source part fails before it can save blank tolerance cells.

#### The PART name is fitted to its cell at build time

The PART note is authored with a text box narrower than the cell it sits in
(measured at 68.83–69.67 mm against a 106.62 mm cell), so a long `Title`
wrapped onto a second line — and because a note grows downward from its
anchor, that line landed under the cell's lower rule, on the `DWG. NO.`
caption. `harmonic-analyzer-assembly` (MHA-A08) shipped that way in v36, along
with 17 other sheets.

`finalize_drawing` now fits the name instead: `_title_block_text.fit_part_name`
picks the largest integer point size (16 pt down to a 9 pt floor) at which the
name fits the cell's real usable width, and
`_drawing_common.fit_title_block_part_name` applies it to that sheet's own
template note through `EditTemplate` → `ITextFormat.LineLength` /
`CharHeightInPts` → `EditSheet`, then re-reads `INote::GetExtent` to prove
the result is one line inside the cell. **Only the points property is
written.** `ITextFormat` also carries `CharHeight`, in system units, and it
is *not* the same number in metres: it is the CHARACTER height, so writing
the em size into it renders the note 1.2053× too big — measured on the farm
across four names at 12/15/16 pt on three workers (extent 2.4850–2.4856 em,
size-independent), and on the same sheet twice: slotted_screw's 15 pt note
measured 13.15 mm with the write and 10.91 mm without it. (An earlier
revision of this note said 1.381×. That was the inflated extent divided by
a one-line constant of 1.8 em that had itself been back-derived from 1.381;
one correct line measures 1.91–2.06 em.)
A note that declares its height in system units (`IsHeightSpecifiedInPts`,
a read-only **method**, returns false) is therefore refused with that
message rather than converted, on every sheet: the em-to-character ratio is
an inference from one campaign, not a measured font constant. The fleet's
templates author in points. The DRWDOT binary is never written; the edit
lives in the SLDDRW. A name that already fits the note's authored box keeps
its ink: the note is read, but no format is written.

The width model is the template font's own glyph advances, taken from the
Century Gothic CID subset embedded in the released PDFs. **If the title block
moves, the cell is resized, or its font changes, re-measure**: the field
geometry lives in `_drawing_registry.DRAWING_TEMPLATES[...].part_name_field`
and the glyph table in `_title_block_text.GLYPH_ADVANCE_PER_MILLE`, both with
their provenance recorded in comments. Re-authoring the note fails the build
loudly rather than mis-fitting, because the applier checks the whole format
the model assumes — family, weight, style and point size, which
`ITextFormat` carries independently — on **every** sheet before it trusts the
model, including the sheets it decides to leave alone, since "this name fits
unwrapped at 16 pt" is itself a verdict of the model and a wider face or a
larger size would break it.

The UNIT cell links `$PRP:"UnitOfMeasure"`, SolidWorks' drawing-document unit
property. SolidWorks updates it when the document unit system changes through
the status-bar unit picker: MMGS displays `mm`, and IPS displays `in`. The
pipeline configures dimensions in millimeters today. No custom UNIT property
is stamped.

### The "For Personal Use Only" watermark

Sheets rendered on a **SolidWorks Maker / Student** seat carry a non-removable
`SOLIDWORKS Maker Product. For Personal Use Only.` watermark — it is imposed by
the licence, not by this template, and there is no API to suppress it. It is
expected on every drawing produced on a Maker seat and is not a defect in the
standard. A commercial seat would render without it.
