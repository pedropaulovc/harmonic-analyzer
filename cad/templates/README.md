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

Four category templates own the static identity of the drawing while sharing
the same ASME B landscape border/zone geometry, title block, tolerance block
and third-angle projection symbol:

- `harmonic-analyzer-part.DRWDOT` — ordinary component drawings
- `harmonic-analyzer-gear.DRWDOT` — the eight gear/toothed-member drawings
- `harmonic-analyzer-schedule.DRWDOT` — spring schedule/specification sheets
- `harmonic-analyzer-assembly.DRWDOT` — BOM/balloon assembly drawings

Their title blocks visibly say PART, GEAR, SCHEDULE or ASSEMBLY, and the saved
sheet name carries the same identity. `_drawing_registry.DrawingCategory` is
the source of truth; each drawing task depends only on its category template,
so changing assembly or gear sheet defaults does not invalidate unrelated
part drawings.

Each template embeds its sheet format, so there is no separate `.slddrt`;
per-drawing setup only sets the sheet scale
(`_drawing_common.new_project_drawing`) and links the sheet's custom-property
view to the first drawing view (`_drawing_common.finalize_drawing`).

The document defaults also pin dimension leaders to bent-leader + horizontal
text for every SolidWorks dimension scope (general, angle, arc length, chamfer,
diameter, hole, linear, ordinate, radius and angular-running). Keep that policy
in all four templates. Do not restore the former per-drawing loop of 10 setters
and 10 readbacks; the template is the document setting's natural source.

`third-angle-projection.SLDBLK` is the projection-symbol block the title block
embeds, kept alongside as the editable source for future template work.

The layout audit's title-block keep-out box
(`_drawing_common._TITLE_BLOCK_LEFT_M` / `_TITLE_BLOCK_TOP_M`) MUST track the
block's extents — re-measure via a sheet-view annotation dump if the block
moves or grows.

### Title block

Left side, top to bottom: the general-tolerance block (**UNLESS OTHERWISE
SPECIFIED** — `.XX` / `.XXX` / angular / surface finish, linked to the source
part's `TOL_LIN_XX` / `TOL_LIN_XXX` / `TOL_ANG` / `TOL_SURFACE` custom
properties from `cad/config/title_block.yaml`); the edge-break note; FINISH;
MATERIAL; the ASME Y14.5-2018 interpretation note; DO NOT SCALE DRAWING; and
the third-angle projection symbol. Right side: project title; PART name; DWG.
NO. (`Number`, the MHA-### registry id); REV (the release tag); scale; UNIT;
copyright + CC BY-SA mark. The linked fields resolve from the source part's
custom properties via `$PRPSHEET` — `Number` / `Revision` / `Title` and the
`TOL_*` set are stamped by `_common.part_properties`, `Drawn By` /
`Revision Description` by `_drawing_marks.apply_drawing_properties`.
(Consolidating those two stamping paths is tracked in issue #249.)
`finalize_drawing` requires the `TOL_*` set on the linked model, so a stale
source part fails loud instead of saving blank tolerance cells.

The edge-break policy is authored directly in all four templates as `R0.25 OR
CHAMFER 0.25 MAX`. Keep generic drawing-wide notes synchronized across the
templates rather than rewriting them through COM for every generated drawing.

The title block's UNIT cell currently reads **mm**, matching the generated
drawing views (which dimension in mm until the inch migration, issue #290,
lands) — and the `TOL_*` display strings in `title_block.yaml` are the mm
renderings of the inch tolerances for the same reason (flip them back to the
inch strings with #290). The pipeline also stamps a `UNIT_DISPLAY` custom
property on every drawing document (`finalize_drawing`, currently `MM`) —
linking the UNIT cell to `$PRP:"UNIT_DISPLAY"` makes the declared unit track
the configured units automatically when #290 flips them to inches.

### The "For Personal Use Only" watermark

Sheets rendered on a **SolidWorks Maker / Student** seat carry a non-removable
`SOLIDWORKS Maker Product. For Personal Use Only.` watermark — it is imposed by
the licence, not by this template, and there is no API to suppress it. It is
expected on every drawing produced on a Maker seat and is not a defect in the
standard. A commercial seat would render without it.
