# Video companion design

## Data flow

The CAD export supplies native geometry and rest transforms. Generated
`mechanics-data.ts` supplies the dimensions, linkage datums and spring catalog
values used by `mechanics.ts`. `export-mechanics.py` and `export-magnifier.py`
read CAD authority; the website does not infer dimensions from video pixels.

`video-catalog.ts` identifies the six original videos in scope and their local
reference hashes. `youtube-player.ts` owns the visible official embed.
`timeline.ts` selects compact source camera and physical-input tracks per view.
`main.ts` follows the original playback clock or permits paused exploration;
`scene.ts` applies the physical pose to the full native GLB.

The GLB hash and source revision must match the generated mechanical data.
A rejected load never enters the visible scene. Bindings resolve genuine native
component names; missing joints have a separate persistent warning and prevent
complete synchronization acceptance. Original geometry is not decimated, resized
or replaced with proxy parts.

## Physical model

All twenty stations contribute to the torque balance, in their CAD row order
(harmonics 20 through 1). Each station uses the actual eccentric circle and rod
closure, rocker contact arc and amplitude-bar geometry. Loaded extension-spring
force is computed from hook separation, catalog rate and initial tension. The
counter spring and lever weights participate in the nonlinear quasistatic
summing equilibrium. The wire and magnifier then determine wheel rotation and
pen travel. An ideal Fourier sum is not used to drive the physical output.

The released hub-wire route preserves its native rest contact and guided wrap.
Positive global +Z wheel rotation pays out the left-rim hanging run, so signed
pen travel is `-rimPitchRadius * wheelAngle`; `R/r` remains a gain magnitude.
This taut, non-slip model is an internal mechanical contract, not evidence that
the film uses the same routing or that a fixture adjustment held other inputs fixed.

Pen travel moves the native rod, v-block, frame, marker and set-screw together.
The hanger and its screw remain fixed. Source-evidenced setup lifts and yaw use
qualified rigid-part overrides; the pen wire remains a separately solved run.
The platen carries its rack, paper, two clips, all twenty-two fillister screws,
two guides and four guide locks as one 33-part group. The crank arm carries its
anchor screw. These attachments follow the released assembly mates pinned to
the native export; frame-mounted hardware remains fixed.

Interactive amplitude is a normalized CAD slide station, bounded by the native
mechanism. The displayed millimetres are not a calibration of the video's
engraved scale. Per-channel phase rotates that channel's cam. Source states must
supply all twenty amplitudes and phases explicitly.

The engaged bank drive is `crankTurns - driveCrankOffsetTurns`; the disengaged
bank retains `heldChannelTurns`. Returning the platform to the engaged state
changes the coupling offset, preserving the stopped bank's pose while the crank
has moved. This does not rewrite the physical cam phases or retune the counter.
The crank, cone shaft and paper feed retain their own drive motion.

The model omits friction, inertia and tooth-contact dynamics. Quasistatic
constraint rejection retains the last valid rendered geometry and shows an
error. It does not substitute a nominal pose or suppress a failed solve.

The native connecting-rod plate eye is used as the functional counterpart of the
filmed U-shaped junction, with the user's approval pending a later CAD correction.
`nativeGeometryAssumptions` identifies the affected rod paths and records that
approval. Animation uses the existing linkage; the head-shape difference remains
an assumption in the HUD and reports. It does not authorize geometry edits,
unrelated omissions or a measured head-topology fidelity claim.

Separately, the user permits only the two small rimmed/recessed lower-rocker
side-face features either side of the fulcrum to remain absent and uncertified.
The closed declaration names `lower-rocker-nearest-left-face-bore` and
`lower-rocker-nearest-right-face-bore`, and permits only qualified
`harmonic-analyzer/channel/rocker-arm-1..20` paths. All twenty native rockers lack
these features. This approval is not a promise of a future CAD match.

`nativeGeometryAssumptions` permits at most one of each exact declaration and
rejects duplicate identities, additional features and other native families.
The HUD distinguishes the rod-head assumption from the lower-rocker exception;
reports and visibility bindings retain the exact records. Neither declaration
establishes whole-part correspondence or makes unavailable source data matched.
Original hole contours remain diagnostics, not fabricated source pixels, native
holes or textures. Native inventory integrity, all other features, pose and
motion remain required. The staged image tolerances below replace the former
38.4-source-pixel limit; timing remains bounded by 0.5 seconds.

