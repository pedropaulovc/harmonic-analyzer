r"""Incremental assembly refresh: update a saved assembly in place (no re-insert/re-mate).

Two tiers (``_refresh_tier.RefreshTier``), chosen by ``dodo.build_or_refresh``
from the recorded per-input digests:

* ``parts`` -- a ``.SLDASM`` is a thin reference layer over its part files, so
  when only a referenced ``.SLDPRT``/sub-``.SLDASM`` changed, reopening the
  assembly and force-rebuilding every configuration loads the new geometry
  WITHOUT the ~500 s from-scratch ``create_assembly`` insert/mate loop. The
  heavy lifting (per-config rebuild, health/DOF/interference gates, in-place
  ``Save3``, PNG export) lives in :func:`_assembly.refresh_assembly`.
* ``explode`` -- only the assembly's explode closure changed: delete the saved
  named explodes and re-author them with the builder's own function
  (:func:`_explode_refresh.refresh_explode`).

Fail loud: any dangling mate, free DOF, interference or geometry drift halts the
refresh with a non-zero exit and leaves the ``.SLDASM`` unsaved. A failed
``parts`` refresh needs the full escape (delete the target + ``doit
assembly:<stem>``); ``dodo.build_or_refresh`` follows a failed ``explode``
refresh with a FULL build in the same task.

Run (SolidWorks already open)::

    uv run python cad\scripts\refresh_assembly.py <stem> <parts|explode>

where ``<stem>`` is an assembly stem (``pd_paper_drive``, ``dt_drive_train``,
``ha_harmonic_analyzer``, ...); ``_`` and ``-`` are interchangeable.
"""

from __future__ import annotations

import importlib
import sys

from _session import run_build
from _assembly import refresh_assembly
from _refresh_tier import RefreshTier, explode_plan

USAGE = (
    "usage: refresh_assembly.py <assembly-stem> <parts|explode>  "
    "(e.g. pd-paper-drive explode)"
)


async def _refresh_parts(adapter, asm_name: str) -> dict[str, str]:
    # The press-fit allowance lookup lives HERE (the entrypoint dodo invokes,
    # outside every assembly's recipe closure) so _interference_contracts and
    # its pinion geometry imports invalidate only the builders that import
    # them directly (codex #359).
    from _interference_contracts import allowed_interference_pairs

    native_contact_check = None
    if asm_name in ("ch-channel", "sm-summing"):
        from _native_spring_contact import assert_assembly_spring_contacts

        native_contact_check = assert_assembly_spring_contacts

    artefacts = await refresh_assembly(
        adapter,
        asm_name,
        allowed_pairs=allowed_interference_pairs(asm_name),
        native_contact_check=native_contact_check,
    )
    if asm_name == "ha-harmonic-analyzer":
        # The top assembly's eight-views gallery + parts-only BOM are not part
        # of the generic refresh tail; regenerate them on the still-open doc so
        # a subassembly change does not leave them stale (codex review #6).
        from build_ha_harmonic_analyzer_assembly import export_gallery_and_bom

        artefacts.update(await export_gallery_and_bom(adapter))
    return artefacts


async def _refresh_explode(adapter, asm_name: str) -> dict[str, str]:
    from _explode_refresh import refresh_explode

    # The same static analysis that admitted the tier names the function, so
    # the refresh authors through exactly what the FULL build calls.
    plan = explode_plan(asm_name.replace("-", "_"))
    if not plan.closure:
        raise RuntimeError(f"{asm_name}: no explode refresh: {plan.decline}")
    create = getattr(importlib.import_module(plan.module), plan.function)
    return await refresh_explode(
        adapter, asm_name, lambda configuration: create(adapter, configuration)
    )


def main() -> int:
    tiers = {
        RefreshTier.PARTS.value: _refresh_parts,
        RefreshTier.EXPLODE.value: _refresh_explode,
    }
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
