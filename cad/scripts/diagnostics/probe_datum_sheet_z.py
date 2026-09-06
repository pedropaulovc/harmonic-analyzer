"""Compare datum SetPosition2 sheet XY with returned Z versus zero, on copies.

The official IAnnotation.SetPosition2/GetPosition docs describe sheet-origin
coordinates but also permit datum constraints to clamp a requested position.
This diagnostic distinguishes True from exact XY; it does not assume either Z
form is valid. Run with the saved cone-gear.SLDDRW and rocker-arm.SLDDRW paths.
Each of the four datums gets a nearest measured outboard target and TWO fresh
byte-copy trials. No original drawing is opened; source hashes are guarded.
Restoration is observed, not assumed to succeed and not used as another seed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
from diagnostics._owned_native_documents import run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from _drawing_annotation_bounds import annotation_box, _native_snapshot  # noqa: E402
import _drawing_native_callouts as callouts  # noqa: E402
from _drawing_view_packing import Rect  # noqa: E402
from diagnostics.probe_drawing_attachments import geometry, views  # noqa: E402
from diagnostics.probe_native_model_pmi import file_digest, render_pdf_png  # noqa: E402
import _telemetry  # noqa: E402

EXPECTED_LABELS = {"cone-gear": {"A"}, "rocker-arm": {"A", "B", "C"}}
EPSILON = 1e-8


def z_variants(xy, original_z):
    if len(xy) != 2 or not all(math.isfinite(v) for v in (*xy, original_z)):
        raise ValueError("datum target needs finite sheet XY and native Z")
    return (("returned_z", (*xy, original_z)), ("sheet_zero", (*xy, 0.0)))


def capture(adapter, view, annotation):
    measured = annotation_box(adapter, annotation)
    symbol = callouts._read_symbol(adapter, view, annotation, lambda *_: measured)
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    return symbol, {
        "geometry": tuple(
            geometry(e, t) for e, t in zip(symbol.entities, symbol.entity_types)
        ),
        "measurement": asdict(measured),
        "native": asdict(_native_snapshot(annotation, extension)),
    }


def serial(symbol, data):
    return {
        "name": symbol.name,
        "kind": symbol.kind,
        "position": symbol.position,
        "body": symbol.body.bounds,
        "properties": symbol.properties,
        "text": symbol.text,
        "format": symbol.format,
        "attachment_types": symbol.entity_types,
        **data,
    }


def assert_witness(app, before, before_data, after, after_data):
    delta = tuple(b - a for a, b in zip(before.position[:2], after.position[:2]))
    predicted = replace(
        before,
        position=after.position,
        body=before.body.translated(delta),
        frame=before.frame.translated(delta) if before.frame is not None else None,
    )
    callouts._final_symbol(app, before, predicted, after)
    if before_data["geometry"] != after_data["geometry"]:
        raise RuntimeError("datum controlled geometry changed")


def run_trial(
    adapter, view, annotation, target, report, *, capture=capture, export=None
):
    """One mutation and one restore; native failures stay explicit in evidence."""
    before, before_data = capture(adapter, view, annotation)
    report["before"] = serial(before, before_data)
    failures = []

    def observe(stage, requested):
        report[stage] = {"requested": requested}
        returned = bool(annotation.SetPosition2(*requested))
        report[stage]["returned"] = returned
        actual, data = capture(adapter, view, annotation)
        distance = math.dist(requested[:2], actual.position[:2])
        report[stage] = {
            "requested": requested,
            "returned": returned,
            "actual": actual.position,
            "xy_error_m": distance,
            "placement": "rejected"
            if not returned
            else "exact_xy"
            if distance <= EPSILON
            else "clamped_xy",
            "state": serial(actual, data),
        }
        assert_witness(adapter.swApp, before, before_data, actual, data)
        return actual, data

    try:
        actual, data = observe("attempt", target)
        if export is not None:
            report["export"] = export()
            saved, saved_data = capture(adapter, view, annotation)
            report["after_export"] = serial(saved, saved_data)
            assert_witness(adapter.swApp, actual, data, saved, saved_data)
            if math.dist(actual.position[:2], saved.position[:2]) > EPSILON:
                raise RuntimeError("datum export changed the observed XY")
    except Exception as error:
        report["attempt_error"] = repr(error)
        failures.append(error)
    finally:
        try:
            observe("restore", before.position)
        except Exception as error:
            report["restore_error"] = repr(error)
            failures.append(error)
    if failures:
        raise RuntimeError("; ".join(str(error) for error in failures))


def guard_sources(report):
    report["source_hashes_after"] = {
        name: file_digest(Path(name)) for name in report["source_hashes"]
    }
    if report["source_hashes_after"] != report["source_hashes"]:
        raise RuntimeError("datum Z diagnostic changed an original drawing or part")


def inventory(adapter):
    result = {}
    for view_key, view in views(adapter.currentModel).items():
        for raw in view.GetAnnotationsByType(2) or ():
            annotation = _early_bound(raw, "IAnnotation")
            symbol, data = capture(adapter, view, annotation)
            key = (view_key, symbol.name)
            if key in result:
                raise RuntimeError("duplicate native datum identity")
            result[key] = (view, symbol, data)
    return result


def baseline_matches(expected, actual):
    for field in (
        "name",
        "kind",
        "properties",
        "text",
        "format",
        "attachment_types",
        "geometry",
    ):
        if expected[field] != actual[field]:
            raise RuntimeError(f"fresh datum copy changed baseline {field}")
    for field in ("position", "body"):
        if len(expected[field]) != len(actual[field]) or any(
            abs(a - b) > EPSILON for a, b in zip(expected[field], actual[field])
        ):
            raise RuntimeError(f"fresh datum copy changed baseline {field}")


async def probe(adapter, sources, directory):
    from diagnostics._owned_native_documents import save_drawing

    adapter.ownership.register_directory(directory)
    for source in sources:
        adapter.ownership.register_source(source)

    report = {
        "sources": [str(p) for p in sources],
        "source_hashes": {},
        "drawings": [],
        "errors": [],
    }
    report_path = directory / "datum-sheet-z.json"

    async def close():
        await adapter.close_owned_documents()

    async def open_copy(source, stem):
        copy = directory / f"{directory.name}-{stem}.SLDDRW"
        shutil.copy2(source, copy)
        check("open unique datum Z copy", await adapter.open_model(str(copy)))
        if Path(adapter.currentModel.GetPathName()).resolve() != copy:
            raise RuntimeError("opened native drawing is not the requested unique copy")
        return copy

    def export(stem):
        output = directory / f"{directory.name}-{stem}-observed.SLDDRW"
        pdf, png = output.with_suffix(".pdf"), output.with_suffix(".png")
        save_drawing(adapter, str(output), pdf_path=str(pdf))
        if not pdf.is_file():
            raise RuntimeError("native datum export produced no PDF")
        render_pdf_png(pdf, png)
        return {"drawing": str(output), "pdf": str(pdf), "png": str(png)}

    try:
        for source in sources:
            # This bounded pilot layout has exactly one same-stem part. Hash it
            # before opening even a drawing copy; verify native references below.
            part = (source.parent.parent / "sldprt" / f"{source.stem}.SLDPRT").resolve(
                strict=True
            )
            for original in (source, part):
                report["source_hashes"][str(original)] = file_digest(original)
            await open_copy(source, f"{source.stem}-baseline")
            for view in views(adapter.currentModel).values():
                if Path(view.ReferencedDocument.GetPathName()).resolve() != part:
                    raise RuntimeError(
                        "pilot drawing references an unguarded source part"
                    )
            baseline = inventory(adapter)
            labels = [row.properties[0] for _, row, _ in baseline.values()]
            if set(labels) != EXPECTED_LABELS[source.stem] or len(labels) != len(
                set(labels)
            ):
                raise RuntimeError(
                    f"unexpected {source.stem} datum label inventory: {labels}"
                )
            drawing_record = {
                "source": str(source),
                "before_export": export(f"{source.stem}-baseline"),
                "trials": [],
            }
            report["drawings"].append(drawing_record)
            plans = []
            for key, (view, row, data) in baseline.items():
                outline = Rect(*view.GetOutline())
                candidates = callouts.placement_candidates(
                    callouts._placement_body(row), outline, ()
                )
                selected = candidates[0]
                xy = tuple(a + b for a, b in zip(row.position[:2], selected.delta))
                plans.append(
                    (
                        key,
                        row.properties[0],
                        serial(row, data),
                        xy,
                        selected.direction.value,
                    )
                )
            await close()
            for key, label, seed, xy, direction in plans:
                for variant, target in z_variants(xy, seed["position"][2]):
                    stem = f"{source.stem}-{label}-{variant}"
                    trial = {
                        "datum": label,
                        "view": key[0],
                        "annotation": key[1],
                        "variant": variant,
                        "direction": direction,
                    }
                    drawing_record["trials"].append(trial)
                    try:
                        trial["copy"] = str(await open_copy(source, stem))
                        bank = inventory(adapter)
                        if bank.keys() != baseline.keys():
                            raise RuntimeError("fresh copy changed datum inventory")
                        view, row, data = bank[key]
                        baseline_matches(seed, serial(row, data))
                        run_trial(
                            adapter,
                            view,
                            row.annotation,
                            target,
                            trial,
                            export=lambda: export(stem),
                        )
                    except Exception as error:
                        trial["error"] = repr(error)
                        report["errors"].append(f"{stem}: {error}")
                    finally:
                        await close()
    except Exception as error:
        report["operation_error"] = repr(error)
        raise
    finally:
        try:
            await close()
        finally:
            try:
                guard_sources(report)
            finally:
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                _telemetry.info(f"datum sheet-Z observations: {report_path}")
    if report["errors"]:
        raise RuntimeError(
            f"datum Z witness failed; complete copy-only evidence: {report_path}"
        )
    return {"report": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path, nargs="+")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    sources = [path.resolve(strict=True) for path in args.drawing]
    if any(
        p.suffix.upper() != ".SLDDRW" or p.stem not in EXPECTED_LABELS for p in sources
    ):
        raise ValueError(
            "this control accepts saved cone-gear and rocker-arm drawings only"
        )
    if not args.worker:
        require_owned_diagnostic_environment()
        sys.path.insert(0, str(ROOT))
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                *map(str, sources),
                "--worker",
            ],
            "native datum sheet-Z control",
            com=True,
            log_stem="datum-sheet-z-probe",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("worker requires the parent COM seat lock")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="datum-sheet-z-", dir=reports))
    return run_copy_diagnostic(lambda adapter: probe(adapter, sources, directory))


if __name__ == "__main__":
    raise SystemExit(main())
