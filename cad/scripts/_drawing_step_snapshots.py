"""DIAGNOSTIC ONLY (branch pedro/drawing-step-snapshots-diag, never merged).

Snapshots a drawing between the build's placement steps so the effect of each
step can be compared: after every view insert (does SolidWorks auto-insert
anything on view creation?), after every model-item import (where SolidWorks
auto-places the imported dimensions), after every curation pass (does the
second reposition pass move anything?), after centre marks (#913), and before
finalize. Each snapshot is one JSON census of the current sheet (views,
annotations with type/name/dimension name/position) and, for the first
``_PDF_LIMIT`` steps, a PDF of the whole drawing.

Written under ``cad/out/reports/failures/step-snapshots/<script>/`` because the
farm worker publishes every fresh file there beside ``task.log``.
"""

from __future__ import annotations

import functools
import inspect
import itertools
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable

import _telemetry
from _common import CAD_ROOT, _early_bound
from solidworks_mcp.adapters.solidworks import drawing as _sw_drawing

_PDF_LIMIT = 100
_JSON_LIMIT = 150
_counter = itertools.count(1)
_adapter: list[Any] = []
_ROOT = (
    CAD_ROOT
    / "out"
    / "reports"
    / "failures"
    / "step-snapshots"
    / Path(sys.argv[0] if sys.argv and sys.argv[0] else "unknown").stem
)


def _safe(fn: Callable[[], Any], default: Any = None) -> Any:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - diagnostic census must not fail a build
        return default if default is not None else f"<error {type(exc).__name__}: {exc}>"


def _position(annotation: Any) -> list[float] | None:
    raw = _safe(lambda: annotation.GetPosition())
    if raw is None or isinstance(raw, str):
        return None
    return [round(float(value), 6) for value in tuple(raw)[:2]]


def _census(adapter: Any) -> dict[str, Any]:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _safe(lambda: _early_bound(ddoc.GetCurrentSheet(), "ISheet"))
    views: list[dict[str, Any]] = []
    for view in _sw_drawing.iter_views(adapter):
        name = _sw_drawing.view_name(adapter, view)
        entry: dict[str, Any] = {
            "name": name,
            "outline": _safe(lambda v=view: [round(float(x), 6) for x in v.GetOutline()]),
            "position": _safe(lambda v=view: [round(float(x), 6) for x in v.Position]),
            "annotations": [],
        }
        raw = _safe(lambda v=view: v.GetAnnotations())
        for annotation in raw if isinstance(raw, (tuple, list)) else ():
            annotation = _early_bound(annotation, "IAnnotation")
            kind = _safe(lambda a=annotation: int(a.GetType()))
            item: dict[str, Any] = {
                "type": kind,
                "name": _safe(lambda a=annotation: str(a.GetName())),
                "position": _position(annotation),
                "visible": _safe(lambda a=annotation: int(a.Visible)),
            }
            if kind == 4:  # swDisplayDimension
                item["dimension"] = _safe(
                    lambda a=annotation: _sw_drawing.dimension_name(adapter, a)
                )
            entry["annotations"].append(item)
        views.append(entry)
    return {
        "sheet": _safe(lambda: str(sheet.GetName())) if sheet is not None else None,
        "views": views,
    }


def snapshot(adapter: Any, step: str) -> None:
    index = next(_counter)
    if index > _JSON_LIMIT:
        return
    started = time.perf_counter()
    _ROOT.mkdir(parents=True, exist_ok=True)
    slug = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in step)[:80]
    base = _ROOT / f"{index:03d}-{slug}"
    record: dict[str, Any] = {"index": index, "step": step}
    record.update(_safe(lambda: _census(adapter), default={"census": "failed"}))
    census_s = time.perf_counter() - started
    if index <= _PDF_LIMIT:
        pdf = base.with_suffix(".pdf")
        _safe(lambda: adapter.currentModel.SaveAs3(str(pdf), 0, 0))
        record["pdf"] = pdf.name if pdf.is_file() else None
    record["census_s"] = round(census_s, 3)
    record["total_s"] = round(time.perf_counter() - started, 3)
    base.with_suffix(".json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    _telemetry.info(f"step snapshot {index:03d} {step}: {record['total_s']} s")


def _label(fn_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    bits = [fn_name]
    for key in ("view_label", "label"):
        if isinstance(kwargs.get(key), str):
            bits.append(kwargs[key])
    if fn_name == "place_view" and len(args) >= 3:
        bits.append(str(args[2]))
    if fn_name == "curate_dimensions":
        bits.append(
            "delete" if kwargs.get("delete") else "reposition"
        )
    return " ".join(bits)


def _wrap_after(module: Any, name: str) -> None:
    original = getattr(module, name)
    if getattr(original, "_step_snapshot", False):
        return

    @functools.wraps(original)
    def wrapper(adapter: Any, *args: Any, **kwargs: Any) -> Any:
        result = original(adapter, *args, **kwargs)
        snapshot(adapter, _label(name, args, kwargs))
        return result

    wrapper._step_snapshot = True  # type: ignore[attr-defined]
    setattr(module, name, wrapper)


def _wrap_finalize(module: Any) -> None:
    original = module.finalize_drawing
    assert inspect.iscoroutinefunction(original)

    @functools.wraps(original)
    async def wrapper(adapter: Any, *args: Any, **kwargs: Any) -> Any:
        snapshot(adapter, "before finalize")
        result = await original(adapter, *args, **kwargs)
        pdf = result.get("pdf") if isinstance(result, dict) else None
        if pdf:
            _safe(lambda: shutil.copyfile(pdf, _ROOT / "999-final.pdf"))
        return result

    module.finalize_drawing = wrapper


def install(drawing_common: Any) -> None:
    """Wrap the placement helpers in ``_drawing_common`` and the adapter module.

    Draw recipes import these names from ``_drawing_common`` (and
    ``place_view``/``auto_center_marks`` from the adapter module) AFTER
    ``_drawing_common`` finishes importing, so they bind the wrappers.
    """
    for name in ("place_view", "auto_center_marks"):
        _wrap_after(_sw_drawing, name)
    for name in (
        "place_view",
        "curate_dimensions",
        "insert_feature_dimensions",
        "insert_marked_dimensions",
        "delete_unnamed_imports",
        "create_section_view",
        "project_part_pmi",
        "set_dimension_callouts",
        "offset_dimension_text",
    ):
        if name == "place_view":
            drawing_common.place_view = _sw_drawing.place_view
            continue
        _wrap_after(drawing_common, name)
    _wrap_finalize(drawing_common)
