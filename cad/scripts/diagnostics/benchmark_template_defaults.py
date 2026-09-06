"""ABBA control: current drawing setup versus an inherited project DRWDOT.

Only arbor_pedestal and pen_marker direct recipes are supported initially.
The original template and source parts are immutable. A derived template is
prepared once per exact sheet-scale/decimal variant; that cost is reported
separately. Both arms retain all recipe layout/manufacturing/export code.
No view quality, automatic-update, font-size or leader policy is changed.
Native execution needs source review, the coordinated seat and AUTOSTART=0.
"""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import sys
import tempfile
import time
import types

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
import _drawing_common as common  # noqa: E402
from _drawing_annotation_bounds import annotation_box  # noqa: E402
from _drawing_registry import DRAWINGS_BY_NAME  # noqa: E402
import _telemetry  # noqa: E402
from solidworks_mcp.adapters.solidworks import drawing  # noqa: E402
from diagnostics import benchmark_drawing_recipes as recipes  # noqa: E402
from diagnostics import probe_drawing_attachments as attachments  # noqa: E402
from diagnostics._owned_native_session import (  # noqa: E402
    require_owned_diagnostic_environment,
)

TARGETS = ("arbor_pedestal", "pen_marker")
ORDER = ("baseline", "candidate", "candidate", "baseline")
# Current set_units_mm explicitly sets linear units after selecting MMGS. Native
# control probe_drawing_unit_defaults.py proves that setter switches the system
# label to swUnitSystem_Custom=4. Preserve that exact terminal state in both arms.
CURRENT_HELPER_UNIT_SYSTEM = 4


@dataclass(frozen=True)
class TemplateSpec:
    scale: tuple[float, float]
    decimals: int

    def __post_init__(self):
        scale = tuple(float(value) for value in self.scale)
        if len(scale) != 2 or any(
            not math.isfinite(value) or value <= 0 for value in scale
        ):
            raise ValueError("template scale needs two positive finite numbers")
        if type(self.decimals) is not int or self.decimals not in (2, 3):
            raise ValueError("this control supports project precision variants 2 and 3")
        object.__setattr__(self, "scale", scale)


def check_setup_arguments(spec, kwargs):
    if set(kwargs) - {"property_view", "scale", "decimals"}:
        raise ValueError("unsupported drawing-setup keyword")
    actual = TemplateSpec(kwargs.get("scale", (1, 1)), kwargs.get("decimals", 2))
    if actual != spec:
        raise ValueError(
            f"recipe changed its drawing-setup variant: {actual} != {spec}"
        )


@contextmanager
def replaced_setup(module, replacement):
    original = module.new_project_drawing
    module.new_project_drawing = replacement
    try:
        yield
    finally:
        module.new_project_drawing = original


def compare_exact(before, after, phase):
    if before != after:
        raise RuntimeError(f"{phase}: saved/default/annotation witness changed")


def validate_units(units, spec):
    expected = {
        "system": CURRENT_HELPER_UNIT_SYSTEM,
        "linear": drawing._SW_LENGTH_MM,
        "decimals": spec.decimals,
    }
    if units != expected:
        raise RuntimeError(
            f"inherited drawing units/precision differ: {units} != {expected}"
        )


def json_value(value):
    """Keep existing attachment-probe nanometre rounding, not relaxed fit gates."""
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RuntimeError("non-finite native snapshot value")
        return round(value, 9)
    return value


def semantic_multiset(rows):
    return sorted(json.dumps(json_value(row), sort_keys=True) for row in rows)


def runtime_fingerprints():
    result = recipes.helper_fingerprints()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        result[str(path.relative_to(ROOT))] = attachments.file_digest(path)
    return result


def immutable_hashes(paths):
    return {
        str(Path(path).resolve(strict=True)): attachments.file_digest(path)
        for path in paths
    }


