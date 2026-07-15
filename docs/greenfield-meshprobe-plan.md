# MeshProbe: greenfield implementation and evaluation plan

## Purpose

MeshProbe is a Python application that lets an AI agent inspect a 3D assembly
without editing it. The agent can find components, move the camera through six
degrees of freedom, switch between orthographic and perspective projection,
change focal length and illumination, hide or isolate components, mark the
parts it is discussing, and produce evidence renders or contact sheets.

The evaluation suite is part of the product, not a collection of demonstrations.
An agent passes an episode only when its answer is correct, the requested scene
changes really occurred, and its rendered evidence supports the answer.

## Decisions fixed by this plan

- Python 3.12 or newer, with `uv` managing the environment and lockfile.
- Blender is the rendering process. It runs factory-clean and receives typed
  commands from the Python controller.
- The CLI is the canonical public interface. An MCP server calls the same Python
  service methods and does not implement a second behavior path.
- GLB/glTF is the primary interchange format because it can preserve component
  names, hierarchy, transforms, and materials. OBJ and STL are accepted with an
  explicit capability report; a single STL does not acquire invented component
  boundaries or names.
- Agent-visible tools cannot execute Python, save a Blender file, or modify
  geometry, transforms, hierarchy, names, or source materials.
- Visual changes live in session state. Closing or resetting the session returns
  every component, camera, and light to the imported state.
- The color renderer uses Blender Eevee. Separate flat-color and depth passes
  provide machine-readable component masks and occlusion evidence.
- All render inputs are explicit and recorded. A render can be reproduced from
  its model hash, scene-state manifest, camera, projection, illumination, and
  renderer version.

## Read-only boundary

MeshProbe reads the source model and writes only derived artifacts:

- rendered images and contact sheets;
- JSON scene, camera, lighting, and evidence manifests;
- execution traces and evaluation reports;
- normalized geometry in a content-addressed cache.

The derived-artifact cache is deterministic and isolated from source files. Each
entry records the source hash, importer version, normalization parameters, and
output hash. Cache eviction removes complete entries; interrupted writes are
staged under a unique directory and become visible only after the manifest and
hash checks pass. Tests compare source hashes before and after every integration
episode.

## Public operation set

The Python service, CLI, and MCP adapter expose the same operations:

| Operation | Result |
| --- | --- |
| `scene.open` | Load a model and return its capabilities and root bounds. |
| `scene.describe` | Return hierarchy, component properties, bounds, and current display state. |
| `component.find` | Resolve exact names, paths, globs, or regular expressions to stable component IDs. |
| `component.inspect` | Return one component's path, transform, bounds, material summary, and relationships. |
| `view.set` | Set an absolute six-degree-of-freedom camera pose and projection. |
| `view.orbit` | Convert target, azimuth, elevation, roll, and distance into an absolute pose. |
| `illumination.set` | Apply a named or custom illumination specification. |
| `component.display` | Set components to `shown`, `hidden`, `isolated`, or `ghosted`. |
| `component.mark` | Set components to `unmarked`, `selected`, `highlighted`, or `labeled`. |
| `render.image` | Render the current state and return the image plus evidence manifest. |
| `render.contact_sheet` | Render a declared set of views and compose a labeled sheet. |
| `session.reset` | Restore imported camera, lighting, colors, and component visibility. |

Calls that address multiple components accept component IDs returned by
`component.find`. A display or mark call that matches zero components fails. A
non-unique exact-name lookup reports every candidate and requires the caller to
choose by stable ID or full hierarchical path.

## Camera and projection model

### Canonical pose

The renderer stores the camera as an absolute world-space pose:

```json
{
  "position_mm": [650.0, 420.0, 780.0],
  "orientation_xyzw": [0.12, -0.31, 0.04, 0.94]
}
```

Position supplies three translational axes and the normalized quaternion
supplies three rotational axes without an Euler singularity. `view.orbit` is a
convenience command for agents and humans. It accepts a target point, azimuth,
elevation, roll, and distance, then returns the absolute pose that was applied.

Every camera-changing operation returns the camera basis vectors, world-space
view frustum, target depth, and projected bounds of the requested focus
components. This makes framing errors visible without requiring the agent to
infer them from a blank or clipped image.

### Projection types

Projection is a discriminated union rather than a set of booleans:

```json
{
  "mode": "perspective",
  "focal_length_mm": 85.0,
  "sensor_width_mm": 36.0,
  "sensor_fit": "horizontal",
  "near_clip_mm": 0.5,
  "far_clip_mm": 100000.0
}
```

