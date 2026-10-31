"""Offline manufacturing boundaries for the modified purchased anchor."""

import asyncio
import contextlib
import math
from types import SimpleNamespace

import pytest

from _printed_tolerance import printed_band_mm
import _stock_trim_drawing as trim_drawing
import _telemetry
import build_sm_vn_boss_hook as part
import sm_vn_boss_hook_spec as spec
import draw_sm_vn_boss_hook as drawing
from _hole_spec import TAP_DRILL_MM
from stock_anchor_geom import ANCHOR_9490T1 as anchor


def test_finished_overall_preserves_factory_thread_datum():
    cut_end = anchor.eye_od_mm / 2 - spec.FINISHED_OVERALL_MM
    assert cut_end == pytest.approx(spec.TRIM.shank_end_y_mm)
    # The full 19.05 boss plus the jam nut's thread above it (#1189).
    assert spec.TRIM.shank_length_mm == pytest.approx(22.886)
    assert spec.TRIM.shank_length_mm - 19.05 >= spec.JAM_NUT_THREAD_MM - 1e-3
    assert spec.FINISHED_OVERALL_MM == pytest.approx(40.4755)


def test_deburr_band_clears_receiver_and_retains_full_threads():
    # The lead-in is a two-place inch chamfer under the printed .XX title-block
    # band, never a tighter one; the governing stack below must hold across it.
    band = printed_band_mm(2, unit="in")
    assert spec.CHAMFER_WIDTH_DEVIATIONS == pytest.approx((-band, band))
    assert spec.DIMENSION_PRECISION["ChamferWidth"] == 2
    assert spec.CHAMFER_WIDTH_MM / 25.4 == pytest.approx(
        round(spec.CHAMFER_WIDTH_MM / 25.4, 2)
    )
    assert spec.DIMENSION_TOLERANCE_TYPES["ChamferWidth"] == 11  # swTolGeneral
    minimum = spec.CHAMFER_WIDTH_MM + spec.CHAMFER_WIDTH_DEVIATIONS[0]
    maximum = spec.CHAMFER_WIDTH_MM + spec.CHAMFER_WIDTH_DEVIATIONS[1]
    assert anchor.thread_major_dia_mm - 2 * minimum < TAP_DRILL_MM[anchor.thread_size]
    # The next two-place nominal down would put the short leg's end over the drill.
    assert (
        anchor.thread_major_dia_mm - 2 * (minimum - 0.254)
        >= TAP_DRILL_MM[anchor.thread_size]
    )
    # The long leg still leaves an end flat: the deburr cannot reach the axis.
    assert anchor.thread_major_radius_mm - maximum > 0.2
    # Include the adverse angular corner, not only the nominal 45-degree leg.
    maximum_axial = maximum / math.tan(
        math.radians(spec.CHAMFER_ANGLE_DEG - spec.CHAMFER_ANGLE_TOLERANCE_DEG)
    )
    short_shank = spec.SHANK_LENGTH_MM + spec.FINISHED_OVERALL_DEVIATIONS[0]
    assert short_shank - maximum_axial > 17.0


def test_finished_overall_prints_its_model_inside_the_xx_band():
    lower, upper = spec.FINISHED_OVERALL_DEVIATIONS
    assert spec.DIMENSION_PRECISION["FinishedOverall"] == 2
    assert lower < 0.0 < upper
    assert upper - lower == pytest.approx(2 * printed_band_mm(2, unit="in"))


