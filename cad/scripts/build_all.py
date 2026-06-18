r"""DEPRECATED: the from-scratch orchestrator is replaced by ``doit`` (dodo.py).

The hand-rolled skip-if-exists / ``--rebuild`` / ``--clean`` bookkeeping is gone.
``doit`` does hash-based staleness (immune to git/worktree mtime churn) and a
part->assembly DAG that REFRESHES an assembly (cheap reopen + ForceRebuild3) when
only its parts changed, instead of the ~500 s from-scratch rebuild. See ``dodo.py``
at the repo root for the commands.

Migration::

    build_all.py                 ->  doit
    build_all.py --rebuild <p>   ->  doit part:<p>            (assemblies refresh)
    build_all.py --clean         ->  doit clean && doit       (or delete cad/out)
    (force a full assembly)      ->  del cad\out\sldasm\<a>.SLDASM && doit assembly:<a>

Run doit with the SolidWorks build venv python (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe -m doit

This shim forwards a bare invocation to ``doit`` so existing muscle memory still
builds; the old flags are rejected with their doit equivalent.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_FLAG_HELP = {
    "--clean": "doit clean    (then `doit` to rebuild)",
    "--rebuild": "doit part:<stem>    (downstream assemblies auto-refresh)",
}


def main() -> int:
    print("DEPRECATED: build_all.py is replaced by `doit` (see dodo.py)")
    flags = [a for a in sys.argv[1:] if a in _FLAG_HELP]
    if flags:
        print("!!  build_all.py is retired; the old flags map to doit:")
        for flag in flags:
            print(f"      {flag:<10} ->  {_FLAG_HELP[flag]}")
        return 2
    print("--  forwarding to `doit` (see dodo.py) ...")
    return subprocess.run(
        [sys.executable, "-m", "doit", *sys.argv[1:]], cwd=str(REPO_ROOT)
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
