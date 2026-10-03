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
`scene.ts` applies the physical pose to the lossless delivery representation of
the full native GLB.

The raw GLB hash and source revision must match the generated mechanical data.
The browser separately verifies the actual optimized bytes against the compiled
representation record before loading them with the Meshopt decoder. A rejected
load never enters the visible scene. Bindings resolve genuine native component
names; missing joints have a separate persistent warning and prevent complete
synchronization acceptance. Original geometry is not decimated, resized or
replaced with proxy parts.

The viewer generates a PMREM room environment once for image-based lighting.
The native steel and brass materials are fully metallic, so diffuse hemisphere
lighting alone leaves their surfaces dark. The environment contributes reflected
light only: its room geometry is not added to the machine scene or drawable
inventory, and native GLB geometry and materials remain unchanged. Temporary room
and PMREM resources are released after generation; the environment render target
is released with the viewer.

## Model delivery and release provenance

`fetch-model.mjs` invokes `optimize-model.mjs`: exact buffer/accessor/mesh/image
deduplication comes first, followed by Meshopt 0.22.0 compression. Quantization,
simplification, node pruning, index reordering and instancing are excluded.
Image dependencies must be sealed in the GLB: embedded buffer-view and data-URI
image bytes are preserved. External image URIs are rejected, including companion
files, network URLs, `blob:` and `file:` references; optimization must not depend
on ambient files or fetched image content.
The optimizer fully decodes source and output and compares semantics bit-exactly
per named drawable; compression and sharing must not change geometry, material,
transform or component identity. This representation check is separate from
geometry acceptance and measured source fidelity; neither is established by
successful optimization.

Raw exports are cached as `.vite/model-source/<rawSHA>.glb`, outside `public/`.
Only `public/models/harmonic-analyzer.glb`, the optimized representation, is
published. Both model files remain untracked. A fresh checkout without an asset
must retain the supported missing-model UI.

Tracked `content/model-representation.json` pins the raw native source commit
and SHA-256 alongside the actual optimized SHA-256, byte count, semantic digest
and codec. Its `pipeline.steps` is exactly `['exact-dedup', 'meshopt']`, in that
order. The browser imports this record at build time, checks its raw association
against `MECHANISM_DATA`, then hashes the fetched optimized bytes.
A public manifest is not a trust authority. Native observations and their model
SHA remain tied to the raw export. Runtime `observedSha256` identifies the actual
optimized bytes; explicit `sourceSha256` identifies the native association.
These hashes must not be aliased or substituted for one another.

For the current release, the single command
`npm --prefix web run fetch-model -- /path/to/raw.glb` validates the existing raw
pin, optimizes and stages publication without changing native mathematical
metadata or historical evidence. With no path, it uses the existing
`cad/out/gltf/` export.

A future actual CAD release requires both approved identifiers:

```sh
npm --prefix web run fetch-model -- /path/to/new.glb --source-commit <full40hexapprovedCADcommit> --source-sha256 <approvedraw64hexreleasehash>
```

The commit is a full 40-hex CAD revision and the hash is the approved 64-hex raw
release digest, not the optimized digest. Neither flag alone authorizes adoption,
and naming the current source commit cannot approve arbitrary replacement bytes.
The command archives the exact matching CAD revision for the parameterized
`export-mechanics.py`, verifies the new raw export's native rest/mechanical
compatibility, then stages native metadata and optimized publication. A missing
commit, incompatible mathematics or a refused release preserves the last working
assets. No invented release sidecar supplies approval or automatic fidelity.

Before publication, new-source adoption checks the archived CAD against the
actual immutable exports/functions in `kinematics.ts`: channel count/order,
physical tooth ratios, cone reduction, paper-chain/reducer/feed pitch and senses,
and total signed feed. It also checks magnifier minimum/built/maximum ratios and
the fixed `PEN_X`/`PEN_Y`/`PEN_Z` world datum from `magnifier.ts` with a 0.002 mm
tolerance. Unsupported mathematical changes are refused with a named parameter
before live assets are replaced. Geometry, rest, spring and setup data may change;
proportional magnifier geometry is allowed when its ratios remain compatible.
The same-current-release path skips native metadata regeneration and these
new-source gates, leaving the four mechanics/math file hashes unchanged.

Spring compatibility is checked against the actual immutable `scene.ts` deformer
and classifier expressions, extracted from its AST rather than a copied browser
formula. Source-derived channel and counter profiles include coil-end inset and
correction, coil/wire radii and free/maximum-length coil ends; the counter also
supplies its coil axis. Channel profiles additionally describe the native
transition polar handle/tangent, hook-eye centres and transition control points.
The channel transition recipe comes from the exact archived
`diag_build_9432K31.py` expressions/constants, with provenance recorded.
The gate permits dynamic stock dimensions, turns, catalogue lengths, force and
setup when the source shape agrees with the actual consumer; counter rigid
loop/transition geometry is not frozen. Only the existing tiny native solver
residue in free-length transition interior points uses a 1e-6 mm positional
tolerance; polar/handle and other comparisons retain their tight checks.

