r"""Incremental assembly refresh: reload parts in place (no re-insert/re-mate).

A ``.SLDASM`` is a thin reference layer over its part files, so when only a
referenced ``.SLDPRT``/sub-``.SLDASM`` changed, reopening the assembly and
force-rebuilding every configuration loads the new geometry WITHOUT the ~500 s
from-scratch ``create_assembly`` insert/mate loop. The heavy lifting (per-config
rebuild, health/DOF/interference gates, in-place ``Save3``, PNG export) lives in
:func:`_assembly.refresh_assembly`; this is the thin entrypoint the build graph
(``dodo.py``) shells out to for the cheap path.

Fail loud: any dangling mate, free DOF, or interference halts the refresh with a
non-zero exit and leaves the ``.SLDASM`` untouched -- recover with the full
escape (delete the target + ``doit assembly:<stem>``).

Run (SolidWorks already open)::

    uv run python cad\scripts\refresh_assembly.py <stem>

where ``<stem>`` is an assembly stem (``output``, ``drive_train``,
``harmonic_analyzer``, ...); ``_`` and ``-`` are interchangeable.
"""

from __future__ import annotations

import sys

from _common import run_build
from _assembly import refresh_assembly

USAGE = "usage: refresh_assembly.py <assembly-stem>  (e.g. paper-drive, drive-train)"


def main() -> int:
    if len(sys.argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    asm_name = sys.argv[1].removesuffix(".SLDASM").replace("_", "-")

    async def build(adapter):
        artefacts = await refresh_assembly(adapter, asm_name)
        if asm_name == "harmonic-analyzer":
            # The top assembly's eight-views gallery + parts-only BOM are not part
            # of the generic refresh tail; regenerate them on the still-open doc so
            # a subassembly change does not leave them stale (codex review #6).
            from build_harmonic_analyzer_assembly import export_gallery_and_bom

            artefacts.update(await export_gallery_and_bom(adapter))
        return artefacts

    return run_build(build)


if __name__ == "__main__":
    sys.exit(main())
