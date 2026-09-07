"""Fresh selected recipe builds with the combined native datum policy.

Default order is rocker then lever. Repeat --target to select an explicit order,
for example --target channel_lever for the independent lever-only control.
Both registered original/guard source pairs remain hash-protected for any order.
Optional --factory normal|prepared selects only the isolated recipe's initial
project drawing factory. Use separate invocations for a functional pair: a
failed normal cold-title witness never authorizes continuing to prepared.

Run only under an explicitly granted COM seat, attaching to the expected existing
SolidWorks process with automatic launch/recovery disabled. Production recipes
and final gates run unchanged; the reviewed benchmark loader redirects SOURCE
and OUTPUTS before defaults/aliases are evaluated. This is a functional pilot,
not an ABBA speed benchmark or a full doit merge gate.

Original source files are disk-read only, never opened. Each recipe uses a
unique-basename exact bytecopy in its registered diagnostic directory. Native
imported callout formatting can mutate the copied source display in memory (the
arbor source-dirty-9cbdz77u control proved this); existing COPY ownership permits
discarding that copy but does not relax protected original/baseline documents.
Copy disk hashes must remain exact: no source save is authorized. Shared
ownership preserves the user's visible lever and unsaved Draw2 throughout.
Every successful recipe gets a fresh saved/reopened geometry, dimension/BASIC,
annotation-content/layout and source-parameter witness. Stop at the first failure.
The named parameter witnesses do not prove full in-memory source immutability.
Failed trials retain fresh native observations and PDF/PNG evidence when the
exact active drawing is owned. Evidence errors never replace the original
failure; no native drawing/source save or additional successful-trial reads.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
from channel_lever_spec import DRAWING_DIMENSIONS, SOURCE_BASIC_DIMENSIONS  # noqa: E402
from rocker_arm_notes import DRAWING_DIMENSIONS as ROCKER_DIMENSIONS  # noqa: E402
from diagnostics import benchmark_drawing_recipes as benchmark  # noqa: E402
from diagnostics import probe_datum_shoulder as shoulder  # noqa: E402
from diagnostics import probe_drawing_attachments as attachments  # noqa: E402
from diagnostics.probe_source_basic_dimensions import part_dimensions  # noqa: E402
from diagnostics._owned_native_documents import DocumentKind, run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from diagnostics._reopen_annotation_comparison import compare_reopened_annotations  # noqa: E402
import _telemetry  # noqa: E402

ORDER = ("rocker_arm", "channel_lever")
EXPECTED_PART_HASHES = {
    "rocker_arm": "3bfb6da45b91e5a73b24c74baf81141899149e3c327aa943930baed3fba4d4a0",
    "channel_lever": "6a994561f19487029c938cd7cca5047acbdfbf686020514be538ef5a632e0841",
}


def target_order(targets=None):
    """Choose only recipes with the pilot's exact source and semantic manifests."""
    if targets is None:
        return ORDER
    if isinstance(targets, str):
        raise ValueError("targets must be a sequence of recipe names")
    order = tuple(targets)
    if not order or any(target not in EXPECTED_PART_HASHES for target in order):
        raise ValueError("select a nonempty order from the registered pilot recipes")
    if len(set(order)) != len(order):
        raise ValueError("each selected recipe may run only once per invocation")
    return order


def adapter_fingerprints():
    """Fingerprint the imported editable package, not an empty worktree submodule."""
    import solidworks_mcp

    package = Path(solidworks_mcp.__file__).resolve(strict=True).parent
    required = (package / "__init__.py", package / "adapters/pywin32_adapter.py")
    if not all(path.is_file() for path in required):
        raise RuntimeError("actual imported adapter package is incomplete")
    return {
        "package_path": str(package),
        "files": {
            str(path.relative_to(package)): attachments.file_digest(path)
            for path in sorted(package.rglob("*.py"))
        },
    }


def helper_fingerprints():
    result = benchmark.helper_fingerprints()
    result.update(
        {
            str(path.relative_to(ROOT)): attachments.file_digest(path)
            for path in sorted((ROOT / "cad/scripts/diagnostics").glob("*.py"))
        }
    )
    return result