def immutable_changes(expected):
    changed = {}
    for path, digest in expected.items():
        try:
            actual = (
                attachments.file_digest(path) if Path(path).is_file() else "missing"
            )
        except OSError as error:
            changed[path] = {"expected": digest, "error": repr(error)}
            continue
        if actual != digest:
            changed[path] = {"expected": digest, "actual": actual}
    return changed


def save_prepared_template(model, path, row):
    """Use the persisted positive shape in probe_drawing_template_save.py."""
    if path.exists():
        raise ValueError("prepared template output is not fresh")
    model.ClearSelection2(True)
    row["save_method"] = "IModelDoc2.SaveAs3(path,0,0)"
    row["save_return"] = model.SaveAs3(str(path), 0, 0)
    # Native integer is recorded, not interpreted as an undocumented status.
    if type(row["save_return"]) is not int:
        raise RuntimeError("ModelDoc2.SaveAs3 returned an unexpected native type")
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("prepared template save produced no complete file")


def semantic_attachment(row, geometry, view_key):
    """Normalize only independently witnessed regenerated annotation labels."""
    if row["owner_view"] != view_key:
        raise RuntimeError("datum semantic owner differs from enumerating native view")
    target_key = f"{view_key}/{row['target_annotation']}/4"
    if geometry["dimensions"].get(target_key) != row["dimension"]:
        raise RuntimeError("datum semantic target is not the witnessed view dimension")
    if set(row) != {
        "kind",
        "owner_view",
        "target_annotation",
        "source",
        "dimension",
        "datum",
    }:
        raise ValueError(
            "new datum semantic fields need an explicit comparison contract"
        )
    return {key: row[key] for key in ("kind", "source", "dimension", "datum")}


def cross_arm_signature(snapshot):
    return {
        "defaults": snapshot["defaults"],
        "view_modes": snapshot["view_modes"],
        "semantic_annotations": snapshot["semantic_annotations"],
    }


def inherited_drawing(adapter, template, spec):
    template = Path(template).resolve(strict=True)
    if template.stat().st_size == 0:
        raise ValueError("derived template is empty")
    draw = drawing.new_drawing(
        adapter,
        template=str(template),
        width=common.ASME_B_WIDTH_M,
        height=common.ASME_B_HEIGHT_M,
    )
    ddoc = _early_bound(draw, "IDrawingDoc")
    ddoc.EditSheet()
    sheet = ddoc.GetCurrentSheet()
    if sheet is None:
        raise RuntimeError("derived template returned no current sheet")
    common.assert_asme_b_sheet(
        adapter, sheet, phase="inherited setup", scale=spec.scale
    )
    draw.ViewZoomtofit2()
    return draw, sheet


