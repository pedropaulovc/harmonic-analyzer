# Michelson–Stratton 1898 trial accuracy and its use in machining tolerances

## Decision

Michelson and Stratton's published trials establish a **whole-device performance benchmark**, not a dimensional tolerance table:

- typical coefficient error: about **0.7% of the largest coefficient**;
- largest tabulated individual coefficient difference: **2.0% of the largest coefficient**;
- authors' application context: **1–2% error** where high accuracy is not required.

Use those values to judge the assembled and calibrated analyzer and to constrain a sensitivity-based tolerance budget. **Do not apply 0.7% or 2% directly to every part dimension.** The paper gives no dimensions, fits, clearances, runout limits, surface finishes, spring-rate tolerances, or allocation of total error among mechanisms.

This document is the source of truth for the **historical trial benchmark and its permitted use**. The actual manufacturing limits remain authoritative in [`../config/tolerances.yaml`](../config/tolerances.yaml), [`../config/title_block.yaml`](../config/title_block.yaml), and the part/drawing specifications. A dimensional tolerance is justified only when a sensitivity calculation or assembled-machine test connects it to the performance envelope below.

## Source and method

Source: A. A. Michelson and S. W. Stratton, “A New Harmonic Analyzer,” *American Journal of Science*, fourth series, vol. V (January 1898), pp. 1–13.

Repository scan: [`28_Michelsons_1898_Paper.pdf`](../../references/albert-michelsons-harmonic-analyzer/28_Michelsons_1898_Paper.pdf), SHA-256 `640058610cd84bb467d08d84ec2d759a71d7c26bf41205324097d67009f5733a`.

The four landscape PDF pages were rendered at 300 dpi for inspection, but their
embedded source rasters are about 100 dpi; upsampling adds no source detail. The
numerical comparisons below are transcribed from the printed `obs.`, `calc.`, and
`Δ` tables on journal pp. 10–11. Derived absolute statistics use the printed `Δ`
column, normalized to the greatest tabulated term (`100`).

Two printed signs disagree with subtraction of the adjacent values: Figure 11
`n = 19` prints `Δ = 0.5` beside `obs. = −3.5` and `calc. = −3.0`, while Figure 12
`n = 8` prints `Δ = −0.8` beside `obs. = 8.8` and `calc. = 8.0`. These apparent
typesetting errors do not affect any absolute-error statistic. Signed means below
treat the printed `Δ` signs literally and are therefore transcription-sensitive.

The grid-paper figures were inspected independently. In the extracted JPEGs, a minor
grid square is about four pixels wide and traces are about one to three pixels thick.
Following a trace therefore carries about `±1–2 px` (`±0.25–0.5` minor square)
uncertainty before scan skew and annotations. None of Figures 11–13 gives a numeric
vertical scale that converts this separation into coefficient units, and some curves are
intentionally displaced instead of overlaid. The printed tables are the only defensible
numeric comparison.

Three primary statements govern the interpretation:

- journal p. 11, Figure 11 trial: “The average error is only 0·65 of one per cent. of the
  value of the greatest term”;
- journal p. 11, Figure 12 trial: “Here the average error is only 0·7 per cent of the
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

For a function constant from `0` to `a` and zero elsewhere, the exact integral underlying its cosine coefficient is

$$
\int_0^a \cos(kx)\,dx =
\begin{cases}
a, & k = 0,\\
\dfrac{\sin(ka)}{k}, & k \ne 0.
\end{cases}
$$

For `a = 4.0`, journal p. 10 prints observed and calculated coefficients and their differences. The published `Δ` sequence for `n = 0…20` is:

```text
 0.0, +1.0,  0.0, +1.0,  0.0, -0.5, -1.5,
 0.0,  0.0, -1.0, -2.0,  0.0,  0.0, -1.0,
-2.0, +0.5, +0.5, -0.5, -1.0, +0.5,  0.0
```

