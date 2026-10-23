"""Offline manufacturing boundaries for the trimmed channel-spring anchor."""

import asyncio
import math
from types import SimpleNamespace

import pytest

import _config
import _purchased_fastener_drawing as purchased_drawing
import _drawing_common as drawing_common
import _stock_trim_drawing as trim_drawing
import draw_ch_vn_spring_hook as drawing
import draw_sm_vn_boss_hook as boss_drawing
import ch_vn_spring_hook_spec as spec
import sm_vn_boss_hook_spec as boss_spec
import spring_mount_geom as mounts
import sm_summing_lever_spec as lever
from _hole_spec import TAP_DRILL_MM
from stock_anchor_geom import ANCHOR_9489T111 as anchor
import ch_anchor_jam_nut_spec as jam_nut
from _interference_contracts import CHANNEL_ANCHOR_NUT_THREAD
from _hole_spec import THREAD_MAJOR_MM
from _supplier_reference_geometry import NativeSketchGeometry


def _source_properties(names):
    values = {
        "Supplier": "McMaster-Carr",
        "Supplier SKUs": "9489T111",
        "Stock Name": "PURCHASED EYEBOLT — RETAIN THE EYE",
        "Isometric View Note": "ISOMETRIC VIEW SCALE 3:1",
        "Manufacturing Notes": "CUT TO FINISHED LENGTH\nRESTORE THE END DEBURR",
    }
    return {name: values.get(name, f"source {name}") for name in names}


def _note_double(link, text, x=0.016, y=0.060, *, owner_type=1):
    note = SimpleNamespace(
        PropertyLinkedText=link, text=text, annotation=SimpleNamespace(OwnerType=owner_type),
        extent=(x, y - 0.003, 0.0, x + 0.025, y, 0.0),
    )
    note.GetAnnotation = lambda: note.annotation
    note.GetText = lambda: note.text
    note.annotation.GetType = lambda: 6
    note.annotation.GetSpecificAnnotation = lambda: note
    note.GetExtent = lambda: note.extent
    return note


def _stock_note_contracts(module):
    if module is drawing:
        labels = (
            ("AS-SUPPLIED EYEBOLT BODY — SUPPLIER REFERENCE", 0.016, 0.2627),
            (
                "SUPPLIED HEX NUT OMITTED FROM THIS BODY VIEW\n"
                "STOCK REFERENCES ONLY — FINISHED CUTTING CONTROLS: SHEET 1",
                0.016, 0.089,
            ),
            ("ISOMETRIC VIEW SCALE 3:1", 0.275, 0.153),
        )
    else:
        labels = (
            ("SUPPLIER NOMINAL STOCK ENVELOPE — AS SUPPLIED", 0.016, 0.2627),
            (
                "NOMINAL PROFILE ONLY — INSTALLED VENDOR-CAD EYE UNCHANGED\n"
                "STOCK REFERENCES ONLY — FINISHED TRIM AND CHAMFER: SHEET 1",
                0.016, 0.089,
            ),
        )
    return [(_note_double(text, text, x, y), text, text) for text, x, y in labels]


def _supplier_stock_capture_scene(monkeypatch, adapter, source_model):
    """Provide immutable stock data to tests of labels and the physical eye."""
    points, circle_offsets, line_offsets = [], [], []
    for center, radius_mm in (
        ((0.0, 0.0), boss_spec.SUPPLIER_NOMINAL_EYE_OD_MM / 2.0),
        ((0.0, 0.0), boss_spec.SUPPLIER_EYE_ID_MM / 2.0),
        (boss_spec.SUPPLIER_STOCK_WIRE_CENTER_MM, boss_spec.SUPPLIER_NOMINAL_WIRE_MM / 2.0),
    ):
        x, y = (value / 1000.0 for value in center)
        radius = radius_mm / 1000.0
        circle_offsets.append(len(points))
        points.extend(((x, y, 0.0), (x + radius, y, 0.0), (x, y + radius, 0.0)))
    outline = boss_spec.SUPPLIER_STOCK_SHANK_OUTLINE_MM
    axis = boss_spec.SUPPLIER_STOCK_AXIS_MM
    for start, end in (
        *zip(outline, (*outline[1:], outline[0])),
        *zip(axis, axis[1:]),
    ):
        line_offsets.append(len(points))
        points.extend((x / 1000.0, y / 1000.0, 0.0) for x, y in (start, end))
    capture = boss_drawing.SupplierStockCapture(
        geometry=NativeSketchGeometry(tuple(points), tuple(line_offsets), tuple(circle_offsets)),
        source_path=boss_drawing.SOURCE.resolve().as_posix(),
        configuration=boss_spec.SUPPLIER_STOCK_CONFIGURATION,
        configuration_id=1,
    )
    captured_configurations = []

    def capture_before_drawing(native_adapter, native_source, finished_configuration):
        assert native_adapter is adapter
        assert native_source is source_model
        assert native_adapter.currentModel is source_model
        assert finished_configuration == "Default"
        captured_configurations.append(finished_configuration)
        return capture

    monkeypatch.setattr(boss_drawing, "_capture_supplier_stock", capture_before_drawing)
    return capture, captured_configurations


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
    "target_orientation", ("*Front", "*Isometric"), ids=("front-a269", "iso-a06"),
)
@pytest.mark.parametrize(
    "placement,fault",
    (
        ("old", None),
        ("previous-whole-mm", None),
        ("current", None),
        ("current", "left-boundary"),
        ("current", "bottom-boundary"),
        ("current", "right-boundary"),
        ("current", "top-boundary"),
        ("current", "left"),
        ("current", "bottom"),
        ("current", "right"),
        ("current", "top"),
        ("current", "missing"),
    ),
)
def test_finished_view_creation_fits_recorded_native_cell(
    monkeypatch, tmp_path, target_orientation, placement, fault,
):
    """Replay recorded native boxes, not a new-leaf or printed-edge proof."""
    native_cases = {
        "*Front": (
            "FRONT_CENTER", (0.100, 0.18625), (5.0, 1.0),
            (
                0.06266199906333915, 0.10143093577628477,
                0.13733800093666088, 0.2710690642237152,
            ),
        ),
        "*Isometric": (
            "FINISHED_ISO_CENTER", (0.310, 0.213), (3.0, 1.0),
            (
                0.2872237893868808, 0.15867221871562523,
                0.3327762106131192, 0.2673277812843747,
            ),
        ),
    }
    center_attribute, old_center, _recorded_scale, recorded_outline = native_cases[target_orientation]
    finished_cell = (0.0127, 0.0651, 0.4191, 0.2667)
    overflow = recorded_outline[3] - finished_cell[3]
    whole_mm_shift = math.ceil(overflow * 1000) / 1000
    assert whole_mm_shift == (0.005 if target_orientation == "*Front" else 0.001)
    assert whole_mm_shift <= recorded_outline[1] - finished_cell[1]
    if placement != "current":
        shift = 0.0 if placement == "old" else whole_mm_shift - 0.001
        monkeypatch.setattr(drawing, center_attribute, (old_center[0], old_center[1] - shift))

    source_path = tmp_path / "anchor.SLDPRT"
    source_path.touch()
    monkeypatch.setattr(drawing, "SOURCE", source_path)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(purchased_drawing, "_early_bound", lambda value, _kind: value)
    state = SimpleNamespace(sheet="FINISHED")
    sheet = SimpleNamespace(
        GetProperties2=lambda: (0, 0, 5.0, 1.0, False, 0.4318, 0.2794),
        GetZoneMargin=lambda _side: 0.0127,
    )
    model = SimpleNamespace(
        ActivateSheet=lambda name: setattr(state, "sheet", name) or True,
        GetCurrentSheet=lambda: sheet, GetEditSheet=lambda: True,
        ActiveDrawingView=None,
    )
    model.ActivateView = lambda _name: setattr(model, "ActiveDrawingView", None) or False
    adapter = SimpleNamespace(currentModel=model, _attempt=lambda operation: operation())
    views, placements, refreshed, checked_cells = {}, [], [], []

    def make_view(name, outline):
        view = SimpleNamespace(
            Name=name, outline=outline,
            ReferencedConfiguration=(
                drawing.SUPPLIER_STOCK_CONFIGURATION if name.startswith("stock-") else "Default"
            ),
        )
        view.UpdateViewDisplayGeometry = lambda: refreshed.append(name)
        view.GetOutline = lambda: view.outline
        view.GetFirstDisplayDimension6 = lambda: None
        view.GetAnnotations = lambda: ()
        return view

    def place_view(_adapter, _path, orientation, x, y, *, scale):
        placements.append((orientation, x, y, scale))
        _attribute, baseline_center, baseline_scale, baseline_outline = native_cases[orientation]
        assert scale == baseline_scale
        outline = tuple(
            value + (x, y)[index % 2] - baseline_center[index % 2]
            for index, value in enumerate(baseline_outline)
        )
        if orientation == target_orientation and fault not in (None, "missing"):
            edge = fault.removesuffix("-boundary")
            index = ("left", "bottom", "right", "top").index(edge)
            values = list(outline)
            values[index] = finished_cell[index] + (
                0.0 if fault.endswith("-boundary") else -1e-12 if index < 2 else 1e-12
            )
            outline = tuple(values)
        view = make_view("finished-front" if orientation == "*Front" else "finished-iso", outline)
        views[orientation] = view
        model.ActiveDrawingView = view
        return view

    stock = make_view("stock-front", (0.110, 0.110, 0.190, 0.240))
    stock_iso = make_view("stock-iso", (0.280, 0.180, 0.340, 0.240))

    def iter_views(_adapter):
        if state.sheet == "FINISHED":
            return tuple(
                view for orientation, view in views.items()
                if fault != "missing" or orientation != target_orientation
            )
        return stock, stock_iso

    def assert_fits(adapter, view, cell, *, label):
        assert view.Name in refreshed
        expected = (
            finished_cell if state.sheet == "FINISHED"
            else (0.0127, 0.094, 0.4191, 0.2577)
        )
        assert cell == pytest.approx(expected, rel=0, abs=1e-15)
        checked_cells.append((view.Name, cell))
        purchased_drawing.assert_supplier_view_fits(adapter, view, cell, label=label)

    async def open_model(_path):
        return {"success": True}

    async def finalize(_adapter, _outputs, *, settled_checks, **_kwargs):
        for verify in settled_checks:
            verify()
        return {"layout": "contained"}

    adapter.open_model = open_model
    monkeypatch.setattr(drawing, "active_configuration_name", lambda *_args: "Default")
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_args, **_kwargs: (model, sheet))
    for name in (
        "check", "create_blank_drawing_sheets", "stamp_drawing_summary",
        "set_hidden_lines_removed", "set_dimension_precision", "set_dimension_callouts",
        "_verify_controls", "_verify_supplier_references", "_verify_source_state",
    ):
        monkeypatch.setattr(drawing, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        drawing, "read_required_properties", lambda _model, names, **_kwargs: _source_properties(names),
    )
    monkeypatch.setattr(
        drawing, "add_property_linked_note",
        lambda _adapter, name, x, y, **_kwargs: _note_double(
            drawing.property_link(name), _source_properties((name,))[name], x, y,
        ),
    )
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(drawing, "_supplier_references", lambda *_args: [])
    monkeypatch.setattr(
        drawing, "_supplier_stock_sheet",
        lambda *_args: (stock, stock_iso, [], _stock_note_contracts(drawing)),
    )
    monkeypatch.setattr(drawing, "place_view", place_view)
    monkeypatch.setattr(drawing, "iter_views", iter_views)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(drawing, "assert_supplier_view_fits", assert_fits)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)

    if placement != "current" or fault in ("left", "bottom", "right", "top", "missing"):
        message = "view disappeared" if fault == "missing" else "view leaves its cell"
        with pytest.raises(RuntimeError, match=message):
            asyncio.run(drawing.build(adapter))
        return

    assert asyncio.run(drawing.build(adapter)) == {"layout": "contained"}
    assert placements == [
        ("*Front", 0.100, 0.18125, (5.0, 1.0)),
        ("*Isometric", 0.310, 0.212, (3.0, 1.0)),
    ]
    assert drawing.STOCK_ISO_CENTER == (0.310, 0.203)
    assert drawing.STOCK_CENTER == (0.150, 0.1755)
    assert drawing.FRONT_KEEP == {
        "FinishedOverall": (0.042, 0.18625),
        "ChamferWidth": (0.168, 0.100),
        "ChamferAngle": (0.124, 0.117),
    }
    expected_outline = [
        value - (whole_mm_shift if index % 2 else 0)
        for index, value in enumerate(recorded_outline)
    ]
    if fault is not None:
        index = ("left", "bottom", "right", "top").index(fault.removesuffix("-boundary"))
        expected_outline[index] = finished_cell[index]
    actual_outline = views[target_orientation].outline
    assert actual_outline == pytest.approx(expected_outline, rel=0, abs=1e-15)
    if target_orientation == "*Isometric" and fault is None:
        assert (
            actual_outline[0] - finished_cell[0],
            actual_outline[1] - finished_cell[1],
            finished_cell[2] - actual_outline[2],
            finished_cell[3] - actual_outline[3],
        ) == pytest.approx(
            (0.2745237893868808, 0.09257221871562523, 0.0863237893868808, 0.0003722187156253),
            rel=0, abs=1e-15,
        )
    assert [name for name, _cell in checked_cells] == [
        "finished-front", "finished-iso", "stock-front", "stock-iso",
    ]


