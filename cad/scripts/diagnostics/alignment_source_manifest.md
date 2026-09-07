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

## Actual-source cold replay passed, 2026-09-07

The command above passed at frozen root `63d6e2e5`, adapter `25bc99b1`, PID
31860, with neither source authoring nor lower-text mutation enabled. Receipt
`cad/out/reports/datum-policy-ojv0f8vq/pilot.json` has SHA-256
`dbdfe5384efc7922082e9863d8ca99a68387ac188660e46591ba311bc248dfe5`.
Recipe time was 47.118125 s; the complete measured pilot was 210.836612 s,
including preparation, source observations and built/cold checks. These are
instrumented functional timings, not a production benchmark.

The copied source ended with the exact enrolled `9e09613d...c0632` identity;
original protection and final runtime guards passed. Built/reopened explicit
attachment banks compare exactly. The annotation comparison passed with no
rejected differences and no coordinate-roundoff exceptions. Existing source,
dimension/tolerance/BASIC, imported callout, and sheet witnesses also passed.

The main agent visually inspected the fresh printed PNG: `THRU - REAM` and
`PRESS FIT` are both readable beneath the bore size/tolerance, and the finish
leader remains at the bore. The PNG SHA-256 is
`ad636ce5eb72379b492407e287f32b6c22fe7e5fece66bf25754623bc113e860`,
identical to the earlier successful production PNG. Owned native drawing SHA is
`1999c20bb37ac3b86c557e5e37d0fdd29ec246855c77620f416aae1addb012f7`;
PDF SHA is `143399a0758ee879631076aed97946e0bffd222270a6eaa7507096cf3dab67ff`.
This closes the new-source alignment pilot, not the drawing fleet or full
stack merge gates. The root manifest/recipe/GTol/clearance baseline tests also
passed 148 tests in 2.11 s (`pytest-telemetry/run-7m9m4le9`).
