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
npm --prefix web run fetch-model -- /path/to/ha-harmonic-analyzer.glb
npm --prefix web run dev
```

The model is a generated artifact, absent from a fresh checkout. Use the exact
raw CAD export identified by `src/mechanics-data.ts`; incompatible bytes are
rejected. `fetch-model` projects native identities through the authoritative CAD
map, performs lossless exact deduplication and Meshopt compression, then publishes
only the optimized GLB. The approved raw export remains unchanged.
It also accepts `cad/out/gltf/ha-harmonic-analyzer.glb` when no path is supplied.
The raw cache stays outside public assets under `web/.vite/model-source/`.
Missing models and failed YouTube playback produce visible errors.

To adopt a future approved CAD release, provide both its full commit and raw
SHA-256 (not the optimized file's hash):

```sh
npm --prefix web run fetch-model -- /path/to/new.glb --source-commit <full40hexapprovedCADcommit> --source-sha256 <approvedraw64hexreleasehash>
```

The release command reads that exact CAD revision, checks native rest geometry
and compatibility with the website's fixed kinematics, magnifier and spring
deformer mathematics, and stages new native metadata and the optimized asset.
Compatible geometry, rest, spring and setup changes are supported; unsupported
ratio, feed, native-rest association or spring-profile changes are refused with
a named parameter, preserving the last working assets. Missing revisions are
also refused.
A current source commit does not approve arbitrary bytes.
Native identity projection preserves parsed JSON numeric semantics, including
signed zero, and leaves binary geometry untouched. It does not preserve the
original JSON number spelling or integers beyond JavaScript's exact range.
Existing source tracks are stale for a new raw model and reject source-following;
manual exploration is not recalibration. See [`DESIGN.md`](DESIGN.md) for the
representation and provenance contract.

The current imported model is the approved **v39** release. All six retained
source tracks still identify the earlier raw model and are rejected for
source-following against v39. Original-video playback and manual exploration
remain separate from that guard. Fresh v39 source captures and qualification are
required; no v39 source-following or footage-fidelity pass is claimed.

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

### Native calibration inventory

`scripts/export-native-inventory.py` exports the approved raw GLB's unchanged
native rest matrices under canonical qualified paths. It independently checks
the release pair, v2 approval, sole identity map and canonical digest. The raw
GLB and CAD tree remain read-only, including hard-linked output aliases.

```sh
# From the repository root; the approved raw GLB remains private.
uv run --isolated --no-project python web/scripts/export-native-inventory.py \
  --model /path/to/raw-native.glb \
  --source-commit 81539e53f5146c06a77541415bd79da673806d96 \
  --expected-model-sha256 60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c \
  --output /tmp/v39-native-model-inventory.json
