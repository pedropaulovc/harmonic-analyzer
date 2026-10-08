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

Current authored observations live at
`content/v39-source/<videoId>.observations.json.gz`; generated browser tracks
live at `content/<videoId>.source-track.json`. The approved target is CAD v39,
raw SHA-256 `60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c`,
source commit `81539e53f5146c06a77541415bd79da673806d96`.
The original six corpora remain archived and hash-sealed, including measurements
not represented in current v39 records. Those records reuse a subset; migration
preserves that subset's source PTS, pixels, hashes, uncertainties and landmarks.
Further reuse requires exact exposure identity and a semantic current-feature
association, not just an unchanged anchor ID. Native identities, world coordinates,
cameras and physical constraints must be recomputed for the target geometry. Inherited
camera and mechanism seeds remain chosen/unobserved, including feasible hidden
settings. Old projection/GPU evidence, identity-translated packets under
`content/canonical-native/` and byte-exact originals from `bfde892a5` are
historical provenance, not current geometry qualification.

Current observations use exact-byte deterministic gzip (level 9, `mtime=0`,
no embedded filename). `canonical-native-evidence.py compress-observations`
accepts only the registered authored observation namespace, retains the source
JSON and preserves decoded bytes and numeric spelling without reserialization.
Consumers use gzip without a plain-loader fallback. Compression does not refit
or qualify geometry. The repository-root command and pinned uv producer
invocations are in [`README.md`](README.md).
Regeneration runs canonical `generate`, the Intro, Analysis/Synthesis, Spin and
Operation/Rocker producers, then canonical `generate` and `check` to bind outputs.
Canonical replay audits identity preservation; it cannot promote historical
evidence to current qualification. Operation/Rocker supports independent
`--video jfH-NbsmvD4` or `--video 4mBuyixt22U`; the default prevalidates both
videos before publishing either.

Half-open cut routing may admit a derived execution key one ULP from a cut only
when an actual source-owned exposure, shot, classification and views match.
Actual decoded PTS and exact authored requested clocks retain strict ownership;
neither is rounded into another shot. Authored source numbers remain unchanged.
The strict same-shot 0.5-second source-exposure
requirement is unchanged. Nine actual independently decoded frames supply
missing Operation fade exposures; existing samples and landmarks are preserved.
Their measured source facts do not make inherited pose guesses observed.
Complete approximate playback remains separate from source-fidelity acceptance.
Each 50/20/10/5 stage requires complete fresh source measurements; a partial run
cannot qualify the current release. There is no acceptance-attempt quota.

The [manifest](content/canonical-native/manifest.json) seals stored-byte and
original SHA-256 values, mapping revision/digest, numeric-token preservation and
historical-code snapshots. Compressed observation records also seal the decoded
payload separately from the stored gzip bytes. Old capture paths/plaintext hashes
remain immutable historical provenance, not current lookups. Nine snapshots seal
original capture inputs; three others seal prior identity-migrated producer
inputs at an explicit commit/path origin. Historical required producer records
retain those hashes even when the live hardware classifier changes.
The registered native inventory is also exact-byte authority; its web-scoped
`-text` attribute prevents checkout newline conversion from changing that seal.
Independent normalized current-consumer seals detect live drift. Ordinary source
production requires the approved live source tuple and sealed live code, scene
and native mathematics; archived inputs cannot satisfy that requirement.
Identity translation does not qualify current CAD, renderer or source-camera
correspondence. Native metadata/compatibility and actual rendered qualification
remain separate gates.

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

`fetch-model.mjs` first projects native node names and declared identity fields
through `cad/config/identity-migration-map.json`, preserving configuration and
instance qualifiers. Raw release bytes remain immutable. An independent check
rejects any other glTF JSON change or binary payload change.
`optimize-model.mjs` then performs exact buffer/accessor/mesh/image deduplication
and Meshopt 0.22.0 compression. Quantization, simplification, node pruning, index
reordering and instancing are excluded.
Image dependencies must be sealed in the GLB: embedded buffer-view and data-URI
image bytes are preserved. External image URIs are rejected, including companion
files, network URLs, `blob:` and `file:` references; optimization must not depend
on ambient files or fetched image content.
The optimizer fully decodes the canonical intermediate and output and compares
semantics bit-exactly per named drawable; compression and sharing must not change
geometry, material, transform or canonical component identity. These two checks
are separate from geometry acceptance and measured source fidelity; neither is
established by successful projection or optimization.