## Iterative synchronization plan

The approved sequence is **50% → 20% → 10% → 5% of source frame width**.
These are maximum landmark-position errors, not percentages of videos covered.
At 1920 pixels wide the limits are 960, 384, 192 and 96 pixels respectively.
The final target is 5%; video/model timing stays within 0.5 seconds at every stage.

Start with working approximate camera and mechanism tracking across **all six**
videos, then present an actual headed-browser demo before refining to 20%, 10%
and 5%. Complete one coarse pass across the collection rather than perfecting
one video while the others remain unavailable. Each stage reports its measured
coverage, maximum errors and unresolved intervals; unmeasured is not passed.

### Runtime tracks

Reuse the existing official player, native scene, physical solver and camera/input
interpolation. Author compact per-video shot tracks with camera keys, complete
feasible physical inputs, discrete setup changes and source view layouts.
Cuts switch atomically; interpolation is confined to compatible continuous shots.
Unobserved inputs may be chosen feasibly and must remain labelled as chosen,
not historically recovered. No second solver, proxy geometry, fake visibility
certificates or arbitrary individual-part adjustments are permitted.

Production playback does not require semantic source certificates for every one
of the 435 native drawables at every exposure. Native model identity, complete
inventory and coherent attached-part motion still matter. Offline source evidence
is separate from compact runtime tracks; full decoded-frame observation corpora
are not a prerequisite for displaying an honestly labelled approximation.

Required coverage includes every retained video's corresponding machine views:
close-ups, moving mechanisms, insets, mirrored views, photographs and montages.
A difficult view does not become exempt because it cannot yet be matched.
Intervals without a corresponding machine may retain the preceding pose.
Unsupported required intervals remain explicit in the UI and reports.

### Measurement and refinement

Use original hashed footage and timestamped source observations. Evaluate every
integer second and visible camera/mechanism change, with additional intermediate
checks around fast motion, cuts and nonlinear interpolation. Reference landmarks
must include spatially distributed fixed features and visible moving features;
a favorable camera fit alone cannot prove the mechanism state.

Compare the actual rendered native model with source landmarks and inspect
source/render overlays and silhouettes. Report source-localization uncertainty
and known geometry exceptions separately; do not relabel unknown correspondences
or uncertain measurements as precise passes. Existing hard foot/guide/pen failures
remain useful regression diagnostics, not obligations to solve an exhaustive
part-identification problem before showing any animation.

Per-video verification is incremental and repeatable, without an acceptance-run
quota. The all-video final gate retains all six pages and the 5%/0.5-second limits.
A coarse demo or a passing subset does not establish final acceptance.
On a failed stage, refine the worst source-visible discrepancy, rerun the affected
shot, then rerun the collection. Escalate actual missing geometry outside approved
exceptions rather than hiding it with a camera warp or an occlusion claim.

### Browser verification

Exercise the original visible audible player and use its actual media time,
not two aliases of an application clock. Seeking, buffering or unavailable media
cannot provide timing evidence. Check deterministic seek/follow behavior and
pause/manual/resume transitions against the actual rendered scene.

Paused exploration must permit orbit, pan, zoom and mechanism operation without
advancing the source video. Compact mode retains the same visible usable player
at least 200 by 200 pixels, with advancing audio and working pause/resume controls.
Verify all six routes; present a headed demo of the working implementation.

Native WebGL landmark readback remains available for rendered-pixel measurements.
CPU projection alone is not final rendered evidence. Existing raster, finite-line,
contour, masking and per-part certificate machinery is diagnostic legacy work:
its historical results are preserved, but completing its entire pending queue is
not a prerequisite for this iterative delivery plan. If a measurement uses a
particular diagnostic path, that path's known correctness defects still matter.


## Assets and rights

The full native GLB is approximately 223 MB. The website loads one model and
reuses geometry buffers during motion. Source observations load per video.
Downloaded MP4s, decoded frames, screenshots and verification reports stay
outside tracked publication assets. The site embeds the originals through
YouTube rather than hosting their streams. The 2014 book's non-commercial
material must not enter a commercial website or campaign product.

The default static base path is `/harmonic-analyzer/`. `SIMULATOR_BASE` must be
consistent between Vite build and production verifier. Portfolio sequencing is
owned by the [project board](https://github.com/users/pedropaulovc/projects/1).
