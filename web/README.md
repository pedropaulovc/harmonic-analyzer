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

The current imported model is the approved **v39** release: raw SHA-256
`60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c`,
source commit `81539e53f5146c06a77541415bd79da673806d96`.
The original six source corpora remain archived and hash-sealed. Current v39
records reuse a subset of their measurements, not every historical landmark row.
Migrating those current records preserves their source pixels, PTS, hashes and
uncertainties while rebuilding release-specific tracks from `content/v39-source/`.
Further reuse requires exact exposure provenance and the same physical feature
under a current native association; an unchanged anchor ID alone is insufficient.
Old model-bound tracks remain incompatible, and approximate current tracks do
not establish source fidelity.
No complete current-release source-fidelity acceptance has been established.

Playback can start while the model or source track loads. Source-following starts
automatically when both are ready; pausing retains manual exploration. Status
announcements exclude the running clock. Force readouts are physical calculations,
not source measurements.

The public YouTube player keeps its existing playback and Restore clock contract.
The private local-original player uses visible app-owned play/pause, mute, volume,
scrub and exact-time seek controls. Its safe seek starts at an IDR verified from
the unchanged H264 access units and presents the requested original exposure;
it does not re-encode media or expose an unsafe browser-native timeline.
Local source selection and Restore bind the owned integer PTS/time base and
`requestVideoFrameCallback` frame to the retained authored sample. Native
`currentTime` remains the real model/draw timing clock, not an exact frame ID.
Do not round source timestamps, replace the clock with PTS, or interpolate cuts.

Migration cameras must also be checked against the posed full assembly.
The Intro pen-macro seed was outside the pen frame but looked through the
platen; reversing that chosen camera made the frame visible without hiding
geometry. Visibility is a playback prerequisite, not evidence of a source
pixel fit.

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
Publication replaces the destination entry atomically, preserving any other
hard-link or symlink targets and the previous inventory if writing fails.
The bytes used for the mesh census are digest-bound to the transform input.

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
General affine matrices remain unchanged. The v39 rest matrices are rigid within
1e-6 orthogonality/determinant tolerance; rotational overrides in the fitter
assume rigid rest transforms and are not qualified for scaled or sheared inputs.

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

Direct Node track-association readbacks invoke the same standard-library
publication-seal checker through `uv run --isolated --no-project python`, not an
ambient `python3` executable or a separate interpreter configuration. Exact
record bytes, current native/assembly authority and live generation seals
remain required.

Ordinary producers for all six videos read only strict
`content/v39-source/<ID>.observations.json.gz` records. They validate the current
tracked representation authority, original MP4 identity, native inventory/map
association, exact camera/source exposure bindings and complete chosen physical
inputs. Construction, build and publication re-read the relevant live seals and
the compressed/decoded observation byte seals; a historical snapshot cannot
replace a missing or changed live input. Pair CLIs build and prepare both tracks
before publishing either output.

Analysis/Synthesis historical replay is separate:
`HistoricalReceiptRevalidator.revalidate_receipt()` checks immutable historical
packets and sealed producer/math snapshots. Its non-publishable receipt is not a
current source track and cannot grant current eligibility.
The same revalidator can replay repeatedly: retained camera/input numbers remain
sealed, while framing application counts describe each individual replay rather
than accumulating across receipts. Validation does not append native exposure
keys to the initialized observations.
The original-native Analysis bank extraction, visible-crank gauge, Synthesis automatic-motion and
Spin mechanics CLI implementations are retired from `scripts/`: their required
historical native tuple is not the current live tuple. Original producer source
remains in the SHA-addressed `content/canonical-native/historical-code` archive,
not as an executable current-native replay or fallback.

For current observations, an omitted landmark `viewId` belongs to `main`.
Present landmark and unavailable-row scope IDs must be strings; explicit `null`
is not an omitted scope and is refused by the runtime contract.
Fitting and observer availability apply that default at the consumer boundary;
they do not rewrite the original source measurements or explicit view scopes.

Historical source diagnostics write only to resolved
`web/.vite/verification-output` or external `/tmp` and `/var/tmp` destinations.
Public assets, other repository destinations and symlink escapes are refused
before generation. Their receipts remain non-publishable historical evidence.
Temporary roots are resolved before comparison, including platform symlinks.
The entire checkout remains excluded from external temporary permission even
when the checkout itself is under `/tmp`; private-root symlink escapes are refused.
The observer, fitter and remaining historical diagnostic CLIs share
`check_namespace()` from `fresh-source-observations.py`. The historical CLIs use
their already-loaded `common.fresh` policy. Declared content aliases are refused
even when they resolve to external temporary files; historical snapshots are not
live policy fallbacks.

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

