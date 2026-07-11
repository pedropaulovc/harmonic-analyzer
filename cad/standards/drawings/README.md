# Harmonic-analyzer drawing standards

`asme-b-book.drwdot` and `asme-b-book.slddrt` are the project-owned SolidWorks
drawing template and sheet format used by every manufacturing drawing.

They are generated from the installed native SolidWorks ASME B landscape
template by `cad/scripts/create_drawing_standards.py`. The generator retains the
native B-size border and zone geometry, removes proprietary/confidential text,
company approval blocks, and unused table sections, then adds a compact
property-linked title block for a hobby-machinist book drawing.

SolidWorks names sheet-format files `.slddrt`; there is no native `.sldfmt`
format. Build-seat provisioning copies both files and registers their directory.

Regenerate only on a SolidWorks seat, then reopen and visually inspect a drawing
before committing changed binary assets.

## Title block

The compact title block carries, top to bottom: Title; a **DRAWN / CHECKED /
DATE** production-control row (DRAWN is `$PRPSHEET:"Drawn By"`; CHECKED and DATE
are blank fill-ins a machinist signs on the printed copy); DWG number, revision,
and revision description; material specification; finish and quantity; scale and
projection; and the sheet count. The linked fields resolve from the source
part's custom properties — `Drawn By` / `Revision Description` are stamped by
`_drawing_marks.apply_drawing_properties`, `Number` / `Revision` / `Title` by
`_common.part_properties`. (Consolidating those two stamping paths is tracked in
issue #249.)

## The "For Personal Use Only" watermark

Sheets rendered on a **SolidWorks Maker / Student** seat carry a non-removable
`SOLIDWORKS Maker Product. For Personal Use Only.` watermark — it is imposed by
the licence, not by this template, and there is no API to suppress it. It is
expected on every drawing produced on a Maker seat and is not a defect in the
standard. A commercial seat would render without it.

