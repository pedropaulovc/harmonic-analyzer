# Prepared defaults in drawing builds

Implementation scope checked on 2026-09-07 at `e5b3da74`. Measurements below
belong to their named revisions; they are not a current fleet result or schedule.
Work sequencing belongs to the [project](https://github.com/users/pedropaulovc/projects/1).

The drawing-only runner prepares or validates a content-addressed DRWDOT before
the recipe opens its source. It then passes a synchronous `drawing_factory`
keyword into the unchanged view, dimension, annotation and finalizer logic.
Every recipe declares `TEMPLATE_SPEC` from its actual scale and precision;
shared fastener and assembly drawing helpers forward the same callable.

`_drawing_sheet_setup.new_project_drawing` is the normal initializer used to
prepare an entry. It never calls the runner. No global factory replacement,
adapter mode, new doit task or concurrent COM operation is involved.
The existing production `run_build` connect/CloseAllDocuments policy is unchanged;
this change does not claim to preserve documents that policy closes.
Invoke drawings through `uv run python -m doit drawing:<registry-name>` so the
existing machine seat is held. An uncoordinated direct script launch now fails
before connect/cleanup, rather than reaching template preparation without a lock.

The preparation key includes original template bytes, actual preparation
and validation helper closures, adapter/config/lock inputs, canonical 1:1 scale
and precision, Python runtime and native SOLIDWORKS revision. Hits verify the
manifest, receipt and derived bytes; corruption fails rather than rebuilding or selecting another
factory. The inherited factory revalidates its entry before creating a drawing.
An adapter/spec mismatch, duplicate creation or unconsumed factory fails.

The production drawing dependency closure includes these new helpers, so normal
doit freshness and remote cache keys change together. Source execution-token and
original-template dependencies remain intact. The derived cache directory is
not an independent recipe input. Parts and assembly builds do not import the
drawing runner. Blank-default validation genuinely uses annotation measurement
and rectangle helpers; edits to those invalidate every drawing. The seven
native-layout pilots additionally import `_drawing_project_layout` directly;
the factory does not enable that layout policy for the other recipes.

There are 15 current scale specifications, all at two decimal places. Each
recipe retains its requested spec, while preparation stores one truthful 1:1
base per precision. The current fleet therefore shares one base, rather than
paying for the older design's 15 scale-specific preparations. Before any model
views exist, the inherited factory validates the base, its empty sheet and exact
active drawing, then calls `SetScale(numerator, denominator, True, False)` and
checks the requested pair. These are the normal initializer's flags: scale
annotation positions, not text height. The finalizer still assigns each populated
sheet's property-linked model view and verifies the actual requested scale.
See the [canonical base contract and native evidence](canonical-prepared-template-base.md).

## Acceptance scope

The earlier [production MISS/HIT at `d6ad5aad`](prepared-template-viewport-control.md#production-misshit-at-d6ad5aad)
completed fulcrum and pivot drawing tasks. The canonical control at `7c86fdba`
later passed all 15 same-requested-scale normal/prepared pairs, including raw
defaults, viewport, saved/cold and printed comparisons on 30 blank drawings.
Those results establish their recorded boundaries, not the final populated fleet.

The remaining merge evidence is a successful full `uv run python -m doit -n 4`
at the final integrated head, affected-render and complete-sheet inspection, and
the saved/cold source, attachment and printed witnesses required by the enabled
annotation changes. `build` includes all 92 drawings; `build_bare` does not.
Production `finalize_drawing` saves native/PDF and renders PNG, but does not
cold-reopen. A successful drawing task alone is not cold-persistence evidence.
One top-of-stack build and visual pass can cover the stacked factory change.

Normal setup remains an explicit diagnostic control. Untried arrangement,
surface-readback or save variants are not additional merge requirements unless
chosen to resolve a production correctness gap. A matched full-recipe/fleet
normal-versus-canonical comparison must include cold preparation and instance
scaling before claiming an end-to-end speedup. No such speedup is claimed here.

## Owned validation and the diagnostic contract

An owned pilot materializes through its existing CREATE/SAVE_AS and guarded
directory-relocation scopes before source opening. It then constructs the same
`prepared_drawing_factory(adapter, entry, spec=requested)` used by production
and passes it into the recipe inside the existing single-drawing creation scope.
NORMAL uses the explicit normal factory and never silently falls back from a
prepared failure.

Current recipe-loading diagnostics require the explicit, required
`drawing_factory` keyword and `TEMPLATE_SPEC`. Pre-migration Git revisions must
run with their matching historical tooling in a separate checkout; there is no
automatic old/new signature adaptation. This deliberately changes invocation
plumbing, not ownership, source-value, cold-reopen or print acceptance gates.

## Fulcrum empty-callout acceptance at `5eb96629`

Historical per-scale results, retained in the 2026-09-07 audit: the following
fulcrum, pivot and lever runs predate canonical preparation. Their hashes,
timings and acceptance scope apply to the recorded implementations.

The owned prepared full-recipe pilot passed on adapter `e77bfda4`, PID 31860,
after `a96cb782` removed the rebuild for empty callout maps. Receipt
`cad/out/reports/datum-policy-zkq8ce0i/pilot.json` has SHA-256
`40a7b468df9c484da558dec3058bc4358a5167138aa9c8ab5b7829c14c12f9aa`.

The fresh isolated entry's MISS took 35.544 s and its checked HIT 0.043 s.
Drawing creation from that entry took 1.068 s, included in the 17.992 s recipe;
total diagnostic time was 129.523 s. These are different scopes, not an A/B
measurement of the removed rebuild. Cold annotation comparison had zero
rejections and zero coordinate-roundoff exclusions. All five explicit roles
(datum, cylindricity, two end perpendicularities and bearing finish) retained
their exact source/drawing witnesses through cold reopening. The PNG eye pass
found readable dimensions, controls and title text with the expected geometry.

Originals and the owned source retained exact hashes; the clean/visible baseline
pivot part and drawing were preserved, owned cleanup succeeded and final guards
were empty. This validates one empty-map recipe through that revision's prepared
factory, not the remaining 21 empty-map recipes or the complete drawing fleet.

The matching pivot-shaft run at `bb56cd28` also passed built/cold checks and
visual inspection: `datum-policy-yc6v83ov/pilot.json`, SHA-256
`71245249198d0ad3a2185a52c446146068954a3310e9d4674154c7d463870d62`.
Its fresh isolated MISS/HIT took 35.640/0.045 s; factory setup took 1.135 s,
included in the 17.924 s recipe. Total diagnostic time was 123.988 s.
Both cold comparison arrays were empty and the same five explicit roles passed.
Source hashes were exact at every saved/closed/reopened checkpoint, baseline
documents were preserved, cleanup succeeded and final guards were empty.
These are two accepted empty-map recipes, not an A/B fleet timing result.

## Lever prepared acceptance at `a25fe21c`

The owned channel-lever recipe also passed built/cold and visual acceptance on
adapter `e77bfda4`, PID 31860: `datum-policy-dqu2i_at/pilot.json`, SHA-256
`7e450161e9575a2f3afc786d8a30c7b645ed5cb910c8a50eed4fd3d63dd55dc9`.
Its isolated MISS/HIT took 37.687/0.046 s. Factory setup took 1.110 s,
included in the 140.089 s recipe; total diagnostic time was 279.759 s.
The two cold comparison arrays were empty. BASIC dimensions, raw source values
and annotation witnesses passed, originals/copy hashes remained exact, and the
baseline pivot documents were preserved with successful cleanup and no final
guard errors. The PNG retained readable dimensions and native leader positions.

This accepts one prepared lever recipe, not a fleet speedup: its 140 s recipe
cost remains after the roughly one-second factory setup. These three retained
runs precede the setup-module extraction in
[prepared-template-key-isolation.md](prepared-template-key-isolation.md); that
later implementation must be assessed using its own evidence, including the
canonical blank control linked above, rather than treating these older timings
as measurements of the current populated fleet.
