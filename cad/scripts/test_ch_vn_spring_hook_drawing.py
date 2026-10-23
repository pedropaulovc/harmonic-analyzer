"""Offline manufacturing boundaries for the trimmed channel-spring anchor."""

import asyncio
import math
from types import SimpleNamespace

import pytest

import _config
import _purchased_fastener_drawing as purchased_drawing
import _stock_trim_drawing as trim_drawing
import draw_ch_vn_spring_hook as drawing
import draw_sm_vn_boss_hook as boss_drawing
import ch_vn_spring_hook_spec as spec
import spring_mount_geom as mounts
import sm_summing_lever_spec as lever
from _hole_spec import TAP_DRILL_MM
from stock_anchor_geom import ANCHOR_9489T111 as anchor
import ch_anchor_jam_nut_spec as jam_nut
from _interference_contracts import CHANNEL_ANCHOR_NUT_THREAD
from _hole_spec import THREAD_MAJOR_MM


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
            ("ISOMETRIC VIEW SCALE 3:1", 0.275, 0.163),
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
    "placement,fault",
    (
        ("old", None),
        ("previous-whole-mm", None),
        ("current", None),
        ("current", "left"),
        ("current", "bottom"),
        ("current", "right"),
        ("current", "top"),
        ("current", "missing"),
    ),
)
def test_finished_front_creation_fits_recorded_a269_native_cell(
    monkeypatch, tmp_path, placement, fault,
):
    """Replay native-box translation, not a new-leaf or printed-edge proof."""
    old_center = (0.100, 0.18625)
    recorded_outline = (
        0.06266199906333915, 0.10143093577628477,
        0.13733800093666088, 0.2710690642237152,
    )
    finished_cell = (0.0127, 0.0651, 0.4191, 0.2667)
    overflow = recorded_outline[3] - finished_cell[3]
    whole_mm_shift = math.ceil(overflow * 1000) / 1000
    assert whole_mm_shift <= recorded_outline[1] - finished_cell[1]
    if placement != "current":
        shift = 0.0 if placement == "old" else whole_mm_shift - 0.001
        monkeypatch.setattr(drawing, "FRONT_CENTER", (old_center[0], old_center[1] - shift))

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
        view = SimpleNamespace(Name=name, outline=outline)
        view.UpdateViewDisplayGeometry = lambda: refreshed.append(name)
        view.GetOutline = lambda: view.outline
        view.GetFirstDisplayDimension6 = lambda: None
        view.GetAnnotations = lambda: ()
        return view

    def place_view(_adapter, _path, orientation, x, y, *, scale):
        placements.append((orientation, x, y, scale))
        if orientation == "*Front":
            ratio = scale[0] / scale[1] / 5.0
            outline = tuple(
                (x, y)[index % 2]
                + (value - old_center[index % 2]) * ratio
                for index, value in enumerate(recorded_outline)
            )
            if fault in ("left", "bottom", "right", "top"):
                index = ("left", "bottom", "right", "top").index(fault)
                values = list(outline)
                values[index] = finished_cell[index] + (-1e-12 if index < 2 else 1e-12)
                outline = tuple(values)
            view = make_view("finished-front", outline)
        else:
            view = make_view("finished-iso", (0.280, 0.180, 0.340, 0.240))
        views[orientation] = view
        model.ActiveDrawingView = view
        return view

    stock = make_view("stock-front", (0.110, 0.110, 0.190, 0.240))
    stock_iso = make_view("stock-iso", (0.280, 0.180, 0.340, 0.240))

    def iter_views(_adapter):
        if state.sheet == "FINISHED":
            return (
                (views["*Isometric"],) if fault == "missing"
                else (views["*Front"], views["*Isometric"])
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

    if placement != "current" or fault is not None:
        message = "view disappeared" if fault == "missing" else "view leaves its cell"
        with pytest.raises(RuntimeError, match=message):
            asyncio.run(drawing.build(adapter))
        return

    assert asyncio.run(drawing.build(adapter)) == {"layout": "contained"}
    orientation, x, y, scale = placements[0]
    assert orientation == "*Front"
    assert (x, y) == pytest.approx(
        (old_center[0], old_center[1] - whole_mm_shift), rel=0, abs=1e-15,
    )
    assert scale == (5.0, 1.0)
    assert placements[1] == ("*Isometric", 0.310, 0.213, (3.0, 1.0))
    assert views["*Front"].outline == pytest.approx(
        (
            recorded_outline[0], 0.09643093577628477,
            recorded_outline[2], 0.2660690642237152,
        )
    )
    assert [name for name, _cell in checked_cells] == [
        "finished-front", "finished-iso", "stock-front", "stock-iso",
    ]


def _settled_eye_scene(monkeypatch, module):
    """Model fresh post-rebuild attachments, without retaining any native handle."""
    monkeypatch.setattr(module, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(module, "assert_supplier_reference_dimension", lambda *_args, **_kwargs: None)
    state = SimpleNamespace(sheet="FINISHED")
    model = SimpleNamespace(
        ActivateSheet=lambda name: setattr(state, "sheet", name) or True,
        ActiveDrawingView=None, GetEditSheet=lambda: True,
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
            )
            annotation.GetAttachedEntities3 = lambda annotation=annotation: tuple(annotation.entities)
            annotation.GetAttachedEntityTypes = lambda annotation=annotation: tuple(annotation.kinds)
            annotation.GetAttachedEntityCount3 = lambda annotation=annotation: len(annotation.entities)
            annotations[name] = annotation
            displays.append(SimpleNamespace(
                GetDimension2=lambda _index, native=native: native,
                GetAnnotation=lambda annotation=annotation: annotation,
            ))
            refs.append((key, {"label": name, "expected_mm": diameters.get(name, 1.0)}))
        if sheet == "FINISHED":
            for name in module.FRONT_KEEP:
                native = SimpleNamespace(FullName=f"{name}@control@anchor.SLDPRT")
                displays.append(SimpleNamespace(GetDimension2=lambda _index, native=native: native))
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
    )


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
              "lost-imported-control", "changed-imported-control"),
)
def test_build_retains_controls_and_refuses_native_save_physical_drift(monkeypatch, tmp_path, module, drift):
    """Execute the real build and its supplied finalizer callbacks, not extracted AST."""
    source_path = tmp_path / "anchor.SLDPRT"
    source_path.touch()
    monkeypatch.setattr(module, "SOURCE", source_path)
    scene = _settled_eye_scene(monkeypatch, module)
    source = scene.source
    front, stock = scene.views["FINISHED"], scene.views["SUPPLIER-STOCK"]
    iso = SimpleNamespace(Name="finished-iso", ReferencedConfiguration="Default")
    stock_iso = SimpleNamespace(Name="stock-iso", ReferencedConfiguration=module.SUPPLIER_STOCK_CONFIGURATION)
    model = scene.adapter.currentModel
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
        monkeypatch.setattr(module, "_supplier_stock_diagram", lambda *_args:
                            (stock, scene.refs["SUPPLIER-STOCK"], _stock_note_contracts(module)))
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
        checkpoint("after_pdf_save")
        assert len(scene.mapping_calls) == observations_after_save
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
    )
    sheet = SimpleNamespace(
        GetProperties2=lambda: (0, 0, 5.0, 1.0, False, 0.4318, 0.2794),
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
        return SimpleNamespace(
            Name=name, ReferencedConfiguration=configuration,
            GetOutline=lambda: (0.100, 0.110, 0.170, 0.240),
            GetFirstDisplayDimension6=lambda: None, GetAnnotations=lambda: (),
            UpdateViewDisplayGeometry=lambda: refresh(name),
        )

    front = view("finished-front", "Default")
    iso = view("finished-iso", "Default")
    stock = view("stock-front", module.SUPPLIER_STOCK_CONFIGURATION)
    stock_iso = view("stock-iso", module.SUPPLIER_STOCK_CONFIGURATION)
    stock_notes = _stock_note_contracts(module)

    async def open_model(_path):
        adapter.currentModel = source
        return {"success": True}

    def read_properties(native_source, names, *, required):
        assert native_source is source
        assert tuple(required) == tuple(names)
        properties = _source_properties(names)
        property_reads.append(properties)
        return properties

    def new_drawing(*_args, **_kwargs):
        adapter.currentModel = model
        return model, sheet

    def place_view(_adapter, _path, orientation, x, y, *, scale):
        placements.append((orientation, x, y, scale))
        native_view = front if orientation == "*Front" else iso
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

    def supplier_stock(*_args):
        model.ActiveDrawingView = None
        if state.target_sheet == "SUPPLIER-STOCK" and stock_notes:
            state.mutate_note(stock_notes[0][0])
        if module is drawing:
            return stock, stock_iso, [], stock_notes
        return stock, [], stock_notes

    async def finalize(_adapter, _outputs, *, settled_checks, checkpoint, **_kwargs):
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
    monkeypatch.setattr(module, "finalize_drawing", finalize)
    return SimpleNamespace(
        adapter=adapter, state=state, model=model, front=front, stock=stock,
        placements=placements, notes=linked_notes, stock_notes=stock_notes,
        property_reads=property_reads, refreshed=refreshed,
    )


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
        ("*Isometric", *module.ISO_CENTER, module.ISO_SCALE),
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
        ("*Isometric", *drawing.ISO_CENTER, drawing.ISO_SCALE),
    ]
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
