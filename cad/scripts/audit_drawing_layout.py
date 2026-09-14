"""Audit one saved manufacturing drawing against its live sheet layout."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import _telemetry
from _common import check, run_build
from _drawing_common import _visible_document_paths, check_drawing_layout
from _drawing_registry import DrawingLayout


async def audit(adapter: Any, drawing_path: Path, layout: DrawingLayout) -> dict[str, str]:
    drawing_path = drawing_path.resolve()
    if not drawing_path.is_file():
        raise FileNotFoundError(f"drawing is missing: {drawing_path}")

    check("open drawing for layout audit", await adapter.open_model(str(drawing_path)))
    drawing = adapter.currentModel
    title = drawing.GetTitle()
    if not title:
        adapter.swApp.CloseAllDocuments(True)
        raise RuntimeError(
            "opened drawing has an empty title; closed all documents instead of "
            "calling CloseDoc(''), which silently no-ops"
        )
    try:
        check_drawing_layout(adapter, layout=layout, stem=drawing_path.stem)
    finally:
        adapter.swApp.CloseDoc(title)
        still_open = [
            path
            for path in _visible_document_paths(adapter)
            if Path(path).resolve() == drawing_path
        ]
        if still_open:
            raise RuntimeError(f"drawing {title!r} did not close after layout audit")
    return {"drawing": str(drawing_path)}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("layout", type=DrawingLayout, choices=tuple(DrawingLayout))
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    _telemetry.set_service("drawing-audit")
    sys.exit(run_build(lambda adapter: audit(adapter, args.drawing, args.layout)))
