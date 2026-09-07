# Cone-gear-shaft native FACE finish placement

The two native FACE finishes passed the owned identity/cold control at
`bd7e3384`, but its printed sheet has two FCF-leader/text crossings. The next
candidate changes only those two existing FCF origins; its native routing is
unvalidated. The successful finish placements, selected faces, source pin,
part-owned controls, five diameter placements and manufacturing values stay
unchanged. The historical finish-placement failure and positive control below
remain evidence of their respective call shapes.

## Retained failure

The owned three-target pilot at root
`f6370560303f9025f6cd48ab9230edc0fd0410dd` passed the tip adjuster and pivot screw
through cold reopen, then failed on the cone gear shaft's first surface finish:

```text
pivot journal finish: explicit annotation attachment mismatch:
count=0, entities=0, types=(), expected=2
```

Receipt `cad/out/reports/datum-policy-e0vlt1wm/pilot.json` has SHA-256
`66a97d1528ee5eefc6ac85ee24f2e9115946b32f843c55100eefb29519ed27b5`.
The cone recipe ran for 19.8580040 seconds; the complete three-target diagnostic
ran for 651.7559998 seconds. Neither duration is a performance comparison.

The observer recorded one exact selected FACE (type 2) for the failed finish.
Its native argument/selection identity check passed. Earlier in the same recipe,
datum A attached to the same journal face with count 1/type 2. The finish failed
after insertion, text/style setters, explicit leader/position setters and rebuild.
There is no intermediate attachment bank to attribute loss to one setter.
The tip finish was not reached.

Failure capture completed with no secondary errors. Its PNG visibly has a Ra 1.6
symbol and leader aimed at the journal, despite the native attachment being
empty. That appearance does not satisfy the identity requirement. The failed
drawing had not reached finalization, so its title scale and missing later
annotations are not evidence of an accepted final sheet.

- Failure PDF: `cone_gear_shaft/failure.pdf`, SHA-256
  `57c2541cdbd0fedeb5fc51c2d3c7c930e0fa535b13d786f2b1b2a2e16d65851e`.
- Failure PNG: `cone_gear_shaft/failure.png`, SHA-256
  `a246721fbd9182f47106eaf2166894ce038fdcf8a5507a9344abfe18a127ff78`.
- Owned source remained
  `8df108cb4053bd47bcc1acc8b83fede6e3a52a9d3c4f6341c1ab3702d512b0ab`.
  All five protected sources, template/cache and runtime fingerprints passed
  final guards. Ownership preserved the visible, clean original tip part and
  reported no cleanup error. Ownership receipt SHA-256:
  `f5c57baa5383ec38faa10368a6dcdb3057c43bb55ea3f77b38e72990866ad7d5`.

## Call-shape change and positive control

Both calls keep `entity=pivot_face` or `entity=tip_face`, `entity_type="FACE"`,
their original labels and the same `surface_finish_by_key` rows. Removing
`symbol_xy` and `leader_attach_xy` selects the shared helper's existing native
placement path:

| Operation | Retained failure | Candidate |
| --- | --- | --- |
| `InsertSurfaceFinishSymbol3` leader/location | `swBENT`, requested XY | `swNO_LEADER`, ignored zero XYZ |
| `SetLeader3`, `SetPosition2`, leader endpoint setter | Called | Not called |
| Face/control validation, text/style, rebuild | Retained | Retained |
| Post-insertion exact attachment identity | Required | Required |

The documented `InsertSurfaceFinishSymbol3` uses the last selection and ignores
its location arguments with `swNO_LEADER`. `SetPosition2` describes direct FACE
surface-finish placement and its restriction to the face. The API documentation
supports this call shape; it does not promise this shaft's resulting layout.
The bundled annotations-array example demonstrates insertion, but its part/
sketch straight-leader shape is not the drawing FACE positive control.

The existing spring-hook and crankshaft FACE recipes use this same no-leader
path. Crankshaft's full owned pilot at `5e773756` passed insertion, built and
fresh cold FACE attachment/type/owner/geometry checks:
`cad/out/reports/datum-policy-_ombplu9/pilot.json`, SHA-256
`f9dd490db1d4d3527670243379d2a0cec8d56ed308e79b3071549947f2f39319`.
See [its complete scope](cold-intersection-edge-identity.md). This establishes
a working FACE call shape, not that bent leaders are generally unsupported.

