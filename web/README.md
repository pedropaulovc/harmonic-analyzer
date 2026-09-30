# Harmonic analyzer video companion

Seven engineerguy videos share an interactive view of the CAD-exported analyzer.
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
| PDF guide | `?video=page-by-page-guide` |
| Machine spin | `?video=machine-spin` |
| Rocker arms | `?video=rocker-arms` |

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

Source playback requires measured camera and complete physical input for each
view. An incomplete required interval is visibly unavailable. A source interval
without a corresponding machine can retain a previously matched pose; without
one, the exploratory pose remains unchanged and no source match is claimed.

All seven observation files currently have incomplete camera/mechanism coverage.
In particular, the guide's post/thumbclamp at 771.6709–779.211767 seconds has no
established correspondence to a native CAD part. That interval is still required;
it has not been exempted or replaced. Full footage fidelity is **not verified**.

```sh
npm --prefix web run build
npm --prefix web run preview

# Full acceptance, once the source prerequisites are complete:
export HARMONIC_REFERENCE_ROOT=/path/to/private-reference-root
npm --prefix web run build && npm --prefix web run verify:sync
```

`HARMONIC_REFERENCE_ROOT` defaults to `/tmp/harmonic-web-reference`. The root
must contain the original seven MP4 files under `videos/`. The verifier serves
`dist/`, launches headed Chromium, exercises the real YouTube media, and checks
every integer second and recorded change. It fails on unavailable prerequisites,
missing source evidence, landmark errors above 38.4 pixels or clock skew above
0.5 seconds. `?verify=1` enables diagnostic GPU landmark readback; mathematical
camera fitting alone does not count as rendered-pixel evidence.

Reports and local screenshots go to `web/.vite/verification-output/` and are
ignored. `HARMONIC_CHROME` selects the Chromium executable; `HARMONIC_HEADLESS=1`
is available for automation. External-media restrictions are failures, not skips.

## Deployment

`npm --prefix web run build` produces static files under `web/dist/`. The default
base path is `/harmonic-analyzer/`; set `SIMULATOR_BASE` consistently for both the
build and verifier when deploying elsewhere. The authentic model is approximately
223 MB, so its first load is substantial. Fidelity verification uses all twenty
channels and the full export; it must not substitute reduced geometry.
