# Crank-arm entity selection validation

Work in progress. This document records the bounded migration requested in
`second-vm-crank-arm-entities.md`; it is not native acceptance or merge readiness.

## Frozen inputs and scope

- Root baseline: `bc593d784fba08fc6552224767a460338f51b664`.
- Adapter: `25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`.
- Independent seed clone and isolated worktree as specified in the handoff;
  exact checkout paths are captured in the local native receipts.
- Branch: `perf/crank-arm-semantic-entities`.
- Initial `git fetch origin main` found no commits in `HEAD..origin/main`.
- Own uv environment, CPython 3.14.5; no borrowed output, cache, DB or tokens.
- Attach-only SolidWorks revision 34.3.0. Initial locked native
  inventory was empty. Cache is disabled for native baseline production.

The part, spec, configuration, adapter and shared drawing helpers remain outside
this patch. Assembly PRs #676, #677 and #678 and their artifacts remain unchanged.

## Deliberate test conflicts reported before edits

`test_shaft_axis_datum_pick_is_radial_with_its_symbol` requires `DATUM_B_RIM`
radius/collinearity and literal coordinate selection. Three location tests require
`add_edge_dimension`; cross-hole station additionally requires `find_edge_near`
and its sheet-search axis. These implementation expectations conflict with the
requested migration. Their replacements must preserve the actual shaft-axis
datum, center-versus-tangent measurements, pivot/cross-hole BASIC assignments,
non-BASIC dimple transverse dimension, and all manufacturing requirements.

## Removed-site inventory

Fifteen source selection sites now use fourteen annotation/dimension calls and
one source-model entity bank. The fifteenth site was a nested edge search.
No sheet point identifies a feature. Remaining positions place text or views.

| Former site | Model role / ownership | View |
|---|---|---|
| Stock width dimension | `Arm` end-face boundaries at Y=-8/+8 | Right |
| Shaft-to-pivot dimension | `ShaftBore` and `PivotBore` cylindrical-face rims | Front |
| Pivot transverse dimension | `Arm` width-side boundary and pivot rim | Front |
| Dimple transverse dimension | Same width-side boundary and `Dimple` rim | Front |
| Cross-hole station dimension + nested search | `Arm` +Y face boundaries: z=0 line and cross-hole arc | Top |
| Datum A | `Arm` end-face boundary at z=8 | Right |
| Datum B | `ShaftBore` rim, native symbol placement | Front |
| Datum C | `Arm` -Y width-side boundary | Front |
| Cross-hole position FCF | Cross-hole arc on the +Y face | Top |
| Pivot position FCF | `PivotBore` rim | Front |
| Broad-face parallelism FCF | `Arm` end-face boundary at z=0 | Right |
| Cross-hole Hole Wizard callout | Cross-hole arc on the +Y face | Top |
| Pivot Hole Wizard callout | `PivotBore` rim | Front |
| Shaft finish | `ShaftBore` rim, explicit MODEL context | Front |

All roles are `FaceBoundary(FeatureFace(...), ...)`; zero or multiple faces/edges
fail rather than falling back to a body scan or sheet pick. The recipe resolves
once before insertion. Exact path, document identity, Default-only source
configuration, active drawing and each view's referenced source/configuration
are checked. Native handles are not persisted across builds or cold opens.

### Baseline datum-side contradiction (decision pending)

Native readback establishes that datum A tags z=8, whereas the existing
cross-hole station measures from z=0. Both yield 4 mm because the cross-hole is
centered. This is not evidence that the two datum sides are interchangeable.
The migration preserves the baseline's physical station attachment. The user
was asked whether to move it to the actual A face; no geometry/spec edit is
included and no answer has been assumed.

## Native baseline and provenance

The genuine cache-off `part:crank_arm` build ran 2026-09-07
14:23:03.678411Z–14:23:51.005805Z (47.327394 s), trace
`0x0078a1db4994887748532129308cb207`. Source size: 129171 bytes. Original SHA-256
and execution token are both
`6b086d5dbcb6e904fb794822728b705f69cd3903a0e8b2c5cf7abb8d9621f102`.
They are never restamped to accept a drawing result.

