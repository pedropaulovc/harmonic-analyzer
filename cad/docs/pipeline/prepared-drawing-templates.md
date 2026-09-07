# Prepared drawing templates: opt-in implementation

The existing `new_project_drawing` path and every production recipe remain
unchanged. No rollout or full-sheet native acceptance is claimed by this patch.

The preceding blank-sheet control (`diagnostics/benchmark_template_setup.py`,
frozen `ba2efb5d`, receipt `template-setup-abba-o46g8sv9`) observed current setup
5.520 s mean versus inherited setup 1.318 s, with 36.409 s one-time preparation.
That was one exploratory ABBA, overlapped by COM-free tests on the same host.
It establishes neither end-to-end speedup nor a conflict probability. Full-recipe
cold-reopen title placement remains a separate acceptance issue.

## API and scope

Explicit callers import `_drawing_prepared_template`; `_drawing_common` does
not import it. This preserves the existing dependency isolation of unmigrated
drawing recipes. The entry type itself selects the prepared policy:

```python
from _drawing_prepared_template import (
    prepare_project_drawing_template,
    inherited_drawing,
)

# Already inside the existing machine-global COM seat, before the drawing's
# creation scope. Any already-open source document remains open and unchanged.
entry = await prepare_project_drawing_template(adapter, scale=(2, 1), decimals=2)
draw, sheet = inherited_drawing(adapter, entry)
```

The accessor prepares once on a miss. The factory only verifies and consumes a
completed entry. Neither silently falls back, changes application preferences,
alters model/view quality, or changes any source model. The cache is local at
`cad/out/prepared-drawing-templates`; it does not replace doit recipe freshness,
execution tokens, the remote artifact cache, or manufacturing/layout gates.

The key includes original project-template bytes, exact scale/precision, full
native revision, interpreter version/architecture, lock/project files, all
adapter Python source, configuration YAML, and the existing transitive local
helper closure of both preparation and current setup. Whole modules are hashed:
unrelated edits in those modules can cause extra preparation. This deliberate
over-invalidation avoids a new function-level dependency analyzer.

Hits verify current input identity, manifest identity, derived DRWDOT hash, and
the hashed native validation receipt. Failed preparation retains its fresh
`pending-*` directory and receipt; incomplete/corrupt published entries fail
loudly rather than being overwritten. No reset/retry is built in.

## Native preparation contract

Preparation creates two blank drawings: current setup saved once as DRWDOT,
then a fresh instance of that DRWDOT. It compares raw units, all ten dimension
style scopes, sheet properties, linked-note expressions/multiplicity, fonts,
horizontal/vertical note justification, position locks, sheet-format visibility,
measured visible note content, and the template's surface-finish symbols. No
floats are rounded: represented native coordinates also compare exactly. The
first native normal baseline exposed an unsupported surface-finish inventory
before reaching cache preparation (recorded below). The expanded raw witness
subsequently passed normal setup and rejected two within-snapshot extent
differences during preparation. The read-order correction subsequently passed
the complete native normal/miss/hit control below; no numerical tolerance was
introduced.

An empty linked note's extent is observational only after every native text,
stroke, other display primitive and ordinary/multi-jog leader count is zero.
Its link, visibility, anchor and font remain exact. The committed blank-template
control proved that such no-ink extents can collapse on instantiation. All raw
extent observations remain in the receipt. Native surface-finish annotations
(kind 7) retain symbol family, its documented all-around/texture subtype, all ten
named text slots after `GetTextCount`, orientation/angle, lay/profile, GOST and
attachment/extra-leader properties, visibility, native XYZ, all sixteen raw
`ITextFormat` properties, `IsHeightSpecifiedInPts` and document-format inheritance.
This includes underline/strikeout, spacing, escapement/slant and text direction,
not only typeface and height. For SF preservation, `_drawing_native_display_data`
captures native `IDisplayData` directly, not a GDI-estimated text box: all ten
primitive counts; complete line/arc/polyline/triangle/arrowhead/polygon arrays;
text strings, XYZ, height, font, angle, reference, inversion, plane matrix and
line spacing; ordinary leader count/style and every native XYZ point. Native
array order, normals, color/style fields and even documented unused slots stay
unrounded. Null/empty text planes remain distinct observations; nine-element
planes are retained without projecting them. The reader rejects malformed
arrays, unknown polyline forms, ellipses/parabolas/points and multi-jog leaders
instead of certifying partial data. Text-in-box APIs document table-cell scope
and are not called for SFs. No native name is used as cross-document identity.
The `ISFSymbol.GetAnnotation` round-trip must match the enumerated annotation
before capture. Rows form an exact multiset, preserving duplicate symbols. Other
non-note kinds and unsupported symbol enums still fail, rather than disappearing
from the witness. This is a template-default witness, not a manufacturing-sheet
geometry proof.
It does not inventory the sheet-format sketch or logos; full rendered/vector
inspection remains required before rollout and is not implied by this receipt.

