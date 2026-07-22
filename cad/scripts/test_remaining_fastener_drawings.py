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
        "ShoulderDiaDim",
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
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC-2A"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}
    if case.part_name == "cone-pivot-screw":
        assert spec.SHOULDER_DIA == catalog.model_diameter_mm
        assert spec.UNDERHEAD_LEN == catalog.length_mm
        assert part.SHOULDER_DIA == spec.SHOULDER_DIA
        assert part.SHOULDER_LEN == spec.SHOULDER_LEN
        assert part.THREAD_TAIL_LEN == spec.THREAD_TAIL_LEN
        assert "GROUND" in spec.DRAWING_NOTES
        return
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert part.SHANK_DIA == spec.SHANK_DIA
    assert part.SHANK_LEN == spec.SHANK_LEN
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


def test_cone_pivot_defines_shoulder_clearance_and_thread_engagement() -> None:
    spec = importlib.import_module("cone_pivot_screw_spec")
    base = importlib.import_module("build_harmonic_base")
    platform = importlib.import_module("build_cone_swing_platform")

    assert spec.SHOULDER_LEN == spec.PLATFORM_THICKNESS + spec.AXIAL_CLEARANCE
    assert spec.PLATFORM_THICKNESS == platform.PLATE_T
    assert platform.PIVOT_HOLE_DIA > spec.SHOULDER_DIA
    assert spec.THREAD_TAIL_LEN >= spec.SHOULDER_DIA
    assert base.PIVOT_SEAT_SPEC.kind == "tapped"
    assert base.PIVOT_SEAT_SPEC.size == spec.THREAD
    assert base.PIVOT_SEAT_SPEC.thread_class == "2B"
    assert base.PIVOT_HOLE_DEPTH - spec.THREAD_TAIL_LEN >= 1.5
    assert "DO NOT RELEASE" not in spec.DRAWING_NOTES
    assert f"THREAD LENGTH {spec.THREAD_TAIL_LEN:.2f}" in spec.DRAWING_NOTES
    assert f"{spec.MIN_FULL_FORM:.2f} MIN FULL-FORM THREAD" in spec.DRAWING_NOTES
    assert "INCOMPLETE THREAD/RUNOUT AT SHOULDER 1P MAX" in spec.DRAWING_NOTES
    assert (
        spec.THREAD_TAIL_LEN
        - spec.THREAD_LENGTH_TOL
        - spec.THREAD_RUNOUT_PITCHES * spec.THREAD_PITCH
        - spec.DISTAL_CHAMFER
        >= spec.MIN_FULL_FORM
    )
    assert f"MATING PLATE THICKNESS {spec.PLATFORM_THICKNESS:.2f} MAX" in (
        spec.DRAWING_NOTES
    )
    assert f"{spec.AXIAL_CLEARANCE:.2f} MIN AXIAL CLEARANCE" in spec.DRAWING_NOTES


def test_cone_pivot_tail_view_exposes_the_ground_shoulder() -> None:
    drawing = importlib.import_module("draw_cone_pivot_screw")
    spec = importlib.import_module("cone_pivot_screw_spec")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    build_source = Path(
        importlib.import_module("build_cone_pivot_screw").__file__
    ).read_text(encoding="utf-8")
    assert drawing.RECIPE.end_view == "*Bottom"
    assert drawing.RECIPE.side_center == (0.190, 0.170)
    assert spec.END_VIEW_NOTE == "SHOULDER-END VIEW"
    assert set(drawing.SIDE_KEEP) == {"HeadHt", "ShoulderLg", "ThreadLg"}
    assert drawing.SIDE_DIMENSION_CALLOUTS["ThreadLg"] == "1/4-20 UNC-2A"
    assert drawing.RECIPE.decorate is drawing._decorate
    assert drawing_source.count("add_datum_feature(") == 1
    assert drawing_source.count("add_feature_control_frame(") == 3
    assert drawing_source.count("add_surface_finish(") == 1
    assert build_source.count("set_dimension_symmetric_tolerance(") == 3
    assert build_source.count("set_dimension_bilateral_tolerance(") == 2
    assert '_blank_ref_geometry(adapter, "HeadTop", "PLANE")' in build_source
    assert '_blank_ref_geometry(adapter, pivot_axis, "AXIS")' in build_source


def test_cone_tip_pinch_sheet_defines_a_flat_end_without_duplicate_head_diameter() -> None:
    drawing = importlib.import_module("draw_cone_tip_pinch_screw")
    spec = importlib.import_module("cone_tip_pinch_screw_spec")
    assert drawing.END_KEEP == {}
    assert drawing.RECIPE.side_center == (0.190, 0.190)
    assert spec.DRAWING_DIMENSIONS == {}
    assert "FLAT-END PINCH SCREW; NO CONICAL POINT" in spec.DRAWING_NOTES
    assert "DISTAL START CHAMFER" in spec.DRAWING_NOTES
    assert "MIDPLANE OFFSET FROM HEAD OD AXIS 0.00 +/-0.05" in spec.DRAWING_NOTES
    assert "HEAD OD TOTAL RUNOUT 0.10 RELATIVE TO THREAD PITCH-DIAMETER AXIS" in (
        spec.DRAWING_NOTES
    )
    assert "BEARING FACE PERPENDICULAR 0.10 TO THREAD PITCH-DIAMETER AXIS" in (
        spec.DRAWING_NOTES
    )


@pytest.mark.parametrize("spec_name", ("hanger_screw_spec", "thumb_screw_spec"))
def test_long_reference_note_is_split_for_readable_rendering(spec_name: str) -> None:
    spec = importlib.import_module(spec_name)
    assert "THREAD GEOMETRY OMITTED IN VIEWS; SHANK OUTLINE REFERENCE ONLY." in (
        spec.DRAWING_NOTES
    )


def test_hanger_hex_head_is_controlled_to_thread_axis() -> None:
    spec = importlib.import_module("hanger_screw_spec")
    assert "HEX CENTER WITHIN DIA 0.10 OF THREAD PITCH-DIAMETER AXIS" in (
        spec.DRAWING_NOTES
    )
    assert "BEARING FACE PERPENDICULAR 0.10 TO THREAD PITCH-DIAMETER AXIS" in (
        spec.DRAWING_NOTES
    )


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
    head_name = "KNOB" if spec_name == "pen_set_screw_spec" else "HEAD"
    assert (
        f"{head_name} OD TOTAL RUNOUT 0.10 RELATIVE TO THREAD PITCH-DIAMETER AXIS"
        in spec.DRAWING_NOTES
    )
    assert "BEARING FACE PERPENDICULAR 0.10 TO THREAD PITCH-DIAMETER AXIS" in (
        spec.DRAWING_NOTES
    )
