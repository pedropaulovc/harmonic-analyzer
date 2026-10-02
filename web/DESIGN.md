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

The viewer generates a PMREM room environment once for image-based lighting.
The native steel and brass materials are fully metallic, so diffuse hemisphere
lighting alone leaves their surfaces dark. The environment contributes reflected
light only: its room geometry is not added to the machine scene or drawable
inventory, and native GLB geometry and materials remain unchanged. Temporary room
and PMREM resources are released after generation; the environment render target
is released with the viewer.

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
These are maximum admitted landmark/contour source-pixel errors, not percentages
of videos covered. At 1920 pixels wide the limits are 960, 384, 192 and 96 pixels respectively.
The final target is 5%; video/model timing stays within 0.5 seconds at every stage.

Start with working approximate camera and mechanism tracking across **all six**
videos, then present an actual browser demo before refining to 20%, 10%
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

Chosen source-informed camera framing is held unless both endpoints explicitly
declare `cameraInterpolation: 'continuous-shot'` with nonblank
`cameraInterpolationEvidence`. `held` at either endpoint vetoes blending,
including for measured camera families; omitted policies preserve existing
source-fit/source-transfer continuity. Unknown policies or missing continuous-shot
evidence reject the track. Existing continuity/provenance families and
cut, layout, gearing and counter-height-mode guards remain authoritative.

Analysis03's bounded **4.4044..7.307300000000001-second** interval and
Synthesis's presenter-to-spin **25.984291667..26.609916667-second** interval
opt in to this chosen continuous framing through the same optional
`content/<videoId>.chosen-camera-continuity.json` permission convention.
Position, quaternion rotation, FOV and principal point interpolate; Synthesis
holds its existing front-camera position/quaternion and blends its chosen
principal-point/FOV reframing keys. Its 16 retained source rows cover native
exposures 623..637. Before normalization, a selected permission requires either
one main view or the retained outgoing/incoming pair: null cameras, full-frame
native rectangles, and no warp or composite metadata. Missing, empty, duplicated or
unmapped views are refused rather than replaced with a fabricated main view.
Normalized main/whole framing is validated afterward; retained source files stay
unchanged. Both active observation and retained-track native-index schemas must
agree when both fields are present. Native PTS must match index/FPS within
1e-9 seconds; decimal cut rounding does not authorize a frame-sized expansion.
Mechanical provenance remains chosen and stages remain unmeasured. Neither this
interpolation nor the scoped headless Analysis **5.9..7.1-second** and Synthesis
**25.98..26.54-second** demonstrations establish recovered camera/mechanical pose,
historical camera motion or a fidelity pass. All six videos retain the final
**5% / 0.5-second** acceptance limits; other videos' framing policies are unchanged.

Eight focused `node:test` cases load the real modules through Vite SSR
(`npm --prefix web run test:playback`). An optional `SOURCE_TRACK_MODULE`
selects a historical source-track module for failing-before controls without
reverting the implementation. Synthetic fixtures test runtime decisions, not
source observations or rendered fidelity.

Phase offsets interpolate along the shortest angular arc; cumulative crank turns
remain linear. The Analysis bank's independently fitted inverse cam roots are
continued on the nearest genuine branch before interpolation. Both roots preserve
the observed rocker angle, but may change an unobserved cam/rod orientation.
Retain the original rod bounds, CHECK pixels and branch-choice audit; do not
suppress an infeasible transition or claim recovered phase history.

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

Count the machine views actually visible in the footage. Synthesis's
presenter-to-spin edit moves one machine image; it uses one native view with
source-informed principal-point/FOV keys. Its coarse framing remains unmeasured.
Actors and formula graphics stay in the original player.

### Measurement and refinement

Use original hashed footage and timestamped source observations. Evaluate every
integer second and visible camera/mechanism change. Additional intermediate probes
use real independently observed source exposures, never interpolated oracle pixels.
Their unavailable measurements are diagnostic; an admitted over-limit error still
fails the stage. Reference landmarks must include spatially distributed fixed
features and visible moving features; a favorable camera fit alone cannot prove
the mechanism state.

Compare the actual rendered native model with source landmarks and inspect
source/render overlays and silhouettes. Report source-localization uncertainty
and known geometry exceptions separately; do not relabel unknown correspondences
or uncertain measurements as precise passes. Existing hard foot/guide/pen failures
remain useful regression diagnostics, not obligations to solve an exhaustive
part-identification problem before showing any animation.

