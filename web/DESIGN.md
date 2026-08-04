# Simulator design

## Goal

A visitor should be able to answer, in five minutes and without reading
anything: *how does turning a crank add twenty sine waves together?*

Not a game, not a configurator, not a CAD viewer. A guided mechanism
explanation you can interrupt and poke at.

## Architecture

```
 cad/out/gltf/harmonic-analyzer.glb        (doit export, on the SolidWorks seat)
            │  npm run fetch-model
            ▼
 public/models/harmonic-analyzer.glb       (gitignored)
            │  GLTFLoader
            ▼
 scene.ts ──── resolves ────► bindings.ts   logical joint -> node-name regex
     │                             ▲
     │ drives                      │ (contract; a miss warns, never throws)
     ▼                             │
 kinematics.ts  ◄──── ratios from cad/config/machine/gear_train.yaml
     │                             + Michelson & Stratton 1898
     ▼
 main.ts  ── animation loop, output trace, narration panel
     ▲
 narration.ts ◄── content/script.md ◄── references/engineerguy-youtube/*.vtt
```

### Why geometry and motion are separate

The GLB carries shapes and rest transforms. It does **not** carry the
kinematics — SolidWorks mates don't survive a glTF export, and even if they
did, deriving a gear ratio by watching a mesh is worse than reading it from the
config that cut the gear.

So `kinematics.ts` is pure maths with no three.js import: `channelAngle`,
`rockerDisplacement`, `output`, `platenPosition`. That makes it unit-testable
and means a re-export can never silently change the physics.

### The binding contract

`doit export` names glTF nodes after SolidWorks component instances:
`cone-gear-1`, `cylinder-gear-7`, `crank-arm-1`. `bindings.ts` matches those
with regexes and records, per joint, the axis and whether it rotates or
translates.

Two properties this buys:

- **Order-independence.** Indexed bindings sort on the trailing instance
  number, so adding a component doesn't shuffle which gear is channel 7.
- **Graceful degradation.** An unresolved binding logs which pattern missed and
  leaves the joint static. A renamed component costs you one joint, not the
  page.

When the CAD renames a component, the fix is a one-line regex change here.

## The maths, stated once

From the 1898 paper: one crank turn advances cylinder gear *k* by *k*/80 of a
revolution. So

```
theta_k(turns) = turns * k * PI / 40
output(turns)  = sum over k of a_k * cos(theta_k)
```

Two crank turns advance gear *k* by *k*·π/20 — exactly the argument of the
*k*-th cosine. That identity is the whole trick behind using the same machine
for analysis: read the output every two turns and you're reading coefficients.

Magnification is ×4 at the magnifying lever (settable by sliding the vertical
rod) and a fixed ×5 at the wheel (100 mm outer over a 20 mm hub).

The cams are **plain eccentric circles**, so the rocker motion is *near*
sinusoidal, not exactly sinusoidal. `rockerDisplacement` takes a `camHarmonic`
term for this; it defaults to 0 (ideal). Modelling it properly is a genuine
fidelity improvement and a good "what the real machine actually does" beat.

## Narration

Ten chapters (`narration.ts`), each with a crank range, an amplitude-bar
setting, a camera hint and the video it derives from. Copy lives in
[`content/script.md`](content/script.md) and is written against the transcripts
in `references/engineerguy-youtube/` — paraphrased, never pasted.

## Roadmap

| # | feature | notes |
|---|---|---|
| 0 | **Write the narration copy** | the ten chapters currently ship placeholder text. This is the part every visitor actually reads, and it is not blocked on anything. Issue #481. |
| 1 | Camera moves per chapter | hints exist in `narration.ts`; needs a tween and a framing helper. Reuse the azimuth/elevation convention from `cad/comparisons/manifest.json` so poses transfer. |
| 2 | Draggable amplitude bars | the single most engaging interaction: set your own coefficients, watch the trace change |
| 3 | Cam-driven rocker motion | replace the ideal cosine with the eccentric-cam profile from `build_cylinder_gear.py` |
| 4 | Section/exploded views | isolate one channel; fade the other nineteen |
| 5 | Analysis mode | draw a function, sample it at twenty points, watch the machine read the coefficients back |
| 6 | Audio | the machine is famously near-silent apart from the amplitude bars' squeak |
| 7 | Deep links | `?chapter=summing&turns=12` for the book and the campaign to link into |

## Asset budget {#asset-budget}

The raw assembly GLB is far too large for a landing page. Before publishing:

- `gltfpack -cc` or Draco compression
- decimate the parts nobody looks closely at (fasteners, the frame interior)
- consider a reduced model: 20 channels of full geometry is a lot of triangles
  for a machine whose *point* reads fine with 5 channels visible
- target < 15 MB over the wire, < 3 s to first interaction on a laptop

Measure before optimising — the 600 kB JS bundle is three.js and is not the
problem.

## Non-goals

- Physical accuracy of spring dynamics. This is a kinematic toy, and it should
  say so.
- Mobile-first. It should not break on a phone, but the target is a laptop.
- A CAD viewer. Nobody needs a tree of 102 parts. The STEP files are one click
  away for anyone who does.