The direct mechanics-export invocation uses the same authority inputs and an
isolated uv environment, but is not a substitute for the staged release command:

```sh
uv run --isolated --no-project --python 3.13 --with-requirements web/scripts/requirements-model-export.txt python web/scripts/export-mechanics.py --model /path/to/raw.glb --source-commit <full40hexapprovedCADcommit> --expected-model-sha256 <approvedraw64hexreleasehash> --output /path/to/mechanics-data.ts
```

The requirements file pins only the exporter's minimal dependencies without
syncing the root SolidWorks project. `--model` is the raw native GLB;
`--source-commit` selects the exact archived CAD revision rather than the working
tree; `--expected-model-sha256` enforces its raw digest. `--output` selects the
metadata destination; the release command uses staged metadata rather than
publishing that output early. Existing tracks and capture-bound evidence for the
old raw model are stale after adoption and must reject source-following.
Compatible manual exploration is not recalibration; replacement needs new
model-bound evidence before any source-fidelity acceptance claim.

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
videos, then present an actual browser demo before refining to 20%, 10%
and 5%. Complete one coarse pass across the collection rather than perfecting
one video while the others remain unavailable. Each stage reports its measured
coverage, maximum errors and unresolved intervals; unmeasured is not passed.
All-six collection acceptance remains unmeasured and unaccepted at every stage;
the regional and CPU diagnostics below do not change that status.

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
remain linear. Outside the bounded Analysis motion scopes below, independently
fitted bank inverse cam roots continue on the nearest genuine branch before
interpolation. Both roots preserve the observed rocker angle but may change an
unobserved cam/rod orientation. The original rod bounds, CHECK pixels and
branch-choice audit remain required; phase history is not recovered.

Synthesis's [automatic-motion packet](content/8KmVDxkia_w.automatic-motion.json)
and [evidence packet](content/8KmVDxkia_w.automatic-motion-evidence.json) are
produced by
[`generate-8KmVDxkia_w-automatic-motion.py`](scripts/generate-8KmVDxkia_w-automatic-motion.py).
They bound the rocker bank to **105.980875..124.4159583 seconds**, with 410 native
knots and unsigned cumulative drive of 28.744620749 turns. The mean
1.559234652 turns/s cadence uses published-video time, including the source's
4× playback; runtime must not divide it by four. The selected
`bank-direction-+1` branch is explicitly chosen because historical physical
direction remains unresolved.

Apply this input only to rocker-bank/main/native full-canvas unwarped views.
Hold the nearest new input through unmeasured same-shot slivers until the real
cut. Preserve all twenty constant common upper phases as a chosen prior and
retain the existing hidden amplitudes/setup as unmeasured feasible choices.
The existing native constraints remain authoritative: shaft phase for channel
`j` is `(T - driveCrankOffsetTurns) * (20 - j) * pi / 40 + phase[j]`.
These are driving-shaft phases, not rocker deflection angles. The lower-crank
**270.35..271.23-second** interval has `phaseMatchQualified: false` and supplies
no runtime motion; neither cadence nor phase continues across a cut.

Conditional actual-metal controls cover **18 held-out exposures at H20**
(maximum 26.50 px) and **17 pixel/feature-held-out exposures at H1**
(maximum 9.43 px); H2–H19 remain unmeasured. The packet's typed
`physicalCHECKHoldout` authority is checked against the actual exposure sets:
H20 CHECK exposures are disjoint from annotation FIT, while all H1 CHECK
times overlap annotation FIT. H1 cross-feature physical pixels stay out of
cadence and H1 pixel-gauge objectives; they are not exposure-held-out controls.
Their scope does not establish actual rocker-mesh GPU motion, full-scene
correspondence or camera qualification. Continuous original-video/native
playback over **105.96..124.45 seconds** recorded 444 media frames and 153
completed draws, with no waiting, stalled, pause, error or seeking events and
maximum media-to-completed-draw skew of 52.690 ms. All twenty native shaft phases
obeyed the formula with zero-radian error while phases and amplitudes stayed
fixed. Separate time-bound native GPU captures at **106.5, 113.5 and 118.5
seconds** retain all 435 drawables and show all twenty named rocker-arm meshes
visible, with changing raster extents and contours at the same camera.
The ordinary twenty landmark anchors are static structural points; their zero
3D displacement is expected and does not test rocker movement. Those historical
captures used the old far-portrait camera; CAD and the 410-knot cumulative clock,
4× cadence, chosen +1 physical sign, phases, amplitudes and setup remain unchanged.

