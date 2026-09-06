"""Locate the first arbor recipe boundary that dirties an OWNED source-part copy.

This diagnostic is not a drawing build or a claim that dirty sources are harmless.
The exact original is hash-protected and never opened. A unique-basename byte
copy is ordinary COPY ownership, not a protected/frozen input: only this copy
may become dirty and be discarded without saving. Existing native documents
remain protected by the attach-only shared session/ownership helpers.

Run only after source review and an explicit COM seat grant. The trusted pinned
recipe bytes are unchanged; the existing loader redirects SOURCE and OUTPUTS.
Temporary function wrappers sample GetSaveFlag around native operation groups,
including nested dimension import/delete/curation. At the first dirty boundary,
a dedicated BaseException stops even through adapter._attempt. A complete
observed feature/display-dimension inventory is captured initially and at that
boundary. GetSaveFlag is also sampled around the initial snapshot, so getters
are not assumed inert. The boundary is an operation group, not proof that a
particular inner COM setter caused the transition. No save/export is allowed.

IFeature.GetFirst/GetNextDisplayDimension enumerate feature/subfeature dimensions
in unspecified order. No display-toggle prerequisite is written by this probe;
coverage is reported as the observed inventory and must include all five arbor
manufacturing dimensions. Missing support fails rather than claiming completeness.

R2026x observation, 2026-09-06, frozen 99eadbe7, trace
0x8d83b3f3456fe76a203b3f0b2b6c84e4: baseline getters, new drawing, three view
inserts, dimension insertion/deletion/curation all left the copied source clean.
The first dirty boundary was AFTER recipe.set_dimension_callouts, before precision
formatting. Among 20 exact IDimensions, only BoreDia's display text changed:
GetText(4)/GetText(8), empty -> THRU; all model values/tolerances and native
dimension identities stayed unchanged. Original and copied disk SHA-256 stayed
dbb991437aea105ca5352b8b76468874077aeed0a74906413a1cc56fb7ca769e.
No save/export occurred; both owned documents closed, original visible lever and
unsaved Draw2 states survived. Receipt: source-dirty-9cbdz77u/source-dirty.json.
This is group-level attribution, not a separated SetText-versus-rebuild trial,
and says nothing yet about later precision operations or other recipes/releases.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from functools import wraps
import inspect
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import check  # noqa: E402
from arbor_pedestal_spec import DRAWING_DIMENSIONS  # noqa: E402
from diagnostics import benchmark_drawing_recipes as benchmark  # noqa: E402
from diagnostics.probe_datum_policy_recipes import (  # noqa: E402
    adapter_fingerprints,
    helper_fingerprints,
)
from diagnostics.probe_drawing_attachments import file_digest  # noqa: E402
from diagnostics._source_dimension_snapshot import (  # noqa: E402
    dimension_snapshot as _source_snapshot,
)
from diagnostics._owned_native_documents import DocumentKind, run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
import _telemetry  # noqa: E402


class DiagnosticStop(BaseException):
    """Expected diagnostic stop; must bypass _attempt's Exception handlers."""


def dimension_snapshot(app, model, path):
    return _source_snapshot(app, model, path, required=DRAWING_DIMENSIONS)


