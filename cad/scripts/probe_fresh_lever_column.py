"""Build a coherent diagnostic lever from its CURRENT part, then test columns.

The real recipe receives explicit source/output/layout inputs. Only this
diagnostic's injected layout omits the separately failing datum/SF clearance
stage; native GTol spacing and full measured sheet packing still run. This is
an experimental baseline, never a production fallback or publishable drawing.
The existing copied-column probe then proves native adornment clearance,
full/narrow reader parity and saved/reopened geometry/value preservation.

Run: uv run python cad/scripts/probe_fresh_lever_column.py CURRENT_PART
    --original-drawing ORIGINAL_SLDDRW
Original part/drawing SHA-256 and source BASIC values/types must remain exact.
Every output has a unique diagnostic path. No source feature or tolerance is
authored, no geometry is picked using a sheet coordinate, and nothing is pushed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import DrawingOutputs, _TITLE_BLOCK_LEFT_M, _TITLE_BLOCK_TOP_M
from _drawing_annotation_bounds import annotation_box
from _drawing_measurement_handoff import AnnotationMeasurementHandoff
from _drawing_native_gtol import arrange_native_gtol_columns
from _drawing_native_layout import repair_native_layout, NativeLayoutStatus
from _drawing_view_packing import Rect
from _drawing_marks import _named_dimension
from channel_lever_spec import SOURCE_BASIC_DIMENSIONS
from draw_channel_lever import build as build_lever
from probe_drawing_right_gtol_column import probe as probe_column
from diagnostics.probe_source_basic_dimensions import drawing_dimensions
import _telemetry


def diagnostic_layout(adapter: Any, *, views, alignments=(), orderings=(), notes=()):
    """Explicit GTol+packing control, with no datum/SF placement stage."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    properties = tuple(
        _early_bound(drawing.GetCurrentSheet(), "ISheet").GetProperties2() or ()
    )
    if len(properties) != 8:
        raise RuntimeError("coherent lever control requires complete sheet properties")
    handoff = AnnotationMeasurementHandoff(
        adapter, views=views, measure_annotation=annotation_box
    )
    try:
        gtols = arrange_native_gtol_columns(
            adapter,
            views=views,
            measure_annotation=annotation_box,
            record_measurement=handoff.record,
        )
        handoff.seal()
        report = repair_native_layout(
            adapter,
            views=views,
            title_block=Rect(
                _TITLE_BLOCK_LEFT_M, 0, float(properties[5]), _TITLE_BLOCK_TOP_M
            ),
            measure_annotation=annotation_box,
            initial_measure_annotation=handoff.initial_measure,
            planning_headroom_m=0.0005,
            alignments=alignments,
            orderings=orderings,
            notes=notes,
        )
    finally:
        handoff.close()
    _telemetry.info(
        "diagnostic-only GTol+packing baseline",
        excluded_stage="datum_and_surface_finish_clearance",
        gtols=json.dumps(gtols),
        packing=json.dumps(asdict(report), default=lambda value: value.value),
    )
    if report.status in (NativeLayoutStatus.NO_FIT, NativeLayoutStatus.SEARCH_LIMIT):
        raise RuntimeError(f"coherent diagnostic baseline did not fit: {report.reason}")
    return report


def source_basic(adapter, source):
    if Path(adapter.currentModel.GetPathName()).resolve() != source:
        raise RuntimeError("coherent control has the wrong active source part")
    rows = {}
    for feature, names in SOURCE_BASIC_DIMENSIONS.items():
        for name in names:
            _, dim = _named_dimension(adapter, feature, name)
            value = float(dim.SystemValue)
            tolerance = int(dim.GetToleranceType())
            if not math.isfinite(value) or tolerance != 1:
                raise RuntimeError(
                    f"current source {name}@{feature} is not finite BASIC"
                )
            rows[f"{name}@{feature}"] = {
                "value_system": value,
                "tolerance_type": tolerance,
                "full_name": str(dim.FullName),
            }
    return rows


async def probe(adapter, source: Path, original_drawing: Path):
    directory = Path(
        tempfile.mkdtemp(prefix="coherent-lever-column-", dir=CAD_ROOT / "out/reports")
    )
    outputs = DrawingOutputs(
        slddrw=directory / f"{directory.name}.SLDDRW",
        pdf=directory / f"{directory.name}.pdf",
        png=directory / f"{directory.name}.png",
    )
    hashes = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (source, original_drawing)
    }
    report = {
        "source": str(source),
        "original_drawing": str(original_drawing),
        "outputs": {name: str(path) for name, path in asdict(outputs).items()},
        "baseline_scope": "real_recipe_with_explicit_gtol_plus_packing_only",
    }
    try:
        check(
            "open current lever source for exact BASIC baseline",
            await adapter.open_model(str(source)),
        )
        report["source_basic_before"] = source_basic(adapter, source)
        await build_lever(
            adapter, source=source, outputs=outputs, layout=diagnostic_layout
        )
        if Path(adapter.currentModel.GetPathName()).resolve() != outputs.slddrw:
            raise RuntimeError("real recipe did not save the unique diagnostic drawing")
        report["fresh_drawing_dimensions"] = drawing_dimensions(adapter, source)
        check(
            "close coherent diagnostic baseline", await adapter.close_model(save=False)
        )
        report["column_control"] = await probe_column(adapter, outputs.slddrw, None)
        check(
            "reopen current lever source for final BASIC witness",
            await adapter.open_model(str(source)),
        )
        report["source_basic_after"] = source_basic(adapter, source)
        if report["source_basic_before"] != report["source_basic_after"]:
            raise RuntimeError("coherent control changed source BASIC dimensions")
        report["outcome"] = "coherent_diagnostic_and_copied_column_completed"
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        try:
            if adapter.currentModel is not None:
                current = Path(adapter.currentModel.GetPathName()).resolve()
                if current in {source, outputs.slddrw}:
                    check(
                        "close owned coherent-control active document",
                        await adapter.close_model(save=False),
                    )
            report["source_unchanged"] = {
                str(path): hashlib.sha256(path.read_bytes()).hexdigest() == digest
                for path, digest in hashes.items()
            }
            if not all(report["source_unchanged"].values()):
                raise RuntimeError("coherent control changed original source bytes")
        finally:
            (directory / "coherent.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            _telemetry.info(f"coherent lever column observations: {directory}")
    return {"report": str(directory / "coherent.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--original-drawing", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source, drawing = (
        args.source.resolve(strict=True),
        args.original_drawing.resolve(strict=True),
    )
    if source.suffix.upper() != ".SLDPRT" or drawing.suffix.upper() != ".SLDDRW":
        raise ValueError(
            "coherent control requires current native part and original drawing"
        )
    if not args.worker:
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                str(source),
                "--original-drawing",
                str(drawing),
                "--worker",
            ],
            "coherent lever column control",
            log_stem="coherent-lever-column",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat")
    _telemetry.set_service("coherent-lever-column-probe")
    return run_build(lambda adapter: probe(adapter, source, drawing))


if __name__ == "__main__":
    raise SystemExit(main())
