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
CAD export identified by `src/mechanics-data.ts`; incompatible bytes are rejected.
`fetch-model` can also copy the existing `cad/out/gltf/` export. Missing models
and failed YouTube playback produce visible errors.

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

Declared reference images are replayed from the original MP4 and checked against
their native frame indices and pixel hashes. Frame selection uses a balanced
expression so long collections stay within FFmpeg's expression-depth limit;
this does not change the selected frames or split the decoder into retries.

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
build and verifier when deploying elsewhere. The authentic model is approximately
223 MB, so its first load is substantial. Fidelity verification uses all twenty
channels and the full export; it must not substitute reduced geometry.
