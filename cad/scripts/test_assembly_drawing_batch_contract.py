"""Cross-drawing contract for the eight simple assembly drawings."""

from __future__ import annotations

import asyncio
import importlib.util
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
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_registry_contains_exactly_the_eight_simple_assembly_drawings() -> None:
    registered = tuple(spec for spec in DRAWINGS if spec.source_kind == "assembly")
    assert {spec.script for spec in registered} == {
        Path(drawing.__file__).resolve() for drawing in ASSEMBLY_DRAWINGS
    }


def test_registry_task_names_outputs_and_assembly_dependencies_are_preserved() -> None:
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


def test_each_recipe_is_only_a_precomputed_shared_builder_call() -> None:
    prohibited = (
        "add_auto_balloons",
        "add_component_bom_balloons",
        "add_note(",
        "create_blank_drawing_sheets",
        "insert_bom_table",
        "insert_identified_bom_table",
        "set_hidden_lines_",
        "stamp_drawing_summary",
        "ViewDisplay",
    )
    for drawing in ASSEMBLY_DRAWINGS:
        source = Path(drawing.__file__).read_text(encoding="utf-8")
        assert "return await build_simple_three_view_drawing(" in source
        assert "place_view(" not in source
        assert "SHEET_NAMES" not in source
        assert "BOM_" not in source
        assert "ASSEMBLY_NOTES" not in source
        assert not any(token in source for token in prohibited), drawing.ARTIFACT_STEM


def test_each_three_view_layout_has_distinct_left_to_right_centers() -> None:
    for drawing in ASSEMBLY_DRAWINGS:
        front_x, _front_y = drawing.FRONT_CENTER
        right_x, _right_y = drawing.RIGHT_CENTER
        iso_x, _iso_y = drawing.ISO_CENTER
        assert front_x < right_x < iso_x, drawing.ARTIFACT_STEM
        assert right_x - front_x >= 0.065, drawing.ARTIFACT_STEM
        assert iso_x - right_x >= 0.065, drawing.ARTIFACT_STEM


def test_shared_builder_uses_default_visuals_and_three_named_views() -> None:
    source = Path(_assembly_drawing.__file__).read_text(encoding="utf-8")
    assert (
        '@_telemetry.traced("drawing.assembly.simple_three_view", '
        'label_param="pdf_title")' in source
    )
    assert source.count("place_view(") == 1
    assert '("*Front", front_center)' in source
    assert '("*Right", right_center)' in source
    assert '("*Isometric", iso_center)' in source
    assert "scale=sheet_scale" in source
    for token in (
        "set_hidden_lines_",
        "ViewDisplay",
        "DisplayMode",
        "add_note(",
        "balloon",
        "bom_table",
        "create_blank_drawing_sheets",
    ):
        assert token not in source


def test_shared_builder_places_exactly_front_right_and_isometric(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "assembly.SLDASM"
    source.touch()
    outputs = DrawingOutputs(
        slddrw=tmp_path / "assembly.SLDDRW",
        pdf=tmp_path / "assembly.pdf",
        png=tmp_path / "assembly.png",
    )
    adapter = SimpleNamespace(open_model=lambda _path: None)

    async def open_model(path: str) -> bool:
        calls.append(("open", path))
        return True

    calls: list[tuple[object, ...]] = []
    adapter.open_model = open_model
    monkeypatch.setattr(
        _assembly_drawing,
        "check",
        lambda _label, result: result,
    )
    monkeypatch.setattr(
        _assembly_drawing,
        "new_project_drawing",
        lambda _adapter, *, scale: calls.append(("new", scale)),
    )
    monkeypatch.setattr(
        _assembly_drawing,
        "place_view",
        lambda _adapter, path, name, x, y, *, scale: calls.append(
            ("view", path, name, x, y, scale)
        ),
    )

    async def finalize(_adapter, actual_outputs, *, pdf_title, scale):
        calls.append(("finalize", actual_outputs, pdf_title, scale))
        return {"pdf": str(actual_outputs.pdf)}

    monkeypatch.setattr(_assembly_drawing, "finalize_drawing", finalize)

    result = asyncio.run(
        _assembly_drawing.build_simple_three_view_drawing(
            adapter,
            source=source,
            outputs=outputs,
            sheet_scale=(1.0, 4.0),
            front_center=(0.1, 0.2),
            right_center=(0.2, 0.2),
            iso_center=(0.3, 0.2),
            pdf_title="Assembly Drawing",
        )
    )

    view_calls = [call for call in calls if call[0] == "view"]
    assert [call[2] for call in view_calls] == ["*Front", "*Right", "*Isometric"]
    assert [call[3:5] for call in view_calls] == [
        (0.1, 0.2),
        (0.2, 0.2),
        (0.3, 0.2),
    ]
    assert all(call[5] == (1.0, 4.0) for call in view_calls)
    assert result == {"pdf": str(outputs.pdf)}
