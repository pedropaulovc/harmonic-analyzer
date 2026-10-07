"""Offline manufacturing boundaries for the modified purchased anchor."""

import asyncio
import math
from types import SimpleNamespace

import pytest
from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus

import _config
import _drawing_marks as marks
import build_vn_boss_hook as part
import _stock_trim_drawing as trim_drawing
import vn_boss_hook_spec as spec
import draw_vn_boss_hook as drawing
from _hole_spec import TAP_DRILL_MM
from stock_anchor_geom import ANCHOR_9490T1 as anchor
from sm_summing_lever_spec import COUNTER_HOLE_SPEC


def test_finished_overall_preserves_factory_thread_datum():
    cut_end = anchor.eye_od_mm / 2 - spec.FINISHED_OVERALL_MM
    assert cut_end == pytest.approx(spec.TRIM.shank_end_y_mm)
    assert spec.TRIM.shank_length_mm == pytest.approx(19.05)
    assert spec.FINISHED_OVERALL_MM == pytest.approx(36.6395)


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


def test_direct_fit_matches_the_canonical_summing_lever_tap():
    assert _config.parts("sm-summing-lever")["number"] == "MHA-SM-003"
    assert COUNTER_HOLE_SPEC.kind == "tapped"
    assert COUNTER_HOLE_SPEC.size == anchor.thread_size == "#10-24"
    assert anchor.nut is None


