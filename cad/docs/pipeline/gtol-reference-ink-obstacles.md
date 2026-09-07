# GTol placement and center-reference ink

This bounded planner correction preserves center marks/centerlines and the final
collision gate. The production rerun and fresh PNG inspection passed as recorded
below; a cold-reopened screw comparison remains pending.

## Retained failure

At root `4c3c1e116980fa8ed0bbb4e384c9c2bd952d95f7`, production
`drawing:cone_pivot_screw` failed in the fresh final annotation check. Trace
`0x4339a41c960ce33fcd059a38e0c03ab2` in
`cad/out/reports/telemetry/traces.jsonl` ends at
`2026-09-07T11:22:34.345307Z`. Template HIT, ThreadTail import, GTol placement,
and packing readback completed before this rejection:

- View `end`: source `DetailItem344`, combined stroke index `7`.
- Target `DetailItem349`, kind `5`, text
  `['<GTOL-TRUN>', '0.05', 'A', 'SHOULDER OD']`.
- Target body in sheet metres:
  `[0.1039590787186291, 0.16291526514446417,
  0.1363848787186291, 0.1754815155262133]`.

That receipt omitted the source kind and stroke coordinates. It does **not**
establish that `DetailItem344` is a center mark. The fastener recipe deliberately
creates end-view center marks before its dimensions, making the missing planner
inventory a concrete lead, not a confirmed identity for that native name. The
existing September 6 screw PNG is stale and is not evidence for this failed run.

## Correction and limits

The planner previously enumerated only datum, dimension, and surface-finish
annotations (`2/4/7`), while the final reverse check already included every
measured annotation's displayed strokes and native leader segments. The planner
now also enumerates `swCenterMarkSym=13` and `swCenterLine=15` through the existing
`IView.GetAnnotationsByType` call. Those enum values and the view-local array
contract were checked against the bundled official API reference.

The existing native bounds reader encloses center-reference strokes and their
measured print widths in the annotation body. That body feeds the existing
outboard/vertical candidate policy; no reference annotation is selected, moved,
removed, or recreated. Hidden and template-owned reference ink is excluded
consistently with the final packing collision bank. Unknown visibility is not
silently treated as hidden.

Each included reference annotation costs one additional fresh full planner read,
plus two type-enumeration calls per nonempty GTol view. Nullable native positions
are supported by the bounds reader, but not by the XYZ-only handoff, so these
measurements are deliberately **not** registered in that cache. Initial/final
packing and all existing semantic, source, attachment, and collision checks stay
unchanged. This is not a zero-COM or measured speedup claim. Rectangle envelopes
can conservatively reject otherwise clear lanes; no exact ink-routing claim is
made. Deferred notes and other final-only kinds are not newly added to planning.

Reverse-collision failures now retain source kind, each hit's exact coordinates
and width, its displayed-stroke versus native-leader inventory/index, and hit
decoration bounds. These are derived only from the existing final snapshot;
the hit predicate and original fields are unchanged.

## Offline regression

In `C:/src/ha-perf-gtol-reference-ink`, fail-first receipt
`cad/out/reports/pytest-telemetry/run-f8qfi2d2` recorded four failures: both
`13/15` reference fixtures still intersected the old accepted GTol lane, and
both error-evidence fixtures lacked source kind. Four exclusion controls passed.
The corrected suite also proves that the new lane passes the unchanged final
check, reference ink is read once and never handed off/moved, empty GTol views
do not scan references, and hidden/template exclusions preserve required ink.

The broader bounds/GTol/layout/handoff suite passed **495 tests** in 6.02 s,
receipt `run-z2z5jtt7`. Focused reproduction from an initialized checkout:

```powershell
uv run python -m pytest cad/scripts/test_native_gtol_drawing.py cad/scripts/test_leader_clearance_drawing.py -q
```

## Production rerun: live gates and fresh export passed

The parent-owned production rerun used root
`0d208ea049bda6f830555446dd0dd932b2baadd5`, adapter
`25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`, and SolidWorks PID `31860`.
Retained trace `0xc3741c28951be4ac801d29216263e471` has **81 OK spans** and no
error span. Independent read-only inspection confirmed these timings:

| Span | Start/end (UTC, September 7) | Elapsed |
| --- | --- | --- |
| `task drawing:cone_pivot_screw` | `11:38:24.525748` / `11:39:49.028702` | 84.502954 s |
| `drawing.build` | `11:38:25.638165` / `11:39:48.845532` | 83.207367 s |
| `drawing.project_native_layout` | `11:38:49.940504` / `11:39:45.930516` | 55.990012 s |

The prepared-template cache hit took 2.555 ms with key
`541ab0717c2abd5f9739543b88a72ceb63064ad896dfdccd3f0f026195f82bbf`.
`drawing.verify_model_callouts` for `ThreadTail` passed. The unchanged fresh
packing-final validation passed at `11:39:45.803365` through `11:39:45.804356`.
Its per-view log reports retain empty outgoing and reverse crossing lists for
`side`, `end`, `iso`, and `right` (GTol counts `2/2/0/1`). Native save, PDF export,
and PNG rendering then passed.

The `end` planner used 15 obstacle rectangles instead of the failed run's 14.
It accepted its first right-side candidate at
`dx=0.031100000101364392 m`, versus `0.02659800009999999 m` previously. Its
measured pre-packing GTol union was
`[0.1010900001013644, 0.14186749933650164,
0.1335158001013644, 0.1690000000999999]`.
This records the actual changed placement, not a timing/speedup claim.

Both the parent and the independent reviewer inspected the fresh PNG: the GTol
frames are clear of center-reference ink, the center references remain present,
the thread callout is readable, and the title fields are separate. This is the
September 7 export, not the stale September 6 image.

Read-only SHA-256 observations below used `FileAccess.Read` with
`FileShare.ReadWrite`, without closing any SolidWorks document. Each file was
hashed twice; both hashes matched and size/mtime remained unchanged across the
observation. Paths are relative to `C:/src/harmonic-analyzer/cad/out`:

- `slddrw/cone-pivot-screw.SLDDRW`: 171969 bytes;
  mtime `2026-09-07T11:39:47.0506206Z`;
  SHA `5990c0d495b154a3b3eb36f2b018be5acc503904d29560f47042abdc6f220119`.
- `pdf/cone-pivot-screw.pdf`: 59332 bytes;
  mtime `2026-09-07T11:39:48.4894085Z`;
  SHA `94b69726556431fd90680edba5a2428cd94d79b31e44d6cbbaacb5c596dec526`.
- `png/cone-pivot-screw_drawing.png`: 866214 bytes;
  mtime `2026-09-07T11:39:48.7785319Z`;
  SHA `c841eb37a982becc4b6bf06c9d3cc794bda8dc3b9cbf6433e0291b1a0a4a1729`.

### Still unproved by this run

The failed run still does not identify `DetailItem344`'s annotation kind or its
exact stroke coordinates. Successful placement with the new inventory does not
retroactively supply those missing fields. Nor does it establish generic
planning coverage for a hypothetical native-only reference leader absent from
the displayed body/open ink; the full final reverse gate still covers native
leader segments independently.

Cold-reopen acceptance is **not** supplied by this production task. Inspection
of `_cached_drawing_action`, `run_drawing_build`, `build_fastener_sheet`,
`finalize_drawing`, and the adapter's `save_drawing` confirms a live recipe,
native save, PDF export, render, and return, without closing/reopening the saved
drawing. The trace likewise contains no cold comparison. A separate owned-copy
replay is needed to establish persisted source/attachment/text/layout equality;
the artifact hashes and live final gate do not substitute for it.
