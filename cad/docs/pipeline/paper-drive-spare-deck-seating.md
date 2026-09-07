# Paper-drive spare sprocket seating

## September 7 native counterexample and revised placement

The first candidate at `e864524b2cc559a04ef90c4d8884771fb2ad2b34`
kept X/Z fixed and lowered Y to the deck. Its paper-drive subassembly passed,
but the complete top assembly rejected **605.55 mm^3** of interference between
`frame-1/nameplate-1` and `paper-drive-1/transgear-removable-3`.
Repro: run the full `uv run python -m doit -n 4` at that commit. Retained
`cad/out/reports/telemetry/{logs,traces}.jsonl` and the assembly build log in
`C:/src/ha-perf-spare-deck-seating` record the failure. The first run stopped
on a modal/low-memory session; the restarted run reached this actual geometric
counterexample and failed in 119.4 seconds for the top task.

The earlier inference that the existing footprint was clear was incomplete:
it checked the base rim but omitted the nameplate. Its shared specification
places the plate at X=159.25..214.25, Z=-50..50, Y=50.8..52.3. The spare at
X=160/Z=-15 overlaps that footprint. No interference exemption was added.

The revised storage station is **(160, STACK_HEIGHT, -75) mm**. The T18 tip
radius is 20 mm, so its Z envelope ends at -55, 5 mm before the plate's -50
edge. It remains a flat, fixed, loose T18 in paper-drive with the same rotation;
only its storage Y/Z change. A new envelope test fails at the first candidate
(`5 <= -55` is false). This is a conservative offline clearance check, not
native contact or full-model clearance evidence. The full build, saved contact
readback, and fresh oblique visual inspection remain required.

The revised tip envelope is X=140..180 and Z=-95..-55 mm. The deck's flat
interior is X=-215.25..215.25 and Z=-126.35..126.35 mm, so the whole circular
envelope lies inside the raised rim. This bound complements the nameplate
clearance test; it does not replace the native interference gate.

The full `uv run python -m doit -n 4` at
`f82021edfff36155b765b50e99c4e2d3e1610bea` exited zero on September 7.
It rebuilt paper-drive and the top assembly, regenerated their drawings, and
passed soundness and kinematics. The recipe gate passed 1,186 tests. Native
contact and visual results follow below; latest-head build/review remain open.

## Saved contact and visual inspection

