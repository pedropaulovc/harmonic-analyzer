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
from _release_artwork import bundle_path
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


def test_station_rim_picks_land_on_each_hole_and_off_the_head_mark() -> None:
    # The pick sits on the rim; the nearest engraved edge stands off it, so
    # the coordinate pick cannot take the head mark instead of the hole.
    engraving = _rings(part.ENGRAVING_DXF)
    picks = [
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


def test_section_a_crosses_the_plate_between_the_lettering_rows() -> None:
    # Both ends stand off the outline, so the arrows and letters print off
    # the plate (r2 review C3).
    outline = _rings(part.OUTLINE_DXF)[0]
    y = drawing.SECTION_Y
    assert drawing.SECTION_X_START < 0.0 < spec.PLATE_WIDTH < drawing.SECTION_X_END
    for x in (drawing.SECTION_X_START, drawing.SECTION_X_END):
        assert not dxf.point_in_ring(outline, (x, y))
    # The only engraved rings the line meets are the border's (pinstripe and
    # field edges, which span the plate); every letter and the ornament
    # stand at least a millimetre clear of it.
    for ring in _rings(part.ENGRAVING_DXF):
        xs = [x for x, _ in ring]
        ys = [y_ for _, y_ in ring]
        if min(ys) <= y <= max(ys):
            assert min(xs) < drawing.SECTION_FIELD_X, ring[0]
            assert max(xs) > spec.PLATE_WIDTH - drawing.SECTION_FIELD_X, ring[0]
        else:
            assert min(abs(min(ys) - y), abs(max(ys) - y)) >= 1.0, ring[0]


def test_section_a_crop_holds_the_border_the_groove_and_the_field() -> None:
    # The engraving DXF's closed rings nest: the pinstripe's outer edge, the
    # field ring (its inner edge), each letter and each letter's counter. A
    # point is cut to the engraving floor where an odd number of them holds it.
    outline = _rings(part.OUTLINE_DXF)[0]
    field = _rings(part.FIELD_DXF)[0]
    engraving = _rings(part.ENGRAVING_DXF)
    assert field in engraving
    y = drawing.SECTION_Y

    def engraved(x: float) -> bool:
        return sum(dxf.point_in_ring(ring, (x, y)) for ring in engraving) % 2 == 1

    face = (drawing.SECTION_FACE_X, y)
    assert dxf.point_in_ring(outline, face) and not dxf.point_in_ring(field, face)
    assert not engraved(drawing.SECTION_FACE_X)
    groove = (drawing.SECTION_GROOVE_X, y)
    assert not dxf.point_in_ring(field, groove) and engraved(drawing.SECTION_GROOVE_X)
    floor = (drawing.SECTION_FIELD_X, y)
    assert dxf.point_in_ring(field, floor) and not engraved(drawing.SECTION_FIELD_X)
    # The crop holds the plate's left edge and the whole thickness, and ends
    # on the field floor, not mid-groove.
    (x0, z0), (x1, z1) = drawing.SECTION_CROP
    assert x0 < 0.0 and z0 > 0.0 and z1 < -spec.PLATE_THICKNESS
    assert x1 > drawing.SECTION_FIELD_X
    end = (x1, y)
    assert dxf.point_in_ring(field, end) and not engraved(x1)


def test_section_a_break_line_closes_the_crops_open_end() -> None:
    # r4 review: the fragment's right end needs a break line. It stands on the
    # crop's right edge, from above the field floor to below the back face,
    # with one Z mid-thickness whose tips sit either side of that edge.
    (x0, z0), (x1, z1) = drawing.SECTION_CROP
    points = drawing.SECTION_BREAK
    assert points[0][0] == points[1][0] == points[-2][0] == points[-1][0] == x1
    assert points[0][1] > -print_spec.FIELD_DEPTH
    assert points[-1][1] < -spec.PLATE_THICKNESS
    assert z0 > points[0][1] and points[-1][1] > z1
    zs = [z for _x, z in points]
    assert zs == sorted(zs, reverse=True)
    tips = sorted(x for x, _z in points[2:4])
    assert tips[0] < x1 < tips[1]
    assert all(
        -spec.PLATE_THICKNESS < z < -print_spec.FIELD_DEPTH for _x, z in points[1:5]
    )
    # The break draws after the crop, once A-A sits on its centre.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    order = [
        source.index("    _crop_section(adapter, view)\n"),
        source.index("    _place_crop_on_center(adapter, view)\n"),
        source.index("    _sketch_section_break(adapter, view)\n"),
    ]
    assert order == sorted(order)


