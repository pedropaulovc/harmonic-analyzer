"""Offline manufacturing boundaries for the trimmed channel-spring anchor."""

import asyncio
import importlib
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


def test_supplier_reference_set_matches_only_source_dimensioned_unchanged_geometry():
    assert spec.SUPPLIER_EYE_MM == {
        "EyeOD": anchor.eye_od_mm,
        "EyeID": anchor.eye_id_mm,
    }
    assert spec.SUPPLIER_EYE_MM["EyeOD"] == pytest.approx(0.5 * 25.4)
    assert spec.SUPPLIER_EYE_MM["EyeID"] == pytest.approx(0.25 * 25.4)
    assert spec.SUPPLIER_REFERENCE_PRECISION == {
        "EyeOD": 1,
        "EyeID": 2,
        "SupplierStockShank": 2,
        "SupplierStockThread": 3,
        "SupplierStockOverall": 2,
    }
    assert spec.SUPPLIER_THREAD == "#6-32"
    assert spec.SUPPLIER_THREAD_MAJOR_MM == anchor.thread_major_dia_mm
    # The supplier does not separately dimension wire. All three original
    # stock lengths end at the removed factory end, not the finished cut end.
    assert set(spec.SUPPLIER_EYE_MM) == {"EyeOD", "EyeID"}
    assert set(drawing.EXPECTED_CONTROLS) == {
        "FinishedOverall",
        "ChamferWidth",
        "ChamferAngle",
    }


def test_original_stock_axis_reproduces_all_three_source_lengths():
    crown, shank_start, thread_start, end = spec.SUPPLIER_STOCK_AXIS_MM
    assert math.dist(crown, end) == pytest.approx(1.25 * 25.4)
    assert math.dist(shank_start, end) == pytest.approx(0.75 * 25.4)
    assert math.dist(thread_start, end) == pytest.approx(0.625 * 25.4)
    assert spec.SUPPLIER_STOCK_MM == {
        "SupplierStockShank": anchor.shank_length_mm,
        "SupplierStockThread": anchor.thread_length_mm,
        "SupplierStockOverall": anchor.overall_length_mm,
    }
    assert spec.SUPPLIER_STOCK_DIMENSIONS == {
        spec.SUPPLIER_STOCK_FEATURE: set(spec.SUPPLIER_STOCK_MM)
    }
    assert spec.SUPPLIER_STOCK_MM[
        "SupplierStockShank"
    ] - spec.SHANK_LENGTH_MM == pytest.approx(0.45)
    assert spec.SUPPLIER_STOCK_MM[
        "SupplierStockOverall"
    ] - spec.FINISHED_OVERALL_MM == pytest.approx(0.45)


@pytest.mark.parametrize(
    "count,configuration",
    [
        (4, spec.SUPPLIER_STOCK_CONFIGURATION),
        (5, "Default"),
    ],
)
def test_settled_supplier_gate_rejects_lost_refs_or_wrong_stock_configuration(
    count, configuration
):
    with pytest.raises(RuntimeError):
        drawing._verify_supplier_references(
            None,
            [None] * count,
            [SimpleNamespace(ReferencedConfiguration=configuration)],
        )


