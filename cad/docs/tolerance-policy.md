# Tolerance & fits policy

Tolerance is part of the **design source**, not a late drawing annotation. Because the output
is a force balance, *inconsistent* fits across the 20 channels bias the equilibrium rather than
just adding noise — **channel-to-channel consistency matters more than absolute precision**.
Fits are therefore shared parameters applied uniformly, never per-part magic numbers.

## Source of truth

Fit classes and clearances live in [`cad/config/tolerances.yaml`](../config/tolerances.yaml)
and flow into geometry and into part custom properties. The build scripts read named fit
classes; they do not hardcode clearance numbers.

Accuracy-driven limits on the **critical features** live in
[`cad/config/error_budget.yaml`](../config/error_budget.yaml) and are derived — not asserted —
by the sensitivity model [`cad/scripts/error_budget.py`](../scripts/error_budget.py)
(`uv run python cad/scripts/error_budget.py`; gate `check:budget`,
[`test_error_budget.py`](../scripts/test_error_budget.py)). Every number quoted below comes
from that report; regenerate it rather than trusting the prose.

The whole-device performance benchmark that constrains this allocation is
[`michelson-1898-trial-accuracy.md`](./michelson-1898-trial-accuracy.md):
approximately 0.7% full-scale mean absolute coefficient error on the historical
80-element machine, largest tabulated difference 2.0%. It is a comparison value, not a
demonstrated target for this project's 20 channels, and it is an assembled-machine output
result, not a percentage to apply to part dimensions. This document is the method that turns
it into dimensional limits.

## How a critical-feature tolerance is decided

A feature earns a tolerance tighter than its title-block general grade only through this
chain; a limit that cannot cite each step is a habit, not a requirement.

1. **Name the transfer quantity** the deviation perturbs: channel *gain*, channel *phase*,
   the *ordinate* setting, *hysteresis/deadband* in the force-summed path, or *readout*.
   A deviation that perturbs none of these (a cosmetic profile, a clearance on a
   one-sided-loaded joint) is not an accuracy feature; it gets a fit class or the general grade.
2. **Classify the deviation.**
   - *Common-mode* — the same on every channel (magnifier ratio, counter-spring rate, a
     spring-preload offset, the slide-arc gain curve). Removed by the calibration run and the
     mean-line zero of the readout procedure below. Free.
   - *Setup* — re-introduced by the operator each trial (measuring-stick reading, alignment).
     A procedure limit, not a machining limit.
   - *Channel-specific* — scatters independently per channel and enters the sum directly.
     This is the only class a **part** tolerance controls.
3. **Compute the sensitivity** — ∂(channel gain)/∂(feature) from the transfer function
   (table below), verified against finite differences of the exact kinematics.
4. **Convert scatter to coefficient error** by Monte Carlo through the readout procedure on the
   reference inputs, in % of the greatest term. Random per-channel gain scatter of σ is
   averaged down to roughly σ/√(2m) over m active channels for a broad spectrum, but shows
   up almost undiluted for a sparse one — so both a broad and a two-channel input are scored.
5. **Allocate** against the benchmark. The channel-specific scatter of every critical feature
   combined may consume at most `targets.scatter_mae_fs_pct` (0.30 % of the 0.7 %); the rest
   is reserved for the nominal-design residual, hysteresis and readout, which are not part
   tolerances. Then compare the derived limit with what a hobby shop and its instruments can
   hold and inspect; if capability is the binding constraint, change the *design* (matching,
   adjustment, calibration) rather than writing an unholdable number.
6. **Pick the drawing limit** as the tightest of (a) what accuracy needs from step 5, (b) what
   the fit class needs (a running fit only exists if the size limits are narrower than the
   clearance band), (c) what the process needs (wall, thread, wear) — and never tighter than
   the tightest of those. The report's `allowable` column is the accuracy bound alone.
7. **Verify on the assembled machine** with the trials in the last section; the model is a
   prediction until a trial confirms it.

## Transfer function and error model

The machine draws, with magnifier gain $G$,

$$
y(\theta) = G\sum_{i=1}^{20} w_i\, u_i(\theta),\qquad
u_i(\theta) \approx K\, d_i \cos(i\theta + \varphi_i),\qquad
w_i = \frac{s_i a_i}{\sum_j s_j a_j^2 + S b^2},
$$