Raw exports are cached as `.vite/model-source/<rawSHA>.glb`, outside `public/`.
Only `public/models/ha-harmonic-analyzer.glb`, the optimized representation, is
published. Both model files remain untracked. A fresh checkout without an asset
must retain the supported missing-model UI.

Tracked `content/model-representation.json` uses schema and pipeline version 2.
It pins the raw native source commit and SHA-256, authoritative identity-map
SHA-256, canonical intermediate SHA-256, renamed-node and total-node counts,
and actual optimized SHA-256, byte count, semantic digest and codec.
Its `pipeline.steps` is exactly `['native-identity-map', 'exact-dedup', 'meshopt']`.
The browser imports this record at build time, checks the raw, map and canonical
associations against independently generated `MECHANISM_DATA`, then hashes the
fetched optimized bytes. There is no runtime identity alias or version-1 shim.
A public manifest is not a trust authority. Native observations and their model
SHA remain tied to the raw export. Runtime `observedSha256` identifies the actual
optimized bytes; explicit `sourceSha256` identifies the native association.
Raw, canonical and optimized hashes must not be substituted for one another.

The browser, offline verifiers and ordinary Python source producers use the
reviewed, tracked representation record as their live approval authority.
`approved-model.mjs` applies the same strict v2 validation for the Node verifiers
and the Python producer gate; expected identity is never inferred from
mechanics-data's own claim. Generated native provenance must independently match
its raw, map and canonical fields. Retained historical source packets identify
the earlier raw export and cannot qualify the approved v39 scene. Current
tracks require regenerated model-bound inputs; compatibility alone supplies no
source-fidelity qualification.
Analysis/Synthesis repeat native and retained numerical checks at build time;
in-process model-label replacement cannot approve earlier native calibration.
The producer supplies its executed-module census to the shared live seal gate.
Whole-pair construction and derivation finish before either output is published.

For a release already pinned with matching canonical metadata, the command
`npm --prefix web run fetch-model -- /path/to/raw.glb` validates the existing raw
pin, projects and optimizes the model without rewriting historical evidence.
Missing or mismatched projection provenance forces metadata regeneration and
native compatibility checks, even when the raw release is unchanged.
With no path, the command uses `cad/out/gltf/ha-harmonic-analyzer.glb`.

A future actual CAD release requires both approved identifiers:

```sh
npm --prefix web run fetch-model -- /path/to/new.glb --source-commit <full40hexapprovedCADcommit> --source-sha256 <approvedraw64hexreleasehash>
```

The commit is a full 40-hex CAD revision and the hash is the approved 64-hex raw
release digest, not the optimized digest. Neither flag alone authorizes adoption,
and naming the current source commit cannot approve arbitrary replacement bytes.
`scripts/released-models.json` is the sole known release commit/raw-digest table
for the JavaScript importer and Python exporter. Both directions are pinned:
a known commit requires its exact raw bytes, and known raw bytes require their
exact commit. The importer rejects a conflicting pair before identity projection
or optimization.
The command archives the exact matching CAD revision for the parameterized
`export-mechanics.py`. Original module filenames are resolved through the CAD
identity map without rewriting the archived source or installing module aliases.
Archived-source provenance uses POSIX repository-relative paths on every host.
Both exporters disable Git's `core.autocrlf` for the archive command, preventing
its native Windows newline conversion of released source bytes. Imported-source
census and telemetry ownership use the resolved snapshot root, including when
the temporary directory is reached through a symlink or junction.
The exporter checks canonical native paths against that revision's rest geometry
and mechanical parameters, then stages metadata and optimized publication.
Telemetry providers loaded from that temporary archive are flushed and closed
before it is removed, including after failed imports or metadata writes. Cleanup
errors remain visible; unrelated process handlers are left untouched.
A missing commit, incompatible mathematics or a refused release preserves the
last working assets. No invented release sidecar supplies approval or fidelity.

