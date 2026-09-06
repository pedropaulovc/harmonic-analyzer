"""Copy-only native dimension AutoArrange after an already arranged GTol layout.

Run ``uv run python cad/scripts/diagnostics/probe_dimensions_after_gtol.py DRAWING``.
One existing auto_arrange_view_dimensions call covers all native drawing views.
No GTol command, view movement, explicit annotation position, or leader routing
is added. Export before/after/reopened copies; compare actual dimension values,
attachment geometry, GTol text/frame/entity identity, and native positions.
Reported leader/text-cell intersections are diagnostics, not glyph-ink verdicts.
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
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check, run_build  # noqa: E402
from _drawing_common import auto_arrange_view_dimensions  # noqa: E402
from _drawing_annotation_bounds import annotation_box  # noqa: E402
from diagnostics import probe_drawing_attachments as attachments  # noqa: E402
from diagnostics import probe_gtol_commands as gtols  # noqa: E402
from diagnostics.probe_native_model_pmi import file_digest, render_pdf_png  # noqa: E402
import _telemetry  # noqa: E402


def segment_intersects_box(start, end, box):
    """Closed segment/rectangle slab test in sheet metres; no picking or edits."""
    low, high = 0.0, 1.0
    for axis, minimum, maximum in ((0, box.xmin, box.xmax), (1, box.ymin, box.ymax)):
        delta = end[axis] - start[axis]
        if delta == 0:
            if not minimum <= start[axis] <= maximum:
                return False
            continue
        enter, leave = sorted(
            ((minimum - start[axis]) / delta, (maximum - start[axis]) / delta)
        )
        low, high = max(low, enter), min(high, leave)
        if low > high:
            return False
    return True


def leader_text_intersections(measured):
    result = []
    for source, leader in measured.items():
        if leader.kind != 5:
            continue
        for target, dimension in measured.items():
            if dimension.kind != 4:
                continue
            runs = [run for run in dimension.text_runs if run.value]
            if len(runs) != len(dimension.text_boxes):
                raise RuntimeError("dimension text boxes do not match native text runs")
            for run, box in zip(runs, dimension.text_boxes, strict=True):
                for index, segment in enumerate(leader.leader_segments):
                    if segment_intersects_box(segment.start, segment.end, box):
                        result.append(
                            {
                                "gtol": source,
                                "dimension": target,
                                "text": run.value,
                                "leader_segment_index": index,
                                "leader_segment": asdict(segment),
                                "text_cell": asdict(box),
                            }
                        )
    return result


def capture(adapter, hashes):
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    semantics = attachments.snapshot(model, app=adapter.swApp)
    for reference in semantics["models"].values():
        source = reference["path"]
        hashes.setdefault(source, file_digest(Path(source)))
    controls, handles = gtols.snapshot(drawing, hashes)
    measured, positions = {}, {}
    for view_key, view in attachments.views(model).items():
        for kind in (4, 5):
            for raw in view.GetAnnotationsByType(kind) or ():
                annotation = _early_bound(raw, "IAnnotation")
                key = f"{view_key}/{annotation.GetName()}/{kind}"
                if key in measured:
                    raise RuntimeError(f"duplicate native annotation: {key}")
                measured[key] = annotation_box(adapter, annotation)
                positions[key] = tuple(annotation.GetPosition())
    return {
        "semantics": semantics,
        "gtols": controls,
        "view_layout": attachments.layout(model),
        "positions": positions,
        "bounds": {key: asdict(value) for key, value in measured.items()},
        "leader_text_cell_intersections": leader_text_intersections(measured),
    }, handles


def compare(adapter, before, after, handles, stage):
    attachments.compare(before["semantics"], after["semantics"], stage)
    attachments.check_layout(before["view_layout"], after["view_layout"], stage)
    gtols.compare(before["gtols"], after["gtols"], handles, adapter.swApp, stage=stage)
    if before["positions"].keys() != after["positions"].keys():
        raise RuntimeError(f"{stage}: annotation inventory changed")
    return {
        key: math.dist(position, after["positions"][key])
        for key, position in before["positions"].items()
    }


async def probe(adapter, source, directory):
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing

    report = {
        "source": str(source),
        "source_hashes": {str(source): file_digest(source)},
    }
    report_path = directory / "dimensions-after-gtol.json"
    copy = directory / f"{directory.name}-source.SLDDRW"
    shutil.copy2(source, copy)
    app = _early_bound(adapter.swApp, "ISldWorks")

    def export(stage):
        target = directory / f"{directory.name}-{stage}.SLDDRW"
        pdf, png = target.with_suffix(".pdf"), target.with_suffix(".png")
        save_drawing(adapter, str(target), pdf_path=str(pdf))
        render_pdf_png(pdf, png)
        report.setdefault("exports", {})[stage] = {
            "drawing": str(target),
            "pdf": str(pdf),
            "png": str(png),
        }
        return target

    try:
        check(
            "open unique post-GTol dimension control",
            await adapter.open_model(str(copy)),
        )
        if Path(adapter.currentModel.GetPathName()).resolve() != copy:
            raise RuntimeError("SolidWorks opened a different drawing copy")
        report["before"], handles = capture(adapter, report["source_hashes"])
        compare(
            adapter,
            report["before"],
            report["before"],
            handles,
            "baseline positive control",
        )
        export("before")
        started = time.perf_counter()
        count = auto_arrange_view_dimensions(
            adapter, attachments.views(adapter.currentModel).values()
        )
        report["native_arrange"] = {
            "selected_dimensions": count,
            "seconds": time.perf_counter() - started,
        }
        if count == 0:
            raise RuntimeError(
                "native ordering positive control selected no dimensions"
            )
        report["after"], handles = capture(adapter, report["source_hashes"])
        report["movement_m"] = compare(
            adapter, report["before"], report["after"], handles, "after native arrange"
        )
        output = export("after")
        if not app.CloseAllDocuments(True):
            raise RuntimeError("failed to close isolated drawing before reopen")
        adapter.currentModel = None
        check(
            "reopen post-GTol dimension control", await adapter.open_model(str(output))
        )
        report["reopened"], handles = capture(adapter, report["source_hashes"])
        report["reopen_movement_m"] = compare(
            adapter, report["after"], report["reopened"], handles, "save/reopen"
        )
        if any(delta > 1e-9 for delta in report["reopen_movement_m"].values()):
            raise RuntimeError("annotation position changed across native save/reopen")
        export("reopened")
        report["status"] = "passed"
    except Exception as error:
        report["operation_error"] = repr(error)
        raise
    finally:
        try:
            if not app.CloseAllDocuments(True):
                raise RuntimeError("failed to close native ordering control")
            adapter.currentModel = None
        finally:
            report["source_hashes_after"] = {
                name: file_digest(Path(name)) for name in report["source_hashes"]
            }
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            _telemetry.info(
                f"post-GTol dimension AutoArrange observations: {report_path}"
            )
    if report["source_hashes"] != report["source_hashes_after"]:
        raise RuntimeError(
            "native ordering control changed an original drawing or part"
        )
    return {"report": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if source.suffix.upper() != ".SLDDRW":
        raise ValueError("requires a native drawing")
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), str(source), "--worker"],
            "post-GTol dimension AutoArrange",
            com=True,
            log_stem="dimensions-after-gtol",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("worker requires the parent COM seat lock")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="dimensions-after-gtol-", dir=reports))
    return run_build(lambda adapter: probe(adapter, source, directory))


if __name__ == "__main__":
    raise SystemExit(main())
