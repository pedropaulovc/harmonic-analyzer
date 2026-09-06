"""Copy-only RIGHT native GTol-column control, without a custom leader router.

Run through uv with DRAWING (optionally --view NAME). The largest unique native
GTol bank is used unless explicitly named. Translate its complete measured body
bank to the first clear RIGHT outboard position, keeping native Y/order/leaders.
Compare actual native leader segments against conservative native text cells;
these are potential text-cell crossings, not exact glyph-ink intersections.
Record both PNGs and final saved/reopened geometry, frame and dimension witnesses.
The original drawing and referenced native parts must remain byte-unchanged.

Requires the integrated _drawing_native_gtol and diagnostics attachment helper.
No production recipe/helper is patched and nothing is published by this probe.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_annotation_bounds import Segment, annotation_box
from _drawing_common import render_pdf_png
from _drawing_view_packing import Rect
import _telemetry


def intersects_cell(segment: Segment, cell: Rect) -> bool:
    """Closed segment/rectangle clipping; include touching as a conservative hit."""
    points = (*segment.start, *segment.end)
    if not all(math.isfinite(value) for value in points):
        raise ValueError("native leader coordinates must be finite")
    lower, upper = 0.0, 1.0
    for start, finish, minimum, maximum in (
        (segment.start[0], segment.end[0], cell.xmin, cell.xmax),
        (segment.start[1], segment.end[1], cell.ymin, cell.ymax),
    ):
        delta = finish - start
        if delta == 0:
            if start < minimum or start > maximum:
                return False
            continue
        enter, leave = sorted(((minimum - start) / delta, (maximum - start) / delta))
        lower, upper = max(lower, enter), min(upper, leave)
        if lower > upper:
            return False
    return True


def _clear(first: Rect, second: Rect, gap: float) -> bool:
    return (
        first.xmax + gap <= second.xmin + 1e-9
        or second.xmax + gap <= first.xmin + 1e-9
        or first.ymax + gap <= second.ymin + 1e-9
        or second.ymax + gap <= first.ymin + 1e-9
    )


def right_translation(
    column: Rect, outline: Rect, obstacles: tuple[Rect, ...], gap_m=0.003
):
    if not math.isfinite(gap_m) or gap_m < 0:
        raise ValueError("column clearance must be finite and nonnegative")
    dx = max(0.0, outline.xmax + gap_m - column.xmin)
    for _ in range(len(obstacles) + 1):
        moved = column.translated((dx, 0.0))
        collision = next(
            (item for item in obstacles if not _clear(moved, item, gap_m)), None
        )
        if collision is None:
            return dx, 0.0
        dx = collision.xmax + gap_m - column.xmin
    raise RuntimeError("bounded right-column candidate did not clear obstacles")


def crossing_records(leader_banks, measurements):
    result = []
    for name, segments in leader_banks.items():
        for target, bounds in measurements.items():
            if target == name:
                continue  # own native leader/frame join is intentional
            for index, cell in enumerate(bounds.text_boxes):
                hits = [
                    i
                    for i, segment in enumerate(segments)
                    if intersects_cell(segment, cell)
                ]
                if hits:
                    result.append(
                        {
                            "leader_annotation": name,
                            "target_annotation": target,
                            "target_kind": bounds.kind,
                            "text_cell_index": index,
                            "text_cell": cell.bounds,
                            "segments": hits,
                            "target_text": [run.value for run in bounds.text_runs],
                        }
                    )
    return result


def _leaders(annotation):
    segments = []
    for index in range(int(annotation.GetLeaderCount())):
        raw = tuple(
            float(value) for value in annotation.GetLeaderPointsAtIndex(index) or ()
        )
        if len(raw) not in (6, 9) or not all(math.isfinite(value) for value in raw):
            raise RuntimeError(
                "native GTol leader is not a finite two/three-point chain"
            )
        points = tuple((raw[i], raw[i + 1]) for i in range(0, len(raw), 3))
        segments.extend(
            Segment(first, second) for first, second in zip(points, points[1:])
        )
    return tuple(segments)


def _native_entities(adapter, view):
    result = {}
    for raw in view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        kind = int(annotation.GetType())
        if kind not in {2, 4, 5, 7}:
            continue
        entities = tuple(annotation.GetAttachedEntities3() or ())
        kinds = tuple(int(item) for item in annotation.GetAttachedEntityTypes() or ())
        if len(entities) != len(kinds) or len(entities) != int(
            annotation.GetAttachedEntityCount3()
        ):
            raise RuntimeError("native annotation attachment inventory is incomplete")
        if (
            any(item is None for item in entities)
            or 0 in kinds
            or annotation.IsDangling()
        ):
            raise RuntimeError(
                "selected lever view has unsupported/null native attachment slots"
            )
        result[str(annotation.GetName())] = annotation, kind, entities, kinds
    return result


def _same_native(app, before, after):
    if before.keys() != after.keys():
        raise RuntimeError("native manufacturing annotation inventory changed")
    for name, (annotation, kind, entities, types) in before.items():
        actual, actual_kind, actual_entities, actual_types = after[name]
        if (
            kind != actual_kind
            or types != actual_types
            or len(entities) != len(actual_entities)
            or int(app.IsSame(annotation, actual)) != 1
            or any(
                int(app.IsSame(a, b)) != 1 for a, b in zip(entities, actual_entities)
            )
        ):
            raise RuntimeError(f"{name}: native annotation/entity identity changed")


def _records(bank):
    return {
        name: {
            "position": row.position,
            "body": row.body.bounds,
            "frames": row.frames,
            "text": row.text,
            "format": row.text_format,
            "attachment_types": row.entity_types,
        }
        for name, row in bank.items()
    }


def _same_saved_frames(before, after):
    if before.keys() != after.keys():
        raise RuntimeError("saved/reopened GTol inventory changed")
    for name, original in before.items():
        actual = after[name]
        for field in ("frames", "text", "format", "attachment_types"):
            if original[field] != actual[field]:
                raise RuntimeError(f"{name}: saved/reopened GTol {field} changed")
        for field in ("position", "body"):
            if len(original[field]) != len(actual[field]) or any(
                abs(a - b) > 1e-8 for a, b in zip(original[field], actual[field])
            ):
                raise RuntimeError(f"{name}: saved/reopened GTol {field} moved")


def _measure_view(adapter, view):
    measured = {}
    for raw in view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.OwnerType) == 2 or int(annotation.Visible) == 3:
            continue
        bounds = annotation_box(adapter, annotation)
        if bounds.name in measured:
            raise RuntimeError("native view annotation names are not unique")
        measured[bounds.name] = bounds
    return measured


async def probe(adapter: Any, source: Path, requested_view: str | None):
    import _drawing_native_gtol as gtol
    from diagnostics.probe_drawing_attachments import snapshot, compare
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing

    reports = CAD_ROOT / "out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(
        tempfile.mkdtemp(prefix="gtol-right-column-", dir=reports)
    ).resolve()
    copy = directory / f"{directory.name}-source.SLDDRW"
    shutil.copy2(source, copy)
    owned = {copy}
    hashes = {source: hashlib.sha256(source.read_bytes()).hexdigest()}
    report = {"source": str(source), "copy": str(copy), "phases": {}}

    def export(stage):
        path = directory / f"{directory.name}-{stage}.SLDDRW"
        owned.add(path)
        outputs = save_drawing(
            adapter, str(path), pdf_path=str(path.with_suffix(".pdf"))
        )
        if not path.with_suffix(".pdf").is_file():
            raise RuntimeError(f"right-column diagnostic PDF missing: {outputs}")
        render_pdf_png(path.with_suffix(".pdf"), path.with_suffix(".png"))
        return path

    try:
        check(
            "open unique right-column drawing copy", await adapter.open_model(str(copy))
        )
        if Path(adapter.currentModel.GetPathName()).resolve() != copy:
            raise RuntimeError("SolidWorks opened the wrong right-column copy")
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        views = [
            _early_bound(raw, "IView")
            for sheet in drawing.GetViews() or ()
            for raw in sheet[1:]
        ]
        for view in views:
            path = Path(view.ReferencedDocument.GetPathName()).resolve(strict=True)
            if path.suffix.upper() != ".SLDPRT":
                raise ValueError(
                    "right-column control supports native part drawings only"
                )
            hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        candidates = [(view, len(view.GetAnnotationsByType(5) or ())) for view in views]
        if requested_view is not None:
            matches = [
                view
                for view, count in candidates
                if str(view.GetName2()) == requested_view and count
            ]
        else:
            largest = max((count for _view, count in candidates), default=0)
            matches = [view for view, count in candidates if count == largest and count]
        if len(matches) != 1:
            raise ValueError(
                "name an exact view or require one uniquely largest nonempty GTol bank"
            )
        view = matches[0]
        report["view"] = str(view.GetName2())
        report["view_inventory"] = {
            str(item.GetName2()): count for item, count in candidates
        }
        if not drawing.ActivateView(str(view.GetName2())):
            raise RuntimeError("right-column owning view activation failed")
        export("before")
        before = gtol._read_gtols(adapter, view, annotation_box)
        if any(int(row.annotation.GetLeaderStyle()) != 2 for row in before.values()):
            raise RuntimeError(
                "right-column control requires existing native bent GTol leaders"
            )
        native_before = _native_entities(adapter, view)
        semantics_before = snapshot(adapter.currentModel)
        measured_before = _measure_view(adapter, view)
        leaders_before = {
            name: _leaders(row.annotation) for name, row in before.items()
        }
        report["phases"]["before"] = {
            "bank": _records(before),
            "leaders": {
                name: [asdict(segment) for segment in rows]
                for name, rows in leaders_before.items()
            },
            "crossings": crossing_records(leaders_before, measured_before),
            "semantics": semantics_before,
        }
        outline = Rect(*view.GetOutline())
        column = gtol._union([row.body for row in before.values()])
        obstacles = tuple(
            bounds.body
            for name, bounds in measured_before.items()
            if name not in before and bounds.kind in {2, 4, 7}
        )
        delta = right_translation(column, outline, obstacles)
        report["placement"] = {
            "column": column.bounds,
            "outline": outline.bounds,
            "obstacles": [item.bounds for item in obstacles],
            "translation_m": delta,
        }
        predicted = gtol._move_bank(
            before,
            {name: delta for name in before},
            "diagnostic alternative right column",
        )
        after = gtol._read_gtols(adapter, view, annotation_box)
        if any(int(row.annotation.GetLeaderStyle()) != 2 for row in after.values()):
            raise RuntimeError(
                "alternative column changed native bent GTol leader style"
            )
        gtol._unchanged(adapter.swApp, before, after, "alternative right column")
        gtol._assert_measured_prediction(predicted, after)
        _same_native(adapter.swApp, native_before, _native_entities(adapter, view))
        semantics_after = snapshot(adapter.currentModel)
        compare(semantics_before, semantics_after, "alternative right column")
        measured_after = _measure_view(adapter, view)
        leaders_after = {name: _leaders(row.annotation) for name, row in after.items()}
        report["phases"]["after"] = {
            "bank": _records(after),
            "leaders": {
                name: [asdict(segment) for segment in rows]
                for name, rows in leaders_after.items()
            },
            "crossings": crossing_records(leaders_after, measured_after),
            "semantics": semantics_after,
        }
        saved = export("right")
        check(
            "close right-column copy for persistence witness",
            await adapter.close_model(save=False),
        )
        check("reopen right-column saved copy", await adapter.open_model(str(saved)))
        if Path(adapter.currentModel.GetPathName()).resolve() != saved:
            raise RuntimeError("reopened right-column document path differs")
        reopened = snapshot(adapter.currentModel)
        compare(semantics_before, reopened, "saved/reopened alternative right column")
        report["reopened_semantics"] = reopened
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        reopened_views = [
            _early_bound(raw, "IView")
            for sheet in drawing.GetViews() or ()
            for raw in sheet[1:]
        ]
        matches = [
            item for item in reopened_views if str(item.GetName2()) == report["view"]
        ]
        if len(matches) != 1:
            raise RuntimeError("saved/reopened right-column view identity changed")
        reopened_bank = gtol._read_gtols(adapter, matches[0], annotation_box)
        _same_saved_frames(_records(after), _records(reopened_bank))
        report["reopened_bank"] = _records(reopened_bank)
        report["outcome"] = "captured_alternative_not_production_layout"
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        try:
            if (
                adapter.currentModel is not None
                and Path(adapter.currentModel.GetPathName()).resolve() in owned
            ):
                check(
                    "close owned right-column diagnostic copy",
                    await adapter.close_model(save=False),
                )
            report["source_unchanged"] = {
                str(path): hashlib.sha256(path.read_bytes()).hexdigest() == digest
                for path, digest in hashes.items()
            }
            if not all(report["source_unchanged"].values()):
                raise RuntimeError(
                    "right-column diagnostic changed original source bytes"
                )
        finally:
            (directory / "column.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            _telemetry.info(f"right-column diagnostic observations: {directory}")
    return {"report": str(directory / "column.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--view")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if source.suffix.upper() != ".SLDDRW":
        raise ValueError("right-column probe needs a native drawing")
    if not args.worker:
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo

        command = [sys.executable, str(Path(__file__).resolve()), str(source)]
        if args.view:
            command += ["--view", args.view]
        dodo._run(
            [*command, "--worker"],
            "native alternative right GTol column",
            log_stem="gtol-right-column",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat")
    _telemetry.set_service("drawing-right-gtol-column-probe")
    return run_build(lambda adapter: probe(adapter, source, args.view))


if __name__ == "__main__":
    raise SystemExit(main())
