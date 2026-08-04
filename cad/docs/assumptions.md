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
- **Cone incline 21.0976°**, derived from exact tracking `sin i = 2.54 / 7.0568` (not the naive
  `arcsin(2.54/7.5) = 19.8°`).
- **Amplitude-bar positions (aⱼ)** are the channel coefficients; nominal demo settings are
  config presets, not historical fact.
- Several dimensions were **scaled from photos** at low/medium confidence and re-measured during
  the photo-tuning pass; see `DIMENSIONS.md` for the per-dimension trail.

## Chirality

The CAD model was found to be a mirror image of the real machine and corrected by mirroring
every placement about the machine YZ plane. Anchors: crank/cone/drive at −X, front = the −Z
paper side. A silhouette is chirality-blind, so true orientation is always derived from photo
**content/position**, never by flipping a reference.
