# Lever dimension-leader crossings: retained native evidence

The `27f0c11e` lever-only pilot completed its recipe in **91.57848239998566 s**,
including GTol placement, whole-view packing and native/PDF/PNG output. It is
**not visually accepted**. Cold reopen separately rejected three linked-title
X-origin fields moving 2.585815265774727 mm.

Receipt: `cad/out/reports/datum-policy-i2i_oplt/pilot.json`, SHA-256
`bd281f36661a6d52001c6104806df241e31df834e3529c65eb59eeedd399e119`.
The source copy remained SHA-256
`6a994561f19487029c938cd7cca5047acbdfbf686020514be538ef5a632e0841`
through build, close and final cleanup. All four original/guard sources were
unchanged and the native session inventory returned from empty to empty.

## Exact line intersections

Both source annotations contain the captured three-line circular callout chain:
arrow-tail joins a diagonal leg, which joins the horizontal text shoulder. The
offending segment is `native.lines[0]`, not a guessed linear extension line.
The target frame is reconstructed only from its four exact closed upright native
edges. The production segment/rectangle clipper confirms the intersection;
the diagonal's bounding rectangle is not used as proof.

| Actual leader | Other annotation | Inside native frame | Inside measured text cell |
| --- | --- | ---: | ---: |
| `FulcrumDia`, Ø6.50 | `NoseRadius`, BASIC R4.75 | 11.730126 mm | 10.598751 mm |
| `RD5`, Ø4.04 THRU ALL | `DetailItem349`, datum C | 8.732148 mm | 4.757773 mm |

The frame crossings are direct stroke evidence. The text cells are conservative
font cells, not exact glyph outlines; the retained PNG independently shows both
leaders through the corresponding text/frame regions.

Repeat without SolidWorks:

```
uv run python cad/scripts/diagnostics/audit_dimension_leader_crossings.py
uv run python -m pytest cad/scripts/test_dimension_crossing_evidence_drawing.py
```

The committed JSON holds four exact archived rows, not a full-sheet certificate.
Diameter-symbol bounds absent from the generic archived diagnostic are NOT
invented; both target frames/text cells needed by this replay were measured.

## Coverage gap and bounded next control

`validate_gtol_leader_clearance` checks GTol leaders against other text and all
annotation strokes against GTol bodies. Neither target here is a GTol. The
view-packing helper deliberately separates decorated view envelopes; it does not
repair collisions inside one view. An exact own-annotation join may be excluded;
that is not permission to skip other dimensions or datums. A type-14 datum joined
to its owning dimension also needs an explicit exact owner witness, not a broad
dimension/datum exemption. Datum C here is attached to an edge, not RD5.

Next proposed native control: one `IModelDocExtension.AlignDimensions(0, .001)`
on the exact dimension bank of the retained front view, after native callout and
GTol placement, on unique owned drawing/part copies. The bundled method and
`Auto-arrange_Dimensions_Example_CSharp` document this per-view selected-dimension
operation. Native success does not promise obstacle clearance: reread every
actual dimension stroke and other annotation body, keep values/tolerances/BASIC,
semantic entities and GTol/datum state exact, and reject either retained crossing
or any new cross-annotation collision. No native drawing save or automatic second
candidate is authorized by this proposal.

`SpaceEvenly=1` and `Stagger=3` are documented independent alignment alternatives,
but untested here. This evidence neither claims AutoArrange cannot solve the
layout nor that a repeated call will solve it. No production gate is weakened.

The offline-tested candidate is now
`diagnostics/probe_dimension_arrangement.py --receipt <pilot.json>`. It requires
`HARMONIC_SW_AUTOSTART=0`, `HARMONIC_REMOTE_CACHE_MODE=off`, an explicit existing
`HARMONIC_DIAGNOSTIC_SW_PID`, and the coordinated native seat. Its first native
result follows below. Exact owned copies are linked while the drawing is closed; only that
owned drawing's reference bytes may change. Original artifacts and the copied
part are never saved. Helpers, imported adapter, every original input and both
copies have final hash witnesses even after operation or cleanup failure.

