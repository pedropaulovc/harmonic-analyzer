# Interactive simulator

The harmonic analyzer running in a browser. Turn the crank, watch twenty sine
waves get added by gears and springs, and see the pen draw the answer.

It runs on the same CAD model the physical machine is built from, which is the
GLB that `doit export` writes. So what you see is the geometry that gets
machined rather than an artist's impression. The narration follows the pacing of
the [engineerguy video series](https://www.youtube.com/playlist?list=PL2FF649D0C4407B30),
so anyone who watched those lands somewhere familiar.

## Implementation coverage

Current Website workstream status and sequencing live in the
[Harmonic Analyzer project](https://github.com/users/pedropaulovc/projects/1).
The implementation loads the model, resolves the joints, drives them from the
real gear ratios and draws the output trace. Narration chapters exist as
structured data with placeholder copy. Camera moves and the amplitude-bar UI are
not built yet. See [`DESIGN.md`](DESIGN.md).

## Run it

```powershell
cd web
npm install
npm run fetch-model     # copies cad/out/gltf/*.glb -> public/models/
npm run dev
```

No GLB is the normal state of a fresh checkout, since the model is a build
artefact. Either run `uv run python -m doit export` on the SolidWorks seat, or
download a release bundle and pass the file with
`npm run fetch-model -- path/to.glb`. Without one the page still loads and tells
you so instead of failing silently.

```powershell
npm run build       # typecheck + production bundle -> dist/
npm run preview     # serve the bundle
```

## Layout

```
web/
  index.html            shell: canvas, narration panel, output trace
  src/
    main.ts             wiring, animation loop, the trace plot
    scene.ts            three.js setup, GLB load, joint resolution
    bindings.ts         THE CONTRACT: logical joint -> glTF node name pattern
    kinematics.ts       the machine's maths, no three.js, unit-testable
    narration.ts        the guided tour, chapter by chapter
  content/script.md     narration copy, sourced from the video transcripts
  scripts/fetch-model.mjs
```

## The two ideas worth knowing

Geometry and motion are separate. The GLB supplies shapes and rest positions,
while `kinematics.ts` supplies the motion, derived from the 1898 paper and
`cad/config/machine/gear_train.yaml`. A re-export therefore cannot silently
change the physics, and the physics can be tested without a browser.

Joints bind by name, not by index. `bindings.ts` matches glTF node names
(`cylinder-gear-7`, `crank-arm-1`, which are the SolidWorks component instances)
with regexes, and the channel number comes from the node's own name. A binding
that doesn't resolve logs a named warning and leaves that joint static, so a
renamed component degrades gracefully instead of blanking the page or, worse,
putting the wrong harmonic on the wrong gear.

## Deploying

Static files. `base` in `vite.config.ts` defaults to `/harmonic-analyzer/` for a
GitHub Pages project site. Override it with `SIMULATOR_BASE` for anywhere else.

The GLB is large. Before shipping publicly, run it through `gltfpack` or Draco.
See [`DESIGN.md`](DESIGN.md#asset-budget).
