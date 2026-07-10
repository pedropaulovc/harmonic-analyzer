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

