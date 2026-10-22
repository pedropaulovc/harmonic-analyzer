"""Offline manufacturing boundaries for the trimmed channel-spring anchor."""

import asyncio
import json
import math
from types import SimpleNamespace

import pytest

import _config
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


def _settled_eye_scene(monkeypatch, module):
    """Model fresh post-rebuild attachments, without retaining any native handle."""
    monkeypatch.setattr(module, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(module, "assert_supplier_reference_dimension", lambda *_args, **_kwargs: None)
    state = SimpleNamespace(sheet="FINISHED")
    model = SimpleNamespace(ActivateSheet=lambda name: setattr(state, "sheet", name) or True)
    owner = object()
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
    views, refs_by_sheet, contracts, annotations, contours = {}, {}, {}, {}, {}
    diameters = spec.SUPPLIER_EYE_MM if module is drawing else {"EyeID": module.SUPPLIER_EYE_ID_MM}

    def contour(diameter, attached_face=face):
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
            UpdateViewDisplayGeometry=lambda: pytest.fail("geometry-read-only verifier refreshed a view"),
            GetFirstDisplayDimension6=lambda displays=displays: displays[0],
        )
        views[sheet], refs_by_sheet[sheet] = view, refs
        contracts[sheet] = ((view.Name,), configuration)
    monkeypatch.setattr(module, "iter_views", lambda _adapter: (views[state.sheet],))
    monkeypatch.setattr(module, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(
        module, "visible_view_entities",
        lambda *_args, **_kwargs: pytest.fail("settled proof must not rescan visible contours"),
    )
    return SimpleNamespace(
        adapter=adapter, refs=refs_by_sheet, contracts=contracts, contours=contours,
        annotations=annotations, views=views, source=source, owner=owner,
        face=face, surface=surface, contour=contour, diameters=diameters, state=state,
    )


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
        scene.face.GetFeature = lambda: object()
        monkeypatch.setattr(module, "visible_view_entities", lambda *_args, **_kwargs: (eye,))
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
            module._supplier_eye_circle(scene.adapter, scene.views["FINISHED"], eye)
        return
    result = module._supplier_eye_circle(scene.adapter, scene.views["FINISHED"], eye)
    if fault is None:
        assert result == curve.CircleParams
    else:
        assert result is None


@pytest.mark.parametrize(
    "module,label", ((drawing, "EyeOD"), (drawing, "EyeID"), (boss_drawing, "EyeID")),
)
@pytest.mark.parametrize(
    "fault", (None, "outer", "foreign-visible", "missing", "extra", "wrong-type",
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
        scene.face.GetFeature = lambda: object()
        monkeypatch.setattr(module, "visible_view_entities", lambda *_args, **_kwargs: tuple(scene.contours.values()))
    elif fault == "missing":
        annotation.entities = []
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
    for name in ("read_required_properties", "create_blank_drawing_sheets", "stamp_drawing_summary",
                 "set_dimension_precision", "set_dimension_callouts", "add_property_linked_note",
                 "set_hidden_lines_removed", "_verify_supplier_layout", "_verify_source_state"):
        monkeypatch.setattr(module, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "curate_view_dimensions", lambda *_args, **_kwargs: imported_controls)
    monkeypatch.setattr(module, "place_view", lambda _adapter, _path, orientation, *_args, **_kwargs:
                        front if orientation == "*Front" else iso)
    def supplier_references(*_args):
        if drift == "lost-imported-control":
            imported_controls.pop()
        elif drift == "changed-imported-control":
            imported_controls[0].dimension.SystemValue += 0.001
        return scene.refs["FINISHED"]

    monkeypatch.setattr(module, "_supplier_references", supplier_references)
    if module is drawing:
        monkeypatch.setattr(module, "_supplier_stock_sheet", lambda *_args:
                            (stock, stock_iso, scene.refs["SUPPLIER-STOCK"], []))
        monkeypatch.setattr(module, "iter_views", lambda _adapter:
                            (front, iso) if scene.state.sheet == "FINISHED" else (stock, stock_iso))
    else:
        monkeypatch.setattr(module, "_supplier_stock_diagram", lambda *_args:
                            (stock, scene.refs["SUPPLIER-STOCK"], []))
        monkeypatch.setattr(module, "iter_views", lambda _adapter:
                            (front, iso) if scene.state.sheet == "FINISHED" else (stock,))
    saved = []

    async def finalize(_adapter, _outputs, *, settled_checks, checkpoint, **_kwargs):
        for verify in settled_checks:
            verify()
        checkpoint("before_drawing_save")
        saved.append("native-save")
        if drift == "foreign-feature":
            scene.face.GetFeature = lambda: object()
        elif drift == "wrong-torus":
            values = list(scene.surface.TorusParams)
            values[6] += 0.001
            scene.surface.TorusParams = tuple(values)
        elif drift == "wrong-circle":
            values = list(scene.contours["EyeID"].GetCurve().CircleParams)
            values[6] += 0.001
            scene.contours["EyeID"].GetCurve().CircleParams = tuple(values)
        checkpoint("after_drawing_save")
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
    result = module._supplier_eye_circle(scene.adapter, scene.views["FINISHED"], eye)
    if module is drawing:
        assert result == eye.GetCurve().CircleParams
    else:
        assert result is None


@pytest.mark.parametrize("fault", (None, "foreign-visible", "wrong-eye-torus", "missing-id"))
def test_channel_creation_uses_source_proof_and_returns_only_data(monkeypatch, fault):
    scene = _settled_eye_scene(monkeypatch, drawing)
    visible = list(scene.contours.values())
    if fault == "foreign-visible":
        scene.face.GetFeature = lambda: object()
    elif fault == "wrong-eye-torus":
        values = list(scene.surface.TorusParams)
        values[6] += 0.001
        scene.surface.TorusParams = tuple(values)
    elif fault == "missing-id":
        visible = [scene.contours["EyeOD"]]
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
        with pytest.raises(RuntimeError) as caught:
            drawing._supplier_references(scene.adapter, scene.views["FINISHED"])
        packet = json.loads(caught.value.__notes__[0])
        assert packet["requested_label"] == ("EyeID" if fault == "missing-id" else "EyeOD")
        if fault == "missing-id":
            assert packet["raw_origin_xy_od_circle_count"] == 1
            assert packet["raw_origin_xy_id_circle_count"] == 0
            assert packet["kind4"][0]["od_diameter_matches_observation_only"] is True
            assert packet["kind4"][0]["id_diameter_matches"] is False


def _channel_missing_eye_census(monkeypatch, scene, visible):
    queries, selected = [], []

    def entities(_view, kind, **_kwargs):
        queries.append(kind)
        return visible if kind == 4 else []

    monkeypatch.setattr(drawing, "visible_view_entities", entities)
    monkeypatch.setattr(
        drawing, "_select_view_entity",
        lambda *_args, **_kwargs: selected.append("selected"),
    )
    with pytest.raises(RuntimeError) as caught:
        drawing._supplier_references(scene.adapter, scene.views["FINISHED"])
    assert type(caught.value) is RuntimeError
    assert str(caught.value) == "EyeOD: unchanged spring eye has no circular silhouette"
    assert len(caught.value.__notes__) == 1
    packet = json.loads(caught.value.__notes__[0])
    assert packet["observation_only"] is True
    assert packet["requested_label"] == "EyeOD"
    assert queries == [4, 1]
    assert selected == []
    json.dumps(packet, allow_nan=False)
    return packet


@pytest.mark.parametrize("fault", ("raw-empty", "foreign-owner", "source-path", "torus-major"))
def test_channel_census_distinguishes_raw_inventory_and_strict_rejection(monkeypatch, fault):
    scene = _settled_eye_scene(monkeypatch, drawing)
    visible = [scene.contours["EyeOD"], scene.contours["EyeID"]]
    if fault == "raw-empty":
        visible = []
    elif fault == "foreign-owner":
        foreign = object()
        scene.face.GetFeature = lambda: foreign
    elif fault == "source-path":
        scene.source.GetPathName = lambda: str(drawing.SOURCE.parent / "foreign.SLDPRT")
    else:
        values = list(scene.surface.TorusParams)
        values[6] += 0.001
        scene.surface.TorusParams = tuple(values)
    packet = _channel_missing_eye_census(monkeypatch, scene, visible)
    assert packet["raw_exact_circle_count"] == len(visible)
    assert packet["accepted_od_count"] == 0
    assert packet["accepted_id_count"] == 0
    assert len(packet["kind4"]) == len(visible)
    assert len(packet["predicate_time"]) == len(visible)
    if visible:
        expected = {
            "foreign-owner": "owner_same_as_expected",
            "source-path": "source_lexical_path_matches",
            "torus-major": "torus_major_matches",
        }[fault]
        assert {row["first_rejection"] for row in packet["predicate_time"]} == {expected}
        assert packet["raw_origin_xy_od_circle_count"] == 1
        assert packet["raw_origin_xy_id_circle_count"] == 1


def test_channel_census_retains_original_false_before_later_true_readback(monkeypatch):
    scene = _settled_eye_scene(monkeypatch, drawing)
    calls = []
    foreign = object()

    def owner():
        calls.append("owner")
        return foreign if len(calls) == 1 else scene.owner

    scene.face.GetFeature = owner
    packet = _channel_missing_eye_census(
        monkeypatch, scene, [scene.contours["EyeOD"], scene.contours["EyeID"]],
    )
    first = packet["predicate_time"][0]
    assert first["first_rejection"] == "owner_same_as_expected"
    assert first["owner_same_as_expected"] == 0
    assert first["surface_present"] == "unobserved"
    assert packet["kind4"][0]["face"]["owner_same_as_expected"] == 1
    assert packet["accepted_od_count"] == 1


def test_channel_native_predicate_exception_is_not_replaced_by_census(monkeypatch):
    scene = _settled_eye_scene(monkeypatch, drawing)
    eye = scene.contours["EyeOD"]
    curve = eye.GetCurve()
    error = OSError("original native eye disconnect")
    calls, queries = [], []

    def disconnected_once():
        calls.append("curve")
        if len(calls) == 1:
            raise error
        return curve

    def entities(_view, kind, **_kwargs):
        queries.append(kind)
        return [eye, scene.contours["EyeID"]] if kind == 4 else []

    eye.GetCurve = disconnected_once
    monkeypatch.setattr(drawing, "visible_view_entities", entities)
    with pytest.raises(OSError) as caught:
        drawing._supplier_references(scene.adapter, scene.views["FINISHED"])
    assert caught.value is error
    assert str(error) == "original native eye disconnect"
    packet = json.loads(error.__notes__[0])
    assert packet["predicate_time"][0]["stage"] == "GetCurve"
    assert packet["predicate_time"][0]["error"]["message"] == str(error)
    assert packet["raw_exact_circle_count"] == 2
    assert queries == [4, 1]


def test_channel_complete_readback_keeps_inclusive_origin_boundary(monkeypatch):
    scene = _settled_eye_scene(monkeypatch, drawing)
    eye = scene.contours["EyeOD"]
    curve = eye.GetCurve()
    values = list(curve.CircleParams)
    values[0] = 1e-8
    curve.CircleParams = tuple(values)
    scene.source.GetPathName = lambda: str(drawing.SOURCE.parent / "foreign.SLDPRT")
    packet = _channel_missing_eye_census(monkeypatch, scene, [eye])
    assert packet["predicate_time"][0]["circle_center_matches"] is True
    assert packet["kind4"][0]["circle_center_matches"] is True
