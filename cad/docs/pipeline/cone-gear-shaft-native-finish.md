# Cone-gear-shaft native FACE finish placement

The candidate changes only the placement request for the two existing journal
surface finishes. Native acceptance on this shaft is pending. The part geometry,
source pin, selected faces, part-owned Ra 1.6 controls, dimensions and PMI remain
unchanged. The coordinate-selected `tip_runout` PMI is outside this change.

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

## Tests and next native acceptance

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

Required evidence remains both exact finish attachments through built/cold
reopen, unchanged source/dimension/PMI banks, final manufacturing/layout checks
and a readable freshly exported PNG. No acceptance predicate or source pin is
changed. No native run was performed while preparing this candidate.
