# Paper-drive spare sprocket seating

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

## Narrow correction and offline repro

Only the spare's Y placement changes: use the shared `STACK_HEIGHT` directly,
leaving X/Z, rotation, T18 configuration, fixed state and subsystem ownership
unchanged. Its thickness then extends upward from the deck to Y=53.2. No part,
mounted sprocket, driven mate, manufacturing value or shared health helper changes.
The added pure-spec import makes deck-height changes an assembly input; it does
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

## Native acceptance still required

This code-only correction is separate from health-only PR #683. Its previous
build/render evidence does not validate the corrected assembly. Before accepting
this geometry change, rebuild paper-drive and the containing top assembly, retain
actual T18 configuration/transform and underside/deck contact readbacks, run the
unchanged soundness/kinematics gates, and inspect fresh top-level side/oblique
renders showing the seating and surrounding clearance. The full pipeline and
review merge gates still apply. No corrected native build or render is claimed.
