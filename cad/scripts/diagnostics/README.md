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