The native save preserves the proven complete legacy call shape:
`ClearSelection2(True); IModelDoc2.SaveAs3(path, 0, 0)`. The integer return is
recorded, not interpreted as the modern SaveAs options/status enum. Fresh file,
exact native path and complete re-instantiated defaults are mandatory.

Pre-existing document handles, path/title/kind, visibility, dirty state and disk
hashes must remain unchanged. Hidden baseline documents are refused because
documented `CloseDoc` behavior can unload them. Empty background sessions are
refused because closing their last document can exit SolidWorks. Only the exact
created handle is closed without saving; the previous adapter pointer and active
document are restored without rebuilding. A setup exception after `NewDocument`
can be cleaned up because current setup assigns `adapter.currentModel` only in
that call: exact baseline-plus-one-new-handle inventory and active identity are
still required. A changed user active document or extra native document stops
cleanup and retains the failure, rather than guessing ownership from its title.
Native save requires the owned handle still be both active and the adapter's
current model. Case-insensitive duplicate or empty document titles are refused
before save/close because the adapter's `CloseDoc` route identifies by title.

Owned diagnostics supply `operation_context(TemplateOperation, exact_path)`:
CREATE maps to their `ownership.creating_document(DocumentKind.DRAWING, path)`;
SAVE_AS maps to `ownership.saving_as(path)`. Register the containing owned
directory first. Call the accessor outside the recipe's creation scope; the
factory then runs inside that recipe scope. The production helper does not
import or bypass the diagnostic ownership framework.

## Verification and remaining acceptance

COM-free tests in `test_prepared_template_drawing.py` cover cache key changes,
corruption, partial publication, strict raw defaults, no-ink exclusions,
partial native creation failures, source preservation, and explicit factory
behavior. Its suffix enrolls it in the existing `check:recipe` test collection.

An offline six-read key profile over 248 actual source files measured 0.290 s
first call and 0.037–0.040 s subsequent calls. This includes static dependency
discovery and file hashing, but substitutes the native revision read and does
not measure COM, DRWDOT/receipt hit validation, or native instantiation:

```powershell
uv run python -c "import sys,time,json; from types import SimpleNamespace; sys.path.insert(0,'cad/scripts'); import _drawing_prepared_template as p; a=SimpleNamespace(swApp=SimpleNamespace(RevisionNumber=lambda:'34.3.0')); rows=[]
for i in range(6):
 start=time.perf_counter(); identity=p.preparation_inputs(a,p.TemplateSpec((2,1),2)); key=p._key(identity); rows.append(time.perf_counter()-start)
print(json.dumps({'native_calls':'none; RevisionNumber is injected','files':len(identity['source_sha256']),'seconds':rows},indent=2))"
```

The owned native miss/hit control, exact raw-default readback, source/session
preservation and complete hit overhead have now been observed below. Still
required before rollout: printed sheet-format preservation, then matched full
recipe/save/cold-reopen and visual acceptance. No production recipe is switched.

## First native cache control

`diagnostics/probe_prepared_template_cache.py` uses the production accessor and
factory with the existing attach-only owned-document runner. It makes exactly
one normal blank drawing, performs one cache miss (two preparation drawings),
instantiates its result, then performs a hit and instantiates again. The five
blank drawings close without saving; only the miss's one DRWDOT is saved. It
opens no part/source model, creates no model views and exports no trial drawing.

After source review and an exclusive seat grant, from the frozen checkout:

```powershell
$env:HARMONIC_SW_AUTOSTART='0'
$env:HARMONIC_REMOTE_CACHE_MODE='off'
$env:HARMONIC_DIAGNOSTIC_SW_PID='31860'
uv run python cad/scripts/diagnostics/probe_prepared_template_cache.py --expected-pid 31860 --scale 2 1 --decimals 2
```

