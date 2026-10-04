# Harmonic analyzer video companion

Six engineerguy videos share an interactive view of the CAD-exported analyzer.
The original YouTube player sits in the model area's lower-right corner. Pause
for manual exploration, then orbit, pan, zoom, turn the crank or adjust the twenty
channels. Compact mode keeps the same visible player and its audio.

Website workstream status lives on the
[Harmonic Analyzer project](https://github.com/users/pedropaulovc/projects/1).
Implementation and fidelity limits are described in [`DESIGN.md`](DESIGN.md).

## Run locally

```sh
npm --prefix web ci
npm --prefix web run fetch-model -- /path/to/harmonic-analyzer.glb
npm --prefix web run dev
```

The model is a generated artifact, absent from a fresh checkout. Use the exact
raw CAD export identified by `src/mechanics-data.ts`; incompatible bytes are
rejected. `fetch-model` validates the current raw pin, performs lossless exact
deduplication and Meshopt compression, then publishes only the optimized GLB.
It also accepts the existing `cad/out/gltf/` export when no path is supplied.
The raw cache stays outside public assets under `web/.vite/model-source/`.
Missing models and failed YouTube playback produce visible errors.

The current imported release is **v39**, CAD revision
`81539e53f5146c06a77541415bd79da673806d96`, raw SHA-256
`60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c`.
Its native metadata, representation descriptor and public asset were published
transactionally. All six observations and source tracks have now been adopted
and generated under `content/v39/`; root `content/` receipts remain immutable
old-release history. Current native associations preserve required losses:
**Intro 16, Synthesis 16, Analysis 21, Operation 169, Spin 42, Rocker 0**.
All six remain unmeasured at the intermediate **50/20/10/5%** stages and strict
**2%** acceptance; successful adoption and generation are not source proof.

To adopt a future approved CAD release, provide both its full commit and raw
SHA-256 (not the optimized file's hash):

```sh
npm --prefix web run fetch-model -- /path/to/new.glb --source-commit <full40hexapprovedCADcommit> --source-sha256 <approvedraw64hexreleasehash>
```

The release command reads that exact CAD revision, checks native rest geometry
and compatibility with the website's fixed kinematics, magnifier and spring
deformer mathematics, and stages new native metadata and the optimized asset.
Compatible geometry, rest, spring, setup and released pen-datum changes are
supported; unsupported ratio, feed or spring-profile changes are refused with a
named parameter, preserving the last working assets. Missing revisions are also refused.
A current source commit does not approve arbitrary bytes.
Existing source tracks are stale for a new raw model and reject source-following;
manual exploration is not recalibration. See [`DESIGN.md`](DESIGN.md) for the
representation and provenance contract.

Playback can start while the model or source track loads. Source-following starts
automatically when both are ready; pausing retains manual exploration. Status
announcements exclude the running clock. Force readouts are physical calculations,
not source measurements.

Routes accept a slug or the corresponding YouTube ID:

| Page | Query |
|---|---|
| Intro / History | `?video=intro-history` |
| Synthesis | `?video=synthesis` |
| Analysis | `?video=analysis` |
| Operation | `?video=operation` |
| Machine spin | `?video=machine-spin` |
| Rocker arms | `?video=rocker-arms` |

The PDF page-by-page guide video (`rMHw9GCAtE8`) is excluded by user scope. It
has no route, observation file or verifier page; its MP4 and source intervals
are not acceptance prerequisites.

The video embeds use the official YouTube IFrame API. Downloaded source videos,
reference screenshots and the GLB remain untracked; the site does not host or
redistribute the footage.

## Fidelity and verification

The interactive mechanism uses CAD-derived eccentric cams, connecting rods,
finite rocker arcs, amplitude bars, twenty loaded extension springs, the counter
spring, wire and magnifier. It solves quasistatic torque balance. It does not
simulate tooth collisions, friction or inertia. The amplitude controls show CAD
station millimetres; calibration to the video's engraved measuring sticks is
not established.

Source-following tracks combine source cameras with complete feasible physical
inputs. Hidden settings may be chosen and are labelled unobserved, not recovered
historical settings. Playback distinguishes a working approximation from measured
fidelity. Unsupported required intervals remain explicit; intervals without a
corresponding machine may retain the preceding pose.

Analysis03's bounded interval **4.4044..7.307300000000001 seconds** and
Synthesis's presenter-to-spin interval **25.984291667..26.609916667 seconds**
opt in to chosen continuous camera framing at both endpoints. Position,
rotation, FOV and principal point blend only within compatible same-shot views;
Synthesis's existing front-camera position/rotation stay fixed while its chosen
principal-point/FOV keys reframe the single machine image. Cuts, layout and
discrete mechanical changes still hold the decoded exposure. This is unmeasured
source-informed framing, not recovered camera history or a fidelity pass.
The strict **2% / 0.5-second** acceptance limits and other videos' policies remain unchanged.

The optional `content/v39/<videoId>.chosen-camera-continuity.json` permission packet
pins source SHA, shot bounds, native coverage and unmeasured main/whole framing
evidence. No packet preserves the old policy. Analysis03 retains all 90 source
observation rows covering the contiguous native exposures 132..218. Synthesis's
presenter-to-spin retains 16 rows covering all 15 native exposures 623..637;
source cameras in both intervals remain null. Only the selected families bypass
the producer's generic 30-degree branch split; generated framing keys are not
new measurements. The Synthesis **25.98..26.54-second** scoped headless
demonstration does not qualify source matching or recover camera/mechanical pose.
Before Synthesis's existing single-main normalization, selected permissions
refuse original measured, partial-frame, mirrored, warped, composite, missing,
empty or unmapped views. Valid null-camera full-frame main or outgoing/incoming views
remain accepted; normalized main framing is checked afterward. Original retained
source layouts are not edited.
Regenerate either video independently with
`uv run --isolated --no-project python web/scripts/generate-analysis-synthesis-source-tracks.py --video 6dW6VYXp9HM`
or replace the video ID with `8KmVDxkia_w` for Synthesis.
Omitting `--video` still validates and prepares both Analysis/Synthesis outputs
before publishing either.

Analysis has bounded cumulative source-drive authority for the visible crank
(79.8130667..86.6866 seconds) and mirrored bank (112.3122..124.4576667 seconds).
The authoritative packets are
[`6dW6VYXp9HM.visible-crank-motion.json`](content/6dW6VYXp9HM.visible-crank-motion.json),
[`6dW6VYXp9HM.visible-crank-gauge.json`](content/6dW6VYXp9HM.visible-crank-gauge.json),
[`6dW6VYXp9HM.automatic-motion.json`](content/6dW6VYXp9HM.automatic-motion.json),
[`6dW6VYXp9HM.motion-controls.json`](content/6dW6VYXp9HM.motion-controls.json)
and [`6dW6VYXp9HM.bank-continuation.json`](content/6dW6VYXp9HM.bank-continuation.json).
The [continuation producer](scripts/6dW6VYXp9HM-fit-bank-continuation.py) replaces
the old late-shot freeze with one cumulative forward-and-return drive over
162 genuine source exposures (3569..3730), preserving the original boundary,
twenty phases/amplitudes, setup and camera. Only the final
124.4576667..124.4910333-second sliver holds through the actual cut.
Historical pre-epoch actual GPU AFTER corner checks give exposure-held RMS/max **19.9945/31.4817 px**
(369 measurements), and feature-held **15.4018/21.1638 px** (17 measurements).
Their inclusive uncertainty bounds are **36.1787/25.8609 px**, respectively.
The independent-corner BEFORE maxima **223.1234/123.0095 px** are CPU projections
of the old hold, not GPU measurements. Other shots, views and presentations
retain their existing paths. [`DESIGN.md`](DESIGN.md#bounded-analysis-motion-authority)
describes typed holdouts and limits; source camera and geometry remain unaccepted.

Synthesis's rocker-bank interval **105.980875..124.4159583 seconds** uses
[automatic-motion inputs](content/8KmVDxkia_w.automatic-motion.json) and
[source evidence](content/8KmVDxkia_w.automatic-motion-evidence.json), produced by
[`generate-8KmVDxkia_w-automatic-motion.py`](scripts/generate-8KmVDxkia_w-automatic-motion.py).
The source's 4× label describes published-video playback: mean cadence is
1.559234652 turns/s, with unsigned cumulative drive of 28.744620749 turns across
410 native knots. `bank-direction-+1` is an explicitly chosen physical direction,
not a recovered historical sign. Twenty constant common upper phases remain a
chosen prior; hidden amplitudes and setup remain chosen and unmeasured.

This drive applies only to the rocker-bank/main/native full-canvas unwarped view.
Unmeasured same-shot slivers hold the nearest new input until the real cut.
The lower-crank interval **270.35..271.23 seconds** is excluded
(`phaseMatchQualified: false`); cadence and phases do not transfer across cuts.
Conditional actual-metal controls cover **18 held-out exposures at H20**
(maximum 26.50 px) and **17 pixel/feature-held-out exposures at H1**
(maximum 9.43 px). H20 CHECK exposures are disjoint from annotation FIT.
H1 CHECK times overlap annotation FIT, but its cross-feature physical pixels
never enter the cadence or H1 pixel-gauge fit. H2–H19 remain unmeasured.
These old controls remain separate from the new camera checks. Historical native
GPU captures exercised all twenty rocker meshes at a fixed camera; the earlier
uninterrupted playback measurement was 52.690 ms maximum media-to-draw skew.
The bank now uses a [held source-informed camera](content/8KmVDxkia_w.bank-camera.json),
from the [camera producer](scripts/8KmVDxkia_w-fit-bank-camera.py), only for
native full-frame rocker-bank/main/bar exposures **2540..2983**, before the real
cut at **124.457666667 seconds**. Its narrow FOV and depth are chosen, not historical.
After freezing the camera from 30 FIT features, 38 independent CHECK features
at 2580/2640/2820 give actual GPU marker RMS/max **17.5405/35.8076 px**, versus
the original far-portrait actual GPU BEFORE **587.1299/778.9835 px**; the inclusive
uncertainty bound is **42.6561 px**. These measure physical terminal-bevel
upper-edge midpoints, not whole-frame framing. A pre-epoch 25-frame depth-tested
part-ID witness places all 38 Synthesis CHECK centres on the correct rocker
surface; Analysis places 283 of 386 centres on their own part and all 386 within
1.2 source pixels of its actual surface. This proves native projection-neighborhood
ownership, not exact source-feature association or self-occlusion depth.
Foreground gears/chain still mismatch; camera, full-scene geometry and stage
acceptance are not established.

The active [cam-rod draw-epoch world receipt](content/8KmVDxkia_w.camrod-draw-epoch-world-receipt-2026-10-03.json)
binds the current native renderer (`f16d8a0c…`) to a completed draw. Native pixel,
world, visibility and physical receipts share its actual `drawEpoch`; repeated
draws at the same media time receive different epochs. Incomplete or
camera-invalidated batches cannot supply captured evidence. The new receipt
(`af7f5ddb…`) retains all nine original FIT world coordinates exactly and all
435 drawables. It permits conditional reuse of the immutable FIT-only camera;
it does not qualify source geometry or camera history. The downloaded lossless
delivery SHA `ad5c2592…` remains distinct from raw-source SHA `2280bfa6…`.
The earlier receipt and the regional GPU measurements above remain pre-epoch
evidence; they are not a fresh GPU replay under `f16d8a0c…`.
A later actual normal-route RTX 3090 capture covers 14 requested Operation,
Rocker, Intro and Spin source exposures, with completed-epoch pixel/world
receipts, 435 drawables and zero page errors. Intro macro body/pen association,
Rocker foreground geometry and Spin whole-frame correspondence remain
unqualified. The full native CPU spring export also fails the unchanged
1e-7 m GPU-equivalence bound; CPU first-surface diagnostics remain CPU-scoped.

The historical `ff57f0a6…` normal-route playback probe of the original MP4 completed **443 source frames /
443 draws** for Synthesis (105.96..124.45 seconds) and **160 / 160** for Analysis
(119.1..124.44 seconds), with maximum media-PTS-to-draw skew **50.565/44.955 ms**.
All twenty shaft phases obeyed the physical law exactly, with fixed source
phases/amplitudes/setup; Analysis exercised both forward and return motion.
Both routes passed actual seek, paused keyboard mechanism control, mouse orbit,
exact chosen-pose restoration and resumed source following. Their compact original
players remained **222×200 pixels**, with advancing clocks, following model draws
and audible audio state with increasing decoded audio bytes. No page errors or
waiting/stalled/pause/error/seeking events occurred during the measured continuous
windows. This proves those local original-media scenarios, not the official
YouTube player, all-six-route runtime coverage or whole-scene fidelity.

Operation019 now retains exact original-source optical-flow measurements across
164 exposures, including 15 previously absent exposures. Original FIT/CHECK roles,
losses and the current chosen camera/input remain unchanged; the historical
CHECK-informed inverse-fit candidate is not imported.
Rocker arms uses a sealed direct FIT-only cap/rim camera evaluated on current
native CPU geometry. Cap FIT RMS improves **21.1155→11.7843 px** and rim FIT RMS
**22.2842→2.47564 px**. Its inherited bank inputs include historical CHECK extrema,
so this is conditional camera authoring, not a new camera/mechanism holdout.
Source exterior, whole-part visibility and GPU qualification remain unavailable.
See [`DESIGN.md`](DESIGN.md#operation-and-rocker-source-authority) for scope and maxima.

`npm --prefix web run test:playback` exercises eight synthetic runtime decisions
through Vite SSR, without a browser or GLB. `SOURCE_TRACK_MODULE` may point to
a historical source-track module for a failing-before control; these tests
do not measure source fidelity.

The filmed U-shaped connecting-rod junction and the native plate-like head are
treated as functionally equivalent for animation, with the user's approval
pending a later CAD correction. The HUD and verification reports retain this
head-shape assumption. Other motion, camera and geometry checks still apply.

The user separately allows a narrow exception for only the two small
rimmed/recessed lower-rocker side-face features either side of the fulcrum.
They are absent from all twenty native rockers and remain explicitly
**uncertified**, not pending a promised CAD correction. The closed declaration
names both exact source features and only `harmonic-analyzer/channel/rocker-arm-1..20`
paths. The HUD identifies this exception separately from the rod-head mapping;
reports retain both exact records when declared.

Neither exception establishes correspondence for an entire moving part. No source
pixels, native holes or textures are fabricated. The native inventory and coherent
mechanism motion remain required; per-part source certificates at every exposure
are no longer prerequisites for approximate playback.

Structural fixed parts that the source cannot identify may remain rendered in
a complete feasible reconstruction, with the user's approval. They are listed
as source-non-identifiable, not geometric-fidelity passed. Moving parts and all
identifiable-feature and timing checks retain their requirements.

Intermediate qualification is **50% → 20% → 10% → 5% of source frame width**,
across all six videos at each stage. These are maximum landmark errors, not
fractions of coverage: 960, 384, 192 and 96 pixels at 1920 pixels wide.
Canonical final acceptance remains **2% (38.4 px at 1920) / 0.5 seconds**;
passing an intermediate stage does not retag it as final acceptance.

First demonstrate working coarse camera/mechanism tracking across the collection
in the browser, then refine the largest visible discrepancies. Verify every
integer second and visible change using distributed fixed and moving landmarks,
actual rendered pixels and visual overlays. Close-ups, insets and montages remain
required. Report uncertainty, exceptions and unavailable measurements explicitly.
Coarse playback is not final footage acceptance.

```sh
npm --prefix web run build
npm --prefix web run preview

# Incremental coarse collection, then refinements:
export HARMONIC_REFERENCE_ROOT="$PWD/web/.vite/reference-root"
HARMONIC_HEADLESS=1 npm --prefix web run verify:sync -- --stage 50
HARMONIC_HEADLESS=1 npm --prefix web run verify:sync -- --stage 20
HARMONIC_HEADLESS=1 npm --prefix web run verify:sync -- --stage 10

# Scoped measurements do not claim a whole-video pass:
HARMONIC_HEADLESS=1 npm --prefix web run verify:sync -- --stage 50 --video analysis --times 117,118,119

# Headless bounded Analysis03 demonstration; not a fidelity acceptance pass:
HARMONIC_HEADLESS=1 npm --prefix web run verify:sync -- --stage 50 --video analysis --from 5.9 --to 7.1 --player local --headless

# Strict full all-video acceptance also requires independently admitted original
# CPU and spring references. These are local, ignored verification artifacts:
export HARMONIC_ORIGINAL_NATIVE_CPU_CLOSURE="$PWD/web/.vite/verification-output/native-original-9e72-cpu-closure-20261003"
export HARMONIC_ORIGINAL_NATIVE_CPU_CLOSURE_SHA256="d3f0bcdeaea5924931d82715ace92e483eb123e0685419ccb5940c06c6730413"
export HARMONIC_ORIGINAL_SPRING_ORACLE="$PWD/web/.vite/verification-output/native-v39-spring-baseline-20261003/original-f64-oracle-sealed-20261003.mjs"
export HARMONIC_ORIGINAL_SPRING_ORACLE_SHA256="e84fd4318890130e8183ebdcce1560796b24b6e0b4ac3e15b890545c8dd9a5fa"
HARMONIC_HEADLESS=1 npm --prefix web run build && HARMONIC_HEADLESS=1 npm --prefix web run verify:sync

# Local demonstration of the unchanged private original footage:
npm --prefix web run preview:reference -- --port 5967
# http://127.0.0.1:5967/harmonic-analyzer/?video=machine-spin&referenceMedia=1
```

`HARMONIC_REFERENCE_ROOT` defaults to durable ignored `web/.vite/reference-root`.
It must contain the six original MP4s under `videos/`. `preview:reference` serves
them locally with range support without copying footage into publication assets.
Default public playback remains the official YouTube embed.
The verifier serves `dist/`, exercises the original media, and reports per-video
coverage, rendered landmark errors and timing. Its default goal uses strict
**2% / 0.5-second** bounds across all six videos, exercising both official YouTube
and local original media, audio, compact mode and manual controls. A passed
`sourceMeasurement` does not qualify full geometry. The native qualification
caller enables the actual scene capture, streams binary evidence into a run-owned
store, and adjudicates it against the independently admitted original references.
Full acceptance requires the same run's protected frame and per-view results:
complete authentic native inventory, all-stock/all-vertex physical proof, actual
production material and ID/depth first-surface support, and separate complete
current-model source-body eligibility. Imported PASS metadata, partial CHECK
edges, four Intro FIT features, or physical-only results cannot satisfy that gate.
Missing original references fail explicitly; the recorded manifest hash must
come from independent admission, not a manifest's own claimed hash or a refreshed
current-source reference. The CPU archive executes the unchanged published
`9e72eb482a22797f48af5a6df2b00832b7137ace` physical code with separately identified
read-only observations; its texture warning remains outside GPU/material proof.
Qualification covers the actual required decoded-source census, not arbitrary
interactive motion. Camera-only views use fresh finite linear/projective
enclosures from adjudicated physical outputs; selected camera transform-feedback
and actual raster evidence remain distinct. No full native/source acceptance is
claimed merely by implementing this caller or admitting its references.
`?verify=1` enables native WebGL landmark readback. Mathematical camera fitting
alone does not count as rendered-pixel evidence.
Diagnostic landmark receipts also retain the actual native marker's world
coordinates from the same completed view draw. Stale, unresolved or
GPU-deformed coordinates remain unavailable; world coordinates are not
source-pixel measurements or camera qualification.
Contour sidecars must join the exact original source SHA, same-format decoded
BGR8/gray8 hash, frame index, decimal PTS, shot and ordered mapped view layout.
Original CHECK roles do not become new holdouts; partial native depth-ID edge
bounds do not qualify whole geometry. Missing or ambiguous rows remain unavailable.

Paused interaction verification exercises a bounded crank turn and an actual
camera orbit, preserving before/after native pixels, camera poses and media
clocks. Camera equality permits only numerical noise (1e-9 metres, radians and
FOV degrees); a real orbit must exceed that bound and change rendered pixels.
Failed interactions retain their measured predicates and screenshots.

Declared reference images are replayed from the original MP4 and checked against
their native frame indices and pixel hashes. Frame selection uses a balanced
expression so long collections stay within FFmpeg's expression-depth limit;
this does not change the selected frames or split the decoder into retries.
Gray references use explicit round-to-nearest limited-to-full 8-bit luma,
not FFmpeg's version-dependent implicit gray conversion. The schema defines the
byte profile; unsupported source formats are refused and existing hashes stay
unchanged.

Compact selection preserves original landmark observations across nominal and
decoded-time aliases only when source frame, hashes, PTS and view layout match.
It does not interpolate source pixels or change the selected camera and input.
Exact aliases use the declared `sha256Bgr8` or `sha256Gray8` hash for their
pixel format. Formats never alias each other; sampling diagnostics list
supported formats and any unsupported source declarations.

Source generators use committed observations, chosen seed states and immutable
numeric calibration metadata under `content/`. Original private capture paths
and hashes remain provenance links, not regeneration dependencies. No source
video or screenshots are included in those inputs. Capture-bound renderer and
model hashes remain strict; changing the renderer requires recapturing its
bound evidence.
Lossless delivery optimization keeps the native raw hash authoritative; it does
not recalibrate observations or establish geometry/source fidelity acceptance.

`npm --prefix web run test:source` runs the source-generation boundary tests
through uv in an isolated Python environment. The suite covers exact-exposure
identity, conflicting landmarks and invalid presentation declarations.

Intro's physical-support gate counts coincident seam vertices as one apex and
refuses overlapping FIT/CHECK support before optimization. The raw-native behavior
test requires the original `2280bfa6…` GLB; optimized delivery cannot substitute:

```sh
INTRO_RAW_NATIVE_MODEL_PATH=/private/raw/harmonic-analyzer.glb \
  npm --prefix web run test:source:geometry
```

The expanded raw-geometry/CLI gate passed ten cases with zero skips. Camera
origins must be finite three-coordinate values and rotations finite 3×3 matrices;
malformed requests retain explicit refusal/error records. A supplemental
current full-435 CPU first-surface packet checks the original HOLD809 chosen input
and native apex facets; it does not measure GPU pixels, source camera, contact or
stage acceptance. [`DESIGN.md`](DESIGN.md#intro-physical-support-and-first-surface)
records the input and qualification limits.

Legacy full-part visibility, finite-line, contour and raster-bound diagnostics
remain historical evidence, not an exhaustive queue that must finish before
source-following animation can be demonstrated. Preserve their real bug fixes
when using those measurement paths. See [`DESIGN.md`](DESIGN.md) for the current
track, coverage and verification contract.

The October 3 raster controls are historical old-f16/ad5 evidence, not validation
of the newly approved v39 release. The v5 replay covered all eight unchanged cases:
all 23 RGBA readbacks matched the original v3 bytes exactly, with zero raster-bound
violations. The original model response was independently captured by request-bound
CDP (**38,975,844 bytes**, SHA-256 `ad5c259265be354fb25d208281301356d7587c6a2e508fce1a6cd29014a74719`);
tar transport and extracted bytes were verified. Mask warp error/bound remain
**51.700120813456685 / 69.54795584625838 px**, above the original **38.4 px**
diagnostic budget; the intermediate 96 px stage is not a waiver. Thin error/bound
are **16.40021067721657 / 20.707409278898922 px**.

One original HOLD view passed native contour mask, census and extent readback
assertions for all **435 Mesh rows**. Finite-native-line evidence remains
unavailable without a real production API. Six separate synthetic Mesh/Points
contour diagnostics passed, but their six clone owners and seven new drawable
geometries are neither genuine 435-part CAD evidence nor source proof.
The corrected v6 General diagnostic passed **9 views / 63 rows**, retaining all
42 original rendered positives: **53 rendered / 10 unresolved**, zero bound
violations, maximum error/bound **2.5764784400118654 / 8.792759708469386 px**.
Dense passed **21 cases**, zero violations, maximum error/bound
**0.6929656016926606 / 0.7071067811865476 px**. Their 16/2 RGBA members and
same-request original model-response bytes were verified. The earlier General
failure (fixture y=280 instead of baseline 300) remains historical; v2 restores
the true BEFORE-v1 controls rather than re-pinning assertions.
Publication's earlier seed differed from `originalBefore`, and v6–v8 transport
attempts remain failed history. The historical old-f16 v9 private publication
diagnostic passed all three cases: accepted 32, refused live 16,385 > 16,384 while
preserving sample/bank/input/epoch, then recovered 48. It retained 435 genuine rows;
six RGBA members and the original response bytes were extracted and SHA-verified.
This forced **1920×1080 private fixture** is not the normal application surface
or source proof. Finite-native-line evidence remains unavailable. All six videos
remain unmeasured, with **0/3 full collection attempts**.
See [`DESIGN.md`](DESIGN.md#current-raster-diagnostic-controls) for evidence and scope.

Reports and local screenshots go to `web/.vite/verification-output/` and are
ignored. `HARMONIC_CHROME` selects the Chromium executable; `HARMONIC_HEADLESS=1`
is available for automation. External-media restrictions are failures, not skips.

## Deployment

`npm --prefix web run build` produces static files under `web/dist/`. The default
base path is `/harmonic-analyzer/`; set `SIMULATOR_BASE` consistently for both the
build and verifier when deploying elsewhere. Deployment publishes the optimized
representation, not the raw export or its private cache.
Exact geometry sharing reduces duplicate buffers; Meshopt reduces transfer
bytes, not the instance-expanded triangle count. No frame-rate improvement is
established. Fidelity verification still uses all twenty channels and the full
geometry; it must not substitute reduced geometry.

The current **v39** import passed native rest validation (now **131 checks**), with exact semantic
equivalence for **460 drawables**. Its raw export is approximately **218.8 MiB**;
Meshopt delivery is **41,071,140 bytes** (about **39.2 MiB**), SHA-256
`81750ae4c422b973dfd647df4e22f3088933003e39ff41c54563d780eb33fa65`.
Semantic SHA-256 is
`5f648e8e3df1dac4c80a6185a9153ac1373d48acf17175e04929c2dea886d37d`.
A bounded current build passed (**37 modules / 5.82 seconds**), and the model
suite passed **34 tests / zero failures or skips**. A separate private RTX 3090
native-viewer smoke verified the current download identity, **479 names /
462 runtime Mesh rows** against 460 raw drawables, zero missing bindings/errors,
completed epochs **2→3**, and crank/manual-orbit interaction. This is not the
normal application surface or source calibration. A separate corrected native
ownership fixture passed **12 actual states / 10,328 checks**, zero failures/page
errors, with full 462-row GPU censuses and real-world-matrix invariants. Its
**479 actual named poses** include the genuinely exported camera sibling, which
is not a CAD drawable; this adds no CAD geometry or proxy. It retains **21 spring
roles / 3,293,594 vertices**. This bounded ownership
proof is not all-vertex spring GPU numerical equivalence, original-footage
normal-route acceptance or first-surface/source proof.

At published checkpoint `7ec232aa`, all-six observation adoption, family producers
and the source-track transaction completed in **74.17 seconds**. Source, playback
and sync-consumer suites passed **51 / 10 / 88 tests**; the build passed in
**8.05 seconds**. JavaScript chunks fell from about **195 MB to 105 MB** (largest
Intro **27.842 MB**). Later review and execution exposed lost source-only endcard/
transition layouts and Operation facts; the subsequent source reconciliation
restored them. This checkpoint is not deploy-ready or normal-route/source acceptance.
Original MP4 SHA, 1920×1080 dimensions, FPS and actual PTS passed for all six;
raw-file/clock identity is not decoded-image replay or footage-fit proof.

The subsequent strict-consumer corrections passed **92 tests** and the identical
historical/current probe. Original Operation change points omitted from the
measurement census fell from **19 to zero**; missing authored samples remain
required. Seven absent/failed/stale/wrong-model/incomplete/metadata-only native
claims previously received full passes. They now preserve meaningful source-only
success while leaving full acceptance unmeasured. Current numerical/full-native
qualification remains pending.

The subsequent source reconciliation regenerated all six tracks transactionally
in **73.37 seconds**. **70 Python source tests** and **106 playback/sync-consumer
tests** passed. Actual adopter and generated-content probes retained the eight
Analysis endcard views, single-main Synthesis transition, Operation observations
and declared events without promoting old camera/input/warp/native certificates.
Crossfade alpha remains explicitly **chosen-unmeasured** in runtime ordered
receipts; a camera certificate cannot make it measured. These checks establish
source-obligation retention and decoder behavior, not rendered footage fidelity.
The integrated build passed in **6.98 seconds**. A runtime-decoder smoke exercised
all **6,681 authored samples / 15,483 views** from the actual generated JSON;
results remained approximate or no-machine, with no source qualification.

The built site also passed a headed, sequential smoke on all six routes using
the original local MP4s and the current native model. Playback advanced by
**1.019–1.031 seconds** per route; the unmuted compact player remained
**222×200 px**. Paused orbiting and manual crank changes worked, with no missing
bindings or page exceptions. All six screenshots were inspected. The sole
console error was a missing favicon. This is normal-route smoke evidence,
not official YouTube playback or source-camera/mechanism fidelity acceptance.

An exact historical/current census control now respects Analysis's declared
**every-native-frame** obligation: **7,328 indexed exposures** at time base
**1/30000**, versus zero native-exposure rows at `9e72eb48`. The current census
still exposes **6,653 missing exact authored poses** and **6,913 unavailable
native rows**; nearby nominal events cannot substitute for them. Five boundary
tests passed. This corrects an omitted obligation, not the missing calibration.

An independently pinned original-CPU archive from published `9e72eb48` passed
both admission and archived replay: **21 frozen modules**, **479 native names**,
**462 drawables** and **21 springs**. Two actual authored Synthesis inputs
changed the original poses and spring lengths; round-trip restoration and
simultaneous child/parent absolute overrides also passed. The closure pin is
`d3f0bcdeaea5924931d82715ace92e483eb123e0685419ccb5940c06c6730413`.
Read-only observations do not change the original physical rules. The real
Node GLTF loader reported an unresolved texture blob; these results establish
geometry and physical-pose reference replay, not texture, material, GPU or
source-frame fidelity.

The corrected camera-round-trip build passed in **7.18 seconds**; **18**
source-playback tests passed, including absolute-override retention, exposure
boundaries and clearing reused buffers. A same-renderer GPU capture smoke passed
on **three authored cases / 18 views**, exercising four real colour/ID/depth
planes, source warp, horizontal mirroring and ordered compositing. Pose and
one-CSS-pixel viewport changes invalidated old captures; retained byte copies
stayed stable. Disabling capture restored ordinary pixels and reclaimed all
**69 textures, 46 framebuffers and one buffer** it created. The three screenshots
were inspected. This proves capture behavior, not all-vertex numerical bounds,
source-image comparison or full-native acceptance.

The native first-surface consumer also passed a narrow raw-geometry regression:
the original screw-head floor spans triangles **38163 and 38164** at their
coplanar shared edge. The retained before-version wrongly refused the genuine
38164 hit; the corrected version accepts either floor triangle while still
refusing a noncoplanar wall of the same body. The source marker and its FIT
observation are unchanged, as is the **1e−7 m** position bound. These controls use
the actual raw head and an independent CPU reference raster, not captured GPU
pixels or whole-scene/source acceptance. Five permanent surface/support controls
passed with the actual low-red-byte ID encoding. Against the retained pre-fix
helper, only the genuine neighbouring-floor case failed; the other four passed.

Original numerical references are admitted by independently pinned archived
bytes, not by their filenames. The spring oracle recovered from the original
executed script's sealed source map is **28,920 bytes**, SHA-256
`e84fd4318890130e8183ebdcce1560796b24b6e0b4ac3e15b890545c8dd9a5fa`.
The subsequently extended 32,053-byte helper is not that original reference.
This distinction preserves the original position law; it does not establish
production shader, normal, material or source-frame qualification.

The production numerical bank measured **16 states / 21 springs** in each of
four shader families: **52,697,504 vertex readings per family**. Standard and
distance world-position errors stayed within the unchanged **1e−7 m** bound;
the maximum was **9.3307e−8 m**, with zero violations. Native-ID and depth local
positions also stayed within the bound. Standard object-normal error peaked at
**8.2223e−6**; no normal acceptance threshold was invented. Independent
verification passed for the **240-member** executed-source/output archive.
These finite-state measurements do not establish source-camera correspondence,
material/shadow pixels or six-video acceptance.

The explicitly admitted web contract suite passed **337 tests**, including
original CPU replay, closed-section axes, surface support, material epoch/view
ownership and presentation isolation. Eleven Python fit-boundary tests passed.
Virtual axes remain camera-only controls: a wall hit cannot turn an empty axis
point into an opaque first surface. Warp-plus-mirror contour rays use the warp
once, without an additional mirror.

Source-fit admission rejects duplicate anchor identities, nonnumeric source
clocks and every non-null declared or resolved selected-view warp. Private
exports require an existing private parent, reject redirected private roots
and escaped symlink parents, and preserve exclusive-create protection. Run the
web-local Python boundary suite separately from the CAD `doit` graph:

```sh
uv run --no-project --with-requirements web/scripts/source-fit-requirements.txt python web/scripts/test_current_native_source_fit.py
```

Current raw-geometry camera diagnostics retain the original source pixels and
FIT/CHECK roles:

| Source exposure | FIT / held-out CHECK | FIT RMS / maximum (px) | CHECK maximum (px) |
|---|---:|---:|---:|
| Intro 809 | 6 / 2 | 1.413 / 2.612 | 24.251 |
| Analysis 426 | 6 / 2 | 9.848 / 16.579 | 5.011 |
| Rocker 0 | 28 / 10 | 3.717 / 7.971 | 5.176 |
| Synthesis 72 | 6 / 2 | 6.794 / 9.383 | 11.825 |
| Operation 12408 (414 s) | 6 / 2 | 46.839 / 72.915 | **66.414 — failed** |

The original Synthesis six-FIT/one-CHECK refusal remains retained. Its fresh
second CHECK is the actual fixed axle's virtual axis at the stored nut-front
plane: a chosen camera-only correspondence, not restored nut-surface lineage.

The diagnostic bound is **38.4 px** at 1920-pixel source width. The earlier Intro
six-FIT/zero-CHECK packet remains retained as a before control. Source depth,
physical correspondence and mechanical inputs remain chosen, not independently
measured. These candidates do not establish opaque support, camera/lens recovery,
GPU fidelity or six-video acceptance; no historical world coordinates are reused.

The historical source-v37 import produced the same result in two runs:

| Representation | Bytes |
|---|---:|
| Raw native export | 222,903,724 |
| Exact deduplication | 61,672,576 |
| Meshopt delivery asset | 38,975,844 |

This is an 82.5145% reduction in delivered model bytes. All 429 source nodes and
433 drawable instances are preserved; triangle count is unchanged. Native
mechanical metadata is unchanged. These measurements establish lossless asset
delivery, not geometry/source fidelity acceptance or a frame-rate improvement.

A historical old-release headed Chromium smoke matched the optimized download hash and byte count to
the compiled raw association, with 435 runtime drawables and no missing bindings.
All twenty rocker GPU raster records matched the raw baseline bit-for-bit;
all twenty spring lengths changed independently. Three continuous original-MP4
Analysis/Synthesis clips had no stall, pause or error events; the maximum
video/completed-draw delta was 54.341 ms after an explicit initial 0.1-second
startup exclusion. This is not an FPS measurement or a new source calibration.
The 49 source regressions pass using a historical source fixture; production
camrod's current-code guard still refuses the old scene receipt. No historical
receipt was rehashed or accepted as fresh calibration.
The 33 model tests pass, including real-exporter acceptance of compatible future
geometry and rejection of unsupported ratio, pitch, feed-sign and spring-profile
changes before publication. The historical raw reimport reproduced the same
optimized hash and size; none of these old-release checks validates v39.