def require_sources(sources, guards):
    hashes = {}
    for target in ORDER:
        for path in (sources[target], guards[target]):
            actual = attachments.file_digest(path)
            hashes[str(path)] = actual
            if actual != EXPECTED_PART_HASHES[target]:
                raise RuntimeError(
                    f"{target}: exact immutable source hash mismatch: {path}: {actual}"
                )
    return hashes


@_telemetry.traced("diagnostic.datum_policy.source_dimensions")
def source_dimensions(model, target, path):
    model = _early_bound(model, "IModelDoc2")
    if (
        model is None
        or int(model.GetType()) != 1
        or Path(model.GetPathName()).resolve() != path
    ):
        raise RuntimeError("source parameter witness has the wrong exact native owner")
    configuration = str(
        _early_bound(
            _early_bound(
                model.ConfigurationManager, "IConfigurationManager"
            ).ActiveConfiguration,
            "IConfiguration",
        ).Name
    )
    if not configuration:
        raise RuntimeError("source parameter witness has no active configuration")
    targets = DRAWING_DIMENSIONS if target == "channel_lever" else ROCKER_DIMENSIONS
    rows, handles = part_dimensions(
        SimpleNamespace(currentModel=model), path, configuration, targets=targets
    )
    if target == "channel_lever":
        for feature, names in SOURCE_BASIC_DIMENSIONS.items():
            for name in names:
                if rows[f"{name}@{feature}"]["tolerance_type"] != 1:
                    raise RuntimeError(
                        f"{name}@{feature}: saved source BASIC designation missing"
                    )
    return {"configuration": configuration, "dimensions": rows}, handles


def require_same_source(
    before, after, stage, *, app=None, handles_before=None, handles_after=None
):
    if before != after:
        raise RuntimeError(f"{stage}: source parameters/tolerances changed")
    if app is not None:
        if handles_before.keys() != handles_after.keys() or any(
            int(app.IsSame(handle, handles_after[name])) != 1
            for name, handle in handles_before.items()
        ):
            raise RuntimeError(f"{stage}: exact source dimension identity changed")


def require_copy_hash(trial, phase):
    """Record the owned part's disk identity; formatting may dirty memory only."""
    actual = attachments.file_digest(Path(trial["copy_source"]))
    trial.setdefault("copy_hashes", {})[phase] = actual
    if actual != EXPECTED_PART_HASHES[trial["target"]]:
        raise RuntimeError(
            f"{phase}: owned source copy changed on disk; no source save is authorized"
        )


def drawing_witness(adapter, *, source, configuration):
    return _drawing_witness(adapter, source=source, configuration=configuration)[0]


def _drawing_witness(adapter, *, source, configuration):
    semantics = attachments.snapshot(adapter.currentModel, app=adapter.swApp)
    if not semantics["models"]:
        raise RuntimeError("functional pilot has no captured drawing view models")
    for view, model in semantics["models"].items():
        if (
            Path(model["path"]).resolve() != source
            or model["configuration"] != configuration
        ):
            raise RuntimeError(
                f"{view}: drawing does not reference the expected owned source/configuration: "
                f"{model} != {source} / {configuration}"
            )
    if (
        not semantics["checked"]
        or not semantics["dimensions"]
        or semantics["dimensions_excluded"]
    ):
        raise RuntimeError(
            "functional pilot needs nonempty geometry/dimensions without dimension exclusions"
        )
    annotations, handles = shoulder.all_annotation_layout(adapter)
    return {
        "semantics": semantics,
        "annotations": annotations,
        "layout": attachments.layout(adapter.currentModel),
    }, handles


def compare_drawing(app, before, after):
    attachments.compare(
        before["semantics"], after["semantics"], "saved production reopen"
    )
    attachments.check_layout(
        before["layout"], after["layout"], "saved production reopen"
    )
    changes = shoulder.compare_all_annotation_layout(
        app, before["annotations"], after["annotations"]
    )
    if changes:
        raise RuntimeError(
            f"saved production reopen changed native annotation layout: {changes}"
        )