The literal handoff command `doit -a drawing:crank_arm` also force-ran the part
dependency, producing another genuine part identity. That run and all its
artifacts are separately retained in `cad/out/reports/crank-arm-entities-forced-dependency-run/`;
it is excluded from fixed-input timing. After closing only this task's produced
documents, the original retained part/token pair was restored byte-for-byte.
`doit -a -s drawing:crank_arm` then forced only the drawing against those inputs.

The fixed-input unmodified drawing ran 14:30:07.472794Z–14:30:22.383833Z
(14.911039 s), trace `0x6ec59549ee15e425ed41ebea7707ee1b`. Its unchanged
source, native drawing, PDF, PNG and telemetry are retained in
`cad/out/reports/crank-arm-entities-baseline/`.

Actual imports are from this worktree's `cad/scripts/draw_crank_arm.py` and
`SolidworksMCP-python/src/solidworks_mcp/adapters/pywin32_adapter.py`, using
`.venv/Scripts/python.exe`. All native jobs attach to the receipt-pinned
SolidWorks process under the machine-global lock and watchdog. Host and PID
are recorded in each local receipt rather than prescribed for another seat.
`HARMONIC_SW_AUTOSTART=0`, `HARMONIC_REMOTE_CACHE_MODE=off`, and
`HARMONIC_DIAGNOSTIC_SW_PID=<receipt-pinned PID>` are set. No restart, source save, source
repair, hidden inventory cleanup bypass or adapter edit is authorized.

### Retained receipts

Paths below are relative to this worktree's `cad/out/reports/`. The JSON receipts
retain actual commits, imports, requests, native readbacks and per-run results;
adjacent `ownership.json` files retain cleanup and borrowed-document evidence.

| Receipt | Result / SHA-256 |
|---|---|
| `crank-arm-entities-egcg01x5/measurements.json` | Pre-drawing source; 23 observed native dimensions, six required. `2a564b1bd9aa00819d3d0cfd275045d5ebab808964f51e77f0a227b33bb7d849` |
| `crank-arm-entities-6x1gg817/measurements.json` | Saved baseline drawing/source; source unchanged and clean. `e24efe0444d38f0cfcdafb3eb9413623807d28f36d700256ca0ef0fae71b2c06` |
| `crank-arm-entities-nq42cu4j/measurements.json` | Width inserted; diagnostic unbound `GetAnnotation` rejected. `c2dfdc19c8c08a31afd99edf08f4ce0617f1d82fe7e70fc98c5cfc046b66f8cd` |
| `crank-arm-entities-77s17dg7/measurements.json` | Width/cross-hole passed; fixed-position B rejected. `169a86d5dffc969bb4f5b98d799914c2ee87e3adab131025ea3744c17e3cf6f9` |
| `crank-arm-entities-e48m58vd/measurements.json` | All four positive callers passed, all five source roles selected/attached exactly. `237abfe8cbadf802d250c2655b186a450ca4b8690777a423460c7e9afe233ff8` |
| `crank-arm-entities-1a4l37xb/measurements.json` | Fourteen candidate annotations passed; diagnostic dimension-key mismatch rejected before cold validation. `0483f8d1704540c2dece10bcaca7f98f3337cb8e7145ade5a2ff86589228d8e4` |

Baseline artifact hashes:

```text
crank-arm.SLDDRW 9c8d090226e956675d00f1d67ad845b824318e117387d871e1cc9997c201fa74
crank-arm.pdf e11cf2ada46d088f3fb2b25ba6a64e5d92671705164e50ea1c49727fab6faa02
crank-arm_drawing.png 72ee90ab661bdedf98770035a8c221835b5cf96395236f5fd6e1473d96349dd5
telemetry/traces.jsonl a072a769d0fcbb86f9dfcd58c4db79717e8bdc2fd9d414de4d8f9bd0ed60b4f8
```

## Positive controls and candidate results

