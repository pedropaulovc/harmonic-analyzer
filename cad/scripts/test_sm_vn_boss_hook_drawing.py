"""Offline manufacturing boundaries for the modified purchased anchor."""

import math
from types import SimpleNamespace

import pytest

import _stock_trim_drawing as trim_drawing
import _drawing_attachment
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
    minimum = spec.CHAMFER_WIDTH_MM - spec.CHAMFER_WIDTH_TOLERANCE_MM
    maximum = spec.CHAMFER_WIDTH_MM + spec.CHAMFER_WIDTH_TOLERANCE_MM
    assert anchor.thread_major_dia_mm - 2 * minimum < TAP_DRILL_MM[anchor.thread_size]
    # Include the adverse angular corner, not only the nominal 45-degree leg.
    maximum_axial = maximum / math.tan(
        math.radians(spec.CHAMFER_ANGLE_DEG - spec.CHAMFER_ANGLE_TOLERANCE_DEG)
    )
    short_shank = spec.SHANK_LENGTH_MM - spec.FINISHED_OVERALL_TOLERANCE_MM
    assert short_shank - maximum_axial > 17.0


@pytest.mark.parametrize(
    "fault", [None, "reference", "nominal", "tolerance", "precision", "missing"]
)
def test_drawing_accepts_general_controls_and_rejects_lost_control(monkeypatch, fault):
    """General is toleranced, unlike None; neither replaces a real driving size."""
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        trim_drawing, "dimension_name", lambda _adapter, annotation: annotation.name
    )
    annotations = []
    for name, nominal, band in (
        (
            "FinishedOverall",
            spec.FINISHED_OVERALL_MM / 1000,
            spec.FINISHED_OVERALL_TOLERANCE_MM / 1000,
        ),
        (
            "ChamferWidth",
            spec.CHAMFER_WIDTH_MM / 1000,
            spec.CHAMFER_WIDTH_TOLERANCE_MM / 1000,
        ),
        (
            "ChamferAngle",
            math.radians(spec.CHAMFER_ANGLE_DEG),
            math.radians(spec.CHAMFER_ANGLE_TOLERANCE_DEG),
        ),
    ):
        tolerance = SimpleNamespace(
            Type=spec.DIMENSION_TOLERANCE_TYPES[name],
            GetMinValue=lambda band=band: -band,
            GetMaxValue=lambda band=band: band,
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
        drawing._verify_controls(None, annotations)
    else:
        with pytest.raises(RuntimeError):
            drawing._verify_controls(None, annotations)


def _physical_eye(circle, face, view):
    curve = SimpleNamespace(IsCircle=lambda: True, CircleParams=circle)
    return SimpleNamespace(
        GetCurve=lambda: curve, GetFace=lambda: face, GetView=lambda: view,
    )


@pytest.mark.parametrize(
    "fault", (None, "missing", "outer", "bend", "wrong-center", "wrong-normal",
              "wrong-radius", "noncircle", "missing-curve"),
)
def test_supplier_eye_materializes_hlr_geometry_before_strict_discovery(monkeypatch, fault):
    """A deferred native repaint is not permission to choose a nearby circle."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    calls = []
    refreshed = False

    def refresh():
        nonlocal refreshed
        refreshed = True
        calls.append("refresh")
        # UpdateViewDisplayGeometry is native void, not a boolean success API.

    front = SimpleNamespace(UpdateViewDisplayGeometry=refresh)
    # Native diagnostic 322abecf0 saw these OD/bend contours, but no ID.
    outer = _physical_eye(
        (-4.4201138409138974e-11, -1.3548712585881306e-10, 0.0,
         0.0, 0.0, 1.0, 0.00879474964484956), object(), front,
    )
    bend = _physical_eye(
        (-0.0028691890547263683, -0.00879475, 0.0,
         0.0, 0.0, -1.0, 0.0004561892673619449), object(), front,
    )
    # This is the required physical circle, not a claimed native ID readback.
    eye = _physical_eye(
        (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, spec.SUPPLIER_EYE_ID_MM / 2000.0),
        object(), front,
    )
    visible = [outer, bend, eye]
    if fault in ("missing", "outer", "bend"):
        visible = {"missing": [], "outer": [outer], "bend": [bend]}[fault]
    elif fault in ("wrong-center", "wrong-normal", "wrong-radius"):
        circle = list(eye.GetCurve().CircleParams)
        circle[{"wrong-center": 0, "wrong-normal": 5, "wrong-radius": 6}[fault]] += 2e-8
        eye.GetCurve().CircleParams = tuple(circle)
    elif fault == "noncircle":
        eye.GetCurve().IsCircle = lambda: False
    elif fault == "missing-curve":
        eye.GetCurve = lambda: None

    def enumerate_visible(_view, kind, **_kwargs):
        assert kind == 4, "physical-ID discovery must not fall back to another entity type"
        calls.append("scan")
        return visible if refreshed else [outer, bend]

    monkeypatch.setattr(drawing, "visible_view_entities", enumerate_visible)
    selected = []
    monkeypatch.setattr(
        drawing, "_select_view_entity",
        lambda _adapter, _view, kind, _point, **kwargs: selected.append((kind, kwargs["entity"])),
    )
    display = SimpleNamespace(GetDimension2=lambda _index: SimpleNamespace(FullName="EyeID@native"))
    model = SimpleNamespace(
        AddDiameterDimension2=lambda *_args: display,
        ClearSelection2=lambda _all: None,
    )
    monkeypatch.setattr(drawing, "supplier_reference_dimension", lambda _adapter, value, **_kwargs: value)
    monkeypatch.setattr(drawing, "curate_stock_dimensions", lambda *_args, **_kwargs: [])
    if fault is None:
        refs = drawing._supplier_references(SimpleNamespace(currentModel=model), front)
        assert selected == [("SILHOUETTE", eye)]
        assert refs[0][1]["expected_mm"] == spec.SUPPLIER_EYE_ID_MM
    else:
        with pytest.raises(RuntimeError, match="no exact ID circular silhouette"):
            drawing._supplier_references(SimpleNamespace(currentModel=model), front)
        assert selected == []
    assert calls == ["refresh", "scan"]


def _settled_boss_eye_scene(monkeypatch):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(_drawing_attachment, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "assert_supplier_reference_dimension", lambda *_args, **_kwargs: None)
    state = SimpleNamespace(sheet="FINISHED")
    model = SimpleNamespace(ActivateSheet=lambda name: setattr(state, "sheet", name) or True)
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )
    views = {}
    refs_by_sheet = {}
    contracts = {}
    annotations = {}
    circle = (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, spec.SUPPLIER_EYE_ID_MM / 2000.0)
    face = object()
    eye = _physical_eye(circle, face, None)
    stale = SimpleNamespace(
        GetFace=lambda: None,
        GetCurve=lambda: pytest.fail("dereferenced a pre-rebuild counter-eye silhouette"),
    )
    for sheet, names, configuration in (
        ("FINISHED", ("EyeID", "SupplierThreadMajor"), "Default"),
        ("SUPPLIER-STOCK", ("SupplierNominalEyeOD", "SupplierNominalWire",
                            "SupplierStockShank", "SupplierStockOverall"),
         spec.SUPPLIER_STOCK_CONFIGURATION),
    ):
        displays = []
        refs = []
        for name in names:
            feature = (
                "native-eye" if name == "EyeID" else
                spec.SUPPLIER_THREAD_FEATURE if name == "SupplierThreadMajor" else
                spec.SUPPLIER_STOCK_FEATURE
            )
            key = f"{name}@{feature}@anchor.SLDPRT"
            native = SimpleNamespace(FullName=key, Tolerance=SimpleNamespace(Type=0), DrivenState=1)
            annotation = SimpleNamespace(
                entities=[eye] if name == "EyeID" else [],
                kinds=[46] if name == "EyeID" else [],
                IsDangling=lambda: False,
            )
            annotation.GetAttachedEntities3 = lambda annotation=annotation: tuple(annotation.entities)
            annotation.GetAttachedEntityTypes = lambda annotation=annotation: tuple(annotation.kinds)
            annotation.GetAttachedEntityCount3 = lambda annotation=annotation: len(annotation.entities)
            annotations[name] = annotation
            displays.append(SimpleNamespace(
                GetDimension2=lambda _index, native=native: native,
                GetAnnotation=lambda annotation=annotation: annotation,
            ))
            refs.append((key, {"label": name}, stale if name == "EyeID" else None))
        if sheet == "FINISHED":
            for name in drawing.FRONT_KEEP:
                native = SimpleNamespace(FullName=f"{name}@control@anchor.SLDPRT")
                displays.append(SimpleNamespace(GetDimension2=lambda _index, native=native: native))
        for index, display in enumerate(displays):
            following = displays[index + 1] if index + 1 < len(displays) else None
            display.GetNext5 = lambda following=following: following
        view = SimpleNamespace(
            Name=f"{sheet}-front", ReferencedConfiguration=configuration,
            UpdateViewDisplayGeometry=lambda: pytest.fail("post-save verifier refreshed geometry"),
            GetFirstDisplayDimension6=lambda displays=displays: displays[0],
        )
        views[sheet] = view
        refs_by_sheet[sheet] = refs
        contracts[sheet] = ((view.Name,), configuration)
    eye.GetView = lambda: views["FINISHED"]
    monkeypatch.setattr(drawing, "iter_views", lambda _adapter: (views[state.sheet],))
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    visible = [eye]
    monkeypatch.setattr(drawing, "visible_view_entities", lambda _view, kind, **_kwargs: visible if kind == 4 else ())
    return adapter, refs_by_sheet, contracts, eye, annotations["EyeID"], views, visible


@pytest.mark.parametrize(
    "fault", (None, "outer", "foreign-face", "missing", "extra", "wrong-type",
              "wrong-center", "wrong-normal", "wrong-radius", "missing-visible",
              "wrong-configuration", "wrong-view", "dangling", "count-mismatch"),
)
def test_boss_eye_reacquires_current_strict_physical_silhouette(monkeypatch, fault):
    adapter, refs, contracts, eye, annotation, views, visible = _settled_boss_eye_scene(monkeypatch)
    if fault == "outer":
        circle = list(eye.GetCurve().CircleParams)
        circle[6] = anchor.eye_od_mm / 2000.0
        annotation.entities = [_physical_eye(tuple(circle), eye.GetFace(), views["FINISHED"])]
    elif fault == "foreign-face":
        annotation.entities = [_physical_eye(eye.GetCurve().CircleParams, object(), views["FINISHED"])]
    elif fault == "missing":
        annotation.entities = []
    elif fault == "extra":
        annotation.entities.append(eye)
    elif fault == "wrong-type":
        annotation.kinds = [1]
    elif fault in ("wrong-center", "wrong-normal", "wrong-radius"):
        circle = list(eye.GetCurve().CircleParams)
        circle[{"wrong-center": 0, "wrong-normal": 5, "wrong-radius": 6}[fault]] += 2e-8
        eye.GetCurve().CircleParams = tuple(circle)
    elif fault == "missing-visible":
        visible.clear()
    elif fault == "wrong-configuration":
        views["FINISHED"].ReferencedConfiguration = spec.SUPPLIER_STOCK_CONFIGURATION
    elif fault == "wrong-view":
        eye.GetView = lambda: SimpleNamespace(Name="another-view")
    elif fault == "dangling":
        annotation.IsDangling = lambda: True
    elif fault == "count-mismatch":
        annotation.GetAttachedEntityCount3 = lambda: 2
    if fault is None:
        drawing._verify_supplier_references(adapter, refs, contracts)
    else:
        with pytest.raises(RuntimeError):
            drawing._verify_supplier_references(adapter, refs, contracts)
