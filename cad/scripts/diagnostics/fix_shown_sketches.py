r"""One-off: blank/hide any SHOWN unabsorbed feature in the listed parts.

Shown (Visible == 2) sketches, helix curves and ref planes render in
every assembly instance — caught twice in the ch30 renders as floating
tick rows above the top frame (M6.8 round 1: 20 helix seed circles + 20
orphan pin-hole circles; round 2: amplitude-bar orphan pin sketch back
after the mirror rebuild, plus never-hidden Helix/Spiral curves and
profile planes in the three spring parts and the gooseneck). Sketches
are blanked via BlankSketch, helix curves and planes via BlankRefGeom;
each hide is verified by re-reading Visible.

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\fix_shown_sketches.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import check, run_build  # noqa: E402
from render_compare import _flag, _read_member  # noqa: E402

import _telemetry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PARTS = [
    "amplitude-bar",
    "channel-spring-installed",
    "channel-spring",
    "counter-spring",
    "gooseneck",
]
# Solid features legitimately report Visible == 2 (their bodies are shown);
# only unabsorbed reference/sketch features leak into assembly renders.
HIDE_TYPES = {
    "ProfileFeature": "SKETCH",
    "Helix": "REFERENCECURVES",
    "RefPlane": "PLANE",
}


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    results: dict[str, str] = {}
    for stem in PARTS:
        path = ROOT / "out" / "sldprt" / f"{stem}.SLDPRT"
        check(f"open {stem}", await adapter.open_model(str(path)))
        model = adapter.currentModel
        _flag(model, "IModelDoc2")

        hidden = []
        feat = _read_member(model, "FirstFeature")
        for _ in range(5000):
            if not feat:
                break
            _flag(feat, "IFeature")
            tn = str(_read_member(feat, "GetTypeName2"))
            name = str(_read_member(feat, "Name"))
            sel_type = HIDE_TYPES.get(tn)
            if sel_type and name != "Origin" and _read_member(feat, "Visible") == 2:
                model.ClearSelection2(True)
                ok = model.Extension.SelectByID2(
                    name, sel_type, 0, 0, 0, False, 0, null_callout(), 0
                )
                if not ok:
                    raise RuntimeError(f"{stem}: cannot select {name} as {sel_type}")
                if tn == "ProfileFeature":
                    model.BlankSketch()
                else:
                    model.BlankRefGeom()
                model.ClearSelection2(True)
                vis = _read_member(feat, "Visible")
                if vis == 2:
                    raise RuntimeError(f"{stem}: {name} [{tn}] still Visible=2")
                hidden.append(f"{name} [{tn}]")
            feat = _read_member(feat, "GetNextFeature")

        if hidden:
            check(f"save {stem}", await adapter.save_file())
        _telemetry.info(f"{stem}: hid {hidden or 'nothing'}")
        results[stem] = ",".join(hidden) or "none"
    return results


if __name__ == "__main__":
    sys.exit(run_build(build))
