# Local crank baseline capture

The `bootstrap` mode of `probe_crank_arm_entities.py` captures a freshly built
local source without changing the accepted VM2 source or receipt pins. It ends
with `status: captured`, `acceptance: not_run`, and `equivalence: unproven`.
A successful capture is evidence for a later migration decision, not that decision.

The implementation starts at integration head
`bca3e4e7231ea5c07b8c9bbc21b9ea131a806cf1`. The original `source`, `drawing`,
`positive`, and `candidate` modes still reject replacement sources, including one
whose execution token matches its new bytes. Their `cfde0355...a65b4d3` source
pin, `19431a0088519bd8755b941a3da73a699c0ed7e1` baseline and pinned historical
receipt are unchanged. No shared resolver, production recipe, or adapter changes
are part of this capture mode.

## Required provenance

Capture requires the caller's exact expected SHA-256, full builder commit and
local native build trace ID. Before entering the owned runner and again at final
capture, it verifies:

- The checkout and its adapter are clean, HEAD is the supplied builder revision,
  and the adapter matches its gitlink. Python, recipe and adapter imports belong
  to this checkout and its own `.venv`.
- The source and `.crank-arm.execution` token equal the supplied SHA. Source and
  token file identities, size and timestamps are retained and compared again.
- The local `cad/out/reports/telemetry/traces.jsonl` contains exactly one successful
  `task part:crank_arm` and its successful `part.build` child in the supplied trace.
  The task must report a cache miss. Source modification time falls within the
  build span; token modification follows it within the task span. A later local
  crank task rejects the request. Other appended telemetry is allowed.
- The matching `logs.jsonl` has exactly one launch and one output-part record
  in that task's trace and span. They identify this checkout's `.venv` Python,
  `build_crank_arm.py`, output part and `_telemetry.py` origin. The launch occurs
  before `part.build`, and the output record after it. Both complete records
  are retained and compared again at final capture. A shared telemetry directory
  does not make a foreign producer local.
- An explicit positive `HARMONIC_DIAGNOSTIC_SW_PID` identifies the licensed process.
  The shared attach-only runner still requires autostart disabled and the parent
  seat lock. The callback independently checks the attached PID.

After opening only a new owned copy, the native `Generator` property must equal
`harmonic-analyzer @ <short builder revision>` without a dirty suffix. This uses
the existing `read_required_properties` path and documented
`IModelDoc2.GetCustomInfoValue`; `GetSaveFlag`, document kind, exact path, active
document and native identity are checked around the source read. No property,
dimension, source save or token setter is introduced.

The build trace, producer logs, token and native stamp are consistency checks within
the local build workflow. They are not signed attestations and do not prove that
two independently rebuilt solids are geometrically equivalent. Copying a native
file or restamping its token does not satisfy this procedure.

## Parent-owned native sequence

Commit and freeze the implementation first. In that same isolated checkout,
with its pinned adapter and `uv sync --frozen` environment, the seat owner runs:

```powershell
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
$env:HARMONIC_SW_AUTOSTART = '0'
# Set HARMONIC_DIAGNOSTIC_SW_PID to the existing licensed process ID.
uv run --frozen python -m doit -a part:crank_arm
```

Wait for that native task to finish. Read and retain its actual source SHA,
execution token, full HEAD and successful local trace ID. Do not run a drawing
or assembly save between the source build and capture. Supply those observed
values explicitly (the placeholders below are intentionally not executable):

```powershell
uv run --frozen python cad/scripts/diagnostics/probe_crank_arm_entities.py bootstrap `
  --expected-source-sha <observed-64-character-source-sha> `
  --builder-revision <frozen-40-character-builder-head> `
  --builder-trace <observed-0x-trace-id>