def _settled_eye_scene(monkeypatch, module):
    """Model fresh geometry while retaining only stable native annotation identity."""
    monkeypatch.setattr(module, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(module, "assert_supplier_reference_dimension", lambda *_args, **_kwargs: None)
    state = SimpleNamespace(sheet="FINISHED", saved=False)
    model = SimpleNamespace(
        ActivateSheet=lambda name: setattr(state, "sheet", name) or True,
        ActiveDrawingView=None, GetEditSheet=lambda: True,
        GetType=lambda: 3,
        GetPathName=lambda: str(module.OUTPUTS.slddrw.resolve()) if state.saved else "",
    )
    model.ActivateView = lambda _name: setattr(model, "ActiveDrawingView", None) or False
    owner = SimpleNamespace(Name="Wire")
    source = SimpleNamespace(
        GetPathName=lambda: str(module.SOURCE.resolve()).upper().replace("/", "\\"),
        FeatureByName=lambda name: owner if name == "Wire" else None,
    )
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )
    adapter.swApp.ActiveDoc = model
    adapter.swApp.GetOpenDocumentByName = lambda _path: adapter.currentModel
    supplier = anchor if module is drawing else module._SUPPLIER_ANCHOR
    surface = SimpleNamespace(
        IsTorus=lambda: True,
        TorusParams=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0,
                     supplier.eye_mean_radius_mm / 1000, supplier.wire_dia_mm / 2000),
    )
    face = SimpleNamespace(GetSurface=lambda: surface, GetFeature=lambda: owner)
    drawing_owner = SimpleNamespace(Name="Wire")
    drawing_surface = SimpleNamespace(
        IsTorus=lambda: True, TorusParams=surface.TorusParams,
    )
    mapped_faces, mapping_calls = {}, []

    def corresponding_entity(drawing_face):
        mapping_calls.append(drawing_face)
        return mapped_faces.get(id(drawing_face))

    source.Extension = SimpleNamespace(GetCorrespondingEntity2=corresponding_entity)
    views, refs_by_sheet, contracts, annotations, contours = {}, {}, {}, {}, {}
    display_lists, native_dimensions = {}, {}
    diameters = spec.SUPPLIER_EYE_MM if module is drawing else {"EyeID": module.SUPPLIER_EYE_ID_MM}

    def contour(diameter, attached_face=face):
        source_face = attached_face
        attached_face = SimpleNamespace(
            GetFeature=lambda: drawing_owner, GetSurface=lambda: drawing_surface,
        )
        mapped_faces[id(attached_face)] = source_face
        curve = SimpleNamespace(
            IsCircle=lambda: True,
            CircleParams=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, diameter / 2000),
        )
        return SimpleNamespace(
            GetCurve=lambda: curve, GetFace=lambda: attached_face,
            GetView=lambda: views["FINISHED"],
        )

    contours.update({name: contour(diameter) for name, diameter in diameters.items()})
    stock_names = (
        ("SupplierStockThread", "SupplierStockShank", "SupplierStockOverall")
        if module is drawing else
        ("SupplierNominalEyeOD", "SupplierNominalWire", "SupplierStockShank", "SupplierStockOverall")
    )
    for sheet, names, configuration in (
        ("FINISHED", (*diameters, "SupplierThreadMajor"), "Default"),
        ("SUPPLIER-STOCK", stock_names, module.SUPPLIER_STOCK_CONFIGURATION),
    ):
        displays, refs = [], []
        for name in names:
            feature = (
                "native-eye" if name in contours else
                module.SUPPLIER_THREAD_FEATURE if name == "SupplierThreadMajor" else
                module.SUPPLIER_STOCK_FEATURE
            )
            key = f"{name}@{feature}@anchor.SLDPRT"
            native = SimpleNamespace(FullName=key, Tolerance=SimpleNamespace(Type=0), DrivenState=1)
            annotation = SimpleNamespace(
                entities=[contours[name]] if name in contours else [],
                kinds=[46] if name in contours else [], IsDangling=lambda: False,
                GetType=lambda: 4, OwnerType=0,
            )
            annotation.GetAttachedEntities3 = lambda annotation=annotation: tuple(annotation.entities)
            annotation.GetAttachedEntityTypes = lambda annotation=annotation: tuple(annotation.kinds)
            annotation.GetAttachedEntityCount3 = lambda annotation=annotation: len(annotation.entities)
            annotations[name] = annotation
            display = SimpleNamespace(
                GetDimension2=lambda _index, native=native: native,
                GetAnnotation=lambda annotation=annotation: annotation,
            )
            annotation.GetSpecificAnnotation = lambda display=display: display
            displays.append(display)
            native_dimensions[name] = native
            refs.append((key, {"label": name, "expected_mm": diameters.get(name, 1.0)}))
        if sheet == "FINISHED":
            for name in module.FRONT_KEEP:
                native = SimpleNamespace(FullName=f"{name}@control@anchor.SLDPRT")
                annotation = SimpleNamespace(GetType=lambda: 4, OwnerType=0)
                display = SimpleNamespace(
                    GetDimension2=lambda _index, native=native: native,
                    GetAnnotation=lambda annotation=annotation: annotation,
                )
                annotation.GetSpecificAnnotation = lambda display=display: display
                displays.append(display)
        for index, display in enumerate(displays):
            following = displays[index + 1] if index + 1 < len(displays) else None
            display.GetNext5 = lambda following=following: following
        view = SimpleNamespace(
            Name=f"{sheet}-front", ReferencedConfiguration=configuration,
            ReferencedDocument=source,
            GetCorrespondingEntity=lambda _face: None,
            UpdateViewDisplayGeometry=lambda: pytest.fail("geometry-read-only verifier refreshed a view"),
            GetFirstDisplayDimension6=lambda displays=displays: displays[0],
        )
        views[sheet], refs_by_sheet[sheet] = view, refs
        display_lists[sheet] = displays
        for display in displays:
            display.GetAnnotation().Owner = view
        view.GetAnnotations = lambda displays=displays: tuple(
            display.GetAnnotation() for display in displays
        )
        contracts[sheet] = ((view.Name,), configuration)
    monkeypatch.setattr(module, "iter_views", lambda _adapter: (views[state.sheet],))
    monkeypatch.setattr(module, "view_name", lambda _adapter, view: view.Name)
    if module is drawing:
        monkeypatch.setattr(
            module, "visible_view_entities",
            lambda *_args, **_kwargs: pytest.fail("settled proof must not rescan visible contours"),
        )
    return SimpleNamespace(
        adapter=adapter, refs=refs_by_sheet, contracts=contracts, contours=contours,
        annotations=annotations, views=views, source=source, owner=owner,
        face=face, surface=surface, contour=contour, diameters=diameters, state=state,
        drawing_owner=drawing_owner, drawing_surface=drawing_surface,
        mapped_faces=mapped_faces, mapping_calls=mapping_calls,
        display_lists=display_lists, native_dimensions=native_dimensions,
    )