The [bank-camera packet](content/8KmVDxkia_w.bank-camera.json),
[FIT evidence](content/8KmVDxkia_w.bank-camera-fit-evidence.json),
[CHECK evidence](content/8KmVDxkia_w.bank-camera-check-evidence.json) and
[CHECK packet](content/8KmVDxkia_w.bank-camera-check.json) are produced by
[`8KmVDxkia_w-fit-bank-camera.py`](scripts/8KmVDxkia_w-fit-bank-camera.py).
The new camera is held only for rocker-bank/main/bar/native, full 1920×1080,
opaque, no-warp exposures **2540..2983**. The actual cut at native 2984
(124.457666667 seconds) is excluded. FOV **6.021955 degrees** and weakly constrained
depth/focal choice are source-informed choices, not recovered camera history.
Thirty FIT observations at 2541/2589 use physical gray terminal-bevel upper-edge
midpoints; the camera was frozen before viewing/measuring the 38 CHECK observations
at 2580/2640/2820. These are pre-epoch measurements. Original actual GPU BEFORE under the old far-portrait camera
has CHECK RMS **587.12994 px**, maximum **778.9835 px**. Actual GPU marker AFTER
has RMS **17.5404813344 px**, maximum **35.8075760140 px**; adding 6 px source
and 0.848528 px native localization uncertainty gives an inclusive
**42.6561041514 px** bound. Keep the old H20 exposure-held and H1 feature-held
controls separate; these new checks do not extend their authority to H2–H19.
Depth-off marker projection is not a visibility certificate. A pre-epoch 25-frame
direct native-surface witness observes the existing `gl.readPixels` result after
the original native call, identifying its buffer by an exact full-435 per-ID
pixel-histogram match to the normal native probe. All 38 Synthesis CHECK centres
have the depth-tested correct rocker part ID (zero nearest-own-surface distance).
For Analysis's 386 CHECK features, 283 centres have their own part ID and all
386 have a correct own-part native-surface pixel within 1.2 source pixels,
inside the actual marker-plus-surface uncertainty. No source code, rendering
or pose is changed; hooks and anchors are restored afterward. This witnesses
actual native projection-surface neighborhoods, not exact source-feature
association, self-occlusion depth or whole-frame correspondence. Sparse contour
distances up to 38 px came from undersampled polylines, not surface absence or
camera error; nearest sparse own-contour sampling is never visibility authority.
Foreground gears/chain still mismatch in eye review. Neither whole-frame framing,
source camera, geometry nor any stage is accepted; CHECK does not retune FIT,
and the 414 unresolved/null source records remain.

The active [cam-rod draw-epoch world receipt](content/8KmVDxkia_w.camrod-draw-epoch-world-receipt-2026-10-03.json)
has SHA-256 `af7f5ddb5add9c7bdf04ad7cdc1444faa3b3f94eff780978cd68759305d42f7d`.
The [pre-epoch receipt](content/8KmVDxkia_w.camrod-current-world-receipt-2026-10-03.json)
(`4d61…`), immutable [historical probe](content/8KmVDxkia_w.camrod-sqpnp-probe-2026-10-01.json)
(`5a9f…`) and [raw historical receipt](content/8KmVDxkia_w.camrod-world-receipt-2026-10-01.json)
(`222d…`) remain unchanged. Archived renderer `7b28468c…` remains historical authority.
Current native scene SHA-256 is
`f16d8a0c03d37a67ccb9c4449b52f9fa0379ec02442aaa00ab09d25aff2e2eb4`.
It may reuse the older FIT-only camera only when the
new receipt matches source exposure 2398, original MP4 `a7ac177e…`, the same
complete physical input and draw, all nine actual native-local coordinates of
three FIT features with exactly zero delta, and all ten current runtime/descriptor
file hashes. The actual downloaded optimized model SHA `ad5c2592…`
(38,975,844 bytes) must match its descriptor and distinct raw-source association
`2280bfa6…` at revision `1268c23d…`. Compiled actual-module evidence does not
establish model byte identity. No historical receipt is rewritten or bypassed,
and no CHECK pixels select the pose. This bridge proves only three-FIT world
compatibility, not geometry, camera or stage acceptance.

The current capture uses original source frame **2398**, decimal PTS
**100.016583**, the same complete historical chosen input, and actual global,
physical and marker epoch **8**. All nine original FIT world coordinates are
exactly equal. The actual model GET is `ad5c2592…` / **38,975,844 bytes**;
that receipt's compiled JavaScript is `d90d08c903d198ab021a1082d7b84b1faf5329e5bbcdfbfb2ad31e2df469f0e5`
/ **1,042,881 bytes**. Analysis/Synthesis canonical generation succeeds with
this new receipt, without promoting a source stage.

A later actual normal-route RTX 3090 capture uses compiled GET SHA-256
`e0168324dc0c88e3e11693a81d28ba116159c54a0f8c7451dca45c53ef78a027`
(`index-DQ4z1uzl`, **1,042,881 bytes**). Its 14 requested source exposures cover
Operation **2826/2847/2877/2907/2937/2967/2989**, Rocker **0/24/144/23976**,
Intro **809/2132**, and Spin **3452**. Actual native visibility retains 435 drawables;
pixel/world receipts share the completed epoch, with zero page errors and original
MP4 clocks within 1 microsecond rounding. All six Intro macro views and all nine
Spin views, including mirror, inset, paper, book and guide, remain present.
Private evidence is `web/.vite/source-fidelity-final-normal-route-20261003.json`.
After the catalog/CLI corrections, another actual RTX 3090 normal-route run
completed the same **14 exposures / 27 views** in **24.42 seconds**, with zero
page errors, all 435 drawables per view, same completed epochs and original-media
clock error within 0.5 seconds. Its HTTP200 compiled GET is
`cbf063c3e0cebecc7c647b4734e064e7a724d1180d771c4c5c39ee409820020a`
(`index-tJXzrUdU`, **1,042,881 bytes**). The report preserves actual canvas CSS,
bitmap and DPR in `web/.vite/source-fidelity-review-corrected-normal-route-20261003.json`.
The earlier `e016…` report remains immutable. Neither run is continuous-window,
all-six collection, first-surface or source-stage acceptance.

