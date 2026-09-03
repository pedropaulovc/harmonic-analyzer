"""Offline contracts for the pen-marker drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a turned marker
clamped in the v-block groove carries no datum, frame or roughness symbol,
its notes are two lines of process fact, and the tip allowance is a leader
note on the apex (machinist review 2026-09-02).
"""

from __future__ import annotations

import math
from pathlib import Path

import build_pen_marker as part
import draw_pen_marker as drawing
import pen_marker_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


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
    source = _source()
    assert source.count("_add_picked_dimension(") >= 3  # def + 2 call sites
    assert '("VERTEX", APEX)' in source
    assert "<MOD-DIAM>" in source
    assert source.count("_display_as_diameter(") == 2  # def + the barrel dim
    assert "_add_axis_centerline(adapter, front" in source


def test_tip_allowance_is_a_leader_note_on_the_apex() -> None:
    # Machinist review 2026-09-02: the 110.00 and 5.00 end at the drawn sharp
    # apex while a flat is permitted, so the allowance is attached to the apex
    # and says the dimensions run to the theoretical sharp.
    note = pen_marker_spec.TIP_NOTE
    assert "THEORETICAL SHARP" in note
    assert "<MOD-DIAM>0.20 MAX" in note
    assert "TIP FLAT" not in pen_marker_spec.DRAWING_NOTES
    source = _source()
    assert "text=TIP_NOTE" in source
    assert "entity_xy=APEX" in source
    assert 'entity_type="VERTEX"' in source
    # The cone-height lane sits above the barrel so the leader has a clear run
    # up to the apex.
    assert drawing.FRONT_KEEP["ConeH"][1] > drawing.FRONT_CENTER[1]
    assert drawing.TIP_NOTE_XY[1] < drawing.FRONT_CENTER[1]


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pen_marker_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    included = 2.0 * math.degrees(
        math.atan((pen_marker_spec.BARREL_DIA / 2.0) / pen_marker_spec.CONE_H)
    )
    assert round(included, 1) == 77.3
    assert "77.3" in notes
    assert "ONE SETTING" in notes
    for banned in ("UOS", "DIMENSIONS IN", "+/-", "DATUM", "RUNOUT", "X.XX", "MAX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3-5: a clamped marker is not on the
    # GD&T allowlist and nothing runs on its barrel.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(pen_marker_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(pen_marker_spec, "GEOMETRIC_CONTROLS")
    assert pen_marker_spec.SURFACE_FINISHES == ()
    assert "surface_finishes=SURFACE_FINISHES" in Path(part.__file__).read_text(
        encoding="utf-8"
    )
    assert "roughness_ra=" not in source


def test_view_scales_are_explicit_and_profile_is_rotated() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = _source()
    assert source.count("scale=(2, 1)") == 1
    assert source.count("scale=(1, 1)") == 1
    assert pen_marker_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert "_rotate_view(adapter, front, -math.pi / 2.0" in source


def test_hidden_lines_stay_on_in_the_profile_view() -> None:
    source = _source()
    assert "set_hidden_lines_visible(adapter, front)" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pen-marker")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
