# meshprobe — a read-only 3D-model inspection layer for AI agents

> Greenfield, mesh-side, Python. Gives an agent read-only inspection powers over a 3D
> model — **6-DOF camera**, **name/highlight components**, **hide/show to expose
> occluded geometry**, **high-density contact-sheet renders** (+ a **section/clip
> plane** for single-mesh interiors and **diagnostic illumination** —
> raking/backlit/flat) — and ships with a **necessity-proven eval set**
> that can only be solved by exercising them.
>
> `meshprobe` is a working name (rename is a find/replace; affects nothing in the
> design). Standalone `uv` project; can be vendored by harmonic-analyzer but does not
> depend on it or on SolidWorks.

## 1. Principles

- **Read-only by construction.** No API mutates the source model. Inspection is a
  session over an in-memory scene; nothing is written back except rendered images.
- **Headless-first.** PyVista on the VTK ≥9.4 OSMesa software-render path — no
  GPU, no display. Already proven in `comparisons/tools/render_diff.py` /
  `osmesa_win.enable_offscreen_gl`.
- **The eval is the product**, and its robustness rests on **deterministic geometric
  proofs, not a VLM's opinion.** Necessity is a claim over *all strategies*; we
  enforce it with ray/depth math, and use the VLM only as a population-level sanity
  check. Mirror the repo's `assert_free_dof_necessity`: prove from both directions,
  name the *required members*.
- **Objective, luck-proof grading.** Answers planted by construction, graded
  programmatically, with per-generator pass thresholds beaten only by real solving.
- **Component identity is first-class, but never a back channel.** Every mesh has a
  stable name; in *eval* scenes, names and metadata are scrubbed of anything that
  correlates with the answer (see §4.3).

## 2. Non-goals

- No geometry creation/editing/repair, no CSG, no CAD-kernel work.
- No SolidWorks/COM path (exists in-repo already; this decouples from it).
- No photorealism / global illumination / ray-traced shadows. We *do* drive
  diagnostic direct-light setups (raking, backlit, flat, high-key — §3 API); cast
  shadows are optional/best-effort, since the diagnostic value comes from the shading
  gradient and the backlit silhouette, not from shadow maps.
- No cross-process session persistence in v1.

## 3. Architecture — five layers, one Python core

```
 ┌ agent surface ─────────────────────────────────────────────┐
 │  CLI (JSON/JSONL) · MCP adapter · Python InspectSession API │  ← every response echoes full session state
 ├ inspection engine ─────────────────────────────────────────┤
 │  camera pose/move · display mode · highlight · section      │  ← stateful, read-only
 │  illumination · render_sheet (one cell = ordinary render)   │
 ├ render backend ────────────────────────────────────────────┤
 │  PyVista Plotter(off_screen, shape=(r,c)) on VTK OSMesa     │  ← one PNG per montage, pixel-budgeted
 ├ scene model ───────────────────────────────────────────────┤
 │  Scene = {name → Component(mesh, transform, bbox, meta)}    │  ← identity + spatial index; eval-scrubbed view
 ├ loader ────────────────────────────────────────────────────┤
 │  glTF/GLB · STL(+manifest) · OBJ · STEP(tessellate via OCP) │  ← trimesh + scene-graph JSON
 └────────────────────────────────────────────────────────────┘
```

### Loader
- `trimesh.load` for glTF/GLB/OBJ (node tree → component names for free). STL pairs
  with a scene-graph manifest JSON (name, transform, parent).
- **Dogfood wrinkle:** harmonic-analyzer's `export_models.py` emits per-part STL +
  a scene JSON with `name/part/cfg/mesh/xform/rgb`, but `rgb` is often **null**
  (colour is resolved separately into a `colors.json` from part-doc reads). The
  loader must run that colour-resolution step or dogfood renders come out
  monochrome. (This is also why colour must never be a *planted* answer on dogfood —
  see §4.3.)
- STEP → tessellate via OCP (`cadquery`/`build123d`) or `gmsh`. Deferred past v1.

