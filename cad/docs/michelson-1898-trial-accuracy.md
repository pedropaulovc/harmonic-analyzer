# Michelson–Stratton 1898 trial accuracy and its use in machining tolerances

## Decision

Michelson and Stratton's published trials establish a **whole-device performance benchmark**, not a dimensional tolerance table:

- typical coefficient error: about **0.7% of the largest coefficient**;
- worst published individual coefficient error: **2.0% of the largest coefficient**;
- application-level envelope endorsed by the authors: **1–2% error** where high accuracy is not required.

Use those values to judge the assembled and calibrated analyzer and to constrain a sensitivity-based tolerance budget. **Do not apply 0.7% or 2% directly to every part dimension.** The paper gives no dimensions, fits, clearances, runout limits, surface finishes, spring-rate tolerances, or allocation of total error among mechanisms.

This document is the source of truth for the **historical trial benchmark and its permitted use**. The actual manufacturing limits remain authoritative in [`../config/tolerances.yaml`](../config/tolerances.yaml), [`../config/title_block.yaml`](../config/title_block.yaml), and the part/drawing specifications. A dimensional tolerance is justified only when a sensitivity calculation or assembled-machine test connects it to the performance envelope below.

## Source and method

Source: A. A. Michelson and S. W. Stratton, “A New Harmonic Analyzer,” *American Journal of Science*, fourth series, vol. V (January 1898), pp. 1–13.

Repository scan: [`28_Michelsons_1898_Paper.pdf`](../../references/albert-michelsons-harmonic-analyzer/28_Michelsons_1898_Paper.pdf), SHA-256 `640058610cd84bb467d08d84ec2d759a71d7c26bf41205324097d67009f5733a`.

The four landscape PDF pages were inspected at 300 dpi. The numerical comparisons below are transcribed from the printed `obs.`, `calc.`, and `Δ` tables on journal pp. 10–11. The grid-paper figures were inspected independently to determine what can and cannot be recovered from the plotted traces. Derived statistics use the printed `Δ = observed − calculated` values, normalized to the greatest tabulated term (`100`).

The printed numbers are stronger evidence than digitizing the line art: figure lines are roughly one or more fine-grid cells thick, the reproduction has scan distortion, and several curves are intentionally displaced rather than overlaid.

Three primary statements govern the interpretation:

- journal p. 11, Figure 11 trial: “The average error is only 0·65 of one per cent. of the
  value of the greatest term”;
- journal p. 11, Figure 12 trial: “Here the average error is only 0·7 per cent. of the
  value of the greatest term”;
- journal p. 13: the machine saves substantial labor “in cases where an error of one or
  two per cent is unimportant.”

## What the trials measured

The 80-element machine sampled ordinates of an input curve, formed approximate sine/cosine Fourier coefficients, and could then recombine those coefficients to reproduce the input. Its measured discrepancy therefore combines several effects:

1. finite-element quadrature/sampling;
2. curve setup and ordinate-reading error;
3. spring and lever nonlinearity or mismatch;
4. eccentric/cam amplitude and phase error;
5. friction, backlash, lost motion, pen width, and graph reading.

The paper does not separate these contributions. Its numbers are end-to-end errors, not pure machining errors.

The paper also mentions encouraging results from an earlier **20-element** machine (journal p. 2) but publishes no numerical trial data for it. The numerical results below belong to the **80-element** machine and must not be presented as a demonstrated accuracy of this project's 20-element reconstruction.

## Trial 1 — rectangular input, Figure 11

For a function constant from `0` to `a` and zero elsewhere, the exact cosine coefficient is

$$
\int_0^a \cos(kx)\,dx = \frac{\sin(ka)}{k}.
$$

For `a = 4.0`, journal p. 10 prints observed and calculated coefficients and their differences. The published `Δ` sequence for `n = 0…20` is:

```text
 0.0, +1.0,  0.0, +1.0,  0.0, -0.5, -1.5,
 0.0,  0.0, -1.0, -2.0,  0.0,  0.0, -1.0,
-2.0, +0.5, +0.5, -0.5, -1.0, +0.5,  0.0
```

The authors state an average error of **0.65% of the greatest term** on journal p. 11. That value is reproduced exactly by the first twenty listed coefficients (`n = 0…19`):