31860 is the current reviewed-session PID, not a reusable default. The explicit
argument, environment and attached native PID must agree before preparation.
The parent wrapper takes the existing machine-global seat. AUTOSTART=0 disables
its recovery/retry path. No probe-triggered launch, global settings or shared
adapter/environment changes are permitted.

Each invocation creates its own cache/output root under
`cad/out/reports/prepared-template-cache/prepared-template-cache-*`. It retains
`measurements.json`, `ownership.json`, native preparation receipts and DRWDOT.
The original project template, all production preparation inputs and the
diagnostic/ownership/runner source fingerprints are pinned across the sequence,
including failure/finally checks. The published DRWDOT, manifest and native
receipt must remain byte-identical through the hit. Mutable ownership audit
JSON is identified separately, not treated as a native cache artifact.

The production pending-directory publication needs a narrow ownership handoff:
`relocate_prepared_template_directory` requires the registered old directory to
be absent, its validated sibling content-key entry to be inside the owned run,
no live/baseline/source/frozen document within either path, and the exact native
DRWDOT hash **and filesystem identity** captured when it closed. Manifest and
receipt validation must also pass before the directory registry changes. A
failed relocation remains failed; it does not create an ownership alias or
erase the missing-directory checkpoint error. Final checkpoint errors aggregate
with the original failure and are recorded in every writable owned receipt.

Accessor, factory, raw-default witness, ownership cleanup, relocation and input
guard timings are recorded separately. Accessor miss timing includes production
preparation and its native validation; hit includes actual key/manifest/receipt
verification. Inner factory timing still includes its adapter assignment. This
single sequence is not ABBA and does not establish end-to-end performance.

All raw-default comparisons remain strict, including note horizontal/vertical
justification, lock state and sheet-format visibility. Sketch/logo geometry and
model-linked title behavior are not covered by those note/default snapshots;
blank export/visual comparison and full-recipe cold-reopen acceptance remain
separate requirements before rollout. First failure stops this sequence; no
automatic weakening, reset or retry occurs.

### First normal-baseline result

At frozen root `c7405ed5b068b4d253f3d89ef0af1721ed00a48d`, the normal blank
drawing setup took 2.8968366 s and its witness ran 7.2077718 s before rejecting
`unsupported non-note blank-sheet annotations: [7, 7]`. This falsified the
validator's notes-only blank-sheet assumption; it did not test or fail the
cache accessor, template save, miss or hit. The receipt has zero accessor rows.

Evidence: root `cad/out/reports/prepared-template-cache/`
`prepared-template-cache-i7taja40/measurements.json`, SHA-256
`5a85d094de19a1210470501aa8fec5f2edbcbb7f8d863c3f0ce5414ec85485ab`.
The accompanying `ownership.json` records empty initial/final native inventories,
baseline preservation and no cleanup error. Native PID was 31860, revision
34.3.0. Original `harmonic-analyzer.DRWDOT` remained SHA-256
`cbad80d25315dddc9bb5fefd690915c6f18fa7d181ac8c30d2f1408a980b55cc`.

`test_prepared_template_surface_finish_drawing.py` first reproduced that same
two-kind-7 rejection, then exercises the added exact SF witness, documented
family-specific getters, duplicate inventory and rejection of changed text,
font, inheritance, placement, native internal geometry and unknown kinds.
This extends the validator; it does not normalize or remove either symbol.
The expanded normal/miss/hit sequence still needs native acceptance, followed
by blank export/visual and full-recipe cold-reopen checks before rollout.

### Raw SF capture replaces the layout font estimator

The next normal control, frozen root `15c20ab73220dc0cf2517603555cd251ec8d0a77`,
completed the added native SF/font getters, then the derived `annotation_box`
rejected the actual font tuple `('Century Gothic', 0.0013229166666666667, 5,
True, 1.0, False, False)`. Normal setup took 2.9748459 s; the failed witness took
1.1059245 s. Cache accessor/save/miss/hit still had not run.

Receipt: `prepared-template-cache-y18kfdkk/measurements.json` under the same root
report directory, SHA-256
`b249fb9e60394f3fd18a51596e1049c641e4cddf73c9801798340b20d3ab7c21`.
Ownership records empty baseline/final inventories, no cleanup error and the
same unchanged original template SHA as above.