@pytest.mark.parametrize("module_name", ["draw_vn_boss_hook", "draw_vn_spring_hook"])
def test_finished_front_import_cannot_visit_supplier_stock_features(
    monkeypatch, module_name
):
    """Exercise the actual curation dispatcher from each full drawing entry point."""
    import _drawing_dimension_import as imports

    module = importlib.import_module(module_name)
    draw = SimpleNamespace(ActivateSheet=lambda _name: True)
    adapter = SimpleNamespace(currentModel=draw)
    imported = []

    async def open_model(_path):
        return True

    adapter.open_model = open_model
    monkeypatch.setattr(module, "SOURCE", SimpleNamespace(is_file=lambda: True))
    monkeypatch.setattr(module, "check", lambda _label, result: result)
    monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        module, "new_project_drawing", lambda *_args, **_kwargs: (draw, object())
    )
    for name in (
        "read_required_properties",
        "create_blank_drawing_sheets",
        "stamp_drawing_summary",
        "set_hidden_lines_removed",
        "set_dimension_precision",
        "set_dimension_callouts",
    ):
        monkeypatch.setattr(module, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "place_view", lambda *_args, **_kwargs: object())

    def import_features(_adapter, _view, features):
        imported.extend(features)
        return [
            (name, SimpleNamespace(name=name))
            for feature in features
            for name in module.DRAWING_DIMENSIONS[feature]
        ]

    def refuse_entire_model(*_args, **_kwargs):
        raise AssertionError("finished view imported supplier-stock marked dimensions")

    monkeypatch.setattr(imports, "insert_feature_dimensions", import_features)
    monkeypatch.setattr(imports, "_curate_entire_model_import", refuse_entire_model)
    monkeypatch.setattr(
        imports, "curate_dimensions", lambda _adapter, rows, **_kwargs: rows
    )
    monkeypatch.setattr(imports, "dimension_name", lambda _adapter, row: row.name)
    monkeypatch.setattr(
        imports, "_reposition_rerun_reason", lambda *_args, **_kwargs: "none"
    )
    observed = []

    class ReachedSupplierReferences(Exception):
        pass

    def controls(_adapter, annotations):
        observed.extend(annotation.name for annotation in annotations)

    def finish_at_supplier_refs(*_args):
        raise ReachedSupplierReferences()

    monkeypatch.setattr(module, "_verify_controls", controls)
    monkeypatch.setattr(module, "_supplier_references", finish_at_supplier_refs)
    with pytest.raises(ReachedSupplierReferences):
        asyncio.run(module.build(adapter))
    assert set(imported) == set(module.DRAWING_DIMENSIONS)
    assert module.SUPPLIER_STOCK_FEATURE not in imported
    assert set(observed) == set(module.FRONT_KEEP)