Raw projected-point diagnostics give Operation maximum **31.899736747 px**
(RMS **14.26..14.93 px**) and Intro809 maximum **32.360778730 px** /
RMS **11.45414636 px** across 14 points (7 FIT, 7 CHECK). They retain Operation
source losses **17/0/8/12/15/15/20** and do not qualify source-physical association,
camera/body correspondence or CHECK independence. Eye review still finds the
Intro macro orientation/body/pen association mismatched; Rocker foreground
gears/chain/frame dominate the unqualified source left shank. Spin's nine runtime
views do not establish source image-card/camera/body correspondence. These scoped
captures do not establish a source stage or global camera impossibility/CAD absence.
The actual corrected-bundle `measureFrame` consumer smoke retains Operation's
losses and Rocker's **3/5/5/40** losses (the final 40 also has one unavailable
CHECK-coverage obligation). Point-only passed rows at Operation2847/Intro809 do
not qualify source frames or stages. Intro2132 has no exact compact frame and
remains unavailable without borrowing; all nine Spin views remain unavailable
to this landmark consumer because no observed landmarks were supplied. The smoke
does not enrich a contour census. Private evidence is
`web/.vite/review-corrected-source-consumer-smoke-20261003.json`.

`NativeEpochViewer` exposes its existing `drawEpoch` as captured `drawRevision`.
`renderViews` returns the actual completed epoch and supplies the reserved epoch
as its callback's third argument. Main records the completed native epoch in
global and physical `sourceDrawRevision`; incomplete or camera-invalidated batches
refuse captured evidence. The contract does not change geometry or mechanism math.
An actual RTX 3090 normal-route control completed two full **435-drawable** draws
at the same **100-second** time, epochs **10→11**. Pixel, world, visibility,
physical and global receipts agree; the retained older native ordinal is distinct,
with zero page errors. The `ff57` baseline completed epochs **3→4**, but its capture
API carried no epoch. This does not claim that the baseline public reader returned
stale pixels.

A separate actual RTX 3090 current-module failure control completed epochs
**4→5**, then drew a real first view in reserved epoch **6** before a caller throw.
During the second callback and after the catch, world/pixel reads were null and
visibility was stale with null `drawRevision`; recovery completed epoch **7**.
An actual `beforeView` camera application invalidated reserved epoch **8→9**
and threw `Viewer draw was invalidated by beforeView`, with unchanged model pose
and complete input. Reads again refused/staled, and recovery completed epoch **10**.
The partial batch advanced native frames **40→44** through **246 draw calls**,
with GL error zero. Actual delivery bytes matched and all 435 native drawables
remained present, with zero page errors; the viewer was disposed afterward.

This private control uses runtime-only HOLD51/camera at 100 seconds, not original
source footage809 or a source-fidelity measurement. Four unchanged native
frame-cross-screw local anchors provide its readback controls. The complete
222-anchor historical HOLD resolution has **74 affected landmarks across six
old mesh-child paths**. Exact raw/decoded-delivery primitive comparisons identify
Three GLTFLoader fallback names as the cause: raw meshes 139/141/142/264 map to
delivery meshes 16/18/19/100 after deduplication. All ten affected primitives have
ordered position/index byte equality; all 429 named nodes, transforms and material
tables are unchanged. Canonical observations have zero affected top-level anchor
references; 849 Intro/Rocker references are embedded historical censuses/exclusions.
Current HOLD producers need stable instance-root plus primitive-index identity,
without fallback-name parsing or guessed aliases. This correspondence does not
qualify source features or imply missing CAD geometry. Private runtime evidence is
`web/.vite/verification-output/native-draw-epoch-controls-20261003/actual-RTX3090-result.json`.

