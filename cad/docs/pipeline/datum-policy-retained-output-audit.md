# Rocker retained-output audit — 2026-09-06

This is failed-pilot evidence, not release acceptance. Frozen recipe candidate
`0bb29b0c18ddcc770d6097ea003503e9fd4a81a7`, native trace
`0x736ce0864a06c21e91e88b0eae59961a`, session 31573 exited 1. Rocker recipe
completed in 92.212 s; total control 168.542 s. Lever was not attempted.

Raw receipt (unchanged):
`C:/src/ha-perf-datum-functional/cad/out/reports/datum-policy-79q2phjn/pilot.json`.
SHA-256 `a924f8259c3f3fc5049a19b2b6715cbaffeb863f003f075e61438fd0ae483feb`.
The [complete exact delta list](evidence/datum-policy-79q2phjn-delta.json)
is reproducible without COM:

```powershell
uv run --no-project --python C:/src/harmonic-analyzer/.venv/Scripts/python.exe python cad/scripts/diagnostics/audit_drawing_snapshot_delta.py --receipt cad/out/reports/datum-policy-79q2phjn/pilot.json --output cad/out/reports/datum-policy-79q2phjn/new-delta.json
```

## Cold-reopen comparison

190 changed leaves, all numeric; no changed strings, enums, booleans, types,
dictionary keys or array lengths. 46 belong to the comparator's generic-display
or annotation-position fields; native/measurement fields repeat those facts.
All captured annotation semantic dictionaries, GTol XML, model/configuration,
attachment geometry, dimension values/tolerance types and view layout agree.
That is not a native-handle identity comparison across close/reopen.

| Annotation | Changed leaves | Maximum absolute delta (m) |
| --- | ---: | ---: |
| View1 / DetailItem343 (marker) | 3 | 1.3877787807814457e-17 |
| View1 / DetailItem346 (marker) | 3 | 1.3877787807814457e-17 |
| View1 / DetailItem349 (datum A) | 103 | 5.551115123125783e-17 |
| View1 / DetailItem350 (SF) | 11 | 2.7755575615628914e-17 |
| View1 / DetailItem352 (datum C) | 58 | 1.942890293094024e-16 |
| View2 / DetailItem351 (datum B) | 9 | 1.3877787807814457e-17 |
| Sheet1 / DetailItem245 (title) | 3 | **0.0072252098470926285** |

The title's `generic.texts[0].position[0]` changes from
0.35389179984999647 to 0.3611170096970891 m. Native and measurement text runs
repeat that same 7.225209847 mm shift. Text `rocker-arm`, Century Gothic font,
height, angle, reference point, anchor, native note extent and measured body are
exactly equal. The native extent remains
(0.36106367681498824, 0.04025453864168621,
0.3977717330210772, 0.047262440281030466) m. At this checkpoint the printed effect
was unproven; the later no-setter export below confirms actual printed movement.
The strict witness remained failed. The other 187 numeric differences are at most
1.942890293094024e-16 m; a future finite-coordinate-only representation tolerance
would need an explicit field contract and negative displacement tests. No such
tolerance or gate change is part of this evidence commit.

### Dedicated cold-reopen coordinate comparison

The functional pilot now uses `_reopen_annotation_comparison.py` only at its
cold-reopen boundary. Explicit coordinate leaves receive the smaller of 16 ULP
at their observed magnitude and 1e-14 m; both operands must be finite floats.
The measured 187 differences are at most eight ULP. The chosen budget gives a
small representation margin without becoming a geometric clearance tolerance.
It is not a guarantee that every future native coordinate delta fits this bound.

Mapped fields are annotation/text anchors, line endpoints, and known native or
measured rectangle coordinates. For the mixed native line arrays, only slots
4-9 are positions; color/type/style/weight remain exact. Arc arrays and text
planes remain exact until their schema is explicitly mapped. Container types,
keys, lengths and ordering, text, XML, fonts, sizes, angles, widths, enums,
visibility and measurement-support exclusions are all still compared exactly.
The full native and measured annotation rows are checked, not only the generic
display subset. Every classified coordinate delta retains its original values.

The committed 190-leaf fixture exercises the distinction: 187 coordinate deltas
are classified as roundoff; all three 7.225 mm title-origin deltas remain errors.
The exact leaf audit, same-session annotation/handle comparison, retained-export
before/after witness, source-dimension gates and template `compare_exact` are
unchanged. One-ULP attachment-signature mutations still fail the existing exact
archive test. Two ownership-test mocks target the new cold-only call site; their
preservation/failure assertions are unchanged.

This removes a demonstrated false cold-reopen failure, not the title bug or a
missing attachment-identity proof. Cold comparisons currently check attachment
signatures; equal-signature reattachment requires a separate persistent-reference
witness. A successful fresh corrected drawing remains necessary for acceptance.

## Confirmed visual collision

The retained PDF/PNG is not a whole-sheet visual pass. RD3 (`8.46`, BASIC) has a
vertical native line at x=0.20824696752879507 m from y=0.16886630953174836 to
0.17966130952459589. GTol DetailItem353's first closed frame cell is
x=[0.20583496752879504, 0.21283496752879505],
y=[0.17688934158156538, 0.1838893415815654]. The dimension line penetrates the
first cell by **2.771967943 mm**; its horizontal extension at
y=0.17966130952459589 ends at x=0.20924696752879507, also inside that cell.
These are actual native line/frame coordinates, not conservative font bounds.
The `133.07` BASIC dimension remains below the part.

