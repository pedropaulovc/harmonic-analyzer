"""Offline manufacturing boundaries for the trimmed channel-spring anchor."""

import math
from types import SimpleNamespace

import pytest

import _config
import _stock_trim_drawing as trim_drawing
import draw_vn_spring_hook as drawing
import vn_spring_hook_spec as spec
import spring_mount_geom as mounts
import sm_summing_lever_spec as lever
from _hole_spec import TAP_DRILL_MM
from stock_anchor_geom import ANCHOR_9489T111 as anchor
import ch_anchor_jam_nut_spec as jam_nut
from _interference_contracts import CHANNEL_ANCHOR_NUT_THREAD
from _hole_spec import THREAD_MAJOR_MM


def test_cut_end_crosses_the_plate_and_carries_the_jam_nut():
    cut_end = anchor.eye_od_mm / 2 - spec.FINISHED_OVERALL_MM
    assert cut_end == pytest.approx(spec.TRIM.shank_end_y_mm)
    # Installed and seated, the Ø3.175 neck shoulders on the plate's top face,
    # so the thread starts there, engages the whole padded tap, and the cut
    # end hangs below the pad underside far enough to carry the jam nut.
    installed_end = mounts.CHANNEL_ANCHOR_XY[1] + spec.TRIM.shank_end_y_mm
    underside = mounts.PLATE_TOP_Y - lever.SPRING_SEAT_T
    assert spec.THREAD_ENGAGEMENT_MM == lever.SPRING_SEAT_T
    thread_start = (
        mounts.CHANNEL_ANCHOR_XY[1]
        + spec.TRIM.shank_end_y_mm
        + (spec.SHANK_LENGTH_MM - anchor.unthreaded_shank_length_mm)
    )
    assert thread_start == pytest.approx(mounts.PLATE_TOP_Y)
    protrusion = underside - installed_end
    assert protrusion == pytest.approx(spec.PROTRUSION_MM)
    assert protrusion > jam_nut.THICKNESS_MAX + spec.ADJUSTMENT_TRAVEL_MM


def test_shortest_part_backed_out_keeps_two_full_threads_past_the_nut():
    # Calibration unscrews the anchor, lifting the cut end; the short-limit
    # part, its deburr at the adverse corner of its band, sets the floor.
    band = spec.LENGTH_BAND_WORST_MM
    assert band >= spec.FINISHED_OVERALL_TOLERANCE_MM
    assert band == pytest.approx(0.8)
    maximum_axial = (
        spec.CHAMFER_WIDTH_MM + spec.CHAMFER_WIDTH_TOLERANCE_MM
    ) / math.tan(
        math.radians(spec.CHAMFER_ANGLE_DEG - spec.CHAMFER_ANGLE_TOLERANCE_DEG)
    )
    assert spec.CHAMFER_AXIAL_MAX_MM == pytest.approx(maximum_axial)
    floor = spec.FULL_THREADS_PAST_NUT * anchor.thread_pitch_mm
    assert spec.FULL_THREADS_PAST_NUT == 2
    assert spec.PAST_NUT_FLOOR_MM == pytest.approx(floor)
    assert floor == pytest.approx(1.5875)
    worst = spec.full_threads_past_nut_mm(spec.ADJUSTMENT_TRAVEL_MM, -band)
    assert worst >= floor + spec.PAST_NUT_MARGIN_MM
    # The trim is sized to that floor and the ruled margin, not past it: only
    # the round-up that puts the printed one-place overall on the model's
    # own number.
    assert worst - floor - spec.PAST_NUT_MARGIN_MM < 0.1
    assert spec.FINISHED_OVERALL_MM == pytest.approx(round(spec.FINISHED_OVERALL_MM, 1))
    # Hand-checked: thread below the seated neck, less the thickest padded
    # tap, nut, deburr.
    short_part = spec.SHANK_LENGTH_MM - band - anchor.unthreaded_shank_length_mm
    assert worst == pytest.approx(
        short_part
        - spec.ADJUSTMENT_TRAVEL_MM
        - (lever.SPRING_SEAT_T + spec.SEAT_BAND_MM)
        - jam_nut.THICKNESS_MAX
        - maximum_axial
    )
    # A nominal part, seated, keeps the band and the budget as extra thread.
    assert spec.full_threads_past_nut_mm(0.0, 0.0) == pytest.approx(
        worst + band + spec.ADJUSTMENT_TRAVEL_MM
    )


