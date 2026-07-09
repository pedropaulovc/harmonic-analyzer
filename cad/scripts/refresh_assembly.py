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
        dof_gate = None
        if asm_name == "harmonic-analyzer":
            # The top's DOF gate is the OPERATIONAL one (six flexible movers,
            # live chains) -- imported here, off every build recipe, and passed
            # in so _assembly.py itself never depends on _assembly_top.
            from _assembly_top import assert_top_operational_dof

            dof_gate = assert_top_operational_dof
        else:
            # A `locked` assembly keeps the STRICT fully-defined gate even if a
            # stale free-era park sidecar survived on disk (the locked FULL
            # build unlinks it via write_park_specs, but the CONFIG is the
            # authority, not a file's absence -- codex #217 round 4). Read here,
            # off every build recipe, so _assembly.py stays _config-free.
            import _config
            from _assembly import assert_components_fully_defined, is_locked_build

            mode = _config.machine("build_lock").get(
                asm_name.replace("-", "_"))
            if mode is not None and is_locked_build(str(mode)):
                dof_gate = assert_components_fully_defined
        artefacts = await refresh_assembly(adapter, asm_name, dof_gate=dof_gate)
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
