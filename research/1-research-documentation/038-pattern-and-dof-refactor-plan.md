# Plan: component patterns for repeated structure + operational-DOF refactor

Two changes to the assembly build scripts:

1. Replace cloned grounded structure with SolidWorks linear component patterns.
2. Re-anchor the assemblies so they retain exactly the degrees of freedom the
   analyzer needs to operate, each pinned to a canonical pose by a suppressible
   "park" driver.

Decision taken up front (the two requests conflict — see below): **DOF wins.
Pattern only the grounded repeated structure; keep every moving part as an
individual mated instance.**

---

## 0. Grounding (what the code does today)

* **Channels are rigid Z-copies at the home snapshot.** `build_channel_assembly.py`
  solves *one* `solve_default_state()` (arm/rod/lever tilts) and applies it to all
  20 channels; only `z_mid = Z0 + 7.0565·j` varies (`build_channel_assembly.py:498-531`).
* **Drive side is the same.** 20 **identical** `cylinder-gear` parts (integral cam)
  at `z_j = Z_DRUM0 + 7.0568·j`, all Rz(1.5°) (`build_drive_train_assembly.py:523-530`).
* **Cone gears are NOT identical** — each a different configuration `T120…T006`
  (120→6 teeth) on the inclined shaft at varying radius (`:512-519`). They can
  never be a component pattern (a pattern copies one seed+config).
* **Anchoring today:** ~75 components fixed (`ground=True`); the moving chain
  (cylinder gears, cone gears, crank, the 4 channel parts) is `ground=False` +
  real revolute/gear mates, each pinned by a **suppressible per-channel driver**
  so a Basic-Motion study can drive it. Crank already has its single park driver
  (`DRIVER #1`, `build_drive_train_assembly.py:670-677`).
* **Adapter support (already implemented):** `pattern_components_linear`
  (`adapters/solidworks/assembly.py:1163`, via `FeatureLinearPattern5`),
  `pattern_components_circular`, `suppress_mate`, `float_component`,
  `set_component_solving`, `create_configuration`. No MCP-package work required.

### The conflict, and why DOF wins

The parts named for patterning — gear, cam, rocker, amplitude-bar, top-lever —
are exactly the **moving** parts. A `LocalLinearPattern` instance is a rigid
slave of the seed: zero DOF, cannot be driven independently in a motion study.
But the analyzer's defining behavior is that **each channel runs at a different
harmonic frequency** (cylinder gear *j* meshes cone gear *j* at ratio
`[120−6j : 120]`, `:657-662`) — the channels decohere the instant the crank
turns. Lockstep patterned instances would be physically wrong.

The irony: the parts safe to pattern (grounded `pivot-bushing ×19`,
`lever-bushing ×19`, cosmetic `channel-spring ×20`) carry **zero mates today**,
so patterning them saves no solve cost — only tree/graphics/authoring tidiness.
The parts where fewer mates *would* help can't be patterned. So Part 1 is a
low-value cleanup; Part 2 is the substantive work.

---

## Part 1 — Linear patterns for grounded repeated structure

### Scope

| Component | Today | Action |
|---|---|---|
| `pivot-bushing` ×19 | 19 fixed inserts at `z_gap` | seed + `LocalLinearPattern`, count 19, spacing `PITCH` along Z |
| `lever-bushing` ×19 | 19 fixed inserts | seed + `LocalLinearPattern`, count 19, spacing `PITCH` |
| `channel-spring-installed` ×20 | 20 fixed inserts | seed + `LocalLinearPattern`, count 20, spacing `PITCH` |
| moving parts (gear/cam/rocker/bar/lever, cone gears) | individual mated | **unchanged** — required for Part 2 |
| `pivot-ball-mount` ×4 | 4 fixed inserts | **unchanged** — asymmetric, not a regular array |

All three patternable families are constant in X/Y across channels (only Z
varies), so a single-axis Z pattern is exact.

### Steps (in `build_channel_assembly.py`)

1. Insert only the **seed** of each family (bushing at gap `0/1`, spring at
   channel 0) inside the per-channel loop guard; drop the other 19/20 inserts.
2. After the loop, call once per family:
   ```python
   await adapter.pattern_components_linear(ComponentLinearPatternParameters(
       components=[<seed component name>],
       count=<19 or 20>,
       spacing=PITCH,                 # mm; impl divides by 1000
       direction_name="Axis1@pivot-shaft",   # the Z-running shaft axis
   ))
   ```
   Use the `pivot-shaft` / `fulcrum-shaft` axis (runs along Z) as the direction
   reference; flip handled by seed placement, not `FlipDir`.
3. Keep `assert_components_fully_defined` and `check_no_interference` as the gate.

### Risks / checks