def test_section_a_dimensions_each_depth_on_its_own_line() -> None:
    # r2 review C2: the two depths shared one face arrow; each now stands on
    # its own station, both from the decorated face (z = 0).
    picks = drawing.SECTION_PICKS
    field, groove = picks["sunk field depth"], picks["engraving depth"]
    assert field["from"][1] == groove["from"][1] == 0.0
    assert field["to"][0] != groove["to"][0]
    assert field["text_xy"][0] != groove["text_xy"][0]
    for pick in picks.values():
        (_, z0), (_, z1) = pick["from"], pick["to"]
        assert math.isclose(z0 - z1, pick["expected_mm"])
        assert not pick["reference"] or pick is picks["floor under engraving"]
    # B3: the floor under the engraving chains below the engraving depth as
    # a reference, plate thickness less the engraving floor depth.
    floor = picks["floor under engraving"]
    assert floor["reference"] and floor["from"] == groove["to"]
    assert math.isclose(
        floor["expected_mm"], spec.PLATE_THICKNESS - print_spec.ENGRAVING_FLOOR_DEPTH
    )
    assert floor["callout"] == "FLOOR UNDER ENGRAVING"


def test_section_a_texts_and_caption_clear_each_other() -> None:
    # Measured r2 text blocks (8:1): a two-row value and callout is about
    # 8 mm tall and its callout row about 2.85 mm a character wide. Each
    # block is boxed left-aligned on its dimension line (as r2 printed),
    # right-aligned on it (as r4 printed the floor reference) and centred on
    # it, so no SOLIDWORKS placement can collide.
    def boxes(pick: dict) -> list[tuple[float, float, float, float]]:
        x, y = pick["text_xy"]
        width = 0.00285 * len(pick["callout"])
        return [
            (x, y - 0.004, x + width, y + 0.004),
            (x - width, y - 0.004, x, y + 0.004),
            (x - width / 2.0, y - 0.004, x + width / 2.0, y + 0.004),
        ]

    def overlaps(a: tuple, b: tuple) -> bool:
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    caption_x, caption_top = drawing.SECTION_CAPTION_XY
    caption = (caption_x - 0.023, caption_top - 0.016, caption_x + 0.023, caption_top)
    crop_low = drawing._section_xy(*drawing.SECTION_CROP[1])
    crop_high = drawing._section_xy(*drawing.SECTION_CROP[0])
    crop = (crop_high[0], crop_low[1], crop_low[0], crop_high[1])
    placed = {name: boxes(pick) for name, pick in drawing.SECTION_PICKS.items()}
    for name, candidates in placed.items():
        for box in candidates:
            assert box[2] < _BORDER[2] - 0.003, name
            assert not overlaps(box, caption), name
            assert not overlaps(box, crop), name
        for other, others in placed.items():
            clash = any(overlaps(a, b) for a in candidates for b in others)
            assert other == name or not clash, (name, other)
    assert not overlaps(caption, crop)
    assert caption[1] > _TITLE_BLOCK[1] + 0.003
    # Below the edge view, whose bottom is the face's bottom edge.
    assert caption[3] < drawing._BOTTOM - 0.005


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
    # The note block's rows fit the left half above the title band.
    assert 1 <= len(notes) <= 4
    assert all(len(note) <= 60 for note in notes), notes
    texts = [
        *notes,
        print_spec.FIELD_DEPTH_CALLOUT,
        print_spec.ENGRAVING_DEPTH_CALLOUT,
        print_spec.FLOOR_UNDER_ENGRAVING_CALLOUT,
        drawing.SCREW_HEAD_NOTE,
        *print_spec.DIMENSION_CALLOUTS.values(),
    ]
    assert not any(re.search(r"\d", text) for text in texts), texts
    # Each vendored contour by the exact path cut_release stages it at.
    for name in (part.OUTLINE_DXF, part.FIELD_DXF, part.ENGRAVING_DXF):
        assert f" PER {bundle_path(name.name)}" in print_spec.MANUFACTURING_NOTES


def test_texts_stand_inside_the_border_and_off_the_title_block() -> None:
    points = [
        *drawing.FRONT_KEEP.values(),
        *drawing.RIGHT_KEEP.values(),
        *(pick["text_xy"] for pick in drawing.FRONT_PICKS.values()),
        *(pick["text_xy"] for pick in drawing.SECTION_PICKS.values()),
        drawing.HOLE_CALLOUT_XY,
        drawing.NOTES_XY,
        drawing.SCREW_HEAD_NOTE_XY,
        drawing.ISO_NOTE_XY,
        drawing.SECTION_CENTER,
        drawing.SECTION_CAPTION_XY,
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
    # r2 audit: the plate height's dimension line crossed both "2X 4.1"
    # station texts, which print 1.5..14.6 mm left of their own lines.
    height_line_x = drawing.FRONT_PICKS["plate height"]["text_xy"][0]
    for station_x, _ in (
        drawing.FRONT_KEEP["S0Z"],
        drawing.FRONT_PICKS["top hole station"]["text_xy"],
    ):
        assert height_line_x < station_x - 0.0146 - 0.002


def test_part_registry_row_carries_the_title_block_facts() -> None:
    import _config

    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-FR-004"
    assert "brass" in str(row["material_specification"]).lower()
    assert row["finish"]
    assert int(row["quantity"]) == 1