At the tested `0bb29b0c`, `_drawing_leader_clearance.validate_gtol_leader_clearance` constructs
leader banks only for kind-5 GTols, then checks those leaders against other text
cells. The reverse dimension-leader-to-GTol-frame/symbol collision is not checked.
GTol placement uses dimension **bodies**, which intentionally exclude extension
lines. Therefore existing body and one-direction leader checks can pass this
real collision. A future repair needs symmetric dimension-stroke/frame checking
and a native-placement candidate; skipping the first symbol cell is not a fix.

### Correction under test

The revised planner includes already-measured open strokes and decorations from
the existing datum/dimension/surface-finish obstacle inventory, in addition to
their bodies. Moving GTol candidates also check whole neighbouring GTol bodies,
not just font cells, so blank symbol/frame areas are not holes in the witness.
The fresh final checker tests all captured displayed strokes and native leader
routes against every other GTol body; it exempts only the exact annotation's own
join. This covers dimensions, other GTols, centermarks and centerlines without
new COM calls or full annotation reads. The original implementation accepts the
captured RD3/frame fixture; the revised one rejects it. Native re-layout and
visual validation of the revised policy remain pending.

Planning uses conservative axis-aligned stroke envelopes to retain the bounded
existing candidate search. A diagonal envelope can block a genuinely clear
position, producing longer leaders or a false no-fit. It is not an exact
segment-aware placement solver, and its fleet rejection rate is not established.
Zero-width native strokes get only an adjacent-representable-float enclosure;
no physical line width is invented. The production 2 mm clearance supplies the
gap. At a zero requested gap, the candidate's numerical tolerance can permit
touching that the closed-segment final check rejects; zero-gap placement is not
validated by this correction. The final checker still fails closed. Centerline
and cosmetic-thread geometry is checked in the complete final inventory but
has not been added to the narrower candidate inventory, avoiding new COM scans;
a collision involving it can therefore fail instead of being automatically moved.

## Safety and remaining proof

All four original/root-guard source hashes and the owned rocker source-copy hash
remain exact. The copied source's three named parameters retain values/tolerance
types and native identities across the recipe; the final cold-reopened source
parameter stage was **not reached**. The drawing cold-reopen had eight supported
geometry witnesses, four dimension values/tolerance types, zero excluded
dimensions and three exact owned-copy/Default view references. Production native,
PDF and PNG exports completed, but the combined diagnostic did not pass.
Cleanup preserved the original clean lever part and dirty unsaved Draw2; no
diagnostic documents remained open. No retry, hash reset or source save occurred.

Next bounded control: open a unique bytecopy of this retained SLDDRW with its
exact saved part reference protected; perform no layout/default/annotation writes
and no native drawing save. Capture title alignment/linked-text/native extent/raw
text positions before and after one production PDF export, render to a unique
PNG, and compare with the retained original PDF/PNG offline. This separates
printed output from cached observations without rebuilding the recipe. It needs
source review and a new explicit COM-seat grant.

## No-setter export result — printed motion confirmed

The follow-up control at `f07bf85556531c5857e1275264ee028b5ab50440` completed
successfully: session 36917, trace `0x223ed7481f353050e82d4c29be052356`,
76.516872 s. The single production PDF-only export took 2.201 s and PNG rendering
0.271 s. No native drawing/source save, rebuild, relink, layout/default or
annotation setter was used. Receipt:
`C:/src/ha-perf-datum-functional/cad/out/reports/retained-export-ca311q5b/retained-export.json`,
SHA-256 `4d990d172460fd2ef85507daea2996cbb8f8931ed9a84eebb4f7e2bcd31c7d02`.

**The earlier title difference changes the printed layout.** PDFium measured all
ten title characters about 20.480957 points (7.225226508 mm) farther right in the
newly reopened export. Text and Y coordinates are unchanged. The native
7.225209847 mm text-origin change agrees with that printed displacement to the
precision of the PDF glyph boxes. The title's left/right glyph ink bounds move
from [1004.138671875, 1105.9906005859375] points to
[1024.61962890625, 1126.4715576171875] points.

The PNG comparison finds 11,232 changed pixels, all inside the title region
[4183, 2749, 4694, 2813] on the 5100-by-3300 image. Everything outside that region
is pixel-identical. The reopened title remains readable. The existing RD3/GTol
collision is unchanged, so this is still **not** whole-sheet visual acceptance.
Generated PDF SHA-256:
`856498e96ca1bb3a95b4199787ded1a693b3b8de0e3aeda91290cd30cb8c2133`;
PNG: `37c1d7f647a7608cf015d93b43fa9d747d354c817662398daf905f34ec56137d`.

Before versus after this one export, the full fresh native snapshot has zero
changed leaves, and the title's ordinary getters are exact. The cold reopen had
already established the changed text origin. `INote.GetTextJustification` is 2
(center); vertical justification is 0 (top), and `PropertyLinkedText` is
`$PRPSHEET:"SW-Title(Title)"`. Extent, anchor and text remain as previously recorded.
This result rejects the hypothesis that only a harmless observation changed;
it does **not** yet establish which cheaper native update boundary can stabilize
linked-note layout before the original recipe export.

All nine protected file hashes and the drawing-copy hash remain exact. The three
source parameters now also match the retained source snapshot on cold reopen and
retain exact native identities/values/tolerance types through export. All fresh
attachment, dimension, annotation-handle and view-layout gates pass. Cleanup
preserved the clean visible lever part and dirty visible unsaved Draw2, with no
cleanup error. No second native invocation followed this completed control.