def defaults_snapshot(adapter, spec):
    """Read document defaults and all sheet note text without changing them."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    ddoc = _early_bound(model, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    common.assert_asme_b_sheet(
        adapter, sheet, phase="defaults witness", scale=spec.scale
    )
    units = {
        "system": int(
            model.GetUserPreferenceIntegerValue(drawing._SW_PREF_UNIT_SYSTEM)
        ),
        "linear": int(
            model.GetUserPreferenceIntegerValue(drawing._SW_PREF_UNITS_LINEAR)
        ),
        "decimals": int(
            model.GetUserPreferenceIntegerValue(drawing._SW_PREF_UNITS_LINEAR_DP)
        ),
    }
    validate_units(units, spec)
    styles = {
        name: int(
            model.Extension.GetUserPreferenceInteger(
                common._PREF_DIM_TEXT_AND_LEADER_STYLE, option
            )
        )
        for name, option in common._DIM_DETAILING_SCOPES.items()
    }
    if any(value != common._BROKEN_LEADER_HORIZONTAL_TEXT for value in styles.values()):
        raise RuntimeError(f"inherited dimension style differs: {styles}")
    notes = []
    sheet_view = _early_bound(ddoc.GetFirstView(), "IView")
    for raw in sheet_view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        note_row = {
            "text": str(note.GetText() or ""),
            "linked_text": str(note.PropertyLinkedText or ""),
            "extent": json_value(tuple(note.GetExtent() or ())),
            "visible": int(annotation.Visible),
        }
        if len(note_row["extent"]) != 6:
            raise RuntimeError("sheet note returned incomplete native extents")
        if note_row["text"] and note_row["visible"] == 1:
            bounds = asdict(annotation_box(adapter, annotation))
            bounds.pop("name")
            note_row["measured"] = json_value(bounds)
        notes.append(note_row)
    edge_break = [
        row
        for row in notes
        if " ".join(row["text"].upper().split()) == common._METRIC_EDGE_BREAK_NOTE
    ]
    if len(edge_break) != 1 or any(
        " ".join(row["text"].upper().split()) == common._OLD_EDGE_BREAK_NOTE
        for row in notes
    ):
        raise RuntimeError("metric edge-break note did not persist exactly once")
    if not ddoc.GetEditSheet():
        raise RuntimeError("derived drawing is still in edit-template mode")
    return {
        "units": units,
        "dimension_styles": styles,
        "sheet_properties": json_value(tuple(sheet.GetProperties2() or ())),
        "sheet_notes": semantic_multiset(notes),
        "sheet_mode": "edit_sheet",
    }


def load_recipe(commit, target, directory, source_root):
    if target not in TARGETS:
        raise ValueError(f"unsupported first-control target: {target}")
    code = recipes.recipe_source(commit, target)
    source_path = directory / "recipe-source.py"
    tree = recipes.redirected_tree(code, str(source_path))
    source = (source_root / f"{DRAWINGS_BY_NAME[target].artifact_stem}.SLDPRT").resolve(
        strict=True
    )
    sources = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "SOURCE"
    ]
    if len(sources) != 1:
        raise ValueError("recipe requires one module-global SOURCE declaration")
    sources[0].value = ast.Name("_benchmark_source", ast.Load())
    setup_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "new_project_drawing"
    ]
    if len(setup_calls) != 1 or len(setup_calls[0].args) != 1:
        raise ValueError("recipe requires exactly one direct new_project_drawing call")
    keywords = {keyword.arg: keyword.value for keyword in setup_calls[0].keywords}
    if set(keywords) - {"property_view", "scale", "decimals"}:
        raise ValueError("recipe has unsupported setup arguments")
    scale_node = keywords.get("scale")
    if not isinstance(scale_node, ast.Name) or scale_node.id != "SHEET_SCALE":
        raise ValueError(
            "recipe setup scale must use the explicit SHEET_SCALE constant"
        )
    decimals = ast.literal_eval(keywords["decimals"]) if "decimals" in keywords else 2
    basename = f"{source.stem}-{directory.parent.name}-{directory.name}"
    outputs = common.DrawingOutputs(
        directory / f"{basename}.SLDDRW",
        directory / f"{basename}.pdf",
        directory / f"{basename}.png",
    )
    module = types.ModuleType("template_benchmark_" + basename.replace("-", "_"))
    module.__file__ = str(source_path)
    module._benchmark_source = source
    module._benchmark_paths = {
        "OUTPUTS": outputs,
        "SLDDRW": outputs.slddrw,
        "PDF": outputs.pdf,
        "PNG": outputs.png,
    }
    source_path.write_text(code, encoding="utf-8")
    sys.modules[module.__name__] = module
    exec(
        compile(ast.fix_missing_locations(tree), str(source_path), "exec"),
        module.__dict__,
    )
    if (
        module.SOURCE != source
        or module.OUTPUTS != outputs
        or module.new_project_drawing is not common.new_project_drawing
    ):
        raise ValueError("recipe rebound isolated source/output/setup contracts")
    return module, TemplateSpec(module.SHEET_SCALE, decimals)


def finished_snapshot(adapter, spec):
    """Fresh persisted witnesses; excluded attachment kinds remain explicit."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    geometry = attachments.snapshot(model, app=adapter.swApp)
    native, semantic, view_modes = {}, [], []
    for view_key, view in attachments.views(model).items():
        role = {
            "orientation": str(view.GetOrientationName()),
            "source": geometry["models"][view_key],
            "position": tuple(view.Position),
            "scale": float(view.ScaleDecimal),
            "angle": float(view.Angle),
            "display_mode": int(view.GetDisplayMode2()),
            "faceted_hlr": bool(view.GetFacettedHlrDisplay()),
            "precision_cosmetic_threads": bool(view.GetCThreadQuality()),
            "tangent_edges": int(view.GetDisplayTangentEdges2()),
            "parent_display_mode": bool(view.GetUseParentDisplayMode()),
            "edges_in_shaded_mode": bool(view.GetDisplayEdgesInShadedMode()),
        }
        view_modes.append(role)
        for raw in view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            kind = int(annotation.GetType())
            key = f"{view_key}/{annotation.GetName()}/{kind}"
            visible = int(annotation.Visible)
            row = {"view": role, "kind": kind, "visible": visible}
            if visible == 1:
                bounds = asdict(annotation_box(adapter, annotation))
                bounds.pop("name")
                row["measured"] = bounds
            for section in (
                "checked",
                "excluded",
                "dimensions",
                "dimensions_excluded",
                "semantic_attachments",
            ):
                if key in geometry[section]:
                    row[section] = geometry[section][key]
            native[key] = json_value(row)
            comparable = dict(row)
            if "semantic_attachments" in comparable:
                comparable["semantic_attachments"] = semantic_attachment(
                    comparable["semantic_attachments"], geometry, view_key
                )
            semantic.append(comparable)
    return {
        "defaults": defaults_snapshot(adapter, spec),
        "attachments": geometry,
        "layout": attachments.layout(model),
        "native_annotations": native,
        "semantic_annotations": semantic_multiset(semantic),
        "view_modes": semantic_multiset(view_modes),
    }


