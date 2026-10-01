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

Source playback requires a measured camera and complete physical input for each
view. Hidden settings may be chosen as a feasible source-compatible
reconstruction, labelled as unobserved. An incomplete required interval remains
visibly unavailable. An interval without a corresponding machine can retain a
previously matched pose, or leave the exploratory pose unchanged.

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
reports and proof bindings retain both exact records when declared.

Neither exception establishes correspondence for an entire moving part or
makes incomplete source data matched. Original hole contours remain diagnostics;
no source pixels, native holes or textures are fabricated. The full 435-part
census, all other features, pose, camera, motion, 38.4-pixel and 0.5-second
requirements remain unchanged.

Structural fixed parts that the source cannot identify may remain rendered in
a complete feasible reconstruction, with the user's approval. They are listed
as source-non-identifiable, not geometric-fidelity passed. Moving parts and all
identifiable-feature and timing checks retain their requirements.

Source occlusion by an independently measured opaque human hand is separate from
those geometry exceptions. A `source-occluded` record must bind the exact original
image and decoded-time point certificate. A fresh all-435 depth GPU capture must
put every positive native ID pixel cell strictly inside its convex source hand
polygon, including the combined source-mask/native uncertainty margin. Source
identity is supplied independently, never inferred from native capture time.
Other exclusions still require zero native ID pixels. These parts remain
**SOURCE-OCCLUDED**, not source-corresponded or geometry-passed; a single-image
mask cannot certify held/interpolated images or times, and a CPU proposal cannot
make unavailable canonical source data matched.

Ordinary rounded requested-time rows and held/interpolated samples remain
**UNAVAILABLE** unless separately source-qualified; the point-only hand mask
cannot supply that qualification. Actual per-exposure masks or separately
qualified temporal closure are source prerequisites, never inferred from an
earlier mask. The 0.5-second timing limit for other reasons is unchanged.

All six observation files currently have incomplete camera/mechanism coverage.
Full footage fidelity is **not verified**.

```sh
npm --prefix web run build
npm --prefix web run preview

# Full acceptance, once the source prerequisites are complete:
export HARMONIC_REFERENCE_ROOT=/path/to/private-reference-root
npm --prefix web run build && npm --prefix web run verify:sync
```

`HARMONIC_REFERENCE_ROOT` defaults to `/tmp/harmonic-web-reference`; that location
does not survive a host reboot. Prefer durable ignored storage such as
`web/.vite/reference-root` and set the variable explicitly. The root must contain
the six original MP4 files for the routes above under `videos/`.
The verifier serves `dist/`, launches headed Chromium, exercises the real YouTube
media, and checks every integer second and recorded change. It fails on
unavailable prerequisites, missing source evidence, landmark errors above 38.4
pixels or clock skew above 0.5 seconds. `?verify=1` enables native WebGL landmark
and depth-tested part-visibility readback. Mathematical camera fitting alone
does not count as rendered-pixel evidence.

Finite-line checks use Euclidean distance to the finite fitted GPU segment.
Contour checks use supported mesh/background depth-ID boundaries, not artificial
image cuts or point/line footprint edges. Their final bounds include independent
source, native and geometry terms; raw error below the limit alone is insufficient.
Filtering contour candidates preserves the full native census and every rendered
ID pixel's extent.

Measured image-plane warps retain a qualified reference camera and native
geometry, with independently identified corners and interior checks. A decoded
exposure is held only inside its explicit certificate; transforms are not invented
between measurements. Nested montage subviews compose into a named image before
fading once, with matching colour/diagnostic masks and spatial opacity checks.
This presentation support does not qualify the incomplete source corpus.

Reports and local screenshots go to `web/.vite/verification-output/` and are
ignored. `HARMONIC_CHROME` selects the Chromium executable; `HARMONIC_HEADLESS=1`
is available for automation. External-media restrictions are failures, not skips.

## Deployment

`npm --prefix web run build` produces static files under `web/dist/`. The default
base path is `/harmonic-analyzer/`; set `SIMULATOR_BASE` consistently for both the
build and verifier when deploying elsewhere. The authentic model is approximately
223 MB, so its first load is substantial. Fidelity verification uses all twenty
channels and the full export; it must not substitute reduced geometry.
