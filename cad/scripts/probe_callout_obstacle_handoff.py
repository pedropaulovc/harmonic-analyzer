"""A/B copied-drawing control for the actual callout-final obstacle handoff.

Run through uv with one native part drawing. FRESH and HANDOFF use independent
unique copies, the same native placement/full final validation, and separate
timed annotation readers. This diagnostic baseline is not a production fallback.
Free native notes are explicitly movable diagnostic groups; recipe-specific
projection links are outside this A/B layout contract. Original files are hashed
and never saved. Only uniquely named outputs under this report directory change.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import cProfile
from dataclasses import asdict
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import pstats
import shutil
import sys
import tempfile
import time
from xml.etree import ElementTree

from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_annotation_bounds import annotation_box
from _drawing_common import _TITLE_BLOCK_LEFT_M, _TITLE_BLOCK_TOP_M
from _drawing_leader_clearance import validate_gtol_leader_clearance
from _drawing_measurement_handoff import AnnotationMeasurementHandoff, HandoffPurpose
from _drawing_native_callouts import GtolPlacement, arrange_native_callouts, _properties
from _drawing_native_gtol import arrange_native_gtol_columns
from _drawing_native_layout import LayoutNote, NativeLayoutStatus, repair_native_layout
from _drawing_view_packing import Rect
from diagnostics.probe_drawing_attachments import snapshot, compare, layout
import _telemetry


class Mode(Enum):
    FRESH = "fresh"
    HANDOFF = "handoff"


def _context(adapter):
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheets = tuple(drawing.GetViews() or ())
    if len(sheets) != 1:
        raise ValueError("obstacle handoff probe requires exactly one native sheet")
    views, notes = {}, []
    for raw in sheets[0][1:]:
        view = _early_bound(raw, "IView")
        name = str(view.GetName2())
        if not name or name in views:
            raise ValueError("probe requires unique native drawing view names")
        views[name] = view
    seen = {}
    for raw_view in sheets[0]:
        view = _early_bound(raw_view, "IView")
        for raw in view.GetAnnotationsByType(6) or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.OwnerType) == 2 or int(annotation.Visible) == 3:
                continue
            if int(annotation.GetAttachedEntityCount3()) != 0:
                continue  # Attached notes remain measured native view obstacles.
            name = str(annotation.GetName())
            if name in seen:
                if int(adapter.swApp.IsSame(seen[name], annotation)) != 1:
                    raise ValueError("probe free notes require unique native names")
                continue
            seen[name] = annotation
            notes.append(LayoutNote(name, annotation))
    return drawing, views, tuple(notes)


def _semantic_fields(views):
    result = {}
    for view_name, view in views.items():
        for kind, interface in ((2, "IDatumTag"), (5, "IGtol"), (7, "ISFSymbol")):
            for raw in view.GetAnnotationsByType(kind) or ():
                annotation = _early_bound(raw, "IAnnotation")
                if int(annotation.OwnerType) == 2 or int(annotation.Visible) == 3:
                    continue
                specific = _early_bound(annotation.GetSpecificAnnotation(), interface)
                key = f"{view_name}/{annotation.GetName()}/{kind}"
                if kind != 5:
                    result[key] = _properties(kind, specific)
                    continue
                count = int(specific.GetFrameCount())
                if count < 1:
                    raise RuntimeError("copied GTol has no native XML frame")
                result[key] = tuple(
                    ElementTree.canonicalize(
                        str(
                            _early_bound(
                                specific.GetFrame(i), "IGtolFrame"
                            ).GetSymbolXml()
                        )
                    )
                    for i in range(1, count + 1)
                )
    return result


def _run_layout(adapter, views, notes, mode, evidence):
    reads, timings, phases = Counter(), Counter(), Counter()
    phase = "callouts"

    @contextmanager
    def timed_phase(name):
        nonlocal phase
        phase = name
        started = time.perf_counter()
        try:
            yield
        finally:
            phases[name] += time.perf_counter() - started

    def measure(adapter, annotation):
        started = time.perf_counter()
        measured = annotation_box(adapter, annotation)
        key = f"{phase}/kind{measured.kind}"
        reads[key] += 1
        timings[key] += time.perf_counter() - started
        return measured

    packing = AnnotationMeasurementHandoff(
        adapter,
        views=views,
        measure_annotation=measure,
        purpose=HandoffPurpose.INITIAL_PACKING,
    )
    obstacle = None
    if mode is Mode.HANDOFF:
        obstacle = AnnotationMeasurementHandoff(
            adapter,
            views=views,
            measure_annotation=measure,
            purpose=HandoffPurpose.GTOL_OBSTACLES,
        )
    started = time.perf_counter()
    try:
        with timed_phase("callouts"):
            evidence["callouts"] = arrange_native_callouts(
                adapter,
                views=views,
                measure_annotation=measure,
                record_measurement=obstacle.record if obstacle is not None else None,
                gtol_placement=GtolPlacement.ARRANGED_NEXT,
                deferred_notes=tuple(note.annotation for note in notes),
            )
            if obstacle is not None:
                obstacle.seal()
        with timed_phase("gtols"):
            evidence["gtols"] = arrange_native_gtol_columns(
                adapter,
                views=views,
                measure_annotation=measure,
                measure_obstacle=obstacle.initial_measure
                if obstacle is not None
                else measure,
                obstacle_read_scope=obstacle.read_scope
                if obstacle is not None
                else None,
                record_measurement=packing.record,
            )
            packing.seal()
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        properties = tuple(
            _early_bound(drawing.GetCurrentSheet(), "ISheet").GetProperties2()
        )

        def final(measurements):
            evidence["final_leader_clearance"] = validate_gtol_leader_clearance(
                measurements
            )

        with timed_phase("packing"):
            report = repair_native_layout(
                adapter,
                views=views,
                notes=notes,
                title_block=Rect(
                    _TITLE_BLOCK_LEFT_M, 0, float(properties[5]), _TITLE_BLOCK_TOP_M
                ),
                measure_annotation=measure,
                initial_measure_annotation=packing.initial_measure,
                initial_measure_scope=packing.read_scope,
                planning_headroom_m=0.0005,
                final_annotation_validation=final,
            )
        evidence["packing"] = asdict(report)
        if report.status not in (
            NativeLayoutStatus.APPLIED,
            NativeLayoutStatus.UNCHANGED,
        ):
            raise RuntimeError(f"copied A/B layout did not fit: {report.reason}")
    finally:
        evidence["layout_seconds"] = time.perf_counter() - started
        evidence["phase_seconds"] = dict(phases)
        evidence["full_measurement_counts"] = dict(reads)
        evidence["full_measurement_seconds"] = dict(timings)
        evidence["full_measurement_total"] = sum(reads.values())
        if obstacle is not None:
            evidence["reused_obstacle_count"] = obstacle._reused
            obstacle.close()
        packing.close()


def _profiled_layout(adapter, views, notes, mode, evidence, directory):
    """Capture native calls and Python time even when a strict witness rejects."""
    profile = cProfile.Profile()
    profile.enable()
    try:
        _run_layout(adapter, views, notes, mode, evidence)
    finally:
        profile.disable()
        output = directory / f"{mode.value}-layout.pstats"
        profile.dump_stats(str(output))
        stats = pstats.Stats(profile)
        rows = []
        for (filename, line, function), values in stats.stats.items():
            primitive_calls, total_calls, self_seconds, cumulative_seconds, _ = values
            rows.append(
                {
                    "file": filename,
                    "line": line,
                    "function": function,
                    "primitive_calls": primitive_calls,
                    "total_calls": total_calls,
                    "self_seconds": self_seconds,
                    "cumulative_seconds": cumulative_seconds,
                }
            )
        evidence["profile"] = {
            "path": str(output),
            "total_calls": stats.total_calls,
            "primitive_calls": stats.prim_calls,
            "total_self_seconds": stats.total_tt,
            "functions": sorted(rows, key=lambda row: -row["cumulative_seconds"]),
        }


async def probe(adapter, source):
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing

    reports = CAD_ROOT / "out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="callout-handoff-", dir=reports)).resolve()
    source = source.resolve(strict=True)
    hashes = {source: hashlib.sha256(source.read_bytes()).hexdigest()}
    owned, report = set(), {"source": str(source), "modes": {}}
    try:
        for mode in Mode:
            copy = directory / f"{directory.name}-{mode.value}.SLDDRW"
            observed = copy.with_stem(copy.stem + "-observed")
            for path in (copy, observed):
                if not path.resolve().is_relative_to(directory) or path == source:
                    raise RuntimeError(
                        "probe output escaped its unique report directory"
                    )
                owned.add(path)
            shutil.copy2(source, copy)
            row = report["modes"][mode.value] = {"copy": str(copy), "stage": "open"}
            check("open independent obstacle copy", await adapter.open_model(str(copy)))
            if Path(adapter.currentModel.GetPathName()).resolve() != copy:
                raise RuntimeError("native application opened the wrong obstacle copy")
            _, views, notes = _context(adapter)
            for view in views.values():
                reference = Path(view.ReferencedDocument.GetPathName()).resolve(
                    strict=True
                )
                if reference.suffix.upper() != ".SLDPRT":
                    raise ValueError(
                        "obstacle A/B control supports native part drawings only"
                    )
                hashes.setdefault(
                    reference, hashlib.sha256(reference.read_bytes()).hexdigest()
                )
            before, fields = (
                snapshot(adapter.currentModel, app=adapter.swApp),
                _semantic_fields(views),
            )
            row["before"] = before
            row["stage"] = "layout"
            _profiled_layout(adapter, views, notes, mode, row, directory)
            after = snapshot(adapter.currentModel, app=adapter.swApp)
            compare(before, after, f"{mode.value} native layout")
            if fields != _semantic_fields(views):
                raise RuntimeError(
                    "native layout changed stored datum/SF/GTol semantic fields"
                )
            row["after"], row["layout_after"] = after, layout(adapter.currentModel)
            save_drawing(
                adapter, str(observed), pdf_path=str(observed.with_suffix(".pdf"))
            )
            for output in (observed, observed.with_suffix(".pdf")):
                if not output.is_file() or output.stat().st_size == 0:
                    raise RuntimeError(
                        f"native A/B output is missing or empty: {output}"
                    )
            row["observed"] = str(observed)
            check("close observed obstacle copy", await adapter.close_model(save=False))
            check(
                "reopen observed obstacle copy", await adapter.open_model(str(observed))
            )
            if Path(adapter.currentModel.GetPathName()).resolve() != observed:
                raise RuntimeError(
                    "native application reopened the wrong obstacle copy"
                )
            reopened = snapshot(adapter.currentModel, app=adapter.swApp)
            compare(before, reopened, f"{mode.value} save/reopen")
            if fields != _semantic_fields(_context(adapter)[1]):
                raise RuntimeError(
                    "save/reopen changed stored datum/SF/GTol semantic fields"
                )
            row["reopened"], row["stage"] = reopened, "passed"
            check("close reopened obstacle copy", await adapter.close_model(save=False))
        fresh, cached = report["modes"]["fresh"], report["modes"]["handoff"]
        compare(fresh["after"], cached["after"], "fresh versus handoff")
        if fresh["layout_after"] != cached["layout_after"]:
            raise RuntimeError("A/B native layout positions differ")
        saved = fresh["full_measurement_total"] - cached["full_measurement_total"]
        if saved != cached["reused_obstacle_count"] or saved <= 0:
            raise RuntimeError(
                "handoff did not remove exactly its recorded obstacle reads"
            )
        report["measurement_reads_saved"] = saved
        report["layout_seconds_saved"] = (
            fresh["layout_seconds"] - cached["layout_seconds"]
        )
        report["stage"] = "passed"
    except Exception as error:
        report["stage"] = "failed"
        report["error"] = repr(error)
        raise
    finally:
        try:
            current = adapter.currentModel
            if current is not None and Path(current.GetPathName()).resolve() in owned:
                check(
                    "close failed obstacle copy unsaved",
                    await adapter.close_model(save=False),
                )
            report["source_unchanged"] = {
                str(path): hashlib.sha256(path.read_bytes()).hexdigest() == digest
                for path, digest in hashes.items()
            }
            report["source_sha256"] = {
                str(path): digest for path, digest in hashes.items()
            }
            if not all(report["source_unchanged"].values()):
                report["stage"] = "failed"
                report["error"] = "obstacle probe changed original source bytes"
                raise RuntimeError("obstacle probe changed original source bytes")
        finally:
            (directory / "handoff.json").write_text(
                json.dumps(report, indent=2, default=lambda value: value.value),
                encoding="utf-8",
            )
            _telemetry.info(f"callout obstacle handoff control: {directory}")
    return {"report": str(directory / "handoff.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if not args.worker:
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo

        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), str(source), "--worker"],
            "callout obstacle handoff control",
            log_stem="callout-obstacle-handoff",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat")
    _telemetry.set_service("drawing-obstacle-handoff-probe")
    return run_build(lambda adapter: probe(adapter, source))


if __name__ == "__main__":
    raise SystemExit(main())