class DirtyMonitor:
    def __init__(self, app, model, path, report, checkpoint):
        self.app, self.model, self.path = app, model, path
        self.report, self.checkpoint = report, checkpoint
        self.handles, self.stack = {}, []
        self.started = time.perf_counter()

    def flag(self):
        if (
            int(self.model.GetType()) != 1
            or Path(self.model.GetPathName()).resolve() != self.path
        ):
            raise RuntimeError("owned source path/kind changed")
        if (
            int(
                self.app.IsSame(
                    self.app.GetOpenDocumentByName(str(self.path)), self.model
                )
            )
            != 1
        ):
            raise RuntimeError("owned source native identity changed")
        value = self.model.GetSaveFlag()
        if value not in (False, True):
            raise RuntimeError("native GetSaveFlag returned a non-boolean value")
        return bool(value)

    def baseline(self):
        before = self.flag()
        self.report["baseline_save_flag"] = {"before": before}
        self.report["baseline"], self.handles = dimension_snapshot(
            self.app, self.model, self.path
        )
        after = self.flag()
        self.report["baseline_save_flag"]["after"] = after
        self.checkpoint()
        if before or after:
            self.report["stop"] = {
                "boundary": "open_copy" if before else "baseline_dimension_snapshot",
                "phase": "before" if before else "after",
                "reason": "dirty_before_recipe",
            }
            self.checkpoint()
            raise DiagnosticStop()

    def observe(self, boundary, phase, *, error=None):
        try:
            self._observe(boundary, phase, error=error)
        except Exception as capture_error:
            # Native/readback/checkpoint failures must not turn into a swallowed
            # _attempt failure and let a dirty-source recipe continue either.
            self.report.setdefault(
                "stop",
                {
                    "boundary": boundary,
                    "phase": phase,
                    "reason": "monitor_failure",
                },
            )["capture_error"] = repr(capture_error)
            try:
                self.checkpoint()
            finally:
                raise DiagnosticStop() from capture_error

    def _observe(self, boundary, phase, *, error=None):
        dirty = self.flag()
        event = {
            "boundary": boundary,
            "phase": phase,
            "dirty": dirty,
            "stack": list(self.stack),
            "elapsed_s": time.perf_counter() - self.started,
        }
        if error is not None:
            event["operation_error"] = repr(error)
        self.report["events"].append(event)
        self.checkpoint()
        if not dirty:
            return
        self.report["stop"] = {**event, "reason": "first_dirty_boundary"}
        self.checkpoint()
        actual, handles = dimension_snapshot(self.app, self.model, self.path)
        initial = self.report["baseline"]["dimensions"]
        rows = actual["dimensions"]
        self.report["stop"].update(
            snapshot=actual,
            changed_since_initial_snapshot=sorted(
                key
                for key in initial.keys() | rows.keys()
                if initial.get(key) != rows.get(key)
            ),
            dimension_identity={
                key: "same"
                if key in handles and int(self.app.IsSame(handle, handles[key])) == 1
                else "replaced_or_missing"
                for key, handle in self.handles.items()
            },
            dirty_after_transition_snapshot=self.flag(),
        )
        self.checkpoint()
        raise DiagnosticStop()

    @contextmanager
    def boundary(self, label):
        self.observe(label, "before")
        self.stack.append(label)
        try:
            yield
        except DiagnosticStop:
            raise
        except BaseException as error:
            self.observe(label, "after_error", error=error)
            raise
        else:
            self.observe(label, "after")
        finally:
            self.stack.pop()

    def wrap(self, label, operation):
        if inspect.iscoroutinefunction(operation):

            @wraps(operation)
            async def asynchronous(*args, **kwargs):
                with self.boundary(label):
                    return await operation(*args, **kwargs)

            return asynchronous

        @wraps(operation)
        def synchronous(*args, **kwargs):
            with self.boundary(label):
                return operation(*args, **kwargs)

        return synchronous

    async def stop_before_finalize(self, *_args, **_kwargs):
        self.observe("recipe.finalize_drawing", "before")
        self.report["stop"] = {
            "boundary": "recipe.finalize_drawing",
            "phase": "before",
            "reason": "clean_before_finalize",
        }
        self.checkpoint()
        raise DiagnosticStop()


@contextmanager
def instrument_recipe(module, monitor):
    """Patch only this process's call boundaries; restore exact functions on exit."""
    import _drawing_common as common

    replacements = []
    # All module-level Python functions except the build/main entrypoints. This
    # also brackets recipe-local helpers containing direct native calls.
    targets = [
        (module, name, f"recipe.{name}")
        for name, value in vars(module).items()
        if inspect.isfunction(value)
        and name not in {"build", "run_build", "_parse_args", "finalize_drawing"}
    ]
    targets.extend(
        (common, name, f"nested.{name}")
        for name in (
            "insert_marked_dimensions",
            "delete_unnamed_imports",
            "curate_dimensions",
        )
    )
    try:
        for owner, name, label in targets:
            original = getattr(owner, name)
            replacements.append((owner, name, original))
            setattr(owner, name, monitor.wrap(label, original))
        replacements.append((module, "finalize_drawing", module.finalize_drawing))
        module.finalize_drawing = monitor.stop_before_finalize
        yield
    finally:
        for owner, name, original in reversed(replacements):
            setattr(owner, name, original)