Before publication, new-source adoption checks the archived CAD against the
actual immutable exports/functions in `kinematics.ts`: channel count/order,
physical tooth ratios, cone reduction, paper-chain/reducer/feed pitch and senses,
and total signed feed. Magnifier minimum/built/maximum ratios remain checked.
Mounted chain paths retain all 68 native links. Sag/radius brackets, solved loop
length and arc closure use the archived numerical bounds, with explicit refusal
checks that remain active under Python optimization.
The nib rest is the raw marker-origin world datum `magnifier.penRestMm`, checked
against the archived assembly's `MARKER_POS` within 0.002 mm. It is distinct from
the rod-wire endpoint `penWireBottomMm`. Runtime uses that nib XYZ datum and adds
only the signed global-Y hanging-run payout.
The gate executes the staged magnifier solver at negative, positive and zero
summing angles, comparing tangent/contact, free length, wheel angle, payout and
nib translation with an independent bisection control. Unsupported mathematical
changes are refused before live assets are replaced; the nib check retains its
0.002 mm tolerance. Geometry, rest, spring and setup data may change; proportional
magnifier geometry is allowed when its ratios remain compatible.
Only an already matching raw, map and canonical association can skip native
metadata regeneration; raw-release equality alone is insufficient.

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

The magnifier exporter also requires the approved raw model and exact CAD revision:

```sh
uv run --isolated --no-project --with-requirements web/scripts/requirements-model-export.txt python web/scripts/export-magnifier.py --source-commit <approved-full-commit> --model <approved-raw.glb> --expected-model-sha256 <approved-raw-sha256>
```

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
The approved v39 platen carries its rack, paper, two clips, fourteen fillister
screws (four clip and ten guide), eight separate low guide-lock screws, two
guides and four guide locks as one 33-part group. Its eight lock screws are not
additional fillisters. The 19-part crank rig includes the keeper chain and link,
seat washer and two drive pins, bonded grip ferrule and butt cup, and anchor
screw. These attachments follow the released assembly mates at
`81539e53f5146c06a77541415bd79da673806d96`
(`build_paper_drive_assembly.py:2185-2476`;
`build_drive_train_assembly.py:5464-5501,5695-5745,5785-5795`).
Canonical paths come only from the authoritative CAD identity map.

The paper train has two distinct rigid rotating groups: nine knob/collar/shaft
members rotate together about axis K, while six disc/feed/hub members (including
three off-axis screws) rotate together about stud S. The Ry180 feed sleeve is
locked to the disc and shares its world +Z spin, not its reversed local axis.
The hanger, latch and pivot support remain fixed at their authored latched
pose; the installed pivot disc spring is not a swept-wire deformer. All 68
native chain links retain their released rest transforms and follow the
source-derived planar display law. Source:
`build_paper_drive_assembly.py:1936-2004,2478-2844` and `_chain.py:154-185`
at the same approved commit. A platen datum reset translates the carriage
without winding either gear group; frame-mounted hardware remains fixed.

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
`ha-harmonic-analyzer/ch-channel/ch-rocker-arm-1..20` paths. All twenty native rockers lack
these features. This approval is not a promise of a future CAD match.

`nativeGeometryAssumptions` permits at most one of each exact declaration and
rejects duplicate identities, additional features and other native families.
The HUD distinguishes the rod-head assumption from the lower-rocker exception;
reports and visibility bindings retain the exact records. Neither declaration
establishes whole-part correspondence or makes unavailable source data matched.
Original hole contours remain diagnostics, not fabricated source pixels, native
holes or textures. Native inventory integrity, all other features, pose and
motion remain required. The coarse image tolerance below replaces the former
38.4-source-pixel limit; timing remains bounded by 0.5 seconds.

## Coarse synchronization and demo plan

The current approved target is **50% of source frame width across all six videos**.
This is a maximum scored landmark-position error, not a percentage of coverage.
At 1920 pixels wide the limit is 960 pixels; video/model timing stays within
0.5 seconds. The 20%, 10% and 5% refinement stages are outside the current request.

Complete one coarse camera/mechanism matching pass across **all six** videos,
then present the working implementation in an actual browser demo. Do not
perfect one video while the others remain unavailable. Report measured coverage,
maximum errors and unresolved intervals; unmeasured or a passing subset is not
an all-six stage-50 pass. Manual operation, original-media audio state and visible
compact playback retain their existing requirements.

### Runtime tracks