The first positive-control error was an unbound COM return, not rejected edge
selection; binding `IDisplayDimension`/`IDatumTag` resolved it. Fixed-position B
requested `(0.09, 0.17)` but read back `(0.056213502192082355,
0.11624875392230077)`: 0.063488 m error against the existing 0.0001 m limit.
Removing only that placement request passed the original attachment checks.
The successful control resolves the shaft, two stock boundaries and two wizard
edges, checks selected object/count/view and reverse-mapped source identity,
then checks attached identities. It executes the otherwise unmodified full
recipe through the actual prepared factory and owned save path.

Production `68709569` passed `doit -a -s drawing:crank_arm`, including the existing
final checks. `drawing.build` took 15.417655 s and its resolver 4.143519 s,
trace `0x33ad5b4c209fcf5e4ed6c81ca9e7fe34`. The comparable baseline took
14.911039 s: this single observation does **not** show a speedup.

Candidate `b981edf1` adds explicit center conditions for both ends of the 75 mm
dimension. Run `1a4l37xb` passed all fourteen live attachment witnesses, then
stopped at the diagnostic key mismatch. Its retained raw values already match
the baseline (e.g. 0.075000000114 m, not exactly 0.075); no tolerance was widened.

Run `2te502ia` at `02d285ba` passed native manufacturing, source immutability,
first cold reopen (including all-annotation comparison), and moved/scaled
attachment/dimension checks. It then rejected an in-place call to the adapter's
new-target save helper (`WinError 32` on unlinking an open drawing). The final
factory guard also correctly rejected concurrent test edits because its helper
fingerprint includes **all** `cad/scripts/*.py`, not just imported files.
The diagnostic now uses the shared attachment probe's guarded `Save3` pattern
for an existing moved copy; initial production save still uses the actual owned
save helper. Subsequent native runs freeze every Python file, including tests.
Both original and copied source retained their original SHA after this failure.

Frozen run `wlp6wb24` at `b974b038` passed the complete composed callback: all
fourteen explicit attachments, raw source/drawing values, BASIC/arc conditions,
first cold annotations, moved/scaled semantics, in-place save, fresh second-cold
handles and annotations, original/copy/token hashes, and factory guards. Its
instrumented recipe took 25.794955 s; this includes diagnostic witnesses and is
not comparable to uninstrumented production timings. Receipts:

```text
crank-arm-entities-wlp6wb24/measurements.json 165ae86b1666ceae8a5d5f30ed6fb9574fe9ab4ca8386f87de9dda7beaeabd3f
crank-arm-entities-wlp6wb24/ownership.json 26fb86db154a46f4410368e7874fc0a2633e432ee554d963c2d4154f5262bf4e
crank-arm-entities-wlp6wb24/cold.png 2ccf3ee2689ee7648605e60b7174bf13023ab4746bb908c47d9914d035a96aa9
```

The subsequent layout adjustment moves only the two transverse dimension text
positions: the pivot value clears the arm outline, and the dimple value sits
between its extension lines. A production run passed with this layout
(18.129079 s, trace `0x82a593ff79a401a75d3855caa0bbaa07`). Fresh native PDF detail
windows are now rendered at 600 dpi before and after cold reopen; they do not
modify the vector PDF or source geometry.

## Commands and gate status

```powershell
uv run python -m doit -a part:crank_arm
uv run python -m doit -a -s drawing:crank_arm
uv run python cad/scripts/diagnostics/probe_crank_arm_entities.py source
uv run python cad/scripts/diagnostics/probe_crank_arm_entities.py drawing
uv run python cad/scripts/diagnostics/probe_crank_arm_entities.py positive
uv run python cad/scripts/diagnostics/probe_crank_arm_entities.py candidate
```

The crank-only diagnostic deliberately pins this VM's genuine source and native
baseline receipt. Another VM must generate and retain its own baseline; these
pins are not fleet registration or permission to reuse this VM's artifacts.

The expanded focused suite passed 134 tests (`run-bc9feyn7`, 3.54 s), including
the actual loaded recipe inside the full mocked callback, wrong source/view,
missing/ambiguous roles, both fresh-handle cold lifetimes, actual in-place save,
save/export/final-guard failures and raw native manufacturing negatives. The
tests do not replace real native acceptance.