@pytest.mark.parametrize("module_name", ["draw_vn_boss_hook", "draw_vn_spring_hook"])
@pytest.mark.parametrize(
    "fault",
    [
        None,
        "dimension_top",
        "title_268",
        "title_278",
        "unreadable_ink",
        "view_owned_title",
        "missing_view",
    ],
)
def test_settled_supplier_ink_uses_real_sheet_height_and_inner_border(
    monkeypatch, module_name, fault
):
    import _drawing_layout_audit as collector
    import _purchased_fastener_drawing as purchased

    module = importlib.import_module(module_name)
    native_ink = {
        "texts": [
            {
                "t": "(11/16 in) SOURCE REF",
                "pos": [0.100, 0.245, 0.0],
                "h": 0.003,
                "w": 0.060,
            }
        ],
    }
    if fault == "dimension_top":
        native_ink["texts"][0]["pos"][1] = 0.268
    annotation = object()
    display = SimpleNamespace(
        GetDimension2=lambda _index: SimpleNamespace(
            FullName="SourceDim@SupplierProfile@Hook"
        ),
        GetAnnotation=lambda: annotation,
        GetNext5=lambda: None,
    )

    class View:
        Name = "FreshSupplierView"
        updates = 0

        def UpdateViewDisplayGeometry(self):
            self.updates += 1
            # VT_VOID: a successful update returns None, not a Boolean.
            return None

        def GetOutline(self):
            return (0.100, 0.105, 0.220, 0.250)

        def GetFirstDisplayDimension6(self):
            return display

        def GetAnnotations(self):
            return ()

    fresh_view = View()
    sheet = SimpleNamespace(
        GetProperties2=lambda: (2, 2, 1.0, 1.0, False, 0.4318, 0.2794, False),
        GetZoneMargin=lambda _side: 0.0127,
    )
    draw = SimpleNamespace(
        ActivateSheet=lambda _name: True,
        GetCurrentSheet=lambda: sheet,
    )
    adapter = SimpleNamespace(currentModel=draw, _attempt=lambda call: call())
    monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(purchased, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        module,
        "iter_views",
        lambda _adapter: iter(() if fault == "missing_view" else (fresh_view,)),
    )
    monkeypatch.setattr(module, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(
        collector,
        "annotation_display",
        lambda *_args: (
            native_ink,
            ["unreadable text"] if fault == "unreadable_ink" else [],
        ),
    )
    title_top = {"title_268": 0.268, "title_278": 0.278}.get(fault, 0.263)
    note = SimpleNamespace(
        GetAnnotation=lambda: SimpleNamespace(
            OwnerType=0 if fault == "view_owned_title" else 1
        ),
        GetExtent=lambda: (0.016, title_top - 0.003, 0.0, 0.200, title_top, 0.0),
    )
    name = "FreshSupplierView"
    names = name if module_name == "draw_vn_boss_hook" else (name,)
    if fault is None:
        module._verify_supplier_layout(
            adapter, {module.SHEET_NAMES[1]: names}, [(note, "source title")]
        )
        assert fresh_view.updates == 1
    else:
        with pytest.raises(RuntimeError):
            module._verify_supplier_layout(
                adapter, {module.SHEET_NAMES[1]: names}, [(note, "source title")]
            )


@pytest.mark.parametrize("module_name", ["build_vn_boss_hook", "build_vn_spring_hook"])
@pytest.mark.parametrize(
    "fault", [None, "selection", "wrong_type", "wrong_span", "missing_dimension"]
)
def test_source_spans_select_native_endpoints_and_refuse_wrong_measurements(
    monkeypatch, module_name, fault
):
    module = importlib.import_module(module_name)
    selected, clears, recorded = [], [], []
    expected = (
        module.SUPPLIER_STOCK_OVERALL_MM
        if module_name == "build_vn_boss_hook"
        else module.SUPPLIER_STOCK_MM["SupplierStockOverall"]
    )
    dimension = SimpleNamespace(
        DrivenState=2,
        SystemValue=(expected + (1.0 if fault == "wrong_span" else 0.0)) / 1000.0,
    )
    display = SimpleNamespace(
        Type2=1 if fault == "wrong_type" else 12,
        GetDimension2=lambda _index: dimension,
    )

    def insert(_x, _y, _z, dimension_type, _error):
        assert dimension_type == 12
        assert selected == ["Axis.start", "Axis.end"]
        return (None if fault == "missing_dimension" else display), 0

    model = SimpleNamespace(
        ClearSelection2=lambda _all: clears.append("clear"),
        Extension=SimpleNamespace(AddSpecificDimension=insert),
    )
    adapter = SimpleNamespace(currentModel=model)

    def resolve(_adapter, ref):
        def select(append, data):
            assert append is True and data is None
            selected.append(ref)
            return fault != "selection"

        return SimpleNamespace(Select4=select)

    monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(module, "_resolve_entity_ref", resolve)
    dims = SimpleNamespace(record=recorded.append)

    def measure():
        if module_name == "build_vn_boss_hook":
            module._stock_overall_reference(adapter, "Axis.start", "Axis.end", dims)
        else:
            module._stock_span(
                adapter,
                "Axis.start",
                "Axis.end",
                expected,
                "SupplierStockOverall",
                dims,
            )

    if fault is None:
        measure()
        assert recorded == ["SupplierStockOverall"]
    else:
        with pytest.raises(RuntimeError):
            measure()
        assert recorded == []
    assert clears == ["clear", "clear"]


def test_spring_stock_requires_the_material_inherited_after_the_before_save_split(
    monkeypatch,
):
    from test_vn_boss_hook_drawing import _hook_configuration_fixture

    part, callback, adapter, model = _hook_configuration_fixture(
        monkeypatch, "build_vn_spring_hook"
    )
    original_read = model.GetMaterialPropertyName2

    def missing_stock_material(name):
        if name == part.SUPPLIER_STOCK_CONFIGURATION:
            return "", "test-materials.sldmat"
        return original_read(name)

    model.GetMaterialPropertyName2 = missing_stock_material
    with pytest.raises(RuntimeError, match="do not carry"):
        asyncio.run(callback(adapter))
    assert model.active == "Default"