* **Fully-defined gate vs pattern instances.** Confirm pattern instances satisfy
  `assert_components_fully_defined` (they're pattern-driven, should read defined)
  and that `check_no_interference` still enumerates them. Verify on a 3-channel
  build (`CHANNEL_COUNT=3`) before the full 20.
* **Instance naming.** Pattern copies get auto-names (`pivot-bushing-2`, …). No
  downstream script references individual bushings/springs by name today, but
  grep before committing.
* **Value.** This is cosmetic/tree cleanup only. Sequence it first as a low-risk
  warm-up that also de-risks the `pattern_components_linear` call headlessly, or
  skip if churn isn't worth it.

---

## Part 2 — Operational degrees of freedom

### DOF inventory (mobility target)

| # | DOF | Type | Components | Today |
|---|---|---|---|---|
| crank | crank rotation (sole drive input) | continuous | crankshaft + keyed chain | ✅ revolute + park driver |
| channels | 20 channel chains follow the crank | dependent | rocker/rod/bar/lever ×20 | ✅ revolutes + suppressible drivers |
| **p0** | amplitude bar adjust (per channel) | setup slide | `amplitude-bar` ×20 | ❌ pinned by foot spin driver, no slide DOF |
| **p1** | cone cluster swing to disengage (ch12) | setup toggle | cone shaft + 64T + 20 cone gears | ❌ revolutes in a **fixed** pivot-post; no swing |
| **p2** | pinion swing to engage (ch25) | setup toggle | drum + 2 straps + handle | ❌ entire rig **fixed** |

Operating mobility (cone engaged, a run in progress) = **1** (crank); the 20
channels are dependent. p0/p1/p2 are quasi-static *setup* freedoms, not driven
during a run.

### Design pattern (applies to every DOF)

Carry forward the recommendation from the DOF discussion:

* **Ground exactly one base** per subassembly (the frame / arbor / pivot-post
  support) so global coordinates and render azimuths stay stable.
* **Every operational DOF = a real joint + a suppressible "park" driver** set to
  the canonical export pose. Park driver active → assembly fully defined (0 DOF),
  deterministic for exports/renders/photo-alignment. Park driver suppressed →
  the joint is free for a Basic-Motion study.
* **Engagement is a state enum, not scattered booleans** (per coding style).
  Represent `drive_state ∈ {rest, cone_disengaged, pinion_engaged}` as **assembly
  configurations** (`create_configuration`), each carrying its swing-driver values
  and its mesh-mate suppression set. `rest` is the default and **must equal
  today's saved pose** so the comparisons pipeline (469 photo pairs, azimuth
  arithmetic) is untouched.

### Work item: p0 — amplitude bar adjust (`build_channel_assembly.py`, 20×)

The amplitude setting is the bar's foot position along the rocker (the radius at
which it picks off the seesaw's displacement = that harmonic's amplitude
coefficient). Today the foot is pinned by a spin driver (`_revolute(..., J3 bar)`,
`:562-568`).

* Replace the foot **spin driver** with a **slide constraint**: foot coincident/
  tangent to the rocker top-edge arc (leaving slide-along-edge free) + the top
  pin revolute to the lever (already present).