```json
{
  "mode": "orthographic",
  "scale_mm": 480.0,
  "near_clip_mm": 0.5,
  "far_clip_mm": 100000.0
}
```

Perspective mode requires a positive focal length and sensor width. MeshProbe
returns the resulting horizontal and vertical fields of view. Orthographic mode
requires the world-space height covered by the camera. Focal length is rejected
for an orthographic camera instead of being silently ignored.

The CLI exposes both forms directly:

```bash
meshprobe view set --pose pose.json --projection perspective \
  --focal-length-mm 85 --sensor-width-mm 36

meshprobe view orbit --focus drive/idler-2 --azimuth 45 --elevation 25 \
  --roll 0 --distance-mm 900 --projection orthographic --scale-mm 500
```

## Illumination model

Illumination is session state and is recorded in every render manifest. Named
presets provide reproducible defaults:

| Preset | Intended use |
| --- | --- |
| `neutral_studio` | General shape and material inspection. |
| `high_key` | Dark assemblies and cavities without crushed shadows. |
| `raking_left` | Relief, engraving, shallow steps, and surface waviness. |
| `raking_right` | The opposite grazing direction for confirmation. |
| `backlit` | Silhouette, gaps, thin parts, and clearance checks. |
| `flat_diagnostic` | Uniform color for identity and segmentation checks. |

A custom specification declares the world background and each light:

```json
{
  "preset": "custom",
  "background_rgb": [0.03, 0.03, 0.04],
  "ambient_strength": 0.18,
  "lights": [
    {
      "id": "key",
      "type": "area",
      "position_mm": [800, 500, 900],
      "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
      "power_w": 900,
      "color_temperature_k": 5200,
      "size_mm": 650
    }
  ]
}
```

Supported light types are `area`, `point`, `spot`, and `sun`. Their schemas
contain only properties that affect that type. Color can be specified as linear
RGB or color temperature, never both. Environment maps are content-addressed
assets with recorded hashes; an undeclared machine-local HDRI cannot affect an
evaluation render.

The renderer rejects a scene that has no effective illumination unless the
request explicitly selects `flat_diagnostic`. It also reports clipped highlights,
crushed-shadow coverage, and median luminance so an agent can correct an
unreadable exposure rather than guessing.

## Scene representation

The import step creates a stable scene manifest:

```text
scene
├── source hash and units
├── component ID
├── full hierarchical path
├── display name and source name
├── parent ID and child IDs
├── mesh hash
├── world transform
├── world and local bounding boxes
├── material summary
└── capability and warning records
```

Component IDs derive from the source hierarchy and instance path, not Blender's
session-specific object names. Geometry instances share mesh data but keep their
own IDs, transforms, and display state.

The importer reports unsupported features such as missing textures, procedural
materials, unsupported animation, or a flattened hierarchy. It does not replace
them with fabricated data.

## Process architecture

```text
Agent, CLI, or MCP client
          |
          v
Python controller
  schemas, session state, artifact store, trace writer
          |
          | line-delimited JSON protocol
          v
Persistent Blender worker
  loader, camera, lights, display overrides, masks, renderer
```

One Blender worker owns one scene session. The controller waits for an explicit
ready event after import, applies one command at a time, and records the state
hash before and after each command. A worker crash invalidates the session; the
controller starts a clean worker and replays the accepted state-changing
commands from the trace.

No request can exceed its declared render dimensions, sample count, wall-time,
or output-byte budget. The worker returns structured errors with the rejected
field and accepted range.

## Rendering and contact sheets

`render.image` emits the color image plus private evaluator passes when an
evaluation session requests them:

- component-ID mask;
- depth;
- surface normals;
- highlighted-component mask;
- shadow and luminance summaries.

The agent receives the color image and public manifest. Evaluation infrastructure
keeps the private passes outside the agent's filesystem.

The default focused contact sheet is a 3 by 3 grid:

1. natural assembly isometric under `neutral_studio`;
2. focused components highlighted in context;
3. the same camera with ranked occluders removed;
4. `+X` focused view;
5. `-X` focused view;
6. `+Y` focused view;
7. `-Y` focused view;
8. `+Z` focused view;
9. `-Z` focused view.

