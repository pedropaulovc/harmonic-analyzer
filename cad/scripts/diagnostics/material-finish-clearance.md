# Measured material and finish clearance experiment

Diagnostic candidate, not native acceptance or production adoption. This branch
preserves parent `77aa0f4f2881dcbe4f86d72a6aa36a23f52d6c68` and merges the
approved test-only correction `b60838991855066d652ef825b5be1cd68ea63835`.
The original material-only branch and its rejected native evidence stay intact.
No production template, builder, factory, source manifest or adapter is changed.

## Evidence and proposed change

The three-source material-center run rejected tube native containment and
material/finish clearance at both built and cold phases. Its retained report is
`C:/src/ha-template-material-centering/cad/out/reports/populated-template-zytj8xas/populated-template.json`,
SHA256 `e98ef04d856a38270db7973d6b8e73581751e40dc6ff822077be4054e097c31d`.
It preserves source inputs, complete linked text, fonts, cold native witnesses
and printed pixels. It is failed evidence, not an accepted layout.

`--layout material-finish` is a separate mode. It reads that exact receipt SHA
and requires the same three pinned foundation sources as the material modes.
Its planner derives regions and native/PDF boxes again from the retained raw
notes, frame segments and PDF observations, then computes:

- MATERIAL Y from the common native envelope midpoint and measured cell center;
- FINISH Y from the midpoint of the intersection of all three sources' native
  and PDF containment and neighboring-field clearance constraints.

Offline replay gives MATERIAL delta `-0.00009582397014626723 m`, FINISH feasible
delta interval `[0.00023675682610665993, 0.0006685480093676921] m`, and midpoint
delta `0.000452652417737176 m`. These values are outputs, not encoded nudges.
Every predicted field must remain in its measured region and at least 1 mm
from each neighboring field. An empty feasible interval fails without writes.

This calculation assumes the measured text envelopes translate with their
anchors. It is a testable prediction, not a native result. The next run must
measure all actual envelopes again; no tolerance is widened to fit the plan.

## Narrow native and receipt contracts

The only native writes are MATERIAL top-to-middle justification and the two
notes' Y positions. X/Z, complete text, property links, fonts, labels, frame
geometry, surface finishes and defaults remain exact. The owned visible drawing
and annotation owners are checked, with immediate justification and position
readback before any following write. Rejections retain partial-call evidence.
The default transition validator and old material-center mode stay unchanged.

Receipt-to-blank comparison permits only the already-existing exact edge-break
conversion from `_OLD_EDGE_BREAK_NOTE` to `_METRIC_EDGE_BREAK_NOTE` during normal
populated drawing setup. Name, owner type, font, anchor and all other metadata
remain equal. Blank authoring still preserves the original edge-break text.
This is not a general static-note exception.

The populated `--population material-finish` mode verifies both complete source
Material and Finish properties, all original native/PDF field checks, exact
cold/PNG equality, and the same protected source/token bytes. Tube's existing
diagnostic-only 1:10 view scale remains; production drawing layout is untouched.

The local SolidWorks bundle documents `INote.GetExtent` as requiring visibility,
`SetTextVerticalJustification` as void, middle alignment as enum value 1, and
`IAnnotation.SetPosition2` as returning a boolean with possible constrained
movement. Exact readbacks and final full-state comparison remain mandatory.
The existing `IModelDoc2.GetCustomInfoValue` call shape is reused for Finish;
the bundle marks that method obsolete, but no property-accessor migration is
included in this layout diagnostic.

## Native launch and acceptance

The parent owns the native seat and must review the new helper, planner,
validator extraction and those bundled API references before granting a run.
Use a visible, verified existing PID, the normal owned runner (never `--worker`
directly), remote cache off, and `HARMONIC_SW_AUTOSTART=0`. Preserve the exact
source paths, hashes and execution tokens in
[the parent protocol](material-template-centering.md#separately-observed-local-source-inputs).
Changed source bytes are a blocker, not permission to repin regenerated parts.

1. Run the owned `probe_baked_template_layout.py` entry point with
   `--layout material-finish --populated-receipt <report-above>
   --populated-sha256 <sha-above>`. Require blank save, new-document inheritance,
   full-state equality, unchanged static-label fit and print equality. This
   blank pass alone cannot accept resolved manufacturing text.
2. Feed its derived DRWDOT path and SHA to `probe_populated_template.py` with
   `--population material-finish`, the original foundation source root and
   actual installed symbol library. Require every native/PDF bound and 1 mm
   clearance, full Material/Finish text, cold/PNG equality and original inputs.
3. Compare raw material/finish fonts, links, complete text and all unrelated
   notes/frame geometry against the retained baseline and rejected candidate.
   Inspect all first/cold full sheets. Keep any failure; do not change fonts,
   frame geometry or thresholds inside this mode to obtain a pass.

Only diagnostic acceptance can result from this sequence. Production template
adoption still needs the eventual integrated production drawing/full-build,
manufacturing, cold, print and review gates.

## Offline controls

Tests exercise actual planners, receipt validation, observer and owned blank
lifecycle with synthetic geometry and simulated native objects. They include
wrong receipt/SHA/source, missing or forged raw evidence, infeasible interval,
foreign ownership, hidden documents, rejected/clamped/throwing setters, partial
calls, inherited-state drift, unrelated metadata changes and shortened Material
or Finish text. They do not constitute a SolidWorks run. Full native field replay
above uses retained observations read-only; it does not refresh those receipts.

Fail-first evidence includes the missing mode/helper, an early population guard
that initially ran after document creation, and the initially absent explicit
Finish property witness. Existing assertions were retained. New synthetic
fixtures needed exact list serialization and the existing PDF unit conversion;
neither correction changed native tolerances or acceptance requirements.