def compare_reopened(before, after):
    attachments.compare(
        before["attachments"], after["attachments"], "template benchmark reopen"
    )
    attachments.check_layout(
        before["layout"], after["layout"], "template benchmark reopen"
    )
    for section in ("defaults", "native_annotations", "view_modes"):
        compare_exact(before[section], after[section], "reopen " + section)


async def prepare_template(adapter, spec, directory, row):
    from diagnostics._owned_native_documents import DocumentKind

    path = directory / "derived.DRWDOT"
    if path.exists():
        raise ValueError("derived template target already exists")
    started = time.perf_counter()
    row.update(path=str(path), spec=asdict(spec), status="running")
    try:
        with _telemetry.span("diagnostic.template.prepare"):
            with adapter.ownership.creating_document(DocumentKind.DRAWING, path):
                draw, _ = common.new_project_drawing(
                    adapter, scale=spec.scale, decimals=spec.decimals
                )
            row["before"] = defaults_snapshot(adapter, spec)
            with adapter.ownership.saving_as(path):
                save_prepared_template(draw, path, row)
            check("close prepared template", await adapter.close_model(save=False))
            with adapter.ownership.creating_document(
                DocumentKind.DRAWING, directory / "verification.SLDDRW"
            ):
                inherited_drawing(adapter, path, spec)
            row["reopened"] = defaults_snapshot(adapter, spec)
            compare_exact(
                row["before"], row["reopened"], "derived template new-document readback"
            )
            check(
                "close template verification drawing",
                await adapter.close_model(save=False),
            )
        row.update(sha256=attachments.file_digest(path), status="passed")
    except Exception as error:
        row.update(status="failed", error=str(error))
        raise
    finally:
        row["seconds"] = time.perf_counter() - started
    return row


