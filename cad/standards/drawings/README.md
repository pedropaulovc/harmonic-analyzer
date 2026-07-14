# Harmonic-analyzer drawing standards

`harmonic-analyzer.DRWDOT` is the project-owned SolidWorks drawing template
used by every manufacturing drawing. It was **created manually in SolidWorks**
(not generated — the old `create_drawing_standards.py` generator and the
`asme-b-book.*` assets it produced are gone): an ASME B landscape sheet with
the border/zone geometry, title block, tolerance block and third-angle
projection symbol drawn directly in the template. The sheet format is embedded
in the template, so there is no separate `.slddrt`; per-drawing setup only
sets the sheet scale (`_drawing_common.new_project_drawing`) and links the
sheet's custom-property view to the first drawing view
(`_drawing_common.finalize_drawing`).

`third-angle-projection.SLDBLK` is the projection-symbol block the title block
embeds, kept alongside as the editable source for future template work.

Edit the template only in SolidWorks, then reopen and visually inspect a
rendered drawing before committing the changed binary. The layout audit's
title-block keep-out box (`_drawing_common._TITLE_BLOCK_LEFT_M` /
`_TITLE_BLOCK_TOP_M`) MUST track the block's extents — re-measure via a
sheet-view annotation dump if the block moves or grows.

## Title block

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

The title block declares **UNIT: IN**; the generated drawing views still
dimension in mm until the inch migration (issue #290) lands.

## The "For Personal Use Only" watermark

Sheets rendered on a **SolidWorks Maker / Student** seat carry a non-removable
`SOLIDWORKS Maker Product. For Personal Use Only.` watermark — it is imposed by
the licence, not by this template, and there is no API to suppress it. It is
expected on every drawing produced on a Maker seat and is not a defect in the
standard. A commercial seat would render without it.
