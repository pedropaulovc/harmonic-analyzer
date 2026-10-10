"""Cross-drawing contract for the four remaining simple assembly drawings."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import _assembly_drawing
import draw_ch_channel_assembly
import draw_dt_drive_train_assembly
import draw_fr_frame_assembly
import draw_ha_harmonic_analyzer_assembly
import draw_mg_magnifier_assembly
import draw_ms_measuring_stick_assembly
import draw_pd_paper_drive_assembly
import draw_pn_pen_assembly
import draw_sm_summing_assembly
from _drawing_common import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    DrawingOutputs,
)
from _drawing_registry import DRAWINGS, DrawingLayout
from test_simplified_helpers import HLR, FakeDrawing, FakeView


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ASSEMBLY_DRAWINGS = (
    draw_pn_pen_assembly,
    draw_ch_channel_assembly,
    draw_dt_drive_train_assembly,
    draw_fr_frame_assembly,
    draw_mg_magnifier_assembly,
    draw_pd_paper_drive_assembly,
    draw_sm_summing_assembly,
    draw_ms_measuring_stick_assembly,
    draw_ha_harmonic_analyzer_assembly,
)

SIMPLE_ASSEMBLY_DRAWINGS = tuple(
    drawing
    for drawing in ASSEMBLY_DRAWINGS
    # The channel sheet left the shared builder when it gained the rocker
    # bank's fit-up steps (#743, Codex PRRT_kwDOPHDy386mRSOK); the paper-drive
    # sheet left it when it became three sheets with its own fit-up steps; the
    # measuring-stick sheet is a full fitter package (BOM, explode, steps).
    if drawing
    not in (
        draw_fr_frame_assembly,
        draw_dt_drive_train_assembly,
        draw_ch_channel_assembly,
        draw_pd_paper_drive_assembly,
        draw_ms_measuring_stick_assembly,
    )
)


def test_registry_contains_exactly_the_nine_assembly_drawings() -> None:
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
            str(path) for path in (*spec.outputs.values(), spec.layout_report)
        }
        deps = dodo._drawing_file_deps(spec.name)
        assert str(spec.source) in deps
        assert dodo._assembly_execution_token(spec.part) in deps
        if drawing is draw_fr_frame_assembly:
            frame_dir = Path(draw_fr_frame_assembly.__file__).resolve().parent
            assert {
                str(frame_dir / "fr_frame_attachment_spec.py"),
                str(frame_dir / "vn_frame_cross_screw_spec.py"),
                str(frame_dir / "vn_tube_frame_cap_spec.py"),
            } <= set(deps)
            assert str(Path(_assembly_drawing.__file__).resolve()) not in deps
        elif drawing is draw_ch_channel_assembly:
            scripts_dir = Path(draw_ch_channel_assembly.__file__).resolve().parent
            assert {
                str(scripts_dir / "ch_channel_assembly_steps.py"),
                str(scripts_dir / "rocker_bank_layout.py"),
            } <= set(deps)
            assert str(Path(_assembly_drawing.__file__).resolve()) not in deps
        elif drawing is draw_dt_drive_train_assembly:
            scripts_dir = Path(draw_dt_drive_train_assembly.__file__).resolve().parent
            assert str(scripts_dir / "dt_drive_train_assembly_spec.py") in deps
            assert str(Path(_assembly_drawing.__file__).resolve()) not in deps
        elif drawing is draw_pd_paper_drive_assembly:
            scripts_dir = Path(draw_pd_paper_drive_assembly.__file__).resolve().parent
            # The steps module, the drive-train steps it reuses, and every
            # spec/geometry module whose constants the sheets print.
            assert {
                str(scripts_dir / name)
                for name in (
                    "pd_paper_drive_assembly_steps.py",
                    "dt_drive_train_steps.py",
                    "vn_transgear_collar_cross_pin_spec.py",
                    "pd_transgear_drive_collar_spec.py",
                    "vn_transgear_disc_screw_spec.py",
                    "vn_transgear_pivot_screw_spec.py",
                    "pd_transgear_knob_shaft_spec.py",
                    "transgear_hanger_joints.py",
                    "pd_latch_hook_geometry.py",
                )
            } <= set(deps)
            assert str(Path(_assembly_drawing.__file__).resolve()) not in deps
        elif drawing is draw_ms_measuring_stick_assembly:
            scripts_dir = Path(draw_ms_measuring_stick_assembly.__file__).resolve().parent
            # The spec module (poses, explode plan, steps text) and the pure
            # part/vendor specs whose constants the sheets print.
            assert {
                str(scripts_dir / name)
                for name in (
                    "ms_measuring_stick_assembly_spec.py",
                    "ms_stop_spec.py",
                    "ms_stick_spec.py",
                    "_mcmaster_91882a221.py",
                    "_mcmaster_90114a124.py",
                )
            } <= set(deps)
            assert str(Path(_assembly_drawing.__file__).resolve()) not in deps
        else:
            assert str(Path(_assembly_drawing.__file__).resolve()) in deps


def test_each_simple_recipe_is_only_a_precomputed_shared_builder_call() -> None:
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
    for drawing in SIMPLE_ASSEMBLY_DRAWINGS:
        source = Path(drawing.__file__).read_text(encoding="utf-8")
        assert "return await build_simple_three_view_drawing(" in source
        assert "place_view(" not in source
        assert "SHEET_NAMES" not in source
        assert "BOM_" not in source
        assert "ASSEMBLY_NOTES" not in source
        assert not any(token in source for token in prohibited), drawing.ARTIFACT_STEM


def test_each_simple_recipe_forwards_its_registered_layout(monkeypatch) -> None:
    for drawing in SIMPLE_ASSEMBLY_DRAWINGS:
        forwarded: list[dict[str, object]] = []

        async def build_shared(_adapter, **kwargs):
            forwarded.append(kwargs)
            return {"pdf": "forwarded"}

        monkeypatch.setattr(drawing, "build_simple_three_view_drawing", build_shared)

        result = asyncio.run(drawing.build(object()))

        assert result == {"pdf": "forwarded"}
        assert len(forwarded) == 1
        assert forwarded[0]["layout"] is drawing.SPEC.layout


def test_each_simple_three_view_layout_has_distinct_left_to_right_centers() -> None:
    for drawing in SIMPLE_ASSEMBLY_DRAWINGS:
        front_x, _front_y = drawing.FRONT_CENTER
        right_x, _right_y = drawing.RIGHT_CENTER
        iso_x, _iso_y = drawing.ISO_CENTER
        assert front_x < right_x < iso_x, drawing.ARTIFACT_STEM
        assert right_x - front_x >= 0.065, drawing.ARTIFACT_STEM
        assert iso_x - right_x >= 0.065, drawing.ARTIFACT_STEM


def test_shared_builder_places_named_views_without_per_script_visual_overrides() -> (
    None
):
    source = Path(_assembly_drawing.__file__).read_text(encoding="utf-8")
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
    views: list[FakeView] = []
    adapter = SimpleNamespace(
        open_model=lambda _path: None, currentModel=FakeDrawing(views)
    )

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
        "read_required_properties",
        lambda model, names, *, required: calls.append(("props", names, required)),
    )
    monkeypatch.setattr(
        _assembly_drawing,
        "new_project_drawing",
        lambda _adapter, *, layout, scale: calls.append(("new", layout, scale)),
    )

    def place(_adapter, path, name, x, y, *, scale):
        calls.append(("view", path, name, x, y, scale))
        views.append(FakeView(scale, name, HLR))
        return views[-1]

    monkeypatch.setattr(_assembly_drawing, "place_view", place)

    async def finalize(_adapter, actual_outputs, *, layout, pdf_title, scale):
        calls.append(("finalize", actual_outputs, layout, pdf_title, scale))
        return {"pdf": str(actual_outputs.pdf)}

    monkeypatch.setattr(_assembly_drawing, "finalize_drawing", finalize)

    result = asyncio.run(
        _assembly_drawing.build_simple_three_view_drawing(
            adapter,
            source=source,
            outputs=outputs,
            layout=DrawingLayout.PORTRAIT,
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
    assert ("new", DrawingLayout.PORTRAIT, (1.0, 4.0)) in calls
    assert (
        "finalize",
        outputs,
        DrawingLayout.PORTRAIT,
        "Assembly Drawing",
        (1.0, 4.0),
    ) in calls
    # The small front and right views print the simplified configuration; the
    # isometric is the drawing's designated full-detail view.
    assert [view.ReferencedConfiguration for view in views] == [
        SIMPLIFIED_VIEW_CONFIGURATION,
        SIMPLIFIED_VIEW_CONFIGURATION,
        ASSEMBLY_VIEW_CONFIGURATION,
    ]