* Add a **distance driver** = pivot-to-foot distance = the amplitude park value
  (default = today's solved contact point, so `rest` is unchanged).
* These bars stay individual instances (not patterned) — no conflict.

### Work item: p1 — cone disengage (`build_drive_train_assembly.py`)

The cone cluster (`cone-gear-shaft` + `crank-drive-gear` + 20 cone gears, all
lock-mated together, `:617-628`) tips out of the cylinder-drum mesh by pivoting
about the big-end journal in the black `cone-pivot-post`.

* The cluster already has its **spin** revolute (driven by the 16:64 mesh). Add a
  second rigid-body **swing** revolute about the big-end journal axis (≈ vertical,
  through the pivot-post bearing). Spin stays gear-driven; swing is the new DOF.
* Park the swing with an **angle driver** at 0° (engaged) for `rest`.
* `cone_disengaged` config: set the swing angle to the clear pose and
  `suppress_mate` the 20 `cone Tk:cyl120` gear mates (SW gear mates don't release
  at distance — they must be suppressed or they fight the swung-out pose) and the
  `16T:64T` drive.
* Swing-axis geometry is photo-calibrated against p.18/ch12 (the tip lifting from
  the knob-post U-slot); leave exact axis to implementation.

### Work item: p2 — pinion engage (`build_drive_train_assembly.py`)

The whole alignment-pinion rig is fixed today (`:462-500`). The engage DOF is the
two swing straps (`pinion-bracket` front/back) carrying the drum, pivoting about
`pinion-pivot-shaft` to mesh the drum with the cylinder drum (rest C2C → engaged
`ENGAGED_C2C = 68.58`, `:261`).

* `float_component` the **swinging group** only: `alignment-pinion` (drum), both
  `pinion-bracket`s, `pinion-handle`. **Keep fixed** the stationary support:
  `pinion-pivot-block` ×2, `pinion-pivot-shaft`, `pinion-lift-rod`, `pinion-lever`.
* Add a revolute of the swinging group about `pinion-pivot-shaft`; **park with an
  angle driver** at the disengaged rest (= today's pose) for `rest`.
* `pinion_engaged` config: set the swing angle to mesh and add a `pinion:cyl`
  gear mate (created **suppressed**, unsuppressed only in this config). Typically
  pair with cone disengaged (alternate drive) — encode that in the same config.

### Engagement-state configurations

Create three configs (`create_configuration`) over the top-level or drive-train
assembly:

| Config | cone swing | cone mesh mates | pinion swing | pinion mesh | Used for |
|---|---|---|---|---|---|
| `rest` (default) | 0° engaged | active | parked out | suppressed | exports, renders, photo gate |
| `cone_disengaged` | swung clear | suppressed | parked out | suppressed | ch12 demo / maintenance |
| `pinion_engaged` | swung clear | suppressed | swung in | active | ch25 alignment |

`rest` must byte-for-byte reproduce today's saved pose — assert it against the
current `assert_components_fully_defined` + interference gates and a render diff.

### Verification

* **Mobility (Kutzbach/Gruebler) check** in `rest` with park drivers active →
  must read **0 DOF** (gate still passes; determinism preserved). Suppress the
  park drivers → operating model reads **1 DOF** (crank). Add a small mobility
  probe helper.
* **Existing gates unchanged** in `rest`: `assert_components_fully_defined`,
  `check_no_interference`.
* **Motion studies** (existing Basic-Motion pipeline, `build_motion_study.py`):
  crank sweep already proven; add short studies that drive the p1 swing, the p2
  swing, and a p0 amplitude sweep to confirm the new joints articulate without
  conflict.
* **Render-pipeline regression:** rebuild `rest`, re-export, diff against the
  current 469-pair baseline — zero drift expected.

---

## Sequencing

1. **Part 1** (patterns) — small, isolated, de-risks `pattern_components_linear`
   headlessly. Validate on `CHANNEL_COUNT=3`, then 20.
2. **p0** amplitude slide — contained to `build_channel_assembly.py`, no
   engagement-state machinery.
3. **p1** cone swing + `cone_disengaged` config.
4. **p2** pinion de-fix + swing + `pinion_engaged` config.
5. **Configurations + mobility probe + motion studies + render regression.**

Each step commits independently; `rest` must pass the existing gates after every
step so the static deliverable never regresses.

## Refined joint topology (from code reading — for execution)

* **p0 amplitude (`build_rocker_arm.py` + `build_channel_assembly.py`):** the rocker
  top edge is the R800 concave arc, centre local `(0, 816)`; the book ties the
  radius to the bar length *"minimizing nonlinearity as the bar slides"* — the
  foot sliding ±88 mm along this arc IS the amplitude. Joint: bar foot-notch roof
  tangent/coincident to the rocker top-edge R800 face (leave slide free) + top-pin
  revolute to the lever (exists). Park: **distance driver** = foot station along
  the arc (default = today's solved contact). Bar `foot axis` = `Axis2@amplitude-bar`
  (local y=0); rocker pivot bore = `Axis1@rocker-arm` (local (0,8)).
* **p1 cone disengage (`build_cone_pivot_post.py` + `build_drive_train_assembly.py`):**
  the cone swings **horizontally (about a vertical/Y axis) through the big-end
  journal** in the pivot-post — explicitly *"not modeled"* today (post is a fixed
  Z-bore block, journal axis = `Axis1@cone-pivot-post` at Top+76). The current
  cone↔post **coincident** mate makes them coaxial (spin journal) and *blocks the
  swing* — so the swing must be a config-conditional joint: `rest` keeps the
  coaxial journal + 20 gear mates; `cone_disengaged` swaps to a Y-axis revolute
  at the journal point (angle driver to the clear pose) and `suppress_mate`s the
  coaxial journal mate + 20 `cone Tk:cyl120` + `16T:64T`. (Hardest of the three —
  needs live probing.)
* **p2 pinion engage (`build_pinion_pivot_shaft.py` + `build_drive_train_assembly.py`):**
  cleanest — the swinging group (`alignment-pinion` + both `pinion-bracket`s +
  `pinion-handle`) revolutes about the `pinion-pivot-shaft` **Z-axis** at
  `(PIVOT_X 27.85, PIVOT_Y 62.8)`. `float_component` that group; concentric the
  brackets' pivot bore to the shaft; **angle park driver** at the rest lean
  (`STRAP_LEAN_DEG 75.62`). `pinion_engaged` config: angle to mesh (`ENGAGED_C2C
  68.58`) + unsuppress a `pinion:cyl` gear mate (created suppressed).

## Risk register

* **Under-defining without a park driver → non-deterministic pose → broken
  exports.** Mitigation: every new DOF ships with its park driver in the same
  commit; `rest` stays fully defined.
* **SW gear mates don't disengage at distance** — must `suppress_mate` per config.
* **De-fixing too much** (floating the whole pinion rig) drifts the stationary
  support. Float only the swinging group.
* **Pattern instances** must satisfy the fully-defined + interference gates and
  not break name-based references (grep first).
* **Makers seat = Basic Motion only** (not MotionAnalysis) — known constraint.