@pytest.mark.parametrize(
    "fault",
    (
        None, "missing", "duplicate", "foreign-annotation", "foreign-owner",
        "sheet-owner", "missing-owner", "foreign-view", "renamed-view",
        "foreign-source", "missing-source", "source-config", "stock-config",
        "source-path", "foreign-drawing", "output-path", "unsaved-path",
        "relative-path", "document-type", "annotation-type", "missing-display",
        "foreign-display", "foreign-returned-annotation", "empty-key", "duplicate-key",
        "incomplete-snapshot", "missing-drawing", "foreign-active-document",
        "missing-open-document", "duplicate-view", "changed-contract-config",
        "cross-sheet-duplicate-key",
    ),
)
def test_channel_saved_keys_require_original_native_annotation_and_binding(monkeypatch, fault):
    scene = _settled_eye_scene(monkeypatch, drawing)
    prior = drawing._verify_supplier_references(scene.adapter, scene.refs, scene.contracts)
    original_refs = {sheet: list(refs) for sheet, refs in scene.refs.items()}
    model, front = scene.adapter.currentModel, scene.views["FINISHED"]
    annotation = scene.annotations["EyeOD"]
    scene.state.saved = True
    scene.native_dimensions["EyeOD"].FullName = "opaque saved key / OD !"
    scene.native_dimensions["EyeID"].FullName = "another actual saved key / ID !"
    actual_annotations = tuple(front.GetAnnotations())
    if fault == "missing":
        front.GetAnnotations = lambda: tuple(item for item in actual_annotations if item is not annotation)
    elif fault == "duplicate":
        front.GetAnnotations = lambda: (*actual_annotations, annotation)
    elif fault == "foreign-annotation":
        foreign = SimpleNamespace(**vars(annotation))
        front.GetAnnotations = lambda: tuple(foreign if item is annotation else item for item in actual_annotations)
    elif fault == "foreign-owner":
        annotation.Owner = SimpleNamespace(**vars(front))
    elif fault == "sheet-owner":
        annotation.OwnerType = 1
    elif fault == "missing-owner":
        annotation.Owner = None
    elif fault == "foreign-view":
        scene.views["FINISHED"] = SimpleNamespace(**vars(front))
    elif fault == "renamed-view":
        front.Name = "different-view"
    elif fault == "foreign-source":
        front.ReferencedDocument = SimpleNamespace(**vars(scene.source))
    elif fault == "missing-source":
        front.ReferencedDocument = None
    elif fault == "source-config":
        front.ReferencedConfiguration = drawing.SUPPLIER_STOCK_CONFIGURATION
    elif fault == "stock-config":
        scene.views["SUPPLIER-STOCK"].ReferencedConfiguration = "Default"
    elif fault == "source-path":
        scene.source.GetPathName = lambda: str(drawing.SOURCE.parent / "foreign.SLDPRT")
    elif fault == "foreign-drawing":
        foreign = SimpleNamespace(**vars(model))
        scene.adapter.currentModel = foreign
        scene.adapter.swApp.ActiveDoc = foreign
    elif fault == "missing-drawing":
        scene.adapter.currentModel = None
    elif fault == "foreign-active-document":
        scene.adapter.swApp.ActiveDoc = SimpleNamespace(**vars(model))
    elif fault == "missing-open-document":
        scene.adapter.swApp.GetOpenDocumentByName = lambda _path: None
    elif fault == "duplicate-view":
        monkeypatch.setattr(
            drawing, "iter_views", lambda _adapter: (scene.views[scene.state.sheet],) * 2,
        )
    elif fault == "changed-contract-config":
        front.ReferencedConfiguration = "ChangedConfiguration"
        scene.contracts["FINISHED"] = (scene.contracts["FINISHED"][0], "ChangedConfiguration")
    elif fault == "output-path":
        model.GetPathName = lambda: str(drawing.OUTPUTS.slddrw.parent / "foreign.SLDDRW")
    elif fault == "unsaved-path":
        model.GetPathName = lambda: ""
    elif fault == "relative-path":
        model.GetPathName = lambda: drawing.OUTPUTS.slddrw.name
    elif fault == "document-type":
        model.GetType = lambda: 1
    elif fault == "annotation-type":
        annotation.GetType = lambda: 6
    elif fault == "missing-display":
        annotation.GetSpecificAnnotation = lambda: None
    elif fault == "foreign-display":
        annotation.GetSpecificAnnotation = lambda: scene.annotations["EyeID"].GetSpecificAnnotation()
    elif fault == "foreign-returned-annotation":
        annotation.GetSpecificAnnotation().GetAnnotation = lambda: scene.annotations["EyeID"]
    elif fault == "empty-key":
        scene.native_dimensions["EyeOD"].FullName = ""
    elif fault == "duplicate-key":
        scene.native_dimensions["EyeOD"].FullName = scene.native_dimensions["EyeID"].FullName
    elif fault == "cross-sheet-duplicate-key":
        scene.native_dimensions["EyeOD"].FullName = scene.native_dimensions["SupplierStockThread"].FullName
    elif fault == "incomplete-snapshot":
        prior = prior[:-1]
    if fault is not None:
        with pytest.raises(RuntimeError):
            drawing._capture_saved_supplier_references(scene.adapter, scene.refs, scene.contracts, prior)
        assert scene.refs == original_refs
        return
    # No relaxed old-key verifier: the pre-save FullName keys still refuse.
    with pytest.raises(RuntimeError, match="supplier dimension disappeared"):
        drawing._verify_supplier_references(scene.adapter, scene.refs, scene.contracts)
    captured = drawing._capture_saved_supplier_references(
        scene.adapter, scene.refs, scene.contracts, prior,
    )
    assert len(drawing._verify_supplier_references(scene.adapter, captured, scene.contracts)) == 6
    assert [key for key, contract in captured["FINISHED"] if contract["label"] in drawing.SUPPLIER_EYE_MM] == [
        "opaque saved key / OD !", "another actual saved key / ID !",
    ]
    assert scene.refs == original_refs
    assert captured is not scene.refs


@pytest.mark.parametrize("identity", ("annotation", "view", "source", "drawing", "display"))
@pytest.mark.parametrize("state", (0, -1, 2, True, 1.0, "1", None))
def test_channel_saved_identity_requires_exact_native_integer_equality(monkeypatch, identity, state):
    scene = _settled_eye_scene(monkeypatch, drawing)
    prior = drawing._verify_supplier_references(scene.adapter, scene.refs, scene.contracts)
    scene.state.saved = True
    target = {
        "annotation": scene.annotations["EyeOD"],
        "view": scene.views["FINISHED"],
        "source": scene.source,
        "drawing": scene.adapter.currentModel,
        "display": scene.annotations["EyeOD"].GetSpecificAnnotation(),
    }[identity]
    scene.adapter.swApp.IsSame = lambda left, right: (
        state if left is target and right is target else int(left is right)
    )
    with pytest.raises(RuntimeError):
        drawing._capture_saved_supplier_references(scene.adapter, scene.refs, scene.contracts, prior)


@pytest.mark.parametrize("member", ("document-path", "source-path", "annotations", "specific", "annotation-type"))
def test_channel_saved_metadata_errors_refuse_without_best_effort_acceptance(monkeypatch, member):
    scene = _settled_eye_scene(monkeypatch, drawing)
    prior = drawing._verify_supplier_references(scene.adapter, scene.refs, scene.contracts)
    scene.state.saved = True
    error = OSError(f"native metadata disconnected: {member}")

    def failed():
        raise error

    target, name = {
        "document-path": (scene.adapter.currentModel, "GetPathName"),
        "source-path": (scene.source, "GetPathName"),
        "annotations": (scene.views["FINISHED"], "GetAnnotations"),
        "specific": (scene.annotations["EyeOD"], "GetSpecificAnnotation"),
        "annotation-type": (scene.annotations["EyeOD"], "GetType"),
    }[member]
    setattr(target, name, failed)
    with pytest.raises(OSError) as caught:
        drawing._capture_saved_supplier_references(scene.adapter, scene.refs, scene.contracts, prior)
    assert caught.value is error


def test_channel_saved_capture_uses_native_identity_not_python_wrappers(monkeypatch):
    scene = _settled_eye_scene(monkeypatch, drawing)
    prior = drawing._verify_supplier_references(scene.adapter, scene.refs, scene.contracts)
    scene.state.saved = True
    front = scene.views["FINISHED"]
    original = scene.annotations["EyeOD"]
    wrapped_view, wrapped_source = SimpleNamespace(**vars(front)), SimpleNamespace(**vars(scene.source))
    wrapped_annotation = SimpleNamespace(**vars(original))
    wrapped_view.ReferencedDocument = wrapped_source
    wrapped_annotation.Owner = wrapped_view
    annotations = tuple(front.GetAnnotations())
    wrapped_view.GetAnnotations = lambda: tuple(
        wrapped_annotation if item is original else item for item in annotations
    )
    original.GetSpecificAnnotation().GetAnnotation = lambda: wrapped_annotation
    scene.views["FINISHED"] = wrapped_view
    aliases = {id(wrapped_view): id(front), id(wrapped_source): id(scene.source), id(wrapped_annotation): id(original)}
    scene.adapter.swApp.IsSame = lambda left, right: int(
        aliases.get(id(left), id(left)) == aliases.get(id(right), id(right))
    )
    scene.native_dimensions["EyeOD"].FullName = "actual wrapper-independent native key"
    captured = drawing._capture_saved_supplier_references(
        scene.adapter, scene.refs, scene.contracts, prior,
    )
    assert len(drawing._verify_supplier_references(scene.adapter, captured, scene.contracts)) == 6
    assert captured["FINISHED"][0][0] == "actual wrapper-independent native key"


@pytest.mark.parametrize("face_context", ("drawing-proxy", "source-face"))
@pytest.mark.parametrize(
    "mapping", ("authoritative", "missing-extension", "unmapped", "foreign-owner", "wrong-sourcepart"),
)
def test_channel_eye_requires_mapping_into_the_authoritative_source_part(
    monkeypatch, face_context, mapping,
):
    scene = _settled_eye_scene(monkeypatch, drawing)
    front, eye = scene.views["FINISHED"], scene.contours["EyeID"]
    drawing_face = eye.GetFace()
    assert drawing_face.GetFeature().Name == scene.owner.Name == "Wire"
    assert scene.adapter.swApp.IsSame(drawing_face.GetFeature(), scene.owner) == 0
    if face_context == "source-face":
        # Even an apparently authoritative direct face cannot bypass mapping.
        drawing_face = scene.face
        eye.GetFace = lambda: drawing_face
        scene.mapped_faces[id(drawing_face)] = scene.face
    if mapping == "missing-extension":
        scene.source.Extension = None
    elif mapping == "unmapped":
        scene.mapped_faces.clear()
    elif mapping == "foreign-owner":
        foreign_owner = SimpleNamespace(Name="Wire")
        scene.mapped_faces[id(drawing_face)] = SimpleNamespace(
            GetFeature=lambda: foreign_owner, GetSurface=lambda: scene.surface,
        )
    elif mapping == "wrong-sourcepart":
        foreign_owner = SimpleNamespace(Name="Wire")
        foreign_face = SimpleNamespace(
            GetFeature=lambda: foreign_owner, GetSurface=lambda: scene.surface,
        )
        front.ReferencedDocument = SimpleNamespace(
            GetPathName=lambda: str(drawing.SOURCE.parent / "foreign.SLDPRT"),
            FeatureByName=lambda _name: foreign_owner,
            Extension=SimpleNamespace(GetCorrespondingEntity2=lambda _face: foreign_face),
        )
    result = drawing._supplier_eye_circle(scene.adapter, front, eye)
    if mapping == "authoritative":
        assert result == eye.GetCurve().CircleParams
    else:
        assert result is None


@pytest.mark.parametrize("module", (drawing, boss_drawing))
@pytest.mark.parametrize(
    "fault", (None, "missing-curve", "stale-curve", "noncircle", "short-circle",
              "nan-circle", "infinite-circle", "wrong-center", "wrong-normal",
              "missing-face", "missing-surface", "nontorus", "short-torus",
              "nan-torus", "infinite-torus", "bend-torus", "wrong-wire",
              "wrong-torus-center", "wrong-torus-normal", "foreign-feature",
              "missing-feature", "missing-owner", "not-same", "wrong-path", "wrong-view"),
)
def test_supplier_eye_proves_authoritative_wire_and_torus(monkeypatch, module, fault):
    scene = _settled_eye_scene(monkeypatch, module)
    eye = scene.contours["EyeID"]
    curve = eye.GetCurve()
    configuration_args = (
        (scene.contracts["FINISHED"][1],) if module is boss_drawing else ()
    )
    if fault == "missing-curve":
        eye.GetCurve = lambda: None
    elif fault == "stale-curve":
        def stale():
            raise RuntimeError("disconnected native curve")
        eye.GetCurve = stale
    elif fault == "noncircle":
        curve.IsCircle = lambda: False
    elif fault == "short-circle":
        curve.CircleParams = curve.CircleParams[:-1]
    elif fault in ("nan-circle", "infinite-circle", "wrong-center", "wrong-normal"):
        values = list(curve.CircleParams)
        index = 5 if fault == "wrong-normal" else 0
        values[index] = {"nan-circle": math.nan, "infinite-circle": math.inf,
                         "wrong-center": 2e-8, "wrong-normal": 0.5}[fault]
        curve.CircleParams = tuple(values)
    elif fault == "missing-face":
        eye.GetFace = lambda: None
    elif fault == "missing-surface":
        scene.face.GetSurface = lambda: None
    elif fault == "nontorus":
        scene.surface.IsTorus = lambda: False
    elif fault == "short-torus":
        scene.surface.TorusParams = scene.surface.TorusParams[:-1]
    elif fault in ("nan-torus", "infinite-torus", "bend-torus", "wrong-wire",
                   "wrong-torus-center", "wrong-torus-normal"):
        values = list(scene.surface.TorusParams)
        index = {"nan-torus": 6, "infinite-torus": 7, "bend-torus": 6, "wrong-wire": 7,
                 "wrong-torus-center": 0, "wrong-torus-normal": 5}[fault]
        values[index] = (
            math.nan if fault == "nan-torus" else math.inf if fault == "infinite-torus"
            else values[index] + 1e-4
        )
        scene.surface.TorusParams = tuple(values)
    elif fault == "foreign-feature":
        # The impostor is visible and has exactly the right circle and torus.
        scene.face.GetFeature = lambda: SimpleNamespace(Name="Wire")
    elif fault == "missing-feature":
        scene.source.FeatureByName = lambda _name: None
    elif fault == "missing-owner":
        scene.face.GetFeature = lambda: None
    elif fault == "not-same":
        scene.adapter.swApp.IsSame = lambda *_args: 0
    elif fault == "wrong-path":
        scene.source.GetPathName = lambda: "D:/unrelated/anchor.SLDPRT"
    elif fault == "wrong-view":
        eye.GetView = lambda: SimpleNamespace(Name="unrelated-front")
    if fault == "stale-curve":
        with pytest.raises(RuntimeError, match="disconnected native curve"):
            module._supplier_eye_circle(
                scene.adapter, scene.views["FINISHED"], eye, *configuration_args,
            )
        return
    result = module._supplier_eye_circle(
        scene.adapter, scene.views["FINISHED"], eye, *configuration_args,
    )
    if fault is None:
        assert result == curve.CircleParams
    else:
        assert result is None


