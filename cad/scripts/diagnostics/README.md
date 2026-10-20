# Diagnostics archive

One-off investigation scripts (`probe_*`, `diag_*`, `poc_*`, `fix_*`) kept for
their hard-won findings, moved here to declutter `cad/scripts/`. They are **not**
part of the build (`doit`/`dodo.py` ignores this directory) and are not maintained.

Shared helpers are imported directly from their focused modules, such as
`_com`, `_check` and `_session`. The path-only `_script_paths.py` bootstrap
locates `cad/scripts` for standalone entrypoints; it re-exports no helpers.
The existing `_chain.py` shim still supports archived chain imports:

```
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\probe_motion.py
```

Reusable knowledge from these has been distilled into the build scripts,
`cad/DIMENSIONS.md`, and the project memory; treat anything here as historical.

## Branch-only paper-drive matrix experiment

The isolated raw-matrix branch uses
[`_verify_pd_digest_probe.py`](../_verify_pd_digest_probe.py), outside this archive,
through the existing supervised paper-drive soundness task, not a standalone
diagnostic launcher. Native execution requires separate parent authorization.
The historical artifact provenance and authenticated 91-file preservation set
remain unchanged. This branch refuses every part/assembly cache miss or restore
error before native producer dispatch or publication; it must never rebuild a
historical substitute. Only exact historical prerequisite restores are allowed.

After the saved Default digest reproduces, the probe checks all 145 components
with wrapped A1/A2, raw B, then wrapped A3 controls. It measures six complete
inventory pairs in AB/BA/AB/BA/AB/BA order, using identical strict finite-16
validation, exact value/hex comparisons against both the paired arm and control,
and explicit pre/post document/component-state equality. Timers include transform
disposal; exception-frame disposal follows both cause and context chains before
timer stop or owned-document cleanup. Evidence remains primitive-only.

For a soundness invocation containing paper-drive, `verify.py` wraps the existing
`run_build` entrypoint with `run_preserved_session`. The wrapper authenticates and
hashes all 91 files **before session entry**, including connection-time document
cleanup, and rehashes them **after `run_build` returns or raises**, including normal
verification and session teardown. It adds `outer_session` evidence to the same
JSON, preserving original nonzero exit codes, nonzero `SystemExit`, and other
exceptions when secondary preservation/publication errors occur. A success-coded
`SystemExit` (`None` or integer zero, including `False`) is retained as failure
evidence but cannot bypass an incomplete outer contract with process exit zero.
Other verification invocations are unchanged.
The inner helper may persist a `pending_outer_session` checkpoint but emits no
task-log report while this guard is active. Exactly one final checksummed
`PD_DIGEST_PROBE_JSON` emission follows outer posthash/finalization; only a complete
outer report and successful session permit a zero subprocess exit and a new stamp.
Any required read, state, ownership, preservation or publication failure fails the
probe. A hard process exit/crash can prevent finalization: missing final outer
evidence is incomplete, never synthetic preservation success.

Exact experiment-recipe cache hits can still skip execution. Require real worker
execution and the final same-session report/log emission, not just a restored
stamp/report or a workflow success. No force refresh, alternate salt/namespace,
environment opt-in, seat takeover, or worker retry change is part of this branch.

This is a warm, same-seat, collapsed-PD microbenchmark. It neither changes the
production getter nor establishes an RPC saving, exploding-drive-train speedup,
or end-to-end build improvement. Its pure regression tests are enrolled in the
existing `check:recipe` gate; offline passes do not prove native behavior.
