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

### Line weights

Both drawing templates set Document Properties > Line Thickness to
**Thin 0.13 mm** and **Normal 0.18 mm**. Thick through Thick(6) keep the
SolidWorks defaults (0.35 to 2.0 mm). Line Font maps visible edges to Normal
and hidden edges, tangent edges, cosmetic threads, and hatch to Thin. The border
uses Thick(2), 0.5 mm.

The SolidWorks defaults of 0.18 mm and 0.25 mm filled dense assembly views at
1:3 with ink. Examples include the cone gear teeth and screw threads on
`drive-train-assembly` sheet 1. The lighter pair keeps the 1.4:1 contrast
between visible and thin lines. ISO 128 lists 0.13 mm as its thinnest line
width. To check weights in an exported PDF, read the stroke widths from its
drawing operators with PyMuPDF `page.get_drawings()`, and multiply by
25.4/72 to get millimetres.

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
NO. (`Number`, the MHA-<subsystem>-### registry id (assembly 000; parts 001 onward)); REV (the release tag); scale; UNIT;
copyright + CC BY-SA mark. The source part supplies the linked `$PRPSHEET`
fields. `_common.part_properties` stamps `Number`, `Revision`, `Title`, and
the `TOL_*` set. `_drawing_marks.apply_drawing_properties` stamps `Drawn By`
and `Revision Description`. Consolidating these stamping paths is tracked in
issue #249.

`finalize_drawing` requires the `TOL_*` set on the linked model, so a stale
source part fails before it can save blank tolerance cells.

The cone-pivot-post drawing also checks the linked Finish note's native extent
against the landscape template's cell rules. In the exported sheet, those rules
are at x = 215.900 / 308.328 mm and y = 33.584 / 44.485 mm, measured from the
lower-left sheet origin. Its check rounds these boundaries inward, not outward.
The linked value starts at about x = 217.8 mm; 218 mm is not the cell's left
rule. When editing this title block, remeasure all four boundaries and update
`draw_dt_cone_pivot_post._FINISH_CELL` with its offline containment cases; do
not move the correctly placed note merely to satisfy an obsolete inset.

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