@pytest.mark.parametrize("fault", [None, "rejected", "faults"])
def test_lead_in_drives_the_restored_deburr_to_the_spec_nominal(monkeypatch, fault):
    """The shared trim restores the factory leg; the anchor drives its own."""
    calls = []
    spans = []

    @contextlib.asynccontextmanager
    async def aspan(name, **_attributes):
        spans.append(name)
        try:
            yield None
        finally:
            spans.append(f"/{name}")

    monkeypatch.setattr(_telemetry, "aspan", aspan)

    class Dimension:
        def SetSystemValue3(self, value, which, names):
            calls.append(("set", value, which, list(spans)))
            return 2 if fault == "rejected" else 0

    async def rebuild(_adapter):
        calls.append(("rebuild", list(spans)))

    monkeypatch.setattr(
        part,
        "_named_dimension",
        lambda _adapter, feature, name: (
            (None, Dimension())
            if (feature, name) == ("StockDeburrProfile", "ChamferWidth")
            else None
        ),
    )
    monkeypatch.setattr(part, "force_rebuild", rebuild)
    monkeypatch.setattr(
        part,
        "_hard_faults",
        lambda _adapter, _model: ["StockDeburr"] if fault == "faults" else [],
    )
    adapter = SimpleNamespace(currentModel=object())
    if fault is None:
        asyncio.run(part._size_lead_in(adapter))
        inside = ["stock.shank.lead_in"]
        assert calls == [
            ("set", spec.CHAMFER_WIDTH_MM / 1000, 2, inside),
            ("rebuild", inside),
        ]
    else:
        with pytest.raises(RuntimeError):
            asyncio.run(part._size_lead_in(adapter))
    # One operation span, closed on success and on refusal alike.
    assert spans == ["stock.shank.lead_in", "/stock.shank.lead_in"]


@pytest.mark.parametrize(
    "fault", [None, "reference", "nominal", "tolerance", "precision", "missing"]
)
def test_drawing_accepts_general_controls_and_rejects_lost_control(monkeypatch, fault):
    """General is toleranced, unlike None; neither replaces a real driving size."""
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    annotations = []
    for name, nominal, (lower, upper) in (
        (
            "FinishedOverall",
            spec.FINISHED_OVERALL_MM / 1000,
            tuple(d / 1000 for d in spec.FINISHED_OVERALL_DEVIATIONS),
        ),
        (
            "ChamferWidth",
            spec.CHAMFER_WIDTH_MM / 1000,
            tuple(d / 1000 for d in spec.CHAMFER_WIDTH_DEVIATIONS),
        ),
        (
            "ChamferAngle",
            math.radians(spec.CHAMFER_ANGLE_DEG),
            (
                -math.radians(spec.CHAMFER_ANGLE_TOLERANCE_DEG),
                math.radians(spec.CHAMFER_ANGLE_TOLERANCE_DEG),
            ),
        ),
    ):
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
    elif fault == "tolerance":
        # swTolNONE must remain invalid; a no-tolerance spec is a regression.
        annotations[0].dimension.Tolerance.Type = 0
    elif fault == "precision":
        annotations[0].display.GetPrimaryPrecision2 = lambda: (
            spec.DIMENSION_PRECISION["FinishedOverall"] + 1
        )
    elif fault == "missing":
        annotations.pop()
    if fault is None:
        drawing._verify_controls(annotations)
    else:
        with pytest.raises(RuntimeError):
            drawing._verify_controls(annotations)


THREAD_KEY = f"SupplierThreadMajor@{spec.SUPPLIER_THREAD_FEATURE}@sm-vn-boss-hook.Part"


def _settled_sheet(monkeypatch, *, thread_key=THREAD_KEY, tolerance_type=0):
    """The finished front/iso views and their settled native dimensions."""
    keys = [f"{name}@Profile@sm-vn-boss-hook.Part" for name in drawing.FRONT_KEEP]
    keys.append(thread_key)
    displays = []
    for key in keys:
        dimension = SimpleNamespace(
            FullName=key, Tolerance=SimpleNamespace(Type=tolerance_type)
        )
        displays.append(SimpleNamespace(GetDimension2=lambda _index, d=dimension: d))
    for display, following in zip(displays, [*displays[1:], None]):
        display.GetNext5 = lambda following=following: following
    front = SimpleNamespace(
        name="Drawing View1", ReferencedConfiguration="Default",
        UpdateViewDisplayGeometry=lambda: None,
        GetFirstDisplayDimension6=lambda: displays[0],
    )
    iso = SimpleNamespace(
        name="Drawing View2", ReferencedConfiguration="Default",
        UpdateViewDisplayGeometry=lambda: None,
    )
    views = [front, iso]
    asserted = []
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "iter_views", lambda _adapter: list(views))
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(
        drawing, "assert_supplier_reference_dimension",
        lambda _adapter, display, **contract: asserted.append((display, contract)),
    )
    contract = {"label": "SupplierThreadMajor"}
    refs = [(thread_key, contract)]
    return SimpleNamespace(
        views=views, displays=displays, refs=refs, asserted=asserted,
        names=(front.name, iso.name),
    )