Historical projection and GPU evidence described below belongs to the earlier
model. Its measured results and chosen settings do not qualify the v39 scene;
source-only measurements remain archival evidence. Promotion into a current
record additionally requires exact exposure and current-feature correspondence;
archival completeness does not imply every measurement is reused in v39.

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
The current **50% / 0.5-second** target and other videos' policies remain unchanged.

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

Immutable historical Analysis packets retain bounded cumulative source-drive
evidence for the visible crank (79.8130667..86.6866 seconds) and mirrored bank
(112.3122..119.0856333 seconds):
[`6dW6VYXp9HM.visible-crank-motion.json`](content/canonical-native/6dW6VYXp9HM.visible-crank-motion.json),
[`6dW6VYXp9HM.visible-crank-gauge.json`](content/canonical-native/6dW6VYXp9HM.visible-crank-gauge.json),
[`6dW6VYXp9HM.automatic-motion.json`](content/canonical-native/6dW6VYXp9HM.automatic-motion.json)
and [`6dW6VYXp9HM.motion-controls.json`](content/canonical-native/6dW6VYXp9HM.motion-controls.json).
They separate observed relative motion from chosen native sign/home and hidden
setup. Historical receipt revalidation retains same-shot margin holds and
original gauges; ordinary current playback instead consumes the fresh records
above. [`DESIGN.md`](DESIGN.md#bounded-analysis-motion-authority) describes the
historical evidence and private source-only flow. These historical drives remain
chosen approximations; source camera and geometry fidelity are unaccepted.

Synthesis's immutable historical rocker-bank interval **105.980875..124.4159583 seconds**
is retained in [automatic-motion inputs](content/canonical-native/8KmVDxkia_w.automatic-motion.json)
and [source evidence](content/canonical-native/8KmVDxkia_w.automatic-motion-evidence.json).
Their original producer bytes are archived for lineage, not a current-native
canonical regeneration command. Historical receipt revalidation consumes these
packets; ordinary current track generation consumes only fresh current records.
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
as source-non-identifiable, not geometric-fidelity passed. Identifiable-feature,
rendered-pixel and actual-clock checks retain their requirements; motion and phase
classifications remain explicit diagnostics, not per-image certificates.

The current plan is **50% of source frame width across all six videos**, followed
by a working browser demo. This is a maximum scored landmark error, not a fraction
of coverage. At 1920 pixels wide the limit is 960 pixels; timing remains within
0.5 seconds. The 20%, 10% and 5% refinement stages are outside the current request.

Complete coarse visual matching across the collection, then demonstrate the
implementation. Verify every required integer second and visible change using
spatially distributed, independently measured source CHECKs associated with the
current native geometry, actual rendered pixels and visual overlays. Close-ups,
insets and montages remain required. Fixed/moving composition, a counterfactual
point-motion witness and a static-rig certificate are not prerequisites for this
visual-and-timing scope. Unknown motion or phase stays unknown in diagnostics;
it does not waive source pixels, current geometry association, physical
feasibility, raster visibility, the 960-pixel limit or the 0.5-second clock bound.
Optional finite native LINE checks retain their fixed-body eligibility; a posed
ruler cannot supply a fixed BODY LINE check. Report uncertainty, exceptions and
unavailable measurements explicitly. A passing subset or missing source CHECK
pixels is not an all-six stage-50 pass.

```sh
npm --prefix web run build
npm --prefix web run preview

# Current all-six coarse collection; no video/time scope or optional eligibility:
HARMONIC_HEADLESS=1 npm --prefix web run verify:sync -- --stage 50 --player local

# After the all-six coarse pass, demonstrate the unchanged private original footage:
npm --prefix web run preview:reference -- --port 5967
# http://127.0.0.1:5967/harmonic-analyzer/?referenceMedia=1
```

`HARMONIC_REFERENCE_ROOT` defaults to durable ignored `web/.vite/reference-root`.
It must contain the six original MP4s under `videos/`. `preview:reference` serves
them locally with range support without copying footage into publication assets.
Default public playback remains the official YouTube embed.
The verifier serves `dist/`, exercises the original media, and reports per-video
coverage, rendered landmark errors and timing. The current collection command
must explicitly select stage 50 because the CLI retains its existing finer-stage
options/default; those are not queued deliverables. Clock skew remains at most
0.5 seconds, and manual operation, native media audio state and compact playback
remain required. No audible-speaker observation is implied by media-state checks.

**Measured checkpoint (2026-10-08 UTC).** The unscoped all-six
`--stage 50 --player local` run at `4cfeaee9373d6e78305e39390f2cc608c12f9aaa`
finished **unavailable**, exit 1, with the actual RTX 3090/D3D12 renderer on
every route. It selected every mandatory census key, but selection is not
independent landmark coverage:

| Video | Required samples containing measurements / required | Passed required samples | Maximum measured error (px) | Maximum measured clock skew (s) |
| --- | ---: | ---: | ---: | ---: |
| Intro/history | 1 / 1212 | 0 | 453.373 | 0.018600 |
| Synthesis | 11 / 629 | 9 | 384.221 | 0.041708 |
| Analysis | 91 / 365 | 78 | 289.864 | 0.016684 |
| Operation | 2 / 1019 | 2 | 50.874 | 0.450450 |
| Machine spin | 2 / 186 | 2 | 73.752 | 0.437938 |
| Rocker arms | 1015 / 1153 | 984 | 32.765 | 0.020834 |

The error maxima include admitted mandatory and diagnostic measurements; they
do not bound unmeasured frames. A sample containing FIT pixels can still lack
independent CHECKs. All six stage summaries remain unmeasured, not accepted.
The run retained missing/unsupported source checks, two Analysis spring-bound
refusals at 113.8137 and 119.08563333333333 seconds, compact-playback failures,
and Analysis/Spin manual-setup decode errors before any crank/orbit exercise.
The original compact-failure predicate values were not saved; subsequent
diagnostic receipts retain actual media/render values before the unchanged
0.3-second advancement and 0.5-second clock assertions.

A separate fresh-page headless smoke at the same checkpoint passed on all six
pages: real paused crank/orbit/pan/zoom, clock-bound Restore of camera/input/
assembly, visible 222×200 original-media native controls, unmuted volume 1,
and advancing current native draws. Its maximum observed playback skew was
0.013994 seconds. Intro also recovered the actual EOF HUD and preserved ongoing
manual crank motion through a paused native seek. These bounded positives do
not clear the collection failures, certify missing intervals, demonstrate speaker
output, or exercise the official provider in this round.
Private source/data/dist seals, complete reports and screenshots are retained in
`web/.vite/complete1227-stage50-20261007/`; they are not publication assets.
Later code/seal changes do not relabel this frozen report as newer-head scoring.

After the repeatability correction and consumer-seal refresh,
`3cfa8f6dd7848020d85079124eb6517d5a1da74e` passed a separately bound fresh
six-page runtime smoke, with maximum observed playback skew 0.015018 seconds.
All observation, track and compiled-dist bytes exactly matched the frozen
checkpoint. A single changed-diagnostic Synthesis arm at 284 seconds retained
the actual compact failure: 0.227414 seconds of native progress after 600 ms,
below the unchanged 0.3-second minimum. Media was unpaused, unmuted at volume 1,
readyState 4 without an error; source following and the 0.009989-second model
skew passed their existing predicates. That time-scoped diagnostic is not an
acceptance run; its short-window failure and the original collection failures
remain failures despite the longer bounded runtime positives.

The bounded native-progress correction replaces the fixed 600 ms observation
with a wait for the same 0.3 seconds of actual source progress, using the existing
20-second timeout. Unmuted positive-volume media, the actual native button,
source following, at most 0.5 seconds of clock skew and a new current native draw
remain required; timeout/error receipts retain their real predicate values.
The changed Synthesis 284-second arm passed with 0.312458 seconds of source
progress and 0.010537 seconds of clock skew. A real original-media pause before
the boundary advanced only 0.000037 seconds and was refused by the 20-second
guard. A fresh six-page compact/manual/Restore smoke passed with maximum observed
skew 0.012847 seconds. These separate receipts are under
`web/.vite/complete1227-stage50-20261007/native-progress/`; they do not rewrite
the frozen scientific report or clear unexercised collection failures.
Restore equality binds camera, input and assembly to the measured native clock;
`currentTime` alone does not identify the exact presented decoded frame.

The first ordinary collector for the next integration, frozen at
`53863496a52d87a02a10a2beb8006cd039a97954`, scoped Operation to 204 seconds
and remained **partial/unavailable**, exit 1: **0 of 1** selected required
samples measured, out of **1019** required collection samples. Its old seek
observer expected `seeking`/`seeked` at the target, whereas the safe player
actually seeks to a verified IDR and then presents the target. Compact discovery
also mistook `media.controls === false` for missing controls despite the visible
app-owned original-media controls. Six preceding ordinary playback draw/clock
brackets passed with observed skew zero; they do not clear those failures.

A separate single real pointer seek on the same frozen ordinary build presented
Operation frame **6114**, integer PTS **6120114 / 30000**, at rVFC time
**204.0038 seconds**. Native `seeking`/`seeked` occurred at IDR time **200.5003**;
the actual paused model/draw/media clock was **203.985846**, not rewritten to PTS.
Unchanged full `measureView` admitted six independently measured main-view
CHECKs, maximum **81.56609 px**, with native/model skew zero. Four old FITs were
excluded for missing edge provenance, and fixed/moving classification remained
unavailable; this is not a required-sample or source-fidelity pass. The unchanged
half-frame timing assertion passed on that packet. Its one offline invocation
on an older genuine raw receipt threw at **0.031493 seconds** of PTS/clock
difference, but that older receipt lacks the real URL/epoch and DOM-canvas fields
needed for full ordinary-consumer qualification. Both outcomes remain separate.
Immutable receipts are under
`web/.vite/stage50-refinement-20261008/`; the new collector must bind owned
original frame identity separately from the unchanged 0.5-second clock limit,
and exercise the actual visible app controls without weakening source floors.


Original-source authority is validated before lazy shared browser startup. Shared
startup becomes ready only after server, browser, context and page acquisition;
failure is one terminal verification prerequisite with acquired-resource cleanup,
not repeated per-video launch attempts. Missing originals remain per-video failures.
Verification-only publications use detached banks: ordinary playback and trusted
manual/layout intent resume the real frame rather than inheriting a diagnostic
candidate. Scoped diagnostic APIs expose guarded methods and detached data, not
live mutable model/viewer handles. Pending or expired publications refuse instead
of rolling back newer state. Failed restoration invalidates source/physics/draw
claims while independent cleanup still runs. See
[`DESIGN.md`](DESIGN.md#browser-verification) for ownership and unexercised
failure-path limits; diagnostic controls never qualify source fidelity.
`?verify=1` enables native WebGL landmark readback. Mathematical camera fitting
alone does not count as rendered-pixel evidence.
Diagnostic landmark receipts also retain the actual native marker's world
coordinates from the same completed view draw. Stale, unresolved or
GPU-deformed coordinates remain unavailable; world coordinates are not
source-pixel measurements or camera qualification.

Optional native eligibility requires `nativeViewportBackingPixels: null` for
unwarped captures and current native backing dimensions for warped captures.
A refused diagnostic lease preserves its original unavailable reason and partial
snapshot/capture evidence; unrelated cleanup failures still propagate. Neither
collection nor a successful metadata join qualifies source fidelity or GPU bounds.
The optional classification is scoped to
`selected-native-stage-pixel-exact-vertex-identity`, not general native-anchor
visibility or validity. A quantized pixel-centre ray can hit an incident native
triangle while exceeding the unchanged 1e-7 m distance to its exact stored vertex
class; tiny nonzero pixel-centre offsets can still pass. The scoped refusal
`cpu-selected-pixel-first-surface-exceeds-exact-vertex-residual` retains the raw
projection and pixel-centre offset. CPU evidence reports
`queried-ray-exact-vertex-identity`; absent or different scope refuses. No pixel
offset enlarges the physical tolerance and no vertex ray substitutes for the
selected pixel ray. Source/GPU approval remains independent and unresolved when
unavailable; corpus-wide practical reachability has not been measured.

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

The pixel observer uses that same native Y raster for both gray identity and
NCC/LK measurements, selected by the declared pixel format rather than video ID.
Source clocks use native integer PTS with the rational stream time base, not
microsecond-rounded display timestamps at half-open cuts. Install its locked
web tooling group from the repository root. With `HARMONIC_REFERENCE_ROOT`
pointing to the unchanged original reference root, a private observation run is:

```sh
uv sync --group web
uv run --group web python web/scripts/observe-source.py \
  --source "$HARMONIC_REFERENCE_ROOT/videos/4mBuyixt22U.mp4" \
  --observations web/content/v39-source/4mBuyixt22U.observations.json.gz \
  --output web/.vite/verification-output/rocker-observed.observations.json.gz
```

Successful decoding/emission does not certify missing independent measurements
or promote unavailable source coverage to passed.

Compact selection preserves original landmark observations across nominal and
decoded-time aliases only when source frame, hashes, PTS and view layout match.
It does not interpolate source pixels or change the selected camera and input.
Exact aliases use the declared `sha256Bgr8` or `sha256Gray8` hash for their
pixel format. Formats never alias each other; sampling diagnostics list
supported formats and any unsupported source declarations.

Current authored inputs are `content/v39-source/<videoId>.observations.json.gz`;
browser outputs are `content/<videoId>.source-track.json`. Preserve source PTS,
pixels, hashes, uncertainties and landmarks. For each CAD release, recompute
native identities, world coordinates, cameras and physical constraints against
the approved geometry. Inherited pose seeds remain chosen/unobserved.
The identity-translated packets under `content/canonical-native/` and byte-exact
originals under `content/` from `bfde892a5` remain historical lineage, including
their old projection/GPU proof; they do not qualify current geometry.

From the repository root, store an authored input without reserializing JSON:

```sh
uv run --isolated --no-project python web/scripts/canonical-native-evidence.py compress-observations web/content/v39-source/<ID>.observations.json
```

The command retains the source file and writes exact-byte deterministic gzip
(level 9, `mtime=0`, no filename). Only the registered authored observation
namespace is accepted. Compression preserves numeric spelling and supplies no
geometry or fidelity qualification.

After authoring stops, regenerate in this order using the pinned source-fit
requirements for the four producers:

```sh
uv run --isolated --no-project python web/scripts/canonical-native-evidence.py generate
uv run --isolated --no-project --python 3.13 --with-requirements web/scripts/source-fit-requirements.txt python web/scripts/generate-intro-source-track.py
uv run --isolated --no-project --python 3.13 --with-requirements web/scripts/source-fit-requirements.txt python web/scripts/generate-analysis-synthesis-source-tracks.py
uv run --isolated --no-project --python 3.13 --with-requirements web/scripts/source-fit-requirements.txt python web/scripts/compact-spin.py
uv run --isolated --no-project --python 3.13 --with-requirements web/scripts/source-fit-requirements.txt python web/scripts/compact-operation-rocker.py
uv run --isolated --no-project python web/scripts/canonical-native-evidence.py generate
uv run --isolated --no-project python web/scripts/canonical-native-evidence.py check
```

The first canonical generation refreshes input seals; the final generate/check
binds the produced tracks. Canonical replay remains an identity audit.
Operation/Rocker accepts `--video jfH-NbsmvD4` or `--video 4mBuyixt22U` for
independent publication; its default prevalidates the pair before publishing
either. Analysis/Synthesis retains its independent `--video` selection.

One-ULP routing at half-open cuts is execution-only: authored source numbers
remain unchanged, and the strict same-shot 0.5-second source-exposure requirement
still applies. Nine actual independently decoded frames fill genuinely missing
Operation fade exposures while preserving existing samples and landmarks.
Inherited camera/mechanism guesses remain chosen/unobserved. Complete playable
approximate tracks do not imply a source-fidelity pass. Fresh rendered reports
must distinguish measured failures, unavailable coverage and unmeasured stages;
there is no acceptance-attempt quota.

The [derivative manifest](content/canonical-native/manifest.json) records each
derivative and original SHA-256, mapping revision and digest, preserved numeric
tokens, and sealed historical-code snapshots. Those code seals establish
original lineage only. They do not qualify the current renderer or CAD.
Analysis's native forward-smoke, visible-crank winding proof and extraction-lineage
code seals verify their original historical producers, not today's native math.
Missing, unreadable or modified historical snapshots reject with `ValueError`.
Synthesis's historical automatic-motion `generationDependencies` now read every
non-content producer/math input only from its exact sealed historical-code
archive. Native-data text comes from those same original archived bytes, never
the live current tuple. The content evidence dependency remains the original
pinned packet at the intended evidence root. The cam-rod
`sceneCurrentSourceSha256` retains its original field name and digest but checks
the corresponding sealed historical scene archive. Missing or modified archives
refuse even when matching bytes exist at nominal live source paths; there is no
live-file or replay-root fallback.

The ordinary current producer remains fresh-only and separately checks its live
authority and observation byte seals. Whole historical receipt revalidation
uses the real archive route without overriding byte/text reads. It preserves
original packet and receipt seals and cannot approve current scene, math,
model, GPU or source fidelity. Historical code, original packets and geometry
remain exact-byte evidence.
Original private capture paths and observation hashes remain provenance links,
not regeneration dependencies; no source video or screenshots are included.
Capture-bound renderer and model hashes remain strict. Current-renderer
recapture and source requalification against the approved v39 native geometry
are required before claiming current-model source fidelity.
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

Cloudflare Workers Builds uses native Git integration (not a GitHub deployment
token or OIDC). Both Workers use repository root **`web`**, install with
`npm ci`, and build with **`npm run build:deploy`**. Wrangler is pinned to
**4.148.0** in the lockfile. The build produces **`web/dist/`** at base path `/`,
including `/deployment.json` with the exact `WORKERS_CI_COMMIT_SHA` and
`WORKERS_CI_BRANCH`. Local builds fall back to the current Git commit/branch;
detached checkouts must supply both native-build variables.
The npm `prebuild:deploy` lifecycle runs `npm run test:deployments` first, so the
deployment identity, reporting and cleanup regression tests gate native builds.

| Deployment | Account name / workers.dev subdomain | Account ID | Worker | Native deploy command |
|---|---|---|---|---|
| Production (`main` only) | `harmonicanalyzer-com-prod` | `6b2522c874d4613dc2bf47bd2ce521a2` | `harmonicanalyzer-com-prod` | `npm run deploy` |
| PPE (branch previews, all PR base branches) | `harmonicanalyzer-com-ppe` | `c8769c20b85cd2857afe22ef2f9a0a21` | `harmonicanalyzer-com-ppe` | `npm run deploy:preview` |

Worker service names match their account names and account subdomains; account
IDs are unchanged. Production's origin is
`https://harmonicanalyzer-com-prod.harmonicanalyzer-com-prod.workers.dev`.
The PPE service origin is
`https://harmonicanalyzer-com-ppe.harmonicanalyzer-com-ppe.workers.dev`;
branch Preview API URLs use
`https://<preview-slug>-harmonicanalyzer-com-ppe.harmonicanalyzer-com-ppe.workers.dev`.
GitHub's `production` and `web-preview` environment variables
`CLOUDFLARE_WORKERS_SUBDOMAIN` must match the respective account subdomains above.

PPE uses `wrangler preview --config wrangler.ppe.jsonc --name "$WORKERS_CI_BRANCH"`
for both its default branch and non-production branch build command. It never
publishes the PPE production Worker with `wrangler deploy`. Production
non-production branch builds must be **disabled in the dashboard**.
Native Git build watch paths use Cloudflare's `web/*` wildcard on both PPE
triggers (main and non-main) and production. GitHub workflow path filters use
`web/**`; these are separate matching systems. GitHub environment reporting and
PPE preview cleanup do not perform deployments. The sole GitHub cleanup token
belongs to the PPE environment/account, never the production account.

Native previews cover **same-repository PR branches**, including drafts and PRs
targeting any base branch, when `web/**` changes. Valid unsupported fork PRs are
**explicitly skipped**, not failed or represented as deployed; the job skips
before credentials, checkout or API calls. Malformed event payloads still fail.
Untrusted fork code never enters a credentialed native build. GitHub's PPE
environment records the actual Cloudflare Preview API URL, not a guessed branch
slug, and normally reports success only after `/deployment.json` matches the
exact PR head SHA and raw branch name. If native watch paths skipped a
non-`web/**` push, an older manifest commit is accepted only when the raw branch
matches and GitHub's root `web` subtree object SHA is identical for that commit
and the requested head. The successful deployment records the **actual manifest
SHA**, with `requestedSha` and `identityProof: "matching-web-tree"` in its
payload; it never mislabels old bytes as the new head. Changed-web mismatches
still fail within the bounded wait. An arbitrary HTTP 200 is not deployment
proof. Production
reporting uses the same exact-commit or proven web-tree-equivalence rule;
the standalone `wait` helper remains exact-SHA-only.
Native deployment is **push-only**: opening or reopening a PR does not trigger
a new Cloudflare build. After a closed PR's Preview has been deleted, reopening
that PR requires a **new push touching `web/`** to recreate it. A reopened PR
with no Preview fails reporting immediately with that instruction. A newly
opened PR still allows the normal bounded 20-minute native startup wait before
reporting a native-build-log/new-web-push diagnostic. Neither path attempts a
build through an additional PPE build-control token.

The PPE cleanup credential is used only to read Preview metadata and delete PPE
Previews. The accepted cleanup contract is **branch-only**: PR closure deletes
the closed branch's Preview resource and branch URL, releases its Preview quota,
and inactivates the GitHub deployment record, unless another open PR shares
that branch. **Immutable deployment URLs deliberately remain public** under the
accepted contract because of Cloudflare's beta behavior documented in
[issue 15945](https://github.com/cloudflare/workers-sdk/issues/15945). A live
cleanup probe confirmed that the Preview resource disappeared and the branch
URL returned 404 while an older immutable deployment URL still served its
deployed bytes. Branch cleanup does not promise full public-URL revocation.
Closed-PR cleanup issues the delete immediately, without the orphan grace
period; branch-URL removal then propagates asynchronously through Cloudflare.
A successful delete is not an instant data-plane 404: a second disposable probe
initially returned 200 after deletion and subsequently returned 404 within the
bounded propagation observation.

Cleanup retries still inactivate matching GitHub deployment records when the
Preview resource and Git branch are already gone. The helper decodes GitHub's
string-wrapped GraphQL deployment payload to recover the recorded branch, and
uses paginated bulk `latestStatus` data to skip already-inactive records without
a separate status-history request for every deployment.
Unreadable payloads are left unchanged without inferring ownership from their
Git refs. Valid later records are still cleaned up; afterward the run fails
with an aggregate error naming the unreadable deployment IDs. GitHub API and
status-write failures propagate immediately rather than being treated as
unreadable payloads.

An hourly reconciler catches late builds and orphaned Preview resources. It
preserves new Previews without a PR for their first **30 minutes**, allowing a
branch push to precede PR creation; otherwise orphan **Preview-resource**
cleanup occurs within **90 minutes of Preview creation**, excluding scheduler
delays. This bound does not imply immutable deployment URL revocation. Missing or
malformed API `created_on` timestamps stop reconciliation instead of risking
premature deletion. Open PR branches are preserved. The deployment lifecycle
helper can also be used manually:

```sh
node web/scripts/cloudflare-deployments.mjs preview
node web/scripts/cloudflare-deployments.mjs production
node web/scripts/cloudflare-deployments.mjs list
node web/scripts/cloudflare-deployments.mjs reconcile
node web/scripts/cloudflare-deployments.mjs cleanup 'raw/branch-name'
node web/scripts/cloudflare-deployments.mjs wait URL FULL_COMMIT_SHA [BRANCH [TIMEOUT_SECONDS]]
```

`wait` accepts an application base URL with or without a trailing slash and
preserves any non-root base path when resolving `deployment.json`.

`list`, `reconcile`, and cleanup require `CLOUDFLARE_CLEANUP_API_TOKEN` plus
the fixed PPE `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_WORKER_NAME`, and
`CLOUDFLARE_WORKERS_SUBDOMAIN` environment values. `cleanup` and `reconcile`
also require `GH_TOKEN` and `GITHUB_REPOSITORY` to protect open PR branches.
The low-level `delete RAW_BRANCH` command deliberately bypasses that open-PR
protection; reserve it for intentional preview-deletion smoke checks.

The Wrangler files explicitly pin account and Worker identity. They contain
only the static asset binding and a lossless asset streaming Worker: no storage,
secrets, unrelated bindings, routes, custom domains or scheduled triggers.
`keep_vars` preserves dashboard variables; routing remains dashboard-managed.
PPE explicitly has a `previews` block to enable noninteractive deployments
without copying production resource settings. It enables Preview console logs
for structured `deployment-asset-stream-abort` diagnostics only; automatic
invocation logs are disabled. Wrangler 4.148.0 retains `assets` (including
`ASSETS` and `run_worker_first`) at the top level, not under `previews`.

The approved v39 optimized model is **41,072,516 bytes**, exceeding the
[25 MiB per-file Workers Assets limit](https://developers.cloudflare.com/workers/platform/limits/#static-assets)
on both Free and Paid plans. `build:deploy` therefore downloads the immutable
[SHA-named v39 optimized release asset](https://github.com/pedropaulovc/harmonic-analyzer/releases/download/v39/ha-harmonic-analyzer-941b6193698091781f133642bdc2a7411a18c2cfcb5252646a79b9bd57c6a805.glb),
checks its SHA-256 and exact length against `content/model-representation.json`,
and caches it under ignored `.vite/deployment-model/`. GitHub is a **build-time
input only**: the deployed application makes no model requests to GitHub.
Missing or wrong bytes fail the build. It neither imports a different CAD model
nor regenerates tracked provenance/native metadata.

After Vite builds, every runtime file larger than 25 MiB (including the model
and large source-track JavaScript modules) gets a lossless gzip representation
and an identity fallback. Each representation is split into ordered **24 MiB**
pieces under `dist/deployment-assets/`. The generated, ignored
`.vite/deployment-assets.json` records original URLs, decoded lengths and
SHA-256 values, plus each representation's encoded length, digest and ordered
pieces. The build verifies the pieces, reconstructed representations and exact
decoded original bytes before deployment. Geometry and source datasets stay
unchanged.

For original chunked-asset URLs, the Worker negotiates from the client's original
`Accept-Encoding` (`request.cf.clientAcceptEncoding` on Cloudflare, not the
normalized edge header). It selects gzip or identity by quality and returns 406
when both are refused. GET/HEAD responses include the
selected representation's length and ETag, `Vary: Accept-Encoding`, and
`Content-Encoding: gzip` when selected. It sequentially streams immutable pieces
through a fixed-length stream, without runtime compression or a full-file buffer.
Initial missing chunks return 502; later missing/short chunks error the response
stream rather than silently completing a truncated 200. The model loader verifies the
original compiled SHA-256 and length before parsing. Ordinary files pass through
to `ASSETS` unchanged, including their native conditional-request behavior.
Each immutable `ASSETS` piece is requested with `Accept-Encoding: identity` and
must return 200 with a body. If a Content-Length header is visible it must match
the manifest, but the native binding can omit that header even though its public
HTTP endpoint supplies it. Piece length and SHA-256 checks, plus exact ordered
whole-file SHA reconstruction, are mandatory **producer/predeploy** checks.
Runtime bodies pipe directly into one native `FixedLengthStream`, which enforces
the **actual total byte length** without per-packet JavaScript processing or
materialized arrays. This relies on Cloudflare's immutable `ASSETS` producer for
individual pieces; there is no separate per-piece runtime byte/SHA scan.
The browser still verifies the complete model SHA before parsing.
Abort diagnostics identify the original URL, active piece path, and error
without body bytes. Header/status refusals include actual response status,
visible length, encoding and expected length.
Chunked routes also honor strong/weak `If-None-Match` and `*` with a 304 before
fetching any pieces, so cache revalidation does not redownload the full asset.
Reconstructed routes retain `Cache-Control: no-transform` so Cloudflare does
not recompress either the precompressed gzip or identity response. A native headed-browser control found
that default `Content-Encoding: zstd` failed partway through the 45,568,082-byte
playback module, while an identity-encoding override completed the exact full
module with HTTP/3 unchanged. The response's Content-Length had been removed
under zstd, so this was not evidence of an explicit length-header mismatch.
The transport uses Cloudflare's
[documented no-transform directive](https://developers.cloudflare.com/speed/optimization/content/compression/#content-length-header-handling),
not an HTTP/3-disabled client fallback. The no-transform-only native deployment
still failed concurrent model/module loads, with Cloudflare invocation analytics
reporting `exceededResources`; this outcome does not identify CPU versus memory.
The transport therefore avoids per-buffer JavaScript processing through native
stream piping. Public native-browser verification is required before claiming
the deployed resource fix verified.
Both configurations explicitly use `run_worker_first: false`, Cloudflare's
asset-first default. Ordinary uploaded files (including the transport pieces)
bypass the Worker; these static requests are
[free and unlimited](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/).
The producer deletes oversized originals only after writing all their pieces,
so requests to those original missing URLs fall through to the Worker and use
the manifest transport, regardless of their directory. Keep
`not_found_handling` at its default `none`: no SPA or custom 404 asset fallback
is configured to swallow these missing-original requests.
Reconstructed original requests still invoke the Worker and retain its
[plan limits](https://developers.cloudflare.com/workers/platform/limits/#daily-requests),
including **100,000 requests/day on Workers Free**; they are not unlimited
static delivery. No visitor/cost estimate is implied by the routing change.
No R2 storage or runtime external origin is required.
Original reference footage is local opt-in verification data, not published:
deployment builds reject a `public/reference-media/` directory.

From a clean clone, the equivalent commands are:

```sh
npm --prefix web ci
npm --prefix web run build:deploy
# Authenticated local use only; native Builds supplies Cloudflare credentials.
npm --prefix web run deploy          # main -> production
npm --prefix web run deploy:preview  # actual branch -> PPE preview
```

Plain `npm --prefix web run build` remains the local static Vite build with
default base `/harmonic-analyzer/`; it is not the native deployment build.
Deployment never publishes the raw CAD export or private source cache.
Exact geometry sharing reduces duplicate buffers; Meshopt reduces transfer
bytes, not the instance-expanded triangle count. No frame-rate improvement is
established. Fidelity verification still uses all twenty channels and the full
geometry; it must not substitute reduced geometry.

### Runtime performance checks

Normal source polling reuses a completed draw only when the media clock,
presented native exposure, source/model identity and draw revision are unchanged.
Pending paint, seeks and explicit diagnostic publications still draw. HUD fields
are written only when their displayed values change. The manual crank retains
elapsed-time motion; idle exploration already renders on demand.

Spring meshes use independent live bounding spheres that enclose their current
shader-deformed vertices, including translated hooks and transition curves.
Only springs outside the camera frustum skip submission. Geometry, materials,
names and native diagnostic ownership are unchanged; full-machine views may
save no draws.

`scripts/measure-performance.js` records three cold-cache navigations, resource
bytes and five-second idle/manual-crank WebGL draw windows. Its draw wrappers add
CPU overhead. `scripts/measure-cpu.js` measures idle, manual and actual
source-following CPU windows without those wrappers. Run each in a fresh native
Windows Chrome session, from the repository root in Windows PowerShell:

```powershell
playwright-cli -s=performance open http://localhost:4178/harmonic-analyzer/ --browser=chrome --headed
playwright-cli -s=performance run-code --filename=web/scripts/measure-performance.js
playwright-cli -s=performance close
playwright-cli -s=cpu open http://localhost:4178/harmonic-analyzer/ --browser=chrome --headed
playwright-cli -s=cpu run-code --filename=web/scripts/measure-cpu.js
playwright-cli -s=cpu close
```

Run `npm --prefix web run build` and `npm --prefix web run preview -- --host
0.0.0.0 --port 4178` first. A plain build needs the approved model staged through
the normal model workflow; `build:deploy` acquires it automatically. Compare the
same browser, viewport, pixel ratio and throttling conditions. Draw calls measure
submission work, not GPU elapsed time. Vite's local compression is not evidence
of Worker encoding negotiation: check actual hosted response headers and
transferred bytes separately. Localhost timings establish neither hosted load
time nor real-user Core Web Vitals.

Run `npm --prefix web run test:performance` after `build:deploy` has acquired the
pinned model, or set `SPRING_MODEL_PATH` to its exact approved bytes. Tests cover
polling/HUD transitions, encoded delivery and every actual native spring vertex
at catalog limits and source override spans.

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
