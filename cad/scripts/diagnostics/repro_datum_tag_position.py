r"""Minimal live repro for session-dependent datum-tag position readback.

The repro intentionally creates one drawing view and one attached datum tag. It
does not import dimensions, center marks, notes, balloons, tables, or any of the
project drawing helpers under investigation.

Run with SOLIDWORKS already open::

    uv run python cad\scripts\diagnostics\repro_datum_tag_position.py

It writes the raw request/readback data plus a drawing and render under
``cad/out/reports/datum-tag-position-repro``. Run it on either side of a
SOLIDWORKS restart to compare the same COM call shape across sessions.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import CAD_ROOT, _early_bound, run_build  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import null_callout  # noqa: E402
from solidworks_mcp.adapters.solidworks.drawing import (  # noqa: E402
    new_drawing,
    place_view,
    save_drawing,
    view_name,
)


SOURCE = CAD_ROOT / "out" / "sldprt" / "pinion-cam.SLDPRT"
TEMPLATE = CAD_ROOT / "templates" / "harmonic-analyzer-part.DRWDOT"
OUT = CAD_ROOT / "out" / "reports" / "datum-tag-position-repro"

# Exact values from the production failure, kept literal so this file has no
# dependency on draw_pinion_cam.py or pinion_cam_spec.py.
VIEW_CENTER = (0.105, 0.150)
EDGE_PICK = (0.105, 0.144195)
REQUESTED = (0.085, 0.105)


def _primitives(tag: Any) -> dict[str, list[list[float]]]:
    """Return the raw IDatumTag line and triangle arrays."""
    lines = [
        [float(value) for value in tag.GetLineAtIndex(index)]
        for index in range(int(tag.GetLineCount()))
    ]
    triangles = [
        [float(value) for value in tag.GetTriangleAtIndex(index)]
        for index in range(int(tag.GetTriangleCount()))
    ]
    return {"lines": lines, "triangles": triangles}


async def build(adapter: Any) -> dict[str, str]:
    for path in (SOURCE, TEMPLATE):
        if not path.is_file():
            raise FileNotFoundError(path)

    model = new_drawing(
        adapter,
        template=str(TEMPLATE),
        width=0.4318,
        height=0.2794,
    )
    view = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *VIEW_CENTER,
        scale=(3, 1),
    )
    drawing = _early_bound(model, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    sheet.SheetFormatVisible = False
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the sole drawing view")
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "",
        "EDGE",
        EDGE_PICK[0],
        EDGE_PICK[1],
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError("failed to select the bore rim")

    raw_tag = model.InsertDatumTag2()
    if raw_tag is None:
        raise RuntimeError("InsertDatumTag2 returned null")
    tag = _early_bound(
        raw_tag,
        "IDatumTag",
        "SetLabel",
        "GetAnnotation",
        "GetLineCount",
        "GetLineAtIndex",
        "GetTriangleCount",
        "GetTriangleAtIndex",
    )
    if not tag.SetLabel("B"):
        raise RuntimeError("SetLabel returned false")
    annotation = _early_bound(
        tag.GetAnnotation(), "IAnnotation", "SetPosition2", "GetPosition"
    )
    before = tuple(float(value) for value in annotation.GetPosition()[:2])
    if not annotation.SetPosition2(REQUESTED[0], REQUESTED[1], 0.0):
        raise RuntimeError("SetPosition2 returned false")
    immediate = tuple(float(value) for value in annotation.GetPosition()[:2])
    model.EditRebuild3()
    rebuilt = tuple(float(value) for value in annotation.GetPosition()[:2])

    report = {
        "source": str(SOURCE),
        "view_center_m": VIEW_CENTER,
        "edge_pick_m": EDGE_PICK,
        "requested_m": REQUESTED,
        "before_set_m": before,
        "immediate_readback_m": immediate,
        "rebuilt_readback_m": rebuilt,
        "immediate_delta_mm": math.dist(REQUESTED, immediate) * 1000.0,
        "rebuilt_delta_mm": math.dist(REQUESTED, rebuilt) * 1000.0,
        "primitives": _primitives(tag),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    model.ViewZoomtofit2()
    artifacts = save_drawing(
        adapter,
        str(OUT / "repro.SLDDRW"),
        pdf_path=str(OUT / "repro.pdf"),
        png_path=str(OUT / "repro.png"),
    )
    print(json.dumps(report, sort_keys=True))
    return {**artifacts, "report": str(report_path)}


if __name__ == "__main__":
    sys.exit(run_build(build))