The wrong assumption was that preserving template content needed the layout
estimator's calibrated font bounds. The committed regression uses the real
estimator to reproduce this exact 5-point rejection, then requires the raw SF
capture to succeed with that same native format. Existing font calibration is
unchanged. Prior derived-geometry assertions were replaced with stricter raw
array/component drift checks, not removed. The notes path remains unchanged.
This raw equality check does not prove printed sketch/logo geometry or rendering;
blank PDF/vector/visual comparison and full-recipe acceptance remain required.
The revised raw control's first native result follows.

### Normal raw capture passes; early and later note extents disagree

At root `6173108a2c05f30700d106f7315817d196077498`, normal setup passed in
3.2238526 s plus 8.2781968 s for its complete witness. The miss ran 21.9323562 s
and failed exact comparison only at the UNIT linked note's two raw extent-X
values. Early X limits were `[0.4024436674473067, 0.4141235035128806]`; later
limits were `[0.40077511943793903, 0.4154583419203746]` metres. Both snapshots'
measured native body/envelope already matched those later limits exactly;
text, links, formatting and raw SF content also matched.

Evidence: `prepared-template-cache-1xvbtz_u/cache/`
`pending-541278447690-37kvnlsy/receipt.json`, SHA-256
`0e403837120483813c46290821bc93dcdf4f40b6b60f12ce39bd67502cb30732`.
The outer measurement SHA is
`d37c4a6ad376b7617a166666ce3cd87ce36e69574eb852705b0dd846af353f34`.
The original template hash and empty baseline/final document inventories remained
unchanged, with no cleanup error. Three owned documents closed; one fresh DRWDOT
was retained in the failed unpublished directory. The hit was never reached.

This is consistent with native content/extent settling during the original
`GetExtent` → text/link → measurement sequence; the precise triggering getter
has not been isolated. The validator now reads text/link and native measurement
before the raw extent. No setter, retry, second normalization or exception
exclusion is added. A fail-first order regression models the observed mismatch,
asserts the raw and measured extent agree, and preserves exact rejection of a
1e-12 extent change even when measured geometry stays identical. The reordered
normal/miss/hit control's result follows.

### Complete native cache control passes

At root `1acb6dfe`, PID 31860 / native revision 34.3.0, the normal setup, cache
miss, prepared instantiation, cache hit and second instantiation all passed.
Every raw-default comparison remained exact. Receipt:
`prepared-template-cache-azvn2o4l/measurements.json`, SHA-256
`8c33ff38fc2ce526da250e4b6acf12cf05c446403a0665476158f958eede966c`.

| Observed operation | Seconds |
| --- | ---: |
| Normal factory | 3.062896 |
| One-time miss, including preparation and native validation | 23.082265 |
| Prepared factory after miss | 1.375135 |
| Cache-hit lookup and receipt/hash validation | 0.054509 |
| Prepared factory after hit | 1.286016 |

The hit lookup plus factory totals **1.340526 s**, versus 3.062896 s for the
normal factory in this sequence. Complete raw witnesses cost a further
8.504/8.600/8.673 s in the three trials, timed separately. This is one sequential
functional control, not ABBA or an end-to-end recipe benchmark. The reordered
UNIT-note read is supported by this result; which getter triggers native extent
settling remains unisolated.

Exactly five owned drawings closed, and only one owned DRWDOT was saved. The
original template stayed byte-exact, all nine input/cache guards passed, and
initial/final document inventories were empty with no cleanup error. Published
DRWDOT SHA-256 is
`b840e9284276bed46116a5345c6d1a54f23543297400044ab023d13cbe4a8b52`;
its native receipt SHA-256 is
`7388ec44b732ab6c654d50c357cf5a75f2dc2406762f5d9e9075d391e0002ec7`.
Neither artifact changed on the hit. This run exported no PDF/PNG and opened no
model, so printed sketch/logo preservation and complete recipe acceptance are
still unproved. The helper stays opt-in.

### Printed-format control

The same probe accepts `--printed-format compare`. It adds one production
PDF-only export and 300-DPI PNG per normal/prepared-miss/prepared-hit trial,
without a native drawing save or model view. It requires identical full-sheet
pixels, PDF page size, text characters and unrounded PDF glyph boxes against
the normal positive control. Raw native defaults are measured again after each
export and must remain exact. Any difference stops before the next trial.

This checks printed appearance including sheet-format lines and logos at the
production preview resolution, not equality of every underlying PDF vector
command or future template variant. PDFs are retained for zoomed visual
inspection. Export/render/readback times are separate from setup timings. The
original template and published cache artifacts remain hash-guarded. Native
printed results and full-recipe validation are still pending for this option.
