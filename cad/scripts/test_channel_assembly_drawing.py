"""Offline contracts for the channel ASSEMBLY drawing."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import draw_channel_assembly as drawing
from _drawing_registry import DRAWINGS, DRAWINGS_BY_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_registry_row_resolves_the_assembly_source() -> None:
    spec = DRAWINGS_BY_NAME["channel_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "channel"
    assert spec.source.as_posix().endswith("/out/sldasm/channel.SLDASM")
    assert spec.script == Path(drawing.__file__).resolve()


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/channel-assembly.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/channel-assembly.pdf")
    assert drawing.PNG.as_posix().endswith("/png/channel-assembly_drawing.png")
    assert drawing.SOURCE == DRAWINGS_BY_NAME["channel_assembly"].source


def test_part_rows_keep_their_part_source() -> None:
    """The assembly rows must not disturb the part-drawing rows."""
    for spec in DRAWINGS:
        if spec.source_kind == "assembly":
            continue
        assert spec.source.as_posix().endswith(
            f"/out/sldprt/{spec.artifact_stem}.SLDPRT"
        )


def test_dodo_deps_use_the_sldasm_recipe_and_exact_assembly_token() -> None:
    dodo = _load_dodo()
    deps = dodo._drawing_file_deps("channel_assembly")
    assert any(
        dep.replace("\\", "/").endswith("/out/sldasm/channel.SLDASM") for dep in deps
    )
    assert dodo._assembly_execution_token("channel") in deps
    assert dodo._part_execution_token("channel") not in deps
    assert any(dep.endswith("harmonic-analyzer.DRWDOT") for dep in deps)


def test_dodo_yields_the_assembly_drawing_task() -> None:
    dodo = _load_dodo()
    assert "channel_assembly" in dodo._drawing_order()
    task = next(
        task for task in dodo.task_drawing() if task["name"] == "channel_assembly"
    )
    targets = {Path(target).name for target in task["targets"]}
    assert targets == {
        "channel-assembly.SLDDRW",
        "channel-assembly.pdf",
        "channel-assembly_drawing.png",
    }


def test_bom_covers_every_placed_component() -> None:
    """Every BOM row corresponds to a component the channel build places.

    The channel build places components in per-active-channel loops, a
    bushing-bank seed + ``LocalLinearPattern``, ``CopyWithMates2`` slice
    replication and a batched ``place_components_batch`` cosmetic bank, so the
    check is a string presence test, not a ``place_component`` count -- the
    runtime ``insert_bom_table`` validates one BOM row per expected component.
    """
    source = (Path(__file__).parent / "build_channel_assembly.py").read_text(
        encoding="utf-8"
    )
    for component in drawing.BOM_COMPONENTS:
        assert f'"{component}"' in source, f"{component} not placed by the build"


def test_assembly_stamps_title_block_properties() -> None:
    source = (Path(__file__).parent / "build_channel_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "apply_custom_properties" in source
    assert "SEE COMPONENT DRAWINGS" in source
    assert "assembly_title_properties(ASM_NAME)" in source
    assert "part_properties(ASM_NAME)" not in source
    assert '"MHA-A02"' in source
    assert source.count('"Material": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Material Specification": "SEE COMPONENT DRAWINGS"') == 1
    assert source.count('"Finish": "SEE COMPONENT DRAWINGS"') == 1


def test_drawing_places_bom_and_balloons() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("insert_identified_bom_table(") == 1
    assert source.count("add_auto_balloons_across_views(") == 1
    assert source.count("position_bom_balloon(") == 2
    assert 'item_number="7"' in source
    assert "position_xy=(0.123, 0.075)" in source
    assert 'item_number="4"' in source
    assert "position_xy=(0.135, 0.075)" in source
    assert "margin=0.006" in source
    assert "add_component_bom_balloons" not in source
    assert "adapter, (front, right, iso)" in source
    assert drawing.SHEET_SCALE == (1.0, 7.0)
    assert source.count("scale=VIEW_SCALE") == 3  # every view pins its scale
    assert source.count("add_note(") == 1
    assert "20 CHANNEL CHAINS AT 7.06 PITCH" in drawing.ASSEMBLY_NOTES
    assert all(
        token not in drawing.ASSEMBLY_NOTES
        for token in ("MATERIAL", "FINISH", "UOS", "DEBUR", "BREAK SHARP")
    )


def test_manual_balloon_moves_are_locked_and_read_back() -> None:
    source = (Path(__file__).parent / "_drawing_common.py").read_text(encoding="utf-8")
    helper = source[source.index("def position_bom_balloon(") :]
    helper = helper[: helper.index("\ndef stamp_drawing_summary(")]
    assert "annotation.SetPosition(" in helper
    assert "annotation.SetPosition2(" not in helper
    assert "annotation.GetSpecificAnnotation()" in helper
    assert "annotation.GetPosition()" in helper
    assert "note.LockPosition = True" in helper
    assert "note.GetBalloonInfo()" in helper
    assert "for _attempt in range(3)" in helper
    assert "position_tolerance_m: float = 1e-6" in helper