def test_the_anchor_is_sized_at_the_pad_thickness_extremes():
    """Code review C10: the lever's 7.00 plate-and-pad prints at the title
    block's .XX band, so the jam nut seats anywhere from 6.49 to 7.51 under
    the plate top.  Sized at the nominal 7.00, the thickest pad left the
    shortest part, backed out, 1.09 of thread past the nut; owner ruling:
    cut shank 18.6, overall 31.3, one 0.1 step over the 1.5875 floor."""
    from sm_summing_lever_notes import LINEAR_BAND

    assert spec.SEAT_BAND_MM == LINEAR_BAND == pytest.approx(0.51)
    thin, thick = 6.49, 7.51
    assert (spec.SEAT_T_MIN_MM, spec.SEAT_T_MAX_MM) == pytest.approx((thin, thick))
    assert (spec.SHANK_LENGTH_MM, spec.FINISHED_OVERALL_MM) == pytest.approx(
        (18.6, 31.3)
    )
    band, budget = spec.LENGTH_BAND_WORST_MM, spec.ADJUSTMENT_TRAVEL_MM
    floor = spec.PAST_NUT_FLOOR_MM
    # Thickest pad, shortest part, backed out: the floor plus the margin.
    at_thick = spec.full_threads_past_nut_mm(budget, -band, thick)
    assert at_thick == pytest.approx(1.6876071730)
    assert at_thick >= floor + spec.PAST_NUT_MARGIN_MM
    assert spec.full_threads_past_nut_mm(budget, -band) == pytest.approx(at_thick)
    # The thinner pads only add thread.
    assert spec.full_threads_past_nut_mm(budget, -band, thin) == pytest.approx(
        at_thick + 2 * spec.SEAT_BAND_MM
    )
    # The old nominal-pad trim (18.0) fails at the thick pad by 0.50.
    old = spec.full_threads_past_nut_mm(budget, -band, thick) - (
        spec.SHANK_LENGTH_MM - 18.0
    )
    assert old == pytest.approx(1.0876071730)
    assert old < floor
    # Deepest cut end: the longest part under the thinnest pad.  The band's
    # upper half stops at the uncut 19.05 stock (only 0.45 is cut off).
    assert spec.SHANK_LENGTH_MM + band > anchor.shank_length_mm
    assert anchor.shank_length_mm - spec.SHANK_LENGTH_MM == pytest.approx(0.45)
    assert spec.PROTRUSION_MAX_MM == pytest.approx(
        anchor.shank_length_mm - anchor.unthreaded_shank_length_mm - thin
    )
    assert spec.PROTRUSION_MAX_MM == pytest.approx(9.385)
    # Modelled at the nominal pad, the cut end hangs 8.425 below it.
    assert spec.PROTRUSION_MM == pytest.approx(8.425)


def test_install_step_locks_the_anchor_with_its_jam_nut():
    nut = _config.parts("ch-anchor-jam-nut")["number"]
    step = " ".join(spec.ANCHOR_INSTALL_STEP.split())
    assert f"RUN ONE {nut} UP" in step
    assert "FORKED DRIVER" in step
    assert "JAM IT AGAINST THE PLATE UNDERSIDE" in step
    assert f"NO MORE THAN {spec.ADJUSTMENT_TURNS} TURN" in step
    assert nut in spec.ANCHOR_INSTALL_CHECK
    assert f"{nut} LOCKS THIS ANCHOR" in spec.DRAWING_NOTES
    assert "NO NUT IS INSTALLED" not in spec.DRAWING_NOTES
    for text in (
        spec.ANCHOR_INSTALL_STEP,
        spec.ANCHOR_INSTALL_CHECK,
        spec.DRAWING_NOTES,
    ):
        for banned in ("THREADLOCK", "LOCTITE", "NYLON", "NYLOC", "PATCH"):
            assert banned not in text.upper()


def test_printed_back_out_limit_matches_the_computed_budget():
    # The registry note is what the fitter reads; a band or plate change that
    # moved the budget must not leave it printing a stale turn count.
    assert spec.ADJUSTMENT_TURNS >= 1
    assert spec.ADJUSTMENT_TURNS * anchor.thread_pitch_mm <= spec.ADJUSTMENT_TRAVEL_MM
    assert (spec.ADJUSTMENT_TURNS + 1) * anchor.thread_pitch_mm > (
        spec.ADJUSTMENT_TRAVEL_MM
    )
    notes = _config.parts("vn-spring-hook")["installation_notes"]
    assert f"BACK OUT {spec.ADJUSTMENT_TURNS} TURN MAX" in " ".join(notes.split())