@pytest.mark.parametrize(
    "module,label", ((drawing, "EyeOD"), (drawing, "EyeID"), (boss_drawing, "EyeID")),
)
@pytest.mark.parametrize(
    "fault", (None, "outer", "foreign-visible", "circle-gap", "missing", "null", "extra", "wrong-type",
              "wrong-configuration", "wrong-view", "dangling", "count-mismatch",
              "wrong-path", "missing-dimension", "extra-dimension"),
)
def test_settled_eye_reacquires_physical_owner_without_old_handles(monkeypatch, module, label, fault):
    scene = _settled_eye_scene(monkeypatch, module)
    annotation = scene.annotations[label]
    if fault == "outer":
        wrong_diameter = (
            scene.diameters["EyeID" if label == "EyeOD" else "EyeOD"]
            if module is drawing else module._SUPPLIER_ANCHOR.eye_od_mm
        )
        annotation.entities = [scene.contour(wrong_diameter)]
    elif fault == "foreign-visible":
        foreign_face = SimpleNamespace(
            GetSurface=lambda: scene.surface,
            GetFeature=lambda: SimpleNamespace(Name="Wire"),
        )
        annotation.entities = [scene.contour(scene.diameters[label], foreign_face)]
    elif fault == "circle-gap":
        replacement = scene.contour(scene.diameters[label])
        replacement.GetCurve().IsCircle = lambda: False
        annotation.entities = [replacement]
    elif fault == "missing":
        annotation.entities = []
    elif fault == "null":
        annotation.entities = [None]
    elif fault == "extra":
        annotation.entities *= 2
    elif fault == "wrong-type":
        annotation.kinds = [1]
    elif fault == "wrong-configuration":
        scene.views["FINISHED"].ReferencedConfiguration = module.SUPPLIER_STOCK_CONFIGURATION
    elif fault == "wrong-view":
        scene.contours[label].GetView = lambda: SimpleNamespace(Name="other-view")
    elif fault == "dangling":
        annotation.IsDangling = lambda: True
    elif fault == "count-mismatch":
        annotation.GetAttachedEntityCount3 = lambda: 2
    elif fault == "wrong-path":
        scene.source.GetPathName = lambda: "D:/foreign.SLDPRT"
    elif fault == "missing-dimension":
        first = scene.views["FINISHED"].GetFirstDisplayDimension6()
        first.GetDimension2(0).FullName = "lost@other@anchor.SLDPRT"
    elif fault == "extra-dimension":
        first = scene.views["FINISHED"].GetFirstDisplayDimension6()
        extra = SimpleNamespace(
            GetDimension2=lambda _index: SimpleNamespace(FullName="Unexpected@owner@anchor.SLDPRT"),
            GetNext5=lambda: first,
        )
        scene.views["FINISHED"].GetFirstDisplayDimension6 = lambda: extra
    if fault is None:
        # A rebuild invalidates the old face, but replaces it with a fresh Wire face.
        old_face = scene.face
        old_face.GetFeature = lambda: pytest.fail("dereferenced obsolete pre-rebuild face")
        fresh_face = SimpleNamespace(GetSurface=lambda: scene.surface, GetFeature=lambda: scene.owner)
        for name, diameter in scene.diameters.items():
            scene.annotations[name].entities = [scene.contour(diameter, fresh_face)]
        for old_contour in scene.contours.values():
            old_contour.GetCurve = lambda: pytest.fail("dereferenced obsolete pre-rebuild contour")
        module._verify_supplier_references(scene.adapter, scene.refs, scene.contracts)
    else:
        with pytest.raises(RuntimeError):
            module._verify_supplier_references(scene.adapter, scene.refs, scene.contracts)


