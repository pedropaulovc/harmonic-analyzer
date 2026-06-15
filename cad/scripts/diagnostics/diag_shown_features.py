r"""Diagnostic: list every feature with Visible == 2 (shown) in the
round-2 rebuilt parts, with type names -- shown sketches/curves render in
every assembly instance (see fix_shown_sketches.py for the M6.8 round-1
occurrence: floating tick rows above the top frame).

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_shown_features.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import check, run_build  # noqa: E402
from render_compare import _flag, _read_member  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PARTS = [
    "amplitude-bar",
    "channel-spring-installed",
    "channel-spring",
    "counter-spring",
    "top-lever",
]


async def build(adapter) -> dict[str, str]:
    results: dict[str, str] = {}
    for stem in PARTS:
        path = ROOT / "out" / "sldprt" / f"{stem}.SLDPRT"
        check(f"open {stem}", await adapter.open_model(str(path)))
        model = adapter.currentModel
        _flag(model, "IModelDoc2")

        shown = []
        feat = _read_member(model, "FirstFeature")
        for _ in range(5000):
            if not feat:
                break
            _flag(feat, "IFeature")
            tn = str(_read_member(feat, "GetTypeName2"))
            name = str(_read_member(feat, "Name"))
            vis = _read_member(feat, "Visible")
            print(f"  {stem}: {name} [{tn}] Visible={vis}")
            if vis == 2:
                shown.append(f"{name} [{tn}]")
            sub = _read_member(feat, "GetFirstSubFeature")
            for _ in range(200):
                if not sub:
                    break
                _flag(sub, "IFeature")
                stn = str(_read_member(sub, "GetTypeName2"))
                sname = str(_read_member(sub, "Name"))
                svis = _read_member(sub, "Visible")
                print(f"  {stem}:   sub {sname} [{stn}] Visible={svis}")
                if svis == 2:
                    shown.append(f"sub {sname} [{stn}]")
                sub = _read_member(sub, "GetNextSubFeature")
            feat = _read_member(feat, "GetNextFeature")

        print(f"  {stem}: SHOWN -> {shown or 'nothing'}")
        results[stem] = ",".join(shown) or "none"
    return results


if __name__ == "__main__":
    sys.exit(run_build(build))
