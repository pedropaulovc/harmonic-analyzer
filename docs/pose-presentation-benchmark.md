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
presentation maximises an Opus subagent's ability to:

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
| mixed | 6 random 2–3-parameter combos per pair, components drawn from the above |
| control | unperturbed (for false-positive rate) |

Renders come from the existing `render_offline.py` path (Blender, exact
manifest camera model), so generation is pure pipeline reuse. Stratify pairs:
macro vs wide framing, dark vs white background, occlusion-heavy (ch17) vs
open (ch30 standards).

## Presentation arms

All arms consume the same two inputs — prepared ref and content-fitted render
at identical registration (the `_fitted_render` transform, neutral align) —
and are normalised to the **same total pixel budget** (~1.4 MP per stimulus,
whether one fused image or a sheet), so no arm wins by resolution.

| id | arm | build recipe |
|---|---|---|
| P1 | **blend-red (incumbent)** | grayscale ref + red-tinted render at α 230/255 (`composite.blend_overlay`) |
| P2 | **side-by-side** | ref \| render, thin neutral gap (the pose-round sheets) |
| P3 | **side-by-side + labelled grid** | P2 with a 10×10 grid, row/column labels on both halves (SoM-style speakable coordinates) |
| P4 | **onion ladder** | 5-tile strip: ref/render opacity 100/0, 75/25, 50/50, 25/75, 0/100 |
| P5 | **blend-subtle** | as P1 but α ≈ 100 and a desaturated tint, so photo texture survives under the render |
| P6 | **checkerboard** | 8×8 alternating tiles ref/render (registered structure reads continuous across tile seams) |
| P7 | **green-magenta fusion** | ref → green channel, render → magenta (R+B); registered = gray, misregistration = complementary fringes |
| P8 | **difference heatmap** | \|ref−render\| grayscale → viridis/inferno colormap, plus the raw pair as thumbnails |
| P9 | **edge overlay** | render's silhouette/Canny edges drawn 2 px in a saturated colour over the untouched colour ref (photo texture fully visible) |
| P10 | **flicker pair** | the two registered full-frame images sent as two consecutive images in one message (blink-comparator analogue) |
| P11 | **dashboard** | one sheet: small sbs pair + P7 fusion + P9 edges (does combining views beat any single view?) |

Secondary factor (crossed only with the 3 best arms in a second phase):
**coordinate grid on/off** — SoM suggests the grid may contribute more than
the blend mode; measuring it separately avoids attributing its gain to an arm.

## Tasks

- **T1 — single-shot direction read.** One stimulus, one response. The
  subagent outputs, per parameter, `direction ∈ {-, 0, +}` and a magnitude
  bucket (`small / medium / large`), as structured output. Primary metric.
- **T2 — closed loop.** The subagent iterates: read stimulus → propose a
  camera correction → harness re-renders → new stimulus, ≤ 6 rounds. Measures
  what actually matters in production. Run only for the top-3 arms from T1
  (it is ~10× the cost).
- **T3 — 2AFC discrimination.** Two stimuli of the same pair (deltas d₁ < d₂),
  "which is better aligned?" Sweeping d₂/d₁ yields a psychometric curve per
  arm — the arm's *detection threshold*, cheap to run and robust to prompt
  wording.

## Metrics

| task | metrics |
|---|---|
| T1 | per-parameter sign accuracy; magnitude bucket accuracy; false-positive rate on controls; per-arm confusion between parameters (e.g. az error read as target-x — the classic degeneracy) |
| T2 | final pose error (rotation geodesic ° + target mm + zoom %); rounds to reach az/el ≤ 1°, target ≤ 5 mm; % diverged |
| T3 | psychometric threshold (delta ratio at 75% correct); AUC |
| all | tokens + images per decision; latency |

## Controls

- Fixed model (Opus), temperature 0, fresh subagent per cell (no context
  bleed), one fixed prompt template per arm (prompt text published with the
  benchmark; no per-arm tuning beyond describing the encoding).
- Randomise ref/render side in P2/P3 and order in P10 (position bias is
  documented — report it as its own number).
- Equal pixel budget per stimulus; JPEG q90 everywhere.
- N ≥ 3 repeats per cell for CIs on the T1 headline numbers.

## Size & cost envelope

T1: 18 pairs × ~26 cases × 11 arms ≈ 5.1k cells — subsample to 6 stratified
pairs for the first pass (≈1.7k cells; at ~1.5k tokens/cell ≈ 2.6M tokens).
T3: 6 pairs × 8 delta-pairs × 11 arms ≈ 0.5k cells. T2: 3 arms × 6 pairs × 4
deltas × ≤6 rounds ≈ 0.4k renders + calls. Generation: ~500 Blender renders,
minutes on the GPU seat.

## Harness sketch (all new code lives outside the shipping pipeline)

- `comparisons/bench/presentations.py` — the 11 builders (P1/P2 wrap existing
  `composite.py` code; the rest are ~10 lines of Pillow each).
- `comparisons/bench/gen_cases.py` — perturb manifest cameras → temp manifest
  → `render_offline.py` → stimuli + `cases.jsonl` (pair, delta, arm, paths).
- `comparisons/bench/run.py` — fans out one subagent per cell (Agent tool /
  Workflow), structured-output schema per task, appends `results.jsonl`;
  resumable (skip answered cells).
- `comparisons/bench/report.py` — tables above + per-arm exemplar sheets.

## Decision rule

Adopt the arm (or arm+grid combo) that wins T1 sign accuracy with ≥5-point
margin AND does not lose T2 convergence; retire `_blend.jpg` generation from
the pipeline if the incumbent P1 is beaten on both, keeping the winner as the
artefact `composite.py` emits. If P2/P3 win, the gallery keeps `_cad` (the
slider) and the pipeline simply stops paying for blends.
