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
remain unchanged.

After the saved Default digest reproduces, the probe checks all 145 components
with wrapped A1/A2, raw B, then wrapped A3 controls. It measures six complete
inventory pairs in AB/BA/AB/BA/AB/BA order, using identical strict finite-16
validation, exact value/hex comparisons against both the paired arm and control,
and explicit pre/post document/component-state equality. Timers include transform
disposal; exception-frame disposal follows both cause and context chains before
timer stop or owned-document cleanup. Evidence remains primitive-only, and any
required read, state, ownership, preservation or publication failure fails the
probe.

This is a warm, same-seat, collapsed-PD microbenchmark. It neither changes the
production getter nor establishes an RPC saving, exploding-drive-train speedup,
or end-to-end build improvement. Its pure regression tests are enrolled in the
existing `check:recipe` gate; offline passes do not prove native behavior.
