# Entity resolver batching experiment

This child experiment follows
`cad/docs/pipeline/second-vm-entity-resolver-performance.md` at
`d67152990960eecb0703a3f9d2bc366d44ac4e8d`.

## Inputs and ownership

- Accepted parent: #682, `19431a0088519bd8755b941a3da73a699c0ed7e1`.
- Adapter: `25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`.
- Branch: `perf/entity-resolver-batching`.
- Isolated checkout: `C:/src/ha-entity-resolver-batching`, with its own
  `uv sync --frozen` environment and no borrowed build state or artifacts.
- Observed main: `c6ab57db`. It includes assembly-health work after the accepted
  parent. This experiment deliberately retains the handoff's pinned parent.

VM1 owns parent integration and merging. This branch does not alter #676-678,
the accepted crank recipe, manufacturing data, annotation placement, the adapter,
or shared build/template helpers.

## Experiment contract

Measure repeated native reads before changing production code. Compare fresh
resolver banks on one unchanged, genuinely built local source, using at least
three alternating ABBA blocks. Keep instrumented resolver timings separate from
uninstrumented production drawing timings. Warm each prepared-template entry
before production measurements.

The acceptance checks remain those of #682: all 14 explicit attachment roles,
13 raw dimensions, manufacturing metadata, native identity, both cold reopens,
move/scale and Save3 association, template guards, source/token hashes, and
production-scale full-sheet/crop inspection. The moved sheet is association
evidence only. No optimization is accepted without repeatable native benefit.

## Evidence

Setup is complete. Native measurements, tests and review are pending; this note
does not claim a performance improvement or acceptance.