### Scene model
```python
@dataclass
class Component:
    name: str
    mesh: pv.PolyData          # world-space, transform baked in
    bbox: tuple[Vec3, Vec3]; centroid: Vec3; volume: float; watertight: bool
    meta: dict                 # FULL truth (source colour, parent, planted tags) — grader/oracle only

@dataclass
class ComponentInfo:           # the AGENT-visible projection — deliberately thin
    name: str                  # neutral (`part_007`) in eval scenes
    visible: bool
    # NO bbox / centroid / volume / colour in eval mode (see §4.3); available in dev/dogfood-structural mode

class Scene:
    components: dict[str, Component]
    eval_mode: bool            # gates what ComponentInfo exposes
    def bounds(self) -> Bounds
    def query(...) -> list[str]     # grader/oracle side only
```

### Inspection engine — minimal agent-facing API

The core is a Python 3.12 package managed by `uv`. `InspectSession` owns all state;
the CLI and MCP server are thin, generated adapters over the same typed command
models. There is no backend behavior in either adapter and no arbitrary-code tool.

Every command returns the complete resulting `SessionState`. Commands use enums,
not transmitted booleans, so later display/projection states remain additive.

```python
class Projection(StrEnum):
    ORTHOGRAPHIC = "orthographic"
    PERSPECTIVE = "perspective"

class DisplayMode(StrEnum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    ISOLATED = "isolated"
    XRAY = "xray"

class IlluminationPreset(StrEnum):
    NEUTRAL = "neutral"      # even, three-point-ish; general shape/material reading (default)
    RAKING = "raking"        # grazing light; reveals shallow relief, engraving, steps
    BACKLIT = "backlit"      # bright background + rim; silhouettes, gaps, thin parts
    FLAT = "flat"            # unlit constant shade; identity/segmentation, no shading cues
    HIGH_KEY = "high_key"    # lifts cavities/dark assemblies without crushing shadows

@dataclass(frozen=True)
class Illumination:
    preset: IlluminationPreset = IlluminationPreset.NEUTRAL
    azimuth_deg: float | None = None    # RAKING: grazing direction in the view plane
    elevation_deg: float | None = None  # RAKING: low angle exaggerates relief
    intensity: float | None = None

@dataclass(frozen=True)
class CameraPose:
    position: Vec3
    target: Vec3
    up: Vec3
    projection: Projection
    vertical_fov_deg: float | None = None
    parallel_scale: float | None = None

@dataclass(frozen=True)
class CameraDelta:              # local camera coordinates
    right: float = 0.0
    up: float = 0.0
    forward: float = 0.0
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0

class InspectSession:
    def __init__(self, scene, size=(1600, 1000), pixel_budget=...): ...

    def list_components(self, query=None) -> CommandResult[list[ComponentInfo]]: ...
    def set_camera(self, pose: CameraPose) -> CommandResult: ...
    def move_camera(self, delta: CameraDelta) -> CommandResult: ...
    def frame(self, names=None, direction=None) -> CommandResult: ...
    def set_display(self, names, mode: DisplayMode, opacity=None) -> CommandResult: ...
    def set_highlight(self, names, style=None) -> CommandResult[list[str]]: ...
    def set_section(self, plane: Plane | None) -> CommandResult: ...
    def set_illumination(self, spec: Illumination) -> CommandResult: ...
    def render_sheet(self, cells, layout=None, labels=True) -> CommandResult[Render]: ...
```

- `CameraPose` is the exact absolute 6-DOF representation. `CameraDelta` makes
  relative navigation easy for an agent without introducing a second camera model.
- `render_sheet` is the only render command. One cell is an ordinary render; many
  cells are a contact sheet. A cell may override camera, display, highlight, section
  and illumination state without mutating the session after the render completes — so
  a surface-inspection sheet can pair `RAKING` from two opposing azimuths with a
  `NEUTRAL` context cell in one PNG.
- **Illumination is session state**, echoed in `SessionState` and recorded in every
  render manifest. Lights are VTK directional/positional lights (`Plotter.add_light`)
  in the software OSMesa path; `FLAT` disables shading (`lighting=False`) for clean
  component-identity reads.
