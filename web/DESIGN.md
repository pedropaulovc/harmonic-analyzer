# Video companion design

## Data flow

- `content/tracks/<slug>.json` + `content/cameras.json` → `src/track.ts`: the
  shot table for the selected video, evaluated at the YouTube player's time
  into one view per tile (camera pose + `MechanismInput`).
- `src/mechanics-data.ts` (generated from `cad/` by `scripts/export-mechanism.py`)
  → `src/mechanics.ts` / `src/magnifier.ts`: the quasistatic solver turns an
  input into a pose (joint angles, spring lengths and forces, wire runs, pen
  and platen travel).
- `public/models/ha-harmonic-analyzer.glb` (release GLB, `scripts/fetch-model.mjs`)
  → `src/scene.ts`: nodes bound by name through `src/bindings.ts` are moved to
  the pose; the viewer draws each tile into its rectangle of a 16:9 gate.
- `src/main.ts` wires the YouTube player, the controls and the frame loop;
  `src/editor.ts` is the `?edit=1` shot editor, loaded on demand.

The mechanism data comes from CAD configuration and pure geometry modules,
never from the model's pixels or the video. The website does not infer
dimensions from footage.

## Model delivery

The site loads the latest release GLB as exported by CAD, with lossless exact
deduplication and Meshopt compression (`scripts/optimize-model.mjs`, which
checks that every decoded buffer is byte-identical). Geometry is never
decimated, resized or replaced with proxies. Part names are the current CAD
stems; there is no name rewriting at load. A binding that finds fewer nodes
than it expects warns in the console and under the controls; everything else
keeps moving. A missing model is a supported state: the solver and force
readout still work.

The viewer generates a PMREM room environment once for image-based lighting:
the steel and brass materials are fully metallic and read as black under
diffuse light alone. The room contributes reflections only.

## Physical model

All twenty stations contribute to the torque balance, in their CAD row order
(harmonics 20 through 1). Each station uses the actual eccentric circle and rod
closure, rocker contact arc and amplitude-bar geometry. Loaded extension-spring
force is computed from hook separation, catalogue rate and initial tension. The
counter spring and lever weights participate in the nonlinear quasistatic
summing equilibrium. The wire and magnifier then determine wheel rotation and
pen travel. An ideal Fourier sum is not used to drive the physical output.

The hub wire keeps its rest contact and guided wrap. Positive global +Z wheel
rotation pays out the left-rim hanging run, so signed pen travel is
`-rimPitchRadius * wheelAngle`. This taut, non-slip model is an internal
mechanical contract, not evidence that the film uses the same routing.

Springs are the GLB's own swept-wire meshes, deformed in the vertex shader:
hooks and transitions move rigidly and the coil pitch follows the solved
length.

Pen travel moves the rod, v-block, frame, marker and set screw together; the
hanger stays fixed. The platen carries its rack, paper, clips, guides, guide
locks and their screws as one group. The crank rig carries its arm, hub,
handle parts, pins and keeper chain. The paper train has two rigid rotating
groups: the knob/collar/shaft members about the knob axis and the
disc/feed/hub members about the disc stud. The 66 chain links keep their rest
transforms and follow the planar chain centreline for the mounted gear pair;
tooth contact and slack are not solved. Medium-medium gearing clones the spare
T18 sprocket onto both seats.

Interactive amplitude is a normalized CAD slide station; the displayed
millimetres are not a calibration of the video's engraved scale. Per-channel
phase rotates that channel's cam. The engaged bank drive is
`crankTurns - driveCrankOffsetTurns`; the disengaged bank holds
`heldChannelTurns`, so re-meshing after a disengaged crank advance keeps the
stopped bank's pose.

The model omits friction, inertia and tooth-contact dynamics.

## Shot tables

A shot is a row of the track: a time span, a camera (named or inline) that may
move to `cameraEnd`, crank turns, a channel preset and setup values. Rows
interpolate linearly; `hold` rows freeze the previous shot's end. Split-screen
source frames use `tiles`, each with its own camera and optional mirror.
Format details are in [`README.md`](README.md#shot-tables).

The tables were converted once (2026-11) from the earlier per-frame fitted
source tracks, preserving every rendered motion segment and camera within 1.01
source pixels. Three simplifications were made in that conversion: crossfades
keep only the dominant layer, image-plane warps render unwarped into their
rectangle, and tiles that showed a photograph of loose gears are left empty.
Setup states that are not the operating machine (bars lifted, the measuring
stick, a gear change, the pen being installed) are not modelled; the Operation
rows that showed them render the operating machine and are marked
`"review": "unverified"`. A setting past a v49 end stop (cone swing, pinion
cam, wire fixture) clamps to that stop. The cameras were fitted on the v39
model; v49 moved some parts (notably the magnifier and pen), so a camera aimed
at them may need re-framing in the editor.

Spans where the footage shows the machine running but the fitted tracks held a
static pose were roughed in afterwards from the engineerguy contact sheets
(also `"review": "unverified"`, with a `note`). Rows are approximate by design:
they are chosen to match each scene, not measured against the footage.

## Assets and rights

The site embeds the original videos through the official YouTube player rather
than hosting their streams. Downloaded videos, frames and screenshots stay out
of the repository and the deployment. Narration and shot order may follow the
engineerguy transcripts (`references/engineerguy-youtube/*.vtt`); paraphrase,
never paste. The 2014 book's non-commercial material must not enter a
commercial website or campaign product. Portfolio sequencing is owned by the
[project board](https://github.com/users/pedropaulovc/projects/1).