async def run_trial(adapter, module, spec, variant, template, row):
    from diagnostics._owned_native_documents import DocumentKind

    def setup(current_adapter, **kwargs):
        check_setup_arguments(spec, kwargs)
        with adapter.ownership.creating_document(
            DocumentKind.DRAWING, module.OUTPUTS.slddrw
        ):
            started = time.perf_counter()
            try:
                with _telemetry.span("diagnostic.template.setup", variant=variant):
                    result = (
                        common.new_project_drawing(current_adapter, **kwargs)
                        if variant == "baseline"
                        else inherited_drawing(
                            current_adapter, Path(template["path"]), spec
                        )
                    )
            finally:
                row.setdefault("setup_seconds", []).append(
                    time.perf_counter() - started
                )
        return result

    original_finalize = module.finalize_drawing

    async def finalize(current_adapter, outputs, **kwargs):
        if outputs != module.OUTPUTS:
            raise RuntimeError("recipe bypassed its isolated output contract")
        with adapter.ownership.saving_as(outputs.slddrw):
            return await original_finalize(current_adapter, outputs, **kwargs)

    module.finalize_drawing = finalize
    started = time.perf_counter()
    try:
        with (
            replaced_setup(module, setup),
            _telemetry.span("diagnostic.template.recipe", variant=variant),
        ):
            artifacts = await module.build(adapter)
    finally:
        row["recipe_seconds"] = time.perf_counter() - started
        module.finalize_drawing = original_finalize
    if len(row.get("setup_seconds", ())) != 1:
        raise RuntimeError("recipe did not invoke setup exactly once")
    row["artifacts"] = recipes.validate_artifacts(artifacts, module.OUTPUTS)
    started = time.perf_counter()
    try:
        with _telemetry.span("diagnostic.template.persisted_checks", variant=variant):
            model = _early_bound(adapter.currentModel, "IModelDoc2")
            if Path(model.GetPathName()).resolve() != module.OUTPUTS.slddrw.resolve():
                raise RuntimeError(
                    "recipe did not leave its exact saved drawing active"
                )
            row["saved"] = finished_snapshot(adapter, spec)
            check("close benchmark drawing", await adapter.close_model(save=False))
            check(
                "reopen benchmark drawing",
                await adapter.open_model(str(module.OUTPUTS.slddrw)),
            )
            row["reopened"] = finished_snapshot(adapter, spec)
            compare_reopened(row["saved"], row["reopened"])
            check(
                "close reopened benchmark drawing",
                await adapter.close_model(save=False),
            )
    finally:
        row["validation_seconds"] = time.perf_counter() - started


