"""Offline manufacturing boundaries for the modified purchased anchor."""

import math
from types import SimpleNamespace

import pytest

import _stock_trim_drawing as trim_drawing
import _drawing_view_display as view_display
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


@pytest.mark.parametrize(
    "fault", (None, "missing", "outer", "bend", "foreign-visible", "wrong-path",
              "missing-curve", "noncircle", "wrong-radius", "stuck-hlv", "stuck-hlr"),
)
def test_supplier_eye_requires_real_mode_regeneration_and_preserves_controls(monkeypatch, fault):
    """An immediate repaint alone cannot restore post-annotation native ID edges."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(view_display, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", view_display.set_hidden_lines_removed)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    owner = object()
    source = SimpleNamespace(
        GetPathName=lambda: str(drawing.SOURCE.resolve()),
        FeatureByName=lambda name: owner if name == "Wire" else None,
    )
    surface = SimpleNamespace(
        IsTorus=lambda: True,
        TorusParams=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0,
                     anchor.eye_mean_radius_mm / 1000, anchor.wire_dia_mm / 2000),
    )
    face = SimpleNamespace(GetSurface=lambda: surface, GetFeature=lambda: owner)
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(trim_drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    controls, control_displays = [], []
    for name, (nominal, lower, upper) in drawing.EXPECTED_CONTROLS.items():
        dimension = SimpleNamespace(
            DrivenState=2, SystemValue=nominal,
            Tolerance=SimpleNamespace(
                Type=spec.DIMENSION_TOLERANCE_TYPES[name],
                GetMinValue=lambda lower=lower: lower,
                GetMaxValue=lambda upper=upper: upper,
            ),
        )
        display_control = SimpleNamespace(
            GetDimension2=lambda _index, dimension=dimension: dimension,
            GetText=lambda _index: "",
            GetPrimaryPrecision2=lambda name=name: spec.DIMENSION_PRECISION[name],
        )
        control_displays.append(display_control)
        controls.append(SimpleNamespace(
            name=name, GetSpecificAnnotation=lambda display=display_control: display,
        ))
    for index, display_control in enumerate(control_displays):
        following = control_displays[index + 1] if index + 1 < len(control_displays) else None
        display_control.GetNext5 = lambda following=following: following
    state = SimpleNamespace(mode=2, hlv_seen=False, regenerated=False, materialized=False)
    front = SimpleNamespace(Name="finished-front", ReferencedDocument=source)
    front.GetFirstDisplayDimension6 = lambda: control_displays[0]

    def set_mode(_parent, mode, *_args):
        if (fault == "stuck-hlv" and mode == 1) or (fault == "stuck-hlr" and mode == 2):
            return False
        previous = state.mode
        state.mode = mode
        if previous == 2 and mode == 1:
            state.hlv_seen = True
        if previous == 1 and mode == 2 and state.hlv_seen:
            state.regenerated = True
        state.materialized = False
        return previous != mode

    def refresh():
        state.materialized = state.regenerated and state.mode == 2

    front.SetDisplayMode4 = set_mode
    front.GetDisplayMode2 = lambda: state.mode
    front.UpdateViewDisplayGeometry = refresh

    def contour(diameter, attached_face=face, center=(0.0, 0.0, 0.0)):
        curve = SimpleNamespace(
            IsCircle=lambda: True,
            CircleParams=(*center, 0.0, 0.0, 1.0, diameter / 2000),
        )
        return SimpleNamespace(
            GetCurve=lambda: curve, GetFace=lambda: attached_face, GetView=lambda: front,
        )

    eye = contour(spec.SUPPLIER_EYE_ID_MM)
    outer = contour(anchor.eye_od_mm)
    bend = contour(0.9123785, center=(-0.002869189, -0.00879475, 0.0))
    visible = [outer, bend, eye]
    if fault in ("missing", "outer", "bend"):
        visible = {"missing": [], "outer": [outer], "bend": [bend]}[fault]
    elif fault == "foreign-visible":
        face.GetFeature = lambda: object()
    elif fault == "wrong-path":
        source.GetPathName = lambda: "D:/foreign.SLDPRT"
    elif fault == "missing-curve":
        eye.GetCurve = lambda: None
    elif fault == "noncircle":
        eye.GetCurve().IsCircle = lambda: False
    elif fault == "wrong-radius":
        values = list(eye.GetCurve().CircleParams)
        values[6] += 2e-8
        eye.GetCurve().CircleParams = tuple(values)

    def enumerate_visible(view, kind, **_kwargs):
        assert view is front
        assert kind == 4, "ID discovery must never fall back to edges"
        # Refresh alone does not regenerate edges after imported annotations.
        return visible if state.materialized else [outer, bend]

    monkeypatch.setattr(drawing, "visible_view_entities", enumerate_visible)
    selected = []
    monkeypatch.setattr(
        drawing, "_select_view_entity",
        lambda _adapter, _view, kind, _point, **kwargs: selected.append((kind, kwargs["entity"])),
    )
    display = SimpleNamespace(GetDimension2=lambda _index: SimpleNamespace(FullName="EyeID@native"))
    model = SimpleNamespace(
        AddDiameterDimension2=lambda *_args: display, ClearSelection2=lambda _all: None,
    )
    adapter = SimpleNamespace(
        currentModel=model, swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )
    monkeypatch.setattr(drawing, "supplier_reference_dimension", lambda _adapter, value, **_kwargs: value)
    monkeypatch.setattr(drawing, "curate_stock_dimensions", lambda *_args, **_kwargs: [])
    drawing._verify_controls(adapter, controls)
    if fault is None:
        refs = drawing._supplier_references(adapter, front)
        assert selected == [("SILHOUETTE", eye)]
        assert refs == [("EyeID@native", {
            "label": "EyeID", "expected_mm": spec.SUPPLIER_EYE_ID_MM, "units": "in",
            "precision": drawing.SUPPLIER_REFERENCE_PRECISION["EyeID"],
            "presentation": "diameter",
            "fraction_denominator": drawing.SUPPLIER_FRACTION_DENOMINATOR,
        })]
        assert state.mode == 2 and state.regenerated and state.materialized
    else:
        with pytest.raises(RuntimeError):
            drawing._supplier_references(adapter, front)
        assert selected == []
    surviving = []
    current = front.GetFirstDisplayDimension6()
    while current is not None:
        surviving.append(current)
        current = current.GetNext5()
    assert len(surviving) == len(drawing.FRONT_KEEP)
    assert all(actual is expected for actual, expected in zip(surviving, control_displays))
    drawing._verify_controls(adapter, controls)
