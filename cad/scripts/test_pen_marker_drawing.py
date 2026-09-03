"""Offline contracts for the pen-marker drawing."""

from __future__ import annotations

import inspect
import math
from itertools import pairwise

from pathlib import Path

import build_pen_marker as part
import build_pen_assembly as assembly
import draw_pen_marker as drawing
import pen_marker_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = pen_marker_spec.SURFACE_FINISHES
    assert control.key == "barrel"
    assert control.roughness_um == 1.6
    assert math.isclose(
        control.face.half_angle_degrees,
        pen_marker_spec.BARREL_FLARE_HALF_ANGLE_DEG,
    )
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "barrel")' in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-marker.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-marker.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-marker_drawing.png")
    assert DRAWINGS_BY_NAME["pen_marker"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pen_marker_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_marker_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked
    assert (drawing.OVERALL_LENGTH, drawing.MAX_DIAMETER, drawing.TIP_NECK_Y) == (
        pen_marker_spec.OVERALL_LENGTH,
        pen_marker_spec.MAX_DIAMETER,
        pen_marker_spec.TIP_NECK_Y,
    )


def test_native_dimensions_cover_diameter_and_overall_length() -> None:
    # The profile chain carries station offsets, so the envelope dimensions are
    # drawing-native: maximum silhouette width and point-to-rear-point overall.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("_add_picked_dimension(") >= 3  # def + 2 call sites
    assert '("VERTEX", APEX)' in source
    assert '("VERTEX", END_POINT)' in source
    assert 'picks=(("EDGE", BARREL_MAX_TOP),),' in source
    assert "BARREL_MAX_BOTTOM" not in source
    assert "<MOD-DIAM>" in source
    assert 'setattr(display, "Diametric", True)' in source
    assert source.count("_display_as_diameter(") == 2  # def + the barrel dim
    assert "_add_axis_centerline(adapter, front" in source
    centerline_source = inspect.getsource(drawing._add_axis_centerline)
    assert "EditSheet()" in centerline_source
    assert "CreateCenterLine(" in centerline_source
    assert "SILHOUETTE" not in centerline_source


def test_authored_profile_matches_the_measured_envelope_and_silhouette() -> None:
    stations = pen_marker_spec.PROFILE_STATIONS
    assert stations[0] == (0.0, 0.0)
    assert stations[-1] == (123.11, 0.0)
    assert pen_marker_spec.OVERALL_LENGTH == 123.11
    assert pen_marker_spec.MAX_DIAMETER == 12.24
    assert len(stations) == 8  # sparse interpretation, not copied mesh topology
    assert all(a[0] < b[0] for a, b in pairwise(stations))
    radii = [radius for _axial_y, radius in stations]
    assert radii[:5] == sorted(radii[:5])
    assert radii[4:] == sorted(radii[4:], reverse=True)
    assert 2.0 * max(radii) == pen_marker_spec.MAX_DIAMETER
    assert pen_marker_spec.TIP_POINT_DIAMETER < pen_marker_spec.TIP_NECK_DIAMETER
    assert pen_marker_spec.TIP_NECK_DIAMETER < pen_marker_spec.SHOULDER_DIAMETER


def test_profile_volume_is_the_sum_of_its_conical_frusta() -> None:
    stations = pen_marker_spec.PROFILE_STATIONS
    expected = sum(
        math.pi * (y1 - y0) * (r0 * r0 + r0 * r1 + r1 * r1) / 3.0
        for (y0, r0), (y1, r1) in pairwise(stations)
    )
    assert math.isclose(pen_marker_spec.revolved_profile_volume_mm3(), expected)
    assert 10_000.0 < expected < 11_000.0
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "revolved_profile_volume_mm3()" in source
    assert "profile_pts = [(radius, axial_y)" in source


def test_every_authored_profile_station_is_equation_driven() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    for global_name in (
        "OverallLength",
        "TipPointY",
        "TipPointDia",
        "MaxDiameter",
        "TipNeckY",
        "TipNeckDia",
        "ShoulderY",
        "ShoulderDia",
        "BarrelFlareY",
        "RearTaperY",
        "RearTaperDia",
        "RearRoundY",
        "RearRoundDia",
    ):
        assert f'"{global_name}"' in source
    lowered = source.lower()
    assert all(suffix not in lowered for suffix in (".stl", ".step", ".obj", ".3mf"))
    notes = pen_marker_spec.DRAWING_NOTES
    assert "123.11" in notes and "12.24" in notes
    assert "PROJECT-AUTHORED" in notes
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in drawing_source


def test_writing_point_datum_and_open_groove_fit_are_preserved() -> None:
    marker_tip_z = assembly.MARKER_POS[2]
    assert math.isclose(
        marker_tip_z,
        assembly.PAPER_FRONT_Z - assembly.CLEARANCE,
        abs_tol=1e-9,
    )
    assert assembly._MARKER_BLOCK_RADIUS > assembly._GROOVE_HALF_CLEAR
    mouth_half_chord = math.sqrt(
        assembly._MARKER_BLOCK_RADIUS**2 - assembly.MARKER_AXIS_LOCAL_Y**2
    )
    assert mouth_half_chord <= assembly._GROOVE_HALF_CLEAR + 1e-9
    assert (
        assembly.MARKER_AXIS_LOCAL_Y + assembly._MARKER_BLOCK_RADIUS
        <= assembly.GROOVE_DEPTH - assembly.CLEARANCE
    )
    frame_window_bottom = assembly._FRAME_ORIGIN_LOCAL[1] + assembly.RAIL_END
    assert assembly._MARKER_BOTTOM_LOCAL_Y >= frame_window_bottom + assembly.CLEARANCE


def test_native_gdt_controls_tip_runout_and_barrel_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'characteristic="circular_runout"' in source
    assert 'datums=("A",)' in source
    assert source.count("add_surface_finish(") == 1
    tip_segment_midpoint = (
        drawing.APEX[0]
        + (pen_marker_spec.TIP_POINT_Y + pen_marker_spec.TIP_NECK_Y)
        / 2.0
        * drawing._AXIAL_SCALE,
        drawing.FRONT_CENTER[1]
        + (pen_marker_spec.TIP_POINT_DIAMETER + pen_marker_spec.TIP_NECK_DIAMETER)
        / 4.0
        * drawing._RADIAL_SCALE,
    )
    assert drawing.TIP_FLANK == tip_segment_midpoint


def test_view_scales_are_explicit_and_profile_is_rotated() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(2, 1)") == 1
    assert source.count("scale=(1, 1)") == 1
    assert pen_marker_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert "_rotate_view(adapter, front, -math.pi / 2.0" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pen-marker")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