$$
\operatorname{MAE}_{11} = \frac{\sum_{n=0}^{19}|\Delta_n|}{20}
= \frac{13.0}{20} = 0.65\%\ \text{full scale}.
$$

Derived from those same twenty printed differences:

| Metric | Result, relative to greatest term |
|---|---:|
| Mean absolute error | **0.65% FS** |
| Root-mean-square error | **0.91% FS** |
| Maximum absolute error | **2.0% FS** |
| Mean signed error | **−0.30% FS** |
| Coefficients within ±1% FS | **17/20** |

The table includes a final `n = 20` row with zero difference. Including it would give `0.619%`, so it is not part of the authors' stated “first twenty coefficients” average.

![Figure 11: measured coefficient curve on grid paper and calculated/observed 25-term reconstructions A and B](../../references/albert-michelsons-harmonic-analyzer/ch28_images/page003_img02.jpeg)

**Image reading.** The upper grid-paper plot follows the expected damped oscillatory `sin(ka)/k` form, including repeated zero crossings and alternating lobes. The lower curves are explicitly labelled `A` (calculated, 25 terms) and `B` (observed), but they are vertically offset for legibility. Their pixel separation is therefore not an error ordinate. The image supports the table's qualitative conclusion—correct phase, sign, and rectangular reconstruction—but cannot improve on the printed coefficient errors.

## Trial 2 — Gaussian input, Figure 12

The second input is

$$
\varphi(x)=e^{-a^2x^2}, \qquad a=1,
$$

with coefficients proportional to

$$
\int_0^\infty e^{-a^2x^2}\cos(kx)\,dx.
$$

Journal p. 11 prints thirteen rows (`n = 0…12`). Its `Δ` sequence is:

```text
0.0, -1.0, -1.0, 0.0, -1.0, 0.0, 0.0,
+1.0, -0.8, +0.5, +1.6, +1.4, +1.1
```

The authors report an average error of **0.7% of the greatest term**. The unrounded value from all thirteen printed rows is:

$$
\operatorname{MAE}_{12} = \frac{9.4}{13} = 0.723\%\ \text{full scale},
$$

which rounds to their `0.7%` statement.

| Metric | Result, relative to greatest term |
|---|---:|
| Mean absolute error | **0.72% FS** |
| Root-mean-square error | **0.90% FS** |
| Maximum absolute error | **1.6% FS** |
| Mean signed error | **+0.14% FS** |
| Coefficients within ±1% FS | **10/13** |

![Figure 12: Gaussian coefficient trial, grid trace, and printed observed/calculated table](../../references/albert-michelsons-harmonic-analyzer/ch28_images/page004_img01.jpeg)

**Image reading.** The plotted transform has the expected even, smooth, rapidly decaying shape. The observed samples remain near the analytic curve as the coefficient approaches zero. Near-zero relative errors would be misleading, so the paper correctly reports absolute discrepancy against the largest term rather than percent error per coefficient.

## Combined numerical estimate

Combining the 20 coefficients used in the Figure 11 average with all 13 Figure 12 coefficients gives 33 published differences:

| Metric | Combined estimate, relative to greatest term |
|---|---:|
| Mean absolute error | **0.679% FS** |
| Root-mean-square error | **0.907% FS** |
| Maximum absolute error | **2.0% FS** |
| Mean signed error | **−0.127% FS** |
| Coefficients within ±1% FS | **27/33 (82%)** |

This pooled value is a descriptive summary, not a confidence interval: the two functions were chosen demonstrations, not random samples from a defined population. The printed precision also limits secondary statistics. Figure 11 readings are predominantly quantized to `0.5` unit, implying about `±0.25% FS` uncertainty on an individual value before scan/transcription uncertainty; aggregate values should not be quoted beyond about `0.1% FS`.

## Full synthesis/reconstruction — Figure 13

Figure 13 completes the analysis/recombination cycle for an arbitrary outline:

- `A`: original curve `φ(x)`;
- `B`, `C`: measured sine and cosine coefficient functions;
- `D`, `E`: 20-term sine and cosine reconstructions;
- `F = D + E`: reconstructed curve.

![Figure 13: original outline, coefficient traces, component reconstructions, and 20-term reconstructed outline](../../references/albert-michelsons-harmonic-analyzer/ch28_images/page004_img03.jpeg)

