# Prepared defaults in drawing builds

The drawing-only runner prepares or validates a content-addressed DRWDOT before
the recipe opens its source. It then passes a synchronous `drawing_factory`
keyword into the unchanged view, dimension, annotation and finalizer logic.
Every recipe declares `TEMPLATE_SPEC` from its actual scale and precision;
shared fastener and assembly drawing helpers forward the same callable.

`_drawing_common.new_project_drawing` remains the normal initializer used to
prepare an entry. It never calls the runner. No global factory replacement,
adapter mode, new doit task or concurrent COM operation is involved.
The existing production `run_build` connect/CloseAllDocuments policy is unchanged;
this change does not claim to preserve documents that policy closes.
Invoke drawings through `uv run python -m doit drawing:<registry-name>` so the
existing machine seat is held. An uncoordinated direct script launch now fails
before connect/cleanup, rather than reaching template preparation without a lock.

The existing preparation key includes original template bytes, actual preparation
and validation helper closures, adapter/config/lock inputs, exact scale/precision,
Python runtime and native SOLIDWORKS revision. Hits verify the manifest, receipt
and derived bytes; corruption fails rather than rebuilding or selecting another
factory. The inherited factory revalidates its entry before creating a drawing.
An adapter/spec mismatch, duplicate creation or unconsumed factory fails.

The production drawing dependency closure includes these new helpers, so normal
doit freshness and remote cache keys change together. Source execution-token and
original-template dependencies remain intact. The derived cache directory is
not an independent recipe input. Parts and assembly builds do not import the
drawing runner. Blank-default validation genuinely uses annotation measurement
and rectangle helpers; edits to those now invalidate every drawing. Placement,
GTol, callout and handoff helpers remain exclusive to the native-layout pilots.

There are 15 current scale specifications, all at two decimal places. Each
unchanged specification reuses one validated entry, but a first cold fleet run
pays up to 15 preparations. No first-fleet speedup is claimed. The earlier owned
blank normal/miss/hit and prepared-rocker results motivate this integration;
native acceptance of this exact production boundary and broader fleet fit still
need to run before merge. Template authoring/promotion is a separate change.

## Owned validation and the diagnostic contract

An owned pilot materializes through its existing CREATE/SAVE_AS and guarded
directory-relocation scopes before source opening. It then constructs the same
`prepared_drawing_factory(adapter, entry)` used by production and passes it into
the recipe inside the existing single-drawing creation scope. NORMAL uses the
explicit normal factory and never silently falls back from a prepared failure.

Current recipe-loading diagnostics require the explicit, required
`drawing_factory` keyword and `TEMPLATE_SPEC`. Pre-migration Git revisions must
run with their matching historical tooling in a separate checkout; there is no
automatic old/new signature adaptation. This deliberately changes invocation
plumbing, not ownership, source-value, cold-reopen or print acceptance gates.
