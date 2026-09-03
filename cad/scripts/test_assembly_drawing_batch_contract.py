"""Cross-drawing contracts for the eight three-sheet assembly packages."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import SimpleNamespace

import _assembly_drawing
import draw_channel_assembly
import draw_drive_train_assembly
import draw_frame_assembly
import draw_harmonic_analyzer_assembly
import draw_magnifier_assembly
import draw_paper_drive_assembly
import draw_pen_assembly
import draw_summing_assembly
from _drawing_registry import DRAWINGS


REPO_ROOT = Path(__file__).resolve().parents[2]
ASSEMBLY_DRAWINGS = (
    draw_pen_assembly,
    draw_channel_assembly,
    draw_drive_train_assembly,
    draw_frame_assembly,
    draw_magnifier_assembly,
    draw_paper_drive_assembly,
    draw_summing_assembly,
    draw_harmonic_analyzer_assembly,
)


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_contains_exactly_the_eight_assembly_packages() -> None:
    registered = tuple(spec for spec in DRAWINGS if spec.source_kind == "assembly")
    assert {spec.script for spec in registered} == {
        Path(drawing.__file__).resolve() for drawing in ASSEMBLY_DRAWINGS
    }


def test_registry_tasks_keep_source_tokens_and_package_helper_as_dependencies() -> None:
    dodo = _load_dodo()
    tasks = {task["name"]: task for task in dodo.task_drawing()}
    for drawing in ASSEMBLY_DRAWINGS:
        spec = drawing.SPEC
        assert spec.name in tasks
        assert set(tasks[spec.name]["targets"]) == {
            str(path) for path in spec.outputs.values()
        }
        deps = dodo._drawing_file_deps(spec.name)
        assert str(spec.source) in deps
        assert dodo._assembly_execution_token(spec.part) in deps
        assert str(Path(_assembly_drawing.__file__).resolve()) in deps


def test_each_entry_point_supplies_real_package_content() -> None:
    for drawing in ASSEMBLY_DRAWINGS:
        source = inspect.getsource(drawing)
        assert "return await build_assembly_package(" in source
        assert "build_simple_three_view_drawing" not in source
        assert len(drawing.ASSEMBLY_STEPS) >= 4
        assert len(drawing.CRITICAL_CHECKS) >= 2
        assert len(drawing.HARDWARE_NOTES) >= 1
        lines = (
            *drawing.ASSEMBLY_STEPS,
            *drawing.CRITICAL_CHECKS,
            *drawing.HARDWARE_NOTES,
        )
        assert all(line.strip() and len(line) <= 96 for line in lines)


def test_shared_recipe_requires_exploded_bom_balloons_and_procedure_sheets() -> None:
    assert _assembly_drawing.SHEET_NAMES == (
        "ASSEMBLED VIEWS",
        "EXPLODED AND BOM",
        "ASSEMBLY PROCEDURE",
    )
    source = inspect.getsource(_assembly_drawing.build_assembly_package)
    for token in (
        "create_blank_drawing_sheets",
        "insert_bom_table",
        "_validate_assembly_bom_columns",
        "add_auto_balloons_across_views",
        "ShowExploded(True)",
        "IsExploded()",
        "ORDERED ASSEMBLY",
        "HARDWARE / CONSUMABLES",
        "ORIENTATION / ADJUSTMENT / ACCEPTANCE",
        "expected_sheet_names=SHEET_NAMES",
    ):
        assert token in source
    assert "HAS NO EXPLODED STATE" not in source
    assert "has no exploded view" in source


def test_bom_metadata_comes_from_active_unsuppressed_components(monkeypatch) -> None:
    def part(title: str, number: str):
        return SimpleNamespace(
            GetCustomInfoValue=lambda configuration, name: {
                "Title": title,
                "Number": number,
            }.get(name, "")
        )

    components = (
        SimpleNamespace(
            IsSuppressed=lambda: False,
            GetPathName=lambda: r"C:\cad\parts\shaft.SLDPRT",
            GetModelDoc2=lambda: part("Drive Shaft", "MHA-101"),
            ReferencedConfiguration="Default",
        ),
        SimpleNamespace(
            IsSuppressed=lambda: False,
            GetPathName=lambda: r"C:\cad\parts\shaft.SLDPRT",
            GetModelDoc2=lambda: part("Drive Shaft", "MHA-101"),
            ReferencedConfiguration="Default",
        ),
        SimpleNamespace(
            IsSuppressed=lambda: True,
            GetPathName=lambda: r"C:\cad\parts\hidden.SLDPRT",
            GetModelDoc2=lambda: part("Hidden", "MHA-999"),
            ReferencedConfiguration="Default",
        ),
    )
    model = SimpleNamespace(
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        ),
        ResolveAllLightWeightComponents=lambda top_only: 0,
        GetComponents=lambda top_only: components,
        GetExplodedViewCount2=lambda configuration: 1,
    )
    adapter = SimpleNamespace(
        _attempt=lambda operation, default=None: operation(),
    )
    monkeypatch.setattr(
        _assembly_drawing, "_early_bound", lambda value, interface: value
    )

    metadata = _assembly_drawing._read_bom_metadata(adapter, model)

    assert metadata.components == ("shaft",)
    assert metadata.descriptions == {"shaft": "Drive Shaft"}
    assert metadata.aliases == {"mha-101": "shaft"}
    assert metadata.configuration == "Default"
    assert metadata.exploded_views == 1