- Turntables and progressive peel views are client-side `render_sheet` recipes, not
  additional tools. Fewer orthogonal tools makes selection easier and traces clearer.
- `render_sheet` uses one `Plotter(shape=(r,c))` and emits **one PNG**, with per-cell
  camera+label under a total-pixel budget (a 3×3 sheet is a multi-MB PNG and a
  context tax — cap it).
- No RNG in the render path; OSMesa AA differences must never flip a graded answer
  (why legibility gates in §4.1 carry margin).
- The same `InspectSession` is the eval's oracle driver — tool and eval share one path.

### CLI and process contract

```console
uv run meshprobe inspect MODEL --commands commands.jsonl --output run/
uv run meshprobe serve --transport stdio MODEL
uv run meshprobe corpus generate --profile dev --count 100
uv run meshprobe corpus validate corpus/dev/
```

- `inspect` replays a JSONL command list against one model and writes the render PNGs
  + a self-describing trace (every `SessionState`) to `--output`.
- `serve` is the MCP adapter over stdio — same typed command models, no second
  behavior path.
- `corpus generate` / `corpus validate` drive the eval factory (§4): generate seeds,
  then run the deterministic necessity gates over them.

## 4. The eval harness — the centerpiece

**Necessity is a claim over all strategies.** A scripted oracle proves only that *its
script* needs an op. So validity is gated by **deterministic geometry**, and ops are
ablated as **capability channels**, not individual methods (the requested ops are not
independent: a `render_sheet` cell pose *is* camera; `DisplayMode.XRAY`/`HIDDEN`/
`section` all reveal occluded geometry; `set_highlight`/`frame` both bind
name↔geometry).

### 4.1 Ground-truth by construction (planted secrets)
Generators plant an answer that is *provably* unobservable from outside, emit
`answer`, `required_channels`, `seed`, a randomised default pose, and full truth for
the grader. Cardinality is raised so guessing loses.

| Generator | Secret | Question | Required channel(s) |
|---|---|---|---|
| `enclosed_token` | inner block carrying a random **code** (unambiguous alphabet, no O/0/I/1/S/5/B/8/Z/2) | "What is the code on the inner block?" | visibility + camera |
| `engraved_face` | random code embossed on one face; **legibility-gated** (see below) | "Read the code engraved on the housing." | camera + illumination (raking) |
| `relief_mark` | shallow stamped mark (arrow/glyph) unreadable under `NEUTRAL`; direction is the answer | "Which way does the stamped arrow point?" | illumination (raking) + camera |
| `gap_silhouette` | a narrow through-gap readable only against a bright backdrop, near its axis | "Is the slot a through-gap or blind?" | illumination (backlit) + camera |
| `buried_count` | N∈**wide, non-canonical range** of enclosed features; non-overlapping silhouettes at the oracle view; N capped for VLM countability | "How many pins are inside the case?" | visibility + camera |
| `occluded_link` | hidden bracket joining 2 of **≥10** parts (C(10,2)=45-way) | "Which two parts does the internal bracket connect?" | visibility + camera |
| `coded_inner` | innermost part tagged with a **colour-band sequence code** (not a nameable colour) | "Read the band code on the innermost part." | visibility + camera |
| `count_by_view` | teeth/holes only fully separable off-axis; high-contrast, count-capped | "How many teeth on the occluded gear?" | visibility + camera |
| `bind_the_part` | neutral-named distractors; answer = the part meeting a spatial predicate | "Name the part bridging the top and base plates." | binding + camera |

- **Composite answers** (code AND count AND relation) multiply the answer space where a
  single field is low-cardinality.
- **Legibility gate** (`engraved_face`, `relief_mark`, `coded_inner`, count generators):
  at generation time, render the oracle's canonical view **under the task's required
  illumination preset** and require the extractor VLM to read the planted answer
  **k/k** times, with a minimum **glyph/feature pixel-height asserted geometrically**.
  Fail → reject the seed. (Text-to-mesh via `trimesh`/VTK is a real
  implementation detail; colour-band or discrete-symbol codes are a more raster-robust
  carrier than extruded glyphs and are preferred where possible.)