where $d_i$ is the amplitude-bar station (the ordinate), $K = (\text{hook}/\text{bar-pin})\cdot
e/r_\text{pin}$ = 0.0907 mm of spring-hook motion per mm of station (cam throw
$e$ = 8.64, rod-pin radius $r_\text{pin}$ = 133.3, lever arms 177.8/127.0), $s_i$ the channel
spring rate, $a_i$ its hook's moment arm on the summing lever (39.85), $S$, $b$ the counter
spring (76.2). Coefficient $k$ is read at $\theta_k = k\pi/20$. A channel's *gain* is
$g_i \propto e_i\, s_i\, a_i \cdot(\text{hook}/\text{bar-pin})/r_{\text{pin},i}$; its *phase*
$\varphi_i$ is the cam-lobe angle relative to the common alignment. The denominator is
common-mode.

**Gain sensitivities** (% of channel gain per mm, spring per %; analytic | finite-difference
on the exact kinematics):

| feature | nominal | sensitivity | note |
|---|---:|---:|---|
| cam eccentricity `cylinder_gear_spec.ECCENTRICITY` | 8.64 | +11.57 \| +11.49 | the only dimension with a double-digit sensitivity |
| rocker rod-pin radius `rocker_arm_spec.ROD_HOLE_X` | 133.07 | −0.75 \| −0.74 | |
| channel-lever bar-pin arm `channel_lever_spec.BAR_PIN_X` | 127.0 | −0.79 \| −0.78 | |
| channel-lever spring-hook arm `channel_lever_spec.LEVER_SPRING_X` | 177.8 | +0.56 \| +0.56 | |
| summing-lever hook arm `summing_lever_spec.HOLE_X` (normal to the knife line) | 39.85 | +2.51 | hole position across the plate; the along-knife pitch is irrelevant |
| channel spring rate | 2.13 N/mm (derived) | +1.00 %/% | numerator only: the spring's share of the common denominator is calibrated out (below) |
| rocker slide radius, rod length, cam OD roundness, gear runout | — | < 0.1 %/mm | DC or 2·i harmonic only; not gain |

Phase: 1° of cam phase = 1.75 % of that channel's amplitude at the readout points where
$\sin(i\theta_k)=\pm1$. Gear tooth errors convert at the *driven* gear's radius (a 0.02 mm
flank error on any cone gear is 0.02/30.6 rad = 0.04° of the cylinder gear), so tooth
accuracy is not a phase driver; cam-lobe-to-notch registration and one-directional backlash
lag are.

### The nominal design has a residual before any tolerance

The exact kinematics (eccentric + rod + rocker pin on an arc + bar foot on the R800 slide + lever
arc) are not a pure cosine. From the report:

| station (mm) | gain / linear | 2nd harmonic / fundamental |
|---:|---:|---:|
| +88 | 1.0112 | 1.50 % |
| +44 | 1.0182 | 1.22 % |
| −44 | 0.9979 | 1.72 % |
| −88 | 1.0064 | 1.62 % |

- **Slider-crank distortion**: rod/throw ratio $e/L$ = 8.64/163.1 gives a second harmonic of
  $\approx e/4L$ = 1.3 % of each channel's amplitude, 1.2–1.7 % once the arc geometry is
  added. It aliases onto every readout point (channel 20's 2nd harmonic is +1.5 % at *all*
  $\theta_k$), so uncorrected it costs 0.1–0.2 % MAE and 1.3–1.5 % max on broad inputs and
  1.1 % MAE / 3.0 % max on the two-channel input — larger than every machining term combined.
- **Null station −0.52 mm**: the slide arc's low point sits 8 mm above the pivot centreline and
  the swing is one-sided (arm level at the top of the stroke), so a bar at the geometric zero
  still moves. 18 idle bars at "zero" add a coherent 0.6 %-of-a-channel error each.
- **Gain asymmetry** ±0.5 % between +d and −d from the same one-sided swing.

All three are deterministic functions of the design, so they are removed by procedure, not by
tolerance (readout section below). With the stick zeroed at the null station and the
second-harmonic correction applied, the nominal residual falls to ≤ 0.04 % MAE / 0.09 % max on
broad inputs (0.36 % max on the alternating-sign input) — the "+c2 corrected" column of the report.
Lengthening the rod would remove it by design but is not photo-faithful; the correction is the
period-appropriate answer (the machine computes, the operator corrects a known table).

## Result: the budget for the critical features

Monte Carlo of [`error_budget.yaml`](../config/error_budget.yaml) (4000 draws, every feature
uniform within ± tolerance per channel, calibrated readout), % of the greatest term. "broad"
pools the all-ones, half-rectangle, Gaussian and alternating inputs; "pair" is channels 1 and
20 alone, the consistency stress case. `allowable` is the tolerance at which the feature
*alone* would consume 0.05 % MAE or 0.5 % pair-p99, the equal-share allocation.

