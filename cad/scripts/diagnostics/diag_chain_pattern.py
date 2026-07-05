r"""Diagnostic: build ONLY the roller chain in a fresh assembly and render it.

Fast iteration harness for the roller chain -- reuses
build_paper_drive_assembly._insert_roller_chain (explicit placement of the 64
alternating inner/outer links along the _chain.py loop + gates) without the
rest of the paper-drive assembly. Renders a few views to cad/out/png/diag-chain/.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_chain_pattern.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _common import OUT_PNG, check, run_build  # noqa: E402
from build_paper_drive_assembly import _insert_roller_chain  # noqa: E402


async def build(adapter) -> dict[str, str]:
    check("create_assembly", await adapter.create_assembly())
    await _insert_roller_chain(adapter)

    png_dir = OUT_PNG / "diag-chain"
    png_dir.mkdir(parents=True, exist_ok=True)
    artefacts: dict[str, str] = {}
    for view in ("front", "back", "isometric"):
        img = (png_dir / f"diag-chain_{view}.png").resolve()
        check(
            f"export_image {view}",
            await adapter.export_image(
                {
                    "file_path": str(img),
                    "format_type": "png",
                    "width": 1800,
                    "height": 1200,
                    "view_orientation": view,
                }
            ),
        )
        artefacts[view] = str(img)
    Path(png_dir).mkdir(exist_ok=True)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
