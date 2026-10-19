# Harmonic-analyzer SolidWorks templates

The project-owned SolidWorks templates were **created manually in SolidWorks**
(the old `create_drawing_standards.py` generator and its `asme-b-book.*` assets
are gone). Maintain their native documents in SolidWorks, either interactively
or with `cad/scripts/maintain_drawing_templates.py`; do not reconstruct their
sheet geometry from code. Rebuild/re-render and visually inspect changed
binaries before committing them.

## harmonic-analyzer.PRTDOT — part template

The default part template every `part:*` build instantiates.
`_session._pin_default_part_template` points the seat's default-part-template
preference at it on every build connect (read-back verified, raises on
failure), so a build never silently runs on a drifted seat template. It must
carry the DimXpert block-tolerance document properties that are GET-ONLY over
COM on R2026x — notably the **angular tolerance ±1°** and the 2/3-decimal
linear precisions (`cad/config/title_block.yaml` is the source of truth;
`_part_properties.apply_block_tolerances` stamps the settable ones and RAISES if the
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
keep-out. Every `DrawingSpec` selects a `DrawingLayout` explicitly; production
drawings use both orientations. Changing a row's layout switches its template
and cache dependency together.

Per-drawing setup sets the sheet scale
(`_drawing_common.new_project_drawing`). `_drawing_common.finalize_drawing`
links each sheet's custom-property view to its first drawing view and enforces
the standard isometric projection as high-quality Shaded With Edges.

### Line weights

Both drawing templates set Document Properties > Line Thickness to
**Thin 0.13 mm** and **Normal 0.35 mm**. Line Font maps visible edges to Normal,
and hidden edges, tangent edges, cosmetic threads, hatch, dimensions and
annotation leaders/frames to Thin. Thick through Thick(6), section cutting
lines and the border retain their existing settings; the border uses
Thick(2), 0.5 mm.

These are document properties persisted in each DRWDOT, not printer or
seat-global preferences and not runtime drawing overrides. The native API
`IModelDocExtension.SetUserPreferenceDouble` uses **metres** for the
`swPageSetupPrinter{Thin,Normal}LineWeight` preferences. The corresponding
line-font integer preferences select `swLineWeights_e` slots. To check the
exported PDF, read its stroke widths with PyMuPDF `page.get_drawings()` and
multiply by 25.4/72 to obtain millimetres. Inspect a representative part and
dense assembly at print size; section cutting lines may legitimately have
the same width as visible edges.

`third-angle-projection.SLDBLK` is the projection-symbol block embedded in both
templates and remains the editable source for future template work.

The layout audit reads the title-block keep-out from `DRAWING_TEMPLATES`. Its
measured `(left, top)` bounds are `(0.216, 0.066)` m for landscape and
`(0.0636, 0.066)` m for portrait. Re-measure and update the matching registry
entry if either block moves or grows.

### Title block

Left side: the general-tolerance block (**UNLESS OTHERWISE SPECIFIED**;
linear / angular / drilled-hole / surface rows, linked to the source model's
`TOL_*` properties from `cad/config/title_block.yaml`); the shared edge-break,
thread-class and inside-corner rows; FINISH; MATERIAL; the ASME Y14.5-2018
interpretation note; DO NOT SCALE DRAWING; and the third-angle projection
symbol. The inside-corner row is `INSIDE CORNERS` followed by
`$PRPSHEET:"TOL_INSIDE_CORNER"`; its full value (including `MAX UNLESS
OTHERWISE SPECIFIED`) comes from `inside_corner.display` in the config.
Right side: project title; PART name; DWG.
NO. (`Number`, the MHA-<subsystem>-## registry id (assembly 00; fabricated parts 01 onward; vendor parts MHA-<parent>-VN-50 onward)); REV (the release tag); scale; UNIT;
copyright + CC BY-SA mark. The source part supplies the linked `$PRPSHEET`
fields. `_part_properties.part_properties` stamps `Number`, `Revision`, `Title`, and
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

A purchased-part sheet whose registry number overruns the DWG. NO. cell into
REV opts in by passing `number_fit=NumberFit.SHRINK_TO_CELL` to
`build_purchased_fastener_drawing`; the four oblique-trammel vendor screws,
MHA-CH-06-TL-VN-65 to -68, do. Once the links resolve, the builder measures
the existing `$PRPSHEET:"Number"` note. Only if it ends less than 1.2 mm
before the REV divider does one proportional write lower that note's local
character height, aimed 0.3 mm inside that limit. The link, number, typeface
and template are unchanged, and `finalize_drawing` re-proves the fit after its
last rebuild. The fit refuses below 3 mm and on the unmeasured portrait
template. The landscape cell's rules are at x = 308.351 / 372.310 mm (REV
divider) and y = 19.969 / 35.906 mm; when editing this title block, remeasure
`_purchased_fastener_drawing._NUMBER_LIMIT` as well.

The fit scales and writes the note's native `ITextFormat.CharHeight`, whatever
its authority. The templates-1636 census read the template's 18 pt DWG. NO. as
`CharHeight` 0.0047625 m and its 15 pt title as 0.00396875 m. 8d9c8dbba
instead scaled `CharHeightInPts` times 0.0254/72 (6.35 mm) and wrote
0.00618 m, 1.30 times the note's native height; its readback ran down to
y = 13.41 mm, below the cell. `INote.GetExtent` is read off the window to the
pixel (0.48 mm on the fitted sheet), so every DWG. NO. readback is taken
zoomed onto the cell. Each readback records its extent, position, both height
authorities, the line and spacing format members and the rendered text rows as
a `drawing.purchased_number_fit.state` span event, and a failed fit quotes the
template and settled states.

The UNIT cell links `$PRP:"UnitOfMeasure"`, SolidWorks' drawing-document unit
property. SolidWorks updates it when the document unit system changes through
the status-bar unit picker: MMGS displays `mm`, and IPS displays `in`. The
pipeline configures dimensions in millimeters today. No custom UNIT property
is stamped.

### Native template maintenance

`cad/scripts/maintain_drawing_templates.py` edits copies of both embedded-format
templates through an **already-held farm COM seat**. Its
`maintain_templates(adapter)` entry point is suitable for an existing cached
COM leaf's `run_build` callback; never call `run_build` again inside that leaf.
The CLI is a seat-held entry point, not a newly admitted farm task. Do not
launch it locally, drain w15, or change the deployed worker to run it.

The `website`, `inside-corner` and `line-weights` operations are independent.
For example, `maintain_templates(adapter, operations=("website",))` changes
only the website from `harmonic-analyzer.vza.net` to `harmonicanalyzer.com`;
the CLI's repeatable `--operation` selects the same operations. This keeps
the website change separately reviewable from the line-weight change.

The script writes these files under `cad/out/templates` for the caller to
declare as cache outputs:

- `harmonic-analyzer-landscape.DRWDOT`
- `harmonic-analyzer-portrait.DRWDOT`
- `harmonic-analyzer-landscape.census.json`
- `harmonic-analyzer-portrait.census.json`

Each census records the original, edited and closed/reopened native document:
sheet properties, sheet-format segments and block transforms, every note's
linked/resolved text, position, extent, font settings/runs, and document
line-weight slots/mappings. Existing note anchors, formatting and sheet
geometry must remain unchanged. The inside-corner operation measures configured
property values temporarily and adds its linked row only in a native free gap
in the existing ruled tolerance cell; it refuses to move or shrink existing
content to make space. No temporary literal values are saved. Source-template
SHA-256 checks ensure the checked-in files were not mutated on the worker.

After successful persisted readback, deliberately install the returned binaries
into this directory, remove any temporary dispatch hook, and render portrait
and landscape samples from the installed templates on the farm. The bootstrap
leaf itself still renders from the checked-in templates, not from a runtime
override. Census success is not visual approval: obtain explicit owner
approval of both sample orientations before merging, and run the applicable
drawing/machinist gates.

### The "For Personal Use Only" watermark

Sheets rendered on a **SolidWorks Maker / Student** seat carry a non-removable
`SOLIDWORKS Maker Product. For Personal Use Only.` watermark — it is imposed by
the licence, not by this template, and there is no API to suppress it. It is
expected on every drawing produced on a Maker seat and is not a defect in the
standard. A commercial seat would render without it.
