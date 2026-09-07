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
and measured visible note content. No floats are rounded: represented native
coordinates also compare exactly. This stricter comparison has **not yet been
run natively** and may reject a representational change; any later numerical
contract requires measured evidence, not blanket tolerance.

An empty linked note's extent is observational only after every native text,
stroke, other display primitive and ordinary/multi-jog leader count is zero.
Its link, visibility, anchor and font remain exact. The committed blank-template
control proved that such no-ink extents can collapse on instantiation. All raw
extent observations remain in the receipt. Unsupported non-note annotations
on a blank sheet fail; they are not silently omitted. This is a template-default
witness, not a manufacturing-sheet geometry proof.

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

Still required before opt-in use: a dedicated owned native miss/hit control,
source/active-document preservation on the real call shapes, raw-default
readback, measured complete hit overhead, then matched full recipe/save/cold
reopen and visual acceptance. No production recipe is switched by this patch.
