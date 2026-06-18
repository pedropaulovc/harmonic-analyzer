r"""Incremental assembly refresh: reload parts in place (no re-insert/re-mate).

A ``.SLDASM`` is a thin reference layer over its part files, so when only a
referenced ``.SLDPRT``/sub-``.SLDASM`` changed, reopening the assembly and
force-rebuilding every configuration loads the new geometry WITHOUT the ~500 s
from-scratch ``create_assembly`` insert/mate loop. The heavy lifting (per-config
rebuild, health/DOF/interference gates, in-place ``Save3``, PNG export) lives in
:func:`_common.refresh_assembly`; this is the thin entrypoint the build graph
(``dodo.py``) shells out to for the cheap path.

Fail loud: any dangling mate, free DOF, or interference halts the refresh with a
non-zero exit and leaves the ``.SLDASM`` untouched -- recover with the full
escape (delete the target + ``doit assembly:<stem>``).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\refresh_assembly.py <stem>

where ``<stem>`` is an assembly stem (``output``, ``drive_train``,
``harmonic_analyzer``, ...); ``_`` and ``-`` are interchangeable.
"""

from __future__ import annotations

import sys

from _common import refresh_assembly, run_build

USAGE = "usage: refresh_assembly.py <assembly-stem>  (e.g. output, drive-train)"


def main() -> int:
    if len(sys.argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    asm_name = sys.argv[1].removesuffix(".SLDASM").replace("_", "-")

    async def build(adapter):
        return await refresh_assembly(adapter, asm_name)

    return run_build(build)


if __name__ == "__main__":
    sys.exit(main())