Primary API pages read in the bundled reference:
[InsertSurfaceFinishSymbol3](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~InsertSurfaceFinishSymbol3.html),
[SetPosition2](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotation~SetPosition2.html),
[SetLeader3](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotation~SetLeader3.html),
[SetLeaderAttachmentPointAtIndex](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotation~SetLeaderAttachmentPointAtIndex.html),
[GetAttachedEntities3](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotation~GetAttachedEntities3.html).

## Original finish-candidate tests and native invocation

Two new actual-call tests failed first against the old recipe because it passed
both coordinate arguments (`pytest-telemetry/run-sm4lyetr`). The existing datum
test's literal finish-position assertion was deliberately retired after the
user-facing contract change was disclosed. Its derived journal-boundary and
manufacturing assertions remain unchanged. Recipe tests now require both exact
FACE/control calls with no position arguments; fresh built/cold fixtures retain
wrong-face, wrong-view, hidden and off-sheet rejection. Shared native helper
tests still reject absent/different/unknown attachments without a fallback.

Focused and adjacent verification passed 368 tests in 32.57 seconds, including
the existing graph and part-isolation tests (`pytest-telemetry/run-3zir1lmy`).
Ruff F and `git diff --check` passed. These are offline results, not the full
build or a native placement proof.

Run the existing owned pilot from a frozen candidate checkout, with the confirmed
current PID and exclusive seat coordination:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '<confirmed-current-PID>'
uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
  --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --guard-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --candidate HEAD --factory prepared --target cone_gear_shaft
