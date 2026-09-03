"""Offline contracts for the pen-frame drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a brass stirrup
yoke carries no datums, frames or roughness symbols; the frame thickness is
a real dimension on the right view; the set-screw hole is a native callout
with two stations on the bottom view, where it is a visible circle (never a
hidden line); the one note is the rail schedule.
"""

from __future__ import annotations

from pathlib import Path

import build_pen_frame as part
import draw_pen_frame as drawing
import pen_frame_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-frame_drawing.png")
    assert DRAWINGS_BY_NAME["pen_frame"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pen_frame_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_frame_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.BOTTOM_KEEP)
    assert kept == marked == {"OuterSpanX", "OuterHeightDim"}
    assert drawing.RIGHT_KEEP == {} and drawing.BOTTOM_KEEP == {}


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pen_frame_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) == 1
    assert "RAILS: LEFT 3.25, RIGHT 4.00, ENDS 5.00 WIDE" in notes
    assert "WINDOW" in notes
    # The tapped hole lives on the bottom view (callout + stations): no
    # duplicated tap instruction, no thread class, no buried location.
    for banned in (
        "#4-40",
        "TAP",
        "12.25",
        "MID-DEPTH",
        "UNC",
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "WITHIN",
        "DATUM",
        "CDA",
        "X.XX",
    ):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_set_screw_hole_is_dimensioned_where_it_is_visible() -> None:
    # Policy rule 7: the hole's axis lies in the front-view plane, so its
    # callout and stations sit on the BOTTOM view (a visible circle with the
    # ASME centre mark), each station re-anchored to the arc centre.
    source = _source()
    assert '"*Bottom"' in source
    assert source.count("add_native_hole_callout(") == 1
    assert source.count("set_arc_endpoints_to_center(") == 2
    for label in (
        'label="set-screw width station"',
        'label="set-screw depth station"',
        'label="set-screw tap"',
    ):
        assert label in source, label
    assert "auto_center_marks(adapter, bottom" in source
    # The stations read from the trimmed left face and the front face.
    assert drawing.SCREW_STATION_X == 12.25
    assert drawing.SCREW_Z == 5.0
    # The one process fact the callout does not state rides its prefix.
    assert drawing.SET_SCREW_PROCESS == "TAP THRU THE BOTTOM RAIL ONLY:"
    assert "process=SET_SCREW_PROCESS" in source
    # Picks are projected through the view's own transform, scale-checked.
    assert "model_point_in_view(" in source
    assert source.count("= _model_frame(") == 2
    # SolidWorks also emits a generic "#4-40 Tapped Hole" note on the front
    # view.  It is redundant with the complete native bottom-view callout and
    # must be removed before the front outline can cross it.
    assert 'remove_notes_matching(adapter, "Tapped Hole")' in source
    # The complete two-line callout is parked well right of the bottom view,
    # with its anchor safely above the title-block top (~0.065 m).
    bottom_right = (
        drawing.BOTTOM_CENTER[0]
        + drawing.OUTER_WIDTH * drawing.VIEW_SCALE / 2000.0
    )
    assert drawing.BOTTOM_CALLOUT_XY[0] >= bottom_right + 0.045
    assert drawing.BOTTOM_CALLOUT_XY[1] >= 0.080


def test_frame_thickness_is_a_real_dimension_on_the_right_view() -> None:
    source = _source()
    assert 'label="frame thickness"' in source
    assert source.count("add_edge_dimension(") == 3
    assert drawing.FRAME_DEPTH == 10.0


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(pen_frame_spec, "GEOMETRIC_TOLERANCES_MM")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right, bottom):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = _source()
    assert "scale=(2, 1)" in source
    assert pen_frame_spec.FRONT_VIEW_NOTE == "FRONT VIEW SCALE 2:1"
    assert pen_frame_spec.RIGHT_VIEW_NOTE == "RIGHT-SIDE VIEW SCALE 2:1"
    assert pen_frame_spec.BOTTOM_VIEW_NOTE == "BOTTOM VIEW SCALE 2:1"
    # The isometric is NOT at the sheet scale, so its caption states 1:1.
    assert pen_frame_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert '"*Right"' in source
    # Third angle: the bottom view sits under the front view.
    assert drawing.BOTTOM_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.BOTTOM_CENTER[1] < drawing.FRONT_CENTER[1]


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert '"Bottom View Note": BOTTOM_VIEW_NOTE' in source
    import _config

    config = _config.parts("pen-frame")
    assert config["material"] == "C36000 free-machining brass"
    assert config["material"] == config["material_specification"]
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