Each panel records its pose, projection, focal length or orthographic scale,
illumination preset, focus set, and hidden-component set. The caption prints the
properties that changed from the sheet defaults. Numbered callouts point to
component projected-bounds centers and use a compact legend instead of covering
small geometry with text.

Custom sheets can vary projection and illumination per panel. A useful surface
inspection recipe pairs orthographic `raking_left` and `raking_right` panels with
a perspective context view. A perspective study can hold the camera pose fixed
while rendering several focal lengths, or preserve subject framing by moving the
camera according to a declared dolly-zoom recipe. The manifest distinguishes
those two experiments.

### Occluder removal

The worker measures the focused component's visible-pixel fraction from a
component-ID pass. If it falls below the recipe threshold, the worker casts rays
from the camera toward stratified samples on the component surface, ranks first-
hit blockers, and removes blockers one at a time. It stops when the target
visibility threshold is reached or the removal budget is exhausted.

The sheet always includes the unmodified context view. The evidence manifest
lists the blockers, their ray-hit counts, the visible fraction before and after,
and the reason the process stopped.

## CLI and Python API

Representative commands:

```bash
meshprobe open pump.glb
meshprobe components find --match 'housing/**/idler*' --json
meshprobe display isolated --components-file ids.json
meshprobe mark highlighted --components-file ids.json
meshprobe illumination set --preset raking_left
meshprobe render image --out evidence.png
meshprobe render sheet --recipe occlusion_peel --out idler-sheet.jpg
meshprobe session reset
```

The Python API returns Pydantic models. CLI JSON output is the serialization of
those same models. Human-readable CLI output is a renderer over the JSON result,
which keeps scripts and agent tools on one contract.

## Evaluation goals

The evaluation suite must answer four different questions:

1. Can the agent discover the right component without relying on a guessed name?
2. Can it manipulate camera, projection, focal length, illumination, and display
   state to reveal the needed evidence?
3. Can it reason correctly from that evidence?
4. Can it leave a complete trace that proves how it reached the answer?

Tool invocation alone earns no credit. A `component.display` call counts only if
the scene state changed and a later render proves the requested visibility. A
focal-length call counts only when the rendered camera matrix and image match the
requested lens.

## Evaluation corpus

### Procedural assemblies

Python generators create models with exact ground truth. They randomize:

- hierarchy depth, instance count, and component names;
- global rotation, scale, units, and handedness;
- camera starting pose and projection;
- housings, doors, baffles, and other occluders;
- duplicate meshes in different positions;
- dark, reflective, and low-contrast materials;
- shallow relief, engraved marks, holes, slots, and surface steps;
- light direction, intensity, background, and color temperature;
- distractor components whose names or silhouettes resemble the target.

Each released generator has held-out seeds. Private qualification also contains
generator families that do not appear in the development split.

### Curated assemblies

The realistic track contains permissively licensed mechanical assemblies such
as gear trains, pumps, valves, bearings, enclosures, hinges, and fastener-heavy
structures. Model families are separated by topology hash and provenance; a
rescaled or renamed copy cannot cross from development into qualification.

### Adversarial models

This track covers duplicate names, Unicode paths, identical instances,
transparent shells, coplanar surfaces, extreme scale ratios, mirrored layouts,
missing materials, malformed meshes, absent targets, flattened STL input, and
questions with more than one defensible answer.

When the evidence is insufficient, the correct result is a structured
`indeterminate` answer with the conflicting candidates or missing capability.

## Task families and operation coverage

| Task family | Operations that must succeed |
| --- | --- |
| Component discovery | open, describe, find, inspect |
| Spatial relationship | find, six-axis camera movement, render |
| Identity verification | find, highlight or label, render |
| Hidden geometry | find, hide or isolate, focus, render |
| Occlusion reasoning | camera movement, visibility changes, comparison renders |
| Projection reasoning | orthographic and perspective renders of the same geometry |
| Lens reasoning | configurable focal length, framing control, perspective evidence |
| Surface-detail reasoning | raking illumination from at least two directions |
| Silhouette and gap reasoning | backlight, projection choice, contact sheet |
| Full investigation | every public operation, including reset |
| Negative and ambiguous | capability inspection and truthful refusal to overclaim |

At least one quarter of private qualification episodes are full investigations.
Passing isolated operation tests cannot compensate for failing that track.

## Tasks that force projection and lighting use

Procedural task templates make metadata insufficient:

- A shallow stamped arrow is unreadable under neutral illumination. The agent
  must use opposing raking lights to report its direction.