```

Use the same invocation for the two-FCF candidate. Required evidence remains
both exact finish attachments through built/cold reopen, unchanged source/
dimension/PMI banks, and a readable freshly exported PNG with measured native
leader/text clearance. No acceptance predicate or source pin changes. The
original offline preparation did not itself establish native acceptance.

## Review follow-up: preserve production identity guards

Review of `78e7082b` found that its native call shape took an existing helper
branch which checked selected/attached identity but skipped the positioned
branch's original-argument, owning-view, attachment-type and native-count checks.
The owned observer still checked these; ordinary production did not. A pure
real-helper regression accepted a correctly attached FACE with the wrong view
owner in native mode, while positioned mode rejected it. The first regression
run retained 15 failures and 11 passing controls (`pytest-telemetry/run-nehpfd7d`).

Native explicit FACE finishes now also use that same existing explicit validator,
including source reverse mapping for MODEL-origin faces. The native position and
selected-attachment validator still runs, and no placement setters are added.
Native EDGE/SILHOUETTE paths and positioned paths are unchanged. Tests retain
the wrong-owner repro, equal-geometry/wrong-identity cases, exact type/count
refusals and source-mapping controls. This repairs a production guard regression;
it does not establish native placement, cold persistence or printed acceptance.

## Shaft native identity/cold PASS; visual FAIL

The prepared-factory pilot at
`bd7e33843eb65d1d22afa4fa8e413b1b78cd59cd` completed with `status=passed`:
`cad/out/reports/datum-policy-y25nr2w2/pilot.json`, SHA-256
`5f6e6a4fc524c95147d3231fee20c0f92392b17c1bf3b6c515defe41d2857c92`.
Both native FACE finishes, datum A and journal cylindricity passed the explicit
entity banks. Tip runout remained a separately reported coordinate-picked role;
the explicit identity result must not be extended to that selection.

Built/cold annotation comparison had zero rejected leaves, zero coordinate
roundoff allowances and zero zero-Z allowances. Source values/tolerances and
semantic attachments passed their existing comparisons. Original and owned-copy
SHA stayed `8df108cb4053bd47bcc1acc8b83fede6e3a52a9d3c4f6341c1ab3702d512b0ab`
through copying, recipe, close, cold reopen/close and final guards. The template
and other protected inputs stayed exact, with no runtime guard errors.
Ownership preserved the single visible clean `cylinder-gear.SLDPRT` baseline;
probe/cleanup errors were null. Ownership receipt SHA-256:
`ae29fab2c07e2e0c689476883528c69a8a3b0068572a2e0facb860406b6cb159`.

Recipe time was 23.1330910 s, separate prepared-template miss 37.1590173 s,
lookup hit 0.0479042 s, and whole pilot 171.6899835 s. This is one sample, not
a performance comparison. The built artifacts under the receipt's
`cone_gear_shaft/` directory use stem
`cone-gear-shaft-datum-policy-y25nr2w2-cone_gear_shaft`:

- PDF SHA-256: `c618e8764d535d30a2d962301a5d21ece8917965c1359054b02fd5b17c4f9323`.
- PNG SHA-256: `afa74c3a14ca69043a2bf08c94188508b028680ca5b369e19dfb8333ec736dce`.

Inspection of that PNG found two real text crossings. Raw annotation segments
and measured text boxes identify their owners; PDFium's lower-left glyph boxes
independently corroborate the printed locations. The following coordinates are
sheet millimetres, displayed to six decimals; the receipt retains raw metres.

| Leader / obstacle | Native segment, elbow to attachment | Crossed native text box |
| --- | --- | --- |
| `Drawing View1/HARMONIC_PMI_tip_runout` / `DetailItem358` Ra 1.6 | `(63.650000,241.500000)` to `(66.731808,215.396875)` | `(57.900407,219.592875)` to `(71.697340,225.172741)` |
| `Drawing View2/HARMONIC_PMI_journal_cylindricity` / `Sec2Dia` 6.350 | `(143.650000,138.500000)` to `(43.649646,83.331143)` | `(95.862898,115.517778)` to `(108.812365,121.097644)` |

The first segment crosses PDF glyph 722 (`1` in Ra 1.6). The second crosses
glyphs 785/786 (`5`/`0` in 6.350) and 791/793/794 (the upper `0.00` zeros).
These are glyph-box checks backed by the inspected PNG, not a general exact
glyph-outline intersection algorithm. The retained-coordinate regression in
`test_cone_gear_shaft_drawing.py` reproduces both old leader/text-box crossings
without COM or access to the original artifact files.

The five diameter strokes have ten pairwise intersections, all at the common
centre `(55,105)`, and no crossings through another diameter's measured text
box. The cylindricity leader adds the off-centre intersections: Sec2's shelf at
`(101.913090,115.474305)`, Sec3's radial line at `(80.750289,103.799071)` and
Sec4's radial line at `(70.963496,98.399829)`. The radial fan is visually busy,
but these observations do not justify treating every common-centre diameter
intersection as an erroneous leader crossing.

The pilot's layout comparison checks persistence of view positions/scales and
annotation geometry, not all-pairs ink clearance. Here it correctly proved that
the bad layout persisted exactly. **Native identity/cold PASS is not visual
acceptance**, and no cold PDF/PNG pixel comparison was performed.

## Two-FCF presentation candidate — native validation pending

Only two existing `PmiDrawingPlacement.position` arguments change:

| Model-owned control | Old origin (mm) | Candidate origin (mm) |
| --- | --- | --- |
| `journal_cylindricity` | `(150,142)` | `(100,85)` |
| `tip_runout` | `(70,245)` | `(110,245)` |

The tip frame requests the free upper band further right of the native finish.
The cylindricity frame requests the band below the diameter labels and above
manufacturing notes. Translating its measured 7 mm-high frame to the candidate
origin gives a nominal 6.464 mm gap to the lowest diameter body and 5.709 mm to
the notes. Those translated-body gaps are placement rationale, **not a prediction
of the new native leader route or proof of clearance**.

The exact existing view/entity references, coordinate-picked tip attachment,
datum A position, two no-leader FACE finish calls, `END_KEEP`, dimension
precision, tolerances, controls and notes are preserved. No arrangement call,
extra save/rebuild, helper change or manufacturing edit is added. The bundled
`IAnnotation.SetPosition2` contract supports GTol origins but allows native
placement restrictions; it cannot certify these proposed routes offline.

The actual-call regression failed first in precisely the two FCF cases against
`bd7e3384`; the eight other placement fields were identical. The datum case and
all prior shaft tests passed (`pytest-telemetry/run-4ea9skkg`: 2 failed,
13 passed). Existing native FACE tests still require the exact original controls
and entities with no coordinate arguments. The candidate needs a new serialized
native pilot, fresh leader/attachment readback, unchanged manufacturing and cold
banks, and native/PDF/PNG clearance inspection before visual acceptance. No
candidate native run has occurred.

Candidate offline verification passed 228 focused/adjacent tests in 17.73 s
(`pytest-telemetry/run-m9zafl_8`): shaft/batch contracts, native FACE recipe and
helper controls, finish ownership, GTol projection, VIEW acceptance and source
manifest tests. A complete recipe AST comparison against `bd7e3384`, restoring
only the two old position literals in memory, was identical. Ruff F and
`git diff --check` passed. Tests used the existing isolated rehearsal venv with
unchanged adapter `25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`; no root environment
or native documents were touched. This is not a full-pipeline or native gate.