def test_cut_stays_in_threaded_metal_clear_of_the_neck():
    # A shorter cut would land in the unthreaded neck (or the bend), where the
    # deburr and the remaining thread cannot both exist.
    assert spec.SHANK_LENGTH_MM >= anchor.min_shank_length_mm
    assert spec.SHANK_LENGTH_MM < anchor.shank_length_mm


def test_deburr_band_clears_the_receiving_tap_drill():
    minimum = spec.CHAMFER_WIDTH_MM - spec.CHAMFER_WIDTH_TOLERANCE_MM
    assert 2 * spec.MIN_CHAMFER_WIDTH_MM == pytest.approx(
        anchor.thread_major_dia_mm - TAP_DRILL_MM[anchor.thread_size]
    )
    assert minimum >= spec.MIN_CHAMFER_WIDTH_MM
    # The cut end's flat must enter the tapped plate, not land on its drill.
    assert anchor.thread_major_dia_mm - 2 * minimum < TAP_DRILL_MM[anchor.thread_size]


@pytest.mark.parametrize(
    "fault",
    [None, "reference", "nominal", "tolerance_type", "widened", "precision", "missing"],
)
def test_drawing_requires_every_cutting_control(monkeypatch, fault):
    """A lost band, a widened band or a reference-only size is a regression."""
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        trim_drawing, "dimension_name", lambda _adapter, annotation: annotation.name
    )
    annotations = []
    for name, (nominal, lower, upper) in drawing.EXPECTED_CONTROLS.items():
        tolerance = SimpleNamespace(
            Type=spec.DIMENSION_TOLERANCE_TYPES[name],
            GetMinValue=lambda lower=lower: lower,
            GetMaxValue=lambda upper=upper: upper,
        )
        dimension = SimpleNamespace(
            DrivenState=2, SystemValue=nominal, Tolerance=tolerance
        )
        display = SimpleNamespace(
            GetDimension2=lambda _configuration, dimension=dimension: dimension,
            GetText=lambda _index: "",
            GetPrimaryPrecision2=lambda name=name: spec.DIMENSION_PRECISION[name],
        )
        annotations.append(
            SimpleNamespace(
                name=name,
                dimension=dimension,
                display=display,
                GetSpecificAnnotation=lambda display=display: display,
            )
        )
    if fault == "reference":
        annotations[0].dimension.DrivenState = 1
    elif fault == "nominal":
        annotations[0].dimension.SystemValue += 0.001
    elif fault == "tolerance_type":
        # swTolSYMMETRIC prints a band the title block already carries.
        annotations[0].dimension.Tolerance.Type = 4
    elif fault == "widened":
        annotations[0].dimension.Tolerance.GetMaxValue = lambda: (
            2 * spec.FINISHED_OVERALL_TOLERANCE_MM / 1000
        )
    elif fault == "precision":
        annotations[0].display.GetPrimaryPrecision2 = lambda: (
            spec.DIMENSION_PRECISION["FinishedOverall"] + 1
        )
    elif fault == "missing":
        annotations.pop()
    if fault is None:
        drawing._verify_controls(None, annotations)
        return
    with pytest.raises(RuntimeError):
        drawing._verify_controls(None, annotations)


def test_nut_thread_interference_literal_matches_the_specs():
    assert CHANNEL_ANCHOR_NUT_THREAD == pytest.approx(
        (
            THREAD_MAJOR_MM[anchor.thread_size],
            TAP_DRILL_MM[anchor.thread_size],
            jam_nut.THICKNESS,
        )
    )
    assert jam_nut.THREAD == anchor.thread_size


def test_chamfer_band_is_owner_accepted_with_both_functional_limits():
    """Machinist gate 2026-10-17 read the 0.46 ±0.05 deburr as over-spec."""
    from machinist_exceptions import load_exceptions

    (entry,) = load_exceptions(_config.CONFIG_DIR, "vn_spring_hook", "part")
    assert entry.kind == "accept"
    band = f"{spec.CHAMFER_WIDTH_MM:.2f} ±{spec.CHAMFER_WIDTH_TOLERANCE_MM:.2f}"
    assert band in entry.where
    assert entry.reason.startswith("owner ruling 2026-10-17")
    # The reason's numbers are the spec's: the tap-drill minimum and the
    # two-pitch past-nut floor.
    assert f"MIN_CHAMFER_WIDTH_MM {spec.MIN_CHAMFER_WIDTH_MM:.4f}" in entry.reason
    low = spec.CHAMFER_WIDTH_MM - spec.CHAMFER_WIDTH_TOLERANCE_MM
    assert f"the {low:.2f} low limit" in entry.reason
    assert f"{spec.FULL_THREADS_PAST_NUT * anchor.thread_pitch_mm:.4f}" in entry.reason