```

The command acquires the existing parent seat wrapper and dispatches the guarded
worker. Do not invoke `--worker` directly or set a pretend seat flag. Source-only
capture opens an owned part copy, records the source dimension/display bank and
named entity/face geometry, then uses the existing owned cleanup path. It creates
no drawing, template, PDF or PNG.

To also capture a drawing, add an explicit `--baseline-revision` full commit. For
example, `2bd566f6224ee74390280922ca92fa9fa50091dc` names the rebased crank recipe.
The selected recipe must have the current explicit factory ABI and the same
adapter pin. The existing loader redirects only its source and output paths;
the receipt retains the exact recipe text hash and revision. Shared helpers are
those of the frozen local builder checkout, recorded by the existing prepared
factory guard, not a claim to replay every historical runtime file.

Preparation uses the existing owned, run-local prepared factory before opening
the source copy. The real recipe runs once. Its existing final layout and
manufacturing checks remain active. Capture records the resulting four views'
exact source/configuration ownership, attachment and annotation snapshots, raw
drawing dimensions and sheet properties. Original source, copied source and token
must remain byte-identical; native parameter handles and raw presentation must
also remain unchanged during that open lifetime. Existing report paths are never
overwritten. Operation errors and independent final guard errors remain in the
receipt and cause failure.
For a cancellation or keyboard interruption, this callback attempts owned-document
cleanup and the ownership checkpoint before rethrowing the original interruption.
This includes interruptions during final hash/provenance reads and receipt writes.
Cleanup runs once. The callback retains earlier capture errors and secondary
cleanup failures, then attempts a failed receipt write. If that write also fails,
the original interruption carries the write error as an exception note; the prior
receipt must not be treated as complete. This handling is local to `bootstrap`.

## Evidence still needed before changing pins

This mode never reads its own capture as historical manufacturing proof. The
current source schema includes tolerance applicability statuses that the old
native source receipt did not record. Missing historical fields remain missing;
there is no zero-fill, rounding allowance or invented status migration.

The source bank is an observed parameter/feature/display inventory, not a complete
BREP comparison. Named face/edge geometry provides additional raw evidence, but
cross-build native identities, old/new source equivalence, historical drawing
dimension and attachment equivalence, cold reopen and rendered print acceptance
remain unproved. The optional drawing uses current shared helpers even when its
recipe text is historical. Its retained PDF/PNG still needs visual inspection.

A later explicit migration must reconcile those schema and manufacturing facts
against independent historical evidence, then update only justified pins and run
the existing complete acceptance controls. No such migration or native capture
has been performed by this implementation task.

## Offline verification

The new CLI/provenance tests first failed on the absent mode and input reader
(`run-ysf6k6hk`); the actual recipe callback tests first failed on the absent
capture function (`run-gkfaqp1n`). Additional fail-first cases covered explicit
PID checks and a deleted copied file (`run-h32xx26h`), then cancellation cleanup
(`run-cta_x3pq`). These receipts are under this worktree's
`cad/out/reports/pytest-telemetry/`.

The final eight-suite run passed 237 tests in 5.18 seconds
(`run-qnqwflfz`): crank entities, candidate callback, failure receipts, recipe,
drawing, resolver performance, entity resolution and prepared-factory tests.
Tests compose the actual loader/recipe callback with mocked native boundaries;
they do not constitute native acceptance. Ruff and `git diff --check` passed.
An AST comparison against the base preserved all 19 existing probe functions
other than CLI dispatch and the source-reader extraction, all 23 existing test
functions/classes, and all top-level constants. No deliberate assertion changed.

## Review corrections after d76c9943

The Windows Codex full-base review of `d76c9943` against `bca3e4e7` found two
problems: trace location alone did not establish the producing checkout, and
interruptions inside the finalizer skipped owned cleanup. Its complete receipt is
retained at `C:/src/ha-bsurf-column-row-review/cad/out/reports/codex-crank-bootstrap-d76c9943/`.
The independent actual-callback reproduction (`run-4pqmm4uf`) left two owned
document doubles live and the receipt `running` when the final provenance read
was interrupted. This was an offline bug witness, not a native run.

The producer check uses existing logs; no shared runtime telemetry changed.
`dodo._run_subprocess` emits `">> part:crank_arm: " + " ".join(cmd)` from its
two-element Python/script argument list. `_common.run_build` emits
`"artefact part: " + path` after the build returns. Retained native trace
`0xd8cf5918a61444e622a0caa4fad294a7` in the primary checkout's September 2
`logs.jsonl` records both shapes with the same task span. This establishes the
record format, not acceptance of a new bootstrap source.

The diagnostic compares each complete emitted string against the frozen producer
paths. It does not parse the unquoted display string as a shell command, split
paths on spaces, strip quotes or accept path substrings. Windows paths containing
spaces are covered; added quotes/options and foreign/duplicate/missing records
reject. Other traces can coexist in the file without supplying this task's proof.

The first 20 new cases failed before the fixes (`run-edt5ruz4` in
`C:/src/ha-crank-bootstrap-guards/cad/out/reports/pytest-telemetry/`). They cover
producer identity and interruption in final provenance, hash and report operations.
The interruption tests call the real `capture_bootstrap` and shared
`owned_callback` with the existing native doubles. Historical modes, source pins
and manufacturing assertions remain unchanged. Native bootstrap and all later
equivalence/cold/print requirements remain pending.

After the fixes, the same eight suites passed 260 tests in 11.37 seconds
(`run-herr9u2a`). Ruff F/E9 and `git diff --check` passed. The read-only
`cad/out/reports/bootstrap-guard-audit.py` replay accepted the complete retained
September 2 task/build/log records; its full output is
`cad/out/reports/bootstrap-guard-audit.log` in the guards worktree. That audit also
confirmed all 27 unchanged probe definitions, 39 unchanged test definitions and
all existing top-level constants remain exact. Only the two corrected bootstrap
functions and the fixture's required producer-log bank are excluded from those
definition counts. This is log-format and offline regression evidence, not a
native bootstrap run.