The authors state an average error of **0.65% of the greatest term** on journal p. 11.
The table prints 21 rows (`n = 0…20`) but describes the result as the first twenty
coefficients. Both end rows have zero difference, so dropping either `n = 0` or `n = 20`
produces the same statistics. Using the harmonic-coefficient convention `n = 1…20`:

$$
\operatorname{MAE}_{11} = \frac{\sum_{n=1}^{20}|\Delta_n|}{20}
= \frac{13.0}{20} = 0.65\%\ \text{full scale}.
$$

Derived from those same twenty printed differences:

| Metric | Result, relative to greatest term |
|---|---:|
| Mean absolute error | **0.65% FS** |
| Root-mean-square error | **0.91% FS** |
| Maximum absolute error | **2.0% FS** |
| Mean signed `Δ` (printed signs) | **−0.30% FS** |
| Coefficients within ±1% FS | **17/20** |

Averaging all 21 printed rows gives `0.619%`. The source does not identify which zero
end row it omitted from the stated twenty-coefficient average.

![Figure 11 (journal p. 9): measured coefficient curve on grid paper, with A the 25-term calculated summation and B the observed trace](../../references/albert-michelsons-harmonic-analyzer/ch28_images/page003_img02.jpeg)

**Image reading.** The upper grid-paper plot follows the expected damped oscillatory `sin(ka)/k` form, including repeated zero crossings and alternating lobes. The lower curves are explicitly labelled `A` (calculated, 25 terms) and `B` (observed), but they are vertically offset for legibility. Their pixel separation is therefore not an error ordinate. The image supports the table's qualitative conclusion—correct phase, sign, and rectangular reconstruction—but cannot improve on the printed coefficient errors.

## Trial 2 — Gaussian input, Figure 12

The second input is

$$
\varphi(x)=e^{-a^2x^2}, \qquad a=0.1,
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

The authors report an average error of **0.7% of the greatest term**. The paper
calls these the “first twelve terms” while printing 13 rows (`n = 0…12`).
Averaging all 13 gives `0.723%`; averaging `n = 0…11` gives `0.692%`. Both round
to the printed `0.7%`. The Figure 11-style harmonic-only interpretation
`n = 1…12` gives `0.783%`, which rounds to `0.8%` and is therefore excluded.
The intended denominator cannot be distinguished between the first two readings.
The primary table below uses all 13 printed rows:

$$
\operatorname{MAE}_{12} = \frac{9.4}{13} = 0.723\%\ \text{full scale}.
$$

| Metric | Result, relative to greatest term |
|---|---:|
| Mean absolute error | **0.72% FS** |
| Root-mean-square error | **0.90% FS** |
| Maximum absolute error | **1.6% FS** |
| Mean signed `Δ` (printed signs) | **+0.14% FS** |
| Coefficients within ±1% FS | **10/13** |

![Figure 12 (journal p. 11): Gaussian coefficient trial, grid trace, and printed observed/calculated table](../../references/albert-michelsons-harmonic-analyzer/ch28_images/page004_img04.jpeg)

**Image reading.** Figure 12 contains one machine-drawn transform trace. It has no
plotted observed points and no calculated overlay, so the image supports only the smooth,
even, rapidly decaying shape. The observed-versus-calculated comparison exists in the
printed table. Because the coefficients approach zero, the paper reports absolute
discrepancy against the largest term rather than percent error per coefficient.

## Combined numerical estimate

Combining the 20 coefficients used in the Figure 11 average with all 13 Figure 12 coefficients gives 33 published differences:

| Metric | Combined estimate, relative to greatest term |
|---|---:|
| Mean absolute error | **0.679% FS** |
| Root-mean-square error | **0.907% FS** |
| Maximum absolute error | **2.0% FS** |
| Mean signed `Δ` (printed signs) | **−0.127% FS** |
| Coefficients within ±1% FS | **27/33 (82%)** |

Using the alternative Figure 12 interpretation (`n = 0…11`) gives 32 pooled values:
`0.666% FS` MAE, `0.900% FS` RMS, `−0.166% FS` mean of the printed signed `Δ`,
and `27/32` within `±1% FS`.