### 4.2 Necessity — deterministic geometric gates (the load-bearing invariants)
For each task, generation-time gates (all deterministic, CI-safe):

1. **Exterior-sweep invisibility.** Dense camera sweep over the view sphere (≥200
   poses × multiple distances); ray-cast / depth-buffer check that **zero pixels** of
   the secret mesh are visible without the required visibility op. Plus assert the
   occluder is **watertight**. → proves "hidden" against *all* camera strategies, not
   just the default pose.
2. **Metadata-only baseline fails.** Feed an LLM the full agent-visible
   `list_components` output (no images); it must **not** recover the answer. Catches
   the cheapest shortcut (bbox/centroid/name/colour leaks). Per task.
3. **Text-only-prior baseline fails / is measured.** LLM answers from the question
   alone (no image). "How many teeth?" has heavy priors (12, 20); measure it and
   design the answer distribution to beat it (wide undisclosed ranges, coded answers).
4. **Oracle-succeeds (smoke test).** Scripted solver drives `InspectSession` through
   `required_channels` and recovers the answer — guards our own bugs; no longer the
   necessity proof.
5. **Channel-ablation (population echo).** Remove a whole capability channel (all
   methods providing it) from the agent and confirm the corpus-level success drop —
   the direct analogue of the exact-set free-DOF gate.

**The capability channels** (ablation operates on these, not on individual methods):
- **camera-pose freedom** — `set_camera` / `move_camera` / `frame`, and per-cell poses in `render_sheet`;
- **visibility control** — `set_display` (`HIDDEN`/`ISOLATED`/`XRAY`) + `set_section`;
- **name↔geometry binding** — `set_highlight` / `frame(names=…)` / hide-diff via `set_display` / `list_components`;
- **illumination control** — `set_illumination` presets/angles (raking, backlit, flat, high-key);
- **multi-view throughput** — a multi-cell `render_sheet`.

**Honesty about `set_highlight`.** Highlight is informationally equivalent to
frame/hide-diff/textual naming, so strict per-task highlight-*necessity* is
impossible. It is **exercised, not necessary**: `bind_the_part` *requires the binding
channel* (some name↔geometry op) and is graded on the **returned name-set** of a
required `set_highlight`/`frame` call (precision/recall), with scrambled/neutral names
so textual naming alone can't shortcut it.

**Illumination necessity is measured, not geometric.** "Unreadable without raking
light" is a shading/legibility fact, not an occlusion one, so its gate is a *measured
legibility differential*: across N seeds the VLM reads the answer **k/k under the
required preset and 0/k under `NEUTRAL`/`FLAT`**. Size the relief depth and grazing
angle so the differential is large and stable (parallels the text-prior gate — a
population measurement, not ray geometry). This is the one channel whose necessity
does not rest on the exterior-sweep proof.

### 4.3 Closing the non-visual shortcuts
- **Scrub agent-visible metadata** (§3 `ComponentInfo`): no bbox/centroid/volume/colour
  in eval mode — those solve `occluded_link`, spatial-relation, and colour questions
  with zero renders.
- **Neutralize names** in generated scenes (`part_007`, not `inner_gear`) — semantic
  names pre-answer "innermost/which-bracket" questions.
- **No colour as a planted answer on dogfood** (colour lives in metadata / `colors.json`
  = a back channel). Synthetic colour answers use band-code geometry, read visually.

### 4.4 Difficulty gradient
- **L1 single-channel** (`engraved_face` → camera only).
- **L2 chained** (hide → orbit → count).
- **L3 exploratory + budgeted** — op-set unknown; discover structure via
  `list_components` + sheets. **Contact-sheet lane (necessity-under-budget):** a hard
  tool-call / image-count budget calibrated so the needed info (verify a feature on 6
  faces; count teeth on 5 gears) *cannot* be gathered in-budget with single-cell
  renders but fits in 1–2 multi-cell `render_sheet`s. Ablation: oracle-with-sheets
  passes in budget; oracle-single-cell-only provably exceeds it. Gives the contact
  sheet a real pass/fail lane without pretending it carries unique information.

