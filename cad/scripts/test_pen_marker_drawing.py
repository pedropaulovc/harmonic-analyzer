"""Offline contracts for the pen-marker drawing."""

from __future__ import annotations

import math
from pathlib import Path

import build_pen_marker as part
import draw_pen_marker as drawing
import pen_marker_spec
from _drawing_registry import DRAWINGS_BY_NAME


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
    assert (drawing.BARREL_DIA, drawing.BARREL_TOP_Y, drawing.CONE_H) == (
        pen_marker_spec.BARREL_DIA,
        pen_marker_spec.BARREL_TOP_Y,
        pen_marker_spec.CONE_H,
    )


def test_native_dimensions_cover_diameter_and_overall_length() -> None:
    # The revolve's sketch chain only carries radius / partial-length dims, so
    # the barrel diameter and overall length are drawing-native picked dims:
    # the Ø silhouette width plus the apex-vertex-to-end-face overall.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("_add_picked_dimension(") >= 3  # def + 2 call sites
    assert '("VERTEX", APEX)' in source
    assert "<MOD-DIAM>" in source
    assert source.count("_display_as_diameter(") == 2  # def + the barrel dim
    assert "referenced_model_cylindrical_face(" in source
    assert "face=barrel_face" in source
    assert "_add_axis_centerline" not in source


def test_cone_geometry_matches_the_notes() -> None:
    notes = pen_marker_spec.DRAWING_NOTES
    included = 2.0 * math.degrees(
        math.atan((pen_marker_spec.BARREL_DIA / 2.0) / pen_marker_spec.CONE_H)
    )
    assert round(included, 1) == 77.3
    assert "77.3" in notes
    assert "TIP" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_tip_runout_and_barrel_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'characteristic="circular_runout"' in source
    assert 'datums=("A",)' in source
    assert source.count("add_surface_finish(") == 1


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