This pooled value is a descriptive summary, not a confidence interval: the two functions
were chosen demonstrations, not random samples from a defined population. The printed
precision also limits secondary statistics. Figure 11 readings are predominantly quantized
to `0.5` unit, so one tabulated observation carries up to about `±0.25% FS` rounding
uncertainty before scan/transcription uncertainty. The pooled table retains extra digits to
make the arithmetic reproducible; they do not represent measured precision.

## Full synthesis/reconstruction — Figure 13

Figure 13 (journal p. 12, described on p. 13) completes the analysis/recombination
cycle for an arbitrary outline:

- `A`: original curve `φ(x)`;
- `B`, `C`: measured sine and cosine coefficient functions;
- `D`, `E`: 20-term sine and cosine reconstructions;
- `F = D + E`: reconstructed curve.

These are twenty-term truncations of the 80-element machine's output. They are not
results from a 20-element machine and provide no accuracy claim for this project's
20 channels.

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
| Mean absolute coefficient error | **about 0.7% FS** | Historical comparison value for an 80-element, end-to-end trial |
| RMS coefficient error | **about 0.9% FS** | Diagnostic summary derived from the two printed tables |
| Largest individual difference | **2.0% FS** | Largest tabulated value, on journal p. 10; derived here, not stated by the authors as a limit |
| Application-level error | **1–2%** | Authors' use-case context on journal p. 13, not a tolerance limit |

The paper does not set a mechanical-residual limit. A claim of historical parity must
compare the assembled machine's end-to-end result with the historical `about 0.7% FS`
mean absolute error. The `2.0% FS` value is the largest observed table entry, not a
guaranteed envelope. The authors' `1–2%` remark describes applications where error is
unimportant; it is not a metrological acceptance rule.

Machining allocation requires separating approximation from machine error:

1. compute the exact continuous coefficient;
2. compute the ideal 20-sample/20-element coefficient using the machine's actual sampling rule;
3. measure the machine coefficient;
4. report continuous-to-discrete approximation error and discrete-to-machine mechanical error separately.

Only then can a mechanical-error budget be assigned. If ideal 20-element approximation
already exceeds the historical comparison for an input, tightening hardware cannot make
the 20-element machine match the 80-element result on that input.

## Contract for deriving machining tolerances

The paper constrains tolerance work in four ways:

1. **The acceptance quantity is output error, normalized to full scale.** It is not percent dimensional error.
2. **Channel consistency is load-bearing.** Per-element amplitude, phase, spring rate, friction, and lever ratio errors enter the sum; common adjustable offsets can be calibrated or tared.
3. **Spring/lever proportionality is explicit.** Journal p. 2 derives
   $$
   y=\frac{\sum x}{n\left(l/L+a/b\right)}
   $$
   and says `l/L` and `a/b` should be as small as practical. Dimensions affecting these ratios and their channel-to-channel repeatability require sensitivity analysis.
4. **The published error is total error.** Any machining-error allocation must fit within
   a chosen assembled-machine requirement, but the paper supplies no defensible subdivision.

Accordingly, a part or assembly tolerance may claim support from this benchmark only if its specification records:

- the affected transfer quantity: amplitude, phase, lever ratio, spring force, friction/deadband, backlash, or readout;
- the sensitivity from dimensional deviation to coefficient error;
- whether the deviation is common-mode, adjustable, or channel-specific;
- worst-case and root-sum-square contribution in `% FS`;
- the assembled benchmark or calibration step that detects it.

Without that chain, the dimensional value may still be justified by fit, manufacturability, wear, or drawing practice, but **not by Michelson's reported accuracy**.

The chain is executed for every critical feature in [`tolerance-policy.md`](./tolerance-policy.md) ("How a critical-feature tolerance is decided"), with the sensitivities, Monte Carlo allocation and readout procedure computed by [`cad/scripts/error_budget.py`](../scripts/error_budget.py) from [`cad/config/error_budget.yaml`](../config/error_budget.yaml).

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
historical comparison: about 0.7% MAE; largest tabulated difference: 2.0%
```