def compare_drawing_reopen(before, after):
    """Keep all attachment/source semantics exact; report coordinate noise only."""
    attachments.compare(
        before["semantics"], after["semantics"], "saved production reopen"
    )
    attachments.check_layout(
        before["layout"], after["layout"], "saved production reopen"
    )
    return compare_reopened_annotations(before["annotations"], after["annotations"])


def _failure_document(adapter, output):
    """Never infer ownership from currentModel or from an output directory."""
    record = adapter.ownership.assert_current_owned()
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    output = Path(output).resolve()
    if (
        output not in record.paths
        or output.parent not in adapter.ownership.directories
        or int(model.GetType()) != int(DocumentKind.DRAWING)
    ):
        raise RuntimeError("failure evidence requires the trial's exact owned DRAWING")
    path = str(model.GetPathName())
    if path and Path(path).resolve() != output:
        raise RuntimeError("failure drawing has an unexpected native path")
    return {
        "path": path,
        "title": str(model.GetTitle()),
        "kind": int(model.GetType()),
        "dirty": bool(model.GetSaveFlag()),
        "visible": bool(model.Visible),
    }


def retain_failed_drawing(adapter, trial, output, checkpoint):
    """Failure-only observations; the caller must re-raise its original error.

    Reuses the existing PDF-only native helper (empty native target), not recipe
    finalization. No rebuild, native/source save, layout or cleanup occurs here.
    Complete measured rows and native handles are checked across export; known
    measurement exclusions remain explicit. The outer pilot retains its source
    and factory guards, and the owned runner still owns cleanup.
    """
    from diagnostics import probe_retained_drawing_export as printed

    evidence = {
        "primary_error": trial["error"],
        "scope": "failed native scene, measured annotation ink and geometry/dimension witnesses; PDF-only export; no cold/native-save acceptance",
        "errors": [],
    }
    trial["failure_evidence"] = evidence
    output = Path(output).resolve()
    receipt = output.parent / "failure-evidence.json"
    handles = {}

    def persist():
        for phase, action in (
            (
                "evidence_checkpoint",
                lambda: receipt.write_text(
                    json.dumps(evidence, indent=2), encoding="utf-8"
                ),
            ),
            ("pilot_checkpoint", checkpoint),
        ):
            try:
                action()
            except Exception as error:
                evidence["errors"].append({"phase": phase, "error": repr(error)})

    def observe(phase, action):
        try:
            with _telemetry.span(
                "diagnostic.datum_policy.failure_evidence", phase=phase
            ):
                evidence[phase] = action()
        except Exception as error:
            evidence["errors"].append({"phase": phase, "error": repr(error)})

    # Refuse existing evidence before any write; never overwrite an earlier
    # observation, and do not inspect/export a borrowed or replaced document.
    observe("ownership", lambda: _failure_document(adapter, output))
    if "ownership" not in evidence:
        return
    if any(
        (output.parent / name).exists()
        for name in ("failure-evidence.json", "failure.pdf", "failure.png")
    ):
        evidence["errors"].append(
            {"phase": "targets", "error": "failure evidence targets already exist"}
        )
        return
    evidence["receipt"] = str(receipt)
    evidence["document_before"] = evidence.pop("ownership")
    persist()

    def hashes():
        paths = {"source_copy": Path(trial["copy_source"]), "native_drawing": output}
        if "original_source" in trial:
            paths["original_source"] = Path(trial["original_source"])
        return {
            name: {
                "path": str(path),
                "sha256": attachments.file_digest(path) if path.is_file() else None,
            }
            for name, path in paths.items()
        }

    def scene(phase):
        _failure_document(adapter, output)
        source = Path(trial["copy_source"]).resolve(strict=True)
        source_model = _early_bound(
            adapter.swApp.GetOpenDocumentByName(str(source)), "IModelDoc2"
        )
        source_values, source_handles = source_dimensions(
            source_model, trial["target"], source
        )
        drawing, annotation_handles = _drawing_witness(
            adapter,
            source=source,
            configuration=trial["source_before"]["configuration"],
        )
        handles[phase] = (
            adapter.currentModel,
            source_model,
            source_handles,
            annotation_handles,
        )
        return {
            "drawing": drawing,
            "source": source_values,
            "source_document": {
                "path": str(source_model.GetPathName()),
                "title": str(source_model.GetTitle()),
                "kind": int(source_model.GetType()),
                "dirty": bool(source_model.GetSaveFlag()),
                "visible": bool(source_model.Visible),
            },
        }

    observe("hashes_before", hashes)
    observe("before", lambda: scene("before"))
    persist()
    pdf, png = output.parent / "failure.pdf", output.parent / "failure.png"

    def pdf_export():
        _failure_document(adapter, output)
        printed.export_pdf_only(adapter, pdf)
        return {"path": str(pdf), "sha256": attachments.file_digest(pdf)}

    def render():
        printed.render_pdf_png(pdf, png)
        return {"path": str(png), "sha256": attachments.file_digest(png)}

    observe("pdf", pdf_export)
    persist()
    if "pdf" in evidence:
        observe("png", render)
        persist()
    # Always observe post-export state/hashes, even if export or rasterization
    # failed. Independent phases retain these when a full snapshot is rejected.
    observe("document_after", lambda: _failure_document(adapter, output))
    observe("hashes_after", hashes)
    observe("after", lambda: scene("after"))
    persist()

    def unchanged():
        for field in ("document", "hashes"):
            if evidence[f"{field}_before"] != evidence[f"{field}_after"]:
                raise RuntimeError(f"failure PDF export changed {field}")
        before, after = evidence["before"], evidence["after"]
        if before["source_document"] != after["source_document"]:
            raise RuntimeError("failure PDF export changed the source document state")
        first, last = handles["before"], handles["after"]
        if any(
            int(adapter.swApp.IsSame(a, b)) != 1 for a, b in zip(first[:2], last[:2])
        ):
            raise RuntimeError("failure export replaced drawing/source native identity")
        require_same_source(
            before["source"],
            after["source"],
            "failure PDF export",
            app=adapter.swApp,
            handles_before=first[2],
            handles_after=last[2],
        )
        compare_drawing(adapter.swApp, before["drawing"], after["drawing"])
        shoulder.compare_all_annotation_layout(
            adapter.swApp,
            before["drawing"]["annotations"],
            after["drawing"]["annotations"],
            first[3],
            last[3],
        )
        if before["drawing"]["annotations"] != after["drawing"]["annotations"]:
            raise RuntimeError(
                "failure PDF export changed raw native annotation measurements"
            )
        return (
            "exact captured state and identity unchanged; original trial still failed"
        )

    if all(
        name in evidence
        for name in (
            "document_after",
            "hashes_before",
            "hashes_after",
            "before",
            "after",
        )
    ):
        observe("export_preservation", unchanged)
    if "before" in evidence:
        observe(
            "recipe_source_preservation",
            lambda: require_same_source(
                trial["source_before"],
                evidence["before"]["source"],
                "failed recipe before evidence export",
            ),
        )
    persist()


