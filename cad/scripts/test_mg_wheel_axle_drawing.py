"""Offline contracts for the wheel-axle drawing and the wheel group it sizes."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from _column_clamp_interface import BAR_DEPTH
import build_mg_wheel_axle as part
import draw_mg_wheel_axle as drawing
import mg_wheel_axle_callouts as callouts
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
    # Full thread only: the die's lead runs out in the step's relief (wider
    # than its 1.5 pitches), and the dome cuts one pitch short.
    assert spec.THREAD_PITCH == pytest.approx(0.635)
    assert spec.DIE_RUNOUT == pytest.approx(1.5 * 0.635)
    assert spec.RELIEF_WIDTH >= spec.DIE_RUNOUT >= spec.THREAD_PITCH
    assert spec.FULL_THREAD_START_Y == pytest.approx(
        spec.PRESS_GAUGE + spec.RELIEF_WIDTH
    )
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


def test_thread_relief_is_cut_under_the_die_root() -> None:
    """Rule 16 (2026-10-24 ENFORCE blocker): the thread running to the shank
    step gets a relief of at least one pitch, the vertical rod's form."""
    assert (spec.RELIEF_DIA, spec.RELIEF_WIDTH, spec.RELIEF_ROOT_R) == (1.85, 1.10, 0.2)
    assert spec.RELIEF_DIA <= spec.THREAD_ROOT_2A_MIN < spec.THREAD_BASIC_MINOR
    assert spec.RELIEF_WIDTH >= spec.THREAD_PITCH
    assert 2.0 * spec.RELIEF_ROOT_R < spec.RELIEF_WIDTH_MIN
    assert spec.FULL_THREAD_FROM_STEP_MAX == spec.RELIEF_WIDTH
    # The Ø and root radius print as single MAX limits at their model values;
    # the width as a LIMIT pair whose MIN holds rule 16's one pitch.
    assert spec.SINGLE_LIMITS == {
        ("PinProfile", "ReliefDia"): (1.85, spec.TOL_TYPE_MAX),
        ("ReliefRoots", "ReliefRootR"): (0.2, spec.TOL_TYPE_MAX),
    }
    assert spec.LIMIT_PAIRS == {("PinProfile", "ReliefWidth"): (0.70, 1.10)}
    assert spec.THREAD_PITCH <= spec.RELIEF_WIDTH_MIN
    assert spec.TOL_TYPE_MAX == 6  # swTolType_e.swTolMAX
    assert spec.TOL_TYPE_LIMIT == 3  # swTolType_e.swTolLIMIT
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "ReliefRoots")' in source
    assert "_single_limits(adapter)" in source
    assert "_limit_pairs(adapter)" in source


def test_volume_gates_see_the_relief() -> None:
    # codjiflo #1996: a whole-part 0.5% gate passed an unrelieved solid.
    assert part.PIN_VOLUME_TOL < part.V_RELIEF_GROOVE
    # One root missing is half the roots' volume: the gate must reject it.
    assert part.ROOTS_VOLUME_TOL < 0.5 * part.V_RELIEF_ROOTS


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) | set(drawing.DETAIL_KEEP) == marked
    assert not set(drawing.SIDE_KEEP) & set(drawing.DETAIL_KEEP)
    assert set(drawing.DETAIL_KEEP) == {"ReliefWidth", "ReliefDia", "ReliefRootR"}
    assert set(drawing.SIDE_KEEP) == {
        "PinDia",
        "ShankLength",
        "ThreadLength",
        "PinLength",
        "DomeR",
    }
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked


def test_detail_fence_holds_every_relief_reference() -> None:
    focus = drawing.DETAIL_FOCUS_MM
    radius = drawing.DETAIL_RADIUS_MM
    floor = spec.RELIEF_DIA / 2.0
    for x, y in (
        (-floor, spec.STEP_Y),
        (-floor, spec.STEP_Y + spec.RELIEF_WIDTH),
        (floor, spec.STEP_Y),
        (floor, spec.STEP_Y + spec.RELIEF_WIDTH),
        *drawing.RELIEF_ROOT_CENTRES_MM,
    ):
        assert math.dist(focus, (x, y)) < radius, (x, y)
    # The crop sits inside the border, left of the title block and under the
    # side view's overall row.
    cx, cy = drawing.DETAIL_CENTER
    crop = drawing.DETAIL_CROP_RADIUS
    assert cx - crop > 0.013 and cx + crop < 0.216
    assert cy - crop > 0.013 and cy + crop < drawing._ROW_Y[2] - 0.010