Reuse the existing official player, native scene, physical solver and camera/input
interpolation. Author compact per-video shot tracks with camera keys, complete
feasible physical inputs, discrete setup changes and source view layouts.
Cuts switch atomically; interpolation is confined to compatible continuous shots.

Decoded exposures retain strict half-open shot ownership. Sparse endpoint
sampling deduplicates nearby keys only within the same shot: an incoming cut key
must not suppress the real final outgoing exposure, even when their clocks are
adjacent floating-point values. Source timestamps are never rounded to merge them.

Unobserved inputs may be chosen feasibly and must remain labelled as chosen,
not historically recovered. No second solver, proxy geometry, fake visibility
certificates or arbitrary individual-part adjustments are permitted.

Held crank-pin clearance uses the hub's current posed matrix, including held
carrier displacement and axial travel, rather than its baseline matrix.
Shaft clearance remains a separate check. This validation neither moves authored
parts nor relaxes contact tolerances.

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
`content/canonical-native/<videoId>.chosen-camera-continuity.json` permission convention.
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
historical camera motion or a fidelity pass. All six videos retain the current
**50% / 0.5-second** target; other videos' framing policies are unchanged.

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

Synthesis's immutable historical
[automatic-motion packet](content/canonical-native/8KmVDxkia_w.automatic-motion.json)
and [evidence packet](content/canonical-native/8KmVDxkia_w.automatic-motion-evidence.json)
retain their original producer lineage in the SHA-addressed
`content/canonical-native/historical-code` archive. The original-native producer
is not a supported current-native regeneration command. These packets are inputs
to non-publishable historical receipt revalidation; current track generation
instead reads the strict `content/v39-source` observation records.
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
3D displacement is expected and does not test rocker movement. The camera and
CAD remain unchanged: the fixed far portrait view still mismatches the filmed
bank close-up. Neither timing nor rendered-motion proof qualifies source camera
or geometric fidelity.

Production playback does not require semantic source certificates for every one
of the 435 native drawables at every exposure. Native model identity, complete
inventory and coherent attached-part motion still matter. Offline source evidence
is separate from compact runtime tracks; full decoded-frame observation corpora
are not a prerequisite for displaying an honestly labelled approximation.

#### Bounded Analysis motion authority

The retained Analysis motion and chosen-gauge packets below are immutable
historical evidence, not canonical outputs regenerated by the current checkout.
Their original producer bytes remain in the SHA-addressed historical-code archive;
the original-native bank extraction and gauge CLIs are retired from `scripts/`.
[`6dW6VYXp9HM-visible-crank-extract.py`](scripts/6dW6VYXp9HM-visible-crank-extract.py)
still produces private original-MP4 source-pixel receipts without native-model
association. The supported bank-controls diagnostic likewise copies retained
source evidence to private output, never canonical content.
`HistoricalReceiptRevalidator.revalidate_receipt()` consumes sealed historical
packets; ordinary
[`generate-analysis-synthesis-source-tracks.py`](scripts/generate-analysis-synthesis-source-tracks.py)
generation reads only fresh current observations and revalidates current live
authority before build/publication. Neither private diagnostic flow approves
source fidelity or regenerates the retained canonical packets.
The crank's [motion packet](content/canonical-native/6dW6VYXp9HM.visible-crank-motion.json)
records clockwise source motion at 0.90..0.98 turns/second over full cycles,
then the actual bottom hold, within 79.8130667..86.6866 seconds.
Source-native sign and absolute home remain `null`. The separate
[chosen gauge](content/canonical-native/6dW6VYXp9HM.visible-crank-gauge.json) applies
`nativeT = -relativeT + 0.711801723` while preserving the initial bank pose.
Actual native crank projection under the existing camera gives normalized
projection-angle RMS 9.19 degrees and maximum 11.34 degrees. This chooses an
integration gauge without establishing historical physical home or qualifying
the camera.

The bank's [automatic-motion packet](content/canonical-native/6dW6VYXp9HM.automatic-motion.json)
uses the frozen [motion controls](content/canonical-native/6dW6VYXp9HM.motion-controls.json) for
112.3122..119.0856333 seconds. It advances effective cumulative `T` by
3.890576427 turns with twenty constant driving-shaft phases and amplitudes,
retaining the first chosen complete hidden setup. These phases are not rocker
deflection angles. Both signed physical alternatives remain possible; neither
phase nor cadence transfers across cuts.

