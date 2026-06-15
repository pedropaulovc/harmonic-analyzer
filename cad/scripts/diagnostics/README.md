# Diagnostics archive

One-off investigation scripts (`probe_*`, `diag_*`, `poc_*`, `fix_*`) kept for
their hard-won findings, moved here to declutter `cad/scripts/`. They are **not**
part of the build (`build_all.py` ignores this directory) and are not maintained.

They still import shared helpers with bare `from _common import ...` /
`from _chain import ...`; the `_common.py` / `_chain.py` shims in this directory
re-export the real modules one level up so the scripts keep running:

```
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\probe_motion.py
```

Reusable knowledge from these has been distilled into the build scripts,
`cad/DIMENSIONS.md`, and the project memory; treat anything here as historical.
