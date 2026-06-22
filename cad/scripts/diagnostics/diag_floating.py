r"""Diagnostic: find what renders above the top frame in harmonic-analyzer.SLDASM.

Scans ALL components (any suppression/visibility state) and reports any whose
world box reaches y > 1150 mm, plus visible top-level assembly sketches.
Read-only.

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_floating.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import check, run_build  # noqa: E402
from render_compare import _flag  # noqa: E402

import _telemetry  # noqa: E402

ASM = Path(__file__).resolve().parents[1] / "out" / "sldasm" / "harmonic-analyzer.SLDASM"


async def build(adapter) -> dict[str, str]:
    check("open", await adapter.open_model(str(ASM)))
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    _flag(model, "IAssemblyDoc")

    comps = model.GetComponents(False) or []
    _telemetry.info(f"--- {len(comps)} components; those with y_max > 1150 mm ---")
    for comp in comps:
        _flag(comp, "IComponent2")
        try:
            box = comp.GetBox(False, False)
        except Exception:
            box = None
        if not box:
            continue
        y_max = box[4] * 1000.0
        if y_max <= 1150.0:
            continue
        x0, y0, z0, x1, y1, z1 = [v * 1000.0 for v in box]
        _telemetry.info(
            f"{comp.Name2}: x[{x0:.0f},{x1:.0f}] y[{y0:.0f},{y1:.0f}] "
            f"z[{z0:.0f},{z1:.0f}] supp={comp.GetSuppression2} vis={comp.Visible}"
        )

    _telemetry.info("--- top-level assembly sketch features ---")
    feat = model.FirstFeature
    while feat is not None:
        tn = feat.GetTypeName2
        if "Profile" in str(tn) or "Sketch" in str(tn):
            _telemetry.info(f"sketch: {feat.Name} type={tn}")
        feat = feat.GetNextFeature

    return {"diag": "done"}


if __name__ == "__main__":
    sys.exit(run_build(build))
