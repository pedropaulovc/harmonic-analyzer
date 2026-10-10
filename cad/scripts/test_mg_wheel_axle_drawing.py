"""Offline contracts for the wheel-axle drawing and the wheel group it sizes."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import build_mg_wheel_axle as part
import draw_mg_wheel_axle as drawing
import mg_magnifying_wheel_geom
import mg_wheel_axle_spec as spec
import mg_wheel_bar_geom
import mg_wheel_group as group
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-wheel-axle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-wheel-axle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-wheel-axle_drawing.png")
    assert DRAWINGS_BY_NAME["mg_wheel_axle"].script == Path(drawing.__file__).resolve()


def test_spec_values_are_the_drill_rod_pin() -> None:
    assert spec.PIN_DIA == pytest.approx(4.7625)
    assert spec.PIN_DIA_TOL == 0.005
    assert spec.SHANK_LEN == 28.5
    assert spec.THREAD == "#4-40"
    assert spec.THREAD_MAJOR == pytest.approx(2.845, abs=1e-3)
    assert spec.THREAD_LEN == 7.2
    assert spec.THREAD_END == pytest.approx(35.7)
    assert spec.PIN_LEN == pytest.approx(36.5)
    assert spec.DOME_R == pytest.approx(1.665, abs=1e-3)
    # The back end is flush with the bar's back face; origin on its front face.
    assert spec.BACK_Y == -mg_wheel_bar_geom.BAR_DEPTH == -9.0
    assert (spec.STEP_Y, spec.THREAD_END_Y, spec.TIP_Y) == pytest.approx(
        (19.5, 26.7, 27.5)
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == marked
    assert marked == {"PinDia", "ShankLength", "ThreadEnd", "PinLength", "DomeR"}
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked
    assert drawing.DRAWING_PRECISION_BY_NAME == spec.DRAWING_PRECISION["PinProfile"]


def test_pin_is_one_front_plane_revolve() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("create_revolve(") == 1
    assert 'create_sketch("Front")' in source
    assert 'name_last_feature(adapter, "PinProfile")' in source
    assert 'name_last_feature(adapter, "Pin")' in source
    assert "create_extrusion(" not in source
    # Axis1 on local Y and the Front Plane carry the assembly mates.
    assert 'name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0' in source
    for name in ("PinDia", "ShankLength", "ThreadEnd", "PinLength", "DomeR"):
        assert re.search(rf'profile\.record\(\s*"{name}"', source), name
    v = (
        math.pi * (spec.PIN_DIA / 2.0) ** 2 * spec.SHANK_LEN
        + math.pi * (spec.THREAD_MAJOR / 2.0) ** 2 * spec.THREAD_LEN
        + math.pi * spec.DOME_H**2 * (3.0 * spec.DOME_R - spec.DOME_H) / 3.0
    )
    assert part.V_TOTAL == pytest.approx(v)


def test_tolerances_are_native_on_the_model() -> None:
    assert model_toleranced_dimensions(part) == {
        ("PinProfile", "PinDia"): "PIN_DIA_TOL",
        ("PinProfile", "ShankLength"): "*deviations(SHANK_LEN_BAND)",
        ("PinProfile", "ThreadEnd"): "*deviations(THREAD_END_BAND)",
    }
    assert set(spec.DRAWING_BANDS) == {
        ("PinProfile", "ShankLength"),
        ("PinProfile", "ThreadEnd"),
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source


def test_no_pmi_or_surface_finish() -> None:
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for token in (
            "author_part_pmi",
            "project_part_pmi",
            "add_surface_finish",
            "add_feature_control_frame(",
            "add_datum_feature(",
            "GEOMETRIC_CONTROLS",
            "PART_DATUMS",
        ):
            assert token not in source, (module.__name__, token)
    for name in ("GEOMETRIC_CONTROLS", "PART_DATUMS", "SURFACE_FINISHES"):
        assert not hasattr(spec, name)


def test_thread_callout_and_notes() -> None:
    assert spec.THREAD_CALLOUT == "#4-40 UNC"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_attached_note(") == 1
    assert "text=THREAD_CALLOUT" in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    notes = spec.DRAWING_NOTES
    assert 1 <= len(notes.splitlines()) <= 4
    assert "DEBURR" not in notes
    assert "X.XX" not in notes


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    assert drawing.VIEW_SCALE == (4, 1)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=VIEW_SCALE") == 2
    assert drawing.SIDE_VIEW_ANGLE == -math.pi / 2.0


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-wheel-axle")
    assert "drill rod" in str(config["material_specification"])
    assert "3/16" in str(config["material_specification"])
    assert config["finish"]
    assert config["process"]
    assert int(config["quantity"]) == 1


def test_wheel_group_stack_fits_the_pin() -> None:
    assert group.STEP_INSIDE_HUB > 0.0
    assert group.STEP_INSIDE_HUB == pytest.approx(0.587, abs=1e-3)
    assert group.LOCKNUT_THREAD_MARGIN >= 0.0
    assert group.LOCKNUT_THREAD_MARGIN == pytest.approx(0.0325, abs=1e-3)
    assert group.THREAD_PAST_LOCKNUT_MAX <= 1.35
    assert group.THREAD_PAST_LOCKNUT_MAX == pytest.approx(1.3437, abs=1e-3)
    assert group.SPOKE_MID_D == pytest.approx(8.0)
    assert group.WHEEL_MID_Z == -146.9


def test_pin_fits_are_press_in_the_bar_and_running_in_the_wheel() -> None:
    assert min(group.BAR_PRESS) > 0.0
    assert min(group.HUB_RUNNING) > 0.0
    assert mg_magnifying_wheel_geom.BORE_DIA > spec.PIN_DIA + spec.PIN_DIA_TOL
    assert mg_wheel_bar_geom.AXLE_BORE_DIA + mg_wheel_bar_geom.AXLE_BORE_BAND[0] < (
        spec.PIN_DIA - spec.PIN_DIA_TOL
    )


def test_pen_travel_literals_match_their_source_modules() -> None:
    import _config
    import build_pd_paper_drive_assembly as paper
    import build_pn_pen_assembly as pen

    assert group.MARKER_TIP_REST_Y == pen.MARKER_POS[1]
    assert group.PAPER_BOTTOM_Y == pytest.approx(
        paper.PLATE_Y0 + paper.PLATE_HEIGHT - paper.PAPER_HEIGHT - 3.0
    )
    assert group.PAPER_TOP_Y == pytest.approx(group.PAPER_BOTTOM_Y + paper.PAPER_HEIGHT)
    # The 3.0 is the sheet's top margin under the plate's top edge.
    paper_source = Path(paper.__file__).read_text(encoding="utf-8")
    assert re.search(r"paper_top_margin = \(?\s*3\.0\b", paper_source)
    assert "PLATE_Y0 + PLATE_HEIGHT - PAPER_HEIGHT - paper_top_margin" in paper_source
    half_trace = float(_config.machine("output", "pen_trace_half_mm"))
    assert half_trace == 15.0
    assert half_trace <= min(group.PEN_DOWN_MAX, group.PEN_UP_MAX)
