"""Verify that every saved cone-gear configuration survives assembly reopen.

This is the positive-control repro for the configured-part persistence failure
found while rebuilding ``drive-train``. It inserts all 20 configurations from
the pipeline-owned part, saves a temporary assembly, closes every document,
reopens the assembly, and requires a clean deep rebuild.

Run with SolidWorks open::

    uv run cad/scripts/diagnostics/diag_direct_config_insert.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _assembly import _prepare_component_configuration, whats_wrong  # noqa: E402
from _assembly_postbuild import discard_open_documents  # noqa: E402
from _common import OUT_SLDPRT, _early_bound, check, run_build  # noqa: E402

CONFIGURATIONS = tuple(f"T{teeth:03d}" for teeth in range(120, 0, -6))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import InsertComponentParameters

    part_path = (OUT_SLDPRT / "cone-gear.SLDPRT").resolve()
    saved_path = (
        Path(__file__).resolve().parents[2]
        / "out"
        / "diagnostics"
        / "direct-config-persistence.SLDASM"
    )
    saved_path.parent.mkdir(parents=True, exist_ok=True)
    saved_path.unlink(missing_ok=True)

    try:
        check("create diagnostic assembly", await adapter.create_assembly())
        components = []
        for index, configuration in enumerate(CONFIGURATIONS):
            _prepare_component_configuration(adapter, str(part_path), configuration)
            data = check(
                f"insert cone {configuration}",
                await adapter.insert_component(
                    InsertComponentParameters(
                        file_path=str(part_path),
                        position=[index * 100.0, 0.0, 0.0],
                        rotation=[0.0, 0.0, 0.0],
                        configuration=configuration,
                    )
                ),
            )
            assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
            component = _early_bound(
                assembly.GetComponentByName(data["name"]), "IComponent2"
            )
            components.append(component)

        rebuilt = adapter._attempt(
            lambda: adapter.currentModel.ForceRebuild3(False), default=None
        )
        actual = tuple(
            str(component.ReferencedConfiguration) for component in components
        )
        faults = whats_wrong(adapter, adapter.currentModel)
        if not rebuilt or actual != CONFIGURATIONS or faults:
            raise RuntimeError(
                "configured insert failed before save: "
                f"rebuilt={rebuilt!r}, actual={actual!r}, faults={faults}"
            )

        adapter._attempt(
            lambda: adapter.currentModel.SaveAs3(str(saved_path), 0, 1 | 2 | 8),
            default=None,
        )
        if not saved_path.exists():
            raise RuntimeError(f"diagnostic assembly was not saved: {saved_path}")

        adapter.swApp.CloseAllDocuments(True)
        adapter.currentModel = None
        check("reopen diagnostic assembly", await adapter.open_model(str(saved_path)))
        reopened = adapter._attempt(
            lambda: adapter.currentModel.ForceRebuild3(True), default=None
        )
        reopened_faults = whats_wrong(adapter, adapter.currentModel)
        if not reopened or reopened_faults:
            raise RuntimeError(
                "configured insert failed after reopen: "
                f"rebuilt={reopened!r}, faults={reopened_faults}"
            )
        return {}
    finally:
        discard_open_documents(adapter)
        saved_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(run_build(build))