The retained `ff57f0a6…` RTX 3090 normal-route AFTER capture covers 29 frames,
retaining all 435 native drawables, zero missing bindings and zero page errors
with that same delivery/source association. Regional Synthesis/Analysis GPU
checks and the following continuous windows are pre-epoch actual captures,
not reruns under `f16d8a0c…`. They do not establish source-camera/geometry/stage acceptance.
The historical normal-route original-MP4 smoke records Synthesis
**105.96..124.45 seconds**, **443 source frames / 443 completed draws**,
maximum media-PTS-to-completed-draw **50.565 ms** and player-clock-to-draw
**17.037 ms**. Its cumulative `T` advances purely forward from 0 to 28.6878.
Analysis **119.1..124.44 seconds** records **160 source frames / 160 draws**,
maximum media-PTS-to-draw **44.955 ms** and player-clock-to-draw **17.416 ms**,
with 71 distinct forward steps and 66 return steps: `T` peaks at 5.8111 and
returns to 0.4758 by the last captured frame. Both keep all twenty shaft-phase
law errors exactly zero radians and source phases/amplitudes/setup fixed.
Only a playing event occurred in each measured continuous window; there were
no waiting, stalled, pause, error or seeking events within those windows.

Separate actual UI checks seek to Synthesis 113.5 and Analysis 121.5 seconds,
pause into exploration, open Mechanism Controls and apply keyboard ArrowRight:
physical crank turns change **11.2020579→11.203** and **4.741108→4.742**,
respectively. Mouse orbit changes the camera quaternion; Restore video pose
returns the exact original chosen crank, and Play resumes `following-video`.
Both compact original video elements measure **222×200 pixels**; their clocks
advance over 0.6 seconds while model draws follow. Audio state is audible at
volume 100, with decoded audio bytes **37,059→338,611** for Synthesis and
**57,227→130,128** for Analysis. Page errors are zero. Private capture evidence
is `web/.vite/source-fidelity-playback-AFTER-20261003.json`.
An earlier helper attempt lacked focus on initially collapsed controls; fixing
that verification precondition required no production-code change, and its
partial Synthesis playback already completed 443 draws. These local-media
checks do not prove the official player, all six routes, camera/geometry or a
fidelity stage; approximation labels and full source-feature/whole-frame limits remain.

Production playback does not require semantic source certificates for every one
of the 435 native drawables at every exposure. Native model identity, complete
inventory and coherent attached-part motion still matter. Offline source evidence
is separate from compact runtime tracks; full decoded-frame observation corpora
are not a prerequisite for displaying an honestly labelled approximation.

#### Bounded Analysis motion authority

The source-specific producers
[`6dW6VYXp9HM-visible-crank-extract.py`](scripts/6dW6VYXp9HM-visible-crank-extract.py),
[`6dW6VYXp9HM-visible-crank-gauge.py`](scripts/6dW6VYXp9HM-visible-crank-gauge.py)
and [`6dW6VYXp9HM-extract-automatic-motion.py`](scripts/6dW6VYXp9HM-extract-automatic-motion.py)
produce the numerical authority consumed by
[`generate-analysis-synthesis-source-tracks.py`](scripts/generate-analysis-synthesis-source-tracks.py).
The crank's [motion packet](content/6dW6VYXp9HM.visible-crank-motion.json)
records clockwise source motion at 0.90..0.98 turns/second over full cycles,
then the actual bottom hold, within 79.8130667..86.6866 seconds.
Source-native sign and absolute home remain `null`. The separate
[chosen gauge](content/6dW6VYXp9HM.visible-crank-gauge.json) applies
`nativeT = -relativeT + 0.711801723` while preserving the initial bank pose.
Actual native crank projection under the existing camera gives normalized
projection-angle RMS 9.19 degrees and maximum 11.34 degrees. This chooses an
integration gauge without establishing historical physical home or qualifying
the camera.

The bank's [automatic-motion packet](content/6dW6VYXp9HM.automatic-motion.json)
uses the frozen [motion controls](content/6dW6VYXp9HM.motion-controls.json) for
112.3122..119.0856333 seconds. It advances effective cumulative `T` by
3.890576427 turns with twenty constant driving-shaft phases and amplitudes,
retaining the first chosen complete hidden setup. These phases are not rocker
deflection angles. Both signed physical alternatives remain possible; neither
phase nor cadence transfers across cuts.

The [continuation packet](content/6dW6VYXp9HM.bank-continuation.json) from
[`6dW6VYXp9HM-fit-bank-continuation.py`](scripts/6dW6VYXp9HM-fit-bank-continuation.py)
replaces the old freeze at `T = 3.890576427` after 119.0856333 seconds.
Actual raw GPU BEFORE contours of all twenty rockers were bit-identical over
late-shot frames. Continuation covers genuine source-native **3569..3730**
(**119.085633333333..124.4576666667 seconds**, 162 exposures), with the original
boundary retained exactly. One cumulative `T` describes the forward and return;
the twenty phases/amplitudes, setup and camera remain unchanged. The producer
retains 386 measurements and **414 unresolved/null records**, not fabricated
coordinates. The combined old/new authority has 365 native physical-input knots.

