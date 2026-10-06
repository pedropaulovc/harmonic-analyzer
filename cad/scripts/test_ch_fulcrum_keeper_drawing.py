"""Offline contracts for the fulcrum-keeper drawing."""

from __future__ import annotations

from pathlib import Path

import build_ch_fulcrum_keeper as part
import draw_ch_fulcrum_keeper as drawing
import ch_fulcrum_keeper_spec
import _config
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from vn_frame_side_screw_spec import HEAD_H as FRAME_SIDE_HEAD_H


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-fulcrum-keeper.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-fulcrum-keeper.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-fulcrum-keeper_drawing.png")
    assert DRAWINGS_BY_NAME["ch_fulcrum_keeper"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set
    # are BOTH the shared spec's map.
    assert part.DRAWING_DIMENSIONS is ch_fulcrum_keeper_spec.DRAWING_DIMENSIONS
    marked = set().union(*ch_fulcrum_keeper_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked


def test_geometry_matches_the_top_frame_contract() -> None:
    # The keeper exists to hold the fulcrum shaft 25.2 above the rail top
    # face (1061.4 - 1036.2, the 2026-08-02 rederive contract); its underside
    # relief must clear the 4.5-proud corner-boss land.
    assert ch_fulcrum_keeper_spec.SHAFT_AXIS_H == 25.2
    assert ch_fulcrum_keeper_spec.RELIEF_H > 4.5
    # The Ø6.35 shaft end must float in the ball bore with real clearance.
    assert ch_fulcrum_keeper_spec.BORE_DIA > 6.35
    assert ch_fulcrum_keeper_spec.BALL_DIA > ch_fulcrum_keeper_spec.BORE_DIA


def test_screw_hole_seats_the_frame_side_screw() -> None:
    hole = ch_fulcrum_keeper_spec.SCREW_HOLE_SPEC
    assert part.SCREW_HOLE_SPEC is hole
    assert hole.kind == "counterbore_fillister"
    assert hole.size == "#8"
    assert hole.overrides_mm == {
        "HoleDiameter": ch_fulcrum_keeper_spec.HOLE_DIA_MM,
        "CounterBoreDiameter": ch_fulcrum_keeper_spec.CBORE_DIA_MM,
        "CounterBoreDepth": ch_fulcrum_keeper_spec.CBORE_DEPTH_MM,
    }
    assert ch_fulcrum_keeper_spec.HOLE_DIA_MM > part.FRAME_SIDE_SHANK_DIA
    assert ch_fulcrum_keeper_spec.CBORE_DIA_MM > part.FRAME_SIDE_HEAD_DIA
    assert ch_fulcrum_keeper_spec.CBORE_DEPTH_MM == FRAME_SIDE_HEAD_H


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.ORTHOGRAPHIC_SCALE == (2, 1)
    assert drawing.ISOMETRIC_SCALE == (1, 1)


def test_manufacturing_note_lane_clears_sheet_and_dimension_keepouts() -> None:
    left, bottom, right, top = drawing.MANUFACTURING_NOTE_FIELD
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    inner_border = 0.0127
    assert left >= inner_border + 0.004
    assert bottom >= inner_border + 0.004
    assert right + 0.002 <= template.title_block_left_m - 0.004
    assert top + 0.004 <= drawing.FRONT_KEEP["PadLen"][1]
    assert drawing.FRONT_CENTER[0] == drawing.TOP_CENTER[0]
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1]


def test_datum_a_remains_associated_with_the_foot_seat() -> None:
    edge_x, edge_y = drawing.DATUM_A_EDGE_XY
    symbol_x, symbol_y = drawing.DATUM_A_SYMBOL_XY
    assert drawing._front_x(-drawing.FOOT_REACH) <= edge_x <= drawing._front_x(0.0)
    assert edge_y == drawing.SEAT_EDGE_Y
    assert symbol_x == edge_x
    assert symbol_y < edge_y


def test_outboard_lug_edge_resolver_filters_visible_geometry(monkeypatch) -> None:
    wrong_x = object()
    wrong_orientation = object()
    expected = object()
    endpoints = {
        wrong_x: (0.002, 0.0048, 0.007, 0.002, 0.0252, 0.007),
        wrong_orientation: (0.003, 0.0252, -0.007, 0.003, 0.0252, 0.007),
        expected: (0.003, 0.0048, 0.007, 0.003, 0.0252, 0.007),
    }

    class FakeSpan:
        def __init__(self) -> None:
            self.attributes = {}

        def set_attribute(self, key, value) -> None:
            self.attributes[key] = value

    span = FakeSpan()
    monkeypatch.setattr(
        drawing._telemetry.trace, "get_current_span", lambda context=None: span
    )
    resolver = drawing._visible_outboard_lug_edge.__wrapped__
    monkeypatch.setattr(
        drawing,
        "visible_view_entities",
        lambda view, entity_kind, *, label: [
            wrong_x,
            wrong_orientation,
            expected,
        ],
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda entity, interface: entity)
    monkeypatch.setattr(
        drawing,
        "_edge_endpoint_key",
        lambda adapter, edge: endpoints[edge],
    )

    assert resolver(object(), object()) is expected
    assert span.attributes["matched"] == 1



def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    assert "FootScrewHole" not in part.DRAWING_DIMENSIONS
    marked = set().union(*part.DRAWING_DIMENSIONS.values())
    assert not {name for name in marked if "Hole" in name}


def test_parts_registry_row() -> None:
    config = _config.parts("ch-fulcrum-keeper")
    assert config["number"] == "MHA-CH-007"
    assert config["material"] == "Plain Carbon Steel"
    assert "black oxide" in str(config["finish"])
    assert int(config["quantity"]) == 2