### 4.5 Corpus
- **Synthetic (primary)** — the generators above; seeded, infinite instances.
- **Dogfood real CAD** — harmonic-analyzer assemblies (STL + `boxes/*.json` + resolved
  colours); **structural questions only** (counts, spatial relations) with exact
  ground truth, no planting.
- **Public models** — small curated slice (Thingi10K/ABC/GrabCAD). ⚠ Mostly
  **single-mesh**, so they exercise *only* camera + `set_section` (`set_display` is a
  no-op on a monolith); scope them explicitly to camera/section tasks. Licences in
  `ATTRIBUTION.md`.

### 4.6 Grading & metrics
- **Objective graders** (backbone): exact numeric, normalised exact-string,
  multiple-choice, name-set precision/recall. No judge in the headline.
- **Headline = luck-proof, not success@1.** **N ≥ 20 seeds per generator**; per-generator
  **pass threshold set by binomial test against the *measured* text-only-prior/chance
  baseline (P(pass|baseline) < 1%)** — not theoretical uniform chance. `success@1`
  reported as a secondary number.
- **Per-capability** success (camera / visibility / binding / illumination /
  contact-under-budget) and **channel-ablation deltas**.
- **Efficiency**: steps-to-solve, wrong-tool rate, sheet-vs-single-cell call counts.
- **Necessity-coverage CI gate = 100%** — survives as a gate *only because* the §4.2
  validity gates are deterministic (no VLM-in-CI flapping).
- Open-ended "describe the mechanism": secondary VLM/rubric judge, out of headline.

### 4.7 Contamination resistance
- Generators are checked in; **answers are not, and neither is a pre-registered test
  seed range** (generator + named seed = model + answer = an answer key with one step).
- **Test seeds drawn from runtime entropy at eval time**, logged in the run report
  (reproducible *from the report*, not *from the repo*). Pin the validity-gate stack
  version in the report so accepted-task sets are re-derivable. Checked-in seed
  manifests are dev-split only.

### 4.8 Runner
- `corpus validate` runs the §4.2 gates; `meshprobe inspect` runs an agent (MCP surface
  or direct function-call loop) across the corpus → JSONL trace + scored report.
  Model-agnostic behind one adapter. **Fresh session per task instance enforced**
  (shared-server state leakage is the classic eval footgun); every command response
  echoes full `SessionState` so traces are self-describing and replayable.

## 5. Repo layout

```
meshprobe/
  pyproject.toml            # uv: pyvista, trimesh, numpy, pillow, fastmcp, pytest, (cadquery/gmsh opt)
  src/meshprobe/
    load.py  scene.py  session.py  render.py  illumination.py  cli.py  mcp_server.py  models.py
  eval/
    generators/   # enclosed_token, engraved_face, buried_count, occluded_link, coded_inner, count_by_view, bind_the_part, relief_mark, gap_silhouette
    gates.py      # §4.2 deterministic validity gates (sweep-invisibility, watertight, metadata-only, text-prior, legibility)
    oracle.py     # scripted solvers (smoke test) driving InspectSession
    grade.py      # objective graders + binomial thresholds + optional VLM judge
    baselines.py  # metadata-only, text-only-prior, chance baselines
    runner.py  tasks.py
  corpus/         # dev fixtures (tracked seed manifests) — test seeds are runtime-entropy, report-logged
  tests/          # unit + necessity-coverage CI gate
  ATTRIBUTION.md
```

## 6. Milestones

- **M0 — spike (compressed, ~0.5 d).** `render_diff.py` already runs this exact OSMesa
  stack at 1600px; just confirm a `render_sheet` of 6 poses in one PNG. Spend the
  recovered time prototyping the **exterior-sweep falsifier** (§4.2.1) — the one truly
  unproven component.
- **M1 — engine.** Loader (incl. dogfood colour-resolution) + Scene + `InspectSession`
  (camera / display / highlight / section / illumination + `render_sheet`) + full
  state-echo, with unit tests.