GPU landmarks explicitly use `depth-off-landmark-projection`. Their errors measure
projected feature positions, not visible native surfaces: an opaque part can cover
an accurately projected marker. A favorable landmark result therefore cannot
replace actual source/render inspection. Use the depth-tested native part-ID
capture to distinguish genuinely occluding components from dark metallic surfaces;
lighting changes must not change those surface owners or hide native geometry.

`verify-sync.mjs` also measures retained raw `SourceContourCheck` curves through
the existing depth-ID API, without copying contours into compact tracks or
changing the selected source camera/input. A sidecar joins only the exact source
video/frame/decoded-PTS and same-format image hash, with an unambiguous measured
source-layout view mapping. Gray and BGR byte identities never compare across
formats. Original endpoints, source-only evidence and partial-edge scope remain
unchanged. Every contour stays CHECK-only, strictly downstream of fitting; a
camera candidate fitted to these rows is not independent and cannot be promoted.

After paused exact source review, a contour-bearing row enables part visibility
and reads the snapshot, landmarks, native visibility and full mechanism solve
from the same redraw. Captured status and camera/principal point, ordered support,
warp, destination-cell/native-backing metadata, time, physical-input and positive
layer contribution must agree. The selected native part must have nonempty actual
depth-ID pixels and sampled boundary centers. Native support/scissor and later-mask
filtering applies; missing, stale, wrong-part, hidden and zero-contribution receipts
cannot become an empty-set success. The all-drawable ID inventory preserves real
native occlusion, not a new per-435 source-certification gate.

The native getters already enforce their private renderer capture epoch. The
bridge exposes the existing source-draw revision only for captured getter output
bound to the current completed source draw; stale/unknown output receives no
revision. Contour, landmark and mechanism revisions must all equal the positive
current snapshot `sourceDrawRevision`, and its `sourceDrawTimeSeconds` must match
capture time. Thus retained same-time old pixel/mechanism records cannot qualify
merely because time, camera, input and layout repeat. Missing old revisions fail
closed; no epoch fallback is synthesized.

For observed partial source points \(S\) and actual captured target-part boundary
sample centers \(N\), the oracle is
`max(s in S) min(n in N) distance(s,n) + source uncertainty + GPU raster bound`.
Both uncertainty terms are source-global pixels, added once; no homography scales
the already-global source term. Warped source localization requires supported
projective footprints and matching resolved/backing receipts. There is no inferred
curve extension, bounding-box/native-endpoint/CPU proxy, RMS smoothing or reverse
distance against unobserved silhouette portions. The actual GPU sample subset can
overstate nearest-boundary distance, never optimistically reduce it.

This is binary ID/depth **layer geometry**, not literal final fractional-alpha
color visibility: positive crossfade layers have their exact weight recorded but
are not area-scaled, and diagnostic depth/material behavior can differ from color
blending. Inherited Rod20 right-exterior evidence certifies only the observed
partial edge if measured; it cannot establish the entire silhouette, opposite
edge, junction topology or material-coordinate identity. Same-part nearest-edge
correspondence and the coarse 384-pixel Stage20 tolerance remain geometric risks.

Per-sample and summary `contourChecks` count each curve once, separately from FIT
and CHECK point landmarks. A genuinely measured contour can supply a view's CHECK
and required sample even without point CHECKs. It supplies moving coverage only
through existing exact-part moving ancestry or the loaded native rig's resolved
indexed `rod` binding. `Machine.readPartBinding(partPath)` and the verification
bridge expose `{partPath,bindingId,kind,motion,stationIndex}` directly from
`RestPart.binding`, never a guessed path-family set or another part's anchor.
For Rod20, the genuine `connectingRods` binding resolves station index19 and the
existing `rod` updater; the consumer records that read-only native metadata with
the independent source contour association. This is kinematic moving eligibility,
not observed source internal movement (`observedSourceInternalMotion` remains
`unmeasured`). Missing/unbound metadata or an unknown classification remains
unavailable for moving coverage. It cannot satisfy the fixed-point requirement or turn
many curve samples into distinct features for the distributed-landmark exclusion
floor. All original source views, selected physical inputs, clocks and coverage
requirements remain mandatory. The canonical Rocker observations already retain
all 48 late Rod20 curves; only Root's current native GPU run can establish their
errors or close the reported gaps.

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
Verify all six routes. Present the working implementation in a headed browser;
headless Playwright with screenshots or recordings is for automated checks.

Native WebGL landmark readback remains available for rendered-pixel measurements.
CPU projection alone is not final rendered evidence. Exhaustive raster, finite-line
and per-part certificate machinery remains diagnostic legacy work, distinct from
the scoped contour CHECK path above:
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
