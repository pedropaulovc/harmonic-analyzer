r"""Diagnostic: enumerate part-level render materials (appearances).

Doc MPV is the legacy colour system; shaded renders prefer attached
render materials (RealView appearances), which apply_material may bring
in with the database material. Lists the IModelDocExtension members that
touch them, then dumps each render material's file/colour for the
suspect parts.

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_render_materials.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import check, run_build  # noqa: E402
from render_compare import _flag, _read_member  # noqa: E402

import _telemetry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

PARTS = ("tube-frame", "platen-paper", "crank-handle", "amplitude-bar", "harmonic-base")


async def build(adapter) -> dict[str, str]:
    first = True
    for part in PARTS:
        check(f"open {part}", await adapter.open_model(
            str(ROOT / "out" / "sldprt" / f"{part}.SLDPRT")))
        model = adapter.currentModel
        _flag(model, "IModelDoc2")
        ext = model.Extension
        _flag(ext, "IModelDocExtension")
        if first:
            names = [n for n in dir(ext)
                     if "Render" in n or "Appearance" in n or "DisplayState" in n]
            _telemetry.info(f"ext members: {names}")
            first = False
        try:
            count = ext.GetRenderMaterialsCount2(2, None)  # swAllDisplayState
        except Exception as exc:
            _telemetry.error(f"{part}: GetRenderMaterialsCount2 failed: {exc}")
            continue
        _telemetry.info(f"{part}: {count} render material(s)")
        if not count:
            continue
        mats = ext.GetRenderMaterials2(2, None)
        for m in mats or []:
            _flag(m, "IRenderMaterial")
            fn = _read_member(m, "FileName")
            pc = _read_member(m, "PrimaryColor")
            n_ent = None
            try:
                n_ent = m.GetEntitiesCount()
            except Exception:
                pass
            rgb = None
            if isinstance(pc, int):
                rgb = (pc & 0xFF, (pc >> 8) & 0xFF, (pc >> 16) & 0xFF)
            _telemetry.info(f"file={fn}")
            _telemetry.info(f"primary={pc} rgb={rgb} entities={n_ent}")
    return {"diag": "done"}


if __name__ == "__main__":
    sys.exit(run_build(build))