- **M2 — CLI + MCP surface.** `inspect`/`serve` adapters over the same typed command
  models; drive from Claude Code; confirm image blocks + pixel budget.
- **M3 — eval v1 *with the shortcut gates built in from day one*.** 2–3 generators +
  oracle + **all §4.2 gates (sweep-invisibility, metadata-only baseline, text-only-prior
  baseline)** + neutralized names/scrubbed metadata + objective graders + binomial
  thresholds. Necessity-coverage gate green. *(These gates land at M3, not M5 —
  discovering at M4 that `occluded_link`/colour were metadata-solvable would invalidate
  an M3 scorecard.)*
- **M4 — eval robust.** All 7 generators, L1–L3 incl. contact-under-budget lane,
  dogfood + scoped public slices, per-channel + ablation metrics, runtime-entropy test
  seeds. First full agent scorecard.
- **M5 — hardening.** More `set_section` tasks for single-mesh interiors, VLM judge for
  open-ended, efficiency metrics, contamination audit, docs.

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Necessity provable on paper, task still shortcut-solvable | Deterministic sweep-invisibility + watertight + metadata-only + text-prior gates (§4.2) replace the stochastic one-view/scripted-ablation proof |
| Metadata/name leaks answer with zero renders | Scrub `ComponentInfo`, neutralize names, metadata-only baseline gate (§4.3) |
| Anti-prior selection bias from VLM rejection | Reject only on deterministic gates; VLM null is population-level, not per-task acceptance |
| Low cardinality / lucky guessing | ≥45-way `occluded_link`, coded (not named) colours, wide count ranges, N≥20 + binomial thresholds |
| Contact sheet un-evaluated (it's affordance, not unique info) | Necessity-under-budget lane (§4.4) gives it a real pass/fail |
| `engraved_face`/`relief_mark` illegible under flat shading | `RAKING` illumination is the intended reveal (grazing light exaggerates shallow relief); legibility gate renders under that preset; unambiguous alphabet, prefer colour-band/symbol codes |
| Illumination necessity is softer than the geometric gates | Rests on a measured legibility differential (k/k under preset, 0/k under `NEUTRAL`/`FLAT`), not ray geometry — size relief depth + grazing angle for a large, stable margin |
| Single-mesh public models exercise only camera | Scope them to camera/section; `set_section` is the only interior-reveal for monoliths |
| Test split = answer key in the repo | Runtime-entropy test seeds logged in report, never pre-registered |
| OSMesa GL libs flaky on a box | pyrender(OSMesa) fallback behind `render.py`; legibility gates carry AA margin |
| VLM judge noise in headline | Judge only grades open-ended tasks, never the backbone |

## 8. Resolved design decisions

- **Stateful session — YES**, with (a) every command response echoing complete
  `SessionState` (camera pose, display map, opacity, section) for replayable traces,
  (b) enforced fresh session per task instance, (c) no RNG in the render path.
- **`set_highlight` returns the name-set** (structured), and binding tasks grade on
  that set — pixels never grade a name task.
- **Contact sheet = necessity-under-budget** (§4.4), not a soft footnote and not a
  fake "unique information" pass/fail. `render_sheet` is the single render command; a
  multi-cell sheet is the only way to meet the L3 budget.
- **`set_section` is a first-class command** (visibility channel), not a deferred
  extra — it is the only interior-reveal for solid/single-mesh models, which the
  public-models slice needs.
- **`set_illumination` is a first-class command and its own capability channel** —
  diagnostic presets (raking for relief/engraving, backlit for gaps/silhouettes, flat
  for identity/segmentation, high-key for cavities). Session state, per-cell
  overridable, recorded in every render manifest. This is what closes the flat-shading
  legibility gap the eval otherwise fights — and it brings the PyVista plan to parity
  with the illumination model in the Blender plan (`docs/greenfield-meshprobe-plan.md`)
  without leaving the headless OSMesa raster path.
- **One Python core, thin adapters** — the CLI and MCP server are generated over the
  same typed command models; no second behavior path, no arbitrary-code tool.