| feature | ± limit | broad MAE | broad p99 max | pair p99 | allowable | how it is held |
|---|---:|---:|---:|---:|---:|---|
| cam eccentricity | 0.025 mm | 0.024 | 0.14 | 0.27 | 0.046 | offset-turn in a 4-jaw, indicate the throw |
| rocker rod-pin radius | 0.10 mm | 0.006 | 0.04 | 0.07 | 0.71 | DRO/CNC hole position |
| lever bar-pin arm | 0.10 mm | 0.007 | 0.04 | 0.07 | 0.68 | DRO/CNC hole position |
| lever spring-hook arm | 0.10 mm | 0.005 | 0.03 | 0.05 | 0.96 | DRO/CNC hole position |
| summing hook arm | 0.15 mm | 0.032 | 0.18 | 0.35 | 0.22 | ½ of the 0.30 pattern-position zone |
| **spring rate** | **1.5 %** | **0.126** | **0.70** | **1.41** | 0.53 | **matched by measurement** (on the spec sheet), stock is ±10 % |
| cam phase | 0.25° | 0.035 | 0.19 | 0.22 | 0.36 | lobe and notch indexed in one setup (on the drawing) |
| mesh lag spread | 0.14° | 0.019 | 0.11 | 0.12 | 0.36 | derived from the 0.05–0.20 backlash band |
| station setting (setup) | 0.20 mm | 0.028 | 0.20 | 0.82 | 0.12 | measuring-stick reading, vernier-graduated |
| **all combined** | | **0.143** | **0.77** | **1.90** | | targets 0.30 / 1.5 / 2.0 |

The budget closes with a factor of two in hand on the broad inputs and just inside the
two-channel consistency target. Read it as follows.

- **The spring is the tolerance problem, not the machining.** At ±1.5 % matched it is half the
  scatter; stock springs at ±10 % would alone give ~0.8 % MAE and ~9 % worst-case on sparse
  spectra — more than the whole benchmark. The matching requirement is a manufacturing output:
  the spring spec sheet's `SET QC` note (`channel_spring_installed_notes.DRAWING_NOTES`,
  pinned by `check:budget`). Match first; the adjustable-hook alternative (a slotted spring
  hole on the channel lever, 0.56 %/mm) is the fallback if a batch cannot be binned, and
  departs from the photographs.
- **The eccentricity limit is capability-driven, not accuracy-driven.** Accuracy alone allows
  ±0.046 mm; the drawing's ±0.025 (`cylinder_gear_spec.DRAWING_NOTES`) is kept because an
  indicated offset in a 4-jaw reads to 0.01 mm and costs nothing extra. Relaxing to ±0.05 is a
  legitimate decision (it consumes 0.05 % MAE); `check:budget` pins the drawing note to the
  yaml so the two cannot silently diverge.
- **The lever arms need no `precision` grade for accuracy**: at the general ±0.10 they use 1/7
  to 1/10 of their allowable. Their bores still carry the `shaft_in_bushing` fit, which is
  what the tighter size limit on the *bore* is for.
- **Summing-lever hole position is the one plate feature that matters** (2.51 %/mm across the
  knife line). Drill the 20 holes from one fixture; the along-knife pitch can be loose.
- **Phase is cheap if lobe and notch are cut in one setup.** ±0.25° is 0.13 mm at the notch.
  Crank in one direction only; a reversal re-seats every mesh on the other flank
  (0.05–0.20 mm backlash = 0.09–0.37° at the 120T pitch radius).
- **Every clearance in the position-driven chain is benign under one-sided load** — strap on
  cam, rod pin, rocker pivot, bar foot, top pin, spring hooks — because the channel spring
  preloads the whole chain in one direction for a station of fixed sign. The strap's
  0.20 mm diametral clearance would otherwise be a 2.3 %-of-amplitude step: it becomes a DC
  offset the mean-line zero removes. Fit classes on these joints exist to prevent binding, not
  for accuracy; do not tighten them in the name of accuracy.

### Terms the budget reserves outside the part tolerances

