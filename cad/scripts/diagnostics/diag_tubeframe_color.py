r"""Diagnostic: where does tube-frame's black come from?

Opens tube-frame.SLDPRT, reports doc-level MPV + body/face appearance
counts, exports an isolated image; then opens frame.SLDASM and reports the
tube-frame components' material property overrides.

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_tubeframe_color.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import check, run_build  # noqa: E402
from render_compare import _flag, _read_member  # noqa: E402

import _telemetry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


async def build(adapter) -> dict[str, str]:
    check("open part", await adapter.open_model(str(ROOT / "out" / "sldprt" / "tube-frame.SLDPRT")))
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    mpv = model.MaterialPropertyValues
    _telemetry.info(f"part doc MPV: {mpv[:3] if mpv else None}")

    bodies = None
    try:
        _flag(model, "IPartDoc")
        bodies = model.GetBodies2(0, True)  # solid bodies
    except Exception as exc:
        _telemetry.error(f"GetBodies2 failed: {exc}")
    for b in bodies or []:
        _flag(b, "IBody2")
        bmpv = _read_member(b, "MaterialPropertyValues2")
        _telemetry.info(f"body MPV: {bmpv[:3] if bmpv else None}")
        faces = b.GetFaces() or []
        n_face_appearance = 0
        for f in faces:
            _flag(f, "IFace2")
            fmpv = _read_member(f, "MaterialPropertyValues")
            if fmpv:
                n_face_appearance += 1
        _telemetry.info(f"faces: {len(faces)}, with face MPV: {n_face_appearance}")

    check("open frame asm", await adapter.open_model(str(ROOT / "out" / "sldasm" / "frame.SLDASM")))
    asm = adapter.currentModel
    _flag(asm, "IModelDoc2")
    _flag(asm, "IAssemblyDoc")
    for comp in asm.GetComponents(True) or []:
        _flag(comp, "IComponent2")
        name = comp.Name2
        if not name.startswith("tube-frame"):
            continue
        cmpv = _read_member(comp, "MaterialPropertyValues")
        _telemetry.info(f"frame comp {name} MPV: {cmpv[:3] if cmpv else None}")

    return {"diag": "done"}


if __name__ == "__main__":
    sys.exit(run_build(build))
