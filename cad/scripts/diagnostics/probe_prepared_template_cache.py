"""Owned blank-drawing control for the opt-in production template cache.

One normal setup, one prepared MISS and one HIT; no part/model opens, model views,
trial native saves or model-linked-title acceptance. Optional printed-format
comparison exports PDF/PNG for each trial without saving the drawing. Only the production
MISS saves one owned DRWDOT. Requires frozen source, AUTOSTART=0, remote cache off,
an explicit existing SW PID and the parent machine-global COM seat.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from enum import StrEnum
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

import _drawing_sheet_setup as sheet_setup  # noqa: E402

from _common import _early_bound  # noqa: E402
import _drawing_common as common  # noqa: E402
import _drawing_prepared_template as prepared  # noqa: E402
import _drawing_template_viewport as viewports  # noqa: E402
from _drawing_template_defaults import compare_defaults, snapshot_defaults  # noqa: E402
import _telemetry  # noqa: E402
from diagnostics import _owned_native_documents as ownership  # noqa: E402
from diagnostics import _owned_native_session as session  # noqa: E402
from diagnostics import _prepared_frame_control as frames  # noqa: E402
from diagnostics import probe_retained_drawing_export as printed  # noqa: E402


class PrintedFormat(StrEnum):
    SKIP = "skip"
    COMPARE = "compare"


class Viewport(StrEnum):
    NORMAL = "normal"
    CAPTURED = "captured"


def require_environment(expected_pid):
    session.require_owned_diagnostic_environment()
    if type(expected_pid) is not int or expected_pid <= 0:
        raise RuntimeError(
            "prepared-template probe requires an explicit positive SW PID"
        )
    if os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID") != str(expected_pid):
        raise RuntimeError("expected PID must equal HARMONIC_DIAGNOSTIC_SW_PID")
    if os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off":
        raise RuntimeError("prepared-template probe requires remote cache off")


def runtime_inputs(adapter, spec):
    files = [
        Path(__file__).resolve(),
        Path(ownership.__file__).resolve(),
        Path(session.__file__).resolve(),
        ROOT / "dodo.py",
        Path(printed.__file__).resolve(),
        Path(viewports.__file__).resolve(),
        Path(frames.__file__).resolve(),
    ]
    return {
        "preparation": prepared.preparation_inputs(adapter, spec),
        "diagnostic_sources": {
            path.relative_to(ROOT).as_posix(): prepared._sha(path) for path in files
        },
    }


@contextmanager
def timed(row, name):
    start = time.perf_counter()
    try:
        yield
    finally:
        row[name] = time.perf_counter() - start


def cache_artifacts(entry):
    expected = {"prepared.DRWDOT", "manifest.json", "receipt.json"}
    actual = {path.name for path in entry.directory.iterdir()}
    if actual != expected | {"ownership.json"}:
        raise RuntimeError(f"unexpected published template-cache inventory: {actual}")
    return {
        str(entry.directory / name): prepared._sha(entry.directory / name)
        for name in sorted(expected)
    }


def blank_witness(adapter):
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    drawing = _early_bound(model, "IDrawingDoc")
    sheets = tuple(drawing.GetViews() or ())
    if (
        int(model.GetType()) != 3
        or str(model.GetPathName())
        or len(sheets) != 1
        or len(tuple(sheets[0] or ())) != 1
    ):
        raise RuntimeError(
            "trial must be an unsaved one-sheet drawing without model views"
        )
    return {"kind": 3, "path": "", "sheet_count": 1, "model_view_count": 0}


def printed_witness(adapter, directory):
    """Production PDF export plus exact pixels and PDF glyph positions, not CAD edits."""
    import pypdfium2 as pdfium

    pdf, png = directory / "format.pdf", directory / "format.png"
    if pdf.exists() or png.exists():
        raise RuntimeError("printed format needs fresh PDF/PNG targets")
    printed.export_pdf_only(adapter, pdf)
    common.render_pdf_png(pdf, png)
    with pdfium.PdfDocument(str(pdf)) as document:
        if len(document) != 1:
            raise RuntimeError("blank format export must have one PDF page")
        page = document[0]
        textpage = page.get_textpage()
        glyphs = [
            {
                "text": textpage.get_text_range(i, 1),
                "box_pt": list(textpage.get_charbox(i)),
            }
            for i in range(textpage.count_chars())
        ]
        if not glyphs:
            raise RuntimeError("blank format positive control has no PDF text")
        page_size = list(page.get_size())
    return {
        "pdf": str(pdf),
        "png": str(png),
        "sha256": {"pdf": prepared._sha(pdf), "png": prepared._sha(png)},
        "page_size_pt": page_size,
        "glyphs": glyphs,
        "scope": "300-DPI full-sheet pixels and exact PDF text glyphs; not raw vector-command equality",
    }


def compare_printed(before, after):
    if (
        before["page_size_pt"] != after["page_size_pt"]
        or before["glyphs"] != after["glyphs"]
    ):
        raise RuntimeError("prepared blank PDF page or exact text glyphs differ")
    for snapshot in (before, after):
        for kind in ("pdf", "png"):
            if prepared._sha(snapshot[kind]) != snapshot["sha256"][kind]:
                raise RuntimeError("printed format artifact changed after capture")
    delta = printed.compare_png(Path(before["png"]), Path(after["png"]))
    if delta["changed_pixel_count"]:
        raise RuntimeError(f"prepared blank printed format differs: {delta}")
    return delta


async def trial(
    adapter,
    spec,
    entry,
    directory,
    row,
    expected,
    checkpoint,
    *,
    printed_format=PrintedFormat.SKIP,
    printed_expected=None,
    viewport=Viewport.NORMAL,
    captured_viewport=None,
):
    errors = []
    row.update(status="running", phase="setup")
    start = time.perf_counter()
    checkpoint()
    try:
        with adapter.ownership.creating_document(
            ownership.DocumentKind.DRAWING, directory / "unsaved.SLDDRW"
        ):
            with (
                timed(row, "setup_seconds"),
                _telemetry.span(
                    "diagnostic.prepared_template.setup", variant=row["variant"]
                ),
            ):
                if entry is None:
                    sheet_setup.new_project_drawing(
                        adapter, scale=spec.scale, decimals=spec.decimals
                    )
                if entry is not None:
                    prepared.inherited_drawing(adapter, entry)
        if viewport is Viewport.CAPTURED:
            row["phase"] = "viewport"
            adapter.ownership.assert_current_owned()
            if captured_viewport is None:
                if entry is not None:
                    raise RuntimeError(
                        "prepared trial needs the normal trial's captured viewport"
                    )
                row["viewport"] = viewports.capture(adapter.currentModel)
            else:
                control = row["viewport_control"] = {}
                with timed(row, "viewport_restore_seconds"):
                    viewports.restore(
                        adapter.swApp, adapter.currentModel, captured_viewport, control
                    )
                row["viewport"] = control["after"]
        row["phase"] = "raw_defaults"
        checkpoint()
        with timed(row, "witness_seconds"):
            row["blank"] = blank_witness(adapter)
            row["defaults"] = snapshot_defaults(adapter, spec)
            if expected is not None:
                compare_defaults(expected, row["defaults"])
        if printed_format is PrintedFormat.COMPARE:
            row["phase"] = "printed_format"
            checkpoint()
            with timed(row, "printed_seconds"):
                row["printed"] = printed_witness(adapter, directory)
                if printed_expected is not None:
                    row["printed_delta"] = compare_printed(
                        printed_expected, row["printed"]
                    )
            with timed(row, "post_print_witness_seconds"):
                row["after_print_defaults"] = snapshot_defaults(adapter, spec)
                compare_defaults(row["defaults"], row["after_print_defaults"])
                row["after_print_blank"] = blank_witness(adapter)
                if viewport is Viewport.CAPTURED:
                    row["after_print_viewport"] = viewports.capture(
                        adapter.currentModel
                    )
                    if row["after_print_viewport"] != row["viewport"]:
                        raise RuntimeError(
                            "printed trial changed the exact captured viewport"
                        )
    except Exception as error:
        row.update(error=repr(error), failed_phase=row["phase"])
        errors.append(error)
    finally:
        row["phase"] = "cleanup"
        checkpoint()
        try:
            with timed(row, "cleanup_seconds"):
                await adapter.close_owned_documents()
        except Exception as error:
            row["cleanup_error"] = repr(error)
            errors.append(error)
        row.update(
            status="failed" if errors else "passed",
            phase="finished",
            elapsed_seconds=time.perf_counter() - start,
        )
        checkpoint()
    if errors:
        raise ExceptionGroup("blank template trial/cleanup failed", errors)


async def probe(
    adapter,
    spec,
    report_root,
    expected_pid,
    *,
    printed_format=PrintedFormat.SKIP,
    viewport=Viewport.NORMAL,
    frame_policy=frames.FramePolicy.UNCHANGED,
    failure_receipt=None,
    failure_receipt_sha256=None,
):
    if not isinstance(printed_format, PrintedFormat):
        raise ValueError("printed format requires an explicit policy enum")
    if not isinstance(viewport, Viewport):
        raise ValueError("viewport requires an explicit policy enum")
    if frame_policy is frames.FramePolicy.MEASURED_RESTORE and (
        viewport is not Viewport.CAPTURED or printed_format is not PrintedFormat.COMPARE
    ):
        raise ValueError(
            "measured_restore requires captured viewport and printed comparison"
        )
    original = sheet_setup.PROJECT_DRWDOT.resolve(strict=True)
    failure_pin = frames.failure_input(
        frame_policy, spec, original, failure_receipt, failure_receipt_sha256
    )
    require_environment(expected_pid)
    if int(adapter.swApp.GetProcessID()) != expected_pid:
        raise RuntimeError(
            "running native PID differs from the explicitly approved PID"
        )
    if (
        failure_pin is not None
        and str(adapter.swApp.RevisionNumber()) != failure_pin["solidworks_revision"]
    ):
        raise RuntimeError("frame control native revision differs from failure receipt")
    report_root.mkdir(parents=True, exist_ok=True)
    directory = Path(
        tempfile.mkdtemp(prefix="prepared-template-cache-", dir=report_root)
    )
    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(original)
    if failure_pin is not None:
        adapter.ownership.register_source(Path(failure_pin["receipt"]["path"]))
    cache_root = directory / "cache"
    pinned = runtime_inputs(adapter, spec)
    original_sha = prepared._sha(original)
    report = {
        "status": "running",
        "phase": "normal_setup",
        "expected_pid": expected_pid,
        "revision": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        ).stdout.strip(),
        "scope": "blank_setup_cache_miss_hit_only",
        "printed_format": printed_format.value,
        "viewport": viewport.value,
        "frame_policy": frame_policy.value,
        "frame_failure_input": failure_pin,
        "frame_control": {},
        "spec": asdict(spec),
        "source_template": {"path": str(original), "sha256": original_sha},
        "runtime_inputs": pinned,
        "cache_root": str(cache_root),
        "accessors": [],
        "trials": [],
        "operation_scopes": [],
        "guards": [],
        "timing_scope": "accessor timing includes its input/hash/receipt work and, on miss, native preparation/witness/cleanup; setup timer includes the inner factory and its native adapter assignment; outer ownership checks, full raw witnesses, cleanup and explicit guards are separately timed",
        "claim_scope": "one observed blank setup/miss/hit sequence and raw-default agreement; not ABBA, full sheet-format sketch/logo preservation, end-to-end speedup, model-linked title acceptance or conflict probability",
    }
    report_path = directory / "measurements.json"
    cached = {}
    pending_directories = set()
    errors = []
    controls = ExitStack()

    def checkpoint():
        report_path.write_text(
            json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
        )

    def guard(phase):
        row = {"phase": phase, "status": "running"}
        report["guards"].append(row)
        try:
            with timed(row, "seconds"):
                frames.require_failure_input_unchanged(failure_pin)
                row["source_sha256"] = prepared._sha(original)
                row["runtime_inputs"] = runtime_inputs(adapter, spec)
                row["cached_artifacts"] = {path: prepared._sha(path) for path in cached}
                if (
                    row["source_sha256"] != original_sha
                    or row["runtime_inputs"] != pinned
                    or row["cached_artifacts"] != cached
                ):
                    raise RuntimeError("immutable template/runtime/cache input changed")
            row["status"] = "passed"
        except Exception as error:
            row.update(status="failed", error=repr(error))
            raise
        finally:
            checkpoint()

    @contextmanager
    def operation_context(kind, path):
        path = Path(path).resolve()
        if not path.is_relative_to(cache_root.resolve()):
            raise RuntimeError("preparation requested a path outside this run's cache")
        if path.parent not in pending_directories:
            adapter.ownership.register_directory(path.parent)
            pending_directories.add(path.parent)
        row = {"operation": kind.value, "path": str(path), "status": "entered"}
        report["operation_scopes"].append(row)
        checkpoint()
        context = (
            adapter.ownership.creating_document(ownership.DocumentKind.DRAWING, path)
            if kind is prepared.TemplateOperation.CREATE
            else adapter.ownership.saving_as(path)
            if kind is prepared.TemplateOperation.SAVE_AS
            else None
        )
        if context is None:
            raise RuntimeError("unknown preparation ownership operation")
        try:
            with context:
                yield
                if (
                    viewport is Viewport.CAPTURED
                    and kind is prepared.TemplateOperation.CREATE
                ):
                    adapter.ownership.assert_current_owned()
                    control = row["viewport_control"] = {}
                    with timed(row, "viewport_restore_seconds"):
                        viewports.restore(
                            adapter.swApp,
                            adapter.currentModel,
                            report["captured_viewport"],
                            control,
                        )
            row["status"] = "completed"
        except Exception as error:
            row.update(status="failed", error=repr(error))
            raise
        finally:
            checkpoint()

    async def run_trial(variant, entry, expected):
        trial_dir = directory / variant
        trial_dir.mkdir()
        adapter.ownership.register_directory(trial_dir)
        row = {"variant": variant}
        report["trials"].append(row)
        options = {}
        if viewport is Viewport.CAPTURED:
            options.update(
                viewport=viewport, captured_viewport=report.get("captured_viewport")
            )
        if printed_format is PrintedFormat.COMPARE:
            options.update(
                {
                    "printed_format": printed_format,
                    "printed_expected": report["trials"][0].get("printed"),
                }
            )
        await trial(
            adapter, spec, entry, trial_dir, row, expected, checkpoint, **options
        )
        guard(variant + "_after_cleanup")
        return row["defaults"]

    checkpoint()
    try:
        controls.enter_context(
            frames.intercept(adapter, frame_policy, report["frame_control"])
        )
        guard("before_normal")
        normal = await run_trial("normal", None, None)
        if viewport is Viewport.CAPTURED:
            report["captured_viewport"] = report["trials"][0]["viewport"]
        for access_kind in ("miss", "hit"):
            report["phase"] = access_kind
            guard("before_" + access_kind)
            start_scopes = len(report["operation_scopes"])
            row = {"kind": access_kind, "status": "running"}
            report["accessors"].append(row)
            checkpoint()
            try:
                with timed(row, "seconds"):
                    entry = await prepared.prepare_project_drawing_template(
                        adapter,
                        scale=spec.scale,
                        decimals=spec.decimals,
                        cache_root=cache_root,
                        operation_context=operation_context,
                    )
                row.update(
                    key=entry.key, path=str(entry.path), directory=str(entry.directory)
                )
                if access_kind == "miss":
                    if len(pending_directories) != 1:
                        raise RuntimeError(
                            "miss did not use exactly one owned pending directory"
                        )
                    with timed(row, "relocation_seconds"):
                        adapter.ownership.relocate_prepared_template_directory(
                            next(iter(pending_directories)),
                            entry,
                        )
                observed = [
                    item["operation"]
                    for item in report["operation_scopes"][start_scopes:]
                ]
                expected = (
                    ["create", "save_as", "create"] if access_kind == "miss" else []
                )
                if observed != expected:
                    raise RuntimeError(
                        f"{access_kind} did not execute the exact expected preparation scopes"
                    )
                after = cache_artifacts(entry)
                if cached and after != cached:
                    raise RuntimeError(
                        "cache hit changed its artifacts or selected another entry"
                    )
                cached = after
                row["artifacts"] = after
                if {path.name for path in cache_root.iterdir()} != {entry.key}:
                    raise RuntimeError(
                        "cache root contains unexpected/unfinished entries"
                    )
                native_receipt = json.loads(
                    (entry.directory / "receipt.json").read_text(encoding="utf-8")
                )
                with timed(row, "normal_comparison_seconds"):
                    compare_defaults(normal, native_receipt["before"])
                    compare_defaults(normal, native_receipt["after"])
                row["status"] = "passed"
            except Exception as error:
                row.update(status="failed", error=repr(error))
                raise
            finally:
                checkpoint()
            guard("after_" + access_kind)
            await run_trial("prepared_" + access_kind, entry, normal)
    except Exception as error:
        report["error"] = repr(error)
        errors.append(error)
    finally:
        report["phase"] = "final_cleanup"
        checkpoint()
        try:
            with timed(report, "final_cleanup_seconds"):
                await adapter.close_owned_documents()
        except Exception as error:
            report["cleanup_error"] = repr(error)
            errors.append(error)
        try:
            controls.close()
        except Exception as error:
            report["frame_control_cleanup_error"] = repr(error)
            errors.append(error)
        try:
            guard("finally")
        except Exception as error:
            report["final_guard_error"] = repr(error)
            errors.append(error)
        report.update(status="failed" if errors else "passed", phase="finished")
        checkpoint()
    if errors:
        raise ExceptionGroup("prepared-template cache control failed", errors)
    return {
        "measurements": str(report_path),
        "ownership": str(directory / "ownership.json"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-pid", type=int, required=True)
    parser.add_argument("--scale", type=float, nargs=2, default=(2.0, 1.0))
    parser.add_argument("--decimals", type=int, choices=(2, 3), default=2)
    parser.add_argument(
        "--viewport", type=Viewport, choices=tuple(Viewport), default=Viewport.NORMAL
    )
    parser.add_argument(
        "--frame-policy",
        type=frames.FramePolicy,
        choices=tuple(frames.FramePolicy),
        default=frames.FramePolicy.UNCHANGED,
    )
    parser.add_argument("--failure-receipt", type=Path)
    parser.add_argument("--failure-receipt-sha256")
    parser.add_argument(
        "--printed-format",
        type=PrintedFormat,
        choices=tuple(PrintedFormat),
        default=PrintedFormat.SKIP,
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        default=ROOT / "cad/out/reports/prepared-template-cache",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require_environment(args.expected_pid)
    spec = prepared.TemplateSpec(tuple(args.scale), args.decimals)
    frames.failure_input(
        args.frame_policy,
        spec,
        sheet_setup.PROJECT_DRWDOT,
        args.failure_receipt,
        args.failure_receipt_sha256,
    )
    if args.worker:
        return ownership.run_copy_diagnostic(
            lambda adapter: probe(
                adapter,
                spec,
                args.report_root.resolve(),
                args.expected_pid,
                printed_format=args.printed_format,
                viewport=args.viewport,
                frame_policy=args.frame_policy,
                failure_receipt=args.failure_receipt,
                failure_receipt_sha256=args.failure_receipt_sha256,
            )
        )
    import dodo

    frame_arguments = ["--frame-policy", args.frame_policy.value]
    if args.failure_receipt is not None:
        frame_arguments += [
            "--failure-receipt",
            str(args.failure_receipt.resolve()),
            "--failure-receipt-sha256",
            args.failure_receipt_sha256,
        ]
    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--expected-pid",
            str(args.expected_pid),
            "--scale",
            *map(str, spec.scale),
            "--decimals",
            str(spec.decimals),
            "--printed-format",
            args.printed_format.value,
            "--viewport",
            args.viewport.value,
            *frame_arguments,
            "--report-root",
            str(args.report_root.resolve()),
            "--worker",
        ],
        "prepared template cache control",
        log_stem="prepared-template-cache",
        com=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