The [saved contact diagnostic](spare-deck-contact-diagnostic.md#accepted-native-contact)
passed at `dad339f0`: exact T18/native-instance checks, opposing support normals,
0.0 m plane separation and 0.0 m trimmed-face contact distance. All 114 saved
input hashes and before/after document states were unchanged; owned cleanup
left the session empty.

Fresh paper-drive and complete-top production renders were inspected. An
additional native close-up at the same saved top used the bundled Zoom to Region
example: transform the eight corners of X=115..230, Y=35..110, Z=-115..25 mm by
the active view orientation, then pass their extrema to `ViewZoomTo2` and export
the current view at 2000x1500. No component was hidden or moved and no model saved.
The receipt is `cad/out/reports/spare-deck-views-dxm_cfcg/views.json`.

The isometric close-up clearly shows the spare seated on the deck, clear of the
nameplate, column and rim. Its PNG SHA-256 is
`4720ba0e1f11eec61f6f649162f8ee85d5abce7ebe5e3f82789194c5e35517e9`.
The front view is occluded by the rim and does not prove seating; the top view
shows clearance but is partly occluded by the lever bank. The oblique view and
native contact measurement provide the seating evidence. All input hashes stayed
unchanged after the three view captures, and owned cleanup left no documents open.

The original candidate analysis below is retained as provenance; its
"only Y changes" proposal was rejected by the full-model test above.

The horizontal grey wheel in the isolated paper-drive render is the intentional
loose T18 speed-change sprocket, not a detached driven wheel. Its support is the
base in `frame.SLDASM`; the top assembly inserts frame and paper-drive at identity.
The spare remains a fixed leaf inside paper-drive, separate from mounted T12/T24.

## Pre-existing placement defect

The September 7, 2026 read-only audit of `ha-assembly-health-stable` at
`d542a1174a99de4e94e091c44969ebf8a9c9b9aa` found an unintended **2.4 mm deck gap**.
This is not caused by the health traversal change:

- `build_paper_drive_assembly.SPARE_GEAR_POS = (160, 53.2, -15)` dates to
  `5a540e872edeeaab8325fcd93403e3e98e270fc2`, July 8, 2026. Both the older tracked
  `cad/docs/images/paper-drive.png` and September 6 root isometric show the spare.
- The fresh isometric PNG is
  `cad/out/png/paper-drive/paper-drive_isometric.png`, SHA-256
  `cd305afc29594dc7ce67ca1e31c83620a829b404d5abba2d38c0c80c3df3c5e3`.
- Retained `cad/out/reports/telemetry/{traces,logs}.jsonl` in that checkout records
  trace `6271c289b9f507960d3e22518ee64659`, span `29627f882684d595`, at
  `2026-09-07T14:41:12.889111Z`: `transgear-removable-3 placed at [160.0, 53.2, -15.0]`.
  The span identifies configuration T18 and fixed placement; the existing placement
  checker also checks the rotation. This proves the authored pose, not contact.
- `build_transgear_removable` constructs the common face thickness along local
  `Z=0..FACE_WIDTH`, with `FACE_WIDTH=2.4`; its blank mass check expects centre Z=1.2.
  Only tooth count changes between T12/T18/T24. The retained default-T24 STL,
  `cad/out/stl/transgear-removable.STL`, independently reads Z bounds
  `[-3.0357660829594124e-15, 2.4000000953674316]` mm, SHA-256
  `75ccc27aadbe1c3b982747c1ca1c2637e0b581fdd215460fbdcc5e38961fa52c`.
  This is a common-thickness cross-check, not a separate native T18 contact probe.
- `_assembly.world_point` and the adapter's transform writer use `world = local·R+t`.
  `ROT_X_NEG90` maps local +Z to machine +Y. Thus the old underside/top are
  Y=53.2/55.6, while `harmonic_base_spec.STACK_HEIGHT` puts the deck at Y=50.8.
  The T18 footprint at X=160, Z=-15 lies inside the rim, not on its raised edge.

## Rejected historical Y-only proposal and offline repro

This section records the rejected Y-only candidate, not the revised Y/Z placement
above. It changed only the spare's Y placement to the shared `STACK_HEIGHT`,
leaving X/Z, rotation, T18 configuration, fixed state and subsystem ownership
unchanged. Its thickness then extended upward from the deck to Y=53.2. No part,
mounted sprocket, driven mate, manufacturing value or shared health helper changed.
The added pure-spec import made deck-height changes an assembly input; it did
not insert the base into this subassembly or change any part recipe.

`test_paper_drive_assembly_drawing.py` is already enrolled by the `check:recipe`
`test_*_drawing.py` discovery. New tests exercise the production point transform
using the authored rows, real base specification and real sprocket thickness;
they also pin the original fixed-T18 insertion and flat-deck footprint. Before
the fix they returned **1 failed, 3 passed**, rejecting `53.2 != 50.8` at the
underside assertion. No existing assertion required the old 53.2 placement.
The mirror-retirement diagnostic and kinematic role resolver read the shared
placement; the existing graph test keeps the spare inside paper-drive.

Re-run the focused contracts in a configured checkout:

```powershell
uv run python -m pytest cad/scripts/test_paper_drive_assembly_drawing.py cad/scripts/test_platen_refit.py cad/scripts/test_component_patterns.py cad/scripts/test_buildgraph.py cad/scripts/test_part_isolation.py -q
```

These five files passed **48 tests in 42.71 s** with the candidate's pinned
adapter `2269009ed56712867826516f4406afc98a0c2814`; Ruff F and `git diff --check`
passed. A one-off AST comparison against base `f3ac51b77c5729c9a5e23d831a4b2c647b0bf01a`
confirmed the builder is otherwise identical after removing only the added spec
import and restoring the old spare-position expression. Actual task enumeration
confirmed the test file in both the recipe command and dependencies; closure
inspection found no part consumers of the changed assembly builder. These are
offline checks, not a full-pipeline result.

## Native acceptance boundary

This code-only correction is separate from health-only PR #683. Its previous
build/render evidence does not validate the corrected assembly. Before accepting
this geometry change, rebuild paper-drive and the containing top assembly, retain
actual T18 configuration/transform and underside/deck contact readbacks, run the
unchanged soundness/kinematics gates, and inspect fresh top-level side/oblique
renders showing the seating and surrounding clearance. The full pipeline and
review merge gates still apply. The revised build, contact and visual results
are recorded above; final head-specific gates remain required before merge.
