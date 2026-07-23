---
name: datum-position-session-drift
description: "Datum-tag GetPosition is exact within one SolidWorks session but moved 24.883 um across one restart; automation persistence tolerance is 1 mm with structured telemetry. Reoccurrence requires deeper analysis, not another tolerance increase."
metadata:
  type: project
---

# Datum-tag position readback: bounded session drift

Investigation on 2026-07-23 isolated the drawing failure to
`cad/scripts/diagnostics/repro_datum_tag_position.py`. The repro uses one
existing part, one checked-in part drawing template, one explicitly scaled
front view, one selected bore rim, and one datum B tag. It imports no
dimensions, notes, balloons, tables, title block, extra views, or production
drawing helpers.

## Evidence

- In one SolidWorks session, 20 identical isolated invocations succeeded 20/20.
  Every invocation begins with `CloseAllDocuments`; all 20 returned exactly one
  unique `(x, y)` readback with 0.000 um spread. Runtime averaged 5.67 s and
  peaked at 6.16 s.
- Across one manual SolidWorks restart, the same call moved from
  `(0.08622953403137881, 0.10799698920959891)` m to
  `(0.08623897858347049, 0.10802001030538469)` m: 24.883135 um.
- One identical post-restart invocation failed to select the bore rim through
  sheet-coordinate `SelectByID2`; the next invocation succeeded. A subsequent
  20-run series reproduced zero selection failures. This is an observation,
  not a measured failure rate.
- The original before/after PNGs were not comparable: drawing `SaveAs3(.png)`
  rasterized the current graphics viewport (765x598 before, 1677x878 after).
  Both PDFs were consistently ASME B, 1224x792 pt (17x11 in). Fixed 144-DPI PDF
  rasters were both 2448x1584; their difference was confined to a 42x42-pixel
  region around datum B. Use PDF rasters, not direct PNGs, for this repro.

## Decision

Datum-tag position persistence is an automation sanity check, not a drawing or
manufacturing tolerance. `add_datum_feature` therefore uses a 1 mm readback
tolerance, and drawing call sites must not restore submillimetre gates. Larger
existing allowances for attachment-constrained tags remain unchanged.

Every datum placement emits structured selection-request and position-readback
OTel events plus correlated logs. They record datum and drawing label; selection
mode, entity type, and sheet pick; requested, normalized-expected, and actual
sheet coordinates; position error and tolerance in millimetres; and whether a
normalized expectation was used. This reuses the gate's existing
`GetPosition()` result and adds no COM call. Search
`cad/out/reports/telemetry/logs.jsonl` and
`cad/out/reports/telemetry/traces.jsonl` for
`drawing.datum_selection_request`, `drawing.datum_position_readback`, or the
`drawing_label`.

Live validation after implementation rebuilt `drawing:pinion_cam` successfully.
The console and both JSONL files recorded selection and readback entries for all
four datums. B and D each read back at their normalized expectation with 0 mm
error against the 1 mm automation limit; C retained its pre-existing 19 mm
attachment-constrained allowance and logged a 17.857088 mm error.

## Escalation rule

If datum-position drift or intermittent datum entity selection reproduces
again, stop. Do not widen the 1 mm gate or add another drawing-specific expected
coordinate. Perform a deeper multi-session analysis that separates selection
from placement and captures, at minimum: SolidWorks PID/session boundary,
template hash, sheet properties, view name/scale/outline, selected entity
identity and topology, requested/expected/actual coordinates, and datum line
and triangle primitives before rebuild, after rebuild, and after save/reopen.
The current data proves same-session determinism and one restart delta; it does
not establish a restart-drift distribution or an edge-selection failure rate.