async def benchmark(adapter, targets, commit, source_root, report_root):
    if len(targets) != len(set(targets)) or set(targets) - set(TARGETS):
        raise ValueError("benchmark needs unique supported target names")
    report_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="template-abba-", dir=report_root))
    adapter.ownership.register_directory(run_dir)
    sources = {
        target: (
            source_root / f"{DRAWINGS_BY_NAME[target].artifact_stem}.SLDPRT"
        ).resolve(strict=True)
        for target in targets
    }
    immutable = immutable_hashes([common.PROJECT_DRWDOT, *sources.values()])
    for path in immutable:
        adapter.ownership.register_source(path)
    inputs = runtime_fingerprints()
    report = {
        "status": "running",
        "revision": commit,
        "helper_revision": recipes.revision("HEAD"),
        "helper_inputs": inputs,
        "immutable_sources": immutable,
        "order": ORDER,
        "template_preparations": [],
        "trials": [],
        "scope": "same current direct part recipes; inherited defaults only; observed ABBA timings, not fleet speedup/risk",
        "timing_scope": "setup inner helper; recipe body includes ownership guards; extra persisted checks and one-time template preparation reported separately",
    }
    report_path = run_dir / "measurements.json"

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    templates = {}
    checkpoint()
    try:
        for target in targets:
            baseline_semantic = None
            for index, variant in enumerate(ORDER):
                directory = run_dir / f"{target}-{index}-{variant}"
                directory.mkdir()
                adapter.ownership.register_directory(directory)
                module, spec = load_recipe(commit, target, directory, source_root)
                if module.SOURCE != sources[target] or immutable_changes(immutable):
                    raise RuntimeError("pinned source/template changed between trials")
                source_hash = immutable[str(module.SOURCE)]
                if spec not in templates:
                    template_dir = run_dir / f"variant-{len(templates)}"
                    template_dir.mkdir()
                    adapter.ownership.register_directory(template_dir)
                    prepared = {}
                    report["template_preparations"].append(prepared)
                    checkpoint()
                    templates[spec] = await prepare_template(
                        adapter, spec, template_dir, prepared
                    )
                    checkpoint()
                template = templates[spec]
                row = {
                    "target": target,
                    "variant": variant,
                    "index": index,
                    "status": "running",
                    "spec": asdict(spec),
                    "source": str(module.SOURCE),
                    "source_sha256": source_hash,
                    "recipe_sha256": attachments.file_digest(
                        directory / "recipe-source.py"
                    ),
                }
                report["trials"].append(row)
                checkpoint()
                try:
                    recipes.check_fingerprints(
                        inputs,
                        runtime_fingerprints(),
                        "benchmark runtime inputs",
                    )
                    compare_exact(
                        template["sha256"],
                        attachments.file_digest(template["path"]),
                        "derived template input",
                    )
                    await run_trial(adapter, module, spec, variant, template, row)
                    if baseline_semantic is None:
                        baseline_semantic = cross_arm_signature(row["reopened"])
                    compare_exact(
                        baseline_semantic,
                        cross_arm_signature(row["reopened"]),
                        "cross-arm manufacturing/layout",
                    )
                    compare_exact(
                        source_hash,
                        attachments.file_digest(module.SOURCE),
                        "source part hash",
                    )
                    recipes.check_fingerprints(
                        inputs,
                        runtime_fingerprints(),
                        "benchmark runtime inputs",
                    )
                    row["status"] = "passed"
                except Exception as error:
                    row.update(status="failed", error=str(error))
                    raise
                finally:
                    checkpoint()
                    try:
                        await adapter.close_owned_documents()
                    except Exception as cleanup_error:
                        row.update(status="failed", cleanup_error=repr(cleanup_error))
                        raise
                    finally:
                        checkpoint()
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        report["immutable_input_changes"] = immutable_changes(immutable)
        report["derived_template_changes"] = immutable_changes(
            {row["path"]: row["sha256"] for row in templates.values()}
        )
        if report["immutable_input_changes"] or report["derived_template_changes"]:
            report["status"] = "failed"
        checkpoint()
        if report["immutable_input_changes"] or report["derived_template_changes"]:
            raise RuntimeError(
                "immutable benchmark inputs changed; see retained report"
            )
    return {"measurements": str(report_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", choices=TARGETS)
    parser.add_argument("--recipe-revision", default="HEAD")
    parser.add_argument("--source-root", type=Path, default=ROOT / "cad/out/sldprt")
    parser.add_argument(
        "--report-root", type=Path, default=ROOT / "cad/out/reports/template-defaults"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    commit = recipes.revision(args.recipe_revision)
    source_root = args.source_root.resolve(strict=True)
    report_root = args.report_root.resolve()
    if args.worker:
        from diagnostics._owned_native_documents import run_copy_diagnostic

        return run_copy_diagnostic(
            lambda adapter: benchmark(
                adapter, args.targets, commit, source_root, report_root
            )
        )
    import dodo

    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            *args.targets,
            "--recipe-revision",
            commit,
            "--source-root",
            str(source_root),
            "--report-root",
            str(report_root),
            "--worker",
        ],
        "drawing template defaults ABBA",
        log_stem="template-defaults-abba",
        com=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
