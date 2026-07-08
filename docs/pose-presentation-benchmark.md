# Pose-feedback presentation benchmark (design — NOT yet run)

Which image presentation lets a vision-model subagent read camera-pose error
best? The comparison workflow's `_blend.jpg` (grayscale ref under a red-tinted
render) is the incumbent, but two incidents this cycle raise doubt: the pose
rounds were actually driven by side-by-side sheets (the blend was too hard to
read for coarse pose work), and a railed `tune_align` fit shipped unnoticed
because nobody re-read the blend after `--write`. This document surveys prior
art and specifies a benchmark that would settle the question empirically.
**Design only — do not run without an explicit go.**

## Prior art

Registration *visualization for humans* is a mature field; none of it has been
evaluated as *VLM input*. That gap is what this benchmark fills.

- **Medical image registration QA** (the richest source). AAPM guidance and
  clinical fusion workstations standardise four displays, all designed to make
  misregistration pop: **checkerboard composite** (alternating tiles from each
  image — continuous anatomy across tile borders = registered), **colour
  fusion** (complementary channels, e.g. green vs magenta: registered
  structure sums to gray, misregistration shows as colour fringes),
  **difference image**, and **linked side-by-side cursors**. See
  [Use of image registration and fusion algorithms and techniques in
  radiotherapy (AAPM TG-132, Med. Phys. 2017)](https://aapm.onlinelibrary.wiley.com/doi/10.1002/mp.12256)
  and the [overlay/checkerboard visual-assessment
  figures](https://www.researchgate.net/figure/Image-overlay-displays-and-checkerboard-images-for-visual-assessment-a-image-overlay_fig4_364593101).
  Colour-scale choice measurably changes human comparative judgement
  ([PMC5148121](https://pmc.ncbi.nlm.nih.gov/articles/PMC5148121/)).
- **Astronomy**: the *blink comparator* — rapid temporal alternation of two
  registered plates — is historically the most sensitive human
  difference-detector (Tombaugh found Pluto with one). VLMs have no temporal
  fusion, but the closest analogue (the same framing presented as two
  sequential messages) is testable.
- **Animation**: *onion-skinning* — semi-transparent superposition of adjacent
  frames — is the direct ancestor of the user-proposed transparency ladder.
- **VLM-specific evidence** (why this needs its own benchmark rather than
  borrowing the human answer):
  - [Set-of-Mark prompting (arXiv 2310.11441)](https://arxiv.org/abs/2310.11441):
    overlaying explicit marks/grids unlocks grounding that raw images do not —
    suggests a labelled coordinate grid may matter more than the blending
    choice itself.
  - [MuirBench (arXiv 2406.09411)](https://arxiv.org/html/2406.09411v1) and
    [position-bias analysis (arXiv 2503.13792)](https://arxiv.org/html/2503.13792v1):
    multi-image reasoning is a documented VLM weakness with strong order/
    position bias — a caution against assuming side-by-side is well-served,
    and a mandatory control (randomise which side the ref is on).
  - Render-and-compare pose methods (iNeRF and descendants) optimise
    photometric loss by gradient, not by VLM reading — no transferable answer.

No published work was found evaluating which composite lets a VLM estimate a
*pose delta*. The benchmark below is therefore novel.

## Question under test

Given a reference photo and a render from a perturbed camera, which
presentation maximises a vision agent's ability (two subject models — see
"Subject models") to:

1. **Detect** that the pose is off (vs an unperturbed control),
2. **Read the direction and rough magnitude** of the error in camera terms
   (az / el / roll / target-x / target-y / zoom),
3. **Converge** an iterative pose-correction loop in few rounds,

at what token cost?

## Ground truth

The 18 frozen pairs (8 ch30 + 10 book close-ups) with their user-approved
cameras are the zero-error anchors. Perturbed cases are generated, so every
case has an exactly known delta — **no LLM judging anywhere; all scoring is
deterministic.**

Perturbation grid, applied one parameter at a time plus a mixed tier:

| class | levels |
|---|---|
| az, el, roll | ±1°, ±3°, ±7°, ±15° |
| target (image-plane x and y separately) | ±5, ±15, ±40 mm |
| zoom | ×0.85, ×1.18 |
| mixed | 6 seeded 2–3-parameter combos per pair (see below) |
| control | unperturbed (for false-positive rate) |

**Target deltas are image-plane, converted at generation.** The renderer's
camera input is a 3-D world-space `target_mm`; a "target-x +15 mm" case is
produced by offsetting the pair's base target along the **unperturbed
camera's right (x) or up (y) axis** — the same r/u basis `blender_worker.py`
derives from az/el/roll — never along world X/Y (a world-axis move changes
projected sign/magnitude with azimuth and roll, corrupting the scores).
`gen_cases.py` does this conversion once and records the resulting world
target in `cases.jsonl`.

**The mixed tier is seeded, drawn once, and committed.** `gen_cases.py`
draws each pair's 6 mixed cases with `random.Random(f"{pair_id}:mixed")`
(2 or 3 distinct parameters, components sampled uniformly from the
single-parameter levels above) and records them in `cases.jsonl` — the
ground-truth artefact every run shares. Re-generating with the same seed
reproduces the identical cases; the first-pass sub-grid uses the first 4 of
each pair's 6.

Renders come from the existing `render_offline.py` path (Blender, exact
manifest camera model), so generation is pure pipeline reuse. Stratify pairs:
macro vs wide framing, dark vs white background, occlusion-heavy (ch17) vs
open (ch30 standards).

## Presentation arms

All arms consume the same two inputs — the prepared ref and the perturbed
render — and are normalised to the **same total pixel budget** (~1.4 MP per
stimulus, whether one fused image or a sheet), so no arm wins by resolution.

**Fixed framing, NOT the pipeline's content fit.** The shipping composite path
(`trim_render_file` + `composite._fitted_render`) crops the render to its
content and rescales/centres it into the ref frame — which would *silently
cancel* exactly the target- and zoom-perturbation signal this benchmark
measures (a shifted or zoomed render re-centres back onto the ref). Benchmark
renders are therefore produced **untrimmed on a fixed canvas** (skip
`trim_render_file`; the unperturbed camera defines the canvas framing for the
whole case family) and every arm pastes ref and render into that same fixed
frame with no per-image re-fitting. Only rotation reads survive content
fitting; translation/zoom reads require this.

**The pair's baseline 2-D align is frozen into the frame, not re-fit.** Some
approved anchors are only registered *after* the manifest `align` (e.g.
`ch30-p002` carries scale 1.13 / dy −233); pasting raw renders would make
even the zero-error control start misregistered, inflating false positives.
`gen_cases.py` applies each pair's manifest align **once**, as a constant of
the whole case family (same scale/offset for the control and every delta),
so the control sits registered and perturbations move relative to it.

| id | arm | build recipe |
|---|---|---|
| P1 | **blend-red (incumbent)** | grayscale ref + red-tinted render at α 230/255, rebuilt fixed-frame in `presentations.py` — do NOT call `composite.blend_overlay`/`_fitted_render` (their content re-fit would cancel the very target/zoom deltas under test; only the `_render_rgba` tint math is reused) |
| P2 | **side-by-side** | ref \| render, thin neutral gap (the pose-round sheets) |
| P3 | **side-by-side + labelled grid** | P2 with a 10×10 grid, row/column labels on both halves (SoM-style speakable coordinates) |
| P4 | **onion ladder** | 5-tile strip: ref/render opacity 100/0, 75/25, 50/50, 25/75, 0/100 |
| P5 | **blend-subtle** | as P1 but α ≈ 100 and a desaturated tint, so photo texture survives under the render |
| P6 | **checkerboard** | 8×8 alternating tiles ref/render (registered structure reads continuous across tile seams) |
| P7 | **green-magenta fusion** | ref → green channel, render → magenta (R+B); registered = gray, misregistration = complementary fringes |
| P8 | **difference heatmap** | \|ref−render\| grayscale → viridis/inferno colormap, plus the raw pair as thumbnails |
| P9 | **edge overlay** | render's silhouette/Canny edges drawn 2 px in a saturated colour over the untouched colour ref (photo texture fully visible) |
| P10 | **flicker pair** | the two registered full-frame images sent as two consecutive images in one message (blink-comparator analogue); each frame downscaled so the two together fit the shared ~1.4 MP budget (~0.7 MP each) — P10 must not win by carrying twice the pixels |
| P11 | **dashboard** | one sheet: small sbs pair + P7 fusion + P9 edges (does combining views beat any single view?) |

Secondary factor: **coordinate grid on/off** — SoM suggests the grid may
contribute more than the blend mode; measuring it separately avoids
attributing its gain to an arm. The grid phase is scheduled **inside the
first pass, after T1 and before T2** (T2's arm set depends on its outcome):
grid-ON variants of the T1 top-3 rerun the same 6-pair × 27-case sub-grid at
N = 3 (the grid-OFF numbers are T1's own) ≈ 1.5k calls ≈ 2.2M tokens per
model. If a grid variant displaces the plain arm as T1 winner, that exact
`arm+grid` variant enters T2 as an additional arm (budgeted like one) — the
decision rule must check convergence on the presentation actually being
adopted, not its grid-less sibling.

## Tasks

- **T1 — single-shot direction read.** One stimulus, one response. The
  subagent outputs, per parameter, `direction ∈ {-, 0, +}` and a magnitude
  bucket (`small / medium / large`), as structured output. Primary metric.
  Bucket ground truth is fixed per parameter class up front: rotations —
  small ≤ 2°, medium 3–8°, large > 8° (so levels 1/3·7/15 map to
  small/medium·medium/large); target — small ≤ 8 mm, medium 9–25 mm, large
  > 25 mm (5/15/40 → small/medium/large); zoom — ×0.85 and ×1.18 both score
  as `large` (only two levels; zoom magnitude is reported but excluded from
  the headline bucket-accuracy number). Mixed-tier components inherit their
  class thresholds.
- **T2 — closed loop.** The subagent iterates: read stimulus → propose a
  camera correction → harness re-renders → new stimulus, ≤ 6 rounds. Measures
  what actually matters in production. Run for the **top-3 arms from T1 plus
  P1 whenever it is not already among them** — the decision rule needs the
  incumbent's T2 baseline, so P1 is never skipped — plus the grid phase's
  winning `arm+grid` variant if one displaced a plain arm (≤ 5 arms; T2 is
  ~10× the per-cell cost). Arm selection is **per subject model**: each
  model runs its own T1 ranking's top-3 (+P1 +grid variant), so the Codex
  generalization check has closed-loop data for its own winner, not Opus's. Start deltas are pinned, 6 per pair — one per parameter
  class so T2 is direct evidence for every parameter the decision rule
  leans on: `az +7°`, `el −7°`, `roll +7°`, `zoom ×0.85`, `target-x +25 mm`,
  and the pair's first recorded mixed case (M1 from `cases.jsonl`).
  Convergence covers **every** perturbed parameter: az/el
  ≤ 1°, roll ≤ 1°, target ≤ 5 mm, zoom within ±3% — a roll- or zoom-carrying
  start cannot count as converged on az/el alone.
- **T3 — 2AFC discrimination.** Two stimuli of the same pair (deltas d₁ < d₂),
  "which is better aligned?" Sweeping d₂/d₁ yields a psychometric curve per
  arm — the arm's *detection threshold*, cheap to run and robust to prompt
  wording. The 8 delta-pairs (d₁, d₂) are pinned: az (1°, 3°), az (3°, 7°),
  az (7°, 15°), el (3°, 7°), roll (3°, 7°), target-y (5, 15 mm),
  target-y (15, 40 mm), target-x (15, 40 mm). Presentation order is NOT
  "d₁ first" (that would make "first" always correct): which delta is shown
  first follows the same deterministic parity schedule as the other
  position-bias controls — `zlib.crc32(f"{case_id}:{arm}:{repeat}:t3")` —
  balanced, identical across executions and models, recorded per row. T3
  cells run the same N = 3 repeats as T1 (the schedule's `repeat` term is
  live): 144 trials per arm-model curve instead of a thin 48.

## Metrics

| task | metrics |
|---|---|
| T1 | per-parameter sign accuracy; magnitude bucket accuracy; false-positive rate on controls; per-arm confusion between parameters (e.g. az error read as target-x — the classic degeneracy) |
| T2 | final pose error (rotation geodesic ° + target mm + zoom %); rounds to reach az/el ≤ 1°, roll ≤ 1°, target ≤ 5 mm, zoom ±3% (all must hold); % diverged |
| T3 | psychometric threshold (delta ratio at 75% correct); AUC |
| all | tokens + images per decision; latency |

## Subject models (crossed factor — every cell runs on both)

| model | invocation | pinning |
|---|---|---|
| **Claude Opus** (the production pose agent) | Agent tool, one fresh subagent per cell | the runner passes `model: "opus"` **explicitly on every spawn** — never rely on inheritance (a subagent inherits the orchestrating session's model by default, which may not be Opus). `run.py` hard-codes the override; a smoke assertion checks the spawned model id before fan-out. |
| **Codex CLI, gpt-5.5, high reasoning** | `codex exec` non-interactive, one invocation per cell | `--model gpt-5.5` + reasoning effort `high` (config flag, e.g. `-c model_reasoning_effort="high"`), stimulus images attached per cell (`-i`), same prompt template and the same JSON output schema (the runner parses the JSON from stdout). Exact flag spellings are verified against the installed `codex` version during harness build and committed in `run.py`. |

Model is fully crossed with arm × case × task: same stimuli, same prompts,
same N. Report every table per model. The **decision rule applies to the
Opus numbers** (Opus is what runs pose feedback in production); the Codex
column is a generalization check — if the winning arm flips between models,
report that prominently instead of averaging it away.

## Controls

- Two fixed subject models (see above), temperature 0 where the backend
  exposes it, fresh context per cell (no bleed), one fixed prompt template
  per arm (prompt text published with the benchmark; no per-arm or per-model
  tuning beyond describing the encoding).
- Balance ref/render side in P2/P3 and order in P10 (position bias is
  documented — report it as its own number). The assignment is
  deterministic, not sampled at run time: side/order = parity of
  `zlib.crc32(f"{case_id}:{arm}:{repeat}")` (balanced across cells,
  identical across executions and both subject models), and each
  `results.jsonl` row records the assignment it used.
- Equal pixel budget per stimulus; JPEG q90 everywhere.
- N ≥ 3 repeats per cell for CIs on the T1 headline numbers.

## Size & cost envelope

The grid is 45 cases/pair (3 rotation params × 8 levels = 24, 2 target axes ×
6 levels = 12, 2 zoom levels, 6 mixed, 1 control). Full T1 would be 18 pairs
× 45 × 11 arms ≈ 8.9k cells *per model* — so the first pass subsamples: **6
stratified pairs × a 27-case sub-grid** (rotations ±3°/±15° = 12, targets
±15/±40 mm × 2 axes = 8, both zooms, the first 4 mixed, 1 control) × 11 arms
≈ 1.8k cells; with N = 3 repeats ≈ **5.3k calls ≈ 8.0M tokens per subject
model** at ~1.5k tokens/cell, ≈ 10.7k calls / 16M tokens across both.
T3: 6 pairs × 8 delta-pairs × 11 arms × N = 3 ≈ 1.6k calls per model. Grid
phase: ≈ 1.5k calls per model (see "Presentation arms"). T2: ≤5 arms
(top-3 + P1 + a winning grid variant, selected per subject model) × 6 pairs
× 6 starts × ≤6 rounds ≈ 1.1k renders + calls per model worst case. First
pass all-in (T1 sub-grid + grid phase + T3 + T2): ≈ **9.5k calls ≈ 14M
tokens per model**, ~28M across both. Generation: 18 pairs × 45 ≈ 800 Blender renders once (shared by all
arms **and both models**), minutes on the GPU seat.

**Full-grid confirmation is a separately approved phase, not part of the
first-pass budget.** It covers the **top 3 arms, plus P1 whenever it is not
among them, plus the winning `arm+grid` variant if one displaced a plain
arm** (the retirement comparison must be full-grid vs full-grid — no
adoptable presentation may carry only subset numbers) on the cells the
first pass did not run: ≤5 arms × (18×45 − 6×27) × N = 3 ≈ **9.7k calls ≈
14.6M tokens per model** — larger than the first pass itself. Project it, report it, and get
an explicit go before starting it; the first-pass budget gate does not
authorize it.

## Harness sketch (all new code lives outside the shipping pipeline)

- `comparisons/bench/presentations.py` — the 11 builders, **all** operating
  on the same fixed-frame ref/render pair (~10 lines of Pillow each; P1
  reuses only `composite._render_rgba`'s tint math — never `_fitted_render`,
  see the P1 row).
- `comparisons/bench/gen_cases.py` — perturb manifest cameras (image-plane →
  world target conversion, seeded mixed draws, frozen baseline align — see
  "Ground truth") → temp manifest with synthetic case ids
  (`<pair_id>+<delta_tag>`, e.g. `…-img01+az+7`) → `render_offline.py` →
  stimuli + `cases.jsonl`. **Prerequisite flags on `render_offline.py`** (it
  currently hardcodes `composite.load_manifest()`, writes through
  `composite.pair_paths()` into the shipping `comparisons/render/` tree, and
  ends with `composite.regenerate()` — all three must be bypassable):
  `--manifest <path>`, `--no-trim --canvas WxH` (fixed framing, see
  "Presentation arms"), `--out-root <dir>` (renders + sidecars under
  `<dir>/render/` **and prepared references under `<dir>/ref/`** —
  `prepare_reference` also writes through `pair_paths()` into
  `comparisons/ref/`, which `cut_release.stage_comparisons` ships wholesale,
  so bench refs must be redirected too, not just renders), and
  `--skip-composites` (no gallery/scores regeneration — bench stimuli are
  built by `presentations.py`). Together these guarantee bench cases never
  touch the shipping gallery cache or release bundle, whatever their ids.
- `comparisons/bench/run.py` — fans out one fresh-context call per cell ×
  subject model: Opus via the Agent tool with the explicit `model: "opus"`
  override, Codex via `codex exec` (see "Subject models"); structured-output
  schema per task, appends `results.jsonl` tagged with the model; resumable
  (skip answered cells).
- `comparisons/bench/report.py` — tables above + per-arm exemplar sheets.

## Decision rule

Adopt the arm (or arm+grid combo) that wins T1 sign accuracy with ≥5-point
margin AND does not lose T2 convergence; retire `_blend.jpg` generation from
the pipeline if the incumbent P1 is beaten on both, keeping the winner as the
artefact `composite.py` emits. If P2/P3 win, the gallery keeps `_cad` (the
slider) and the pipeline simply stops paying for blends.

Retiring the blend is a coordinated change, not a deletion: current consumers
hard-require it — `cut_release.stage_comparisons` lists
`composite/<id>_blend.jpg` in its complete-or-absent gallery validation, and
`gallery.py` renders a blend cell per pair. The retirement PR must swap both
to the winning artefact (or drop the cell) in the same change, or every
release would ship galleryless with a "gallery incomplete" warning.

## Runbook — everything an executor needs

The instruction "run the benchmark in docs/pose-presentation-benchmark.md" is
sufficient given this section. All decisions are pinned; do not re-ask them.

1. **Seat preconditions**: Blender seat (the render_offline path must work),
   `uv sync` done, and a **current `cad/out` STL/boxes cache**. The benchmark
   run itself needs no SolidWorks — but *producing* that cache does
   (`doit export` is a COM-spine task on a SolidWorks seat). On a
   Blender-only seat, pull an already-built tree (remote cache / a seat that
   ran the export); do not attempt `doit export` locally. Also: `codex` CLI
   installed and authenticated, with `gpt-5.5` available.
2. **Build the harness first** (nothing exists yet): the four
   `comparisons/bench/` files from the harness sketch, plus the four
   `render_offline.py` flags (`--manifest <path>`, `--no-trim --canvas WxH`,
   `--out-root <dir>`, `--skip-composites`). Bench outputs live in
   `comparisons/bench/out/` — add it to `.gitignore`; the bench *code* is
   tracked. Nothing the bench renders may land under `comparisons/render/`
   or `comparisons/composite/`.
3. **First-pass pairs** (stratified, pinned — manifest-exact ids, the
   renderer's `--only` matches `pair["id"]` verbatim):
   `harmonic_analyzer--ch30-p002-img01` (wide, dark),
   `harmonic_analyzer--ch30-p007-img01` (wide, dark, oblique),
   `harmonic_analyzer--ch12-p002-img09` (macro, dark),
   `harmonic_analyzer--ch12-p001-img02` (macro, white bg),
   `harmonic_analyzer--ch17-p002-img06` (macro, occlusion-heavy),
   `harmonic_analyzer--ch23-p004-img02` (down-look macro).
4. **Runner config** (pinned): both subject models per "Subject models" —
   Opus subagents spawned with the **explicit `model: "opus"` override**
   (never inherited), and `codex exec --model gpt-5.5` at high reasoning
   effort; temperature 0 where exposed, fresh context per cell, structured
   output, N = 3 repeats, prompt templates committed beside the runner
   before the first full pass.
5. **Smoke before fan-out**: run ~10 hand-picked cells (one easy + one hard
   delta on two arms) **on each subject model**, verify the Opus spawn
   reports the Opus model id and the codex invocation returns parseable
   JSON, eyeball the stimuli sheets and the parsed outputs, THEN fan out. Do
   not launch 5k cells on an unsmoked harness.
6. **Budget gate — per phase, not per benchmark**: the first pass all-in
   (T1 sub-grid ≈ 5.3k + grid phase ≈ 1.5k + T3 ≈ 1.6k + T2 ≤ 1.1k calls)
   ≈ **9.5k calls / ~14M tokens per subject model** (~28M across both);
   abort and report if its projected total exceeds 16M tokens per model.
   Phase order within the first pass: T1 → grid phase → T3 ∥ T2 (T2's arm
   set needs T1 + grid results; T3 needs only T1 stimuli). The **full-grid
   confirmation (≈ 14.6M tokens per model, see the cost envelope) is NOT
   covered by this gate** — project it after the first-pass report and get
   an explicit go before launching it.
7. **Deliverables**: `results.jsonl` + the report tables per subject model
   (per-arm T1 sign accuracy with CIs, T3 thresholds, cost per decision),
   per-arm exemplar stimulus sheets, and a recommendation applying the
   decision rule above to the Opus numbers, with the Codex column as the
   generalization check.