| term | size | what it depends on | controlled by |
|---|---|---|---|
| nominal residual after correction | ≤ 0.04 % MAE | design geometry | null-station zero + 2nd-harmonic correction |
| knife-edge hysteresis | 2.2 % of one channel's full scale per 0.01 mm of edge rolling-resistance length, at the derived 1.5 kN edge load | edge sharpness/hardness, total spring load | hardened insert on a hardened seat (assessment §6); *measured* as trace width on a slow reversal |
| ordinate readout | 0.67 % FS per 0.1 mm of reading at the modelled 15 mm half-stroke | pen line width, grid interpolation, pen stroke | run the magnifier/pen at the largest stroke the paper allows: a 0.3 mm line read to half its width is ±1.0 % FS at 15 mm half-stroke, ±0.4 % at 40 mm |
| timebase (reading at the wrong θ) | 0.84 % FS per 0.1 mm of abscissa at the 1.596 mm/crank-turn feed; 0.21 % with the coarse T24/T12 set; 0.30 % for a crank stopped on an index within ±8° | paper feed ratio, index repeatability | stop the crank on its index at 2k turns and read the pen, or use the coarsest feed |

The knife and readout terms are why the paper's 0.7 % is hard even with perfect parts. They are
procedure and design-adjustment items and are listed so no one tries to buy them back with
tighter machining.

## Readout and calibration procedure (what the model assumes)

The Monte Carlo and the residual numbers above hold only under this procedure; it is part of
the specification.

1. **Zero the measuring stick at the null station**, found on the assembled machine: with one
   bar alone, slide it until the fundamental vanishes (the model says −0.52 mm from the pivot
   zero). Graduate or calibrate the stick from single-channel runs, not from a ruler — the gain
   deviates from linear by up to 1.8 % and differs between +d and −d (table above), and Michelson's
   own stick was "hand stamped, unevenly spaced" for the same reason.
2. **Calibration run**: every bar at full scale, one full period. The k = 0 reading above the
   mean line is $K\cdot 20\cdot d_\text{max}$; this $K$ scales every trial and removes all
   common-mode gain.
3. **Mean-line zero**: for each trial, take the zero as the mean of the trace over one full
   period, not the pen's neutral position. This removes the one-sided-swing DC, spring-preload
   scatter, strap-clearance offsets and tare drift in one step.
4. **Second-harmonic correction**: subtract $\sum_i x_i\,\kappa_i \cos(2 i\theta_k)$ from
   reading $k$, with $\kappa_i$ the per-station ratio from the report (or measured: run channel
   20 alone; $\kappa = (r_\text{even}-|r_\text{odd}|)/(r_\text{even}+|r_\text{odd}|)$ over its
   alternating readings). The ordinates $x_i$ are known — the operator set them.
5. **Crank in one direction**, and read coefficient $k$ with the crank stopped on its index at
   $2k$ turns (the 80-turn period makes $\theta_k = k\pi/20$ exactly two turns apart) rather
   than at a ruled abscissa on a moving paper.
6. Report errors as $e_k = (O_k - C_k)/\max_j|C_j|$ with $C_k$ computed by the **same
   20-sample rule** the machine realises, so quadrature error is never charged to the hardware.

## Assembled-machine verification (which trial detects which feature)

