"""Output routing and provenance controls for the recipe-only ABBA runner."""

import ast
from contextlib import nullcontext
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from _drawing_common import DrawingOutputs
from diagnostics import benchmark_drawing_recipes as bench


def recipe(source):
    return f"""
from pathlib import Path
from _drawing_common import DrawingOutputs
SOURCE = Path({str(source)!r})
OUTPUTS = DrawingOutputs(Path("production.SLDDRW"), Path("production.pdf"), Path("production.png"))
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
ALIAS = OUTPUTS
def captured(outputs=OUTPUTS, pdf=PDF):
    return outputs, pdf
async def build(adapter):
    return await adapter.draw(OUTPUTS, SOURCE)
"""


def test_recipe_outputs_are_redirected_before_defaults_and_aliases(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        bench, "recipe_source", lambda *_: recipe(tmp_path / "part.SLDPRT")
    )
    module = bench.load_recipe("pinned", "cone_pivot_screw", tmp_path)
    assert module.ALIAS is module.OUTPUTS
    assert module.captured() == (module.OUTPUTS, module.OUTPUTS.pdf)
    assert module.PDF == module.OUTPUTS.pdf
    assert module.SLDDRW.parent == tmp_path
    assert module.__file__ == str(tmp_path / "recipe-source.py")


@pytest.mark.parametrize(
    "extra",
    [
        'OTHER = SPEC.outputs["pdf"]',
        'Path("production.pdf").write_bytes(b"overwrite")',
        'def build(adapter):\n    adapter.SaveAs3("production.SLDDRW", 0, 0)',
    ],
)
def test_unmanaged_output_paths_are_rejected_before_execution(extra):
    with pytest.raises(ValueError, match="bypasses"):
        bench.redirected_tree(recipe(Path("part.SLDPRT")) + extra, "recipe.py")


def test_mixed_output_declaration_fails_before_execution():
    with pytest.raises(ValueError, match="mixed output declaration"):
        bench.redirected_tree(
            "OUTPUTS = DrawingOutputs()\nPDF, OTHER = values", "recipe.py"
        )


@pytest.mark.parametrize(
    "declaration",
    [
        "OUTPUTS = PDF = values",
        "OUTPUTS = SLDDRW, PDF, PNG = values",
        "OUTPUTS, (PDF, PNG) = values",
        "OUTPUTS.pdf = values",
        "OUTPUTS[0] = values",
        "OUTPUTS, *PDF = values",
        "OUTPUTS: DrawingOutputs",
    ],
)
def test_unsupported_output_assignment_shapes_fail_before_execution(declaration):
    with pytest.raises(ValueError, match="output declaration"):
        bench.redirected_tree(declaration, "recipe.py")


def test_output_declaration_contract_is_required():
    with pytest.raises(ValueError, match="exactly one"):
        bench.redirected_tree("async def build(adapter):\n    return {}", "recipe.py")


@pytest.mark.parametrize("failure", ["missing", "empty", "other_path", "missing_kind"])
def test_exact_existing_nonempty_artifacts_are_required(tmp_path, failure):
    outputs = DrawingOutputs(
        tmp_path / "drawing.SLDDRW", tmp_path / "drawing.pdf", tmp_path / "drawing.png"
    )
    artifacts = {
        "drawing": str(outputs.slddrw),
        "pdf": str(outputs.pdf),
        "png": str(outputs.png),
    }
    for path in artifacts.values():
        Path(path).write_bytes(b"output")
    if failure == "missing":
        outputs.pdf.unlink()
    if failure == "empty":
        outputs.pdf.write_bytes(b"")
    if failure == "other_path":
        artifacts["pdf"] = str(tmp_path / "other.pdf")
    if failure == "missing_kind":
        del artifacts["pdf"]
    with pytest.raises(RuntimeError):
        bench.validate_artifacts(artifacts, outputs)


def test_dirty_helper_contents_change_fingerprint(tmp_path, monkeypatch):
    scripts = tmp_path / "cad/scripts"
    scripts.mkdir(parents=True)
    helper = scripts / "_drawing_common.py"
    helper.write_text("VERSION = 1")
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    before = bench.helper_fingerprints()
    helper.write_text("VERSION = 2")
    with pytest.raises(RuntimeError, match="helpers changed"):
        bench.check_fingerprints(before, bench.helper_fingerprints(), "helpers")


@pytest.mark.parametrize("change", ["contents", "added_resource", "removed_resource"])
def test_project_template_resources_are_fingerprinted(tmp_path, monkeypatch, change):
    templates = tmp_path / "cad/templates"
    templates.mkdir(parents=True)
    template = templates / "harmonic-analyzer.DRWDOT"
    template.write_bytes(b"original drawing template")
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    before = bench.helper_fingerprints()
    assert before[str(template.relative_to(tmp_path))] == bench.file_digest(template)
    if change == "contents":
        template.write_bytes(b"changed drawing template")
    if change == "added_resource":
        (templates / "project.SLDDRT").write_bytes(b"new sheet format")
    if change == "removed_resource":
        template.unlink()
    with pytest.raises(RuntimeError, match="resources changed"):
        bench.check_fingerprints(before, bench.helper_fingerprints(), "resources")