The authors say `F` agrees sufficiently well with `A` for the original to be “easily recognizable.” The image confirms topology and major feature placement, including the face profile noted in the modern introduction. It does **not** support a defensible pointwise error number:

- `A` and `F` are drawn in different parts of the sheet, not on a shared baseline;
- no common ordinate scale is stated;
- the reconstruction is truncated to twenty sine and twenty cosine terms;
- line thickness, grid distortion, and the original hand trace are comparable to small visible deviations.

Figure 13 is therefore a qualitative end-to-end validation only. Assigning an RMS or maximum error from its pixel geometry would fabricate precision absent from the source.

## Normative whole-device accuracy benchmark

For assembled-machine verification, use full-scale normalization exactly as the paper does:

$$
e_n = \frac{O_n-C_n}{\max_j |C_j|}\times100\%,
$$

where `O` is observed machine output and `C` is the expected coefficient from numerical integration using the same sampled input.

The historical benchmark is:

| Requirement | Historical basis | Use |
|---|---|---|
| Mean absolute coefficient error | **about 0.7% FS** | Target for a calibrated, well-behaved benchmark run |
| RMS coefficient error | **about 0.9% FS** | Diagnostic summary derived from the two printed tables |
| Maximum coefficient error | **2.0% FS** | Published single-coefficient envelope |
| Application-level error | **1–2%** | Authors' stated acceptable regime on journal p. 13 |

For this project, **≤1.0% FS MAE and ≤2.0% FS maximum error** is the evidence-backed whole-device acceptance envelope to attempt on representable benchmark inputs. Record the 0.7% historical MAE as the comparison target, not as a guaranteed pass criterion for a 20-element machine. Report truncation/sampling error separately from mechanical residual whenever possible:

1. compute the exact continuous coefficient;
2. compute the ideal 20-sample/20-element coefficient using the machine's actual sampling rule;
3. measure the machine coefficient;
4. report continuous-to-discrete approximation error and discrete-to-machine mechanical error separately.

That split avoids tightening hardware to compensate for unavoidable 20-element truncation.

## Contract for deriving machining tolerances

The paper constrains tolerance work in four ways:

1. **The acceptance quantity is output error, normalized to full scale.** It is not percent dimensional error.
2. **Channel consistency is load-bearing.** Per-element amplitude, phase, spring rate, friction, and lever ratio errors enter the sum; common adjustable offsets can be calibrated or tared.
3. **Spring/lever proportionality is explicit.** Journal p. 2 derives
   $$
   y=\frac{\sum x}{n\left(l/L+a/b\right)}
   $$
   and says `l/L` and `a/b` should be as small as practical. Dimensions affecting these ratios and their channel-to-channel repeatability require sensitivity analysis.
4. **The published error is total error.** No individual machining source may consume more than the whole-device 1–2% envelope, but the paper supplies no defensible subdivision of that budget.

Accordingly, a part or assembly tolerance may claim support from this benchmark only if its specification records:

- the affected transfer quantity: amplitude, phase, lever ratio, spring force, friction/deadband, backlash, or readout;
- the sensitivity from dimensional deviation to coefficient error;
- whether the deviation is common-mode, adjustable, or channel-specific;
- worst-case and root-sum-square contribution in `% FS`;
- the assembled benchmark or calibration step that detects it.

Without that chain, the dimensional value may still be justified by fit, manufacturability, wear, or drawing practice, but **not by Michelson's reported accuracy**.

## What this evidence does not authorize

Do not infer any of the following from the 1898 plots:

- `±0.7%` on every linear or angular dimension;
- a universal `±0.1 mm`, `±0.025 mm`, runout, backlash, or surface-finish requirement;
- equal tolerance allocation to all 20 channels or all parts;
- demonstrated `0.7%` accuracy for the untested 20-element reconstruction;
- a claim that machining error alone was `0.7%`;
- a pointwise Figure 13 reconstruction error.

The correct relationship is:

```text
part tolerances + assembly adjustment + calibration
                    ↓ sensitivity/error model
predicted mechanical contribution in % full scale
                    ↓ assembled benchmark
≤ 1% MAE target and ≤ 2% maximum historical envelope
```

This preserves the paper as ground truth without turning a system-level performance measurement into dimensionally invalid part tolerances.