npm --prefix web run test:inventory
```

The v39 artifact has 457 released descendant transforms: 450 mesh nodes and
seven assembly transforms. Its mesh primitives produce 460 native drawables.
The assembly root, camera and runtime-generated spare instances are not
inventory rows. `fit-source.py` consumes the matrices as column-major
part-local-metres to native-world-metres, and checks the original raw-model
digest before using any landmark. This inventory does not supply source
observations, camera calibration, motion evidence, historical bounds or
source-fidelity qualification.

The inventory tests are enrolled in `test:model`. They are web-only tooling,
not CAD/doit tests; their independent transform and immutable-input controls
run without SolidWorks, a GPU, source footage or the private GLB.

## Canonical identity evidence audit

`content/canonical-native/manifest.json` seals 29 identity-only derivatives.
The sole mapping authority is `../cad/config/identity-migration-map.json`.
Original evidence files and `canonical-native/historical-code/` snapshots are
immutable inputs; the offline audit never executes archived producers, fetches
network data or recovers files from Git.

```sh
npm --prefix web run verify:identity-evidence
# From web/: read-only seals and deterministic byte replay
uv run --isolated --no-project python scripts/canonical-native-evidence.py validate
uv run --isolated --no-project python scripts/canonical-native-evidence.py check
# Explicit authoring only, after an intentional mapping/input change:
uv run --isolated --no-project python scripts/canonical-native-evidence.py generate
```

`verify:sync` runs the identity evidence check first. Both read-only commands
check exact original, derivative and historical-snapshot SHA-256 seals,
CRLF-to-LF-normalized current-consumer input seals, original numeric-token
certificates, dependency pins and deterministic
replay. `generate` rewrites only declared derivatives, current SHA pins and
the manifest's existing seals. JSON numbers are never parsed as floating-point
values; all original numeric lexemes remain byte-identical. The six observation
derivatives additionally remove only JSON whitespace outside quoted strings and
have exactly one decoded EOF newline. They are stored as deterministic
`*.observations.json.gz` files; current generators and verifiers decode gzip.
The manifest seals both stored bytes (`sha256`) and decoded bytes
(`decodedSha256`). Gzip uses compression level 9, zero timestamp and no embedded
filename. Historical capture commands keep their recorded plaintext paths;
they are provenance, not current loader aliases. Evidence paths are translated
only for declared
manifest members; authored source tracks remain directly under `content/`.
Path/hash projection updates explicitly current regeneration inputs and the three
current `sourceObservations` metadata fields. Required producer-code records must
declare their usage. `historical-producer-lineage` retains its recorded SHA and
an exact commit/source-path/hash-addressed snapshot origin; it is never re-sealed
against a changed live classifier. The nine original-capture snapshots and three
prior identity-migrated input snapshots have distinct provenance. Duplicate
projection containers or authority members are ambiguous and refused; unrelated
capture duplicates remain byte-exact.
Inactive inputs do not authorize path/hash projection; their captured duplicates
remain uninterpreted even when a neighboring current input is updated.
Sealed canonical files are exempt from Git newline conversion. Replay preserves
the original non-observation whitespace bytes; observation packets use the
compact LF form above. Do not convert sealed derivatives to checkout-native
CRLF: dependency SHA pins refer to their exact replay bytes.
The manifest explicitly declares `canonicalConsumerHashNormalization` as
`CRLF-to-LF` for editable current code/data inputs only. Their hashes certify
the normalized text, not checkout byte identity. Original evidence, historical
snapshots, mapping bytes and derivative dependency pins are never normalized.

Ordinary producers for all six videos validate the trusted tracked representation
through the same strict v2 `approved-model.mjs` loader used by offline verifiers.
They compare observations with its approved raw tuple before derivation or
publication, and check normalized live approval, producer, classifier, scene and
native-math inputs against current-consumer seals. Producers declare the additional
modules they execute; Analysis seals the bank-controls module's actual loaded
path. Synthesis checks both primary and secondary observations. Construction and
build recheck native model associations and retained calibration. Analysis also
rechecks consumed numerical inputs, motion indexes and held-camera/bank data.
Synthesis rechecks automatic-motion candidates and times; its additional framing
cameras and lineage hashes are construction-time data. Its old-model framing
pins still refuse v39 generation. A new model label
cannot approve old native readbacks. The pair is constructed and built before
either output is prepared or published. Changed or missing live inputs refuse
even when a matching historical snapshot exists.
Analysis/Synthesis historical replay uses
`HistoricalReceiptRevalidator.revalidate_receipt()`. Its receipt cannot be built
or published as a current source track. Historical lineage never supplies
current eligibility.

Compression reduces current storage, not Git ancestry. Oversized historical
blobs remain unless history is explicitly rewritten.

Native bindings use explicit root/component or root/assembly/component forms,
with optional structural `/mesh` or indexed `/mesh_N` leaves. Identity and
instance suffix translation uses the sole map; unsupported segments fail closed.
The qualification-case `nativePartPaths`/error fields may contain mapped-stem
`-*` family selectors, not concrete drawables. An unbound visible-motion feature
(`partPath: null`) may retain a well-formed numeric `candidatePartFamily` range:
only its declared root/assembly translate; its opaque historical family symbol
is not promoted to a current part identity. The source-backed spare-sprocket
`@upper`/`@crank` consumer-instance suffixes remain intact. These semantic forms
do not permit unknown concrete `partPath` bindings or general suffix aliases.
Qualification-case `negative-native-` names embed the corresponding native
locator after that schema-specific prefix and translate it as a concrete
binding. Historical localhost web-route commands are not native CAD locators
and retain their original route spelling.
Inventory includes those schema-specific labels, not lookalike prose elsewhere.
Before replay returns any output (and before `generate` writes), all 29 original
members are inventoried. One failure packet lists every undeclared occurrence
in source-path/traversal order with its exact JSONPath, binding and reason;
duplicate object members and occurrences remain distinct. Keys and values are
decoded for escaped slashes. This diagnostic walk retains numeric lexemes as
strings and never authors JSON; output still uses lexical string-token rewrites.
Only exact existing archived-binding entries receive `archived-not-current:`.
Byte-replay failures list every mismatching derivative path, rather than
stopping at the first packet.

These certificates establish identity/provenance preservation, **not** fresh
geometry, source-camera or browser qualification. The approved v39 raw export
can supply canonical identities through the importer; a newer CAD export is not
required for renaming. Mechanics/magnifier regeneration and native/browser
qualification remain separate gates. There is no runtime old-to-new GLB alias,
and projecting identities does not make historical observations current.

## Fidelity and verification

The interactive mechanism uses CAD-derived eccentric cams, connecting rods,
finite rocker arcs, amplitude bars, twenty loaded extension springs, the counter
spring, wire and magnifier. It solves quasistatic torque balance. It does not
simulate tooth collisions, friction or inertia. The amplitude controls show CAD
station millimetres; calibration to the video's engraved measuring sticks is
not established.

The source evidence described below belongs to the earlier model. Its measured
results and chosen settings do not qualify the current v39 scene.

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
The final **5% / 0.5-second** limits and other videos' policies remain unchanged.

The optional `content/canonical-native/<videoId>.chosen-camera-continuity.json` permission packet
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
(79.8130667..86.6866 seconds) and mirrored bank (112.3122..119.0856333 seconds).
The authoritative packets are
[`6dW6VYXp9HM.visible-crank-motion.json`](content/canonical-native/6dW6VYXp9HM.visible-crank-motion.json),
[`6dW6VYXp9HM.visible-crank-gauge.json`](content/canonical-native/6dW6VYXp9HM.visible-crank-gauge.json),
[`6dW6VYXp9HM.automatic-motion.json`](content/canonical-native/6dW6VYXp9HM.automatic-motion.json)
and [`6dW6VYXp9HM.motion-controls.json`](content/canonical-native/6dW6VYXp9HM.motion-controls.json).
They separate observed relative motion from chosen native sign/home and hidden
setup. Same-shot margins hold the nearest new input through the real cut;
other shots, views and presentations retain their existing paths.
[`DESIGN.md`](DESIGN.md#bounded-analysis-motion-authority) describes the gauges,
source-specific producers and limits. These drives remain chosen approximations;
source camera and geometry fidelity are unaccepted.

Synthesis's rocker-bank interval **105.980875..124.4159583 seconds** uses
[automatic-motion inputs](content/canonical-native/8KmVDxkia_w.automatic-motion.json) and
[source evidence](content/canonical-native/8KmVDxkia_w.automatic-motion-evidence.json), produced by
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
They do not qualify GPU motion, the full scene or the camera. Separate native
GPU captures exercised all twenty visible rocker meshes, with changing raster
extents and contours at a fixed camera. Uninterrupted original-video/native
playback had a maximum 52.690 ms media-to-completed-draw skew. The fixed far
portrait camera still mismatches the filmed bank close-up; camera and geometric
fidelity remain unqualified.

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
names both exact source features and only `ha-harmonic-analyzer/ch-channel/ch-rocker-arm-1..20`
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

The iterative plan is **50% → 20% → 10% → 5% of source frame width**, across
all six videos at each stage. These are maximum landmark errors, not fractions
of coverage. At 1920 pixels wide the limits are 960, 384, 192 and 96 pixels.
The final tolerance is 5%; timing remains within 0.5 seconds throughout.

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

# Final all-video acceptance, including the official player:
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
coverage, rendered landmark errors and timing. Incremental runs are repeatable;
there is no acceptance-attempt quota. The default final target is 5% of each
source frame's width, with clock skew no greater than 0.5 seconds.
`?verify=1` enables native WebGL landmark readback. Mathematical camera fitting
alone does not count as rendered-pixel evidence.
Diagnostic landmark receipts also retain the actual native marker's world
coordinates from the same completed view draw. Stale, unresolved or
GPU-deformed coordinates remain unavailable; world coordinates are not
source-pixel measurements or camera qualification.

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

Source generators and active loaders use the identity-translated observations,
seed states, calibration and motion packets under `content/canonical-native/`.
The originals under `content/` remain byte-exact archival evidence from
`bfde892a5`; fitting, observation and static-calibration commands refuse those
original observation files as current inputs.

The [derivative manifest](content/canonical-native/manifest.json) records each
derivative and original SHA-256, mapping revision and digest, preserved numeric
tokens, and sealed historical-code snapshots. Those code seals establish
original lineage only. They do not qualify the current renderer or CAD.
Analysis's native forward-smoke, visible-crank winding proof and extraction-lineage
code seals verify their original historical producers, not today's native math.
Missing, unreadable or modified historical snapshots reject with `ValueError`.
Synthesis's automatic-motion `generationDependencies`, by contrast, require exact
current bytes at the intended generation root, including all three native-math
files and the motion producer script. Its cam-rod `sceneCurrentSourceSha256` also
checks that root's actual `web/src/scene.ts`: even cosmetic byte changes require
new bound GPU evidence. These gates do not use historical snapshots or the
manifest's normalized consumer seals as substitutes for current source.
`web/.gitattributes` fixes those five live source inputs and the three current
raw-hashed regeneration inputs (the Operation producer, shared source reader and
native bindings) to LF on checkout, including with `core.autocrlf=true`.
Producer and consumer hashes still use exact bytes. This source-authority
contract is separate from the normalized identity-audit inputs listed in the
manifest. Historical code, original packets and geometry remain
exact-byte evidence.
Historical behavioral fixtures scope the exact archived scene and all four
producer/math sources to those intended source paths, for both byte and text
reads. They leave original packets and receipt seals untouched and replay only
original evidence; they do not approve the current scene, math, model or GPU.
Original private capture paths and observation hashes remain provenance links,
not regeneration dependencies; no source video or screenshots are included.
Capture-bound renderer and model hashes remain strict. Canonical farm GLB
export, metadata re-export and current-renderer recapture/requalification are
still required before claiming current-model source fidelity.
Lossless delivery optimization keeps the native raw hash authoritative; it does
not recalibrate observations or establish geometry/source fidelity acceptance.

`npm --prefix web run test:source` runs the source-generation boundary tests
through uv in an isolated Python environment. The suite covers exact-exposure
identity, conflicting landmarks and invalid presentation declarations.

Legacy full-part visibility, finite-line, contour and raster-bound diagnostics
remain historical evidence, not an exhaustive queue that must finish before
source-following animation can be demonstrated. Preserve their real bug fixes
when using those measurement paths. See [`DESIGN.md`](DESIGN.md) for the current
track, coverage and verification contract.

Reports and local screenshots go to `web/.vite/verification-output/` and are
ignored. `HARMONIC_CHROME` selects the Chromium executable; `HARMONIC_HEADLESS=1`
is available for automation. External-media restrictions are failures, not skips.

## Deployment

`npm --prefix web run build` produces static files under `web/dist/`. The default
base path is `/harmonic-analyzer/`; set `SIMULATOR_BASE` consistently for both the
build and verifier when deploying elsewhere. Deployment publishes the optimized
representation, not the 222,903,724-byte raw export or its private cache.
Exact geometry sharing reduces duplicate buffers; Meshopt reduces transfer
bytes, not the instance-expanded triangle count. No frame-rate improvement is
established. Fidelity verification still uses all twenty channels and the full
geometry; it must not substitute reduced geometry.

The source-v37 measurements and verification results below are preserved from
that snapshot. Use the [subsystem identity guide](../cad/docs/subsystem-identities.md)
for current CAD identities.

The current source-v37 import produced the same result in two runs:

| Representation | Bytes |
|---|---:|
| Raw native export | 222,903,724 |
| Exact deduplication | 61,672,576 |
| Meshopt delivery asset | 38,975,844 |

This is an 82.5145% reduction in delivered model bytes. All 429 source nodes and
433 drawable instances are preserved; triangle count is unchanged. Native
mechanical metadata is unchanged. These measurements establish lossless asset
delivery, not geometry/source fidelity acceptance or a frame-rate improvement.

A headed Chromium smoke matched the optimized download hash and byte count to
the compiled raw association, with 435 runtime drawables and no missing bindings.
All twenty rocker GPU raster records matched the raw baseline bit-for-bit;
all twenty spring lengths changed independently. Three continuous original-MP4
Analysis/Synthesis clips had no stall, pause or error events; the maximum
video/completed-draw delta was 54.341 ms after an explicit initial 0.1-second
startup exclusion. This is not an FPS measurement or a new source calibration.
Source-regression replay uses explicit historical source fixtures; production
cam-rod and automatic-motion current-code guards still refuse stale evidence.
No historical receipt is rehashed or accepted as fresh calibration.
The 33 model tests pass, including real-exporter acceptance of compatible future
geometry and rejection of unsupported ratio, pitch, feed-sign and spring-profile
changes before publication. A current raw reimport reproduced the same optimized
hash and size.
