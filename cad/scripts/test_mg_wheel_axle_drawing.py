"""Offline contracts for the wheel-axle drawing and the wheel group it sizes."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from _column_clamp_interface import BAR_DEPTH
import build_mg_wheel_axle as part
import draw_mg_wheel_axle as drawing
import mg_magnifying_wheel_geom
import mg_wheel_axle_spacer_spec
import mg_wheel_axle_spec as spec
import mg_wheel_bar_geom
import mg_wheel_group as group
import _recording_geometry as recording_geometry
import mg_vn_wheel_axle_back_washer_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import MACHINED_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-wheel-axle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-wheel-axle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-wheel-axle_drawing.png")
    assert DRAWINGS_BY_NAME["mg_wheel_axle"].script == Path(drawing.__file__).resolve()


def test_spec_values_are_the_drill_rod_pin() -> None:
    spacer = mg_wheel_axle_spacer_spec.LENGTH
    assert spec.PIN_DIA == pytest.approx(4.7625)
    assert spec.PIN_DIA_TOL == 0.005
    # The rev-10 pin grows by the spacer's length, shank and gauge alike.
    assert spec.SHANK_LEN == pytest.approx(28.4 + spacer)
    assert spec.THREAD == "#4-40"
    assert spec.THREAD_MAJOR == pytest.approx(2.845, abs=1e-3)
    assert spec.THREAD_LEN == 8.20
    assert spec.PIN_LEN == pytest.approx(37.40 + spacer)
    # Full thread only: 1.5 pitches of die run-out at the step, one pitch
    # cut short by the dome.
    assert spec.THREAD_PITCH == pytest.approx(0.635)
    assert spec.FULL_THREAD_START_Y == pytest.approx(spec.PRESS_GAUGE + 1.5 * 0.635)
    assert spec.FULL_THREAD_END_Y == pytest.approx(spec.THREAD_END_Y - 0.635)
    assert spec.DOME_R == pytest.approx(1.665, abs=1e-3)
    # Pressed to the gauge from the bar's front face (the origin); the back
    # end then sits 0.60 inside the 9.5 bar's back face (ruling B grew the
    # bar 0.5 rearward; the pin keeps its 8.9 in the bore).
    assert spec.PRESS_GAUGE == spec.STEP_Y == pytest.approx(19.5 + spacer)
    assert spec.BACK_Y == pytest.approx(-BAR_DEPTH + 0.60)
    assert (spec.THREAD_END_Y, spec.TIP_Y) == pytest.approx(
        (spec.STEP_Y + 8.20, spec.STEP_Y + 9.00)
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == marked
    assert marked == {"PinDia", "ShankLength", "ThreadLength", "PinLength", "DomeR"}
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
    for name in ("PinDia", "ShankLength", "ThreadLength", "PinLength", "DomeR"):
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
        ("PinProfile", "ThreadLength"): "*deviations(THREAD_LEN_BAND)",
    }
    assert set(spec.DRAWING_BANDS) == {("PinProfile", "ThreadLength")}
    # Both lengths read from the gauged step: the shank only places the back
    # end (.X), the thread holds the locknut (the user's option (c),
    # 2026-10-12); the overall is reference.
    assert spec.DRAWING_PRECISION["PinProfile"]["ShankLength"] == 1
    assert spec.THREAD_LEN_BAND == (0.25, -0.25)
    assert spec.REFERENCE_DIMENSIONS == {"PinLength"}
    assert spec.DRAWING_PRECISION["PinProfile"]["PinLength"] == 1
    assert drawing.DIMENSION_CALLOUTS["ShankLength"] == "FROM SHANK STEP"
    assert drawing.DIMENSION_CALLOUTS["ThreadLength"] == (
        "FROM SHANK STEP;\nLOCKNUT ON FULL THREAD,\nEND 2.9 MAX PAST LOCKNUT"
    )
    assert drawing.ORIGIN_DIMENSIONS == ("ShankLength", "ThreadLength")
    assert group.THREAD_PAST_LOCKNUT_MAX <= group.THREAD_PAST_LOCKNUT_LIMIT == 2.9
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source


def test_journal_finish_and_no_gdt() -> None:
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for token in (
            "project_part_pmi",
            "add_feature_control_frame(",
            "add_datum_feature(",
            "GEOMETRIC_CONTROLS",
            "PART_DATUMS",
        ):
            assert token not in source, (module.__name__, token)
    for name in ("GEOMETRIC_CONTROLS", "PART_DATUMS"):
        assert not hasattr(spec, name)
    # The wheel runs on the shank: a journal, machined grade (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)).
    assert [(c.key, c.roughness_um) for c in spec.SURFACE_FINISHES] == [
        ("mg_axle_journal", MACHINED_UM)
    ]


def test_thread_callout_and_notes() -> None:
    assert spec.THREAD_CALLOUT == "#4-40 UNC"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_attached_note(") == 1
    assert "text=THREAD_CALLOUT" in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    notes = spec.DRAWING_NOTES
    assert 1 <= len(notes.splitlines()) <= 4
    flat = " ".join(notes.splitlines())
    assert "TO THE GAUGE ON MHA-MG-00 (AXLE AS PRESSED)" in flat
    assert not re.search(r"\d+\.\d|\+/-|±|Ø|MAX|MIN", notes)
    assert all(len(line) <= 80 for line in notes.splitlines())
    assert "REAMED BORE" not in notes
    assert drawing.DIMENSION_CALLOUTS["PinDia"] == (
        "PRESS FIT IN MG-WHEEL-BAR\n<MOD-DIAM>4.737-4.747 REAMED BORE"
    )
    assert "DEBURR" not in notes
    assert "X.XX" not in notes


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    assert drawing.VIEW_SCALE == (3, 1)
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
    assert group.STEP_INSIDE_HUB == pytest.approx(0.6566, abs=1e-3)
    # (b) on FULL thread: the dome's incomplete pitch is not counted, and the
    # first nut stays clear of the die run-out at the step.
    assert group.LOCKNUT_THREAD_MARGIN >= 0.0
    assert group.LOCKNUT_THREAD_MARGIN == pytest.approx(0.0016, abs=1e-3)
    assert group.NUT_RUNOUT_MARGIN == pytest.approx(0.2113, abs=1e-3)
    assert group.THREAD_PAST_LOCKNUT_MAX <= group.THREAD_PAST_LOCKNUT_LIMIT == 2.9
    assert group.THREAD_PAST_LOCKNUT_MAX == pytest.approx(2.8666, abs=1e-3)
    assert group.THREAD_PAST_LOCKNUT_NOMINAL == pytest.approx(1.6875, abs=1e-3)
    # Pressed to the gauge, the .X shank lands the back end near the back
    # face; nothing stands behind it there.
    assert spec.BACK_END_PROUD_MAX == pytest.approx(0.35)
    assert spec.BACK_END_SUNK_MAX == pytest.approx(1.55)
    # The spacer lands the spokes' mid-plane on the pen-rod line.
    assert group.SPOKE_MID_D == pytest.approx(
        mg_wheel_axle_spacer_spec.LENGTH
        + mg_vn_wheel_axle_back_washer_spec.MODEL_THICKNESS
        + mg_magnifying_wheel_geom.HUB_BACK_Z
    )
    assert group.WHEEL_MID_Z == recording_geometry.PEN_Z_MID
    assert mg_wheel_bar_geom.BAR_FRONT_Z - group.SPOKE_MID_D == pytest.approx(
        recording_geometry.PEN_Z_MID
    )


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
    import pn_pen_carriage_geom as carriage

    assert group.MARKER_TIP_REST_Y == pytest.approx(carriage.MARKER_POS[1], abs=5e-4)
    # The 3.0 is the sheet's top margin under the plate's top edge.
    paper_height = recording_geometry.RECORDING_PAPER_HEIGHT_MM
    assert group.PAPER_BOTTOM_Y == pytest.approx(
        paper.PLATE_Y0 + paper.PLATE_HEIGHT - paper_height - 3.0
    )
    assert group.PAPER_TOP_Y == pytest.approx(group.PAPER_BOTTOM_Y + paper_height)
    half_trace = float(_config.machine("output", "pen_trace_half_mm"))
    assert half_trace == 15.0
    assert half_trace <= min(group.PEN_DOWN_MAX, group.PEN_UP_MAX)
