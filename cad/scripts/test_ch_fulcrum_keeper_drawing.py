"""Offline contracts for the fulcrum-keeper drawing."""

from __future__ import annotations

from pathlib import Path

import build_ch_fulcrum_keeper as part
import draw_ch_fulcrum_keeper as drawing
import ch_fulcrum_keeper_spec
import _config
from _drawing_registry import DRAWINGS_BY_NAME
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
    # face (1061.4 - 1036.2, the 2026-08-02 rederive contract) on a flat
    # seat: a 6.0 lug with a straight foot running OUTBOARD to x = 13.5.
    spec = ch_fulcrum_keeper_spec
    assert spec.SHAFT_AXIS_H == 25.2
    assert spec.CROWN_DIA == spec.KEEPER_WIDTH == 14.0
    assert 2.0 * spec.LUG_HALF_T == 6.0
    assert spec.FOOT_TIP_X == spec.LUG_HALF_T + spec.FOOT_L == 13.5
    assert spec.SCREW_X == 8.25
    assert spec.KEEPER_SCREW_Z_OFF == spec.KEEPER_Z_OFF + spec.SCREW_X == 82.25
    # Plain reamed slide-fit bore on the plain Ø6.35 shaft.
    assert spec.BORE_DIA == 6.35
    assert spec.BORE_DIA_BAND == (0.025, 0.010)  # (upper, lower)


def test_crown_set_screw_tap_stops_at_the_bore() -> None:
    spec = ch_fulcrum_keeper_spec
    assert spec.SET_SCREW_THREAD == "#1-72"
    assert spec.SET_SCREW_HOLE_SPEC.kind == "tapped"
    assert spec.SET_SCREW_HOLE_SPEC.end == "through_next"
    assert spec.CROWN_TOP_Y == spec.SHAFT_AXIS_H + spec.CROWN_DIA / 2.0
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="SetScrewTap"' in source
    # through_next stops at the bore only if the bore is already cut.
    assert source.index('"cut bore"') < source.index('name="SetScrewTap"')


def test_rule_12_worst_case_walls_and_thread() -> None:
    # Worst case of the printed bands (policy rule 12): >= 1.5D of full
    # crown thread, >= 1.5 web from the thread major to each lug face and
    # from the foot counterbore to the foot tip.
    spec = ch_fulcrum_keeper_spec
    assert spec.SET_SCREW_ENGAGEMENT_D >= 1.5
    assert spec.SET_SCREW_WEB_MM >= 1.5
    assert spec.FOOT_TIP_WALL_MM >= 1.5
    assert round(spec.SET_SCREW_WEB_MM, 3) == 1.813
    assert round(spec.FOOT_TIP_WALL_MM, 3) == 1.725
    # The web is only met with the lug and tap station at three places.
    assert spec.DRAWING_PRECISION["LugBody"]["LugThickness"] == 3
    assert spec.DRAWING_PRECISION["SetScrewReference"]["SetScrewLocation"] == 3


def test_tap_station_reference_sketch() -> None:
    assert part.REFERENCE_SKETCHES == ch_fulcrum_keeper_spec.REFERENCE_SKETCHES
    assert [row[0] for row in part.REFERENCE_LINES] == ["SetScrewReference"]
    _, plane, dimension, start, end, _, value, _ = part.REFERENCE_LINES[0]
    assert plane == "Front"
    assert dimension == "SetScrewLocation"
    # From the outer lug face (datum B) to the tap axis, on the crown top.
    assert start == (
        ch_fulcrum_keeper_spec.LUG_HALF_T,
        ch_fulcrum_keeper_spec.CROWN_TOP_Y,
    )
    assert end == (0.0, ch_fulcrum_keeper_spec.CROWN_TOP_Y)
    assert value == ch_fulcrum_keeper_spec.LUG_HALF_T


def test_keeper_tap_spec_for_the_frame() -> None:
    tap = ch_fulcrum_keeper_spec.KEEPER_TAP_SPEC
    assert (tap.kind, tap.size, tap.end) == ("tapped", "#4-40", "blind")
    assert tap.size == ch_fulcrum_keeper_spec.FOOT_SCREW_THREAD
    assert tap.overrides_mm["ThreadDepth"] < tap.depth_mm


def test_screw_hole_seats_the_frame_side_screw() -> None:
    hole = ch_fulcrum_keeper_spec.SCREW_HOLE_SPEC
    assert part.SCREW_HOLE_SPEC is hole
    assert hole.kind == "counterbore_fillister"
    assert hole.size == "#4"
    assert hole.overrides_mm == {
        "HoleDiameter": ch_fulcrum_keeper_spec.HOLE_DIA_MM,
        "CounterBoreDiameter": ch_fulcrum_keeper_spec.CBORE_DIA_MM,
        "CounterBoreDepth": ch_fulcrum_keeper_spec.CBORE_DEPTH_MM,
    }
    assert ch_fulcrum_keeper_spec.HOLE_DIA_MM > part.FRAME_SIDE_SHANK_DIA
    assert ch_fulcrum_keeper_spec.CBORE_DIA_MM > part.FRAME_SIDE_HEAD_DIA
    assert ch_fulcrum_keeper_spec.CBORE_DEPTH_MM == FRAME_SIDE_HEAD_H
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="FootScrewHole"' in source


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source
    assert "scale=(1, 1)" in source
    assert ch_fulcrum_keeper_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert "add_native_hole_callout(" in source


def test_outboard_lug_edge_resolver_filters_visible_geometry(monkeypatch) -> None:
    wrong_x = object()
    wrong_orientation = object()
    expected = object()
    endpoints = {
        wrong_x: (0.002, 0.008, 0.007, 0.002, 0.0252, 0.007),
        wrong_orientation: (0.003, 0.008, -0.007, 0.003, 0.008, 0.007),
        expected: (0.003, 0.008, 0.007, 0.003, 0.0252, 0.007),
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


def test_notes_cover_the_fit_the_tap_and_the_screw() -> None:
    notes = ch_fulcrum_keeper_spec.DRAWING_NOTES
    assert "BLACK OXIDE" in notes
    assert "REAM" in notes
    assert "MHA-CH-004" in notes
    assert "MHA-VN-055" in notes
    assert "MHA-VN-022" in notes
    assert "2 REQUIRED" in notes
    assert len(notes.splitlines()) <= 6


def test_keeper_is_one_body_with_no_ball() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "merge_result=False" not in source
    assert "Ball" not in source
    assert not hasattr(ch_fulcrum_keeper_spec, "BALL_DIA")


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
