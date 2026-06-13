r"""One-off: render the drive-chain bead loop in ISOLATION.

Opens output.SLDASM, hides every component except the 63 chain-bead
pattern instances, zooms to the chain, and exports PNGs -- a quick visual
of the bead chain on its own (the chain only exists as an assembly chain
component pattern, so it has no standalone part to render). Read-only on
the model (hide state is not saved).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_render_chain.py
"""

from __future__ import annotations

import sys

from _common import OUT_PNG, OUT_SLDASM, _flag, check, log, run_build


async def build(adapter) -> dict[str, str]:
    asm_path = (OUT_SLDASM / "output.SLDASM").resolve()
    check(f"open {asm_path.name}", await adapter.open_model(str(asm_path)))
    model = adapter.currentModel
    _flag(model, "IModelDoc2")

    components = [c for c in (model.GetComponents(True) or [])]
    for c in components:
        _flag(c, "IComponent2")
    hidden = kept = 0
    for c in components:
        if c.Name2.startswith("chain-bead"):
            kept += 1
            continue
        c.Visible = False
        hidden += 1
    model.EditRebuild3()
    log(f"kept {kept} chain beads visible, hid {hidden} other components")

    adapter._zoom_to_fit(model)
    out_dir = OUT_PNG / "chain-loop"
    out_dir.mkdir(parents=True, exist_ok=True)
    artefacts = {}
    for view in ("front", "isometric", "trimetric"):
        img = (out_dir / f"chain-loop_{view}.png").resolve()
        check(
            f"export_image {view}",
            await adapter.export_image(
                {
                    "file_path": str(img),
                    "format_type": "png",
                    "width": 1600,
                    "height": 1000,
                    "view_orientation": view,
                }
            ),
        )
        artefacts[view] = str(img)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