Authority is confined to `analysis-16/main/native` for the crank and
`analysis-22/bar-bank/horizontal-mirror` for the bank. Unmeasured same-shot
margins hold the nearest new input through the real cut: the crank shot spans
79.4460333..87.0202667 seconds and the bank shot ends at 124.4910333 seconds.
There is no cadence extrapolation or blend back to the old drive at the measured
endpoint. Outside those exact shot/view/presentation scopes, existing input
paths remain intact. Packet facts are authoritative; generated metadata labels
the drive chosen/approximate. Cameras and CAD are unchanged, and source camera
and geometry fidelity remain unaccepted. Native motion evidence does not
establish source spatial alignment or acceptance of all twenty rendered rockers.

Required coverage includes every retained video's corresponding machine views:
close-ups, moving mechanisms, insets, mirrored views, photographs and montages.
A difficult view does not become exempt because it cannot yet be matched.
Intervals without a corresponding machine may retain the preceding pose.
Unsupported required intervals remain explicit in the UI and reports.

Count the machine views actually visible in the footage. Synthesis's
presenter-to-spin edit moves one machine image; it uses one native view with
source-informed principal-point/FOV keys. Its coarse framing remains unmeasured.
Actors and formula graphics stay in the original player.

### Coarse measurement

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

Per-video diagnostics remain incremental and repeatable, without an acceptance-run
quota. The current collection gate is all six pages at **50% / 0.5 seconds**,
followed by the browser demo; no finer-stage certification is queued.
Per-video and aggregate reports stream their complete existing JSON evidence
with bounded serialization memory and atomic publication. Ordinary serialization
or I/O failures before publication preserve the previous complete report; no
fsync or power-loss durability guarantee is made.
Saved failure reasons retain the actual serialization or filesystem cause and
any temporary-file cleanup failure, alongside the output-path context.
On a failed coarse pass, correct the worst source-visible discrepancy and measure
the affected shot before rerunning the collection. Escalate actual missing
geometry outside approved exceptions rather than hiding it with a camera warp
or an occlusion claim.