Typed holdouts separate **141 new FIT exposures**, **19 exposure-held CHECK
exposures**, and **3710 feature-held CHECK**. Exposure 3710's centroid informed an
early prototype, but its final corner pixels never enter FIT; it is feature-held,
not exposure-held. Pre-epoch actual GPU AFTER exposure CHECK (369 measurements) has RMS
**19.9944791878 px**, maximum **31.4816573134 px**; 3 px source plus 1.697056 px
native uncertainty gives inclusive **36.1787135883 px**. Feature CHECK (17
measurements) has RMS **15.4018384491 px**, maximum **21.1638031103 px**, inclusive
**25.8608593851 px**. Independent-corner BEFORE maxima are **223.12344 px**
(exposure) and **123.009496 px** (feature), explicitly **CPU hold projections**,
not actual GPU BEFORE pixel measurements. These limited moving-feature checks
do not qualify full geometry, camera or a stage.

Authority is confined to `analysis-16/main/native` for the crank and
`analysis-22/bar-bank/horizontal-mirror` for the bank. Unmeasured same-shot crank
margins hold through its 79.4460333..87.0202667-second shot. The bank no longer
holds at the old 119.0856333-second endpoint: only the final
**124.4576667..124.4910333-second** sliver holds to the actual cut, with no cadence
extrapolation or blend back to the old drive. Later `analysis-23` and its inset
through 139.806 seconds remain unchanged. Outside those exact shot/view/presentation
scopes, existing input paths remain intact. Packet facts are authoritative;
generated metadata and the GUI label the drive chosen/approximate. Cameras and
CAD remain unchanged for Analysis, and source camera and geometry fidelity remain
unaccepted. Native motion evidence does not establish source spatial alignment
or acceptance of all twenty rendered rockers.

Canonical generation succeeds for both videos: Synthesis **69 shots / 1,071
frames / 1,535 views**; Analysis **42 shots / 952 frames / 1,136 views**.
`coverageComplete` describes authored compact coverage, not measured fidelity:
stages remain **UNMEASURED**. The all-six-video 5% (96 px at 1920 wide) and
0.5-second contract, unknown source associations and native inventory remain intact.

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

`measureFrame` and `finishVideo` retain the required source-loss ledger.
Undeclared roles remain null; a loss cannot supply coverage or become an exclusion.
The verifier/playback follow-up gate executed **73 passes, zero failures/skips**
in **0.144 s**, including original-loss retention when census availability is null.
Before-fix controls failed the two loss cases and the census case. These software
checks do not supply source-fidelity measurements.

Per-video verification is incremental and repeatable, without an acceptance-run
quota. The all-video final gate retains all six pages and the 5%/0.5-second limits.
A coarse demo or a passing subset does not establish final acceptance.
On a failed stage, refine the worst source-visible discrepancy, rerun the affected
shot, then rerun the collection. Escalate actual missing geometry outside approved
exceptions rather than hiding it with a camera warp or an occlusion claim.

### Operation and Rocker source authority

Operation's [chosen seeds](content/jfH-NbsmvD4.source-seeds.json),
[observations](content/jfH-NbsmvD4.observations.json) and
[canonical track](content/jfH-NbsmvD4.source-track.json) retain Operation019's
actual original-MP4 source flow over **94.2942..99.76633333333334 seconds**.
The correction covers **164 exact exposures**, adding 15 to the original 149
distinct exposures (154 records). Original FIT/CHECK roles, provenance, pixels
and losses remain intact; non-019 frames are unchanged. Two actual original-image
correlation controls have zero difference; a displaced negative gives **-0.193**.
No historically CHECK-informed v3 camera/input candidate is imported. Source
flow does not qualify native rendering, source-camera history or mechanism inputs.
The canonical packet has **1,033 samples / 1,460 views / 144 shots**, retaining
90 source-loss declarations. Source time 135 seconds, frame 19451, remains
unmeasured. Chain, removable gears, disassembly, mirror, simultaneous panels and
pen remain required.
Operation's single authoritative catalog has **221 anchors**, including **188
genuine fragment definitions**. Orphan IDs are refused; duplicate fragment seed
copies no longer override the catalog. The source-generation gate executed
**63 passes, zero failures** in **33.638 s**; the before-fix catalog control
had three failures and one error. Existing camera/input choices are unchanged.

Rocker's [seed `cameraChoice`](content/4mBuyixt22U.source-seeds.json) is the clean
producer authority; `historicalCameraChoices` retains the body candidate as
provenance only, without fallback. The sealed `f87b4121…` direct cap/rim FIT-only
camera was evaluated on actual current **435-drawable / 1,078-input** CPU worlds,
with 20 rigid rockers and 30 cap anchors. The complete51 input is unchanged.
`postEpochCPUNativeForward` pins receipt `0d1d400b…`, executed graph `f15cf27e…`
and actual scene `f16d8a0c…`; the independent cap-transform delta is
**5.55e-17 m**. No new optimizer run or CHECK-driven winner selection occurred.

| Original FIT diagnostic | Count | CPU RMS before / after (px) | CPU maximum before / after (px) |
|---|---:|---:|---:|
| Cap pixels | 25,878 | 21.1155 / 11.7843 | 49.6469 / 26.8082 |
| Upper rim pixels | 60 | 22.2842 / 2.47564 | 36.6445 / 5.91268 |

