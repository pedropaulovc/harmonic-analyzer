# Fillister's declared model-dimension coverage

This is diagnostic coverage, not a drawing or source change. Native acceptance
of the new contract is pending. The original `checked_empty` failure remains
retained; no geometry annotation is added to make that counter nonzero.

## Retained failure and supported API contract

The owned prepared-factory pilot at `bac448575a824ec4333649e31be26d58239e08ac`
completed the 15.7737488 s fillister recipe, saved its drawing/PDF/PNG, then
rejected `checked_empty` before cold acceptance:
`cad/out/reports/datum-policy-smpqcc8q/pilot.json`, SHA-256
`4c4c89c20c46a084eb74111e278db67d6964f6851075b9da462e2940259fe517`.
Original and copied source stayed exactly
`e7b48995c9f2e87af473219edfca1500a14e77bd353a330c64883011ab4fb60d`;
runtime final guards and ownership cleanup passed.

The raw semantic bank contains all four concrete model dimensions, no excluded
dimensions, and no checked model geometry. `ShankDia@ShankProfile` and
`HeadDia@HeadProfile` each have one type-10 sketch segment. `HeadHt@Head` and
`ShankLg@Shank` have empty geometry arrays. The remaining two annotations are
ordinary notes. The unchanged recipe declares no datum, GTol or surface finish.

[GetAttachedEntities3](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotation~GetAttachedEntities3.html)
supports sketch segments and documents empty arrays for annotations without
geometry associations. Type 10 is outside this repository's generic geometry
reader, not unsupported by SolidWorks.
[GetDimension2](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDisplayDimension~GetDimension2.html)
returns the underlying model dimension. The existing dimension-attached-datum
witness and source-callout verifier already compare that handle with an
independently resolved source parameter. Names and rounded values alone do not
provide this proof.

## Explicit, bounded enrollment

`RecipeTarget.coverage` defaults to `GEOMETRY` for all sixteen other targets.
Only fillister declares `MODEL_DIMENSIONS_ONLY`, with this exact manifest:

| Source parameter | View orientation | Display type | Raw attachment types |
| --- | --- | ---: | --- |
| `HeadDia@HeadProfile` | `*Back` | 6 | `(10,)` |
| `ShankDia@ShankProfile` | `*Right` | 6 | `(10,)` |
| `HeadHt@Head` | `*Right` | 2 | `()` |
| `ShankLg@Shank` | `*Right` | 2 | `()` |

The declared view inventory is Right, Back and Isometric, each exactly once.
There is no target-name exception, `checked OR dimensions` predicate, fake
geometry signature, coordinate tolerance or new production helper dependency.
The default `_drawing_semantics` implementation and its deliberate
`test_semantic_gate_reports_exact_failed_conditions_and_retains_snapshot` test
remain unchanged. The explicit new policy is a different acceptance contract,
not a claim that the old guard passed.

The selected observer records four raw source parameters before the recipe.
For built and reopened drawings it freshly resolves the owned source by exact
path and proves each display's native parameter against the named source
parameter. It checks exact view/source/configuration, owner, visible/non-dangling
state, display roundtrip, required inventory and the declared attachment arrays.
Unexpected geometry annotations, attached notes, missing or duplicate dimensions,
and required geometry roles in the manifest fail. No sketch-entity identity or
geometry equivalence across reopen is claimed.

Values, tolerance type/min/max, all eight GetText compartments, numeric
visibility and both precision getters are retained without rounding. The source
bank must stay exact. Drawing text/numeric visibility must match the source;
drawing precision may differ from the source because the existing recipe formats
its imported displays, but must remain exact across drawing reopen. Live source
handles are discarded after the built capture; cold checks use freshly resolved
source and drawing handles. Dirty-state exit banks and secondary guard failures
are retained without replacing the original exception.

The generic attachment snapshot lends its already-enumerated view inventory to
the selected observer. There is no second full annotation enumeration for this
bank. The normal full native ink/layout capture still runs independently.
Expected thread designation and UNDERHEAD LENGTH must occur in the correct
dimension's printed runs. The observed native padding (`' #4-40 UNC-2A '`) is
trimmed only for literal-presence checks; raw strings stay exact in both banks.
The whole-text dimension rejects residual numeric or duplicate printed content.
No new save, export, rebuild, selection, or other native setter is introduced.

The prior saved PNG visibly contains the thread-only designation, head size and
height, underhead length and complete notes. That is a built-image observation,
not cold printing evidence. The existing pilot does not export a second cold
PDF/PNG; its fresh cold native text/ink/layout witnesses remain mandatory.

## Offline and native verification

New tests cover the four-row native-shaped bank, wrong source/view/parameter,
missing/duplicate dimensions, added geometry roles, raw value/tolerance/text and
numeric-visibility changes, malformed native booleans, fresh cold handles,
printed padding without content waivers, and failure/dirty-state evidence.
Real pilot composition tests exercise success, wrong imported identity, cold
raw-tolerance drift, and the unchanged production failure path. Existing real
ownership lifecycle tests keep every assertion; only their intentionally mocked
native witness seam receives the new declared observer.

The focused/adjacent run passed 478 tests in 28.63 s, including graph and
part-isolation tests (`pytest-telemetry/run-flsk73eu`). These are offline results,
not native acceptance or the full final build gate. The existing initial-source
read shapes are reused; the reference-dimension getter is checked on drawing
displays only, not added to source-part reads.

After reviewing and freezing the integrated head, the main seat owner can run
the existing `probe_datum_policy_recipes` parent command with
`--candidate <frozen-head> --target fillister_screw --factory prepared`, preserving
its explicit source/guard/report roots and attach-only environment. No input pin
changes or source reauthoring are part of this control. Success still requires
the exact source/hash/ownership guards, four-parameter native identities, full
printed/layout bank and fresh cold comparison; inspect the newly retained PNG.
