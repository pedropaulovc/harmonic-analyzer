"""Offline contracts for the engraved nameplate's manufacturing drawing (#628)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _dxf_text as dxf
import build_fr_nameplate as part
import draw_fr_nameplate as drawing
import fr_nameplate_drawing_spec as print_spec
import fr_nameplate_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_band_mm
from vn_fillister_screw_spec import HEAD_DIA

# Sheet B landscape inner border and the title block's top-left corner (m).
_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
_TITLE_BLOCK = (0.216, 0.065)


def _rings(path: Path) -> list[dxf.Ring]:
    text = path.read_text(encoding="ascii")
    return [ring for ring, _ in dxf.read_lwpolylines(text[text.find("\nENTITIES\n") :])]


def test_registry_row_names_this_script_and_stem() -> None:
    row = DRAWINGS_BY_NAME["fr_nameplate"]
    assert row.part == "fr_nameplate"
    assert row.artifact_stem == part.PART_NAME
    assert row.script == Path(drawing.__file__).resolve()


def test_marked_set_is_exactly_what_the_sheet_keeps() -> None:
    # The build marks and gives places to DRAWING_DIMENSIONS; the sheet keeps
    # exactly their union, and every sheet-derived dimension has spec places.
    assert part.DRAWING_DIMENSIONS is print_spec.DRAWING_DIMENSIONS
    marked = set().union(*print_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert set(print_spec.DRAWING_PRECISION_BY_NAME) == marked
    derived = set(drawing.FRONT_PICKS) | set(drawing.SECTION_PICKS)
    assert derived == set(print_spec.DRAWING_REFERENCE_PRECISION)
    assert set(print_spec.DIMENSION_PREFIXES) <= marked
    assert set(print_spec.DIMENSION_CALLOUTS) <= marked


def test_no_model_band_every_dimension_prints_the_title_block_grade() -> None:
    assert model_toleranced_dimensions(part) == {}


def test_isometric_note_names_the_isometric_view_scale() -> None:
    scale = f"{drawing.ISO_SCALE[0]}:{drawing.ISO_SCALE[1]}"
    assert print_spec.ISOMETRIC_VIEW_NOTE == f"ISOMETRIC VIEW SCALE {scale}"
    assert drawing.SHEET_SCALE == (2.0, 1.0) and drawing.VIEW_SCALE == (2, 1)


def test_print_contract_matches_the_built_geometry() -> None:
    assert print_spec.SCREW_HOLE_DIA == part.SCREW_HOLE_DIA
    assert print_spec.FIELD_DEPTH == part.RECESS_DEPTH
    assert print_spec.ENGRAVING_FLOOR_DEPTH == part.RECESS_DEPTH + part.ENGRAVE_DEPTH
    # The sheet measures each far-edge station on the hole the spec's
    # ligament check judges (to the 0.0002 the traced stations differ by).
    for name, edge in (("right hole station", "right"), ("top hole station", "top")):
        expected = drawing.FRONT_PICKS[name]["expected_mm"]
        assert expected == pytest.approx(print_spec.HOLE_EDGE_STATIONS[edge], abs=1e-3)
    assert drawing.FRONT_PICKS["plate width"]["expected_mm"] == spec.PLATE_WIDTH
    assert drawing.FRONT_PICKS["plate height"]["expected_mm"] == spec.PLATE_HEIGHT


def test_each_hole_prints_one_station_value_per_edge_pair() -> None:
    # "2X" stands for two holes whose stations print the same number.
    places = print_spec.DRAWING_PRECISION["ScrewHoles"]
    bottom_left, bottom_right, top_left, top_right = spec.SCREW_XY
    assert round(bottom_left[0], places["S0X"]) == round(top_left[0], places["S0X"])
    assert round(bottom_left[1], places["S0Z"]) == round(bottom_right[1], places["S0Z"])
    right = [spec.PLATE_WIDTH - x for x in (bottom_right[0], top_right[0])]
    top = [spec.PLATE_HEIGHT - y for y in (top_left[1], top_right[1])]
    for values, label in ((right, "right hole station"), (top, "top hole station")):
        rounded = {
            round(v, print_spec.DRAWING_REFERENCE_PRECISION[label]) for v in values
        }
        assert len(rounded) == 1, label


def test_rim_picks_land_on_each_hole_and_off_the_head_mark() -> None:
    # The pick sits on the rim; the nearest engraved edge stands off it, so
    # the coordinate pick cannot take the head mark instead of the hole.
    engraving = _rings(part.ENGRAVING_DXF)
    picks = [
        drawing._rim(drawing.TOP_LEFT, drawing.HOLE_CALLOUT_RIM_DEGREES),
        drawing.FRONT_PICKS["right hole station"]["p1"],
        drawing.FRONT_PICKS["top hole station"]["p1"],
    ]
    for point in picks:
        nearest_hole = min(spec.SCREW_XY, key=lambda xy: math.dist(xy, point[:2]))
        assert math.isclose(math.dist(nearest_hole, point[:2]), drawing.HOLE_R)
        clearance = min(
            _segment_distance(point[:2], ring[i], ring[(i + 1) % len(ring)])
            for ring in engraving
            for i in range(len(ring))
        )
        assert clearance > 0.15, (point, clearance)


def _segment_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length if length else 0.0
    t = max(0.0, min(1.0, t))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def test_section_a_stations_cut_border_field_and_a_letter() -> None:
    # The engraving DXF's closed rings nest: the pinstripe's outer edge, the
    # field ring (its inner edge), each letter and each letter's counter. A
    # point is cut to the engraving floor where an odd number of them holds it.
    outline = _rings(part.OUTLINE_DXF)[0]
    field = _rings(part.FIELD_DXF)[0]
    engraving = _rings(part.ENGRAVING_DXF)
    assert field in engraving

    def engraved(x: float) -> bool:
        point = (x, drawing.SECTION_Y)
        return sum(dxf.point_in_ring(ring, point) for ring in engraving) % 2 == 1

    y = drawing.SECTION_Y
    assert not dxf.point_in_ring(outline, (drawing.SECTION_X_START, y))
    border = (drawing.SECTION_BORDER_X, y)
    assert dxf.point_in_ring(outline, border) and not dxf.point_in_ring(field, border)
    assert not engraved(drawing.SECTION_BORDER_X)
    floor = (drawing.SECTION_FIELD_X, y)
    assert dxf.point_in_ring(field, floor) and not engraved(drawing.SECTION_FIELD_X)
    letter = (drawing.SECTION_LETTER_X, y)
    assert dxf.point_in_ring(field, letter) and engraved(drawing.SECTION_LETTER_X)
    # The removed section ends on the field floor, not mid-groove.
    end = (drawing.SECTION_X_END, y)
    assert dxf.point_in_ring(field, end) and not engraved(drawing.SECTION_X_END)


def test_heads_stay_on_the_border_at_the_worst_printed_station() -> None:
    # The base is spotted through the plate, so the head follows the hole
    # wherever the shop drilled it inside the printed stations.
    outline = _rings(part.OUTLINE_DXF)[0]
    field = _rings(part.FIELD_DXF)[0]
    shift = math.hypot(
        print_spec.HOLE_STATION_SHIFT_MAX, print_spec.HOLE_STATION_SHIFT_MAX
    )
    reach = HEAD_DIA / 2.0 + shift
    for hx, hy in spec.SCREW_XY:
        for degrees in range(0, 360, 2):
            angle = math.radians(degrees)
            point = (hx + reach * math.cos(angle), hy + reach * math.sin(angle))
            assert dxf.point_in_ring(outline, point), (hx, hy, point)
            assert not dxf.point_in_ring(field, point), (hx, hy, point)


def test_hole_ligaments_and_engraving_floor_at_the_printed_worst_case() -> None:
    assert min(print_spec.HOLE_LIGAMENTS_WORST.values()) >= print_spec.LIGAMENT_FLOOR
    floor = (
        spec.PLATE_THICKNESS
        - printed_band_mm(3)
        - (print_spec.ENGRAVING_FLOOR_DEPTH + printed_band_mm(3))
    )
    assert math.isclose(print_spec.ENGRAVING_FLOOR_MIN, floor)
    assert floor > 0.5


def test_notes_and_callouts_carry_no_numbers_and_stay_short() -> None:
    notes = print_spec.MANUFACTURING_NOTES.splitlines()
    assert 1 <= len(notes) <= 4
    texts = [
        *notes,
        print_spec.FIELD_DEPTH_CALLOUT,
        print_spec.ENGRAVING_DEPTH_CALLOUT,
        *print_spec.DIMENSION_CALLOUTS.values(),
    ]
    assert not any(re.search(r"\d", text) for text in texts), texts
    for name in (part.OUTLINE_DXF, part.FIELD_DXF, part.ENGRAVING_DXF):
        assert name.name.upper() in print_spec.MANUFACTURING_NOTES


def test_texts_stand_inside_the_border_and_off_the_title_block() -> None:
    points = [
        *drawing.FRONT_KEEP.values(),
        *drawing.RIGHT_KEEP.values(),
        *(pick["text_xy"] for pick in drawing.FRONT_PICKS.values()),
        *(pick["text_xy"] for pick in drawing.SECTION_PICKS.values()),
        drawing.HOLE_CALLOUT_XY,
        drawing.NOTES_XY,
        drawing.ISO_NOTE_XY,
        drawing.SECTION_CENTER,
        drawing.ISO_CENTER,
    ]
    for x, y in points:
        assert _BORDER[0] + 0.005 < x < _BORDER[2] - 0.005, (x, y)
        assert _BORDER[1] < y < _BORDER[3] - 0.005, (x, y)
        assert not (x > _TITLE_BLOCK[0] and y < _TITLE_BLOCK[1] + 0.008), (x, y)
    # Dimension texts stand off the plate face, never on the engraving.
    left, bottom = drawing._front_xy(0.0, 0.0)
    right, top = drawing._front_xy(spec.PLATE_WIDTH, spec.PLATE_HEIGHT)
    for x, y in [
        *drawing.FRONT_KEEP.values(),
        *(pick["text_xy"] for pick in drawing.FRONT_PICKS.values()),
        drawing.HOLE_CALLOUT_XY,
    ]:
        assert not (
            left - 0.003 < x < right + 0.003 and bottom - 0.003 < y < top + 0.003
        )


def test_part_registry_row_carries_the_title_block_facts() -> None:
    import _config

    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-FR-004"
    assert "brass" in str(row["material_specification"]).lower()
    assert row["finish"]
    assert int(row["quantity"]) == 1