The direct camera objective consumes FIT only, but the unchanged bank inherits
all twenty station extrema, including CHECK stations 1/5/9/13/17. This is
conditional camera authoring, not a new investigation-wide camera/mechanism
holdout. The historical balanced camera consumed all nine Rod20 CHECK observations
at frame0. All 85 frame0 observations remain CHECK, and all 14,004 original contour
roles remain explicit. The [canonical Rocker track](content/4mBuyixt22U.source-track.json)
has **1,085 samples / 1,043 views / 27 shots** and retains **8,448 unavailable**
source declarations. No post-choice actual GPU proof establishes full exterior,
materials, shank, left edge, linkage identity or whole-435 visibility.

### Intro physical support and first surface

The [eligibility profile](content/NAsM30MAHLg.calibration-eligibility.json) and
[native request](content/NAsM30MAHLg.native-eligibility-request.json) distinguish
stored vertex indices from physical camera support. Indices
**124/126/130/133/136/139** coincide at one apex and cannot supply six independent
FIT supports. FIT/CHECK physical coincidence refuses the fit before optimization;
true rank-three support reaches the actual camera optimizer. The dedicated
[`test_intro_feature_eligibility.py`](scripts/test_intro_feature_eligibility.py)
executed **3 cases, 3 passes, 0 skips** in **0.331 seconds** on its first post-fix
run. Missing `INTRO_RAW_NATIVE_MODEL_PATH` raises `RuntimeError`, without a skip.
`npm --prefix web run test:source:geometry` uses isolated uv with pinned
numpy **2.5.3**, scipy **1.18.1** and opencv-python-headless **5.0.0.93**.
The enrolled npm gate's initial three cases passed in **0.391 seconds**.
Its expanded seven-case gate executed **7 passes, zero failures/skips** in
**1.198 seconds**, covering three raw support cases and four public CLI
refusal/error-state cases without a private full435 test dependency.
The nested-native-metadata follow-up gate executed **8 passes** in **2.166 seconds**;
malformed code-hash metadata retains error rows rather than escaping as an exception.
Set `INTRO_RAW_NATIVE_MODEL_PATH` to the original raw `2280bfa6…` GLB,
as shown in the README. Missing or mismatched raw bytes fail the prerequisite;
the optimized public `ad5c2592…` model cannot substitute.
The public first-surface CLI refuses unknown pose/input fields and accepts no
per-part matrix overrides. Refusal/error rows preserve the exact request and use
nullable, unvalidated native identity when execution cannot establish identity.
The actual sealed CPU435 CLI packet evaluated **17 rays**, with **7 eligible**,
zero refused and zero error rows, preserving the original complete51 input.
Private evidence is `sealed-native-apex17-after-20261003.json`; these eligibility
results remain native CPU diagnostics without source or GPU acceptance.
A separate actual full435 CPU API-boundary control retained the real sealed-marker
positive and rejected the front-right C-frame occluder. Three removed detached
API calls raised `TypeError`, with native geometry unchanged. Private evidence is
`web/.vite/verification-output/intro-spin-20261003/sealed-ray-detachment-after-20261003.json`.
This proves the sealed Float64 complete51 state/API boundary, without extending
GPU or source qualification.

The exact historical `f20571861` static-producer blob (`8626bdf7…`) was run
against those same three raw-native cases: the coincident-apex and FIT/CHECK
coincidence cases failed at the actual optimizer sentinel; the true six-FIT /
two-CHECK rank-three positive passed. `INTRO_STATIC_PRODUCER_PATH` selects this
historical producer without hand-reverting a predicate.

A supplemental current CPU first-surface export uses the original HOLD809
complete51 chosen input, not the older pen variant differing in 28 scalar fields.
It contains all **435 drawables**, with **21 springs evaluated from their actual
GLSL AST/uniforms/attributes**, **6,741,474 vertices** and **16,888,236 indices**.
Actual nearest-apex facets **124/97/108/113** have residuals
**1.39e-16..1.38e-17 m**; additional positive facet125 is consistent with the
same physical apex. The 32 coincident stored indices **96..127** and their
incident triangles count as one point. Fifteen independent ray controls reject
adjacent/body/C-frame/v-block/screw/platen negatives at **4.65..110 mm**.
This is native CPU geometry conditional on original HOLD and the first-surface
guard. GPU pixels, source-camera/contact correspondence, historical inputs and
stage acceptance remain unqualified.

An actual RTX 3090 numerical comparison executed all **21 spring programs /
3,293,594 vertices**, with current code/program/attribute hashes checked. It
**fails** the unchanged **1e-7 m** CPU/GPU equivalence bound: GPU world Float32
maximum error is **3.273407359328867e-7 m**, with **407,744 vertices** outside;
GPU local Float32 followed by the exact current CPU Float64 world matrix gives
**3.0548974587765615e-7 m**, with **141,075 vertices** outside. Both failures span
all 21 springs. The CPU first-surface controls therefore remain CPU-scoped,
without a current full-geometry GPU equivalence proof, bound relaxation or exemption.
Private evidence is
`web/.vite/verification-output/current-native-exports-20261003/actual-RTX3090-current21-spring-numerical-comparison-20261003.json`.

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
CPU projection alone is not final rendered evidence. Existing raster, finite-line,
contour, masking and per-part certificate machinery is diagnostic legacy work:
its historical results are preserved, but completing its entire pending queue is
not a prerequisite for this iterative delivery plan. If a measurement uses a
particular diagnostic path, that path's known correctness defects still matter.

