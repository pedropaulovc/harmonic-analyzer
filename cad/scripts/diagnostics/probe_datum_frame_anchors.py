"""Read datum anchors versus native generic frames on a unique drawing copy.

No datum, dimension, view or geometry setters are called. Capture generic and
specific primitives independently before/after native copy export. The frame
relation is an observation, not an assumed horizontal-side attachment rule.
Original drawing/part SHA-256 values and exact native identity are guarded.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check, run_build  # noqa: E402
from _drawing_annotation_bounds import (  # noqa: E402
    _native_snapshot,
    _frame_lines,
    bounds_from_snapshot,
)
from diagnostics import probe_drawing_attachments as attachments  # noqa: E402
from diagnostics.probe_datum_dimension_attachment import (  # noqa: E402
    raw_display_data,
    rendered_datum_text,
    same_handles,
)
from diagnostics.probe_datum_sheet_z import guard_sources  # noqa: E402
from diagnostics.probe_native_model_pmi import file_digest, render_pdf_png  # noqa: E402
import _telemetry  # noqa: E402


def frame_relation(position, frame):
    if (
        len(position) != 3
        or len(frame) != 4
        or not all(math.isfinite(v) for v in (*position, *frame))
    ):
        raise ValueError("frame observation needs finite native coordinates")
    xmin, ymin, xmax, ymax = frame
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("frame observation needs a positive rectangle")
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    points = {
        "left": (xmin, cy),
        "right": (xmax, cy),
        "bottom": (cx, ymin),
        "top": (cx, ymax),
    }
    errors = {side: math.dist(position[:2], point) for side, point in points.items()}
    return {
        "frame": frame,
        "offset_from_center": (position[0] - cx, position[1] - cy),
        "side_midpoint_errors_m": errors,
        "matching_side_midpoints": tuple(
            side for side, error in errors.items() if error <= 1e-8
        ),
    }


def count(value):
    result = int(value)
    if not 0 <= result <= 10000:
        raise RuntimeError("unbounded native datum count")
    return result


def capture(adapter, part):
    records, handles = {}, {}
    for view_key, view in attachments.views(adapter.currentModel).items():
        source = _early_bound(view.ReferencedDocument, "IModelDoc2")
        if Path(source.GetPathName()).resolve() != part:
            raise RuntimeError("datum view refers to an unguarded source part")
        for raw in view.GetAnnotationsByType(2) or ():
            annotation = _early_bound(raw, "IAnnotation")
            tag = _early_bound(annotation.GetSpecificAnnotation(), "IDatumTag")
            if (
                int(annotation.OwnerType) != 0
                or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1
                or int(adapter.swApp.IsSame(tag.GetAnnotation(), annotation)) != 1
            ):
                raise RuntimeError("datum native annotation/tag/view identity differs")
            entities = tuple(annotation.GetAttachedEntities3() or ())
            kinds = tuple(int(k) for k in annotation.GetAttachedEntityTypes() or ())
            if len(entities) != int(annotation.GetAttachedEntityCount3()) or len(
                entities
            ) != len(kinds):
                raise RuntimeError("datum attachment arrays disagree")
            name = f"{view_key}/{annotation.GetName()}"
            if name in records:
                raise RuntimeError("datum identity is duplicated")
            position = tuple(float(v) for v in annotation.GetPosition() or ())
            if len(position) != 3 or not all(math.isfinite(v) for v in position):
                raise RuntimeError("datum native anchor is invalid")
            generic = raw_display_data(annotation)
            label = str(tag.GetLabel())
            record = {
                "label": label,
                "position": position,
                "owner_type": int(annotation.OwnerType),
                "visible": int(annotation.Visible),
                "dangling": bool(annotation.IsDangling()),
                "attachment_types": kinds,
                "null_attachments": tuple(e is None for e in entities),
                "geometry": tuple(
                    attachments.geometry(e, k)
                    for e, k in zip(entities, kinds)
                    if e is not None and k in {1, 2, 3}
                ),
                "view_outline": tuple(view.GetOutline()),
                "view_position": tuple(view.Position),
                "configuration": str(view.ReferencedConfiguration),
                "shoulder": bool(tag.Shoulder),
                "forced_shoulder": bool(tag.ForcedShoulder),
                "style": int(tag.GetDisplayStyle()),
                "label_render": rendered_datum_text(generic, label),
                "generic": generic,
                "specific": {
                    "texts": tuple(
                        str(tag.GetTextAtIndex(i))
                        for i in range(count(tag.GetTextCount()))
                    ),
                    "lines": tuple(
                        tuple(tag.GetLineAtIndex(i))
                        for i in range(count(tag.GetLineCount()))
                    ),
                },
                "leader_style": int(annotation.GetLeaderStyle()),
                "leaders": tuple(
                    tuple(annotation.GetLeaderPointsAtIndex(i) or ())
                    for i in range(count(annotation.GetLeaderCount()))
                ),
            }
            try:
                native = _native_snapshot(annotation, adapter.currentModel.Extension)
                measured = bounds_from_snapshot(native)
                frame_lines = _frame_lines(native.lines)
                record["native"] = asdict(native)
                record["measurement"] = asdict(measured)
                record["frame_lines"] = tuple(asdict(line) for line in frame_lines)
                if len(frame_lines) != 4:
                    raise ValueError(
                        "datum has no single closed rectangular generic frame"
                    )
                points = tuple(
                    p for line in frame_lines for p in (line.start, line.end)
                )
                frame = (
                    min(p[0] for p in points),
                    min(p[1] for p in points),
                    max(p[0] for p in points),
                    max(p[1] for p in points),
                )
                record["frame_relation"] = frame_relation(position, frame)
            except ValueError as error:
                record["measurement_error"] = str(error)
            records[name] = record
            handles[name] = (annotation, tag, view, *entities)
    if not records:
        raise RuntimeError("drawing has no native datum annotations")
    return records, handles


def compare(app, before, before_handles, after, after_handles):
    if before.keys() != after.keys():
        raise RuntimeError("copy export changed datum inventory")
    fields = (
        "label",
        "owner_type",
        "visible",
        "dangling",
        "attachment_types",
        "null_attachments",
        "geometry",
        "configuration",
        "shoulder",
        "forced_shoulder",
        "style",
        "label_render",
    )
    for name, original in before.items():
        same_handles(app, before_handles[name], after_handles[name])
        if any(original[field] != after[name][field] for field in fields):
            raise RuntimeError(f"{name}: export changed native datum semantics")
        if math.dist(original["position"], after[name]["position"]) > 1e-8:
            raise RuntimeError(f"{name}: export moved native datum")


async def probe(adapter, source, directory):
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing

    part = (source.parent.parent / "sldprt" / f"{source.stem}.SLDPRT").resolve(
        strict=True
    )
    report = {"source_hashes": {str(p): file_digest(p) for p in (source, part)}}
    app = _early_bound(adapter.swApp, "ISldWorks")
    report_path = directory / "datum-frame-anchors.json"
    try:
        copy = directory / f"{directory.name}-source.SLDDRW"
        shutil.copy2(source, copy)
        check("open unique datum frame copy", await adapter.open_model(str(copy)))
        if Path(adapter.currentModel.GetPathName()).resolve() != copy:
            raise RuntimeError("active drawing is not the unique requested copy")
        manufacturing = attachments.snapshot(adapter.currentModel, app=adapter.swApp)
        report["before"], handles = capture(adapter, part)
        drawing = directory / f"{directory.name}-export.SLDDRW"
        pdf, png = drawing.with_suffix(".pdf"), drawing.with_suffix(".png")
        save_drawing(adapter, str(drawing), pdf_path=str(pdf))
        render_pdf_png(pdf, png)
        report["export"] = {"drawing": str(drawing), "pdf": str(pdf), "png": str(png)}
        report["after"], after_handles = capture(adapter, part)
        compare(app, report["before"], handles, report["after"], after_handles)
        attachments.compare(
            manufacturing,
            attachments.snapshot(adapter.currentModel, app=adapter.swApp),
            "datum frame copy export",
        )
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        try:
            if not app.CloseAllDocuments(True):
                raise RuntimeError("failed to close copied datum frame documents")
            adapter.currentModel = None
        finally:
            try:
                guard_sources(report)
            finally:
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                _telemetry.info(f"native datum frame observations: {report_path}")
    return {"report": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), str(source), "--worker"],
            "native datum frame anchors",
            com=True,
            log_stem="datum-frame-anchors",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("datum frame capture requires the coordinated COM seat")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="datum-frames-", dir=reports))
    return run_build(lambda adapter: probe(adapter, source, directory))


if __name__ == "__main__":
    raise SystemExit(main())
