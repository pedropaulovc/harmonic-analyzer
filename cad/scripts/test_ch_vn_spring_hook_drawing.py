"""Offline manufacturing boundaries for the trimmed channel-spring anchor."""

import math
from types import SimpleNamespace

import pytest

import _config
import _stock_trim_drawing as trim_drawing
import draw_ch_vn_spring_hook as drawing
import ch_vn_spring_hook_spec as spec
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
    # so the thread starts there, engages the whole coefficient plate, and
    # the cut end hangs below its underside far enough to carry the jam nut.
    installed_end = mounts.CHANNEL_ANCHOR_XY[1] + spec.TRIM.shank_end_y_mm
    underside = mounts.PLATE_BOTTOM_Y
    assert underside == pytest.approx(mounts.PLATE_TOP_Y - lever.COEFFICIENT_T)
    assert spec.THREAD_ENGAGEMENT_MM == lever.COEFFICIENT_T
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
    assert band == pytest.approx(0.254)  # the printed .XX overall's ±.01
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
    # the round-up that puts the printed two-place inch overall on the model's
    # own number.
    assert worst - floor - spec.PAST_NUT_MARGIN_MM < 0.254
    overall_in = spec.FINISHED_OVERALL_MM / 25.4
    assert overall_in == pytest.approx(round(overall_in, 2))
    # Hand-checked: thread below the seated neck, less the thickest plate,
    # nut and deburr.
    short_part = spec.SHANK_LENGTH_MM - band - anchor.unthreaded_shank_length_mm
    assert worst == pytest.approx(
        short_part
        - spec.ADJUSTMENT_TRAVEL_MM
        - (lever.COEFFICIENT_T + spec.SEAT_BAND_MM)
        - jam_nut.THICKNESS_MAX
        - maximum_axial
    )
    # A nominal part, seated, keeps the band and the budget as extra thread.
    assert spec.full_threads_past_nut_mm(0.0, 0.0) == pytest.approx(
        worst + band + spec.ADJUSTMENT_TRAVEL_MM
    )


def test_the_anchor_is_sized_at_the_coefficient_plate_thickness_extremes():
    """The uniform 7.00 coefficient plate retains the lever's .XX band, so the
    jam nut seats anywhere from 6.49 to 7.51 below its fixed top. The trim is
    18.034 shank / 1.21 in overall, one .01 step over the worst-case 1.5875
    full-thread floor plus the round-up to the printed grid."""
    from sm_summing_lever_notes import LINEAR_BAND

    assert spec.SEAT_BAND_MM == LINEAR_BAND == pytest.approx(0.51)
    thin, thick = 6.49, 7.51
    assert (spec.SEAT_T_MIN_MM, spec.SEAT_T_MAX_MM) == pytest.approx((thin, thick))
    assert (spec.SHANK_LENGTH_MM, spec.FINISHED_OVERALL_MM) == pytest.approx(
        (18.034, 30.734)
    )
    band, budget = spec.LENGTH_BAND_WORST_MM, spec.ADJUSTMENT_TRAVEL_MM
    floor = spec.PAST_NUT_FLOOR_MM
    # Thickest plate, shortest part, backed out: the floor plus the margin.
    at_thick = spec.full_threads_past_nut_mm(budget, -band, thick)
    assert at_thick == pytest.approx(1.9652006006)
    assert at_thick >= floor + spec.PAST_NUT_MARGIN_MM
    assert spec.full_threads_past_nut_mm(budget, -band) == pytest.approx(at_thick)
    # The thinner plates only add thread.
    assert spec.full_threads_past_nut_mm(budget, -band, thin) == pytest.approx(
        at_thick + 2 * spec.SEAT_BAND_MM
    )
    # Deepest cut end: the longest part under the thinnest plate, still cut
    # from the 19.05 stock (1.016 comes off).
    assert spec.SHANK_LENGTH_MM + band < anchor.shank_length_mm
    assert anchor.shank_length_mm - spec.SHANK_LENGTH_MM == pytest.approx(1.016)
    assert spec.PROTRUSION_MAX_MM == pytest.approx(
        spec.SHANK_LENGTH_MM + band - anchor.unthreaded_shank_length_mm - thin
    )
    assert spec.PROTRUSION_MAX_MM == pytest.approx(8.623)
    # Modelled at nominal thickness, the cut end hangs 7.859 below the plate.
    assert spec.PROTRUSION_MM == pytest.approx(7.859)


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
    notes = _config.parts("ch-vn-spring-hook")["installation_notes"]
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
    annotations = []
    for name, (nominal, lower, upper) in drawing.EXPECTED_CONTROLS.items():
        tolerance = SimpleNamespace(
            Type=spec.DIMENSION_TOLERANCE_TYPES[name],
            GetMinValue=lambda lower=lower: lower,
            GetMaxValue=lambda upper=upper: upper,
        )
        dimension = SimpleNamespace(
            Name=name, DrivenState=2, SystemValue=nominal, Tolerance=tolerance
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
        drawing._verify_controls(annotations)
        return
    with pytest.raises(RuntimeError):
        drawing._verify_controls(annotations)


def test_nut_thread_interference_literal_matches_the_specs():
    assert CHANNEL_ANCHOR_NUT_THREAD == pytest.approx(
        (
            THREAD_MAJOR_MM[anchor.thread_size],
            TAP_DRILL_MM[anchor.thread_size],
            jam_nut.THICKNESS,
        )
    )
    assert jam_nut.THREAD == anchor.thread_size


@pytest.mark.parametrize(
    "fault", [None, "extra", "missing", "foreign", "banded", "configuration"]
)
def test_settled_sheet_keeps_only_the_thread_as_supplier_reference(monkeypatch, fault):
    """The #6-32 thread is the one replacement reference; eye and as-supplied
    sizes are not sourcing criteria, so any extra native dimension fails."""
    thread = f"SupplierThreadMajor@{spec.SUPPLIER_THREAD_FEATURE}@ch-vn-spring-hook.Part"
    names = [thread, *(f"{name}@Sketch@ch-vn-spring-hook.Part" for name in drawing.FRONT_KEEP)]
    if fault == "extra":
        names.append("EyeID@Drawing View1")
    elif fault == "missing":
        names.remove(thread)
    elif fault == "foreign":
        names[0] = thread = "SupplierThreadMajor@SupplierStockAxis@ch-vn-spring-hook.Part"
    displays = []
    for name in names:
        native = SimpleNamespace(
            FullName=name,
            Tolerance=SimpleNamespace(Type=1 if fault == "banded" else 0),
        )
        displays.append(SimpleNamespace(GetDimension2=lambda _index, native=native: native))
    for display, following in zip(displays, [*displays[1:], None]):
        display.GetNext5 = lambda following=following: following
    configuration = "Default"
    front = SimpleNamespace(
        name="Drawing View1",
        ReferencedConfiguration="AsSuppliedStock" if fault == "configuration" else configuration,
        UpdateViewDisplayGeometry=lambda: None,
        GetFirstDisplayDimension6=lambda: displays[0],
    )
    iso = SimpleNamespace(name="Drawing View2", ReferencedConfiguration=configuration)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "iter_views", lambda _adapter: (front, iso))
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(drawing, "assert_supplier_reference_dimension", lambda *_a, **_k: None)
    refs = [(thread, {"label": "SupplierThreadMajor"})]

    def check():
        drawing._verify_supplier_references(
            None, refs, ("Drawing View1", "Drawing View2"), configuration
        )

    if fault is None:
        check()
        return
    with pytest.raises(RuntimeError):
        check()


