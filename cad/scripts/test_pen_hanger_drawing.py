"""Offline contracts for the pen-hanger drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a brazed strap and
guide block carries no datums, frames or roughness symbols; every size and
station is a dimension on the front or top view (the review of 2026-09-02
found the block envelope, strap thickness, channel and hole stations in the
notes); the three note lines are the bench fit, the brazed joint and the
strap foot's centring.
"""

from __future__ import annotations

from pathlib import Path

import build_pen_hanger as part
import draw_pen_hanger as drawing
import pen_hanger_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-hanger.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-hanger.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-hanger_drawing.png")
    assert DRAWINGS_BY_NAME["pen_hanger"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pen_hanger_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_hanger_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    # Front: block width AND height, the strap's two widths, rise and
    # right-edge lean (the two widths + the lean fix both sloping edges).
    assert set(drawing.FRONT_KEEP) == {
        "BlockWidth",
        "BlockDepth",
        "StrapBotWidth",
        "StrapTaperDx",
        "StrapTaperDy",
        "StrapTopRun",
    }
    # Top: the channel's two sides, a visible square there.
    assert set(drawing.TOP_KEEP) == {"ChannelWidth", "ChannelDepth"}


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pen_hanger_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) == 3
    # The mid-band block must stay clear of the isometric to its right.
    assert max(len(line) for line in lines) <= 68
    assert "SLIDING FIT ON THE PEN ROD" in notes  # the one fit, made at the bench
    assert "MATES WITH MHA-051" in notes  # the pen rod this print cannot show
    assert "SILVER-BRAZE" in notes
    assert "BACK FACES FLUSH" in notes  # the two faces that register
    assert "STRAP FOOT CENTRED ON THE BLOCK" in notes
    # Every number is on a view; a fully dimensioned print fixes handedness.
    assert not any(character.isdigit() for character in notes.replace("MHA-051", ""))
    for banned in (
        "DO NOT MIRROR",
        "#6-32",
        "DRILL",
        "TAP",
        "FROM BACK",
        "SQ CHANNEL",
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "MAX",
        "WITHIN",
        "AISI",
        "X.XX",
    ):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_hanger_hole_has_a_native_callout_and_two_stations() -> None:
    source = _source()
    assert source.count("add_native_hole_callout(") == 1
    assert 'label="hanger-screw tap"' in source
    # No process prefix on a tap (policy rule 7).
    assert "process=" not in source
    # 5.00 down from the strap's top edge, 8.50 in from its top-right corner
    # (the strap edges beside the hole are inclined), both to the arc centre.
    assert drawing.SCREW_TOP_STATION == 5.0
    assert drawing.SCREW_CORNER_STATION == 8.5
    assert 'entity_types=("VERTEX", "EDGE")' in source
    assert 'label="hanger-screw top station"' in source
    assert 'label="hanger-screw corner station"' in source
    assert "auto_center_marks(adapter, front" in source


def test_block_strap_and_channel_facts_are_dimensions_on_the_top_view() -> None:
    # The top view carries the block depth, the strap thickness and the
    # channel's two stations (the channel sides are marked model dims); the
    # picks are projected through the view's own transform, scale-checked.
    source = _source()
    for label in (
        'label="block depth"',
        'label="strap thickness"',
        'label="channel front station"',
        'label="channel side station"',
    ):
        assert label in source, label
    assert source.count("add_edge_dimension(") == 6
    assert source.count("set_arc_endpoints_to_center(") == 2
    assert "model_point_in_view(" in source
    assert source.count("= _model_frame(") == 1
    assert "curate_view_dimensions(adapter, top, keep=TOP_KEEP" in source


def test_front_view_lanes_nest_shortest_nearest() -> None:
    top = drawing._fy(drawing.STRAP_TOP_Y)
    # Above the strap top: the 8.50 hole station and the 5.00 lean chained
    # through the top-right corner (nearest), the 16.00 top run outside.
    assert drawing.SCREW_CORNER_STATION_TEXT_XY[1] == drawing.FRONT_KEEP["StrapTaperDx"][1]
    assert drawing.FRONT_KEEP["StrapTopRun"][1] > drawing.FRONT_KEEP["StrapTaperDx"][1] > top
    # Under the block: the 10.00 strap foot nearest, the 12.00 block outside.
    bottom = drawing._fy(-drawing.BLOCK_HALF)
    assert bottom > drawing.FRONT_KEEP["StrapBotWidth"][1] > drawing.FRONT_KEEP["BlockWidth"][1]
    # Left: the hole's top station nested inside the strap rise.
    assert drawing.FRONT_KEEP["StrapTaperDy"][0] < drawing.SCREW_TOP_STATION_TEXT_XY[0]
    # Block height right of the block.
    assert drawing.FRONT_KEEP["BlockDepth"][0] > drawing._fx(drawing.BLOCK_HALF)


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
    assert not hasattr(pen_hanger_spec, "GEOMETRIC_TOLERANCES_MM")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = _source()
    assert "scale=(2, 1)" in source
    assert "scale=(1, 1)" in source
    assert pen_hanger_spec.FRONT_VIEW_NOTE == "FRONT VIEW SCALE 2:1"
    assert pen_hanger_spec.TOP_VIEW_NOTE == "TOP VIEW SCALE 2:1"
    assert '"*Top"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pen-hanger")
    assert config["material"] == "AISI 1018 cold-finished steel"
    assert config["material"] == config["material_specification"]
    assert "steel" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