async def pilot(
    adapter,
    candidate,
    source_root,
    guard_root,
    output_root,
    *,
    targets=None,
    setup_controller=None,
):
    order = target_order(targets)
    output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="datum-policy-", dir=output_root))
    adapter.ownership.register_directory(directory)
    sources = {
        target: (source_root / f"{target.replace('_', '-')}.SLDPRT").resolve(
            strict=True
        )
        for target in ORDER
    }
    guards = {
        target: (guard_root / sources[target].name).resolve(strict=True)
        for target in ORDER
    }
    report = {
        "status": "running",
        "candidate": candidate,
        "helper_revision": benchmark.revision("HEAD"),
        "order": order,
        "factory": setup_controller.variant.value if setup_controller else "normal",
        "trials": [],
        "scope": "one functional build per recipe; no speedup/full-pipeline claim",
        "source_witness_scope": "exact original/copy disk hashes and named recipe dimension identities/values/tolerances/BASIC; not full in-memory source immutability",
    }
    report_path = directory / "pilot.json"
    failure_output = None
    pilot_started = time.perf_counter()
    report["elapsed_scope"] = (
        "pilot source guards, preparation, recipe and cold witnesses; excludes parent lock/attach and outer owned-session cleanup"
    )

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    checkpoint()
    _telemetry.info("combined datum-policy pilot report", path=str(report_path))
    try:
        report["sources_before"] = require_sources(sources, guards)
        for path in (*sources.values(), *guards.values()):
            adapter.ownership.register_source(path)
        report["helpers"] = helper_fingerprints()
        report["imported_adapter"] = adapter_fingerprints()
        for target in order:
            failure_output = None
            trial = {"target": target, "status": "running"}
            report["trials"].append(trial)
            trial_dir = directory / target
            trial_dir.mkdir()
            adapter.ownership.register_directory(trial_dir)
            copy_source = (
                trial_dir / f"{sources[target].stem}-source-{directory.name}.SLDPRT"
            )
            shutil.copy2(sources[target], copy_source)
            trial.update(
                original_source=str(sources[target]), copy_source=str(copy_source)
            )
            # Do not register/freeze this as a protected source: it is an owned
            # COPY, and imported drawing formatting can legitimately dirty it.
            require_copy_hash(trial, "copied")
            checkpoint()
            module = benchmark.load_recipe(
                candidate, target, trial_dir, source=copy_source
            )
            failure_output = module.OUTPUTS.slddrw
            await adapter.close_owned_documents()
            if setup_controller is not None:
                await setup_controller.configure(adapter, module, trial, trial_dir)
            check(
                "open exact owned source copy",
                await adapter.open_model(str(copy_source)),
            )
            adapter.ownership.assert_current_owned()
            source_model = adapter.currentModel
            trial["source_before"], source_handles = source_dimensions(
                source_model, target, copy_source
            )
            trial["recipe_sha256"] = attachments.file_digest(
                trial_dir / "recipe-source.py"
            )
            started = time.perf_counter()
            try:
                with _telemetry.span("diagnostic.datum_policy.recipe", target=target):
                    with adapter.ownership.creating_document(
                        DocumentKind.DRAWING, module.OUTPUTS.slddrw
                    ):
                        artifacts = await module.build(adapter)
                if setup_controller is not None:
                    setup_controller.require_used()
            finally:
                trial["recipe_seconds"] = time.perf_counter() - started
                checkpoint()
            trial["artifacts"] = benchmark.validate_artifacts(artifacts, module.OUTPUTS)
            require_copy_hash(trial, "after_recipe")
            adapter.ownership.assert_current_owned()
            with _telemetry.span(
                "diagnostic.datum_policy.drawing_witness", target=target, phase="built"
            ):
                trial["built"] = drawing_witness(
                    adapter,
                    source=copy_source,
                    configuration=trial["source_before"]["configuration"],
                )
            trial["source_after"], after_handles = source_dimensions(
                source_model, target, copy_source
            )
            require_same_source(
                trial["source_before"],
                trial["source_after"],
                "recipe",
                app=adapter.swApp,
                handles_before=source_handles,
                handles_after=after_handles,
            )
            await adapter.close_owned_documents()
            require_copy_hash(trial, "after_close")
            check(
                "reopen owned production drawing",
                await adapter.open_model(str(module.OUTPUTS.slddrw)),
            )
            adapter.ownership.assert_current_owned()
            with _telemetry.span(
                "diagnostic.datum_policy.drawing_witness",
                target=target,
                phase="reopened",
            ):
                trial["reopened"] = drawing_witness(
                    adapter,
                    source=copy_source,
                    configuration=trial["source_before"]["configuration"],
                )
            trial["reopen_annotation_comparison"] = compare_drawing_reopen(
                trial["built"], trial["reopened"]
            )
            if trial["reopen_annotation_comparison"]["status"] != "passed":
                raise RuntimeError(
                    "saved production reopen changed native annotation layout: "
                    f"{trial['reopen_annotation_comparison']['rejected']}"
                )
            reopened_source = adapter.swApp.GetOpenDocumentByName(str(copy_source))
            trial["source_reopened"], _ = source_dimensions(
                reopened_source, target, copy_source
            )
            require_same_source(
                trial["source_before"], trial["source_reopened"], "saved reopen"
            )
            benchmark.check_fingerprints(
                report["helpers"],
                helper_fingerprints(),
                "frozen helpers/config/template",
            )
            if report["imported_adapter"] != adapter_fingerprints():
                raise RuntimeError(
                    "actual imported adapter changed during functional pilot"
                )
            require_sources(sources, guards)
            await adapter.close_owned_documents()
            require_copy_hash(trial, "after_reopened_close")
            trial["status"] = "passed"
            checkpoint()
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        if report["trials"]:
            report["trials"][-1].update(status="failed", error=repr(error))
        if failure_output is not None:
            try:
                checkpoint()
                retain_failed_drawing(
                    adapter, report["trials"][-1], failure_output, checkpoint
                )
            except Exception as evidence_error:
                report["trials"][-1]["failure_evidence_error"] = repr(evidence_error)
        raise
    finally:
        primary_error = sys.exception()
        for trial in report["trials"]:
            if "copy_source" not in trial:
                continue
            try:
                trial["copy_final"] = attachments.file_digest(
                    Path(trial["copy_source"])
                )
            except OSError as error:
                trial["copy_final"] = {"error": repr(error)}
        report["sources_after"] = {}
        for path in (*sources.values(), *guards.values()):
            try:
                report["sources_after"][str(path)] = attachments.file_digest(path)
            except OSError as error:
                report["sources_after"][str(path)] = {"error": repr(error)}
        guard_errors = []
        if setup_controller is not None:
            guard_errors = setup_controller.final_guards()
            report["factory_final_guards"] = setup_controller.guards
            if guard_errors:
                report.update(
                    status="failed",
                    factory_guard_errors=[repr(error) for error in guard_errors],
                )
        report["elapsed_seconds"] = time.perf_counter() - pilot_started
        checkpoint()
        if guard_errors:
            raise BaseExceptionGroup(
                "functional recipe/factory final guards failed",
                ([primary_error] if primary_error is not None else []) + guard_errors,
            )
    return {"report": str(report_path)}


