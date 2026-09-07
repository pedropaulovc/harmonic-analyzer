# Native recipe dependency separation

Offline candidate based on `a89a27b0b4f6b77b666a6d0418a013c07bd56436`.
This improves future edits; it does **not** make stale artifacts reusable in the
current build. Native execution, full-stack acceptance and clean review remain
separate gates.

## Boundaries

- `_dimension_prefix.py` owns the diagnostic-only prefix storage operation.
  Its corrected void `SetText` handling, exact `GetText` comparison and operation
  span are unchanged. `_drawing_marks` no longer defines or re-exports it.
- `_model_provenance.py` owns `DRAWN_BY`. All eight assembly builders import the
  constant directly. Actual author metadata remains a recipe input.
- `cone_pivot_post_callouts`, `crank_drive_gear_callouts`,
  `cone_pivot_screw_callouts`, and `fillister_screw_callouts` own the existing
  manufacturing text maps. Their builders and drawings share the same objects.
  Thread text still derives from the original spec's `THREAD_DESIGNATION`.
  The geometric specs do not import these modules back.

The four maps previously reached three unrelated scalar consumers:
`cone_swing_platform`, `harmonic_base`, and `platen_clip`. Geometry/spec edits
still invalidate those genuine consumers. No manufacturing text, dimension
selection, native call sequence, placement, tolerance or acceptance predicate is
changed. Existing assertions use the new owning module where the data moved.
The intentional fillister pilot-enrollment disagreement is not resolved here.

`_common.py`, `dodo.py`, `_buildgraph.py`, adapter source, assembly pattern/coupling
helpers and VM2's turned-part recipes are unchanged. The remaining 31 callout
specs are not reorganized in this bounded batch. Broader assembly-builder import
separation remains VM2's work; it is not simulated by digest exclusions.

## Measured recipe effects

One-time migration: **87 of 108 part recipes and all eight assembly construction
recipes change**. This is the same affected part set as the foundation-to-a89
transition, not an expansion to all 108 parts. Changed recipes still require an
ordinary successful build or legitimate cache restore under the new inputs.

Future single-module content edits, measured with the actual production
dependency functions, `ContentChecker` and `_digest_files`:

| Edited operation/data | Part recipes before → after | Assembly construction recipes before → after |
| --- | ---: | ---: |
| Diagnostic prefix setter | 86 → 0 | 8 → 0 |
| Pivot-post callouts | 2 → 1 | 2 → 2 |
| Crank-drive-gear callouts | 2 → 1 | 2 → 0 |
| Cone-pivot-screw callouts | 2 → 1 | 3 → 2 |
| Fillister callouts | 2 → 1 | 3 → 0 |
| Other production `_drawing_marks` operations | 86 → 86 | 8 → 6 |

Every moved map still changes its own producing part and drawing recipe.
The table counts assembly **construction** inputs, not downstream assembly
refreshes: referenced part recipes and exact child execution identities continue
to propagate through the normal assembly graph. Nothing aliases cache keys,
restamps tokens, modifies ledgers or treats parent-save byte churn as a new
execution identity.

## Reproducible checks

```powershell
uv run --frozen python -m pytest cad/scripts/test_native_dependency_boundaries_drawing.py -q
uv run --frozen python -m doit check:recipe check:graph check:partiso
```

The new boundary tests locate the actual definition in either the old or new
module, then perturb that Python input's byte digest in memory. They retain the
real production dependency lists and digest functions. Synthetic adapter
sidecars stay in memory; no native artifacts, tokens or ledgers are written by
the tests. Before extraction, seven boundary checks failed and the positive
metadata control passed. Positive controls also require genuine geometric-spec
edits to invalidate their scalar consumers.

Existing fleet tests retain the original expression AST, shared map identity,
all 75 authored manufacturing rows and author/verify ordering. Existing prefix
tests retain exact readback, exception identity, operation spans and owned-copy
failure checks. These offline tests do not establish native save/cold/print
acceptance for the reorganized candidate.

The historical migration classifier recognizes only the four explicitly named
new map modules, including the existing fillister whole-text map. Its controls
keep geometric names, other owners and relative imports visible to the audit.
The 102-file AST comparison against a89 passes; this is its bounded manufacturing
migration check, not a review of every changed file or a native acceptance gate.
Map expressions and runtime object identity remain separately checked by the
fleet/fillister contracts, including definitions moved into new modules.

The final complete COM-free recipe gate produced **6,807 passed, one failed** in
168.35 s. The sole failure is the unchanged
`test_fillister_is_not_silently_enrolled_in_full_owned_pilot` assertion that
`fillister_screw` is absent from `TARGETS`, conflicting with its explicit existing
enrollment. Neither that assertion nor the enrollment/source pin is changed.
The run is therefore not a green recipe gate. Its complete log is retained at
`cad/out/logs/check-recipe.log`, with isolated telemetry in
`cad/out/reports/pytest-telemetry/run-d4gyopfh`. Graph passed 89 tests and part
isolation passed four tests; neither result covers native execution.

Local exact-input evidence is retained under
`cad/out/reports/dependency-separation/`: `audit_candidate.py` and `candidate.json`.
The script requires the SHA-pinned earlier read-only baseline audit; its report
includes candidate Python hashes, per-task input differences and edit effects.
That retained local evidence is not a portable cache or manufacturing manifest.