`doit -n 4 check:graph check:partiso check:recipe` passed graph (83 tests) and
isolation (4 tests), but recipe returned 6142 passes and two failures
(`run-ftjlmi6q`, 265.91 s). One failure was introduced here: a fleet contract
requires the original `callout_source_model = adapter.currentModel` capture.
That capture and verifier arguments have been restored without changing the
entity-bank ownership checks.

The other failure is already in the pinned baseline:
`test_fillister_is_not_silently_enrolled_in_full_owned_pilot` asserts that
`fillister_screw` is absent from `TARGETS`, while
`diagnostics/_recipe_acceptance_targets.py` explicitly registers it. Both files
are unchanged from `bc593d784fba08fc6552224767a460338f51b664`. The test also
fails alone (`run-t80pghl0`, 0.63 s):

```powershell
git diff bc593d784fba08fc6552224767a460338f51b664 -- cad/scripts/test_fillister_first_dirty_drawing.py cad/scripts/diagnostics/_recipe_acceptance_targets.py
uv run python -m pytest cad/scripts/test_fillister_first_dirty_drawing.py::test_fillister_is_not_silently_enrolled_in_full_owned_pilot -q --tb=short
```

No shared registry/test was changed. This deliberate-test contradiction needs
coordination with the parent owner before the full build gate can be green.

PR [#682](https://github.com/pedropaulovc/harmonic-analyzer/pull/682) targets the
unchanged drawing parent. CodeRabbit skipped automatic review on the non-default
base, and the explicit review was rate-limited (comment 5572490004). Use the
installed Windows `cr.exe` with
`review --agent --committed --base-commit <exact merge-base>`. No billing changes.

Local review at `b974b038`, merge-base `bc593d784fba08fc6552224767a460338f51b664`,
completed with one finding. Full structured output is
`cad/out/reports/crank-arm-local-review-3.log`, SHA-256
`cc33fbc43142c40f81208fb6ae6e0ce7cecd2fb36592d1cd752272836633973e`.
It claims datum B requires `symbol_xy` and surface finish rejects
`entity_context`. Those are not the signatures at this checkout: the unchanged
pinned `_drawing_common.py:439` declares `symbol_xy=None` for `add_datum_feature`,
and line 1061 declares both `symbol_xy=None` and `entity_context` for
`add_surface_finish`. With an explicit entity, native datum placement is
supported. The handoff specifically requires MODEL context for source-owned
finish entities. Real native run `wlp6wb24` executes both calls and passes their
exact attachment/cold checks. No TypeError occurs. This is evidence against the
finding, not a clean review verdict; a contextualized re-review is still required.

Frozen native run `pr4c3vvn` at `8484e910` passed the full candidate callback,
including both cold opens, move/scale checks, all fourteen exact attachments,
source/token preservation and final guards. Built and first-cold 600 dpi detail
crops were byte-identical. Inspection found the shaft diameter leader crossing
R8 text, overlapping finish/datum arrows, and two FCF borders touching nearby
lines. The next revision adjusts annotation placement and finish leader routing
only; it does not change the selected entities or manufacturing requirements.

The corrected fleet capture passed a 445-test focused suite (`run-8zjmnqo7`,
11.46 s). The repeated full recipe gate returned 6144 passes and only the
baseline fillister failure (`run-2zdoiquy`, 267.58 s).

Local review at `8484e910` found three minor issues (machine-specific paths in
this document and regex literal style in two test files), plus a valid evidence
preservation issue: a final source-hash/token read could mask an earlier error
and prevent the receipt from being written. All are addressed. The source and
positive-control finalizers now attempt every guard independently, persist the
failure receipt, and retain the primary error alongside final evidence errors.
Fifteen new regression tests cover unreadable/changed hashes and tokens,
persistence failures, and positive-control final guards.

Final frozen replay and print inspection of the adjusted layout, a clean
latest-code local review, and the full graph build gate remain pending. The full
graph build has not run; the known baseline recipe failure prevents a green
result. No merge readiness is claimed.
