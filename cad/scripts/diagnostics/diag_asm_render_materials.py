r"""Diagnostic: assembly-level render materials (component appearance
overrides) in frame.SLDASM / output.SLDASM / harmonic-analyzer.SLDASM.

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_asm_render_materials.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import check, run_build  # noqa: E402
from render_compare import _flag, _read_member  # noqa: E402

import _telemetry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

ASMS = ("frame", "output", "harmonic-analyzer")


async def build(adapter) -> dict[str, str]:
    for asm in ASMS:
        path = ROOT / "out" / "sldasm" / f"{asm}.SLDASM"
        if not path.exists():
            _telemetry.info(f"{asm}: no file")
            continue
        check(f"open {asm}", await adapter.open_model(str(path)))
        model = adapter.currentModel
        _flag(model, "IModelDoc2")
        ext = model.Extension
        _flag(ext, "IModelDocExtension")
        try:
            count = ext.GetRenderMaterialsCount2(2, None)
        except Exception as exc:
            _telemetry.error(f"{asm}: count failed: {exc}")
            continue
        _telemetry.info(f"{asm}: {count} render material(s)")
        if not count:
            continue
        for m in ext.GetRenderMaterials2(2, None) or []:
            _flag(m, "IRenderMaterial")
            fn = _read_member(m, "FileName")
            pc = _read_member(m, "PrimaryColor")
            rgb = (pc & 0xFF, (pc >> 8) & 0xFF, (pc >> 16) & 0xFF) if isinstance(pc, int) else None
            ents = []
            try:
                n = m.GetEntitiesCount()
                if n:
                    for e in m.GetEntities() or []:
                        name = None
                        for iface in ("IComponent2", "IFace2", "IBody2", "IFeature"):
                            try:
                                _flag(e, iface)
                                name = _read_member(e, "Name2") or _read_member(e, "Name")
                                if name:
                                    name = f"{iface}:{name}"
                                    break
                            except Exception:
                                continue
                        ents.append(name or type(e).__name__)
            except Exception as exc:
                ents = [f"entities failed: {exc}"]
            _telemetry.info(f"file={Path(fn).name if fn else fn} rgb={rgb} entities={ents}")
    return {"diag": "done"}


if __name__ == "__main__":
    sys.exit(run_build(build))