Contour sidecars join on original source SHA-256, same-format decoded
`sha256Bgr8` or `sha256Gray8`, native `frameIndex`, exact decimal PTS, shot and
ordered mapped view layout. BGR8 and gray8 hashes cannot alias each other.
The current decoder supplies no rational-clock fields; ambiguous decimal joins
remain unavailable. Missing, ambiguous, alias-conflicting or off-track rows remain
required unavailable measurements. A mandatory census cannot manufacture ready
interpolated source frames or synthetic dense compact curves.

For actual depth-tested part-ID partial-edge measurements, the bound is the
source-to-sampled-native maximum plus source and native localization uncertainties.
Masks, scissors, resolved warp, current completed epoch, selected camera and
complete input must agree. A `readPartBinding` wrapper or sparse projected contour
does not supply this authority. Original CHECK roles stay original CHECK, without
new independence; FIT diagnostics do not establish CHECK or moving coverage.


## Assets and rights

The current raw native GLB is 222,903,724 bytes with approximately 5.627 million
instance-expanded triangles. Its twenty exact-duplicate channel springs each
contain 147,248 triangles and contribute 52.3% of that triangle count. Measured
duplicate raw payload accounts for 102,076,512 bytes; two identical PNGs account
for a further 10,415,064 duplicate bytes. These source measurements are not
measured optimized savings.

Two current source-v37 imports produced identical optimized bytes:

| Representation | Bytes |
|---|---:|
| Raw native export | 222,903,724 |
| Exact deduplication | 61,672,576 |
| Meshopt delivery asset | 38,975,844 |

The measured overall byte reduction is 82.5145%. All 429 source nodes and 433
drawable instances are preserved. Exact sharing reduces mesh definitions from
324 to 141 and images from two to one, without reducing drawable instances or
instance-expanded triangles. Full decode comparison matched 222,538,856 bytes
exactly. The four native mechanics/math file SHA-256 values remained unchanged.

The raw SHA-256 is
`2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d`;
the actual optimized SHA-256 is
`ad5c259265be354fb25d208281301356d7587c6a2e508fce1a6cd29014a74719`.
The per-named-drawable semantic digest is
`b60baed017b499c6d48e8b5aeab3c2c19f2ad256c26c0bd8e17cb094b3b4a093`.
These are import/representation measurements, not a browser-runtime count,
frame-rate result or geometry/source fidelity acceptance.

A real headed Chromium smoke verified the 38,975,844-byte download against the
optimized SHA-256 above and the compiled raw association. It observed 435 runtime
drawables with zero missing bindings. At the same 106.5/118.5 camera, all twenty
rocker GPU raster records (pixel counts, extents and contours) matched the raw
baseline bit-for-bit. All twenty spring lengths changed independently; eighteen
visible spring rasters changed, while two springs were occluded.

Three continuous original-MP4 Analysis/Synthesis clips completed with 209, 205
and 444 frames and no stall, pause or error events. The maximum
video/completed-draw delta was 54.341 ms after explicitly excluding the initial
0.1-second startup period. This scoped playback/render smoke is not an FPS
improvement measurement or source-fidelity acceptance.

The 49 source regressions pass using a historical source fixture, not a new
renderer calibration. Production camrod's current-code guard still refuses the
old `7b28` scene receipt; no old receipt was rehashed or accepted as fresh
calibration. The optimized-loader smoke is delivery evidence; the separate
current cam-rod draw-epoch recapture above supplies the bounded world receipt.

All 33 model tests passed: 24 top-level tests and nine real-exporter negative
subtests. The actual exporter accepted compatible future geometry and refused
unsupported tooth-ratio, feed-pitch, feed-sign and six spring-profile changes
with named parameters before writing any live files. The archived source-v37
export checked 211 source files and 130 native rest conditions and passed the
enriched mathematical and spring-profile gates against the unchanged runtime.
A current raw reimport reproduced the optimized SHA-256 and 38,975,844-byte
size above; the production build also passed.

The website loads one optimized model and reuses geometry buffers during motion.
Exact sharing reduces buffers and cache duplication, while Meshopt changes
download encoding, not the instance-expanded triangle count. Frame-rate
improvement has not been measured. Source observations load per video.
Downloaded MP4s, decoded frames, screenshots and verification reports stay
outside tracked publication assets. The site embeds the originals through
YouTube rather than hosting their streams. The 2014 book's non-commercial
material must not enter a commercial website or campaign product.

The default static base path is `/harmonic-analyzer/`. `SIMULATOR_BASE` must be
consistent between Vite build and production verifier. Portfolio sequencing is
owned by the [project board](https://github.com/users/pedropaulovc/projects/1).