@pytest.mark.parametrize(
    "fault",
    [
        None, "no_reference", "configuration", "lost_view", "extra_dimension",
        "duplicate", "attachment", "tolerance", "presentation",
    ],
)
def test_settled_thread_reference_is_the_one_native_supplier_dimension(monkeypatch, fault):
    """The kept #10-24 carrier stays native, untoleranced and on its sketch."""
    case = _settled_sheet(
        monkeypatch,
        thread_key=(
            "SupplierThreadMajor@SupplierNominalStockProfile@sm-vn-boss-hook.Part"
            if fault == "attachment" else THREAD_KEY
        ),
        tolerance_type=1 if fault == "tolerance" else 0,
    )
    if fault == "no_reference":
        case.refs.clear()
    elif fault == "configuration":
        case.views[1].ReferencedConfiguration = spec.SUPPLIER_STOCK_CONFIGURATION
    elif fault == "lost_view":
        case.views.pop()
    elif fault == "extra_dimension":
        stray = SimpleNamespace(
            GetDimension2=lambda _index: SimpleNamespace(
                FullName="EyeID@Drawing View1", Tolerance=SimpleNamespace(Type=0)
            ),
            GetNext5=lambda: None,
        )
        case.displays[-1].GetNext5 = lambda: stray
    elif fault == "duplicate":
        case.displays[-1].GetNext5 = lambda: case.displays[0]
    elif fault == "presentation":
        def refuse(_adapter, _display, **_contract):
            raise RuntimeError("native supplier presentation differs")
        monkeypatch.setattr(drawing, "assert_supplier_reference_dimension", refuse)
    arguments = (object(), case.refs, case.names, "Default")
    if fault is None:
        drawing._verify_supplier_references(*arguments)
        assert case.asserted == [(case.displays[-1], case.refs[0][1])]
    else:
        with pytest.raises(RuntimeError):
            drawing._verify_supplier_references(*arguments)


def _footer_note(owner, extent):
    annotation = SimpleNamespace(OwnerType=owner)
    return SimpleNamespace(GetAnnotation=lambda: annotation, GetExtent=lambda: extent)


@pytest.mark.parametrize(
    "fault", [None, "lost_view", "outside", "view_owned_note", "note_off_sheet"]
)
def test_settled_layout_checks_view_ink_cell_and_sheet_owned_footer(monkeypatch, fault):
    """Views/dimensions stay above the footer; footer notes are the sheet's."""
    case = _settled_sheet(monkeypatch)
    region = SimpleNamespace(xmin=0.01, ymin=0.01, xmax=0.41, ymax=0.287)
    sheet = SimpleNamespace(GetProperties2=lambda: (0, 0, 1, 1, 0, 0.42, 0.297))
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetCurrentSheet=lambda: sheet)
    )
    monkeypatch.setattr(drawing, "sheet_drawable_region", lambda *_a, **_k: region)
    checked = []

    def fits(_adapter, view, cell, *, label):
        if fault == "outside" and view is case.views[1]:
            raise RuntimeError(f"{label}: settled supplier view leaves its cell")
        checked.append((view.name, cell))

    monkeypatch.setattr(drawing, "assert_supplier_view_fits", fits)
    # The native r1 Supplier extent: below the view-ink cell, inside the border.
    supplier = (0.01574, 0.05630, 0.0, 0.04481, 0.06011, 0.0)
    notes = [
        ("Supplier", _footer_note(1, supplier)),
        ("Stock Name", _footer_note(1, (0.016, 0.045, 0.0, 0.06, 0.049, 0.0))),
    ]
    assert supplier[1] < drawing.INK_CELL_YMIN
    if fault == "lost_view":
        case.views.pop()
    elif fault == "view_owned_note":
        notes[0] = ("Supplier", _footer_note(0, supplier))
    elif fault == "note_off_sheet":
        notes[1] = ("Stock Name", _footer_note(1, (0.016, 0.005, 0.0, 0.06, 0.009, 0.0)))
    if fault is None:
        drawing._verify_supplier_layout(adapter, case.names, notes)
        cell = (region.xmin, drawing.INK_CELL_YMIN, region.xmax, region.ymax)
        assert checked == [(name, cell) for name in case.names]
    else:
        with pytest.raises(RuntimeError):
            drawing._verify_supplier_layout(adapter, case.names, notes)
