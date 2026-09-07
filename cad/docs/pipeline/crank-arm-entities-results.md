# Crank-arm entity selection validation

Work in progress. This document records the bounded migration requested in
`second-vm-crank-arm-entities.md`; it is not native acceptance or merge readiness.

## Frozen inputs and scope

- Root baseline: `bc593d784fba08fc6552224767a460338f51b664`.
- Adapter: `25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`.
- Independent seed clone: `C:/src/ha-crank-arm-vm-seed`.
- Worktree: `C:/src/ha-crank-arm-semantic-entities`.
- Branch: `perf/crank-arm-semantic-entities`.
- Initial `git fetch origin main` found no commits in `HEAD..origin/main`.
- Own uv environment, CPython 3.14.5; no borrowed output, cache, DB or tokens.
- Attach-only SolidWorks PID 18748, revision 34.3.0. Initial locked native
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
`.venv/Scripts/python.exe`. All native jobs attach to PID 18748 on
`vm-solidworks` (SolidWorks 34.3.0) under the machine-global lock and watchdog.
`HARMONIC_SW_AUTOSTART=0`, `HARMONIC_REMOTE_CACHE_MODE=off`, and
`HARMONIC_DIAGNOSTIC_SW_PID=18748` are set. No restart, source save, source
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

Ninety focused tests passed (`run-x4hrhhsy`, 1.80 s): crank recipe, entity
diagnostic, full mocked recipe, shared resolver and `test_surface_finish_ownership_a.py`.
Additional full-composed callback tests and raw-dimension/requirements negatives
are being completed before the next frozen run. The tests execute the loaded
production recipe, not merely diagnostic wrappers.

PR [#682](https://github.com/pedropaulovc/harmonic-analyzer/pull/682) targets the
unchanged drawing parent. CodeRabbit skipped automatic review on the non-default
base, and the explicit review was rate-limited (comment 5572490004). Use the
installed Windows `C:/Users/pedro/AppData/Local/Programs/coderabbit/cr.exe` with
`review --agent --committed --base-commit <exact merge-base>`. No billing changes.

Full frozen native replay, final production rerun, fresh readable detail crops,
final print acceptance, clean latest-head review and the full graph build gate
are still pending. The first full-sheet renders preserve manufacturing content
but expose inherited crowded transverse-dimension placement; a green native
layout gate alone is not print acceptance. No merge readiness is claimed.