@pytest.mark.parametrize("module", (drawing, boss_drawing))
@pytest.mark.parametrize(
    "drift", (None, "foreign-feature", "wrong-torus", "wrong-circle",
              "lost-imported-control", "changed-imported-control",
              "pdf-key", "close-key", "pdf-circle", "close-circle",
              "pdf-owner", "close-source", "pdf-output-path"),
)
def test_build_retains_controls_and_refuses_native_save_physical_drift(monkeypatch, tmp_path, module, drift):
    """Execute the real build and its supplied finalizer callbacks, not extracted AST."""
    source_path = tmp_path / "anchor.SLDPRT"
    source_path.touch()
    monkeypatch.setattr(module, "SOURCE", source_path)
    scene = _settled_eye_scene(monkeypatch, module)
    source = scene.source
    front, stock = scene.views["FINISHED"], scene.views["SUPPLIER-STOCK"]
    iso = SimpleNamespace(
        Name="finished-iso", ReferencedConfiguration="Default", ReferencedDocument=source,
        GetAnnotations=lambda: (),
    )
    stock_iso = SimpleNamespace(
        Name="stock-iso", ReferencedConfiguration=module.SUPPLIER_STOCK_CONFIGURATION,
        ReferencedDocument=source, GetAnnotations=lambda: (),
    )
    model = scene.adapter.currentModel
    stock_capture, capture_calls = (
        _supplier_stock_capture_scene(monkeypatch, scene.adapter, source)
        if module is boss_drawing else (None, [])
    )
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(trim_drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    imported_controls = []
    for name, (nominal, lower, upper) in module.EXPECTED_CONTROLS.items():
        dimension = SimpleNamespace(
            DrivenState=2, SystemValue=nominal,
            Tolerance=SimpleNamespace(
                Type=module.DIMENSION_TOLERANCE_TYPES[name],
                GetMinValue=lambda lower=lower: lower,
                GetMaxValue=lambda upper=upper: upper,
            ),
        )
        display = SimpleNamespace(
            GetDimension2=lambda _index, dimension=dimension: dimension,
            GetText=lambda _index: "",
            GetPrimaryPrecision2=lambda name=name: module.DIMENSION_PRECISION[name],
        )
        imported_controls.append(SimpleNamespace(
            name=name, dimension=dimension,
            GetSpecificAnnotation=lambda display=display: display,
        ))

    async def open_model(_path):
        scene.adapter.currentModel = source
        return {"success": True}

    def new_drawing(*_args, **_kwargs):
        if module is boss_drawing:
            assert capture_calls == ["Default"]
        scene.adapter.currentModel = model
        return model, object()

    monkeypatch.setattr(scene.adapter, "open_model", open_model, raising=False)
    monkeypatch.setattr(module, "check", lambda *_args: None)
    monkeypatch.setattr(module, "active_configuration_name", lambda *_args: "Default")
    monkeypatch.setattr(module, "new_project_drawing", new_drawing)
    for name in ("create_blank_drawing_sheets", "stamp_drawing_summary",
                 "set_dimension_precision", "set_dimension_callouts",
                 "set_hidden_lines_removed", "_verify_supplier_layout", "_verify_source_state"):
        monkeypatch.setattr(module, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module, "read_required_properties", lambda _model, names, **_kwargs: _source_properties(names),
    )
    monkeypatch.setattr(
        module, "add_property_linked_note",
        lambda _adapter, name, x, y, **_kwargs: _note_double(
            module.property_link(name), _source_properties((name,))[name], x, y,
        ),
    )
    monkeypatch.setattr(module, "curate_view_dimensions", lambda *_args, **_kwargs: imported_controls)
    monkeypatch.setattr(module, "place_view", lambda _adapter, _path, orientation, *_args, **_kwargs:
                        front if orientation == "*Front" else iso)
    def supplier_references(*_args):
        if module is boss_drawing:
            assert _args[2] == scene.contracts["FINISHED"][1]
        if drift == "lost-imported-control":
            imported_controls.pop()
        elif drift == "changed-imported-control":
            imported_controls[0].dimension.SystemValue += 0.001
        return scene.refs["FINISHED"]

    monkeypatch.setattr(module, "_supplier_references", supplier_references)
    if module is drawing:
        monkeypatch.setattr(module, "_supplier_stock_sheet", lambda *_args:
                            (stock, stock_iso, scene.refs["SUPPLIER-STOCK"], _stock_note_contracts(module)))
        monkeypatch.setattr(module, "iter_views", lambda _adapter:
                            (front, iso) if scene.state.sheet == "FINISHED" else (stock, stock_iso))
    else:
        def supplier_stock_diagram(stock_adapter, source_model, capture):
            assert stock_adapter is scene.adapter
            assert source_model is source
            assert capture is stock_capture
            return stock, scene.refs["SUPPLIER-STOCK"], _stock_note_contracts(module)

        monkeypatch.setattr(module, "_supplier_stock_diagram", supplier_stock_diagram)
        monkeypatch.setattr(module, "iter_views", lambda _adapter:
                            (front, iso) if scene.state.sheet == "FINISHED" else (stock,))
    saved = []

    async def finalize(_adapter, _outputs, *, settled_checks, checkpoint, **_kwargs):
        for verify in settled_checks:
            verify()
        observations_before_save = len(scene.mapping_calls)
        sheet_before_save = scene.state.sheet
        checkpoint("before_drawing_save")
        assert len(scene.mapping_calls) == observations_before_save
        assert scene.state.sheet == sheet_before_save
        saved.append("native-save")
        scene.state.saved = True
        # Actual native FullName strings are deliberately opaque for physical
        # dimensions; only original annotation identity may associate them.
        for index, name in enumerate(scene.diameters):
            scene.native_dimensions[name].FullName = f"saved-native-key-{index}!"
        fresh_surface = SimpleNamespace(
            IsTorus=lambda: True, TorusParams=scene.surface.TorusParams,
        )
        fresh_owner = (
            SimpleNamespace(Name="Wire") if drift == "foreign-feature" else scene.owner
        )
        fresh_face = SimpleNamespace(
            GetSurface=lambda: fresh_surface, GetFeature=lambda: fresh_owner,
        )
        if drift == "wrong-torus":
            values = list(fresh_surface.TorusParams)
            values[6] += 0.001
            fresh_surface.TorusParams = tuple(values)
        for name, diameter in scene.diameters.items():
            replacement = scene.contour(diameter, fresh_face)
            if drift == "wrong-circle" and name == "EyeID":
                values = list(replacement.GetCurve().CircleParams)
                values[6] += 0.001
                replacement.GetCurve().CircleParams = tuple(values)
            scene.annotations[name].entities = [replacement]
        scene.face.GetFeature = lambda: pytest.fail("read pre-save source face")
        for old_contour in scene.contours.values():
            old_contour.GetCurve = lambda: pytest.fail("read pre-save contour")

        def unexpected_mutation(*_args):
            pytest.fail("native-save observer mutated geometry or source configuration")

        model.EditRebuild3 = unexpected_mutation
        model.ForceRebuild3 = unexpected_mutation
        source.ShowConfiguration2 = unexpected_mutation
        checkpoint("after_drawing_save")
        assert scene.state.sheet == "FINISHED"
        observations_after_save = len(scene.mapping_calls)
        if drift == "pdf-key":
            scene.native_dimensions["EyeID"].FullName = "unexpected later PDF key"
        elif drift == "pdf-circle":
            scene.annotations["EyeID"].entities = [scene.contour(scene.diameters["EyeID"] + 1.0, fresh_face)]
        elif drift == "pdf-owner":
            scene.annotations["EyeID"].Owner = iso
        elif drift == "pdf-output-path":
            model.GetPathName = lambda: str(module.OUTPUTS.slddrw.parent / "foreign.SLDDRW")
        checkpoint("after_pdf_save")
        assert len(scene.mapping_calls) > observations_after_save
        assert scene.state.sheet == "FINISHED"
        if drift == "close-key":
            scene.native_dimensions["EyeID"].FullName = "unexpected later close key"
        elif drift == "close-circle":
            scene.annotations["EyeID"].entities = [scene.contour(scene.diameters["EyeID"] + 1.0, fresh_face)]
        elif drift == "close-source":
            front.ReferencedDocument = SimpleNamespace(**vars(source))
        checkpoint("before_drawing_close")
        assert scene.state.sheet == "FINISHED"
        saved.append("pdf-export")
        return {"drawing": "saved"}

    monkeypatch.setattr(module, "finalize_drawing", finalize)
    if drift is None:
        assert asyncio.run(module.build(scene.adapter)) == {"drawing": "saved"}
        assert saved == ["native-save", "pdf-export"]
    else:
        with pytest.raises(RuntimeError):
            asyncio.run(module.build(scene.adapter))
        assert saved == ([] if drift in ("lost-imported-control", "changed-imported-control")
                         else ["native-save"])


@pytest.mark.parametrize("module", (drawing, boss_drawing))
@pytest.mark.parametrize("geometry", ("circle", "torus"))
def test_supplier_origin_boundary_preserves_recipe_contract(monkeypatch, module, geometry):
    scene = _settled_eye_scene(monkeypatch, module)
    eye = scene.contours["EyeID"]
    target = eye.GetCurve() if geometry == "circle" else scene.surface
    attribute = "CircleParams" if geometry == "circle" else "TorusParams"
    values = list(getattr(target, attribute))
    values[0] = 1e-8
    setattr(target, attribute, tuple(values))
    configuration_args = (
        (scene.contracts["FINISHED"][1],) if module is boss_drawing else ()
    )
    result = module._supplier_eye_circle(
        scene.adapter, scene.views["FINISHED"], eye, *configuration_args,
    )
    if module is drawing:
        assert result == eye.GetCurve().CircleParams
    else:
        assert result is None


@pytest.mark.parametrize(
    "fault", (None, "foreign-visible", "wrong-eye-torus", "missing-id", "missing-od", "circle-gap"),
)
def test_channel_creation_uses_source_proof_and_returns_only_data(monkeypatch, fault):
    scene = _settled_eye_scene(monkeypatch, drawing)
    visible = list(scene.contours.values())
    if fault == "foreign-visible":
        scene.face.GetFeature = lambda: SimpleNamespace(Name="Wire")
    elif fault == "wrong-eye-torus":
        values = list(scene.surface.TorusParams)
        values[6] += 0.001
        scene.surface.TorusParams = tuple(values)
    elif fault == "missing-id":
        visible = [scene.contours["EyeOD"]]
    elif fault == "missing-od":
        visible = [scene.contours["EyeID"]]
    elif fault == "circle-gap":
        scene.contours["EyeID"].GetCurve().IsCircle = lambda: False
    monkeypatch.setattr(drawing, "visible_view_entities", lambda *_args, **_kwargs: visible)
    selected = []

    def select(_adapter, _view, kind, _point, *, entity, **_kwargs):
        assert kind == "SILHOUETTE"
        selected.append(entity)

    def dimension(*_args):
        label = next(name for name, eye in scene.contours.items() if eye is selected[-1])
        return SimpleNamespace(
            GetDimension2=lambda _index: SimpleNamespace(FullName=f"{label}@native-eye@anchor.SLDPRT"),
        )

    monkeypatch.setattr(drawing, "_select_view_entity", select)
    monkeypatch.setattr(scene.adapter.currentModel, "AddDiameterDimension2", dimension, raising=False)
    monkeypatch.setattr(scene.adapter.currentModel, "ClearSelection2", lambda _all: None, raising=False)
    monkeypatch.setattr(drawing, "supplier_reference_dimension", lambda _adapter, display, **_kwargs: display)
    monkeypatch.setattr(drawing, "curate_stock_dimensions", lambda *_args, **_kwargs: [])
    if fault is None:
        refs = drawing._supplier_references(scene.adapter, scene.views["FINISHED"])
        assert selected == [scene.contours["EyeOD"], scene.contours["EyeID"]]
        assert len(refs) == 2
        assert all(len(ref) == 2 and isinstance(ref[0], str) and isinstance(ref[1], dict) for ref in refs)
        assert {contract["label"]: contract["expected_mm"] for _key, contract in refs} == spec.SUPPLIER_EYE_MM
    else:
        missing_label = "EyeID" if fault in ("missing-id", "circle-gap") else "EyeOD"
        with pytest.raises(
            RuntimeError,
            match=f"{missing_label}: unchanged spring eye has no circular silhouette",
        ):
            drawing._supplier_references(scene.adapter, scene.views["FINISHED"])


def test_channel_creation_preserves_native_errors_without_rescanning(monkeypatch):
    scene = _settled_eye_scene(monkeypatch, drawing)
    eye = scene.contours["EyeOD"]
    error = OSError("original native eye disconnect")
    calls, queries = [], []

    def disconnected():
        calls.append("curve")
        raise error

    def entities(_view, kind, **_kwargs):
        queries.append(kind)
        return [eye, scene.contours["EyeID"]]

    eye.GetCurve = disconnected
    monkeypatch.setattr(drawing, "visible_view_entities", entities)
    with pytest.raises(OSError) as caught:
        drawing._supplier_references(scene.adapter, scene.views["FINISHED"])
    assert caught.value is error
    assert calls == ["curve"]
    assert queries == [4]


def _note_build_scene(monkeypatch, tmp_path, module):
    """Exercise real build/layout callbacks with native-shaped notes and views."""
    source_path = tmp_path / "note-source.SLDPRT"
    source_path.touch()
    monkeypatch.setattr(module, "SOURCE", source_path)
    monkeypatch.setattr(module, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(purchased_drawing, "_early_bound", lambda value, _kind: value)
    source = SimpleNamespace()
    state = SimpleNamespace(
        sheet="FINISHED", edit_sheet=True, keep_view_active=False, missing_creation=False,
        target_sheet="FINISHED", mutate_note=lambda _note: None, saved=False,
        sheet_scales={}, initial_scale=None, finalizer_options=None,
    )
    sheet = SimpleNamespace(
        GetProperties2=lambda: (
            0, 0, *state.sheet_scales.get(state.sheet, module.SHEET_SCALE),
            False, 0.4318, 0.2794,
        ),
        GetZoneMargin=lambda _side: 0.0127,
    )
    model = SimpleNamespace(
        ActivateSheet=lambda name: setattr(state, "sheet", name) or True,
        GetCurrentSheet=lambda: sheet, GetEditSheet=lambda: state.edit_sheet,
        ActiveDrawingView=None,
    )

    def activate_view(name):
        assert name == ""
        if not state.keep_view_active:
            model.ActiveDrawingView = None
        return False  # Normal native sheet-context return, not a failed transition.

    model.ActivateView = activate_view
    adapter = SimpleNamespace(currentModel=source, _attempt=lambda operation: operation())
    placements, linked_notes, property_reads, refreshed = [], {}, [], []

    def refresh(name):
        if state.saved:
            pytest.fail("post-save callback refreshed drawing geometry")
        refreshed.append(name)

    def view(name, configuration):
        native_view = SimpleNamespace(
            Name=name, ReferencedConfiguration=configuration,
            outline=(0.100, 0.110, 0.170, 0.240),
            GetFirstDisplayDimension6=lambda: None, GetAnnotations=lambda: (),
            UpdateViewDisplayGeometry=lambda: refresh(name),
        )
        native_view.GetOutline = lambda: native_view.outline
        return native_view

    front = view("finished-front", "Default")
    iso = view("finished-iso", "Default")
    stock = view("stock-front", module.SUPPLIER_STOCK_CONFIGURATION)
    stock_iso = view("stock-iso", module.SUPPLIER_STOCK_CONFIGURATION)
    stock_notes = _stock_note_contracts(module)
    stock_capture, capture_calls = (
        _supplier_stock_capture_scene(monkeypatch, adapter, source)
        if module is boss_drawing else (None, [])
    )

    async def open_model(_path):
        adapter.currentModel = source
        return {"success": True}

    def read_properties(native_source, names, *, required):
        assert native_source is source
        assert tuple(required) == tuple(names)
        properties = _source_properties(names)
        property_reads.append(properties)
        return properties

    def new_drawing(*_args, **kwargs):
        if module is boss_drawing:
            assert capture_calls == ["Default"]
        state.initial_scale = kwargs["scale"]
        adapter.currentModel = model
        return model, sheet

    def place_view(_adapter, _path, orientation, x, y, *, scale):
        placements.append((orientation, x, y, scale))
        native_view = (
            (front if orientation == "*Front" else iso)
            if state.sheet == "FINISHED"
            else (stock if orientation == "*Front" else stock_iso)
        )
        model.ActiveDrawingView = native_view
        return native_view

    def references(*_args):
        model.ActiveDrawingView = front
        return []

    def linked_note(_adapter, name, x, y, *, char_height):
        if state.missing_creation and name == "Supplier":
            return None
        note = _note_double(
            module.property_link(name), property_reads[0][name].replace("\n", "\r\n"), x, y,
            owner_type=0 if model.ActiveDrawingView is not None else 1,
        )
        note.position, note.char_height = (x, y), char_height
        linked_notes[name] = note
        if state.target_sheet == "FINISHED" and name == "Supplier":
            state.mutate_note(note)
        return note

    def supplier_stock(stock_adapter, *source_models):
        model.ActiveDrawingView = None
        if state.target_sheet == "SUPPLIER-STOCK" and stock_notes:
            state.mutate_note(stock_notes[0][0])
        if module is drawing:
            return stock, stock_iso, [], stock_notes
        assert stock_adapter is adapter
        assert len(source_models) == 2
        assert source_models[0] is source
        assert source_models[1] is stock_capture
        return stock, [], stock_notes

    async def finalize(_adapter, _outputs, *, settled_checks, checkpoint, **_kwargs):
        state.finalizer_options = _kwargs
        state.sheet_scales = dict(_kwargs["sheet_scales"])
        for verify in settled_checks:
            verify()
        checkpoint("before_drawing_save")
        state.saved = True
        checkpoint("after_drawing_save")
        checkpoint("after_pdf_save")
        return {"drawing": "saved"}

    adapter.open_model = open_model
    monkeypatch.setattr(module, "active_configuration_name", lambda *_args: "Default")
    for name in (
        "check", "create_blank_drawing_sheets", "stamp_drawing_summary",
        "set_hidden_lines_removed", "set_dimension_precision", "set_dimension_callouts",
        "_verify_controls", "_verify_supplier_references", "_verify_source_state",
    ):
        monkeypatch.setattr(module, name, lambda *_args, **_kwargs: None)
    snapshot = (object(),)
    monkeypatch.setattr(module, "_verify_supplier_references", lambda *_args, **_kwargs: snapshot)

    def capture_saved(native_adapter, refs_by_sheet, _view_contracts, prior):
        assert native_adapter is adapter
        assert state.saved
        assert prior is snapshot
        return {sheet_name: list(refs) for sheet_name, refs in refs_by_sheet.items()}

    monkeypatch.setattr(module, "_capture_saved_supplier_references", capture_saved)
    monkeypatch.setattr(module, "read_required_properties", read_properties)
    monkeypatch.setattr(module, "new_project_drawing", new_drawing)
    monkeypatch.setattr(module, "place_view", place_view)
    monkeypatch.setattr(module, "curate_view_dimensions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(module, "_supplier_references", references)
    monkeypatch.setattr(module, "add_property_linked_note", linked_note)
    monkeypatch.setattr(
        module, "_supplier_stock_sheet" if module is drawing else "_supplier_stock_diagram",
        supplier_stock,
    )
    monkeypatch.setattr(module, "iter_views", lambda _adapter:
                        (front, iso) if state.sheet == "FINISHED" else
                        (stock, stock_iso) if module is drawing else (stock,))
    monkeypatch.setattr(module, "view_name", lambda _adapter, native_view: native_view.Name)
    if module is boss_drawing:
        # These tests own labels/ownership, not the root native-profile oracle.
        def stock_bounds(stock_adapter, native_stock, source_model, capture):
            assert stock_adapter is adapter
            assert native_stock is stock
            assert source_model is source
            assert capture is stock_capture
            native_stock.UpdateViewDisplayGeometry()
            return native_stock.outline

        monkeypatch.setattr(module, "_supplier_stock_bounds", stock_bounds)
    monkeypatch.setattr(module, "finalize_drawing", finalize)
    return SimpleNamespace(
        adapter=adapter, state=state, model=model, source=source, sheet=sheet,
        front=front, iso=iso, stock=stock, stock_iso=stock_iso,
        placements=placements, notes=linked_notes, stock_notes=stock_notes,
        property_reads=property_reads, refreshed=refreshed,
    )


@pytest.mark.parametrize("module", (drawing, boss_drawing))
@pytest.mark.parametrize("operation", ("drawing_save", "pdf_save"))
def test_build_save_failure_keeps_primary_error_when_identity_observer_refuses(
    monkeypatch, tmp_path, module, operation,
):
    scene = _note_build_scene(monkeypatch, tmp_path, module)
    primary = OSError(f"original native {operation} failure")
    secondary = RuntimeError("original annotation identity capture refused")
    capture = module._capture_saved_supplier_references
    scene.state.failed_save = False

    def failing_capture(*args):
        if scene.state.failed_save:
            raise secondary
        return capture(*args)

    async def finalize(_adapter, _outputs, *, settled_checks, checkpoint, **_kwargs):
        for verify in settled_checks:
            verify()
        scene.state.saved = True
        if operation == "pdf_save":
            checkpoint("after_drawing_save")
        scene.state.failed_save = True
        # The production checkpoint emits after_* on failure and keeps the
        # actual SaveAs exception primary even when the read-only audit refuses.
        with drawing_common._drawing_checkpoint(checkpoint, operation):
            raise primary

    monkeypatch.setattr(module, "_capture_saved_supplier_references", failing_capture)
    monkeypatch.setattr(module, "finalize_drawing", finalize)
    with pytest.raises(OSError) as caught:
        asyncio.run(module.build(scene.adapter))
    assert caught.value is primary
    assert primary.__notes__ == [
        f"after_{operation} checkpoint also failed: RuntimeError: {secondary}",
    ]


@pytest.mark.parametrize("module", (drawing, boss_drawing))
def test_build_does_not_publish_identity_snapshot_after_failed_strict_presave_checks(
    monkeypatch, tmp_path, module,
):
    scene = _note_build_scene(monkeypatch, tmp_path, module)
    primary = RuntimeError("last strict supplier dimension lost its physical contour")
    observed_priors = []

    def strict_refusal(*_args):
        raise primary

    def inspect_unpublished(_adapter, _refs, _views, prior):
        observed_priors.append(prior)
        raise RuntimeError("no successfully verified original snapshot")

    async def finalize(_adapter, _outputs, *, settled_checks, checkpoint, **_kwargs):
        with pytest.raises(RuntimeError) as caught:
            for verify in settled_checks:
                verify()
        assert caught.value is primary
        with pytest.raises(RuntimeError, match="no successfully verified original snapshot"):
            checkpoint("after_drawing_save")
        raise primary

    monkeypatch.setattr(module, "_verify_supplier_references", strict_refusal)
    monkeypatch.setattr(module, "_capture_saved_supplier_references", inspect_unpublished)
    monkeypatch.setattr(module, "finalize_drawing", finalize)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(module.build(scene.adapter))
    assert caught.value is primary
    assert observed_priors == [None]


@pytest.mark.parametrize(
    "candidate",
    (
        "inside", "recorded-5", "recorded-5-at-4",
        "left-boundary", "bottom-boundary", "right-boundary", "top-boundary",
        "left", "bottom", "right", "top", "inverted", "nonfinite",
        "dimension-outside", "dimension-unreadable", "dimension-owner", "hidden-value",
    ),
)
def test_channel_stock_scale_creation_metadata_and_native_candidate_cell(
    monkeypatch, tmp_path, candidate,
):
    """4:1 needs its own native box; this fake candidate is not a fit prediction."""
    native_stock_builder = drawing._supplier_stock_sheet
    scene = _note_build_scene(monkeypatch, tmp_path, drawing)
    monkeypatch.setattr(drawing, "_supplier_stock_sheet", native_stock_builder)
    cell = (0.0127, 0.094, 0.4318 - 0.0127, 0.2794 - 0.0127 - 0.009)
    assert cell == pytest.approx((0.0127, 0.094, 0.4191, 0.2577), rel=0, abs=1e-15)
    recorded_5 = (
        0.11266199801221032, 0.08855998560357987,
        0.18733799988553204, 0.26046300056871236,
    )
    # Even the best translation cannot put 171.903 mm into this 163.7 mm cell.
    assert recorded_5[3] - recorded_5[1] > cell[3] - cell[1]
    assert (cell[1] - recorded_5[1], recorded_5[3] - cell[3]) == pytest.approx(
        (0.00544001439642013, 0.00276300056871236), rel=0, abs=1e-15,
    )
    assert (4, 1) in purchased_drawing._SCALES
    if candidate == "recorded-5":
        monkeypatch.setattr(drawing, "STOCK_SCALE", (5.0, 1.0))
    # Independent fake native readback, never a scaled version of recorded_5.
    outline = (0.120, 0.105, 0.180, 0.246)
    if candidate in ("recorded-5", "recorded-5-at-4"):
        outline = recorded_5
    elif candidate.removesuffix("-boundary") in ("left", "bottom", "right", "top"):
        index = ("left", "bottom", "right", "top").index(candidate.removesuffix("-boundary"))
        values = list(outline)
        values[index] = cell[index] + (
            0.0 if candidate.endswith("-boundary") else -1e-12 if index < 2 else 1e-12
        )
        outline = tuple(values)
    elif candidate == "inverted":
        outline = (0.180, 0.105, 0.120, 0.246)
    elif candidate == "nonfinite":
        outline = (0.120, 0.105, math.nan, 0.246)
    scene.stock.outline = outline
    scene.stock.Position = (0.150, 0.1755)
    scene.model.EditRebuild3 = lambda: True
    scene.adapter.swApp = SimpleNamespace(IsSame=lambda first, second: int(first is second))
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(
        drawing, "_show_hidden_owners",
        lambda *_args, **_kwargs: (drawing.SUPPLIER_STOCK_FEATURE,),
    )
    monkeypatch.setattr(
        drawing, "model_points_in_view", lambda *_args, **_kwargs: ((0.150, 0.1755),),
    )
    expected_anchors = {
        "SupplierStockShank": (0.105, 0.150),
        "SupplierStockThread": (0.210, 0.140),
        "SupplierStockOverall": (0.065, 0.1755),
    }
    expected_precision = {
        "SupplierStockShank": 2, "SupplierStockThread": 3, "SupplierStockOverall": 2,
    }
    expected_callouts = {
        "SupplierStockShank": "AS-SUPPLIED SHANK",
        "SupplierStockThread": "AS-SUPPLIED THREAD LENGTH",
        "SupplierStockOverall": "AS-SUPPLIED OVERALL",
    }
    dimensions, displays, annotations = {}, [], []
    for name, expected_mm in spec.SUPPLIER_STOCK_MM.items():
        native = SimpleNamespace(
            FullName=f"{name}@SupplierStockAxis@anchor.SLDPRT",
            SystemValue=expected_mm / 1000.0,
        )
        dimensions[name] = native
        annotation = SimpleNamespace(
            name=name, OwnerType=0, Owner=scene.stock, Visible=1, IsDangling=lambda: False,
        )
        display = SimpleNamespace(
            GetDimension2=lambda _index, native=native: native,
            GetAnnotation=lambda annotation=annotation: annotation,
            GetOverride=lambda: False, ShowDimensionValue=True,
        )
        annotation.GetSpecificAnnotation = lambda display=display: display
        annotations.append(annotation)
        displays.append(display)
    for index, display in enumerate(displays):
        following = displays[index + 1] if index + 1 < len(displays) else None
        display.GetNext5 = lambda following=following: following
    scene.stock.GetFirstDisplayDimension6 = lambda: displays[0]
    if candidate == "dimension-owner":
        annotations[0].Owner = scene.front
    elif candidate == "hidden-value":
        displays[0].ShowDimensionValue = False
    presented, created_notes, checked_cells = [], [], []

    def curate_stock(_adapter, view, *, keep, dimensions_by_feature, **_kwargs):
        assert view is scene.stock
        assert keep == expected_anchors
        assert dimensions_by_feature == {"SupplierStockAxis": set(expected_anchors)}
        return annotations

    def supplier_reference(_adapter, display, **contract):
        name = contract["label"]
        assert contract == {
            "label": name, "expected_mm": spec.SUPPLIER_STOCK_MM[name], "units": "in",
            "precision": expected_precision[name], "callout": expected_callouts[name],
        }
        assert display.GetDimension2(0).SystemValue == spec.SUPPLIER_STOCK_MM[name] / 1000.0
        presented.append(name)
        return display

    def annotation_ink(_adapter, annotation):
        x, y = expected_anchors[annotation.name]
        return {
            "texts": [{
                "t": f"({spec.SUPPLIER_STOCK_MM[annotation.name] / 25.4:g} in)",
                "pos": (x, y, 0.0), "h": 0.003,
                "w": 1.0 if candidate == "dimension-outside" else 0.022,
                "ang": 0.0, "ref": 2,
            }],
        }, {"refused": True} if candidate == "dimension-unreadable" else {}

    def add_stock_note(_adapter, text, x, y):
        note = _note_double(text, text, x, y)
        created_notes.append((note, text, text))
        return note

    def assert_fits(adapter, view, actual_cell, *, label):
        expected_cell = cell if scene.state.sheet == "SUPPLIER-STOCK" else (
            0.0127, 0.0651, 0.4191, 0.2667,
        )
        assert actual_cell == pytest.approx(expected_cell, rel=0, abs=1e-15)
        checked_cells.append(view.Name)
        purchased_drawing.assert_supplier_view_fits(adapter, view, actual_cell, label=label)

    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "curate_stock_dimensions", curate_stock)
    monkeypatch.setattr(drawing, "supplier_reference_dimension", supplier_reference)
    monkeypatch.setattr(drawing, "add_note", add_stock_note)
    monkeypatch.setattr(drawing, "assert_supplier_view_fits", assert_fits)
    monkeypatch.setattr(purchased_drawing, "annotation_display", annotation_ink)
    if candidate in ("inside", "left-boundary", "bottom-boundary", "right-boundary", "top-boundary"):
        assert asyncio.run(drawing.build(scene.adapter)) == {"drawing": "saved"}
        assert scene.state.saved
        assert checked_cells == ["finished-front", "finished-iso", "stock-front", "stock-iso"]
    else:
        message = (
            "invalid native extent" if candidate == "nonfinite" else
            "empty or inverted native extent" if candidate == "inverted" else
            "supplier dimension leaves its cell" if candidate == "dimension-outside" else
            "unreadable settled native dimension ink" if candidate == "dimension-unreadable" else
            "unsound supplier annotation owner/value" if candidate in ("dimension-owner", "hidden-value") else
            "settled supplier view leaves its cell"
        )
        with pytest.raises(RuntimeError, match=message):
            asyncio.run(drawing.build(scene.adapter))
        assert not scene.state.saved
    expected_stock_scale = (5.0, 1.0) if candidate == "recorded-5" else (4.0, 1.0)
    assert scene.placements == [
        ("*Front", 0.100, 0.18125, (5.0, 1.0)),
        ("*Isometric", 0.310, 0.212, (3.0, 1.0)),
        ("*Front", 0.150, 0.1755, expected_stock_scale),
        ("*Isometric", 0.310, 0.203, (3.0, 1.0)),
    ]
    assert scene.state.initial_scale == scene.state.finalizer_options["scale"] == (5.0, 1.0)
    assert scene.state.finalizer_options["sheet_scales"] == {
        "FINISHED": (5.0, 1.0), "SUPPLIER-STOCK": expected_stock_scale,
    }
    assert scene.model.ActivateSheet("SUPPLIER-STOCK") is True
    assert tuple(scene.sheet.GetProperties2()[2:4]) == expected_stock_scale
    assert scene.stock.Position == (0.150, 0.1755)
    assert scene.stock.ReferencedConfiguration == scene.stock_iso.ReferencedConfiguration == "AsSuppliedStock"
    assert set(presented) == set(expected_anchors)
    assert {name: native.SystemValue for name, native in dimensions.items()} == {
        name: value / 1000.0 for name, value in spec.SUPPLIER_STOCK_MM.items()
    }
    expected_notes = _stock_note_contracts(drawing)
    assert [(link, text) for _note, link, text in created_notes] == [
        (link, text) for _note, link, text in expected_notes
    ]
    for (note, _link, _text), (expected_note, _expected_link, _expected_text) in zip(
        created_notes, expected_notes,
    ):
        assert note.extent == pytest.approx(expected_note.extent, rel=0, abs=1e-15)
    assert created_notes[-1][1:] == ("ISOMETRIC VIEW SCALE 3:1", "ISOMETRIC VIEW SCALE 3:1")


@pytest.mark.parametrize(
    "shift_mm,fault",
    (
        (0, None), (9, None), (10, None),
        (10, "left-boundary"), (10, "bottom-boundary"),
        (10, "right-boundary"), (10, "top-boundary"),
        (10, "left"), (10, "bottom"), (10, "right"), (10, "top"),
        (10, "caption-text"), (10, "caption-owner"),
    ),
)
def test_stock_iso_creation_translates_native_box_and_caption_together(
    monkeypatch, tmp_path, shift_mm, fault,
):
    """Translate c12's actual box only; new native ink/readability remains pending."""
    native_stock_builder = drawing._supplier_stock_sheet
    scene = _note_build_scene(monkeypatch, tmp_path, drawing)
    monkeypatch.setattr(drawing, "_supplier_stock_sheet", native_stock_builder)
    old_center, old_caption = (0.310, 0.213), (0.275, 0.163)
    recorded_box = (
        0.2872237893868808, 0.15756259535002917,
        0.3327762106131192, 0.2673277812843747,
    )
    cell = (0.0127, 0.094, 0.4318 - 0.0127, 0.2794 - 0.0127 - 0.009)
    before_clearances = (
        recorded_box[0] - cell[0], recorded_box[1] - cell[1],
        cell[2] - recorded_box[2], cell[3] - recorded_box[3],
    )
    assert before_clearances == pytest.approx(
        (0.2745237893868808, 0.06356259535002917, 0.0863237893868808, -0.0096277812843747),
        rel=0, abs=1e-15,
    )
    assert math.ceil(-before_clearances[3] * 1000) == 10
    assert recorded_box[3] - 0.009 - cell[3] == pytest.approx(
        0.0006277812843747, rel=0, abs=1e-15,
    )
    if shift_mm != 10:
        shift = shift_mm / 1000.0
        monkeypatch.setattr(drawing, "STOCK_ISO_CENTER", (old_center[0], old_center[1] - shift))
        monkeypatch.setattr(drawing, "STOCK_ISO_CAPTION", (old_caption[0], old_caption[1] - shift))
    scene.stock.Position = (0.150, 0.1755)
    scene.model.EditRebuild3 = lambda: True
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(
        drawing, "_show_hidden_owners",
        lambda *_args, **_kwargs: (drawing.SUPPLIER_STOCK_FEATURE,),
    )
    monkeypatch.setattr(
        drawing, "model_points_in_view", lambda *_args, **_kwargs: ((0.150, 0.1755),),
    )
    monkeypatch.setattr(drawing, "curate_stock_dimensions", lambda *_args, **_kwargs: [])
    created_notes, fit_labels = [], []
    fixture_place_view = drawing.place_view

    def place_view(adapter, path, orientation, x, y, *, scale):
        view = fixture_place_view(adapter, path, orientation, x, y, scale=scale)
        if scene.state.sheet == "SUPPLIER-STOCK" and orientation == "*Isometric":
            assert scale == (3.0, 1.0)
            outline = [
                value + (x, y)[index % 2] - old_center[index % 2]
                for index, value in enumerate(recorded_box)
            ]
            edge = "" if fault is None else fault.removesuffix("-boundary")
            if edge in ("left", "bottom", "right", "top"):
                index = ("left", "bottom", "right", "top").index(edge)
                outline[index] = cell[index] + (
                    0.0 if fault.endswith("-boundary") else -1e-12 if index < 2 else 1e-12
                )
            view.outline = tuple(outline)
        return view

    def add_stock_note(_adapter, text, x, y):
        note = _note_double(text, text, x, y)
        note.position = (x, y)
        if text == "ISOMETRIC VIEW SCALE 3:1":
            if fault == "caption-text":
                note.text = "ISOMETRIC VIEW SCALE 4:1"
            elif fault == "caption-owner":
                note.annotation.OwnerType = 0
        created_notes.append(note)
        return note

    def assert_fits(adapter, view, actual_cell, *, label):
        assert f"view={view.Name!r}" in label
        assert f"configuration={view.ReferencedConfiguration!r}" in label
        assert f"cell={actual_cell!r}" in label
        fit_labels.append(label)
        purchased_drawing.assert_supplier_view_fits(adapter, view, actual_cell, label=label)

    monkeypatch.setattr(drawing, "place_view", place_view)
    monkeypatch.setattr(drawing, "add_note", add_stock_note)
    monkeypatch.setattr(drawing, "assert_supplier_view_fits", assert_fits)
    accepted = shift_mm == 10 and (fault is None or fault.endswith("-boundary"))
    if accepted:
        assert asyncio.run(drawing.build(scene.adapter)) == {"drawing": "saved"}
        assert scene.state.saved
        assert len(fit_labels) == 4
    else:
        caption_failure = fault in ("caption-text", "caption-owner")
        with pytest.raises(
            RuntimeError,
            match="source label changed" if caption_failure else "settled supplier view leaves its cell",
        ) as failure:
            asyncio.run(drawing.build(scene.adapter))
        assert not scene.state.saved
        if not caption_failure:
            message = str(failure.value)
            assert "view='stock-iso'" in message
            assert "configuration='AsSuppliedStock'" in message
            assert f"cell={cell!r}" in message
            assert repr(scene.stock_iso.outline) in message
    expected_y = 0.203 if shift_mm == 10 else old_center[1] - shift_mm / 1000.0
    expected_caption_y = 0.153 if shift_mm == 10 else old_caption[1] - shift_mm / 1000.0
    assert scene.placements == [
        ("*Front", 0.100, 0.18125, (5.0, 1.0)),
        ("*Isometric", 0.310, 0.212, (3.0, 1.0)),
        ("*Front", 0.150, 0.1755, (4.0, 1.0)),
        ("*Isometric", 0.310, expected_y, (3.0, 1.0)),
    ]
    caption = created_notes[-1]
    assert caption.position == (0.275, expected_caption_y)
    assert (caption.position[0] - 0.310, caption.position[1] - expected_y) == pytest.approx(
        (-0.035, -0.050), rel=0, abs=1e-15,
    )
    assert caption.PropertyLinkedText == "ISOMETRIC VIEW SCALE 3:1"
    assert scene.notes["Isometric View Note"].position == (0.275, 0.163)
    assert scene.notes["Isometric View Note"].GetText() == "ISOMETRIC VIEW SCALE 3:1"
    assert scene.stock.ReferencedConfiguration == scene.stock_iso.ReferencedConfiguration == "AsSuppliedStock"
    assert scene.state.finalizer_options["sheet_scales"] == {
        "FINISHED": (5.0, 1.0), "SUPPLIER-STOCK": (4.0, 1.0),
    }
    if shift_mm == 10 and fault is None:
        box = scene.stock_iso.outline
        assert (box[0] - cell[0], box[1] - cell[1], cell[2] - box[2], cell[3] - box[3]) == pytest.approx(
            (0.2745237893868808, 0.05356259535002917, 0.0863237893868808, 0.0003722187156253),
            rel=0, abs=1e-15,
        )
        assert caption.GetText() == "ISOMETRIC VIEW SCALE 3:1"
        assert caption.annotation.OwnerType == 1


@pytest.mark.parametrize("module", (drawing, boss_drawing))
def test_finished_source_notes_keep_links_resolved_text_and_sheet_ownership(
    monkeypatch, tmp_path, module,
):
    scene = _note_build_scene(monkeypatch, tmp_path, module)
    assert asyncio.run(module.build(scene.adapter)) == {"drawing": "saved"}
    assert len(scene.property_reads) == 1
    assert set(scene.notes) == {
        "Supplier", "Supplier SKUs", "Stock Name", "Isometric View Note", "Manufacturing Notes",
    }
    expected_positions = {
        "Supplier": ((0.016, 0.060), 0.003),
        "Supplier SKUs": ((0.080, 0.060), 0.003),
        "Stock Name": ((0.016, 0.049), 0.003),
        "Isometric View Note": ((0.275, 0.163), None),
        "Manufacturing Notes": ((0.016, 0.083 if module is drawing else 0.076), 0.003),
    }
    for name, note in scene.notes.items():
        assert note.annotation.OwnerType == 1
        assert note.PropertyLinkedText == module.property_link(name)
        assert note.GetText().replace("\r\n", "\n") == scene.property_reads[0][name]
        assert (note.position, note.char_height) == expected_positions[name]
    # These are legal sheet labels below the unchanged 65.1 mm geometry cell.
    assert scene.notes["Supplier"].extent[1] < 0.0651
    assert scene.placements == [
        ("*Front", *module.FRONT_CENTER, module.SHEET_SCALE),
        (
            "*Isometric",
            *(module.FINISHED_ISO_CENTER if module is drawing else module.ISO_CENTER),
            module.ISO_SCALE,
        ),
    ]
    assert scene.state.sheet == "FINISHED"
    assert scene.state.saved
    assert len(scene.refreshed) == (4 if module is drawing else 3)


@pytest.mark.parametrize("module", (drawing, boss_drawing))
@pytest.mark.parametrize("fault", ("edit-template", "active-view", "missing-note"))
def test_finished_note_creation_requires_checked_sheet_context_and_a_note(
    monkeypatch, tmp_path, module, fault,
):
    scene = _note_build_scene(monkeypatch, tmp_path, module)
    scene.state.edit_sheet = fault != "edit-template"
    scene.state.keep_view_active = fault == "active-view"
    scene.state.missing_creation = fault == "missing-note"
    with pytest.raises(RuntimeError):
        asyncio.run(module.build(scene.adapter))
    assert not scene.notes
    assert not scene.state.saved


@pytest.mark.parametrize("module", (drawing, boss_drawing))
@pytest.mark.parametrize("sheet_name", ("FINISHED", "SUPPLIER-STOCK"))
@pytest.mark.parametrize(
    "fault",
    (
        "view-owner", "template-owner", "missing-annotation", "wrong-link", "wrong-resolved",
        "left", "bottom", "right", "top", "short-extent", "nan-extent", "inverted-extent",
    ),
)
def test_build_refuses_sheet_note_ownership_text_and_actual_border_drift(
    monkeypatch, tmp_path, module, sheet_name, fault,
):
    scene = _note_build_scene(monkeypatch, tmp_path, module)
    scene.state.target_sheet = sheet_name

    def mutate(note):
        if fault in ("view-owner", "template-owner"):
            note.annotation.OwnerType = 0 if fault == "view-owner" else 2
        elif fault == "missing-annotation":
            note.annotation = None
        elif fault == "wrong-link":
            note.PropertyLinkedText = '$PRPSHEET:"Foreign Property"'
        elif fault == "wrong-resolved":
            note.text += " CHANGED"
        elif fault == "short-extent":
            note.extent = note.extent[:-1]
        else:
            extent = list(note.extent)
            if fault == "nan-extent":
                extent[0] = math.nan
            elif fault == "inverted-extent":
                extent[3] = extent[0]
            else:
                index, boundary, direction = {
                    "left": (0, 0.0127, -1),
                    "bottom": (1, 0.0127, -1),
                    "right": (3, 0.4191, 1),
                    "top": (4, 0.2667, 1),
                }[fault]
                extent[index] = boundary + direction * 1e-12
            note.extent = tuple(extent)

    scene.state.mutate_note = mutate
    with pytest.raises(RuntimeError):
        asyncio.run(module.build(scene.adapter))
    assert not scene.state.saved


@pytest.mark.parametrize("module", (drawing, boss_drawing))
@pytest.mark.parametrize("fault", ("literal-instead-of-link", "unresolved-property"))
def test_finished_notes_require_both_live_links_and_authoritative_resolved_text(
    monkeypatch, tmp_path, module, fault,
):
    scene = _note_build_scene(monkeypatch, tmp_path, module)

    def mutate(note):
        if fault == "literal-instead-of-link":
            note.PropertyLinkedText = note.text
        else:
            note.text = note.PropertyLinkedText

    scene.state.mutate_note = mutate
    with pytest.raises(RuntimeError):
        asyncio.run(module.build(scene.adapter))
    assert not scene.state.saved


@pytest.mark.parametrize("module", (drawing, boss_drawing))
@pytest.mark.parametrize("fault", ("missing-contract", "null-note"))
def test_stock_note_mapping_retains_every_literal_contract(monkeypatch, tmp_path, module, fault):
    scene = _note_build_scene(monkeypatch, tmp_path, module)
    if fault == "missing-contract":
        scene.stock_notes.pop()
    else:
        _note, link, text = scene.stock_notes[0]
        scene.stock_notes[0] = (None, link, text)
    with pytest.raises(RuntimeError):
        asyncio.run(module.build(scene.adapter))
    assert not scene.state.saved


@pytest.mark.parametrize("module", (drawing, boss_drawing))
def test_sheet_owned_note_still_in_native_view_inventory_is_not_waived(
    monkeypatch, tmp_path, module,
):
    scene = _note_build_scene(monkeypatch, tmp_path, module)
    scene.front.GetAnnotations = lambda: (scene.notes["Supplier"].annotation,)
    with pytest.raises(RuntimeError, match="supplier note leaves its cell"):
        asyncio.run(module.build(scene.adapter))
    assert scene.notes["Supplier"].annotation.OwnerType == 1
    assert not scene.state.saved


@pytest.mark.parametrize("fault", (None, "edit-template", "active-view", "missing-note"))
def test_channel_stock_builder_returns_sheet_owned_literal_triples(monkeypatch, fault):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    sheet = SimpleNamespace(
        GetProperties2=lambda: (0, 0, 5.0, 1.0, False, 0.4318, 0.2794),
        GetZoneMargin=lambda _side: 0.0127,
    )
    stock = SimpleNamespace(Position=drawing.STOCK_CENTER, UpdateViewDisplayGeometry=lambda: None)
    iso = SimpleNamespace()
    model = SimpleNamespace(
        ActiveDrawingView=stock, GetEditSheet=lambda: fault != "edit-template",
        GetCurrentSheet=lambda: sheet, EditRebuild3=lambda: True,
    )

    def activate_view(name):
        assert name == ""
        if fault != "active-view":
            model.ActiveDrawingView = None
        return False

    model.ActivateView = activate_view
    adapter = SimpleNamespace(currentModel=model, _attempt=lambda operation: operation())
    placements, created = [], []

    def place_view(_adapter, _path, orientation, x, y, *, scale):
        placements.append((orientation, x, y, scale))
        return stock if orientation == "*Front" else iso

    def add_note(_adapter, text, x, y):
        if fault == "missing-note":
            return None
        note = _note_double(text, text, x, y, owner_type=0 if model.ActiveDrawingView else 1)
        created.append(note)
        return note

    monkeypatch.setattr(drawing, "place_view", place_view)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing, "_show_hidden_owners", lambda *_args, **_kwargs:
                        (drawing.SUPPLIER_STOCK_FEATURE,))
    monkeypatch.setattr(drawing, "model_points_in_view", lambda *_args, **_kwargs:
                        (drawing.STOCK_CENTER,))
    monkeypatch.setattr(drawing, "curate_stock_dimensions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(drawing, "add_note", add_note)
    if fault is not None:
        with pytest.raises(RuntimeError):
            drawing._supplier_stock_sheet(adapter)
        assert not created
        return
    actual_stock, actual_iso, refs, notes = drawing._supplier_stock_sheet(adapter)
    assert (actual_stock, actual_iso, refs) == (stock, iso, [])
    assert [note for note, _link, _text in notes] == created
    expected = _stock_note_contracts(drawing)
    assert [(link, text) for _note, link, text in notes] == [
        (link, text) for _note, link, text in expected
    ]
    assert all(note.annotation.OwnerType == 1 for note in created)
    for (note, _link, _text), (expected_note, _expected_link, _expected_text) in zip(notes, expected):
        assert note.extent == pytest.approx(expected_note.extent)
    assert placements == [
        ("*Front", *drawing.STOCK_CENTER, drawing.STOCK_SCALE),
        ("*Isometric", *drawing.STOCK_ISO_CENTER, drawing.ISO_SCALE),
    ]
    assert drawing.STOCK_ISO_CENTER == (0.310, 0.203)
    assert placements[1] == ("*Isometric", 0.310, 0.203, (3.0, 1.0))
    assert stock.ReferencedConfiguration == iso.ReferencedConfiguration == drawing.SUPPLIER_STOCK_CONFIGURATION


@pytest.mark.parametrize("module", (drawing, boss_drawing))
@pytest.mark.parametrize("sheet_name", ("FINISHED", "SUPPLIER-STOCK"))
def test_note_ownership_failure_is_reported_before_a_native_view_cell_failure(
    monkeypatch, tmp_path, module, sheet_name,
):
    scene = _note_build_scene(monkeypatch, tmp_path, module)
    scene.state.target_sheet = sheet_name
    scene.state.mutate_note = lambda note: setattr(note.annotation, "OwnerType", 0)
    native_view = scene.front if sheet_name == "FINISHED" else scene.stock
    native_view.GetOutline = lambda: (0.100, 0.010, 0.170, 0.240)
    with pytest.raises(RuntimeError, match="actual owner=0"):
        asyncio.run(module.build(scene.adapter))
    assert not scene.state.saved


@pytest.mark.parametrize("module", (drawing, boss_drawing))
@pytest.mark.parametrize("newline", ("\n", "\r\n", "\r"), ids=("authored-lf", "native-crlf", "bare-cr-drift"))
def test_finished_note_line_endings_preserve_authored_lf_without_accepting_bare_cr(
    monkeypatch, tmp_path, module, newline,
):
    scene = _note_build_scene(monkeypatch, tmp_path, module)
    create_note = module.add_property_linked_note

    def linked_note(adapter, name, x, y, *, char_height):
        note = create_note(adapter, name, x, y, char_height=char_height)
        if name == "Manufacturing Notes":
            authored = scene.property_reads[0][name]
            assert "\n" in authored and "\r" not in authored
            note.text = authored.replace("\n", newline)
        return note

    monkeypatch.setattr(module, "add_property_linked_note", linked_note)
    if newline == "\r":
        with pytest.raises(RuntimeError, match="changed or leaves the usable sheet"):
            asyncio.run(module.build(scene.adapter))
        assert not scene.state.saved
    else:
        assert asyncio.run(module.build(scene.adapter)) == {"drawing": "saved"}
        assert scene.state.saved
    note = scene.notes["Manufacturing Notes"]
    assert note.PropertyLinkedText == module.property_link("Manufacturing Notes")
    assert note.GetText() == scene.property_reads[0]["Manufacturing Notes"].replace("\n", newline)
