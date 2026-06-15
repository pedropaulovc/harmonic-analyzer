r"""Diagnostic: list sketch features in channel.SLDASM (assembly level) and in
each unique referenced part, with visibility. Read-only.

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_sketches.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import check, run_build  # noqa: E402
from render_compare import _flag  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "out" / "sldasm" / "channel.SLDASM"


def _get(obj, name):
    v = getattr(obj, name)
    return v() if callable(v) else v


def list_sketches(model, label: str) -> None:
    print(f"--- features of {label} ---")
    feat = _get(model, "FirstFeature")
    while feat is not None:
        _flag(feat, "IFeature")
        tn = str(_get(feat, "GetTypeName2"))
        if "Profile" in tn or "Sketch" in tn:
            vis = None
            try:
                vis = _get(feat, "Visible")
            except Exception:
                pass
            print(f"  {_get(feat, 'Name')}  type={tn}  visible={vis}")
        feat = _get(feat, "GetNextFeature")


async def build(adapter) -> dict[str, str]:
    check("open", await adapter.open_model(str(ASM)))
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    _flag(model, "IAssemblyDoc")
    list_sketches(model, "channel.SLDASM")

    comps = model.GetComponents(True) or []
    seen = set()
    for comp in comps:
        _flag(comp, "IComponent2")
        doc = _get(comp, "GetModelDoc2")
        if doc is None:
            continue
        _flag(doc, "IModelDoc2")
        title = _get(doc, "GetTitle")
        if title in seen:
            continue
        seen.add(title)
        list_sketches(doc, title)

    return {"diag": "done"}


if __name__ == "__main__":
    sys.exit(run_build(build))