- Two coaxial rings overlap in orthographic projection. The agent must choose a
  perspective view and suitable focal length to identify which ring is nearer.
- A clearance is measurable in orthographic projection but distorted in a
  close wide-angle view. The agent must submit the orthographic evidence.
- A foreground fork hides a clip at long focal length from the initial pose. The
  agent must move the camera or shorten the lens while preserving target framing.
- A narrow through-gap is visible only when backlit and viewed near its axis.
- A mirrored assembly changes the answer to a left-versus-right question while
  retaining the same component names.

The generator randomizes the answer, global pose, names, and distractors after
the prompt template is selected. The ground truth cannot be recovered from a
fixed filename or canonical camera.

## Full-stack episode example

> Locate the component whose path ends in `idler`. Determine which numbered
> shaft it contacts and whether its retaining clip is on the positive or negative
> local-X side. Submit a contact sheet containing: the idler highlighted in the
> natural assembly, the enclosing cover removed, orthographic views from all six
> axes, one 85 mm perspective context view, and a raking-light close-up that makes
> the clip visible.

The episode generator randomizes the idler path, contacted shaft, clip side,
cover identity, global transform, starting camera, and material contrast. The
answer oracle reads the generated assembly graph. Render oracles verify every
required panel and scene state.

## Episode isolation and leakage control

Each episode runs in a fresh directory with no network access. The agent can
read the assigned model and its own public artifacts. It cannot read generator
parameters, evaluator masks, answer manifests, other episodes, or source code
used to construct the model.

Prompts and served filenames use opaque episode IDs. The harness records the
mapping in an evaluator-owned directory. It scans prompts, public manifests, and
tool errors for leaked component IDs or answer fields before accepting a run.

Agent adapters cover command-line agents and MCP/tool-calling clients. They all
receive the same prompt, tool schemas, turn budget, render budget, and answer
schema.

## Oracles and pass gates

An episode passes only if every applicable gate succeeds:

1. **Answer gate:** structured answer matches generated or curated ground truth.
2. **State gate:** required camera, projection, lens, illumination, display, and
   mark transitions occurred with valid values.
3. **Evidence gate:** renders were produced after those transitions and contain
   the required target pixels, contrast, framing, and panels.
4. **Coverage gate:** every operation named by the task changed or inspected the
   intended state; no-op calls do not count.
5. **Read-only gate:** source hashes and source directory metadata are unchanged.
6. **Reset gate:** episodes that require reset finish at the imported visual
   state.
7. **Budget gate:** the run stays within declared calls, pixels, bytes, and time.

Private image oracles inspect component masks, depth, and luminance. For example:

- a highlighted target must contribute the expected highlight pixels;
- a hidden blocker must contribute no visible pixels after the hide operation;
- a focal-length render must use the expected projection matrix within numeric
  tolerance;
- a raking-light panel must meet target-local contrast thresholds without
  excessive clipping;
- a contact sheet must contain distinct required poses rather than copies of one
  image with different captions.

Secondary metrics rank passing runs by tool calls, render count, wall time,
peak memory, evidence compactness, and recovery from rejected commands. These
metrics never turn a failed mandatory gate into a pass.

## Metamorphic evaluation

The harness derives controlled variants from each base task:

- rename and reorder components while preserving references;
- apply a global rigid transform;
- rescale the model and convert units;
- mirror the assembly and update handed answers;
- change harmless materials and backgrounds;
- add irrelevant occluders or distractors;
- reorder hierarchy nodes without changing world transforms;
- change the starting projection, focal length, or illumination.

Each task declares which answers must remain invariant and which must transform.
This catches reliance on filenames, default cameras, memorized colors, and
canonical left-right orientation.

## Evaluation size and reporting

The first qualification release contains:

- 16 procedural generator families with 32 seeds each: 512 models;
- 20 curated assemblies with 8 controlled variants each: 160 models;
- at least three task episodes per model;
- at least 2,000 scored episodes;
- at least 500 private full-stack episodes.

Execution tiers are fixed subsets:

| Tier | Episodes | Use |
| --- | ---: | --- |
| Smoke | 40 | Tool and harness sanity check. |
| Pull request | 200 | Deterministic regression gate. |
| Nightly | 800 | Broader procedural and adversarial coverage. |
| Release | 2,000 or more | Complete qualification report. |
| Private | Held-out models and seeds | Generalization measurement. |

