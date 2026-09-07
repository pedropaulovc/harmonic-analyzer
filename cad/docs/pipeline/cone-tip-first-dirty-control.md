# Cone-tip source first-dirty control

Historical pre-run design below. The subsequent native control localized the
source write; its exact receipt and the separately proposed migration are in
[cone-tip source-owned reference text](cone-tip-source-reference.md).

This diagnostic-only extension is based on `fb958fda`. It does not change the
source part, drawing recipe, reference notation, save policy or acceptance gates.
The new tip target has not run natively yet.

The preceding owned full-recipe receipt
`cad/out/reports/datum-policy-sd8umcdz/pilot.json` has SHA-256
`100067e57314e7eeee8d9d848190d246868bebf2035cc1613f76e91d2078fce0`.
At `fb958fdad1c55653ab6747c28eeaa31ca547850a`, the tip recipe took
24.0260824 s and the complete diagnostic 183.5877625 s. It failed at the
after-recipe immutable-copy hash gate. This establishes a saved copy change,
not which prior operation first dirtied the source.

The current rebuilt original and execution token were read-only verified as
`f3578ac2b2ab95e478bc7bd72c316ebab057c125d5244af6fa2c3e12f4d48468`.
Standard `Get-FileHash` was blocked by native file sharing; an explicit
read-only `FileStream` with ReadWrite/Delete sharing read the same exact hash.
No document was opened or mutated for that check.

## One existing monitor, two explicit targets

`diagnostics/probe_source_dirty_recipe.py --target cone_tip_adjuster` selects
the exact trusted recipe, its source spec and a unique `cone-tip-adjuster-*`
copy basename through a two-entry enum registry. Omitting `--target` retains
the original `arbor_pedestal` control and `arbor-*` copies. `--candidate` resolves
to an exact commit before the parent forwards it and the target to the locked
worker; only recipe bytes come from that commit. Helper/spec/adapter inputs remain
the current frozen checkout, as before. This uses the existing **normal** drawing
factory, not a new prepared-factory comparison.

The tip source snapshot must observe `BodyDiaDim@BodyProfile`, `BodyLenDim@Body`,
`CupDiaDim@CupProfile`, `CupDepth@Cup` and `SlotWDim@SlotProfile`. It also records
every other supported observed feature/display dimension, full names, native
values, tolerance/BASIC fields, precision, marking and GetText(1..8) fields.
Missing required dimensions, ambiguous identity and malformed/unsupported reads
still fail. Hole-callout text remains explicitly excluded by the existing reader;
the official GetText page does not support that form or selector 0.

The monitor brackets initial getters and each existing recipe operation group.
At the first dirty source flag it captures the same full bank and native identity
comparison, then raises its existing BaseException-derived stop through `_attempt`.
If no earlier group dirties the source, it stops before the real finalizer.
No drawing save, PDF/PNG export, source save, reset, retry or second recipe follows.
The exact source and copied bytes, actual imported adapter/helper fingerprints,
owned-copy lifecycle and unrelated document preservation remain guarded.

The tip recipe's `set_reference_dimensions` currently writes prefix/suffix through
SetText. It is a candidate group, **not an established source writer**. The comment
claiming ShowParenthesis cannot render on leadered diameters is not proven by this
extension. Bundled GetText/SetText documentation and the example were read; the
per-method page excludes GetText(0), despite its use in that older example. No API
reader or presentation alternative is introduced here. A later ShowParenthesis
plus documented redraw positive control remains separate and untested.

## Invocation after review and an explicit native seat grant

```powershell
$env:HARMONIC_SW_AUTOSTART='0'
$env:HARMONIC_REMOTE_CACHE_MODE='off'
$env:HARMONIC_DIAGNOSTIC_SW_PID='<approved-current-PID>'
uv run python cad/scripts/diagnostics/probe_source_dirty_recipe.py --target cone_tip_adjuster --candidate HEAD --source C:/src/harmonic-analyzer/cad/out/sldprt/cone-tip-adjuster.SLDPRT --expected-sha256 f3578ac2b2ab95e478bc7bd72c316ebab057c125d5244af6fa2c3e12f4d48468
```

Run from the reviewed frozen checkout. The process must already be licensed and
match the explicit PID environment; the existing runner only attaches. The report
names exact selection, spec, required dimensions and candidate revision. A group
boundary is not inner-setter attribution, BREP equivalence or native API failure.
The original arbor historical native receipt remains unchanged in the probe
docstring and [drawing-defaults benchmark](drawing-defaults-benchmark.md).

There were no deliberate assertion conflicts: arbor stays the default. Only the
synthetic required-dimension injection moved from the old arbor-only global to
that same spec in the explicit registry. Existing clean/dirty, getter-induced
dirty, error/identity, unsupported inventory and no-save checks are retained;
target-specific fakes additionally exercise prefix/suffix changes and CLI/worker
forwarding. Native tip localization remains pending.

Five new target/CLI cases failed before implementation while all 21 prior cases
passed. The completed focused/adjacent run passed 400 tests in 5.76 s, including
the shared source-bank, owned lifecycle, recipe-loader and factory suites
(`pytest-telemetry/run-5divicex`). Ruff F and `git diff --check` passed. One earlier
adjacent command named a nonexistent test file and ran zero tests; it was corrected,
not counted as verification. No COM was executed.
