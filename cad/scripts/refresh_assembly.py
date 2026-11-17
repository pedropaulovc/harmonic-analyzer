r"""Incremental assembly refresh: update a saved assembly in place (no re-insert/re-mate).

The ``parts`` tier (``_refresh_tier.RefreshTier.PARTS``), chosen by
``dodo.build_or_refresh`` from the recorded per-input digests: a ``.SLDASM`` is
a thin reference layer over its part files, so when only a referenced
``.SLDPRT``/sub-``.SLDASM`` changed, reopening the assembly and force-rebuilding
every configuration loads the new geometry WITHOUT the ~500 s from-scratch
``create_assembly`` insert/mate loop. The heavy lifting (per-config rebuild,
health/DOF/interference gates, in-place ``Save3``, PNG export) lives in
:func:`_assembly.refresh_assembly`.

Fail loud: any dangling mate, free DOF, interference or geometry drift halts the
refresh with a non-zero exit and leaves the ``.SLDASM`` unsaved. A failed
refresh needs the full escape (delete the target + ``doit assembly:<stem>``).

Run (SolidWorks already open)::

    uv run python cad\scripts\refresh_assembly.py <stem> parts

where ``<stem>`` is an assembly stem (``pd_paper_drive``, ``dt_drive_train``,
``ha_harmonic_analyzer``, ...); ``_`` and ``-`` are interchangeable.
"""

from __future__ import annotations

import importlib
import sys

from _buildgraph import interference_module
from _session import run_build
from _assembly import refresh_assembly
from _refresh_tier import RefreshTier

USAGE = "usage: refresh_assembly.py <assembly-stem> parts  (e.g. pd-paper-drive parts)"


def _allowed_pairs(asm_name: str):
    # The press-fit allowance lookup lives HERE (the entrypoint dodo invokes,
    # outside every assembly's recipe closure) and resolves only this
    # assembly's own table, so _<stem>_interference invalidates only the
    # builder that imports it directly (and the assemblies that contain it).
    return importlib.import_module(interference_module(asm_name)).ALLOWED_PAIRS


async def _refresh_parts(adapter, asm_name: str) -> dict[str, str]:
    native_contact_check = None
    if asm_name in ("ch-channel", "sm-summing"):
        from _native_spring_contact import assert_assembly_spring_contacts

        native_contact_check = assert_assembly_spring_contacts

    artefacts = await refresh_assembly(
        adapter,
        asm_name,
        allowed_pairs=_allowed_pairs(asm_name),
        native_contact_check=native_contact_check,
    )
    if asm_name == "ha-harmonic-analyzer":
        # The top assembly's eight-views gallery + parts-only BOM are not part
        # of the generic refresh tail; regenerate them on the still-open doc so
        # a subassembly change does not leave them stale (codex review #6).
        from build_ha_harmonic_analyzer_assembly import export_gallery_and_bom

        artefacts.update(await export_gallery_and_bom(adapter))
    return artefacts


def main() -> int:
    tiers = {RefreshTier.PARTS.value: _refresh_parts}
    if len(sys.argv) != 3 or sys.argv[2] not in tiers:
        print(USAGE, file=sys.stderr)
        return 2
    asm_name = sys.argv[1].removesuffix(".SLDASM").replace("_", "-")
    refresh = tiers[sys.argv[2]]

    async def build(adapter):
        return await refresh(adapter, asm_name)

    return run_build(build)


if __name__ == "__main__":
    sys.exit(main())
