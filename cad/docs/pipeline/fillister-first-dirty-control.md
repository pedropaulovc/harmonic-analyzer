# Fillister source first-dirty control

Diagnostic-only addition on top of the reviewed tip probe `83c17ea1`.
No production recipe, source authoring, full-pilot enrollment, source pin, save
policy or geometry change. No native fillister result is claimed.

## Exact subject and observed input

The frozen fillister drawing calls `set_dimension_text` for imported
`ShankDia@ShankProfile`, with the exact whole-text replacement `#4-40 UNC-2A`.
The common helper calls void `IDisplayDimension.SetText(0, text)`, reads back
GetText(1), then invokes its existing drawing rebuild. Presence of these calls
does not establish that the source part becomes dirty or which inner call does it.

Read-only file access at 2026-09-07 12:40:57 UTC found
`C:/src/harmonic-analyzer/cad/out/sldprt/fillister-screw.SLDPRT`, 79,367 bytes,
SHA-256 `f3adf8b31928cb001a623d9970a42f1a911335e8b4060c866c8a17d6524d5d4a`.
The existing `.fillister-screw.execution` token matched exactly. The check used
a read-only FileStream with ReadWrite/Delete sharing; no native document was
opened, rebuilt, saved, reset or repinned. This is a point-in-time byte witness,
not a new builder receipt or proof that this part satisfies the current recipe's
earlier read-only callout verifier. If an earlier group fails, the probe stops;
it does not author missing source text to reach the whole-text operation.

## Same monitor, one more explicit target

`--target fillister_screw` selects its actual spec, trusted pinned recipe, and a
unique `fillister-screw-source-dirty-*` copy. All four required dimensions must be
observed: `HeadDia@HeadProfile`, `ShankDia@ShankProfile`, `HeadHt@Head`, and
`ShankLg@Shank`. Arbor remains the default; arbor and tip retain their exact
five-dimension assertions. There is no automatic next target or full-pilot entry.

The source bank retains every supported observed feature/display dimension,
native full name/value/tolerance/BASIC, marking, precision and GetText(1..8).
It now also reads raw `ShowDimensionValue` for each observed display. That
documented Boolean must be a Boolean, as must `IsHoleCallout`; no truthiness
coercion is accepted. GetText fields must be strings, including actual empty
strings. Unsupported hole-callout text remains explicitly excluded rather than
calling an unsupported getter; visibility is still recorded. A malformed read or
native exception aborts instead of being converted to empty text or a clean state.
This additive shared diagnostic-bank field is required for other callers too;
production modules do not import this diagnostic reader.

The official SetText page specifies that selector 0 puts the string in the
prefix, clears suffix/callout text and hides the numeric value. GetText expressly
does not support selector 0; the probe continues to read only 1..8. The
ShowDimensionValue/IsHoleCallout pages and display-properties VBA example were
read. No property setter or redraw is added by this diagnostic observation.

Initial getter reads remain bracketed by source dirty-flag checks. Each existing
recipe operation group is monitored, including `set_dimension_text`; the first
dirty flag triggers a full bank/native identity capture and BaseException stop,
even through `_attempt`. A malformed transition read is retained as a capture
failure. If no earlier group dirties the copy, the existing stop occurs before
the real finalizer. This is group attribution, not a SetText-versus-rebuild
experiment, a complete BREP proof, or persisted/printed drawing acceptance.

Original and copied source SHA, frozen helper/adapter/recipe bytes, exact owned
handles, and baseline documents retain the existing guards. No finalizer,
SLDDRW/PDF/PNG save, source save, reset or retry is introduced.

## Invocation after review and an explicit seat grant

Run from the frozen integrated checkout, substituting only the separately
confirmed current native PID. The exact SHA is reviewed input, not an auto-pin:

```powershell
$env:HARMONIC_SW_AUTOSTART='0'
$env:HARMONIC_REMOTE_CACHE_MODE='off'
$env:HARMONIC_DIAGNOSTIC_SW_PID='31860'
uv run --no-sync python cad/scripts/diagnostics/probe_source_dirty_recipe.py `
  --target fillister_screw --candidate HEAD `
  --source C:/src/harmonic-analyzer/cad/out/sldprt/fillister-screw.SLDPRT `
  --expected-sha256 f3adf8b31928cb001a623d9970a42f1a911335e8b4060c866c8a17d6524d5d4a
```

The existing parent runner holds the machine-global seat; the worker attaches
only and forwards the exact target, candidate and source. The receipt records
those inputs, required dimension names, original/copy hashes, baseline flags,
observations and the first dirty/clean-before-finalizer stop.

## Offline proof

The fail-first run retained 21 failures and 29 passing cases
(`pytest-telemetry/run-_j0q3xej`): missing target/visibility capture and malformed
read rejection were not implemented. Existing arbor/tip assertions were not
relaxed. The final fixture invokes the **real** whole-text helper with a void
SetText(0) test double, verifies True→False numeric visibility and all eight text
fields, and proves no later operation or finalizer runs. A separate malformed
transition preserves the capture error and stops as well. This unit test does
not establish native source propagation.

The existing source-authoring fixture gained only the native-shaped
`ShowDimensionValue=True` property; its save, cold, source and failure assertions
are unchanged. No COM, root checkout, adapter or remote write was performed.

Focused/adjacent verification passed 358 tests in 6.64 s
(`pytest-telemetry/run-kyuo8wsm`), covering the real owned-copy lifecycle,
source authoring/save boundaries, template banks, recipe loader/factory, and
unchanged fillister drawing assertions. Ruff F and `git diff --check` passed.