| trial | procedure | detects | pass |
|---|---|---|---|
| channel consistency | each bar alone at full scale, read the k = 0 amplitude | spring rate, eccentricity, arms, summing holes (gain scatter) | every channel within ±2 % of the mean (the budget's combined worst case is ±2.4 %); an outlier is a spring to swap |
| channel phase | same runs, zero-crossing position vs. expected | cam-to-notch, mesh lag | ≤ 0.4° each (0.25° + 0.14° budgeted) |
| hysteresis | one bar at full scale, crank forward then back slowly | knife edge, wheel bearing, wire preload | proposed: trace width ≤ 1 % of that channel's stroke (an edge rolling-resistance length ≤ 0.005 mm at the derived load) |
| null station | one bar near zero, find the station of vanishing fundamental | slide-arc height, stick zero | record; stamp the stick from it |
| broad-input benchmark | Michelson's Gaussian ($e^{-(0.1i)^2}$) and half-range rectangle, corrected readout | everything | MAE ≈ 0.7 %, max ≈ 2 % of the greatest term — historical parity |
| sparse-input stress | channels 1 and 20 alone | consistency without averaging | worst coefficient ≤ 2 % |

## Fit classes (interfaces that must carry a rule)

| Interface | Class | Intent |
|---|---|---|
| shaft ↔ bushing (crank/rocker/lever pivots) | running clearance | hand-cranked, low-speed → generous slip fit, beginner-safe |
| gear ↔ gear mesh (cone↔cylinder, platen rack) | backlash | zero-backlash-in-CAD gears bind in brass |
| cam ↔ follower / connecting rod | contact clearance | follower rides without jamming at dwell |
| amplitude bar ↔ rocker | sliding side clearance | bar slides without binding through full sweep |
| fastener ↔ clearance hole | close / normal | per fastener class |

None of these is an accuracy feature (see the one-sided-load argument above); their limits are
set by binding, wear and assembly, and the size limits on the mating features must be narrow
enough to deliver the band ([assessment §4](./tolerance-gdt-assessment.md)).

## Verification gates

`verify.py` runs a **tolerance audit** (and writes `cad/out/reports/tolerance_audit.csv`) that
fails the build if any part lacks material / tolerance class / process, or any moving interface
lacks a fit class. This is the Gate-E pass. `check:budget` fails the build if the sensitivity
model disagrees with the exact kinematics, a toleranced nominal no longer resolves to the spec
constant the CAD builds from, a drawing limit disagrees with the budget, or the Monte Carlo
leaves its targets.

## Current analytic clearance assertions (kept, being migrated)

The build scripts already assert clearance margins analytically (and raise on violation) — these
are the concrete realizations of the classes above, being lifted into `tolerances.yaml`:

- spring-eye threading margins into the lever hole / under the tab;
- oblique cone↔drum mesh penetration guard (edge slack);
- rack–pinion backlash;
- bushing clearance under the amplitude-bar foot.

## Open items the budget exposed

- **Spring rate and preload are not specified anywhere**; the 2.13 N/mm and 76 N per spring
  used for the knife-load estimate are derived from wire geometry (low confidence), and that
  preload does not balance against the modelled counter spring (0.51 N/mm would need ~1.5 m of
  extension). Specify both as requirements; the hysteresis term scales with the edge load.
- **Magnification bookkeeping**: the lever is stated "up to 4×", the wheel 5× by geometry,
  and the model uses a single `magnify_factor` 4.0; the pen half-stroke (15 mm) that sets the
  readout term depends on the reconciliation.
- `amplitude.max_travel_mm` 88 vs. the ledger's ±146 mm foot travel: the budget uses 88; a
  larger full scale improves every readout term proportionally.
- The eccentricity drawing limit (±0.025) vs. its accuracy allowable (±0.046): keep or relax
  is a stated decision, pinned either way by `check:budget`.

## Scope of manufacturing outputs

Reassessed in [`tolerance-gdt-assessment.md`](./tolerance-gdt-assessment.md) §11 — nothing here is
left "deferred":

- **GD&T (full, ASME Y14.5-2018), surface-finish specs, critical-feature callouts — IN SCOPE.**
  Held in config, stamped into the model as PMI, imported onto the drawings, audited. The full
  vocabulary is available — form, orientation, location (true position + MMC/LMC bonus), profile,
  and runout, over explicit datum reference frames — applied **functionally**: a feature-control
  frame appears only where the error model rewards it (the knife edge, the cams, channel
  consistency), and a general tolerance block (an ASME decimal-place title-block table; ISO 2768 if
  drawing to ISO) governs everything unspecified. This
  **retires the earlier "lite" cap** that limited geometry to dial-indicator runout on the theory the
  audience couldn't parse frames — the supplement now ships a GD&T primer instead (see assessment
  §1/§5).
- **2D shop drawings — IN SCOPE (planned).** A hobby machinist builds from a dimensioned, toleranced
  print, so generated PDF drawings (Tier-1 precision-critical parts first) are the vehicle that
  carries the tolerances to the bench. Same `SaveAs3` path the STEP/STL export already uses; a new
  `drawing:<stem>` doit task that takes the COM seat lock.
- **CAM (STEP→CAM→G-code) — IN SCOPE, deferred until the nominal model is frozen and validated.**
  The build is manual-primary for fidelity, with the PM-30MV **CNC** cutting the repetitive high-count
  parts (20 cams, 19+19 spacer bushings, cone/cylinder gear train). The primary feed is the **3D solid
  via STEP** (emitted by `SaveAs3` in `export_models.py`/`cut_release.py`) into **Fusion 360**
  (Makers SKU) → G-code; CAM cuts nominal, so the toleranced print carries fits/finish. **Caveat:** the
  neutral export writes one STEP per SLDPRT (active config), so a multi-config part like the 20-config
  `cone-gear` needs a **per-config STEP export path added** before all 20 can be fed to CAM (see the
  assessment §11). Authored after the §4 Findings close. Manual mill + lathe still make every one-off part.
- **DXF — narrow role, NOT the primary CAM feed.** 2D only; used only for genuinely flat parts, 2.5D
  contour/indexed profiles (cam/gear-tooth flanks), and inspection-reference overlays — subordinate to
  the STEP→CAM path (which handles the real 3D solids). Carries geometry, not tolerances.
