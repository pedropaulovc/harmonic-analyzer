"""Offline manufacturing boundaries for the trimmed channel-spring anchor."""

import ast
import inspect
import math
from types import SimpleNamespace

import pytest

import _config
import _drawing_attachment
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


def _settled_eye_scene(monkeypatch):
    """Old silhouette handles are deliberately unusable after a view rebuild."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(_drawing_attachment, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "assert_supplier_reference_dimension", lambda *_args, **_kwargs: None)
    state = SimpleNamespace(sheet="FINISHED")
    model = SimpleNamespace(ActivateSheet=lambda name: setattr(state, "sheet", name) or True)
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )

    def contour(diameter, face):
        curve = SimpleNamespace(
            IsCircle=lambda: True,
            CircleParams=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, diameter / 2000.0),
        )
        return SimpleNamespace(
            GetCurve=lambda: curve, GetFace=lambda: face,
            GetView=lambda: views["FINISHED"],
        )

    contours = {
        name: contour(diameter, object()) for name, diameter in spec.SUPPLIER_EYE_MM.items()
    }
    # Exact positive readbacks from native diagnostic 2942dd065, worker log L42.
    for name, circle in {
        "EyeOD": (-2.102257677834285e-10, -7.358970724458125e-11, 0.0,
                  0.0, 0.0, 1.0, 0.006350000187332174),
        "EyeID": (-2.102257677834285e-10, -7.358970724458125e-11, 0.0,
                  0.0, 0.0, -1.0, 0.003175000187332174),
    }.items():
        contours[name].GetCurve().CircleParams = circle
    annotations = {}
    views = {}
    refs_by_sheet = {}
    contracts = {}
    for sheet, names, configuration in (
        ("FINISHED", ("EyeOD", "EyeID", "SupplierThreadMajor"), "Default"),
        ("SUPPLIER-STOCK", ("SupplierStockThread", "SupplierStockShank", "SupplierStockOverall"), spec.SUPPLIER_STOCK_CONFIGURATION),
    ):
        displays = []
        refs = []
        for name in names:
            feature = (
                "native-eye" if name in contours else
                spec.SUPPLIER_THREAD_FEATURE if name == "SupplierThreadMajor" else
                spec.SUPPLIER_STOCK_FEATURE
            )
            key = f"{name}@{feature}@anchor.SLDPRT"
            native = SimpleNamespace(FullName=key, Tolerance=SimpleNamespace(Type=0), DrivenState=1)
            annotation = SimpleNamespace(
                entities=[contours[name]] if name in contours else [],
                kinds=[46] if name in contours else [],
            )
            annotation.GetAttachedEntities3 = lambda annotation=annotation: tuple(annotation.entities)
            annotation.GetAttachedEntityTypes = lambda annotation=annotation: tuple(annotation.kinds)
            annotation.GetAttachedEntityCount3 = lambda annotation=annotation: len(annotation.entities)
            annotation.IsDangling = lambda: False
            annotations[name] = annotation
            display = SimpleNamespace(
                GetDimension2=lambda _index, native=native: native,
                GetAnnotation=lambda annotation=annotation: annotation,
            )
            displays.append(display)
            stale = SimpleNamespace(
                GetCurve=lambda: pytest.fail("dereferenced a pre-rebuild silhouette"),
                GetFace=lambda: None,
            ) if name in contours else None
            refs.append((key, {"label": name, "expected_mm": spec.SUPPLIER_EYE_MM.get(name, 1.0)}, stale))
        if sheet == "FINISHED":
            for name in drawing.FRONT_KEEP:
                native = SimpleNamespace(FullName=f"{name}@control@anchor.SLDPRT")
                displays.append(SimpleNamespace(GetDimension2=lambda _index, native=native: native))
        for index, display in enumerate(displays):
            following = displays[index + 1] if index + 1 < len(displays) else None
            display.GetNext5 = lambda following=following: following
        view = SimpleNamespace(
            Name=f"{sheet}-front", ReferencedConfiguration=configuration,
            UpdateViewDisplayGeometry=lambda: pytest.fail("geometry-read-only verifier refreshed a view"),
            GetFirstDisplayDimension6=lambda displays=displays: displays[0],
        )
        views[sheet] = view
        refs_by_sheet[sheet] = refs
        contracts[sheet] = ((view.Name,), configuration)
    monkeypatch.setattr(drawing, "iter_views", lambda _adapter: (views[state.sheet],))
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    visible = list(contours.values())
    monkeypatch.setattr(drawing, "visible_view_entities", lambda _view, kind, **_kwargs: visible if kind == 4 else ())
    return adapter, refs_by_sheet, contracts, contours, annotations, views, visible, contour


@pytest.mark.parametrize("label", ("EyeOD", "EyeID"))
@pytest.mark.parametrize(
    "fault",
    (None, "duplicate-visible", "outer", "same-face-wrong-circle", "foreign-face", "missing",
     "extra", "wrong-type", "missing-visible", "wrong-center", "wrong-normal", "wrong-radius",
     "wrong-configuration", "wrong-view", "dangling", "count-mismatch"),
)
def test_settled_eye_reacquires_exact_physical_contour_and_refuses_drift(monkeypatch, label, fault):
    adapter, refs, contracts, contours, annotations, views, visible, contour = _settled_eye_scene(monkeypatch)
    annotation = annotations[label]
    original = contours[label]
    other = "EyeOD" if label == "EyeID" else "EyeID"
    if fault == "outer":
        annotation.entities = [contours[other]]
    elif fault == "same-face-wrong-circle":
        annotation.entities = [contour(spec.SUPPLIER_EYE_MM[other], original.GetFace())]
    elif fault == "foreign-face":
        annotation.entities = [contour(spec.SUPPLIER_EYE_MM[label], object())]
    elif fault == "missing":
        annotation.entities = []
    elif fault == "extra":
        annotation.entities.append(original)
    elif fault == "wrong-type":
        annotation.kinds = [1]
    elif fault == "missing-visible":
        visible.remove(original)
    elif fault == "duplicate-visible":
        # Actual native CH enumeration contains two identical ID-circle readbacks.
        visible.append(contour(spec.SUPPLIER_EYE_MM[label], original.GetFace()))
    elif fault in ("wrong-center", "wrong-normal"):
        values = list(original.GetCurve().CircleParams)
        values[0 if fault == "wrong-center" else 5] += 2e-8
        original.GetCurve().CircleParams = tuple(values)
    elif fault == "wrong-configuration":
        views["FINISHED"].ReferencedConfiguration = spec.SUPPLIER_STOCK_CONFIGURATION
    elif fault == "wrong-radius":
        values = list(original.GetCurve().CircleParams)
        values[6] += 2e-8
        original.GetCurve().CircleParams = tuple(values)
    elif fault == "wrong-view":
        original.GetView = lambda: SimpleNamespace(Name="another-view")
    elif fault == "dangling":
        annotation.IsDangling = lambda: True
    elif fault == "count-mismatch":
        annotation.GetAttachedEntityCount3 = lambda: 2
    if fault in (None, "duplicate-visible"):
        drawing._verify_supplier_references(adapter, refs, contracts)
    else:
        with pytest.raises(RuntimeError):
            drawing._verify_supplier_references(adapter, refs, contracts)


@pytest.mark.parametrize("module", (drawing, boss_drawing))
def test_native_save_observer_checks_only_native_save_and_preserves_failures(module):
    """Exercise the actual nested callback without constructing a COM adapter."""
    build = ast.parse(inspect.getsource(module.build)).body[0]
    callback = next(
        node for node in build.body
        if isinstance(node, ast.FunctionDef) and node.name == "verify_after_native_save"
    )
    calls = []
    namespace = {
        "adapter": object(), "refs_by_sheet": object(), "view_contracts": object(),
        "SHEET_NAMES": module.SHEET_NAMES,
        "drawing": SimpleNamespace(ActivateSheet=lambda name: calls.append(("sheet", name)) or True),
        "_verify_supplier_references": lambda *args: calls.append(("verify", args)),
    }
    exec(compile(ast.Module(body=[callback], type_ignores=[]), "<native-save-observer>", "exec"), namespace)
    observer = namespace[callback.name]
    for event in ("before_drawing_save", "before_pdf_save", "after_pdf_save", "after_drawing_close"):
        observer(event)
    assert calls == []
    observer("after_drawing_save")
    assert calls == [
        ("verify", (namespace["adapter"], namespace["refs_by_sheet"], namespace["view_contracts"])),
        ("sheet", module.SHEET_NAMES[0]),
    ]

    def refuse(*_args):
        raise RuntimeError("saved attachment changed")

    namespace["_verify_supplier_references"] = refuse
    with pytest.raises(RuntimeError, match="saved attachment changed"):
        observer("after_drawing_save")