@pytest.mark.parametrize("fault", [None, "reference", "nominal", "precision"])
def test_part_authors_precision_before_marking_cutting_controls(monkeypatch, fault):
    dimensions = {}
    displays = {}
    for name, (nominal, lower, upper) in drawing.EXPECTED_CONTROLS.items():
        tolerance = SimpleNamespace(Type=4, lower=lower, upper=upper)

        def set_values(lower, upper, tolerance=tolerance):
            tolerance.lower, tolerance.upper = lower, upper
            return True

        tolerance.SetValues = set_values
        tolerance.GetMinValue = lambda tolerance=tolerance: tolerance.lower
        tolerance.GetMaxValue = lambda tolerance=tolerance: tolerance.upper
        dimensions[name] = SimpleNamespace(
            DrivenState=2, SystemValue=nominal, Tolerance=tolerance
        )
        display = SimpleNamespace(precision=-2)

        def set_precision(primary, _dual, _primary_tol, _dual_tol, display=display):
            display.precision = primary + (1 if fault == "precision" else 0)
            return 0

        display.SetPrecision3 = set_precision
        display.GetPrimaryPrecision2 = lambda display=display: display.precision
        displays[name] = display
    if fault == "reference":
        dimensions["FinishedOverall"].DrivenState = 1
    elif fault == "nominal":
        dimensions["FinishedOverall"].SystemValue += 0.001
    monkeypatch.setattr(part, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(marks, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(part, "clear_dimensions_for_drawing", lambda _adapter: None)
    monkeypatch.setattr(
        part, "_named_dimension",
        lambda _adapter, _feature, name: (displays[name], dimensions[name]),
    )
    for setter in (
        "set_dimension_symmetric_tolerance",
        "set_dimension_symmetric_angular_tolerance",
    ):
        monkeypatch.setattr(part, setter, lambda *_args: None)
    monkeypatch.setattr(
        marks,
        "_iter_features",
        lambda _adapter: iter(
            SimpleNamespace(Name=name) for name in spec.DRAWING_PRECISION
        ),
    )
    monkeypatch.setattr(
        marks, "_com_invoke", lambda feature, _kind, _member: feature.Name
    )
    monkeypatch.setattr(
        marks,
        "_named_dimensions",
        lambda _adapter, _feature, names, **_kwargs: {
            name: (displays[name], dimensions[name]) for name in names
        },
    )
    marked = set()

    def mark(_adapter, feature, names):
        for name in names:
            assert displays[name].precision == spec.DRAWING_PRECISION[feature][name]
            marked.add(name)

    monkeypatch.setattr(part, "mark_dimensions_for_drawing", mark)
    properties = {}
    registry_instructions = "Changed registry instructions for this consumer test."
    monkeypatch.setattr(
        part._config, "parts",
        lambda _name: {"installation_notes": registry_instructions},
    )
    monkeypatch.setattr(
        part, "apply_drawing_properties",
        lambda _adapter, _name, extra: properties.update(extra),
    )
    if fault is None:
        part._manufacturing_controls(None)
        assert marked == set(drawing.EXPECTED_CONTROLS)
        for name, tolerance_type in spec.DIMENSION_TOLERANCE_TYPES.items():
            assert dimensions[name].Tolerance.Type == tolerance_type
        assert properties["Manufacturing Notes"] == (
            registry_instructions + "\n" + spec.DRAWING_NOTES
        )
    else:
        with pytest.raises(RuntimeError):
            part._manufacturing_controls(None)
        assert not marked


@pytest.mark.parametrize(
    "fault", [None, "reference", "nominal", "tolerance", "precision", "missing"]
)
def test_drawing_accepts_native_controls_and_rejects_lost_control(monkeypatch, fault):
    """Imported controls stay driving, toleranced, and at persisted model precision."""
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
            GetPrimaryPrecision2=lambda name=name: spec.DRAWING_PRECISION_BY_NAME[name],
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
            spec.DRAWING_PRECISION_BY_NAME["FinishedOverall"] + 1
        )
    elif fault == "missing":
        annotations.pop()
    if fault is None:
        drawing._verify_controls(None, annotations)
    else:
        with pytest.raises(RuntimeError):
            drawing._verify_controls(None, annotations)


@pytest.mark.parametrize(
    "fault", [None, "unresolved", "different", "overflow", "nonfinite", "rebuild"]
)
def test_custom_drawing_consumes_source_instructions_in_measured_cell(monkeypatch, fault):
    instructions = (
        "Registry-owned direct-joint instructions.\n"
        "Orient the eye.\n"
        "Secure the joint.\n"
        "Purchased geometry remains reference."
    )
    text = instructions.replace("\n", "\r\n")
    if fault == "unresolved":
        text = ""
    elif fault == "different":
        text = text.replace("Secure", "Omit")
    extent = [0.016, 0.065, 0.0, 0.210, 0.084, 0.0]
    if fault == "overflow":
        extent[1] = 0.060
    elif fault == "nonfinite":
        extent[0] = float("nan")
    note = SimpleNamespace(GetText=lambda: text, GetExtent=lambda: extent)
    model = SimpleNamespace(EditRebuild3=lambda: fault != "rebuild")

    async def open_model(_path):
        return AdapterResult(AdapterResultStatus.SUCCESS)

    async def finalize(*_args, **_kwargs):
        return {"drawing": "accepted"}

    adapter = SimpleNamespace(currentModel=model, open_model=open_model)
    monkeypatch.setattr(drawing, "SOURCE", SimpleNamespace(is_file=lambda: True))
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        drawing, "read_required_properties",
        lambda *_args, **_kwargs: {"Manufacturing Notes": instructions},
    )
    monkeypatch.setattr(
        drawing, "new_project_drawing", lambda *_args, **_kwargs: (model, None)
    )
    view = SimpleNamespace(UpdateViewDisplayGeometry=lambda: None)
    monkeypatch.setattr(drawing, "place_view", lambda *_args, **_kwargs: view)
    monkeypatch.setattr(trim_drawing, "end_detail", lambda *_args: view)
    for owner, name in (
        (drawing, "stamp_drawing_summary"),
        (drawing, "set_hidden_lines_visible"),
        (drawing, "set_hidden_lines_removed"),
        (drawing, "_verify_controls"),
        (trim_drawing, "position_detail_label"),
        (trim_drawing, "position_parent_detail_letter"),
    ):
        monkeypatch.setattr(owner, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        drawing, "curate_view_dimensions", lambda *_args, **_kwargs: []
    )
    linked_properties = []

    def linked_note(_adapter, property_name, *_args, **_kwargs):
        linked_properties.append(property_name)
        return note

    monkeypatch.setattr(drawing, "add_property_linked_note", linked_note)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    if fault is None:
        assert asyncio.run(drawing.build(adapter)) == {"drawing": "accepted"}
        assert "Manufacturing Notes" in linked_properties
    else:
        message = {
            "unresolved": "instructions did not resolve",
            "different": "instructions did not resolve",
            "overflow": "note exceeds its cell",
            "nonfinite": "no finite native extent",
            "rebuild": "rebuild boss-hook notes failed",
        }[fault]
        with pytest.raises(RuntimeError, match=message):
            asyncio.run(drawing.build(adapter))