@pytest.mark.parametrize("mode", ["failed_close", "still_open"])
def test_close_documents_checks_result_and_remaining_document(monkeypatch, mode):
    app = SimpleNamespace(
        CloseAllDocuments=lambda _: mode != "failed_close",
        GetFirstDocument=lambda: object() if mode == "still_open" else None,
    )
    monkeypatch.setattr(bench, "_early_bound", lambda obj, _: obj)
    with pytest.raises(RuntimeError, match="did not close"):
        bench.close_documents(SimpleNamespace(swApp=app))


class Adapter:
    def __init__(self, mode):
        self.mode = mode
        self.drawn = []
        self.scoped_closes = []
        self.ownership = SimpleNamespace(
            register_directory=Mock(),
            register_source=Mock(),
            creating_document=Mock(side_effect=lambda *_: nullcontext()),
        )
        self.swApp = SimpleNamespace(
            CloseAllDocuments=lambda _: True, GetFirstDocument=lambda: None
        )

    async def close_owned_documents(self):
        self.scoped_closes.append(len(self.drawn))

    async def draw(self, outputs, source):
        self.drawn.append(outputs)
        if self.mode == "source_drift":
            source.write_bytes(b"changed part")
        artifacts = {"drawing": outputs.slddrw, "pdf": outputs.pdf, "png": outputs.png}
        for path in artifacts.values():
            path.write_bytes(b"drawing artifact")
        return {key: str(path) for key, path in artifacts.items()}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["normal", "source_drift", "helper_drift"])
async def test_abba_reports_actual_scope_and_rejects_input_drift(
    tmp_path, monkeypatch, mode
):
    source = tmp_path / "part.SLDPRT"
    source.write_bytes(b"original part")
    monkeypatch.setattr(bench, "recipe_source", lambda *_: recipe(source))
    monkeypatch.setattr(bench, "revision", lambda _: "helper-head")
    monkeypatch.setattr(bench, "_early_bound", lambda obj, _: obj)
    reads = []

    def helpers():
        reads.append(1)
        return {
            "helper.py": "drift"
            if mode == "helper_drift" and len(reads) > 2
            else "original"
        }

    monkeypatch.setattr(bench, "helper_fingerprints", helpers)
    adapter = Adapter(mode)
    monkeypatch.setattr(
        bench,
        "close_documents",
        Mock(
            side_effect=AssertionError("legacy global-close helper must remain unused")
        ),
    )
    reports = tmp_path / "reports"
    if mode == "normal":
        result = await bench.benchmark(
            adapter, ["cone_pivot_screw"], "base-sha", "candidate-sha", reports
        )
        result_path = Path(result["measurements"])
    else:
        with pytest.raises(RuntimeError, match="changed"):
            await bench.benchmark(
                adapter, ["cone_pivot_screw"], "base-sha", "candidate-sha", reports
            )
        (result_path,) = reports.glob("*/measurements.json")
    report = json.loads(result_path.read_text())
    assert report["helper_revision"] == "helper-head"
    assert report["helper_fingerprints"] == {"helper.py": "original"}
    assert report["baseline"] == "base-sha"
    assert report["candidate"] == "candidate-sha"
    assert "current helpers" in report["scope"]
    assert "observed paired recipe timings" in report["timing_scope"]
    assert report["status"] == ("passed" if mode == "normal" else "failed")
    assert len(adapter.drawn) == (4 if mode == "normal" else 1)
    assert adapter.scoped_closes == list(range(len(adapter.drawn)))
    assert adapter.ownership.creating_document.call_count == len(adapter.drawn)
    for call, outputs in zip(
        adapter.ownership.creating_document.call_args_list, adapter.drawn, strict=True
    ):
        assert call.args == (bench.DocumentKind.DRAWING, outputs.slddrw)
    assert len({outputs.slddrw for outputs in adapter.drawn}) == len(adapter.drawn)
    assert all(trial["seconds"] >= 0 for trial in report["trials"])
    if mode == "normal":
        assert [trial["variant"] for trial in report["trials"]] == list(bench._ORDER)
    else:
        assert report["trials"][0]["status"] == "failed"


def test_target_recipes_meet_output_redirection_contract():
    """The real initial pilot recipes must pass the same loader preflight."""
    for name in ("cone_pivot_screw", "arbor_pedestal"):
        path = bench.ROOT / f"cad/scripts/draw_{name}.py"
        tree = bench.redirected_tree(path.read_text(encoding="utf-8"), str(path))
        compile(ast.fix_missing_locations(tree), str(path), "exec")