This control uses fresh symbol-aware measurements, rejects unsupported visible
annotations and half-hidden state 2, and records every dimension stroke against
every other dimension/datum/GTol/note/surface-finish body in its view. Exact own
annotation joins are excluded; unsupported dimension-attached datums fail before
mutation. These whole-body cells may include whitespace. A conservative cell
intersection is a gate failure, not necessarily glyph-ink intersection. The two
specific closed-frame crossings above have the stronger native-stroke proof.
Post-operation PDF output, if present, is diagnostic even when a gate fails;
there is no native-save, accepted-sheet claim or automatic second candidate.

## Native result: accepted call, no dimension movement

At frozen root `7ae01b6d`, adapter `e77bfda4`, PID 31860, the control reproduced
both known crossings and passed the archived drawing/source checks before the
single native call. `AlignDimensions(0, 0.001)` returned true in **0.0011768 s**
with ten exact front-view display dimensions selected. No dimension moved:
the recorded `moved_dimensions` is empty and fresh before/after measurements
are identical. This particular post-layout, per-view call is a no-op; it does
not establish a general limitation of AutoArrange or its other call contexts.

Receipt: `cad/out/reports/dimension-arrange-bb7lbqpw/dimension-arrange.json`,
SHA-256 `2af31fda94f0bccd9aa89384131e911376e8ae3de0a2722874595d4290d0fffc`.
The final conservative body check still reports seven front-view and one top-view
crossings, including both independently proven text/frame intersections. The
other reported body intersections are not all classified as glyph-ink defects.
The diagnostic therefore exited nonzero; no production arrangement change was
adopted. `SpaceEvenly`, `Stagger`, another call phase and a less crowded view
layout remain untested alternatives, not established fixes.

PDF-only `after.pdf` and its production preview `after.png` were retained next
to the receipt. Original-resolution visual inspection confirms that the R4.75
and datum C crossings remain. Export did not change native annotations or
measured geometry. All nine protected inputs, copied-source bytes, post-relink
drawing-copy bytes, helper/config fingerprints and imported adapter fingerprints
passed final guards. Initial/final native inventories were empty, with no cleanup
error. Only the isolated closed drawing copy's reference bytes were changed;
there was no native drawing/part save or rebuild.

After integration, the seven selected COM-free gates passed at `e5a970bc`:
`check:recipe` ran **3,655 tests in 53.86 s**; six other gates were current.
Telemetry: `cad/out/reports/pytest-telemetry/run-5ufhufmj`. This is not the full
native pipeline merge gate, and the lever remains visually unaccepted.

## Next bounded variant: native radial spacing

The same owned-copy diagnostic now accepts
`--arrangement radial_space_evenly`. It makes exactly one
`IModelDocExtension.AlignDimensions(1, 0.001)` call on the five front-view
radius/diameter annotations: `NoseRadius`, `TipRadius`, `FulcrumDia`, `RD4`,
`RD5`. The captured semantic `display_type` bank and a fresh native
`IDisplayDimension.Type2` read must agree exactly (5 = radius, 6 = diameter).
All ten front-view annotations retain their exact native identity/owner checks;
the five linear dimensions are not selected or permitted to move.

