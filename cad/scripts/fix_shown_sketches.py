r"""One-off: blank any SHOWN sketch in the four affected parts, in place.

Shown (unabsorbed) sketches render in every assembly instance — caught as
floating tick rows above the top frame in the ch30 renders (20 helix seed
circles + 20 orphan pin-hole circles). Source scripts now blank them at
build time; this patches the saved SLDPRTs without a full rebuild.

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\fix_shown_sketches.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import check, run_build  # noqa: E402
from render_compare import _flag, _read_member  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PARTS = [
    "channel-spring-installed",
    "channel-spring",
    "amplitude-bar",
    "counter-spring",
]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    results: dict[str, str] = {}
    for stem in PARTS:
        path = ROOT / "out" / "sldprt" / f"{stem}.SLDPRT"
        check(f"open {stem}", await adapter.open_model(str(path)))
        model = adapter.currentModel
        _flag(model, "IModelDoc2")

        blanked = []
        feat = _read_member(model, "FirstFeature")
        for _ in range(5000):
            if not feat:
                break
            _flag(feat, "IFeature")
            tn = str(_read_member(feat, "GetTypeName2"))
            if tn == "ProfileFeature":
                vis = _read_member(feat, "Visible")
                name = str(_read_member(feat, "Name"))
                if vis == 2:
                    model.ClearSelection2(True)
                    ok = model.Extension.SelectByID2(
                        name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
                    )
                    if not ok:
                        raise RuntimeError(f"{stem}: cannot select {name}")
                    model.BlankSketch()
                    model.ClearSelection2(True)
                    blanked.append(name)
            feat = _read_member(feat, "GetNextFeature")

        if blanked:
            check(f"save {stem}", await adapter.save_file())
        print(f"  {stem}: blanked {blanked or 'nothing'}")
        results[stem] = ",".join(blanked) or "none"
    return results


if __name__ == "__main__":
    sys.exit(run_build(build))
