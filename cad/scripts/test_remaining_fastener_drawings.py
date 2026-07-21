"""Offline contracts for the six remaining PR 358 fastener sheets."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

import pytest

import _config
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener


@dataclass(frozen=True)
class Case:
    part_name: str
    module_name: str
    spec_name: str
    build_name: str
    shank_dim: str
    thread_on_dimension: bool = False


CASES = (
    Case(
        "cone-pivot-screw",
        "draw_cone_pivot_screw",
        "cone_pivot_screw_spec",
        "build_cone_pivot_screw",
        "ShankDiaDim",
    ),
    Case(
        "cone-tip-pinch-screw",
        "draw_cone_tip_pinch_screw",
        "cone_tip_pinch_screw_spec",
        "build_cone_tip_pinch_screw",
        "ShankDiaDim",
    ),
    Case(
        "hanger-screw",
        "draw_hanger_screw",
        "hanger_screw_spec",
        "build_hanger_screw",
        "ShankDia",
    ),
    Case(
        "pen-set-screw",
        "draw_pen_set_screw",
        "pen_set_screw_spec",
        "build_pen_set_screw",
        "ShankDia",
    ),
    Case(
        "swing-stop-screw",
        "draw_swing_stop_screw",
        "swing_stop_screw_spec",
        "build_swing_stop_screw",
        "ShankDiaDim",
    ),
    Case(
        "thumb-screw",
        "draw_thumb_screw",
        "thumb_screw_spec",
        "build_thumb_screw",
        "ShankDia",
    ),
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.part_name)
def test_registry_paths_and_marked_dimensions(case: Case) -> None:
    drawing = importlib.import_module(case.module_name)
    spec = importlib.import_module(case.spec_name)
    part = importlib.import_module(case.build_name)
    key = case.part_name.replace("-", "_")
    registered = DRAWINGS_BY_NAME[key]

    assert registered.script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith(f"/slddrw/{case.part_name}.SLDDRW")
    assert drawing.PDF.as_posix().endswith(f"/pdf/{case.part_name}.pdf")
    assert drawing.PNG.as_posix().endswith(f"/png/{case.part_name}_drawing.png")
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    kept = set(drawing.END_KEEP) | set(getattr(drawing, "SIDE_KEEP", {}))
    assert kept == set().union(*spec.DRAWING_DIMENSIONS.values())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.part_name)
def test_catalog_thread_and_dimension_callout_are_not_invented(case: Case) -> None:
    drawing = importlib.import_module(case.module_name)
    spec = importlib.import_module(case.spec_name)
    part = importlib.import_module(case.build_name)
    catalog = fastener(case.part_name)

    assert spec.THREAD == catalog.thread
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert part.SHANK_DIA == spec.SHANK_DIA
    assert part.SHANK_LEN == spec.SHANK_LEN
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC-2A"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}
    if case.part_name == "cone-pivot-screw":
        assert "GROUND" in spec.DRAWING_NOTES
        return
    assert "REFERENCE ONLY" in spec.DRAWING_NOTES
    assert "FULL THREAD" in spec.DRAWING_NOTES
    assert "END FACE SQUARE TO THREAD AXIS" in spec.DRAWING_NOTES


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.part_name)
def test_title_block_properties_are_complete(case: Case) -> None:
    config = _config.parts(case.part_name)
    assert config["number"].startswith("MHA-")
    assert config["material"] == config["material_specification"]
    assert config["finish"].strip()
    assert int(config["quantity"]) >= 1


@pytest.mark.parametrize(
    ("spec_name", "build_name"),
    (
        ("cone_pivot_screw_spec", "build_cone_pivot_screw"),
        ("cone_tip_pinch_screw_spec", "build_cone_tip_pinch_screw"),
        ("swing_stop_screw_spec", "build_swing_stop_screw"),
    ),
)
def test_slotted_screw_slot_dimensions_live_in_the_pure_contract(
    spec_name: str, build_name: str
) -> None:
    spec = importlib.import_module(spec_name)
    build_source = Path(importlib.import_module(build_name).__file__).read_text(
        encoding="utf-8"
    )
    assert spec.SLOT_W > 0
    assert spec.SLOT_D > 0
    assert f"{spec.SLOT_W:.2f} +/-0.10 WIDE" in spec.DRAWING_NOTES
    assert f"{spec.SLOT_D:.2f} +/-0.10 DEEP" in spec.DRAWING_NOTES
    assert "SLOT_W," in build_source
    assert "SLOT_D," in build_source


def test_cone_pivot_does_not_hide_the_missing_threaded_tail_definition() -> None:
    spec = importlib.import_module("cone_pivot_screw_spec")
    assert "THREADED-END LENGTH IS NOT DEFINED" in spec.DRAWING_NOTES
    assert "DO NOT RELEASE AS A MADE-PART DRAWING" in spec.DRAWING_NOTES
    assert "USE THE COMMERCIAL SHOULDER SCREW" in spec.DRAWING_NOTES


def test_cone_pivot_tail_view_exposes_the_ground_shoulder() -> None:
    drawing = importlib.import_module("draw_cone_pivot_screw")
    spec = importlib.import_module("cone_pivot_screw_spec")
    assert drawing.RECIPE.end_view == "*Bottom"
    assert drawing.RECIPE.side_center == (0.190, 0.170)
    assert spec.END_VIEW_NOTE == "SHOULDER-END VIEW"


def test_cone_tip_pinch_sheet_defines_a_flat_end_without_duplicate_head_diameter() -> None:
    drawing = importlib.import_module("draw_cone_tip_pinch_screw")
    spec = importlib.import_module("cone_tip_pinch_screw_spec")
    assert drawing.END_KEEP == {}
    assert drawing.RECIPE.side_center == (0.190, 0.190)
    assert spec.DRAWING_DIMENSIONS == {}
    assert "FLAT-END PINCH SCREW; NO CONICAL POINT" in spec.DRAWING_NOTES
    assert "DISTAL START CHAMFER" in spec.DRAWING_NOTES
    assert "MIDPLANE OFFSET FROM HEAD OD AXIS 0.00 +/-0.05" in spec.DRAWING_NOTES
    assert "DATUM A = THREAD PITCH-DIAMETER AXIS." in spec.DRAWING_NOTES
    assert "HEAD OD TOTAL RUNOUT 0.10 TO A" in spec.DRAWING_NOTES
    assert "BEARING FACE PERP 0.10 TO A" in spec.DRAWING_NOTES


@pytest.mark.parametrize("spec_name", ("hanger_screw_spec", "thumb_screw_spec"))
def test_long_reference_note_is_split_for_readable_rendering(spec_name: str) -> None:
    spec = importlib.import_module(spec_name)
    assert "THREAD GEOMETRY OMITTED IN VIEWS; SHANK OUTLINE REFERENCE ONLY." in (
        spec.DRAWING_NOTES
    )


def test_hanger_hex_head_is_controlled_to_thread_axis() -> None:
    spec = importlib.import_module("hanger_screw_spec")
    assert "DATUM A = THREAD PITCH-DIAMETER AXIS." in spec.DRAWING_NOTES
    assert "HEX CENTER WITHIN DIA 0.10 OF A" in spec.DRAWING_NOTES
    assert "BEARING FACE PERP 0.10 TO A" in spec.DRAWING_NOTES


def test_thumb_note_uses_short_lines_in_a_raised_lane() -> None:
    drawing = importlib.import_module("draw_thumb_screw")
    spec = importlib.import_module("thumb_screw_spec")
    assert drawing.RECIPE.note_xy == (0.020, 0.110)
    assert max(map(len, spec.DRAWING_NOTES.splitlines())) < 80


@pytest.mark.parametrize(
    "module_name",
    (
        "draw_bracket_screw",
        "draw_clamp_screw",
        "draw_fillister_screw",
        "draw_foot_screw",
        "draw_lag_screw",
        "draw_slotted_screw",
    ),
)
def test_custom_head_end_view_does_not_show_hidden_shank_circle(
    module_name: str,
) -> None:
    source = Path(importlib.import_module(module_name).__file__).read_text(
        encoding="utf-8"
    )
    assert "set_hidden_lines_removed(adapter, end)" in source
    assert "set_hidden_lines_visible(adapter, end)" not in source


@pytest.mark.parametrize(
    ("build_name", "spec_name"),
    (
        ("build_pen_set_screw", "pen_set_screw_spec"),
        ("build_thumb_screw", "thumb_screw_spec"),
    ),
)
def test_reeded_builder_uses_spec_groove_count(
    build_name: str, spec_name: str
) -> None:
    build = importlib.import_module(build_name)
    spec = importlib.import_module(spec_name)
    source = Path(build.__file__).read_text(encoding="utf-8")
    assert build.GROOVE_COUNT == spec.GROOVE_COUNT
    assert "groove_count=GROOVE_COUNT" in source
    assert "DATUM A = THREAD PITCH-DIAMETER AXIS." in spec.DRAWING_NOTES
    head_name = "KNOB" if spec_name == "pen_set_screw_spec" else "HEAD"
    assert f"{head_name} OD TOTAL RUNOUT 0.10 TO A" in spec.DRAWING_NOTES
    assert "BEARING FACE PERP 0.10 TO A" in spec.DRAWING_NOTES