The local `AlignDimensions`, `swAlignDimensionType_e`, `IDisplayDimension.Type2`
and `swDimensionType_e` references provide the API contract. The bundled
Auto-arrange C# example establishes the selected drawing-dimension call shape.
The official [dimension-palette help](https://help.solidworks.com/2016/english/solidworks/sldworks/r_dim_palette_alignment_tools.htm)
describes linear/radial spacing inside the existing nearest/farthest placement
range; its Stagger operation targets linear dimensions. The current
[command reference](https://help.solidworks.com/2026/english/api/swcommands/SolidWorks.Interop.swcommands~SolidWorks.Interop.swcommands.swCommands_e.html)
also names the native Space Evenly/Radial tool. These contracts justify this
separate radial experiment, not a claim that it clears obstacles or fixes the
two retained leaders. No coordinate search, position setter, leader editor,
additional rebuild, automatic second variant or changed global preference is
introduced. Actual movement is read back, never inferred from a true return.

After source review and an exclusive seat grant, from the frozen candidate
checkout with its own venv and exact runtime inputs:

```powershell
$env:HARMONIC_SW_AUTOSTART='0'
$env:HARMONIC_REMOTE_CACHE_MODE='off'
# Set HARMONIC_DIAGNOSTIC_SW_PID to the confirmed existing native PID first.
uv run python cad/scripts/diagnostics/probe_dimension_arrangement.py --receipt C:/src/harmonic-analyzer/cad/out/reports/datum-policy-i2i_oplt/pilot.json --arrangement radial_space_evenly
```

The default `--arrangement auto_arrange` preserves the original ten-dimension
positive baseline/control. Each invocation operates on fresh exact owned copies,
not the output of another variant. Initial archived drawing/source comparison,
both known crossing repros, all dimension values/tolerances/BASIC, exact native
attachments, fixed-annotation content/geometry, post-export witnesses and final
hash/cleanup checks remain. Both variants retain the same all-view crossing gate:
independent linear/top-view intersections can still reject radial spacing, even
if its two intended leaders improve. The PDF remains diagnostic-only; there is
no native save or production recipe change. Offline selection/safety tests do
not prove native movement, saved persistence or a performance benefit. Native
execution of the radial variant is pending.

### Native radial result: accepted call, unchanged geometry

The frozen `e8cae04d` radial control selected exactly the five intended native
dimensions and returned true from `AlignDimensions(1, 0.001)` in **0.0025896 s**.
`moved_dimensions` is empty. All complete symbol-aware measurements before,
after and after PDF export are exactly equal, and all eight recorded crossings
remain (seven front-view, one top-view). The overall control therefore failed;
this is not a successful layout or a performance improvement.

Receipt: `cad/out/reports/dimension-arrange-ua1q54y6/dimension-arrange.json`,
SHA-256 `437eec9bee4390ba7ce0e6165166e8aed6b791789d439fc32d85b0d6600631bd`.
Its retained `after.pdf` and `after.png` show the unchanged diameter 6.50 leader
through BASIC R4.75 and diameter 4.04 leader through datum C. Independent visual
inspection confirms both defects. The other conservative body intersections
remain reported, not silently treated as exact glyph-ink defects.

Original input, post-relink owned-copy, helper/config and imported-adapter hash
banks all match their final observations. Source semantic/native identity checks
and post-export witnesses passed. Ownership began/ended empty and cleanup error
is null. The native control held the seat for 94.65 s, mostly capture/validation;
the 2.6 ms selected API call itself does not measure a full-recipe improvement.

This result is limited to one radial bank on the already-packed retained sheet.
It does not establish that native dimension arrangement is generally inert.
The next meaningful change is less crowded view ownership and an earlier
dimension-layout phase, not repeated calls against this unchanged scene.

## Five-view recipe candidate (native acceptance pending)

The next isolated recipe candidate splits the ten front-view dimensions into
two five-dimension banks at the existing 1:2 scale. It creates one additional
standard `*Front` view with the already-used `CreateDrawViewFromModelView3`
path; no crop sketch, detail-circle picker or coordinate-search loop is added.

| view | retained manufacturing content |
| --- | --- |
| profile Front | BASIC R4.75, R3, 169, 182.8 and 9.5; outer-profile GTol |
| hole-pattern Front | diameter 6.50, both native hole callouts, BASIC 127/177.8; datum B; bore perpendicularity and both hole-position GTols |
| Top | thickness 3.0; datum C on the same exact top-front model edge |
| Right | datum A on the same exact broad-face entity; opposite-face parallelism |
| isometric | unchanged 1:4 view and property-linked caption |

The source part, four source BASIC designations, all reference-dimension values,
all three datum identities and all five GTol contents/attachments remain the
contract. View ownership changes deliberately: diameter and profile-radius
leaders no longer share one Front, and the Top thickness dimension no longer
shares its view with datum A. The original manufacturing/property-linked notes
remain. This does not yet prove native datum placement in the changed views,
printed clarity, or five-view sheet fit.

The recipe requests **one** native AutoArrange pass after all dimensions and
hole callouts, before datums/GTols, with `spacing_m=0.003`. The documented
`AlignDimensions` spacing parameter specifies metres between dimensions. The
previous 1 mm request left 6 mm text-anchor steps with measured BASIC bodies
intersecting adjacent extension lines. A larger native request is a hypothesis,
not a promise of exact pitch or obstacle avoidance. No annotation position retry
or leader-routing algorithm is introduced.

The original all-view dimension-stroke/foreign-body checker is now shared with
the retained diagnostic. The lever alone opts into it through an additional
final validation callback. The mandatory GTol gate runs unconditionally first;
both consume the **same fresh final packing measurements**, with no additional
COM scan. Dimensions, datums, GTols, notes and surface-finish bodies retain the
original crossing rules, including touching and native leader decorations.
Center marks retain the original geometry-adornment exclusion; no new datum or
dimension exception is added. Any crossing prevents production export.

Run this candidate only through the existing owned
`diagnostics/probe_datum_policy_recipes.py --target channel_lever --candidate <revision>`
control after an explicit seat grant, with the exact current source and protected
guard roots. The runtime must contain the matching shared-helper changes.
Acceptance requires the full source/attachment/dimension/BASIC witnesses,
successful native construction, the strict final crossing gate, saved/cold
reopen checks and an eye pass over the changed PNG. Do not infer native movement
from AutoArrange's return value or call the redesign faster before measuring
the complete recipe. Five-view construction and measured fit may cost more;
this candidate targets the concrete remaining readability defect.

### First integrated native runs

The five-view recipe was tested with the prepared factory, so these runs check
that combination, not an isolated layout-speed comparison. Both used the exact
registered lever source and guard, adapter `e77bfda4`, existing PID 31860,
autostart disabled and remote cache off.

At `44185bd7`, the run stopped during the document-wide datum leader policy:
sheet-format surface-finish annotation `DetailItem325` failed its fixed-native-ink
comparison. The original diagnostic retained its name but not the differing
fields. Receipt `datum-policy-s8cl936z/pilot.json`, SHA-256
`5f80856e29634fd6d6bdddaa1e83b752561e51c65772965642761157d4dc2f8c`.
This is an unresolved preservation failure, not proof that printed ink moved.

Commit `f0fb2a43` added failure-only native identity, visibility and complete
before/after snapshot logging without changing the comparison. A fresh repeat
passed that check and reached final packing/GTol validation, then failed the
dimension gate on two remaining pairs:

- Profile: `BarLength` stroke 6 crosses the `TipCentreX` BASIC 182.80 body.
- Hole pattern: `RD1` stroke 6 crosses the `RD2` BASIC 177.80 body.

Right, Top and isometric had no reported dimension/body crossing. Six of the
old eight pairs are absent, including the two known diameter/radius and datum-C
defects, but export was correctly stopped before a new PNG existed. Native
stroke/box evidence does not substitute for inspecting the redesigned print.
The full failed final snapshot and diagnostic-only rendered evidence should be
retained before owned cleanup in the next control.

Repeat receipt `datum-policy-jgxaythz/pilot.json`, SHA-256
`93009bd209655fb61fd3e7a7127a1bd573b2e2322a2b95bd7a954386e1643684`.
Its recipe took 99.123294 s before failure; pilot time was 132.711814 s. The
earlier fixed-template mismatch did not recur, but no implementation fix was
made and it remains unresolved. Neither run is accepted or a speedup.

Both runs preserved original/guard hashes and exact source-copy bytes, passed
final template/cache/helper/adapter guards, and returned to the initially empty
document table without cleanup errors. The full offline recipe gate exposed one
older assertion requiring arrangement after datums; this contradicted the
approved earlier arrangement. After raising that conflict, `f0933f94` retained
all semantic/forbidden-selector assertions and pinned the lever's one pass
between dimension creation and datum/GTol creation. Seven COM-free gates passed
at `f0fb2a43`, including 3,784 recipe tests in 72.35 s. This is not the full
drawing-inclusive native merge gate.
## Five-view failure print retained

At root `89412bcc`, adapter `e77bfda4`, PID 31860, the next prepared lever run
again passed the unchanged template-ink check and stopped on the same two final
crossings. Failure-only capture retained a PDF and PNG before owned cleanup.
Both were inspected: the shorter horizontal dimension line touches/crosses the
lower, longer BASIC dimension's box for 169/182.80 and 127/177.80. These are not
the earlier hole/radius leader conflicts. No crossing was exempted.

The full semantic capture failed before and after export because the saved-owner
dimension checker rejected the unsaved native identity
`RD1@Drawing View1@Draw52.Drawing`. Consequently complete native ink/attachment
preservation was **not** proved by this run. The PDF/PNG still exist; the original
crossing exception remains the primary failed outcome. Independent raw-annotation
capture is the next diagnostic correction, not a semantic-check waiver.

The drawing stayed unsaved, dirty and visible across the PDF-only export. No
native drawing file was created; original/copy hashes were unchanged. Original
template, prepared cache, runtime helper/adapter guards passed. Owned cleanup
returned the empty initial document inventory without error. The failed image's
SCALE 1:1 text precedes `finalize_drawing`, which re-pins and checks sheet scale;
it is not evidence that a finalized lever drawing would retain that scale.

Receipts under `cad/out/reports/datum-policy-duc4i6q5/`:

- `pilot.json`: `31b0c77d80d68d164148672cc78bd7072931379fdc00963eef278a865fcc9e4e`.
- `channel_lever/failure-evidence.json`: `2dabcbd286f80cfc7ddf05f83e8a28df4f2c795e758e213359e80cf0118200c7`.
- `channel_lever/failure.pdf`: `82dca5698477aa76b2419f6e4fc53fdd5de5491eddac0ef25d4e69485e39d039`.
- `channel_lever/failure.png`: `334034f8ee058a5e83c01768f1249924de296dc86e4ecdbc476aebfdb492ba76`.

The recipe ran 99.840350 s; the pilot including failure capture ran 143.337249 s.
Offline gates ran concurrently, so these are not comparative performance data.
All seven offline gates passed at this code checkpoint, including 3,890 recipe
tests in 74.42 s (`pytest-telemetry/run-svaajh5a`). This is not the full native
pipeline or final drawing acceptance.

### Independent raw capture verified

At frozen root `fe78272f`, adapter `e77bfda4`, PID 31860, the unchanged lever
recipe again failed on the same two BASIC-box crossings. The corrected capture
retained the complete raw annotation rows before and after PDF export. Exact
native handles, raw rows, source dimensions, drawing/source state, sheet
properties and file hashes were unchanged. The semantic checker still rejected
the unsaved `RD1@Drawing View1@Draw57.Drawing` owner in both phases; the report
therefore explicitly remains `partial`, not complete attachment acceptance.

Receipt `datum-policy-uxnsbzpi/pilot.json` has SHA-256
`55f1c0abc48a1b4c876f54132b1a1b92f5587515d234006bfcebe51f968656dc`.
The retained `channel_lever/failure-evidence.json` has SHA-256
`30d74449027b9425e55e937d745fd2ff7d4b711c80e536d9cc9c0906899f1828`.
Its PNG hash is identical to the preceding failed print
(`334034f8ee058a5e83c01768f1249924de296dc86e4ecdbc476aebfdb492ba76`).
Original and copied sources, template/cache/runtime guards and empty-to-empty
owned cleanup passed. The native sheet scale was 1:1 before finalization,
unchanged by export. Recipe time was 86.066959 s; the 171.240112 s pilot also
includes preparation and failure evidence, but excludes outer cleanup and seat
attachment. This is a functional capture result, not an A/B performance claim.

### Named parallel spacing reached the native operation

At root `3db3efe2` / adapter `e77bfda4` / PID 31860, the nominal-precision
correction let both exact named pairs reach `AlignParallelDimensions`. The
profile call took 10.5405 ms and the hole-pattern call took 10.3532 ms. The
drawing-local spacing preference retained the measured request of 6.5798667 mm.
Native TipCentreX moved down 0.5798667 mm and RD2 moved up 2.7100667 mm; all
source values/handles, annotation semantics/attachments, unselected ink and view
layout passed the exact before/after checks. These are operation timings, not
the much longer diagnostic capture or a complete recipe speedup.

The trial then failed before the unchanged layout gates: the diagnostic wrapper
forwarded `views` positionally to a keyword-only function. Its permissive mock
had hidden that integration bug. The fixture now uses the actual unwrapped
production function signature, reproducing two failures before the callback
correction; afterward all 111 linear-control/owned-pilot tests passed. Notes,
views and the mandatory validation callback are forwarded as keywords. This
does not establish final crossing clearance or cold drawing acceptance.

Receipt `datum-policy-k5mypm3x/pilot.json` has SHA-256
`c678cdf0b4f3b9f8b56524e0a540731ad78b533f859e8a5296919a409a0b98c0`.
Failure capture remains explicitly partial because the unsaved drawing-reference
owner is rejected; no native drawing or source save was substituted.