def test_angle_text_sits_inside_the_deburr_wedge_on_its_bisector():
    """An angle's text outside its 0..45 deg wedge measures another angle; on
    the bisector at radius 26 it stands off both rays by more than its box."""
    vertex = (0.1065, 0.1032)
    x, y = drawing.FRONT_KEEP["ChamferAngle"]
    bearing = math.degrees(math.atan2(y - vertex[1], x - vertex[0]))
    assert bearing == pytest.approx(spec.CHAMFER_ANGLE_DEG / 2, abs=0.5)
    assert math.hypot(x - vertex[0], y - vertex[1]) == pytest.approx(0.026, abs=2e-4)
    assert drawing.FRONT_KEEP["ChamferWidth"][1] < 0.100


def test_fixed_deburr_angle_text_clears_its_own_ink_by_two_millimetres():
    """Arithmetic on the settled native 45 deg (layout audits of runs fa43a1a5
    and ae121732, FRONT_KEEP's bisector placement), sheet metres: its run box
    at SolidWorks' 9.625 width, both arrowheads (GetArrowHeadAtIndex2 rows)
    and both extension lines stand at least the fleet's 2 mm arrow-to-text
    clearance off its text, and its lower arrowhead off the width block's MIN
    row (machinist b344192: the text sat on its own ray and arrowhead)."""
    from _layout_audit import arrowhead_segments
    from _layout_geometry import (
        ARROW_TEXT_CLEARANCE_M,
        Box,
        Segment,
        segment_box_distance,
    )

    assert drawing.FRONT_KEEP["ChamferAngle"] == pytest.approx((0.1305, 0.1132))
    text = Box(0.1256875, 0.1104219, 0.1256875 + 0.009625, 0.1104219 + 0.0035)
    min_row = Box(0.1232316, 0.0952219, 0.1232316 + 0.0895368, 0.0952219 + 0.0035)
    arrowheads = [
        arrowhead_segments(row)
        for row in (
            (
                0.1324869,
                0.1032311,
                0.0005,
                -0.0679048,
                0.9976918,
                0.0,
                0.003556,
                0.000762,
            ),
            (
                0.124871,
                0.1216174,
                0.0005,
                0.6574587,
                -0.7534906,
                0.0,
                0.003556,
                0.000762,
            ),
        )
    ]
    rays = (
        Segment(0.1120414, 0.1032311, 0.1334869, 0.1032311, "ext-line"),
        Segment(0.1094701, 0.1062166, 0.1255781, 0.1223246, "ext-line"),
    )

    def gap(segments, box):
        return min(segment_box_distance(segment, box) for segment in segments)

    clearances = [gap(head, text) for head in arrowheads] + [
        gap([ray], text) for ray in rays
    ]
    assert clearances == pytest.approx([0.00362, 0.00477, 0.00719, 0.00602], abs=5e-5)
    assert min(clearances) >= ARROW_TEXT_CLEARANCE_M
    assert gap(arrowheads[0], min_row) == pytest.approx(0.00451, abs=5e-5)
    assert gap(arrowheads[0], min_row) >= ARROW_TEXT_CLEARANCE_M