Reports show overall and full-stack pass rates, then split results by operation,
task family, difficulty, projection, focal-length band, illumination preset,
model source, and failure class. A high component-discovery score cannot hide a
poor occlusion or lighting score.

## Test strategy

### Unit and property tests

- Quaternion normalization and pose round trips.
- Orbit-to-pose conversion across poles and roll angles.
- Perspective field-of-view and projection-matrix calculations.
- Orthographic scale and projected-bounds calculations.
- Light schema validation and color-temperature conversion.
- Component selector uniqueness and hierarchy behavior.
- State hashing, reset, trace replay, and cache publication.
- Contact-sheet layout, captions, and panel-manifest correspondence.

Hypothesis generates poses, focal lengths, sensor sizes, orthographic scales,
light arrangements, transforms, and hierarchy shapes. Invalid combinations must
fail with stable error codes.

### Blender integration tests

Small generated scenes verify that camera, visibility, color, lighting, and
render state reach Blender exactly. Tests compare evaluator passes and numeric
manifests rather than demanding byte-identical color images across GPU drivers.
Golden images use bounded perceptual and edge differences alongside exact
component-mask checks.

### Failure and recovery tests

- Blender crash during import and render.
- Truncated protocol messages.
- Interrupted cache publication.
- Missing textures and unsupported nodes.
- Requests beyond render or light limits.
- Reset after a partially applied command sequence.
- Replay after worker restart.
- Source directory made read-only at the operating-system level.

## Repository layout

```text
meshprobe/
├── pyproject.toml
├── uv.lock
├── src/meshprobe/
│   ├── cli.py
│   ├── protocol.py
│   ├── models.py
│   ├── controller.py
│   ├── session.py
│   ├── artifacts.py
│   ├── selectors.py
│   ├── contact_sheet.py
│   ├── mcp_server.py
│   └── blender/
│       ├── worker.py
│       ├── loader.py
│       ├── camera.py
│       ├── illumination.py
│       ├── display.py
│       ├── occlusion.py
│       └── renderer.py
├── evals/
│   ├── generators/
│   ├── tasks/
│   ├── oracles/
│   ├── harness/
│   ├── manifests/
│   └── reports/
└── tests/
    ├── unit/
    ├── property/
    ├── integration/
    ├── golden/
    └── safety/
```

## Delivery sequence and exit criteria

### 1. Protocol and scene core

Implement schemas, component IDs, capability reporting, artifact hashing, and
the controller-worker protocol.

Exit: a generated hierarchical GLB opens reproducibly; selectors return stable
IDs; source hashes remain unchanged.

### 2. Camera, projection, and illumination

Implement absolute pose, orbit conversion, perspective and orthographic
projection, configurable focal length, lighting presets, and custom lights.

Exit: numeric projection tests pass; integration renders prove pose, lens,
orthographic scale, and light changes; manifests reproduce each render.

### 3. Component inspection and display

Implement find, inspect, visibility modes, ghosting, highlighting, labels, and
reset.

Exit: private masks prove every state transition; ambiguous selectors fail with
candidate IDs; reset restores the import-state hash.

### 4. Evidence rendering

Implement color and evaluator passes, framing diagnostics, contact sheets, and
occluder removal.

Exit: every declared panel has a distinct state manifest; occlusion tests prove
the focused component becomes visible while the natural-context panel remains.

### 5. Procedural evaluation factory

Implement generators, task schemas, ground-truth manifests, operation-aware
oracles, metamorphic variants, and leakage scanning.

Exit: every public operation has positive, negative, and adversarial episodes;
full-stack tasks fail when any required state transition is removed.

### 6. Agent harness and qualification corpus

Implement isolated runners, CLI and MCP adapters, trace capture, replay, curated
model ingestion, and reports.

Exit: the smoke, pull-request, nightly, release, and private tiers run from pinned
manifests; reports expose results for every operation and full-stack track.

## Definition of done

MeshProbe is ready for its first release when:

- the CLI and MCP adapter pass the same contract tests;
- all supported inputs produce explicit capability reports;
- orthographic and perspective cameras, focal length, and illumination are fully
  represented in state, manifests, traces, and evaluation oracles;
- the persistent worker survives the recovery suite;
- source immutability is proven on every integration and evaluation run;
- the 2,000-episode release suite is reproducible from its pinned manifest;
- every operation family and the full-stack track meet separately published pass
  thresholds;
- a clean machine can install, run the smoke suite, and reproduce its report with
  `uv` plus Blender.
