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
    """The uniform 7.00 coefficient plate retains the title block's .XX
    band, so the jam nut seats anywhere from 6.49 to 7.51 below its fixed
    top. The C10 trim remains 18.6 shank / 31.3 overall, one 0.1 step over
    the worst-case 1.5875 full-thread floor."""
    from sm_summing_lever_notes import LINEAR_BAND

    assert spec.SEAT_BAND_MM == LINEAR_BAND == pytest.approx(0.51)
    thin, thick = 6.49, 7.51
    assert (spec.SEAT_T_MIN_MM, spec.SEAT_T_MAX_MM) == pytest.approx((thin, thick))
    assert (spec.SHANK_LENGTH_MM, spec.FINISHED_OVERALL_MM) == pytest.approx(
        (18.6, 31.3)
    )
    band, budget = spec.LENGTH_BAND_WORST_MM, spec.ADJUSTMENT_TRAVEL_MM
    floor = spec.PAST_NUT_FLOOR_MM
    # Thickest plate, shortest part, backed out: the floor plus the margin.
    at_thick = spec.full_threads_past_nut_mm(budget, -band, thick)
    assert at_thick == pytest.approx(1.6876071730)
    assert at_thick >= floor + spec.PAST_NUT_MARGIN_MM
    assert spec.full_threads_past_nut_mm(budget, -band) == pytest.approx(at_thick)
    # The thinner plates only add thread.
    assert spec.full_threads_past_nut_mm(budget, -band, thin) == pytest.approx(
        at_thick + 2 * spec.SEAT_BAND_MM
    )
    # The old nominal-thickness trim (18.0) fails at the thick limit by 0.50.
    old = spec.full_threads_past_nut_mm(budget, -band, thick) - (
        spec.SHANK_LENGTH_MM - 18.0
    )
    assert old == pytest.approx(1.0876071730)
    assert old < floor
    # Deepest cut end: the longest part under the thinnest plate. The band's
    # upper half stops at the uncut 19.05 stock (only 0.45 is cut off).
    assert spec.SHANK_LENGTH_MM + band > anchor.shank_length_mm
    assert anchor.shank_length_mm - spec.SHANK_LENGTH_MM == pytest.approx(0.45)
    assert spec.PROTRUSION_MAX_MM == pytest.approx(
        anchor.shank_length_mm - anchor.unthreaded_shank_length_mm - thin
    )
    assert spec.PROTRUSION_MAX_MM == pytest.approx(9.385)
    # Modelled at nominal thickness, the cut end hangs 8.425 below the plate.
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


def test_chamfer_band_is_owner_accepted_with_both_functional_limits():
    """Machinist gate 2026-10-17 read the 0.46 ±0.05 deburr as over-spec."""
    from machinist_exceptions import load_exceptions

    (entry,) = load_exceptions(_config.CONFIG_DIR, "ch_vn_spring_hook", "part")
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


def _mm_box(x0, y0, x1, y1):
    from _layout_geometry import Box

    return Box(x0 / 1000, y0 / 1000, x1 / 1000, y1 / 1000)


def _mm_run(x0, y0, x1, y1, role):
    from _layout_geometry import Segment

    return Segment(x0 / 1000, y0 / 1000, x1 / 1000, y1 / 1000, role)


def _deburr_ink(placement):
    """The deburr controls' settled ink in sheet mm. ``b344192`` is the
    machinist-reviewed render's layout audit: the 45 deg parked beside its
    45 deg ray at radius 22.3. ``moved`` is FRONT_KEEP's: the text on the
    bisector at radius 26 about the (106.5, 103.2) vertex, the arc broken
    round it, and the width block 2 mm lower."""
    from _layout_geometry import AnnotationGeometry

    if placement == "b344192":
        text, width_row = (120.6, 115.2, 127.4, 118.7), (123.5, 98.2, 212.5, 101.7)
        runs = (
            (109.5, 106.2, 122.9, 119.7, "ext-line"),
            (112.0, 103.2, 129.8, 103.2, "ext-line"),
            (128.8, 103.2, 124.0, 117.0, "dim-line"),
            (124.0, 117.0, 123.1, 118.0, "dim-line"),
            (128.8, 103.2, 128.1, 106.7, "arrow"),
            (122.3, 119.0, 124.5, 116.3, "arrow"),
        )
    else:
        text, width_row = (127.1, 111.4, 133.9, 114.9), (123.5, 96.2, 212.5, 99.7)
        runs = (
            (109.5, 106.2, 125.6, 122.3, "ext-line"),
            (112.0, 103.2, 133.5, 103.2, "ext-line"),
            (132.5, 103.2, 131.6, 109.9, "dim-line"),
            (129.0, 116.2, 124.9, 121.6, "dim-line"),
            (132.5, 103.2, 132.3, 106.7, "arrow"),
            (124.9, 121.6, 127.2, 119.0, "arrow"),
        )
    angle = AnnotationGeometry(
        "ChamferAngle", "dim", "front", (_mm_box(*text),),
        tuple(_mm_run(*run) for run in runs),
    )
    width = AnnotationGeometry("ChamferWidth", "dim", "front", (_mm_box(*width_row),))
    return {"ChamferAngle": angle, "ChamferWidth": width}


@pytest.mark.parametrize("placement", ["moved", "b344192", "own_arrow"])
def test_settled_deburr_texts_clear_their_own_line_ink(monkeypatch, placement):
    """Machinist b344192 (rule 14): the 45 deg sat on its own chamfer
    extension line and arc arrowhead. The reviewed layout must fail the
    settled check and the moved one pass; an own arrowhead within the
    arrow-to-text clearance fails even with every line clear."""
    from dataclasses import replace

    ink = _deburr_ink("b344192" if placement == "b344192" else "moved")
    if placement == "own_arrow":
        angle = ink["ChamferAngle"]
        ink["ChamferAngle"] = replace(
            angle,
            segments=(*angle.segments, _mm_run(129.0, 116.2, 128.0, 115.5, "arrow")),
        )
    reader = SimpleNamespace(take_errors=lambda: [])
    monkeypatch.setattr(drawing, "_Reader", lambda _adapter: reader)
    monkeypatch.setattr(drawing, "_dump_annotation", lambda _reader, name: {"name": name})
    monkeypatch.setattr(drawing, "calibrate_sheet_advance", lambda _records: 0.6)
    monkeypatch.setattr(
        drawing, "annotation_geometry",
        lambda record, *, owner, advance: ink[record["name"]],
    )

    def check():
        drawing._verify_control_ink(None, list(ink))

    if placement == "moved":
        check()
        return
    with pytest.raises(RuntimeError, match="struck by line ink"):
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
