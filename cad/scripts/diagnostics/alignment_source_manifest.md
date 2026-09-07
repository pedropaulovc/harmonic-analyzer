# Alignment production-source enrollment

On 2026-09-07, the diagnostic pin for `alignment_pinion` was deliberately changed
from `858dc759943c2f739b3081fd02f313c26ead01eb837e08f9c79d59caac388920`
to `9e09613dcdfeadcd76cfa4e28f2c9b6035ea1736bdb1bbcca1a7ecc3239c0632`.
All other 13 target pins, source naming/dimension maps, entity roles, exact hash
checks and cold witnesses remain unchanged. There is no automatic pinning,
accepted-old-hash alternative, command-line bypass, or source rewrite.

The old identity belongs to the original source used by the historical
source-authoring controls. Their receipts and provenance remain unchanged in
[the source-save evidence](../../docs/pipeline/alignment-source-save-boundaries.md).
Run historical controls with their matching historical tooling and inputs; this
new pin does not relabel their authored copies as actual builder outputs.

## Verified provenance

The actual uncached production part and drawing passed at `fdf1e84d`, adapter
`25bc99b1`, native PID 31860. Before this pin migration, a read-only check again
confirmed that `C:/src/harmonic-analyzer/cad/out/sldprt/alignment-pinion.SLDPRT`
and `.alignment-pinion.execution` both carry the new SHA-256 above.

Retained trace `0x03198c7eb54a5ef6a8061d04a5213a1c` records the successful real
part task from 10:08:04.674988 to 10:08:59.646541 UTC (54.971553 s), including
`dim.model_callouts` on `ArborBoreProfile` (1.698686 s). The builder authors after
dimension naming/marking and uses its existing final save. This is not the
diagnostic `SourceCalloutControl` authoring path.

Trace `0x05e139a123febf51647d5102365986d9` records the successful production
drawing task (64.975201 s), its actual read-only callout verification
(1.108503 s), native drawing save and PDF export. Both production renders were
visually inspected, as recorded in the linked evidence. The saved drawing hash
is `456c46b901ec86b919ca5e0cf7dca72b247d4d4f2af9ac87bc8d415986623355`.
These traces establish the named build provenance; token equality alone would
not establish it. A cold replay of this exact source is still pending.

## Existing full-recipe cold replay

After integrating this pin and freezing the reviewed root head, run from the
root checkout only under an explicitly granted native seat. Confirm the intended
live PID before using the value below. The parent entrypoint takes the existing
machine-global seat; do not invoke `--worker` directly.

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_DIAGNOSTIC_SW_PID = '31860'
uv run --no-sync python cad/scripts/diagnostics/probe_datum_policy_recipes.py `
  --candidate HEAD `
  --source-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --guard-root C:/src/harmonic-analyzer/cad/out/sldprt `
  --target alignment_pinion --factory prepared `
  --source-observation alignment_save --drawing-save legacy
```

There is **no** `--source-callout-authoring` or `--callout-storage` option. The
existing verifier ABI is selected; source banks observe it without replacing it
with a setter. `legacy` leaves the ordinary ownership-guarded native/PDF writer
intact. The factory uses the real prepared-template accessor and explicit factory
contract. Original alignment, rocker and lever inputs remain protected; only the
selected alignment recipe opens a unique exact source copy. The source copy must
retain the new starting bytes throughout this replay, including save/export and
close. The existing source and drawing cold reopen checks, exact native identity,
values/tolerances/BASIC, imported annotation content/layout and failure retention
remain in force. No successful result is claimed by this offline migration.

New tests pin the complete 14-target hash map, reject old/arbitrary alignment
identities, and exercise both parent/worker CLI forwarding without source
authoring. They initially failed on the retired alignment pin
(`pytest-telemetry/run-ziev77dg`). The seven-file adjacent gate passed 263 tests
in 16.74 s (`pytest-telemetry/run-hrllo_ol`); Ruff and diff checks passed. A
read-only invocation of the real `require_sources` also passed against all three
protected root files (alignment, rocker and lever), without opening them in SW.
The new test follows the enrolled `test_*_drawing.py` naming convention.

Production helper closures and build-cache inputs do not change: only diagnostic
enrollment, tests and this provenance do. A read-only `module_deps_of` audit of
all 213 `build_*.py`/`draw_*.py` files found no consumer of the changed diagnostic
manifest; its only runtime importer is the diagnostic pilot.
