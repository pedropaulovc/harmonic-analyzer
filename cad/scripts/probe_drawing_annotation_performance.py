"""Copy-only cProfile and per-dispatch timings of native annotation measurement.

Run through ``uv run python cad/scripts/probe_drawing_annotation_performance.py
DRAWING``. One uninstrumented and one profiled measurement of unchanged native
annotations distinguish COM cost from profiler overhead. Manual timers isolate
the invoking thread's makepy dispatch and returned-object wrapping costs; cProfile
may also capture background threads. Optional ``--scope layout-controls`` runs
small view-position, GTol-cardinality and outline observations afterwards.
No document is saved. Source drawing and referenced model hashes are guarded.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
import cProfile
from dataclasses import asdict
from enum import Enum
import hashlib
import io
import json
import math
import os
from pathlib import Path
import pstats
import shutil
import sys
import tempfile
import threading
import time
from typing import Any
from unittest.mock import patch

from _common import CAD_ROOT, _early_bound, check
from diagnostics._owned_native_documents import run_copy_diagnostic
from diagnostics._owned_native_session import require_owned_diagnostic_environment
from _drawing_annotation_bounds import annotation_box
from solidworks_mcp.adapters.com_variant import double_array
import _telemetry


class ProbeScope(Enum):
    MEASUREMENTS = "measurements"
    LAYOUT_CONTROLS = "layout-controls"


@contextmanager
def dispatch_timings(base: type, rows: dict, *, clock=time.perf_counter):
    """Time invoking-thread makepy dispatch without replacing any COM object."""
    original = base._ApplyTypes_
    thread_id = threading.get_ident()

    def timed(
        instance, dispid, flags, return_type, argument_types, member, clsid, *args
    ):
        if threading.get_ident() != thread_id:
            return original(
                instance,
                dispid,
                flags,
                return_type,
                argument_types,
                member,
                clsid,
                *args,
            )
        key = f"{type(instance).__name__}.{member}"
        started = clock()
        try:
            result = original(
                instance,
                dispid,
                flags,
                return_type,
                argument_types,
                member,
                clsid,
                *args,
            )
        except Exception:
            rows[key]["errors"] += 1
            raise
        finally:
            elapsed = clock() - started
            rows[key]["calls"] += 1
            rows[key]["seconds"] += elapsed
            rows[key]["max_seconds"] = max(rows[key]["max_seconds"], elapsed)
        return result

    with patch.object(base, "_ApplyTypes_", timed):
        yield


@contextmanager
def return_wrapping_timings(client, rows: dict, *, clock=time.perf_counter):
    """Measure pywin32's returned-dispatch wrapping on this thread only.

    This includes native type discovery and Python wrapper lookup/construction,
    not the native call that returned the object. It can overlap _ApplyTypes_
    timings, so the two categories must not be added together. No COM object or
    return value is substituted. Missing pywin32 internals fail explicitly.
    """
    original = client.__WrapDispatch
    thread_id = threading.get_ident()

    def timed(*args, **kwargs):
        if threading.get_ident() != thread_id:
            return original(*args, **kwargs)
        member = kwargs.get("userName", args[1] if len(args) > 1 else None)
        key = str(member or "<unnamed>")
        started = clock()
        try:
            return original(*args, **kwargs)
        except Exception:
            rows[key]["errors"] += 1
            raise
        finally:
            elapsed = clock() - started
            rows[key]["calls"] += 1
            rows[key]["seconds"] += elapsed
            rows[key]["max_seconds"] = max(rows[key]["max_seconds"], elapsed)

    with patch.object(client, "__WrapDispatch", timed):
        yield


def _dispatch_rows():
    return defaultdict(
        lambda: {"calls": 0, "errors": 0, "seconds": 0.0, "max_seconds": 0.0}
    )


def _profile_report(profiler: cProfile.Profile) -> dict[str, Any]:
    stats = pstats.Stats(profiler)
    functions = [
        {
            "file": file,
            "line": line,
            "function": name,
            "primitive_calls": primitive,
            "calls": calls,
            "self_seconds": own,
            "cumulative_seconds": cumulative,
        }
        for (file, line, name), (
            primitive,
            calls,
            own,
            cumulative,
            _callers,
        ) in stats.stats.items()
    ]
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(50)
    return {
        "functions": sorted(
            functions, key=lambda row: row["cumulative_seconds"], reverse=True
        ),
        "summary": stream.getvalue(),
    }


def _measure(adapter: Any, annotations: list[Any]) -> tuple[list[Any], dict[str, Any]]:
    results, timings = [], []
    started = time.perf_counter()
    for annotation in annotations:
        item_started = time.perf_counter()
        result = annotation_box(adapter, annotation)
        timings.append(
            {
                "name": result.name,
                "kind": result.kind,
                "seconds": time.perf_counter() - item_started,
            }
        )
        results.append(result)
    return results, {"seconds": time.perf_counter() - started, "annotations": timings}


def _small_controls(adapter: Any, views: list[Any]) -> dict[str, Any]:
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    app = _early_bound(adapter.swApp, "ISldWorks")
    bank_view = next(
        (view for view in views if len(tuple(view.GetAnnotationsByType(5) or ())) >= 3),
        None,
    )
    view = bank_view or views[0]
    original = tuple(view.Position)
    target = (original[0] + 0.011, original[1] - 0.007)
    report: dict[str, Any] = {
        "view": view.GetName2(),
        "original": original,
        "target": target,
        "position_trials": [],
    }
    try:
        for variant in (
            "bare_tuple_property",
            "typed_array_property",
            "typed_SetViewPosition",
        ):
            row: dict[str, Any] = {"variant": variant}
            try:
                if variant == "bare_tuple_property":
                    view.Position = target
                elif variant == "typed_array_property":
                    view.Position = double_array(target)
                else:
                    row["return"] = view.SetViewPosition(double_array(target), False)
                row["actual"] = tuple(view.Position)
                row["distance_to_target_m"] = math.dist(row["actual"], target)
            except Exception as error:
                row["error"] = repr(error)
            finally:
                report["position_trials"].append(row)
                if (
                    not view.SetViewPosition(double_array(original), False)
                    or math.dist(tuple(view.Position), original) > 1e-8
                ):
                    raise RuntimeError(
                        "position control could not restore original copy view"
                    )
        report["gtol_cardinality"] = []
        if bank_view is None:
            report["gtol_cardinality_exclusion"] = (
                "no view contains at least three GTols"
            )
            return report
        gtols = tuple(
            _early_bound(item, "IAnnotation")
            for item in bank_view.GetAnnotationsByType(5)
        )
        for count in (2, 3):
            if not drawing.ActivateView(bank_view.GetName2()):
                raise RuntimeError("cannot activate GTol control view")
            model.ClearSelection2(True)
            if not all(item.Select2(True, 0) for item in gtols[:count]):
                raise RuntimeError("GTol cardinality selection rejected")
            actual_count = selection.GetSelectedObjectCount2(-1)
            if actual_count != count:
                raise RuntimeError("GTol cardinality selection count differs")
            report["gtol_cardinality"].append(
                {
                    "count": count,
                    "space_down_317": app.IsCommandEnabled(317),
                    "align_left_307": app.IsCommandEnabled(307),
                }
            )
        model.ClearSelection2(True)
        annotation = gtols[0]
        anchor = tuple(annotation.GetPosition())
        outline = tuple(bank_view.GetOutline())
        displaced = (outline[2] + 0.08, outline[3] + 0.06, anchor[2])
        try:
            if not annotation.SetPosition2(*displaced):
                raise RuntimeError("GTol outline control position rejected")
            if not model.EditRebuild3():
                raise RuntimeError("GTol outline control rebuild failed")
            report["outline_control"] = {
                "before": outline,
                "after": tuple(bank_view.GetOutline()),
                "annotation_original": anchor,
                "annotation_requested": displaced,
                "annotation_actual": tuple(annotation.GetPosition()),
            }
        finally:
            if (
                not annotation.SetPosition2(*anchor)
                or not model.EditRebuild3()
                or math.dist(tuple(annotation.GetPosition()), anchor) > 1e-8
            ):
                raise RuntimeError("GTol outline control could not restore annotation")
        return report
    finally:
        model.ClearSelection2(True)


def scope_controls(adapter, views, scope):
    if scope is ProbeScope.MEASUREMENTS:
        return {"status": "not_requested"}
    if scope is ProbeScope.LAYOUT_CONTROLS:
        return _small_controls(adapter, views)
    raise ValueError("annotation profile requires an explicit probe scope")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument(
        "--scope",
        choices=[scope.value for scope in ProbeScope],
        default=ProbeScope.MEASUREMENTS.value,
    )
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    scope = ProbeScope(args.scope)
    source = args.drawing.resolve(strict=True)
    if not args.worker:
        require_owned_diagnostic_environment()
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                str(source),
                "--scope",
                scope.value,
                "--worker",
            ],
            "annotation measurement profile",
            log_stem="annotation-measurement-profile",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat")

    async def probe(adapter: Any) -> dict[str, str]:
        import win32com.client

        root = CAD_ROOT / "out/reports"
        root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="annotation-profile-", dir=root))
        adapter.ownership.register_directory(folder)
        adapter.ownership.register_source(source)
        copy = folder / f"{folder.name}-{source.name}"
        shutil.copy2(source, copy)
        hashes = {source: hashlib.sha256(source.read_bytes()).hexdigest()}
        report: dict[str, Any] = {
            "source": str(source),
            "copy": str(copy),
            "scope": scope.value,
            "stage": "open",
            "helper_sha256": hashlib.sha256(
                (CAD_ROOT / "scripts/_drawing_annotation_bounds.py").read_bytes()
            ).hexdigest(),
        }
        try:
            check("open unique profile copy", await adapter.open_model(str(copy)))
            if Path(adapter.currentModel.GetPathName()).resolve() != copy:
                raise RuntimeError("SolidWorks opened the wrong profile copy")
            drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
            views = [
                _early_bound(view, "IView")
                for sheet in drawing.GetViews() or ()
                for view in sheet[1:]
            ]
            annotations, seen = [], {}
            report["exclusions"] = []
            for view in views:
                reference = Path(view.ReferencedDocument.GetPathName()).resolve(
                    strict=True
                )
                hashes[reference] = hashlib.sha256(reference.read_bytes()).hexdigest()
                for raw in view.GetAnnotations() or ():
                    annotation = _early_bound(raw, "IAnnotation")
                    if annotation.OwnerType == 2:
                        report["exclusions"].append(
                            {
                                "name": annotation.GetName(),
                                "reason": "template annotation",
                            }
                        )
                        continue
                    key = (
                        annotation.OwnerType,
                        view.GetName2(),
                        annotation.GetName(),
                        annotation.GetType(),
                    )
                    if key in seen:
                        if int(adapter.swApp.IsSame(annotation, seen[key])) != 1:
                            raise RuntimeError(
                                "profile annotation inventory is ambiguous"
                            )
                        continue
                    seen[key] = annotation
                    annotations.append(annotation)
            if not annotations:
                raise RuntimeError("profile contains no manufacturing annotations")
            report["stage"] = "uninstrumented"
            expected, report["uninstrumented"] = _measure(adapter, annotations)
            report["stage"] = "profiled"
            profiler, dispatch, wrapping = (
                cProfile.Profile(),
                _dispatch_rows(),
                _dispatch_rows(),
            )
            with (
                dispatch_timings(win32com.client.DispatchBaseClass, dispatch),
                return_wrapping_timings(win32com.client, wrapping),
            ):
                try:
                    profiler.enable()
                    measured, report["profiled"] = _measure(adapter, annotations)
                finally:
                    profiler.disable()
                    profiler.dump_stats(str(folder / "annotation-measurement.pstats"))
                    report["cprofile"] = _profile_report(profiler)
                    report["dispatch"] = sorted(
                        (
                            {"member": name, **values}
                            for name, values in dispatch.items()
                        ),
                        key=lambda row: row["seconds"],
                        reverse=True,
                    )
                    report["main_thread_return_wrapping"] = sorted(
                        (
                            {"member": name, **values}
                            for name, values in wrapping.items()
                        ),
                        key=lambda row: row["seconds"],
                        reverse=True,
                    )
                    report["manual_timer_scope"] = {
                        "thread_id": threading.get_ident(),
                        "categories_overlap": [
                            "dispatch",
                            "main_thread_return_wrapping",
                        ],
                        "cprofile_threads": "not_isolated",
                    }
            if expected != measured:
                raise RuntimeError(
                    "profiling changed measured native annotation bounds"
                )
            report["bounds"] = [asdict(value) for value in measured]
            report["stage"] = "small_controls"
            report["controls"] = scope_controls(adapter, views, scope)
            report["stage"] = "passed"
        except Exception as error:
            report["error"] = repr(error)
            raise
        finally:
            try:
                await adapter.close_owned_documents()
                report["source_unchanged"] = {
                    str(path): hashlib.sha256(path.read_bytes()).hexdigest() == digest
                    for path, digest in hashes.items()
                }
                if not all(report["source_unchanged"].values()):
                    raise RuntimeError("measurement profile changed source bytes")
            finally:
                (folder / "profile.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
                _telemetry.info(f"annotation measurement profile: {folder}")
        return {"report": str(folder / "profile.json")}

    _telemetry.set_service("drawing-annotation-performance-probe")
    return run_copy_diagnostic(probe)


if __name__ == "__main__":
    raise SystemExit(main())
