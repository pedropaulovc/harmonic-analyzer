# Video companion design

## Data flow

The CAD export supplies native geometry and rest transforms. Generated
`mechanics-data.ts` supplies the dimensions, linkage datums and spring catalog
values used by `mechanics.ts`. `export-mechanics.py` and `export-magnifier.py`
read CAD authority; the website does not infer dimensions from video pixels.

`video-catalog.ts` identifies the six original videos in scope and their local
reference hashes. `youtube-player.ts` owns the visible official embed.
`timeline.ts` reads independent source observations and selects measured
camera/physical input per view. `main.ts` changes between following playback and
paused exploration; `scene.ts` applies the physical pose to the full native GLB.

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

## Source coverage

Each observation identifies the original MP4 hash, source dimensions, decoded
presentation time, shot classification, camera and independently observed
landmarks. Camera fitting uses fit points and held-out check points. Mechanism
input must be complete and finite. It may be fully observed, or a chosen feasible
reconstruction constrained by source measurements. Unidentified coordinates in
the latter are explicitly unobserved; they are not recovered historical settings.

Every required frame needs a passing camera and complete physical input for all
of its views, with a source correspondence census covering the native drawable
inventory. Both observed inputs and constrained reconstructions require a bound
visibility proof. Physical photographs and transitions remain required when they
show a corresponding native mechanism.

The user permits source-non-identifiable structural fixed parts in a complete
feasible reconstruction. They stay rendered and in the native visibility census,
with their actual dark/cropped source region and fixed-motion evidence recorded.
The HUD and reports list them as not geometric-fidelity passed. Moving, deforming
or source-overridden parts cannot use this category; identified-feature error
and timing limits do not change.

Runtime states:

| State | Meaning |
|---|---|
| `matched` | Every required view has a passing camera and complete observed input or source-compatible constrained reconstruction. |
| `unavailable` | Required evidence is missing, incomplete or outside the observation record. |
| `held` | An exempt source interval retains an actual earlier matched pose. |
| `no-machine` | An exempt interval has no earlier match; current exploratory geometry/camera stay unchanged. |

Interpolation requires compatible, source-evidenced motion and view regimes.
Every observed or reconstructed view must cover the requested time with its
visibility certificate. A decoded exposure can be held inside that explicit
interval; point certificates do not cover gaps or expired tails. Preparation uses
a separate reusable sample bank. Mechanical/source validity and device target
capacity must pass before publishing views, input, camera or proof metadata.
Required incomplete footage never falls back to a held pose. The player remains
usable when source matching is unavailable; the warning distinguishes video
playback from verified geometry synchronization.

The current observation corpus is incomplete for all six videos, so footage
acceptance is not met. Source-camera reprojection results conditional on
unmeasured poses are not a complete physical match. The PDF page-by-page guide
video (`rMHw9GCAtE8`) is excluded by user scope; its footage is not part of the
catalog, observations or acceptance.

Measured photo/page transforms use the `source-image-plane-registered` camera
evidence kind and an authored `imagePlaneWarp`. Ordered physical
corner identities and the unwarped viewport determine the sole homography;
independent interior checks cannot be reused fitting corners. The reference
camera must be qualified independently. Native pose, field of view and reference
aspect stay unchanged; intrinsics scale uniformly rather than taking the target
ROI's aspect. No homography-coefficient interpolation or invented camera
trajectory is used. Manual exploration drops the image-plane presentation.

Each crossfade image has an explicit `imageLayerId`. Its ordered native subviews
compose opaquely into one transparent image, then receive the image's common
weight once. Higher same-image subviews mask lower colour and diagnostic samples
inside their actual rectangle/quad support. Different fading images do not mask
each other. Support-union weights are checked spatially, including nested insets;
disjoint regions do not create an artificial global opacity sum.

## Browser verification

`verify:sync` checks the original media identity, decoded samples, source-image
provenance and complete observations before launching the production site. It
requires all six pages, every integer-second sample and recorded change, a
38.4-pixel maximum landmark error and 0.5-second maximum timing error. Missing
media, blocked external playback and missing native geometry fail the command.

The verifier clicks the real YouTube controls and reads the iframe's actual
HTMLMediaElement state, decoded size, duration and currentTime. It rejects ads,
muted playback, seeking/buffering samples and incorrect native content. Reference
review seeks the official player, waits for a paused decoded frame and restores
exploration afterwards. Compact mode must keep the same visible iframe at least
200 by 200 pixels with working pause/resume controls and advancing audible media.

With `?verify=1`, diagnostic three-dimensional landmark markers follow native
node transforms and supported native deformation shaders. They pass through the
same viewport, scissor, mirror, image-plane warp and ordered image mask as the
scene. Marker readback proves projection only: depth-off markers do not prove
that a native surface is visible. The separate depth-tested part-ID capture
covers all native drawable paths and records their actual raster visibility.
Proof bindings and captures include the source exposure, camera, input, overrides,
geometry assumptions, authored/resolved warp or explicit nulls, and full ordered
support layout. Source/native uncertainty belongs in the final error bound;
raw reprojection error below 38.4 pixels alone is not acceptance.
Ordinary landmark coordinates use exact destination pixel-cell mapping.
Rasterized reference markers independently verify that mapping rather than
calibrating it. Marker, blit and warped-cell errors remain explicit native terms.
CPU camera projection and two aliases of the player's clock are insufficient
evidence. Native WebGL readback may use a software renderer; it does not imply
hardware acceleration.

Finite native-line diagnostics return the clipped GPU raster and its source-pixel
quantization bound. Every declared segment must stay inside its native drawable's
rest bounding box; that check alone does not identify a physical surface or axis.
The final ledger adds source localization, independently certified axis geometry,
native quantization and raster-fit deviation. A bundled axis allowance requires
an explicit decomposition so source localization is counted exactly once.
Contour bounds add source localization to nearest depth-boundary distance and
native quantization. Independently observed line endpoints, edge-row midpoints
and contour points must lie inside the view's unmasked image support; a nearby
surviving boundary cannot certify an observation hidden by a higher inset.
Fixed-part source-region containment uses the full exclusive pixel-cell extent,
not sampled contours. Warped diagnostics include native and destination raster
cell bounds transformed into source pixels. They retain full depth-tested support
rather than substituting CPU bounds.

Paused interaction checks the actual canvas pixels, crank input and unchanged
camera, then verifies pointer-driven orbit while native media remains paused.
A positive mathematical or renderer diagnostic proves only its exercised path;
it does not certify missing footage observations.

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