The actual unscoped stage-50/local checkpoint `4cfeaee9373d6e78305e39390f2cc608c12f9aaa`
selected all mandatory keys but remained unavailable: only 1122 of 4564 required
samples contained any measurements, and 1075 passed their full required-sample
checks. The [README results table](README.md#fidelity-and-verification) retains
per-video coverage and measured pixel/clock maxima; sparse measured maxima are
not whole-video bounds. Independent CHECK gaps, actual Analysis spring-bound
refusals, strict compact-playback failures and Analysis/Spin native decode errors
remain in the original reports. A separate fresh-page original-media smoke
passed bounded manual/Restore/compact controls on all six pages, without clearing
those collection failures or granting footage acceptance. No optional native
eligibility, finer stage or per-drawable certification was run for this checkpoint.
After a source correction, preserve the frozen measured head and compare exact
track/observation/dist bytes separately; new-head runtime proof is a new receipt,
not a renamed old measurement.

### Browser verification

Exercise the original visible audible player and use its actual media time,
not two aliases of an application clock. Seeking, buffering or unavailable media
cannot provide timing evidence. Check deterministic seek/follow behavior and
pause/manual/resume transitions against the actual rendered scene.

Playback receipts cover every source view that contributes native colour and
require at least one current completed draw. A zero-opacity crossfade layer has
no draw receipt; any positive opacity still requires fresh pose, clock and shared
revision evidence. Failed playback remains failed even if a later real native
seek establishes the strictly paused state needed for independent measurements.
After seeking away from actual EOF, the local player publishes the settled native
state on `seeked` only when it changes; a paused getter and the HUD must agree,
without aliasing ended. Unchanged paused scrubs must not interrupt ongoing manual
crank motion through a redundant state callback.

Verification-only native diagnostic leases own the paused selected source state.
Diagnostic publications use detached playback banks and validation caches, sharing
only immutable compiled observations and synchronous production preparation math;
ordinary follow, review and media callbacks never read candidate publication banks.
Real playback/clock, route, layout or manual intent supersedes lease ownership.
Before that intent is consumed, the real frame and renderer/probe resources resume,
including capture-phase camera input and before compact resize or mode guards.
The initiating slider value is not overwritten by a saved HUD refresh.

Stale operations and callback results reject without replacing the newer owner.
The guarded context exposes no live viewer, machine, input or provenance handles.
Serialized snapshots and native target callback records are detached data; retaining
one cannot mutate a newer source owner after the scoped method expires.
Transactions expire on synchronous throws as well as asynchronous completion.
Returning an outer callback with a publication still pending refuses immediately:
it does not drain work that may depend on the outer result, and late cleanup cannot
restore over a later lease. Between publications, input, completed draw, camera,
canvas and probes again describe the same real frame under the same lease resources.
Publication probes return to null/null; only outer release restores the exact saved
normal probe identities.
Receipts distinguish `superseded` with a refusal reason from exact unchanged-state
`restored`; original callback causes and independent resource-cleanup failures stay
visible. New-owner rendering/errors remain on the ordinary fail-closed path, not
diagnostic-cleanup aggregation. A failed frame restoration clears advertised source,
physics, layout and draw receipts, disables native capture and refreshes the HUD
without overwriting a superseding input event. Independent resource cleanup still
runs. Locally created nested cleanup aggregates retain the original callback cause
and first error rather than hiding it inside another wrapper.
Exact `restored` status requires every required frame restoration to succeed.
A frame-restoration failure stays latched for the lease even if a later draw succeeds;
a separate resource-cleanup refusal may retain honest successfully restored frame flags.
Actual native context loss and a real descriptor cleanup refusal exercise these
paths; they do not prove every solver/draw restoration failure or a naturally
occurring new-owner exception. An oversized RTX 3090 viewport clamped its backing
buffer and did not reproduce the alleged capacity-error trigger.

The verifier validates original-source authority before lazy shared GPU startup.
Shared readiness requires acquisition of server, browser, context and page, not
merely a truthy browser. A shared startup failure is one terminal verification
prerequisite, retaining the validated source identity and original stack while
closing acquired resources; it is not retried for each video. Missing originals
remain per-video prerequisites without starting GPU/server work. Successful
empty-census startup controls establish resource ownership only, not playback,
source measurement or fidelity. Uninduced context/page and startup-cleanup failures
remain static-only coverage.

Paused exploration must permit orbit, pan, zoom and mechanism operation without
advancing the source video. Compact mode retains the same visible usable player
at least 200 by 200 pixels, with advancing audio and working pause/resume controls.
Official-player checks use visible provider-accessible Play controls in the
layout actually served, not an assumed desktop chrome bar. Compact receipts
retain the clicked control's accessible name, dimensions and native-pointer proof;
this does not establish coverage of another provider layout. A real native
pointer click must still produce audible, advancing, synchronized playback.
Verify all six routes. Present the working implementation in a headed browser;
headless Playwright with screenshots or recordings is for automated checks.

Native WebGL landmark readback remains available for rendered-pixel measurements.
CPU projection alone is not final rendered evidence. Existing raster, finite-line,
contour, masking and per-part certificate machinery is diagnostic legacy work:
its historical results are preserved, but completing its entire pending queue is
not a prerequisite for this iterative delivery plan. If a measurement uses a
particular diagnostic path, that path's known correctness defects still matter.

Optional native eligibility classifies only
`selected-native-stage-pixel-exact-vertex-identity`. Its quantized pixel-centre
ray may hit an incident triangle yet miss the exact stored vertex class by more
than the unchanged 1e-7 m physical residual. The scoped refusal
`cpu-selected-pixel-first-surface-exceeds-exact-vertex-residual` is not a general
anchor visibility or validity verdict. Raw projection and pixel-centre offset
are retained; tiny nonzero offsets can pass, and corpus-wide practical
reachability has not been measured. CPU evidence must declare
`queried-ray-exact-vertex-identity`; absent or different scope refuses. Pixel
offset does not enlarge the tolerance, and a vertex ray never substitutes for
the selected pixel ray. Source/GPU approval remains separate and unresolved
when unavailable.


## Assets and rights

The source-v37 measurements, checksums and verification results below retain
their original snapshot identities. Current CAD identities are listed in the
[subsystem identity guide](../cad/docs/subsystem-identities.md).

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
calibration. The optimized-loader smoke does not replace the required current
camrod GPU recapture.

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
