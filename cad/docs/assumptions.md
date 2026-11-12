# Reverse-engineering assumptions

This is a reconstruction of a historical device from incomplete evidence. Where the record is
incomplete, the assumption is encoded **explicitly in the config with a source note** — *how we
reasoned from incomplete evidence is itself book content.*

## Dimension provenance & confidence

Every dimension carries a source method and confidence, tracked in
[`cad/DIMENSIONS.md`](../cad/DIMENSIONS.md) (generated from the `cad/config/*.yaml` `source` /
`confidence` fields). Authority order, highest first:

1. **annotated** — callouts printed on the book's photographs (authoritative);
2. **stated** — dimensions in the chapter text (authoritative);
3. **scaled** — proportionally measured off photos (medium confidence);
4. **legacy** — values from old KCL/C# code (tiebreaker only);
5. **derived** — computed from a formula (flagged with the formula).

On conflict, the book wins over any derivative file.

## Key reasoned assumptions

- **Cylinder gear tooth count = 120**, derived: the 1/4 input reduction and the per-channel
  ratio `[120 − 6j : 120]` force `T = 120` for a unit-fundamental channel.
- **Channel station pitch .300 in (7.62 mm)**, owner ruling 2026-11-11 (#1038): the original
  measures 7.5 to 7.6 mm (eleven photo/callout reads, 7.555 ±0.048 mm), and .300 in is the
  smallest round value that keeps the amplitude bars' least foot gap above its floor. The former
  7.0565 mm was a doubled cosine error, not a measurement (`dimensions.yaml` Appendix C #3).
- **Cone incline 12.0247°**, derived from exact tracking `sin i = 3m / 7.62`: each 6-tooth
  step adds 3m of pitch radius per 7.62 mm channel pitch, with the 48DP module
  `m = 25.4 / 48` mm (13.0011° at the former 7.0565 mm pitch).
- **Gear standard: 48DP / 20° train, normal 24DP / 20° crank pair, 48DP and 32DP / 20° paper
  drive.** A deliberate anachronism. The original's pitch and pressure angle are not recorded;
  the earlier DP 49.82 was back-calculated from a scaled photo and the 14.5° was assumed. See
  [`gear-standard.md`](./gear-standard.md).
- **Amplitude-bar positions (aⱼ)** are the channel coefficients; nominal demo settings are
  config presets, not historical fact.
- Several dimensions were **scaled from photos** at low/medium confidence and re-measured during
  the photo-tuning pass; see `DIMENSIONS.md` for the per-dimension trail.

## Chirality

The CAD model was found to be a mirror image of the real machine and corrected by mirroring
every placement about the machine YZ plane. Anchors: crank/cone/drive at −X, front = the −Z
paper side. A silhouette is chirality-blind, so true orientation is always derived from photo
**content/position**, never by flipping a reference.
