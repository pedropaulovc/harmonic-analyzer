"""Focused source contracts for shared fastener drawing annotations."""

from __future__ import annotations

from pathlib import Path

import pytest

import _fastener_annotations as annotations


def _source() -> str:
    return Path(annotations.__file__).read_text(encoding="utf-8")


def test_sheet_point_conversion_uses_the_drawing_view_center(monkeypatch) -> None:
    import _drawing_common

    class View:
        Position = (0.190, 0.190)
        ScaleRatio = (6.0, 1.0)

    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, _kind: value)
    assert _drawing_common._sheet_to_view_sketch(
        object(), View(), (0.190, 0.2191), label="thread"
    ) == pytest.approx((0.0, 0.00485))


def test_unified_callout_drives_nominal_crest_diameter() -> None:
    major = annotations._nominal_thread_major_diameter_mm
    assert abs(major("#3-48 UNC") - 0.099 * 25.4) < 1e-12
    assert abs(major("#10-24 UNC") - 0.190 * 25.4) < 1e-12
    assert abs(major("1/4-20 UNC") - 6.35) < 1e-12


@pytest.mark.parametrize(
    "designation",
    (
        "",
        "#10-foo UNC",
        "#10-0 UNC",
        "1/4-20",
        "1/4-20 UNKNOWN",
        "1/4-20 UNC 2A",
    ),
)
def test_unified_callout_rejects_malformed_pitch_or_series(
    designation: str,
) -> None:
    with pytest.raises(ValueError, match="Unified thread designation"):
        annotations._nominal_thread_major_diameter_mm(designation)


def test_center_marks_do_not_emit_detached_extension_stubs() -> None:
    source = _source()
    assert "mark.UseDocDisplaySettings = False" in source
    assert "mark.ShowLines = False" in source
    assert "if bool(mark.UseDocDisplaySettings):" in source
    assert "if bool(mark.ShowLines):" in source


def test_end_diameter_leaders_stop_at_the_named_rim() -> None:
    source = _source()
    assert "display.ArrowSide = _ARROWS_OUTSIDE" in source
    assert "display.ArcExtensionLineOrOppositeSide = False" in source
    assert "display.SetSecondArrow(False, False)" in source
    assert "display.GetUseDocSecondArrow()" in source
    assert "display.GetSecondArrow()" in source


def test_external_thread_depiction_uses_thin_minor_and_thick_major_lines() -> None:
    source = _source()
    assert "major_diameter_mm, tpi = _unified_thread_geometry_mm(designation)" in source
    assert source.count("for side in (-1.0, 1.0):") == 3
    assert '"SILHOUETTE",\n            minor_pick' in source
    assert source.count("ddoc.HideEdge()") == 1
    assert "ddoc.SetLineWidth" not in source
    assert '("minor", minor_radius, minor_axis_end, _LINE_WEIGHT_THIN)' in source
    assert '("major", major_radius, major_axis_end, _LINE_WEIGHT_THICK)' in source
    assert "axis_end_xy[0] - ux * pitch_sheet" in source
    assert "chamfer_length = major_radius - minor_radius" in source
    assert "chamfer_start_sheet" in source
    assert "chamfer_end_sheet" in source
    assert "chamfer.Width = _LINE_WEIGHT_THICK" in source
    assert "segment.Color = _COLOR_BLACK" in source
    assert "segment.Style = _LINE_CONTINUOUS" in source
    assert "segment.Width = weight" in source


def test_occluded_shank_circle_uses_hidden_line_style() -> None:
    source = _source()
    assert "circle.Style = _LINE_HIDDEN" in source
    assert "circle.Width = _LINE_WEIGHT_THIN" in source