def test_pin_is_one_front_plane_revolve() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("create_revolve(") == 1
    assert 'create_sketch("Front")' in source
    assert 'name_last_feature(adapter, "PinProfile")' in source
    assert 'name_last_feature(adapter, "Pin")' in source
    assert "create_extrusion(" not in source
    # Axis1 on local Y and the Front Plane carry the assembly mates.
    assert 'name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0' in source
    for name in spec.DRAWING_DIMENSIONS["PinProfile"]:
        assert re.search(rf'profile\.record\(\s*"{name}"', source), name
    floor_r = spec.RELIEF_DIA / 2.0
    v = (
        math.pi * (spec.PIN_DIA / 2.0) ** 2 * spec.SHANK_LEN
        + math.pi * floor_r**2 * spec.RELIEF_WIDTH
        + math.pi
        * (spec.THREAD_MAJOR / 2.0) ** 2
        * (spec.THREAD_LEN - spec.RELIEF_WIDTH)
        + math.pi * spec.DOME_H**2 * (3.0 * spec.DOME_R - spec.DOME_H) / 3.0
    )
    assert part.V_PROFILE == pytest.approx(v)
    assert 0.0 < part.V_RELIEF_ROOTS < 0.2
    assert part.V_TOTAL == pytest.approx(v + part.V_RELIEF_ROOTS)


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
    assert "SHANK STEP" in callouts.SHANK_LENGTH_CALLOUT
    # Rule 4: the band names the stack it sets, its locknut and the feature
    # it ends on; the assembled 2.9 MAX past the locknut is MHA-MG-00's
    # check, not this part's.
    words = " ".join(callouts.THREAD_LENGTH_CALLOUT.split())
    for required in ("SHANK STEP", "THREAD END", "MHA-MG-00", "MHA-MG-VN-52"):
        assert required in words, required
    assert "2.9" not in words
    assert drawing.ORIGIN_DIMENSIONS == ("ShankLength", "ThreadLength")
    assert drawing.BROKEN_LINE_DIMENSIONS == ("PinLength",)
    assert group.THREAD_PAST_LOCKNUT_MAX <= spec.THREAD_PAST_LOCKNUT_LIMIT == 2.9
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
    # The wheel runs on the shank: a journal, machined grade (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)), and
    # the Ø callout says so beside the press fit.
    assert [(c.key, c.roughness_um) for c in spec.SURFACE_FINISHES] == [
        ("mg_axle_journal", MACHINED_UM)
    ]
    pin_words = callouts.PIN_DIA_CALLOUT.split()
    assert "MG-MAGNIFYING-WHEEL" in pin_words and "RUNS" in pin_words


def test_thread_callout_and_no_general_notes() -> None:
    assert spec.THREAD_CALLOUT == "#4-40 UNC"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_attached_note(") == 1
    assert "text=THREAD_CALLOUT" in source
    # Rule 7: the press-to-gauge step is MHA-MG-00's, and the optional
    # thread locker is gone; no general note remains.
    assert "Manufacturing Notes" not in source
    assert not hasattr(spec, "DRAWING_NOTES")
    assert "Manufacturing Notes" not in Path(part.__file__).read_text(encoding="utf-8")
    # The Ø callout names both fits: the press into the bar's reamed bore,
    # at that bore's limits, and the wheel running on the shank.
    words = " ".join(callouts.PIN_DIA_CALLOUT.split())
    low, high = sorted(spec.BAR_BORE_LIMITS)
    for required in ("PRESS FIT", "MG-WHEEL-BAR", f"{low:.3f}-{high:.3f}"):
        assert required in words, required
    assert "MG-MAGNIFYING-WHEEL" in words


def test_callouts_are_part_authored_and_only_read_by_the_sheet() -> None:
    """#1942: dimension text set from the sheet writes through to the part."""
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "SetText" not in drawing_source
    assert "set_dimension_callouts" not in drawing_source
    assert "set_reference_dimension" not in drawing_source
    assert "_assert_part_authored_text(named)" in drawing_source
    assert "settled_checks=" in drawing_source
    assert "author_dimension_callouts(adapter)" in Path(part.__file__).read_text(
        encoding="utf-8"
    )
    authored = callouts.authored_by_name()
    assert set(authored) == {
        "PinDia",
        "ShankLength",
        "ThreadLength",
        "ReliefWidth",
        "ReliefRootR",
        "PinLength",
    }
    assert authored["PinLength"] == {
        callouts.TEXT_PREFIX: "(",
        callouts.TEXT_SUFFIX: ")",
    }
    assert authored["ReliefRootR"] == {callouts.CALLOUT_ABOVE: "2X"}


def test_detail_circles_are_authored_without_inference() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "manager.AddToDB = True" in source
    assert "manager.AddToDB = previous_add_to_db" in source
    assert "native_circle_geometry(circle" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    assert drawing.VIEW_SCALE == (3, 1)
    assert drawing.DETAIL_SCALE == (10, 1)
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
    # first nut stays clear of the step's relief.
    assert group.LOCKNUT_THREAD_MARGIN >= 0.0
    assert group.LOCKNUT_THREAD_MARGIN == pytest.approx(0.0016, abs=1e-3)
    assert group.NUT_RUNOUT_MARGIN == pytest.approx(0.0638, abs=1e-3)
    assert group.THREAD_PAST_LOCKNUT_MAX <= spec.THREAD_PAST_LOCKNUT_LIMIT == 2.9
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