def main(argv=None):
    from diagnostics._recipe_template_factory import (
        DrawingFactory,
        RecipeTemplateFactory,
        require_factory_environment,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--guard-root", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument("--candidate", default="HEAD")
    parser.add_argument(
        "--factory",
        type=DrawingFactory,
        choices=tuple(DrawingFactory),
        help="explicit full-recipe factory control; prepared materialization is timed separately",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=tuple(EXPECTED_PART_HASHES),
        help="repeat to choose recipe order; default: rocker_arm then channel_lever",
    )
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args(argv)
    order = target_order(args.target)
    require_owned_diagnostic_environment()  # before dodo._run in the parent
    if args.factory is not None:
        require_factory_environment()
    candidate = benchmark.revision(args.candidate)
    source_root, guard_root = (
        args.source_root.resolve(strict=True),
        args.guard_root.resolve(strict=True),
    )
    if not args.worker:
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--source-root",
                str(source_root),
                "--guard-root",
                str(guard_root),
                "--report-root",
                str(args.report_root.resolve()),
                "--candidate",
                candidate,
                *(
                    ["--factory", args.factory.value]
                    if args.factory is not None
                    else []
                ),
                *(argument for target in order for argument in ("--target", target)),
                "--worker",
            ],
            "combined datum-policy functional pilot",
            com=True,
            log_stem="datum-policy-functional",
        )
        return 0
    return run_copy_diagnostic(
        lambda adapter: pilot(
            adapter,
            candidate,
            source_root,
            guard_root,
            args.report_root.resolve(),
            targets=order,
            **(
                {"setup_controller": RecipeTemplateFactory(args.factory)}
                if args.factory is not None
                else {}
            ),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