async def probe(adapter, source, expected_hash, candidate, report_root):
    report_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="source-dirty-", dir=report_root))
    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(source)
    report = {
        "status": "running",
        "events": [],
        "source": str(source),
        "candidate": candidate,
        "helper_revision": benchmark.revision("HEAD"),
    }
    report_path = directory / "source-dirty.json"

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    checkpoint()
    _telemetry.info("source dirty boundary diagnostic", report=str(report_path))
    copied = directory / f"arbor-{directory.name}.SLDPRT"
    try:
        report["original_before"] = file_digest(source)
        if report["original_before"] != expected_hash:
            raise RuntimeError(
                "original arbor source does not match reviewed exact hash"
            )
        shutil.copy2(source, copied)
        report["copy_before"] = file_digest(copied)
        if report["copy_before"] != expected_hash:
            raise RuntimeError("owned source copy does not match exact original bytes")
        report["copy"] = str(copied)
        report["helpers"] = helper_fingerprints()
        report["imported_adapter"] = adapter_fingerprints()
        module = benchmark.load_recipe(
            candidate, "arbor_pedestal", directory, source=copied
        )
        report["recipe_sha256"] = file_digest(directory / "recipe-source.py")
        check("open owned arbor copy", await adapter.open_model(str(copied)))
        adapter.ownership.assert_current_owned()
        monitor = DirtyMonitor(
            adapter.swApp, adapter.currentModel, copied, report, checkpoint
        )
        try:
            monitor.baseline()
            with instrument_recipe(module, monitor):
                with adapter.ownership.creating_document(
                    DocumentKind.DRAWING, module.OUTPUTS.slddrw
                ):
                    await module.build(adapter)
            raise RuntimeError("recipe returned without diagnostic finalization stop")
        except DiagnosticStop:
            report["status"] = "stopped_at_boundary"
            if "capture_error" in report["stop"]:
                raise RuntimeError(
                    f"source transition capture failed: {report['stop']['capture_error']}"
                )
        benchmark.check_fingerprints(
            report["helpers"], helper_fingerprints(), "frozen helpers"
        )
        if report["imported_adapter"] != adapter_fingerprints():
            raise RuntimeError(
                "actual imported adapter changed during dirty-source control"
            )
        if any(
            path.exists()
            for path in (module.OUTPUTS.slddrw, module.OUTPUTS.pdf, module.OUTPUTS.png)
        ):
            raise RuntimeError("diagnostic unexpectedly saved/exported a drawing")
        if file_digest(copied) != expected_hash or file_digest(source) != expected_hash:
            raise RuntimeError("no-save original/copy disk identity guard failed")
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        for key, path in (("original_after", source), ("copy_after", copied)):
            try:
                report[key] = file_digest(path)
            except OSError as error:
                report[key] = {"error": repr(error)}
        checkpoint()
    return {"report": str(report_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--candidate", default="HEAD")
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    if len(args.expected_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in args.expected_sha256
    ):
        raise ValueError("expected SHA-256 must be 64 lowercase hexadecimal characters")
    source = args.source.resolve(strict=True)
    if source.suffix.upper() != ".SLDPRT":
        raise ValueError("source must be an exact native part")
    candidate = benchmark.revision(args.candidate)
    if not args.worker:
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--source",
                str(source),
                "--expected-sha256",
                args.expected_sha256,
                "--candidate",
                candidate,
                "--report-root",
                str(args.report_root.resolve()),
                "--worker",
            ],
            "source dirty recipe boundary diagnostic",
            com=True,
            log_stem="source-dirty-recipe",
        )
        return 0
    return run_copy_diagnostic(
        lambda adapter: probe(
            adapter, source, args.expected_sha256, candidate, args.report_root.resolve()
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
